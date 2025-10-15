from django.db import models
from django.utils import timezone

from bpp.models.autor import Autor
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from bpp.models.jednostka import Jednostka


class MetrykaAutora(models.Model):
    """Model przechowujący metryki ewaluacyjne dla autora"""

    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, related_name="metryki")

    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)

    jednostka = models.ForeignKey(
        Jednostka,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="metryka_autora",
        help_text="Główna jednostka autora w okresie ewaluacji",
    )

    # Dane z algorytmu plecakowego (nazbierane optymalne)
    slot_maksymalny = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Maksymalny slot z IloscUdzialowDlaAutoraZaCalosc",
    )

    slot_nazbierany = models.DecimalField(
        max_digits=10, decimal_places=4, help_text="Suma slotów z algorytmu plecakowego"
    )

    punkty_nazbierane = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Suma punktów PKDaut z algorytmu plecakowego",
    )

    prace_nazbierane = models.JSONField(
        default=list,
        help_text="Lista ID prac z Cache_Punktacja_Autora_Query wybranych przez algorytm",
    )

    srednia_za_slot_nazbierana = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Średnia punktów PKDaut za slot (nazbierane)",
    )

    # Dane za wszystkie prace autora w okresie 2022-2025
    slot_wszystkie = models.DecimalField(
        max_digits=10, decimal_places=4, help_text="Suma slotów za wszystkie prace"
    )

    punkty_wszystkie = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        help_text="Suma punktów PKDaut za wszystkie prace",
    )

    prace_wszystkie = models.JSONField(
        default=list,
        help_text="Lista wszystkich ID prac z Cache_Punktacja_Autora_Query",
    )

    liczba_prac_wszystkie = models.IntegerField(
        default=0, help_text="Liczba wszystkich prac autora w okresie"
    )

    srednia_za_slot_wszystkie = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Średnia punktów PKDaut za slot (wszystkie)",
    )

    # Procent wykorzystania slotów
    procent_wykorzystania_slotow = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Procent wykorzystania slotów (nazbierane/maksymalny * 100)",
    )

    # Metadane
    data_obliczenia = models.DateTimeField(
        auto_now=True, help_text="Data ostatniego przeliczenia metryk"
    )

    rok_min = models.IntegerField(
        default=2022, help_text="Początkowy rok okresu ewaluacji"
    )

    rok_max = models.IntegerField(
        default=2025, help_text="Końcowy rok okresu ewaluacji"
    )

    rodzaj_autora = models.CharField(
        max_length=1,
        blank=True,
        default="",
        help_text="Skrót rodzaju autora (N, D, B, Z)",
    )

    class Meta:
        verbose_name = "Metryka autora"
        verbose_name_plural = "Metryki autorów"
        unique_together = [("autor", "dyscyplina_naukowa")]
        ordering = ["-srednia_za_slot_nazbierana", "autor__nazwisko", "autor__imiona"]
        indexes = [
            models.Index(fields=["-srednia_za_slot_nazbierana"]),
            models.Index(fields=["jednostka", "-srednia_za_slot_nazbierana"]),
            models.Index(fields=["dyscyplina_naukowa", "-srednia_za_slot_nazbierana"]),
        ]

    def __str__(self):
        return f"{self.autor} - {self.dyscyplina_naukowa.nazwa}"

    def save(self, *args, **kwargs):
        # Wylicz średnie przed zapisem
        if self.slot_nazbierany and self.slot_nazbierany > 0:
            self.srednia_za_slot_nazbierana = (
                self.punkty_nazbierane / self.slot_nazbierany
            )
        else:
            self.srednia_za_slot_nazbierana = 0

        if self.slot_wszystkie and self.slot_wszystkie > 0:
            self.srednia_za_slot_wszystkie = self.punkty_wszystkie / self.slot_wszystkie
        else:
            self.srednia_za_slot_wszystkie = 0

        # Wylicz procent wykorzystania
        if self.slot_maksymalny and self.slot_maksymalny > 0:
            self.procent_wykorzystania_slotow = (
                self.slot_nazbierany / self.slot_maksymalny
            ) * 100
        else:
            self.procent_wykorzystania_slotow = 0

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """Zwraca URL do widoku szczegółów metryki używając stabilnych identyfikatorów"""
        from django.urls import reverse

        return reverse(
            "ewaluacja_metryki:szczegoly",
            kwargs={
                "autor_slug": self.autor.slug,
                "dyscyplina_kod": self.dyscyplina_naukowa.kod,
            },
        )

    @property
    def slot_niewykorzystany(self):
        """Zwraca ilość niewykorzystanych slotów"""
        if self.slot_maksymalny:
            return self.slot_maksymalny - self.slot_nazbierany
        return 0

    @property
    def czy_pelne_wykorzystanie(self):
        """Czy autor wykorzystał wszystkie dostępne sloty"""
        return (
            self.procent_wykorzystania_slotow >= 99.99
            if self.procent_wykorzystania_slotow
            else False
        )


