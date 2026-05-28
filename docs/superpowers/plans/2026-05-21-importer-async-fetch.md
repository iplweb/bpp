# Async Fetch + Create w wizardzie importer_publikacji — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przenieść dwa wąskie gardła wizard-a importera publikacji (`FetchView.post`, `CreateView.post`) do Celery tasków z paskiem postępu (HTMX polling), user-friendly komunikatami błędów i automatycznym Rollbar reportingiem.

**Architecture:** Dwa `@shared_task(bind=True)` task-i + jeden parametryzowany widok statusu + jeden partial postępu. `ImportSession.status` jako single source of truth dla stanu (Redis AsyncResult używamy tylko dla `task.info` z progress meta). Globalny `@task_failure.connect` w `src/django_bpp/celery_tasks.py:40-42` auto-raportuje Rollbar — task body wystarczy `raise` po zapisaniu user-safe message.

**Tech Stack:** Django 5.x + Celery + Redis + HTMX + Foundation CSS + pytest + model_bakery. Wszystkie komendy z prefiksem `uv run`. Worktree: `~/Programowanie/bpp-importer-async`, branch `feat/importer-async-fetch`. Aktualna baza migracji: `0006_merge_20260421_1100`.

Spec: `docs/superpowers/specs/2026-05-21-importer-async-fetch-design.md`.

---

## Struktura plików

### Tworzone

- `src/importer_publikacji/tasks.py` — `fetch_session_task`, `create_publication_task`
- `src/importer_publikacji/progress.py` — tabela stages + `report_progress` + `_user_safe_message`
- `src/importer_publikacji/views/task_status.py` — `ImportTaskStatusView`
- `src/importer_publikacji/views/retry.py` — `ImportTaskRetryView`
- `src/importer_publikacji/templates/importer_publikacji/step_task_status.html`
- `src/importer_publikacji/templates/importer_publikacji/partials/task_progress.html`
- `src/importer_publikacji/templates/importer_publikacji/partials/task_error.html`
- `src/importer_publikacji/migrations/0007_async_import_state.py`
- `src/importer_publikacji/tests/test_progress.py`
- `src/importer_publikacji/tests/test_tasks.py`
- `src/importer_publikacji/tests/test_views_task_status.py`
- `src/importer_publikacji/tests/test_views_retry.py`

### Modyfikowane

- `src/importer_publikacji/models.py` — nowe Status choices + pola + `get_continue_url`
- `src/importer_publikacji/views/wizard.py` — `FetchView.post`, `CreateView.post` enqueueują taski
- `src/importer_publikacji/views/authors.py` — wyciągnięcie `_auto_match_single_author` z `_auto_match_authors`
- `src/importer_publikacji/urls.py` — nowe URL-e `task-status` i `task-retry`
- `src/importer_publikacji/templates/importer_publikacji/partials/session_list.html` — branding nowych statusów

### Bez zmian (referencyjne)

- `src/pbn_komparator_zrodel/templates/pbn_komparator_zrodel/_progress.html` — wzorzec dla naszego `task_progress.html`
- `src/django_bpp/celery_tasks.py` — globalny `@task_failure.connect` (już istnieje)
- `src/django_bpp/settings/base.py:333-336` — `CELERY_TASK_ALWAYS_EAGER=True` pod testami (już istnieje)

---

## Task 1: Migracja modelu — nowe statusy i pola

**Files:**
- Modify: `src/importer_publikacji/models.py`
- Create: `src/importer_publikacji/migrations/0007_async_import_state.py`
- Test: `src/importer_publikacji/tests/test_models.py` (dorzucenie nowych testów)

- [ ] **Step 1: Napisz testy dla nowych pól i statusów**

Otwórz `src/importer_publikacji/tests/test_models.py` i dodaj na końcu pliku:

```python
import pytest
from model_bakery import baker

from importer_publikacji.models import ImportSession


@pytest.mark.django_db
def test_import_session_has_async_state_fields():
    session = baker.make(ImportSession)
    # Defaults dla nowych pól
    assert session.celery_task_id == ""
    assert session.last_error_message == ""
    assert session.last_error_traceback == ""
    assert session.last_failed_stage == ""


@pytest.mark.django_db
def test_import_session_status_includes_new_choices():
    choices = dict(ImportSession.Status.choices)
    assert ImportSession.Status.FETCHING in choices
    assert ImportSession.Status.CREATING in choices
    assert ImportSession.Status.IMPORT_FAILED in choices
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_models.py::test_import_session_has_async_state_fields src/importer_publikacji/tests/test_models.py::test_import_session_status_includes_new_choices -v
```

Expected: `FAIL` z `AttributeError: type object 'Status' has no attribute 'FETCHING'` (lub podobny).

- [ ] **Step 3: Dodaj nowe statusy i pola do modelu**

W `src/importer_publikacji/models.py`, w klasie `Status` (linia 10–20) dodaj po `FETCHED`:

```python
    class Status(models.TextChoices):
        FETCHED = "fetched", "Pobrane"
        FETCHING = "fetching", "Trwa pobieranie"
        CREATING = "creating", "Trwa tworzenie rekordu"
        IMPORT_FAILED = "import_failed", "Błąd importu"
        VERIFIED = "verified", "Zweryfikowane"
        SOURCE_MATCHED = "source_matched", "Źródło dopasowane"
        AUTHORS_MATCHED = "authors_matched", "Autorzy dopasowani"
        REVIEW = "review", "Do przeglądu"
        COMPLETED = "completed", "Ukończone"
        CANCELLED = "cancelled", "Anulowane"
```

W tej samej klasie `ImportSession`, po istniejących polach (przed `class Meta` jeśli jest, lub przed `get_continue_url`), dodaj:

```python
    celery_task_id = models.CharField(
        "Celery task ID",
        max_length=64,
        blank=True,
        default="",
    )

    last_error_message = models.CharField(
        "Ostatni komunikat błędu",
        max_length=255,
        blank=True,
        default="",
    )

    last_error_traceback = models.TextField(
        "Pełny traceback ostatniego błędu",
        blank=True,
        default="",
    )

    last_failed_stage = models.CharField(
        "Etap który padł",
        max_length=16,
        blank=True,
        default="",
        help_text="'fetch' lub 'create'",
    )
```

- [ ] **Step 4: Wygeneruj migrację**

```bash
uv run python src/manage.py makemigrations importer_publikacji
```

Expected output: `Migrations for 'importer_publikacji': 0007_<auto-name>.py`. Plik powinien zawierać `AlterField` dla `status` oraz `AddField` dla czterech nowych pól.

- [ ] **Step 5: Przemianuj migrację na opisową**

```bash
mv src/importer_publikacji/migrations/0007_*.py src/importer_publikacji/migrations/0007_async_import_state.py
```

Otwórz `src/importer_publikacji/migrations/0007_async_import_state.py` i upewnij się, że `dependencies` to:

```python
    dependencies = [
        ("importer_publikacji", "0006_merge_20260421_1100"),
    ]
```

- [ ] **Step 6: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_models.py::test_import_session_has_async_state_fields src/importer_publikacji/tests/test_models.py::test_import_session_status_includes_new_choices -v
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

```bash
git add src/importer_publikacji/models.py src/importer_publikacji/migrations/0007_async_import_state.py src/importer_publikacji/tests/test_models.py
git commit -m "feat(importer_publikacji): dodaj statusy FETCHING/CREATING/IMPORT_FAILED + pola async"
```

---

## Task 2: `get_continue_url` dla nowych statusów

**Files:**
- Modify: `src/importer_publikacji/models.py` (metoda `get_continue_url`, linie ~150–157)
- Test: `src/importer_publikacji/tests/test_models.py`

- [ ] **Step 1: Napisz testy**

Dodaj na końcu `src/importer_publikacji/tests/test_models.py`:

```python
@pytest.mark.django_db
def test_get_continue_url_fetching_points_to_task_status():
    session = baker.make(
        ImportSession,
        status=ImportSession.Status.FETCHING,
    )
    url = session.get_continue_url()
    assert "task-status" in url
    assert str(session.pk) in url


@pytest.mark.django_db
def test_get_continue_url_creating_points_to_task_status():
    session = baker.make(
        ImportSession,
        status=ImportSession.Status.CREATING,
    )
    url = session.get_continue_url()
    assert "task-status" in url


@pytest.mark.django_db
def test_get_continue_url_import_failed_points_to_task_status():
    session = baker.make(
        ImportSession,
        status=ImportSession.Status.IMPORT_FAILED,
    )
    url = session.get_continue_url()
    # Status view renderuje error partial sam — kierujemy tam.
    assert "task-status" in url
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_models.py::test_get_continue_url_fetching_points_to_task_status -v
```

Expected: `FAIL` (URL `task-status` jeszcze nie istnieje albo `get_continue_url` nie zna nowych statusów).

- [ ] **Step 3: Zaktualizuj `get_continue_url`**

W `src/importer_publikacji/models.py`, znajdź metodę `get_continue_url` (~linia 150) i rozszerz mapping. Dotychczasowa wersja zwraca `reverse("importer_publikacji:<view>", kwargs={"session_id": self.pk})` na podstawie słownika. Zachowaj istniejące wpisy i dodaj trzy nowe:

```python
    def get_continue_url(self):
        from django.urls import reverse

        mapping = {
            self.Status.FETCHED: "verify",
            self.Status.FETCHING: "task-status",
            self.Status.CREATING: "task-status",
            self.Status.IMPORT_FAILED: "task-status",
            self.Status.VERIFIED: "source",
            self.Status.SOURCE_MATCHED: "authors",
            self.Status.AUTHORS_MATCHED: "review",
            self.Status.REVIEW: "review",
            self.Status.COMPLETED: "done",
        }
        view_name = mapping.get(self.status)
        if not view_name:
            return None
        return reverse(
            f"importer_publikacji:{view_name}",
            kwargs={"session_id": self.pk},
        )
```

> Jeśli oryginał używa innej struktury (np. nazwy view inne niż `"verify"`, `"source"`) — zachowaj nazwy z oryginału, dorzuć tylko nowe trzy wpisy.

- [ ] **Step 4: Stwórz placeholder URL `task-status`, żeby `reverse` w teście działał**

W `src/importer_publikacji/urls.py`, znajdź `urlpatterns = [...]` i dodaj **tymczasowy** wpis (zostanie zastąpiony w Task 11):

```python
    path(
        "task-status/<uuid:session_id>/",
        TemplateView.as_view(template_name="importer_publikacji/index.html"),
        name="task-status",
    ),
```

I upewnij się, że na górze pliku jest:

```python
from django.views.generic import TemplateView
```

- [ ] **Step 5: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_models.py -v -k get_continue_url
```

Expected: trzy nowe testy `PASS` + wszystkie istniejące `PASS`.

- [ ] **Step 6: Commit**

```bash
git add src/importer_publikacji/models.py src/importer_publikacji/tests/test_models.py src/importer_publikacji/urls.py
git commit -m "feat(importer_publikacji): get_continue_url mapuje nowe statusy do task-status"
```

---

## Task 3: Branding nowych statusów w `session_list.html`

**Files:**
- Modify: `src/importer_publikacji/templates/importer_publikacji/partials/session_list.html` (linie ~102–112)

- [ ] **Step 1: Zlokalizuj fragment z labelami statusów**

Przeczytaj `src/importer_publikacji/templates/importer_publikacji/partials/session_list.html`, linie 100–115. Wzorzec to mniej więcej:

```django
{% if session.status == 'completed' %}
    <span class="label success">{{ session.get_status_display }}</span>
{% elif session.status == 'cancelled' %}
    <span class="label alert">{{ session.get_status_display }}</span>
{% else %}
    <span class="label primary">{{ session.get_status_display }}</span>
{% endif %}
```

- [ ] **Step 2: Dodaj nowe branche**

Zmodyfikuj na:

```django
{% if session.status == 'completed' %}
    <span class="label success">{{ session.get_status_display }}</span>
{% elif session.status == 'cancelled' %}
    <span class="label alert">{{ session.get_status_display }}</span>
{% elif session.status == 'import_failed' %}
    <span class="label alert">{{ session.get_status_display }}</span>
{% elif session.status == 'fetching' or session.status == 'creating' %}
    <span class="label warning">{{ session.get_status_display }}</span>
{% else %}
    <span class="label primary">{{ session.get_status_display }}</span>
{% endif %}
```

- [ ] **Step 3: Sprawdź czy template kompiluje się**

```bash
uv run python src/manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add src/importer_publikacji/templates/importer_publikacji/partials/session_list.html
git commit -m "feat(importer_publikacji): branding nowych statusow na liscie sesji"
```

---

## Task 4: `progress.py` — tabela stages + `report_progress`

**Files:**
- Create: `src/importer_publikacji/progress.py`
- Create: `src/importer_publikacji/tests/test_progress.py`

- [ ] **Step 1: Napisz testy**

Stwórz `src/importer_publikacji/tests/test_progress.py`:

```python
from unittest.mock import MagicMock

import pytest

from importer_publikacji.progress import (
    FETCH_STAGES,
    CREATE_STAGES,
    report_progress,
)


def test_fetch_stages_weights_sum_to_100():
    total = sum(weight for _, _, weight in FETCH_STAGES)
    assert total == 100


def test_create_stages_weights_sum_to_100():
    total = sum(weight for _, _, weight in CREATE_STAGES)
    assert total == 100


def test_report_progress_first_stage_no_counter():
    task = MagicMock()
    report_progress(task, "provider_fetch", stages=FETCH_STAGES)

    task.update_state.assert_called_once()
    args, kwargs = task.update_state.call_args
    assert kwargs["state"] == "PROGRESS"
    meta = kwargs["meta"]
    assert meta["stage_code"] == "provider_fetch"
    assert meta["label"] == "Pobieram dane z dostawcy..."
    # Pierwszy etap nie ma per-item counter
    assert meta["current"] == 0
    assert meta["total"] == 0
    # Stage progress: dla "weszliśmy w stage" pokazujemy poprzednie ukończone
    assert meta["progress"] == 0


def test_report_progress_middle_stage_with_counter():
    task = MagicMock()
    # match_authors ma wagę 60, poprzednie 10+5+5=20.
    # current=25, total=50 → 25/50 = 50% wagi 60 = 30, plus 20 = 50%
    report_progress(
        task,
        "match_authors",
        sub_current=25,
        sub_total=50,
        stages=FETCH_STAGES,
    )

    meta = task.update_state.call_args.kwargs["meta"]
    assert meta["stage_code"] == "match_authors"
    assert meta["current"] == 25
    assert meta["total"] == 50
    assert meta["progress"] == 50


def test_report_progress_last_stage_at_end():
    task = MagicMock()
    # prefill_zgl ma wagę 20, poprzednie 10+5+5+60=80
    # przy domyślnym sub_current=0, sub_total=1 → 0% wagi 20 + 80 = 80
    report_progress(task, "prefill_zgl", stages=FETCH_STAGES)

    meta = task.update_state.call_args.kwargs["meta"]
    assert meta["progress"] == 80


def test_report_progress_unknown_stage_raises():
    task = MagicMock()
    with pytest.raises(ValueError, match="Unknown stage"):
        report_progress(task, "nonexistent_stage", stages=FETCH_STAGES)


def test_report_progress_label_contains_counter_when_total_gt_1():
    task = MagicMock()
    report_progress(
        task,
        "match_authors",
        sub_current=12,
        sub_total=50,
        stages=FETCH_STAGES,
    )
    meta = task.update_state.call_args.kwargs["meta"]
    # Label powinien zawierać "(12/50)"
    assert "12/50" in meta["label"] or meta["counter_display"] == "12/50"
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_progress.py -v
```

Expected: `FAIL` z `ModuleNotFoundError: No module named 'importer_publikacji.progress'`.

- [ ] **Step 3: Zaimplementuj `progress.py`**

Stwórz `src/importer_publikacji/progress.py`:

```python
"""Tabela stages dla tasków importera + funkcja report_progress.

Wagi w tabelach FETCH_STAGES/CREATE_STAGES sumują się do 100 i są
używane do obliczenia overall percent z (stage, sub_current, sub_total).
Najwolniejszy etap dostaje największą wagę, żeby pasek postępu
faktycznie rósł podczas najdłuższej operacji.
"""

# (stage_code, label_template, weight)
# label_template może zawierać {current}/{total} dla per-item counter.
FETCH_STAGES = [
    ("provider_fetch", "Pobieram dane z dostawcy...", 10),
    ("create_session", "Tworzę sesję importu...", 5),
    ("match_type_lang", "Dopasowuję typ publikacji i język...", 5),
    ("match_authors", "Dopasowuję autorów ({current}/{total})...", 60),
    ("prefill_zgl", "Wyszukuję zgłoszenia dla dyscyplin...", 20),
]

CREATE_STAGES = [
    ("verify", "Weryfikuję dane publikacji...", 5),
    ("create_record", "Tworzę rekord publikacji...", 10),
    ("add_authors", "Zapisuję autorów ({current}/{total})...", 50),
    ("create_abstracts", "Tworzę streszczenia...", 5),
    ("calc_score", "Uzupełniam punktację ze źródła...", 10),
    ("link_pbn", "Powiązanie z PBN...", 20),
]


def report_progress(task, stage_code, sub_current=0, sub_total=1, *, stages):
    """Raportuj postęp do Celery z mapowania (stage, sub_current/sub_total)
    na overall percent (0-100).

    Wywołuje task.update_state(state="PROGRESS", meta={...}). Meta zawiera:
        - stage_code: identyfikator etapu (str)
        - label: tekst do wyświetlenia (z interpolowanym {current}/{total})
        - current, total: sub_current/sub_total (0/0 gdy etap bez counter)
        - counter_display: "M/N" lub "" gdy total <= 1
        - progress: overall percent (0-100, int)
    """
    completed_weight = 0
    found = None
    for code, label_template, weight in stages:
        if code == stage_code:
            found = (code, label_template, weight)
            break
        completed_weight += weight

    if found is None:
        raise ValueError(f"Unknown stage: {stage_code}")

    _, label_template, weight = found

    if sub_total > 1:
        stage_fraction = sub_current / sub_total
        counter_display = f"{sub_current}/{sub_total}"
        label = label_template.format(current=sub_current, total=sub_total)
    else:
        stage_fraction = 0
        counter_display = ""
        # Strip placeholders gdyby były w template
        label = label_template.replace(
            " ({current}/{total})", ""
        )

    progress = int(completed_weight + weight * stage_fraction)

    task.update_state(
        state="PROGRESS",
        meta={
            "stage_code": stage_code,
            "label": label,
            "current": sub_current,
            "total": sub_total if sub_total > 1 else 0,
            "counter_display": counter_display,
            "progress": progress,
        },
    )
