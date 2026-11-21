"""System data fixtures: typy_odpowiedzialnosci, jezyki, charaktery_formalne, etc."""

import functools
import itertools
import json
import os

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


# Szybkie ścieżki fixtur słownikowych
# ===================================
#
# Słowniki (tytuły, typy KBN, statusy korekt, języki) siedzą w baseline, więc
# w typowym teście fixtura nie ma nic do zrobienia — a mimo to dawniej
# wysyłała po jednym ``get_or_create`` na wpis (``tytuly``: 31 SELECT-ów,
# ~16 ms na KAŻDE wywołanie; łącznie ~45 s czasu workerów w pełnej suicie).
# Teraz: jeden SELECT całej tabeli, porównanie w Pythonie i dawne
# ``get_or_create`` WYŁĄCZNIE dla wpisów, których brakuje albo które się
# różnią (np. po TRUNCATE testu transakcyjnego). Wynik w bazie — identyczny.
# Wzorce z plików JSON czytamy raz na proces (``functools.cache``); są
# krotkami, więc nikt ich przypadkiem nie zmodyfikuje.


@functools.cache
def _wzorzec_wg_pk(nazwa_pliku):
    """``((pk, ((pole, wartosc), ...)), ...)`` z pliku fixture Django."""
    return tuple(
        (elem["pk"], tuple(elem["fields"].items())) for elem in fixture(nazwa_pliku)
    )


def _zapewnij_wg_pk(model, nazwa_pliku):
    """Odpowiednik ``get_or_create(pk=..., **fields)`` dla każdego wpisu
    pliku — z jednym SELECT-em, gdy baza już ma te wiersze. Zwraca
    ``{pk: obiekt}`` całej tabeli."""
    obiekty = {o.pk: o for o in model.objects.all()}
    zmiana = False
    for pk, pola in _wzorzec_wg_pk(nazwa_pliku):
        obj = obiekty.get(pk)
        if obj is None or any(
            getattr(obj, model._meta.get_field(pole).attname) != wartosc
            for pole, wartosc in pola
        ):
            model.objects.get_or_create(pk=pk, **dict(pola))
            zmiana = True
    if zmiana:
        obiekty = {o.pk: o for o in model.objects.all()}
    return obiekty


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
    """Typy odpowiedzialności z ``typ_odpowiedzialnosci_v2.json``.

    Szybka ścieżka: baseline ma dokładnie te same wiersze (pk + wszystkie
    pola), więc wystarczy jeden SELECT i porównanie. Dawne bezwarunkowe
    ``delete()`` + 9 × ``get_or_create`` to było 97 zapytań (z savepointami
    easyaudit) na KAŻDE wywołanie — ~19 s czasu workerów w pełnej suicie —
    i przy okazji kaskadowo kasowało rekordy innych fixtures wskazujące na
    te typy. Pełne odtworzenie zostaje, gdy stan bazy różni się od wzorca
    (np. po TRUNCATE testu transakcyjnego albo gdy test coś zmienił).
    """
    pola = ("skrot", "nazwa", "typ_ogolny")
    wzorzec = {
        (elem["pk"], *(elem["fields"][f] for f in pola))
        for elem in fixture("typ_odpowiedzialnosci_v2.json")
    }
    obiekty = list(Typ_Odpowiedzialnosci.objects.all())
    stan = {(o.pk, *(getattr(o, f) for f in pola)) for o in obiekty}
    if stan != wzorzec:
        Typ_Odpowiedzialnosci.objects.all().delete()
        for elem in fixture("typ_odpowiedzialnosci_v2.json"):
            Typ_Odpowiedzialnosci.objects.get_or_create(pk=elem["pk"], **elem["fields"])
        obiekty = list(Typ_Odpowiedzialnosci.objects.all())
    return {x.skrot: x for x in obiekty}


