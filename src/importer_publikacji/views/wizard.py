"""Class-based views wizarda importera publikacji.

Każdy widok odpowiada jednemu krokowi (Index → Fetch → Verify → Source →
Authors → Review → Create → Done) plus boczne akcje na autorach i
anulowanie sesji.
"""

from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from bpp.models import Uczelnia
from bpp.views.api import ostatnia_dyscyplina, ostatnia_jednostka

from ..forms import (
    AuthorMatchForm,
    FetchForm,
    PunktacjaForm,
    SourceForm,
    VerifyForm,
)
from ..models import (
    EntryStatus,
    ImportedAuthor,
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)
from ..permissions import ImporterPermissionMixin
from ..providers import InputMode, get_provider
from ..tasks import create_publication_task, fetch_session_task
from .authors import (
    _create_single_author,
    _create_unmatched_authors,
    _orcid_settable_qs,
)
from .helpers import (
    BATCH_DETAIL,
    SESSIONS_PARTIAL,
    STEP_DONE,
    STEP_FETCH,
    STEP_LANDING,
    _fetch_context,
    _is_htmx_partial,
    _landing_context,
    _push_url,
    _render_full_page,
    _sessions_list_context,
    _with_breadcrumbs_oob,
)
from .steps import (
    _is_chapter,
    _render_authors_step,
    _render_pbn_step,
    _render_punktacja_step,
    _render_review_step,
    _render_source_step,
    _render_verify_full,
    _render_verify_step,
)


class SessionListView(ImporterPermissionMixin, View):
    """Lista sesji z filtrami, sortowaniem i paginacją.

    Dostępna jako samodzielna strona (link z paska „importy w toku" na
    kaflowej stronie głównej — patrz ``IndexView``) — stąd
    ``standalone=True`` w kontekście, żeby partial doklejał link powrotny
    (przy embedowaniu w kroku fetch tego klucza nie ma, więc link nie
    dubluje się tam, gdzie i tak już jesteśmy na stronie importera).
    """

    def get(self, request):
        ctx = _sessions_list_context(request)
        ctx["standalone"] = True
        if _is_htmx_partial(request):
            return render(request, SESSIONS_PARTIAL, ctx)
        return _render_full_page(request, SESSIONS_PARTIAL, ctx)


class IndexView(ImporterPermissionMixin, View):
    """Strona główna importera: kafelki dostawców danych albo (z parametrem
    ``?provider=``) formularz pobrania danych od konkretnego dostawcy.

    ``?provider=`` (opcjonalnie z ``?identifier=``) jest zachowane wstecznie
    kompatybilnie — używają go istniejące linki z adminowych list zmian
    (Wydawnictwo_Ciagle/Zwarte „Dodaj z CrossRef API") oraz przycisk
    „Użyj importera" w adminie Zgłoszeń Publikacji. Kafle na stronie
    głównej celują w ten sam parametr, więc kliknięcie kafla renderuje
    dokładnie tę samą stronę co bezpośredni deep-link/refresh/Back.
    """

    def get(self, request):
        if request.GET.get("provider"):
            return self._get_fetch_form(request)
        return self._get_landing(request)

    def _get_fetch_form(self, request):
        initial = {"provider": request.GET["provider"]}
        if request.GET.get("identifier"):
            initial["identifier"] = request.GET["identifier"]
        form = FetchForm(initial=initial)

        ctx = _fetch_context(form, request=request)
        ctx.update(_sessions_list_context(request))
        if _is_htmx_partial(request):
            response = render(request, STEP_FETCH, ctx)
            return _with_breadcrumbs_oob(response, request)
        return _render_full_page(request, STEP_FETCH, ctx)

    def _get_landing(self, request):
        ctx = _landing_context(request)
        if _is_htmx_partial(request):
            response = render(request, STEP_LANDING, ctx)
            return _with_breadcrumbs_oob(response, request)
        return _render_full_page(request, STEP_LANDING, ctx)


def _hx_or_redirect(request, url):
    """Zwróć ``HX-Redirect`` dla żądań HTMX, w przeciwnym razie zwykły 302."""
    if request.headers.get("HX-Request"):
        response = HttpResponse(status=200)
        response["HX-Redirect"] = url
        return response
    return HttpResponseRedirect(url)


def _date_to_iso(value):
    """``datetime.date`` → string ISO ``YYYY-MM-DD`` (JSON-owalny) lub None."""
    return value.isoformat() if value else None


