# Import wielu prac z BibTeX (`MultipleWorksImport`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gdy user wklei ≥2 wpisy BibTeX do importera publikacji, zapisz je w nadrzędnym rekordzie `MultipleWorksImport` (+ dzieci `MultipleWorksImportEntry`) i pozwól importować po jednym, z per-wpis statusem, pominięciem i ponowieniem — zamiast po cichu importować tylko pierwszy wpis.

**Architecture:** Fan-out w warstwie wejścia (`FetchView.post`), nie w `fetch()` providera. Provider dostaje nadpisywalne `split_input(text) -> list[SplitRecord]` (BibTeX zwraca po jednym rekordzie na wpis oraz na uszkodzony blok). Status wpisu jest **wyliczany** z `ImportSession.status` + `skipped` + `parse_error` (jedno źródło prawdy). `ImportSession` pozostaje nietknięty (1 sesja = 1 praca).

**Tech Stack:** Django, `bibtexparser` 2.0.0b9 (v2 API: `parse_string`, `library.blocks`, `entry.raw`, `entry.fields_dict[k].value`, `library.failed_blocks`), pytest + `model_bakery`, HTMX (formularz fetch).

## Global Constraints

- Max line length: 88 znaków (ruff).
- Python `uv run` prefix dla WSZYSTKICH komend Pythona/pytest.
- NIE modyfikować istniejących migracji w `src/*/migrations/`.
- NIE odświeżać `baseline-sql/baseline.sql` na tym branchu (refresh przy scalaniu do `dev`).
- Testy: pytest (funkcje, bez klas `unittest.TestCase`), `@pytest.mark.django_db`, `model_bakery.baker.make`.
- Django template comments `{# … #}` — każda linia własny `{# … #}`.
- Nazwa FK usera: `created_by` (spójnie z `ImportSession`).
- Provider `name` dla BibTeX = `"BibTeX"`.
- `ImportSession.Status` (istniejące): `FETCHED, FETCHING, CREATING, IMPORT_FAILED, VERIFIED, SOURCE_MATCHED, AUTHORS_MATCHED, PUNKTACJA, PBN_CHECK, REVIEW, COMPLETED, CANCELLED`.

---

### Task 1: `SplitRecord` + `DataProvider.split_input` (domyślnie jedno-rekordowy)

**Files:**
- Modify: `src/importer_publikacji/providers/__init__.py`
- Test: `src/importer_publikacji/tests/test_split_input.py`

**Interfaces:**
- Produces: `SplitRecord(raw: str, ok: bool = True, title: str = "", error: str = "")` (dataclass) i metoda `DataProvider.split_input(self, text: str) -> list[SplitRecord]` zwracająca domyślnie `[SplitRecord(raw=text)]`.

- [ ] **Step 1: Write the failing test**

Utwórz `src/importer_publikacji/tests/test_split_input.py`:

```python
from importer_publikacji.providers import DataProvider, SplitRecord


class _DummyProvider(DataProvider):
    name = "Dummy"
    identifier_label = "X"

    def fetch(self, identifier):
        return None

    def validate_identifier(self, identifier):
        return identifier


def test_split_input_default_returns_single_record():
    records = _DummyProvider().split_input("cokolwiek")
    assert records == [SplitRecord(raw="cokolwiek")]
    assert records[0].ok is True
    assert records[0].title == ""
    assert records[0].error == ""
```

