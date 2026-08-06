"""Kontrakt DDL po fazie 01: widok filtruje, funkcja kasuje, bramka przepuszcza.

Trzy pierwsze testy są „substringowe" (``pg_get_viewdef`` / ``pg_get_functiondef``
/ ``pg_get_triggerdef``) — pilnują, że migracja w ogóle się odbyła. Czwarty jest
SEMANTYCZNY i jest jedyną realną wyrocznią KLUCZA filtra: trzy pierwsze
przechodzą także dla klucza BŁĘDNEGO (``object_id_raw``, czyli id publikacji,
zamiast ``(id)[2]``, czyli pk wiersza through), bo ``pg_depend`` widzi kolumnę
użytą w podzapytaniu niezależnie od tego, czy porównanie ma jakikolwiek sens.
"""

import pytest
from django.db import connection
from model_bakery import baker

from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle

WIDOKI = [
    "bpp_wydawnictwo_ciagle_autorzy",
    "bpp_wydawnictwo_zwarte_autorzy",
    "bpp_patent_autorzy",
]
FUNKCJE = [
    "bpp_refresh_autor_wydawnictwo_ciagle",
    "bpp_refresh_autor_wydawnictwo_zwarte",
    "bpp_refresh_autor_patent",
]
TRIGGERY = [
    ("bpp_wydawnictwo_ciagle_autor", "bpp_wydawnictwo_ciagle_autor_cache_upd"),
    ("bpp_wydawnictwo_zwarte_autor", "bpp_wydawnictwo_zwarte_autor_cache_upd"),
    ("bpp_patent_autor", "bpp_patent_autor_cache_upd"),
]


@pytest.mark.django_db
@pytest.mark.parametrize("widok", WIDOKI)
def test_widok_zrodlowy_filtruje_po_deleted_at(widok):
    with connection.cursor() as cur:
        cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
        defn = cur.fetchone()[0]
    assert "deleted_at" in defn, f"{widok} nie filtruje po deleted_at"


@pytest.mark.django_db
@pytest.mark.parametrize("fn", FUNKCJE)
def test_funkcja_refresh_ma_galaz_kasujaca(fn):
    """Bez DELETE odfiltrowanie z widoku jest no-opem (upsert nic nie usuwa)."""
    with connection.cursor() as cur:
        cur.execute("SELECT pg_get_functiondef(%s::regproc)", [fn])
        src = cur.fetchone()[0]
    assert "NEW.deleted_at IS NOT NULL" in src, f"{fn}: brak gałęzi kasującej"
    assert "DELETE FROM bpp_autorzy_mat" in src, f"{fn}: brak DELETE"


@pytest.mark.django_db
@pytest.mark.parametrize("tabela,trigger", TRIGGERY)
def test_bramka_when_zna_deleted_at(tabela, trigger):
    """Bez deleted_at w bramce UPDATE soft-delete nie dochodzi do funkcji."""
    with connection.cursor() as cur:
        cur.execute(
            "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t "
            "WHERE t.tgrelid = %s::regclass AND t.tgname = %s",
            [tabela, trigger],
        )
        row = cur.fetchone()
    assert row is not None, f"brak triggera {trigger}"
    assert "deleted_at" in row[0], f"{trigger}: bramka WHEN nie zna deleted_at"


def _przesun_sekwencje_through_ponad_id_publikacji(cur):
    """Podnosi sekwencję pk tabeli through ponad max(id) obu tabel.

    Dzięki temu pk NASTĘPNEGO wiersza ``bpp_wydawnictwo_ciagle_autor`` jest
    gwarantowanie WOLNYM id publikacji — możemy założyć publikację-pułapkę o
    dokładnie takim id i sprawdzić, czy błędny klucz filtra (``object_id_raw``
    = id publikacji) wycina JEJ autorstwa.

    Sekwencje są poza transakcją, więc ten skok nie cofnie się po teście —
    zostawia tylko lukę w numeracji, co jest nieszkodliwe.
    """
    cur.execute(
        "SELECT setval("
        "  pg_get_serial_sequence('bpp_wydawnictwo_ciagle_autor', 'id'),"
        "  GREATEST("
        "    (SELECT COALESCE(MAX(id), 0) FROM bpp_wydawnictwo_ciagle_autor),"
        "    (SELECT COALESCE(MAX(id), 0) FROM bpp_wydawnictwo_ciagle)"
        "  ) + 1000,"
        "  true)"
    )


