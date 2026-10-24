"""Identyfikatory zewnętrznych profili autora (WoS / Scopus / Google Scholar)."""

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from bpp.util.identyfikatory import (
    normalizuj_google_scholar_id,
    normalizuj_scopus_author_id,
    normalizuj_wos_researcherid,
)


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        ("A-1234-2008", "A-1234-2008"),
        ("  aab-1234-2020 ", "AAB-1234-2020"),
        (
            "https://www.webofscience.com/wos/author/record/ABC-1234-2019",
            "ABC-1234-2019",
        ),
        ("https://www.webofscience.com/wos/author/record/1234567", "1234567"),
        ("http://www.researcherid.com/rid/B-2222-2011", "B-2222-2011"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalizuj_wos_researcherid(wejscie, oczekiwane):
    assert normalizuj_wos_researcherid(wejscie) == oczekiwane


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        ("57190000001", "57190000001"),
        (
            "https://www.scopus.com/authid/detail.uri?authorId=7004212771",
            "7004212771",
        ),
        (
            "https://www.scopus.com/authid/detail.uri?authorId=7004212771&x=1",
            "7004212771",
        ),
        ("", ""),
    ],
)
def test_normalizuj_scopus_author_id(wejscie, oczekiwane):
    assert normalizuj_scopus_author_id(wejscie) == oczekiwane


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        ("qc6CJjYAAAAJ", "qc6CJjYAAAAJ"),
        (
            "https://scholar.google.com/citations?user=qc6CJjYAAAAJ&hl=pl",
            "qc6CJjYAAAAJ",
        ),
        ("https://scholar.google.pl/citations?hl=pl&user=qc6CJjYAAAAJ", "qc6CJjYAAAAJ"),
        ("", ""),
    ],
)
def test_normalizuj_google_scholar_id(wejscie, oczekiwane):
    assert normalizuj_google_scholar_id(wejscie) == oczekiwane


def test_nierozpoznana_wartosc_zostaje_bez_zmian_do_walidacji():
    # Normalizacja nie zgaduje — śmieci przechodzą dalej i odrzuca je walidator.
    assert normalizuj_scopus_author_id("abc") == "abc"


@pytest.mark.django_db
def test_url_profili_budowane_z_identyfikatorow():
    autor = baker.make(
        Autor,
        wos_researcherid="A-1234-2008",
        scopus_author_id="7004212771",
        google_scholar_id="qc6CJjYAAAAJ",
    )
    assert autor.wos_url == (
        "https://www.webofscience.com/wos/author/record/A-1234-2008"
    )
    assert autor.scopus_url == (
        "https://www.scopus.com/authid/detail.uri?authorId=7004212771"
    )
    assert autor.google_scholar_url == (
        "https://scholar.google.com/citations?user=qc6CJjYAAAAJ"
    )


@pytest.mark.django_db
def test_puste_identyfikatory_daja_puste_url():
    autor = baker.make(Autor)
    assert autor.wos_url == ""
    assert autor.scopus_url == ""
    assert autor.google_scholar_url == ""


@pytest.mark.django_db
@pytest.mark.parametrize(
    "pole,wartosc",
    [
        ("wos_researcherid", "nie-id"),
        ("scopus_author_id", "12ab"),
        ("google_scholar_id", "za-krotki"),
    ],
)
def test_walidacja_odrzuca_bledny_format(pole, wartosc):
    autor = baker.make(Autor)
    setattr(autor, pole, wartosc)
    with pytest.raises(ValidationError) as exc:
        autor.full_clean()
    assert pole in exc.value.message_dict


@pytest.mark.django_db
def test_strona_autora_pokazuje_linki_profili(client, uczelnia):
    uczelnia.etykieta_profilu_uczelni = "PPM UML"
    uczelnia.save()
    autor = baker.make(
        Autor,
        wos_researcherid="A-1234-2008",
        scopus_author_id="7004212771",
        google_scholar_id="qc6CJjYAAAAJ",
        url_profilu_uczelni="https://ppm.example.edu.pl/info/author/X1/",
    )
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert autor.wos_url in tresc
    assert autor.scopus_url in tresc
    assert autor.google_scholar_url in tresc
    assert "https://ppm.example.edu.pl/info/author/X1/" in tresc
    assert "PPM UML" in tresc


@pytest.mark.django_db
def test_strona_autora_bez_profili_nie_pokazuje_kart(client):
    autor = baker.make(Autor)
    tresc = client.get(autor.get_absolute_url()).content.decode()
    assert "Web of Science" not in tresc
    assert "Google Scholar" not in tresc
    assert "Profil w portalu uczelni" not in tresc


@pytest.mark.django_db
def test_autor_zapisuje_profile_wklejajac_adresy(client, django_user_model):
    autor = baker.make(Autor)
    user = django_user_model.objects.create_user(username="autor-id", password="x")
    user.autor = autor
    user.save(update_fields=["autor"])
    client.force_login(user)

    resp = client.post(
        reverse("bpp:profil-edycja"),
        {
            "biogram": "",
            "biogram_format": "md",
            "wos_researcherid": (
                "https://www.webofscience.com/wos/author/record/ABC-1234-2019"
            ),
            "scopus_author_id": (
                "https://www.scopus.com/authid/detail.uri?authorId=7004212771"
            ),
            "google_scholar_id": (
                "https://scholar.google.com/citations?user=qc6CJjYAAAAJ&hl=pl"
            ),
            "url_profilu_uczelni": "https://ppm.example.edu.pl/info/author/X1/",
        },
    )
    assert resp.status_code == 302, resp.content.decode()
    autor.refresh_from_db()
    assert autor.wos_researcherid == "ABC-1234-2019"
    assert autor.scopus_author_id == "7004212771"
    assert autor.google_scholar_id == "qc6CJjYAAAAJ"
    assert autor.url_profilu_uczelni == "https://ppm.example.edu.pl/info/author/X1/"


@pytest.mark.django_db
def test_bledny_identyfikator_pokazuje_blad_formularza(client, django_user_model):
    autor = baker.make(Autor)
    user = django_user_model.objects.create_user(username="autor-err", password="x")
    user.autor = autor
    user.save(update_fields=["autor"])
    client.force_login(user)

    resp = client.post(
        reverse("bpp:profil-edycja"),
        {"biogram": "", "biogram_format": "md", "scopus_author_id": "abc"},
    )
    assert resp.status_code == 200
    assert "Scopus Author ID to sam ciąg cyfr" in resp.content.decode()