class StatusGenerowania(models.Model):
    """Model przechowujący informację o ostatnim generowaniu metryk (singleton)"""

    data_rozpoczecia = models.DateTimeField(
        null=True, blank=True, help_text="Data rozpoczęcia ostatniego generowania"
    )

    data_zakonczenia = models.DateTimeField(
        null=True, blank=True, help_text="Data zakończenia ostatniego generowania"
    )

    w_trakcie = models.BooleanField(
        default=False, help_text="Czy generowanie jest w trakcie"
    )

    liczba_przetworzonych = models.IntegerField(
        default=0, help_text="Liczba przetworzonych autorów"
    )

    liczba_do_przetworzenia = models.IntegerField(
        default=0, help_text="Całkowita liczba autorów do przetworzenia"
    )

    liczba_bledow = models.IntegerField(
        default=0, help_text="Liczba błędów podczas generowania"
    )

    ostatni_komunikat = models.TextField(
        blank=True,
        default="",
        help_text="Ostatni komunikat z procesu generowania",
    )

    task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="ID zadania Celery",
    )

    class Meta:
        verbose_name = "Status generowania metryk"
        verbose_name_plural = "Status generowania metryk"

    def __str__(self):
        if self.w_trakcie:
            return f"Generowanie w trakcie (przetworzono: {self.liczba_przetworzonych})"
        elif self.data_zakonczenia:
            return f"Ostatnie generowanie: {self.data_zakonczenia.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            return "Brak informacji o generowaniu"

    def save(self, *args, **kwargs):
        # Singleton - zawsze nadpisuj rekord o id=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create(cls):
        """Pobierz lub utwórz instancję singleton"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def rozpocznij_generowanie(self, task_id="", liczba_do_przetworzenia=0):
        """Oznacz rozpoczęcie generowania"""
        self.data_rozpoczecia = timezone.now()
        self.data_zakonczenia = None
        self.w_trakcie = True
        self.liczba_przetworzonych = 0
        self.liczba_do_przetworzenia = liczba_do_przetworzenia
        self.liczba_bledow = 0
        self.ostatni_komunikat = "Rozpoczęto generowanie metryk"
        self.task_id = task_id
        self.save()

    def zakoncz_generowanie(self, liczba_przetworzonych=0, liczba_bledow=0):
        """Oznacz zakończenie generowania"""
        self.data_zakonczenia = timezone.now()
        self.w_trakcie = False
        self.liczba_przetworzonych = liczba_przetworzonych
        self.liczba_bledow = liczba_bledow
        self.ostatni_komunikat = (
            f"Zakończono generowanie. Przetworzono: {liczba_przetworzonych}, "
            f"błędy: {liczba_bledow}"
        )
        self.save()

    def aktualizuj_postep(self, liczba_przetworzonych, komunikat=""):
        """Aktualizuj postęp generowania"""
        self.liczba_przetworzonych = liczba_przetworzonych
        if komunikat:
            self.ostatni_komunikat = komunikat
        self.save()

    @property
    def czas_trwania(self):
        """Zwróć czas trwania ostatniego generowania"""
        if self.data_rozpoczecia and self.data_zakonczenia:
            return self.data_zakonczenia - self.data_rozpoczecia
        return None
