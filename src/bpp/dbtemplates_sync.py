"""Pomocnicze funkcje do synchronizacji szablonów dbtemplates z dyskiem.

Główny problem: ``dbtemplates`` cache'uje treść szablonu (oraz marker
``notfound``, gdy szablonu nie ma w bazie) w backendzie cache Django. Po
usunięciu wiersza ``Template`` z bazy loader nadal serwuje STARĄ treść z
cache, dopóki klucze nie zostaną wyczyszczone. ``remove_cached_template`` z
dbtemplates czyści tylko klucze dla *site'ów* powiązanych z szablonem — gdy
szablon nie ma site'ów, nie czyści nic. Stąd ta jawna, oparta o nazwę,
inwalidacja.
"""

from dbtemplates.utils.cache import (
    cache,
    get_cache_key,
    get_cache_notfound_key,
)
from django.template.engine import Engine
from django.template.loaders.cached import Loader as CachedLoader


def wyczysc_cache_dbtemplate(name):
    """Usuń z cache treść i marker ``notfound`` szablonu o danej nazwie oraz
    odpowiadający wpis w Django ``CachedLoader``.

    Po tym wywołaniu kolejne ``get_template(name)`` trafi cache-miss i
    przeczyta źródło na nowo (z bazy, a jeśli wiersza już nie ma — z dysku)."""
    cache.delete(get_cache_key(name))
    cache.delete(get_cache_notfound_key(name))

    for loader in Engine.get_default().template_loaders:
        if isinstance(loader, CachedLoader):
            loader.get_template_cache.pop(loader.cache_key(name), None)


def usun_dbtemplate_i_przebuduj(name, modele, *, flush=False, log=None):
    """Skasuj wiersz dbtemplate ``name`` (render spadnie na dysk) i oznacz
    ``modele`` do przebudowy denorma. Współdzielone przez migrację i komendę
    ``drop_dbtemplate``.

    GUARD: kasuje TYLKO gdy nazwa ma odpowiednik na dysku
    (``disk_template_source(name) is not None``). Wiersz DB-only bez pliku na
    dysku zostaje nietknięty — inaczej ``nazwa_szablonu`` zostałaby dyndająca i
    ``get_template`` rzucałby ``TemplateDoesNotExist`` przy każdym renderze /
    flushu denorma. Zwraca ``False`` gdy pominięto (guard), ``True`` gdy
    skasowano lub wiersza nie było mimo pliku na dysku.

    ``flush=True`` → synchroniczny ``denorms.flush()`` (komenda deployowa chce
    odświeżyć od ręki); ``flush=False`` → tylko oznaczenie dirty (async kolejka
    ``denorm`` dokończy — użycie w migracji)."""
    from dbtemplates.models import Template

    from bpp.util import rebuild_instances_of_models
    from bpp.util.dbtemplates_disk import disk_template_source

    log = log or (lambda msg: None)

    if disk_template_source(name) is None:
        log(
            f"[guard] '{name}' nie ma pliku na dysku — NIE kasuję wiersza "
            f"dbtemplate (zostawiam, by nie zdyndać nazwy_szablonu)."
        )
        return False

    tpl = Template.objects.filter(name=name).first()
    if tpl is not None:
        log(f"[usuwam dbtemplate '{name}'] backup treści:\n{tpl.content}")
        tpl.delete()
        # Cache dbtemplates nie znika sam (delete modelem historycznym nie
        # odpala sygnałów); czyścimy synchronicznie jak drop_dbtemplate.
        wyczysc_cache_dbtemplate(name)

    if modele:
        rebuild_instances_of_models(list(modele))
        if flush:
            from denorm import denorms

            denorms.flush()

    return True
