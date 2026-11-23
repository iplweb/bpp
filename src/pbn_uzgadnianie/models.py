"""Przebieg operacji „Uzgodnij z PBN” (FD#477)."""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class UzgodnienieZPBN(models.Model):
    """Jeden przebieg uzgadniania: zakres, tryb, stan i wynik (raport)."""

    class Tryb(models.TextChoices):
        POBRANIE = "pobranie", "pobranie danych z PBN"
        PODGLAD = "podglad", "podgląd (bez zmian w BPP)"
        WYKONANIE = "wykonanie", "wykonanie"

    class Status(models.TextChoices):
        OCZEKUJE = "oczekuje", "oczekuje w kolejce"
        W_TOKU = "w_toku", "w toku"
        ZAKONCZONE = "zakonczone", "zakończone"
        ANULOWANE = "anulowane", "anulowane"
        BLAD = "blad", "błąd"

    AKTYWNE = (Status.OCZEKUJE, Status.W_TOKU)

    #: Po tylu minutach bez znaku życia przebieg „w toku” uznajemy za przerwany
    #: (restart workera, zabity proces).
    MINUTY_DO_UZNANIA_ZA_PRZERWANY = 30

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, related_name="uzgodnienia_z_pbn"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uzgodnienia_z_pbn",
    )
    rok_od = models.PositiveSmallIntegerField("Rok od")
    rok_do = models.PositiveSmallIntegerField("Rok do")
    tryb = models.CharField(max_length=16, choices=Tryb.choices)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OCZEKUJE
    )
    #: Przebieg, z którego pochodzą dane z PBN: pobranie danych (podgląd
    #: i wykonanie pracują na nim, same niczego nie pobierają) albo podgląd
    #: (wykonanie „dokładnie tego podglądu”).
    na_podstawie = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wykonania",
    )

    etap = models.CharField(max_length=200, blank=True, default="")
    postep = models.PositiveSmallIntegerField(default=0)
    anuluj = models.BooleanField(default=False)
    blad = models.TextField(blank=True, default="")

    utworzono = models.DateTimeField(auto_now_add=True)
    rozpoczeto = models.DateTimeField(null=True, blank=True)
    zakonczono = models.DateTimeField(null=True, blank=True)
    ostatnia_aktualizacja = models.DateTimeField(auto_now=True)

    #: Zakres ustalony w etapie 1: profil instytucji w PBN (identyfikator
    #: publikacji → przypięta wersja) i lista prac z wybranych lat.
    zakres = models.JSONField(default=dict, blank=True)
    #: Raport: lista wpisów (po jednym na pracę) — patrz ``silnik``.
    wynik = models.JSONField(default=list, blank=True)
    podsumowanie = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = "uzgodnienie z PBN"
        verbose_name_plural = "uzgodnienia z PBN"
        ordering = ["-utworzono"]
        constraints = [
            # Jeden aktywny przebieg na uczelnię — dwa równoległe mogłyby
            # utworzyć ten sam rekord dwa razy.
            models.UniqueConstraint(
                fields=["uczelnia"],
                condition=Q(status__in=["oczekuje", "w_toku"]),
                name="pbn_uzgadnianie_jeden_aktywny_na_uczelnie",
            ),
            models.CheckConstraint(
                condition=Q(rok_od__lte=models.F("rok_do")),
                name="pbn_uzgadnianie_rok_od_lte_rok_do",
            ),
        ]

    def __str__(self):
        return (
            f"Uzgodnienie z PBN {self.rok_od}–{self.rok_do} "
            f"({self.get_tryb_display()}, {self.get_status_display()})"
        )

    @property
    def aktywne(self):
        return self.status in self.AKTYWNE

    @property
    def to_podglad(self):
        return self.tryb == self.Tryb.PODGLAD

    @property
    def to_pobranie(self):
        return self.tryb == self.Tryb.POBRANIE

    @classmethod
    def ostatnie_pobranie(cls, uczelnia, rok_od=None, rok_do=None):
        """Najnowsze zakończone pobranie danych uczelni (albo ``None``).

        Z latami: tylko pobranie OBEJMUJĄCE cały zakres ``rok_od``–``rok_do``
        (publikacje i oświadczenia pobieramy tylko dla lat pobrania).
        """
        pobrania = cls.objects.filter(
            uczelnia=uczelnia,
            tryb=cls.Tryb.POBRANIE,
            status=cls.Status.ZAKONCZONE,
        )
        if rok_od is not None:
            pobrania = pobrania.filter(rok_od__lte=rok_od, rok_do__gte=rok_do)
        return pobrania.order_by("-zakonczono").first()

    @classmethod
    def oznacz_przerwane(cls, uczelnia):
        """Przebiegi „w toku” bez znaku życia → ``błąd`` (zwalnia blokadę)."""
        granica = timezone.now() - timedelta(minutes=cls.MINUTY_DO_UZNANIA_ZA_PRZERWANY)
        return cls.objects.filter(
            uczelnia=uczelnia,
            status__in=cls.AKTYWNE,
            ostatnia_aktualizacja__lt=granica,
        ).update(
            status=cls.Status.BLAD,
            blad="Przebieg przerwany (brak postępu) — uruchom ponownie. "
            "Zmiany wykonane do chwili przerwania są zapisane; ponowne "
            "uruchomienie dokończy resztę.",
            zakonczono=timezone.now(),
        )
