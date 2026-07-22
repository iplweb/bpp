from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_detail(client, wydawnictwo_ciagle):
    res = client.get(
        reverse("api_v1:wydawnictwo_ciagle-detail", args=(wydawnictwo_ciagle.pk,))
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_list(client, wydawnictwo_ciagle):
    res = client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_filtering_1(api_client, wydawnictwo_ciagle):
    czas = localtime(wydawnictwo_ciagle.ostatnio_zmieniony).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    res = api_client.get(
        reverse("api_v1:wydawnictwo_ciagle-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_filtering_2(api_client, wydawnictwo_ciagle):
    czas = localtime(
        wydawnictwo_ciagle.ostatnio_zmieniony + timedelta(seconds=1)
    ).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:wydawnictwo_ciagle-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_filtering_rok(api_client, wydawnictwo_ciagle, rok):
    res = api_client.get(
        reverse("api_v1:wydawnictwo_ciagle-list") + f"?rok_min={rok + 1}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_ukryj_status(
    api_client, wydawnictwo_ciagle, uczelnia, przed_korekta, po_korekcie
):
    res = api_client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
    assert res.json()["count"] == 1

    wydawnictwo_ciagle.status_korekty = przed_korekta
    wydawnictwo_ciagle.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
    assert res.json()["count"] == 0


@pytest.fixture
def wiele_wydawnictw_ciaglych(db):
    # Create one template object using baker.make to get all required fields with defaults
    template = baker.make(Wydawnictwo_Ciagle)

    # Use bulk_create for 100x performance improvement over individual saves
    # Copy all fields from template except PK (id) and cached properties
    Wydawnictwo_Ciagle.objects.bulk_create(
        [
            Wydawnictwo_Ciagle(
                rok=template.rok,
                jezyk=template.jezyk,
                typ_kbn=template.typ_kbn,
                status_korekty=template.status_korekty,
                charakter_formalny=template.charakter_formalny,
                # Copy optional fields that have defaults
                tytul_oryginalny=template.tytul_oryginalny or f"Wydawnictwo {i}",
            )
            for i in range(100)
        ]
    )


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_no_queries(
    wiele_wydawnictw_ciaglych, django_assert_max_num_queries, api_client
):
    with django_assert_max_num_queries(11):
        api_client.get(reverse("api_v1:wydawnictwo_ciagle-list"))


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_html_rendering(
    wiele_wydawnictw_ciaglych, admin_client
):
    res = admin_client.get(
        reverse("api_v1:wydawnictwo_ciagle-list"),
        headers={"Accept": "text/html"},
    )
    assert res.status_code == 200


TEKST_STRESZCZENIA = b"Tekst streszczenia"
TEXT_OF_SUMMARY = b"Text of summary"


@pytest.fixture
def wydawnictwo_ciagle_ze_streszczeniami(wydawnictwo_ciagle, jezyki):
    wydawnictwo_ciagle.streszczenia.create(
        jezyk_streszczenia=jezyki["pol."], streszczenie=TEKST_STRESZCZENIA
    )

    wydawnictwo_ciagle.streszczenia.create(
        jezyk_streszczenia=jezyki["ang."], streszczenie=TEXT_OF_SUMMARY
    )

    return wydawnictwo_ciagle


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_streszczenia_eksport(
    wydawnictwo_ciagle_ze_streszczeniami, client
):
    res = client.get(
        reverse(
            "api_v1:wydawnictwo_ciagle-detail",
            args=(wydawnictwo_ciagle_ze_streszczeniami.pk,),
        )
    )

    for elem in res.json()["streszczenia"]:
        ts = client.get(elem)
        assert (TEXT_OF_SUMMARY in ts.content) or (TEKST_STRESZCZENIA in ts.content)


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_autor_filter_autor(
    api_client, wydawnictwo_ciagle, autor_jan_kowalski, autor_jan_nowak, jednostka
):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    res = api_client.get(
        reverse("api_v1:wydawnictwo_ciagle_autor-list")
        + f"?autor={autor_jan_kowalski.pk}"
    )
    assert res.json()["count"] == 1

    res = api_client.get(
        reverse("api_v1:wydawnictwo_ciagle_autor-list") + f"?autor={autor_jan_nowak.pk}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_autor_ukrywa_nieeksportowane(
    client, wydawnictwo_ciagle, autor_jan_kowalski, jednostka
):
    # Pod-zasób /wydawnictwo_ciagle_autor/ nie może ujawniać powiązań
    # autor-jednostka dla rekordów oznaczonych nie_eksportuj_przez_api=True.
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    res = client.get(reverse("api_v1:wydawnictwo_ciagle_autor-list"))
    assert res.json()["count"] == 1

    wydawnictwo_ciagle.nie_eksportuj_przez_api = True
    wydawnictwo_ciagle.save()
    res = client.get(reverse("api_v1:wydawnictwo_ciagle_autor-list"))
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_streszczenie_ukrywa_nieeksportowane(
    client, wydawnictwo_ciagle_ze_streszczeniami
):
    # Pod-zasób /wydawnictwo_ciagle_streszczenie/ nie może ujawniać abstraktów
    # rekordów wykluczonych z eksportu API.
    res = client.get(reverse("api_v1:wydawnictwo_ciagle_streszczenie-list"))
    assert res.json()["count"] == 2

    wydawnictwo_ciagle_ze_streszczeniami.nie_eksportuj_przez_api = True
    wydawnictwo_ciagle_ze_streszczeniami.save()
    res = client.get(reverse("api_v1:wydawnictwo_ciagle_streszczenie-list"))
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_autor_ukrywa_ukryty_status(
    api_client,
    wydawnictwo_ciagle,
    autor_jan_kowalski,
    jednostka,
    uczelnia,
    przed_korekta,
):
    # Pod-zasób respektuje ukryte statusy korekty (jak rekord-rodzic).
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_ciagle.status_korekty = przed_korekta
    wydawnictwo_ciagle.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:wydawnictwo_ciagle_autor-list"))
    assert res.json()["count"] == 0
