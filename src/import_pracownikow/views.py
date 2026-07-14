# Create your views here.

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.db.models import (
    Case,
    Count,
    IntegerField,
    Prefetch,
    Value,
    When,
)
from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import DetailView, FormView, ListView
from liveops.views import CreateLiveOperationView, RestartView

from bpp.models import (
    Autor,
    Jednostka,
    StanowiskoDydaktyczne,
    StopienSluzbowy,
    Tytul,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from import_common.exceptions import BadNoOfSheetsException, HeaderNotFoundException
from import_pracownikow.forms import MapowanieForm, NowyImportForm
from import_pracownikow.mapping import dopasuj_profil, wybierz_profil_fallback
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
    ImportPracownikowStanowisko,
    ImportPracownikowStopien,
    ImportPracownikowTytul,
    ProfilMapowania,
    wiersz_kwalifikuje_do_przepiecia,
)
from import_pracownikow.pbn import adnotuj_pbn_instytucjonalny
from import_pracownikow.pewnosc import (
    CONFIDENCE_CHOICES,
    STATUS_BRAK,
    STATUS_DEDUP,
    STATUS_RECZNY,
    STATUS_TWARDY,
    odtworz_autor_jednostka,
)

GROUP_REQUIRED = "wprowadzanie danych"


def oznacz_przepiecie_prac(rows, parent):
    """Dokłada do każdego wiersza atrybuty sterujące kolumną „Przepnij prace”.

    ``przepnij_dostepne`` (bool), ``przepnij_stara_jednostka`` (Jednostka|None),
    ``przepnij_liczba_prac`` (int). N liczone AGREGATEM (dwa GROUP BY na
    Wydawnictwo_*_Autor) dla wszystkich kwalifikujących się wierszy naraz —
    bez N+1. Kwalifikacja przez wspólny ``wiersz_kwalifikuje_do_przepiecia``
    (F1/F2 — IDENTYCZNY warunek co faza commit i akcja zbiorcza): autor
    ustawiony, stara i nowa jednostka ustawione i różne, a stara jednostka NIE
    jest „parą z pliku” (potwierdzonym etatem w innym wierszu — pułapka drugiego
    etatu). ``parent.pary_z_pliku()`` liczone RAZ na całym imporcie (dla
    pojedynczego wiersza w swapie HTMX też patrzymy na cały plik).
    """
    pary_z_pliku = parent.pary_z_pliku()
    stare = {}
    pary = set()
    for row in rows:
        stara_id = row.autor.aktualna_jednostka_id if row.autor_id else None
        stare[row.pk] = stara_id
        if wiersz_kwalifikuje_do_przepiecia(
            row.autor_id, stara_id, row.jednostka_id, pary_z_pliku
        ):
            pary.add((row.autor_id, stara_id))
    liczby = {}
    jednostki_map = {}
    if pary:
        autor_ids = {a for a, _ in pary}
        jednostka_ids = {j for _, j in pary}
        for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor):
            agg = (
                model.objects.filter(
                    autor_id__in=autor_ids, jednostka_id__in=jednostka_ids
                )
                .values("autor_id", "jednostka_id")
                .annotate(n=Count("id"))
            )
            for w in agg:
                klucz = (w["autor_id"], w["jednostka_id"])
                liczby[klucz] = liczby.get(klucz, 0) + w["n"]
        jednostki_map = Jednostka.objects.in_bulk(jednostka_ids)
    for row in rows:
        stara_id = stare[row.pk]
        dostepne = (row.autor_id, stara_id) in pary
        row.przepnij_dostepne = dostepne
        row.przepnij_stara_jednostka = jednostki_map.get(stara_id) if dostepne else None
        row.przepnij_liczba_prac = liczby.get((row.autor_id, stara_id), 0)
    return rows


class ListaImportowView(GroupRequiredMixin, ListView):
    """Lista importów bieżącego użytkownika.

    Dawniej long_running.LongRunningOperationsView. Teraz zwykły owner-scoped
    ListView — strona live (postęp/wynik) jest osobno, pod centralnym
    ``liveops:live`` (link przez ``object.get_absolute_url``).
    """

    group_required = GROUP_REQUIRED
    model = ImportPracownikow
    template_name = "import_pracownikow/importpracownikow_list.html"

    def get_queryset(self):
        return ImportPracownikow.objects.filter(owner=self.request.user).order_by(
            "-created_on"
        )


class NowyImportView(GroupRequiredMixin, CreateLiveOperationView):
    """Formularz nowego importu.

    ``CreateLiveOperationView`` (liveops) sam ustawia owner, zapisuje,
    kolejkuje operację i przekierowuje na ``get_absolute_url()`` czyli
    centralną stronę live. Gating grupy — braces GroupRequiredMixin
    (superuser-exempt, jak w long_running).
    """

    group_required = GROUP_REQUIRED
    model = ImportPracownikow
    form_class = NowyImportForm

    def get(self, request, *args, **kwargs):
        if ImportPracownikow.objects.filter(
            owner=request.user, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
        ).exists():
            messages.warning(
                request,
                "Masz niezatwierdzony import w podglądzie — nowa analiza może "
                "unieważnić jego wynik.",
            )
        return super().get(request, *args, **kwargs)

    def form_valid(self, form):
        # NIE enqueue — najpierw ekran mapowania (analiza dopiero po zmapowaniu).
        self.object = form.save(commit=False)
        self.object.owner = self.request.user
        self.object.stan = ImportPracownikow.STAN_UTWORZONY
        self.object.save()
        return HttpResponseRedirect(
            reverse("import_pracownikow:mapowanie", kwargs={"pk": self.object.pk})
        )


# Stany, w których mapowanie jest dozwolone (przed commitem). NIE zmapowany na
# zintegrowanym — kasowanie wierszy zniszczyłoby audyt log_zmian (spec §4).
_STANY_MAPOWALNE = (
    ImportPracownikow.STAN_UTWORZONY,
    ImportPracownikow.STAN_ZMAPOWANY,
    ImportPracownikow.STAN_PRZEANALIZOWANY,
)


class MapowanieView(GroupRequiredMixin, FormView):
    """Ekran mapowania kolumn. GET: auto-propozycja (lub profil) + próbka.
    POST: zapis mapowania + ewentualny profil → stan zmapowany → (re)enqueue."""

    group_required = GROUP_REQUIRED
    form_class = MapowanieForm
    template_name = "import_pracownikow/mapowanie.html"

    @cached_property
    def object(self):
        return get_object_or_404(
            ImportPracownikow, pk=self.kwargs["pk"], owner=self.request.user
        )

    def _przygotuj(self, request):
        """Wywoływane z get()/post() (PO kontroli dostępu GroupRequiredMixin,
        żeby nie robić I/O pliku dla anonimowego/bez-grupy usera). Zwraca
        ``HttpResponseRedirect`` (błąd) albo ``None`` (OK)."""
        if self.object.stan not in _STANY_MAPOWALNE:
            messages.error(
                request, "Tego importu nie można już mapować (zatwierdzony)."
            )
            return HttpResponseRedirect(reverse("import_pracownikow:index"))
        try:
            self._naglowki, self._probka = self.object.naglowki_i_probka()
        except HeaderNotFoundException:
            messages.error(
                request,
                "Nie rozpoznano wiersza nagłówka w pliku — sprawdź, czy plik "
                "zawiera kolumny takie jak nazwisko / imię / jednostka.",
            )
            return HttpResponseRedirect(reverse("import_pracownikow:index"))
        except BadNoOfSheetsException as exc:
            # „Jeden arkusz = jeden import" — plik wieloarkuszowy (np. dwie
            # uczelnie w jednym skoroszycie) odrzucamy z czytelnym komunikatem.
            messages.error(request, str(exc))
            return HttpResponseRedirect(reverse("import_pracownikow:index"))
        if not self._naglowki:
            messages.error(request, "Plik nie zawiera kolumn do zmapowania.")
            return HttpResponseRedirect(reverse("import_pracownikow:index"))
        return None

    def get(self, request, *args, **kwargs):
        return self._przygotuj(request) or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self._przygotuj(request) or super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["naglowki"] = self._naglowki
        profil = dopasuj_profil(self._naglowki) or wybierz_profil_fallback(
            self._naglowki
        )
        # Zapamiętaj na instancji dla get_context_data (info w szablonie §13).
        self._profil_zastosowany = profil
        if profil is not None:
            kwargs["initial_mapowanie"] = profil.mapowanie
            initial = kwargs.get("initial") or {}
            initial["profil_zastosowany"] = profil.pk
            kwargs["initial"] = initial
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.object
        ctx["probka_rows"] = [
            [w.get(h, "") for h in self._naglowki] for w in self._probka
        ]
        profil = getattr(self, "_profil_zastosowany", None)
        ctx["profil_zastosowany_nazwa"] = profil.nazwa if profil else None
        return ctx

    def form_valid(self, form):
        obj = self.object
        obj.mapowanie_kolumn = form.mapowanie()
        obj.stan = ImportPracownikow.STAN_ZMAPOWANY
        obj.tworz_brakujace_jednostki = form.cleaned_data.get(
            "tworz_brakujace_jednostki", True
        )
        obj.tworz_brakujace_tytuly = form.cleaned_data.get(
            "tworz_brakujace_tytuly", True
        )
        obj.tworz_brakujace_stopnie = form.cleaned_data.get(
            "tworz_brakujace_stopnie", True
        )
        obj.tworz_brakujace_stanowiska = form.cleaned_data.get(
            "tworz_brakujace_stanowiska", True
        )
        # on_restart() kasuje wiersze podglądu (stan==zmapowany) — inaczej
        # ponowna analiza by je zduplikowała.
        obj.on_restart()
        # Reset pól operacji liveops (jak RestartView.post) — inaczej po
        # anulowanym/zakończonym przebiegu enqueue rusza z brudnym stanem
        # (cancel_requested=True → natychmiastowe „cancelled").
        pola_liveops = obj.reset_liveops_state()
        obj.save(
            update_fields=[
                "mapowanie_kolumn",
                "stan",
                "tworz_brakujace_jednostki",
                "tworz_brakujace_tytuly",
                "tworz_brakujace_stopnie",
                "tworz_brakujace_stanowiska",
            ]
            + pola_liveops
        )

        if form.cleaned_data.get("zapisz_profil"):
            ProfilMapowania.objects.update_or_create(
                nazwa=form.cleaned_data["nazwa_profilu"],
                defaults={
                    "mapowanie": obj.mapowanie_kolumn,
                    "utworzony_przez": self.request.user,
                    "ostatnio_uzyty": timezone.now(),
                },
            )

        # Stempel „ostatnio użyty" na zastosowanym profilu (fallback/dopasowany) —
        # dzięki temu wybierz_profil_fallback następnym razem podniesie właśnie ten.
        profil_pk = form.cleaned_data.get("profil_zastosowany")
        if profil_pk:
            ProfilMapowania.objects.filter(pk=profil_pk).update(
                ostatnio_uzyty=timezone.now()
            )

        obj.enqueue()
        return HttpResponseRedirect(obj.get_absolute_url())


