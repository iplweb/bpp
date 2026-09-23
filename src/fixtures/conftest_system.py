"""System data fixtures: typy_odpowiedzialnosci, jezyki, charaktery_formalne, etc."""

import json
import os
import random

import pytest
from model_bakery import baker
from rest_framework.test import APIClient

from bpp import const
from bpp.fixtures import get_openaccess_data
from bpp.models import Zewnetrzna_Baza_Danych
from bpp.models.autor import Funkcja_Autora, Tytul
from bpp.models.system import (
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
)
from bpp.util import get_fixture


def fixture(name):
    path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../bpp", "fixtures", name)
    )
    with open(path, "rb") as f:
        return json.load(f)


@pytest.fixture(scope="function")
def typ_odpowiedzialnosci_autor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", nazwa="autor", typ_ogolny=const.TO_AUTOR
    )[0]


@pytest.fixture(scope="function")
def typ_odpowiedzialnosci_redaktor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="red.", nazwa="redaktor", typ_ogolny=const.TO_REDAKTOR
    )[0]


@pytest.fixture(scope="function")
def typy_odpowiedzialnosci(db):
    Typ_Odpowiedzialnosci.objects.all().delete()
    for elem in fixture("typ_odpowiedzialnosci_v2.json"):
        Typ_Odpowiedzialnosci.objects.get_or_create(pk=elem["pk"], **elem["fields"])
    return {x.skrot: x for x in Typ_Odpowiedzialnosci.objects.all()}


@pytest.fixture(scope="function")
def tytuly():
    # Lookup po kluczu naturalnym (skrot jest unique), NIGDY po pk — inaczej
    # wiersz o tym samym skrocie pod innym pk => INSERT => IntegrityError.
    for elem in fixture("tytul.json"):
        fields = dict(elem["fields"])
        skrot = fields.pop("skrot")
        Tytul.objects.get_or_create(skrot=skrot, defaults=fields)


@pytest.fixture(scope="function")
def jezyki():
    """Języki referencyjne — komplet, z ``kod_bcp47`` i ``skrot_crossref``.

    Test, który potrzebuje języków, bierze tę fixturę. NIE zakładaj, że są
    w bazie „same z siebie": owszem, sieją je migracje danych (``0022`` polski
    i angielski, ``0035`` resztę z fixture ``jezyk.json``, ``0480`` kody
    BCP 47), ale transakcyjny flush (``TransactionTestCase``) truncate'uje
    tabele, a migracje już się nie powtórzą — kolejny test na tym workerze
    zobaczyłby pustkę.

    ``pol.``/``ang.`` zakładamy po kluczu naturalnym (skrót), resztę bierzemy
    z tego samego fixture co migracja, a kody BCP 47 z mapowania migracji
    ``0480`` — żeby wartości nie dryfowały między testami a produkcją.
    ``skrot_crossref`` ustawiamy tylko tutaj: kolumna jest ``unique``, a na
    produkcji wypełnia ją wyłącznie migracja ``0410`` i tylko dla polskiego.
    """
    from importlib import import_module

    for skrot, nazwa in (("pol.", "polski"), ("ang.", "angielski")):
        Jezyk.objects.get_or_create(skrot=skrot, defaults={"nazwa": nazwa})

    for pola in get_fixture("jezyk").values():
        pola = dict(pola)
        Jezyk.objects.get_or_create(skrot=pola.pop("skrot"), defaults=pola)

    kody = import_module("bpp.migrations.0480_cerif_mapowania_slownikow")
    kody._uzupelnij(Jezyk, "kod_bcp47", kody.JEZYKI)

    for skrot, crossref in (("pol.", "pl"), ("ang.", "en")):
        Jezyk.objects.filter(skrot=skrot).update(skrot_crossref=crossref)

    return {jezyk.skrot: jezyk for jezyk in Jezyk.objects.all()}


