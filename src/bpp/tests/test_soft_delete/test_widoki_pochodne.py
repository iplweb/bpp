"""Widoki POCHODNE (spoza rodziny ``bpp_*_autorzy``) po soft-delete autorstwa.

Faza 01 przefiltrowała widoki ``bpp_*_autorzy`` (migracja 0489) — ale to nie
jedyne miejsce, gdzie SQL czyta SUROWĄ tabelę ``*_autor``. Ponieważ
``delete()`` jest miękki od pierwszej sekundy po wdrożeniu (żadnej feature
flagi), każdy taki widok wycieka skasowane autorstwa od dnia 1.

Ten moduł pilnuje dwóch takich rodzin widoków:

1. ``bpp_<typ>_view`` (migracja 0421) — ``count(*_autor.autor_id) AS
   liczba_autorow``; karmi ``bpp_rekord_mat`` (model ``Rekord``). Zawyżona
   ``liczba_autorow`` cicho psuje multiseek: kryterium „Ostatnie nazwisko i
   imię" filtruje ``kolejnosc ∈ [liczba_autorow-1, liczba_autorow)``, więc
   przy zawyżonej wartości celuje w pozycję, na której nikogo nie ma
   (``bpp/multiseek_registry/fields/author_fields.py``).
2. ``bpp_nowe_sumy_*_view`` (migracja 0458) — sumy punktów per autor,
   źródło rankingu autorów (``ranking_autorow.views``). Wyciek = zdublowany
   (i skasowany) autor trzyma punkty w rankingu na zawsze.
"""

import pytest
from django.db import connection

from bpp.models.cache import Rekord
from bpp.models.sumy_views import Sumy
from bpp.tests.test_soft_delete.test_kanarek_katalogowy import (
    _widoki_zalezne_od_deleted_at,
)

# (widok sum, tabela PUBLIKACJI) — wymiar domkniety w fazie 02 (bpp.0498).
# Wymiar AUTORSTWA (0495) obejmowal tylko pierwsze trzy, bo pozostale dwa
# nie maja tabeli *_autor.
SUMY_PUBLIKACJE = [
    ("bpp_nowe_sumy_wydawnictwo_ciagle_view", "bpp_wydawnictwo_ciagle"),
    ("bpp_nowe_sumy_wydawnictwo_zwarte_view", "bpp_wydawnictwo_zwarte"),
    ("bpp_nowe_sumy_patent_view", "bpp_patent"),
    ("bpp_nowe_sumy_praca_doktorska_view", "bpp_praca_doktorska"),
    ("bpp_nowe_sumy_praca_habilitacyjna_view", "bpp_praca_habilitacyjna"),
]


