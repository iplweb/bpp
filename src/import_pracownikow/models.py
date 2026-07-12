# Create your models here.
from datetime import date

from django import forms
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DataError, models, transaction
from django.db.models import Count, JSONField, Q
from django.db.models.expressions import RawSQL
from django.urls import reverse
from django.utils import timezone
from liveops.models import LiveOperation

from bpp.models import (
    Autor,
    Autor_Jednostka,
    Funkcja_Autora,
    Grupa_Pracownicza,
    Jednostka,
    Tytul,
    Wymiar_Etatu,
)
from import_common.exceptions import BPPDatabaseError
from import_common.forms import ExcelDateField
from import_common.models import ImportRowMixin
from import_pracownikow.pewnosc import (
    CONFIDENCE_CHOICES,
    STATUS_BRAK,
    STATUS_CHOICES,
    STATUS_DISPLAY,
    STATUS_RECZNY,
    STATUS_TWARDY,
    STATUS_WIELU,
    STATUS_ZGADYWANIE,
)


class JednostkaForm(forms.Form):
    nazwa_jednostki = forms.CharField(max_length=10240)
    wydział = forms.CharField(max_length=500, required=False)


class AutorForm(forms.Form):
    nazwisko = forms.CharField(max_length=200)
    imię = forms.CharField(max_length=200)

    numer = forms.IntegerField(required=False)
    orcid = forms.CharField(max_length=19, required=False)
    tytuł_stopień = forms.CharField(max_length=200, required=False)
    pbn_uuid = forms.CharField(required=False, max_length=24, min_length=24)
    bpp_id = forms.IntegerField(required=False)

    stanowisko = forms.CharField(max_length=200, required=False)
    grupa_pracownicza = forms.CharField(max_length=200, required=False)
    data_zatrudnienia = ExcelDateField(required=False)
    data_końca_zatrudnienia = ExcelDateField(required=False)
    podstawowe_miejsce_pracy = forms.BooleanField(required=False)
    wymiar_etatu = forms.CharField(max_length=200, required=False)
    # email tolerancyjny: CharField (nie EmailField), max_length=128 =
    # Autor.email.max_length — dłuższy adres wywaliłby Autor.objects.create
    # przez nieprzechwycony DataError. Miękkie czyszczenie/porównywarka = Plan 4.
    email = forms.CharField(max_length=128, required=False)
    stopień_służbowy = forms.CharField(max_length=200, required=False)
    stanowisko_dydaktyczne = forms.CharField(max_length=200, required=False)


