# Create your views here.

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.db.models import (
    Case,
    Count,
    IntegerField,
    Prefetch,
    Q,
    Value,
    When,
)
from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import FormView, ListView
from liveops.views import CreateLiveOperationView, RestartView

from bpp.models import (
    Jednostka,
    Tytul,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
)
from import_common.core.autor import znajdz_kandydatow_autora
from import_common.exceptions import HeaderNotFoundException
from import_pracownikow.forms import MapowanieForm, NowyImportForm
from import_pracownikow.mapping import dopasuj_profil
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
    ImportPracownikowRowKandydat,
    ProfilMapowania,
    wiersz_kwalifikuje_do_przepiecia,
)
from import_pracownikow.pewnosc import (
    STATUS_BRAK,
    STATUS_TWARDY,
    STATUS_WIELU,
    oblicz_status_pewnosci,
    odtworz_autor_jednostka,
    wybierz_autora_z_kandydatow,
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
        # on_restart() kasuje wiersze podglądu (stan==zmapowany) — inaczej
        # ponowna analiza by je zduplikowała.
        obj.on_restart()
        # Reset pól operacji liveops (jak RestartView.post) — inaczej po
        # anulowanym/zakończonym przebiegu enqueue rusza z brudnym stanem
        # (cancel_requested=True → natychmiastowe „cancelled").
        pola_liveops = obj.reset_liveops_state()
        obj.save(update_fields=["mapowanie_kolumn", "stan"] + pola_liveops)

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
        row.wybrany_kandydat = autor
        row.autor = autor
        row.confidence = STATUS_TWARDY
        # G2: zmiana autora unieważnia opt-in przepięcia poprzedniego autora.
        row.przepnij_prace = False

        # Materializacja autora MUSI odtworzyć powiązanie Autor_Jednostka tak
        # jak faza analizy (analyze._przetworz_wiersz) I zdjąć ewentualny
        # nieaktualny wpis diff od poprzedniego autora — inaczej integrate() →
        # _integrate_autor_jednostka() zrobi aj.save() na None (AttributeError)
        # albo utworzy AJ dla złego autora. `row.autor` jest ustawiony wyżej,
        # więc helper może bezpiecznie wołać check_if_integration_needed().
        odtworz_autor_jednostka(row, autor)
        row.save(
            update_fields=[
                "wybrany_kandydat",
                "autor",
                "confidence",
                "autor_jednostka",
                "diff_do_utworzenia",
                "zmiany_potrzebne",
                "przepnij_prace",
            ]
        )
        return self._render_wiersz()


def _rematch_wiersz(row, imiona, nazwisko, tytul):
    """Ponawia dopasowanie autora dla skorygowanego wiersza (synchronicznie).
    Nadpisuje confidence/autor/kandydatów, tytuł (FK) i dane_znormalizowane;
    odtwarza Autor_Jednostka dla NOWEGO autora i przelicza zmiany_potrzebne.
    Ścieżka bez ID (korekta dotyczy rozbicia nazwiska)."""
    kandydaci = znajdz_kandydatow_autora(imiona, nazwisko)
    status = oblicz_status_pewnosci(kandydaci, match_po_id=False)
    autor = wybierz_autora_z_kandydatow(kandydaci, status)

    dane = dict(row.dane_znormalizowane or {})
    dane["imię"] = imiona
    dane["nazwisko"] = nazwisko
    if tytul:
        dane["tytuł_stopień"] = tytul
    else:
        dane.pop("tytuł_stopień", None)
    row.dane_znormalizowane = dane

    # Korekta tytułu MUSI trafić do FK row.tytul — integracja czyta row.tytul_id
    # (z analizy), nie JSON; bez tego do bazy poszedłby stary tytuł.
    # G4: filter().first() (nie .get()) — wejście od usera; ten sam string bywa
    # `nazwa` jednego tytułu i `skrot` innego (unique tylko osobno), więc .get()
    # rzuciłby MultipleObjectsReturned (500). None gdy brak dopasowania.
    if tytul:
        row.tytul = Tytul.objects.filter(Q(nazwa=tytul) | Q(skrot=tytul)).first()
    else:
        row.tytul = None

    row.korekta_uzytkownika = {
        "imiona": imiona,
        "nazwisko": nazwisko,
        "tytul": tytul,
    }
    row.confidence = status
    row.autor = autor
    # G2: zmiana autora unieważnia opt-in przepięcia poprzedniego autora.
    row.przepnij_prace = False
    row.wybrany_kandydat = None

    # Materializacja NOWEGO autora → PRZELICZ Autor_Jednostka od zera (nie ufaj
    # staremu row.autor_jednostka od poprzedniego autora) przez wspólny helper,
    # który ZAWSZE zdejmuje uśpiony wpis diff od poprzedniego autora. Bez AJ
    # integrate() → _integrate_autor_jednostka() zrobiłby aj.save() na None
    # (AttributeError). `row.autor` jest ustawiony wyżej.
    if autor is None:
        # brak/wielu po korekcie: też zdejmij uśpiony wpis AJ od poprzedniego
        # autora (inaczej integracja utworzy AJ dla już-nie-autora wiersza),
        # wyzeruj powiązanie, nic do integracji dopóki user nie rozstrzygnie.
        row.diff_do_utworzenia.pop("autor_jednostka", None)
        row.autor_jednostka = None
        row.zmiany_potrzebne = False
    else:
        odtworz_autor_jednostka(row, autor)

    row.save()
    # zapisz_dla kasuje starych kandydatów i wstawia nowych; dla nie-wielu
    # przekazujemy [] (tylko czyszczenie — wiersz zszedł z „wielu").
    ImportPracownikowRowKandydat.zapisz_dla(
        row, kandydaci if status == STATUS_WIELU else []
    )


class EdytujWierszView(_WierszImportuMixin):
    """POST (HTMX): korekta rozbicia imiona/nazwisko/tytuł → zapis
    ``korekta_uzytkownika`` + synchroniczny re-match → partial wiersza."""

    def post(self, request, *args, **kwargs):
        blad = self._blad_jesli_nie_podglad()
        if blad is not None:
            return blad
        row = self.row
        imiona = (request.POST.get("imiona") or "").strip()
        nazwisko = (request.POST.get("nazwisko") or "").strip()
        tytul = (request.POST.get("tytul") or "").strip()
        if not nazwisko:
            return HttpResponseBadRequest("Nazwisko jest wymagane.")
        _rematch_wiersz(row, imiona, nazwisko, tytul)
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
        parent = self.parent_object
        odpiecia = parent.odpiecia.select_related(
            "autor_jednostka__autor",
            "autor_jednostka__autor__tytul",
            "autor_jednostka__jednostka",
        )
        ctx = super().get_context_data(
            parent_object=parent,
            odpiecia=odpiecia,
            **kwargs,
        )
        if parent.stan == ImportPracownikow.STAN_PRZEANALIZOWANY:
            oznacz_przepiecie_prac(list(ctx["object_list"]), parent)
        return ctx


class _PkOwnerRestartMixin(RestartView):
    """Wspólny ``get_object`` dla widoków restartu — URL ma tylko ``pk``
    (bez ``op_type``), więc nadpisujemy ``OpTypeObjectMixin.get_object``
    i rozwiązujemy konkretny model wprost, owner-scoped."""

    model = ImportPracownikow

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
    """

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.stan = ImportPracownikow.STAN_ZATWIERDZONY
        obj.save(update_fields=["stan"])
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
