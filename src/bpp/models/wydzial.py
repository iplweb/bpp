"""
Struktura uczelni.
"""

from collections import defaultdict

from autoslug import AutoSlugField
from django.db import models
from django.db.models import CASCADE, Q
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.urls.base import reverse
from django.utils import timezone
from tinymce.models import HTMLField

from bpp.models import ModelZAdnotacjami
from bpp.models.abstract import ModelZPBN_ID
from bpp.util import FulltextSearchMixin

from .uczelnia import Uczelnia


class Wydzial(ModelZAdnotacjami, ModelZPBN_ID):
    uczelnia = models.ForeignKey(Uczelnia, CASCADE)
    nazwa = models.CharField(
        max_length=512,
        unique=True,
        help_text='Pełna nazwa wydziału, np. "Wydział Lekarski"',
    )
    skrot_nazwy = models.CharField(
        max_length=250,
        unique=True,
        blank=True,
        null=True,
        help_text='Skrót nazwy wydziału, wersja czytelna, np. "Wydz. Lek."',
    )
    skrot = models.CharField(
        "Skrót",
        max_length=10,
        unique=True,
        help_text='Skrót nazwy wydziału, wersja minimalna, np. "WL"',
    )

    opis = HTMLField(null=True, blank=True)
    pokazuj_opis = models.BooleanField(default=False)
    slug = AutoSlugField(populate_from="nazwa", max_length=512, unique=True)
    poprzednie_nazwy = models.CharField(max_length=4096, blank=True, default="")
    kolejnosc = models.IntegerField("Kolejność", default=0)
    widoczny = models.BooleanField(
        default=True,
        help_text="""Czy wydział ma być widoczny przy przeglądaniu strony dla zakładki "Uczelnia"?""",
    )

    zezwalaj_na_ranking_autorow = models.BooleanField(
        "Zezwalaj na generowanie rankingu autorów dla tego wydziału", default=True
    )

    zarzadzaj_automatycznie = models.BooleanField(
        "Zarządzaj automatycznie",
        default=True,
        help_text="""Wydział ten będzie dowolnie modyfikowany przez procedury importujace dane z zewnętrznych
        systemów informatycznych. W przypadku, gdy pole ma ustawioną wartość na 'fałsz', wydział ten może być""",
    )

    otwarcie = models.DateField("Data otwarcia wydziału", blank=True, null=True)
    zamkniecie = models.DateField("Data zamknięcia wydziału", blank=True, null=True)

    class Meta:
        verbose_name = "wydział"
        verbose_name_plural = "wydziały"
        ordering = ["kolejnosc", "skrot"]
        app_label = "bpp"

    def __str__(self):
        return self.nazwa

    def get_absolute_url(self):
        return reverse("bpp:browse_wydzial", args=(self.slug,))

    def jednostki(self):
        """Lista jednostek - dla WWW"""
        from .jednostka import Jednostka

        # Faza B (#438): po retargecie ``Jednostka.wydzial`` to self-FK do
        # KORZENIA drzewa (Jednostka), a nie Wydzial. Ten Wydzial mapuje na
        # węzeł-korzeń o ``legacy_wydzial_id == self.pk`` — filtrujemy przez
        # niego (``wydzial__legacy_wydzial_id``), a nie przez ``wydzial=self``
        # (które po cichu porównywałoby Jednostka-pk do Wydzial-pk).
        return Jednostka.objects.filter(
            wydzial__legacy_wydzial_id=self.pk, widoczna=True
        ).order_by(*Jednostka.objects.get_default_ordering())

    def aktualne_jednostki(self):
        """Lista jednostek aktualnie przypisanych do danego wydziału,
        bez kół naukowych."""
        return (
            self.jednostki()
            .exclude(rodzaj__nazwa="Koło naukowe")
            .exclude(aktualna=False)
        )

    def historyczne_jednostki(self):
        """Lista przeszłych (historycznych) jednostek, które kiedyś były przypisane
        do danego wydziału, bez kół naukowych"""
        from .jednostka import Jednostka, Jednostka_Rodzic

        today = timezone.now().date()

        # Faza B (#438): metryczka historyczna wskazuje węzeł-rodzic; ten
        # wydział mapuje węzeł o legacy_wydzial_id == self.pk.
        return (
            Jednostka.objects.all()
            .exclude(aktualna=True)
            .filter(
                pk__in=Jednostka_Rodzic.objects.filter(
                    parent__legacy_wydzial_id=self.pk
                )
                .exclude(do=None)
                .exclude(do__gte=today)
                .values_list("jednostka_id", flat=True)
            )
            .order_by(*Jednostka.objects.get_default_ordering())
        )

    def kola_naukowe(self):
        from .jednostka import Jednostka, Jednostka_Rodzic

        today = timezone.now().date()

        return (
            Jednostka.objects.filter(rodzaj__nazwa="Koło naukowe")
            .filter(
                # Faza B (#438): ``wydzial`` to self-FK do korzenia — ten
                # Wydzial = węzeł o ``legacy_wydzial_id == self.pk``.
                Q(wydzial__legacy_wydzial_id=self.pk, aktualna=True)
                | Q(
                    wydzial=None,
                    pk__in=Jednostka_Rodzic.objects.filter(
                        parent__legacy_wydzial_id=self.pk
                    )
                    .exclude(do=None)
                    .exclude(do__lt=today),
                )
            )
            .order_by(*Jednostka.objects.get_default_ordering())
        )

    def wymaga_nawigacji(self):
        """Jeżeli wydział ma aktualne jednostki i koła naukowe lub jednostki historyczne, to wymaga
        wyświetlenia nawigacji na podstronie oglądania wydziału, więc wtedy zwróć True
        """
        res = defaultdict(int)

        res[self.aktualne_jednostki().exists()] += 1
        res[self.historyczne_jednostki().exists()] += 1
        res[self.kola_naukowe().exists()] += 1

        return res[True] >= 2


