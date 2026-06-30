"""
Testy charakteryzujące (pinning) zachowanie funkcji znajdz_podobne_zrodla.

Celem tych testów jest UTRWALENIE obecnego zachowania scoringu źródeł przed
refaktoryzacją zdejmującą # noqa: C901. Pinujemy dla reprezentatywnych wejść:
- do której kategorii (najlepsze/dobre/akceptowalne) trafia dopasowanie,
- jaki ma typ dopasowania (reason) oraz dokładny score,
- kolejność i obcinanie wyników do max_results.

To NIE jest TDD red-green: testy MUSZĄ przechodzić przeciw kodowi PRZED
refaktoryzacją. Jeśli któryś opisuje zachowanie błędnie — poprawiamy TEST,
nie kod (zachowujemy zachowanie 1:1).
"""

import pytest
from model_bakery import baker

from przemapuj_zrodla_pbn.views import znajdz_podobne_zrodla


def _make_journal(**kwargs):
    defaults = {
        "title": "",
        "issn": "",
        "eissn": "",
        "websiteLink": "",
        "mniswId": None,
    }
    defaults.update(kwargs)
    return baker.make("pbn_api.Journal", **defaults)


def _znajdz_item(lista, obj):
    """Zwróć krotkę (obj, reason, score) dla danego obiektu z listy wyników."""
    for item in lista:
        if item[0].pk == obj.pk:
            return item
    return None


# --- CZĘŚĆ 1: TABELA ZRODLO (zrodla_bpp) ---------------------------------


@pytest.mark.django_db
def test_zrodlo_issn_nazwa_z_mniswid_trafia_do_najlepsze():
    skasowane = _make_journal(status="DELETED", title="Foo", issn="1111-1111")

    aktywne = _make_journal(status="ACTIVE", title="X", issn="1111-1111", mniswId=999)
    zrodlo = baker.make(
        "bpp.Zrodlo", nazwa="Foo Bar", issn="1111-1111", pbn_uid=aktywne
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["zrodla_bpp"]["najlepsze"], zrodlo)
    assert item is not None
    assert item[1] == "ISSN+NAZWA"
    assert item[2] == 1.0
    # Nie powinien wpaść do innych kategorii
    assert _znajdz_item(results["zrodla_bpp"]["dobre"], zrodlo) is None
    assert _znajdz_item(results["zrodla_bpp"]["akceptowalne"], zrodlo) is None


@pytest.mark.django_db
def test_zrodlo_issn_nazwa_bez_mniswid_trafia_do_dobre():
    skasowane = _make_journal(status="DELETED", title="Foo", issn="1111-1111")

    aktywne = _make_journal(status="ACTIVE", title="X", issn="1111-1111", mniswId=None)
    zrodlo = baker.make(
        "bpp.Zrodlo", nazwa="Foo Bar", issn="1111-1111", pbn_uid=aktywne
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["zrodla_bpp"]["dobre"], zrodlo)
    assert item is not None
    assert item[1] == "ISSN+NAZWA"
    assert item[2] == 1.0
    assert _znajdz_item(results["zrodla_bpp"]["najlepsze"], zrodlo) is None


@pytest.mark.django_db
def test_zrodlo_sam_issn_bez_pasujacej_nazwy_trafia_do_dobre():
    skasowane = _make_journal(status="DELETED", title="Foo", issn="2222-2222")

    aktywne = _make_journal(status="ACTIVE", title="X", issn="2222-2222", mniswId=999)
    zrodlo = baker.make(
        "bpp.Zrodlo",
        nazwa="Zupelnie Inna Nazwa",
        issn="2222-2222",
        pbn_uid=aktywne,
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["zrodla_bpp"]["dobre"], zrodlo)
    assert item is not None
    assert item[1] == "ISSN"
    assert item[2] == 0.9
    assert _znajdz_item(results["zrodla_bpp"]["najlepsze"], zrodlo) is None


@pytest.mark.django_db
def test_zrodlo_prefix_bez_issn_match_trafia_do_dobre():
    skasowane = _make_journal(status="DELETED", title="Unikat", issn="", eissn="")

    aktywne = _make_journal(status="ACTIVE", title="X", mniswId=999)
    zrodlo = baker.make(
        "bpp.Zrodlo", nazwa="Unikat Czasopismo", issn="", pbn_uid=aktywne
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["zrodla_bpp"]["dobre"], zrodlo)
    assert item is not None
    assert item[1] == "PREFIX"
    assert item[2] == 0.8
    assert _znajdz_item(results["zrodla_bpp"]["najlepsze"], zrodlo) is None


