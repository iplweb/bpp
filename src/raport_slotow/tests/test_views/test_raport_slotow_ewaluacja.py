from io import BytesIO

import pytest
from django.urls import reverse
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import Jednostka
from raport_slotow.models import RaportUczelniaEwaluacjaView


def _ustaw_rozne_wydzialy(praca_z_dyscyplina, drugi_wydzial):
    autorstwo = praca_z_dyscyplina.autorzy_set.select_related(
        "autor", "jednostka__wydzial"
    ).get()

    afiliowany_wydzial = autorstwo.jednostka.wydzial
    afiliowany_wydzial.nazwa = "Wydział afiliowanej jednostki"
    afiliowany_wydzial.save(update_fields=["nazwa"])

    drugi_wydzial.nazwa = "Wydział aktualnej jednostki"
    drugi_wydzial.save(update_fields=["nazwa"])
    aktualna_jednostka = baker.make(
        Jednostka,
        nazwa="Aktualna jednostka autora",
        skrot="AJA",
        uczelnia=drugi_wydzial.uczelnia,
        parent=drugi_wydzial,
    )
    aktualna_jednostka.refresh_from_db()

    autorstwo.autor.aktualna_jednostka = aktualna_jednostka
    autorstwo.autor.save(update_fields=["aktualna_jednostka"])
    autorstwo.autor.refresh_from_db()

    assert autorstwo.autor.aktualna_jednostka_id == aktualna_jednostka.pk
    assert aktualna_jednostka.wydzial_id == drugi_wydzial.pk

    return drugi_wydzial.nazwa, afiliowany_wydzial.nazwa


def test_raport_slotow_ewaluacja_parametry_view(admin_client):
    res = admin_client.get(reverse("raport_slotow:index-ewaluacja"))
    assert res.status_code == 200


def test_raport_slotow_ewaluacja_parametry_view_post(admin_client):
    res = admin_client.post(
        reverse("raport_slotow:index-ewaluacja"),
        {"od_roku": 2020, "do_roku": 2020, "_export": "html"},
    )
    assert res.status_code == 302


def test_raport_slotow_ewaluacja_raport(
    admin_client,
    praca_z_dyscyplina,
    django_assert_max_num_queries,
    constance_cache_warmed_up,
):
    # Query count increased from 50 to 65 after django-constance was added
    # for runtime configuration (commit 2760c7aa). The constance context
    # processor adds ~12 queries for cache checks on each request.
    with django_assert_max_num_queries(68):
        res = admin_client.get(
            reverse("raport_slotow:raport-ewaluacja")
            + "?_export=html&od_roku=2020&do_roku=2020"
        )
    assert res.status_code == 200


def test_raport_slotow_ewaluacja_raport_xlsx(admin_client, praca_z_dyscyplina):
    res = admin_client.get(
        reverse("raport_slotow:raport-ewaluacja")
        + "?_export=xlsx&od_roku=2020&do_roku=2020"
    )
    assert res.status_code == 200


@pytest.mark.parametrize("uzywaj_wydzialow", [True, False])
def test_raport_slotow_ewaluacja_wydzialy_html_zaleza_od_ustawienia_uczelni(
    admin_client,
    praca_z_dyscyplina,
    uczelnia,
    drugi_wydzial,
    rok,
    uzywaj_wydzialow,
):
    aktualny_wydzial, afiliowany_wydzial = _ustaw_rozne_wydzialy(
        praca_z_dyscyplina, drugi_wydzial
    )
    uczelnia.uzywaj_wydzialow = uzywaj_wydzialow
    uczelnia.save(update_fields=["uzywaj_wydzialow"])

    res = admin_client.get(
        reverse("raport_slotow:raport-ewaluacja"),
        {"_export": "html", "od_roku": rok, "do_roku": rok},
    )

    assert res.status_code == 200
    table = res.context["table"]
    column_names = table.columns.names()
    if uzywaj_wydzialow:
        assert column_names.index("aktualny_wydzial") == (
            column_names.index("aktualna_jednostka") + 1
        )
        assert column_names.index("afiliowany_wydzial") == (
            column_names.index("afiliowana_jednostka") + 1
        )
        row = next(iter(table.rows))
        assert row.get_cell_value("aktualny_wydzial") == aktualny_wydzial
        assert row.get_cell_value("afiliowany_wydzial") == afiliowany_wydzial
    else:
        assert "aktualny_wydzial" not in column_names
        assert "afiliowany_wydzial" not in column_names


@pytest.mark.parametrize("uzywaj_wydzialow", [True, False])
def test_raport_slotow_ewaluacja_wydzialy_xlsx_zaleza_od_ustawienia_uczelni(
    admin_client,
    praca_z_dyscyplina,
    uczelnia,
    drugi_wydzial,
    rok,
    uzywaj_wydzialow,
):
    aktualny_wydzial, afiliowany_wydzial = _ustaw_rozne_wydzialy(
        praca_z_dyscyplina, drugi_wydzial
    )
    uczelnia.uzywaj_wydzialow = uzywaj_wydzialow
    uczelnia.save(update_fields=["uzywaj_wydzialow"])

    res = admin_client.get(
        reverse("raport_slotow:raport-ewaluacja"),
        {"_export": "xlsx", "od_roku": rok, "do_roku": rok},
    )

    assert res.status_code == 200
    rows = list(load_workbook(BytesIO(res.content)).active.iter_rows(values_only=True))
    headers = next(row for row in rows if "Aktualna jednostka" in row)
    values = {value for row in rows for value in row if value is not None}
    if uzywaj_wydzialow:
        assert headers.index("Aktualny wydział") == (
            headers.index("Aktualna jednostka") + 1
        )
        assert headers.index("Afiliowany wydział") == (
            headers.index("Afiliowana jednostka") + 1
        )
        assert aktualny_wydzial in values
        assert afiliowany_wydzial in values
    else:
        assert "Aktualny wydział" not in headers
        assert "Afiliowany wydział" not in headers


@pytest.mark.django_db
def test_RaportUczelniaEwaluacjaView_model(praca_z_dyscyplina):
    assert RaportUczelniaEwaluacjaView.objects.all().count() == 1