(`name`/`identifier_label` nadpisane atrybutem klasy — abstract property da się tak spełnić w podklasie konkretnej.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Programowanie/bpp-bibtex-import-wiele-prac && uv run pytest src/importer_publikacji/tests/test_split_input.py -v`
Expected: FAIL — `ImportError: cannot import name 'SplitRecord'`.

- [ ] **Step 3: Write minimal implementation**

W `src/importer_publikacji/providers/__init__.py` dodaj dataclass tuż pod `FetchedPublication` (po linii 35):

```python
@dataclass
class SplitRecord:
    """Pojedynczy rekord wyodrębniony z surowego wejścia providera.

    ``ok is False`` oznacza fragment, który się nie sparsował (np. uszkodzony
    blok BibTeX) — niesiemy go dalej, żeby nic nie znikało po cichu.
    """

    raw: str
    ok: bool = True
    title: str = ""
    error: str = ""
```

W klasie `DataProvider` dodaj metodę (po `input_help_text`, przed `fetch`):

```python
    def split_input(self, text: str) -> list["SplitRecord"]:
        """Rozbij surowe wejście na pojedyncze rekordy.

        Domyślnie provider jest jedno-rekordowy i zwraca wejście bez zmian.
        Providery wielo-rekordowe (BibTeX) nadpisują tę metodę.
        """
        return [SplitRecord(raw=text)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/importer_publikacji/tests/test_split_input.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/bpp-bibtex-import-wiele-prac
git add src/importer_publikacji/providers/__init__.py src/importer_publikacji/tests/test_split_input.py
git commit -m "feat(importer_publikacji): SplitRecord + DataProvider.split_input (domyslnie 1-rekordowy)"
```

---

### Task 2: `BibTeXProvider.split_input` + `peek_title` (wpisy + uszkodzone bloki)

**Files:**
- Modify: `src/importer_publikacji/providers/bibtex.py`
- Test: `src/importer_publikacji/tests/test_split_input.py` (dopisz), `src/importer_publikacji/tests/test_bibtex_provider.py` (regresja — bez zmian, tylko uruchomienie)

**Interfaces:**
- Consumes: `SplitRecord` z Task 1.
- Produces: `BibTeXProvider.split_input(text) -> list[SplitRecord]` — jeden rekord na `library.blocks` będący `Entry` (`ok=True`, `title` z `peek_title`) lub `ParsingFailedBlock` (`ok=False`, `error`). Kolejność źródłowa. `BibTeXProvider.peek_title(entry) -> str`.

- [ ] **Step 1: Write the failing tests**

Dopisz do `src/importer_publikacji/tests/test_split_input.py`:

```python
from importer_publikacji.providers import get_provider

SAMPLE_A = """@article{a,
  title = {Pierwsza praca},
  author = {Kowalski, Jan},
  year = {2021},
}"""

SAMPLE_B = """@book{b,
  title = {Druga praca},
  author = {Nowak, Anna},
  year = {2022},
}"""

# Uszkodzony blok: brak zamkniecia klamry / smiec skladniowy.
BROKEN = "@article{c, title = {Trzecia"


def test_bibtex_split_multiple_entries_order_preserved():
    provider = get_provider("BibTeX")
    records = provider.split_input(SAMPLE_A + "\n\n" + SAMPLE_B)
    assert len(records) == 2
    assert all(r.ok for r in records)
    assert records[0].title == "Pierwsza praca"
    assert records[1].title == "Druga praca"
    # Kazdy raw re-parsuje sie do dokladnie jednego wpisu:
    import bibtexparser

    for r in records:
        assert len(bibtexparser.parse_string(r.raw).entries) == 1


def test_bibtex_split_keeps_broken_block_as_failed_record():
    provider = get_provider("BibTeX")
    records = provider.split_input(SAMPLE_A + "\n\n" + BROKEN + "\n\n" + SAMPLE_B)
    # Nic nie znika: 3 rekordy (2 ok + 1 uszkodzony), kolejnosc zrodlowa.
    assert len(records) == 3
    assert [r.ok for r in records] == [True, False, True]
    assert records[1].error  # niepusty komunikat
    assert records[0].title == "Pierwsza praca"
    assert records[2].title == "Druga praca"


def test_bibtex_peek_title_missing_returns_empty():
    provider = get_provider("BibTeX")
    records = provider.split_input("@misc{x, author = {Ktos, Ktos}}")
    assert len(records) == 1
    assert records[0].title == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/importer_publikacji/tests/test_split_input.py -v`
Expected: FAIL — `AttributeError: 'BibTeXProvider' object has no attribute 'split_input'`? (nie — dziedziczy domyślne; padnie na `len(records) == 2`, bo domyślne zwraca 1). Expected: FAIL na asercji liczby rekordów.

- [ ] **Step 3: Write implementation**

W `src/importer_publikacji/providers/bibtex.py` zmień import na górze (linia 8-13) tak, by dołączyć `SplitRecord`:

```python
from . import (
    DataProvider,
    FetchedPublication,
    InputMode,
    SplitRecord,
    register_provider,
)
```

Dodaj `from bibtexparser.model import Entry, ParsingFailedBlock` pod `import bibtexparser` (linia 4):

```python
import bibtexparser
from bibtexparser.model import Entry, ParsingFailedBlock
```

W klasie `BibTeXProvider` dodaj metody (np. po `validate_identifier`, przed `fetch`):

```python
    def peek_title(self, entry) -> str:
        """Wyciągnij tytuł z wpisu do wyświetlenia (unwrap Field + LaTeX)."""
        return _get_field(entry.fields_dict, "title", "")

    def split_input(self, text: str) -> list[SplitRecord]:
        """Rozbij wklejony BibTeX na pojedyncze rekordy.

        Każdy poprawny wpis → jeden ``SplitRecord(ok=True)`` z ``entry.raw``
        (verbatim). Każdy uszkodzony blok (``failed_blocks``) → jeden
        ``SplitRecord(ok=False)`` niosący surowy tekst + komunikat — inaczej
        znikałby po cichu (dokładnie bug, który naprawiamy). Kolejność
        źródłowa zachowana przez iterację po ``library.blocks``.
        """
        library = bibtexparser.parse_string(text)
        records: list[SplitRecord] = []
        for block in library.blocks:
            if isinstance(block, Entry):
                records.append(
                    SplitRecord(raw=block.raw, ok=True, title=self.peek_title(block))
                )
            elif isinstance(block, ParsingFailedBlock):
                records.append(
                    SplitRecord(
                        raw=block.raw,
                        ok=False,
                        error="Nie udało się sparsować wpisu BibTeX.",
                    )
                )
        return records
```

(`_get_field` już istnieje w tym module i robi `.value` + `str().strip()`; `peek_title` domyślnie NIE odpala `_clean_latex` — tytuł do wyświetlenia zwykle jest czysty. Jeśli w praktyce klamry przeszkadzają, owinąć w `_clean_latex` w osobnym commicie.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/importer_publikacji/tests/test_split_input.py src/importer_publikacji/tests/test_bibtex_provider.py -v`
Expected: PASS (w tym istniejący `test_fetch_multiple_entries_takes_first` — dowód, że `fetch()` się nie zmieniło).

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/providers/bibtex.py src/importer_publikacji/tests/test_split_input.py
git commit -m "feat(importer_publikacji): BibTeXProvider.split_input + peek_title (wpisy + uszkodzone bloki)"
```

---

### Task 3: Modele `MultipleWorksImport` + `MultipleWorksImportEntry` + migracja + admin

**Files:**
- Modify: `src/importer_publikacji/models.py` (dopisz na końcu)
- Modify: `src/importer_publikacji/admin.py`
- Create: `src/importer_publikacji/migrations/00XX_multiple_works_import.py` (wygenerowana)
- Test: `src/importer_publikacji/tests/test_models_batch.py`

**Interfaces:**
- Consumes: `ImportSession` (istniejący).
- Produces:
  - `MultipleWorksImport(created_by, provider_name, raw_input, created, modified)`; property `progress -> dict` z kluczami `imported, skipped, total, done`.
  - `MultipleWorksImportEntry(parent, order, raw_bibtex, title, parse_error, skipped, session)` z `session = OneToOneField(ImportSession, null=True, related_name="batch_entry")`; property `status -> str` (wartości z `EntryStatus`).
  - `EntryStatus` (TextChoices): `PENDING, IN_PROGRESS, IMPORTED, FAILED, SKIPPED, MALFORMED`.

- [ ] **Step 1: Write the failing tests**

Utwórz `src/importer_publikacji/tests/test_models_batch.py`:

```python
import pytest
from model_bakery import baker

from importer_publikacji.models import (
    EntryStatus,
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)


@pytest.mark.django_db
def test_entry_status_pending_without_session():
    entry = baker.make(MultipleWorksImportEntry, session=None, skipped=False)
    assert entry.status == EntryStatus.PENDING


@pytest.mark.django_db
def test_entry_status_malformed_when_parse_error():
    entry = baker.make(
        MultipleWorksImportEntry, session=None, parse_error="zepsute", skipped=False
    )
    assert entry.status == EntryStatus.MALFORMED


@pytest.mark.django_db
def test_entry_status_skipped_beats_pending():
    entry = baker.make(MultipleWorksImportEntry, session=None, skipped=True)
    assert entry.status == EntryStatus.SKIPPED


@pytest.mark.django_db
def test_entry_status_imported_when_session_completed():
    session = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    entry = baker.make(MultipleWorksImportEntry, session=session)
    assert entry.status == EntryStatus.IMPORTED


@pytest.mark.django_db
def test_entry_status_failed_when_session_import_failed():
    session = baker.make(ImportSession, status=ImportSession.Status.IMPORT_FAILED)
    entry = baker.make(MultipleWorksImportEntry, session=session)
    assert entry.status == EntryStatus.FAILED


@pytest.mark.django_db
def test_entry_status_failed_when_session_stalled(monkeypatch):
    session = baker.make(ImportSession, status=ImportSession.Status.FETCHING)
    monkeypatch.setattr(session, "is_stalled", lambda: True)
    entry = MultipleWorksImportEntry(
        parent=baker.make(MultipleWorksImport), order=0, session=session
    )
    assert entry.status == EntryStatus.FAILED


@pytest.mark.django_db
def test_entry_status_cancelled_maps_to_pending():
    session = baker.make(ImportSession, status=ImportSession.Status.CANCELLED)
    entry = baker.make(MultipleWorksImportEntry, session=session)
    assert entry.status == EntryStatus.PENDING


@pytest.mark.django_db
def test_entry_status_in_progress_mid_wizard():
    session = baker.make(ImportSession, status=ImportSession.Status.VERIFIED)
    entry = baker.make(MultipleWorksImportEntry, session=session)
    assert entry.status == EntryStatus.IN_PROGRESS


@pytest.mark.django_db
def test_progress_counts():
    batch = baker.make(MultipleWorksImport)
    done = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=done)
    baker.make(MultipleWorksImportEntry, parent=batch, order=1, skipped=True)
    baker.make(MultipleWorksImportEntry, parent=batch, order=2, session=None)
    progress = batch.progress
    assert progress == {"imported": 1, "skipped": 1, "total": 3, "done": False}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/importer_publikacji/tests/test_models_batch.py -v`
Expected: FAIL — `ImportError: cannot import name 'MultipleWorksImport'`.

- [ ] **Step 3: Implement models**

Dopisz na końcu `src/importer_publikacji/models.py`:

```python
class EntryStatus(models.TextChoices):
    PENDING = "pending", "Oczekuje"
    IN_PROGRESS = "in_progress", "W toku"
    IMPORTED = "imported", "Zaimportowano"
    FAILED = "failed", "Błąd"
    SKIPPED = "skipped", "Pominięty"
    MALFORMED = "malformed", "Uszkodzony"


class MultipleWorksImport(models.Model):
    """Paczka wielu prac wklejonych naraz (stager) — np. wielo-wpisowy BibTeX.

    Trzyma surowy wsad i N dzieci (``entries``); pojedyncza ``ImportSession``
    powstaje leniwie dopiero na żądanie importu konkretnego wpisu.
    """

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="importer_publikacji_batches",
        verbose_name="utworzył",
    )
    provider_name = models.CharField("dostawca danych", max_length=50)
    raw_input = models.TextField("surowy wsad")
    created = models.DateTimeField("utworzono", auto_now_add=True)
    modified = models.DateTimeField("zmodyfikowano", auto_now=True)

    class Meta:
        verbose_name = "import wielu prac"
        verbose_name_plural = "importy wielu prac"
        ordering = ["-created"]

    def __str__(self):
        return f"{self.provider_name}: paczka #{self.pk}"

    @property
    def progress(self) -> dict:
        entries = list(self.entries.select_related("session"))
        imported = sum(1 for e in entries if e.status == EntryStatus.IMPORTED)
        skipped = sum(1 for e in entries if e.status == EntryStatus.SKIPPED)
        total = len(entries)
        done = all(
            e.status in (EntryStatus.IMPORTED, EntryStatus.SKIPPED) for e in entries
        )
        return {
            "imported": imported,
            "skipped": skipped,
            "total": total,
            "done": done if total else False,
        }