class ImportPracownikow(LiveOperation):
    STAN_UTWORZONY = "utworzony"
    STAN_ZMAPOWANY = "zmapowany"
    STAN_PRZEANALIZOWANY = "przeanalizowany"
    STAN_ZATWIERDZONY = "zatwierdzony"
    # Struktura (jednostki [+ tytuły]) zapisana, osoby JESZCZE nie — faza osób
    # (Krok 2). Wymuszamy „najpierw struktura, potem osoby": w podglądzie
    # (przeanalizowany) import osób jest zablokowany i szczegóły autorów ukryte,
    # dopóki jednostki nie zostaną rozstrzygnięte i zapisane (Krok 1).
    STAN_STRUKTURA_ZINTEGROWANA = "struktura_zintegrowana"
    STAN_ZINTEGROWANY = "zintegrowany"
    STAN_PORZUCONY = "porzucony"
    STAN_CHOICES = [
        (STAN_UTWORZONY, "utworzony"),
        (STAN_ZMAPOWANY, "zmapowany (kolumny określone)"),
        (STAN_PRZEANALIZOWANY, "przeanalizowany (dry-run gotowy)"),
        (STAN_ZATWIERDZONY, "zatwierdzony do zapisu"),
        (STAN_STRUKTURA_ZINTEGROWANA, "struktura zapisana (osoby czekają)"),
        (STAN_ZINTEGROWANY, "zintegrowany"),
        (STAN_PORZUCONY, "porzucony"),
    ]

    # Zakres integracji (co „Zapisz do bazy" faktycznie tworzy):
    # - PELNY: struktura + osoby (domyślne, pełny import),
    # - JEDNOSTKI: same jednostki (bez tytułów i bez osób),
    # - STRUKTURA: jednostki + tytuły (bez osób).
    ZAKRES_PELNY = "pelny"
    ZAKRES_JEDNOSTKI = "jednostki"
    ZAKRES_STRUKTURA = "struktura"
    ZAKRES_CHOICES = [
        (ZAKRES_PELNY, "pełny import (struktura + osoby)"),
        (ZAKRES_JEDNOSTKI, "tylko jednostki"),
        (ZAKRES_STRUKTURA, "jednostki + tytuły + stopnie + stanowiska (bez osób)"),
    ]

    plik_xls = models.FileField(upload_to="protected/import_pracownikow/")
    stan = models.CharField(max_length=32, choices=STAN_CHOICES, default=STAN_UTWORZONY)
    mapowanie_kolumn = models.JSONField(default=dict, blank=True)
    tworz_brakujace_jednostki = models.BooleanField(
        "Twórz brakujące jednostki",
        default=True,
        help_text="Gdy zaznaczone, jednostki nieobecne w bazie (i bez bliskiego "
        "dopasowania) trafiają na ekran weryfikacji do utworzenia. Gdy "
        "odznaczone — wiersze bez dopasowanej jednostki są pomijane.",
    )
    tworz_brakujace_tytuly = models.BooleanField(
        "Twórz brakujące tytuły",
        default=True,
        help_text="Gdy zaznaczone, tytuły nieobecne w bazie (i bez bliskiego "
        "dopasowania) trafiają na ekran weryfikacji do utworzenia. Gdy "
        "odznaczone — wiersze z niedopasowanym tytułem zostają bez tytułu.",
    )
    tworz_brakujace_stopnie = models.BooleanField(
        "Twórz brakujące stopnie służbowe",
        default=True,
        help_text="Gdy zaznaczone, stopnie służbowe nieobecne w bazie (i bez "
        "bliskiego dopasowania) trafiają na ekran weryfikacji do utworzenia. "
        "Gdy odznaczone — wiersze z niedopasowanym stopniem zostają bez stopnia.",
    )
    tworz_brakujace_stanowiska = models.BooleanField(
        "Twórz brakujące stanowiska dydaktyczne",
        default=True,
        help_text="Gdy zaznaczone, stanowiska dydaktyczne nieobecne w bazie (i "
        "bez bliskiego dopasowania) trafiają na ekran weryfikacji do utworzenia. "
        "Gdy odznaczone — wiersze z niedopasowanym stanowiskiem zostają bez "
        "stanowiska.",
    )
    data_zmian_personalnych = models.DateField(
        "Data zmian personalnych",
        null=True,
        blank=True,
        help_text="Data, na którą obowiązuje ten wykaz zmian personalnych. "
        "Zostanie użyta jako data początku pracy przy DOPISYWANIU autora do "
        "jednostki (nowe powiązanie), gdy wiersz w pliku nie podaje własnej "
        "daty zatrudnienia. Nie nadpisuje dat z pliku ani dat istniejących "
        "powiązań.",
    )
    przepnij_wszystkie_prace = models.BooleanField(
        "Zaznacz wszystkie prace do przepięcia na nowe jednostki",
        default=False,
        # HTML (crispy renderuje help_text przez |safe) — świadomie łamiemy tekst
        # na linie <br> i podbijamy CAPS-ami <strong>, bo to opcja groźna na
        # dojrzałej bazie. Ten sam string dosłownie w migracji 0021 (inaczej
        # makemigrations wygeneruje AlterField).
        help_text="Gdy zaznaczone, <strong>WSZYSTKIE prace autorów</strong> "
        "zostaną domyślnie oznaczone do przepięcia na jednostki z pliku.<br>"
        "<strong>ZAZNACZ</strong> przy imporcie struktury autorów do "
        "<strong>ŚWIEŻEJ</strong> bazy (np. tuż po imporcie do PBN).<br>"
        "Na <strong>DOJRZAŁEJ</strong> bazie produkcyjnej <strong>NA PEWNO "
        "zostaw ODZNACZONE</strong> — przepięłoby to historyczne afiliacje.<br>"
        "Można korygować per wiersz przed zapisem osób.",
    )
    zakres_integracji = models.CharField(
        "Zakres integracji",
        max_length=20,
        choices=ZAKRES_CHOICES,
        default=ZAKRES_PELNY,
        help_text="Co „Zapisz do bazy” faktycznie tworzy: pełny import "
        "(struktura + osoby), same jednostki, albo jednostki + tytuły + stopnie "
        "+ stanowiska (bez osób). Ustawiane przez przycisk zatwierdzenia na "
        "hubie.",
    )

    stages = ["Wczytywanie", "Integracja"]

    @property
    def faza_struktury(self):
        """Krok 1: podgląd po analizie — rozstrzygamy jednostki (i tytuły) oraz
        zapisujemy strukturę. Import osób i szczegóły autorów są tu ZABLOKOWANE."""
        return self.stan == self.STAN_PRZEANALIZOWANY

    @property
    def faza_osob(self):
        """Krok 2: struktura zapisana — dopiero teraz odsłaniamy i pozwalamy
        edytować dopasowania autorów, przepięcia i odpięcia oraz zaimportować
        osoby (pełny commit)."""
        return self.stan == self.STAN_STRUKTURA_ZINTEGROWANA

    @property
    def edytowalny_podglad(self):
        """Stany, w których wolno EDYTOWAĆ decyzje o osobach (dopasowanie autora,
        przepięcie, odpięcie) — podgląd (Krok 1) oraz faza osób (Krok 2). W
        podglądzie edycja jest technicznie dozwolona, ale hub jej nie odsłania
        (najpierw struktura); pełną kontrolę operator dostaje w fazie osób."""
        return self.stan in (
            self.STAN_PRZEANALIZOWANY,
            self.STAN_STRUKTURA_ZINTEGROWANA,
        )

    def get_success_url(self):
        """URL, na który ``liveops.js`` przenosi po zakończonym runie
        (FINISHED_OK). ``progress.py`` woła to w ``transaction.on_commit``, więc
        ``self.stan`` jest już finalny (analyze/integrate ustawiają go na tej
        samej instancji ``self``).

        Auto-przejście: po analizie (dry-run) → hub „szczegóły importu"
        (Krok 1); po zapisaniu struktury (``struktura_zintegrowana``) → hub
        (Krok 2, import osób) z query-paramem ``?zapisano=struktura``, który
        na fresh-GET wyzwala jednorazowy flash (``messages`` nie działa z
        celery ``on_commit``, więc komunikat ustawia dopiero widok huba).
        Po PEŁNEJ integracji osób (``zintegrowany``) zwracamy ``None`` —
        zostajemy na panelu wyniku liveops z podsumowaniem
        (zintegrowano/utworzono/pominięto) i linkiem do logu zmian. Zastępuje
        martwy inline-``<script>`` z ``import_pracownikow_result.html``, który
        nigdy się nie wykonywał: liveops wstrzykuje wynik przez
        ``DOMParser``+``replaceWith``, a tak wstawiony ``<script>`` przeglądarka
        oznacza „already started"."""
        if self.stan == self.STAN_PRZEANALIZOWANY:
            return reverse("import_pracownikow:przeglad", kwargs={"pk": self.pk})
        if self.stan == self.STAN_STRUKTURA_ZINTEGROWANA:
            return (
                reverse("import_pracownikow:przeglad", kwargs={"pk": self.pk})
                + "?zapisano=struktura"
            )
        return None

    def run(self, p):
        # liveops.runner._handle_error zapisuje traceback WYŁĄCZNIE do bazy (pole
        # `traceback`) — bez śladu na konsoli workera i bez zgłoszenia do
        # rollbara. Owijamy właściwy przebieg, żeby błąd był WIDOCZNY: surowy
        # traceback na stderr (konsola celery/run-site) + rollbar (konwencja
        # bg-tasków w projekcie), po czym re-raise — liveops i tak zapisze
        # traceback do bazy i pokaże błąd w UI/adminie.
        try:
            self._wykonaj(p)
        except Exception:
            import sys
            import traceback as _traceback

            import rollbar

            _traceback.print_exc()
            rollbar.report_exc_info(sys.exc_info())
            raise

    def _wykonaj(self, p):
        if self.stan == self.STAN_ZMAPOWANY:
            from import_pracownikow.pipeline.analyze import analizuj

            # Etap „Wczytywanie" (analiza/dry-run). `p.stage()` ustawia
            # stage_states[name]=active→done, dzięki czemu klocki etapów w
            # liveops podświetlają się na żywo (bez tego zostają „pending").
            with p.stage("Wczytywanie"):
                analizuj(self, p)
        elif self.stan == self.STAN_ZATWIERDZONY:
            from import_pracownikow.pipeline.integrate import integruj

            # Etap „Integracja" (zapis do bazy).
            with p.stage("Integracja"):
                integruj(self, p)
        else:
            p.log(f"run() w nieoczekiwanym stanie: {self.stan!r} — pomijam")

    def on_restart(self):
        # kasujemy wiersze przy (ponownej) analizie: świeży upload czeka w
        # utworzony (bez wierszy), ponowna analiza cofa do zmapowany.
        if self.stan in (self.STAN_UTWORZONY, self.STAN_ZMAPOWANY):
            self.importpracownikowrow_set.all().delete()
            # Odpięcia (§9) materializuje faza analizy — przy cofnięciu do
            # zmapowany kasujemy je razem z wierszami, żeby ponowna analiza
            # nie zduplikowała zbioru.
            self.odpiecia.all().delete()
            # Po strukturalnym imporcie (zakres jednostki / struktura) ponowna
            # analiza wraca do pełnego zakresu — inaczej kolejne „Zapisz do
            # bazy" po re-analizie po cichu pominęłoby osoby. Zapisujemy
            # od razu (własny update_fields), bo wołający — RestartView oraz
            # MapowanieView — składają save z listą pól nieobejmującą tego pola.
            if self.zakres_integracji != self.ZAKRES_PELNY:
                self.zakres_integracji = self.ZAKRES_PELNY
                self.save(update_fields=["zakres_integracji"])

    # Pola operacji liveops zerowane przed (po)ponownym enqueue. Zwierciadło
    # ``RestartView.post`` (liveops inline'uje ten reset, nie wystawia go jako
    # metody) — jedyne miejsce w naszym kodzie, gdzie ta lista żyje, więc
    # ``MapowanieView`` (FormView, nie może dziedziczyć po RestartView) nie
    # trzyma własnej kopii i nie zdryfuje.
    _POLA_LIVEOPS_RESET = (
        "finished_on",
        "started_on",
        "finished_successfully",
        "cancelled",
        "cancel_requested",
        "traceback",
        "result_context",
        "current_stage",
        "stage_states",
        "log",
        "percent",
        "log_seq",
    )

    def reset_liveops_state(self):
        """Zeruje pola stanu operacji liveops (jak ``RestartView.post``), tak
        by kolejny ``enqueue()`` wystartował z czystym przebiegiem — inaczej
        ``cancel_requested=True`` po anulowanym runie natychmiast ubiłby nowy.
        NIE zapisuje (caller składa ``update_fields``) i NIE woła ``enqueue``.
        Zwraca listę ustawionych pól — do doklejenia w ``save(update_fields=)``."""
        self.finished_on = None
        self.started_on = None
        self.finished_successfully = False
        self.cancelled = False
        self.cancel_requested = False
        self.traceback = None
        self.result_context = None
        self.current_stage = -1
        self.stage_states = {}
        self.log = []
        self.percent = 0
        self.log_seq = 0
        return list(self._POLA_LIVEOPS_RESET)

    def waliduj_liczbe_arkuszy(self):
        """Egzekwuje „jeden arkusz = jeden import": otwiera plik i podnosi
        ``BadNoOfSheetsException``, gdy ma > 1 arkusz z danymi. Dla widoków
        ruszających analizę z pominięciem ekranu mapowania (RestartAnalizaView) —
        ``naglowki_i_probka`` robi tę samą kontrolę na ścieżce mapowania."""
        from import_common.sources import otworz_zrodlo
        from import_pracownikow.mapping import (
            MIN_POINTS,
            TRY_NAMES,
            sprawdz_pojedynczy_arkusz,
        )

        zrodlo = otworz_zrodlo(
            self.plik_xls.path, try_names=TRY_NAMES, min_points=MIN_POINTS
        )
        sprawdz_pojedynczy_arkusz(zrodlo)

    def naglowki_i_probka(self, limit=10):
        """Synchronicznie (bez liveops) czyta znormalizowane nagłówki i do
        ``limit`` wierszy próbki — na ekran mapowania. Nagłówki = klucze
        wiersza bez kluczy lokalizacyjnych. Używa ``TRY_NAMES``/``MIN_POINTS``
        z ``mapping`` (rozpoznaje przemianowane kolumny — patrz T2). Może
        rzucić ``HeaderNotFoundException`` (plik bez rozpoznawalnego
        nagłówka) — widok (T8) łapie to i pokazuje komunikat, nie 500."""
        from import_common.sources import otworz_zrodlo
        from import_pracownikow.mapping import (
            MIN_POINTS,
            TRY_NAMES,
            sprawdz_pojedynczy_arkusz,
        )

        zrodlo = otworz_zrodlo(
            self.plik_xls.path, try_names=TRY_NAMES, min_points=MIN_POINTS
        )
        # „Jeden arkusz = jeden import" — plik wieloarkuszowy odrzucamy zanim
        # użytkownik zacznie mapować (mieszałby dwa rozłączne zbiory). Widok
        # łapie BadNoOfSheetsException i pokazuje komunikat.
        sprawdz_pojedynczy_arkusz(zrodlo)
        probka = []
        naglowki = []
        for i, wiersz in enumerate(zrodlo.data()):
            if i == 0:
                naglowki = [
                    k
                    for k in wiersz.keys()
                    if k not in ("__xls_loc_sheet__", "__xls_loc_row__")
                ]
            if i >= limit:
                break
            probka.append(wiersz)
        return naglowki, probka

    @property
    def zmiany_potrzebne_set(self):
        return self.importpracownikowrow_set.filter(zmiany_potrzebne=True)

    def get_details_set(self):
        return (
            self.importpracownikowrow_set.all()
            .annotate(
                nr_wiersza=RawSQL("(dane_z_xls->>'__xls_loc_row__')::int+1", []),
                nr_arkusza=RawSQL("(dane_z_xls->>'__xls_loc_sheet__')::int+1", []),
            )
            .order_by("nr_arkusza", "nr_wiersza")
            .select_related(
                "autor",
                "autor__aktualna_jednostka",
                "jednostka",
                "jednostka__wydzial",
                "autor__tytul",
                "grupa_pracownicza",
                "funkcja_autora",
                "wymiar_etatu",
                # Porównywarka „plik vs baza" (§12) czyta FK bazy — bez N+1.
                "autor__stopien_sluzbowy",
                "autor_jednostka__stanowisko",
            )
        )

    def autorzy_spoza_pliku_set(self, uczelnia=None, today=None):
        """Powiązania Autor+Jednostka do odpięcia: pary ``(autor, jednostka)``
        OBECNE w bazie, ale NIEOBECNE w tym imporcie.

        Porównanie po parach ``(autor_id, jednostka_id)`` z wierszy (znane
        nawet gdy ``autor_jednostka`` jest NULL — odroczone AJ / statusy
        brak/wielu), z jawnym odfiltrowaniem NULL-i. NIE po pk
        ``Autor_Jednostka``: subquery z NULL-em daje SQL ``NOT IN (…, NULL)``
        → pusty zbiór (regresja §9). Kryteria wykluczeń: jednostka zarządzana
        automatycznie, nie-obca, powiązanie aktywne, autor ma aktualną
        jednostkę. „Nie-obca” działa dwuwarstwowo: wykluczamy autorów, których
        aktualna (podstawowa) jednostka to obca, ORAZ pojedyncze powiązania
        wskazujące NA obcą jednostkę (np. zagraniczna współafiliacja publikacji
        u autora zatrudnionego w realnej jednostce) — takich afiliacji nie
        proponujemy do odpięcia, nawet gdy autora nie ma w pliku.
        """
        if today is None:
            today = timezone.now().date()

        pary_z_pliku = self.pary_z_pliku()

        qry = (
            Autor_Jednostka.objects.exclude(autor__aktualna_jednostka=None)
            .exclude(jednostka__zarzadzaj_automatycznie=False)
            .exclude(zakonczyl_prace__lte=today)
        )

        if uczelnia is not None and uczelnia.obca_jednostka_id is not None:
            qry = qry.exclude(
                autor__aktualna_jednostka_id=uczelnia.obca_jednostka_id
            ).exclude(jednostka_id=uczelnia.obca_jednostka_id)

        if pary_z_pliku:
            wyklucz = Q()
            for autor_id, jednostka_id in pary_z_pliku:
                wyklucz |= Q(autor_id=autor_id, jednostka_id=jednostka_id)
            qry = qry.exclude(wyklucz)

        return qry

    def pary_z_pliku(self):
        """Zbiór par ``(autor_id, jednostka_id)`` OBECNYCH w wierszach importu
        (autor i jednostka ustawione) — „para z pliku”, tj. potwierdzony etat.

        Wspólne źródło dla guardu „para z pliku” w przepięciach (F1) i dla
        definicji „spoza pliku” w odpięciach (§9). Semantyka identyczna z
        per-wierszowym ``.filter(autor_id=, jednostka_id=).exists()`` guardu G1.
        """
        return set(
            self.importpracownikowrow_set.filter(
                autor__isnull=False, jednostka__isnull=False
            )
            .values_list("autor_id", "jednostka_id")
            .distinct()
        )

    def liczniki_ludzi_z_xls(self):
        """Rozkład wierszy importu po statusie dopasowania autora
        (``confidence``) — dane kafelka „Ludzie z XLS" na hubie.

        Zwraca ``{"twardy","zgadywanie","wielu","brak"}``. **Koalescencja
        ``confidence=None`` → ``"brak"``**: pole jest ``null=True`` i stare
        wiersze (sprzed migracji 0013) mają ``None``; bez tego suma kafelka nie
        równałaby się liczbie wierszy. Jeden ``values('confidence')`` +
        ``Count`` — bez N+1."""
        liczniki = {
            STATUS_TWARDY: 0,
            STATUS_RECZNY: 0,
            STATUS_ZGADYWANIE: 0,
            STATUS_WIELU: 0,
            STATUS_BRAK: 0,
        }
        for wiersz in self.importpracownikowrow_set.values("confidence").annotate(
            n=Count("id")
        ):
            klucz = wiersz["confidence"] or STATUS_BRAK
            liczniki[klucz] = liczniki.get(klucz, 0) + wiersz["n"]
        return liczniki

    @staticmethod
    def _liczniki_decyzji(queryset, tryb_brak, tryb_zgadywanie):
        """Rozkład NIEROZSTRZYGNIĘTYCH decyzji (jednostek/tytułów) po ``tryb``:
        ``brak`` → ``do_utworzenia``, ``zgadywanie`` → ``do_sprawdzenia``.
        Wspólny rdzeń ``liczniki_jednostek``/``liczniki_tytulow`` (identyczny
        kształt, różnią się tylko modelem i stałymi trybu)."""
        liczniki = {"do_utworzenia": 0, "do_sprawdzenia": 0}
        for wiersz in queryset.values("tryb").annotate(n=Count("id")):
            if wiersz["tryb"] == tryb_brak:
                liczniki["do_utworzenia"] += wiersz["n"]
            elif wiersz["tryb"] == tryb_zgadywanie:
                liczniki["do_sprawdzenia"] += wiersz["n"]
        return liczniki

    def liczniki_jednostek(self):
        """``{"do_utworzenia","do_sprawdzenia"}`` z nierozstrzygniętych decyzji
        o jednostkach (``utworzona__isnull=True``) — dane kafelka „Jednostki"."""
        return self._liczniki_decyzji(
            self.jednostki_do_decyzji.filter(utworzona__isnull=True),
            ImportPracownikowJednostka.TRYB_BRAK,
            ImportPracownikowJednostka.TRYB_ZGADYWANIE,
        )

    def liczniki_tytulow(self):
        """``{"do_utworzenia","do_sprawdzenia"}`` z nierozstrzygniętych decyzji
        o tytułach (``utworzony__isnull=True``) — dane kafelka „Tytuły"."""
        return self._liczniki_decyzji(
            self.tytuly_do_decyzji.filter(utworzony__isnull=True),
            ImportPracownikowTytul.TRYB_BRAK,
            ImportPracownikowTytul.TRYB_ZGADYWANIE,
        )

    @property
    def ma_tytuly(self):
        """Czy import w ogóle dotyka tytułów (kolumna tytułu w pliku) — decyduje
        o pokazaniu afordancji „Zobacz tytuły" na hubie (item 2). Prawda, gdy są
        decyzje o tytułach ALBO któryś wiersz ma dopasowany tytuł."""
        return (
            self.tytuly_do_decyzji.exists()
            or self.importpracownikowrow_set.filter(tytul__isnull=False).exists()
        )

    @property
    def tytuly_wymagaja_rozstrzygniecia(self):
        """Czy są tytuły z pliku, które import osób UTWORZYŁBY/USTAWIŁ, a które
        NIE zostały jeszcze zmaterializowane (``utworzony=None``) i nie są
        świadomie pominięte (``decyzja != pomin``).

        Bramka item 3: import osób (zakres pełny) nie może po cichu tworzyć
        tytułów — najpierw trzeba je rozstrzygnąć/utworzyć. „Zapisz tylko
        jednostki" odkłada tytuły → po tej ścieżce ta właściwość jest prawdą i
        import osób pozostaje zablokowany, dopóki tytuły nie trafią do bazy
        (przycisk „Utwórz brakujące tytuły" w Kroku 2 albo „Zapisz jednostki +
        tytuły" w Kroku 1). ``pomin`` liczymy jako rozstrzygnięte (świadoma
        decyzja: nie ustawiaj tytułu)."""
        return (
            self.tytuly_do_decyzji.filter(utworzony__isnull=True)
            .exclude(decyzja=ImportPracownikowTytul.DECYZJA_POMIN)
            .exists()
        )

    @property
    def stopnie_wymagaja_rozstrzygniecia(self):
        """Mirror ``tytuly_wymagaja_rozstrzygniecia`` — bramka: import osób
        (zakres pełny) nie może po cichu tworzyć stopni służbowych. ``pomin``
        liczymy jako rozstrzygnięte."""
        return (
            self.stopnie_do_decyzji.filter(utworzony__isnull=True)
            .exclude(decyzja=ImportPracownikowStopien.DECYZJA_POMIN)
            .exists()
        )

    @property
    def stanowiska_wymagaja_rozstrzygniecia(self):
        """Mirror ``tytuly_wymagaja_rozstrzygniecia`` dla stanowisk
        dydaktycznych (pole rozstrzygnięcia: ``utworzone``)."""
        return (
            self.stanowiska_do_decyzji.filter(utworzone__isnull=True)
            .exclude(decyzja=ImportPracownikowStanowisko.DECYZJA_POMIN)
            .exists()
        )

    def liczniki_stopni(self):
        """``{"do_utworzenia","do_sprawdzenia"}`` z nierozstrzygniętych decyzji
        o stopniach służbowych (``utworzony__isnull=True``)."""
        return self._liczniki_decyzji(
            self.stopnie_do_decyzji.filter(utworzony__isnull=True),
            ImportPracownikowStopien.TRYB_BRAK,
            ImportPracownikowStopien.TRYB_ZGADYWANIE,
        )

    def liczniki_stanowisk(self):
        """``{"do_utworzenia","do_sprawdzenia"}`` z nierozstrzygniętych decyzji
        o stanowiskach dydaktycznych (``utworzone__isnull=True``)."""
        return self._liczniki_decyzji(
            self.stanowiska_do_decyzji.filter(utworzone__isnull=True),
            ImportPracownikowStanowisko.TRYB_BRAK,
            ImportPracownikowStanowisko.TRYB_ZGADYWANIE,
        )


