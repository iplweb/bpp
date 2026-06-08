import pytest
from django.core.files.base import ContentFile
from django.urls import reverse
from model_bakery import baker

from zglos_publikacje.models import (
    Zgloszenie_Publikacji,
    Zgloszenie_Publikacji_Zalacznik,
)


def _zgloszenie_z_zalacznikiem(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path)
    settings.SENDFILE_ROOT = str(tmp_path)

    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Zgłoszenie z plikami",
        email="autor@example.com",
        rok=2024,
        rodzaj_zglaszanej_publikacji=Zgloszenie_Publikacji.Rodzaje.ARTYKUL,
        forma_dostepu=Zgloszenie_Publikacji.FormyDostepu.OGRANICZONY,
        oryginalna_nazwa_pliku="legacy.pdf",
    )
    zgloszenie.plik.save("legacy.pdf", ContentFile(b"legacy"), save=True)

    zalacznik = Zgloszenie_Publikacji_Zalacznik.objects.create(
        zgloszenie=zgloszenie,
        oryginalna_nazwa_pliku="zalacznik.pdf",
        kolejnosc=0,
    )
    zalacznik.plik.save("zalacznik.pdf", ContentFile(b"zalacznik"), save=True)

    return zgloszenie, zalacznik


@pytest.mark.django_db
def test_zgloszenie_publikacji_admin_pokazuje_linki_do_zalacznikow(
    admin_client, tmp_path, settings
):
    zgloszenie, zalacznik = _zgloszenie_z_zalacznikiem(tmp_path, settings)

    change_url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_change",
        args=[zgloszenie.pk],
    )
    legacy_download_url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_plik",
        args=[zgloszenie.pk],
    )
    zalacznik_download_url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_zalacznik",
        args=[zgloszenie.pk, zalacznik.pk],
    )

    response = admin_client.get(change_url)

    assert response.status_code == 200
    html = response.content.decode()
    assert "legacy.pdf" in html
    assert "zalacznik.pdf" in html
    assert legacy_download_url in html
    assert zalacznik_download_url in html
    assert "/media/protected/" not in html


@pytest.mark.django_db
def test_zgloszenie_publikacji_admin_pobiera_zalacznik(
    admin_client, tmp_path, settings
):
    zgloszenie, zalacznik = _zgloszenie_z_zalacznikiem(tmp_path, settings)
    download_url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_pobierz_zalacznik",
        args=[zgloszenie.pk, zalacznik.pk],
    )

    response = admin_client.get(download_url)

    assert response.status_code == 200
    assert "zalacznik.pdf" in response["Content-Disposition"]