class MultipleWorksImportEntry(models.Model):
    """Pojedynczy wpis paczki. Status jest WYLICZANY z ``session`` +
    ``skipped`` + ``parse_error`` — nie przechowujemy go, żeby nie rozjeżdżał
    się z ``ImportSession.status``."""

    parent = models.ForeignKey(
        MultipleWorksImport,
        on_delete=models.CASCADE,
        related_name="entries",
        verbose_name="paczka",
    )
    order = models.PositiveIntegerField("kolejność", default=0)
    raw_bibtex = models.TextField("pojedynczy wpis BibTeX")
    title = models.TextField("tytuł (podgląd)", blank=True, default="")
    parse_error = models.TextField("błąd parsowania", blank=True, default="")
    skipped = models.BooleanField("pominięty", default=False)
    session = models.OneToOneField(
        ImportSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_entry",
        verbose_name="sesja importu",
    )

    class Meta:
        verbose_name = "wpis paczki"
        verbose_name_plural = "wpisy paczki"
        ordering = ["order"]

    def __str__(self):
        return f"#{self.order}: {self.title or '(bez tytułu)'}"

    @property
    def status(self) -> str:
        session = self.session
        if session is not None and session.status == ImportSession.Status.COMPLETED:
            return EntryStatus.IMPORTED
        if self.skipped:
            return EntryStatus.SKIPPED
        if self.parse_error:
            return EntryStatus.MALFORMED
        if session is None:
            return EntryStatus.PENDING
        if session.status == ImportSession.Status.IMPORT_FAILED or session.is_stalled():
            return EntryStatus.FAILED
        if session.status == ImportSession.Status.CANCELLED:
            return EntryStatus.PENDING
        return EntryStatus.IN_PROGRESS