class ImportPracownikowRow(ImportRowMixin, models.Model):
    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,  # related_name="row_set"
    )
    dane_z_xls = JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)
    dane_znormalizowane = JSONField(null=True, blank=True, encoder=DjangoJSONEncoder)

    autor = models.ForeignKey(Autor, on_delete=models.CASCADE, null=True, blank=True)
    jednostka = models.ForeignKey(
        Jednostka, on_delete=models.CASCADE, null=True, blank=True
    )
    jednostka_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
    )
    zrodlo_jednostki = models.ForeignKey(
        "ImportPracownikowJednostka",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiersze",
        help_text="Decyzja o źródłowej nazwie jednostki (współdzielona przez "
        "wiersze o tej samej nazwie). Wypełniona, gdy jednostka wymaga "
        "rozstrzygnięcia (utworzenie / mapowanie / auto-dopasowanie).",
    )
    autor_jednostka = models.ForeignKey(
        Autor_Jednostka, on_delete=models.CASCADE, null=True, blank=True
    )

    podstawowe_miejsce_pracy = models.BooleanField(null=True, blank=True, default=None)
    funkcja_autora = models.ForeignKey(
        Funkcja_Autora, on_delete=models.CASCADE, null=True, blank=True
    )
    grupa_pracownicza = models.ForeignKey(
        Grupa_Pracownicza, on_delete=models.CASCADE, null=True, blank=True
    )
    wymiar_etatu = models.ForeignKey(
        Wymiar_Etatu, on_delete=models.CASCADE, null=True, blank=True
    )
    tytul = models.ForeignKey(Tytul, on_delete=models.SET_NULL, null=True)
    tytul_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
    )
    zrodlo_tytulu = models.ForeignKey(
        "ImportPracownikowTytul",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiersze_tytul",
        help_text="Decyzja o źródłowym tytule (współdzielona przez wiersze o "
        "tej samej nazwie). Wypełniona, gdy tytuł wymaga rozstrzygnięcia "
        "(utworzenie / mapowanie / auto-dopasowanie).",
    )
    stopien = models.ForeignKey(
        "bpp.StopienSluzbowy", on_delete=models.SET_NULL, null=True, blank=True
    )
    stopien_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
    )
    zrodlo_stopnia = models.ForeignKey(
        "ImportPracownikowStopien",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiersze_stopien",
        help_text="Decyzja o źródłowym stopniu służbowym (współdzielona przez "
        "wiersze o tej samej nazwie). Wypełniona, gdy stopień wymaga "
        "rozstrzygnięcia (utworzenie / mapowanie / auto-dopasowanie).",
    )
    stanowisko_dydaktyczne = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    stanowisko_dydaktyczne_status = models.CharField(  # noqa: DJ001
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
    )
    zrodlo_stanowiska_dydaktycznego = models.ForeignKey(
        "ImportPracownikowStanowisko",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wiersze_stanowisko",
        help_text="Decyzja o źródłowym stanowisku dydaktycznym (współdzielona "
        "przez wiersze o tej samej nazwie). Wypełniona, gdy stanowisko wymaga "
        "rozstrzygnięcia (utworzenie / mapowanie / auto-dopasowanie).",
    )

    zmiany_potrzebne = models.BooleanField()

    diff_do_utworzenia = models.JSONField(default=dict, blank=True)
    pominiety_bo_nieaktualny = models.BooleanField(default=False)

    confidence = models.CharField(  # noqa: DJ001
        max_length=20, choices=CONFIDENCE_CHOICES, null=True, blank=True
    )
    korekta_uzytkownika = models.JSONField(default=dict, blank=True)
    wybrany_kandydat = models.ForeignKey(
        "bpp.Autor",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    utworz_nowego = models.BooleanField(default=False)
    przepnij_prace = models.BooleanField(default=False)

    log_zmian = JSONField(encoder=DjangoJSONEncoder, null=True, blank=True)

    # Snapshot stanów pól (POLA_ROZNIC) zamrożony przy integracji — po niej baza
    # = plik, więc live porównanie dałoby „zgodne"; filtr czyta stabilną wartość.
    stany_pol_snapshot = JSONField(null=True, blank=True)

    MAPPING_DANE_NA_AUTOR = [
        ("numer", "system_kadrowy_id"),
        ("orcid", "orcid"),
        ("pbn_uuid", "pbn_uid_id"),
    ]

    @property
    def dane_bardziej_znormalizowane(self):
        """parsuje daty w dwóch polach, bo JSON w PostgreSQL to raz, a JSONDecoder
        w Django nie ma czegos takiego jak dekoder JSON do pól JSON"""
        for fld in ["data_zatrudnienia", "data_końca_zatrudnienia"]:
            if self.dane_znormalizowane.get(fld):
                v = self.dane_znormalizowane.get(fld)
                if v is None or isinstance(v, date) or v == "":
                    continue
                self.dane_znormalizowane[fld] = date.fromisoformat(v)

        return self.dane_znormalizowane

    @property
    def confidence_badge(self):
        """(klasa Foundation label, ikona Foundation-Icons, etykieta) dla
        ``confidence`` — do szablonu podglądu. ``None`` (stare wiersze) →
        bezpieczny neutralny badge."""
        return STATUS_DISPLAY.get(
            self.confidence, ("secondary", "fi-minus", self.confidence or "—")
        )

    @staticmethod
    def _porownaj_email(plik, baza):
        """Trójka porównania e-maila: ``{plik, baza, rozne}``. ``rozne`` = obie
        strony NIEPUSTE i różne (case-insensitive) — pole puste w pliku LUB w
        bazie NIE jest różnicą (e-mail to no-overwrite: import nie nadpisuje
        istniejącego). Pustej bazy nie podświetlamy, ale import i tak jej NIE
        uzupełnia — e-mail trafia do bazy WYŁĄCZNIE przy tworzeniu nowego autora
        (``Autor.objects.create``); ``MAPPING_DANE_NA_AUTOR`` nie zawiera
        ``email``, więc istniejący autor z pustym e-mailem tak czy inaczej go nie
        dostaje z tego importu."""
        p = str(plik or "").strip()
        b = str(baza or "").strip()
        rozne = bool(p) and bool(b) and p.casefold() != b.casefold()
        return {"plik": p, "baza": b, "rozne": rozne}

    @staticmethod
    def _porownaj_fk(plik_str, baza_obj, plik_id):
        """Trójka porównania pola FK (stopień/stanowisko): ``{plik, baza,
        rozne}``. Porównanie SEMANTYCZNE po ID — skrót w pliku vs nazwa w bazie
        NIE może decydować o różnicy. ``rozne`` = plik WSKAZUJE FK (``plik_id``
        ustawione) i baza ma inny (lub żaden) FK — overwrite-if-different
        (Plan 3), inaczej niż no-overwrite e-maila. ``plik`` = wartość z pliku
        (skrót); ``baza`` = ``str`` FK z bazy."""
        baza_id = baza_obj.pk if baza_obj else None
        return {
            "plik": str(plik_str or "").strip(),
            "baza": str(baza_obj) if baza_obj else "",
            "rozne": plik_id is not None and baza_id != plik_id,
        }

    def porownaj_z_baza(self):
        """Porównanie „plik vs baza" dla e-maila, stopnia służbowego,
        stanowiska dydaktycznego, tytułu naukowego i funkcji w jednostce
        (§12). CZYSTY odczyt — NIC nie zapisuje ani nie nadpisuje. E-mail:
        no-overwrite (porównanie stringów). Stopień/stanowisko/tytuł/funkcja:
        overwrite-if-different, porównywane SEMANTYCZNIE po FK (skrót w pliku vs
        nazwa w bazie dałyby fałszywe „różne"); FK z pliku rozwiązuje Plan 3 na
        ``self.stopien`` / ``self.stanowisko_dydaktyczne``. Strona bazy: FK autora
        / powiązania; stanowisko i funkcja z ``autor_jednostka`` (aktualizowanego
        przez ten wiersz). Dla wiersza bez autora/AJ strona bazy jest pusta."""
        dane = self.dane_znormalizowane or {}
        autor = self.autor
        aj = self.autor_jednostka
        stopien_baza = (
            autor.stopien_sluzbowy if autor and autor.stopien_sluzbowy_id else None
        )
        stanowisko_baza = aj.stanowisko if aj and aj.stanowisko_id else None
        tytul_baza = autor.tytul if autor and autor.tytul_id else None
        funkcja_baza = aj.funkcja if aj and aj.funkcja_id else None
        return {
            "email": self._porownaj_email(
                dane.get("email"), autor.email if autor else ""
            ),
            "stopien": self._porownaj_fk(
                dane.get("stopień_służbowy"), stopien_baza, self.stopien_id
            ),
            "stanowisko": self._porownaj_fk(
                dane.get("stanowisko_dydaktyczne"),
                stanowisko_baza,
                self.stanowisko_dydaktyczne_id,
            ),
            # tytuł / funkcja: gdy brak autora/AJ → plik_id=None → rozne=False
            # (niuans: bez dopasowania nie podświetlamy różnicy).
            "tytul": self._porownaj_fk(
                dane.get("tytuł_stopień"),
                tytul_baza,
                self.tytul_id if autor else None,
            ),
            "funkcja": self._porownaj_fk(
                dane.get("stanowisko"),
                funkcja_baza,
                self.funkcja_autora_id if aj else None,
            ),
        }

    def stany_pol(self):
        """Stan każdego pola różnic: ``{klucz: "zmienione"|"zgodne"|"brak"}``.
        Zwraca zamrożony ``stany_pol_snapshot`` gdy istnieje (po integracji baza
        = plik, więc live dałoby „zgodne"), inaczej live wyliczenie z
        ``POLA_ROZNIC`` (jednostka / email / tytuł / stopień / funkcja /
        stanowisko). Zasila filtr stanu pól i atrybuty ``data-diff-*``."""
        if self.stany_pol_snapshot is not None:
            return self.stany_pol_snapshot
        from import_pracownikow.roznice import POLA_ROZNIC

        return {klucz: ekstraktor(self) for klucz, _et, ekstraktor in POLA_ROZNIC}

    @property
    def ostrzezenie_email(self):
        """Komunikat o odrzuconym adresie e-mail (z
        ``dane_znormalizowane["ostrzeżenia"]``) albo ``None`` — renderowany w
        komórce e-mail porównywarki jako ``label alert``."""
        for o in (self.dane_znormalizowane or {}).get("ostrzeżenia") or []:
            if "e-mail" in o.lower():
                return o
        return None

    def _check_autor_needs_update(self, dane):
        """Sprawdza czy autor wymaga aktualizacji."""
        a = self.autor
        for klucz_danych, atrybut_autora in self.MAPPING_DANE_NA_AUTOR:
            v = dane.get(klucz_danych)
            if v is not None and str(v) != "" and getattr(a, atrybut_autora) != v:
                return True
        # Import USTAWIA tytuł, nigdy go nie kasuje (spójne z ``_integrate_autor``,
        # który ustawia ``a.tytul_id`` tylko przy ``self.tytul_id is not None``).
        # Bez tego guardu utytułowany autor z pustym/niedopasowanym tytułem dawał
        # ``zmiany_potrzebne=True`` + puste ``integrate()``.
        if self.tytul_id is not None and self.tytul_id != a.tytul_id:
            return True
        # Stopień służbowy — overwrite-if-different (mirror tytuł, spec §11.2).
        if self.stopien_id is not None and self.stopien_id != a.stopien_sluzbowy_id:
            return True
        return False

    def _check_autor_jednostka_needs_update(self, dane):
        """Sprawdza czy powiązanie autor-jednostka wymaga aktualizacji."""
        aj = self.autor_jednostka
        if aj is None:
            # Wiersz z odroczoną jednostką (jednostka=None) nie ma AJ do
            # zaktualizowania — nie ma też czego ustawić jako podstawowe miejsce
            # pracy. Guard przed dostępem do atrybutów None (checki niżej łapią
            # None dopiero przez short-circuit dane.get(...), a #4 primary nie).
            return False
        checks = [
            # #4: rozpoczęcie stemplujemy TYLKO gdy puste (data z pliku / importu)
            # — integracja potrzebna, gdy plik niesie datę, a AJ jej nie ma.
            dane.get("data_zatrudnienia") is not None and aj.rozpoczal_prace is None,
            dane.get("data_końca_zatrudnienia") is not None
            and aj.zakonczyl_prace != dane["data_końca_zatrudnienia"],
            self.funkcja_autora is not None and aj.funkcja != self.funkcja_autora,
            self.grupa_pracownicza is not None
            and aj.grupa_pracownicza != self.grupa_pracownicza,
            self.wymiar_etatu is not None and aj.wymiar_etatu != self.wymiar_etatu,
            self.podstawowe_miejsce_pracy is not None
            and self.podstawowe_miejsce_pracy != aj.podstawowe_miejsce_pracy,
            # #4: domyślnie import ustawia jednostkę autora jako podstawowe miejsce
            # pracy — integracja potrzebna, gdy AJ jeszcze nim nie jest, a plik nie
            # mówi jawnie „Podstawowe miejsce pracy"=NIE.
            self.podstawowe_miejsce_pracy is not False
            and not aj.podstawowe_miejsce_pracy,
            # Stanowisko dydaktyczne — overwrite-if-different (mirror funkcja).
            self.stanowisko_dydaktyczne_id is not None
            and aj.stanowisko_id != self.stanowisko_dydaktyczne_id,
        ]
        return any(checks)

    def check_if_integration_needed(self):
        dane = self.dane_bardziej_znormalizowane
        return self._check_autor_needs_update(
            dane
        ) or self._check_autor_jednostka_needs_update(dane)

    def _integrate_autor(self):
        dane = self.dane_znormalizowane
        a = self.autor

        def _spr(klucz_danych, atrybut_autora):
            v = dane.get(klucz_danych)
            if v is None or (str(v) == ""):
                return

            if getattr(a, atrybut_autora) != v:
                return True

        for klucz_danych, atrybut_autora in self.MAPPING_DANE_NA_AUTOR:
            if _spr(klucz_danych, atrybut_autora):
                self.log_zmian["autor"].append(
                    f"{atrybut_autora} -> {dane.get(klucz_danych)}"
                )
                setattr(a, atrybut_autora, dane.get(klucz_danych))

        self._ustaw_tytul_i_stopien_autora(a)

        try:
            a.save()
        except DataError as e:
            raise BPPDatabaseError(self.dane_z_xls, self, f"DataError {e}") from e

    def _ustaw_tytul_i_stopien_autora(self, a):
        """Ustawia tytuł naukowy i stopień służbowy na autorze
        (overwrite-if-different, spec §11.2) i loguje zmiany. Import USTAWIA,
        nigdy nie kasuje (guard is-not-None — spójne z ``_check_autor_needs_update``,
        które te same pola liczy do ``zmiany_potrzebne``)."""
        if self.tytul_id is not None and a.tytul_id != self.tytul_id:
            a.tytul_id = self.tytul_id
            self.log_zmian["autor"].append(
                f"tytuł naukowy -> {self.tytul.skrot if self.tytul_id else 'brak'}"
            )
        if self.stopien_id is not None and a.stopien_sluzbowy_id != self.stopien_id:
            a.stopien_sluzbowy_id = self.stopien_id
            self.log_zmian["autor"].append(
                "stopień służbowy -> "
                f"{self.stopien.skrot if self.stopien_id else 'brak'}"
            )

    def _integruj_daty_aj(self, aj, dane):
        """Ustawia daty zatrudnienia na powiązaniu z danych wiersza.

        Polityka „no-overwrite" (#4): ``rozpoczal_prace`` stemplujemy TYLKO gdy
        puste — nie nadpisujemy istniejącej daty (decyzja usera #4; dawniej data
        z pliku nadpisywała istniejącą wartość). Priorytet przy stemplowaniu
        pustej daty: data zatrudnienia z pliku → globalna „data zmian
        personalnych" z importu (item 8) → dzień importu (dziś). Item 8 dotyczy
        właśnie dopisywania autora do jednostki (nowe AJ, pusta data), więc jest
        spójny z no-overwrite."""
        if aj.rozpoczal_prace is None:
            nowa_data = (
                dane.get("data_zatrudnienia")
                or self.parent.data_zmian_personalnych
                or timezone.localdate()
            )
            aj.rozpoczal_prace = nowa_data
            self.log_zmian["autor_jednostka"].append(
                f"data rozpoczęcia pracy na {nowa_data}"
            )

        data_konca = dane.get("data_końca_zatrudnienia")
        if data_konca is not None and aj.zakonczyl_prace != data_konca:
            aj.zakonczyl_prace = data_konca
            self.log_zmian["autor_jednostka"].append(
                f"data końca zatrudnienia na {data_konca}"
            )

    def _integrate_autor_jednostka(self):
        aj = self.autor_jednostka
        dane = self.dane_bardziej_znormalizowane

        self._integruj_daty_aj(aj, dane)

        if self.funkcja_autora is not None and aj.funkcja != self.funkcja_autora:
            aj.funkcja = self.funkcja_autora
            self.log_zmian["autor_jednostka"].append(
                f"funkcja na {self.funkcja_autora}"
            )

        if (
            self.stanowisko_dydaktyczne_id is not None
            and aj.stanowisko_id != self.stanowisko_dydaktyczne_id
        ):
            aj.stanowisko_id = self.stanowisko_dydaktyczne_id
            self.log_zmian["autor_jednostka"].append(
                f"stanowisko dydaktyczne na {self.stanowisko_dydaktyczne}"
            )

        if (
            self.grupa_pracownicza is not None
            and aj.grupa_pracownicza != self.grupa_pracownicza
        ):
            aj.grupa_pracownicza = self.grupa_pracownicza
            self.log_zmian["autor_jednostka"].append(
                f"grupa_pracownicza na {self.grupa_pracownicza}"
            )

        if self.wymiar_etatu is not None and aj.wymiar_etatu != self.wymiar_etatu:
            aj.wymiar_etatu = self.wymiar_etatu
            self.log_zmian["autor_jednostka"].append(
                f"wymiar_etatu na {self.wymiar_etatu}"
            )

        # #4: domyślnie KAŻDY zaimportowany wiersz ustawia swoją jednostkę jako
        # podstawowe miejsce pracy autora — ustaw_podstawowe_miejsce_pracy()
        # (+ trigger) zdejmuje flagę z pozostałych AJ tego autora. Kolumna
        # „Podstawowe miejsce pracy"=NIE w pliku (self.podstawowe_miejsce_pracy is
        # False) wyłącza to dla danego wiersza; brak kolumny (None) = domyślnie TAK.
        if self.podstawowe_miejsce_pracy is False:
            if aj.podstawowe_miejsce_pracy is not False:
                aj.podstawowe_miejsce_pracy = False
                self.log_zmian["autor_jednostka"].append(
                    "podstawowe_miejsce_pracy -> nie"
                )
        elif not aj.podstawowe_miejsce_pracy:
            aj.ustaw_podstawowe_miejsce_pracy()
            self.log_zmian["autor_jednostka"].append("podstawowe_miejsce_pracy -> tak")

        # Autor_Jednostka.clean() waliduje rozpoczal < zakonczyl, ale Model.save()
        # NIE woła clean() (uwaga reviewera #4). Bronimy niezmiennika tutaj — na
        # jedynej ścieżce zapisu integracji — żeby odwrócony zakres dat z XLS nie
        # trafił do bazy. Regułę „koniec < dziś" celowo pomijamy: import może nieść
        # przyszłe daty końca zatrudnienia (to reguła admina, nie importu).
        if (
            aj.rozpoczal_prace is not None
            and aj.zakonczyl_prace is not None
            and aj.rozpoczal_prace >= aj.zakonczyl_prace
        ):
            raise BPPDatabaseError(
                self.dane_z_xls,
                self,
                f"data rozpoczęcia pracy ({aj.rozpoczal_prace}) jest późniejsza "
                f"lub równa dacie zakończenia ({aj.zakonczyl_prace})",
            )

        aj.save()

    @transaction.atomic
    def integrate(self):
        assert self.zmiany_potrzebne
        # Zamroź stan pól ZANIM zmienimy bazę (potem live = „zgodne").
        self.stany_pol_snapshot = self.stany_pol()
        self.log_zmian = {"autor": [], "autor_jednostka": []}
        self._integrate_autor()
        self._integrate_autor_jednostka()
        self.save()

    def sformatowany_log_zmian(self):
        # Renderuje WSZYSTKIE klucze audytu (#513 F1 / #508 M4). Faza integracji
        # zapisuje obok `autor`/`autor_jednostka` także `utworzono` (m.in. „nowy
        # autor: …"), `przepiecie` (raport przepięcia prac) i
        # `przepiecie_pominiete` — bez ich renderu utworzenie autora i
        # przepięcie dorobku były niewidoczne w jedynym widoku log_zmian po
        # integracji. `.get()` bo starsze rekordy mogą nie mieć niektórych kluczy.
        if self.log_zmian is None:
            return
        log = self.log_zmian

        if log.get("autor"):
            yield "Zmiany obiektu Autor: " + ", ".join(log["autor"])

        if log.get("autor_jednostka"):
            yield "Zmiany obiektu Autor_Jednostka: " + ", ".join(log["autor_jednostka"])

        if log.get("utworzono"):
            yield "Utworzono: " + ", ".join(log["utworzono"])

        przepiecie = log.get("przepiecie")
        if przepiecie:
            yield (
                f"Przepięto prace: {przepiecie.get('prace_ciagle', 0)} ciągłych, "
                f"{przepiecie.get('prace_zwarte', 0)} zwartych "
                f"z „{przepiecie.get('z', '?')}” do „{przepiecie.get('do', '?')}”."
            )

        if log.get("przepiecie_pominiete"):
            yield "Przepięcie pominięte: " + log["przepiecie_pominiete"]

    @property
    def log_zmian_lista(self):
        """Zmaterializowana lista opisów zmian (``sformatowany_log_zmian``) — do
        ekranu audytu (item 6). Pusta lista = wiersz nic nie zmienił (nie
        pokazujemy go w audycie)."""
        return list(self.sformatowany_log_zmian())


class ProfilMapowania(models.Model):
    """Zapisywalne mapowanie nagłówków pliku → pola systemowe, do reużycia
    przy powtarzalnych plikach (ta sama uczelnia co kwartał). BPP jest
    single-tenant per instalacja, więc profile są globalne dla instancji."""

    nazwa = models.CharField(max_length=200, unique=True)
    mapowanie = models.JSONField(default=dict)
    ostatnio_uzyty = models.DateTimeField(null=True, blank=True)
    utworzony_przez = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        verbose_name = "profil mapowania importu pracowników"
        verbose_name_plural = "profile mapowania importu pracowników"
        ordering = ["nazwa"]

    def __str__(self):
        return self.nazwa


class ImportPracownikowRowKandydat(models.Model):
    """Kandydat na dopasowanie autora dla wiersza o statusie ``wielu``.

    Materializuje listę z ``znajdz_kandydatow_autora`` (pewność, powód strategii,
    liczba publikacji), żeby dropdown w podglądzie mógł pokazać userowi pełny
    kontekst. Wzorzec: ``importer_publikacji.ImportedAuthor_Candidate``.
    """

    row = models.ForeignKey(
        ImportPracownikowRow,
        on_delete=models.CASCADE,
        related_name="kandydaci",
        verbose_name="wiersz importu",
    )
    autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.CASCADE,
        verbose_name="autor BPP",
    )
    pewnosc = models.FloatField("pewność")
    powod = models.CharField("powód dopasowania", max_length=32)
    publikacji_count = models.PositiveIntegerField("liczba publikacji", default=0)

    class Meta:
        verbose_name = "kandydat na autora (import pracowników)"
        verbose_name_plural = "kandydaci na autora (import pracowników)"
        ordering = ["-pewnosc"]

    def __str__(self):
        return f"{self.autor} ({self.pewnosc})"

    @classmethod
    def zapisz_dla(cls, row, kandydaci):
        """Nadpisuje kandydatów wiersza listą ``KandydatAutora`` (z
        ``znajdz_kandydatow_autora``): kasuje poprzednich i tworzy nowych
        (``bulk_create``). Jedno źródło mapowania ``k.* → pola modelu`` dla
        analizy (T7) oraz re-matchu inline (T10). Przekaż ``[]``, by tylko
        wyczyścić kandydatów (np. wiersz po korekcie zszedł z ``wielu``)."""
        row.kandydaci.all().delete()
        cls.objects.bulk_create(
            [
                cls(
                    row=row,
                    autor=k.autor,
                    pewnosc=k.pewnosc,
                    powod=k.powod,
                    publikacji_count=k.publikacji,
                )
                for k in kandydaci
            ]
        )