def _ct_wydawnictwo_ciagle(cur):
    cur.execute(
        "SELECT id FROM django_content_type "
        "WHERE app_label='bpp' AND model='wydawnictwo_ciagle'"
    )
    return cur.fetchone()[0]


@pytest.mark.django_db
def test_widok_odcina_WLASCIWY_wiersz_a_nie_cudzy(standard_data):
    """Test SEMANTYCZNY klucza filtra — nie sam fakt obecności ``deleted_at``.

    Scenariusz jest tak dobrany, żeby ZŁY klucz wywalił się na OBU asercjach
    naraz: pk kasowanego wiersza through jest równy id publikacji-pułapki.
    Przy filtrze po ``object_id_raw`` skasowane autorstwo zostałoby w widoku,
    a wycięte zostałyby autorstwa publikacji-pułapki.
    """
    with connection.cursor() as cur:
        _przesun_sekwencje_through_ponad_id_publikacji(cur)

    jednostka = baker.make(Jednostka)
    kasowany = baker.make(Autor, imiona="Jan", nazwisko="Kasowany")
    obcy_autor = baker.make(Autor, imiona="Jan", nazwisko="Obcy")

    wc = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Publikacja z kasowanym autorstwem",
        szczegoly="sz",
        uwagi="u",
    )
    wca = wc.dodaj_autora(kasowany, jednostka)

    # Publikacja-pułapka: jej id jest RÓWNE pk kasowanego wiersza through.
    wc_pulapka = baker.make(
        Wydawnictwo_Ciagle,
        id=wca.pk,
        tytul_oryginalny="Publikacja-pulapka",
        szczegoly="sz",
        uwagi="u",
    )
    assert wc_pulapka.pk == wca.pk, "setup pułapki nie zadziałał"
    obcy = wc_pulapka.dodaj_autora(obcy_autor, jednostka)

    wca.delete()

    with connection.cursor() as cur:
        ct = _ct_wydawnictwo_ciagle(cur)

        cur.execute(
            "SELECT count(*) FROM bpp_wydawnictwo_ciagle_autorzy WHERE (id)[2] = %s",
            [wca.pk],
        )
        assert cur.fetchone()[0] == 0, (
            "skasowane autorstwo NADAL w widoku — filtr używa złego klucza"
        )

        cur.execute(
            "SELECT count(*) FROM bpp_wydawnictwo_ciagle_autorzy WHERE (id)[2] = %s",
            [obcy.pk],
        )
        assert cur.fetchone()[0] == 1, (
            "filtr wyciął autorstwo INNEJ publikacji — klucz porównuje "
            "id publikacji z id wiersza through"
        )

        # Sam filtr widoku nie sprząta _mat — to robi gałąź kasująca w funkcji
        # refresh, przepuszczona przez bramkę WHEN. Sprawdzamy cały łańcuch.
        cur.execute(
            "SELECT count(*) FROM bpp_autorzy_mat WHERE id = ARRAY[%s, %s]::integer[]",
            [ct, wca.pk],
        )
        assert cur.fetchone()[0] == 0, (
            "skasowane autorstwo zostało w bpp_autorzy_mat — bramka WHEN nie "
            "przepuściła UPDATE-u albo funkcja refresh nie ma gałęzi kasującej"
        )

        cur.execute(
            "SELECT count(*) FROM bpp_autorzy_mat WHERE id = ARRAY[%s, %s]::integer[]",
            [ct, obcy.pk],
        )
        assert cur.fetchone()[0] == 1, (
            "z bpp_autorzy_mat zniknęło autorstwo INNEJ publikacji"
        )