```

- [ ] **Step 4: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_progress.py -v
```

Expected: `7 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/progress.py src/importer_publikacji/tests/test_progress.py
git commit -m "feat(importer_publikacji): progress.py z report_progress i tabelami stages"
```

---

## Task 5: `_user_safe_message` w `progress.py`

**Files:**
- Modify: `src/importer_publikacji/progress.py`
- Modify: `src/importer_publikacji/tests/test_progress.py`

- [ ] **Step 1: Napisz testy**

Dodaj do `src/importer_publikacji/tests/test_progress.py`:

```python
import requests

from importer_publikacji.progress import (
    user_safe_message,
    ProviderReturnedNothing,
)


def test_user_safe_message_for_provider_returned_nothing():
    msg = user_safe_message(ProviderReturnedNothing(), task_kind="fetch")
    assert "dostawcy" in msg.lower()
    assert "spróbuj" in msg.lower()


def test_user_safe_message_for_http_error():
    exc = requests.exceptions.HTTPError("500 server error")
    msg = user_safe_message(exc, task_kind="fetch")
    assert "nie odpowiada" in msg.lower() or "spróbuj" in msg.lower()


def test_user_safe_message_for_timeout():
    exc = requests.exceptions.Timeout("read timeout")
    msg = user_safe_message(exc, task_kind="fetch")
    assert "spróbuj" in msg.lower() or "czas" in msg.lower()


def test_user_safe_message_for_validation_error_uses_messages():
    from django.core.exceptions import ValidationError

    exc = ValidationError(["Pierwszy", "Drugi"])
    msg = user_safe_message(exc, task_kind="create")
    assert "Pierwszy" in msg
    assert "Drugi" in msg


def test_user_safe_message_unknown_fallback_for_fetch():
    msg = user_safe_message(RuntimeError("internal"), task_kind="fetch")
    assert "pobierania" in msg.lower() or "fetch" in msg.lower()
    assert "administrator" in msg.lower()


def test_user_safe_message_unknown_fallback_for_create():
    msg = user_safe_message(RuntimeError("internal"), task_kind="create")
    assert "tworzenia" in msg.lower() or "create" in msg.lower()
    assert "administrator" in msg.lower()
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_progress.py -v -k user_safe_message
```

Expected: `FAIL` z `ImportError`.

- [ ] **Step 3: Zaimplementuj `user_safe_message` + wyjątek**

Dopisz do `src/importer_publikacji/progress.py`:

```python
class ProviderReturnedNothing(Exception):
    """Provider zwrócił None - identyfikator nie został rozpoznany
    lub nie ma takiej publikacji w bazie dostawcy.
    """


def user_safe_message(exc, *, task_kind):
    """Zamapuj wyjątek na user-friendly komunikat (po polsku).

    task_kind: "fetch" lub "create" — wpływa na fallback message.
    """
    import requests
    from django.core.exceptions import ValidationError

    if isinstance(exc, ProviderReturnedNothing):
        return (
            "Nie udało się pobrać danych z dostawcy. "
            "Sprawdź poprawność identyfikatora i spróbuj ponownie."
        )

    if isinstance(exc, requests.exceptions.Timeout):
        return (
            "Dostawca danych nie odpowiada w wyznaczonym czasie. "
            "Spróbuj ponownie za chwilę."
        )

    if isinstance(
        exc,
        (requests.exceptions.HTTPError, requests.exceptions.ConnectionError),
    ):
        return (
            "Dostawca danych nie odpowiada. "
            "Spróbuj ponownie za chwilę."
        )

    if isinstance(exc, ValidationError):
        messages = getattr(exc, "messages", None) or [str(exc)]
        return " ".join(messages)

    kind_text = "pobierania danych" if task_kind == "fetch" else "tworzenia rekordu"
    return (
        f"Wystąpił błąd podczas {kind_text}. "
        f"Administrator został powiadomiony."
    )
```

- [ ] **Step 4: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_progress.py -v
```

Expected: wszystkie testy w tym pliku `PASS`.

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/progress.py src/importer_publikacji/tests/test_progress.py
git commit -m "feat(importer_publikacji): user_safe_message mapuje wyjatki na polskie komunikaty"
```

---

## Task 6: Refactor `_auto_match_authors` — wyciągnięcie `_auto_match_single_author`

**Files:**
- Modify: `src/importer_publikacji/views/authors.py` (linie 68–108)
- Test: `src/importer_publikacji/tests/test_authors.py` (lub stwórz, jeśli nie istnieje)

- [ ] **Step 1: Sprawdź czy `test_authors.py` istnieje**

```bash
ls src/importer_publikacji/tests/test_authors.py 2>/dev/null || echo "MISSING"
```

Jeśli `MISSING`: stwórz pusty plik:

```bash
touch src/importer_publikacji/tests/test_authors.py
```

- [ ] **Step 2: Napisz testy**

Dodaj do `src/importer_publikacji/tests/test_authors.py`:

```python
from unittest.mock import patch

import pytest
from model_bakery import baker

from importer_publikacji.models import ImportedAuthor, ImportSession
from importer_publikacji.views.authors import (
    _auto_match_authors,
    _auto_match_single_author,
)


@pytest.mark.django_db
def test_auto_match_single_author_creates_imported_author():
    session = baker.make(ImportSession)
    author_data = {"family": "Kowalski", "given": "Jan", "orcid": ""}

    imported = _auto_match_single_author(session, author_data, order=0, year=2024)

    assert imported.pk is not None
    assert imported.session_id == session.pk
    assert imported.family_name == "Kowalski"
    assert imported.given_name == "Jan"
    assert imported.order == 0


@pytest.mark.django_db
def test_auto_match_authors_calls_single_per_author():
    session = baker.make(ImportSession)
    authors_data = [
        {"family": "Kowalski", "given": "Jan", "orcid": ""},
        {"family": "Nowak", "given": "Anna", "orcid": ""},
    ]

    with patch(
        "importer_publikacji.views.authors._auto_match_single_author"
    ) as mock_single:
        _auto_match_authors(session, authors_data, year=2024)

    assert mock_single.call_count == 2
    # Sprawdź order
    assert mock_single.call_args_list[0].args[2] == 0
    assert mock_single.call_args_list[1].args[2] == 1
```

- [ ] **Step 3: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_authors.py -v
```

Expected: `FAIL` z `ImportError: cannot import name '_auto_match_single_author'`.

- [ ] **Step 4: Wyciągnij `_auto_match_single_author`**

W `src/importer_publikacji/views/authors.py`, zastąp funkcję `_auto_match_authors` (linie 68–108) dwiema funkcjami:

```python
def _auto_match_single_author(session, author_data, order, year):
    """Dopasuj pojedynczego autora i zwróć utworzony ImportedAuthor.

    Wyciągnięte z _auto_match_authors żeby task mógł raportować postęp
    po każdej iteracji.
    """
    imported = ImportedAuthor.objects.create(
        session=session,
        order=order,
        family_name=author_data.get("family", ""),
        given_name=author_data.get("given", ""),
        orcid=author_data.get("orcid", ""),
    )

    result = Komparator.porownaj_author(author_data)

    if result.status == StatusPorownania.DOKLADNE:
        bpp_autor = result.rekord_po_stronie_bpp
        if bpp_autor:
            imported.matched_autor = bpp_autor
            imported.match_status = ImportedAuthor.MatchStatus.AUTO_EXACT
            imported.matched_jednostka = bpp_autor.aktualna_jednostka
            if year:
                dyscyplina = _get_dyscyplina(bpp_autor, year)
                imported.matched_dyscyplina = dyscyplina
                if dyscyplina:
                    imported.dyscyplina_source = (
                        ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA
                    )
    elif result.status == StatusPorownania.LUZNE:
        bpp_autor = result.rekord_po_stronie_bpp
        if bpp_autor:
            imported.matched_autor = bpp_autor
            imported.match_status = ImportedAuthor.MatchStatus.AUTO_LOOSE
            imported.matched_jednostka = bpp_autor.aktualna_jednostka
            if year:
                dyscyplina = _get_dyscyplina(bpp_autor, year)
                imported.matched_dyscyplina = dyscyplina
                if dyscyplina:
                    imported.dyscyplina_source = (
                        ImportedAuthor.DyscyplinaSource.AUTO_JEDYNA
                    )

    imported.save()
    return imported


def _auto_match_authors(session, authors_data, year):
    """Auto-dopasuj autorów z danych dostawcy (thin wrapper, używany
    w testach i w synchronicznych ścieżkach bez progress reporting).
    """
    for i, author_data in enumerate(authors_data):
        _auto_match_single_author(session, author_data, i, year)
```

- [ ] **Step 5: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_authors.py -v
```

Expected: `2 passed`.

- [ ] **Step 6: Uruchom istniejące testy importera, żeby sprawdzić brak regresji**

```bash
uv run pytest src/importer_publikacji/tests/ -v --no-header -x
```

Expected: wszystkie istniejące testy nadal `PASS`.

- [ ] **Step 7: Commit**