class JednostkaCreateManager(FulltextSearchMixin, models.Manager):
    """Manager zapewniający kompatybilność wsteczną przy tworzeniu Jednostka.

    Automatycznie ustawia uczelnia na podstawie wydzial, jeśli nie podano.
    Uwaga: Główny JednostkaManager znajduje się w jednostka.py (dziedziczy z TreeManager).
    """

    def create(self, *args, **kw):
        if "wydzial" in kw and not ("uczelnia" in kw or "uczelnia_id" in kw):
            # Kompatybilność wsteczna, z czasów, gdy nie było metryczki historycznej
            # dla obecności jednostki w wydziałach
            kw["uczelnia"] = kw["wydzial"].uczelnia
        return super().create(*args, **kw)


@receiver(post_save, sender=Wydzial)
def invalidate_uczelnia_cache_on_wydzial_change(sender, instance, **kwargs):
    """
    Invalidate main page cache when wydzial is saved.
    This ensures the homepage is updated immediately.
    """
    from bpp.views.browse import get_uczelnia_context_data

    get_uczelnia_context_data.invalidate()


@receiver(post_delete, sender=Wydzial)
def usun_wezel_lustro_wydzialu(sender, instance, **kwargs):
    """Faza B (#438): sprząta węzeł-lustro (Jednostka o
    ``legacy_wydzial_id == wydzial.id``) gdy Wydzial jest kasowany — bez tego
    zostałaby sierota wskazująca na nieistniejący już wydział. Model lustra
    jest LAZY (tworzone dopiero przy linkowaniu), więc to rzadkie, ale tanie.

    **Guard markera lustra (I-4, #438).** ``legacy_wydzial_id`` NIE oznacza już
    wyłącznie syntetycznego lustra: 1-elementowy wydział jest w I-4 (0457)
    „promowany" — jego jedyna, REALNA jednostka staje się rootem i dostaje
    ``legacy_wydzial_id`` zastąpionego wydziału (żeby mapowania 0460/0463
    ją obejmowały). Taka jednostka ma jednak ``jest_lustrem=False``, a
    syntetyczne lustro — ``jest_lustrem=True``. Kasujemy WYŁĄCZNIE lustra
    (``jest_lustrem=True``); promowana realna jednostka z dorobkiem ZOSTAJE,
    nawet gdy jej stary Wydzial jest kasowany.

    **Guard referencji (I-4 + II-2/0460).** Po I-4 węzeł-lustro MA DZIECI — pod
    niego podpięte są realne jednostki (``parent``, TreeForeignKey CASCADE) oraz
    wpisy ``Jednostka_Rodzic.parent`` (CASCADE). Dodatkowo 0460 przepięło na
    ``Jednostka`` FK konsumentów wydziału: ``Kierunek_Studiow.wydzial`` (PROTECT),
    ``Patent.wydzial`` (SET_NULL), ``Opi_2012_Afiliacja_Do_Wydzialu.wydzial``
    (CASCADE). Bezwarunkowe ``.delete()`` skaskadowałoby / wyzerowałoby /
    zprotectowałoby te dane. Dlatego kasujemy węzeł WYŁĄCZNIE, gdy NIC go nie
    referencuje (transient lustro sprzed jakiegokolwiek podlinkowania). Sam
    check dzieci-Jednostek nie wystarcza — trzeba objąć wszystkie FK/O2O.
    """
    from .jednostka import Jednostka

    # ``jest_lustrem=True`` odsiewa promowane realne jednostki (I-4): mają
    # ``legacy_wydzial_id``, ale nie są syntetycznym lustrem (stabilny marker,
    # nie edytowalna nazwa rodzaju).
    for node in Jednostka.objects.filter(
        legacy_wydzial_id=instance.id, jest_lustrem=True
    ):
        if _wezel_lustro_ma_referencje(node):
            # Cokolwiek wskazuje na węzeł (dzieci po I-4 LUB konsument z 0460)
            # → NIE kasuj: CASCADE/SET_NULL/PROTECT zniszczyłby/uszkodził cudze
            # dane albo wywaliłby kasowanie Wydziału.
            continue
        node.delete()


