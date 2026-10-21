"""Rozstrzyganie szablonów a baza danych (regresja #766).

BPP stawia ``dbtemplates.loader.Loader`` przed loaderami dyskowymi, więc
``get_template()`` potrafi sięgnąć po ``django_template``. Loader ogranicza
to zbiorem znanych nazw (``DBTEMPLATES_SKIP_UNKNOWN_NAMES``), ale ten zbiór
jest globalny dla PROCESU i kasowany przy każdym zapisie/usunięciu wiersza
``Template`` — czyli w pełnym przebiegu suity jego stan zależy od tego, co
wcześniej przeleciało na tym samym workerze xdist.

Skutkiem był #766: dwa testy z ``django_bpp/tests/test_auth_server.py``
padały w pełnym przebiegu (``RuntimeError: Database access not allowed``
z wnętrza ``get_template``), a przechodziły w izolacji i na shardowanym CI.

Guard siedzi w ``src/conftest.py``; te testy pilnują jego założeń.
"""

import pytest
from django.conf import settings
from django.template.loader import get_template

NAZWA_SZABLONU_Z_DYSKU = "auth_server/login.html"


def test_loader_dbtemplates_pyta_o_znane_nazwy():
    """``DBTEMPLATES_SKIP_UNKNOWN_NAMES`` musi być włączone.

    Guard z ``src/conftest.py`` opiera się na tym, że loader przed pójściem
    do bazy pyta ``known_names()``. Z wyłączoną flagą loader odpytywałby
    bazę bezwarunkowo i guard przestałby chronić — ten test zamienia taką
    zmianę konfiguracji w czerwony wynik zamiast w powrót #766 kilka
    miesięcy później.
    """
    assert settings.DBTEMPLATES_SKIP_UNKNOWN_NAMES is True


def test_cache_nazw_jest_zimny_na_starcie_testu():
    """Żaden test nie dziedziczy zbioru nazw szablonów po poprzedniku.

    Kontrakt fixture'u ``_zeruj_cache_nazw_dbtemplates``. Ciepły cache
    z nazwami z bazy INNEGO testu (wycofanej rollbackiem) sprawia, że
    loader idzie do bazy po nazwę, której już nie ma — albo pomija
    nadpisanie, które w bieżącym teście naprawdę istnieje.
    """
    from dbtemplates.utils import names

    assert names._names is None


def test_szablon_z_dysku_rozstrzyga_sie_przy_zimnym_cache_i_bez_bazy():
    """Bez ``django_db`` i z zimnym cache nazw szablon z dysku musi się
    wyrenderować.

    To jest właściwy test regresji #766. Zimny cache to stan po KAŻDYM
    zapisie/usunięciu wiersza ``Template`` (sygnały w
    ``dbtemplates/models.py``), więc w pełnym przebiegu trafia się
    nieprzewidywalnie. Bez guardu ``get_template`` leci stąd do bazy
    i dostaje ``RuntimeError: Database access not allowed`` — niezależnie
    od kolejności testów, bo cache zerujemy tu jawnie.
    """
    from dbtemplates.utils.names import invalidate_known_names

    invalidate_known_names()

    html = get_template(NAZWA_SZABLONU_Z_DYSKU).render({})

    assert "Logowanie do BPP" in html


@pytest.mark.django_db
def test_z_baza_nadpisanie_szablonu_wierszem_w_bazie_dalej_dziala():
    """Guard nie może uciszyć dbtemplates tam, gdzie baza JEST dostępna.

    Druga strona poprawki: „pusty zbiór znanych nazw" obowiązuje wyłącznie
    wtedy, gdy pytest-django blokuje bazę. Test z ``django_db`` musi nadal
    dostawać treść z wiersza ``Template``, a nie z dysku.
    """
    from dbtemplates.models import Template

    Template.objects.create(name=NAZWA_SZABLONU_Z_DYSKU, content="TREŚĆ Z BAZY")

    assert get_template(NAZWA_SZABLONU_Z_DYSKU).render({}) == "TREŚĆ Z BAZY"