```bash
git add src/importer_publikacji/views/authors.py src/importer_publikacji/tests/test_authors.py
git commit -m "refactor(importer_publikacji): wyciagnij _auto_match_single_author na potrzeby progress reportingu"
```

---

## Task 7: `fetch_session_task` — Celery task dla fetcha

**Files:**
- Create: `src/importer_publikacji/tasks.py`
- Create: `src/importer_publikacji/tests/test_tasks.py`

- [ ] **Step 1: Napisz testy**

Stwórz `src/importer_publikacji/tests/test_tasks.py`:

```python
from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from importer_publikacji.models import ImportSession
from importer_publikacji.progress import ProviderReturnedNothing
from importer_publikacji.tasks import fetch_session_task


@pytest.fixture
def fetch_session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(
        ImportSession,
        created_by=user,
        provider_name="crossref",
        identifier="10.1234/test",
        status=ImportSession.Status.FETCHING,
    )


@pytest.mark.django_db
def test_fetch_session_task_success_sets_status_fetched(fetch_session):
    fake_result = MagicMock(
        raw_data={"k": "v"},
        title="Test",
        doi="10.1234/test",
        year=2024,
        authors=[],
        source_title="",
        source_abbreviation="",
        issn="",
        e_issn="",
        isbn="",
        e_isbn="",
        publisher="",
        publication_type="article",
        language="en",
        abstract="",
        volume="",
        issue="",
        pages="",
        url="",
        license_url="",
        keywords=[],
        extra={},
    )

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = fake_result
        mock_get_provider.return_value = provider

        fetch_session_task(fetch_session.pk, fetch_session.created_by_id)

    fetch_session.refresh_from_db()
    assert fetch_session.status == ImportSession.Status.FETCHED
    assert fetch_session.celery_task_id == ""
    assert fetch_session.last_error_message == ""


@pytest.mark.django_db
def test_fetch_session_task_provider_returns_none_marks_failed(fetch_session):
    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = None
        mock_get_provider.return_value = provider

        with pytest.raises(ProviderReturnedNothing):
            fetch_session_task(fetch_session.pk, fetch_session.created_by_id)

    fetch_session.refresh_from_db()
    assert fetch_session.status == ImportSession.Status.IMPORT_FAILED
    assert fetch_session.last_failed_stage == "fetch"
    assert "dostawcy" in fetch_session.last_error_message.lower()
    assert fetch_session.last_error_traceback != ""


@pytest.mark.django_db
def test_fetch_session_task_provider_raises_marks_failed(fetch_session):
    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.side_effect = RuntimeError("boom")
        mock_get_provider.return_value = provider

        with pytest.raises(RuntimeError, match="boom"):
            fetch_session_task(fetch_session.pk, fetch_session.created_by_id)

    fetch_session.refresh_from_db()
    assert fetch_session.status == ImportSession.Status.IMPORT_FAILED
    assert fetch_session.last_failed_stage == "fetch"
    assert "administrator" in fetch_session.last_error_message.lower()
    assert "boom" in fetch_session.last_error_traceback


@pytest.mark.django_db
def test_fetch_session_task_processes_authors(fetch_session):
    fake_result = MagicMock(
        raw_data={"k": "v"},
        title="Test",
        doi="10.1234/test",
        year=2024,
        authors=[
            {"family": "Kowalski", "given": "Jan", "orcid": ""},
            {"family": "Nowak", "given": "Anna", "orcid": ""},
        ],
        source_title="",
        source_abbreviation="",
        issn="",
        e_issn="",
        isbn="",
        e_isbn="",
        publisher="",
        publication_type="",
        language="",
        abstract="",
        volume="",
        issue="",
        pages="",
        url="",
        license_url="",
        keywords=[],
        extra={},
    )

    with patch("importer_publikacji.tasks.get_provider") as mock_get_provider:
        provider = MagicMock()
        provider.fetch.return_value = fake_result
        mock_get_provider.return_value = provider

        fetch_session_task(fetch_session.pk, fetch_session.created_by_id)

    fetch_session.refresh_from_db()
    assert fetch_session.authors.count() == 2
    assert fetch_session.status == ImportSession.Status.FETCHED
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_tasks.py -v
```

Expected: `FAIL` z `ModuleNotFoundError: No module named 'importer_publikacji.tasks'`.

- [ ] **Step 3: Zaimplementuj `fetch_session_task`**

Stwórz `src/importer_publikacji/tasks.py`:

```python
"""Celery taski dla wizard-a importera publikacji.

Globalny @task_failure.connect w src/django_bpp/celery_tasks.py:40-42
automatycznie raportuje wyjątki do Rollbar — task body wystarczy raise
po zapisaniu user-safe message w sesji.
"""

import sys
import traceback

from celery import shared_task

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
        session.last_error_message = user_safe_message(exc, task_kind="fetch")
        session.last_error_traceback = traceback.format_exc()
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
```

- [ ] **Step 4: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_tasks.py -v
```

Expected: `4 passed`. Jeśli któryś test mocka `get_provider` nie znajduje atrybutu — sprawdź czy import w `tasks.py` to `from .providers import get_provider` (mock musi zgadzać się z miejscem użycia).

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/tasks.py src/importer_publikacji/tests/test_tasks.py
git commit -m "feat(importer_publikacji): fetch_session_task z progress reportingiem i error handlingiem"
```

---

## Task 8: `create_publication_task` — Celery task dla create

**Files:**
- Modify: `src/importer_publikacji/tasks.py`
- Modify: `src/importer_publikacji/tests/test_tasks.py`

- [ ] **Step 1: Napisz testy**

Dodaj do `src/importer_publikacji/tests/test_tasks.py`:

```python
from importer_publikacji.tasks import create_publication_task


@pytest.fixture
def review_session(db, django_user_model):
    user = baker.make(django_user_model)
    return baker.make(
        ImportSession,
        created_by=user,
        provider_name="crossref",
        identifier="10.1234/test",
        status=ImportSession.Status.CREATING,
        normalized_data={"title": "Test", "year": 2024},
    )


@pytest.mark.django_db
def test_create_publication_task_success_sets_completed(review_session):
    fake_record = MagicMock(pk=42)
    with patch(
        "importer_publikacji.tasks._create_publication"
    ) as mock_create:
        mock_create.return_value = fake_record

        create_publication_task(
            review_session.pk,
            review_session.created_by_id,
            also_pbn=False,
        )

    review_session.refresh_from_db()
    assert review_session.status == ImportSession.Status.COMPLETED
    assert review_session.celery_task_id == ""


@pytest.mark.django_db
def test_create_publication_task_failure_marks_import_failed(review_session):
    with patch(
        "importer_publikacji.tasks._create_publication"
    ) as mock_create:
        mock_create.side_effect = RuntimeError("create exploded")

        with pytest.raises(RuntimeError, match="create exploded"):
            create_publication_task(
                review_session.pk,
                review_session.created_by_id,
                also_pbn=False,
            )

    review_session.refresh_from_db()
    assert review_session.status == ImportSession.Status.IMPORT_FAILED
    assert review_session.last_failed_stage == "create"
    assert "administrator" in review_session.last_error_message.lower()


@pytest.mark.django_db
def test_create_publication_task_with_pbn_calls_pbn_export(review_session):
    fake_record = MagicMock(pk=42)
    with patch(
        "importer_publikacji.tasks._create_publication"
    ) as mock_create, patch(
        "bpp.admin.helpers.pbn_api.gui.sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui"
    ) as mock_pbn:
        mock_create.return_value = fake_record

        create_publication_task(
            review_session.pk,
            review_session.created_by_id,
            also_pbn=True,
        )

    # PBN export wywołany z record
    mock_pbn.assert_called_once()
    assert mock_pbn.call_args.args[1] == fake_record
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_tasks.py -v -k create_publication
```

Expected: `FAIL` z `ImportError: cannot import name 'create_publication_task'`.

- [ ] **Step 3: Zaimplementuj `create_publication_task`**

Dodaj do `src/importer_publikacji/tasks.py`:

```python
@shared_task(bind=True)
def create_publication_task(self, session_id, request_user_id, also_pbn):
    """Utwórz rekord publikacji z danych sesji + opcjonalnie zleć
    eksport do PBN. Działa w tle, raportuje postęp przez update_state.

    Granularność progress: wagi z CREATE_STAGES. Per-author counter
    w stage "add_authors" (50% wagi).
    """
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType

    session = ImportSession.objects.get(pk=session_id)
    user_model = get_user_model()
    request_user = user_model.objects.get(pk=request_user_id)

    try:
        report_progress(self, "verify", stages=CREATE_STAGES)

        # Inwokacja oryginalnego _create_publication, ale tutaj
        # progress reporting per stage dobieramy "na sztywno":
        # _create_publication jest atomic — nie da się go przerwać
        # po stronie taska, więc wagi stages odzwierciedlają tylko
        # to, co możemy zobaczyć z zewnątrz (entry/exit).
        report_progress(self, "create_record", stages=CREATE_STAGES)
        report_progress(
            self,
            "add_authors",
            sub_current=0,
            sub_total=max(session.authors.count(), 1),
            stages=CREATE_STAGES,
        )

        record = _create_publication(session)

        report_progress(self, "create_abstracts", stages=CREATE_STAGES)
        report_progress(self, "calc_score", stages=CREATE_STAGES)

        if also_pbn:
            report_progress(self, "link_pbn", stages=CREATE_STAGES)
            from bpp.admin.helpers.pbn_api.gui import (
                sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui,
            )

            # Wymaga obiektu request-like; budujemy minimalny stub.
            class _RequestStub:
                pass

            req = _RequestStub()
            req.user = request_user
            req._messages = []
            sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(req, record)

        session.status = ImportSession.Status.COMPLETED
        session.created_record_content_type = ContentType.objects.get_for_model(
            record
        )
        session.created_record_id = record.pk
        session.modified_by = request_user
        session.celery_task_id = ""
        session.save()
    except Exception as exc:
        session.status = ImportSession.Status.IMPORT_FAILED
        session.last_failed_stage = "create"
        session.last_error_message = user_safe_message(exc, task_kind="create")
        session.last_error_traceback = traceback.format_exc()
        session.save()
        raise


def _create_publication(session):
    """Thin wrapper na views.publikacja._create_publication.
    Wydzielone do osobnej funkcji żeby testy mogły patchować
    importer_publikacji.tasks._create_publication.
    """
    from .views.publikacja import _create_publication as _impl

    return _impl(session)
```

