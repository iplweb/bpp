import pytest
from django.urls import NoReverseMatch, reverse
from model_bakery import baker

from bpp.models import Jednostka


def test_rest_api_jednostka_detail(client, jednostka):
    res = client.get(reverse("api_v1:jednostka-detail", args=(jednostka.pk,)))
    assert res.status_code == 200


def test_rest_api_jednostka_list(client, jednostka):
    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 200


def test_rest_api_wydzial_endpoint_removed():
    # Faza C (#438): model Wydzial znika — zasób /api/v1/wydzial/ nie istnieje.
    # „Wydział" to top-level Jednostka, więc dostępny jest wyłącznie przez
    # /api/v1/jednostka/.
    with pytest.raises(NoReverseMatch):
        reverse("api_v1:wydzial-list")


@pytest.mark.django_db
def test_rest_api_jednostka_detail_niewidoczna_rozwiazuje_sie(client):
    """Regresja zgłoszenia UMLub: jednostka obca ma ``widoczna=False``, ale
    autorzy obcy afiliują się do niej — serializery API emitują do niej
    hiperłącze. Detail MUSI się rozwiązać (200), inaczej harvester dostaje
    404 i eksport pada. Widoczność NIE bramkuje już API — decyduje wyłącznie
    ``nie_eksportuj_przez_api``."""
    obca = baker.make(Jednostka, widoczna=False, nazwa="Obca jednostka")
    res = client.get(reverse("api_v1:jednostka-detail", args=(obca.pk,)))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_jednostka_detail_oznaczona_nie_eksportuj_daje_404(client):
    """Kill switch: jawne ``nie_eksportuj_przez_api=True`` chowa jednostkę
    z API niezależnie od widoczności."""
    ukryta = baker.make(
        Jednostka, widoczna=True, nie_eksportuj_przez_api=True, nazwa="Zablokowana"
    )
    res = client.get(reverse("api_v1:jednostka-detail", args=(ukryta.pk,)))
    assert res.status_code == 404


@pytest.mark.django_db
def test_rest_api_jednostka_list_wg_nie_eksportuj_nie_widocznosci(client):
    """Listing API: widoczność nie ma znaczenia — jednostka ``widoczna=False``
    z ``nie_eksportuj_przez_api=False`` pojawia się, a oflagowana znika."""
    baker.make(Jednostka, widoczna=False, nazwa="NiewidocznaAleEksportowana")
    baker.make(
        Jednostka, widoczna=True, nie_eksportuj_przez_api=True, nazwa="Zablokowana"
    )
    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 200
    nazwy = [r["nazwa"] for r in res.json()["results"]]
    assert "NiewidocznaAleEksportowana" in nazwy
    assert "Zablokowana" not in nazwy