@pytest.mark.django_db
def test_liczba_autorow_nie_liczy_soft_deletowanych(
    denorms, wydawnictwo_ciagle_z_dwoma_autorami
):
    """``Rekord.liczba_autorow`` po soft-delete = liczba ŻYWYCH autorstw.

    Wyrocznia: gdyby ``bpp_wydawnictwo_ciagle_view`` liczyło
    ``count(bpp_wydawnictwo_ciagle_autor.autor_id)`` po surowej tabeli (stan
    sprzed poprawki), ostatnia asercja zwróciłaby 2 przy jednym żywym
    autorstwie.

    ``denorms.flush()`` po ``delete()`` jest KONIECZNY: trigger na tabeli
    ``*_autor`` odświeża tylko ``bpp_autorzy_mat``; ``liczba_autorow`` w
    ``bpp_rekord_mat`` przelicza się dopiero, gdy flush denorm dotknie
    wiersza publikacji (patrz komentarz przy polu ``Rekord.liczba_autorow``).
    Tak samo działa to przy TWARDYM kasowaniu autorstwa — to nie jest
    regresja soft-delete.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    denorms.flush()

    assert wc.autorzy_set.count() == 2
    assert Rekord.objects.get_for_model(wc).liczba_autorow == 2

    wc.autorzy_set.first().delete()  # soft-delete
    denorms.flush()

    assert wc.autorzy_set.count() == 1
    assert Rekord.objects.get_for_model(wc).liczba_autorow == 1


@pytest.mark.django_db
def test_sumy_rankingu_nie_licza_soft_deletowanych(wydawnictwo_ciagle_z_autorem):
    """``Sumy`` (``bpp_nowe_sumy_view``) nie widzą skasowanego autorstwa.

    Wyrocznia: gdyby ``bpp_nowe_sumy_wydawnictwo_ciagle_view`` joinowało
    surową ``bpp_wydawnictwo_ciagle_autor`` (stan sprzed poprawki), druga
    asercja by padła — a to dokładnie ten wiersz, po którym ranking autorów
    sumuje punkty. Deduplikator autorów przenosi autorstwa i kasuje źródłowe
    (od fazy 01 — miękko), więc bez tego filtra zduplikowany autor trzymałby
    punkty w rankingu bezterminowo.
    """
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    autor_id = wca.autor_id

    assert Sumy.objects.filter(autor_id=autor_id).exists()

    wca.delete()  # soft-delete

    assert not Sumy.objects.filter(autor_id=autor_id).exists()


@pytest.mark.django_db
def test_sumy_rankingu_wracaja_po_restore(wydawnictwo_ciagle_z_autorem):
    """Filtr w ``bpp_nowe_sumy_*`` jest odwracalny: ``restore()`` przywraca
    punkty do rankingu. Wyrocznia dla poprawki nadgorliwej (np. filtr po
    ``restored_at`` zamiast ``deleted_at``)."""
    from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor

    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    autor_id, pk = wca.autor_id, wca.pk

    wca.delete()
    assert not Sumy.objects.filter(autor_id=autor_id).exists()

    Wydawnictwo_Ciagle_Autor.global_objects.get(pk=pk).restore()

    assert Sumy.objects.filter(autor_id=autor_id).exists()


# --- wymiar PUBLIKACJI (faza 02, migracja 0498) -------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("widok,tabela", SUMY_PUBLIKACJE)
def test_sumy_zaleza_od_deleted_at_publikacji(widok, tabela):
    """Kontrakt DDL: dowód, że ``0498`` w ogóle się wykonała.

    Pytamy ``pg_depend`` o zależność KOLUMNOWĄ, nie tekst definicji — trzy
    z tych widoków zawierają już ``deleted_at`` z migracji ``0495`` (wymiar
    autorstwa), więc test substringowy dawałby dla nich fałszywą zieleń.
    """
    with connection.cursor() as cur:
        assert (widok, tabela) in _widoki_zalezne_od_deleted_at(cur, [tabela]), (
            f"{widok} nie zalezy od kolumny {tabela}.deleted_at"
        )


@pytest.mark.django_db
def test_sumy_pomijaja_soft_deletowana_publikacje_IZOLOWANE(
    wydawnictwo_ciagle_z_autorem,
):
    """Wyrocznia dla SAMEGO wymiaru publikacji.

    ⚠️ Kasujemy publikację SUROWYM UPDATE-em, a nie ``wc.delete()``, i jest
    to celowe. ``delete()`` kaskaduje na autorstwa, więc wiersz zniknąłby
    z sum z DWÓCH niezależnych powodów: przez filtr publikacji (``0498``,
    czyli to, co ten test ma sprawdzać) ORAZ przez filtr autorstwa
    (``0495``). Test przechodziłby wtedy nawet po cofnięciu ``0498`` — czyli
    nie byłby wyrocznią niczego.

    Surowy SQL omija też gate na ``.update(deleted_at=...)``
    (``BppSoftDeleteQuerySet``), co poza testem izolującym wymiar jest
    zakazane.
    """
    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id

    assert Sumy.objects.filter(autor_id=autor_id).exists()

    with connection.cursor() as cur:
        cur.execute(
            "UPDATE bpp_wydawnictwo_ciagle SET deleted_at = now() WHERE id = %s",
            [wc.pk],
        )

    assert not Sumy.objects.filter(autor_id=autor_id).exists(), (
        "soft-skasowana publikacja dalej wnosi punkty do rankingu"
    )


@pytest.mark.django_db
def test_sumy_pomijaja_soft_deletowana_publikacje_end_to_end(
    wydawnictwo_ciagle_z_autorem,
):
    """Realna ścieżka (``delete()`` z kaskadą) + powrót po ``restore()``.

    Nie izoluje wymiaru (patrz test wyżej), ale pokrywa to, co faktycznie
    robi operator, łącznie z odwracalnością.
    """
    wc = wydawnictwo_ciagle_z_autorem
    autor_id = wc.autorzy_set.first().autor_id

    assert Sumy.objects.filter(autor_id=autor_id).exists()

    wc.delete()
    assert not Sumy.objects.filter(autor_id=autor_id).exists()

    wc.restore()
    assert Sumy.objects.filter(autor_id=autor_id).exists(), (
        "po restore publikacja nie wrocila do rankingu"
    )
