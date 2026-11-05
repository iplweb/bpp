"""Eksport publikacji autora do XLSX z punktacją (obok BibTeX/RIS)."""

import io
from unittest import mock

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker
from openpyxl import load_workbook

from bpp.models import AutorEksportTask, OpcjaWyswietlaniaField

pytestmark = pytest.mark.django_db


@pytest.fixture
def autor_z_punktacja(uczelnia, autor_jan_nowak, wydawnictwo_ciagle, jednostka):
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora

    wydawnictwo_ciagle.tytul_oryginalny = "Praca z punktami"
    wydawnictwo_ciagle.rok = 2022
    wydawnictwo_ciagle.punkty_kbn = 100
    wydawnictwo_ciagle.impact_factor = 2.5
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)
    baker.make(
        Cache_Punktacja_Autora,
        rekord_id=[ct.pk, wydawnictwo_ciagle.pk],
        autor=autor_jan_nowak,
        jednostka=jednostka,
        pkdaut=50,
        slot=0.5,
    )
    return autor_jan_nowak


def _wygeneruj(autor, **pola):
    from bpp.tasks import generuj_eksport_autora

    task = AutorEksportTask.objects.create(autor=autor, format="xlsx", **pola)
    generuj_eksport_autora(str(task.pk))
    task.refresh_from_db()
    assert task.status == "completed", task.error_message
    assert task.nazwa_pliku.endswith(".xlsx")
    return load_workbook(io.BytesIO(task.result_file.read()))


def _wiersze(arkusz):
    return [list(w) for w in arkusz.iter_rows(values_only=True)]


def test_xlsx_bez_punktacji_autora(autor_z_punktacja):
    wb = _wygeneruj(autor_z_punktacja)
    assert wb.sheetnames == ["Publikacje", "Podsumowanie"]

    naglowek, *dane = _wiersze(wb["Publikacje"])
    assert "PKdAut" not in naglowek
    assert len(dane) == 1
    wiersz = dict(zip(naglowek, dane[0], strict=True))
    assert wiersz["Rok"] == 2022
    assert wiersz["Tytuł oryginalny"] == "Praca z punktami"
    assert float(wiersz["PK"]) == 100
    assert float(wiersz["Impact Factor"]) == 2.5

    naglowek, *dane = _wiersze(wb["Podsumowanie"])
    assert naglowek == ["Rok", "Liczba prac", "Σ PK", "Σ IF"]
    assert dane[0][:2] == [2022, 1]


def test_xlsx_z_punktacja_autora(autor_z_punktacja):
    wb = _wygeneruj(autor_z_punktacja, z_punktacja_autora=True)

    naglowek, wiersz = _wiersze(wb["Publikacje"])
    wiersz = dict(zip(naglowek, wiersz, strict=True))
    assert float(wiersz["PKdAut"]) == 50
    assert float(wiersz["Slot"]) == 0.5

    naglowek, wiersz = _wiersze(wb["Podsumowanie"])
    wiersz = dict(zip(naglowek, wiersz, strict=True))
    assert float(wiersz["Σ PKdAut"]) == 50


def test_xlsx_punktacja_pomija_statusy_ukryte_dla_slotow(
    autor_z_punktacja, wydawnictwo_ciagle
):
    wb = _wygeneruj(
        autor_z_punktacja,
        z_punktacja_autora=True,
        ukryte_statusy_slotow=[wydawnictwo_ciagle.status_korekty_id],
    )
    naglowek, wiersz = _wiersze(wb["Publikacje"])
    wiersz = dict(zip(naglowek, wiersz, strict=True))
    # Praca zostaje na liście, ale bez punktacji autora.
    assert wiersz["Tytuł oryginalny"] == "Praca z punktami"
    assert wiersz["PKdAut"] is None


@pytest.mark.parametrize(
    "opcja,oczekiwane",
    [
        (OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE, True),
        (OpcjaWyswietlaniaField.POKAZUJ_NIGDY, False),
    ],
)
def test_start_xlsx_bramkuje_punktacje_jak_sekcja_slotow(
    client, django_user_model, uczelnia, autor_z_punktacja, opcja, oczekiwane
):
    uczelnia.pokazuj_raport_slotow_autor = opcja
    uczelnia.save()
    client.force_login(
        django_user_model.objects.create_user(username="czytelnik", password="x")
    )
    url = reverse("bpp:autor_eksport_start", args=(autor_z_punktacja.pk, "xlsx"))
    assert client.get(url).status_code == 200

    with mock.patch("bpp.tasks.generuj_eksport_autora.delay"):
        resp = client.post(url)
    assert resp.status_code == 302
    task = AutorEksportTask.objects.get(autor=autor_z_punktacja)
    assert task.format == "xlsx"
    assert task.z_punktacja_autora is oczekiwane


def test_start_bib_nie_ustawia_punktacji(
    client, django_user_model, uczelnia, autor_z_punktacja
):
    uczelnia.pokazuj_raport_slotow_autor = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.save()
    client.force_login(
        django_user_model.objects.create_user(username="czytelnik", password="x")
    )
    url = reverse("bpp:autor_eksport_start", args=(autor_z_punktacja.pk, "bib"))
    with mock.patch("bpp.tasks.generuj_eksport_autora.delay"):
        client.post(url)
    task = AutorEksportTask.objects.get(autor=autor_z_punktacja)
    assert task.z_punktacja_autora is False
