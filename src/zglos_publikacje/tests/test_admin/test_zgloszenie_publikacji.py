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


@pytest.mark.django_db
def test_zgloszenie_publikacji_admin_przycisk_uzyj_importera_z_doi(admin_client):
    """Freshdesk #380: gdy strona_www to DOI, przycisk przekazuje go do importera."""
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca z DOI",
        strona_www="https://doi.org/10.1234/abc.def",
    )
    change_url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_change",
        args=[zgloszenie.pk],
    )

    response = admin_client.get(change_url)

    assert response.status_code == 200
    html = response.content.decode()
    importer_url = reverse("importer_publikacji:index")
    assert "Użyj importera" in html
    assert importer_url in html
    assert "provider=CrossRef" in html
    assert "10.1234%2Fabc.def" in html


@pytest.mark.django_db
def test_zgloszenie_publikacji_admin_przycisk_uzyj_importera_bez_doi(admin_client):
    """Freshdesk #380/#430: adres niebędący DOI -> importer z providerem WWW."""
    zgloszenie = baker.make(
        Zgloszenie_Publikacji,
        tytul_oryginalny="Praca bez DOI",
        strona_www="https://example.com/papers/123",
    )
    change_url = reverse(
        "admin:zglos_publikacje_zgloszenie_publikacji_change",
        args=[zgloszenie.pk],
    )

    response = admin_client.get(change_url)

    assert response.status_code == 200
    html = response.content.decode()
    assert "Użyj importera" in html
    # FD#430: import z ogólnej strony WWW, nie CrossRef.
    assert "provider=CrossRef" not in html
    assert "provider=Pozosta%C5%82e+strony+WWW" in html
    assert "identifier=https%3A%2F%2Fexample.com%2Fpapers%2F123" in html
