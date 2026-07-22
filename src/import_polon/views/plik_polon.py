from braces.views import GroupRequiredMixin
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.views.generic import DetailView, ListView
from liveops.views import CreateLiveOperationView, RestartView

from import_polon.forms import NowyImportForm, WierszImportuPlikuPolonFilterForm
from import_polon.models import ImportPlikuPolon


class ZapiszDoBazyMixin(LoginRequiredMixin, DetailView):
    """Domknięcie dry-runa zapisem do bazy.

    Gdy import uruchomiono bez zapisu (``zapisz_zmiany_do_bazy=False``), ta akcja
    przestawia flagę na ``True`` i resetuje obiekt do ponownego uruchomienia —
    „taki reset, ALE tym razem modyfikuj bazę". GET pokazuje stronę
    potwierdzenia; dopiero POST modyfikuje bazę (prefetch/robot nie wywoła
    zapisu). ``on_restart()`` kasuje wiersze-dzieci, ``reset_liveops_state()``
    czyści stan operacji; ponowny ``enqueue()`` — tym razem z zapisem.

    Owner-scope własnym ``get_queryset`` (bez ``long_running`` — Faza 4 wymaga
    braku importów z tamtego pakietu). Bramka grupy dochodzi w podklasach
    (``GroupRequiredMixin`` przez ``BaseImportPlikuPolonMixin``).
    """

    template_name = "import_polon/potwierdz_zapis_do_bazy.html"

    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user)

    @transaction.atomic
    def post(self, *args, **kwargs):
        # select_for_update: blokuje wiersz na czas transakcji, więc dwa
        # równoległe POST-y nie przejdą obu przez guard i nie odpalą podwójnego
        # zapisu — drugi czeka, po commicie widzi już zapisz_zmiany_do_bazy=True.
        self.object = self.get_object(self.get_queryset().select_for_update())
        # Guard: domknąć zapisem można tylko dry-run zakończony POMYŚLNIE —
        # użytkownik musiał zobaczyć podgląd. Odsiewa import w trakcie, zakończony
        # błędem oraz już zapisany do bazy (ochrona przed podwójnym zapisem).
        if self.object.finished_successfully and not self.object.zapisz_zmiany_do_bazy:
            self.object.zapisz_zmiany_do_bazy = True
            self.object.on_restart()  # kasuje wiersze-dzieci poprzedniego runu
            pola = self.object.reset_liveops_state()
            self.object.save(update_fields=["zapisz_zmiany_do_bazy", *pola])
            # ``enqueue()`` przy RUNNER="celery" woła .delay() BEZ on_commit —
            # w bloku atomic worker mógłby czytać stan sprzed commitu. Odraczamy
            # do on_commit, żeby ponowny przebieg widział flagę + wyczyszczony
            # stan już utrwalone w bazie.
            transaction.on_commit(self.object.enqueue)
        # Stary „.." (router URL) kasowany w tej fazie → 404. Kierujemy na
        # centralną stronę live liveops.
        return HttpResponseRedirect(self.object.get_absolute_url())


class BaseImportPlikuPolonMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportPlikuPolon


class PokazImporty(BaseImportPlikuPolonMixin, ListView):
    """Lista importów bieżącego użytkownika (owner-scoped, zawężona do uczelni).

    Dawniej ``long_running.LongRunningOperationsView``; teraz zwykły ListView.
    Strona live (postęp/wynik) jest osobno, pod centralnym ``liveops:live``
    (link przez ``object.get_absolute_url``).
    """

    max_previous_ops = 10

    def get_queryset(self):
        # Multi-hosted: importy pokazuj tylko na stronie uczelni, z której
        # zostały zaczęte (uczelnia z requestu: domena→Site→Uczelnia). Stare
        # importy (uczelnia=None, sprzed pola) pokazuj wszędzie — wstecz-kompat.
        # Gdy uczelni nie da się rozstrzygnąć (single-host bez domeny / pusta
        # baza) → brak zawężenia (zachowanie wsteczne).
        #
        # Kasowanie starych operacji (max_previous_ops) robimy PO zawężeniu,
        # per-uczelnia — inaczej wejście na stronę uczelni X kasowałoby stare
        # importy uczelni Y właściciela.
        from bpp.models import Uczelnia

        qset = self.model.objects.filter(owner=self.request.user).order_by(
            "-created_on"
        )

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is not None:
            qset = qset.filter(Q(uczelnia=uczelnia) | Q(uczelnia__isnull=True))

        for elem in qset[self.max_previous_ops :]:
            elem.delete()

        return qset


class UtworzImportPlikuPolon(BaseImportPlikuPolonMixin, CreateLiveOperationView):
    form_class = NowyImportForm

    def form_valid(self, form):
        # Multi-hosted: przypnij import do uczelni z requestu (domena→Site→
        # Uczelnia). Zawęża późniejszą walidację ZATRUDNIENIE, dopasowanie
        # autora i raport niezmatchowanych do tej jednej uczelni. Gdy nie da
        # się rozstrzygnąć (single-host bez domeny / pusta baza) → None →
        # zachowanie wsteczne bez zawężenia. Owner + save + enqueue + redirect
        # na get_absolute_url robi bazowe CreateLiveOperationView.form_valid.
        from bpp.models import Uczelnia

        form.instance.uczelnia = Uczelnia.objects.get_for_request(self.request)
        return super().form_valid(form)