class ImportPracownikowOdpiecie(models.Model):
    """Materializowana decyzja o odpięciu jednego powiązania Autor+Jednostka
    spoza pliku (§9 D3).

    Powstaje w fazie analizy dla każdego powiązania z
    ``autorzy_spoza_pliku_set`` (domyślnie ODZNACZONE); user zaznacza w
    podglądzie; faza commit kończy zatrudnienie dla ``zaznaczone=True`` i
    ustawia ``wykonane=True``. ``autor_jednostka`` wskazuje ISTNIEJĄCE
    powiązanie (realne, z pk) — do zakończenia. Decyzja jest persystowana (nie
    liczona dynamicznie), żeby przeżyła drift bazy między podglądem a commitem.
    """

    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,
        related_name="odpiecia",
        verbose_name="import pracowników",
    )
    autor_jednostka = models.ForeignKey(
        "bpp.Autor_Jednostka",
        on_delete=models.CASCADE,
        verbose_name="powiązanie autor-jednostka",
    )
    zaznaczone = models.BooleanField(default=False)
    wykonane = models.BooleanField(default=False)

    class Meta:
        verbose_name = "odpięcie autora spoza pliku (import pracowników)"
        verbose_name_plural = "odpięcia autorów spoza pliku (import pracowników)"
        ordering = ["autor_jednostka__autor__nazwisko"]

    def __str__(self):
        return f"odpięcie {self.autor_jednostka} (zaznaczone={self.zaznaczone})"


