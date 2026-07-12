from unittest import mock

import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker
from rest_framework.test import APIClient

from api_v1.permissions import MoznaUzywacZapytania
from bpp.const import GR_WPROWADZANIE_DANYCH

# Rzadki token — nie wystąpi w danych referencyjnych baseline.
ZTOKEN = "zqxjkwira"


def _rekord_id(obj):
    ct = ContentType.objects.get_for_model(obj)
    return f"{ct.pk}-{obj.pk}"


def _ids(resp):
    return {r["id"] for r in resp.data["results"]}


def _druga_uczelnia_z_jednostka():
    """Utwórz uczelnię B (własny Site) z jedną jednostką. Zwraca jednostkę B."""
    from django.contrib.sites.models import Site

    from bpp.models import Jednostka, Uczelnia, Wydzial
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    site_b = Site.objects.create(domain="uczelnia-b.example.com", name="B")
    uczelnia_b = Uczelnia.objects.create(nazwa="Uczelnia B", skrot="BB", site=site_b)
    wydzial_b = Wydzial.objects.create(uczelnia=uczelnia_b, nazwa="WB", skrot="WB")
    parent_b, _ = znajdz_lub_utworz_wezel_wydzialu(wydzial_b)
    return Jednostka.objects.create(
        nazwa="Jedn. B", skrot="JB", parent=parent_b, uczelnia=uczelnia_b
    )


class _FakeRequest:
    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
def test_gate_anon_odrzucony():
    assert (
        MoznaUzywacZapytania().has_permission(_FakeRequest(AnonymousUser()), None)
        is False
    )


@pytest.mark.django_db
def test_gate_superuser_przechodzi():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is True


@pytest.mark.django_db
def test_gate_staff_w_grupie_przechodzi():
    from django.contrib.auth.models import Group

    u = baker.make("bpp.BppUser", is_staff=True, is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grupa)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is True


@pytest.mark.django_db
def test_gate_zwykly_zalogowany_odrzucony():
    u = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is False


def _staff_client():
    u = baker.make("bpp.BppUser", is_staff=True, is_superuser=True)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


@pytest.mark.django_db
def test_zapytanie_rekord_anon_403():
    resp = APIClient().get("/api/v1/zapytanie/rekord/", {"q": "rok = 2024"})
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_zapytanie_rekord_puste_q_zwraca_pusto():
    resp = _staff_client().get("/api/v1/zapytanie/rekord/", {"q": ""})
    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_zapytanie_rekord_bledne_q_400():
    resp = _staff_client().get(
        "/api/v1/zapytanie/rekord/", {"q": "nieistniejace_pole = 1"}
    )
    assert resp.status_code == 400
    assert "error" in resp.data


@pytest.mark.django_db
def test_zapytanie_autor_happy():
    baker.make("bpp.Autor", nazwisko="Kowalski")
    resp = _staff_client().get("/api/v1/zapytanie/autor/", {"q": 'nazwisko ~ "Kowal"'})
    assert resp.status_code == 200
    assert any(r["nazwisko"] == "Kowalski" for r in resp.data["results"])


