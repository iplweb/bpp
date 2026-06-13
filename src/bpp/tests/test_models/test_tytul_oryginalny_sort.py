"""Testy klucza sortowania tytułu (`tytul_oryginalny_sort`).

Po pożegnaniu z plpython3u logikę dawnego triggera `trigger_tytul_sort`
liczy `ModelPrzeszukiwalny.save()` (bpp/models/abstract/search.py). Tu:
1. czysta funkcja `oblicz_tytul_oryginalny_sort` (wszystkie języki + edge),
2. integracja przez ORM dla Patentu (brak jezyk_id -> "pol.") oraz
   gotcha `update_fields`.
"""

import pytest

from bpp.models.abstract.search import oblicz_tytul_oryginalny_sort


@pytest.mark.parametrize(
    "tytul,jezyk_skrot,oczekiwany",
    [
        # angielski: obcina "the "/"a "
        ("The 'APPROACH'", "ang.", "approach"),
        ("A House", "ang.", "house"),
        ("the the end", "ang.", "end"),  # obcina powtórzony rodzajnik
        # francuski: "la "/"le "/"en "
        ("le 'test'", "fr.", "test"),
        ("La Vie", "fr.", "vie"),
        # niemiecki
        ("Der Spiegel", "niem.", "spiegel"),
        ("Die Welt", "niem.", "welt"),
        ("Das Boot", "niem.", "boot"),
        # włoski / hiszpański
        ("La Strada", "wł.", "strada"),
        ("De La Cosa", "hiszp.", "cosa"),
        # polski (i nieznany język) — bez obcinania rodzajnika
        ("Pełna Treść", "pol.", "pełna treść"),
        ("The Title", "pol.", "the title"),  # po polsku NIE obcinamy "the"
        ("Tytuł", "nieznany", "tytuł"),
        # usuwanie cudzysłowów + strip + lower
        ('  "Cudzysłów"  ', "pol.", "cudzysłów"),
        # edge: pusty / None
        ("", "ang.", ""),
        (None, "ang.", ""),
    ],
)
def test_oblicz_tytul_oryginalny_sort(tytul, jezyk_skrot, oczekiwany):
    assert oblicz_tytul_oryginalny_sort(tytul, jezyk_skrot) == oczekiwany


@pytest.mark.django_db
def test_save_hook_patent_bez_jezyka(patent):
    """Patent nie ma kolumny jezyk_id — klucz liczony jak dla 'pol.'
    (bez obcinania rodzajnika), wiernie jak dawny trigger."""
    patent.tytul_oryginalny = "The Invention"
    patent.save()
    patent.refresh_from_db()
    # 'pol.' -> bez obcinania "the"
    assert patent.tytul_oryginalny_sort == "the invention"


@pytest.mark.django_db
def test_save_hook_wydawnictwo_ciagle_z_jezykiem(wydawnictwo_ciagle, jezyki):
    """Dla rekordu z jezyk_id klucz uwzględnia rodzajniki języka."""
    wydawnictwo_ciagle.tytul_oryginalny = "The Best Paper"
    wydawnictwo_ciagle.jezyk = jezyki["ang."]
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.tytul_oryginalny_sort == "best paper"


@pytest.mark.django_db
def test_save_hook_update_fields_gotcha(wydawnictwo_ciagle, jezyki):
    """Gdy update_fields zawiera tytul_oryginalny, policzony klucz MUSI
    trafić do bazy (save() dorzuca tytul_oryginalny_sort do update_fields)."""
    wydawnictwo_ciagle.jezyk = jezyki["ang."]
    wydawnictwo_ciagle.tytul_oryginalny = "The First"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.tytul_oryginalny_sort == "first"

    wydawnictwo_ciagle.tytul_oryginalny = "A Second"
    wydawnictwo_ciagle.save(update_fields=["tytul_oryginalny"])
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.tytul_oryginalny == "A Second"
    assert wydawnictwo_ciagle.tytul_oryginalny_sort == "second"


@pytest.mark.django_db
def test_save_hook_update_fields_niezwiazane_nie_przelicza(wydawnictwo_ciagle, jezyki):
    """Częściowy zapis nieruszający tytułu/języka nie przelicza klucza
    (odpowiednik bramki 'nic się nie zmieniło' dawnego triggera)."""
    wydawnictwo_ciagle.jezyk = jezyki["ang."]
    wydawnictwo_ciagle.tytul_oryginalny = "The Stable"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.tytul_oryginalny_sort == "stable"

    # zmieniamy tytuł w pamięci, ale zapisujemy TYLKO inne pole:
    wydawnictwo_ciagle.tytul_oryginalny = "A Different In Memory"
    wydawnictwo_ciagle.szczegoly = "x"
    wydawnictwo_ciagle.save(update_fields=["szczegoly"])
    wydawnictwo_ciagle.refresh_from_db()
    # klucz w bazie pozostał z poprzedniego zapisu:
    assert wydawnictwo_ciagle.tytul_oryginalny_sort == "stable"
