from io import BytesIO
from urllib.parse import urlencode

import pytest
from django.urls import reverse
from openpyxl import load_workbook


@pytest.mark.parametrize("dziel_na_jednostki_i_wydzialy", [True, False])
def test_raport_slotow_uczelnia_brak_danych(
    admin_client, rok, dziel_na_jednostki_i_wydzialy,
):
    res = admin_client.get(
        reverse("raport_slotow:raport-uczelnia")
        + "?"
        + urlencode(
            {
                "od_roku": rok,
                "do_roku": rok,
                "dziel_na_jednostki_i_wydzialy": dziel_na_jednostki_i_wydzialy,
                "_export": "html",
                "maksymalny_slot": 1,
            }
        )
    )

    assert res.status_code == 200
    assert "Brak danych" in res.rendered_content


@pytest.mark.parametrize("dziel_na_jednostki_i_wydzialy", [True, False])
def test_raport_slotow_uczelnia_sa_dane(
    admin_client, rekord_slotu, rok, dziel_na_jednostki_i_wydzialy,
):
    url = (
        reverse("raport_slotow:raport-uczelnia")
        + "?"
        + urlencode(
            {
                "od_roku": rok,
                "do_roku": rok,
                "dziel_na_jednostki_i_wydzialy": dziel_na_jednostki_i_wydzialy,
                "_export": "html",
                "maksymalny_slot": 20,
            }
        )
    )

    res = admin_client.get(url)
    assert res.status_code == 200
    assert "Brak danych" not in res.rendered_content

    res = admin_client.get(
        reverse("raport_slotow:raport-uczelnia")
        + "?"
        + urlencode(
            {
                "od_roku": rok,
                "do_roku": rok,
                "dziel_na_jednostki_i_wydzialy": dziel_na_jednostki_i_wydzialy,
                "_export": "xlsx",
                "maksymalny_slot": 20,
            }
        )
    )
    assert res.status_code == 200
    wb = load_workbook(BytesIO(res.content))
    assert len(wb.get_sheet_names()) > 0