@pytest.mark.django_db
def test_zapytanie_autorzy_happy(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    wydawnictwo_ciagle.rok = 2023
    wydawnictwo_ciagle.tytul_oryginalny = "Praca X"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    from bpp.models import Rekord

    Rekord.objects.full_refresh()

    resp = _staff_client().get("/api/v1/zapytanie/autorzy/", {"q": "rekord.rok = 2023"})
    assert resp.status_code == 200
    assert len(resp.data["results"]) >= 1
    wpis = resp.data["results"][0]
    assert "zapisany_jako" in wpis and "rekord" in wpis
    assert wpis["rekord"]["rekord_url"] is not None


def test_zapytanie_limit_ma_twardy_cap():
    from api_v1.viewsets.zapytanie import ZapytanieRekordViewSet

    v = ZapytanieRekordViewSet()
    assert v.paginator.max_limit == 100


@pytest.mark.django_db
def test_zapytanie_timeout_daje_503():
    from django.db.utils import OperationalError

    with mock.patch(
        "api_v1.viewsets.zapytanie.ZapytanieAPIBaseViewSet.get_queryset",
        side_effect=OperationalError("canceling statement due to statement timeout"),
    ):
        resp = _staff_client().get("/api/v1/zapytanie/rekord/", {"q": "rok = 2024"})
    assert resp.status_code == 503
    assert "error" in resp.data


# --- Uwaga #1 reviewera: /zapytanie/ musi respektować politykę widoczności ---


@pytest.mark.django_db
def test_zapytanie_rekord_wyklucza_nie_eksportuj_przez_api(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    from bpp.models import Rekord

    wydawnictwo_ciagle.tytul_oryginalny = f"{ZTOKEN} ciagle"
    wydawnictwo_ciagle.nie_eksportuj_przez_api = True
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    Rekord.objects.full_refresh()

    resp = _staff_client().get(
        "/api/v1/zapytanie/rekord/", {"q": f'tytul_oryginalny ~ "{ZTOKEN}"'}
    )
    assert resp.status_code == 200
    assert _rekord_id(wydawnictwo_ciagle) not in _ids(resp)


@pytest.mark.django_db
def test_zapytanie_rekord_wyklucza_ukryte_statusy(
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    jednostka,
    typy_odpowiedzialnosci,
    uczelnia,
    przed_korekta,
):
    from bpp.models import Rekord

    wydawnictwo_ciagle.tytul_oryginalny = f"{ZTOKEN} ciagle"
    wydawnictwo_ciagle.status_korekty = przed_korekta
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    Rekord.objects.full_refresh()

    q = {"q": f'tytul_oryginalny ~ "{ZTOKEN}"'}
    assert _rekord_id(wydawnictwo_ciagle) in _ids(
        _staff_client().get("/api/v1/zapytanie/rekord/", q)
    )

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    assert _rekord_id(wydawnictwo_ciagle) not in _ids(
        _staff_client().get("/api/v1/zapytanie/rekord/", q)
    )


@pytest.mark.django_db
def test_zapytanie_rekord_scope_dwie_uczelnie(
    uczelnia,
    wydzial,
    jednostka,
    wydawnictwo_ciagle,
    zwarte_maker,
    autor_jan_kowalski,
    autor_jan_nowak,
    typy_odpowiedzialnosci,
):
    from bpp.models import Rekord

    jednostka_b = _druga_uczelnia_z_jednostka()

    rekord_a = wydawnictwo_ciagle
    rekord_a.tytul_oryginalny = f"{ZTOKEN} wA"
    rekord_a.save()
    rekord_a.dodaj_autora(autor_jan_kowalski, jednostka)

    rekord_b = zwarte_maker(tytul_oryginalny=f"{ZTOKEN} wB")
    rekord_b.dodaj_autora(autor_jan_nowak, jednostka_b)
    Rekord.objects.full_refresh()

    resp = _staff_client().get(
        "/api/v1/zapytanie/rekord/", {"q": f'tytul_oryginalny ~ "{ZTOKEN}"'}
    )
    ids = _ids(resp)
    assert _rekord_id(rekord_a) in ids
    assert _rekord_id(rekord_b) not in ids


@pytest.mark.django_db
def test_zapytanie_autorzy_scope_dwie_uczelnie(
    uczelnia,
    wydzial,
    jednostka,
    wydawnictwo_ciagle,
    zwarte_maker,
    autor_jan_kowalski,
    autor_jan_nowak,
    typy_odpowiedzialnosci,
):
    from bpp.models import Rekord

    jednostka_b = _druga_uczelnia_z_jednostka()

    wydawnictwo_ciagle.rok = 2023
    wydawnictwo_ciagle.tytul_oryginalny = f"{ZTOKEN} wA"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    rekord_b = zwarte_maker(tytul_oryginalny=f"{ZTOKEN} wB", rok=2023)
    rekord_b.dodaj_autora(autor_jan_nowak, jednostka_b)
    Rekord.objects.full_refresh()

    resp = _staff_client().get("/api/v1/zapytanie/autorzy/", {"q": "rekord.rok = 2023"})
    assert resp.status_code == 200
    jednostki = {w["jednostka"] for w in resp.data["results"]}
    assert "Jedn. B" not in jednostki


@pytest.mark.django_db
def test_zapytanie_autor_scope_dwie_uczelnie(uczelnia, wydzial, jednostka):
    from bpp.models import Autor

    jednostka_b = _druga_uczelnia_z_jednostka()
    autor_a = Autor.objects.create(
        nazwisko=f"{ZTOKEN}A", imiona="Jan", aktualna_jednostka=jednostka
    )
    autor_b = Autor.objects.create(
        nazwisko=f"{ZTOKEN}B", imiona="Adam", aktualna_jednostka=jednostka_b
    )

    resp = _staff_client().get(
        "/api/v1/zapytanie/autor/", {"q": f'nazwisko ~ "{ZTOKEN}"'}
    )
    assert resp.status_code == 200
    nazwiska = {r["nazwisko"] for r in resp.data["results"]}
    assert autor_a.nazwisko in nazwiska
    assert autor_b.nazwisko not in nazwiska
