"""FD#527: aliasy ``punkty_mnisw`` / ``typ_mnisw`` obok dawnych nazw pól.

Kolumny w bazie zostają (``punkty_kbn``, ``typ_kbn``) — nowe nazwy działają
w zapytaniach DjangoQL (raporty, „Szukaj zapytaniem", adminy, API) i jako
dodatkowe klucze w API. Dawne nazwy muszą działać bez zmian: używają ich
zapytania zapisane w bazach instalacji i integracje klientów.
"""

from decimal import Decimal

import pytest
from djangoql.queryset import apply_search
from djangoql.serializers import DjangoQLSchemaSerializer
from model_bakery import baker

from bpp.djangoql_schema import (
    BppQLSchema,
    BppQLSchemaOgraniczony,
    RekordLLMSchema,
)
from bpp.models import Rekord, Typ_KBN, Wydawnictwo_Ciagle
from nowe_raporty.query_backends import BppDjangoQLQueryBackend, BppDSLQueryBackend

SCHEMATY = [BppQLSchema, BppQLSchemaOgraniczony, RekordLLMSchema]


@pytest.fixture
def prace(db, jezyki, charaktery_formalne, statusy_korekt):
    typ_a = baker.make(Typ_KBN, nazwa="Typ A", skrot="TA")
    typ_b = baker.make(Typ_KBN, nazwa="Typ B", skrot="TB")
    wysoka = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="FD527 wysoka",
        punkty_kbn=Decimal("140"),
        typ_kbn=typ_a,
    )
    niska = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="FD527 niska",
        punkty_kbn=Decimal("20"),
        typ_kbn=typ_b,
    )
    return wysoka, niska


def _tytuly(model, zapytanie, schemat):
    qs = model.objects.filter(tytul_oryginalny__startswith="FD527")
    return sorted(
        apply_search(qs, zapytanie, schema=schemat).values_list(
            "tytul_oryginalny", flat=True
        )
    )


PARY = [
    ("punkty_kbn >= 100", "punkty_mnisw >= 100", ["FD527 wysoka"]),
    ('typ_kbn.skrot = "TB"', 'typ_mnisw.skrot = "TB"', ["FD527 niska"]),
    (
        'punkty_kbn < 100 and typ_kbn.nazwa = "Typ B"',
        'punkty_mnisw < 100 and typ_mnisw.nazwa = "Typ B"',
        ["FD527 niska"],
    ),
    (
        'typ_kbn.skrot in ("TA", "TB") and punkty_kbn != 20',
        'typ_mnisw.skrot in ("TA", "TB") and punkty_mnisw != 20',
        ["FD527 wysoka"],
    ),
]


@pytest.mark.parametrize("schemat", SCHEMATY)
@pytest.mark.parametrize("stare,nowe,oczekiwane", PARY)
@pytest.mark.parametrize("model", [Wydawnictwo_Ciagle, Rekord])
def test_fd527_alias_daje_ten_sam_wynik_co_stara_nazwa(
    prace, schemat, stare, nowe, oczekiwane, model
):
    # Strażnik: dawna nazwa pola działa jak dotąd…
    assert _tytuly(model, stare, schemat) == oczekiwane
    # …a nowa daje dokładnie to samo.
    assert _tytuly(model, nowe, schemat) == oczekiwane


def test_fd527_mieszanie_starej_i_nowej_nazwy(prace):
    assert _tytuly(
        Wydawnictwo_Ciagle,
        'punkty_mnisw >= 100 and typ_kbn.skrot = "TA"',
        BppQLSchema,
    ) == ["FD527 wysoka"]


def test_fd527_alias_w_pickerze_rel(prace):
    assert (
        _tytuly(Wydawnictwo_Ciagle, 'typ_mnisw__rel ~ "Typ A"', BppQLSchema)
        == _tytuly(Wydawnictwo_Ciagle, 'typ_kbn__rel ~ "Typ A"', BppQLSchema)
        == ["FD527 wysoka"]
    )


def test_fd527_alias_przez_relacje(prace):
    """Alias działa też w środku ścieżki (autor → rekord → pole)."""
    from bpp.models import Autor, Jednostka

    wysoka, _ = prace
    autor = baker.make(Autor, nazwisko="Fdpiecsetdwadziesciasiedem")
    wysoka.dodaj_autora(autor, baker.make(Jednostka), zapisany_jako="F. A.")
    stare = apply_search(
        Autor.objects.all(),
        "wydawnictwo_ciagle_autor.rekord.punkty_kbn >= 100",
        schema=BppQLSchema,
    )
    nowe = apply_search(
        Autor.objects.all(),
        "wydawnictwo_ciagle_autor.rekord.punkty_mnisw >= 100",
        schema=BppQLSchema,
    )
    assert list(stare) == list(nowe) == [autor]


