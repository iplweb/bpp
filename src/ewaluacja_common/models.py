from django.conf import settings
from django.db import models


class Rodzaj_Autora(models.Model):
    nazwa = models.CharField(max_length=100, verbose_name="Nazwa")
    skrot = models.CharField(max_length=1, unique=True, verbose_name="Skrót")
    sort = models.PositiveSmallIntegerField(verbose_name="Sortowanie")
    jest_w_n = models.BooleanField(
        default=False, verbose_name="Określa czy dany rodzaj autora wchodzi do liczby N"
    )
    licz_sloty = models.BooleanField(
        default=False, verbose_name="Określa, czy dany rodzaj autora ma obliczane sloty"
    )

    class Meta:
        verbose_name = "Rodzaj autora"
        verbose_name_plural = "Rodzaje autorów"
        ordering = ["sort"]

    def __str__(self):
        return f"{self.skrot} - {self.nazwa}"


class OkresEwaluacji(models.Model):
    """Okres objęty ewaluacją (np. 2022–2025, 2026–2030).

    Trzymany w bazie, a nie w kodzie: długość kolejnego okresu zależy od
    nowelizacji ustawy (projekt z 2026 r. wydłuża okres z 4 do 5 lat).
    Okresy definiujemy MY — w adminie są tylko do odczytu (bez dodawania,
    edycji i usuwania); zmiana przepisów = migracja danych w wydaniu.
    Użytkownik przełącza okres na pasku okresu pod ścieżką nawigacji stron ewaluacji; wybór jest
    zapamiętywany na stałe (``WybranyOkresEwaluacji``). Bez wyboru — okres,
    w którym mieści się bieżący rok (``ewaluacja_common.okres.okres_domyslny``).
    """

    rok_od = models.PositiveSmallIntegerField("pierwszy rok", unique=True)
    rok_do = models.PositiveSmallIntegerField("ostatni rok")
    uwagi = models.TextField(
        blank=True,
        help_text="Np. podstawa prawna albo informacja, że zasady są tymczasowe.",
    )

    class Meta:
        verbose_name = "okres ewaluacji"
        verbose_name_plural = "okresy ewaluacji"
        ordering = ["rok_od"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(rok_do__gte=models.F("rok_od")),
                name="okres_ewaluacji_rok_do_gte_rok_od",
            )
        ]

    def __str__(self):
        return f"{self.rok_od}–{self.rok_do}"

    @property
    def slug(self):
        """Okres w adresie URL stron ewaluacji, np. ``2026-2030``."""
        return f"{self.rok_od}-{self.rok_do}"

    @property
    def lata(self):
        return list(range(self.rok_od, self.rok_do + 1))

    @property
    def liczba_lat(self):
        return self.rok_do - self.rok_od + 1

    def ostatni_rok_liczenia(self, dzis=None):
        """Ostatni rok okresu, za który liczymy liczbę N: rok bieżący dla
        okresu trwającego, ``rok_do`` dla zakończonego (``rok_od - 1``, gdy
        okres się jeszcze nie zaczął — wtedy nie ma lat do liczenia)."""
        from django.utils import timezone

        biezacy = (dzis or timezone.localdate()).year
        return max(min(self.rok_do, biezacy), self.rok_od - 1)

    def zawiera(self, rok):
        return self.rok_od <= rok <= self.rok_do


class WybranyOkresEwaluacji(models.Model):
    """Ostatnio wybrany przez użytkownika okres ewaluacji — obowiązuje na
    wszystkich stronach ewaluacji, także po ponownym zalogowaniu."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wybrany_okres_ewaluacji",
    )
    okres = models.ForeignKey(OkresEwaluacji, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "wybrany okres ewaluacji"
        verbose_name_plural = "wybrane okresy ewaluacji"

    def __str__(self):
        return f"{self.user}: {self.okres}"


class OdczytPrzebiegu(models.Model):
    """Pamięć strażnika przebiegów w tle (``ewaluacja_common.przebiegi``):
    ostatni odczyt stanu przebiegu w Celery i od kiedy ten stan trwa.

    W bazie, a nie w cache: cache bywa wyłączony (środowisko deweloperskie)
    albo osobny dla każdego procesu serwera, a anulowanie wymaga stanu
    potwierdzonego w kolejnych odczytach.
    """

    klucz = models.CharField(max_length=200, unique=True)
    task_id = models.CharField(max_length=255)
    stan = models.CharField(max_length=32)
    od = models.DateTimeField(help_text="Od kiedy trwa odczytany stan")
    sprawdzono = models.DateTimeField(help_text="Kiedy ostatnio pytano Celery")

    class Meta:
        verbose_name = "odczyt przebiegu w tle"
        verbose_name_plural = "odczyty przebiegów w tle"

    def __str__(self):
        return f"{self.klucz}: {self.stan}"
