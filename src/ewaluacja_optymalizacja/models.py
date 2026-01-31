from django.db import models
from django.urls import reverse
from django.utils import timezone

from bpp.models import Autor, Dyscyplina_Naukowa, Uczelnia
from bpp.models.fields import TupleField
from ewaluacja_common.models import Rodzaj_Autora


class OptimizationRun(models.Model):
    """
    Stores metadata about each optimization run.
    Tracks when optimization was performed and overall results.
    """

    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa, on_delete=models.CASCADE, verbose_name="Dyscyplina naukowa"
    )
    uczelnia = models.ForeignKey(
        Uczelnia,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Uczelnia",
        help_text="Uczelnia dla której wykonano optymalizację (opcjonalne dla pojedynczych dyscyplin)",
    )

    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Rozpoczęto")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Zakończono")

    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="running", verbose_name="Status"
    )

    # Overall statistics
    total_points = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=0,
        verbose_name="Suma punktów",
    )
    total_slots = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=0,
        verbose_name="Suma slotów",
    )
    total_publications = models.IntegerField(
        default=0, verbose_name="Liczba publikacji"
    )

    low_mono_count = models.IntegerField(
        default=0, verbose_name="Liczba nisko punktowanych monografii"
    )
    low_mono_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        verbose_name="Procent nisko punktowanych monografii",
    )

    validation_passed = models.BooleanField(
        default=True, verbose_name="Walidacja przeszła pomyślnie"
    )

    is_optimal = models.BooleanField(
        default=True,
        verbose_name="Rozwiązanie optymalne",
        help_text="False jeśli solver zwrócił rozwiązanie dopuszczalne ale nieoptymalne "
        "(np. z powodu timeout)",
    )

    optimality_gap = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Luka optymalizacyjna (%)",
        help_text="Różnica procentowa między znalezionym rozwiązaniem a teoretycznym "
        "maksimum. Wartość 0% oznacza rozwiązanie optymalne. Null jeśli niedostępne.",
    )

    best_bound = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        null=True,
        blank=True,
        verbose_name="Teoretyczna górna granica punktów",
        help_text="Teoretyczne maksimum punktów obliczone przez solver. "
        "Null jeśli niedostępne.",
    )

    # Additional metadata
    notes = models.TextField(blank=True, default="", verbose_name="Notatki")

    class Meta:
        verbose_name = "Wynik optymalizacji"
        verbose_name_plural = "Wyniki optymalizacji"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["-started_at"]),
            models.Index(fields=["dyscyplina_naukowa", "-started_at"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.dyscyplina_naukowa.nazwa} - {self.started_at.strftime('%Y-%m-%d %H:%M')}"

    def get_absolute_url(self):
        return reverse("ewaluacja_optymalizacja:run-detail", kwargs={"pk": self.pk})


class OptimizationAuthorResult(models.Model):
    """
    Stores per-author results within an optimization run.
    """

    optimization_run = models.ForeignKey(
        OptimizationRun,
        on_delete=models.CASCADE,
        related_name="author_results",
        verbose_name="Wynik optymalizacji",
    )
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, verbose_name="Autor")
    rodzaj_autora = models.ForeignKey(
        Rodzaj_Autora,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Rodzaj autora",
        help_text="Określa czy autor jest w liczbie N",
    )

    # Results
    total_points = models.DecimalField(
        max_digits=20, decimal_places=4, default=0, verbose_name="Suma punktów"
    )
    total_slots = models.DecimalField(
        max_digits=20, decimal_places=4, default=0, verbose_name="Suma slotów"
    )
    mono_slots = models.DecimalField(
        max_digits=20,
        decimal_places=4,
        default=0,
        verbose_name="Sloty monografii",
    )

    # Limits used for this author
    slot_limit_total = models.DecimalField(
        max_digits=20, decimal_places=4, verbose_name="Limit slotów (ogółem)"
    )
    slot_limit_mono = models.DecimalField(
        max_digits=20, decimal_places=4, verbose_name="Limit slotów (monografie)"
    )

    class Meta:
        verbose_name = "Wynik autora w optymalizacji"
        verbose_name_plural = "Wyniki autorów w optymalizacji"
        ordering = ["optimization_run", "autor__nazwisko", "autor__imiona"]
        unique_together = [("optimization_run", "autor")]
        indexes = [
            models.Index(fields=["optimization_run", "autor"]),
            models.Index(fields=["autor"]),
        ]

    def __str__(self):
        return f"{self.autor} - {self.optimization_run}"