@pytest.fixture(scope="function")
def rodzaje_jednostek(db):
    """Rodzaje jednostek zasiane migracjami danych: ``Standard``, ``Wydział``,
    ``Koło naukowe`` — wraz z atrybutami dokładanymi przez kolejne migracje.

    Test pytający o rodzaj po nazwie bierze tę fixturę. Wiersze są w baseline,
    ale transakcyjny flush (``TransactionTestCase``) truncate'uje tabele,
    a migracje lecą raz, przy zakładaniu bazy — kolejny test na tym samym
    workerze zobaczyłby pustkę. Wołamy oryginalne, idempotentne funkcje
    migracji, żeby wartości nie dryfowały między testami a produkcją.
    """
    from importlib import import_module

    from django.apps import apps as django_apps

    from bpp.models import RodzajJednostki

    for modul, funkcja in (
        ("bpp.migrations.0449_seed_rodzajjednostki", "seed"),
        ("bpp.migrations.0454_faza_b_i1", "seed_pokazuj_strukture_podjednostek"),
        (
            "bpp.migrations.0464_rodzajjednostki_autor_moze_afiliowac",
            "wydzial_bez_afiliacji",
        ),
    ):
        getattr(import_module(modul), funkcja)(django_apps, None)

    return {rodzaj.nazwa: rodzaj for rodzaj in RodzajJednostki.objects.all()}


@pytest.fixture(scope="function")
def instytucje_finansujace(db):
    """Słownik instytucji finansujących (NCN, NCBR, MNiSW, …) z migracji 0486.

    Ta sama klasa zależności co ``rodzaje_jednostek``: dane pochodzą z migracji
    danych, więc po transakcyjnym flushu nie wracają same.
    """
    from importlib import import_module

    from django.apps import apps as django_apps

    from bpp.models import Instytucja_Finansujaca

    import_module("bpp.migrations.0486_seed_instytucje_finansujace").seed(
        django_apps, None
    )

    return {x.akronim: x for x in Instytucja_Finansujaca.objects.all()}


@pytest.fixture(scope="function")
def crossref_mappery(db):
    """Wiersze ``Crossref_Mapper`` (mapowanie typów Crossref → charakter) —
    seedowane migracją 0467. Nie zakładaj baseline: reużywa idempotentnej
    funkcji seedującej migracji (``get_or_create``), więc bezpieczne zawsze.
    """
    from importlib import import_module

    from django.apps import apps as django_apps

    from bpp.models import Crossref_Mapper

    import_module(
        "bpp.migrations.0467_seed_crossref_mapper_rows"
    ).seed_crossref_mapper_rows(django_apps, None)
    return Crossref_Mapper.objects.all()


@pytest.fixture(scope="function")
def rzeczowniki(db):
    """Wiersze ``Rzeczownik`` (override lematów UCZELNIA/WYDZIAL/JEDNOSTKA) —
    normalnie seedowane migracjami. Nie zakładaj baseline: zasiej z
    ``DOMYSLNE_LEMATY`` (jedyne źródło prawdy dla lematów) przez idempotentny
    ``get_or_create``. Bieżący model ma tylko ``uid`` + ``m`` (mianownik);
    liczba mnoga liczona jest inflekcją, więc wystarczy mianownik.
    """
    from bpp.models import Rzeczownik
    from bpp.nazwy import DOMYSLNE_LEMATY

    for uid, m in DOMYSLNE_LEMATY.items():
        Rzeczownik.objects.get_or_create(uid=uid, defaults={"m": m})
    return Rzeczownik.objects.all()


@pytest.fixture(scope="function")
def first_run_wizard_state(db):
    """Singleton ``FirstRunWizardState`` (pk=1) — normalnie seedowany migracją
    ``first_run_wizard.0001`` (``get_or_create(pk=1)``). Wiersz NIE ma receivera
    ``post_migrate``, więc transakcyjny sąsiad (flush → ``TRUNCATE``) wymiata go
    i już nie wraca. Bez tego wiersza middleware first-run-wizarda w
    ``_install_is_finished`` trafia na ``state is None`` i przerywa PRZED ścieżką
    naprawczą (``mark_completed``) — ``completed_at`` nigdy się nie stempluje, a
    widoki ``/setup/`` zwracają 302 (redirect na krok) zamiast 404 (setup
    zamknięty). Fixtura odtwarza wiersz idempotentnie (jak migracja); samo jego
    ISTNIENIE wystarcza — backfill ``completed_at`` robi już middleware, gdy
    wszystkie kroki są kompletne.
    """
    from first_run_wizard.models import FirstRunWizardState

    FirstRunWizardState.objects.get_or_create(pk=1)
    return FirstRunWizardState.load()