@pytest.mark.django_db
def test_zrodlo_similarity_bez_mniswid_trafia_do_akceptowalne():
    skasowane = _make_journal(
        status="DELETED", title="Aaaa Bbbb Cccc Dddd Eeee", issn=""
    )

    aktywne = _make_journal(status="ACTIVE", title="X", mniswId=None)
    # Nazwa podobna ale NIE zaczynająca się od szukanego (różnica na końcu),
    # więc trafi do scoringu SIMILARITY, nie PREFIX.
    zrodlo = baker.make(
        "bpp.Zrodlo", nazwa="Aaaa Bbbb Cccc Dddd EeeX", issn="", pbn_uid=aktywne
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["zrodla_bpp"]["akceptowalne"], zrodlo)
    assert item is not None
    assert item[1] == "SIMILARITY"
    assert item[2] >= 0.5
    assert _znajdz_item(results["zrodla_bpp"]["dobre"], zrodlo) is None


@pytest.mark.django_db
def test_zrodlo_similarity_z_mniswid_powyzej_07_trafia_do_dobre():
    skasowane = _make_journal(
        status="DELETED",
        title="Czasopismo Naukowe Uniwersytetu Warszawskiego",
        issn="",
    )

    aktywne = _make_journal(status="ACTIVE", title="X", mniswId=999)
    # Jeden znak różnicy w ~45 znakach -> podobieństwo >> 0.7, ale nie prefix.
    zrodlo = baker.make(
        "bpp.Zrodlo",
        nazwa="Czasopismo Naukowe Uniwersytetu WarszawskiegX",
        issn="",
        pbn_uid=aktywne,
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["zrodla_bpp"]["dobre"], zrodlo)
    assert item is not None
    assert item[1] == "SIMILARITY"
    assert item[2] > 0.7
    assert _znajdz_item(results["zrodla_bpp"]["akceptowalne"], zrodlo) is None


@pytest.mark.django_db
def test_nazwa_do_wyszukania_pochodzi_z_zrodla_skasowanego_gdy_istnieje():
    skasowane = _make_journal(status="DELETED", title="Tytul Z PBN", issn="", eissn="")
    # Źródło BPP wskazujące na skasowany journal -> nazwa BPP nadpisuje tytuł PBN.
    baker.make("bpp.Zrodlo", nazwa="Nazwa Z Bpp", pbn_uid=skasowane)

    aktywne = _make_journal(status="ACTIVE", title="X", mniswId=999)
    # Pasuje prefixem do nazwy BPP ("Nazwa Z Bpp"), a NIE do tytułu PBN.
    zrodlo = baker.make(
        "bpp.Zrodlo", nazwa="Nazwa Z Bpp Extra", issn="", pbn_uid=aktywne
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["zrodla_bpp"]["dobre"], zrodlo)
    assert item is not None
    assert item[1] == "PREFIX"


# --- CZĘŚĆ 2: TABELA JOURNAL (journale_pbn) ------------------------------


@pytest.mark.django_db
def test_journal_issn_nazwa_z_mniswid_trafia_do_najlepsze():
    skasowane = _make_journal(status="DELETED", title="Jrnl", issn="3333-3333")

    kandydat = _make_journal(
        status="ACTIVE", title="Jrnl Plus", issn="3333-3333", mniswId=5
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["journale_pbn"]["najlepsze"], kandydat)
    assert item is not None
    assert item[1] == "ISSN+NAZWA"
    assert item[2] == 1.0
    assert _znajdz_item(results["journale_pbn"]["dobre"], kandydat) is None


@pytest.mark.django_db
def test_journal_issn_nazwa_bez_mniswid_trafia_do_dobre():
    skasowane = _make_journal(status="DELETED", title="Jrnl", issn="3333-3334")

    kandydat = _make_journal(
        status="ACTIVE", title="Jrnl Plus", issn="3333-3334", mniswId=None
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["journale_pbn"]["dobre"], kandydat)
    assert item is not None
    assert item[1] == "ISSN+NAZWA"
    assert item[2] == 1.0
    assert _znajdz_item(results["journale_pbn"]["najlepsze"], kandydat) is None


@pytest.mark.django_db
def test_journal_sam_issn_trafia_do_dobre():
    skasowane = _make_journal(status="DELETED", title="Jrnl", issn="4444-4444")

    kandydat = _make_journal(
        status="ACTIVE", title="Inna Nazwa Calkiem", issn="4444-4444", mniswId=5
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["journale_pbn"]["dobre"], kandydat)
    assert item is not None
    assert item[1] == "ISSN"
    assert item[2] == 0.9
    assert _znajdz_item(results["journale_pbn"]["najlepsze"], kandydat) is None


