from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime
from model_bakery import baker

from bpp.models import Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_detail(client, wydawnictwo_zwarte):
    res = client.get(
        reverse("api_v1:wydawnictwo_zwarte-detail", args=(wydawnictwo_zwarte.pk,))
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_list(client, wydawnictwo_zwarte):
    res = client.get(reverse("api_v1:wydawnictwo_zwarte-list"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_filtering_1(api_client, wydawnictwo_zwarte):
    czas = localtime(wydawnictwo_zwarte.ostatnio_zmieniony).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    res = api_client.get(
        reverse("api_v1:wydawnictwo_zwarte-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_filtering_2(api_client, wydawnictwo_zwarte):
    czas = localtime(
        wydawnictwo_zwarte.ostatnio_zmieniony + timedelta(seconds=1)
    ).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:wydawnictwo_zwarte-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_filtering_rok(api_client, wydawnictwo_ciagle, rok):
    res = api_client.get(
        reverse("api_v1:wydawnictwo_zwarte-list") + f"?rok_min={rok + 1}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_ukryj_status(
    api_client, wydawnictwo_zwarte, uczelnia, przed_korekta, po_korekcie
):
    res = api_client.get(reverse("api_v1:wydawnictwo_zwarte-list"))
    assert res.json()["count"] == 1

    wydawnictwo_zwarte.status_korekty = przed_korekta
    wydawnictwo_zwarte.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:wydawnictwo_zwarte-list"))
    assert res.json()["count"] == 0


@pytest.fixture
def wiele_wydawnictw_zwartych(db):
    # Create one template object using baker.make to get all required fields with defaults
    template = baker.make(Wydawnictwo_Zwarte)

    # Use bulk_create for 100x performance improvement over individual saves
    # Copy all fields from template except PK (id) and cached properties
    Wydawnictwo_Zwarte.objects.bulk_create(
        [
            Wydawnictwo_Zwarte(
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
def test_rest_api_wydawnictwo_zwarte_no_queries(
    wiele_wydawnictw_zwartych, django_assert_max_num_queries, api_client
):
    # 12 (było 11): wyrwanie opis_bibliograficzny.html z dbtemplates (#329)
    # dokłada jedno Site.objects.get_current() (ścieżka loadera dbtemplates po
    # skasowaniu wiersza). Stałe O(1), indeksowane po PK; w produkcji
    # amortyzowane przez SITE_CACHE (pytest-django czyści go per-test — stąd
    # widać to zapytanie tutaj, a nie na produkcji).
    with django_assert_max_num_queries(12):
        api_client.get(reverse("api_v1:wydawnictwo_zwarte-list"))


TEKST_STRESZCZENIA = b"Tekst streszczenia"
TEXT_OF_SUMMARY = b"Text of summary"


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_html_rendering(
    wiele_wydawnictw_zwartych, admin_client
):
    res = admin_client.get(
        reverse("api_v1:wydawnictwo_zwarte-list"),
        headers={"Accept": "text/html"},
    )
    assert res.status_code == 200


@pytest.fixture
def wydawnictwo_zwarte_ze_streszczeniami(wydawnictwo_zwarte, jezyki):
    wydawnictwo_zwarte.streszczenia.create(
        jezyk_streszczenia=jezyki["pol."], streszczenie=TEKST_STRESZCZENIA
    )

    wydawnictwo_zwarte.streszczenia.create(
        jezyk_streszczenia=jezyki["ang."], streszczenie=TEXT_OF_SUMMARY
    )

    return wydawnictwo_zwarte


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_streszczenia_eksport(
    wydawnictwo_zwarte_ze_streszczeniami, client
):
    res = client.get(
        reverse(
            "api_v1:wydawnictwo_zwarte-detail",
            args=(wydawnictwo_zwarte_ze_streszczeniami.pk,),
        )
    )

    for elem in res.json()["streszczenia"]:
        ts = client.get(elem)
        assert (TEXT_OF_SUMMARY in ts.content) or (TEKST_STRESZCZENIA in ts.content)


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_autor_filter_autor(
    api_client, wydawnictwo_zwarte, autor_jan_kowalski, autor_jan_nowak, jednostka
):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    res = api_client.get(
        reverse("api_v1:wydawnictwo_zwarte_autor-list")
        + f"?autor={autor_jan_kowalski.pk}"
    )
    assert res.json()["count"] == 1

    res = api_client.get(
        reverse("api_v1:wydawnictwo_zwarte_autor-list") + f"?autor={autor_jan_nowak.pk}"
    )
    assert res.json()["count"] == 0