```

- [ ] **Step 4: Generate migration**

Run:
```bash
uv run python src/manage.py makemigrations importer_publikacji -n multiple_works_import
```
Expected: nowy plik migracji w `src/importer_publikacji/migrations/`. Zweryfikuj brak driftu:
```bash
uv run python src/manage.py makemigrations --check --dry-run
```
Expected: „No changes detected".

- [ ] **Step 5: Register in admin**

W `src/importer_publikacji/admin.py` zmień import modeli:

```python
from .models import (
    ImportedAuthor,
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)
```

Dopisz na końcu pliku:

```python
class MultipleWorksImportEntryInline(admin.TabularInline):
    model = MultipleWorksImportEntry
    extra = 0
    fields = ["order", "title", "skipped", "parse_error", "session"]
    readonly_fields = ["order", "title", "parse_error", "session"]


@admin.register(MultipleWorksImport)
class MultipleWorksImportAdmin(admin.ModelAdmin):
    list_display = ["id", "created", "provider_name", "created_by"]
    list_filter = ["provider_name", "created", "created_by"]
    list_select_related = ["created_by"]
    date_hierarchy = "created"
    inlines = [MultipleWorksImportEntryInline]
```

- [ ] **Step 6: Run tests + admin check**

Run:
```bash
uv run pytest src/importer_publikacji/tests/test_models_batch.py -v
uv run python src/manage.py check
```
Expected: testy PASS, `check` bez błędów.

- [ ] **Step 7: Commit**

```bash
git add src/importer_publikacji/models.py src/importer_publikacji/admin.py src/importer_publikacji/migrations/
git add src/importer_publikacji/tests/test_models_batch.py
git commit -m "feat(importer_publikacji): modele MultipleWorksImport(+Entry) ze statusem wyliczanym"
```

---

### Task 4: Fan-out w `FetchView.post` + helper `_start_import_session`

**Files:**
- Modify: `src/importer_publikacji/views/wizard.py`
- Modify: `src/importer_publikacji/urls.py` (dodaj route `batch-detail` — placeholder widoku w Task 5; tu potrzebny do `reverse`)
- Test: `src/importer_publikacji/tests/test_views_batch.py`

**Interfaces:**
- Consumes: `provider.split_input` (Task 2), `MultipleWorksImport`/`MultipleWorksImportEntry` (Task 3).
- Produces: funkcja modułowa `_start_import_session(request, provider_name, identifier) -> ImportSession` (tworzy sesję FETCHING + enqueue `fetch_session_task`, BEZ guardu double-click). `FetchView.post` przy `len(records) >= 2` tworzy paczkę i zwraca `HX-Redirect` na `batch-detail`.

> Kolejność: ten Task zakłada, że route `importer_publikacji:batch-detail` istnieje. Dodajemy go tu wraz z tymczasowym `MultipleWorksImportDetailView` (pełną treść dostaje w Task 5). Jeśli wykonujesz Task 5 równolegle — uzgodnij, że route dodaje Task 4.

- [ ] **Step 1: Write the failing test**

Utwórz `src/importer_publikacji/tests/test_views_batch.py`:

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from importer_publikacji.models import (
    ImportSession,
    MultipleWorksImport,
    MultipleWorksImportEntry,
)

TWO_ENTRIES = """@article{a,
  title = {Pierwsza},
  author = {Kowalski, Jan},
  year = {2021},
}

@book{b,
  title = {Druga},
  author = {Nowak, Anna},
  year = {2022},
}"""

ONE_ENTRY = """@article{a,
  title = {Jedyna},
  author = {Kowalski, Jan},
  year = {2021},
}"""


@pytest.fixture
def operator(django_user_model):
    user = baker.make(django_user_model, is_superuser=True, is_staff=True)
    return user


@pytest.mark.django_db
def test_fetch_two_entries_creates_batch_and_hx_redirects(client, operator):
    client.force_login(operator)
    resp = client.post(
        reverse("importer_publikacji:fetch"),
        {"provider": "BibTeX", "text_input": TWO_ENTRIES},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    batch = MultipleWorksImport.objects.get()
    assert batch.entries.count() == 2
    assert MultipleWorksImportEntry.objects.filter(session__isnull=False).count() == 0
    expected = reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    assert resp["HX-Redirect"] == expected
    # Zaden ImportSession nie powstal (leniwy drip):
    assert ImportSession.objects.count() == 0


@pytest.mark.django_db
def test_fetch_single_entry_unchanged(client, operator):
    client.force_login(operator)
    resp = client.post(
        reverse("importer_publikacji:fetch"),
        {"provider": "BibTeX", "text_input": ONE_ENTRY},
        HTTP_HX_REQUEST="true",
    )
    assert resp.status_code == 200
    assert MultipleWorksImport.objects.count() == 0
    session = ImportSession.objects.get()
    assert resp["HX-Redirect"] == reverse(
        "importer_publikacji:task-status", kwargs={"session_id": session.pk}
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -v`
Expected: FAIL — `NoReverseMatch: 'batch-detail'` (route jeszcze nie istnieje).

- [ ] **Step 3: Add route + temporary detail view**

W `src/importer_publikacji/urls.py` dodaj do `urlpatterns` (przed `task-status`):

```python
    path(
        "batch/<int:batch_id>/",
        views.MultipleWorksImportDetailView.as_view(),
        name="batch-detail",
    ),
```

W `src/importer_publikacji/views/wizard.py` dodaj tymczasowy widok (pełna treść w Task 5) — na razie minimalny GET, żeby route był rozwiązywalny. Dopisz do importów z `..models` (linia 28): `MultipleWorksImport, MultipleWorksImportEntry`. Dodaj klasę:

```python
class MultipleWorksImportDetailView(ImporterPermissionMixin, View):
    def get(self, request, batch_id):
        batch = get_object_or_404(MultipleWorksImport, pk=batch_id)
        return HttpResponse(f"batch {batch.pk}")  # Task 5 zastąpi renderem
```

