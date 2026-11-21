"""Wspólny fundament soft-delete (kosza) dla BPP.

Pełna mapa „co jest kasowane miękko, a co nie i dlaczego" (z PBN, stage 2
i oknem serwisowym): ``docs/deweloper/soft-delete.md``. Skrót:

- TAK (``deleted_at``): pięć modeli publikacji
  (``BppPublikacjaSoftDeleteMixin``), ``Autor`` (tylko autor bez prac),
  struktura (``Uczelnia``, ``Jednostka``) i słowniki ``Zrodlo``,
  ``Wydawca``, ``Konferencja``, ``Seria_Wydawnicza``
  (``BppSoftDeleteSlownikMixin`` — tylko rekord nieużywany); niezależnie od
  dawna ``Element_Repozytorium`` i ``Zgloszenie_Publikacji``.
- NIE: tabele łączące ``*_Autor`` i dzieci publikacji
  (``*_Streszczenie``, ``*_Zewnetrzna_Baza_Danych``) — NIE mają własnego
  kosza; ich domyślny menedżer (``BppDzieckoPublikacjiMixin``) ukrywa
  wiersze, których publikacja jest w koszu, więc znikają razem z nią
  i wracają przy ``restore()`` bez żadnej pracy. Dane kadrowe autora,
  słowniki systemowe, cache i kolejka PBN — kasowanie twarde jak dotąd.

INWARIANTY:

- ``restore()`` na każdej ścieżce (instancja, ``global_objects``,
  ``deleted_objects``) ma domyślne ``strict=False`` — pakiet
  ``django_softdelete`` ma ``strict=True`` i rzucałby
  ``SoftDeleteException`` dla każdego zwykłego FK do modelu spoza kosza.
- soft-delete i restore BUMPUJĄ ``ostatnio_zmieniony``
  (``dopisz_znacznik_zmiany``) — konsumenci przyrostowi (OAI-PMH, CERIF,
  API) muszą zobaczyć zmianę: ``Model.deleted_objects.filter(
  ostatnio_zmieniony__gte=X)`` to gotowa lista nagrobków.
- nigdy ``queryset.update(deleted_at=...)`` (gate w
  ``BppSoftDeleteQuerySet.update``) — ominęłoby sygnały, ``SoftDeleteLog``
  i PBN.
"""

import uuid
from collections import defaultdict

from django.core.exceptions import FieldDoesNotExist
from django.db import models, transaction
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


def manager_z_koszem(model):
    """Menedżer widzący WSZYSTKIE wiersze modelu — także kosz.

    Dla modeli soft-delete to ``global_objects``; dla dzieci publikacji
    (``*_Autor``, streszczenia) — ``all_objects`` (domyślny ``objects``
    ukrywa wiersze publikacji z kosza); dla pozostałych — ``objects``.
    Używaj w „kategorii B": import, deduplikacja, scalanie, sprzątanie.
    """
    for nazwa in ("global_objects", "all_objects"):
        manager = getattr(model, nazwa, None)
        if manager is not None:
            return manager
    return model.objects


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

    DLACZEGO ``_base_manager``, A NIE ``objects``: domyślny menedżer
    ``*_Autor`` ukrywa autorstwa publikacji z kosza. Autor, którego wszystkie
    prace są w koszu, wyglądałby przez ``objects`` na pustego — a przywrócenie
    takiej pracy dałoby publikację wskazującą na autora z kosza.
    """
    ile = 0
    probka = []
    for model, pole in relations:
        # ``_base_manager`` widzi WSZYSTKO: kosz publikacji, autorstwa
        # publikacji z kosza (domyślny menedżer ``*_Autor`` je ukrywa)
        # i wiersze modeli spoza soft-delete.
        qs = model._base_manager.filter(**{pole: instance})
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
    (omijałoby post_save, sygnały, SoftDeleteLog i PBN)."""

    def hard_delete(self):
        return hard_delete_per_instancja(self)

    hard_delete.alters_data = True

    def update(self, **kwargs):
        if "deleted_at" in kwargs or "restored_at" in kwargs:
            raise RuntimeError(
                "Nie ustawiaj deleted_at/restored_at przez .update() — "
                "użyj .delete()/.restore(). Bulk update omija post_save, "
                "sygnały, SoftDeleteLog i kolejkę PBN."
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
    co nadpisywałoby domyślną wartość z ``BppPublikacjaSoftDeleteMixin.
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


class BppZywyRodzicManager(models.Manager):
    """Domyślny menedżer dziecka publikacji: ukrywa wiersze publikacji z kosza.

    Tabele łączące ``*_Autor`` i dzieci (``*_Streszczenie``,
    ``*_Zewnetrzna_Baza_Danych``) NIE mają własnego ``deleted_at``
    (decyzja właściciela, listopad 2026): wiersz „znika" razem z publikacją
    i wraca przy jej ``restore()``. Ten menedżer daje to samo zabezpieczenie,
    które wcześniej dawał kosz na tabeli łączącej — kod czytający
    ``Wydawnictwo_Ciagle_Autor.objects`` wprost (głównie ewaluacja) nie widzi
    autorstw publikacji z kosza — bez warunkowych constraintów, bez
    wierszy-śmieci po edycji inline'a i bez migracji wielkich tabel.

    Lookup ``rekord__deleted_at`` to JOIN po kluczu głównym publikacji.
    ``all_objects`` (zwykły menedżer) widzi wszystko — dla guardów, PBN
    i stage 2 (reversion).
    """

    def __init__(self, pole_rodzica="rekord"):
        super().__init__()
        self.pole_rodzica = pole_rodzica

    def deconstruct(self):
        # Menedżer nie idzie do migracji (``use_in_migrations=False``), ale
        # ``deconstruct`` musi znać argumenty konstruktora.
        return (
            False,
            f"{self.__class__.__module__}.{self.__class__.__qualname__}",
            None,
            (self.pole_rodzica,),
            {},
        )

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .filter(**{f"{self.pole_rodzica}__deleted_at__isnull": True})
        )


