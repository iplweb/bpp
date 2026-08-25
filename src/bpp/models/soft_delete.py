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

import uuid
from collections import defaultdict

from django.core.exceptions import FieldDoesNotExist
from django.db import transaction
from django.db.models import ProtectedError
from django.utils import timezone
from django_softdelete.managers import (
    DeletedManager,
    DeletedQuerySet,
    GlobalManager,
    SoftDeleteManager,
    SoftDeleteQuerySet,
)
from django_softdelete.models import SoftDeleteModel
from django_softdelete.signals import post_restore, post_soft_delete

from bpp.models.soft_delete_context import soft_delete_context

#: Akcesor relacji odwrotnej publikacja -> wiersze ``*_Autor``. Istnieje
#: jako PRAWDZIWA relacja tylko dla trzech typów z through-modelem;
#: ``Praca_Doktorska``/``Praca_Habilitacyjna`` mają pod tą nazwą property
#: zwracającą atrapy — patrz ``BppPublikacjaSoftDeleteMixin``.
NAZWA_RELACJI_AUTORSTW = "autorzy_set"

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


#: Ile chronionych obiektów najwyżej dołączamy do ``ProtectedError``.
#: Django wypełnia ``protected_objects`` po to, żeby admin mógł je pokazać —
#: przy autorze z tysiącami prac materializacja całości byłaby czystym
#: marnotrawstwem (i tak nikt nie wypisze tysiąca pozycji na stronie błędu).
#: Liczbę raportujemy z ``count()``, więc obcięcie próbki jej nie zafałszuje.
LIMIT_PROBKI_CHRONIONYCH = 20


def raise_if_has_protected_children(instance, relations, label):
    """Blokuje soft-delete ``instance``, jeśli ma „chronione" dzieci.

    ``relations`` to lista krotek ``(Model, "pole_fk")``. Rzuca
    ``django.db.models.ProtectedError`` z komunikatem PL, gdy w którejkolwiek
    z relacji jest co najmniej jedno dziecko.

    DLACZEGO GUARD W OGÓLE MUSI ISTNIEĆ, SKORO FK SĄ ``PROTECT``: ``on_delete``
    obsługuje wyłącznie kolektor Django dla kasowania TWARDEGO. Miękkie
    ``delete()`` to zwykły ``UPDATE`` na ``deleted_at`` — nie przechodzi przez
    kolektor i o ``PROTECT`` się nawet nie dowiaduje. Warstwa pierwsza (FK)
    broni przed ``hard_delete()``, ta broni przed ``delete()``.

    DLACZEGO ``global_objects``, A NIE ``objects``: ``objects`` ukrywa
    autorstwa skasowane kaskadą fazy 02. Autor, którego wszystkie prace
    poszły do kosza, wyglądałby przez ``objects`` na pustego — a to nieprawda:
    przywrócenie takiej pracy dałoby publikację wskazującą na autora, którego
    już nie ma (spec §3.2). Model spoza soft-delete (np. ``Projekt_Autor``)
    nie ma ``global_objects``, więc schodzimy na ``objects`` — tak samo, jak
    robi to ``wiersze_do_transferu`` w scalaniu autorów.
    """
    ile = 0
    probka = []
    for model, pole in relations:
        manager = getattr(model, "global_objects", model.objects)
        qs = manager.filter(**{pole: instance})
        ile += qs.count()
        if len(probka) < LIMIT_PROBKI_CHRONIONYCH:
            probka.extend(qs[: LIMIT_PROBKI_CHRONIONYCH - len(probka)])

    if ile:
        raise ProtectedError(
            f"Nie można usunąć {label} „{instance}” — rekord ma {ile} "
            f"powiązanych rekordów (autorstwa / doktorat / habilitacja / "
            f"rozdziały / projekty), także tych w koszu. Najpierw przenieś "
            f"lub usuń te powiązania.",
            probka,
        )