> **Uwaga o `_RequestStub`**: oryginalny `CreateView.post` (wizard.py:574–579) przekazuje `request` do `sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui`. Helper używa `request.user` i `messages` framework. W tle nie mamy request-a. Sprawdź podczas implementacji co dokładnie helper wymaga (Read `src/bpp/admin/helpers/pbn_api/gui.py`). Jeśli używa Django `messages.add_message(request, ...)` — może wymagać prawdziwego request z fabryki testowej, albo (lepiej) refactor: dodać alternatywne entrypoint helpera bez `messages` (sygnatura `(user, record)`), zapisywać feedback na sesji jako `matched_data["pbn_export_status"]`.

- [ ] **Step 4: Sprawdź wymagania `sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui`**

```bash
grep -n "def sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui" src/bpp/admin/helpers/pbn_api/gui.py
```

Otwórz funkcję. Jeśli używa wyłącznie `request.user` — `_RequestStub` powyżej wystarczy. Jeśli używa `messages.success(request, ...)` — dorzuć `from django.contrib.messages.storage.fallback import FallbackStorage; req._messages = FallbackStorage(req)` w stubie (i dodaj `req.session = {}`).

Jeśli helper jest zbyt request-zależny: zrób fallback. Zmień wywołanie w `create_publication_task` na: skip PBN export w tasku, zapisz `session.matched_data["pbn_export_pending"] = True`, a w `ImportTaskStatusView` po zakończeniu task-a (success path) wywołaj helper z prawdziwym request po sukcesie (HTMX HX-Redirect → user dostaje messages na następnej stronie).

- [ ] **Step 5: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_tasks.py -v
```

Expected: wszystkie testy w tym pliku `PASS`.

- [ ] **Step 6: Commit**

```bash
git add src/importer_publikacji/tasks.py src/importer_publikacji/tests/test_tasks.py
git commit -m "feat(importer_publikacji): create_publication_task z progress reportingiem"
```

---

## Task 9: `ImportTaskStatusView` — widok statusu z HTMX polling

**Files:**
- Create: `src/importer_publikacji/views/task_status.py`
- Create: `src/importer_publikacji/templates/importer_publikacji/step_task_status.html`
- Create: `src/importer_publikacji/templates/importer_publikacji/partials/task_progress.html`
- Create: `src/importer_publikacji/templates/importer_publikacji/partials/task_error.html`
- Create: `src/importer_publikacji/tests/test_views_task_status.py`
- Modify: `src/importer_publikacji/urls.py` (zastąp placeholder z Task 2)

- [ ] **Step 1: Napisz testy**

Stwórz `src/importer_publikacji/tests/test_views_task_status.py`:

```python
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportSession


@pytest.fixture
def authed_client(client, django_user_model):
    user = baker.make(
        django_user_model,
        is_staff=True,
        is_superuser=True,
    )
    user.set_password("test")
    user.save()
    client.force_login(user)
    return client, user


@pytest.fixture
def fetching_session(db, authed_client):
    _, user = authed_client
    return baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.FETCHING,
        celery_task_id="task-uuid-1",
    )


@pytest.mark.django_db
def test_task_status_get_renders_progress_partial_for_htmx(
    authed_client, fetching_session
):
    client, _ = authed_client
    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )

    with patch(
        "importer_publikacji.views.task_status.AsyncResult"
    ) as mock_async:
        mock_async.return_value = MagicMock(
            info={
                "stage_code": "match_authors",
                "label": "Dopasowuję autorów...",
                "current": 5,
                "total": 50,
                "counter_display": "5/50",
                "progress": 30,
            }
        )

        response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Dopasowuj" in response.content
    assert b"30" in response.content


@pytest.mark.django_db
def test_task_status_get_renders_full_page_for_non_htmx(
    authed_client, fetching_session
):
    client, _ = authed_client
    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )

    with patch(
        "importer_publikacji.views.task_status.AsyncResult"
    ) as mock_async:
        mock_async.return_value = MagicMock(info={"progress": 50})
        response = client.get(url)

    assert response.status_code == 200
    # Pełna strona zawiera HTML wrapper (np. doctype lub <html)
    assert b"<html" in response.content.lower() or b"step_task_status" in response.content


@pytest.mark.django_db
def test_task_status_terminal_status_redirects_with_hx_redirect(
    authed_client, fetching_session
):
    client, _ = authed_client
    fetching_session.status = ImportSession.Status.FETCHED
    fetching_session.celery_task_id = ""
    fetching_session.save()

    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    # HTMX redirect przez HX-Redirect header
    assert "HX-Redirect" in response.headers
    assert "verify" in response.headers["HX-Redirect"]


@pytest.mark.django_db
def test_task_status_failed_renders_error_partial(
    authed_client, fetching_session
):
    client, user = authed_client
    fetching_session.status = ImportSession.Status.IMPORT_FAILED
    fetching_session.last_error_message = "Nie udało się pobrać"
    fetching_session.last_error_traceback = "Traceback..."
    fetching_session.last_failed_stage = "fetch"
    fetching_session.save()

    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Nie uda" in response.content
    # Superuser widzi traceback
    assert b"Traceback" in response.content


@pytest.mark.django_db
def test_task_status_failed_hides_traceback_from_non_superuser(
    client, django_user_model
):
    user = baker.make(django_user_model, is_staff=True, is_superuser=False)
    user.set_password("test")
    user.save()
    client.force_login(user)

    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_error_message="User msg",
        last_error_traceback="secret traceback",
    )

    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": session.pk},
    )
    response = client.get(url, HTTP_HX_REQUEST="true")

    assert b"User msg" in response.content
    assert b"secret traceback" not in response.content


