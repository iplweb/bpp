"""Wspólny fundament soft-delete dla BPP: queryset-gate blokujący bulk
ustawienie deleted_at/restored_at + managery przepleciające filtr soft-delete
z naszą podklasą queryset (gate). Guard zależności (PROTECT) dokłada faza 04.

INWARIANT (dot. ``restore()``): żadna ścieżka przywracania w BPP — instancja
(``obj.restore()``), ``deleted_objects`` ani ``global_objects`` — nie może
rzucić ``SoftDeleteException`` tylko dlatego, że model powiązany (np.
``Autor``, ``Jednostka``, rekord) nie jest sam ``SoftDeleteModel``. Pakiet
``django_softdelete`` ma tu domyślnie ``strict=True`` na wszystkich trzech
ścieżkach (asymetrycznie względem ``delete()``, który domyślnie ma
``strict=False``) — w BPP wymuszamy domyślne ``strict=False`` wszędzie:

- instancja: nadpisany ``BppAutorstwoSoftDeleteMixin.restore()``,
- ``global_objects``: ``BppSoftDeleteQuerySet.restore()`` (ta sama klasa
  queryset, którą już zwracał ``BppGlobalManager`` dla gate'u ``update()``),
- ``deleted_objects``: KONTRAKT ROZSZERZONY o czwartą klasę,
  ``BppDeletedQuerySet``/``BppDeletedManager`` (pakietowy ``DeletedManager``
  zwracał ``DeletedQuerySet`` bez naszego nadpisania — to samo
  ``strict=True`` co wyżej).

Wszystkie cztery klasy (``BppSoftDeleteQuerySet``, ``BppSoftDeleteManager``,
``BppGlobalManager``, ``BppDeletedQuerySet``/``BppDeletedManager``) razem z
``BppAutorstwoSoftDeleteMixin`` są PINNED — Task 1 zdefiniował pierwszą
trójkę, Task 2 (runda poprawek 2) dopisał ``BppDeletedQuerySet``/
``BppDeletedManager`` jako część tego samego kontraktu.
"""

from django_softdelete.managers import (
    DeletedManager,
    DeletedQuerySet,
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

    def restore(self, strict: bool = False, *args, **kwargs):
        """Przywraca wiersze querysetu (ścieżka ``global_objects``).

        Bazowy ``SoftDeleteQuerySet`` (pakiet) w ogóle nie ma ``restore()``
        — dodajemy go tutaj, żeby ``global_objects.restore()`` (via
        ``BppGlobalManager``, który zwraca tę właśnie klasę) nie rzucał
        ``AttributeError``. Domyślne ``strict=False`` — patrz inwariant w
        docstringu modułu.
        """
        qs = self.filter(*args, **kwargs)
        for obj in qs:
            obj.restore(strict=strict)
        return

    restore.alters_data = True


class BppSoftDeleteManager(SoftDeleteManager):
    def get_queryset(self):
        return BppSoftDeleteQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=True
        )


class BppGlobalManager(GlobalManager):
    def get_queryset(self):
        return BppSoftDeleteQuerySet(self.model, using=self._db)


class BppDeletedQuerySet(DeletedQuerySet):
    """``DeletedQuerySet`` (pakiet) z domyślnym ``strict=False`` w
    ``restore()`` — patrz inwariant w docstringu modułu. Bez tego
    ``deleted_objects.restore()`` woła jawne ``strict=True`` (kod pakietu),
    co nadpisywałoby domyślną wartość z ``BppAutorstwoSoftDeleteMixin.
    restore()`` i rzucało ``SoftDeleteException``.
    """

    def restore(self, strict: bool = False, *args, **kwargs):
        qs = self.filter(*args, **kwargs)
        for obj in qs:
            obj.restore(strict=strict)
        return

    restore.alters_data = True


class BppDeletedManager(DeletedManager):
    def get_queryset(self):
        return BppDeletedQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=False
        )


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
    deleted_objects = BppDeletedManager()

    class Meta:
        abstract = True

    def restore(
        self, strict: bool = False, transaction_id: str = None, *args, **kwargs
    ):
        """`SoftDeleteModel.restore()` domyślnie ma `strict=True` — dla
        KAŻDEJ relacji (nie tylko kaskadowanej) wymaga, żeby powiązany
        model też był `SoftDeleteModel`, inaczej rzuca
        `SoftDeleteException`. `*_Autor` ma zwykłe FK do `Autor`,
        `Jednostka` i rekordu (żaden z nich nie jest soft-delete w tej
        fazie), więc strict=True wywaliłoby każde `.restore()`.
        `delete()` z tego samego pakietu domyślnie ma `strict=False` —
        ujednolicamy `restore()` do tego samego domyślnego zachowania.

        Sygnatura celowo odwzorowuje rodzica (``strict``, ``transaction_id``
        jako pierwsze dwa parametry) — przekazywanie ich pozycyjnie do
        ``super().restore()`` unika ``TypeError: got multiple values for
        argument 'strict'`` przy wywołaniu pozycyjnym typu
        ``obj.restore(False, txid)``.
        """
        return super().restore(strict, transaction_id, *args, **kwargs)
