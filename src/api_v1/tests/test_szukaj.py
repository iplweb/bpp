"""Testy endpointu wyszukiwania ``GET /api/v1/szukaj/`` (Faza 0)."""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from bpp.models import (
    Rekord,
)

# Rzadki, wymyślony token — nie wystąpi w danych referencyjnych baseline.
TOKEN = "kwakwahita"


def _ids_from(res):
    return {pozycja["id"] for pozycja in res.json()["results"]}


@pytest.fixture
def piec_typow(
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    patent,
    praca_doktorska,
    praca_habilitacyjna,
    autor_jan_kowalski,
    jednostka,
    typy_odpowiedzialnosci,
):
    """Po jednym rekordzie każdego z 5 typów publikacji, wszystkie z TOKEN."""
    wydawnictwo_ciagle.tytul_oryginalny = f"{TOKEN} ciagle"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    wydawnictwo_zwarte.tytul_oryginalny = f"{TOKEN} zwarte"
    wydawnictwo_zwarte.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    patent.tytul_oryginalny = f"{TOKEN} patent"
    patent.save()
    patent.dodaj_autora(autor_jan_kowalski, jednostka)

    praca_doktorska.tytul_oryginalny = f"{TOKEN} doktorska"
    praca_doktorska.save()

    praca_habilitacyjna.tytul_oryginalny = f"{TOKEN} habilitacyjna"
    praca_habilitacyjna.save()

    Rekord.objects.full_refresh()
    return {
        "ciagle": wydawnictwo_ciagle,
        "zwarte": wydawnictwo_zwarte,
        "patent": patent,
        "doktorska": praca_doktorska,
        "habilitacyjna": praca_habilitacyjna,
    }


def _rekord_id(obj):
    ct = ContentType.objects.get_for_model(obj)
    return f"{ct.pk}-{obj.pk}"


@pytest.mark.django_db
def test_szukaj_trafienie(api_client, piec_typow):
    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    assert res.status_code == 200
    assert res.json()["count"] == 5
    assert _rekord_id(piec_typow["ciagle"]) in _ids_from(res)


@pytest.mark.django_db
def test_szukaj_brak_trafienia(api_client, piec_typow):
    res = api_client.get(reverse("api_v1:szukaj-list") + "?q=niematakiegoslowa999")
    assert res.status_code == 200
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_szukaj_puste_q_zwraca_pusta_liste(api_client, piec_typow):
    # Brak q → fulltext_empty(), NIE 500.
    res = api_client.get(reverse("api_v1:szukaj-list"))
    assert res.status_code == 200
    assert res.json()["count"] == 0

    res = api_client.get(reverse("api_v1:szukaj-list") + "?q=")
    assert res.status_code == 200
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_szukaj_rok_od_do(api_client, piec_typow):
    ciagle = piec_typow["ciagle"]
    ciagle.rok = 1999
    ciagle.save()
    Rekord.objects.full_refresh()

    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}&rok_do=2000")
    ids = _ids_from(res)
    assert _rekord_id(ciagle) in ids
    assert _rekord_id(piec_typow["zwarte"]) not in ids

    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}&rok_od=2000")
    ids = _ids_from(res)
    assert _rekord_id(ciagle) not in ids


@pytest.mark.django_db
def test_szukaj_limit_offset(api_client, piec_typow):
    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}&limit=2")
    assert res.json()["count"] == 5
    assert len(res.json()["results"]) == 2

    res2 = api_client.get(
        reverse("api_v1:szukaj-list") + f"?q={TOKEN}&limit=2&offset=2"
    )
    assert len(res2.json()["results"]) == 2
    # Strony nie zachodzą na siebie.
    assert _ids_from(res).isdisjoint(_ids_from(res2))


@pytest.mark.django_db
def test_szukaj_stabilna_paginacja_przy_remisach(api_client, piec_typow):
    # Przechodząc limit=1 po całości nie gubimy ani nie dublujemy rekordów,
    # nawet gdy ranki są remisowe (deterministyczny tiebreaker id/sort).
    zebrane = []
    for offset in range(5):
        res = api_client.get(
            reverse("api_v1:szukaj-list") + f"?q={TOKEN}&limit=1&offset={offset}"
        )
        wyniki = res.json()["results"]
        assert len(wyniki) == 1
        zebrane.append(wyniki[0]["id"])
    assert len(set(zebrane)) == 5


@pytest.mark.django_db
def test_szukaj_nie_eksportuj_przez_api_per_typ(api_client, piec_typow):
    ciagle = piec_typow["ciagle"]
    ciagle.nie_eksportuj_przez_api = True
    ciagle.save()
    Rekord.objects.full_refresh()

    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    ids = _ids_from(res)
    assert _rekord_id(ciagle) not in ids
    # Pozostałe 4 typy nadal widoczne (wykluczenie jest per-typ).
    assert _rekord_id(piec_typow["zwarte"]) in ids
    assert res.json()["count"] == 4


@pytest.mark.django_db
def test_szukaj_wyklucza_ukryte_statusy(
    api_client, piec_typow, uczelnia, przed_korekta
):
    ciagle = piec_typow["ciagle"]
    ciagle.status_korekty = przed_korekta
    ciagle.save()
    Rekord.objects.full_refresh()

    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    assert _rekord_id(ciagle) in _ids_from(res)

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    assert _rekord_id(ciagle) not in _ids_from(res)