@pytest.fixture(scope="function")
def tytuly():
    # Lookup po kluczu naturalnym (skrot jest unique), NIGDY po pk — inaczej
    # wiersz o tym samym skrocie pod innym pk => INSERT => IntegrityError.
    # Szybka ścieżka: tylko brakujące skróty idą do ``get_or_create``.
    wzorzec = _wzorzec_wg_pk("tytul.json")
    istniejace = set(Tytul.objects.values_list("skrot", flat=True))
    for _pk, pola in wzorzec:
        fields = dict(pola)
        skrot = fields.pop("skrot")
        if skrot not in istniejace:
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

    kody = import_module("bpp.migrations.0480_cerif_mapowania_slownikow")
    podstawowe = (("pol.", "polski"), ("ang.", "angielski"))
    crossref = (("pol.", "pl"), ("ang.", "en"))

    # Szybka ścieżka: gdy wszystkie skróty już są (typowo — baseline), jeden
    # SELECT + UPDATE tylko tych wierszy, w których wartość faktycznie się
    # różni (zwykle jeden: baseline nie ma ``skrot_crossref`` dla ``ang.``).
    # Dawniej każde wywołanie to ~20 zapytań, w tym 11 UPDATE-ów — prawie
    # wszystkie niezmieniające ani jednego wiersza. ``skrot`` jest unique,
    # więc UPDATE po pk to to samo, co dawne ``filter(skrot=...).update()``.
    jezyki = {jezyk.skrot: jezyk for jezyk in Jezyk.objects.all()}
    if all(skrot in jezyki for skrot, _ in podstawowe) and all(
        pola["skrot"] in jezyki for pola in get_fixture("jezyk").values()
    ):
        zmiany = [
            (jezyki[skrot], "kod_bcp47", kod)
            for skrot, kod in kody.JEZYKI.items()
            if skrot in jezyki and jezyki[skrot].kod_bcp47 in ("", None)
        ] + [
            (jezyki[skrot], "skrot_crossref", kod)
            for skrot, kod in crossref
            if jezyki[skrot].skrot_crossref != kod
        ]
        for jezyk, pole, wartosc in zmiany:
            Jezyk.objects.filter(pk=jezyk.pk).update(**{pole: wartosc})
            setattr(jezyk, pole, wartosc)
        return jezyki

    for skrot, nazwa in podstawowe:
        Jezyk.objects.get_or_create(skrot=skrot, defaults={"nazwa": nazwa})

    for pola in get_fixture("jezyk").values():
        pola = dict(pola)
        Jezyk.objects.get_or_create(skrot=pola.pop("skrot"), defaults=pola)

    kody._uzupelnij(Jezyk, "kod_bcp47", kody.JEZYKI)

    for skrot, kod in crossref:
        Jezyk.objects.filter(skrot=skrot).update(skrot_crossref=kod)

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


_CHF_POLA_POMIJANE = {"skrot", "lft", "rght", "tree_id", "level"}


@functools.cache
def _charaktery_formalne_stan_docelowy():
    """Stan docelowy tabeli: ``{skrot: {attname: wartosc}}``.

    Wartości z ``charakter_formalny.json``, a dla pól, których JSON nie ma,
    wartości domyślne modelu. To jest dokładnie to, co dawało dawne
    ``delete()`` + ``get_or_create(defaults=...)`` — testy są pisane pod ten
    stan, a NIE pod stan z baseline, gdzie migracje danych ustawiły np.
    ``rodzaj_pbn``/``charakter_ogolny`` także innym charakterom.

    Liczone raz na proces (``functools.cache``) — wynik jest tylko czytany.
    """
    domyslne = {
        f.attname: f.get_default()
        for f in Charakter_Formalny._meta.concrete_fields
        if not f.primary_key and f.name not in _CHF_POLA_POMIJANE
    }
    cel = {}
    for elem in fixture("charakter_formalny.json"):
        fields = dict(elem["fields"])
        skrot = fields.pop("skrot")
        cel[skrot] = {**domyslne, **fields}

    cel["KSP"].update(
        rodzaj_pbn=const.RODZAJ_PBN_KSIAZKA,
        charakter_ogolny=const.CHARAKTER_OGOLNY_KSIAZKA,
        charakter_sloty=const.CHARAKTER_SLOTY_KSIAZKA,
        nazwa_w_primo="Książka",
    )
    cel["ROZ"].update(
        rodzaj_pbn=const.RODZAJ_PBN_ROZDZIAL,
        charakter_ogolny=const.CHARAKTER_OGOLNY_ROZDZIAL,
        charakter_sloty=const.CHARAKTER_SLOTY_ROZDZIAL,
    )
    return cel