def hard_delete_per_instancja(queryset):
    """``hard_delete()`` wiersz po wierszu, żeby leciał ``post_hard_delete``.

    DLACZEGO NIE BULK: pakietowy ``hard_delete()`` na querysecie to goły
    ``super().delete()`` (``django_softdelete/managers.py``) — jedno
    zapytanie, ZERO sygnałów. Rekordy znikały fizycznie i bez jednego wpisu
    w ``SoftDeleteLog``, czyli dokładnie ta klasa cichej utraty, przed którą
    ten log ma chronić. Najbardziej prawdopodobna droga do tej luki to
    opróżnianie kosza z admina (faza 07).

    To ta sama zasada, którą kieruje się gate w ``BppSoftDeleteQuerySet.
    update()`` i wąska kaskada fazy 02: operacja masowa nie ma prawa być
    tańsza kosztem pominięcia sygnałów. Pakiet stosuje ją zresztą sam —
    jego ``SoftDeleteQuerySet.delete()`` też iteruje po instancjach.

    KOSZT: N zapytań zamiast jednego. Świadomy — audyt masowego kasowania
    jest wart więcej niż pojedynczy ``DELETE ... WHERE id IN (...)``.

    Zwrotka jak w Django: ``(łączna_liczba, {etykieta_modelu: liczba})``,
    zsumowana po instancjach.
    """
    laczna = 0
    liczniki = defaultdict(int)
    # list(): iterujemy po materializowanej liście, bo kasujemy w trakcie.
    for obiekt in list(queryset):
        ile, per_model = obiekt.hard_delete()
        laczna += ile
        for etykieta, n in per_model.items():
            liczniki[etykieta] += n
    return laczna, dict(liczniki)


class BppSoftDeleteQuerySet(SoftDeleteQuerySet):
    """Gate: blokuje bulk-ustawienie deleted_at/restored_at przez .update()
    (omijałoby post_save, kaskadę *_Autor, SoftDeleteLog i reversion)."""

    def hard_delete(self):
        return hard_delete_per_instancja(self)

    hard_delete.alters_data = True

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

    def hard_delete(self):
        """Opróżnianie kosza też musi zostawiać ślad — patrz
        ``hard_delete_per_instancja()``."""
        return hard_delete_per_instancja(self)

    hard_delete.alters_data = True


class BppDeletedManager(DeletedManager):
    def get_queryset(self):
        return BppDeletedQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=False
        )


#: Atrybut, pod którym ``hard_delete()`` zostawia ``pk`` na czas sygnału.
ATRYBUT_PK_PRZED_HARD_DELETE = "_bpp_pk_przed_hard_delete"


class BppPkPrzedHardDeleteMixin:
    """Zapamiętuje ``pk`` przed twardym skasowaniem, dla receivera fazy 06.

    ``SoftDeleteModel.hard_delete()`` woła ``Model.delete()``, a kolektor
    Django na samym końcu zeruje ``pk`` skasowanych instancji —
    ``post_hard_delete`` leci PO tym (pakiet, ``models.py:84-85``). Receiver
    dostaje więc instancję z ``pk is None`` i nie ma z czego zapisać
    ``SoftDeleteLog.object_id``.

    Naiwne „zapisz ``instance.pk``" dałoby ``object_id=None``, czyli
    ``IntegrityError`` w receiverze — a wyjątek z receivera przewróciłby
    ``hard_delete()``. Audyt zepsułby operację, którą ma tylko obserwować.

    NIE jest modelem (zwykła klasa, nie ``models.Model``) — dlatego
    dopisanie go do baz istniejącego modelu NIE generuje migracji. Musi
    stać PRZED ``SoftDeleteModel`` w liście baz, żeby jego ``hard_delete``
    wygrał w MRO.

    Strażnikiem kompletności jest
    ``test_receivers.py::test_kazdy_model_soft_delete_zachowuje_pk`` —
    nowy model soft-delete bez tego mixinu zapala się w testach, nie
    dopiero przy pierwszym twardym skasowaniu na produkcji.
    """

    def hard_delete(self, *args, **kwargs):
        setattr(self, ATRYBUT_PK_PRZED_HARD_DELETE, self.pk)
        return super().hard_delete(*args, **kwargs)

    hard_delete.alters_data = True


