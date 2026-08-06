"""Wspólny fundament soft-delete dla BPP: queryset-gate blokujący bulk
ustawienie deleted_at/restored_at + managery przepleciające filtr soft-delete
z naszą podklasą queryset (gate). Guard zależności (PROTECT) dokłada faza 04.
"""

from django_softdelete.managers import (
    GlobalManager,
    SoftDeleteManager,
    SoftDeleteQuerySet,
)


class BppSoftDeleteQuerySet(SoftDeleteQuerySet):
    """Gate: blokuje bulk-ustawienie deleted_at/restored_at przez .update()
    (omijałoby post_save, kaskadę *_Autor, SoftDeleteLog i reversion)."""

    def update(self, **kwargs):
        if "deleted_at" in kwargs or "restored_at" in kwargs:
            raise RuntimeError(
                "Nie ustawiaj deleted_at/restored_at przez .update() — "
                "użyj .delete()/.restore(). Bulk update omija post_save, "
                "kaskadę *_Autor, SoftDeleteLog i reversion."
            )
        return super().update(**kwargs)


class BppSoftDeleteManager(SoftDeleteManager):
    def get_queryset(self):
        return BppSoftDeleteQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=True
        )


class BppGlobalManager(GlobalManager):
    def get_queryset(self):
        return BppSoftDeleteQuerySet(self.model, using=self._db)