class _ImportPodgladMixin(GroupRequiredMixin, View):
    """Wspólna bramka podglądu importu (owner/superuser scoping + stan
    ``przeanalizowany``) dla widoków HTMX modyfikujących decyzje wiersza/odpięcia
    (Faza 3/4). Wydzielona, żeby scoping i bramka żyły w JEDNYM miejscu —
    dziedziczą po niej ``_WierszImportuMixin`` (dokłada ``row``/``_render_wiersz``)
    i ``PrzelaczOdpiecieView`` (dokłada ``odpiecie``)."""

    group_required = GROUP_REQUIRED

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def _blad_jesli_nie_podglad(self):
        """G3: modyfikacje decyzji o osobach (wybór/edycja autora, odpięcie,
        utwórz-nowego, przepięcie) dozwolone dla importu w fazie edytowalnej —
        podgląd (``przeanalizowany``) LUB faza osób po zapisie struktury
        (``struktura_zintegrowana``). Bez tej bramki bezpośredni POST (retry
        HTMX, back-button, wyścig z Zatwierdź) na imporcie już `zintegrowanym`
        nadpisałby audyt ``log_zmian`` po commicie / zmienił decyzję odpięcia po
        jej wykonaniu. Zwraca ``HttpResponseBadRequest`` (blokada) albo ``None``."""
        if not self.parent_object.edytowalny_podglad:
            return HttpResponseBadRequest(
                "Decyzje o osobach można edytować tylko przed zapisem osób."
            )
        return None


class _WierszImportuMixin(_ImportPodgladMixin):
    """Wspólny fetch wiersza importu (dokłada ``row`` do bazowej bramki
    ``_ImportPodgladMixin``). Render partiala do odpowiedzi HTMX.

    Odpowiedź HTMX to SAM partial komórek (``_wiersz_preview_kom.html``) — bez
    wrappera ``<tr>``. Akcje wiersza swapują ``innerHTML`` istniejącego ``<tr>``,
    więc węzeł zostaje stały i DataTables odczytuje go po swapie (uwaga #6)."""

    partial_template = "import_pracownikow/partials/_wiersz_preview_kom.html"

    @cached_property
    def row(self):
        return get_object_or_404(
            ImportPracownikowRow, pk=self.kwargs["row_pk"], parent=self.parent_object
        )

    def _render_wiersz(self):
        # Re-pobierz wiersz przez get_details_set(), żeby partial miał adnotacje
        # nr_arkusza/nr_wiersza (RawSQL) oraz autor_z_pbn_inst (Exists) — inaczej
        # te komórki/badge byłyby puste po swapie HTMX. Odzwierciedla zapisane
        # właśnie zmiany.
        row = adnotuj_pbn_instytucjonalny(self.parent_object.get_details_set()).get(
            pk=self.row.pk
        )
        oznacz_przepiecie_prac([row], self.parent_object)
        return render(
            self.request,
            self.partial_template,
            {"row": row, "parent_object": self.parent_object},
        )


def _zwiaz_autora_z_wierszem(row, autor):
    """Wiąże wiersz importu z WSKAZANYM autorem (ręczny wybór / override) i
    przelicza powiązanie ``Autor_Jednostka`` + ``zmiany_potrzebne``. Wspólny
    rdzeń ``WybierzKandydataView`` (wybór spośród policzonych kandydatów) i
    ``DopasujAutoraView`` (dowolny autor z autocomplete).

    - ustawia ``row.autor = autor`` PRZED liczeniem (``odtworz_autor_jednostka``
      / ``check_if_integration_needed`` czytają ``self.autor``);
    - **guard ``jednostka=None``**: wiersz z odroczoną jednostką NIE może wołać
      ``odtworz_autor_jednostka`` — ta odłożyłaby AJ z ``jednostka=None`` do
      ``diff_do_utworzenia`` → integracja (``_materializuj_diff``)
      ``get_or_create(jednostka_id=None)`` → ``IntegrityError`` ubijający cały
      task liveops. Mirror ``analyze._przetworz_wiersz`` (jednostka odroczona →
      ``autor_jednostka=None``, zdejmij wpis AJ, ``zmiany_potrzebne=False``);
    - ręczny wybór jest jednoznaczny → ``confidence = STATUS_RECZNY``
      (świadomy wybór operatora — NIE „twardy match" z auto-analizy, badge nie
      kłamie), ``utworz_nowego=False``, ``przepnij_prace=False`` (G2: zmiana
      autora unieważnia opt-in przepięcia poprzedniego autora);
    - zeruje ``wybrany_kandydat`` (``WybierzKandydataView`` przywraca je PO
      helperze jako provenance wyboru spośród kandydatów).

    Zapisuje wiersz KOMPLETNYM ``update_fields`` — bez zerowanych flag
    (``utworz_nowego``/``przepnij_prace``/``wybrany_kandydat``) reset nie
    trafiłby do bazy.
    """
    row.autor = autor
    if row.jednostka_id is None:
        row.diff_do_utworzenia.pop("autor_jednostka", None)
        row.autor_jednostka = None
        row.zmiany_potrzebne = False
        # Zmiana autora unieważnia decyzję okresu (odtworz robi to sam w else).
        row._zapomnij_okres()
    else:
        odtworz_autor_jednostka(row, autor)
    row.confidence = STATUS_RECZNY
    row.utworz_nowego = False
    row.przepnij_prace = False
    row.wybrany_kandydat = None
    row.save(
        update_fields=[
            "autor",
            "confidence",
            "autor_jednostka",
            "diff_do_utworzenia",
            "zmiany_potrzebne",
            "utworz_nowego",
            "przepnij_prace",
            "wybrany_kandydat",
        ]
    )


