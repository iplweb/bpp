from io import BytesIO

from django.urls import reverse
from openpyxl import load_workbook


def test_raport_slotow_uczelnia_brak_danych(admin_client, rok):
    res = admin_client.get(reverse(
        "raport_slotow:raport-uczelnia",
        kwargs={"od_roku": rok, "do_roku": rok, }
    ))
    assert res.status_code == 200
    assert "Brak danych" in res.rendered_content




def test_raport_slotow_uczelnia_sa_dane(admin_client, rekord_slotu, rok):
    url = reverse("raport_slotow:raport-uczelnia", kwargs={"od_roku": rok, "do_roku": rok, })

    res = admin_client.get(url)
    assert res.status_code == 200
    assert "Brak danych" not in res.rendered_content

    res = admin_client.get(url + "?_export=xlsx")
    assert res.status_code == 200
    wb = load_workbook(BytesIO(res.content))
    assert len(wb.get_sheet_names()) > 0

