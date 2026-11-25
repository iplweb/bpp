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


def test_fd527_importer_i_formularz_raportu_zostaja_przy_mnisw():
    """Strażnik: te etykiety już były „…MNiSW” — mają takie zostać."""
    from importer_publikacji.forms import PunktacjaForm, VerifyForm
    from nowe_raporty.forms import BaseRaportForm
    from nowe_raporty.seeding import definicje

    assert VerifyForm.base_fields["typ_kbn"].label == "Typ MNiSW"
    assert PunktacjaForm.base_fields["punkty_kbn"].label == "Punkty MNiSW"
    assert "Pkt. MNiSW" in [kolumna["label"] for kolumna in definicje.KOLUMNY]
    etykiety = [str(p.label) for p in BaseRaportForm.base_fields.values()]
    assert "Tylko prace punktowane (pkt MNiSW > 0)" in etykiety


@pytest.mark.parametrize(
    "zapytanie,w_komunikacie,nie_w_komunikacie",
    [
        # pickera ``__rel`` nie ma w schemacie API — błąd ma mówić o tym,
        # co wpisał użytkownik, nie o nazwie po podmianie aliasu
        ('typ_mnisw__rel = "x"', "typ_mnisw__rel", "typ_kbn__rel"),
        ("punkty_mnisw__rel > 1", "punkty_mnisw__rel", "punkty_kbn__rel"),
    ],
)
def test_fd527_blad_pokazuje_nazwe_wpisana_przez_uzytkownika(
    db, zapytanie, w_komunikacie, nie_w_komunikacie
):
    from djangoql.exceptions import DjangoQLSchemaError

    with pytest.raises(DjangoQLSchemaError) as blad:
        apply_search(Rekord.objects.all(), zapytanie, schema=RekordLLMSchema)
    assert w_komunikacie in str(blad.value)
    assert nie_w_komunikacie not in str(blad.value)
    assert blad.value.value == w_komunikacie


def test_fd527_blad_ze_stara_nazwa_bez_zmian(db):
    """Strażnik: kto wpisał dawną nazwę, widzi w błędzie dawną nazwę."""
    from djangoql.exceptions import DjangoQLSchemaError

    with pytest.raises(DjangoQLSchemaError) as blad:
        apply_search(Rekord.objects.all(), 'typ_kbn__rel = "x"', schema=RekordLLMSchema)
    assert "typ_kbn__rel" in str(blad.value)
    assert "mnisw" not in str(blad.value)


def test_fd527_schemat_dlugowieczny_nie_miesza_zapytan(prace):
    """Instancja schematu bywa singletonem (eksport multiseek→DjangoQL):
    aliasy z jednego zapytania nie mogą przeciekać do błędu następnego."""
    from djangoql.exceptions import DjangoQLSchemaError
    from djangoql.parser import DjangoQLParser

    schemat = RekordLLMSchema(Rekord)
    schemat.validate(DjangoQLParser().parse("punkty_mnisw > 1"))
    with pytest.raises(DjangoQLSchemaError) as blad:
        schemat.validate(DjangoQLParser().parse('typ_kbn__rel = "x"'))
    assert "typ_kbn__rel" in str(blad.value)


def test_fd527_eksport_multiseek_do_djangoql_uzywa_nowych_nazw(prace):
    from bpp.multiseek_registry import registry
    from bpp.multiseek_registry.djangoql_export import multiseek_form_to_djangoql

    punkty = registry.get_field_by_name("Punkty MNiSW")
    typ = registry.get_field_by_name("Typ MNiSW")
    formularz = {
        "form_data": [
            None,
            {
                "field": "Punkty MNiSW",
                "operator": str(punkty.ops[0]),
                "value": 140,
                "prev_op": None,
            },
            {
                "field": "Typ MNiSW",
                "operator": str(typ.ops[0]),
                "value": "Typ A",
                "prev_op": "and",
            },
        ]
    }
    wynik = multiseek_form_to_djangoql(formularz, registry)

    assert "punkty_mnisw" in wynik.query
    assert "typ_mnisw" in wynik.query
    assert "kbn" not in wynik.query
    # Wygenerowane zapytanie działa i daje to, co wersja na dawnych nazwach.
    nowe = _tytuly(Rekord, wynik.query, BppQLSchemaOgraniczony)
    stare = _tytuly(
        Rekord,
        wynik.query.replace("punkty_mnisw", "punkty_kbn").replace(
            "typ_mnisw", "typ_kbn"
        ),
        BppQLSchemaOgraniczony,
    )
    assert nowe == stare == ["FD527 wysoka"]


def test_fd527_przyklady_w_pomocy_szukaj_zapytaniem_bez_kbn(db):
    from bpp.views import zapytanie

    teksty = repr(zapytanie.examples_z_okresami())
    assert "punkty_mnisw" in teksty
    assert "kbn" not in teksty.lower()


@pytest.mark.parametrize(
    "stare,nowe",
    [
        ('typ_kbn__nazwa = "Typ A"', 'typ_mnisw__nazwa = "Typ A"'),
        ('typ_kbn__skrot = "TA"', 'typ_mnisw__skrot = "TA"'),
        ("punkty_kbn__gte = 100", "punkty_mnisw__gte = 100"),
        ("punkty_kbn >= 100", "punkty_mnisw >= 100"),
        # samodzielny skrót zachowuje znaczenie „po skrócie typu”
        ('typ_kbn = "TA"', 'typ_mnisw = "TA"'),
        (
            'punkty_kbn__gte = 100 AND NOT typ_kbn__nazwa = "Typ B"',
            'punkty_mnisw__gte = 100 AND NOT typ_mnisw__nazwa = "Typ B"',
        ),
    ],
)
def test_fd527_django_dsl_alias_na_poczatku_sciezki(prace, stare, nowe):
    qs = Rekord.objects.filter(tytul_oryginalny__startswith="FD527")
    backend = BppDSLQueryBackend()
    backend.validate(stare, Rekord)
    backend.validate(nowe, Rekord)
    wynik_stary = [r.tytul_oryginalny for r in backend.filter_queryset(qs, stare)]
    wynik_nowy = [r.tytul_oryginalny for r in backend.filter_queryset(qs, nowe)]
    assert wynik_nowy == wynik_stary == ["FD527 wysoka"]


def test_fd527_django_dsl_literowka_nadal_odrzucana(prace):
    from django.core.exceptions import ValidationError

    for zle in ('typ_mniswx__nazwa = "a"', "punkty_mnisw__nie_ma = 1"):
        with pytest.raises(ValidationError):
            BppDSLQueryBackend().validate(zle, Rekord)
