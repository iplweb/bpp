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
    STATUS_BRAK,
    STATUS_CHOICES,
    STATUS_DISPLAY,
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
        (ZAKRES_STRUKTURA, "jednostki + tytuły (bez osób)"),
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
    zakres_integracji = models.CharField(
        "Zakres integracji",
        max_length=20,
        choices=ZAKRES_CHOICES,
        default=ZAKRES_PELNY,
        help_text="Co „Zapisz do bazy” faktycznie tworzy: pełny import "
        "(struktura + osoby), same jednostki, albo jednostki + tytuły "
        "(bez osób). Ustawiane przez przycisk zatwierdzenia na hubie.",
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

        Auto-przejście TYLKO po analizie (dry-run) → hub „szczegóły importu"
        (Krok 1). Po integracji zwracamy ``None`` — zostajemy na panelu wyniku
        liveops z podsumowaniem (zintegrowano/utworzono/pominięto). Zastępuje
        martwy inline-``<script>`` z ``import_pracownikow_result.html``, który
        nigdy się nie wykonywał: liveops wstrzykuje wynik przez
        ``DOMParser``+``replaceWith``, a tak wstawiony ``<script>`` przeglądarka
        oznacza „already started"."""
        if self.stan == self.STAN_PRZEANALIZOWANY:
            return reverse("import_pracownikow:przeglad", kwargs={"pk": self.pk})
        return None

    def run(self, p):
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

    def naglowki_i_probka(self, limit=10):
        """Synchronicznie (bez liveops) czyta znormalizowane nagłówki i do
        ``limit`` wierszy próbki — na ekran mapowania. Nagłówki = klucze
        wiersza bez kluczy lokalizacyjnych. Używa ``TRY_NAMES``/``MIN_POINTS``
        z ``mapping`` (rozpoznaje przemianowane kolumny — patrz T2). Może
        rzucić ``HeaderNotFoundException`` (plik bez rozpoznawalnego
        nagłówka) — widok (T8) łapie to i pokazuje komunikat, nie 500."""
        from import_common.sources import otworz_zrodlo
        from import_pracownikow.mapping import MIN_POINTS, TRY_NAMES

        zrodlo = otworz_zrodlo(
            self.plik_xls.path, try_names=TRY_NAMES, min_points=MIN_POINTS
        )
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

    zmiany_potrzebne = models.BooleanField()

    diff_do_utworzenia = models.JSONField(default=dict, blank=True)
    pominiety_bo_nieaktualny = models.BooleanField(default=False)

    confidence = models.CharField(  # noqa: DJ001
        max_length=20, choices=STATUS_CHOICES, null=True, blank=True
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
        return False

    def _check_autor_jednostka_needs_update(self, dane):
        """Sprawdza czy powiązanie autor-jednostka wymaga aktualizacji."""
        aj = self.autor_jednostka
        checks = [
            dane.get("data_zatrudnienia") is not None
            and aj.rozpoczal_prace != dane["data_zatrudnienia"],
            dane.get("data_końca_zatrudnienia") is not None
            and aj.zakonczyl_prace != dane["data_końca_zatrudnienia"],
            self.funkcja_autora is not None and aj.funkcja != self.funkcja_autora,
            self.grupa_pracownicza is not None
            and aj.grupa_pracownicza != self.grupa_pracownicza,
            self.wymiar_etatu is not None and aj.wymiar_etatu != self.wymiar_etatu,
            self.podstawowe_miejsce_pracy is not None
            and self.podstawowe_miejsce_pracy != aj.podstawowe_miejsce_pracy,
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

        if self.tytul_id is not None:
            if a.tytul_id != self.tytul_id:
                a.tytul_id = self.tytul_id
                self.log_zmian["autor"].append(
                    f"tytuł naukowy -> {self.tytul.skrot if self.tytul_id else 'brak'}"
                )

        try:
            a.save()
        except DataError as e:
            raise BPPDatabaseError(self.dane_z_xls, self, f"DataError {e}") from e

    def _integrate_autor_jednostka(self):
        aj = self.autor_jednostka
        dane = self.dane_bardziej_znormalizowane

        if (
            dane.get("data_zatrudnienia") is not None
            and aj.rozpoczal_prace != dane["data_zatrudnienia"]
        ):
            aj.rozpoczal_prace = dane["data_zatrudnienia"]
            self.log_zmian["autor_jednostka"].append(
                f"data zatrudnienia na {dane['data_zatrudnienia']}"
            )

        if (
            dane.get("data_końca_zatrudnienia") is not None
            and aj.zakonczyl_prace != dane["data_końca_zatrudnienia"]
        ):
            aj.zakonczyl_prace = dane["data_końca_zatrudnienia"]
            self.log_zmian["autor_jednostka"].append(
                f"data końca zatrudnienia na {dane['data_końca_zatrudnienia']}"
            )

        if self.funkcja_autora is not None and aj.funkcja != self.funkcja_autora:
            aj.funkcja = self.funkcja_autora
            self.log_zmian["autor_jednostka"].append(
                f"funkcja na {self.funkcja_autora}"
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

        if (
            self.podstawowe_miejsce_pracy is not None
            and self.podstawowe_miejsce_pracy != aj.podstawowe_miejsce_pracy
        ):
            if not self.podstawowe_miejsce_pracy:
                aj.podstawowe_miejsce_pracy = False
                self.log_zmian["autor_jednostka"].append(
                    "podstawowe_miejsce_pracy -> nie"
                )
            else:
                aj.ustaw_podstawowe_miejsce_pracy()
                self.log_zmian["autor_jednostka"].append(
                    "podstawowe_miejsce_pracy -> tak"
                )

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
