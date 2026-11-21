"""Readable ``__str__`` of the discrepancy views (links, breadcrumbs, messages)."""

import pytest

from bpp.models import Autor_Dyscyplina
from rozbieznosci_dyscyplin.admin import (
    SUBDYSCYPLINA_AUTORA,
    ResultNotifier,
    real_ustaw_dyscypline,
)
from rozbieznosci_dyscyplin.models import RozbieznosciView, RozbieznosciZrodelView


@pytest.mark.django_db
def test_rozbieznosci_view_str(zle_przypisana_praca, autor_jan_kowalski):
    elem = RozbieznosciView.objects.get()

    tekst = str(elem)

    assert "object (" not in tekst
    assert zle_przypisana_praca.tytul_oryginalny in tekst
    assert autor_jan_kowalski.nazwisko in tekst
    assert tekst.endswith(f"({zle_przypisana_praca.rok})")


@pytest.mark.django_db
def test_rozbieznosci_view_str_dlugi_tytul_skrocony(zle_przypisana_praca):
    zle_przypisana_praca.tytul_oryginalny = "<i>Bardzo</i> długi tytuł " * 20
    zle_przypisana_praca.save()

    tekst = str(RozbieznosciView.objects.get())

    assert "<i>" not in tekst
    assert "…" in tekst
    assert len(tekst.split(" — ")[0]) <= 80


@pytest.mark.django_db
def test_rozbieznosci_view_str_brak_powiazanych():
    elem = RozbieznosciView(
        id=[1, 2, 3], rekord_id=[999, 999], autor_id=999999, rok=2024
    )

    tekst = str(elem)

    assert "999999" in tekst
    assert "(2024)" in tekst


@pytest.mark.django_db
def test_rozbieznosci_zrodel_view_str(wydawnictwo_ciagle, zrodlo):
    elem = RozbieznosciZrodelView(
        id=[1, 2, 3, 4],
        zrodlo=zrodlo,
        wydawnictwo_ciagle=wydawnictwo_ciagle,
        rok=2024,
    )

    tekst = str(elem)

    assert "object (" not in tekst
    assert wydawnictwo_ciagle.tytul_oryginalny in tekst
    assert zrodlo.nazwa in tekst
    assert tekst.endswith("(2024)")


@pytest.mark.django_db
def test_rozbieznosci_zrodel_view_str_brak_powiazanych():
    elem = RozbieznosciZrodelView(
        id=[1, 2, 3, 4], zrodlo_id=999998, wydawnictwo_ciagle_id=999997, rok=2024
    )

    tekst = str(elem)

    assert "999998" in tekst
    assert "999997" in tekst


@pytest.mark.django_db
def test_ostrzezenie_bez_object(zle_przypisana_praca):
    Autor_Dyscyplina.objects.filter(
        autor=zle_przypisana_praca.autorzy.first(), rok=zle_przypisana_praca.rok
    ).update(subdyscyplina_naukowa=None)
    pk = RozbieznosciView.objects.get().pk

    notifier = ResultNotifier()
    real_ustaw_dyscypline(SUBDYSCYPLINA_AUTORA, [pk], notifier)

    assert len(notifier.retbuf) == 1
    komunikat = notifier.retbuf[0][1]
    assert "nie ma drugiej dyscypliny" in komunikat
    assert "object (" not in komunikat