class OptimizationPublication(models.Model):
    """
    Stores individual publications selected for each author in an optimization run.
    """

    KIND_CHOICES = [
        ("article", "Artykuł"),
        ("monography", "Monografia"),
    ]

    author_result = models.ForeignKey(
        OptimizationAuthorResult,
        on_delete=models.CASCADE,
        related_name="publications",
        verbose_name="Wynik autora",
    )

    rekord_id = TupleField(
        models.IntegerField(),
        size=2,
        db_index=True,
        verbose_name="ID rekordu (content_type_id, object_id)",
    )

    kind = models.CharField(max_length=20, choices=KIND_CHOICES, verbose_name="Rodzaj")

    points = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="Punkty")
    slots = models.DecimalField(max_digits=20, decimal_places=4, verbose_name="Sloty")

    is_low_mono = models.BooleanField(
        default=False, verbose_name="Nisko punktowana monografia (< 200 pkt)"
    )

    author_count = models.IntegerField(
        default=1,
        verbose_name="Liczba autorów z przypiętymi dyscyplinami",
    )

    class Meta:
        verbose_name = "Publikacja w optymalizacji"
        verbose_name_plural = "Publikacje w optymalizacji"
        ordering = ["author_result", "-points"]
        indexes = [
            models.Index(fields=["author_result"]),
            models.Index(fields=["rekord_id"]),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} - {self.points} pkt - {self.author_result.autor}"

    @property
    def efficiency(self):
        """Points per slot ratio"""
        return float(self.points) / float(self.slots) if self.slots > 0 else 0


class UnpinningOpportunity(models.Model):
    """
    Stores analysis results for potential unpinning opportunities.

    Identifies multi-author works where:
    - Autor A: work did NOT enter their collected works (not in prace_nazbierane)
              AND has FULL slots (slot_nazbierany >= 80-90% of slot_maksymalny)
    - Autor B: work DID enter their collected works (in prace_nazbierane)
              AND has unfilled slots (can take more)
    - Unpinning from Autor A allows Autor B to claim higher share
    """

    # Metadata
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Data utworzenia analizy"
    )

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        verbose_name="Uczelnia",
    )

    dyscyplina_naukowa = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.CASCADE,
        verbose_name="Dyscyplina naukowa",
    )

    # Work information
    rekord_id = TupleField(
        models.IntegerField(),
        size=2,
        db_index=True,
        verbose_name="ID rekordu (content_type_id, object_id)",
    )

    rekord_tytul = models.TextField(
        verbose_name="Tytuł pracy", help_text="Cached title for display"
    )

    # Author to unpin (work did NOT enter, has FULL slots)
    autor_could_benefit = models.ForeignKey(
        Autor,
        on_delete=models.CASCADE,
        related_name="unpinning_could_benefit",
        verbose_name="Autor któremu należy odpiąć (ma pełne sloty)",
    )

    metryka_could_benefit = models.ForeignKey(
        "ewaluacja_metryki.MetrykaAutora",
        on_delete=models.CASCADE,
        related_name="unpinning_could_benefit",
        verbose_name="Metryka autora (któremu należy odpiąć)",
    )

    slot_in_work = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Slot autora A w tej pracy",
        help_text="Slot value for autor_could_benefit (to unpin) in this work",
    )

    slots_missing = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Ile autor B może jeszcze wziąć",
        help_text="slot_maksymalny - slot_nazbierany for autor_currently_using (who benefits)",
    )

    # Author who will benefit (work DID enter, has unfilled slots)
    autor_currently_using = models.ForeignKey(
        Autor,
        on_delete=models.CASCADE,
        related_name="unpinning_currently_using",
        verbose_name="Autor który skorzysta (ma miejsce na więcej)",
    )

    metryka_currently_using = models.ForeignKey(
        "ewaluacja_metryki.MetrykaAutora",
        on_delete=models.CASCADE,
        related_name="unpinning_currently_using",
        verbose_name="Metryka autora (który skorzysta)",
    )

    # Analysis result
    makes_sense = models.BooleanField(
        default=False,
        verbose_name="Czy odpięcie ma sens",
        help_text="True if unpinning increases points for autor B",
    )

    # Różnice po odpięciu - Autor A (któremu odpinamy)
    punkty_roznica_a = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name="Różnica punktów A (surowa)",
        help_text="Surowa różnica punktów A: punkty_after - punkty_before (zazwyczaj 0 lub ujemne)",
    )

    sloty_roznica_a = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name="Różnica slotów A",
        help_text="O ile zmienią się sloty autora A po odpięciu (zazwyczaj 0 lub ujemne)",
    )

    # Różnice po odpięciu - Autor B (który skorzysta)
    punkty_roznica_b = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name="Różnica punktów B (surowa)",
        help_text="Surowa różnica punktów B: punkty_after - punkty_before (zazwyczaj dodatnie)",
    )

    sloty_roznica_b = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name="Różnica slotów B",
        help_text="O ile wzrosną sloty autora B po odpięciu (może być ujemna)",
    )

    # Rzeczywiste wartości używane do obliczenia makes_sense
    punkty_strata_a = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name="Rzeczywista strata punktów A",
        help_text=(
            "Rzeczywista strata punktów A (zawsze >= 0). "
            "Jeśli praca nie była w prace_nazbierane, strata = 0 (A nie wykazywał tej pracy). "
            "Jeśli praca była wykazana, strata = abs(punkty_roznica_a)."
        ),
    )

    punkty_zysk_b = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=0,
        verbose_name="Rzeczywisty zysk punktów B",
        help_text="Rzeczywisty zysk punktów B (zawsze >= 0). Równe punkty_roznica_b jeśli dodatnie, inaczej 0.",
    )

    praca_byla_wykazana_dla_a = models.BooleanField(
        default=False,
        verbose_name="Czy praca była wykazana dla A",
        help_text="True jeśli praca była w prace_nazbierane autora A (wtedy odpięcie spowoduje rzeczywistą stratę punktów)",
    )

    class Meta:
        verbose_name = "Możliwość odpięcia"
        verbose_name_plural = "Możliwości odpięcia"
        ordering = ["-makes_sense", "-slots_missing", "rekord_tytul"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["uczelnia", "dyscyplina_naukowa"]),
            models.Index(fields=["makes_sense"]),
            models.Index(fields=["-slots_missing"]),
        ]

    def __str__(self):
        return (
            f"{self.rekord_tytul[:50]}... - "
            f"{self.autor_could_benefit} (brakuje {self.slots_missing}) <- "
            f"{self.autor_currently_using}"
        )

    @property
    def rekord(self):
        """Get the Rekord object for this publication"""
        # Check if we have a cached rekord from the view
        if hasattr(self, "_cached_rekord") and self._cached_rekord is not None:
            return self._cached_rekord

        # Otherwise fetch from database
        from bpp.models import Rekord

        return Rekord.objects.get(pk=self.rekord_id)


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