def _patent_guard(request, session):
    """Guard kroków Source/PBN: patenty je pomijają.

    Gdy sesja jest patentem, zwróć przekierowanie na właściwy krok
    (``get_continue_url`` po gałęzi patentowej → Authors/Review) zamiast
    pozwolić widokowi Source/PBN przetworzyć request (co skorumpowałoby sesję
    patentową — zapis ``zrodlo``/``pbn_mongo_id``). Zwraca ``None`` dla
    nie-patentów (widok działa normalnie).
    """
    if session.rodzaj_rekordu == ImportSession.RodzajRekordu.PATENT:
        # get_continue_url zwraca None dla statusów spoza mapy (np. CANCELLED)
        # — nie przekierowuj wtedy na literalne "None", tylko na listę sesji.
        url = session.get_continue_url() or reverse("importer_publikacji:index")
        return _hx_or_redirect(request, url)
    return None


def _create_batch(request, provider_name, normalized, records):
    """Utwórz ``MultipleWorksImport`` + wszystkie jego wpisy naraz."""
    batch = MultipleWorksImport.objects.create(
        created_by=request.user,
        uczelnia=Uczelnia.objects.get_for_request(request),
        provider_name=provider_name,
        raw_input=normalized,
    )
    MultipleWorksImportEntry.objects.bulk_create(
        [
            MultipleWorksImportEntry(
                parent=batch,
                order=i,
                raw_bibtex=rec.raw,
                title=rec.title,
                parse_error="" if rec.ok else rec.error,
            )
            for i, rec in enumerate(records)
        ]
    )
    return batch


def _start_import_session(request, provider_name, identifier):
    """Utwórz sesję importu (FETCHING) + wystartuj task fetch.

    BEZ guardu double-click po ``identifier`` — używane też przez import
    pojedynczego wpisu paczki, gdzie duplikaty wpisów są dozwolone, a przed
    podwójnym startem chroni ``entry.session`` po stronie wołającego.
    """
    session = ImportSession.objects.create(
        created_by=request.user,
        uczelnia=Uczelnia.objects.get_for_request(request),
        provider_name=provider_name,
        identifier=identifier,
        status=ImportSession.Status.FETCHING,
        raw_data={},
        normalized_data={},
    )
    task = fetch_session_task.delay(session.pk, request.user.pk)
    session.celery_task_id = task.id
    session.save(update_fields=["celery_task_id"])
    return session


class FetchView(ImporterPermissionMixin, View):
    """Walidacja identyfikatora + utworzenie sesji + enqueue Celery task-a."""

    def post(self, request):
        form = FetchForm(request.POST)
        if not form.is_valid():
            return render(request, STEP_FETCH, _fetch_context(form))

        provider_name = form.cleaned_data["provider"]
        request.session["importer_last_provider"] = provider_name
        provider = get_provider(provider_name)

        if provider.input_mode == InputMode.TEXT:
            raw_input = form.cleaned_data["text_input"]
            error_field = "text_input"
        else:
            raw_input = form.cleaned_data["identifier"]
            error_field = "identifier"

        normalized = provider.validate_identifier(raw_input)
        if normalized is None:
            help_hint = getattr(provider, "input_help_text", "")
            placeholder = getattr(provider, "input_placeholder", "")
            msg = f"Nie rozpoznano formatu dla dostawcy „{provider.name}”."
            if help_hint:
                msg += f" Oczekiwany format: {help_hint}"
            if placeholder:
                msg += f" Przykład: {placeholder}"
            form.add_error(error_field, msg)
            return render(request, STEP_FETCH, _fetch_context(form))

        # Wielo-rekordowe wejście (BibTeX z ≥2 wpisami) → paczka, nie
        # pojedyncza sesja. Pojedyncze sesje powstają leniwie przy
        # imporcie wpisu.
        records = provider.split_input(normalized)
        if len(records) >= 2:
            batch = _create_batch(request, provider_name, normalized, records)
            url = reverse(
                "importer_publikacji:batch-detail",
                kwargs={"batch_id": batch.pk},
            )
            return _hx_or_redirect(request, url)

        # Idempotency (C2): jesli juz jest sesja in-flight tego samego usera
        # dla tego samego (provider, identifier), nie startuj kolejnej —
        # zredirectuj do istniejacej. Defense przed double-click i refresh.
        recent_in_flight = (
            ImportSession.objects.filter(
                created_by=request.user,
                provider_name=provider_name,
                identifier=normalized,
                status__in=[
                    ImportSession.Status.FETCHING,
                    ImportSession.Status.FETCHED,
                ],
            )
            .order_by("-created")
            .first()
        )
        if recent_in_flight is not None:
            return _hx_or_redirect(request, recent_in_flight.get_continue_url())

        session = _start_import_session(request, provider_name, normalized)

        url = reverse(
            "importer_publikacji:task-status",
            kwargs={"session_id": session.pk},
        )
        return _hx_or_redirect(request, url)


