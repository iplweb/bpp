from datetime import timedelta

from django.conf import settings
from django.db import models
from django.db.models import Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from bpp.models.autor import Autor
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from bpp.models.jednostka import Jednostka
from ewaluacja_common.przebiegi import PilnowanyPrzebiegMixin


def _domyslny_okres_pk():
    """Domyślny okres ewaluacji dla nowej metryki (okres zawierający bieżący
    rok). Kod generujący metryki zawsze podaje okres jawnie — ta wartość
    domyślna chroni tylko ręcznie tworzone wiersze (admin, testy)."""
    from ewaluacja_common.okres import okres_domyslny

    okres = okres_domyslny()
    return okres.pk if okres is not None else None


class MetrykaAutora(models.Model):
    """Model przechowujący metryki ewaluacyjne dla autora"""

    # Auto-indeks FK redundantny: pokrywa go unique_together
    # [autor, dyscyplina_naukowa]
    autor = models.ForeignKey(
        Autor, on_delete=models.CASCADE, related_name="metryki", db_index=False
    )

    # Auto-indeks FK redundantny: pokrywa go Meta.Index
    # [dyscyplina_naukowa, -srednia_za_slot_nazbierana]
    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa, on_delete=models.CASCADE, db_index=False
    )

    # Auto-indeks FK redundantny: pokrywa go Meta.Index
    # [jednostka, -srednia_za_slot_nazbierana]
    jednostka = models.ForeignKey(
        Jednostka,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="metryka_autora",
        help_text="Główna jednostka autora w okresie ewaluacji",
        db_index=False,
    )

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        help_text="Uczelnia, dla której policzono metrykę (multi-hosted)",
    )

    okres = models.ForeignKey(
        "ewaluacja_common.OkresEwaluacji",
        on_delete=models.PROTECT,
        default=_domyslny_okres_pk,
        related_name="metryki_autorow",
        help_text="Okres ewaluacji, za który policzono metrykę",
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

    # Dane za wszystkie prace autora w okresie ewaluacji
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
        unique_together = [("autor", "dyscyplina_naukowa", "uczelnia", "okres")]
        ordering = ["-srednia_za_slot_nazbierana", "autor__nazwisko", "autor__imiona"]
        indexes = [
            models.Index(fields=["-srednia_za_slot_nazbierana"]),
            models.Index(fields=["jednostka", "-srednia_za_slot_nazbierana"]),
            models.Index(fields=["dyscyplina_naukowa", "-srednia_za_slot_nazbierana"]),
            models.Index(fields=["uczelnia", "-srednia_za_slot_nazbierana"]),
        ]

    def __str__(self):
        return f"{self.autor} - {self.dyscyplina_naukowa.nazwa}"

    def save(self, *args, **kwargs):
        # Lata metryki muszą mieścić się w jej okresie — gdy nie (np. wiersz
        # utworzony bez jawnych lat), przyjmij granice okresu.
        if self.okres_id is not None and not (
            self.okres.zawiera(self.rok_min) and self.okres.zawiera(self.rok_max)
        ):
            self.rok_min = self.okres.rok_od
            self.rok_max = self.okres.rok_do

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

        # ``update_or_create`` (Django ≥ 4.2) zapisuje z ``update_fields`` =
        # klucze ``defaults`` — bez tego wyliczone wyżej pola zostałyby
        # w bazie ze starymi wartościami po ponownym generowaniu metryk.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {
                "srednia_za_slot_nazbierana",
                "srednia_za_slot_wszystkie",
                "procent_wykorzystania_slotow",
                "rok_min",
                "rok_max",
            }

        super().save(*args, **kwargs)

    def get_absolute_url(self):
        """URL szczegółów metryki (stabilne identyfikatory) z okresem metryki
        w adresie — otwiera dokładnie ten okres, niezależnie od okresu
        wybranego przez oglądającego."""
        from django.urls import reverse

        from ewaluacja_common.url_okres import reverse_w_okresie

        kwargs = {
            "autor_slug": self.autor.slug,
            "dyscyplina_kod": self.dyscyplina_naukowa.kod,
        }
        if self.okres_id is None:
            return reverse("ewaluacja_metryki:szczegoly", kwargs=kwargs)
        return reverse_w_okresie(
            "ewaluacja_metryki:szczegoly", self.okres, kwargs=kwargs
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


#: Po ilu sekundach od zlecenia generowanie metryk, które w ogóle nie ruszyło
#: (zadanie w tle nie zgłosiło startu), jest automatycznie anulowane.
#: Do zmiany ustawieniem ``EWALUACJA_METRYKI_LIMIT_STARTU_SEKUNDY``.
DOMYSLNY_LIMIT_STARTU_SEKUNDY = 5 * 60


def limit_startu_generowania():
    """Ile wolno czekać na start zleconego generowania metryk."""
    return timedelta(
        seconds=getattr(
            settings,
            "EWALUACJA_METRYKI_LIMIT_STARTU_SEKUNDY",
            DOMYSLNY_LIMIT_STARTU_SEKUNDY,
        )
    )


class StatusGenerowania(PilnowanyPrzebiegMixin, models.Model):
    """Model przechowujący informację o ostatnim generowaniu metryk (per uczelnia)."""

    # Strażnik przebiegów (``ewaluacja_common.przebiegi``): generowanie,
    # które wystartowało i padło w trakcie, zostaje anulowane.
    ZADANIA_PRZEBIEGU = (
        "ewaluacja_metryki.tasks.generuj_metryki_task_parallel",
        "ewaluacja_metryki.tasks.generuj_metryki_task",
        "ewaluacja_metryki.tasks.oblicz_metryki_dla_autora_task",
        "ewaluacja_metryki.tasks.finalizuj_generowanie_metryk",
    )
    NAZWA_PRZEBIEGU = "Generowanie metryk"

    #: Komunikat zapisywany przy ZLECENIU generowania (w żądaniu HTTP).
    #: Dopóki status go zawiera, zadanie w tle nie dało znaku życia —
    #: po starcie zadanie od razu podmienia go na ``KOMUNIKAT_WYSTARTOWALO``
    #: (``potwierdz_start``). To jedyny sygnał „zadanie ruszyło” przed
    #: pierwszym przetworzonym autorem (przeliczanie liczby N na dużej
    #: uczelni trwa), więc nie zmieniaj tego tekstu bez przejrzenia
    #: ``czeka_na_start``.
    KOMUNIKAT_ZLECONO = "Rozpoczęto generowanie metryk"
    KOMUNIKAT_WYSTARTOWALO = "Zadanie rozpoczęte — przygotowanie danych..."
    KOMUNIKAT_OBLICZANIE = "Obliczanie metryk autorów..."

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

    # Zostaje nullable: moduł ewaluacja_optymalizacja (poza zakresem federacji)
    # używa StatusGenerowania.get_or_create() bez argumentu w 3 miejscach
    # (views/unpinning_analysis.py:39,149, views/unpinning_list.py:137),
    # co rozwiązuje się do wiersza uczelnia=None. Pełny per-uczelnia status
    # należy do późniejszych prac federacyjnych.
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Uczelnia, której dotyczy ten status (multi-hosted)",
    )

    # Status jest per (uczelnia, okres): generowanie metryk jednego okresu nie
    # blokuje przeglądania ani generowania metryk innego okresu (metryki,
    # liczba N i udziały są przechowywane osobno dla każdego okresu).
    okres = models.ForeignKey(
        "ewaluacja_common.OkresEwaluacji",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
        help_text="Okres ewaluacji, którego dotyczy ten status",
    )

    class Meta:
        verbose_name = "Status generowania metryk"
        verbose_name_plural = "Status generowania metryk"
        constraints = [
            # Jeden status na (uczelnia, okres). NULL-e w zwykłym indeksie
            # unikalnym PostgreSQL są wzajemnie rozróżnialne — stąd COALESCE
            # i osobny indeks częściowy dla wierszy bez uczelni (dwa
            # równoległe ``get_or_create()`` bez argumentu tworzyły kiedyś
            # dwa takie wiersze → trwałe ``MultipleObjectsReturned``).
            models.UniqueConstraint(
                "uczelnia",
                Coalesce("okres", Value(0)),
                condition=models.Q(uczelnia__isnull=False),
                name="ewaluacja_metryki_status_uczelnia_okres",
            ),
            models.UniqueConstraint(
                Coalesce("okres", Value(0)),
                condition=models.Q(uczelnia__isnull=True),
                name="ewaluacja_metryki_status_jeden_wiersz_bez_uczelni",
            ),
        ]

    def __str__(self):
        if self.w_trakcie:
            return f"Generowanie w trakcie (przetworzono: {self.liczba_przetworzonych})"
        elif self.data_zakonczenia:
            return f"Ostatnie generowanie: {self.data_zakonczenia.strftime('%Y-%m-%d %H:%M:%S')}"
        else:
            return "Brak informacji o generowaniu"

    @classmethod
    def get_or_create(cls, uczelnia=None, okres=None):
        """Pobierz lub utwórz status generowania dla uczelni i okresu
        ewaluacji (obiekt albo pk)."""
        okres_id = getattr(okres, "pk", okres)
        obj, created = cls.objects.get_or_create(uczelnia=uczelnia, okres_id=okres_id)
        return obj

    @classmethod
    def aktualny(cls, uczelnia=None, okres=None):
        """Status do POKAZANIA albo do decyzji „czy generowanie trwa”:
        jak ``get_or_create``, ale przebieg, który nie wystartował w czasie
        albo padł w trakcie, zostaje przy okazji anulowany. Zadania w tle
        używają ``get_or_create`` — one niczego nie anulują."""
        status = cls.get_or_create(uczelnia=uczelnia, okres=okres)
        status.anuluj_jesli_nie_wystartowalo()
        status.anuluj_jesli_martwy()
        return status

    def _przebieg_juz_zakonczony(self):
        # ``task_id`` to zadanie-rodzic, które kończy się zaraz po rozesłaniu
        # zadań per autor — jego wynik nic nie mówi o przebiegu. Koniec
        # przebiegu zdejmuje ``w_trakcie`` sam (``zakoncz_generowanie``).
        return False

    def rozpocznij_generowanie(
        self, task_id="", liczba_do_przetworzenia=0, okres=None, komunikat=None
    ):
        """Oznacz rozpoczęcie generowania.

        Bez ``komunikat`` status jest „zlecony, czeka na start zadania”
        (patrz ``KOMUNIKAT_ZLECONO``); zadanie, które już pracuje, podaje
        własny komunikat."""
        if okres is not None:
            self.okres = okres
        self.data_rozpoczecia = timezone.now()
        self.data_zakonczenia = None
        self.w_trakcie = True
        self.liczba_przetworzonych = 0
        self.liczba_do_przetworzenia = liczba_do_przetworzenia
        self.liczba_bledow = 0
        self.ostatni_komunikat = komunikat or self.KOMUNIKAT_ZLECONO
        self.task_id = task_id or ""
        self.save()

    @property
    def czeka_na_start(self):
        """Generowanie zlecone, ale zadanie w tle nie dało znaku życia."""
        return (
            self.w_trakcie
            and self.liczba_przetworzonych == 0
            and self.ostatni_komunikat == self.KOMUNIKAT_ZLECONO
        )

    @property
    def anulowane(self):
        """Ostatni przebieg przerwano przed końcem (nie trwa i nigdy się nie
        zakończył). Zakończenie — także błędem — zawsze ustawia
        ``data_zakonczenia``, więc ten stan zostawia tylko anulowanie."""
        return bool(
            not self.w_trakcie
            and self.data_rozpoczecia is not None
            and self.data_zakonczenia is None
        )

    def oznacz_anulowane(self, komunikat):
        """Przerwij przebieg z komunikatem dla użytkownika (stan
        ``anulowane``: nie trwa, bez daty zakończenia)."""
        self.w_trakcie = False
        self.data_zakonczenia = None
        self.ostatni_komunikat = komunikat
        self.save(update_fields=["w_trakcie", "data_zakonczenia", "ostatni_komunikat"])

    def potwierdz_start(self, task_id):
        """Wołane przez zadanie w tle na samym początku: „ruszyłem”.

        Zwraca ``False``, gdy ten przebieg nie jest już aktualny (anulowany
        albo zastąpiony nowym zleceniem) — zadanie ma wtedy wyjść, niczego
        nie zmieniając. Warunkowy UPDATE, żeby nie ścigać się z anulowaniem.
        """
        zmienione = (
            type(self)
            .objects.filter(pk=self.pk, w_trakcie=True, task_id=task_id)
            .update(ostatni_komunikat=self.KOMUNIKAT_WYSTARTOWALO)
        )
        if zmienione:
            self.refresh_from_db()
        return bool(zmienione)

    def anuluj_jesli_nie_wystartowalo(self):
        """Anuluj przebieg, który od zlecenia nie ruszył przez
        ``limit_startu_generowania()`` (nie działa worker, kolejka stoi,
        zadanie przepadło). Zwraca ``True``, gdy anulowano.

        Przebieg, który dał znak życia (``potwierdz_start``) albo przetworzył
        choć jednego autora, NIE jest tu ruszany, choćby trwał długo.
        """
        if not self.czeka_na_start or self.data_rozpoczecia is None:
            return False
        limit = limit_startu_generowania()
        if timezone.now() - self.data_rozpoczecia < limit:
            return False

        from .celery_worker import czy_dziala_worker_celery

        # Raz na anulowany przebieg: po anulowaniu ``czeka_na_start`` jest
        # już fałszem, więc kolejne odpytania statusu tu nie dochodzą.
        worker_dziala = czy_dziala_worker_celery()

        minuty = max(1, round(limit.total_seconds() / 60))
        komunikat = (
            f"Generowanie metryk nie rozpoczęło się w ciągu {minuty} min "
            "od uruchomienia i zostało anulowane. "
        )
        if worker_dziala is False:
            komunikat += (
                "Usługa przetwarzania zadań w tle nie działa — zgłoś to "
                "administratorowi systemu. Dopóki nie zostanie uruchomiona, "
                "ponowne uruchomienie generowania nic nie da."
            )
        elif worker_dziala:
            komunikat += (
                "Usługa przetwarzania zadań w tle działa — spróbuj uruchomić "
                "generowanie ponownie."
            )
        else:
            komunikat += (
                "Nie udało się sprawdzić, czy usługa przetwarzania zadań "
                "w tle działa — spróbuj uruchomić generowanie ponownie, "
                "a jeśli sytuacja się powtórzy, zgłoś to administratorowi "
                "systemu."
            )

        # Warunkowy UPDATE: jeśli w międzyczasie zadanie jednak ruszyło
        # (zmieniło komunikat) albo zlecono nowy przebieg — nic nie robimy.
        zmienione = (
            type(self)
            .objects.filter(
                pk=self.pk,
                w_trakcie=True,
                liczba_przetworzonych=0,
                ostatni_komunikat=self.KOMUNIKAT_ZLECONO,
                task_id=self.task_id,
                data_rozpoczecia=self.data_rozpoczecia,
            )
            .update(w_trakcie=False, ostatni_komunikat=komunikat)
        )
        self.refresh_from_db()
        return bool(zmienione)

    def zakoncz_generowanie(self, liczba_bledow=0):
        """
        Oznacz zakończenie generowania.

        WAŻNE: NIE nadpisuje liczba_przetworzonych - używa wartości już zaktualizowanej atomowo przez taski.
        """
        self.data_zakonczenia = timezone.now()
        self.w_trakcie = False
        self.liczba_bledow = liczba_bledow
        self.ostatni_komunikat = (
            f"Zakończono generowanie. Przetworzono: {self.liczba_przetworzonych}, "
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