class _PkOwnerRestartMixin(GroupRequiredMixin, RestartView):
    """Gejtowany restart importu (POLON/absencji).

    URL restartu ma tylko ``pk`` (bez ``op_type``), więc nadpisujemy
    ``OpTypeObjectMixin.get_object`` i rozwiązujemy konkretny model wprost,
    owner-scoped.

    Bramka grupy (precedens #508 F4): liveops ``BaseLiveOperationMixin`` gejtuje
    tylko gdy ``LIVEOPS["REQUIRED_GROUP"]`` ustawione — w BPP NIE jest, więc
    tamta bramka to no-op. Dokładamy braces ``GroupRequiredMixin`` (konwencja
    projektu, jak reszta widoków importu). Restart z ``zapisz_zmiany_do_bazy=
    True`` PONOWNIE zapisuje do bazy (akcja destrukcyjna) — nie zostawiamy go
    owner-only.
    """

    model = ImportPlikuPolon
    group_required = "wprowadzanie danych"

    def get_object(self, queryset=None):
        return get_object_or_404(
            self.model, pk=self.kwargs["pk"], owner=self.request.user
        )


class RestartImportView(_PkOwnerRestartMixin):
    model = ImportPlikuPolon


class ZapiszDoBazyImportView(BaseImportPlikuPolonMixin, ZapiszDoBazyMixin):
    pass


class ImportPolonResultsView(BaseImportPlikuPolonMixin, ListView):
    # paginate_by OBOWIĄZKOWE: szablon renderuje stronicowanie, a bez tego
    # tysiące wierszy trafiłoby na jedną stronę (cicha utrata paginacji).
    paginate_by = 25

    @cached_property
    def parent_object(self):
        return get_object_or_404(
            ImportPlikuPolon, pk=self.kwargs["pk"], owner=self.request.user
        )

    def get_queryset(self):
        queryset = self.parent_object.get_details_set()

        # Get filter parameters
        autor_wiersz = self.request.GET.get("autor_wiersz", "").strip()
        dyscyplina = self.request.GET.get("dyscyplina", "").strip()
        grupa_stanowisk = self.request.GET.get("grupa_stanowisk", "").strip()
        pokaz_tylko_roznice = self.request.GET.get("pokaz_tylko_roznice", "")

        # Apply combined autor/wiersz filter
        if autor_wiersz:
            try:
                # Try to convert to int for row number filtering
                wiersz_int = int(autor_wiersz)
                queryset = queryset.filter(nr_wiersza=wiersz_int)
            except ValueError:
                # If not a number, search in author fields and result
                queryset = queryset.filter(
                    Q(dane_z_xls__NAZWISKO__icontains=autor_wiersz)
                    | Q(dane_z_xls__IMIE__icontains=autor_wiersz)
                    | Q(rezultat__icontains=autor_wiersz)
                )

        # Apply combined dyscyplina filter (searches both dyscyplina and subdyscyplina)
        if dyscyplina:
            queryset = queryset.filter(
                Q(dane_z_xls__DYSCYPLINA_N__icontains=dyscyplina)
                | Q(dane_z_xls__DYSCYPLINA_N_KOLEJNA__icontains=dyscyplina)
            )

        # Apply grupa stanowisk filter
        if grupa_stanowisk:
            queryset = queryset.filter(
                dane_z_xls__GRUPA_STANOWISK__icontains=grupa_stanowisk
            )

        # Apply "show only differences" filter
        if pokaz_tylko_roznice:
            queryset = queryset.exclude(
                rezultat__startswith="W BPP jest identycznie jak w XLSX"
            )

        return queryset

    def get_context_data(self, **kwargs):
        # object=self.parent_object OBOWIĄZKOWE: szablon woła {% url ... object.pk %}
        # (bez tego NoReverseMatch).
        context = super().get_context_data(object=self.parent_object, **kwargs)

        # Get base queryset for form choices
        base_queryset = self.parent_object.get_details_set()

        # Create filter form with current GET parameters and queryset for choices
        filter_form = WierszImportuPlikuPolonFilterForm(
            data=self.request.GET or None, queryset=base_queryset
        )

        context["filter_form"] = filter_form

        # Add flag to indicate if filtering is active
        context["is_filtered"] = bool(
            self.request.GET.get("autor_wiersz")
            or self.request.GET.get("dyscyplina")
            or self.request.GET.get("grupa_stanowisk")
            or self.request.GET.get("pokaz_tylko_roznice")
        )

        # Autorzy z dyscyplinami dla roku importu, których nie było w pliku.
        # Multi-hosted: zawężone do autorów związanych z uczelnią importu przez
        # realną jednostkę (obecnie lub historycznie; jednostki obce pomijane —
        # patrz ImportPlikuPolon.autorzy_niezmatchowani) — bez tego raport
        # wyciekałby autorów innych uczelni współistniejących w bazie.
        unmatched_autor_dyscyplina = self.parent_object.autorzy_niezmatchowani()

        context["unmatched_autor_dyscyplina"] = unmatched_autor_dyscyplina
        context["unmatched_count"] = unmatched_autor_dyscyplina.count()

        return context