class DisciplineSwapOpportunity(models.Model):
    """
    Przechowuje wyniki analizy możliwości zamiany dyscyplin.

    Identyfikuje publikacje gdzie:
    - Autor ma przypisane dwie dyscypliny (dyscyplina + subdyscyplina) w Autor_Dyscyplina
    - Zamiana dyscypliny z głównej na subdyscyplinę (lub odwrotnie) zwiększa punktację
    """

    # Metadane
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Data utworzenia analizy"
    )

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        verbose_name="Uczelnia",
    )

    # Informacje o publikacji
    rekord_id = TupleField(
        models.IntegerField(),
        size=2,
        db_index=True,
        verbose_name="ID rekordu (content_type_id, object_id)",
    )

    rekord_tytul = models.TextField(
        verbose_name="Tytuł pracy", help_text="Cache tytułu do wyświetlania"
    )

    rekord_rok = models.PositiveSmallIntegerField(
        verbose_name="Rok publikacji",
        null=True,
        blank=True,
    )

    rekord_typ = models.CharField(
        max_length=50,
        verbose_name="Typ publikacji",
        help_text="Ciagle/Zwarte",
        default="",
    )

    # Autor do zamiany dyscypliny
    autor = models.ForeignKey(
        Autor,
        on_delete=models.CASCADE,
        related_name="discipline_swap_opportunities",
        verbose_name="Autor do zamiany dyscypliny",
    )

    # Dyscypliny - obecna i docelowa
    current_discipline = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.CASCADE,
        related_name="swap_from",
        verbose_name="Obecna dyscyplina",
    )

    target_discipline = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa",
        on_delete=models.CASCADE,
        related_name="swap_to",
        verbose_name="Docelowa dyscyplina",
    )

    # Punktacja przed i po zamianie
    points_before = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Punkty przed zamianą",
        help_text="Całkowita punktacja publikacji przed zamianą dyscypliny",
    )

    points_after = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Punkty po zamianie",
        help_text="Całkowita punktacja publikacji po zamianie dyscypliny",
    )

    point_improvement = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name="Poprawa punktów",
        help_text="points_after - points_before",
    )

    # Dla Wydawnictwo_Ciagle: czy docelowa dyscyplina pasuje do dyscyplin źródła
    zrodlo_discipline_match = models.BooleanField(
        default=False,
        verbose_name="Dyscyplina pasuje do źródła",
        help_text=(
            "True jeśli docelowa dyscyplina jest w Dyscyplina_Zrodla "
            "dla tego źródła i roku"
        ),
    )

    # Wynik analizy
    makes_sense = models.BooleanField(
        default=False,
        verbose_name="Czy zamiana ma sens",
        help_text="True jeśli zamiana zwiększa całkowitą punktację",
    )

    class Meta:
        verbose_name = "Możliwość zamiany dyscypliny"
        verbose_name_plural = "Możliwości zamiany dyscyplin"
        ordering = ["-makes_sense", "-point_improvement", "rekord_tytul"]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["uczelnia"]),
            models.Index(fields=["makes_sense"]),
            models.Index(fields=["-point_improvement"]),
            models.Index(fields=["current_discipline"]),
            models.Index(fields=["target_discipline"]),
            models.Index(fields=["zrodlo_discipline_match"]),
            models.Index(fields=["rekord_rok"]),
        ]

    def __str__(self):
        return (
            f"{self.rekord_tytul[:50]}... - "
            f"{self.autor}: {self.current_discipline} -> {self.target_discipline} "
            f"(+{self.point_improvement})"
        )

    @property
    def rekord(self):
        """Pobierz obiekt Rekord dla tej publikacji."""
        if hasattr(self, "_cached_rekord") and self._cached_rekord is not None:
            return self._cached_rekord
        from bpp.models import Rekord

        return Rekord.objects.get(pk=self.rekord_id)


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