Zarejestruj w `src/importer_publikacji/views/__init__.py`: dodaj `MultipleWorksImportDetailView` do importu z `.wizard` oraz do `__all__`.

- [ ] **Step 4: Implement helper + fan-out**

W `src/importer_publikacji/views/wizard.py` dodaj funkcję modułową (np. nad `FetchView`):

```python
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
```

W `FetchView.post`, po bloku walidacji `normalized is None` (po linii 127) a przed guardem idempotencji, wstaw fan-out:

```python
        # Wielo-rekordowe wejście (BibTeX z ≥2 wpisami) → paczka, nie pojedyncza
        # sesja. Pojedyncze sesje powstają leniwie przy imporcie wpisu.
        records = provider.split_input(normalized)
        if len(records) >= 2:
            batch = MultipleWorksImport.objects.create(
                created_by=request.user,
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
            url = reverse(
                "importer_publikacji:batch-detail",
                kwargs={"batch_id": batch.pk},
            )
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=200)
                response["HX-Redirect"] = url
                return response
            return HttpResponseRedirect(url)
```

Następnie zamień istniejące jawne tworzenie sesji (linie 153-165) na wywołanie helpera:

```python
        session = _start_import_session(request, provider_name, normalized)
```

(usuwając stary blok `ImportSession.objects.create(...)` + `fetch_session_task.delay` + `save`). Reszta (`url = reverse(... task-status ...)` + HX-Redirect) bez zmian.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py src/importer_publikacji/tests/test_views_fetch_async.py -v`
Expected: PASS (nowe + regresja istniejących fetch-testów).

- [ ] **Step 6: Commit**

```bash
git add src/importer_publikacji/views/wizard.py src/importer_publikacji/views/__init__.py src/importer_publikacji/urls.py src/importer_publikacji/tests/test_views_batch.py
git commit -m "feat(importer_publikacji): fan-out ≥2 wpisow BibTeX do MultipleWorksImport"
```

---

### Task 5: `MultipleWorksImportDetailView` + szablon `batch_detail.html` (+ sweep stalled)

**Files:**
- Modify: `src/importer_publikacji/views/wizard.py` (rozbuduj widok z Task 4)
- Modify: `src/importer_publikacji/views/helpers.py` (dodaj stałą ścieżki szablonu)
- Create: `src/importer_publikacji/templates/importer_publikacji/partials/batch_detail.html`
- Test: `src/importer_publikacji/tests/test_views_batch.py` (dopisz)

**Interfaces:**
- Consumes: `MultipleWorksImport`, `EntryStatus` (Task 3), `_render_full_page` (istn.).
- Produces: `MultipleWorksImportDetailView.get` renderuje pełną stronę z listą wpisów; przed renderem robi sweep `mark_stalled()` po wpisach in-flight. Stała `BATCH_DETAIL = "importer_publikacji/partials/batch_detail.html"`.

- [ ] **Step 1: Write the failing test**

Dopisz do `src/importer_publikacji/tests/test_views_batch.py`:

```python
from importer_publikacji.models import EntryStatus


