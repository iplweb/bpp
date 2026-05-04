from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime
from model_bakery import baker

from bpp.models import Autor, Praca_Habilitacyjna


@pytest.mark.django_db
def test_rest_api_praca_habilitacyjna_detail(client, praca_habilitacyjna):
    res = client.get(
        reverse("api_v1:praca_habilitacyjna-detail", args=(praca_habilitacyjna.pk,))
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_praca_habilitacyjna_list(client, praca_habilitacyjna):
    res = client.get(reverse("api_v1:praca_habilitacyjna-list"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_praca_habilitacyjna_filtering_1(api_client, praca_habilitacyjna):
    czas = localtime(praca_habilitacyjna.ostatnio_zmieniony).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    res = api_client.get(
        reverse("api_v1:praca_habilitacyjna-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_praca_habilitacyjna_filtering_2(api_client, praca_habilitacyjna):
    czas = localtime(
        praca_habilitacyjna.ostatnio_zmieniony + timedelta(seconds=1)
    ).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:praca_habilitacyjna-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_praca_habilitacyjna_filtering_rok(
    api_client, praca_habilitacyjna, rok
):
    res = api_client.get(
        reverse("api_v1:praca_habilitacyjna-list") + f"?rok_min={rok + 1}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_praca_habilitacyjna_ukryj_status(
    api_client, praca_habilitacyjna, uczelnia, przed_korekta, po_korekcie
):

    res = api_client.get(reverse("api_v1:praca_habilitacyjna-list"))
    assert res.json()["count"] == 1

    praca_habilitacyjna.status_korekty = przed_korekta
    praca_habilitacyjna.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:praca_habilitacyjna-list"))
    assert res.json()["count"] == 0


@pytest.fixture
def wiele_prac_habilitacyjnych(db, typy_odpowiedzialnosci):
    # Create one template object using baker.make to get all required fields with defaults
    template = baker.make(Praca_Habilitacyjna)

    # Create single jednostka for all objects (much faster than 100 separate baker.make calls)
    jednostka = template.jednostka

    # Create 100 different authors (unique constraint on autor_id for Praca_Habilitacyjna)
    autorzy = baker.prepare(Autor, _quantity=100)
    Autor.objects.bulk_create(autorzy)

    # Use bulk_create for 100x performance improvement over individual saves
    # Each Praca_Habilitacyjna must have unique autor (unique constraint)
    Praca_Habilitacyjna.objects.bulk_create(
        [
            Praca_Habilitacyjna(
                autor=autorzy[i],
                jednostka=jednostka,
                rok=template.rok,
                jezyk=template.jezyk,
                typ_kbn=template.typ_kbn,
                status_korekty=template.status_korekty,
                # Copy optional fields that have defaults
                tytul_oryginalny=template.tytul_oryginalny or f"Praca {i}",
            )
            for i in range(100)
        ]
    )


@pytest.mark.django_db
def test_rest_api_praca_habilitacyjna_no_queries(
    wiele_prac_habilitacyjnych,
    django_assert_max_num_queries,
    api_client,
):
    with django_assert_max_num_queries(11):
        api_client.get(reverse("api_v1:praca_habilitacyjna-list"))