@pytest.mark.django_db
def test_task_status_pending_renders_initialization_message(
    authed_client, fetching_session
):
    client, _ = authed_client
    url = reverse(
        "importer_publikacji:task-status",
        kwargs={"session_id": fetching_session.pk},
    )

    with patch(
        "importer_publikacji.views.task_status.AsyncResult"
    ) as mock_async:
        # PENDING task ma info=None lub puste
        mock_async.return_value = MagicMock(info=None)

        response = client.get(url, HTTP_HX_REQUEST="true")

    assert response.status_code == 200
    assert b"Inicjalizacja" in response.content or b"Trwa" in response.content
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_views_task_status.py -v
```

Expected: `FAIL` z błędami importu / brakującego template-a.

- [ ] **Step 3: Stwórz partial postępu**

Stwórz `src/importer_publikacji/templates/importer_publikacji/partials/task_progress.html`:

```django
{% if info %}
    <div class="callout warning">
        <h4><span class="fi-loop"></span> {{ info.label }}</h4>

        <div class="progress large" role="progressbar"
             aria-valuenow="{{ info.progress|default:0 }}"
             aria-valuemin="0" aria-valuemax="100">
            <div class="progress-meter"
                 style="width: {{ info.progress|default:0 }}%">
                <p class="progress-meter-text">{{ info.progress|default:0 }}%</p>
            </div>
        </div>

        {% if info.counter_display %}
            <p><strong>Postęp etapu:</strong> {{ info.counter_display }}</p>
        {% endif %}

        <p><em>Status odświeża się co 3 sekundy. Możesz zostać na stronie lub wrócić — zadanie wykonuje się w tle.</em></p>
    </div>
{% else %}
    <div class="callout warning">
        <h4><span class="fi-loop"></span> Inicjalizacja zadania...</h4>
        <p>Trwa rozpoczynanie. Strona odświeży się automatycznie.</p>
    </div>
{% endif %}
```

- [ ] **Step 4: Stwórz partial błędu**

Stwórz `src/importer_publikacji/templates/importer_publikacji/partials/task_error.html`:

```django
<div class="callout alert">
    {# Naglowek bledu importu - polski komunikat dla usera #}
    <h4><span class="fi-x"></span> Wystąpił błąd</h4>

    <p>{{ session.last_error_message }}</p>

    <form method="post"
          action="{% url 'importer_publikacji:task-retry' session_id=session.pk %}"
          style="display:inline-block;">
        {% csrf_token %}
        <button type="submit" class="button primary">
            <span class="fi-refresh"></span> Spróbuj ponownie
        </button>
    </form>

    <a href="{% url 'importer_publikacji:index' %}" class="button secondary">
        <span class="fi-arrow-left"></span> Wróć do początku
    </a>

    {% if request.user.is_superuser and session.last_error_traceback %}
        <details style="margin-top: 1rem;">
            {# Sekcja widoczna tylko dla superusera #}
            <summary><strong>Traceback (admin)</strong></summary>
            <pre style="background:#f4f4f4;padding:1rem;overflow:auto;">{{ session.last_error_traceback }}</pre>
        </details>
    {% endif %}
</div>
```

- [ ] **Step 5: Stwórz pełną stronę statusu**

Stwórz `src/importer_publikacji/templates/importer_publikacji/step_task_status.html`:

```django
{% extends "base.html" %}

{% block title %}Import publikacji — status zadania{% endblock %}

{% block content %}
<div class="row">
    <div class="large-12 columns">
        <h1>Trwa import publikacji</h1>

        <div class="callout secondary">
            <p><strong>Identyfikator:</strong> {{ session.identifier }}</p>
            <p><strong>Dostawca:</strong> {{ session.provider_name }}</p>
        </div>

        <div id="progress-container"
             hx-get="{% url 'importer_publikacji:task-status' session_id=session.pk %}"
             hx-trigger="every 3s"
             hx-swap="innerHTML">
            {% if session.status == 'import_failed' %}
                {% include "importer_publikacji/partials/task_error.html" %}
            {% else %}
                {% include "importer_publikacji/partials/task_progress.html" %}
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Zaimplementuj `ImportTaskStatusView`**

Stwórz `src/importer_publikacji/views/task_status.py`:

```python
"""Widok statusu Celery task-a dla wizard-a importera.

Source of truth dla "done/failed" to session.status. AsyncResult używamy
TYLKO dla task.info (progress meta). Powód: race condition gdy task w
Redis już SUCCESS, ale session.save() jeszcze nie zafiałduje w DB.
"""

from celery.result import AsyncResult
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.views import View

from ..models import ImportSession
from ..permissions import ImporterPermissionMixin

TERMINAL_STATUSES = {
    ImportSession.Status.FETCHED,
    ImportSession.Status.VERIFIED,
    ImportSession.Status.SOURCE_MATCHED,
    ImportSession.Status.AUTHORS_MATCHED,
    ImportSession.Status.REVIEW,
    ImportSession.Status.COMPLETED,
    ImportSession.Status.CANCELLED,
}


class ImportTaskStatusView(ImporterPermissionMixin, View):
    """GET — renderuje partial postępu (HTMX) lub pełną stronę.

    Decyzja co renderować na podstawie session.status:
    - IMPORT_FAILED → partial task_error.html
    - terminal status → HX-Redirect lub HttpResponseRedirect na
      session.get_continue_url()
    - FETCHING/CREATING → partial task_progress.html z task.info
    """

    def get(self, request, session_id):
        session = get_object_or_404(ImportSession, pk=session_id)

        is_htmx = request.headers.get("HX-Request") == "true"

        if session.status == ImportSession.Status.IMPORT_FAILED:
            return self._render_error(request, session, is_htmx)

        if session.status in TERMINAL_STATUSES:
            return self._redirect_to_continue(session, is_htmx)

        # FETCHING / CREATING — pobierz progress z Redis
        info = None
        if session.celery_task_id:
            task = AsyncResult(session.celery_task_id)
            if isinstance(task.info, dict):
                info = task.info

        return self._render_progress(request, session, info, is_htmx)

    def _render_error(self, request, session, is_htmx):
        template = (
            "importer_publikacji/partials/task_error.html"
            if is_htmx
            else "importer_publikacji/step_task_status.html"
        )
        return render(request, template, {"session": session})

    def _redirect_to_continue(self, session, is_htmx):
        url = session.get_continue_url()
        if is_htmx:
            response = HttpResponse(status=200)
            response["HX-Redirect"] = url
            return response
        return HttpResponseRedirect(url)

    def _render_progress(self, request, session, info, is_htmx):
        ctx = {"session": session, "info": info}
        template = (
            "importer_publikacji/partials/task_progress.html"
            if is_htmx
            else "importer_publikacji/step_task_status.html"
        )
        return render(request, template, ctx)
```

- [ ] **Step 7: Zastąp placeholder w `urls.py`**

W `src/importer_publikacji/urls.py`, znajdź placeholder z Task 2:

```python
    path(
        "task-status/<uuid:session_id>/",
        TemplateView.as_view(template_name="importer_publikacji/index.html"),
        name="task-status",
    ),
```

Zastąp go:

```python
    path(
        "task-status/<uuid:session_id>/",
        ImportTaskStatusView.as_view(),
        name="task-status",
    ),
```

I dodaj import na górze pliku:

```python
from .views.task_status import ImportTaskStatusView
```

Usuń niewymagany już `from django.views.generic import TemplateView` jeśli nie jest używany gdzie indziej.

- [ ] **Step 8: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_views_task_status.py -v
```

Expected: `6 passed`.

- [ ] **Step 9: Commit**

```bash
git add src/importer_publikacji/views/task_status.py src/importer_publikacji/templates/importer_publikacji/step_task_status.html src/importer_publikacji/templates/importer_publikacji/partials/task_progress.html src/importer_publikacji/templates/importer_publikacji/partials/task_error.html src/importer_publikacji/urls.py src/importer_publikacji/tests/test_views_task_status.py
git commit -m "feat(importer_publikacji): ImportTaskStatusView + partials postepu i bledu"
```

---

## Task 10: `ImportTaskRetryView` — retry endpoint

**Files:**
- Create: `src/importer_publikacji/views/retry.py`
- Create: `src/importer_publikacji/tests/test_views_retry.py`
- Modify: `src/importer_publikacji/urls.py`

- [ ] **Step 1: Napisz testy**

Stwórz `src/importer_publikacji/tests/test_views_retry.py`:

```python
from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportedAuthor, ImportSession


@pytest.fixture
def authed_client(client, django_user_model):
    user = baker.make(django_user_model, is_staff=True)
    user.set_password("test")
    user.save()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_retry_fetch_clears_state_and_enqueues_fetch_task(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_failed_stage="fetch",
        last_error_message="boom",
        last_error_traceback="tb",
        raw_data={"x": 1},
        normalized_data={"title": "stara"},
    )
    # Stwórz powiązane ImportedAuthor (połowicznie zapisane z poprzedniej próby)
    baker.make(ImportedAuthor, session=session, _quantity=3)
    assert session.authors.count() == 3

    url = reverse(
        "importer_publikacji:task-retry", kwargs={"session_id": session.pk}
    )

    with patch(
        "importer_publikacji.views.retry.fetch_session_task"
    ) as mock_task:
        mock_task.delay.return_value.id = "new-task-id"
        response = client.post(url)

    session.refresh_from_db()
    assert response.status_code == 302
    assert "task-status" in response["Location"]
    assert session.status == ImportSession.Status.FETCHING
    assert session.celery_task_id == "new-task-id"
    assert session.last_error_message == ""
    assert session.last_error_traceback == ""
    assert session.last_failed_stage == ""
    assert session.raw_data == {} or session.raw_data is None
    assert session.normalized_data == {} or session.normalized_data is None
    assert session.authors.count() == 0
    mock_task.delay.assert_called_once_with(session.pk, user.pk)


@pytest.mark.django_db
def test_retry_create_enqueues_create_task_and_clears_record_link(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_failed_stage="create",
        last_error_message="create boom",
        created_record_id=999,
    )

    url = reverse(
        "importer_publikacji:task-retry", kwargs={"session_id": session.pk}
    )

    with patch(
        "importer_publikacji.views.retry.create_publication_task"
    ) as mock_task:
        mock_task.delay.return_value.id = "new-task-id-2"
        response = client.post(url)

    session.refresh_from_db()
    assert session.status == ImportSession.Status.CREATING
    assert session.celery_task_id == "new-task-id-2"
    assert session.created_record_id is None
    mock_task.delay.assert_called_once_with(session.pk, user.pk, False)


@pytest.mark.django_db
def test_retry_non_failed_returns_400(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.FETCHED,
    )

    url = reverse(
        "importer_publikacji:task-retry", kwargs={"session_id": session.pk}
    )
    response = client.post(url)

    assert response.status_code == 400


@pytest.mark.django_db
def test_retry_get_returns_405(authed_client):
    client, user = authed_client
    session = baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.IMPORT_FAILED,
        last_failed_stage="fetch",
    )

    url = reverse(
        "importer_publikacji:task-retry", kwargs={"session_id": session.pk}
    )
    response = client.get(url)

    assert response.status_code == 405
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_views_retry.py -v
```

Expected: `FAIL` z błędami importu / `NoReverseMatch`.

- [ ] **Step 3: Zaimplementuj `ImportTaskRetryView`**

Stwórz `src/importer_publikacji/views/retry.py`:

```python
"""Endpoint do retry-owania task-a importera publikacji po błędzie."""

from django.http import HttpResponseBadRequest, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect
from django.views import View

from ..models import ImportSession
from ..permissions import ImporterPermissionMixin
from ..tasks import create_publication_task, fetch_session_task


class ImportTaskRetryView(ImporterPermissionMixin, View):
    """POST — wyczyść state błędu, enqueueuj odpowiedni task ponownie."""

    def post(self, request, session_id):
        session = get_object_or_404(ImportSession, pk=session_id)

        if session.status != ImportSession.Status.IMPORT_FAILED:
            return HttpResponseBadRequest(
                "Retry można wywołać tylko na sesji w stanie IMPORT_FAILED."
            )

        failed_stage = session.last_failed_stage

        # Wyczyść state błędu
        session.last_error_message = ""
        session.last_error_traceback = ""
        session.last_failed_stage = ""

        if failed_stage == "fetch":
            # Cleanup ImportedAuthors + dane fetcha
            session.authors.all().delete()
            session.raw_data = {}
            session.normalized_data = {}
            session.status = ImportSession.Status.FETCHING
            session.save()

            task = fetch_session_task.delay(session.pk, request.user.pk)
            session.celery_task_id = task.id
            session.save(update_fields=["celery_task_id"])

        elif failed_stage == "create":
            session.created_record_content_type = None
            session.created_record_id = None
            session.status = ImportSession.Status.CREATING
            session.save()

            also_pbn = bool(
                session.matched_data.get("pbn_export_pending", False)
            )
            task = create_publication_task.delay(
                session.pk, request.user.pk, also_pbn
            )
            session.celery_task_id = task.id
            session.save(update_fields=["celery_task_id"])

        else:
            return HttpResponseBadRequest(
                f"Nieznany last_failed_stage: {failed_stage}"
            )

        return redirect(
            "importer_publikacji:task-status", session_id=session.pk
        )

    def get(self, request, session_id):
        return HttpResponseNotAllowed(["POST"])
```

- [ ] **Step 4: Dodaj URL**

W `src/importer_publikacji/urls.py`, dodaj wpis (tuż po `task-status`):

```python
    path(
        "task-retry/<uuid:session_id>/",
        ImportTaskRetryView.as_view(),
        name="task-retry",
    ),
```

I import:

```python
from .views.retry import ImportTaskRetryView
```

- [ ] **Step 5: Uruchom testy — powinny PASS**

```bash
uv run pytest src/importer_publikacji/tests/test_views_retry.py -v
```

Expected: `4 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/importer_publikacji/views/retry.py src/importer_publikacji/urls.py src/importer_publikacji/tests/test_views_retry.py
git commit -m "feat(importer_publikacji): ImportTaskRetryView z cleanup-em stanu i ponownym enqueue"
```

---

## Task 11: Refactor `FetchView.post` — enqueue task zamiast pracy inline

**Files:**
- Modify: `src/importer_publikacji/views/wizard.py` (`FetchView.post`, linie 94–207)
- Test: dorzucenie testów do `src/importer_publikacji/tests/test_views.py` (lub nowy plik `test_views_fetch_async.py`)

- [ ] **Step 1: Napisz testy "two-tab" i "enqueue"**

Stwórz `src/importer_publikacji/tests/test_views_fetch_async.py`:

```python
from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportSession


@pytest.fixture
def authed_client(client, django_user_model):
    user = baker.make(django_user_model, is_staff=True)
    user.set_password("test")
    user.save()
    client.force_login(user)
    return client, user


@pytest.mark.django_db
def test_fetch_view_post_creates_session_with_fetching_status(authed_client):
    client, user = authed_client

    with patch(
        "importer_publikacji.views.wizard.fetch_session_task"
    ) as mock_task, patch(
        "importer_publikacji.views.wizard.get_provider"
    ) as mock_provider:
        mock_provider.return_value.input_mode = "identifier"
        mock_provider.return_value.validate_identifier.return_value = "10.1234/x"
        mock_task.delay.return_value.id = "task-uuid"

        response = client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "crossref", "identifier": "10.1234/x"},
        )

    sessions = ImportSession.objects.filter(provider_name="crossref")
    assert sessions.count() == 1
    session = sessions.first()
    assert session.status == ImportSession.Status.FETCHING
    assert session.celery_task_id == "task-uuid"
    mock_task.delay.assert_called_once_with(session.pk, user.pk)
    assert response.status_code in (200, 302)


