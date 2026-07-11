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
    Tytul,
    Uczelnia,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from import_common.exceptions import HeaderNotFoundException
from import_pracownikow.forms import MapowanieForm, NowyImportForm
from import_pracownikow.mapping import dopasuj_profil
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowJednostka,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
    ImportPracownikowTytul,
    ProfilMapowania,
    wiersz_kwalifikuje_do_przepiecia,
)
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
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
        profil = dopasuj_profil(self._naglowki)
        if profil is not None:
            kwargs["initial_mapowanie"] = profil.mapowanie
        return kwargs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["object"] = self.object
        ctx["probka_rows"] = [
            [w.get(h, "") for h in self._naglowki] for w in self._probka
        ]
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
        """G3: modyfikacje decyzji (wybór/edycja/odpięcie/utwórz-nowego)
        dozwolone WYŁĄCZNIE dla importu w podglądzie (``przeanalizowany``). Bez
        tej bramki bezpośredni POST (retry HTMX, back-button, wyścig z Zatwierdź)
        na imporcie już `zintegrowanym` nadpisałby audyt ``log_zmian`` po
        commicie / zmienił decyzję odpięcia po jej wykonaniu. Analog
        `_STANY_MAPOWALNE` — zintegrowany wykluczony. Zwraca
        ``HttpResponseBadRequest`` (blokada) albo ``None`` (OK)."""
        if self.parent_object.stan != ImportPracownikow.STAN_PRZEANALIZOWANY:
            return HttpResponseBadRequest(
                "Wiersz można edytować tylko dla importu w podglądzie."
            )
        return None