class ImportPracownikowJednostka(models.Model):
    """Decyzja o jednej UNIKALNEJ (znormalizowanej) nazwie jednostki z pliku,
    której nie da się dopasować dokładnie.

    Deduplikowana po nazwie (jednostki są współdzielone przez wielu pracowników,
    więc jedna decyzja obsługuje wszystkie wiersze o tej samej nazwie — wzorzec
    ``ImportPracownikowOdpiecie``). Analiza wypełnia pola liczone
    (``tryb``/``auto_jednostka``/``auto_similarity``/``skrot_sugerowany``),
    użytkownik ustawia wybór (``decyzja``/``wybrany_parent``/``wybrana_jednostka``)
    na ekranie weryfikacji, integracja materializuje wynik do ``utworzona``.
    """

    TRYB_ZGADYWANIE = "zgadywanie"
    TRYB_BRAK = "brak"
    TRYB_CHOICES = [
        (TRYB_ZGADYWANIE, "auto-dopasowanie (podobna nazwa)"),
        (TRYB_BRAK, "brak dopasowania (do utworzenia)"),
    ]

    DECYZJA_AKCEPTUJ = "akceptuj"
    DECYZJA_MAPUJ = "mapuj"
    DECYZJA_POMIN = "pomin"
    DECYZJA_CHOICES = [
        (DECYZJA_AKCEPTUJ, "akceptuj (utwórz nową / użyj auto-dopasowania)"),
        (DECYZJA_MAPUJ, "mapuj na istniejącą"),
        (DECYZJA_POMIN, "pomiń (nie importuj tych wierszy)"),
    ]

    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,
        related_name="jednostki_do_decyzji",
        verbose_name="import pracowników",
    )
    nazwa_zrodlowa = models.CharField("nazwa źródłowa", max_length=512)
    skrot_sugerowany = models.CharField("sugerowany skrót", max_length=128, blank=True)
    tryb = models.CharField(max_length=20, choices=TRYB_CHOICES)
    auto_jednostka = models.ForeignKey(
        "bpp.Jednostka",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="auto-dopasowana jednostka",
    )
    auto_similarity = models.FloatField("podobieństwo auto", null=True, blank=True)
    wybrany_parent = models.ForeignKey(
        "bpp.Jednostka",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="wybrany parent (wydział)",
        help_text="Miejsce w drzewie dla nowej jednostki. Puste = root (gdy "
        "uczelnia nie używa wydziałów) albo Wydział Domyślny (gdy używa).",
    )
    decyzja = models.CharField(
        max_length=20, choices=DECYZJA_CHOICES, default=DECYZJA_AKCEPTUJ
    )
    wybrana_jednostka = models.ForeignKey(
        "bpp.Jednostka",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="wybrana istniejąca jednostka (mapuj)",
    )
    utworzona = models.ForeignKey(
        "bpp.Jednostka",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="jednostka utworzona/rozstrzygnięta",
        help_text="Ustawiane przez integrację. Guard idempotencji (restart / "
        "podwójny commit nie duplikuje jednostek).",
    )

    class Meta:
        verbose_name = "decyzja o jednostce (import pracowników)"
        verbose_name_plural = "decyzje o jednostkach (import pracowników)"
        unique_together = (("parent", "nazwa_zrodlowa"),)
        ordering = ["nazwa_zrodlowa"]

    def __str__(self):
        return f"{self.nazwa_zrodlowa} ({self.tryb} → {self.decyzja})"