class MultipleWorksImportDetailView(ImporterPermissionMixin, View):
    """Lista wpisów paczki z per-wpis statusem i akcjami (drip import)."""

    def get(self, request, batch_id):
        batch = self.get_scoped_or_404(MultipleWorksImport, pk=batch_id)
        entries = list(batch.entries.select_related("session"))
        # Sweep zombie: martwy worker zostawia sesje w FETCHING/CREATING —
        # bez tego wpis wisialby "w toku" i paczka nigdy nie bylaby gotowa.
        for entry in entries:
            if entry.session is not None and entry.session.is_stalled():
                entry.session.mark_stalled()
        return _render_full_page(
            request,
            BATCH_DETAIL,
            {"batch": batch, "entries": entries, "progress": batch.progress},
        )


class BatchEntryImportView(ImporterPermissionMixin, View):
    """Wystartuj import pojedynczego wpisu paczki (leniwy drip)."""

    # Statusy TERMINALNE (odwrotność in-flight): sesja w którymkolwiek z nich
    # jest skończona/martwa, więc wolno wystartować import wpisu od nowa.
    # NB: NIE mylić z ``ImportSession._INFLIGHT_STATUSES`` (FETCHING/CREATING),
    # które trzyma statusy przeciwne — stąd celowo inna, jednoznaczna nazwa.
    _TERMINAL_STATUSES = (
        ImportSession.Status.COMPLETED,
        ImportSession.Status.IMPORT_FAILED,
        ImportSession.Status.CANCELLED,
    )

    def post(self, request, entry_id):
        entry = self.get_scoped_or_404(
            MultipleWorksImportEntry, uczelnia_path="parent__uczelnia", pk=entry_id
        )
        if entry.status == EntryStatus.IMPORTED:
            # Wpis juz zaimportowany — nie startuj kolejnej sesji (defense
            # przed stalym formularzem "Importuj" w drugiej karcie albo
            # powtorzonym POST-em), tylko odesle do gotowej strony wpisu.
            return HttpResponseRedirect(entry.session.get_continue_url())
        if entry.parse_error:
            return HttpResponseBadRequest("Wpis uszkodzony — nie można zaimportować.")
        session = entry.session
        if (
            session is not None
            and session.status not in self._TERMINAL_STATUSES
            and not session.is_stalled()
        ):
            # Juz sie importuje — nie startuj drugiej sesji (defense double-click).
            return HttpResponseRedirect(session.get_continue_url())
        session = _start_import_session(
            request, entry.parent.provider_name, entry.raw_bibtex
        )
        entry.session = session
        entry.save(update_fields=["session"])
        url = reverse(
            "importer_publikacji:task-status",
            kwargs={"session_id": session.pk},
        )
        return HttpResponseRedirect(url)


class BatchEntrySkipView(ImporterPermissionMixin, View):
    """Pomiń lub przywróć wpis paczki (toggle)."""

    def post(self, request, entry_id):
        entry = self.get_scoped_or_404(
            MultipleWorksImportEntry, uczelnia_path="parent__uczelnia", pk=entry_id
        )
        if entry.status == EntryStatus.IMPORTED:
            return HttpResponseBadRequest("Nie można pominąć zaimportowanego wpisu.")
        entry.skipped = not entry.skipped
        entry.save(update_fields=["skipped"])
        url = reverse(
            "importer_publikacji:batch-detail",
            kwargs={"batch_id": entry.parent_id},
        )
        return HttpResponseRedirect(url)