def pk_dla_audytu(instance):
    """``pk`` instancji, także po twardym skasowaniu (zerującym ``pk``).

    Rzuca ``RuntimeError``, gdy ``pk`` nie jest znany — to znaczy, że model
    soft-delete nie ma ``BppPkPrzedHardDeleteMixin``. Głośno, bo cichy
    ``return`` zamieniłby audyt w atrapę dokładnie w tym przypadku, przed
    którym ma chronić: rekord znikający fizycznie i bez śladu.
    """
    if instance.pk is not None:
        return instance.pk

    pk = getattr(instance, ATRYBUT_PK_PRZED_HARD_DELETE, None)
    if pk is None:
        raise RuntimeError(
            f"Nie znam pk dla {instance._meta.label} — model soft-delete bez "
            f"BppPkPrzedHardDeleteMixin, więc SoftDeleteLog nie ma czego "
            f"zapisać w object_id. Dopisz ten mixin do baz modelu (przed "
            f"SoftDeleteModel)."
        )
    return pk


class BppAutorstwoSoftDeleteMixin(BppPkPrzedHardDeleteMixin, SoftDeleteModel):
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


class BppPublikacjaSoftDeleteMixin(BppPkPrzedHardDeleteMixin, SoftDeleteModel):
    """SoftDeleteModel dla 5 modeli PUBLIKACJI (faza 02) z **wąską,
    kontrolowaną** kaskadą na własne wiersze ``*_Autor`` pod wspólnym
    ``transaction_id``.

    DLACZEGO NIE REFLEKSYJNA KASKADA PAKIETU: ``SoftDeleteModel.delete()``
    przechodzi po wszystkich relacjach zwrotnych. Zjechałaby więc po
    ``*_Streszczenie``, ``*_Zewnetrzna_Baza_Danych`` i
    ``Publikacja_Habilitacyjna`` — modelach, które soft-delete NIE obejmuje.
    Co gorsza zrobiłaby to CICHO: ``delete()`` pakietu ma domyślnie
    ``strict=False``, więc nie usłyszelibyśmy ``SoftDeleteException``.
    Dlatego kaskadę piszemy sami i zatrzymujemy ją na ``*_Autor``.

    Kaskada NIE jest jednolita dla wszystkich pięciu modeli — patrz
    ``_relacja_autorstw()``.
    """

    # Managery z gate'em na .update() (faza 01). ``deleted_objects`` to
    # NASZ ``BppDeletedManager``, nie pakietowy ``DeletedManager`` —
    # pakietowy zwraca queryset z ``strict=True`` w ``restore()``, co łamie
    # inwariant z docstringu modułu.
    objects = BppSoftDeleteManager()
    global_objects = BppGlobalManager()
    deleted_objects = BppDeletedManager()

    class Meta:
        abstract = True

    # --- rozpoznanie kształtu kaskady ----------------------------------

    def _relacja_autorstw(self):
        """Relacja odwrotna ``autorzy_set`` (``ForeignObjectRel``) albo
        ``None``, gdy publikacja nie ma through-modelu autorstw.

        DLACZEGO PYTAMY ``_meta``, A NIE TYPU ATRYBUTU: pod nazwą
        ``autorzy_set`` kryją się dwie różne rzeczy. Dla
        ``Wydawnictwo_Ciagle``/``Wydawnictwo_Zwarte``/``Patent`` to
        prawdziwy related manager (``related_name`` FK w modelu
        ``*_Autor``). Dla ``Praca_Doktorska``/``Praca_Habilitacyjna`` to
        PROPERTY zwracająca ``FakeSet`` z atrapami (autor leży na wierszu
        samej publikacji) — ``FakeSet`` jest podklasą ``list``, nie ma
        ``.model``, a atrapy nie mają ``.delete()``.

        Rozpoznawanie tego przez ``type(self).__dict__.get("autorzy_set")``
        NIE DZIAŁA: property jest zadeklarowana na abstrakcyjnej bazie
        ``Praca_Doktorska_Baza``, a dziedziczenie abstrakcyjne w Django
        kopiuje do klasy potomnej POLA, nie zwykłe atrybuty Pythona — te
        zostają na bazie i są znajdowane dopiero przez MRO. ``__dict__``
        klasy konkretnej jest więc pusty i test na ``property`` dawałby
        fałszywe „to jest through-model", a zaraz potem ``AttributeError``
        na ``FakeSet.model``.

        ``_meta.related_objects`` zna wyłącznie PRAWDZIWE relacje, więc
        odpowiada na pytanie, które faktycznie zadajemy.
        """
        for rel in self._meta.related_objects:
            if rel.get_accessor_name() == NAZWA_RELACJI_AUTORSTW:
                return rel
        return None

    def _model_through(self):
        """Model ``*_Autor`` tej publikacji albo ``None``."""
        rel = self._relacja_autorstw()
        return rel.related_model if rel is not None else None

    def _autorstwa_do_kaskady(self):
        """Wiersze ``*_Autor`` do soft-delete; pusto bez through-modelu.

        Czyta przez domyślny manager (``objects``, więc już-skasowane są
        pominięte) — kasowanie drugi raz nie szkodzi, ale i nie ma po co.
        """
        if self._relacja_autorstw() is None:
            return []
        return list(getattr(self, NAZWA_RELACJI_AUTORSTW).all())

    # --- atrybucja tenanta ----------------------------------------------

    def uczelnia_rekordu(self):
        """Uczelnia, do której należy rekord, albo ``None`` przy dwuznaczności.

        PO CO: wpisy ``PBN_Export_Queue`` tworzone przez receivery fazy 06
        nie mają requestu, z którego reszta kodu bierze tenanta
        (``Uczelnia.objects.get_for_request``). Bez uczelni
        ``_pozyskaj_klienta_pbn()`` spada na „jedyna-albo-głośny-błąd", więc
        w multi-hosted wycofanie oświadczeń kończyłoby się
        ``FINISHED_ERROR``.

        REGUŁA JEST ODWRÓCENIEM PRZYNALEŻNOŚCI Z FAZY 05b — ``naleza_
        wydawnictwa`` / ``naleza_prace`` (``cerif_export/providers/
        publikacje.py``). Nie definiujemy drugiej, konkurencyjnej: gdy
        tamta się zmieni, ta musi pójść za nią. Odwracamy, zamiast wołać
        wprost, bo ``cerif_export`` zależy od ``bpp``, nie odwrotnie.

        ``global_objects`` JEST KONIECZNE, nie ostrożnościowe: wąska
        kaskada fazy 02 kasuje wiersze ``*_Autor`` PRZED wysłaniem
        ``post_soft_delete`` rodzica. W momencie odczytu autorstwa są już
        w koszu, więc ``objects`` zwróciłoby pustkę i uczelnia wychodziłaby
        ``None`` przy każdym kasowaniu — czyli zawsze wtedy, kiedy jest
        potrzebna.

        DWUZNACZNOŚĆ → ``None``. Praca współautorska między uczelniami nie
        ma jednego właściciela, a wybranie „pierwszej z brzegu" wysłałoby
        wycofanie przez konto PBN cudzego tenanta. ``None`` degraduje do
        zachowania sprzed tej fazy: jedna uczelnia w bazie działa, kilka
        daje głośny błąd na wpisie kolejki.
        """
        from bpp.models.uczelnia import Uczelnia

        rel = self._relacja_autorstw()
        if rel is None:
            # Praca_Doktorska / Praca_Habilitacyjna — autor i jednostka
            # siedzą na wierszu samej pracy (odpowiednik ``naleza_prace``).
            uczelnie = {self.jednostka.uczelnia_id}
        else:
            uczelnie = set(
                rel.related_model.global_objects.filter(
                    **{rel.field.name: self}
                ).values_list("jednostka__uczelnia_id", flat=True)
            )

        uczelnie.discard(None)
        if len(uczelnie) != 1:
            return None
        return Uczelnia.objects.filter(pk=uczelnie.pop()).first()

    # --- kontrakt zapisu ------------------------------------------------

    def save(self, *args, **kwargs):
        """Bump ``ostatnio_zmieniony`` przy soft-delete i restore.

        Ten sam kontrakt (PINNED), co
        ``BppAutorstwoSoftDeleteMixin.save()`` — pełne uzasadnienie
        mechanizmu jest w docstringu ``dopisz_znacznik_zmiany()``. Bez
        tego nagrobki dla harvestu przyrostowego (OAI-PMH, CERIF, REST
        API) byłyby nieodpytywalne po ``ostatnio_zmieniony__gte``, bo
        ``auto_now`` nie rusza pola nieobecnego w ``update_fields``.
        """
        update_fields = kwargs.get("update_fields")
        if update_fields:
            kwargs["update_fields"] = dopisz_znacznik_zmiany(self, update_fields)
        return super().save(*args, **kwargs)

    # --- soft-delete / restore ------------------------------------------

    def delete(self, *args, user=None, reason="", **kwargs):
        """Soft-delete publikacji + wąska kaskada na ``*_Autor``.

        ``user``/``reason`` trafiają do ``SoftDeleteLog`` (faza 06) przez
        thread-local ``soft_delete_context``. Kontekst obejmuje CAŁE ciało,
        nie samo ``post_soft_delete.send()``: kaskada na ``*_Autor`` wysyła
        własne sygnały (przez ``delete()`` pakietu), a te mają zostać
        zalogowane z tym samym userem i powodem. Zawężenie kontekstu do
        ostatniej linii dałoby wpisy autorstw z ``user=None`` mimo
        świadomej decyzji operatora.
        """
        txid = kwargs.pop("transaction_id", None) or uuid.uuid4()
        with soft_delete_context(user=user, reason=reason), transaction.atomic():
            # 1. kaskada per-instancja — NIGDY bulk update(deleted_at=...),
            #    bo omijałby post_save, sygnały i reversion (gate w
            #    BppSoftDeleteQuerySet.update() egzekwuje to fail-fast).
            for autorstwo in self._autorstwa_do_kaskady():
                autorstwo.delete(transaction_id=txid)
            # 2. własny wiersz
            self.deleted_at = timezone.now()
            self.restored_at = None
            self.transaction_id = txid
            self.save(update_fields=["deleted_at", "restored_at", "transaction_id"])
            post_soft_delete.send(sender=self.__class__, instance=self)
        return 1, {self._meta.label: 1}

    delete.alters_data = True

    def restore(self, *args, strict: bool = False, user=None, **kwargs):
        """Przywrócenie publikacji + tych ``*_Autor``, które zniknęły RAZEM
        z nią (ten sam ``transaction_id``).

        Filtr po ``transaction_id`` jest istotny: autorstwo skasowane
        wcześniej, osobną decyzją operatora, ma POZOSTAĆ w koszu.

        ``strict`` przyjmujemy i ignorujemy świadomie — przekazują go
        ścieżki queryset-owe (``global_objects``/``deleted_objects``), a my
        i tak nie wołamy ``super().restore()``, więc pakietowy
        ``SoftDeleteException`` nie ma jak polecieć (inwariant z docstringu
        modułu).
        """
        txid = self.transaction_id
        rel = self._relacja_autorstw()
        with soft_delete_context(user=user), transaction.atomic():
            if txid is not None and rel is not None:
                # Nazwa pola FK z metadanych relacji — bez zaszywania
                # "rekord" na sztywno.
                filtr = {rel.field.name: self, "transaction_id": txid}
                for autorstwo in rel.related_model.deleted_objects.filter(**filtr):
                    autorstwo.restore(transaction_id=txid)
            self.deleted_at = None
            self.restored_at = timezone.now()
            self.transaction_id = None
            self.save(update_fields=["deleted_at", "restored_at", "transaction_id"])
            post_restore.send(sender=self.__class__, instance=self, transaction_id=txid)

    restore.alters_data = True