class ImportPracownikowTytul(models.Model):
    """Decyzja o jednym UNIKALNYM (znormalizowanym) stringu tytułu z pliku,
    którego nie da się dopasować dokładnie.

    Mirror ``ImportPracownikowJednostka``, uproszczony — tytuł nie ma drzewa
    ani wydziału. Deduplikowany po nazwie źródłowej (tytuły są współdzielone
    przez wielu pracowników, więc jedna decyzja obsługuje wszystkie wiersze o
    tej samej nazwie). Analiza wypełnia pola liczone
    (``tryb``/``auto_tytul``/``auto_similarity``), użytkownik ustawia wybór
    (``decyzja``/``wybrany_tytul``/``nazwa_do_utworzenia``/``skrot_do_utworzenia``)
    na ekranie weryfikacji, integracja materializuje wynik do ``utworzony``.
    """

    TRYB_ZGADYWANIE = "zgadywanie"
    TRYB_BRAK = "brak"
    TRYB_CHOICES = [
        (TRYB_ZGADYWANIE, "auto-dopasowanie (podobna nazwa)"),
        (TRYB_BRAK, "brak dopasowania (do utworzenia)"),
    ]

    DECYZJA_AKCEPTUJ = "akceptuj"
    DECYZJA_MAPUJ = "mapuj"
    DECYZJA_POMIN = "pomin"
    DECYZJA_CHOICES = [
        (DECYZJA_AKCEPTUJ, "akceptuj (utwórz nowy / użyj auto-dopasowania)"),
        (DECYZJA_MAPUJ, "mapuj na istniejący"),
        (DECYZJA_POMIN, "pomiń (nie ustawiaj tytułu tym wierszom)"),
    ]

    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,
        related_name="tytuly_do_decyzji",
        verbose_name="import pracowników",
    )
    nazwa_zrodlowa = models.CharField("nazwa źródłowa", max_length=512)
    tryb = models.CharField(max_length=20, choices=TRYB_CHOICES)
    auto_tytul = models.ForeignKey(
        "bpp.Tytul",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="auto-dopasowany tytuł",
    )
    auto_similarity = models.FloatField("podobieństwo auto", null=True, blank=True)
    nazwa_do_utworzenia = models.CharField(
        "nazwa do utworzenia", max_length=512, blank=True, default=""
    )
    skrot_do_utworzenia = models.CharField(
        "skrót do utworzenia", max_length=128, blank=True, default=""
    )
    decyzja = models.CharField(
        max_length=20, choices=DECYZJA_CHOICES, default=DECYZJA_AKCEPTUJ
    )
    wybrany_tytul = models.ForeignKey(
        "bpp.Tytul",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="wybrany istniejący tytuł (mapuj)",
    )
    utworzony = models.ForeignKey(
        "bpp.Tytul",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="tytuł utworzony/rozstrzygnięty",
        help_text="Ustawiane przez integrację. Guard idempotencji (restart / "
        "podwójny commit nie duplikuje tytułów).",
    )

    class Meta:
        verbose_name = "decyzja o tytule (import pracowników)"
        verbose_name_plural = "decyzje o tytułach (import pracowników)"
        unique_together = (("parent", "nazwa_zrodlowa"),)
        ordering = ["nazwa_zrodlowa"]

    def __str__(self):
        return f"{self.nazwa_zrodlowa} ({self.tryb} → {self.decyzja})"


