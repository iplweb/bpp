"""Testy menedżerów i queryset-gate'a soft-delete."""

import pytest

from bpp.models.soft_delete import (
    BppGlobalManager,
    BppSoftDeleteManager,
    BppSoftDeleteQuerySet,
)


def test_queryset_gate_blokuje_deleted_at():
    """update(deleted_at=...) musi rzucić RuntimeError (omija post_save,
    kaskadę *_Autor, SoftDeleteLog i reversion)."""
    from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor

    qs = BppSoftDeleteQuerySet(Wydawnictwo_Ciagle_Autor)
    with pytest.raises(RuntimeError, match="Nie ustawiaj deleted_at"):
        qs.update(deleted_at="2026-06-04")


def test_queryset_gate_blokuje_restored_at():
    from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor

    qs = BppSoftDeleteQuerySet(Wydawnictwo_Ciagle_Autor)
    with pytest.raises(RuntimeError, match="Nie ustawiaj deleted_at"):
        qs.update(restored_at="2026-06-04")


def test_queryset_gate_przepuszcza_inne_pola():
    """update() na zwykłym polu działa normalnie (nie rzuca)."""
    from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor

    qs = BppSoftDeleteQuerySet(Wydawnictwo_Ciagle_Autor).none()
    assert qs.update(kolejnosc=5) == 0  # pusty QS, ale nie rzuca


def test_managery_zwracaja_bpp_queryset():
    """Oba managery MUSZĄ zwracać BppSoftDeleteQuerySet — inaczej gate
    na update() nie zadziała (pakietowy QuerySet go nie ma).

    Uwaga: brief zakładał użycie ``Wydawnictwo_Ciagle_Autor`` (model bez
    kolumny ``deleted_at`` na tym etapie — dodaje ją dopiero Task 2) na
    założeniu, że budowa queryset-u jest w pełni leniwa i nie odpali się
    aż do iteracji. W praktyce Django resoluje nazwy pól już przy
    wywołaniu ``.filter()`` (budowa drzewa WHERE), nie dopiero przy
    wykonaniu SQL-a — więc ``BppSoftDeleteManager.get_queryset()`` (który
    filtruje po ``deleted_at__isnull=True``) rzucał ``FieldError`` zanim
    zdążył cokolwiek zwrócić. Używamy więc ``Element_Repozytorium`` —
    istniejącego modelu, który już dziedziczy po
    ``django_softdelete.models.SoftDeleteModel`` i naprawdę ma kolumny
    ``deleted_at``/``restored_at`` w ``_meta`` — dzięki czemu ``.filter()``
    rozwiązuje się poprawnie bez dotykania bazy danych (nadal nie
    iterujemy po wyniku, więc SQL się nie wykonuje)."""
    from bpp.models.repozytorium import Element_Repozytorium

    for manager_cls in (BppSoftDeleteManager, BppGlobalManager):
        manager = manager_cls()
        manager.model = Element_Repozytorium
        manager._db = None
        assert isinstance(manager.get_queryset(), BppSoftDeleteQuerySet), (
            f"{manager_cls.__name__} nie zwraca BppSoftDeleteQuerySet"
        )
