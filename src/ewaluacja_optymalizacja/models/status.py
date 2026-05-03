"""Singleton modele śledzące status długo-działających zadań Celery.

Każdy z modeli ``Status*`` przechowuje stan jednego rodzaju zadania
optymalizacji/analizy. Używane do zapewnienia, że tylko jedno zadanie
danego typu może być uruchomione naraz oraz do prezentacji statusu w UI.
"""

from django.db import models
from django.utils import timezone

from bpp.models import Uczelnia


class StatusOptymalizacjiZOdpinaniem(models.Model):
    """
    Singleton model śledzący status zadania optymalizacji z odpinaniem.
    Używany do zapewnienia, że tylko jedno zadanie może być uruchomione naraz
    oraz do przekierowania użytkownika do strony statusu działającego zadania.
    """

    w_trakcie = models.BooleanField(
        default=False,
        verbose_name="W trakcie",
        help_text="Czy zadanie jest obecnie uruchomione",
    )
    task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="ID zadania Celery",
    )
    data_rozpoczecia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data rozpoczęcia",
    )
    data_zakonczenia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data zakończenia",
    )
    ostatni_komunikat = models.TextField(
        blank=True,
        default="",
        verbose_name="Ostatni komunikat",
    )

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Status optymalizacji z odpinaniem"
        verbose_name_plural = "Status optymalizacji z odpinaniem"

    def __str__(self):
        if self.w_trakcie:
            return f"W trakcie (task_id: {self.task_id})"
        elif self.data_zakonczenia:
            return f"Zakończono: {self.data_zakonczenia.strftime('%Y-%m-%d %H:%M:%S')}"
        return "Brak uruchomionych zadań"

    def save(self, *args, **kwargs):
        # Singleton - zawsze nadpisuj rekord o pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create(cls):
        """Pobierz lub utwórz instancję singleton."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def rozpocznij(self, task_id):
        """Oznacz rozpoczęcie zadania optymalizacji z odpinaniem."""
        self.w_trakcie = True
        self.task_id = task_id
        self.data_rozpoczecia = timezone.now()
        self.data_zakonczenia = None
        self.ostatni_komunikat = "Rozpoczęto optymalizację z odpinaniem"
        self.save()

    def zakoncz(self, komunikat=""):
        """Oznacz zakończenie zadania optymalizacji z odpinaniem."""
        self.w_trakcie = False
        self.data_zakonczenia = timezone.now()
        self.ostatni_komunikat = komunikat or "Zakończono"
        self.save()


class StatusOptymalizacjiBulk(models.Model):
    """
    Singleton model śledzący status zadania "Policz całą ewaluację".
    Używany do zapewnienia, że tylko jedno zadanie może być uruchomione naraz
    oraz do przekierowania użytkownika do strony statusu działającego zadania.
    """

    w_trakcie = models.BooleanField(
        default=False,
        verbose_name="W trakcie",
        help_text="Czy zadanie jest obecnie uruchomione",
    )
    task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="ID zadania Celery",
    )
    uczelnia = models.ForeignKey(
        Uczelnia,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Uczelnia",
    )
    data_rozpoczecia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data rozpoczęcia",
    )
    data_zakonczenia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data zakończenia",
    )
    ostatni_komunikat = models.TextField(
        blank=True,
        default="",
        verbose_name="Ostatni komunikat",
    )
    plik_zip_wszystkie_xls = models.FileField(
        upload_to="protected/ewaluacja_optymalizacja/",
        null=True,
        blank=True,
        verbose_name="Plik ZIP ze wszystkimi XLS",
        help_text="Cache pliku ZIP generowanego po zakończeniu optymalizacji bulk",
    )

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Status optymalizacji bulk"
        verbose_name_plural = "Status optymalizacji bulk"

    def __str__(self):
        if self.w_trakcie:
            return f"W trakcie (task_id: {self.task_id})"
        elif self.data_zakonczenia:
            return f"Zakończono: {self.data_zakonczenia.strftime('%Y-%m-%d %H:%M:%S')}"
        return "Brak uruchomionych zadań"

    def save(self, *args, **kwargs):
        # Singleton - zawsze nadpisuj rekord o pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create(cls):
        """Pobierz lub utwórz instancję singleton."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def rozpocznij(self, task_id, uczelnia):
        """Oznacz rozpoczęcie zadania bulk optimization."""
        # Usuń stary plik ZIP przed nową optymalizacją
        if self.plik_zip_wszystkie_xls:
            self.plik_zip_wszystkie_xls.delete(save=False)

        self.w_trakcie = True
        self.task_id = task_id
        self.uczelnia = uczelnia
        self.data_rozpoczecia = timezone.now()
        self.data_zakonczenia = None
        self.ostatni_komunikat = "Rozpoczęto optymalizację całej ewaluacji"
        self.save()

    def zakoncz(self, komunikat=""):
        """Oznacz zakończenie zadania bulk optimization."""
        self.w_trakcie = False
        self.data_zakonczenia = timezone.now()
        self.ostatni_komunikat = komunikat or "Zakończono"
        self.save()


