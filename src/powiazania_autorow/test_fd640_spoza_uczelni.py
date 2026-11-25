"""FD#640 — sieć powiązań: autor spoza uczelni zostaje w grafie (węzeł,
krawędzie, liczba prac), ale bez sumarycznej punktacji (Σ IF, Σ PK)."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Wydawnictwo_Ciagle
from powiazania_autorow.models import AuthorConnection


@pytest.fixture
def para_autorow(uczelnia_z_obca_jednostka, obca_jednostka, jednostka):
    """Autor uczelni i obcy współautor jednej punktowanej pracy."""
    nasz = baker.make(Autor, imiona="Jan", nazwisko="Nasz")
    Autor_Jednostka.objects.create(autor=nasz, jednostka=jednostka)
    obcy = baker.make(Autor, imiona="Ewa", nazwisko="Obca")
    Autor_Jednostka.objects.create(autor=obcy, jednostka=obca_jednostka)

    praca = baker.make(Wydawnictwo_Ciagle, rok=2022, punkty_kbn=100, impact_factor=2.5)
    praca.dodaj_autora(nasz, jednostka)
    praca.dodaj_autora(obcy, obca_jednostka, afiliuje=False)
    AuthorConnection.objects.create(
        primary_author=nasz, secondary_author=obcy, shared_publications_count=1
    )
    return nasz, obcy


@pytest.mark.django_db
def test_fd640_dane_json_obcy_sasiad_bez_sum(
    client, para_autorow, typy_odpowiedzialnosci
):
    nasz, obcy = para_autorow
    url = reverse("bpp:browse_autor_powiazania_dane", args=[nasz.pk])
    data = client.get(url).json()

    sasiad = data["neighbors"][0]
    assert sasiad["id"] == obcy.pk
    assert sasiad["spoza_uczelni"] is True
    assert sasiad["if_sum"] is None
    assert sasiad["pk_sum"] is None
    # struktura grafu zostaje: liczba wspólnych prac i liczba prac
    assert sasiad["shared"] == 1
    assert sasiad["total_works"] == 1

    # strażnik: autor uczelni (centrum) z sumami jak dotąd
    centrum = data["center"]
    assert centrum["spoza_uczelni"] is False
    assert centrum["pk_sum"] == 100
    assert centrum["if_sum"] == 2.5


@pytest.mark.django_db
def test_fd640_dane_json_obcy_jako_centrum_bez_sum(
    client, para_autorow, typy_odpowiedzialnosci
):
    nasz, obcy = para_autorow
    url = reverse("bpp:browse_autor_powiazania_dane", args=[obcy.pk])
    resp = client.get(url)
    assert resp.status_code == 200  # graf obcego autora zostaje dostępny
    data = resp.json()
    assert data["center"]["pk_sum"] is None
    assert data["center"]["if_sum"] is None
    assert data["neighbors"][0]["id"] == nasz.pk
    assert data["neighbors"][0]["pk_sum"] == 100


@pytest.mark.django_db
def test_fd640_siec_json_obcy_wezel_bez_sum(
    client, para_autorow, typy_odpowiedzialnosci
):
    nasz, obcy = para_autorow
    url = reverse("bpp:browse_autor_powiazania_siec", args=[nasz.pk])
    data = client.get(url).json()

    wezly = {n["id"]: n for n in data["nodes"]}
    assert wezly[obcy.pk]["pk_sum"] is None
    assert wezly[obcy.pk]["if_sum"] is None
    assert wezly[obcy.pk]["total_works"] == 1
    assert wezly[nasz.pk]["pk_sum"] == 100
    assert wezly[nasz.pk]["if_sum"] == 2.5
    assert data["edges"] == [{"source": nasz.pk, "target": obcy.pk, "shared": 1}]
