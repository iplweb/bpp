"""Testy eksportu publikacji autora do BibTeX i RIS (§3.3).

Plik generuje wyłącznie zadanie Celery (``test_eksport_async``); dawne
adresy ``eksport.bib``/``eksport.ris`` tylko przekierowują na stronę startu
eksportu w tle.
"""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.export.ris import export_to_ris
from bpp.models import Autor, AutorEksportTask, Wydawnictwo_Zwarte

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "nazwa,fmt", [("autor_eksport_bibtex", "bib"), ("autor_eksport_ris", "ris")]
)
@pytest.mark.parametrize("zalogowany", [False, True])
def test_dawny_adres_eksportu_przekierowuje_na_start(
    client, admin_user, mocker, nazwa, fmt, zalogowany
):
    delay = mocker.patch("bpp.tasks.generuj_eksport_autora.delay")
    autor = baker.make(Autor)
    if zalogowany:
        client.force_login(admin_user)

    resp = client.get(reverse(f"bpp:{nazwa}", args=(autor.pk,)))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("bpp:autor_eksport_start", args=(autor.pk, fmt))
    # Przekierowanie niczego nie generuje ani nie kolejkuje.
    assert not resp.has_header("Content-Disposition")
    assert not AutorEksportTask.objects.exists()
    delay.assert_not_called()


def test_dawny_adres_nieistniejacy_autor_404_na_starcie(client):
    resp = client.get(reverse("bpp:autor_eksport_bibtex", args=(999999,)), follow=True)
    assert resp.status_code == 404


def test_export_to_ris_artykul_i_ksiazka(
    transactional_db,
    standard_data,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    wydawnictwo_ciagle.tom = "7"
    wydawnictwo_ciagle.nr_zeszytu = "2"
    wydawnictwo_ciagle.strony = "11-22"
    wydawnictwo_ciagle.doi = "10.1/abc"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)
    denorms.flush()

    ris_ciagle = export_to_ris([wydawnictwo_ciagle])
    assert "TY  - JOUR" in ris_ciagle
    assert "VL  - 7" in ris_ciagle
    assert "IS  - 2" in ris_ciagle
    assert "SP  - 11" in ris_ciagle
    assert "EP  - 22" in ris_ciagle
    assert "DO  - 10.1/abc" in ris_ciagle
    assert ris_ciagle.rstrip().endswith("ER  -")

    ris_zwarte = export_to_ris([wydawnictwo_zwarte])
    assert "TY  - BOOK" in ris_zwarte
    assert "ER  -" in ris_zwarte


def test_export_to_ris_rozdzial_ma_typ_chap(
    transactional_db,
    standard_data,
    wydawnictwo_zwarte,
    denorms,
):
    nadrzedne = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Książka nadrzędna")
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = nadrzedne
    wydawnictwo_zwarte.save()

    ris = export_to_ris([wydawnictwo_zwarte])
    assert "TY  - CHAP" in ris


def test_eksport_pusty_autor_nie_wybucha(autor_jan_nowak):
    from bpp.tasks import generuj_eksport_autora

    for fmt in ("bib", "ris"):
        task = AutorEksportTask.objects.create(autor=autor_jan_nowak, format=fmt)
        generuj_eksport_autora(str(task.pk))
        task.refresh_from_db()
        assert task.status == "completed"
