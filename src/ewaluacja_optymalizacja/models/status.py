"""Singleton modele śledzące status długo-działających zadań Celery.

Każdy z modeli ``Status*`` przechowuje stan jednego rodzaju zadania
optymalizacji/analizy. Używane do zapewnienia, że tylko jedno zadanie
danego typu może być uruchomione naraz oraz do prezentacji statusu w UI.
"""

from django.db import models
from django.utils import timezone

from bpp.models import Uczelnia
from django_bpp.db_locks import advisory_lock_id

from .bariera import zajmij_slot_pod_bariera, zwolnij_slot


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

    # Bariera bazodanowa (patrz models/bariera.py) — druga, niezależna od
    # Redisa warstwa ochrony przed równoległym optimize_and_unpin_task po
    # clear_locks na worker_ready. Stały literał klucza — pilnuje go test
    # test_advisory_lock_id.py; NIE licz go przez hash() (solony
    # PYTHONHASHSEED). Próg zombie = time_limit zadania (3600s) + 15 min.
    BARIERA_LOCK_ID = advisory_lock_id(
        "ewaluacja_optymalizacja.optimize_and_unpin_task.slot"
    )
    BARIERA_STALE_AFTER = 3600 + 15 * 60

    @classmethod
    def sprobuj_zajac_slot(cls, task_id, logger=None):
        """Bariera na WEJŚCIU do zadania. True = działaj, False = wycofaj się."""
        return zajmij_slot_pod_bariera(
            cls, cls.BARIERA_LOCK_ID, task_id, cls.BARIERA_STALE_AFTER, logger
        )


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


class StatusOdpinaniaWszystkich(models.Model):
    """Singleton statusu zadania ``unpin_all_sensible_task``.

    Ten model powstał głównie po to, by ``unpin_all_sensible_task`` — obok
    ``optimize_and_unpin_task`` jedno z dwóch najgroźniejszych zadań masowo
    odpinających przypięcia całej uczelni — miał trwały stan „w_trakcie +
    timestamp", na którym może stanąć bariera bazodanowa niezależna od Redisa
    (patrz ``models/bariera.py``). Wcześniej to zadanie polegało wyłącznie na
    locku ``celery_singleton`` (Redis), kasowanym przez ``clear_locks`` na
    ``worker_ready`` przy rolling restarcie dowolnego workera.

    W przeciwieństwie do ``StatusOptymalizacjiZOdpinaniem`` slot jest tu
    zdejmowany przez samo zadanie (``zwolnij_slot`` w ``finally``), bo widok
    ``unpin_all_sensible`` nie prowadzi własnego stanu statusu.
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
        verbose_name = "Status odpinania wszystkich sensownych"
        verbose_name_plural = "Status odpinania wszystkich sensownych"

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

    # Bariera bazodanowa — patrz komentarz przy StatusOptymalizacjiZOdpinaniem.
    # Próg zombie = time_limit zadania (7200s) + 15 min.
    BARIERA_LOCK_ID = advisory_lock_id(
        "ewaluacja_optymalizacja.unpin_all_sensible_task.slot"
    )
    BARIERA_STALE_AFTER = 7200 + 15 * 60

    @classmethod
    def sprobuj_zajac_slot(cls, task_id, logger=None):
        """Bariera na WEJŚCIU do zadania. True = działaj, False = wycofaj się."""
        return zajmij_slot_pod_bariera(
            cls, cls.BARIERA_LOCK_ID, task_id, cls.BARIERA_STALE_AFTER, logger
        )

    @classmethod
    def zwolnij_slot(cls, task_id):
        """Zwolnij slot po zakończeniu zadania (tylko gdy wciąż nasz)."""
        zwolnij_slot(cls, task_id)
