"""Wspólny fundament soft-delete (kosza) dla BPP.

Pełna mapa „co jest kasowane miękko, a co nie i dlaczego" (z PBN, stage 2
i oknem serwisowym): ``docs/deweloper/soft-delete.md``. Skrót:

- TAK (``deleted_at``): pięć modeli publikacji
  (``BppPublikacjaSoftDeleteMixin``), ``Autor`` (tylko autor bez prac),
  ``Uczelnia`` i słowniki ``Zrodlo``,
  ``Wydawca``, ``Konferencja``, ``Seria_Wydawnicza``
  (``BppSoftDeleteSlownikMixin`` — tylko rekord nieużywany), zgłoszenia
  publikacji (ten sam mixin, guard nic nie blokuje); niezależnie od dawna
  ``Element_Repozytorium``.
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

import threading
import uuid
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.core.exceptions import (
    NON_FIELD_ERRORS,
    FieldDoesNotExist,
    ValidationError,
)
from django.db import IntegrityError, connection, models, transaction
from django.db.models import (
    BooleanField,
    Count,
    ExpressionWrapper,
    ProtectedError,
    Q,
    Window,
)
from django.utils import timezone
from django.utils.text import capfirst
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


_flaga_kosza = threading.local()


@contextmanager
def operacja_kosza():
    """Zezwolenie bazy na operację kosza (``bpp.kosz_operacja = 'on'``).

    Trigger ``bpp_kosz_straznik`` (migracja ``0523``) zamraża rekordy
    w koszu i odrzuca każdą zmianę ``deleted_at`` poza tym blokiem. Flagę
    ustawiają WYŁĄCZNIE ``delete()``/``restore()``/``hard_delete()`` (i testy,
    które muszą „cofnąć zegar" rekordu w koszu).

    Flaga jest transakcyjna (``set_config(..., true)``) i wyłączana na końcu
    bloku — nie „przecieka" na resztę transakcji wołającego. Przy wyjątku
    zdejmuje ją wycofanie savepointu. Zagnieżdżenie: flagę zdejmuje dopiero
    najbardziej zewnętrzny blok.
    """
    glebokosc = getattr(_flaga_kosza, "glebokosc", 0)
    with transaction.atomic():
        if glebokosc == 0:
            with connection.cursor() as cur:
                cur.execute("SELECT set_config('bpp.kosz_operacja', 'on', true)")
        _flaga_kosza.glebokosc = glebokosc + 1
        try:
            yield
        finally:
            _flaga_kosza.glebokosc = glebokosc
        if glebokosc == 0:
            with connection.cursor() as cur:
                cur.execute("SELECT set_config('bpp.kosz_operacja', 'off', true)")


def jest_bledem_kosza(exc):
    """Czy wyjątek bazy pochodzi z triggera ``bpp_kosz_straznik``."""
    return "BPP_KOSZ:" in str(exc)


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


#: Ile pozycji na relację pokazuje strona „Nie można przenieść do kosza".
#: Resztę streszcza „…i jeszcze N" (liczba z tego samego zapytania).
LIMIT_POZYCJI_BLOKADY = 15

#: Czytelne etykiety grup na stronie blokady kosza (``"app.Model.pole"``).
#: Relacje spoza słownika dostają etykietę z ``_meta``:
#: „<verbose_name_plural> (<verbose_name pola>)".
ETYKIETY_RELACJI_KOSZA = {
    "bpp.Wydawnictwo_Ciagle_Autor.autor": "Autorstwa w wydawnictwach ciągłych",
    "bpp.Wydawnictwo_Zwarte_Autor.autor": "Autorstwa w wydawnictwach zwartych",
    "bpp.Patent_Autor.autor": "Autorstwa patentów",
    "bpp.Praca_Doktorska.autor": "Doktoraty (autor)",
    "bpp.Praca_Doktorska.promotor": "Doktoraty (promotor)",
    "bpp.Praca_Habilitacyjna.autor": "Habilitacje (autor)",
    "bpp.Wydawnictwo_Zwarte.wydawnictwo_nadrzedne": (
        "Rozdziały i części (wydawnictwo nadrzędne)"
    ),
    "bpp.Wydawnictwo_Ciagle.zrodlo": "Artykuły w tym źródle",
}


def url_w_adminie(obj):
    """URL strony zmiany ``obj`` w adminie albo ``None`` (model bez admina)."""
    from django.urls import NoReverseMatch, reverse

    try:
        return reverse(
            f"admin:{obj._meta.app_label}_{obj._meta.model_name}_change",
            args=[obj.pk],
        )
    except NoReverseMatch:
        return None


@dataclass(frozen=True)
class PozycjaBlokady:
    """Jeden rekord blokujący kosz.

    ``obj`` — co pokazać i dokąd linkować: dla wiersza dziecka publikacji
    (``*_Autor``) to publikacja-rodzic, inaczej sam ``wiersz``.
    ``w_koszu`` — ``obj`` (albo rodzic wiersza) jest w koszu.
    """

    obj: object
    w_koszu: bool = False
    wiersz: object = None
    #: Tekst pozycji, gdy ``str(obj)`` nie wystarcza (np. wpis kolejki PBN).
    opis: str = ""

    @property
    def url(self):
        return url_w_adminie(self.obj)

    @property
    def tekst(self):
        return self.opis or str(self.obj)


@dataclass
class GrupaBlokady:
    """Rekordy jednej relacji blokujące kosz (próbka + liczby z bazy)."""

    etykieta: str
    liczba: int
    w_koszu: int = 0
    pozycje: list = field(default_factory=list)

    @property
    def reszta(self):
        return max(0, self.liczba - len(self.pozycje))


class BlokadaKosza(ProtectedError):
    """``ProtectedError`` guardu kosza z listą blokujących powiązań
    pogrupowaną per relacja (``grupy``) — admin pokazuje ją na stronie
    „Nie można przenieść do kosza", żeby operator mógł je odszukać."""

    def __init__(self, msg, protected_objects, grupy=()):
        super().__init__(msg, protected_objects)
        self.grupy = list(grupy)


def _pole_rodzica(model):
    """Pole FK do publikacji-rodzica dla dziecka publikacji, inaczej ``None``."""
    manager = model._default_manager
    if isinstance(manager, BppZywyRodzicManager):
        return manager.pole_rodzica
    return None


def _ma_kosz(model):
    try:
        model._meta.get_field("deleted_at")
    except FieldDoesNotExist:
        return False
    return True


def etykieta_relacji_kosza(model, pole):
    klucz = f"{model._meta.label}.{pole}"
    if klucz in ETYKIETY_RELACJI_KOSZA:
        return ETYKIETY_RELACJI_KOSZA[klucz]
    nazwa_pola = model._meta.get_field(pole).verbose_name
    return f"{capfirst(model._meta.verbose_name_plural)} ({nazwa_pola})"


def grupa_blokady(
    instance, model, pole, limit=None, qs=None, rodzic=None, etykieta=None
):
    """Powiązania ``instance`` w relacji ``(model, pole)`` jako
    ``GrupaBlokady`` albo ``None`` (brak powiązań).

    JEDNO zapytanie na relację: próbka ``limit`` wierszy (najpierw te
    w koszu) z liczbą wszystkich i liczbą tych w koszu policzonymi funkcją
    okna (``COUNT(*) OVER ()``) — przed ``LIMIT``, więc niezależnie od
    próbki.

    ``_base_manager`` widzi WSZYSTKO: kosz, autorstwa publikacji z kosza
    (domyślny menedżer ``*_Autor`` je ukrywa) i wiersze modeli spoza
    soft-delete.

    ``qs``/``rodzic``/``etykieta`` — dla powiązań spoza ``_meta`` (GenericFK):
    gotowy queryset, pole rekordu do pokazania i nazwa grupy.
    """
    if limit is None:
        limit = LIMIT_POZYCJI_BLOKADY
    if qs is None:
        qs = model._base_manager.filter(**{pole: instance})
    if rodzic is None:
        rodzic = _pole_rodzica(model)
    lookup_kosza = None
    if rodzic is not None:
        lookup_kosza = f"{rodzic}__deleted_at__isnull"
        qs = qs.select_related(rodzic)
    elif _ma_kosz(model):
        lookup_kosza = "deleted_at__isnull"

    adnotacje = {"_bpp_razem": Window(Count("pk"))}
    kolejnosc = ["pk"]
    if lookup_kosza is not None:
        w_koszu = Q(**{lookup_kosza: False})
        adnotacje["_bpp_w_koszu"] = Window(Count("pk", filter=w_koszu))
        adnotacje["_bpp_jest_w_koszu"] = ExpressionWrapper(
            w_koszu, output_field=BooleanField()
        )
        kolejnosc = ["-_bpp_jest_w_koszu", "pk"]
    wiersze = list(qs.annotate(**adnotacje).order_by(*kolejnosc)[:limit])
    if not wiersze:
        return None
    return GrupaBlokady(
        etykieta=etykieta or etykieta_relacji_kosza(model, pole),
        liczba=wiersze[0]._bpp_razem,
        w_koszu=getattr(wiersze[0], "_bpp_w_koszu", 0),
        pozycje=[
            PozycjaBlokady(
                obj=getattr(w, rodzic) if rodzic else w,
                w_koszu=bool(getattr(w, "_bpp_jest_w_koszu", False)),
                wiersz=w,
            )
            for w in wiersze
        ],
    )


def raise_if_has_protected_children(instance, relations, label):
    """Blokuje soft-delete ``instance``, jeśli ma „chronione" dzieci.

    ``relations`` to lista krotek ``(Model, "pole_fk")``. Rzuca
    ``BlokadaKosza`` (``ProtectedError``) z komunikatem PL i listą powiązań
    pogrupowaną per relacja, gdy w którejkolwiek z relacji jest co
    najmniej jedno dziecko.

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
    grupy = [
        g
        for g in (grupa_blokady(instance, model, pole) for model, pole in relations)
        if g is not None
    ]
    if not grupy:
        return
    ile = sum(g.liczba for g in grupy)
    ile_w_koszu = sum(g.w_koszu for g in grupy)
    opisy = "; ".join(f"{g.etykieta}: {g.liczba}" for g in grupy)
    w_tym = f", w tym {ile_w_koszu} w koszu" if ile_w_koszu else ""
    probka = [p.wiersz for g in grupy for p in g.pozycje][:LIMIT_PROBKI_CHRONIONYCH]
    raise BlokadaKosza(
        f"Nie można usunąć {label} „{instance}” — rekord ma {ile} "
        f"powiązanych rekordów{w_tym} ({opisy}). Najpierw przenieś lub usuń "
        f"te powiązania.",
        probka,
        grupy,
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


class NiedozwolonaZmianaKosza(ValueError):
    """``delete()`` rekordu, który JUŻ jest w koszu, albo ``restore()``
    rekordu, który w koszu nie jest — taki stan nie może zajść (decyzja
    właściciela): ponowne „usunięcie" przesunęłoby datę nagrobka, dopisało
    drugi ``SoftDeleteLog`` i zleciło drugie wycofanie z PBN."""


def sprawdz_stan_kosza(instance, ma_byc_w_koszu):
    """Blokuje wiersz i rzuca ``NiedozwolonaZmianaKosza``, gdy rekord nie
    jest w stanie wymaganym przez operację."""
    w_koszu = zablokuj_i_sprawdz_kosz(instance)
    if w_koszu and not ma_byc_w_koszu:
        raise NiedozwolonaZmianaKosza(f"„{instance}” jest już w koszu.")
    if not w_koszu and ma_byc_w_koszu:
        raise NiedozwolonaZmianaKosza(f"„{instance}” nie jest w koszu.")


def zablokuj_i_sprawdz_kosz(instance):
    """Blokuje wiersz (``SELECT … FOR UPDATE``) i zwraca ``True``, gdy rekord
    JEST w koszu (stan z bazy, nie z pamięci).

    ``delete()`` rekordu już w koszu nie może przesunąć ``deleted_at``
    (konsumenci ``/api/v1/usuniete/`` widzieliby go jako świeżo usunięty),
    dopisać drugiego ``SoftDeleteLog`` ani zlecić drugiego wycofania z PBN
    — patrz ``sprawdz_stan_kosza``. Blokada serializuje też równoległe
    kosz/przywrócenie tego samego rekordu.
    """
    deleted_at = (
        type(instance)
        ._base_manager.select_for_update()
        .filter(pk=instance.pk)
        .values_list("deleted_at", flat=True)
        .first()
    )
    instance.deleted_at = deleted_at
    return deleted_at is not None


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
        # Fizyczne usunięcie (także rekordu z kosza) — jedyna dozwolona droga
        # poza delete()/restore(); trigger kosza przepuszcza je z flagą.
        with operacja_kosza():
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


# --- unikalność a kosz ------------------------------------------------------
#
# Rekord w koszu ZACHOWUJE swoje wartości unikalne (slug, nazwa, ORCID,
# PBN UID, …) — decyzja właściciela (listopad 2026): link /jan-kowalski/
# zostaje na zawsze. Konsekwencje:
#
# - autoslug sprawdza unikalność przez menedżer widzący kosz
#   (``AutoSlugField(manager_name="global_objects")``), więc nowy
#   „Jan Kowalski" dostaje po prostu nowy slug (``jan-kowalski-2``);
# - wpisanie wartości trzymanej przez rekord z kosza kończy się błędem
#   WALIDACJI formularza („jest w koszu — przywróć go") zamiast
#   ``IntegrityError`` — ``BppUnikalnoscZKoszemMixin.validate_unique``;
# - ``restore()`` niczego nie odzyskuje; jeśli mimo to łamie ograniczenie
#   (np. warunkowe „jedna żywa habilitacja"), kończy się
#   ``KonfliktPrzywracania`` z czytelnym komunikatem, nie 500.


class KonfliktPrzywracania(ValueError):
    """Rekordu nie da się przywrócić z kosza — przywrócenie złamałoby
    ograniczenie unikalności (np. autor ma już żywą habilitację)."""


#: Czytelne komunikaty dla znanych ograniczeń łamanych przy przywracaniu.
KOMUNIKATY_KONFLIKTU = {
    "phab_uniq_autor_zywy": "Nie można przywrócić — autor ma już habilitację.",
}


def zapisz_przywrocenie(instance, update_fields):
    """``save(update_fields=...)`` przywrócenia w savepoincie;
    ``IntegrityError`` (naruszenie unikalności) → ``KonfliktPrzywracania``."""
    try:
        with operacja_kosza():
            instance.save(update_fields=update_fields)
    except IntegrityError as e:
        nazwa = getattr(getattr(e.__cause__, "diag", None), "constraint_name", "")
        komunikat = KOMUNIKATY_KONFLIKTU.get(
            nazwa,
            f"Nie można przywrócić „{instance}” — narusza to ograniczenie "
            f"unikalności ({nazwa or e}). Zmień dane jednego z rekordów "
            f"i spróbuj ponownie.",
        )
        # Instancja w pamięci wraca do stanu z bazy (nadal w koszu).
        instance.refresh_from_db(fields=update_fields)
        raise KonfliktPrzywracania(komunikat) from e


def komunikat_wartosc_w_koszu(obj):
    """Komunikat walidacji: wartość należy do rekordu z kosza."""
    from django.utils.html import format_html

    url = url_w_adminie(obj)
    if url:
        return format_html(
            'Ta wartość należy do rekordu w koszu: <a href="{}">{}</a>. '
            "Zamiast wpisywać ją tutaj, przywróć tamten rekord z kosza "
            "(lista z filtrem „Kosz → 🗑️ Tylko skasowane”, akcja „♻️ "
            "Przywróć zaznaczone”).",
            url,
            obj,
        )
    return (
        f"Ta wartość należy do rekordu w koszu: „{obj}”. Zamiast wpisywać ją "
        f"tutaj, przywróć tamten rekord z kosza."
    )


class BppUnikalnoscZKoszemMixin:
    """``validate_unique`` widzący kosz.

    Django sprawdza unikalność przez ``_default_manager``, który kosza nie
    widzi — wartość trzymana przez rekord z kosza przechodziła walidację
    i kończyła się ``IntegrityError`` (500). Tu, po standardowej walidacji,
    sprawdzamy te same zestawy pól (``unique``, ``unique_together``,
    bezwarunkowe ``UniqueConstraint``) wśród rekordów Z KOSZA i zwracamy
    błąd formularza wskazujący rekord do przywrócenia.
    """

    def validate_unique(self, exclude=None):
        super().validate_unique(exclude=exclude)
        bledy = {}
        unique_checks, _ = self._get_unique_checks(exclude=exclude)
        for model_class, pola in unique_checks:
            if not hasattr(model_class, "deleted_objects"):
                continue
            warunki = {}
            for nazwa in pola:
                pole = self._meta.get_field(nazwa)
                wartosc = getattr(self, pole.attname)
                # Jak Django na PostgreSQL: tylko NULL nie podlega unikalności
                # — pusty napis już tak.
                if wartosc is None:
                    break
                warunki[pole.attname if pole.is_relation else nazwa] = wartosc
            else:
                qs = model_class.deleted_objects.filter(**warunki)
                if self.pk is not None:
                    qs = qs.exclude(pk=self.pk)
                w_koszu = qs.first()
                if w_koszu is not None:
                    klucz = pola[0] if len(pola) == 1 else NON_FIELD_ERRORS
                    bledy.setdefault(klucz, []).append(
                        komunikat_wartosc_w_koszu(w_koszu)
                    )
        if bledy:
            raise ValidationError(bledy)


def relacje_przychodzace(model, pomijane=frozenset()):
    """Wszystkie przychodzące FK/O2O do ``model`` (``[(Model, "pole")]``),
    poza ``pomijane`` (``"app.Model.pole"``) i modelami niezarządzanymi.

    Guard kosza wyprowadzany GENERYCZNIE z ``_meta`` (ten sam zbiór relacji,
    który widzi kolektor kasowania Django): nowa relacja dopisana w
    przyszłości jest chroniona domyślnie, a pomijane są wyłącznie relacje
    jawnie wymienione (dane „przy rekordzie", które znikają razem z nim,
    dane wyliczane, logi i wiersze importów).
    """
    from django.db.models.deletion import get_candidate_relations_to_delete

    wynik = []
    for rel in get_candidate_relations_to_delete(model._meta):
        related = rel.related_model
        if not related._meta.managed:
            continue
        if f"{related._meta.label}.{rel.field.name}" in pomijane:
            continue
        wynik.append((related, rel.field.name))
    return wynik


class BppPublikacjaSoftDeleteMixin(
    BppUnikalnoscZKoszemMixin, BppPkPrzedHardDeleteMixin, SoftDeleteModel
):
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

    #: Relacje przychodzące, które NIE blokują kosza publikacji: dzieci,
    #: które znikają razem z nią (bez własnego kosza), logi rozbieżności,
    #: cache OPI, sesje importu. Wszystko inne — rozdziały książki,
    #: zgłoszenia wskazujące książkę nadrzędną, przyszłe relacje — blokuje
    #: (``relacje_przychodzace``).
    POMIJANE_RELACJE_KOSZA = frozenset(
        {
            "bpp.Wydawnictwo_Ciagle_Autor.rekord",
            "bpp.Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych.rekord",
            "bpp.Wydawnictwo_Ciagle_Tytul.rekord",
            "bpp.Wydawnictwo_Ciagle_Streszczenie.rekord",
            "bpp.Wydawnictwo_Zwarte_Autor.rekord",
            "bpp.Wydawnictwo_Zwarte_Zewnetrzna_Baza_Danych.rekord",
            "bpp.Wydawnictwo_Zwarte_Tytul.rekord",
            "bpp.Wydawnictwo_Zwarte_Streszczenie.rekord",
            "bpp.Patent_Autor.rekord",
            "bpp.Publikacja_Habilitacyjna.praca_habilitacyjna",
            "bpp.Opi_2012_Tytul_Cache.wydawnictwo_zwarte",
            "rozbieznosci.IgnorowanaRozbieznosc.rekord",
            "rozbieznosci.RozbieznoscLog.rekord",
            "importer_publikacji.ImportSession.wydawnictwo_nadrzedne",
        }
    )

    def _sprawdz_odwolania_generyczne(self):
        """GenericFK nie są relacjami ``_meta`` (``relacje_przychodzace`` ich
        nie widzi) — publikacja wskazana w habilitacji
        (``Publikacja_Habilitacyjna.publikacja``) blokuje kosz jawnie."""
        from django.contrib.contenttypes.models import ContentType

        from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna

        qs = Publikacja_Habilitacyjna.objects.filter(
            content_type=ContentType.objects.get_for_model(self),
            object_id=self.pk,
        )
        grupa = grupa_blokady(
            self,
            Publikacja_Habilitacyjna,
            None,
            qs=qs,
            rodzic="praca_habilitacyjna",
            etykieta="Habilitacje wskazujące tę publikację",
        )
        if grupa is not None:
            raise BlokadaKosza(
                f"Nie można przenieść do kosza „{self}” — publikacja jest "
                f"wskazana w habilitacji ({grupa.liczba}× powiązanie "
                f"publikacji z habilitacją). Najpierw usuń te powiązania.",
                [p.wiersz for p in grupa.pozycje],
                [grupa],
            )

    def sprawdz_czy_mozna_do_kosza(self, *args, **kwargs):
        """Guard kosza (BEZ efektów ubocznych) — rzuca ``ProtectedError``,
        gdy publikacji nie wolno wyrzucić:

        - wskazuje na nią żywy (albo z kosza) rekord, np. rozdział książki,
          zgłoszenie z tą książką jako nadrzędną;
        - ma autorów z KILKU uczelni — kosz jest per instalacja, więc jedna
          uczelnia wyrzuciłaby rekord także drugiej (i wycofała go z jej
          PBN). Uczelnia powinna usunąć z rekordu SWOICH autorów i zapisać.
        """
        raise_if_has_protected_children(
            self,
            relacje_przychodzace(type(self), self.POMIJANE_RELACJE_KOSZA),
            label="publikacji",
        )
        self._sprawdz_odwolania_generyczne()
        rel = self._relacja_autorstw()
        if rel is None:
            return
        autorstwa = rel.related_model.all_objects.filter(**{rel.field.name: self})
        uczelnie = {
            u
            for u in autorstwa.values_list("jednostka__uczelnia__nazwa", flat=True)
            if u
        }
        if len(uczelnie) > 1:
            raise BlokadaKosza(
                f"Nie można przenieść do kosza „{self}” — rekord ma autorów "
                f"z kilku uczelni ({', '.join(sorted(uczelnie))}). Zamiast "
                f"usuwać cały rekord, usuń z niego autorów swojej uczelni "
                f"i zapisz rekord.",
                [],
                self._grupy_autorow_per_uczelnia(autorstwa),
            )

    def _grupy_autorow_per_uczelnia(self, autorstwa):
        """Autorzy rekordu pogrupowani per uczelnia (do strony blokady)."""
        grupy = {}
        for wiersz in autorstwa.select_related("autor", "jednostka__uczelnia").order_by(
            "jednostka__uczelnia__nazwa", "kolejnosc", "pk"
        ):
            uczelnia = wiersz.jednostka.uczelnia if wiersz.jednostka_id else None
            if uczelnia is None:
                continue
            grupa = grupy.setdefault(
                uczelnia.pk,
                GrupaBlokady(etykieta=f"Autorzy z uczelni: {uczelnia}", liczba=0),
            )
            grupa.liczba += 1
            if len(grupa.pozycje) < LIMIT_POZYCJI_BLOKADY:
                grupa.pozycje.append(PozycjaBlokady(obj=wiersz.autor, wiersz=wiersz))
        return list(grupy.values())

    def delete(self, *args, user=None, reason="", **kwargs):
        """Soft-delete publikacji. BEZ kaskady na dzieci.

        Rekord z niezakończonym wpisem kolejki PBN NIE trafia do kosza
        (``RekordWKolejcePBN``).

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
            from pbn_export_queue.operacje import sprawdz_kolejke_przed_koszem

            sprawdz_stan_kosza(self, ma_byc_w_koszu=False)
            self.sprawdz_czy_mozna_do_kosza()
            # Blokada kolejki rekordu + reguła „niezakończony wpis blokuje"
            # + świeży ``pbn_uid`` (decyduje o wycofaniu w receiverze).
            sprawdz_kolejke_przed_koszem(self)
            self.deleted_at = timezone.now()
            self.restored_at = None
            self.transaction_id = txid
            with operacja_kosza():
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
        from pbn_export_queue.operacje import sprawdz_kolejke_przed_koszem

        with soft_delete_context(user=user), transaction.atomic():
            sprawdz_stan_kosza(self, ma_byc_w_koszu=True)
            txid = self.transaction_id
            # Ta sama reguła co przy koszu (np. wycofanie jeszcze trwa), pod
            # blokadą kolejki, w tej samej transakcji co zlecenie wysyłki.
            sprawdz_kolejke_przed_koszem(self)
            self.deleted_at = None
            self.restored_at = timezone.now()
            self.transaction_id = None
            zapisz_przywrocenie(self, ["deleted_at", "restored_at", "transaction_id"])
            post_restore.send(sender=self.__class__, instance=self, transaction_id=txid)

    restore.alters_data = True


class BppSoftDeleteSlownikMixin(
    BppUnikalnoscZKoszemMixin, BppPkPrzedHardDeleteMixin, SoftDeleteModel
):
    """Kosz dla uczelni i słowników (``Uczelnia``, ``Zrodlo``, ``Wydawca``,
    ``Konferencja``, ``Seria_Wydawnicza``) oraz zgłoszeń publikacji
    (``zglos_publikacje.Zgloszenie_Publikacji`` — wszystkie jego relacje
    przychodzące są pominięte, więc guard nic nie blokuje).
    ``Jednostka`` NIE ma kosza
    (nie kasuje się jej wcale — ``JednostkaNieDoUsuniecia``).

    Do kosza trafia wyłącznie rekord NIEUŻYWANY: guard bierze WSZYSTKIE
    przychodzące relacje (``relacje_przychodzace``) poza jawnie pominiętymi
    w ``pomijane_relacje_kosza`` i liczy powiązania przez ``_base_manager``
    (także w koszu). Kaskady pakietu NIE wołamy (kasowałaby twardo dzieci
    spoza kosza). Wartości unikalne zostają przy rekordzie — patrz
    komentarz sekcji wyżej.

    Model z własnym menedżerem ``objects`` musi go oprzeć na
    ``BppSoftDeleteManager`` (inaczej kosz nie jest ukryty).
    """

    #: ``"app.Model.pole"`` — relacje, które NIE blokują kosza.
    pomijane_relacje_kosza = frozenset()

    objects = BppSoftDeleteManager()
    global_objects = BppGlobalManager()
    deleted_objects = BppDeletedManager()

    class Meta:
        abstract = True

    def relacje_chronione_kosza(self):
        """``[(Model, "pole_fk"), …]`` — powiązania blokujące kosz."""
        return relacje_przychodzace(type(self), self.pomijane_relacje_kosza)

    def sprawdz_czy_mozna_do_kosza(self, *args, **kwargs):
        """Guard: rzuca ``ProtectedError``, gdy rekord jest używany."""
        raise_if_has_protected_children(
            self,
            self.relacje_chronione_kosza(),
            label=f"rekordu „{self._meta.verbose_name}”",
        )

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields:
            kwargs["update_fields"] = dopisz_znacznik_zmiany(self, update_fields)
        return super().save(*args, **kwargs)

    def delete(self, *args, user=None, reason="", **kwargs):
        txid = kwargs.pop("transaction_id", None) or uuid.uuid4()
        with soft_delete_context(user=user, reason=reason), transaction.atomic():
            sprawdz_stan_kosza(self, ma_byc_w_koszu=False)
            self.sprawdz_czy_mozna_do_kosza()
            self.deleted_at = timezone.now()
            self.restored_at = None
            self.transaction_id = txid
            with operacja_kosza():
                self.save(update_fields=["deleted_at", "restored_at", "transaction_id"])
            post_soft_delete.send(sender=self.__class__, instance=self)
        return 1, {self._meta.label: 1}

    delete.alters_data = True

    def restore(self, *args, strict: bool = False, user=None, **kwargs):
        with soft_delete_context(user=user), transaction.atomic():
            sprawdz_stan_kosza(self, ma_byc_w_koszu=True)
            txid = self.transaction_id
            self.deleted_at = None
            self.restored_at = timezone.now()
            self.transaction_id = None
            zapisz_przywrocenie(self, ["deleted_at", "restored_at", "transaction_id"])
            post_restore.send(sender=self.__class__, instance=self, transaction_id=txid)

    restore.alters_data = True
