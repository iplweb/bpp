from __future__ import annotations

import django.test.client
from django.http import HttpResponse
from django.urls import reverse

from bpp.models import Autor
from bpp.tests import normalize_response_content


def test_ImportPracownikowResetujPodstawoweMiejscePracyView_nic_do_odpiecia(
    import_pracownikow_performed,
    uczelnia_z_obca_jednostka,
    admin_client: django.test.client.Client,
):
    url = reverse(
        "import_pracownikow:importpracownikow-results",
        kwargs={"pk": import_pracownikow_performed.pk},
    )
    res: HttpResponse = admin_client.get(url)
    assert "tego pliku nie powoduje" in normalize_response_content(res)


def test_ImportPracownikowResetujPodstawoweMiejscePracyView_czlowiek_do_odpiecia(
    import_pracownikow_performed,
    uczelnia_z_obca_jednostka,
    admin_client: django.test.client.Client,
    autor_spoza_pliku: Autor,
    jednostka_spoza_pliku,
):
    autor_spoza_pliku.dodaj_jednostke(jednostka_spoza_pliku)

    url = reverse(
        "import_pracownikow:importpracownikow-results",
        kwargs={"pk": import_pracownikow_performed.pk},
    )
    res: HttpResponse = admin_client.get(url)
    assert "tego pliku nie powoduje" not in normalize_response_content(res)


def test_ImportPracownikowResetujPodstawoweMiejscePracyView_autor_do_odpiecia(
    import_pracownikow_performed,
    uczelnia_z_obca_jednostka,
    admin_client: django.test.client.Client,
    autor_spoza_pliku,
    jednostka_spoza_pliku,
):
    autor_spoza_pliku.dodaj_jednostke(jednostka_spoza_pliku)
    autor_spoza_pliku.refresh_from_db()
    assert autor_spoza_pliku.aktualna_jednostka == jednostka_spoza_pliku

    url = reverse(
        "import_pracownikow:importpracownikow-resetuj-podstawowe-miejsce-pracy",
        kwargs={"pk": import_pracownikow_performed.pk},
    )
    admin_client.get(url)

    autor_spoza_pliku.refresh_from_db()
    assert autor_spoza_pliku.aktualna_jednostka is None
