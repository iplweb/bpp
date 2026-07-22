"""Widoki importu a multi-hosted uczelnia:

- ``NowyImportView`` łapie uczelnię z requestu i utrwala na imporcie,
- bramka: >1 uczelnia bez mapowania domeny → wejście redirectuje na home,
- pule „Mapuj na" / „Wydział (parent)" na ekranie ``/jednostki/`` są zawężone
  do uczelni bieżącego requestu.

Uwaga: autouse fixture ``_biezaca_uczelnia_importu`` (conftest) tworzy jedną
uczelnię zmapowaną na host klienta dla testów z klientem. Testy multi-hosted
zarządzają uczelniami jawnie — ``ustaw_biezaca_uczelnie`` przepina host na
wskazaną uczelnię (zwalniając go od autouse-uczelni)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia
from import_pracownikow.models import ImportPracownikow, ImportPracownikowJednostka
from import_pracownikow.tests._helpers import ustaw_biezaca_uczelnie

BRAK = ImportPracownikowJednostka.TRYB_BRAK
AKCEPTUJ = ImportPracownikowJednostka.DECYZJA_AKCEPTUJ
MAPUJ = ImportPracownikowJednostka.DECYZJA_MAPUJ


def _jedyna_uczelnia():
    """Utwardza „dokładnie jedna uczelnia" (kasuje ambient/autouse-nadmiar)."""
    u = baker.make(Uczelnia)
    Uczelnia.objects.exclude(pk=u.pk).delete()
    return u


@pytest.mark.django_db
def test_nowy_import_lapie_uczelnie_z_requestu(admin_client):
    """POST na ``/new/`` tworzy import z ustawioną ``uczelnia`` (z requestu —
    przy jednej uczelni to ona przez fallback ``get_single_uczelnia_or_none``)."""
    u = _jedyna_uczelnia()
    plik = SimpleUploadedFile(
        "wykaz.xlsx",
        b"PK\x03\x04 dummy",  # form to FileField — nie waliduje treści xlsx tutaj
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    resp = admin_client.post(reverse("import_pracownikow:new"), {"plik_xls": plik})
    assert resp.status_code == 302  # redirect na mapowanie
    imp = ImportPracownikow.objects.latest("pk")
    assert imp.uczelnia_id == u.pk


@pytest.mark.django_db
def test_jednostki_redirect_gdy_uczelnia_nieokreslona(admin_client, admin_user):
    """>1 uczelnia + brak mapowania domeny → wejście na /jednostki/ redirectuje
    na home (bramka „brak uczelni"). Kasujemy autouse-uczelnię, by odtworzyć
    scenariusz nierozstrzygalnej uczelni."""
    Uczelnia.objects.all().delete()
    baker.make(Uczelnia)
    baker.make(Uczelnia)  # >1 i brak mapowania → get_for_request = None
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        uczelnia=None,
    )
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 302
    assert resp.url == "/"


@pytest.mark.django_db
def test_jednostki_bez_ostrzezenia_gdy_uczelnia_znana(
    admin_client, admin_user, settings
):
    """Uczelnia ustalona (zmapowana na host) → brak ostrzeżenia, mimo >1 uczelni."""
    baker.make(Uczelnia)
    u = baker.make(Uczelnia)
    host = ustaw_biezaca_uczelnie(u, settings)
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        uczelnia=u,
    )
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="Zakład Do Utworzenia",
        tryb=BRAK,
        utworzona=None,
    )
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url, HTTP_HOST=host)
    assert resp.status_code == 200
    assert 'data-uczelnia-nieokreslona="1"' not in resp.content.decode()


@pytest.mark.django_db
def test_picker_pokazuje_tylko_jednostki_uczelni_importu(
    admin_client, admin_user, settings
):
    """Multi-hosted: pula „Mapuj na" na /jednostki/ pokazuje TYLKO jednostki
    uczelni importu — jednostki innej uczelni są niewidoczne w selektorze."""
    u_import = baker.make(Uczelnia)
    u_inna = baker.make(Uczelnia)
    host = ustaw_biezaca_uczelnie(u_import, settings)
    baker.make(
        Jednostka,
        nazwa="Katedra Mojej Uczelni",
        skrot="KMU",
        uczelnia=u_import,
        skupia_pracownikow=True,
        widoczna=True,
    )
    baker.make(
        Jednostka,
        nazwa="Katedra Obcej Uczelni",
        skrot="KOU",
        uczelnia=u_inna,
        skupia_pracownikow=True,
        widoczna=True,
    )
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        uczelnia=u_import,
    )
    baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="Zrodlowa",
        tryb=BRAK,
        utworzona=None,
    )
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    content = admin_client.get(url, HTTP_HOST=host).content.decode()
    assert "Katedra Mojej Uczelni" in content
    assert "Katedra Obcej Uczelni" not in content


@pytest.mark.django_db
def test_post_odrzuca_mape_na_jednostke_innej_uczelni(
    admin_client, admin_user, settings
):
    """Twarda obrona serwera: POST „mapuj na" jednostkę INNEJ uczelni jest
    odrzucany (spoza puli ``_z_puli``) — cel nie zostaje ustawiony, walidacja
    „mapuj bez celu" alarmuje i NIE zapisuje (re-render 200, nie redirect)."""
    u_import = baker.make(Uczelnia)
    u_inna = baker.make(Uczelnia)
    host = ustaw_biezaca_uczelnie(u_import, settings)
    j_obca = baker.make(
        Jednostka,
        nazwa="Obca",
        skrot="OB",
        uczelnia=u_inna,
        skupia_pracownikow=True,
        widoczna=True,
    )
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
        uczelnia=u_import,
    )
    dec = baker.make(
        ImportPracownikowJednostka,
        parent=imp,
        nazwa_zrodlowa="Zrodlowa",
        tryb=BRAK,
        decyzja=AKCEPTUJ,
        utworzona=None,
    )
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url,
        {f"dec_{dec.pk}_decyzja": MAPUJ, f"dec_{dec.pk}_wybrana": str(j_obca.pk)},
        HTTP_HOST=host,
    )
    assert resp.status_code == 200  # re-render z alarmem, brak redirectu
    dec.refresh_from_db()
    assert dec.wybrana_jednostka_id is None  # obca jednostka odrzucona (spoza puli)
    assert dec.decyzja == AKCEPTUJ  # nic nie zapisano (POST nie przeszedł walidacji)