@pytest.fixture(scope="function")
def charaktery_formalne():
    Charakter_Formalny.objects.all().delete()
    # Lookup po kluczu naturalnym (skrot jest unique), NIGDY po pk (w JSON-ie
    # pk bywa null) — inaczej wiersz o tym samym skrocie/nazwie pod innym pk
    # => INSERT => IntegrityError.
    for elem in fixture("charakter_formalny.json"):
        fields = dict(elem["fields"])
        skrot = fields.pop("skrot")
        Charakter_Formalny.objects.get_or_create(skrot=skrot, defaults=fields)

    chf_ksp = Charakter_Formalny.objects.get(skrot="KSP")
    chf_ksp.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    chf_ksp.charakter_ogolny = const.CHARAKTER_OGOLNY_KSIAZKA
    chf_ksp.charakter_sloty = const.CHARAKTER_SLOTY_KSIAZKA
    chf_ksp.nazwa_w_primo = "Książka"
    chf_ksp.save()

    chf_roz = Charakter_Formalny.objects.get(skrot="ROZ")
    chf_roz.rodzaj_pbn = const.RODZAJ_PBN_ROZDZIAL
    chf_ksp.charakter_ogolny = const.CHARAKTER_OGOLNY_ROZDZIAL
    chf_roz.charakter_sloty = const.CHARAKTER_SLOTY_ROZDZIAL
    chf_roz.save()

    return {x.skrot: x for x in Charakter_Formalny.objects.all()}


@pytest.fixture(scope="function")
def ksiazka_polska(charaktery_formalne):
    return charaktery_formalne["KSP"]


@pytest.fixture(scope="function")
def charakter_formalny_rozdzial(charaktery_formalne):
    return charaktery_formalne["ROZ"]


@pytest.fixture(scope="function")
def artykul_w_czasopismie(charaktery_formalne):
    return charaktery_formalne["AC"]


@pytest.fixture(scope="function")
def typy_kbn():
    for elem in fixture("typ_kbn.json"):
        Typ_KBN.objects.get_or_create(pk=elem["pk"], **elem["fields"])


@pytest.fixture(scope="function")
def statusy_korekt():
    for elem in fixture("status_korekty.json"):
        Status_Korekty.objects.get_or_create(pk=elem["pk"], **elem["fields"])
    return {status.nazwa: status for status in Status_Korekty.objects.all()}


@pytest.fixture(scope="function")
def przed_korekta(statusy_korekt):
    return statusy_korekt["przed korektą"]


@pytest.fixture(scope="function")
def po_korekcie(statusy_korekt):
    return statusy_korekt["po korekcie"]


@pytest.fixture(scope="function")
def w_trakcie_korekty(statusy_korekt):
    return statusy_korekt["w trakcie korekty"]


@pytest.fixture(scope="function")
def funkcje_autorow():
    for elem in get_fixture("funkcja_autora").values():
        Funkcja_Autora.objects.get_or_create(**elem)


@pytest.fixture(scope="function")
def standard_data(
    typy_odpowiedzialnosci,
    tytuly,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    funkcje_autorow,
):
    class StandardData:
        @classmethod
        def clean(self):
            for model in (
                Typ_Odpowiedzialnosci,
                Tytul,
                Jezyk,
                Charakter_Formalny,
                Typ_KBN,
                Status_Korekty,
                Funkcja_Autora,
            ):
                model.objects.all().delete()

    return StandardData


@pytest.fixture(scope="function")
def openaccess_data():
    from django.contrib.contenttypes.models import ContentType

    for model_name, skrot, nazwa in get_openaccess_data():
        klass = ContentType.objects.get_by_natural_key("bpp", model_name).model_class()
        klass.objects.get_or_create(nazwa=nazwa, skrot=skrot)


@pytest.fixture
def denorms():
    from denorm import denorms

    yield denorms


@pytest.fixture
def api_client(client):
    return APIClient()


@pytest.fixture
def baza_wos():
    return Zewnetrzna_Baza_Danych.objects.get_or_create(
        nazwa="Web of Science", skrot="WOS"
    )[0]


def gen_kod_dyscypliny_func():
    top = random.randint(1, 8)
    bottom = random.randint(1, 500)
    return f"{top}.{bottom}"


baker.generators.add(
    "bpp.models.dyscyplina_naukowa.KodDyscyplinyField", gen_kod_dyscypliny_func
)
