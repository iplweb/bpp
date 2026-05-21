"""Celery taski dla wizard-a importera publikacji.

Globalny @task_failure.connect w src/django_bpp/celery_tasks.py:40-42
automatycznie raportuje wyjątki do Rollbar — task body wystarczy raise
po zapisaniu user-safe message w sesji.
"""

import traceback

from celery import shared_task
from django.contrib.contenttypes.models import ContentType

from .models import ImportSession
from .progress import (
    CREATE_STAGES,
    FETCH_STAGES,
    ProviderReturnedNothing,
    report_progress,
    user_safe_message,
)
from .providers import get_provider


@shared_task(bind=True)
def fetch_session_task(self, session_id, request_user_id):
    """Pobierz dane z dostawcy + auto-dopasuj autorów + uzupełnij
    dyscypliny ze zgłoszeń. Działa w tle, raportuje postęp przez
    update_state, na końcu ustawia session.status = FETCHED.

    Wszystkie wyjątki: zapisz user-safe message + traceback na sesji,
    raise (globalny @task_failure.connect zgłosi do Rollbar).

    Args:
        session_id: ImportSession.pk
        request_user_id: User who initiated the task. Currently unused in
            this body but kept for signature symmetry with
            create_publication_task (Task 8) and potential retry-audit
            usage in ImportTaskRetryView (Task 10).
    """
    session = ImportSession.objects.get(pk=session_id)
    try:
        report_progress(self, "provider_fetch", stages=FETCH_STAGES)
        provider = get_provider(session.provider_name)
        result = provider.fetch(session.identifier)
        if result is None:
            raise ProviderReturnedNothing(
                f"Provider {session.provider_name} returned None for "
                f"{session.identifier}"
            )

        report_progress(self, "create_session", stages=FETCH_STAGES)
        _store_normalized_data(session, result)
        session.save()

        report_progress(self, "match_type_lang", stages=FETCH_STAGES)
        _auto_match_type_and_language(session, result)
        session.save()

        report_progress(
            self,
            "match_authors",
            sub_current=0,
            sub_total=max(len(result.authors), 1),
            stages=FETCH_STAGES,
        )
        from .views.authors import _auto_match_single_author

        for i, author_data in enumerate(result.authors):
            _auto_match_single_author(session, author_data, i, result.year)
            report_progress(
                self,
                "match_authors",
                sub_current=i + 1,
                sub_total=max(len(result.authors), 1),
                stages=FETCH_STAGES,
            )

        report_progress(self, "prefill_zgl", stages=FETCH_STAGES)
        from .views.authors import _prefill_dyscypliny_z_zgloszen

        _prefill_dyscypliny_z_zgloszen(session)

        session.status = ImportSession.Status.FETCHED
        session.celery_task_id = ""
        session.save()
    except Exception as exc:
        session.status = ImportSession.Status.IMPORT_FAILED
        session.last_failed_stage = "fetch"
        session.last_error_message = user_safe_message(exc, task_kind="fetch")[:255]
        session.last_error_traceback = traceback.format_exc()
        session.celery_task_id = ""
        session.save()
        raise


def _store_normalized_data(session, result):
    """Zapisz znormalizowane dane w session.raw_data/normalized_data.
    Dokładny układ pól zgodny z FetchView.post (wizard.py:152-182).
    """
    from .views.publikacja import _build_abstracts_list

    session.raw_data = result.raw_data
    session.normalized_data = {
        "title": result.title,
        "doi": result.doi,
        "year": result.year,
        "authors": result.authors,
        "source_title": result.source_title,
        "source_abbreviation": result.source_abbreviation,
        "issn": result.issn,
        "e_issn": result.e_issn,
        "isbn": result.isbn,
        "e_isbn": result.e_isbn,
        "publisher": result.publisher,
        "publication_type": result.publication_type,
        "language": result.language,
        "abstract": result.abstract,
        "volume": result.volume,
        "issue": result.issue,
        "pages": result.pages,
        "url": result.url,
        "license_url": result.license_url,
        "keywords": result.keywords,
        "article_number": result.extra.get("article_number"),
        "original_title": result.extra.get("original_title"),
        "abstracts": _build_abstracts_list(result),
    }


def _auto_match_type_and_language(session, result):
    """Mapowanie typu publikacji + języka. Zachowuje logikę z
    FetchView.post (wizard.py:184-201).
    """
    from crossref_bpp.core import Komparator

    from .views.helpers import _detect_language, _get_crossref_mapper

    mapper = _get_crossref_mapper(result.publication_type)
    if mapper and mapper.charakter_formalny_bpp_id:
        session.charakter_formalny = mapper.charakter_formalny_bpp
        session.jest_wydawnictwem_zwartym = mapper.jest_wydawnictwem_zwartym

    language_code = result.language
    if not language_code:
        language_code = _detect_language(result.title, result.abstract)
    if language_code:
        lang_result = Komparator.porownaj_language(language_code)
        if lang_result.rekord_po_stronie_bpp:
            session.jezyk = lang_result.rekord_po_stronie_bpp