@pytest.mark.django_db
def test_batch_detail_lists_entries_and_progress(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    done = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, title="Alfa", session=done
    )
    baker.make(MultipleWorksImportEntry, parent=batch, order=1, title="Beta")
    resp = client.get(
        reverse("importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk})
    )
    assert resp.status_code == 200
    content = resp.content.decode()
    assert "Alfa" in content
    assert "Beta" in content
    assert "1 z 2" in content


@pytest.mark.django_db
def test_batch_detail_marks_stalled_session_as_failed(client, operator, settings):
    settings.IMPORTER_STALL_TIMEOUT = 0  # kazda sesja in-flight = stalled
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    stuck = baker.make(ImportSession, status=ImportSession.Status.FETCHING)
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, session=stuck
    )
    client.get(
        reverse("importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk})
    )
    entry.refresh_from_db()
    entry.session.refresh_from_db()
    assert entry.session.status == ImportSession.Status.IMPORT_FAILED
    assert entry.status == EntryStatus.FAILED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -k batch_detail -v`
Expected: FAIL — widok zwraca `HttpResponse("batch N")`, brak „Alfa"/„1 z 2".

- [ ] **Step 3: Add template-path constant**

W `src/importer_publikacji/views/helpers.py` dodaj po `SESSIONS_PARTIAL` (linia 34):

```python
BATCH_DETAIL = "importer_publikacji/partials/batch_detail.html"
```

- [ ] **Step 4: Implement the view**

W `src/importer_publikacji/views/wizard.py` zaktualizuj import z `.helpers` (dodaj `BATCH_DETAIL`) i zastąp tymczasowy `MultipleWorksImportDetailView`:

```python
class MultipleWorksImportDetailView(ImporterPermissionMixin, View):
    """Lista wpisów paczki z per-wpis statusem i akcjami (drip import)."""

    def get(self, request, batch_id):
        batch = get_object_or_404(MultipleWorksImport, pk=batch_id)
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
```

- [ ] **Step 5: Create the template**

Utwórz `src/importer_publikacji/templates/importer_publikacji/partials/batch_detail.html`. Sprawdź linię `{% extends %}` w `src/importer_publikacji/templates/importer_publikacji/partials/step_fetch.html` (albo `index.html`) i użyj tego samego bloku treści. Zawartość bloku:

```django
<div class="callout primary">
    <h4>Import wielu prac ({{ batch.provider_name }})</h4>
    <p>
        Zaimportowano
        <strong>{{ progress.imported }} z {{ progress.total }}</strong>
        {% if progress.skipped %}(+{{ progress.skipped }} pominiętych){% endif %}
    </p>
</div>

<table class="stack hover">
    <thead>
        <tr>
            <th>#</th>
            <th>Tytuł</th>
            <th>Status</th>
            <th>Akcja</th>
        </tr>
    </thead>
    <tbody>
        {% for entry in entries %}
            <tr>
                <td>{{ forloop.counter }}</td>
                <td>{{ entry.title|default:"(bez tytułu)" }}</td>
                <td>{{ entry.get_status_display_badge }}</td>
                <td>
                    {% if entry.status == "pending" %}
                        <form method="post"
                              action="{% url 'importer_publikacji:batch-entry-import' entry_id=entry.pk %}">
                            {% csrf_token %}
                            <button type="submit" class="button tiny">Importuj</button>
                        </form>
                    {% elif entry.status == "in_progress" %}
                        <a class="button tiny secondary"
                           href="{{ entry.session.get_continue_url }}">Kontynuuj</a>
                    {% elif entry.status == "imported" %}
                        <a class="button tiny success"
                           href="{{ entry.session.created_record.get_absolute_url }}">Zobacz pracę</a>
                    {% elif entry.status == "failed" %}
                        <form method="post"
                              action="{% url 'importer_publikacji:task-retry' session_id=entry.session.pk %}"
                              style="display:inline">
                            {% csrf_token %}
                            <button type="submit" class="button tiny alert">Ponów</button>
                        </form>
                        <form method="post"
                              action="{% url 'importer_publikacji:batch-entry-skip' entry_id=entry.pk %}"
                              style="display:inline">
                            {% csrf_token %}
                            <button type="submit" class="button tiny hollow">Pomiń</button>
                        </form>
                    {% elif entry.status == "malformed" %}
                        <form method="post"
                              action="{% url 'importer_publikacji:batch-entry-skip' entry_id=entry.pk %}">
                            {% csrf_token %}
                            <button type="submit" class="button tiny hollow">Pomiń</button>
                        </form>
                    {% elif entry.status == "skipped" %}
                        <form method="post"
                              action="{% url 'importer_publikacji:batch-entry-skip' entry_id=entry.pk %}">
                            {% csrf_token %}
                            <button type="submit" class="button tiny hollow">Przywróć</button>
                        </form>
                    {% endif %}
                </td>
            </tr>
            {% if entry.parse_error %}
                <tr>
                    <td></td>
                    <td colspan="3">
                        <small class="alert-color">{{ entry.parse_error }}</small>
                    </td>
                </tr>
            {% endif %}
        {% endfor %}
    </tbody>
</table>
```

Uwaga: `{{ entry.get_status_display_badge }}` nie istnieje — zastąp prostym mapowaniem inline. Dodaj do modelu `MultipleWorksImportEntry` property `status_label` zwracające `EntryStatus(self.status).label` i użyj `{{ entry.status_label }}`:

```python
    @property
    def status_label(self) -> str:
        return EntryStatus(self.status).label
```

W szablonie zamień `{{ entry.get_status_display_badge }}` → `{{ entry.status_label }}`.

Routes `batch-entry-import` / `batch-entry-skip` powstają w Task 6/7; szablon je referuje, ale test z tego Taska nie klika akcji (renderuje listę). **Aby test nie wywalił się na `NoReverseMatch`, wykonaj Task 6 i 7 przed uruchomieniem pełnego renderu, LUB** dodaj oba routy jako placeholdery w tym kroku (patrz Task 6 Step 3 / Task 7 Step 3) — zalecane: dodaj oba `path(...)` teraz, a widoki w Task 6/7.

Dodaj do `src/importer_publikacji/urls.py` (jeśli nie dodane w Task 6/7):

```python
    path(
        "batch/entry/<int:entry_id>/import/",
        views.BatchEntryImportView.as_view(),
        name="batch-entry-import",
    ),
    path(
        "batch/entry/<int:entry_id>/skip/",
        views.BatchEntrySkipView.as_view(),
        name="batch-entry-skip",
    ),
```

(oraz zapewnij, że `BatchEntryImportView`/`BatchEntrySkipView` są zaimportowane w `views/__init__.py`; ich implementacja w Task 6/7).

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -k batch_detail -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/importer_publikacji/views/wizard.py src/importer_publikacji/views/helpers.py src/importer_publikacji/models.py src/importer_publikacji/templates/importer_publikacji/partials/batch_detail.html src/importer_publikacji/urls.py src/importer_publikacji/views/__init__.py src/importer_publikacji/tests/test_views_batch.py
git commit -m "feat(importer_publikacji): strona paczki z lista wpisow + sweep stalled"
```

---

### Task 6: `BatchEntryImportView` (drip import + guard in-flight)

**Files:**
- Modify: `src/importer_publikacji/views/wizard.py`
- Modify: `src/importer_publikacji/urls.py`, `src/importer_publikacji/views/__init__.py` (jeśli nie dodane w Task 5)
- Test: `src/importer_publikacji/tests/test_views_batch.py` (dopisz)

**Interfaces:**
- Consumes: `_start_import_session` (Task 4), `MultipleWorksImportEntry` (Task 3).
- Produces: `BatchEntryImportView.post(request, entry_id)` — tworzy sesję dla `entry.raw_bibtex` przez helper, podpina `entry.session`, redirect na `task-status`. Guard: MALFORMED → 400; istniejąca sesja in-flight → redirect na `get_continue_url()`.

- [ ] **Step 1: Write the failing tests**

Dopisz do `test_views_batch.py`:

```python
@pytest.mark.django_db
def test_batch_entry_import_creates_session(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, raw_bibtex=ONE_ENTRY
    )
    resp = client.post(
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk})
    )
    entry.refresh_from_db()
    assert entry.session is not None
    assert entry.session.identifier == ONE_ENTRY
    assert resp.status_code == 302
    assert resp["Location"] == reverse(
        "importer_publikacji:task-status", kwargs={"session_id": entry.session.pk}
    )


@pytest.mark.django_db
def test_batch_entry_import_guards_inflight(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    existing = baker.make(ImportSession, status=ImportSession.Status.FETCHED)
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, session=existing
    )
    resp = client.post(
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk})
    )
    entry.refresh_from_db()
    # Nie powstala druga sesja; redirect na kontynuacje istniejacej.
    assert entry.session == existing
    assert ImportSession.objects.count() == 1
    assert resp["Location"] == existing.get_continue_url()


@pytest.mark.django_db
def test_batch_entry_import_rejects_malformed(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, parse_error="zepsute"
    )
    resp = client.post(
        reverse("importer_publikacji:batch-entry-import", kwargs={"entry_id": entry.pk})
    )
    assert resp.status_code == 400
    entry.refresh_from_db()
    assert entry.session is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -k entry_import -v`
Expected: FAIL — `AttributeError`/`NoReverseMatch` lub widok nie istnieje.

- [ ] **Step 3: Implement view + route**

W `src/importer_publikacji/urls.py` upewnij się, że jest route (dodany w Task 5 lub tu):

```python
    path(
        "batch/entry/<int:entry_id>/import/",
        views.BatchEntryImportView.as_view(),
        name="batch-entry-import",
    ),
```

W `wizard.py` dodaj widok:

```python
class BatchEntryImportView(ImporterPermissionMixin, View):
    """Wystartuj import pojedynczego wpisu paczki (leniwy drip)."""

    _INFLIGHT = (
        ImportSession.Status.COMPLETED,
        ImportSession.Status.IMPORT_FAILED,
        ImportSession.Status.CANCELLED,
    )

    def post(self, request, entry_id):
        entry = get_object_or_404(MultipleWorksImportEntry, pk=entry_id)
        if entry.parse_error:
            return HttpResponseBadRequest("Wpis uszkodzony — nie można zaimportować.")
        session = entry.session
        if (
            session is not None
            and session.status not in self._INFLIGHT
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
```

Dodaj `BatchEntryImportView` do importu w `views/__init__.py` (`from .wizard import ...`) i do `__all__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -k entry_import -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/views/wizard.py src/importer_publikacji/views/__init__.py src/importer_publikacji/urls.py src/importer_publikacji/tests/test_views_batch.py
git commit -m "feat(importer_publikacji): BatchEntryImportView (drip import + guard in-flight)"
```

---

### Task 7: `BatchEntrySkipView` (pomiń / przywróć, guard na IMPORTED)

**Files:**
- Modify: `src/importer_publikacji/views/wizard.py`
- Modify: `src/importer_publikacji/urls.py`, `src/importer_publikacji/views/__init__.py` (jeśli nie dodane wcześniej)
- Test: `src/importer_publikacji/tests/test_views_batch.py` (dopisz)

**Interfaces:**
- Produces: `BatchEntrySkipView.post(request, entry_id)` — toggluje `entry.skipped`, redirect na `batch-detail`. Guard: wpis w statusie IMPORTED nie może być skipnięty.

- [ ] **Step 1: Write the failing tests**

Dopisz do `test_views_batch.py`:

```python
@pytest.mark.django_db
def test_batch_entry_skip_toggles(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, skipped=False
    )
    url = reverse("importer_publikacji:batch-entry-skip", kwargs={"entry_id": entry.pk})
    resp = client.post(url)
    entry.refresh_from_db()
    assert entry.skipped is True
    assert resp["Location"] == reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    client.post(url)  # przywroc
    entry.refresh_from_db()
    assert entry.skipped is False


@pytest.mark.django_db
def test_batch_entry_skip_refuses_imported(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    done = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    entry = baker.make(
        MultipleWorksImportEntry, parent=batch, order=0, session=done
    )
    resp = client.post(
        reverse("importer_publikacji:batch-entry-skip", kwargs={"entry_id": entry.pk})
    )
    entry.refresh_from_db()
    assert entry.skipped is False  # niezmienione
    assert resp.status_code in (302, 400)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -k entry_skip -v`
Expected: FAIL — widok nie istnieje.

- [ ] **Step 3: Implement view + route**

Route w `urls.py` (jeśli nie dodany):

```python
    path(
        "batch/entry/<int:entry_id>/skip/",
        views.BatchEntrySkipView.as_view(),
        name="batch-entry-skip",
    ),
```

W `wizard.py`:

```python
class BatchEntrySkipView(ImporterPermissionMixin, View):
    """Pomiń lub przywróć wpis paczki (toggle)."""

    def post(self, request, entry_id):
        from ..models import EntryStatus

        entry = get_object_or_404(MultipleWorksImportEntry, pk=entry_id)
        if entry.status == EntryStatus.IMPORTED:
            return HttpResponseBadRequest("Nie można pominąć zaimportowanego wpisu.")
        entry.skipped = not entry.skipped
        entry.save(update_fields=["skipped"])
        url = reverse(
            "importer_publikacji:batch-detail",
            kwargs={"batch_id": entry.parent_id},
        )
        return HttpResponseRedirect(url)
```

Dodaj `BatchEntrySkipView` do `views/__init__.py` (import + `__all__`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -k entry_skip -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/importer_publikacji/views/wizard.py src/importer_publikacji/views/__init__.py src/importer_publikacji/urls.py src/importer_publikacji/tests/test_views_batch.py
git commit -m "feat(importer_publikacji): BatchEntrySkipView (pomin/przywroc, guard IMPORTED)"
```

---

### Task 8: `DoneView` + `CancelView` batch-aware + szablon `step_done.html`

**Files:**
- Modify: `src/importer_publikacji/views/wizard.py`
- Modify: `src/importer_publikacji/templates/importer_publikacji/partials/step_done.html`
- Test: `src/importer_publikacji/tests/test_views_batch.py` (dopisz)

**Interfaces:**
- Consumes: reverse-accessor `session.batch_entry` (OneToOne z Task 3).
- Produces: `DoneView` wstrzykuje `batch` + `batch_progress` do kontekstu, gdy sesja należy do paczki; szablon pokazuje „Wróć do paczki (X z N)". `CancelView` przy sesji-z-paczki wraca na `batch-detail`.

- [ ] **Step 1: Write the failing tests**

Dopisz do `test_views_batch.py`:

```python
@pytest.mark.django_db
def test_done_shows_back_to_batch_link(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    session = baker.make(ImportSession, status=ImportSession.Status.COMPLETED)
    baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=session)
    baker.make(MultipleWorksImportEntry, parent=batch, order=1)
    resp = client.get(
        reverse("importer_publikacji:done", kwargs={"session_id": session.pk})
    )
    content = resp.content.decode()
    batch_url = reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    assert batch_url in content
    assert "Wróć do paczki" in content


@pytest.mark.django_db
def test_cancel_returns_to_batch(client, operator):
    client.force_login(operator)
    batch = baker.make(MultipleWorksImport)
    session = baker.make(ImportSession, status=ImportSession.Status.VERIFIED)
    baker.make(MultipleWorksImportEntry, parent=batch, order=0, session=session)
    resp = client.post(
        reverse("importer_publikacji:cancel", kwargs={"session_id": session.pk})
    )
    batch_url = reverse(
        "importer_publikacji:batch-detail", kwargs={"batch_id": batch.pk}
    )
    # Redirect albo push-url na batch-detail:
    location = resp.get("Location") or resp.get("HX-Push-Url") or ""
    assert batch_url in location or batch_url in resp.content.decode()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -k "done_shows or cancel_returns" -v`
Expected: FAIL — brak linku „Wróć do paczki".

- [ ] **Step 3: Make `DoneView` batch-aware**

W `wizard.py` w `DoneView.get` (linie 807-817) zbuduj kontekst z informacją o paczce:

```python
    def get(self, request, session_id):
        session = get_object_or_404(
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
```

(`getattr(session, "batch_entry", None)` — reverse OneToOne rzuca `RelatedObjectDoesNotExist`, gdy brak; `getattr` z domyślnym `None` bezpiecznie to obsłuży, bo `hasattr` łapie ten wyjątek.)

- [ ] **Step 4: Update `step_done.html`**

W `src/importer_publikacji/templates/importer_publikacji/partials/step_done.html` zamień końcowy link (linie 76-80) na warunek:

```django
    {% if batch %}
        <a href="{% url 'importer_publikacji:batch-detail' batch_id=batch.pk %}"
           class="button">
            <span class="fi-arrow-left"></span>
            Wróć do paczki ({{ batch_progress.imported }} z {{ batch_progress.total }})
        </a>
    {% else %}
        <a href="{% url 'importer_publikacji:index' %}"
           class="button hollow secondary">
            <span class="fi-arrow-left"></span>
            Importuj kolejną publikację
        </a>
    {% endif %}
```

- [ ] **Step 5: Make `CancelView` batch-aware**

W `wizard.py` `CancelView.post` (linie 823-837), po ustawieniu statusu na CANCELLED, jeśli sesja należy do paczki — wróć na `batch-detail` zamiast na indeks:

```python
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

        url = reverse("importer_publikacji:index")
        ctx = _fetch_context(request=request)
        ctx["cancelled"] = True
        ctx.update(_sessions_list_context(request))
        response = render(request, STEP_FETCH, ctx)
        response = _with_breadcrumbs_oob(response, request)
        return _push_url(response, url)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest src/importer_publikacji/tests/test_views_batch.py -v`
Expected: PASS (cały plik).

- [ ] **Step 7: Full module regression + commit**

Run:
```bash
uv run pytest src/importer_publikacji/ -v
uv run python src/manage.py makemigrations --check --dry-run
ruff format src/importer_publikacji/ && ruff check src/importer_publikacji/
```
Expected: wszystkie testy modułu PASS, brak driftu migracji, ruff czysty.

```bash
git add src/importer_publikacji/views/wizard.py src/importer_publikacji/templates/importer_publikacji/partials/step_done.html src/importer_publikacji/tests/test_views_batch.py
git commit -m "feat(importer_publikacji): Done/Cancel batch-aware (powrot do paczki)"
```

---

## Self-Review

**Spec coverage:**
- §4 modele → Task 3 (oba modele, `progress`, status wyliczany, `OneToOneField`, admin). ✅
- §5 `split_input`/`SplitRecord`/`peek_title` + failed_blocks → Task 1 (baza) + Task 2 (BibTeX). ✅
- §6.1 fan-out + HX-Redirect + helper → Task 4. ✅
- §6.2 detail view + group-scope + sweep stalled + progress → Task 5. ✅
- §6.3 import wpisu + guard in-flight + MALFORMED + [Ponów]=task-retry → Task 6 (+ szablon Task 5 kieruje Ponów na istniejący `task-retry`). ✅
- §6.4 skip toggle + guard IMPORTED → Task 7. ✅
- §6.5 Done + Cancel batch-aware → Task 8. ✅
- §6.6 URL-e → Task 4/5/6/7. ✅
- §8 testy (10 pozycji) → rozłożone po Taskach; regresja `test_fetch_multiple_entries_takes_first` w Task 2. ✅
- §9 migracja + brak baseline refresh + `makemigrations --check` → Task 3 Step 4 + Task 8 Step 7. ✅

**Placeholder scan:** brak TODO/TBD; każdy krok ma konkretny kod i komendę z oczekiwanym wynikiem. Jedyny „miękki" punkt — linia `{% extends %}` w `batch_detail.html` — rozwiązywana przez odczyt istniejącego `step_fetch.html`/`index.html` (instrukcja w Task 5 Step 5).

**Type consistency:** `SplitRecord(raw, ok, title, error)` spójne w Task 1/2/4. `EntryStatus` wartości (`pending/in_progress/imported/failed/skipped/malformed`) spójne w modelu (Task 3), szablonie (Task 5) i guardach (Task 6/7). `_start_import_session(request, provider_name, identifier)` definiowany w Task 4, używany w Task 4/6. `session.batch_entry` (OneToOne reverse) spójne w Task 3/8. `batch_id`/`entry_id` jako nazwy kwargs spójne w urls + testach.

**Uwaga wykonawcza (kolejność routów):** route `batch-entry-import`/`batch-entry-skip` są referowane przez szablon z Task 5, a implementowane w Task 6/7. Wykonuj Taski 5→6→7 sekwencyjnie **albo** dodaj oba `path(...)` + puste widoki-placeholdery w Task 5, żeby render listy nie rzucił `NoReverseMatch`. Zalecenie: sekwencyjnie.