class VerifyView(ImporterPermissionMixin, View):
    """Weryfikacja typu publikacji i duplikatów."""

    def get(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        if _is_htmx_partial(request):
            return _render_verify_step(request, session)
        return _render_verify_full(request, session)

    def post(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        form = VerifyForm(request.POST)

        if not form.is_valid():
            return _render_verify_step(request, session, form=form)

        rodzaj = form.cleaned_data["rodzaj_rekordu"]
        session.rodzaj_rekordu = rodzaj
        # back-compat: downstream (dispatch tworzenia, punktacja, krok źródła)
        # nadal czyta boolean; wyliczamy go z radia.
        session.jest_wydawnictwem_zwartym = rodzaj == ImportSession.RodzajRekordu.ZWARTE
        # Rok wpisany/poprawiony przez operatora → jedyne źródło prawdy o roku.
        # Ustawiamy go tu (najwcześniejszy edytowalny krok), żeby działały
        # kroki zależne od roku: dopasowanie dyscyplin autorów, punktacja
        # źródła, sugestia punktów, tworzenie rekordu.
        session.normalized_data["year"] = form.cleaned_data["rok"]
        session.status = ImportSession.Status.VERIFIED
        session.modified_by = request.user

        if rodzaj == ImportSession.RodzajRekordu.PATENT:
            self._apply_patent_fields(session, form)
            session.save()
            # Patent pomija krok Source (brak źródła/wydawcy) → prosto Autorzy.
            return _render_authors_step(request, session)

        session.charakter_formalny = form.cleaned_data["charakter_formalny"]
        session.typ_kbn = form.cleaned_data["typ_kbn"]
        session.jezyk = form.cleaned_data["jezyk"]
        session.save()

        return _render_source_step(request, session)

    @staticmethod
    def _apply_patent_fields(session, form):
        """Zapisz pola patentowe do ``normalized_data`` i wyczyść stale stan
        nie-patentowy (scenariusz toggle CIAGLE/ZWARTE → PATENT).

        Wszystkie klucze patentowe są zapisywane bezwarunkowo (nawet jako
        ``None``), żeby prefill kroku Verify odróżnił „operator wyczyścił pole"
        (klucz obecny = None) od „pierwsze wejście" (klucz nieobecny → dozwolony
        best-effort z BibTeX).
        """
        cd = form.cleaned_data
        # Patent hardkoduje charakter_formalny/jezyk i nie ma typ_kbn — wyzeruj
        # ewentualne wartości sesyjne (żeby _create_publication nie zbudował
        # z nich common_fields trujących Patent.objects.create()).
        session.charakter_formalny = None
        session.typ_kbn = None
        session.jezyk = None
        # Wyczyść pola źródła/PBN — stale wartości (toggle po kroku Source/PBN)
        # inaczej: uzupelnij_punktacje_z_zrodla wlałaby punktację czasopisma do
        # patentu, a stale pbn_mongo_id → _link_pbn_uid ustawiłby pole pbn_uid,
        # którego Patent NIE MA (create task by się wywalił).
        session.zrodlo = None
        session.wydawca = None
        session.wydawnictwo_nadrzedne = None
        session.wydawnictwo_nadrzedne_w_pbn = None
        session.matched_data.pop("pbn_mongo_id", None)
        session.matched_data.pop("wydawca_opis", None)
        # Punkty policzone na ścieżce czasopisma nie dotyczą patentu (brak
        # źródła) — wyczyść, żeby krok Punktacja patentu nie prefillował ich.
        session.matched_data.pop("punkty_kbn", None)

        nd = session.normalized_data
        nd["patent_number"] = cd.get("numer_zgloszenia") or None
        nd["filing_date"] = _date_to_iso(cd.get("data_zgloszenia"))
        nd["patent_grant_number"] = cd.get("numer_prawa_wylacznego") or None
        nd["grant_date"] = _date_to_iso(cd.get("data_decyzji"))
        nd["patent_holder"] = cd.get("uprawniony") or None
        rodzaj_prawa = cd.get("rodzaj_prawa")
        nd["rodzaj_prawa_id"] = rodzaj_prawa.pk if rodzaj_prawa else None
        nd["wdrozenie"] = cd.get("wdrozenie")
        wydzial = cd.get("wydzial")
        nd["wydzial_id"] = wydzial.pk if wydzial else None


class SourceView(ImporterPermissionMixin, View):
    """Dopasowanie źródła (czasopisma/wydawcy)."""

    def get(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        guard = _patent_guard(request, session)
        if guard is not None:
            return guard
        if _is_htmx_partial(request):
            return _render_source_step(request, session)
        from .steps import _render_source_full

        return _render_source_full(request, session)

    def post(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        guard = _patent_guard(request, session)
        if guard is not None:
            return guard
        form = SourceForm(request.POST)

        if not form.is_valid():
            return _render_source_step(request, session, form=form)

        if session.jest_wydawnictwem_zwartym:
            wydawca = form.cleaned_data.get("wydawca")
            wydawca_opis = form.cleaned_data.get("wydawca_opis", "")
            if not wydawca and not wydawca_opis.strip():
                form.add_error(
                    "wydawca",
                    "Podaj wydawcę lub wpisz szczegóły wydawcy.",
                )
                return _render_source_step(request, session, form=form)

            # Rozdział wymaga wydawnictwa nadrzędnego
            if _is_chapter(session):
                wn = form.cleaned_data.get("wydawnictwo_nadrzedne")
                wn_pbn = form.cleaned_data.get("wydawnictwo_nadrzedne_w_pbn")
                if not wn and not wn_pbn:
                    form.add_error(
                        "wydawnictwo_nadrzedne",
                        "Dla rozdziału wymagane jest wydawnictwo nadrzędne.",
                    )
                    return _render_source_step(request, session, form=form)
                if wn and wn_pbn:
                    form.add_error(
                        "wydawnictwo_nadrzedne",
                        "Podaj tylko jedno: wydawnictwo"
                        " nadrzędne lub wydawnictwo"
                        " nadrzędne w PBN.",
                    )
                    return _render_source_step(request, session, form=form)
        else:
            if not form.cleaned_data.get("zrodlo"):
                form.add_error(
                    "zrodlo",
                    "Źródło jest wymagane dla wydawnictwa ciągłego.",
                )
                return _render_source_step(request, session, form=form)

        session.zrodlo = form.cleaned_data["zrodlo"]
        session.wydawca = form.cleaned_data["wydawca"]
        session.matched_data["wydawca_opis"] = form.cleaned_data.get("wydawca_opis", "")
        session.wydawnictwo_nadrzedne = form.cleaned_data.get("wydawnictwo_nadrzedne")
        session.wydawnictwo_nadrzedne_w_pbn = form.cleaned_data.get(
            "wydawnictwo_nadrzedne_w_pbn"
        )
        session.status = ImportSession.Status.SOURCE_MATCHED
        session.modified_by = request.user
        session.save()

        return _render_authors_step(request, session)


class AuthorsView(ImporterPermissionMixin, View):
    """Lista autorów z paginacją."""

    def get(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        if _is_htmx_partial(request):
            return _render_authors_step(request, session)
        from .steps import _render_authors_full

        return _render_authors_full(request, session)


class AuthorCandidatesModalView(ImporterPermissionMixin, View):
    """Zwraca HTML partial z listą kandydatów dla ImportedAuthor.

    Używane w modalu edycji żeby pokazać użytkownikowi listę autorów
    BPP pasujących do importowanego — z metadanymi (pewnosc, powod,
    publikacji_count, ORCID, jednostka) i klikalnym wyborem.
    """

    def get(self, request, session_id, author_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)
        imported_author = get_object_or_404(
            ImportedAuthor, pk=author_id, session=session
        )
        candidates = imported_author.candidates.select_related(
            "autor", "autor__aktualna_jednostka"
        ).order_by("-pewnosc", "-publikacji_count")
        return render(
            request,
            "importer_publikacji/partials/modal_candidates.html",
            {
                "session": session,
                "author": imported_author,
                "candidates": candidates,
            },
        )


class AuthorInfoView(ImporterPermissionMixin, View):
    """Zwraca JSON z metadanymi autora BPP (pk, slug, orcid, pbn_uid_id)
    — używane w modalu edycji do aktualizacji linków do admina/BPP/PBN/
    ORCID po zmianie wybranego autora w select2.

    Parameter ``author_id`` to PK ``Autor`` (nie ``ImportedAuthor``).
    """

    def get(self, request, session_id, author_id):
        self.get_scoped_or_404(ImportSession, pk=session_id)
        from bpp.models import Autor

        autor = get_object_or_404(Autor, pk=author_id)
        return JsonResponse(
            {
                "pk": autor.pk,
                "slug": autor.slug,
                "display": str(autor),
                "orcid": autor.orcid or "",
                "pbn_uid_id": autor.pbn_uid_id or "",
            }
        )


class AuthorMatchView(ImporterPermissionMixin, View):
    """Aktualizacja dopasowania pojedynczego autora."""

    def post(self, request, session_id, author_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        imported_author = get_object_or_404(
            ImportedAuthor,
            pk=author_id,
            session=session,
        )

        form = AuthorMatchForm(request.POST)
        if not form.is_valid():
            return render(
                request,
                "importer_publikacji/partials/author_row.html",
                {
                    "session": session,
                    "author": imported_author,
                },
            )

        # "Zapisany jako" jest niezależne od stanu dopasowania —
        # user może chcieć ustawić zapis nawet dla niedopasowanego autora.
        zj = (form.cleaned_data.get("zapisany_jako") or "").strip()
        if zj:
            imported_author.zapisany_jako = zj

        # Typ autora (autor/redaktor) — również niezależny od dopasowania.
        typ = form.cleaned_data.get("typ")
        if typ is not None:
            imported_author.typ_ogolny = typ

        if form.cleaned_data.get("autor"):
            imported_author.matched_autor = form.cleaned_data["autor"]
            imported_author.match_status = ImportedAuthor.MatchStatus.MANUAL
            imported_author.matched_jednostka = form.cleaned_data.get("jednostka")
            imported_author.matched_dyscyplina = form.cleaned_data.get("dyscyplina")

            if imported_author.matched_dyscyplina:
                imported_author.dyscyplina_source = (
                    ImportedAuthor.DyscyplinaSource.MANUAL
                )

            if imported_author.matched_autor and not imported_author.matched_jednostka:
                imported_author.matched_jednostka = ostatnia_jednostka(
                    request,
                    imported_author.matched_autor,
                )
            if imported_author.matched_autor and not imported_author.matched_dyscyplina:
                year = session.normalized_data.get("year")
                if year:
                    dyscyplina = ostatnia_dyscyplina(
                        request,
                        imported_author.matched_autor,
                        year,
                    )
                    imported_author.matched_dyscyplina = dyscyplina
                    if dyscyplina:
                        imported_author.dyscyplina_source = (
                            ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA
                        )
        else:
            imported_author.match_status = ImportedAuthor.MatchStatus.UNMATCHED
            imported_author.matched_autor = None
            imported_author.matched_jednostka = None
            imported_author.matched_dyscyplina = None
            imported_author.dyscyplina_source = ""

        imported_author.save()

        return render(
            request,
            "importer_publikacji/partials/author_row.html",
            {
                "session": session,
                "author": imported_author,
            },
        )


class AuthorDeleteView(ImporterPermissionMixin, View):
    """Usuń pojedynczy wiersz importowanego autora z sesji.

    Freshdesk #332: gdy dostawca (CrossRef / DOI) zwrócił błędny lub
    pusty wpis autora, operator musi móc go usunąć, żeby import mógł
    przebiec bez niego. Usuwamy rekord ``ImportedAuthor`` — kolejne kroki
    odpytują ``session.authors``, więc usunięcie jest trwałe i wiersz nie
    trafi do tworzonego rekordu publikacji. Pozostała luka w polu
    ``order`` nie szkodzi — służy ono tylko do sortowania.
    """

    def post(self, request, session_id, author_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        imported_author = get_object_or_404(
            ImportedAuthor,
            pk=author_id,
            session=session,
        )
        imported_author.delete()

        # Przerysuj cały krok autorów — statystyki (liczniki dopasowań,
        # niedopasowanych) i przyciski nawigacji muszą się odświeżyć po
        # usunięciu wiersza, więc nie wystarczy zwrócić samego wiersza.
        return _render_authors_step(request, session)


class AuthorCreateNewView(ImporterPermissionMixin, View):
    """Utwórz NOWEGO autora dla pojedynczego wiersza ("Edytuj" → "Utwórz
    nowego autora").

    Pozwala rozwiązać niedopasowany wiersz bezpośrednio z modala edycji,
    bez wracania do zbiorczego żółtego przycisku na górze listy. Tworzy
    (lub dopasowuje po ORCID) rekord ``Autor`` z danych dostawcy
    i przypisuje go do obcej jednostki — reużywa ``_create_single_author``,
    czyli ten sam rdzeń co masowy ``CreateUnmatchedAuthorsView``.

    Opcjonalne pola POST ``nazwisko`` / ``imiona`` / ``zapisany_jako``
    pozwalają skorygować dane przed utworzeniem (np. literówka w danych
    dostawcy). Puste pola → użycie wartości z ``ImportedAuthor``.
    """

    def post(self, request, session_id, author_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)
        imported_author = get_object_or_404(
            ImportedAuthor,
            pk=author_id,
            session=session,
        )

        uczelnia = Uczelnia.objects.get_for_request(request)
        obca = uczelnia.obca_jednostka if uczelnia else None
        if not obca:
            return render(
                request,
                "importer_publikacji/partials/author_row.html",
                {
                    "session": session,
                    "author": imported_author,
                    "row_error": (
                        "Brak skonfigurowanej obcej jednostki w "
                        "ustawieniach uczelni. Skontaktuj się z "
                        "administratorem."
                    ),
                },
            )

        # Korekta danych przed utworzeniem (opcjonalna).
        nazwisko = (request.POST.get("nazwisko") or "").strip()
        imiona = (request.POST.get("imiona") or "").strip()
        zapisany_jako = (request.POST.get("zapisany_jako") or "").strip()
        if nazwisko:
            imported_author.family_name = nazwisko
        if imiona:
            imported_author.given_name = imiona
        if zapisany_jako:
            imported_author.zapisany_jako = zapisany_jako

        _create_single_author(imported_author, obca)

        return render(
            request,
            "importer_publikacji/partials/author_row.html",
            {
                "session": session,
                "author": imported_author,
            },
        )


class AuthorsConfirmView(ImporterPermissionMixin, View):
    """Potwierdź wszystkie dopasowania autorów."""

    def post(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )

        unmatched = session.authors.filter(
            matched_autor=None,
        ).count()
        if unmatched:
            if unmatched == 1:
                error = (
                    "Nie można przejść dalej — pozostał 1 "
                    "niedopasowany autor. Dopasuj go ręcznie "
                    "lub utwórz jako nowego autora w systemie."
                )
            else:
                error = (
                    f"Nie można przejść dalej — pozostało {unmatched} "
                    f"niedopasowanych autorów. Dopasuj ich ręcznie "
                    f"lub utwórz jako nowych autorów w systemie."
                )
            return _render_authors_step(request, session, error=error)

        session.status = ImportSession.Status.AUTHORS_MATCHED
        session.modified_by = request.user
        session.save()

        return _render_punktacja_step(request, session)


class PunktacjaView(ImporterPermissionMixin, View):
    """Krok sugerowania punktacji ministerialnej."""

    def get(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)
        if _is_htmx_partial(request):
            return _render_punktacja_step(request, session)
        from .steps import _render_punktacja_full

        return _render_punktacja_full(request, session)

    def post(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)
        form = PunktacjaForm(request.POST)
        if not form.is_valid():
            return _render_punktacja_step(request, session, form=form)

        punkty = form.cleaned_data.get("punkty_kbn")
        session.matched_data["punkty_kbn"] = "" if punkty is None else str(punkty)
        session.status = ImportSession.Status.PUNKTACJA
        session.modified_by = request.user
        session.save()

        # Patent nie idzie do PBN — pomijamy krok „Sprawdź w PBN" i idziemy
        # prosto do przeglądu.
        if session.rodzaj_rekordu == ImportSession.RodzajRekordu.PATENT:
            return _render_review_step(request, session)
        # Dla źródeł NIE-PBN wchodzimy w krok „Sprawdź w PBN"; dla źródła PBN
        # pomijamy go (odpowiednik i tak jest znany) i idziemy do przeglądu.
        if session.provider_name == "PBN":
            return _render_review_step(request, session)
        return _render_pbn_step(request, session)


class PbnCheckView(ImporterPermissionMixin, View):
    """Krok „Sprawdź w PBN" — wyszukanie i wybór odpowiednika PBN.

    Tylko dla źródeł NIE-PBN. Dla źródła PBN przekierowuje do przeglądu
    (krok nie dotyczy). Jeśli operator nie jest zalogowany do PBN — pokazuje
    panel z propozycją logowania lub pominięcia (weryfikacja opcjonalna).
    """

    def get(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)
        guard = _patent_guard(request, session)
        if guard is not None:
            return guard
        if session.provider_name == "PBN":
            return HttpResponseRedirect(
                reverse(
                    "importer_publikacji:review",
                    kwargs={"session_id": session.pk},
                )
            )
        if request.headers.get("HX-Request"):
            return _render_pbn_step(request, session)
        from .steps import _render_pbn_full

        return _render_pbn_full(request, session)

    def post(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)
        guard = _patent_guard(request, session)
        if guard is not None:
            return guard
        session.status = ImportSession.Status.PBN_CHECK
        session.modified_by = request.user
        session.save()
        return _render_review_step(request, session)


class PbnSelectView(ImporterPermissionMixin, View):
    """Wybierz rekord PBN jako odpowiednik importowanej pracy."""

    def post(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)
        guard = _patent_guard(request, session)
        if guard is not None:
            return guard
        mongo_id = (request.POST.get("mongo_id") or "").strip()

        from .pbn_search import _select_pbn_equivalent
        from .steps import _render_pbn_step as _render

        _select_pbn_equivalent(session, request.user, mongo_id)
        # Nie ponawiamy wyszukiwania — pokazujemy wynik wyboru.
        return _render(request, session, do_search=False)


class PbnClearView(ImporterPermissionMixin, View):
    """Usuń wybrany odpowiednik PBN."""

    def post(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)
        guard = _patent_guard(request, session)
        if guard is not None:
            return guard

        from .pbn_search import _clear_pbn_equivalent

        _clear_pbn_equivalent(session)
        return _render_pbn_step(request, session)


class CreateUnmatchedAuthorsView(ImporterPermissionMixin, View):
    """Utwórz rekordy Autor dla niedopasowanych."""

    def post(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        uczelnia = Uczelnia.objects.get_for_request(request)
        obca = uczelnia.obca_jednostka if uczelnia else None

        if not obca:
            return _render_authors_step(
                request,
                session,
                error=(
                    "Brak skonfigurowanej obcej"
                    " jednostki w ustawieniach"
                    " uczelni. Skontaktuj się"
                    " z administratorem."
                ),
            )

        _create_unmatched_authors(session, obca)
        return _render_authors_step(request, session)


class AuthorSetOrcidView(ImporterPermissionMixin, View):
    """Ustaw ORCID pojedynczemu autorowi w BPP."""

    def post(self, request, session_id, author_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        imported = get_object_or_404(
            ImportedAuthor.objects.select_related("matched_autor"),
            pk=author_id,
            session=session,
        )

        if (
            not imported.orcid
            or not imported.matched_autor
            or imported.matched_autor.orcid
        ):
            return HttpResponseBadRequest("Warunki ustawienia ORCID nie są spełnione.")

        imported.matched_autor.orcid = imported.orcid
        imported.matched_autor.save(update_fields=["orcid"])

        return render(
            request,
            "importer_publikacji/partials/author_row.html",
            {"session": session, "author": imported},
        )


class AuthorsSetOrcidsView(ImporterPermissionMixin, View):
    """Ustaw ORCIDy grupowo autorom w BPP."""

    def post(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        settable = _orcid_settable_qs(session)
        for imported in settable.select_related("matched_autor"):
            imported.matched_autor.orcid = imported.orcid
            imported.matched_autor.save(update_fields=["orcid"])

        return _render_authors_step(request, session)


class ReviewView(ImporterPermissionMixin, View):
    """Przegląd końcowy przed utworzeniem rekordu."""

    def get(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        if _is_htmx_partial(request):
            return _render_review_step(request, session)
        from .steps import _render_review_full

        return _render_review_full(request, session)


class CreateView(ImporterPermissionMixin, View):
    """Enqueueuje create_publication_task; redirect na task-status."""

    def post(self, request, session_id):
        session = self.get_scoped_or_404(ImportSession, pk=session_id)

        # Idempotency (C2): jesli sesja juz jest w trakcie tworzenia lub
        # zakonczona — nie enqueueuj kolejnego taska. Redirect do
        # task-status (lub done dla COMPLETED) zamiast podwojnego POST-a.
        if session.status in (
            ImportSession.Status.CREATING,
            ImportSession.Status.COMPLETED,
        ):
            url = session.get_continue_url()
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=200)
                response["HX-Redirect"] = url
                return response
            return HttpResponseRedirect(url)

        # #438: pre-flight afiliacji — zanim wejdziemy dalej w importera
        # (enqueue taska), odmów utworzenia pracy, gdy któryś dopasowany autor
        # afiliowałby do jednostki nieprzyjmującej afiliacji (np. wydział).
        # User dostaje komunikat na przeglądzie i może poprawić dopasowanie.
        from django.core.exceptions import ValidationError

        from .publikacja import waliduj_afiliacje_sesji
        from .steps import _render_review_full, _render_review_step

        try:
            waliduj_afiliacje_sesji(session)
        except ValidationError as exc:
            error = " ".join(exc.messages)
            if request.headers.get("HX-Request"):
                return _render_review_step(request, session, error=error)
            return _render_review_full(request, session, error=error)

        # Patent nie ma ścieżki eksportu do PBN — ignoruj also_pbn nawet gdy
        # przyszło w POST (replay ze starej karty / ręczny POST).
        also_pbn = (
            "_create_and_pbn" in request.POST
            and session.rodzaj_rekordu != ImportSession.RodzajRekordu.PATENT
        )

        # Persist for retry path (Task 10 reads this)
        session.matched_data["pbn_export_pending"] = also_pbn
        session.status = ImportSession.Status.CREATING
        session.save(update_fields=["matched_data", "status"])

        task = create_publication_task.delay(session.pk, request.user.pk, also_pbn)
        session.celery_task_id = task.id
        session.save(update_fields=["celery_task_id"])

        url = reverse(
            "importer_publikacji:task-status",
            kwargs={"session_id": session.pk},
        )
        if request.headers.get("HX-Request"):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = url
            return response
        return HttpResponseRedirect(url)


class DoneView(ImporterPermissionMixin, View):
    """Strona potwierdzenia utworzenia rekordu (GET)."""

    def get(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        record = session.created_record
        ctx = {"session": session, "record": record}
        batch_entry = getattr(session, "batch_entry", None)
        if batch_entry is not None:
            ctx["batch"] = batch_entry.parent
            ctx["batch_progress"] = batch_entry.parent.progress
        return _render_full_page(request, STEP_DONE, ctx)


class CancelView(ImporterPermissionMixin, View):
    """Anuluj sesję importu."""

    def post(self, request, session_id):
        session = self.get_scoped_or_404(
            ImportSession,
            pk=session_id,
        )
        session.status = ImportSession.Status.CANCELLED
        session.modified_by = request.user
        session.save()

        batch_entry = getattr(session, "batch_entry", None)
        if batch_entry is not None:
            url = reverse(
                "importer_publikacji:batch-detail",
                kwargs={"batch_id": batch_entry.parent_id},
            )
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=200)
                response["HX-Redirect"] = url
                return response
            return HttpResponseRedirect(url)

        # Wraca na kaflową stronę główną (bez ``?provider=``) — musi być
        # ta sama treść, co przy zwykłym GET/refreshu tego samego URL-a
        # (patrz IndexView._get_landing), inaczej Back/refresh po anulowaniu
        # pokazywałby co innego niż to, co właśnie wypchnięto do historii.
        url = reverse("importer_publikacji:index")
        ctx = _landing_context(request)
        ctx["cancelled"] = True
        response = render(request, STEP_LANDING, ctx)
        response = _with_breadcrumbs_oob(response, request)
        return _push_url(response, url)