class ImportPracownikowStopien(models.Model):
    """Decyzja o jednym UNIKALNYM (znormalizowanym) stringu stopnia służbowego
    z pliku, którego nie da się dopasować dokładnie.

    Mirror ``ImportPracownikowTytul`` (Tytul→StopienSluzbowy, tytul→stopien).
    Deduplikowany po nazwie źródłowej; analiza wypełnia pola liczone
    (``tryb``/``auto_stopien``/``auto_similarity``), użytkownik ustawia wybór
    (``decyzja``/``wybrany_stopien``/``nazwa_do_utworzenia``/
    ``skrot_do_utworzenia``), integracja materializuje wynik do ``utworzony``.
    """

    TRYB_ZGADYWANIE = "zgadywanie"
    TRYB_BRAK = "brak"
    TRYB_CHOICES = [
        (TRYB_ZGADYWANIE, "auto-dopasowanie (podobna nazwa)"),
        (TRYB_BRAK, "brak dopasowania (do utworzenia)"),
    ]

    DECYZJA_AKCEPTUJ = "akceptuj"
    DECYZJA_MAPUJ = "mapuj"
    DECYZJA_POMIN = "pomin"
    DECYZJA_CHOICES = [
        (DECYZJA_AKCEPTUJ, "akceptuj (utwórz nowy / użyj auto-dopasowania)"),
        (DECYZJA_MAPUJ, "mapuj na istniejący"),
        (DECYZJA_POMIN, "pomiń (nie ustawiaj stopnia tym wierszom)"),
    ]

    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,
        related_name="stopnie_do_decyzji",
        verbose_name="import pracowników",
    )
    nazwa_zrodlowa = models.CharField("nazwa źródłowa", max_length=512)
    tryb = models.CharField(max_length=20, choices=TRYB_CHOICES)
    auto_stopien = models.ForeignKey(
        "bpp.StopienSluzbowy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="auto-dopasowany stopień",
    )
    auto_similarity = models.FloatField("podobieństwo auto", null=True, blank=True)
    nazwa_do_utworzenia = models.CharField(
        "nazwa do utworzenia", max_length=512, blank=True, default=""
    )
    skrot_do_utworzenia = models.CharField(
        "skrót do utworzenia", max_length=128, blank=True, default=""
    )
    decyzja = models.CharField(
        max_length=20, choices=DECYZJA_CHOICES, default=DECYZJA_AKCEPTUJ
    )
    wybrany_stopien = models.ForeignKey(
        "bpp.StopienSluzbowy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="wybrany istniejący stopień (mapuj)",
    )
    utworzony = models.ForeignKey(
        "bpp.StopienSluzbowy",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="stopień utworzony/rozstrzygnięty",
        help_text="Ustawiane przez integrację. Guard idempotencji (restart / "
        "podwójny commit nie duplikuje stopni).",
    )

    class Meta:
        verbose_name = "decyzja o stopniu służbowym (import pracowników)"
        verbose_name_plural = "decyzje o stopniach służbowych (import pracowników)"
        unique_together = (("parent", "nazwa_zrodlowa"),)
        ordering = ["nazwa_zrodlowa"]

    def __str__(self):
        return f"{self.nazwa_zrodlowa} ({self.tryb} → {self.decyzja})"


