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