@pytest.mark.django_db
def test_journal_prefix_bez_issn_trafia_do_dobre():
    skasowane = _make_journal(status="DELETED", title="Pref", issn="", eissn="")

    kandydat = _make_journal(status="ACTIVE", title="Pref Journal", issn="", mniswId=5)

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["journale_pbn"]["dobre"], kandydat)
    assert item is not None
    assert item[1] == "PREFIX"
    assert item[2] == 0.8
    assert _znajdz_item(results["journale_pbn"]["najlepsze"], kandydat) is None


@pytest.mark.django_db
def test_journal_similarity_bez_mniswid_trafia_do_akceptowalne():
    skasowane = _make_journal(
        status="DELETED", title="Zzzz Yyyy Xxxx Wwww Vvvv", issn=""
    )

    kandydat = _make_journal(
        status="ACTIVE", title="Zzzz Yyyy Xxxx Wwww VvvX", issn="", mniswId=None
    )

    results = znajdz_podobne_zrodla(skasowane)

    item = _znajdz_item(results["journale_pbn"]["akceptowalne"], kandydat)
    assert item is not None
    assert item[1] == "SIMILARITY"
    assert item[2] >= 0.5
    assert _znajdz_item(results["journale_pbn"]["dobre"], kandydat) is None


@pytest.mark.django_db
def test_journal_juz_w_bpp_jest_pomijany():
    skasowane = _make_journal(status="DELETED", title="Jrnl", issn="5555-5555")

    kandydat = _make_journal(
        status="ACTIVE", title="Jrnl Plus", issn="5555-5555", mniswId=5
    )
    # Journal który ma już odpowiednik w BPP -> NIE pojawia się w journale_pbn.
    baker.make("bpp.Zrodlo", nazwa="Jrnl Plus", issn="5555-5555", pbn_uid=kandydat)

    results = znajdz_podobne_zrodla(skasowane)

    for subcat in ("najlepsze", "dobre", "akceptowalne"):
        assert _znajdz_item(results["journale_pbn"][subcat], kandydat) is None


# --- SORTOWANIE I OBCINANIE ---------------------------------------------


@pytest.mark.django_db
def test_kategorie_sa_sortowane_malejaco_po_score():
    skasowane = _make_journal(status="DELETED", title="Foo", issn="6666-6666")

    a = _make_journal(status="ACTIVE", title="X", issn="6666-6666", mniswId=None)
    # ISSN+NAZWA -> 1.0
    z_wysoki = baker.make(
        "bpp.Zrodlo", nazwa="Foo Najlepszy", issn="6666-6666", pbn_uid=a
    )
    b = _make_journal(status="ACTIVE", title="Y", issn="6666-6666", mniswId=None)
    # sam ISSN -> 0.9
    z_nizszy = baker.make("bpp.Zrodlo", nazwa="Inny Tytul", issn="6666-6666", pbn_uid=b)

    results = znajdz_podobne_zrodla(skasowane)
    dobre = results["zrodla_bpp"]["dobre"]
    scores = [item[2] for item in dobre]
    assert scores == sorted(scores, reverse=True)
    # Wyższy score przed niższym
    idx_wysoki = next(i for i, it in enumerate(dobre) if it[0].pk == z_wysoki.pk)
    idx_nizszy = next(i for i, it in enumerate(dobre) if it[0].pk == z_nizszy.pk)
    assert idx_wysoki < idx_nizszy


@pytest.mark.django_db
def test_max_results_obcina_kategorie():
    skasowane = _make_journal(status="DELETED", title="Foo", issn="7777-7777")

    for i in range(4):
        a = _make_journal(
            status="ACTIVE", title=f"X{i}", issn="7777-7777", mniswId=None
        )
        baker.make("bpp.Zrodlo", nazwa=f"Rozne {i}", issn="7777-7777", pbn_uid=a)

    results = znajdz_podobne_zrodla(skasowane, max_results=2)
    assert len(results["zrodla_bpp"]["dobre"]) == 2


@pytest.mark.django_db
def test_struktura_wynikow_zawiera_obie_kategorie_glowne():
    skasowane = _make_journal(status="DELETED", title="Cos", issn="")
    results = znajdz_podobne_zrodla(skasowane)
    assert set(results.keys()) == {"zrodla_bpp", "journale_pbn"}
    for glowna in results.values():
        assert set(glowna.keys()) == {"najlepsze", "dobre", "akceptowalne"}
        for lista in glowna.values():
            assert isinstance(lista, list)