class StatusUnpinningAnalyzy(models.Model):
    """
    Singleton model śledzący status zadania analizy możliwości odpinania.
    Używany do zapewnienia, że tylko jedno zadanie może być uruchomione naraz
    oraz do przekierowania użytkownika do strony statusu działającego zadania.

    Zastępuje wcześniejsze przechowywanie task_id w sesji przeglądarki,
    co pozwala na śledzenie statusu zadania globalnie dla wszystkich użytkowników.
    """

    w_trakcie = models.BooleanField(
        default=False,
        verbose_name="W trakcie",
        help_text="Czy zadanie jest obecnie uruchomione",
    )
    task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="ID zadania Celery",
    )
    data_rozpoczecia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data rozpoczęcia",
    )
    data_zakonczenia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data zakończenia",
    )
    ostatni_komunikat = models.TextField(
        blank=True,
        default="",
        verbose_name="Ostatni komunikat",
    )

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Status analizy unpinning"
        verbose_name_plural = "Status analizy unpinning"

    def __str__(self):
        if self.w_trakcie:
            return f"W trakcie (task_id: {self.task_id})"
        elif self.data_zakonczenia:
            return f"Zakończono: {self.data_zakonczenia.strftime('%Y-%m-%d %H:%M:%S')}"
        return "Brak uruchomionych zadań"

    def save(self, *args, **kwargs):
        # Singleton - zawsze nadpisuj rekord o pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create(cls):
        """Pobierz lub utwórz instancję singleton."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def rozpocznij(self, task_id):
        """Oznacz rozpoczęcie zadania analizy unpinning."""
        self.w_trakcie = True
        self.task_id = task_id
        self.data_rozpoczecia = timezone.now()
        self.data_zakonczenia = None
        self.ostatni_komunikat = "Rozpoczęto analizę możliwości odpinania"
        self.save()

    def zakoncz(self, komunikat=""):
        """Oznacz zakończenie zadania analizy unpinning."""
        self.w_trakcie = False
        self.data_zakonczenia = timezone.now()
        self.ostatni_komunikat = komunikat or "Zakończono"
        self.save()


class StatusDisciplineSwapAnalysis(models.Model):
    """
    Singleton model śledzący status zadania analizy zamiany dyscyplin.
    Używany do zapewnienia, że tylko jedno zadanie może być uruchomione naraz
    oraz do przekierowania użytkownika do strony statusu działającego zadania.
    """

    w_trakcie = models.BooleanField(
        default=False,
        verbose_name="W trakcie",
        help_text="Czy zadanie jest obecnie uruchomione",
    )
    task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="ID zadania Celery",
    )
    data_rozpoczecia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data rozpoczęcia",
    )
    data_zakonczenia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data zakończenia",
    )
    ostatni_komunikat = models.TextField(
        blank=True,
        default="",
        verbose_name="Ostatni komunikat",
    )

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Status analizy zamiany dyscyplin"
        verbose_name_plural = "Status analizy zamiany dyscyplin"

    def __str__(self):
        if self.w_trakcie:
            return f"W trakcie (task_id: {self.task_id})"
        elif self.data_zakonczenia:
            return f"Zakończono: {self.data_zakonczenia.strftime('%Y-%m-%d %H:%M:%S')}"
        return "Brak uruchomionych zadań"

    def save(self, *args, **kwargs):
        # Singleton - zawsze nadpisuj rekord o pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create(cls):
        """Pobierz lub utwórz instancję singleton."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def rozpocznij(self, task_id):
        """Oznacz rozpoczęcie zadania analizy zamiany dyscyplin."""
        self.w_trakcie = True
        self.task_id = task_id
        self.data_rozpoczecia = timezone.now()
        self.data_zakonczenia = None
        self.ostatni_komunikat = "Rozpoczęto analizę możliwości zamiany dyscyplin"
        self.save()

    def zakoncz(self, komunikat=""):
        """Oznacz zakończenie zadania analizy zamiany dyscyplin."""
        self.w_trakcie = False
        self.data_zakonczenia = timezone.now()
        self.ostatni_komunikat = komunikat or "Zakończono"
        self.save()


