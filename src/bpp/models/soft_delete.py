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

INWARIANT (dot. ``ostatnio_zmieniony``): soft-delete JEST modyfikacją
rekordu, więc ``ostatnio_zmieniony`` MUSI być bumpowany przy ``delete()``
ORAZ ``restore()`` — tak, jak wygląda to dla każdego konsumenta
przyrostowego (OAI-PMH, CERIF, REST API). Realizują to
``POLE_ZNACZNIKA_ZMIANY`` + ``dopisz_znacznik_zmiany()`` +
``BppAutorstwoSoftDeleteMixin.save()`` — również PINNED (kontrakt dopisany
2026-08-07, obowiązuje też fazy 02 i 04). Dzięki niemu nagrobki dla
harvestu przyrostowego są odpytywalne od ręki, bez ``SoftDeleteLog``
z fazy 06::

    Model.deleted_objects.filter(ostatnio_zmieniony__gte=X)
"""

from django.core.exceptions import FieldDoesNotExist
from django_softdelete.managers import (
    DeletedManager,
    DeletedQuerySet,
    GlobalManager,
    SoftDeleteManager,
    SoftDeleteQuerySet,
)
from django_softdelete.models import SoftDeleteModel

#: Nazwa pola-znacznika czasu modyfikacji. Ta sama w
#: ``BazaModeluOdpowiedzialnosciAutorow`` (``abstract/authors.py``) i w
#: ``ModelZAdnotacjami`` (``abstract/metadata.py``), więc jedna stała
#: obsługuje autorstwa (faza 01), publikacje (faza 02) i ``Autor`` (04).
POLE_ZNACZNIKA_ZMIANY = "ostatnio_zmieniony"


def dopisz_znacznik_zmiany(instance, update_fields):
    """Dokłada ``ostatnio_zmieniony`` do ``update_fields`` zapisu, który
    ustawia ``deleted_at`` — czyli soft-delete ALBO restore: pakiet w obu
    ścieżkach woła ``save(update_fields=['deleted_at', 'restored_at',
    'transaction_id'])``.

    DLACZEGO PRZEZ ``save()``, a nie przez nadpisanie ``delete()``/
    ``restore()``: kaskada i księgowość transakcji siedzą w kodzie
    pakietu, a ten woła ``self.save()`` z własną listą pól. Doklejenie
    się do ``save()`` obsługuje KAŻDĄ ścieżkę pakietu (instancja,
    queryset, kaskada one-to-many) i nie kopiuje ani grama logiki
    pakietu — przeżyje więc jego aktualizację.

    DLACZEGO SAMO DOPISANIE NAZWY WYSTARCZA: ``Model._save_table()``
    najpierw zawęża listę pól do zapisu przez ``update_fields``, a
    dopiero na tak zawężonej liście woła ``Field.pre_save()``.
    ``DateTimeField.pre_save()`` to jedyne miejsce, w którym ``auto_now``
    podstawia ``timezone.now()`` — pole nieobecne w ``update_fields``
    nie jest więc bumpowane, a obecne jest. (Zweryfikowane testem
    ``test_ostatnio_zmieniony.py``, nie tylko lekturą źródeł Django.)

    Model bez pola ``ostatnio_zmieniony`` (np. ``Element_Repozytorium``,
    a docelowo część modeli z faz 02/04) dostaje ``update_fields``
    nietknięte — dopisanie nieistniejącej nazwy wywaliłoby ``save()``
    na ``ValueError``.
    """
    if not update_fields:
        # Pełny zapis (``update_fields=None``) i tak przepuszcza wszystkie
        # pola przez ``pre_save()`` — ``auto_now`` zadziała samo.
        return update_fields

    nazwy = set(update_fields)
    if "deleted_at" not in nazwy:
        # Zwykły częściowy zapis — nie nasza sprawa. Podbijanie znacznika
        # przy KAŻDYM ``update_fields`` zmieniłoby semantykę daleko poza
        # soft-deletem (np. denorm celowo wyklucza pola ``auto_now``).
        return update_fields
    if POLE_ZNACZNIKA_ZMIANY in nazwy:
        return update_fields

    try:
        instance._meta.get_field(POLE_ZNACZNIKA_ZMIANY)
    except FieldDoesNotExist:
        return update_fields

    return list(update_fields) + [POLE_ZNACZNIKA_ZMIANY]


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

    def save(self, *args, **kwargs):
        """Soft-delete i restore MUSZĄ podbić ``ostatnio_zmieniony``.

        Pakiet zapisuje obie operacje przez ``save(update_fields=[
        'deleted_at', 'restored_at', 'transaction_id'])``. Django woła
        ``pre_save()`` (a więc i ``auto_now``) tylko dla pól obecnych w
        ``update_fields``, więc bez dopisania nazwy znacznik stałby w
        miejscu — a soft-delete jest modyfikacją rekordu i tak musi
        wyglądać dla konsumentów przyrostowych (OAI-PMH, CERIF, REST API).

        Czytamy ``update_fields`` wyłącznie z ``kwargs``: pakiet (i cały
        kod BPP) przekazuje je nazwanie, a przekazanie pozycyjne jest w
        Django deprecated. Klucza nie wstrzykujemy, gdy go nie było —
        pełny zapis ma zostać pełnym zapisem.
        """
        update_fields = kwargs.get("update_fields")
        if update_fields:
            kwargs["update_fields"] = dopisz_znacznik_zmiany(self, update_fields)
        return super().save(*args, **kwargs)

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
