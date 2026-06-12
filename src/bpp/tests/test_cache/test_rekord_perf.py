"""Testy wydajnościowe Rekord (spec-optymalizacje-wydajnosci-2026-06).

1. Wyszukanie po slug (PracaViewBySlug — kanoniczny publiczny URL rekordu)
   musi używać indeksu — bez niego każde wejście na stronę rekordu robi
   Seq Scan po całej, szerokiej tabeli bpp_rekord_mat.

2. ma_punktacje_sloty ma kosztować jedno zapytanie, nie dwa osobne EXISTS.
"""

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import Rekord
from bpp.models.cache import Cache_Punktacja_Dyscypliny
from bpp.tests.util import any_ciagle


@pytest.mark.django_db
def test_wyszukanie_po_slug_uzywa_indeksu():
    any_ciagle(tytul_oryginalny="Praca ze slugiem")
    with connection.cursor() as c:
        # enable_seqscan=off: przy małej tabeli planner i tak wybrałby
        # Seq Scan; wyłączenie wymusza indeks JEŚLI ISTNIEJE — a o jego
        # istnienie tu chodzi.
        c.execute("SET enable_seqscan = off")
        c.execute("EXPLAIN SELECT id FROM bpp_rekord_mat WHERE slug = 'nie-ma-takiego'")
        plan = "\n".join(row[0] for row in c.fetchall())
        c.execute("RESET enable_seqscan")
    assert "Seq Scan on bpp_rekord_mat" not in plan, plan


@pytest.mark.django_db
def test_ma_punktacje_sloty_jedno_zapytanie(django_assert_num_queries):
    wc = any_ciagle()
    rekord = Rekord.objects.get_original(wc)
    with django_assert_num_queries(1):
        assert rekord.ma_punktacje_sloty is False


@pytest.mark.django_db
def test_ma_punktacje_sloty_wykrywa_punktacje_dyscypliny():
    """Strażnik: punktacja TYLKO w Cache_Punktacja_Dyscypliny (bez wpisu
    per-autor) nadal daje True — pojedyncze zapytanie musi pokrywać
    obie tabele."""
    wc = any_ciagle()
    rekord = Rekord.objects.get_original(wc)
    baker.make(
        Cache_Punktacja_Dyscypliny,
        rekord_id=list(rekord.pk),
        pkd=10,
        slot=1,
    )
    assert rekord.ma_punktacje_sloty is True
