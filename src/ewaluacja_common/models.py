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
    nowelizacji ustawy (projekt z 2026 r. wydłuża okres z 4 do 5 lat) — gdy
    przepisy się zmienią, poprawia się wpis w adminie, bez wydania.
    Domyślny okres to ten, w którym mieści się bieżący rok
    (``ewaluacja_common.okres.okres_domyslny``); użytkownik może przełączyć
    się na inny w górnej belce stron ewaluacji.
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
    def lata(self):
        return list(range(self.rok_od, self.rok_do + 1))

    @property
    def liczba_lat(self):
        return self.rok_do - self.rok_od + 1

    def zawiera(self, rok):
        return self.rok_od <= rok <= self.rok_do
