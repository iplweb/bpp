"""Wspólny fundament soft-delete dla BPP: queryset-gate blokujący bulk
ustawienie deleted_at/restored_at + managery przepleciające filtr soft-delete
z naszą podklasą queryset (gate). Guard zależności (PROTECT) dokłada faza 04.
"""

from django_softdelete.managers import (
    DeletedManager,
    GlobalManager,
    SoftDeleteManager,
    SoftDeleteQuerySet,
)
from django_softdelete.models import SoftDeleteModel


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


class BppAutorstwoSoftDeleteMixin(SoftDeleteModel):
    """SoftDeleteModel + nasze managery dla through-modeli *_Autor.

    Wpinany w 3 KONKRETNE modele (Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor, Patent_Autor), NIE w abstrakt
    BazaModeluOdpowiedzialnosciAutorow — ten ma czwartego potomka,
    Zgloszenie_Publikacji_Autor, który jest poza zakresem soft-delete.
    """

    # Nadpisujemy managery pakietu naszymi (gate na update()).
    # Kolejność: pierwszy zdefiniowany manager = _default_manager.
    objects = BppSoftDeleteManager()
    global_objects = BppGlobalManager()
    deleted_objects = DeletedManager()

    class Meta:
        abstract = True

    def restore(self, strict: bool = False, *args, **kwargs):
        """`SoftDeleteModel.restore()` domyślnie ma `strict=True` — dla
        KAŻDEJ relacji (nie tylko kaskadowanej) wymaga, żeby powiązany
        model też był `SoftDeleteModel`, inaczej rzuca
        `SoftDeleteException`. `*_Autor` ma zwykłe FK do `Autor`,
        `Jednostka` i rekordu (żaden z nich nie jest soft-delete w tej
        fazie), więc strict=True wywaliłoby każde `.restore()`.
        `delete()` z tego samego pakietu domyślnie ma `strict=False` —
        ujednolicamy `restore()` do tego samego domyślnego zachowania.
        """
        return super().restore(*args, strict=strict, **kwargs)