@pytest.mark.django_db
def test_szukaj_mapowanie_contenttype_wszystkie_5_typow(api_client, piec_typow):
    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    po_id = {pozycja["id"]: pozycja for pozycja in res.json()["results"]}

    oczekiwane_sciezki = {
        "ciagle": ("wydawnictwo_ciagle", "api_v1:wydawnictwo_ciagle-detail"),
        "zwarte": ("wydawnictwo_zwarte", "api_v1:wydawnictwo_zwarte-detail"),
        "patent": ("patent", "api_v1:patent-detail"),
        "doktorska": ("praca_doktorska", "api_v1:praca_doktorska-detail"),
        "habilitacyjna": ("praca_habilitacyjna", "api_v1:praca_habilitacyjna-detail"),
    }
    for klucz, obj in piec_typow.items():
        rekord_id = _rekord_id(obj)
        assert rekord_id in po_id, f"brak {klucz} w wynikach"
        pozycja = po_id[rekord_id]
        _fragment, viewname = oczekiwane_sciezki[klucz]
        oczekiwany_url = reverse(viewname, args=(obj.pk,))
        assert pozycja["rekord_url"].endswith(oczekiwany_url)


@pytest.mark.django_db
def test_szukaj_search_index_nie_wycieka(api_client, piec_typow):
    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    pozycja = res.json()["results"][0]
    assert "search_index" not in pozycja
    assert set(pozycja.keys()) == {
        "id",
        "tytul_oryginalny",
        "rok",
        "opis_bibliograficzny",
        "rekord_url",
        "absolute_url",
    }


@pytest.mark.django_db
def test_szukaj_websearch_minus_i_cudzyslow(
    api_client, wydawnictwo_ciagle, zwarte_maker, autor_jan_kowalski, jednostka
):
    wydawnictwo_ciagle.tytul_oryginalny = f"{TOKEN} alfa"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    zwarte = zwarte_maker(tytul_oryginalny=f"{TOKEN} gamma")
    zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    Rekord.objects.full_refresh()

    # Minus (websearch) — wyklucz rekordy z "gamma".
    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN} -gamma")
    ids = _ids_from(res)
    assert _rekord_id(wydawnictwo_ciagle) in ids
    assert _rekord_id(zwarte) not in ids

    # Cudzysłów (fraza) — dokładny "TOKEN alfa".
    res = api_client.get(reverse("api_v1:szukaj-list") + f'?q="{TOKEN} alfa"')
    ids = _ids_from(res)
    assert _rekord_id(wydawnictwo_ciagle) in ids
    assert _rekord_id(zwarte) not in ids


@pytest.mark.django_db
def test_szukaj_opis_bibliograficzny_fallback(api_client, piec_typow):
    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    for pozycja in res.json()["results"]:
        # opis nigdy nie jest pusty (fallback na tytuł).
        assert pozycja["opis_bibliograficzny"]


@pytest.mark.django_db
def test_szukaj_brak_mapowania_site_uczelnia(
    api_client, uczelnia, jednostka, wydawnictwo_ciagle, autor_jan_kowalski
):
    # Przepinamy uczelnię na inny Site (Site "testserver" zostaje sierotą, bez
    # uczelni) i dokładamy drugą uczelnię → get_for_request zwraca None
    # (jedyna-albo-None przy count>1) → scope no-op, brak wykluczania statusów;
    # rekord nadal widoczny (jak reszta API).
    from django.contrib.sites.models import Site

    from bpp.models import Uczelnia

    uczelnia.site = Site.objects.create(domain="inny.example.com", name="inny")
    uczelnia.save()
    Uczelnia.objects.create(
        nazwa="Uczelnia B",
        skrot="BB",
        site=Site.objects.create(domain="uczelnia-b.example.com", name="B"),
    )

    wydawnictwo_ciagle.tytul_oryginalny = f"{TOKEN} bezscope"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    Rekord.objects.full_refresh()

    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    assert res.status_code == 200
    assert _rekord_id(wydawnictwo_ciagle) in _ids_from(res)


@pytest.mark.django_db
def test_szukaj_scope_dwie_uczelnie(
    api_client,
    uczelnia,
    wydzial,
    jednostka,
    wydawnictwo_ciagle,
    zwarte_maker,
    autor_jan_kowalski,
    autor_jan_nowak,
):
    # uczelnia (A) jest zmapowana na Site "testserver" (fixture). Tworzymy
    # drugą uczelnię B z własną jednostką; rekord z autorem tylko w B nie
    # powinien wyjść przy oglądaniu jako A.
    from django.contrib.sites.models import Site

    from bpp.models import Uczelnia, Wydzial
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    site_b = Site.objects.create(domain="uczelnia-b.example.com", name="B")
    uczelnia_b = Uczelnia.objects.create(nazwa="Uczelnia B", skrot="BB", site=site_b)
    wydzial_b = Wydzial.objects.create(uczelnia=uczelnia_b, nazwa="WB", skrot="WB")
    from bpp.models import Jednostka

    parent_b, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial_b)
    jednostka_b = Jednostka.objects.create(
        nazwa="Jedn. B", skrot="JB", parent=parent_b, uczelnia=uczelnia_b
    )

    rekord_a = wydawnictwo_ciagle
    rekord_a.tytul_oryginalny = f"{TOKEN} wA"
    rekord_a.save()
    rekord_a.dodaj_autora(autor_jan_kowalski, jednostka)

    rekord_b = zwarte_maker(tytul_oryginalny=f"{TOKEN} wB")
    rekord_b.dodaj_autora(autor_jan_nowak, jednostka_b)

    Rekord.objects.full_refresh()

    # Request na "testserver" → uczelnia A. Scope aktywny (2 uczelnie).
    res = api_client.get(reverse("api_v1:szukaj-list") + f"?q={TOKEN}")
    ids = _ids_from(res)
    assert _rekord_id(rekord_a) in ids
    assert _rekord_id(rekord_b) not in ids