class _WierszImportuMixin(_ImportPodgladMixin):
    """Wspólny fetch wiersza importu (dokłada ``row`` do bazowej bramki
    ``_ImportPodgladMixin``). Render partiala do odpowiedzi HTMX."""

    partial_template = "import_pracownikow/partials/_wiersz_preview.html"

    @cached_property
    def row(self):
        return get_object_or_404(
            ImportPracownikowRow, pk=self.kwargs["row_pk"], parent=self.parent_object
        )

    def _render_wiersz(self):
        # Re-pobierz wiersz przez get_details_set(), żeby partial miał adnotacje
        # nr_arkusza/nr_wiersza (RawSQL) — inaczej te komórki byłyby puste po
        # swapie HTMX. Odzwierciedla zapisane właśnie zmiany.
        row = self.parent_object.get_details_set().get(pk=self.row.pk)
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
    - ręczny wybór jest jednoznaczny → ``confidence = STATUS_TWARDY``,
      ``utworz_nowego=False``, ``przepnij_prace=False`` (G2: zmiana autora
      unieważnia opt-in przepięcia poprzedniego autora);
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
    else:
        odtworz_autor_jednostka(row, autor)
    row.confidence = STATUS_TWARDY
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
    ``_zwiaz_autora_z_wierszem`` (ustawia ``STATUS_TWARDY``).

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

    partial_template = "import_pracownikow/partials/_odpiecie_row.html"

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
        return render(
            request,
            self.partial_template,
            {"odp": odp, "parent_object": self.parent_object},
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
        # non-twardy (do rozstrzygnięcia) na górę, potem kolejność z pliku.
        # G5: prefetch kandydatów Z AUTOREM — partial dla wierszy `wielu` iteruje
        # row.kandydaci.all i czyta k.autor per opcja dropdownu; bez tego N+1
        # (setki zapytań przy dużych plikach).
        return (
            self.parent_object.get_details_set()
            .annotate(
                _prio=Case(
                    When(confidence=STATUS_TWARDY, then=Value(1)),
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
        if parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY:
            oznacz_przepiecie_prac(list(ctx["object_list"]), parent)
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
                "odpiecia_count": odpiecia_count,
                "pary_z_pliku_puste": pary_z_pliku_puste,
                # Ostrzeżenie: wszystkie jednostki odroczone → wszystkie aktywne
                # AJ uczelni flagowane jako „spoza pliku" (znane ograniczenie).
                "ostrzezenie_odpiecia": pary_z_pliku_puste and odpiecia_count > 0,
                "stan": parent.stan,
                "moze_zatwierdzic": (
                    parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY
                ),
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
        return self.parent_object.odpiecia.select_related(
            "autor_jednostka__autor",
            "autor_jednostka__autor__tytul",
            "autor_jednostka__jednostka",
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(parent_object=self.parent_object, **kwargs)


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

    def get(self, request, *args, **kwargs):
        parent = self.parent_object
        uczelnia = Uczelnia.objects.get_single_uczelnia_or_none()
        decyzje = list(self._decyzje())
        ctx = {
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
            "DECYZJA_AKCEPTUJ": ImportPracownikowJednostka.DECYZJA_AKCEPTUJ,
            "DECYZJA_MAPUJ": ImportPracownikowJednostka.DECYZJA_MAPUJ,
            "DECYZJA_POMIN": ImportPracownikowJednostka.DECYZJA_POMIN,
        }
        return render(request, self.template_name, ctx)

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
        decyzje = list(parent.jednostki_do_decyzji.all())
        # Walidacja: „mapuj na istniejącą" bez wskazanej jednostki docelowej to
        # cicha pułapka — integracja zostawiłaby te wiersze niedopasowane.
        # Alarmuj i NIE zapisuj, dopóki user nie wskaże celu.
        bez_celu = [
            dec.nazwa_zrodlowa
            for dec in decyzje
            if request.POST.get(f"dec_{dec.pk}_decyzja")
            == ImportPracownikowJednostka.DECYZJA_MAPUJ
            and not (request.POST.get(f"dec_{dec.pk}_wybrana") or "")
        ]
        if bez_celu:
            messages.error(
                request,
                'Wybierz jednostkę docelową w kolumnie „Mapuj na" dla: '
                + ", ".join(bez_celu),
            )
            return HttpResponseRedirect(
                reverse("import_pracownikow:jednostki", kwargs={"pk": parent.pk})
            )
        for dec in decyzje:
            pref = f"dec_{dec.pk}_"
            decyzja = request.POST.get(pref + "decyzja")
            if decyzja in prawidlowe:
                dec.decyzja = decyzja
            parent_id = request.POST.get(pref + "parent") or ""
            dec.wybrany_parent = (
                Jednostka.objects.filter(pk=parent_id).first() if parent_id else None
            )
            mapuj_id = request.POST.get(pref + "wybrana") or ""
            dec.wybrana_jednostka = (
                Jednostka.objects.filter(pk=mapuj_id).first() if mapuj_id else None
            )
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
            mapuj_id = request.POST.get(pref + "wybrana") or ""
            dec.wybrany_tytul = (
                Tytul.objects.filter(pk=mapuj_id).first() if mapuj_id else None
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

    ``zakres`` (POST) wybiera co integracja utworzy: pełny import (domyślne),
    same jednostki, albo jednostki + tytuły (bez osób). Trzy przyciski na hubie
    posyłają odpowiednią wartość. Nieznana/brakująca wartość → PELNY (bezpieczny
    domyślny — zachowanie sprzed tej funkcji).
    """

    _ZAKRESY_PRAWIDLOWE = {z for z, _ in ImportPracownikow.ZAKRES_CHOICES}

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        zakres = request.POST.get("zakres", ImportPracownikow.ZAKRES_PELNY)
        if zakres not in self._ZAKRESY_PRAWIDLOWE:
            zakres = ImportPracownikow.ZAKRES_PELNY
        obj.stan = ImportPracownikow.STAN_ZATWIERDZONY
        obj.zakres_integracji = zakres
        obj.save(update_fields=["stan", "zakres_integracji"])
        return super().post(request, *args, **kwargs)


class RestartAnalizaView(_PkOwnerRestartMixin):
    """Cofa import do stanu ``zmapowany`` i uruchamia analizę od nowa.

    Ustawiamy stan na ``zmapowany`` PRZED wywołaniem bazowego POST-a, żeby
    ``on_restart()`` skasował istniejące wiersze podglądu (dry-run od zera).
    """

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.stan = ImportPracownikow.STAN_ZMAPOWANY
        obj.save(update_fields=["stan"])
        return super().post(request, *args, **kwargs)