class ImportPracownikowStanowisko(models.Model):
    """Decyzja o jednym UNIKALNYM (znormalizowanym) stringu stanowiska
    dydaktycznego z pliku. Mirror ``ImportPracownikowStopien``
    (StopienSluzbowy→StanowiskoDydaktyczne)."""

    TRYB_ZGADYWANIE = "zgadywanie"
    TRYB_BRAK = "brak"
    TRYB_CHOICES = [
        (TRYB_ZGADYWANIE, "auto-dopasowanie (podobna nazwa)"),
        (TRYB_BRAK, "brak dopasowania (do utworzenia)"),
    ]

    DECYZJA_AKCEPTUJ = "akceptuj"
    DECYZJA_MAPUJ = "mapuj"
    DECYZJA_POMIN = "pomin"
    DECYZJA_CHOICES = [
        (DECYZJA_AKCEPTUJ, "akceptuj (utwórz nowe / użyj auto-dopasowania)"),
        (DECYZJA_MAPUJ, "mapuj na istniejące"),
        (DECYZJA_POMIN, "pomiń (nie ustawiaj stanowiska tym wierszom)"),
    ]

    parent = models.ForeignKey(
        ImportPracownikow,
        on_delete=models.CASCADE,
        related_name="stanowiska_do_decyzji",
        verbose_name="import pracowników",
    )
    nazwa_zrodlowa = models.CharField("nazwa źródłowa", max_length=512)
    tryb = models.CharField(max_length=20, choices=TRYB_CHOICES)
    auto_stanowisko = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="auto-dopasowane stanowisko",
    )
    auto_similarity = models.FloatField("podobieństwo auto", null=True, blank=True)
    nazwa_do_utworzenia = models.CharField(
        "nazwa do utworzenia", max_length=512, blank=True, default=""
    )
    skrot_do_utworzenia = models.CharField(
        "skrót do utworzenia", max_length=128, blank=True, default=""
    )
    decyzja = models.CharField(
        max_length=20, choices=DECYZJA_CHOICES, default=DECYZJA_AKCEPTUJ
    )
    wybrane_stanowisko = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="wybrane istniejące stanowisko (mapuj)",
    )
    utworzone = models.ForeignKey(
        "bpp.StanowiskoDydaktyczne",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        verbose_name="stanowisko utworzone/rozstrzygnięte",
        help_text="Ustawiane przez integrację. Guard idempotencji (restart / "
        "podwójny commit nie duplikuje stanowisk).",
    )

    class Meta:
        verbose_name = "decyzja o stanowisku dydaktycznym (import pracowników)"
        verbose_name_plural = (
            "decyzje o stanowiskach dydaktycznych (import pracowników)"
        )
        unique_together = (("parent", "nazwa_zrodlowa"),)
        ordering = ["nazwa_zrodlowa"]

    def __str__(self):
        return f"{self.nazwa_zrodlowa} ({self.tryb} → {self.decyzja})"


def wiersz_kwalifikuje_do_przepiecia(autor_id, stara_id, jednostka_id, pary_z_pliku):
    """Czy wiersz kwalifikuje się do przepięcia prac (§10 D6/D7, F1/F2/F3).

    Wspólny warunek dla podglądu (kolumna/toggle/bulk) i fazy commit — MUSI
    dać identyczny zbiór kwalifikujących wierszy wszędzie. ``stara_id`` =
    ``aktualna_jednostka`` autora sprzed importu (w podglądzie odczyt live, w
    commit ze snapshotu — trigger DB zdążył ją przestawić).

    True gdy: autor ustawiony, stara i nowa jednostka ustawione (F2) i różne
    (jest co przepiąć), a para ``(autor_id, stara_id)`` NIE jest parą Z PLIKU
    (stara jednostka nie jest potwierdzona jako aktywny etat w innym wierszu —
    inaczej „pułapka drugiego etatu”, F1).
    """
    if autor_id is None or stara_id is None or jednostka_id is None:
        return False
    if stara_id == jednostka_id:
        return False
    if (autor_id, stara_id) in pary_z_pliku:
        return False
    return True