@pytest.mark.django_db
def test_fetch_view_post_invalid_identifier_returns_form_error(authed_client):
    client, _ = authed_client

    with patch(
        "importer_publikacji.views.wizard.get_provider"
    ) as mock_provider:
        mock_provider.return_value.input_mode = "identifier"
        mock_provider.return_value.validate_identifier.return_value = None

        response = client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "crossref", "identifier": "garbage"},
        )

    assert response.status_code == 200
    # Sesja nie powstała
    assert ImportSession.objects.count() == 0


@pytest.mark.django_db
def test_fetch_view_post_does_not_call_provider_fetch_inline(authed_client):
    """Najważniejsza inwariata: provider.fetch() NIE leci w request,
    tylko w tasku. W teście EAGER=True task wykona się synchronicznie,
    więc fetch() wywoła się — ale z TASKA, nie z view.
    Sprawdzamy że delay() jest wywołane."""
    client, _ = authed_client

    with patch(
        "importer_publikacji.views.wizard.fetch_session_task"
    ) as mock_task, patch(
        "importer_publikacji.views.wizard.get_provider"
    ) as mock_provider:
        mock_provider.return_value.input_mode = "identifier"
        mock_provider.return_value.validate_identifier.return_value = "10.1234/x"

        client.post(
            reverse("importer_publikacji:fetch"),
            {"provider": "crossref", "identifier": "10.1234/x"},
        )

    # View nie powinno wywoływać provider.fetch() bezpośrednio
    mock_provider.return_value.fetch.assert_not_called()
    # Task delay był wywołany
    mock_task.delay.assert_called_once()
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_views_fetch_async.py -v
```

Expected: `FAIL` (test_fetch_view_post_does_not_call_provider_fetch_inline: `provider.fetch` JEST wywołane bo to obecne zachowanie).

- [ ] **Step 3: Refactor `FetchView.post`**

W `src/importer_publikacji/views/wizard.py`, dodaj import na górze:

```python
from .helpers import _push_url
from ..tasks import fetch_session_task
```

(`_push_url` już jest importowane).

Zastąp ciało `FetchView.post` (linie 97–207):

```python
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
            form.add_error(error_field, "Nieprawidłowy format danych.")
            return render(request, STEP_FETCH, _fetch_context(form))

        # Sesja w stanie FETCHING — task zajmie się fetchem + matchowaniem
        session = ImportSession.objects.create(
            created_by=request.user,
            provider_name=provider_name,
            identifier=normalized,
            status=ImportSession.Status.FETCHING,
        )

        task = fetch_session_task.delay(session.pk, request.user.pk)
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
```

Dodaj importy jeśli ich brak (HttpResponse, HttpResponseRedirect):

```python
from django.http import HttpResponse, HttpResponseRedirect
```

Usuń teraz niepotrzebne importy z `wizard.py`: `Komparator`, `_auto_match_authors`, `_prefill_dyscypliny_z_zgloszen`, `ContentType` jeśli były używane tylko w starym `FetchView.post`. **Uwaga**: niektóre z nich mogą być używane przez `CreateView.post` — zostaw je. Sprawdź narzędziem `Grep`/`grep` w pliku:

```bash
grep -n "Komparator\|_auto_match_authors\|_prefill_dyscypliny_z_zgloszen" src/importer_publikacji/views/wizard.py
```

Usuń tylko te, które nie pojawiają się nigdzie indziej w `wizard.py`.

- [ ] **Step 4: Uruchom testy — powinny PASS (nowe i istniejące)**

```bash
uv run pytest src/importer_publikacji/tests/test_views_fetch_async.py -v
```

Expected: `3 passed`.

```bash
uv run pytest src/importer_publikacji/tests/test_views.py -v
```

Expected: jeśli któryś test fail-uje bo "po POST do fetch oczekuję redirectu na verify" — zaktualizuj go: teraz POST → task-status (a w EAGER task wykonuje się i sesja kończy w FETCHED, więc `get_continue_url()` zwraca `verify` przy followup). Dwie strategie:
- (a) Test zmodyfikuj: po POST → follow=True i sprawdź `verify` na docelowym URL.
- (b) Test zmodyfikuj: po POST sprawdź `Location` to `task-status`, potem osobny GET na task-status → HX-Redirect.

Wybierz (a) — najprostsze i odzwierciedla user flow.

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/views/wizard.py src/importer_publikacji/tests/test_views_fetch_async.py src/importer_publikacji/tests/test_views.py
git commit -m "feat(importer_publikacji): FetchView.post enqueueuje fetch_session_task zamiast pracy inline"
```

---

## Task 12: Refactor `CreateView.post` — enqueue task zamiast pracy inline

**Files:**
- Modify: `src/importer_publikacji/views/wizard.py` (`CreateView.post`, linie ~531–591)
- Create: `src/importer_publikacji/tests/test_views_create_async.py`

- [ ] **Step 1: Napisz testy**

Stwórz `src/importer_publikacji/tests/test_views_create_async.py`:

```python
from unittest.mock import patch

import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import ImportSession


@pytest.fixture
def authed_client(client, django_user_model):
    user = baker.make(django_user_model, is_staff=True)
    user.set_password("test")
    user.save()
    client.force_login(user)
    return client, user


@pytest.fixture
def review_session(authed_client):
    _, user = authed_client
    return baker.make(
        ImportSession,
        created_by=user,
        status=ImportSession.Status.REVIEW,
    )


@pytest.mark.django_db
def test_create_view_post_enqueues_task_and_marks_creating(
    authed_client, review_session
):
    client, user = authed_client

    with patch(
        "importer_publikacji.views.wizard.create_publication_task"
    ) as mock_task:
        mock_task.delay.return_value.id = "create-task-uuid"
        url = reverse(
            "importer_publikacji:create",
            kwargs={"session_id": review_session.pk},
        )
        response = client.post(url, {})

    review_session.refresh_from_db()
    assert review_session.status == ImportSession.Status.CREATING
    assert review_session.celery_task_id == "create-task-uuid"
    mock_task.delay.assert_called_once_with(review_session.pk, user.pk, False)
    assert response.status_code in (200, 302)


@pytest.mark.django_db
def test_create_view_post_with_pbn_flag_passes_true(
    authed_client, review_session
):
    client, _ = authed_client

    with patch(
        "importer_publikacji.views.wizard.create_publication_task"
    ) as mock_task:
        mock_task.delay.return_value.id = "create-task-uuid"
        url = reverse(
            "importer_publikacji:create",
            kwargs={"session_id": review_session.pk},
        )
        client.post(url, {"_create_and_pbn": "1"})

    args = mock_task.delay.call_args.args
    assert args[2] is True  # also_pbn=True
```

- [ ] **Step 2: Uruchom testy — powinny FAIL**

```bash
uv run pytest src/importer_publikacji/tests/test_views_create_async.py -v
```

Expected: `FAIL` (`create_publication_task` w `wizard.py` nie istnieje jako import).

- [ ] **Step 3: Refactor `CreateView.post`**

W `src/importer_publikacji/views/wizard.py`, dodaj import:

```python
from ..tasks import create_publication_task
```

Zastąp ciało `CreateView.post` (linie ~531–591):

```python
class CreateView(ImporterPermissionMixin, View):
    """Enqueueuje create_publication_task; redirect na task-status."""

    def post(self, request, session_id):
        session = get_object_or_404(ImportSession, pk=session_id)

        also_pbn = "_create_and_pbn" in request.POST
        session.status = ImportSession.Status.CREATING
        session.save(update_fields=["status"])

        task = create_publication_task.delay(
            session.pk, request.user.pk, also_pbn
        )
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
```

> Usuń `try/except` z oryginalnego `CreateView.post` — błędy obsługuje teraz task, user widzi je w `task-status`.

- [ ] **Step 4: Uruchom testy**

```bash
uv run pytest src/importer_publikacji/tests/test_views_create_async.py src/importer_publikacji/tests/test_views.py -v
```

Expected: nowe testy `PASS`. Istniejące testy `test_views.py::test_create_*` mogą wymagać update-u na podobnej zasadzie jak FetchView (zob. Task 11 step 4).

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/views/wizard.py src/importer_publikacji/tests/test_views_create_async.py src/importer_publikacji/tests/test_views.py
git commit -m "feat(importer_publikacji): CreateView.post enqueueuje create_publication_task"
```

---

## Task 13: Pełny test suite + manual smoke test

**Files:** (verification only)

- [ ] **Step 1: Uruchom pełny suite testów modułu**

```bash
uv run pytest src/importer_publikacji/tests/ -v
```

Expected: wszystkie testy `PASS`. Jeśli któryś fail-uje:
- Czytaj message uważnie.
- Najczęstsza przyczyna: istniejące testy zakładały, że POST do `fetch` wykonuje pracę inline. Trzeba dopisać `follow=True` lub zmienić assercje na ten URL z `task-status`.

- [ ] **Step 2: Uruchom pełny suite testów BPP (bez playwright)**

```bash
make tests-without-playwright
```

Expected: wszystkie testy `PASS`. Może potrwać do 8 min.

- [ ] **Step 3: Manual smoke test — uruchom dev stack**

```bash
uv run run-site run --no-browser
```

W innej zakładce / oknie poczekaj aż banner pokaże `http://localhost:<port>` i pobierz port:

```bash
PORT=$(grep -oE 'http://localhost:[0-9]+' /tmp/run_site.log 2>/dev/null | head -1 || cat .dev_helpers_port)
echo "Dev stack: http://localhost:$PORT"
```

Otwórz w przeglądarce `http://localhost:$PORT/importer_publikacji/`, zaloguj się (admin/admin), wpisz DOI np. `10.1016/j.cyto.2013.08.002` (artykuł z Cytokine, dużo autorów), kliknij "Dalej". Sprawdź:

- Przeglądarka NIE wisi — zaraz dostajemy widok task-status ze spinnerem.
- Pasek rośnie, etykiety zmieniają się ("Pobieram...", "Dopasowuję autorów (12/53)...").
- Po zakończeniu user przeskakuje na krok Verify.
- W przypadku celowego błędu (np. DOI nie istnieje — `10.0000/nonsense`): user widzi callout `alert` z "Nie udało się pobrać danych z dostawcy", przycisk "Spróbuj ponownie".

- [ ] **Step 4: Manual smoke test — Create**

Przejdź wizard do końca (Verify → Source → Authors → Review), kliknij "Utwórz rekord". Sprawdź że view nie wisi — task-status pokazuje się, pasek leci, kończy na "Done".

- [ ] **Step 5: Manual smoke test — superuser widzi traceback**

W bazie wyzeruj sesję na ścieżkę błędu: `uv run python src/manage.py shell -c "from importer_publikacji.models import ImportSession; s = ImportSession.objects.last(); s.status = s.Status.IMPORT_FAILED; s.last_error_message = 'Test msg'; s.last_error_traceback = 'fake traceback'; s.last_failed_stage = 'fetch'; s.save()"`

Otwórz `http://localhost:$PORT/importer_publikacji/task-status/<session_pk>/`. Sprawdź że jako superuser widzisz sekcję "Traceback (admin)" z `<details>`. Wyloguj się i zaloguj jako zwykły user — traceback powinien zniknąć.

- [ ] **Step 6: Commit jakichkolwiek poprawek z smoke testów**

Jeśli smoke testy wykazały bug — popraw, dorzuć test, scommituj:

```bash
git add <files>
git commit -m "fix(importer_publikacji): <opis>"
```

- [ ] **Step 7: Final push (do PR)**

```bash
git push -u origin feat/importer-async-fetch
```

Następnie utwórz PR ręcznie lub przez `gh pr create` (patrz `commit-commands:commit-push-pr` skill).

---

## Self-review (po napisaniu planu)

**1. Spec coverage** — każda sekcja speca pokryta:
- §3.1 Nowe pliki — Task 4 (progress.py), Task 7+8 (tasks.py), Task 9 (task_status.py + 3 templates), Task 10 (retry.py), Task 1 (migracja), testy w 4/5/7/8/9/10/11/12.
- §3.2 Zmiany w istniejących — Task 1 (modele), Task 2 (get_continue_url), Task 3 (template), Task 6 (refactor authors.py), Task 11+12 (FetchView/CreateView), Task 9+10 (urls.py).
- §3.3 Stages i wagi — Task 4.
- §3.4 Anatomia taska — Task 7 (fetch), Task 8 (create).
- §3.5 Widok statusu — Task 9.
- §3.6 Retry — Task 10.
- §3.7 Error handling — Task 5 (user_safe_message), Task 7+8 (try/except + raise pattern).
- §3.8 Auth — Task 9+10 (`ImporterPermissionMixin`).
- §5 Testowanie — Task 4/5/7/8/9/10/11/12 (TDD per task), Task 13 (manual).
- §8 Otwarte ryzyka — "Stale sesje gdy worker padnie" NIE pokryte żadnym taskem (świadomie odsuwam do follow-up — w spec sekcja 8 jest oznaczona jako "ryzyko", nie wymaganie).

**2. Placeholder scan** — sprawdzone, brak "TBD" / "TODO".

**3. Type/name consistency** — sprawdzone:
- `fetch_session_task(self, session_id, request_user_id)` — używane spójnie w Task 7/10/11.
- `create_publication_task(self, session_id, request_user_id, also_pbn)` — Task 8/10/12.
- `report_progress(task, stage_code, sub_current=0, sub_total=1, *, stages)` — Task 4/7/8.
- `user_safe_message(exc, *, task_kind)` — Task 5/7/8.
- `Status.FETCHING / CREATING / IMPORT_FAILED` — Task 1/2/9/10/11/12.
- Pola `celery_task_id / last_error_message / last_error_traceback / last_failed_stage` — Task 1/7/8/9/10/11/12.

**4. Otwarte items (zostawione świadomie):**
- PBN export z poziomu taska wymaga albo (a) request stuba który spełnia helper, albo (b) refactoru helpera. Task 8 step 4 instruuje implementatora żeby sprawdził helpera i podjął decyzję. Jeśli refactor — to osobny commit w ramach Task 8.

---

## Wykonanie planu

Plan complete and saved to `docs/superpowers/plans/2026-05-21-importer-async-fetch.md`. Dwie opcje wykonania:

1. **Subagent-Driven (recommended)** — dispatchuję świeżego subagenta per task, review między taskami, szybka iteracja.
2. **Inline Execution** — wykonuję tasks w obecnej sesji, batch z checkpointami.

Którą wybierasz?
