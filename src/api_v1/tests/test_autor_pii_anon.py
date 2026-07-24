"""Testy regresyjne luki bezpieczeństwa: publiczne API autorów nie może
ujawniać danych osobowych (PII) ani autorów oznaczonych jako ukryci
(``pokazuj=False``) użytkownikom niezalogowanym.
"""

from datetime import date

import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIClient

from bpp.models import Autor


def _staff_client():
    u = baker.make("bpp.BppUser", is_staff=True, is_superuser=True)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


@pytest.mark.django_db
def test_anon_lista_nie_zawiera_ukrytego_autora():
    """Autor z ``pokazuj=False`` nie może pojawić się na publicznej liście."""
    baker.make(Autor, nazwisko="Widoczny", imiona="Wiktor", pokazuj=True)
    baker.make(Autor, nazwisko="Ukryty", imiona="Urban", pokazuj=False)

    res = APIClient().get(reverse("api_v1:autor-list"))
    nazwiska = {row["nazwisko"] for row in res.json()["results"]}
    assert "Widoczny" in nazwiska
    assert "Ukryty" not in nazwiska


@pytest.mark.django_db
def test_anon_detal_ukrytego_autora_404():
    """Detal autora z ``pokazuj=False`` jest niedostępny anonimowo (404)."""
    autor = baker.make(Autor, nazwisko="Ukryty", imiona="Urban", pokazuj=False)

    res = APIClient().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    assert res.status_code == 404


@pytest.mark.django_db
def test_zalogowany_widzi_ukrytego_autora():
    """Regresja w drugą stronę: zalogowany widzi ukrytego autora."""
    autor = baker.make(Autor, nazwisko="Ukryty", imiona="Urban", pokazuj=False)

    res = _staff_client().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    assert res.status_code == 200


@pytest.mark.django_db
def test_anon_nie_widzi_emaila():
    """E-mail autora to PII — nie może wyciec do anonima."""
    autor = baker.make(
        Autor,
        nazwisko="Kowalski",
        imiona="Jan",
        pokazuj=True,
        email="jan.kowalski@example.com",
    )

    res = APIClient().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    data = res.json()
    assert "jan.kowalski@example.com" not in str(data)
    assert not data.get("email")


@pytest.mark.django_db
def test_zalogowany_widzi_email():
    """Zalogowany nadal widzi e-mail autora."""
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", email="jan.kowalski@example.com"
    )

    res = _staff_client().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    assert res.json()["email"] == "jan.kowalski@example.com"


@pytest.mark.django_db
def test_anon_nie_widzi_pelnej_daty_urodzenia():
    """Pełna data urodzenia to PII — anonim nie może jej otrzymać."""
    autor = baker.make(
        Autor,
        nazwisko="Kowalski",
        imiona="Jan",
        pokazuj=True,
        urodzony=date(1970, 3, 15),
    )

    res = APIClient().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    data = res.json()
    assert "1970-03-15" not in str(data)
    assert data.get("urodzony") in (None, "")


@pytest.mark.django_db
def test_zalogowany_widzi_pelna_date_urodzenia():
    """Zalogowany nadal widzi pełną datę urodzenia."""
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", urodzony=date(1970, 3, 15)
    )

    res = _staff_client().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    assert res.json()["urodzony"] == "1970-03-15"


@pytest.mark.django_db
def test_anon_nie_widzi_poprzednich_nazwisk_gdy_ukryte():
    """Gdy ``pokazuj_poprzednie_nazwiska=False``, anonim nie dostaje pola."""
    autor = baker.make(
        Autor,
        nazwisko="Nowak",
        imiona="Anna",
        pokazuj=True,
        poprzednie_nazwiska="Kowalska",
        pokazuj_poprzednie_nazwiska=False,
    )

    res = APIClient().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    data = res.json()
    assert "Kowalska" not in str(data)
    assert not data.get("poprzednie_nazwiska")


@pytest.mark.django_db
def test_anon_widzi_poprzednie_nazwiska_gdy_wlaczone():
    """Gdy ``pokazuj_poprzednie_nazwiska=True``, anonim widzi je normalnie."""
    autor = baker.make(
        Autor,
        nazwisko="Nowak",
        imiona="Anna",
        pokazuj=True,
        poprzednie_nazwiska="Kowalska",
        pokazuj_poprzednie_nazwiska=True,
    )

    res = APIClient().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    assert res.json()["poprzednie_nazwiska"] == "Kowalska"


@pytest.mark.django_db
def test_zalogowany_widzi_poprzednie_nazwiska_mimo_flagi():
    """Zalogowany widzi poprzednie nazwiska nawet gdy flaga wyłączona."""
    autor = baker.make(
        Autor,
        nazwisko="Nowak",
        imiona="Anna",
        poprzednie_nazwiska="Kowalska",
        pokazuj_poprzednie_nazwiska=False,
    )

    res = _staff_client().get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    assert res.json()["poprzednie_nazwiska"] == "Kowalska"


@pytest.mark.django_db
def test_anon_filtrowanie_po_nazwisku_dziala(autor_jan_kowalski):
    """Fix nie może zepsuć istniejącego filtrowania po nazwisku."""
    res = APIClient().get(reverse("api_v1:autor-list") + "?nazwisko=kowal")
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_anon_nie_widzi_zatrudnienia_ukrytego_autora():
    """``/api/v1/autor_jednostka/`` nie może ujawniać powiązań zatrudnienia
    autora ukrytego (``pokazuj=False``). Inaczej jednostka, daty pracy oraz
    PK autora wyciekają anonimowi, obchodząc ``pokazuj=False`` egzekwowane
    przez ``AutorViewSet``."""
    from bpp.models import Autor_Jednostka, Jednostka

    jednostka = baker.make(Jednostka)
    widoczny = baker.make(Autor, nazwisko="Widoczny", pokazuj=True)
    ukryty = baker.make(Autor, nazwisko="Ukryty", pokazuj=False)
    baker.make(Autor_Jednostka, autor=widoczny, jednostka=jednostka)
    baker.make(Autor_Jednostka, autor=ukryty, jednostka=jednostka)

    res = APIClient().get(reverse("api_v1:autor_jednostka-list"))
    autor_urls = {row["autor"] for row in res.json()["results"]}
    ukryty_url = reverse("api_v1:autor-detail", args=(ukryty.pk,))
    widoczny_url = reverse("api_v1:autor-detail", args=(widoczny.pk,))

    assert any(widoczny_url in u for u in autor_urls)
    assert not any(ukryty_url in u for u in autor_urls)


@pytest.mark.django_db
def test_zalogowany_widzi_zatrudnienie_ukrytego_autora():
    """Regresja w drugą stronę: zalogowany (redaktor) widzi powiązania
    zatrudnienia także autorów ukrytych."""
    from bpp.models import Autor_Jednostka, Jednostka

    jednostka = baker.make(Jednostka)
    ukryty = baker.make(Autor, nazwisko="Ukryty", pokazuj=False)
    baker.make(Autor_Jednostka, autor=ukryty, jednostka=jednostka)

    res = _staff_client().get(reverse("api_v1:autor_jednostka-list"))
    autor_urls = {row["autor"] for row in res.json()["results"]}
    ukryty_url = reverse("api_v1:autor-detail", args=(ukryty.pk,))

    assert any(ukryty_url in u for u in autor_urls)
