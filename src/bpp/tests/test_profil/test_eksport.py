"""Testy eksportu publikacji autora do BibTeX i RIS (§3.3)."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.export.ris import export_to_ris
from bpp.models import Wydawnictwo_Zwarte

pytestmark = pytest.mark.django_db


def _zbuduj_autora_z_pracami(
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    """Podpina jeden artykuł i jedno zwarte pod autora i odświeża cache."""
    wydawnictwo_ciagle.tytul_oryginalny = "Artykuł testowy o eksporcie"
    wydawnictwo_ciagle.doi = "10.1234/test.doi"
    wydawnictwo_ciagle.tom = "12"
    wydawnictwo_ciagle.nr_zeszytu = "3"
    wydawnictwo_ciagle.strony = "100-110"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)

    wydawnictwo_zwarte.tytul_oryginalny = "Książka testowa o eksporcie"
    wydawnictwo_zwarte.save()
    wydawnictwo_zwarte.dodaj_autora(autor_jan_nowak, jednostka)

    denorms.flush()


def test_eksport_bib_zwraca_bibtex(
    client,
    transactional_db,
    standard_data,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    _zbuduj_autora_z_pracami(
        wydawnictwo_ciagle, wydawnictwo_zwarte, autor_jan_nowak, jednostka, denorms
    )

    url = reverse("bpp:autor_eksport_bibtex", args=(autor_jan_nowak.pk,))
    resp = client.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/x-bibtex")
    disp = resp["Content-Disposition"]
    assert "attachment" in disp
    assert ".bib" in disp

    body = resp.content.decode("utf-8")
    assert "@article" in body
    assert "Nowak" in body


def test_eksport_ris_zwraca_ris(
    client,
    transactional_db,
    standard_data,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    denorms,
):
    _zbuduj_autora_z_pracami(
        wydawnictwo_ciagle, wydawnictwo_zwarte, autor_jan_nowak, jednostka, denorms
    )

    url = reverse("bpp:autor_eksport_ris", args=(autor_jan_nowak.pk,))
    resp = client.get(url)

    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("application/x-research-info-systems")
    disp = resp["Content-Disposition"]
    assert "attachment" in disp
    assert ".ris" in disp

    body = resp.content.decode("utf-8")
    assert "TY  - JOUR" in body
    assert "AU  - " in body
    assert "ER  -" in body
    assert "Artykuł testowy o eksporcie" in body
    assert f"PY  - {wydawnictwo_ciagle.rok}" in body


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


def test_eksport_pusty_autor_nie_wybucha(client, autor_jan_nowak):
    url_bib = reverse("bpp:autor_eksport_bibtex", args=(autor_jan_nowak.pk,))
    url_ris = reverse("bpp:autor_eksport_ris", args=(autor_jan_nowak.pk,))

    resp_bib = client.get(url_bib)
    assert resp_bib.status_code == 200

    resp_ris = client.get(url_ris)
    assert resp_ris.status_code == 200


def test_eksport_nieistniejacy_autor_404(client):
    url = reverse("bpp:autor_eksport_bibtex", args=(999999,))
    resp = client.get(url)
    assert resp.status_code == 404
