"""Item 9: globalny opt-in ``przepnij_wszystkie_prace`` pre-zaznacza per-wiersz
``przepnij_prace`` w analizie (dla wierszy z autorem i rozstrzygniętą jednostką).
LIVEOPS.RUNNER='eager' → analiza rusza synchronicznie w POST-cie mapowania."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka, Tytul
from import_pracownikow.models import ImportPracownikow


def _import_z_jednym_dopasowanym(admin_user, *, przepnij):
    """Import z 1 wierszem twardo dopasowanym (autor + istniejąca jednostka),
    analiza odpalona przez POST mapowania. Zwraca odświeżony import."""
    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa", skrot="Kat. T.")
    Tytul.objects.get_or_create(skrot="dr", defaults={"nazwa": "doktor"})
    autor = baker.make(
        Autor, nazwisko="Zielinski", imiona="Adam", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)

    csv = (f"Osoba;Nazwa jednostki\ndr Adam Zielinski;{jednostka.nazwa}\n").encode()
    imp = ImportPracownikow(
        owner=admin_user,
        stan=ImportPracownikow.STAN_UTWORZONY,
        przepnij_wszystkie_prace=przepnij,
    )
    imp.plik_xls = SimpleUploadedFile("p.csv", csv)
    imp.save()
    return imp, autor


@pytest.mark.django_db
def test_przepnij_wszystkie_pre_zaznacza_flage(admin_client, admin_user):
    """Item 9: gdy import ma ``przepnij_wszystkie_prace=True``, analiza ustawia
    ``przepnij_prace=True`` dla wiersza z autorem i rozstrzygniętą jednostką."""
    imp, autor = _import_z_jednym_dopasowanym(admin_user, przepnij=True)
    url_map = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    resp = admin_client.post(
        url_map,
        {
            "kol__osoba": "osoba_sklejona",
            "kol__nazwa_jednostki": "nazwa_jednostki",
            "zapisz_profil": False,
            "nazwa_profilu": "",
        },
    )
    assert resp.status_code == 302
    imp.refresh_from_db()
    assert imp.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    assert row.przepnij_prace is True


@pytest.mark.django_db
def test_bez_przepnij_wszystkie_flaga_domyslnie_odznaczona(admin_client, admin_user):
    """Item 9: domyślnie (``przepnij_wszystkie_prace=False``) analiza NIE
    zaznacza ``przepnij_prace``."""
    imp, autor = _import_z_jednym_dopasowanym(admin_user, przepnij=False)
    url_map = reverse("import_pracownikow:mapowanie", kwargs={"pk": imp.pk})
    admin_client.post(
        url_map,
        {
            "kol__osoba": "osoba_sklejona",
            "kol__nazwa_jednostki": "nazwa_jednostki",
            "zapisz_profil": False,
            "nazwa_profilu": "",
        },
    )
    imp.refresh_from_db()
    row = imp.importpracownikowrow_set.get()
    assert row.autor_id == autor.pk
    assert row.przepnij_prace is False