@pytest.fixture(scope="function")
def charaktery_formalne():
    """Charaktery formalne z ``charakter_formalny.json``.

    Szybka ścieżka: baseline ma już te same 27 rekordów (wszystkie jako
    korzenie drzewa MPTT), więc tylko dopasowujemy ich pola jednym
    ``bulk_update`` — bez kasowania i ponownego wstawiania, które przy
    MPTT przestawiało drzewo (``UPDATE ... tree_id = tree_id + 1``) przy
    każdym rekordzie. W profilu pełnej suity dawna wersja zjadała ~13%
    czasu workerów (spec-testcontainers-pg-szybciej-2026-11.md).

    Wolna ścieżka (dawne zachowanie): gdy zestaw skrótów się nie zgadza
    (np. tabela wymieciona przez TRUNCATE testu transakcyjnego) albo
    któryś rekord ma rodzica.
    """
    cel = _charaktery_formalne_stan_docelowy()
    istniejace = {c.skrot: c for c in Charakter_Formalny.objects.all()}

    if set(istniejace) == set(cel) and all(
        c.parent_id is None for c in istniejace.values()
    ):
        # Różnice baseline vs wzorzec są typowo te same (~10 rekordów, 3 pola,
        # kilka wartości docelowych), więc jeden ``UPDATE ... WHERE pk IN``
        # na parę (pole, wartość) zamiast ``bulk_update``, który budował
        # w Pythonie ``CASE WHEN`` po wszystkich obiektach dla każdego pola.
        grupy = {}
        for skrot, obj in istniejace.items():
            for attname, wartosc in cel[skrot].items():
                if getattr(obj, attname) != wartosc:
                    setattr(obj, attname, wartosc)
                    grupy.setdefault((attname, wartosc), []).append(obj.pk)
        meta = Charakter_Formalny._meta
        for (attname, wartosc), pki in grupy.items():
            Charakter_Formalny.objects.filter(pk__in=pki).update(
                **{meta.get_field(attname).name: wartosc}
            )
        # Obiekty mają już stan zapisany w bazie — bez drugiego SELECT-a.
        return istniejace
    else:
        Charakter_Formalny.objects.all().delete()
        # Lookup po kluczu naturalnym (skrot jest unique), NIGDY po pk (w
        # JSON-ie pk bywa null) — inaczej wiersz o tym samym skrocie/nazwie
        # pod innym pk => INSERT => IntegrityError.
        for skrot, wartosci in cel.items():
            Charakter_Formalny.objects.get_or_create(
                skrot=skrot, defaults=dict(wartosci)
            )

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
    _zapewnij_wg_pk(Typ_KBN, "typ_kbn.json")


@pytest.fixture(scope="function")
def statusy_korekt():
    obiekty = _zapewnij_wg_pk(Status_Korekty, "status_korekty.json")
    return {status.nazwa: status for status in obiekty.values()}


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


_kod_dyscypliny_seq = itertools.count()


def gen_kod_dyscypliny_func():
    """Unikalny ``kod`` dla ``baker.make(Dyscyplina_Naukowa)``.

    ``kod`` jest ``unique``. Losowanie (dawniej ``randint(1, 8).randint(1, 500)``)
    kolidowało z kodami już zapisanymi w bazie testu (IntegrityError na
    ``bpp_dyscyplina_naukowa_kod_key``, flake na CI). Teraz: sekwencja po
    końcówkach 500-999 (jawne kody w testach kończą się najwyżej na .232),
    z pominięciem kodów, które już istnieją w bazie.
    """
    from bpp.models import Dyscyplina_Naukowa

    while True:
        n = next(_kod_dyscypliny_seq) % (8 * 500)
        kod = f"{n % 8 + 1}.{500 + n // 8}"
        if not Dyscyplina_Naukowa.objects.filter(kod=kod).exists():
            return kod


baker.generators.add(
    "bpp.models.dyscyplina_naukowa.KodDyscyplinyField", gen_kod_dyscypliny_func
)