class StatusPrzegladarkaRecalc(models.Model):
    """
    Singleton model śledzący status przeliczania z poziomu przeglądarki ewaluacji.
    Przechowuje również punkty przed zmianą do obliczenia diff.
    """

    w_trakcie = models.BooleanField(
        default=False,
        verbose_name="W trakcie",
        help_text="Czy przeliczanie jest obecnie uruchomione",
    )
    task_id = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name="ID zadania Celery",
    )
    uczelnia = models.ForeignKey(
        Uczelnia,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Uczelnia",
    )
    data_rozpoczecia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data rozpoczęcia",
    )
    data_zakonczenia = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data zakończenia",
    )
    ostatni_komunikat = models.TextField(
        blank=True,
        default="",
        verbose_name="Ostatni komunikat",
    )
    # Punkty przed akcją - do obliczenia diff w podsumowaniu
    punkty_przed = models.JSONField(
        default=dict,
        verbose_name="Punkty przed zmianą",
        help_text="Dict: {discipline_id: points_value} przed akcją",
    )

    class Meta:
        app_label = "ewaluacja_optymalizacja"
        verbose_name = "Status przeliczania przeglądarki"
        verbose_name_plural = "Status przeliczania przeglądarki"

    def __str__(self):
        if self.w_trakcie:
            return f"W trakcie (task_id: {self.task_id})"
        elif self.data_zakonczenia:
            return f"Zakończono: {self.data_zakonczenia.strftime('%Y-%m-%d %H:%M:%S')}"
        return "Brak uruchomionych zadań"

    def save(self, *args, **kwargs):
        # Singleton - zawsze nadpisuj rekord o pk=1
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_or_create(cls):
        """Pobierz lub utwórz instancję singleton."""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj

    def rozpocznij(self, task_id, uczelnia, punkty_przed):
        """Oznacz rozpoczęcie przeliczania z przeglądarki."""
        self.w_trakcie = True
        self.task_id = task_id
        self.uczelnia = uczelnia
        self.data_rozpoczecia = timezone.now()
        self.data_zakonczenia = None
        self.punkty_przed = punkty_przed
        self.ostatni_komunikat = "Rozpoczęto przeliczanie ewaluacji"
        self.save()

    def zakoncz(self, komunikat=""):
        """Oznacz zakończenie przeliczania."""
        self.w_trakcie = False
        self.data_zakonczenia = timezone.now()
        self.ostatni_komunikat = komunikat or "Zakończono"
        self.save()