class WybierzKandydataView(_WierszImportuMixin):
    """POST: ustaw wybranego kandydata dla wiersza ``wielu`` → materializuj
    ``row.autor`` i przelicz ``zmiany_potrzebne``. Zwraca partial wiersza."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        try:
            wybrany_id = int(request.POST.get("wybrany_kandydat", ""))
        except (TypeError, ValueError):
            return HttpResponseBadRequest("Brak lub błędny wybrany_kandydat.")
        kandydat = row.kandydaci.filter(autor_id=wybrany_id).first()
        if kandydat is None:
            # Wybór musi być jednym z zapisanych kandydatów tego wiersza.
            return HttpResponseBadRequest("Autor nie jest kandydatem tego wiersza.")

        autor = kandydat.autor
        _zwiaz_autora_z_wierszem(row, autor)
        # Provenance kandydata: helper wyzerował ``wybrany_kandydat`` na None,
        # tu nadpisujemy go wybranym autorem (ślad, że wybór padł spośród
        # policzonych kandydatów — nie override z autocomplete).
        row.wybrany_kandydat = autor
        row.save(update_fields=["wybrany_kandydat"])
        return self._render_wiersz()


class DopasujAutoraView(_WierszImportuMixin):
    """POST (HTMX): dopasuj wiersz do WSKAZANEGO autora BPP z autocomplete
    ``import-autor-autocomplete`` — override dla ``twardy``/``zgadywanie``,
    wybór dla ``brak``, „inny autor" dla ``wielu``. Wiąże ``row.autor`` i
    przelicza jak ``WybierzKandydataView`` przez wspólny
    ``_zwiaz_autora_z_wierszem`` (ustawia ``STATUS_RECZNY``).

    ``autor`` (pk) walidowany ``get_object_or_404`` — przy ręcznym ajaxie
    zamiast pk może przyjść tekst. Owner/superuser-scoped + bramka stanu
    ``przeanalizowany`` (via ``_WierszImportuMixin``). Zwraca partial wiersza.
    """

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        autor = get_object_or_404(Autor, pk=request.POST.get("autor"))
        _zwiaz_autora_z_wierszem(row, autor)
        return self._render_wiersz()


class PrzelaczUtworzNowegoView(_WierszImportuMixin):
    """POST (HTMX): przełącz flagę ``utworz_nowego`` dla wiersza ``brak``
    (D2). Tworzenie nowego autora nastąpi dopiero w fazie commit (integracja) —
    dry-run nic nie tworzy. Wzorzec jak ``WybierzKandydataView``: owner-scoped,
    bramka stanu ``przeanalizowany``. Zwraca partial wiersza."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        if row.confidence != STATUS_BRAK:
            return HttpResponseBadRequest(
                "„Utwórz nowego” dotyczy tylko wierszy bez dopasowania."
            )
        # Radio grupy Pomiń/Utwórz/Dopasuj: „utworz" → flaga True, cokolwiek
        # innego (Pomiń) → False. Legacy param `utworz_nowego` (checkbox) nadal
        # akceptowany, żeby stare wywołania/testy nie padły.
        wybor = request.POST.get("wybor")
        if wybor is not None:
            row.utworz_nowego = wybor == "utworz"
        else:
            row.utworz_nowego = request.POST.get("utworz_nowego") is not None
        row.save(update_fields=["utworz_nowego"])
        return self._render_wiersz()


class PrzepnijPraceView(_WierszImportuMixin):
    """POST (HTMX): przełącz flagę ``przepnij_prace`` wiersza (§10 D6/D7).

    Samo przepięcie prac wykona się dopiero w fazie commit (integracja).
    Owner/superuser-scoped + bramka stanu ``przeanalizowany`` — via
    ``_WierszImportuMixin``. F2/G2: odrzuca 400 TYLKO przy WŁĄCZANIU, gdy wiersz
    nie kwalifikuje się do przepięcia (autor/jednostka nieustawione,
    aktualna==jednostka, albo stara jednostka jest „parą z pliku”) — inaczej
    commit crashowałby na ``Jednostka.objects.get(pk=None)`` / przepinałby wbrew
    guardowi F1. ODZNACZANIE jest zawsze dozwolone: wiersz mógł przestać się
    kwalifikować po fakcie (inny wiersz rozstrzygnięto na starą jednostkę,
    rematch zmienił autora) i renderuje „—”, ale flagę-zombie w DB trzeba dać
    zdjąć. Warunek IDENTYCZNY z commit i bulk
    (``wiersz_kwalifikuje_do_przepiecia``). Zwraca partial wiersza."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        nowa_wartosc = request.POST.get("przepnij_prace") is not None
        # G2: waliduj kwalifikację TYLKO przy włączaniu — odznaczanie musi
        # przejść nawet dla wiersza-zombie, który przestał się kwalifikować.
        if nowa_wartosc:
            pary_z_pliku = self.parent_object.pary_z_pliku()
            stara_id = row.autor.aktualna_jednostka_id if row.autor_id else None
            if not wiersz_kwalifikuje_do_przepiecia(
                row.autor_id, stara_id, row.jednostka_id, pary_z_pliku
            ):
                return HttpResponseBadRequest(
                    "Wiersz nie kwalifikuje się do przepięcia prac."
                )
        row.przepnij_prace = nowa_wartosc
        row.save(update_fields=["przepnij_prace"])
        return self._render_wiersz()


class ZaznaczWszystkiePrzepieciaView(_ImportPodgladMixin):
    """POST: zaznacz ``przepnij_prace`` dla WSZYSTKICH wierszy KWALIFIKUJĄCYCH
    się do przepięcia. Owner/superuser-scoped + bramka podglądu. Redirect na
    tabelę.

    F1: warunek kwalifikacji IDENTYCZNY z podglądem i commit
    (``wiersz_kwalifikuje_do_przepiecia`` z guardem „para z pliku”). Guardu
    „stara jednostka jest w pliku” nie da się wprost wyrazić jednym
    ``.exclude(F())``, więc zbieramy pary z pliku w Pythonie i aktualizujemy po
    ``pk__in`` liście kwalifikujących wierszy."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        parent = self.parent_object
        pary_z_pliku = parent.pary_z_pliku()
        kwalifikujace = []
        for row in parent.importpracownikowrow_set.filter(
            autor__isnull=False, jednostka__isnull=False
        ).select_related("autor"):
            stara_id = row.autor.aktualna_jednostka_id
            if wiersz_kwalifikuje_do_przepiecia(
                row.autor_id, stara_id, row.jednostka_id, pary_z_pliku
            ):
                kwalifikujace.append(row.pk)
        n = parent.importpracownikowrow_set.filter(pk__in=kwalifikujace).update(
            przepnij_prace=True
        )
        messages.success(request, f"Zaznaczono przepięcie prac dla {n} wierszy.")
        return HttpResponseRedirect(
            reverse(
                "import_pracownikow:importpracownikow-results",
                kwargs={"pk": parent.pk},
            )
        )


class PrzelaczOdpiecieView(_ImportPodgladMixin):
    """POST (HTMX): ustaw ``zaznaczone`` odpięcia (§9) z obecności pola
    ``zaznaczone`` w POST. Owner/superuser-scoped + bramka stanu
    ``przeanalizowany`` — via ``_ImportPodgladMixin``. Zwraca partial
    ``_odpiecie_row.html``."""

    # Odpowiedź HTMX to SAM partial komórek (bez wrappera <tr>) — toggle swapuje
    # innerHTML istniejącego <tr>, węzeł zostaje stały (DataTables, uwaga #6).
    partial_template = "import_pracownikow/partials/_odpiecie_row_kom.html"

    @cached_property
    def odpiecie(self):
        return get_object_or_404(
            ImportPracownikowOdpiecie,
            pk=self.kwargs["odp_pk"],
            parent=self.parent_object,
        )

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        odp = self.odpiecie
        odp.zaznaczone = request.POST.get("zaznaczone") is not None
        odp.save(update_fields=["zaznaczone"])
        # Re-pobierz z adnotacją autor_z_pbn_inst (Exists) — inaczej badge „PBN"
        # zniknąłby po swapie HTMX (partial czyta odp.autor_z_pbn_inst).
        odp = adnotuj_pbn_instytucjonalny(
            self.parent_object.odpiecia.select_related(
                "autor_jednostka__autor", "autor_jednostka__autor__tytul"
            ),
            autor_path="autor_jednostka__autor",
        ).get(pk=odp.pk)
        return render(
            request,
            self.partial_template,
            {"odp": odp, "parent_object": self.parent_object},
        )


