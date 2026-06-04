"""Testy optymalizacji triggera cache (issue #311): widoki per-typ wystawiają
surową kolumnę object_id_raw, a bpp_refresh_cache() filtruje po niej (index seek)
zamiast po wyliczanej kolumnie-tablicy na unii. Zachowanie cache musi pozostać
identyczne — to jest siatka bezpieczeństwa dla tej zmiany.
"""

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import Autor, Jednostka, Rekord, Wydawnictwo_Ciagle

VIEWS_Z_OBJECT_ID_RAW = [
    "bpp_wydawnictwo_ciagle_view",
    "bpp_wydawnictwo_zwarte_view",
    "bpp_patent_view",
    "bpp_praca_doktorska_view",
    "bpp_praca_habilitacyjna_view",
    "bpp_wydawnictwo_ciagle_autorzy",
    "bpp_wydawnictwo_zwarte_autorzy",
    "bpp_patent_autorzy",
    "bpp_praca_doktorska_autorzy",
    "bpp_praca_habilitacyjna_autorzy",
]


@pytest.mark.django_db
def test_object_id_raw_obecne_na_wszystkich_widokach():
    with connection.cursor() as c:
        for v in VIEWS_Z_OBJECT_ID_RAW:
            c.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = %s AND column_name = 'object_id_raw'",
                [v],
            )
            assert c.fetchone() is not None, f"{v} nie ma kolumny object_id_raw"


@pytest.mark.django_db
def test_object_id_raw_daje_index_seek_na_pk():
    """Filtr po object_id_raw musi schodzić do Index Cond na PK tabeli bazowej,
    nie do Seq Scan (sedno optymalizacji)."""
    wc = baker.make(Wydawnictwo_Ciagle)
    with connection.cursor() as c:
        c.execute(
            "EXPLAIN SELECT * FROM bpp_wydawnictwo_ciagle_view "
            "WHERE object_id_raw = %s",
            [wc.pk],
        )
        plan = "\n".join(row[0] for row in c.fetchall())
    assert "Index Cond" in plan, plan
    assert "Seq Scan on bpp_wydawnictwo_ciagle " not in plan, plan


@pytest.mark.django_db
def test_edycja_publikacji_odswieza_rekord_mat(standard_data, denorms):
    wc = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="STARY TYTUL", szczegoly="sz", uwagi="u"
    )
    assert Rekord.objects.get_for_model(wc).tytul_oryginalny == "STARY TYTUL"
    wc.tytul_oryginalny = "NOWY TYTUL"
    wc.save()
    assert Rekord.objects.get_for_model(wc).tytul_oryginalny == "NOWY TYTUL"


@pytest.mark.django_db
def test_dodanie_i_usuniecie_autora_odswieza_autorzy_mat(standard_data, denorms):
    wc = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Test", szczegoly="sz", uwagi="u"
    )
    a = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    j = baker.make(Jednostka)
    wca = wc.dodaj_autora(a, j)
    denorms.flush()
    assert Rekord.objects.get_for_model(wc).autorzy_set.filter(autor=a).exists()

    # edycja/usunięcie jednego wiersza *_autor (ścieżka through-table z autor_id)
    wca.delete()
    denorms.flush()
    assert not Rekord.objects.get_for_model(wc).autorzy_set.filter(autor=a).exists()