class BppWszystkieWierszeManager(models.Manager):
    """``all_objects`` dziecka publikacji — bez filtra kosza rodzica."""


class BppDzieckoPublikacjiMixin(models.Model):
    """Mixin dla dzieci publikacji BEZ własnego kosza (``*_Autor`` itd.).

    ``objects`` (domyślny, pierwszy zadeklarowany) ukrywa wiersze, których
    rodzic jest w koszu; ``all_objects`` widzi wszystko. Kolektor Django
    przy twardym kasowaniu używa ``_base_manager`` (niefiltrującego), więc
    ``hard_delete()`` publikacji nadal kaskadowo usuwa jej dzieci.

    Skutek uboczny, świadomy: relacja odwrotna ``publikacja.autorzy_set``
    na publikacji Z KOSZA jest pusta (related manager dziedziczy klasę
    domyślnego menedżera). Rekord w koszu nie jest edytowalny w adminie,
    a kod, który musi zajrzeć do autorstw skasowanej publikacji (PBN,
    atrybucja tenanta), używa ``all_objects``.
    """

    objects = BppZywyRodzicManager()
    all_objects = BppWszystkieWierszeManager()

    class Meta:
        abstract = True


class BppPublikacjaSoftDeleteMixin(BppPkPrzedHardDeleteMixin, SoftDeleteModel):
    """SoftDeleteModel dla 5 modeli PUBLIKACJI.

    ``delete()``/``restore()`` są nadpisane: NIE wołamy kaskady pakietu
    (kasowałaby twardo dzieci spoza soft-delete). Dzieci publikacji nie mają
    własnego kosza — ukrywa je ``BppZywyRodzicManager``.
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

    # --- relacja autorstw ------------------------------------------------

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

        ``all_objects`` JEST KONIECZNE, nie ostrożnościowe: receiver
        ``post_soft_delete`` czyta autorstwa, gdy publikacja ma już
        ``deleted_at``, a domyślny menedżer ``*_Autor`` ukrywa wtedy
        wszystkie jej wiersze — uczelnia wychodziłaby ``None`` przy każdym
        kasowaniu, czyli zawsze wtedy, kiedy jest potrzebna.

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
                rel.related_model.all_objects.filter(
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
        ``Autor.save()`` — pełne uzasadnienie
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
        """Soft-delete publikacji. BEZ kaskady na dzieci.

        Pakietowy ``SoftDeleteModel.delete()`` przechodzi po wszystkich
        relacjach odwrotnych i dzieci spoza soft-delete kasowałby TWARDO
        (cicho, bo ``strict=False``) — dlatego go nie wołamy. Wiersze
        ``*_Autor``, streszczenia i bazy zewnętrzne zostają nietknięte;
        ukrywa je ``BppZywyRodzicManager``, a ``restore()`` przywraca je
        automatycznie.

        ``user``/``reason`` trafiają do ``SoftDeleteLog`` przez thread-local
        ``soft_delete_context``.
        """
        txid = kwargs.pop("transaction_id", None) or uuid.uuid4()
        with soft_delete_context(user=user, reason=reason), transaction.atomic():
            self.deleted_at = timezone.now()
            self.restored_at = None
            self.transaction_id = txid
            self.save(update_fields=["deleted_at", "restored_at", "transaction_id"])
            post_soft_delete.send(sender=self.__class__, instance=self)
        return 1, {self._meta.label: 1}

    delete.alters_data = True

    def restore(self, *args, strict: bool = False, user=None, **kwargs):
        """Przywrócenie publikacji (razem z nią „wracają" jej dzieci).

        ``strict`` przyjmujemy i ignorujemy świadomie — przekazują go
        ścieżki queryset-owe; ``super().restore()`` nie jest wołane, więc
        pakietowy ``SoftDeleteException`` nie ma jak polecieć.
        """
        txid = self.transaction_id
        with soft_delete_context(user=user), transaction.atomic():
            self.deleted_at = None
            self.restored_at = timezone.now()
            self.transaction_id = None
            self.save(update_fields=["deleted_at", "restored_at", "transaction_id"])
            post_restore.send(sender=self.__class__, instance=self, transaction_id=txid)

    restore.alters_data = True