class ZaznaczOdpieciaView(_ImportPodgladMixin):
    """POST: ustaw ``zaznaczone`` dla listy odpięć podanej w ``odp_pk`` — wiersze
    z bieżącego filtra tabeli DataTables, zebrane po stronie klienta. Flaga
    ``zaznacz`` (``1``/``0``) decyduje zaznacz/odznacz. Owner/superuser-scope +
    bramka podglądu (``_ImportPodgladMixin``). Redirect na tabelę odpięć.

    Analogicznie do ``ZaznaczWszystkiePrzepieciaView`` (form POST → redirect),
    ale zakres bierze z jawnej listy ``odp_pk`` (nie „wszystkie") — dzięki temu
    działa na podzbiorze przefiltrowanym w tabeli."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        parent = self.parent_object
        zaznacz = request.POST.get("zaznacz") == "1"
        # Tylko numeryczne pk — odporność na śmieci w POST (pk__in z nie-intem
        # rzuciłby ValueError). Filtr po parent = scoping (cudze odpięcia poza).
        pks = [p for p in request.POST.getlist("odp_pk") if p.isdigit()]
        n = parent.odpiecia.filter(pk__in=pks).update(zaznaczone=zaznacz)
        akcja = "zaznaczono do odpięcia" if zaznacz else "odznaczono"
        messages.success(request, f"Zbiorczo {akcja}: {n} powiązań.")
        return HttpResponseRedirect(
            reverse("import_pracownikow:odpiecia", kwargs={"pk": parent.pk})
        )


class ImportPracownikowResultsView(GroupRequiredMixin, ListView):
    """Filtrowalna tabela wyników importu (dopasowani/niedopasowani autorzy).

    Zastępuje dawną long_running.LongRunningResultsView: właściciel-scoping
    przez ``parent_object`` i queryset z ``get_details_set()``. Strona live
    (liveops:live) linkuje tu przez panel wyniku po zakończeniu importu.
    """

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/importpracownikowrow_list.html"
    context_object_name = "object_list"

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def get_queryset(self):
        # Rozstrzygnięte (twardy match + ręczny wybór operatora) na dół, wiersze
        # do rozstrzygnięcia (brak/wielu/zgadywanie) na górę, potem kolejność z
        # pliku. G5: prefetch kandydatów Z AUTOREM — partial dla wierszy `wielu`
        # iteruje row.kandydaci.all i czyta k.autor per opcja dropdownu; bez
        # tego N+1 (setki zapytań przy dużych plikach).
        return (
            adnotuj_pbn_instytucjonalny(self.parent_object.get_details_set())
            .annotate(
                _prio=Case(
                    When(
                        confidence__in=[STATUS_TWARDY, STATUS_RECZNY, STATUS_DEDUP],
                        then=Value(1),
                    ),
                    default=Value(0),
                    output_field=IntegerField(),
                )
            )
            .prefetch_related(
                Prefetch(
                    "kandydaci",
                    queryset=ImportPracownikowRowKandydat.objects.select_related(
                        "autor"
                    ),
                )
            )
            .order_by("_prio", "nr_arkusza", "nr_wiersza")
        )

    def get_context_data(self, **kwargs):
        # Sekcja odpięć („Ludzie spoza XLS") żyje teraz w OSOBNYM widoku
        # OdpieciaView (hub-podstrona) — tu jej NIE renderujemy.
        parent = self.parent_object
        ctx = super().get_context_data(
            parent_object=parent,
            **kwargs,
        )
        if parent.edytowalny_podglad:
            oznacz_przepiecie_prac(list(ctx["object_list"]), parent)
        # Pasek filtrów stanu pól — etykiety z rejestru POLA_ROZNIC (jedno źródło
        # prawdy z modelem/szablonem). Dzielimy na ZAWSZE WIDOCZNE (główne) i
        # ZWIJANE (dodatkowe, w <details>). Stopień/stanowisko wypadają całkiem,
        # gdy plik nie ma takiej kolumny — nie filtrujemy po polu, którego nie
        # ma (spójne z ukryciem wiersza w karcie).
        from import_pracownikow.roznice import POLA_ROZNIC

        etykiety = {k: etykieta for k, etykieta, _ in POLA_ROZNIC}
        klucze_glowne = ["jednostka", "tytul", "data_od", "data_do"]
        klucze_dodatkowe = ["email", "stopien", "funkcja", "stanowisko"]
        if not parent.ma_kolumne_stopnia:
            klucze_dodatkowe.remove("stopien")
        if not parent.ma_kolumne_stanowiska:
            klucze_dodatkowe.remove("stanowisko")
        ctx["pola_glowne"] = [(k, etykiety[k]) for k in klucze_glowne]
        ctx["pola_dodatkowe"] = [(k, etykiety[k]) for k in klucze_dodatkowe]
        # Filtr „Rodzaj dopasowania" — opcje statusów (jedno źródło:
        # CONFIDENCE_CHOICES) + syntetyczne „do pominięcia" (autor IS NULL AND
        # NOT utworz_nowego, patrz row.do_pominiecia). Deep-link z ostrzeżenia
        # finalizacji przychodzi jako ?rodzaj=do-pominiecia; walidujemy go tu,
        # a śmieciowa wartość degraduje do "" (traktowane jak „wszystkie").
        ctx["rodzaje_confidence"] = list(CONFIDENCE_CHOICES)
        dozwolone_rodzaje = {"do-pominiecia"} | {k for k, _ in CONFIDENCE_CHOICES}
        rodzaj = self.request.GET.get("rodzaj", "")
        ctx["wybrany_rodzaj"] = rodzaj if rodzaj in dozwolone_rodzaje else ""
        return ctx


class PodgladImportuView(GroupRequiredMixin, DetailView):
    """Hub „szczegóły importu" — landing z 2–4 kafelkami (Jednostki / Ludzie z
    XLS / Ludzie spoza XLS / Tytuły) i skupionymi podstronami.

    Nowy główny punkt wejścia „szczegóły importu" (z listy importów i panelu
    wyniku live). Owner/superuser-scoped (jak ``ImportPracownikowResultsView``).
    Kafelki Jednostki/Tytuły są WARUNKOWE (tylko gdy są decyzje do
    rozstrzygnięcia); Ludzie z XLS / spoza XLS — zawsze."""

    group_required = GROUP_REQUIRED
    model = ImportPracownikow
    template_name = "import_pracownikow/przeglad.html"
    context_object_name = "parent_object"

    def get_object(self, queryset=None):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def get(self, request, *args, **kwargs):
        # Item 4: flash po auto-redircie z zapisu struktury (Krok 1 → Krok 2).
        # ``get_success_url`` dokleja ``?zapisano=struktura`` (messages nie
        # działa z celery ``on_commit``, więc komunikat ustawiamy tu, na
        # fresh-GET po redircie liveops).
        if request.GET.get("zapisano") == "struktura":
            messages.success(
                request,
                "Struktura zapisana. Teraz sprawdź dopasowania osób poniżej "
                "i zaimportuj je do bazy (Krok 2).",
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        parent = self.object
        ludzie = parent.liczniki_ludzi_z_xls()
        odpiecia_count = parent.odpiecia.count()
        pary_z_pliku_puste = len(parent.pary_z_pliku()) == 0
        ctx.update(
            {
                "liczniki_ludzi": ludzie,
                "ludzie_do_akceptacji": ludzie["wielu"] + ludzie["brak"],
                "liczniki_jednostek": parent.liczniki_jednostek(),
                "liczniki_tytulow": parent.liczniki_tytulow(),
                "pokaz_jednostki": parent.jednostki_do_decyzji.exists(),
                "pokaz_tytuly": parent.tytuly_do_decyzji.exists(),
                # Item 2: „Zobacz tytuły" w Kroku 1 nawet gdy wszystko dopasowane.
                "ma_tytuly": parent.ma_tytuly,
                # Item 3: bramka — import osób zablokowany, dopóki są tytuły z
                # pliku nierozstrzygnięte (do utworzenia, nie zmaterializowane).
                "tytuly_wymagaja_rozstrzygniecia": (
                    parent.tytuly_wymagaja_rozstrzygniecia
                ),
                "liczniki_stopni": parent.liczniki_stopni(),
                "liczniki_stanowisk": parent.liczniki_stanowisk(),
                "pokaz_stopnie": parent.stopnie_do_decyzji.exists(),
                "pokaz_stanowiska": parent.stanowiska_do_decyzji.exists(),
                # Bramka Kroku 2 (finding #2): import osób nie tworzy słowników
                # po cichu — dowolny nierozstrzygnięty słownik blokuje.
                "slowniki_wymagaja_rozstrzygniecia": (
                    parent.tytuly_wymagaja_rozstrzygniecia
                    or parent.stopnie_wymagaja_rozstrzygniecia
                    or parent.stanowiska_wymagaja_rozstrzygniecia
                ),
                # „Zapisz jednostki + słowniki" (zakres=struktura) ma sens, gdy
                # jest COKOLWIEK słownikowego do utworzenia poza jednostkami.
                "pokaz_struktura_slowniki": (
                    parent.tytuly_do_decyzji.exists()
                    or parent.stopnie_do_decyzji.exists()
                    or parent.stanowiska_do_decyzji.exists()
                ),
                "odpiecia_count": odpiecia_count,
                "pary_z_pliku_puste": pary_z_pliku_puste,
                # Ostrzeżenie: wszystkie jednostki odroczone → wszystkie aktywne
                # AJ uczelni flagowane jako „spoza pliku" (znane ograniczenie).
                "ostrzezenie_odpiecia": pary_z_pliku_puste and odpiecia_count > 0,
                "stan": parent.stan,
                # Dwustopniowy hub: Krok 1 = struktura (w podglądzie), Krok 2 =
                # osoby (dopiero po zapisaniu struktury). Wymusza „najpierw
                # jednostki, potem autorzy" i chowa szczegóły osób do Kroku 2.
                "faza_struktury": parent.faza_struktury,
                "faza_osob": parent.faza_osob,
                "moze_zapisac_strukture": parent.faza_struktury,
                "moze_importowac_osoby": parent.faza_osob,
                "pokaz_ludzi": (
                    parent.faza_osob
                    or parent.stan == ImportPracownikow.STAN_ZINTEGROWANY
                ),
                # Item 6: ekran audytu (log zmian) ma sens po pełnej integracji
                # osób — wtedy wiersze mają zapisany log_zmian.
                "pokaz_audyt": parent.stan == ImportPracownikow.STAN_ZINTEGROWANY,
            }
        )
        return ctx


class OdpieciaView(GroupRequiredMixin, ListView):
    """Podstrona huba „Ludzie spoza XLS" — powiązania Autor+Jednostka OBECNE w
    bazie, ale NIEOBECNE w tym imporcie (§9 odpięcia).

    Wydzielona z dołu ``importpracownikowrow_list.html``. Owner/superuser-scoped.
    Queryset przeniesiony z ``ImportPracownikowResultsView.get_context_data``.
    ``przelacz-odpiecie`` (toggle checkboxa) bez zmian."""

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/odpiecia.html"
    context_object_name = "odpiecia"

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def get_queryset(self):
        return adnotuj_pbn_instytucjonalny(
            self.parent_object.odpiecia.select_related(
                "autor_jednostka__autor",
                "autor_jednostka__autor__tytul",
                "autor_jednostka__jednostka",
            ),
            autor_path="autor_jednostka__autor",
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(parent_object=self.parent_object, **kwargs)


class LogZmianView(GroupRequiredMixin, ListView):
    """Ekran audytu (item 6) — per-wiersz log zmian po integracji: utworzenia
    (autor/jednostka/tytuł), zmiany Autora i Autor_Jednostka, przepięcia prac
    (z→do, liczba) oraz wykonane odpięcia. Owner/superuser-scoped.

    Czyta ``log_zmian`` (materializowany przez integrację) — wiersze bez zmian
    (``log_zmian`` puste) NIE są pokazywane (filtr ``log_zmian__isnull=False``
    plus per-wiersz ``log_zmian_lista`` w szablonie odsiewa puste rekordy)."""

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/audyt.html"
    context_object_name = "wiersze"
    # Bez serwerowego stronicowania — audyt jest read-only po integracji, a
    # wyszukiwanie/stronicowanie przejmuje DataTables po stronie klienta
    # (poz. 10). Ładujemy wszystkie wiersze ze zmianami do DOM.

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def get_queryset(self):
        # ``get_details_set`` adnotuje nr_arkusza/nr_wiersza (kolejność z pliku)
        # i robi select_related — filtrujemy do wierszy z zapisanym log_zmian.
        # ORCID/tytuł jadą z select_related autora; PBN-inst przez Exists.
        return adnotuj_pbn_instytucjonalny(
            self.parent_object.get_details_set().filter(log_zmian__isnull=False)
        )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(parent_object=self.parent_object, **kwargs)
        ctx["odpiecia_wykonane"] = adnotuj_pbn_instytucjonalny(
            self.parent_object.odpiecia.filter(wykonane=True).select_related(
                "autor_jednostka__autor",
                "autor_jednostka__autor__tytul",
                "autor_jednostka__jednostka",
            ),
            autor_path="autor_jednostka__autor",
        )
        return ctx


class WeryfikacjaJednostekView(GroupRequiredMixin, View):
    """Ekran weryfikacji decyzji o jednostkach (do utworzenia / auto-dopasowane).

    GET renderuje listę decyzji z kontrolkami (utwórz/mapuj/pomiń + parent +
    cel mapowania), POST zapisuje wszystkie decyzje naraz. Krok OPCJONALNY —
    import może iść z domyślnymi decyzjami (akceptuj), więc NIE bramkuje
    zatwierdzenia; służy do korekty umiejscowienia przed commitem. Edycja tylko
    w stanie ``przeanalizowany`` (jak reszta decyzji podglądu)."""

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/weryfikacja_jednostek.html"

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def _decyzje(self):
        return (
            self.parent_object.jednostki_do_decyzji.select_related(
                "auto_jednostka", "wybrany_parent", "wybrana_jednostka"
            )
            .annotate(liczba_osob=Count("wiersze", distinct=True))
            .order_by("nazwa_zrodlowa")
        )

    def _build_context(self, parent, decyzje, bledne_pks=frozenset()):
        """Kontekst szablonu zbudowany z listy decyzji — WSPÓLNY dla GET i dla
        re-renderu po błędzie walidacji. Przy re-renderze ``decyzje`` mają
        NAŁOŻONE (niezapisane) wartości z POST, więc formularz nie gubi tego, co
        user ustawił; ``bledne_pks`` podświetla wiersze „mapuj bez celu”."""
        uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
        return {
            "parent_object": parent,
            "decyzje_brak": [
                d for d in decyzje if d.tryb == ImportPracownikowJednostka.TRYB_BRAK
            ],
            "decyzje_zgadywanie": [
                d
                for d in decyzje
                if d.tryb == ImportPracownikowJednostka.TRYB_ZGADYWANIE
            ],
            "uzywaj_wydzialow": bool(uczelnia and uczelnia.uzywaj_wydzialow),
            "parent_opcje": Jednostka.objects.filter(parent__isnull=True).order_by(
                "nazwa"
            ),
            "mapuj_opcje": Jednostka.objects.filter(
                skupia_pracownikow=True, widoczna=True
            ).order_by("nazwa"),
            "moze_edytowac": parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY,
            "bledne_pks": bledne_pks,
            "DECYZJA_AKCEPTUJ": ImportPracownikowJednostka.DECYZJA_AKCEPTUJ,
            "DECYZJA_MAPUJ": ImportPracownikowJednostka.DECYZJA_MAPUJ,
            "DECYZJA_POMIN": ImportPracownikowJednostka.DECYZJA_POMIN,
        }

    @staticmethod
    def _z_puli(raw, queryset):
        """Zwraca obiekt z ``queryset`` po pk z POST, albo ``None``.

        Broni POST-a decyzji jednostek przed dwoma nadużyciami (uwaga reviewera
        #5): (a) nienumeryczne id (``filter(pk="abc")`` → ``ValueError`` → 500) —
        zwracamy ``None`` zamiast wywracać widok; (b) pk spoza puli UI — filtr po
        TYM SAMYM querysecie co formularz (roots dla parenta, widoczne jednostki
        skupiające pracowników dla „mapuj"), więc spreparowany POST nie przypisze
        pracowników do ukrytej/niewłaściwej jednostki ani nie użyje dowolnego
        węzła jako parenta."""
        raw = (raw or "").strip()
        if not raw.isdigit():
            return None
        return queryset.filter(pk=int(raw)).first()

    def _naloz_post(self, dec, prawidlowe):
        """Nakłada wybory z POST na obiekt decyzji (BEZ zapisu do bazy). Wspólne
        dla walidacji, re-renderu po błędzie i finalnego zapisu — jedno źródło
        prawdy o tym, jak POST mapuje się na pola decyzji."""
        pref = f"dec_{dec.pk}_"
        decyzja = self.request.POST.get(pref + "decyzja")
        if decyzja in prawidlowe:
            dec.decyzja = decyzja
        # Te same querysety co pula UI w ``_build_context`` (parent_opcje /
        # mapuj_opcje) — patrz ``_z_puli``.
        dec.wybrany_parent = self._z_puli(
            self.request.POST.get(pref + "parent"),
            Jednostka.objects.filter(parent__isnull=True),
        )
        dec.wybrana_jednostka = self._z_puli(
            self.request.POST.get(pref + "wybrana"),
            Jednostka.objects.filter(skupia_pracownikow=True, widoczna=True),
        )

    def get(self, request, *args, **kwargs):
        parent = self.parent_object
        return render(
            request,
            self.template_name,
            self._build_context(parent, list(self._decyzje())),
        )

    def post(self, request, *args, **kwargs):
        parent = self.parent_object
        if parent.stan != ImportPracownikow.STAN_PRZEANALIZOWANY:
            return HttpResponseBadRequest(
                "Decyzje o jednostkach można zmieniać tylko w podglądzie."
            )
        prawidlowe = {
            ImportPracownikowJednostka.DECYZJA_AKCEPTUJ,
            ImportPracownikowJednostka.DECYZJA_MAPUJ,
            ImportPracownikowJednostka.DECYZJA_POMIN,
        }
        decyzje = list(self._decyzje())
        for dec in decyzje:
            self._naloz_post(dec, prawidlowe)
        # Walidacja: „mapuj na istniejącą" bez wskazanej jednostki docelowej to
        # cicha pułapka — integracja zostawiłaby te wiersze niedopasowane.
        # Alarmuj i NIE zapisuj, ale RE-RENDERUJ z nałożonymi wartościami (BEZ
        # redirectu) — inaczej user traci wszystko, co ustawił w innych wierszach.
        bledne_pks = {
            dec.pk
            for dec in decyzje
            if dec.decyzja == ImportPracownikowJednostka.DECYZJA_MAPUJ
            and dec.wybrana_jednostka_id is None
        }
        if bledne_pks:
            nazwy = [dec.nazwa_zrodlowa for dec in decyzje if dec.pk in bledne_pks]
            messages.error(
                request,
                'Wybierz jednostkę docelową w kolumnie „Mapuj na" dla: '
                + ", ".join(nazwy),
            )
            return render(
                request,
                self.template_name,
                self._build_context(parent, decyzje, bledne_pks),
            )
        for dec in decyzje:
            dec.save(update_fields=["decyzja", "wybrany_parent", "wybrana_jednostka"])
        messages.success(request, "Zapisano decyzje o jednostkach.")
        return HttpResponseRedirect(
            reverse("import_pracownikow:jednostki", kwargs={"pk": parent.pk})
        )


class WeryfikacjaTytulowView(GroupRequiredMixin, View):
    """Ekran weryfikacji decyzji o tytułach (do utworzenia / auto-dopasowane).

    Mirror ``WeryfikacjaJednostekView`` — tytuł nie ma drzewa ani wydziału,
    więc prostszy. GET renderuje decyzje z kontrolkami (utwórz/mapuj/pomiń +
    edytowalne nazwa/skrót dla trybu ``brak`` + cel mapowania), POST zapisuje
    wszystkie decyzje naraz. Krok OPCJONALNY — import może iść z domyślnymi
    decyzjami (``akceptuj``), więc NIE bramkuje zatwierdzenia; służy do korekty
    przed commitem. Edycja tylko w stanie ``przeanalizowany`` (jak reszta
    decyzji podglądu)."""

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/weryfikacja_tytulow.html"

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def _decyzje(self):
        return (
            self.parent_object.tytuly_do_decyzji.select_related(
                "auto_tytul", "wybrany_tytul"
            )
            .annotate(liczba_osob=Count("wiersze_tytul", distinct=True))
            .order_by("nazwa_zrodlowa")
        )

    def get(self, request, *args, **kwargs):
        parent = self.parent_object
        decyzje = list(self._decyzje())
        ctx = {
            "parent_object": parent,
            "decyzje_brak": [
                d for d in decyzje if d.tryb == ImportPracownikowTytul.TRYB_BRAK
            ],
            "decyzje_zgadywanie": [
                d for d in decyzje if d.tryb == ImportPracownikowTytul.TRYB_ZGADYWANIE
            ],
            "mapuj_opcje": Tytul.objects.all().order_by("skrot"),
            "moze_edytowac": parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY,
            "DECYZJA_AKCEPTUJ": ImportPracownikowTytul.DECYZJA_AKCEPTUJ,
            "DECYZJA_MAPUJ": ImportPracownikowTytul.DECYZJA_MAPUJ,
            "DECYZJA_POMIN": ImportPracownikowTytul.DECYZJA_POMIN,
        }
        return render(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        parent = self.parent_object
        if parent.stan != ImportPracownikow.STAN_PRZEANALIZOWANY:
            return HttpResponseBadRequest(
                "Decyzje o tytułach można zmieniać tylko w podglądzie."
            )
        prawidlowe = {
            ImportPracownikowTytul.DECYZJA_AKCEPTUJ,
            ImportPracownikowTytul.DECYZJA_MAPUJ,
            ImportPracownikowTytul.DECYZJA_POMIN,
        }
        decyzje = list(parent.tytuly_do_decyzji.all())
        # Walidacja jak przy jednostkach: „mapuj" bez wskazanego tytułu to cicha
        # pułapka — alarmuj i nie zapisuj, dopóki user nie wskaże celu.
        bez_celu = [
            dec.nazwa_zrodlowa
            for dec in decyzje
            if request.POST.get(f"dec_{dec.pk}_decyzja")
            == ImportPracownikowTytul.DECYZJA_MAPUJ
            and not (request.POST.get(f"dec_{dec.pk}_wybrana") or "")
        ]
        if bez_celu:
            messages.error(
                request,
                'Wybierz tytuł docelowy w kolumnie „Mapuj na" dla: '
                + ", ".join(bez_celu),
            )
            return HttpResponseRedirect(
                reverse("import_pracownikow:tytuly", kwargs={"pk": parent.pk})
            )
        for dec in decyzje:
            pref = f"dec_{dec.pk}_"
            decyzja = request.POST.get(pref + "decyzja")
            if decyzja in prawidlowe:
                dec.decyzja = decyzja
            # isdigit guard: nienumeryczny pk z POST-a nie może wywrócić widoku
            # (Tytul.objects.filter(pk="abc") → ValueError → 500). Pula UI dla
            # tytułów to wszystkie Tytul, więc nie zawężamy querysetu — tylko
            # bronimy przed nie-liczbą.
            mapuj_id = (request.POST.get(pref + "wybrana") or "").strip()
            dec.wybrany_tytul = (
                Tytul.objects.filter(pk=int(mapuj_id)).first()
                if mapuj_id.isdigit()
                else None
            )
            update_fields = ["decyzja", "wybrany_tytul"]
            # Nazwa/skrót edytowalne TYLKO dla „do utworzenia” (tryb brak) —
            # dla zgadywania rozstrzyga auto_tytul/wybrany_tytul, nie tworzymy.
            if dec.tryb == ImportPracownikowTytul.TRYB_BRAK:
                nazwa = request.POST.get(pref + "nazwa")
                if nazwa is not None:
                    dec.nazwa_do_utworzenia = nazwa.strip()[:512]
                    update_fields.append("nazwa_do_utworzenia")
                skrot = request.POST.get(pref + "skrot")
                if skrot is not None:
                    dec.skrot_do_utworzenia = skrot.strip()[:128]
                    update_fields.append("skrot_do_utworzenia")
            dec.save(update_fields=update_fields)
        messages.success(request, "Zapisano decyzje o tytułach.")
        return HttpResponseRedirect(
            reverse("import_pracownikow:tytuly", kwargs={"pk": parent.pk})
        )


class WeryfikacjaStopniView(GroupRequiredMixin, View):
    """Ekran weryfikacji decyzji o stopniach służbowych (mirror
    ``WeryfikacjaTytulowView``)."""

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/weryfikacja_stopni.html"

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def _decyzje(self):
        return (
            self.parent_object.stopnie_do_decyzji.select_related(
                "auto_stopien", "wybrany_stopien"
            )
            .annotate(liczba_osob=Count("wiersze_stopien", distinct=True))
            .order_by("nazwa_zrodlowa")
        )

    def get(self, request, *args, **kwargs):
        parent = self.parent_object
        decyzje = list(self._decyzje())
        ctx = {
            "parent_object": parent,
            "decyzje_brak": [
                d for d in decyzje if d.tryb == ImportPracownikowStopien.TRYB_BRAK
            ],
            "decyzje_zgadywanie": [
                d for d in decyzje if d.tryb == ImportPracownikowStopien.TRYB_ZGADYWANIE
            ],
            "mapuj_opcje": StopienSluzbowy.objects.all().order_by("skrot"),
            "moze_edytowac": parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY,
            "DECYZJA_AKCEPTUJ": ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
            "DECYZJA_MAPUJ": ImportPracownikowStopien.DECYZJA_MAPUJ,
            "DECYZJA_POMIN": ImportPracownikowStopien.DECYZJA_POMIN,
        }
        return render(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        parent = self.parent_object
        if parent.stan != ImportPracownikow.STAN_PRZEANALIZOWANY:
            return HttpResponseBadRequest(
                "Decyzje o stopniach można zmieniać tylko w podglądzie."
            )
        prawidlowe = {
            ImportPracownikowStopien.DECYZJA_AKCEPTUJ,
            ImportPracownikowStopien.DECYZJA_MAPUJ,
            ImportPracownikowStopien.DECYZJA_POMIN,
        }
        decyzje = list(parent.stopnie_do_decyzji.all())
        bez_celu = [
            dec.nazwa_zrodlowa
            for dec in decyzje
            if request.POST.get(f"dec_{dec.pk}_decyzja")
            == ImportPracownikowStopien.DECYZJA_MAPUJ
            and not (request.POST.get(f"dec_{dec.pk}_wybrana") or "")
        ]
        if bez_celu:
            messages.error(
                request,
                'Wybierz stopień docelowy w kolumnie „Mapuj na" dla: '
                + ", ".join(bez_celu),
            )
            return HttpResponseRedirect(
                reverse("import_pracownikow:stopnie", kwargs={"pk": parent.pk})
            )
        for dec in decyzje:
            pref = f"dec_{dec.pk}_"
            decyzja = request.POST.get(pref + "decyzja")
            if decyzja in prawidlowe:
                dec.decyzja = decyzja
            mapuj_id = (request.POST.get(pref + "wybrana") or "").strip()
            dec.wybrany_stopien = (
                StopienSluzbowy.objects.filter(pk=int(mapuj_id)).first()
                if mapuj_id.isdigit()
                else None
            )
            update_fields = ["decyzja", "wybrany_stopien"]
            if dec.tryb == ImportPracownikowStopien.TRYB_BRAK:
                nazwa = request.POST.get(pref + "nazwa")
                if nazwa is not None:
                    dec.nazwa_do_utworzenia = nazwa.strip()[:512]
                    update_fields.append("nazwa_do_utworzenia")
                skrot = request.POST.get(pref + "skrot")
                if skrot is not None:
                    dec.skrot_do_utworzenia = skrot.strip()[:128]
                    update_fields.append("skrot_do_utworzenia")
            dec.save(update_fields=update_fields)
        messages.success(request, "Zapisano decyzje o stopniach służbowych.")
        return HttpResponseRedirect(
            reverse("import_pracownikow:stopnie", kwargs={"pk": parent.pk})
        )


class WeryfikacjaStanowiskView(GroupRequiredMixin, View):
    """Ekran weryfikacji decyzji o stanowiskach dydaktycznych (mirror
    ``WeryfikacjaStopniView``)."""

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/weryfikacja_stanowisk.html"

    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def _decyzje(self):
        return (
            self.parent_object.stanowiska_do_decyzji.select_related(
                "auto_stanowisko", "wybrane_stanowisko"
            )
            .annotate(liczba_osob=Count("wiersze_stanowisko", distinct=True))
            .order_by("nazwa_zrodlowa")
        )

    def get(self, request, *args, **kwargs):
        parent = self.parent_object
        decyzje = list(self._decyzje())
        ctx = {
            "parent_object": parent,
            "decyzje_brak": [
                d for d in decyzje if d.tryb == ImportPracownikowStanowisko.TRYB_BRAK
            ],
            "decyzje_zgadywanie": [
                d
                for d in decyzje
                if d.tryb == ImportPracownikowStanowisko.TRYB_ZGADYWANIE
            ],
            "mapuj_opcje": StanowiskoDydaktyczne.objects.all().order_by("skrot"),
            "moze_edytowac": parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY,
            "DECYZJA_AKCEPTUJ": ImportPracownikowStanowisko.DECYZJA_AKCEPTUJ,
            "DECYZJA_MAPUJ": ImportPracownikowStanowisko.DECYZJA_MAPUJ,
            "DECYZJA_POMIN": ImportPracownikowStanowisko.DECYZJA_POMIN,
        }
        return render(request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        parent = self.parent_object
        if parent.stan != ImportPracownikow.STAN_PRZEANALIZOWANY:
            return HttpResponseBadRequest(
                "Decyzje o stanowiskach można zmieniać tylko w podglądzie."
            )
        prawidlowe = {
            ImportPracownikowStanowisko.DECYZJA_AKCEPTUJ,
            ImportPracownikowStanowisko.DECYZJA_MAPUJ,
            ImportPracownikowStanowisko.DECYZJA_POMIN,
        }
        decyzje = list(parent.stanowiska_do_decyzji.all())
        bez_celu = [
            dec.nazwa_zrodlowa
            for dec in decyzje
            if request.POST.get(f"dec_{dec.pk}_decyzja")
            == ImportPracownikowStanowisko.DECYZJA_MAPUJ
            and not (request.POST.get(f"dec_{dec.pk}_wybrana") or "")
        ]
        if bez_celu:
            messages.error(
                request,
                'Wybierz stanowisko docelowe w kolumnie „Mapuj na" dla: '
                + ", ".join(bez_celu),
            )
            return HttpResponseRedirect(
                reverse("import_pracownikow:stanowiska", kwargs={"pk": parent.pk})
            )
        for dec in decyzje:
            pref = f"dec_{dec.pk}_"
            decyzja = request.POST.get(pref + "decyzja")
            if decyzja in prawidlowe:
                dec.decyzja = decyzja
            mapuj_id = (request.POST.get(pref + "wybrana") or "").strip()
            dec.wybrane_stanowisko = (
                StanowiskoDydaktyczne.objects.filter(pk=int(mapuj_id)).first()
                if mapuj_id.isdigit()
                else None
            )
            update_fields = ["decyzja", "wybrane_stanowisko"]
            if dec.tryb == ImportPracownikowStanowisko.TRYB_BRAK:
                nazwa = request.POST.get(pref + "nazwa")
                if nazwa is not None:
                    dec.nazwa_do_utworzenia = nazwa.strip()[:512]
                    update_fields.append("nazwa_do_utworzenia")
                skrot = request.POST.get(pref + "skrot")
                if skrot is not None:
                    dec.skrot_do_utworzenia = skrot.strip()[:128]
                    update_fields.append("skrot_do_utworzenia")
            dec.save(update_fields=update_fields)
        messages.success(request, "Zapisano decyzje o stanowiskach dydaktycznych.")
        return HttpResponseRedirect(
            reverse("import_pracownikow:stanowiska", kwargs={"pk": parent.pk})
        )


class _PkOwnerRestartMixin(GroupRequiredMixin, RestartView):
    """Wspólny ``get_object`` dla widoków restartu — URL ma tylko ``pk``
    (bez ``op_type``), więc nadpisujemy ``OpTypeObjectMixin.get_object``
    i rozwiązujemy konkretny model wprost, owner-scoped.

    Bramka grupy (#508 F4): liveops ``BaseLiveOperationMixin`` gejtuje tylko
    gdy ``LIVEOPS["REQUIRED_GROUP"]`` jest ustawione — w BPP NIE jest, więc
    tamta bramka to no-op. Dokładamy braces ``GroupRequiredMixin`` (konwencja
    projektu, jak reszta widoków importu), inaczej dowolny zalogowany user
    odpaliłby integrację / restart analizy (akcje destrukcyjne, skala importu).
    """

    model = ImportPracownikow
    group_required = GROUP_REQUIRED

    def get_object(self, queryset=None):
        return get_object_or_404(
            ImportPracownikow, pk=self.kwargs["pk"], owner=self.request.user
        )


class ZatwierdzImportView(_PkOwnerRestartMixin):
    """Zatwierdza dry-run (analizę) i uruchamia integrację na już
    zapisanym pliku (bez ponownego uploadu).

    Ustawiamy stan na ``zatwierdzony`` (żeby ``on_restart()`` NIE skasował
    wierszy podglądu — kasuje tylko gdy stan==utworzony lub zmapowany) i delegujemy
    resztę do bazowego POST-a liveops ``RestartView`` (reset stanu
    operacji, re-enqueue, przekierowanie na stronę live).

    ``zakres`` (POST) wybiera co integracja utworzy: pełny import (osoby +
    struktura), same jednostki, albo jednostki + tytuły (bez osób).

    Bramka „najpierw struktura, potem osoby":
    - zakres STRUKTURALNY (jednostki / jednostki+tytuły) wolno odpalić z podglądu
      (``przeanalizowany``, Krok 1) LUB z fazy osób (``struktura_zintegrowana``,
      Krok 2) — to drugie służy DOTWORZENIU odłożonych tytułów przed importem
      osób (item 3; idempotentne — reconcilery mają guard
      ``utworzona``/``utworzony``);
    - PEŁNY import (osoby) TYLKO po zapisaniu struktury
      (``struktura_zintegrowana``, Krok 2) i TYLKO gdy nie ma nierozstrzygniętych
      tytułów z pliku (item 3 — import osób nie tworzy tytułów po cichu).
      Importowanie osób bez rozstrzygniętych jednostek nie ma sensu.
    Nieznana/brakująca wartość ``zakres`` → PELNY.
    """

    _ZAKRESY_PRAWIDLOWE = {z for z, _ in ImportPracownikow.ZAKRES_CHOICES}

    def post(self, request, *args, **kwargs):
        obj = self.get_object()  # 404 dla nie-ownera
        zakres = request.POST.get("zakres", ImportPracownikow.ZAKRES_PELNY)
        if zakres not in self._ZAKRESY_PRAWIDLOWE:
            zakres = ImportPracownikow.ZAKRES_PELNY

        # Skrót „Przejdź do kolejnego kroku": gdy zapis struktury (same jednostki)
        # NIC nie utworzy (wszystkie decyzje to auto-dopasowania do istniejących),
        # integracja jest de-facto no-opem strukturalnym. Uruchamiamy ją
        # SYNCHRONICZNIE (materializuje ewentualne guessy → podłącza wiersze) i
        # lądujemy PROSTO w Kroku 2, z pominięciem strony live „Struktura
        # zapisana" — skoro nic nie zapisano, celebracja byłaby myląca.
        if zakres == ImportPracownikow.ZAKRES_JEDNOSTKI and obj.nic_do_utworzenia:
            return self._przejdz_do_kroku2_synchronicznie(request, obj)

        if zakres == ImportPracownikow.ZAKRES_JEDNOSTKI:
            # Same jednostki — tylko z podglądu (Krok 1). Po zapisaniu struktury
            # nie ma sensu ich zapisywać ponownie.
            stany_wymagane = {ImportPracownikow.STAN_PRZEANALIZOWANY}
            blad = "Zapis samych jednostek jest możliwy tylko z podglądu (Krok 1)."
        elif zakres == ImportPracownikow.ZAKRES_STRUKTURA:
            # Jednostki + tytuły: z podglądu (Krok 1) ALBO dotworzenie odłożonych
            # tytułów w fazie osób (Krok 2, item 3; idempotentne — reconcilery
            # jednostek/tytułów mają guard ``utworzona``/``utworzony``).
            stany_wymagane = {
                ImportPracownikow.STAN_PRZEANALIZOWANY,
                ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA,
            }
            blad = (
                "Strukturę można zapisać z podglądu (Krok 1) albo dotworzyć "
                "brakujące tytuły w fazie osób (Krok 2)."
            )
        else:
            # PELNY = import osób: dopiero po zapisaniu struktury i po
            # rozstrzygnięciu słowników (item 3 / spec §12 finding #2 — brak
            # cichego tworzenia tytułów / stopni / stanowisk).
            if (
                obj.tytuly_wymagaja_rozstrzygniecia
                or obj.stopnie_wymagaja_rozstrzygniecia
                or obj.stanowiska_wymagaja_rozstrzygniecia
            ):
                return HttpResponseBadRequest(
                    "Najpierw utwórz brakujące słowniki z pliku "
                    "(Krok 2: tytuły / stopnie służbowe / stanowiska "
                    "dydaktyczne) — import osób nie tworzy ich po cichu."
                )
            stany_wymagane = {ImportPracownikow.STAN_STRUKTURA_ZINTEGROWANA}
            blad = "Najpierw zapisz strukturę (jednostki) — dopiero potem osoby."
        # Atomowy compare-and-set (uwaga reviewera #1): warunkowy UPDATE
        # ``WHERE stan IN stany_wymagane`` przestawia stan na ``zatwierdzony``
        # tylko gdy import NADAL jest w stanie wyjściowym. Dwa równoległe
        # zatwierdzenia (celery z >1 workerem) serializuje baza — dokładnie jedno
        # trafia 1 wiersz i kolejkuje integrację; drugie dostaje 0 → 400. Bez
        # tego oba przeszłyby bramkę na ``obj.stan`` odczytanym na starcie i
        # wyzwoliłyby integrację dwa razy (duplikaty autorów/jednostek/przepięć).
        zmieniono = ImportPracownikow.objects.filter(
            pk=obj.pk, stan__in=stany_wymagane
        ).update(stan=ImportPracownikow.STAN_ZATWIERDZONY, zakres_integracji=zakres)
        if not zmieniono:
            return HttpResponseBadRequest(blad)
        return super().post(request, *args, **kwargs)

    def _przejdz_do_kroku2_synchronicznie(self, request, obj):
        """Zapisuje strukturę bez tworzenia czegokolwiek i przenosi PROSTO do
        Kroku 2, z pominięciem strony live. Atomowy CAS (jak w ``post``) broni
        przed podwójnym odpaleniem; integrację biegniemy w wątku żądania
        (``TextProgress`` — bez channels/celery), bo dla „nic do utworzenia" jest
        to lekkie: rozstrzygnięcie auto-dopasowań + podłączenie wierszy. Na błąd
        cofamy import do Kroku 1 (reconcilery idempotentne → bezpieczny retry)."""
        import sys

        from liveops.progress import TextProgress

        zmieniono = ImportPracownikow.objects.filter(
            pk=obj.pk, stan=ImportPracownikow.STAN_PRZEANALIZOWANY
        ).update(
            stan=ImportPracownikow.STAN_ZATWIERDZONY,
            zakres_integracji=ImportPracownikow.ZAKRES_JEDNOSTKI,
        )
        if not zmieniono:
            return HttpResponseBadRequest(
                "Ten import nie jest już w podglądzie (Krok 1)."
            )
        obj.refresh_from_db()
        # Czyścimy pola liveops z fazy analizy (mirror RestartView) — bez tego
        # stary snapshot mieszałby się z wynikiem integracji; sami nie enqueue'ujemy.
        obj.save(update_fields=obj.reset_liveops_state())
        try:
            # obj.run dispatchuje integruj() dla stanu ``zatwierdzony`` (zgłasza do
            # rollbara i re-raise'uje na błędzie); integruj ustawia stan →
            # ``struktura_zintegrowana``.
            obj.run(TextProgress(obj, sys.stdout))
        except Exception:
            # Cofnij do Kroku 1 — reconcilery mają guardy ``utworzon*``, więc
            # ponowna próba jest bezpieczna. obj.run już zgłosił błąd do rollbara.
            obj.refresh_from_db()
            obj.stan = ImportPracownikow.STAN_PRZEANALIZOWANY
            obj.save(update_fields=["stan"])
            messages.error(
                request,
                "Nie udało się przejść do kolejnego kroku — spróbuj ponownie "
                "(szczegóły błędu w panelu administracyjnym).",
            )
            return HttpResponseRedirect(
                reverse("import_pracownikow:przeglad", kwargs={"pk": obj.pk})
            )
        messages.success(
            request,
            "Wszystkie jednostki są już w bazie — nic nowego nie powstało. "
            "Sprawdź dopasowania osób poniżej i zaimportuj je do bazy (Krok 2).",
        )
        return HttpResponseRedirect(
            reverse("import_pracownikow:przeglad", kwargs={"pk": obj.pk})
        )


class RestartAnalizaView(_PkOwnerRestartMixin):
    """Cofa import do stanu ``zmapowany`` i uruchamia analizę od nowa.

    Ustawiamy stan na ``zmapowany`` PRZED wywołaniem bazowego POST-a, żeby
    ``on_restart()`` skasował istniejące wiersze podglądu (dry-run od zera).
    """

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        # „Jeden arkusz = jeden import" — restart ISTNIEJĄCEGO importu wchodzi w
        # analizę z pominięciem ekranu mapowania, więc plik wieloarkuszowy
        # (np. import sprzed tej reguły) łapiemy tutaj, zamiast pozwolić mu
        # wywalić analizę w tle.
        try:
            obj.waliduj_liczbe_arkuszy()
        except BadNoOfSheetsException as exc:
            messages.error(request, str(exc))
            return HttpResponseRedirect(reverse("import_pracownikow:index"))
        obj.stan = ImportPracownikow.STAN_ZMAPOWANY
        obj.save(update_fields=["stan"])
        return super().post(request, *args, **kwargs)
