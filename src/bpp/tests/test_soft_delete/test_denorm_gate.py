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