def test_fd527_literal_z_nazwa_aliasu_nie_jest_ruszany(prace):
    """Podmieniamy nazwy pól, nie treść napisów w zapytaniu."""
    assert (
        _tytuly(Wydawnictwo_Ciagle, 'tytul_oryginalny ~ "punkty_mnisw"', BppQLSchema)
        == []
    )
    wysoka, _ = prace
    wysoka.tytul_oryginalny = "FD527 punkty_mnisw w tytule"
    wysoka.save()
    assert _tytuly(
        Wydawnictwo_Ciagle, 'tytul_oryginalny ~ "punkty_mnisw"', BppQLSchema
    ) == ["FD527 punkty_mnisw w tytule"]


def _pola(schemat, model):
    opis = DjangoQLSchemaSerializer().serialize(schemat(model))
    return opis["models"][opis["current_model"]]


def test_fd527_edytor_podpowiada_stare_i_nowe_nazwy(db):
    for schemat in (BppQLSchema, BppQLSchemaOgraniczony):
        pola = _pola(schemat, Wydawnictwo_Ciagle)
        for nazwa in ("punkty_kbn", "typ_kbn", "punkty_mnisw", "typ_mnisw"):
            assert nazwa in pola, (schemat, nazwa)
        assert pola["punkty_mnisw"]["type"] == pola["punkty_kbn"]["type"]
        assert pola["typ_mnisw"]["relation"] == pola["typ_kbn"]["relation"]


def test_fd527_opis_schematu_dla_llm_bez_duplikatow(db):
    pola = _pola(RekordLLMSchema, Rekord)
    assert "punkty_kbn" in pola
    assert "punkty_mnisw" not in pola
    assert "typ_mnisw" not in pola


@pytest.mark.parametrize(
    "backend,zapytania",
    [
        (
            BppDjangoQLQueryBackend,
            (
                'punkty_kbn > 0 and typ_kbn.skrot != "TB"',
                'punkty_mnisw > 0 and typ_mnisw.skrot != "TB"',
            ),
        ),
        (
            # django-dsl: język zapytań raportów zakładanych przez seed.
            BppDSLQueryBackend,
            (
                'punkty_kbn > 0 AND NOT typ_kbn = "TB"',
                'punkty_mnisw > 0 AND NOT typ_mnisw = "TB"',
            ),
        ),
    ],
)
def test_fd527_zrodlo_danych_raportu_przyjmuje_obie_nazwy(prace, backend, zapytania):
    """Zapytania źródeł danych raportów (flexible reports), oba języki."""
    qs = Rekord.objects.filter(tytul_oryginalny__startswith="FD527")
    for zapytanie in zapytania:
        backend().validate(zapytanie, Rekord)
        wynik = backend().filter_queryset(qs, zapytanie)
        assert [r.tytul_oryginalny for r in wynik] == ["FD527 wysoka"], zapytanie


def test_fd527_nieznane_pole_nadal_jest_bledem(db):
    from djangoql.exceptions import DjangoQLSchemaError

    with pytest.raises(DjangoQLSchemaError):
        apply_search(
            Wydawnictwo_Ciagle.objects.all(), "punkty_xyz > 1", schema=BppQLSchema
        )


def _naglowki_eksportu(resource):
    return resource.get_export_headers()


@pytest.mark.parametrize(
    "sciezka",
    [
        "bpp.admin.xlsx_export.resources.Wydawnictwo_CiagleResource",
        "bpp.admin.xlsx_export.resources.Wydawnictwo_ZwarteResource",
        "bpp.admin.patent.PatentResource",
        "bpp.admin.praca_doktorska.Praca_DoktorskaResource",
        "bpp.admin.praca_habilitacyjna.Praca_HabilitacyjnaResource",
    ],
)
def test_fd527_naglowki_eksportu_xlsx_z_list_w_adminie(sciezka):
    from django.utils.module_loading import import_string

    naglowki = _naglowki_eksportu(import_string(sciezka)())
    assert "typ_mnisw" in naglowki
    assert "punkty_mnisw" in naglowki
    assert not [n for n in naglowki if "kbn" in n.lower()]
    # Strażnik: pozostałe kolumny nazywają się jak dotąd i każda jest raz.
    assert "charakter_formalny" in naglowki
    assert "impact_factor" in naglowki
    assert len(naglowki) == len(set(naglowki))


def test_fd527_naglowki_eksportu_rozbieznosci_dyscyplin():
    from rozbieznosci_dyscyplin.admin import RozbieznosciZrodelViewResource

    naglowki = _naglowki_eksportu(RozbieznosciZrodelViewResource())
    assert "punkty_mnisw" in naglowki
    assert "punkty_kbn" not in naglowki
    assert naglowki.index("punkty_mnisw") == 8


def test_fd527_eksport_xlsx_wartosci_pod_nowymi_naglowkami(prace):
    from bpp.admin.xlsx_export.resources import Wydawnictwo_CiagleResource

    dane = Wydawnictwo_CiagleResource().export(
        Wydawnictwo_Ciagle.objects.filter(tytul_oryginalny="FD527 wysoka")
    )
    wiersz = dane.dict[0]
    assert wiersz["typ_mnisw"] == "Typ A"
    assert Decimal(str(wiersz["punkty_mnisw"])) == Decimal("140")