@shared_task(bind=True)
def create_publication_task(self, session_id, request_user_id, also_pbn):
    """Utwórz rekord publikacji z danych sesji + opcjonalnie zleć
    eksport do PBN. Działa w tle, raportuje postęp przez update_state.

    Granularność progress: wagi z CREATE_STAGES. Progress raportowany
    jest tylko na granicach ``_create_publication()`` — nie można
    obserwować pętli autorów z zewnątrz (cała operacja jest atomowa
    i synchronizowana wewnątrz helper-a).

    PBN export decision: B1 — gdy ``also_pbn=True``, wołamy oryginalny
    helper ``sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui`` z minimalnym
    request-stubem (atrybuty ``user`` oraz ``_messages`` jako no-op
    storage). Helper używa ``request.user`` do utworzenia wpisu w
    PBN_Export_Queue oraz wywołań ``messages.success/info/error/warning``;
    no-op ``_messages`` połyka te komunikaty bez błędu (w Celery worker-ze
    nie ma sensownego odbiorcy dla flash messages). ``Uczelnia.get_for_request``
    bezpiecznie spada do ``get_default()`` gdy ``hasattr(request, "_uczelnia")``
    jest False, więc nie trzeba podstawiać sesji / cache uczelni.
    """
    from django.contrib.auth import get_user_model

    session = ImportSession.objects.get(pk=session_id)
    user_model = get_user_model()
    request_user = user_model.objects.get(pk=request_user_id)

    try:
        report_progress(self, "prepare", stages=CREATE_STAGES)
        report_progress(self, "create_record", stages=CREATE_STAGES)
        record = _create_publication(session)

        if also_pbn:
            report_progress(self, "link_pbn", stages=CREATE_STAGES)
            _enqueue_pbn_export(request_user, record)

        session.status = ImportSession.Status.COMPLETED
        session.created_record_content_type = ContentType.objects.get_for_model(record)
        session.created_record_id = record.pk
        session.modified_by = request_user
        session.celery_task_id = ""
        session.save()
    except Exception as exc:
        session.status = ImportSession.Status.IMPORT_FAILED
        session.last_failed_stage = "create"
        session.last_error_message = user_safe_message(exc, task_kind="create")[:255]
        session.last_error_traceback = traceback.format_exc()
        session.celery_task_id = ""
        session.save()
        raise


def _create_publication(session):
    """Thin wrapper na ``views.publikacja._create_publication``.
    Wydzielone do osobnej funkcji żeby testy mogły patchować
    ``importer_publikacji.tasks._create_publication`` bez naruszania
    importu w ``views.publikacja`` (gdzie funkcja jest też wołana
    synchronicznie z ``CreateView`` w trybie pre-async).
    """
    from .views.publikacja import _create_publication as _impl

    return _impl(session)


class _NoopMessageStorage:
    """No-op zamiennik ``request._messages`` dla wywołań w Celery worker-ze.

    Django ``messages.success/info/error/warning`` wewnętrznie wołają
    ``request._messages.add(level, message, extra_tags)``. W kontekście
    background taska nie mamy gdzie tych komunikatów wyświetlić — po
    prostu je odrzucamy. Brak ``_messages`` na obiekcie spowodowałby
    ``MessageFailure`` z django.contrib.messages.api.add_message.
    """

    def add(self, level, message, extra_tags=""):
        return None


class _PbnRequestStub:
    """Minimalny request stub dla PBN helper-a uruchamianego w Celery.

    Wymagane atrybuty:
        - ``user``: model User (helper przekazuje go do
          ``PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(request.user, obj)``).
        - ``_messages``: storage dla flash messages (helper woła
          ``messages.success/info/error/warning``).
    Nieobecność ``_uczelnia`` jest OK — ``Uczelnia.get_for_request``
    fallbackuje do ``get_default()`` gdy ``hasattr(request, "_uczelnia")``
    jest False.
    """

    def __init__(self, user):
        self.user = user
        self._messages = _NoopMessageStorage()


def _enqueue_pbn_export(request_user, record):
    """Wywołaj helper PBN export z minimalnym request stubem.

    Decision: B1 (patrz docstring create_publication_task). Helper
    wymaga ``request.user`` (do utworzenia wpisu w kolejce) oraz
    ``request._messages`` (do wywołań flash messages — odrzucane).
    """
    from bpp.admin.helpers.pbn_api.gui import (
        sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui,
    )

    request_stub = _PbnRequestStub(request_user)
    sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(request_stub, record)
