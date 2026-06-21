"""Repro dla FD#321 — import z CrossRef czasopisma z encją HTML w tytule.

CrossRef REST API zwraca ``container-title`` / ``short-container-title``
z encjami HTML (np. ``Leukemia &amp; Lymphoma``). Wartość ta przepływała
dosłownie przez normalizację i dopasowanie trygramowe, więc nie
dopasowywała się do zapisanego w bazie źródła o nazwie
``Leukemia & Lymphoma`` — w kroku 3 "Dopasowanie źródła" pole „źródło
(czasopismo)" zostawało puste.

DOI z repro: 10.3109/10428194.2014.985672.

Encja ``&amp;`` w środku napisu dokłada 4 dodatkowe znaki, które
zaburzają podobieństwo trygramowe. Dla krótkich tytułów (np. „R&D")
podobieństwo spada poniżej progu 0.6 i dopasowanie znika całkowicie;
dla dłuższych tytułów wynik jest zafałszowany. Naprawą jest
``html.unescape`` zastosowany do wartości z CrossRef *przed*
normalizacją do porównania z bazą.
"""

import pytest
from model_bakery import baker

from bpp.models import Zrodlo
from crossref_bpp.core import Komparator
from import_common.core import (
    normalize_zrodlo_nazwa_for_db_lookup,
    normalize_zrodlo_skrot_for_db_lookup,
)


def test_normalize_zrodlo_nazwa_unescapes_html_entities():
    # Wartość z CrossRef (z encją) po normalizacji musi być identyczna jak
    # znormalizowana wartość zapisana w bazie (z gołym znakiem &).
    assert normalize_zrodlo_nazwa_for_db_lookup(
        "Leukemia &amp; Lymphoma"
    ) == normalize_zrodlo_nazwa_for_db_lookup("Leukemia & Lymphoma")


def test_normalize_zrodlo_skrot_unescapes_html_entities():
    assert normalize_zrodlo_skrot_for_db_lookup(
        "Leuk. &amp; Lymphoma"
    ) == normalize_zrodlo_skrot_for_db_lookup("Leuk. & Lymphoma")


@pytest.mark.django_db
def test_porownaj_container_title_short_title_with_entity():
    # Krótki tytuł z & — bez unescape encja zabija podobieństwo trygramowe
    # (sim ~0.50 < próg 0.60), więc źródło nie zostaje dopasowane.
    zrodlo = baker.make(Zrodlo, nazwa="R&D")

    wynik = Komparator.porownaj_container_title("R&amp;D")

    assert wynik.rekord_po_stronie_bpp == zrodlo


@pytest.mark.django_db
def test_porownaj_container_title_leukemia_lymphoma():
    # Tytuł z oryginalnego zgłoszenia FD#321.
    zrodlo = baker.make(Zrodlo, nazwa="Leukemia & Lymphoma")

    wynik = Komparator.porownaj_container_title("Leukemia &amp; Lymphoma")

    assert wynik.rekord_po_stronie_bpp == zrodlo
