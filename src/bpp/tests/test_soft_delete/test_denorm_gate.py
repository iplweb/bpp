"""Task 3b: bramka WHEN triggera django-denorm musi znać `deleted_at`.

BPP ma DWA niezależne systemy triggerów na tabelach `*_Autor`:

1. cache ``_mat`` (nasz) — naprawiony w Tasku 3 (migracja 0489).
2. ``django-denorm`` — bramka WHEN budowana z list ``only=`` w
   ``@depend_on_related``. Naprawiany właśnie tutaj (Task 3b).

Bez ``deleted_at`` w ``only=``/``denorm_always_only`` UPDATE, który tylko
soft-kasuje wiersz ``*_Autor`` (ustawia ``deleted_at``), nie odpala triggera
denorm — pola denormalizowane rodzica (``opis_bibliograficzny_cache`` i
pochodne) zostają nieświeże NA STAŁE.
"""

import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_soft_delete_autorstwa_odswieza_opis_biblio(
    wydawnictwo_ciagle_z_autorem, denorms
):
    """Soft-delete autorstwa MUSI unieważnić denorm-cache rodzica.

    Drugi system triggerów (django-denorm) ma własną bramkę WHEN po liście
    ``only=`` — bez ``deleted_at`` UPDATE soft-delete jej nie przechodzi i
    opis zostaje nieświeży NA STAŁE.
    """
    wc = wydawnictwo_ciagle_z_autorem
    denorms.flush()
    wc.refresh_from_db()
    assert "KOWALSKI" in wc.opis_bibliograficzny_cache

    wc.autorzy_set.first().delete()
    denorms.flush()
    wc.refresh_from_db()

    assert "KOWALSKI" not in wc.opis_bibliograficzny_cache, (
        "denorm-cache nieświeży — bramka WHEN triggera denorm nie zna "
        "deleted_at (denorm_always_only)"
    )


# --- Faza 02: publikacje --------------------------------------------------
#
# INWENTARYZACJA (2026-08-07). W całym kodzie produkcyjnym są DOKŁADNIE DWIE
# zależności ``@depend_on_related`` celujące w model publikacji — obie to
# ``("self", "wydawnictwo_nadrzedne")`` na ``Wydawnictwo_Zwarte``
# (``wydawnictwo_zwarte.py:384`` i ``:434``), obie BEZ ``only=``.
#
# Brak ``only=`` oznacza, że denorm buduje bramkę WHEN ze WSZYSTKICH kolumn,
# więc ``deleted_at`` wchodzi do niej automatycznie — bez żadnej zmiany
# w kodzie. Potwierdzone niezależnie i przypadkiem: testy odwracalności
# migracji padały na ``CREATE TRIGGER ... WHEN (OLD."deleted_at" IS DISTINCT
# FROM ...)`` dla ``bpp_patent``, czyli denorm tę kolumnę widzi.
#
# Dlatego faza 02 NIE dokłada tu ``denorm_always_only`` ani list ``only=`` —
# byłby to martwy kod. Zostaje jedna rzecz warta przypięcia testem:
# semantyka poniżej.


@pytest.mark.django_db
def test_soft_delete_ksiazki_matki_nie_psuje_cache_rozdzialu(denorms):
    """Soft-delete książki-matki NIE może uszkodzić rozdziału ani jego cache'u.

    Kaskada fazy 02 jest WĄSKA — zatrzymuje się na ``*_Autor`` rodzica i nie
    rusza rozdziałów. Rozdział zostaje żywy, a jego opis nadal odwołuje się
    do tytułu matki, bo soft-delete NIE zmienia tytułu: usunięty rekord dalej
    istnieje i dalej ma swoje dane.

    To jest odpowiedź na pytanie postawione w planie fazy 02 („czy soft-delete
    książki-matki ma unieważniać denorm-cache rozdziałów"): NIE ma czego
    unieważniać. Gdyby cache miał się tu zmieniać, znaczyłoby to, że opis
    rozdziału zależy od tego, czy matka jest w koszu — a nie zależy i nie
    powinien.

    Faza 04 doda guard PROTECT, który prawdopodobnie w ogóle zablokuje
    skasowanie książki mającej rozdziały. Do tego czasu ta ścieżka jest
    osiągalna i ten test opisuje, co się na niej dzieje.
    """
    from bpp.models import Wydawnictwo_Zwarte

    matka = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Ksiazka Matka Zzz")
    rozdzial = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Rozdzial Podrzedny Yyy",
        wydawnictwo_nadrzedne=matka,
    )
    denorms.flush()

    rozdzial.refresh_from_db()
    slug_przed = rozdzial.slug
    # ``slugify_function`` BPP NIE obniża wielkości liter — porównujemy bez
    # rozróżniania, żeby test nie zależał od tego szczegółu.
    assert "matka" in slug_przed.lower(), (
        f"setup zepsuty — slug rozdzialu nie zawiera tytulu matki: {slug_przed!r}"
    )

    matka.delete()  # soft
    denorms.flush()

    assert Wydawnictwo_Zwarte.objects.filter(pk=rozdzial.pk).exists(), (
        "rozdzial znikl razem z matka — kaskada NIE jest waska"
    )

    rozdzial.refresh_from_db()
    assert rozdzial.deleted_at is None, "rozdzial zostal soft-skasowany kaskadowo"
    assert rozdzial.slug == slug_przed, (
        f"denorm-cache rozdzialu zmienil sie po skasowaniu matki: "
        f"{slug_przed!r} -> {rozdzial.slug!r}"
    )