def _wezel_lustro_ma_referencje(node):
    """True, gdy JAKIKOLWIEK trwały wiersz referencuje ``node`` przez FK/O2O —
    wtedy NIE jest transientnym lustrem i kasowanie uszkodziłoby cudze dane
    (CASCADE / SET_NULL / PROTECT).

    Iterujemy WSZYSTKIE odwrotne relacje przez ``get_fields(include_hidden=True)``
    (a NIE ``related_objects``, które POMIJA ukryte odwrotne FK/O2O z
    ``related_name="+"`` — a ten wzorzec jest w repo używany dla drugich FK do
    ``Jednostka``: ``Import_Dyscyplin_Row.wydzial`` SET_NULL, denorm
    ``Jednostka.wydzial``). Pomijamy modele ``managed=False``: (a) tabele
    tymczasowe ``bpp_temporary_*`` (cache/punktacja) potrafią nie istnieć w danym
    momencie i zapytanie rzuca ProgrammingError wywalający transakcję; (b) widoki
    DB (np. ``Nowe_Sumy_View``, DO_NOTHING) są DERYWOWANE — brak trwałych danych.
    Generyczność jest tu ISTOTNA: inwentarz II-2 ma 8 konsumentów (m.in.
    przepięci poza bpp — ``Obslugujacy_Zgloszenia_Wydzialow`` CASCADE w
    zglos_publikacje, ``Import_Dyscyplin_Row`` SET_NULL) — kuratorowana lista już
    raz je zgubiła, a nowe FK dojdą bez aktualizacji tej funkcji."""
    from django.db.models.fields.reverse_related import ForeignObjectRel

    for rel in node._meta.get_fields(include_hidden=True):
        if not isinstance(rel, ForeignObjectRel):
            continue
        related_model = rel.related_model
        if not related_model._meta.managed:
            continue
        if related_model._base_manager.filter(**{rel.field.name: node}).exists():
            return True
    return False
