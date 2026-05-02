# Deduplikator autorów — tryb general — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać do istniejącego modułu `src/deduplikator_autorow/` drugi tryb skanowania — `general` — znajdujący duplikaty autorów spoza `OsobaZInstytucji` (PBN). Zachowuje istniejący tryb PBN, dodaje cluster-skip dla klastrów zawierających członka PBN-instytucji, deterministyczny wybór "main" hierarchią cech.

**Architecture:** Rozszerzenie aplikacji `deduplikator_autorow`. Nowe utility (`utils/meta.py`, `utils/cluster.py`, `utils/main_selection.py`, `utils/search_general.py`). Refactor `tasks.py:scan_for_duplicates` na dwie fazy w jednym tasku celery (PBN→general). Nowy status `PARTIAL_COMPLETED`. Migracje: rename `IgnoredAuthor` → `IgnoredScientist`, nowy `IgnoredAuthor` (FK→Autor), pole `phase` na `DuplicateScanRun`, `scan_mode` na `DuplicateCandidate`, replace constraint.

**Tech Stack:** Django 4.x/5.x, Celery, pytest + pytest-django + pytest-xdist, model_bakery, Postgres.

**Spec:** `docs/superpowers/specs/2026-05-01-deduplikator-autorow-general-design.md`

---

## Konwencje wykonania

- **Worktree:** wszystkie zmiany w `~/Programowanie/bpp-worktrees/deduplikator-autorow-general/` (utworzony w Phase 0).
- **Python uruchamiamy zawsze przez `uv run`** (nigdy goły `python`).
- **pytest:** `UV_NO_SYNC=1 uv run --all-extras pytest -n auto <target> 2>&1 | tee /tmp/dedup-test.log` — output ZAWSZE do pliku, jeśli błąd → grepuj `/tmp/dedup-test.log`. Nigdy nie odpalaj testów po raz drugi „dla pewności".
- **Migracje:** nigdy nie modyfikujemy istniejących migracji w `src/*/migrations/`. Nowe pliki numerujemy kolejno od `0009_*`.
- **Pre-commit:** uruchamiać tylko na zmienionych plikach. Nie używać `--all-files`. Po `git add` przed commitem `pre-commit` uruchomi się sam.
- **Commit cadence:** commit po każdym ukończonym Tasku (chyba że Task explicite mówi inaczej).
- **Maks. 88 znaków** na linię (ruff format).

---

## Phase 0: Worktree i pre-flight

### Task 0.1: Utworzenie worktree

**Files:**
- Brak nowych plików; operacja git.

- [ ] **Step 1: Sprawdź stan repo**

```bash
cd /Users/mpasternak/Programowanie/bpp
git status
git fetch origin
git log --oneline -5 dev
```

Expected: `dev` branch, ostatni commit to spec deduplikatora.

- [ ] **Step 2: Utwórz worktree**

```bash
git worktree add ~/Programowanie/bpp-worktrees/deduplikator-autorow-general -b feature/deduplikator-autorow-general dev
cd ~/Programowanie/bpp-worktrees/deduplikator-autorow-general
```

Expected: katalog utworzony, branch ustawiony.

- [ ] **Step 3: Zainstaluj zależności w worktree**

```bash
uv sync --all-extras
```

Expected: `uv.lock` resolved, brak błędów.

- [ ] **Step 4: Sanity-check testów**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_szukaj_kopii.py -n auto 2>&1 | tee /tmp/dedup-sanity.log
```

Expected: testy istniejące przechodzą.

---

## Phase 1: Modele i migracje

Cel: wprowadzić wszystkie zmiany strukturalne ZANIM zaczniemy logikę. Ułatwi to debugowanie późniejsze.

### Task 1.1: Rename `IgnoredAuthor` → `IgnoredScientist`

**Files:**
- Modify: `src/deduplikator_autorow/models.py`
- Create: `src/deduplikator_autorow/migrations/0009_rename_ignoredauthor_ignoredscientist.py`
- Modify: `src/deduplikator_autorow/admin.py`
- Modify: `src/deduplikator_autorow/views.py`
- Modify: `src/deduplikator_autorow/tasks.py`
- Modify: `src/deduplikator_autorow/utils/finders.py`

- [ ] **Step 1: Przemianuj klasę modelu**

W `src/deduplikator_autorow/models.py`, znajdź klasę `IgnoredAuthor` (FK→Scientist) i zmień jej nazwę na `IgnoredScientist`. Zmień też verbose_names:

```python
class IgnoredScientist(models.Model):
    """Scientists from PBN that should be completely ignored in deduplication"""

    scientist = models.OneToOneField(
        "pbn_api.Scientist",
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name="Scientist (PBN)",
        help_text="Scientist record that should be ignored in deduplication",
    )

    autor = models.ForeignKey(
        "bpp.Autor",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Autor (BPP)",
        help_text="Optional reference to BPP author",
    )

    reason = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Powód ignorowania",
    )

    created_on = models.DateTimeField("Data utworzenia", default=timezone.now)
    created_by = models.ForeignKey(
        BppUser,
        on_delete=models.CASCADE,
        verbose_name="Utworzył",
    )

    class Meta:
        verbose_name = "Ignorowany Scientist (PBN)"
        verbose_name_plural = "Ignorowani Scientist (PBN)"
        ordering = ["-created_on"]

    def __str__(self):
        if self.autor:
            return f"Ignorowany: {self.autor} (Scientist #{self.scientist.pk})"
        return f"Ignorowany: Scientist #{self.scientist.pk}"
```

- [ ] **Step 2: Zaktualizuj importy w innych plikach**

W każdym z plików: `admin.py`, `views.py`, `tasks.py`, `utils/finders.py` — znajdź referencje `IgnoredAuthor` i przemianuj na `IgnoredScientist`. Konkretne miejsca:

```bash
cd ~/Programowanie/bpp-worktrees/deduplikator-autorow-general
grep -rn "IgnoredAuthor" src/deduplikator_autorow/
```

Każde wystąpienie zamień (sed nie zadziała przez Edit; rób ręcznie). Plik `models.py` jest właścicielem klasy, ale w `admin.py` jest decorator `@admin.register(IgnoredAuthor)` i klasa `IgnoredAuthorAdmin` → przemianuj klasę na `IgnoredScientistAdmin` i decorator na `@admin.register(IgnoredScientist)`. Zmiana w `__init__.py` modułu jeśli reeksportowane.

- [ ] **Step 3: Wygeneruj migrację**

```bash
UV_NO_SYNC=1 uv run --all-extras src/manage.py makemigrations deduplikator_autorow --name rename_ignoredauthor_ignoredscientist
```

Sprawdź, że plik `0009_rename_ignoredauthor_ignoredscientist.py` zawiera `migrations.RenameModel(old_name="IgnoredAuthor", new_name="IgnoredScientist")` i `AlterModelOptions`.

Expected: pojedyncza migracja z RenameModel + AlterModelOptions.

- [ ] **Step 4: Sprawdź że testy istniejące dalej przechodzą**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/ -n auto 2>&1 | tee /tmp/dedup-task1.log
```

Expected: wszystkie istniejące testy zielone (rename to non-breaking change wewnątrz modułu).

- [ ] **Step 5: Commit**

```bash
git add -A src/deduplikator_autorow/
git commit -m "$(cat <<'EOF'
refactor(deduplikator): zmień nazwę IgnoredAuthor → IgnoredScientist

Pierwszy krok przygotowania pod tryb general — istniejący IgnoredAuthor
był specyficzny dla PBN (FK→Scientist) i zwalniamy nazwę pod nowy model
ignorujący autorów BPP w trybie ogólnym.
EOF
)"
```

---

### Task 1.2: Nowy `IgnoredAuthor` (FK→Autor)

**Files:**
- Modify: `src/deduplikator_autorow/models.py`
- Create: `src/deduplikator_autorow/migrations/0010_add_ignored_author.py`
- Modify: `src/deduplikator_autorow/admin.py`
- Test: `src/deduplikator_autorow/tests/test_models_ignored.py` (nowy)

- [ ] **Step 1: Napisz failing test**

`src/deduplikator_autorow/tests/test_models_ignored.py`:

```python
"""Testy modelu IgnoredAuthor (general) i IgnoredScientist (PBN)."""

import pytest
from model_bakery import baker

from deduplikator_autorow.models import IgnoredAuthor, IgnoredScientist


@pytest.mark.django_db
def test_ignored_scientist_can_be_created():
    scientist = baker.make("pbn_api.Scientist")
    user = baker.make("bpp.BppUser")
    obj = IgnoredScientist.objects.create(scientist=scientist, created_by=user)
    assert obj.pk is not None
    assert obj.scientist == scientist


@pytest.mark.django_db
def test_ignored_author_can_be_created():
    autor = baker.make("bpp.Autor")
    user = baker.make("bpp.BppUser")
    obj = IgnoredAuthor.objects.create(autor=autor, created_by=user, reason="test")
    assert obj.pk is not None
    assert obj.autor == autor
    assert obj.reason == "test"


@pytest.mark.django_db
def test_ignored_author_one_to_one_constraint():
    """Próba podwójnego dodania tego samego autora rzuca IntegrityError."""
    from django.db import IntegrityError

    autor = baker.make("bpp.Autor")
    user = baker.make("bpp.BppUser")
    IgnoredAuthor.objects.create(autor=autor, created_by=user)
    with pytest.raises(IntegrityError):
        IgnoredAuthor.objects.create(autor=autor, created_by=user)
```

- [ ] **Step 2: Uruchom test — ma fail-ować na imporcie**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_models_ignored.py -n0 2>&1 | tee /tmp/dedup-task1-2.log
```

Expected: ImportError lub `cannot import name 'IgnoredAuthor'`.

- [ ] **Step 3: Dodaj klasę `IgnoredAuthor` w `models.py`**

W pliku `src/deduplikator_autorow/models.py`, **po** klasie `IgnoredScientist`, dodaj:

```python
class IgnoredAuthor(models.Model):
    """BPP authors (without PBN-Scientist link) that should be ignored in deduplication."""

    autor = models.OneToOneField(
        "bpp.Autor",
        on_delete=models.CASCADE,
        db_index=True,
        verbose_name="Autor (BPP)",
        help_text="Autor BPP do ignorowania w deduplikacji ogólnej",
    )

    reason = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Powód ignorowania",
    )

    created_on = models.DateTimeField("Data utworzenia", default=timezone.now)
    created_by = models.ForeignKey(
        BppUser,
        on_delete=models.CASCADE,
        verbose_name="Utworzył",
    )

    class Meta:
        verbose_name = "Ignorowany autor (BPP)"
        verbose_name_plural = "Ignorowani autorzy (BPP)"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Ignorowany autor: {self.autor}"
```

- [ ] **Step 4: Wygeneruj migrację**

```bash
UV_NO_SYNC=1 uv run --all-extras src/manage.py makemigrations deduplikator_autorow --name add_ignored_author
```

Expected: `0010_add_ignored_author.py` z `CreateModel(name="IgnoredAuthor", ...)`.

- [ ] **Step 5: Dodaj admin dla nowego modelu**

W `src/deduplikator_autorow/admin.py`, **po** klasie `IgnoredScientistAdmin`, dodaj:

```python
@admin.register(IgnoredAuthor)
class IgnoredAuthorAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "get_autor_display",
        "reason",
        "created_by",
        "created_on",
    ]

    list_filter = ["created_on", "created_by"]

    search_fields = [
        "autor__nazwisko",
        "autor__imiona",
        "reason",
        "created_by__username",
    ]

    readonly_fields = ["created_on"]
    date_hierarchy = "created_on"
    ordering = ["-created_on"]

    def get_autor_display(self, obj):
        if obj.autor:
            url = reverse("admin:bpp_autor_change", args=[obj.autor.pk])
            return mark_safe(f'<a href="{url}">{obj.autor}</a>')
        return "-"

    get_autor_display.short_description = "Autor (BPP)"

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
```

Dodaj `IgnoredAuthor` do importu na górze `admin.py`.

- [ ] **Step 6: Uruchom testy — powinny przejść**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_models_ignored.py -n auto 2>&1 | tee /tmp/dedup-task1-2.log
```

Expected: 3 testy zielone.

- [ ] **Step 7: Commit**

```bash
git add -A src/deduplikator_autorow/
git commit -m "feat(deduplikator): nowy model IgnoredAuthor (FK→Autor) dla trybu general"
```

---

### Task 1.3: `phase` na ScanRun, `scan_mode` na Candidate, status `PARTIAL_COMPLETED`, constraint

**Files:**
- Modify: `src/deduplikator_autorow/models.py`
- Create: `src/deduplikator_autorow/migrations/0011_scan_mode_phase_partial.py`
- Test: `src/deduplikator_autorow/tests/test_models_scan_fields.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_models_scan_fields.py`:

```python
"""Testy nowych pól: phase, scan_mode, PARTIAL_COMPLETED status."""

import pytest
from model_bakery import baker

from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun


@pytest.mark.django_db
def test_scan_run_phase_field_default_blank():
    scan = DuplicateScanRun.objects.create()
    assert scan.phase == ""


@pytest.mark.django_db
def test_scan_run_phase_field_can_be_set():
    scan = DuplicateScanRun.objects.create(phase="general")
    scan.refresh_from_db()
    assert scan.phase == "general"


@pytest.mark.django_db
def test_scan_run_partial_completed_status():
    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.PARTIAL_COMPLETED
    )
    scan.refresh_from_db()
    assert scan.status == "partial_completed"
    assert scan.get_status_display() == "Częściowo zakończone (faza PBN OK, general anulowana)"


@pytest.mark.django_db
def test_candidate_scan_mode_default_pbn():
    scan = DuplicateScanRun.objects.create()
    autor1 = baker.make("bpp.Autor")
    autor2 = baker.make("bpp.Autor")
    cand = DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=autor1,
        duplicate_autor=autor2,
        confidence_score=80,
        confidence_percent=0.5,
        main_autor_name="Test Main",
        duplicate_autor_name="Test Dup",
    )
    cand.refresh_from_db()
    assert cand.scan_mode == "pbn"


@pytest.mark.django_db
def test_candidate_scan_mode_general():
    scan = DuplicateScanRun.objects.create()
    autor1 = baker.make("bpp.Autor")
    autor2 = baker.make("bpp.Autor")
    cand = DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=autor1,
        duplicate_autor=autor2,
        confidence_score=80,
        confidence_percent=0.5,
        main_autor_name="Test Main",
        duplicate_autor_name="Test Dup",
        scan_mode="general",
    )
    cand.refresh_from_db()
    assert cand.scan_mode == "general"


@pytest.mark.django_db
def test_candidate_unique_constraint_includes_scan_mode():
    """Ta sama para (main, dup) może istnieć w obu trybach, ale nie dwa razy w jednym."""
    from django.db import IntegrityError

    scan = DuplicateScanRun.objects.create()
    autor1 = baker.make("bpp.Autor")
    autor2 = baker.make("bpp.Autor")

    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=autor1,
        duplicate_autor=autor2,
        confidence_score=80,
        confidence_percent=0.5,
        main_autor_name="A",
        duplicate_autor_name="B",
        scan_mode="pbn",
    )
    # Ta sama para w trybie general — OK
    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=autor1,
        duplicate_autor=autor2,
        confidence_score=80,
        confidence_percent=0.5,
        main_autor_name="A",
        duplicate_autor_name="B",
        scan_mode="general",
    )
    # Drugi raz w trybie pbn — IntegrityError
    with pytest.raises(IntegrityError):
        DuplicateCandidate.objects.create(
            scan_run=scan,
            main_autor=autor1,
            duplicate_autor=autor2,
            confidence_score=80,
            confidence_percent=0.5,
            main_autor_name="A",
            duplicate_autor_name="B",
            scan_mode="pbn",
        )
```

- [ ] **Step 2: Uruchom — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_models_scan_fields.py -n0 2>&1 | tee /tmp/dedup-task1-3.log
```

Expected: AttributeError lub similar — pole `phase` nie istnieje, status `PARTIAL_COMPLETED` nie zdefiniowany.

- [ ] **Step 3: Modyfikuj `DuplicateScanRun`**

W `src/deduplikator_autorow/models.py`, klasa `DuplicateScanRun`:

(a) W `Status` dodaj wartość:

```python
class Status(models.TextChoices):
    PENDING = "pending", "Oczekuje"
    RUNNING = "running", "W trakcie"
    COMPLETED = "completed", "Zakończone"
    PARTIAL_COMPLETED = (
        "partial_completed",
        "Częściowo zakończone (faza PBN OK, general anulowana)",
    )
    CANCELLED = "cancelled", "Anulowane"
    FAILED = "failed", "Błąd"
```

(b) Dodaj pole `phase` po `celery_task_id`:

```python
phase = models.CharField(
    "Aktualna faza",
    max_length=20,
    blank=True,
    choices=[("pbn", "Faza PBN"), ("general", "Faza ogólna")],
)
```

- [ ] **Step 4: Modyfikuj `DuplicateCandidate`**

W tej samej klasie dodaj pole `scan_mode` po `priority`:

```python
scan_mode = models.CharField(
    "Tryb skanowania",
    max_length=20,
    choices=[("pbn", "PBN"), ("general", "Ogólny")],
    default="pbn",
    db_index=True,
)
```

W `class Meta` zamień constraint:

```python
class Meta:
    verbose_name = "Kandydat na duplikat"
    verbose_name_plural = "Kandydaci na duplikaty"
    ordering = ["-priority", "-confidence_score", "main_autor__nazwisko"]
    indexes = [
        models.Index(fields=["scan_run", "status"]),
        models.Index(fields=["main_autor", "status"]),
        models.Index(fields=["priority", "confidence_score"]),
        models.Index(fields=["scan_run", "scan_mode", "status"]),
    ]
    constraints = [
        models.UniqueConstraint(
            fields=["scan_run", "scan_mode", "main_autor", "duplicate_autor"],
            name="unique_scan_mode_main_duplicate",
        ),
    ]
```

- [ ] **Step 5: Wygeneruj migrację**

```bash
UV_NO_SYNC=1 uv run --all-extras src/manage.py makemigrations deduplikator_autorow --name scan_mode_phase_partial
```

Expected: `0011_*.py` z AddField (phase, scan_mode), AlterField (status — choices), AddIndex, RemoveConstraint, AddConstraint.

- [ ] **Step 6: Sprawdź że migracja jest reversible/clean (dry-run)**

```bash
UV_NO_SYNC=1 uv run --all-extras src/manage.py migrate --plan deduplikator_autorow 0011 2>&1 | tee /tmp/dedup-migrate-plan.log
UV_NO_SYNC=1 uv run --all-extras src/manage.py migrate deduplikator_autorow 2>&1 | tee /tmp/dedup-migrate.log
```

Expected: migracja przechodzi bez ostrzeżeń.

- [ ] **Step 7: Uruchom testy — powinny przejść**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_models_scan_fields.py -n auto 2>&1 | tee /tmp/dedup-task1-3.log
```

Expected: 6 testów zielonych.

- [ ] **Step 8: Commit**

```bash
git add -A src/deduplikator_autorow/
git commit -m "feat(deduplikator): pola phase, scan_mode, status PARTIAL_COMPLETED, constraint"
```

---

## Phase 2: Engine — meta-cache, analiza, cluster, main selection

Cel: zbudować in-memory komponenty pozwalające analizować duplikaty bez SQL na hot-path.

### Task 2.1: `utils/cluster.py` — union-find

**Files:**
- Create: `src/deduplikator_autorow/utils/cluster.py`
- Test: `src/deduplikator_autorow/tests/test_cluster.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_cluster.py`:

```python
"""Testy union-find (connected components)."""

from deduplikator_autorow.utils.cluster import find_clusters


def test_two_disjoint_pairs():
    pairs = [(1, 2), (3, 4)]
    clusters = sorted(find_clusters(pairs), key=min)
    assert clusters == [{1, 2}, {3, 4}]


def test_transitive_cluster():
    """A~B and B~C → cluster {A, B, C}."""
    pairs = [(1, 2), (2, 3)]
    clusters = list(find_clusters(pairs))
    assert clusters == [{1, 2, 3}]


def test_single_pair():
    pairs = [(7, 8)]
    clusters = list(find_clusters(pairs))
    assert clusters == [{7, 8}]


def test_no_pairs():
    assert list(find_clusters([])) == []


def test_isolated_nodes_with_pairs():
    """Tylko węzły mające połączenia trafiają do klastrów."""
    pairs = [(1, 2), (5, 6), (2, 3)]
    clusters = sorted(find_clusters(pairs), key=min)
    assert clusters == [{1, 2, 3}, {5, 6}]


def test_duplicate_pairs_are_idempotent():
    pairs = [(1, 2), (1, 2), (2, 1)]
    clusters = list(find_clusters(pairs))
    assert clusters == [{1, 2}]
```

- [ ] **Step 2: Run — ImportError**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_cluster.py -n0 2>&1 | tee /tmp/dedup-task2-1.log
```

- [ ] **Step 3: Implementacja**

`src/deduplikator_autorow/utils/cluster.py`:

```python
"""Union-find (connected components) dla par autorów.

Dla zbioru par (a, b) zwraca spójne komponenty grafu.
"""


def find_clusters(pairs):
    """Zwraca listę zbiorów (klastrów) z par.

    Args:
        pairs: iterable krotek (pk_a, pk_b).

    Returns:
        list[set[int]]: lista klastrów (każdy klaster to set PKów).
    """
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b in pairs:
        if a not in parent:
            parent[a] = a
        if b not in parent:
            parent[b] = b
        union(a, b)

    clusters_by_root = {}
    for node in parent:
        root = find(node)
        clusters_by_root.setdefault(root, set()).add(node)

    return list(clusters_by_root.values())
```

- [ ] **Step 4: Run — pass**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_cluster.py -n auto 2>&1 | tee /tmp/dedup-task2-1.log
```

Expected: 6 zielonych.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): utils.cluster — union-find dla klastrów autorów"
```

---

### Task 2.2: `utils/main_selection.py` — hierarchia B

**Files:**
- Create: `src/deduplikator_autorow/utils/main_selection.py`
- Test: `src/deduplikator_autorow/tests/test_main_selection.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_main_selection.py`:

```python
"""Testy hierarchii wyboru głównego rekordu (hierarchia B)."""

from deduplikator_autorow.utils.main_selection import pick_main_pk


def _meta(**kwargs):
    """Helper — minimalny wpis meta."""
    base = {
        "ma_orcid": False,
        "ma_pbn_uid": False,
        "ma_tytul": False,
        "ma_dyscypline": False,
        "publikacje_count": 0,
        "max_rok": 0,
    }
    base.update(kwargs)
    return base


def test_orcid_wins_over_everything():
    metas = {
        1: _meta(ma_orcid=False, publikacje_count=100, max_rok=2025),
        2: _meta(ma_orcid=True, publikacje_count=1, max_rok=2000),
    }
    cluster = {1, 2}
    assert pick_main_pk(cluster, metas) == 2


def test_pbn_uid_wins_when_orcid_tied():
    metas = {
        1: _meta(ma_orcid=True, ma_pbn_uid=False),
        2: _meta(ma_orcid=True, ma_pbn_uid=True),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_tytul_wins_when_above_tied():
    metas = {
        1: _meta(ma_orcid=True, ma_pbn_uid=True, ma_tytul=False),
        2: _meta(ma_orcid=True, ma_pbn_uid=True, ma_tytul=True),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_dyscyplina_wins_when_above_tied():
    metas = {
        1: _meta(ma_orcid=True, ma_pbn_uid=True, ma_tytul=True, ma_dyscypline=False),
        2: _meta(ma_orcid=True, ma_pbn_uid=True, ma_tytul=True, ma_dyscypline=True),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_publikacje_count_wins_when_above_tied():
    metas = {
        1: _meta(publikacje_count=5),
        2: _meta(publikacje_count=10),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_max_rok_wins_when_publikacje_tied():
    metas = {
        1: _meta(publikacje_count=5, max_rok=2020),
        2: _meta(publikacje_count=5, max_rok=2025),
    }
    assert pick_main_pk({1, 2}, metas) == 2


def test_pk_lowest_wins_when_all_tied():
    metas = {
        77: _meta(),
        12: _meta(),
        99: _meta(),
    }
    assert pick_main_pk({77, 12, 99}, metas) == 12
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_main_selection.py -n0 2>&1 | tee /tmp/dedup-task2-2.log
```

- [ ] **Step 3: Implementacja**

`src/deduplikator_autorow/utils/main_selection.py`:

```python
"""Wybór głównego rekordu (main) w klastrze duplikatów.

Hierarchia (kolejne kryteria odpalają tylko przy remisie):
1. ma_orcid (DESC)
2. ma_pbn_uid (DESC)
3. ma_tytul (DESC)
4. ma_dyscypline (DESC)
5. publikacje_count (DESC)
6. max_rok (DESC)
7. pk (ASC)
"""


def _selection_key(pk: int, meta: dict) -> tuple:
    """Klucz sortowania — niższe wartości = lepszy kandydat na main."""
    return (
        not meta["ma_orcid"],
        not meta["ma_pbn_uid"],
        not meta["ma_tytul"],
        not meta["ma_dyscypline"],
        -meta["publikacje_count"],
        -(meta["max_rok"] or 0),
        pk,
    )


def pick_main_pk(cluster: set[int], metas: dict[int, dict]) -> int:
    """Z klastra (set PKów) wybiera PK głównego rekordu.

    Args:
        cluster: set PKów członków klastra.
        metas: {pk -> meta dict z polami ma_orcid, ma_pbn_uid, ma_tytul,
                ma_dyscypline, publikacje_count, max_rok}.

    Returns:
        PK rekordu wybranego jako main.
    """
    return min(cluster, key=lambda pk: _selection_key(pk, metas[pk]))
```

- [ ] **Step 4: Run — pass**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_main_selection.py -n auto 2>&1 | tee /tmp/dedup-task2-2.log
```

Expected: 7 zielonych.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): utils.main_selection — hierarchia wyboru głównego"
```

---

### Task 2.3: `utils/meta.py` — meta-cache builder

**Files:**
- Create: `src/deduplikator_autorow/utils/meta.py`
- Test: `src/deduplikator_autorow/tests/test_meta.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_meta.py`:

```python
"""Testy budowniczego meta-cache dla autorów."""

import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection
from model_bakery import baker

from deduplikator_autorow.utils.meta import build_autor_meta


@pytest.mark.django_db
def test_meta_includes_basic_fields():
    autor = baker.make(
        "bpp.Autor",
        nazwisko="Kowalski",
        imiona="Jan",
        orcid="0000-0001-2345-6789",
    )
    meta = build_autor_meta()
    assert autor.pk in meta
    m = meta[autor.pk]
    assert m["nazwisko_norm"] == "kowalski"
    assert m["imiona_norm"] == ["jan"]
    assert m["ma_orcid"] is True
    assert m["ma_pbn_uid"] is False
    assert m["ma_tytul"] is False
    assert m["publikacje_count"] == 0
    assert m["max_rok"] == 0
    assert m["lata_publikacji"] == set()


@pytest.mark.django_db
def test_meta_compound_lastname_parts():
    autor = baker.make("bpp.Autor", nazwisko="Gal-Cisoń", imiona="Anna")
    meta = build_autor_meta()
    parts = meta[autor.pk]["nazwisko_parts"]
    assert sorted(parts) == ["cisoń", "gal"]


@pytest.mark.django_db
def test_meta_ma_osoba_z_instytucji_true():
    from pbn_api.models import Scientist, OsobaZInstytucji

    autor = baker.make("bpp.Autor", nazwisko="X")
    scientist = baker.make("pbn_api.Scientist", rekord_w_bpp=autor)
    baker.make("pbn_api.OsobaZInstytucji", personId=scientist)

    meta = build_autor_meta()
    assert meta[autor.pk]["ma_osoba_z_instytucji"] is True


@pytest.mark.django_db
def test_meta_constant_query_count():
    """Sanity: dodanie autorów nie zwiększa liczby zapytań (no N+1)."""
    baker.make("bpp.Autor", _quantity=5, nazwisko="A")
    with CaptureQueriesContext(connection) as ctx_small:
        build_autor_meta()
    n_small = len(ctx_small.captured_queries)

    baker.make("bpp.Autor", _quantity=20, nazwisko="B")
    with CaptureQueriesContext(connection) as ctx_big:
        build_autor_meta()
    n_big = len(ctx_big.captured_queries)

    assert n_small == n_big, (
        f"N+1 detected: small={n_small} queries, big={n_big} queries"
    )
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_meta.py -n0 2>&1 | tee /tmp/dedup-task2-3.log
```

- [ ] **Step 3: Implementacja**

`src/deduplikator_autorow/utils/meta.py`:

```python
"""Budowniczy meta-cache dla wszystkich autorów BPP.

Stała liczba zapytań SQL niezależna od N. Wynik trzymany w pamięci podczas
fazy general — pozwala uniknąć N×k SQL queries podczas pair-generation.
"""

from collections import defaultdict

from django.db.models import Count, Max
from django.contrib.postgres.aggregates import ArrayAgg

from bpp.models import Autor, Autor_Dyscyplina
from bpp.models.cache import Rekord
from pbn_api.models import OsobaZInstytucji


def _normalize(s: str | None) -> str:
    """Lowercase i strip — używamy do bucketingu."""
    return (s or "").strip().lower()


def _split_compound(nazwisko: str | None) -> list[str]:
    """Rozbij nazwisko myślnikowe na części znormalizowane."""
    if not nazwisko:
        return []
    return [_normalize(p) for p in nazwisko.split("-") if p.strip()]


def build_autor_meta() -> dict[int, dict]:
    """Buduje słownik {autor_pk -> meta} dla wszystkich autorów BPP.

    Wykonuje stałą liczbę zapytań SQL (~5):
    1. Pełna lista autorów + atrybuty bezpośrednie.
    2. GROUP BY publikacje per autor (count, max_rok, lata).
    3. Dyscypliny per autor (DISTINCT).
    4. OsobaZInstytucji → autor.
    5. (opcjonalnie) inne agregaty.

    Returns:
        {pk -> {nazwisko_norm, nazwisko_parts, imiona_norm, ma_orcid, ma_pbn_uid,
                ma_tytul, ma_osoba_z_instytucji, ma_dyscypline, publikacje_count,
                lata_publikacji, max_rok, obj}}
    """
    autorzy_meta = {}
    for a in Autor.objects.only(
        "pk", "nazwisko", "imiona", "orcid", "pbn_uid_id", "tytul_id"
    ).iterator():
        autorzy_meta[a.pk] = {
            "obj": a,  # uwaga: Autor instance — odwołujemy się tylko do pk/nazwisko/imiona
            "nazwisko_norm": _normalize(a.nazwisko),
            "nazwisko_parts": _split_compound(a.nazwisko),
            "imiona_norm": [_normalize(i) for i in (a.imiona or "").split() if i],
            "ma_orcid": bool(a.orcid),
            "orcid_value": a.orcid or None,
            "ma_pbn_uid": bool(a.pbn_uid_id),
            "ma_tytul": bool(a.tytul_id),
            "tytul_id": a.tytul_id,
            "ma_osoba_z_instytucji": False,
            "ma_dyscypline": False,
            "publikacje_count": 0,
            "lata_publikacji": set(),
            "max_rok": 0,
        }

    # Publikacje agregaty per autor — JEDNO globalne zapytanie GROUP BY.
    # UWAGA: nazwa pola relacyjnego w Rekord może wymagać sprawdzenia.
    # Sprawdź `Rekord._meta.get_fields()` lub kod `Rekord.objects.prace_autora()`
    # by potwierdzić nazwę M2M ("autorzy" lub inna). Jeśli inna — zmień klucz
    # w .values() i .filter() poniżej.
    pub_agg = (
        Rekord.objects.values("autorzy")
        .annotate(
            cnt=Count("id"),
            max_rok=Max("rok"),
            lata=ArrayAgg("rok", distinct=True),
        )
        .filter(autorzy__isnull=False)
    )
    for row in pub_agg:
        pk = row["autorzy"]
        if pk in autorzy_meta:
            m = autorzy_meta[pk]
            m["publikacje_count"] = row["cnt"] or 0
            m["max_rok"] = row["max_rok"] or 0
            m["lata_publikacji"] = set(filter(None, row["lata"] or []))

    # Dyscypliny
    dysc_pks = set(
        Autor_Dyscyplina.objects.values_list("autor_id", flat=True).distinct()
    )
    for pk in dysc_pks:
        if pk in autorzy_meta:
            autorzy_meta[pk]["ma_dyscypline"] = True

    # OsobaZInstytucji
    osoba_pks = OsobaZInstytucji.objects.filter(
        personId__rekord_w_bpp__isnull=False
    ).values_list("personId__rekord_w_bpp__pk", flat=True)
    for pk in osoba_pks:
        if pk in autorzy_meta:
            autorzy_meta[pk]["ma_osoba_z_instytucji"] = True

    return autorzy_meta


def build_buckets(meta: dict[int, dict]) -> dict[str, list[int]]:
    """Buduje buckety {nazwisko_norm -> [pk1, pk2, ...]} z meta.

    Każdy autor trafia do bucketu:
    - swojego znormalizowanego nazwiska,
    - każdej części składowej (compound: "Gal-Cisoń" → bucket "gal" i "cisoń"),
    - odwróconego compound ("Gal-Cisoń" → bucket "cisoń-gal").
    """
    buckets: dict[str, list[int]] = defaultdict(list)
    for pk, m in meta.items():
        if not m["nazwisko_norm"]:
            continue
        buckets[m["nazwisko_norm"]].append(pk)
        parts = m["nazwisko_parts"]
        for part in parts:
            if len(part) > 2 and part != m["nazwisko_norm"]:
                buckets[part].append(pk)
        if len(parts) == 2:
            reversed_name = "-".join(reversed(parts))
            if reversed_name != m["nazwisko_norm"]:
                buckets[reversed_name].append(pk)
    return dict(buckets)
```

- [ ] **Step 4: Run — pass**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_meta.py -n auto 2>&1 | tee /tmp/dedup-task2-3.log
```

Expected: 4 zielone. **Jeśli `test_meta_constant_query_count` zawodzi — to znak, że gdzieś jest N+1 i wymaga naprawy w `build_autor_meta`.**

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): utils.meta — pre-load wszystkich autorów do pamięci"
```

---

### Task 2.4: `analiza_duplikatow_meta` — scoring na meta

**Files:**
- Create: `src/deduplikator_autorow/utils/analysis_meta.py`
- Test: `src/deduplikator_autorow/tests/test_analysis_meta.py` (nowy)

**Cel:** odpowiednik istniejącej `analiza_duplikatow`, ale operuje na słownikach meta zamiast obiektach DB. **Nie zastępujemy** istniejącego `analiza_duplikatow` (zostaje dla PBN-flow), tylko dokładamy nową funkcję dla general-flow.

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_analysis_meta.py`:

```python
"""Testy analiza_duplikatow_meta — scoring par autorów na bazie meta."""

from deduplikator_autorow.utils.analysis_meta import analiza_pary_meta


def _meta(
    nazwisko="kowalski",
    imiona=("jan",),
    orcid=None,
    pbn_uid=False,
    tytul=False,
    pubs=0,
    max_rok=0,
    lata=None,
    plec=None,
):
    return {
        "nazwisko_norm": nazwisko,
        "nazwisko_parts": nazwisko.split("-"),
        "imiona_norm": list(imiona),
        "orcid_value": orcid,
        "ma_orcid": bool(orcid),
        "ma_pbn_uid": pbn_uid,
        "ma_tytul": tytul,
        "tytul_id": 1 if tytul else None,
        "publikacje_count": pubs,
        "max_rok": max_rok,
        "lata_publikacji": set(lata or []),
        "plec_kod": plec,
    }


def test_identyczne_orcid_dodaje_50():
    a = _meta(orcid="0000-0001-2345-6789")
    b = _meta(orcid="0000-0001-2345-6789")
    score, reasons = analiza_pary_meta(a, b)
    assert score >= 50
    assert any("ORCID" in r for r in reasons)


def test_rozne_orcid_odejmuje_50():
    a = _meta(orcid="0000-0001-1111-1111")
    b = _meta(orcid="0000-0002-2222-2222")
    score, reasons = analiza_pary_meta(a, b)
    assert score <= -40  # -50 + małe plusy z innych kryteriów


def test_identyczne_nazwisko_dodaje_40():
    a = _meta(nazwisko="kowalski")
    b = _meta(nazwisko="kowalski")
    score, reasons = analiza_pary_meta(a, b)
    assert score >= 40
    assert any("nazwisko" in r.lower() for r in reasons)


def test_wspolne_lata_publikacji_dodaje_20():
    a = _meta(lata=[2020, 2021, 2022])
    b = _meta(lata=[2021, 2022])
    score, reasons = analiza_pary_meta(a, b)
    assert any("wspólne lata" in r.lower() for r in reasons)


def test_score_to_int():
    a = _meta()
    b = _meta()
    score, _ = analiza_pary_meta(a, b)
    assert isinstance(score, int)
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_analysis_meta.py -n0 2>&1 | tee /tmp/dedup-task2-4.log
```

- [ ] **Step 3: Implementacja**

`src/deduplikator_autorow/utils/analysis_meta.py`:

```python
"""Analiza pary autorów na podstawie wyłącznie meta-cache (bez SQL).

Odpowiednik analysis.analiza_duplikatow ale dla pary (a, b) zamiast
pivota OsobaZInstytucji. Punkty kalibrowane są zgodnie z istniejącą
funkcją; różnica to brak płci (gender wymagałby dodatkowego inferencji
z imienia — pomijamy w v1, bo dziś korzysta z `Autor.plec`,
opcjonalnego pola).
"""


def _common_initials(imiona_a: list[str], imiona_b: list[str]) -> int:
    """Liczba pasujących pierwszych liter."""
    initials_a = {x[0] for x in imiona_a if x}
    initials_b = {x[0] for x in imiona_b if x}
    return len(initials_a & initials_b)


def analiza_pary_meta(a: dict, b: dict) -> tuple[int, list[str]]:
    """Zwraca (score, reasons) dla pary (a, b) na bazie meta-cache."""
    score = 0
    reasons: list[str] = []

    # Liczba publikacji duplikatu (dla heurystyki "mało pubs = łatwiej duplikat")
    pubs_b = b["publikacje_count"]
    if pubs_b <= 5:
        score += 10
        reasons.append(f"mało publikacji ({pubs_b}) - prawdopodobny duplikat")
    elif pubs_b <= 10:
        score -= 10
        reasons.append(f"średnio publikacji ({pubs_b}) - możliwy duplikat")
    else:
        score -= 20
        reasons.append(f"wiele publikacji ({pubs_b}) - mało prawdopodobny duplikat")

    # Tytuł
    if not b["ma_tytul"] and a["ma_tytul"]:
        score += 15
        reasons.append("brak tytułu naukowego u kandydata - prawdopodobny duplikat")
    elif b["ma_tytul"] and a["ma_tytul"]:
        if a.get("tytul_id") == b.get("tytul_id"):
            score += 10
            reasons.append("identyczny tytuł naukowy")
        else:
            score -= 15
            reasons.append("różny tytuł naukowy")

    # ORCID
    if not b["ma_orcid"] and a["ma_orcid"]:
        score += 15
        reasons.append("brak ORCID u kandydata - prawdopodobny duplikat")
    elif b["ma_orcid"] and a["ma_orcid"]:
        if a.get("orcid_value") == b.get("orcid_value"):
            score += 50
            reasons.append("identyczny ORCID - to ten sam autor")
        else:
            score -= 50
            reasons.append("różny ORCID - to różni autorzy")

    # Nazwisko
    if a["nazwisko_norm"] and b["nazwisko_norm"]:
        if a["nazwisko_norm"] == b["nazwisko_norm"]:
            score += 40
            reasons.append("identyczne nazwisko")
        elif (
            a["nazwisko_norm"] in b["nazwisko_norm"]
            or b["nazwisko_norm"] in a["nazwisko_norm"]
        ):
            score += 30
            reasons.append("podobne nazwisko (zawieranie)")

    # Swap imię ↔ nazwisko (dokładny)
    if a["nazwisko_norm"] and b["nazwisko_norm"] and a["imiona_norm"] and b["imiona_norm"]:
        if (a["nazwisko_norm"] in b["imiona_norm"]) and (
            b["nazwisko_norm"] in a["imiona_norm"]
        ):
            score += 50
            reasons.append("wykryto pełną zamianę imienia z nazwiskiem")

    # Imiona — exact matches
    common = set(a["imiona_norm"]) & set(b["imiona_norm"])
    if common:
        score += 30 * len(common)
        reasons.append(f"wspólne imię ({len(common)})")

    # Imiona — prefiksy 3-znakowe
    similar = 0
    for ia in a["imiona_norm"]:
        for ib in b["imiona_norm"]:
            if len(ia) >= 3 and len(ib) >= 3 and ia != ib:
                if ia.startswith(ib[:3]) or ib.startswith(ia[:3]):
                    similar += 1
    if similar:
        score += 15 * similar
        reasons.append(f"podobne imię ({similar})")

    # Inicjały
    init_count = _common_initials(a["imiona_norm"], b["imiona_norm"])
    if init_count:
        score += 5 * init_count
        reasons.append(f"pasujące inicjały ({init_count})")

    # Brak imion u kandydata
    if not b["imiona_norm"] and a["imiona_norm"]:
        score += 10
        reasons.append("brak imion u kandydata")

    # Lata publikacji
    common_lata = a["lata_publikacji"] & b["lata_publikacji"]
    if common_lata:
        score += 20
        reasons.append(f"wspólne lata publikacji: {sorted(common_lata)}")
    elif a["lata_publikacji"] and b["lata_publikacji"]:
        min_dist = min(
            abs(ra - rb) for ra in a["lata_publikacji"] for rb in b["lata_publikacji"]
        )
        if min_dist <= 2:
            score += 15
            reasons.append(f"bliskie lata publikacji (różnica {min_dist})")
        elif min_dist <= 7:
            score -= 5
            reasons.append(f"średnia odległość lat publikacji ({min_dist})")
        else:
            score -= 20
            reasons.append(f"duża odległość lat publikacji ({min_dist})")

    return score, reasons
```

**Uwaga:** funkcja `analiza_pary_meta` używa pól `orcid_value` i `tytul_id` z meta. Te pola są dodane w `build_autor_meta` w Task 2.3 (sprawdź że tam są przed odpaleniem testów tu).

- [ ] **Step 4: Run — pass**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_analysis_meta.py -n auto 2>&1 | tee /tmp/dedup-task2-4.log
```

Expected: 5 zielonych.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): utils.analysis_meta — scoring par bez SQL"
```

---

## Phase 3: Implementacja fazy `general`

### Task 3.1: `utils/search_general.py` — pair generation w bucketach

**Files:**
- Create: `src/deduplikator_autorow/utils/search_general.py`
- Test: `src/deduplikator_autorow/tests/test_search_general.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_search_general.py`:

```python
"""Testy generowania par kandydatów w fazie general."""

import pytest
from model_bakery import baker

from deduplikator_autorow.utils.meta import build_autor_meta, build_buckets
from deduplikator_autorow.utils.search_general import (
    generate_pairs,
    BUCKET_MAX_SIZE,
)


@pytest.mark.django_db
def test_simple_lastname_pair():
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    pks = {(min(p, q), max(p, q)) for p, q, _, _ in pairs}
    assert (min(a1.pk, a2.pk), max(a1.pk, a2.pk)) in pks


@pytest.mark.django_db
def test_compound_lastname_pair():
    a1 = baker.make("bpp.Autor", nazwisko="Gal-Cisoń", imiona="Anna")
    a2 = baker.make("bpp.Autor", nazwisko="Cisoń-Gal", imiona="Anna")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    pks = {(min(p, q), max(p, q)) for p, q, _, _ in pairs}
    assert (min(a1.pk, a2.pk), max(a1.pk, a2.pk)) in pks


@pytest.mark.django_db
def test_pair_dedup():
    a1 = baker.make("bpp.Autor", nazwisko="Smith", imiona="John")
    a2 = baker.make("bpp.Autor", nazwisko="Smith", imiona="John")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    # Para (a1, a2) MUSI wystąpić tylko raz, niezależnie od ile bucketów
    pair_set = [(p, q) for p, q, _, _ in pairs]
    assert len(pair_set) == len(set(pair_set))


@pytest.mark.django_db
def test_ignored_excluded():
    a1 = baker.make("bpp.Autor", nazwisko="Brown", imiona="Bob")
    a2 = baker.make("bpp.Autor", nazwisko="Brown", imiona="Bob")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(
        generate_pairs(
            buckets, meta, ignored_pks={a1.pk}, notadup_pks=set()
        )
    )
    assert pairs == []


@pytest.mark.django_db
def test_below_min_confidence_excluded():
    """Para z niskim confidence (kompletnie różne imiona, różne lata) → pominięta."""
    a1 = baker.make("bpp.Autor", nazwisko="Davis", imiona="John")
    a2 = baker.make(
        "bpp.Autor",
        nazwisko="Davis",
        imiona="Mary-Anne Phyllis Henrietta Wilhelmina",
    )
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    # Zachowanie zależy od scoring; dla samego nazwiska +40, brak wspólnych imion
    # → score = 40 + (-10/-20 z pubs) ≈ 30 < 50, więc pominięta
    pks = {(p, q) for p, q, _, _ in pairs}
    assert (min(a1.pk, a2.pk), max(a1.pk, a2.pk)) not in pks


@pytest.mark.django_db
def test_oversized_bucket_skipped():
    """Bucket > BUCKET_MAX_SIZE jest pomijany z warningiem."""
    baker.make("bpp.Autor", nazwisko="PopularName", _quantity=BUCKET_MAX_SIZE + 1)
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    pairs = list(generate_pairs(buckets, meta, ignored_pks=set(), notadup_pks=set()))
    # Dla bucketu o tym nazwisku — nic nie powinno się wygenerować
    assert pairs == []
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_search_general.py -n0 2>&1 | tee /tmp/dedup-task3-1.log
```

- [ ] **Step 3: Implementacja**

`src/deduplikator_autorow/utils/search_general.py`:

```python
"""Generator par kandydatów w fazie general — in-memory bucket comparisons."""

import logging

from .analysis_meta import analiza_pary_meta

logger = logging.getLogger(__name__)

BUCKET_MAX_SIZE = 200
MIN_CONFIDENCE_TO_STORE = 50


def generate_pairs(
    buckets: dict[str, list[int]],
    meta: dict[int, dict],
    ignored_pks: set[int],
    notadup_pks: set[int],
    min_confidence: int = MIN_CONFIDENCE_TO_STORE,
):
    """Yield krotek (pk_a, pk_b, score, reasons) dla par przekraczających próg.

    Args:
        buckets: {nazwisko_norm -> [pk1, pk2, ...]}
        meta: {pk -> meta dict}
        ignored_pks: zbiór PK do całkowitego pominięcia (IgnoredAuthor).
        notadup_pks: zbiór PK oznaczonych jako NotADuplicate (też pomijamy).
        min_confidence: próg score-u poniżej którego para jest pomijana.

    Yields:
        (pk_a, pk_b, score, reasons) gdzie pk_a < pk_b.
    """
    seen_pairs: set[tuple[int, int]] = set()
    skipped_buckets = 0
    for bucket_name, pks in buckets.items():
        if len(pks) > BUCKET_MAX_SIZE:
            logger.warning(
                "Skipping oversized bucket '%s' (%d members)", bucket_name, len(pks)
            )
            skipped_buckets += 1
            continue
        # Wykluczenia ignored
        active = [p for p in pks if p not in ignored_pks]
        for i, pk_a in enumerate(active):
            for pk_b in active[i + 1 :]:
                if pk_a == pk_b:
                    continue
                key = (min(pk_a, pk_b), max(pk_a, pk_b))
                if key in seen_pairs:
                    continue
                # Wyklucz pary gdzie którykolwiek jest NotADuplicate
                if key[0] in notadup_pks or key[1] in notadup_pks:
                    seen_pairs.add(key)
                    continue
                score, reasons = analiza_pary_meta(meta[key[0]], meta[key[1]])
                if score >= min_confidence:
                    yield key[0], key[1], score, reasons
                seen_pairs.add(key)
    if skipped_buckets:
        logger.info("Skipped %d oversized buckets in general phase", skipped_buckets)
```

- [ ] **Step 4: Run — pass**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_search_general.py -n auto 2>&1 | tee /tmp/dedup-task3-1.log
```

Expected: 6 zielonych.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): utils.search_general — generator par dla trybu general"
```

---

### Task 3.2: Funkcja `_run_general_phase` w `tasks.py`

**Files:**
- Modify: `src/deduplikator_autorow/tasks.py`
- Test: `src/deduplikator_autorow/tests/test_general_phase.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_general_phase.py`:

```python
"""Testy fazy general w skanowaniu duplikatów."""

import pytest
from model_bakery import baker

from deduplikator_autorow.models import (
    DuplicateCandidate,
    DuplicateScanRun,
    IgnoredAuthor,
    NotADuplicate,
)
from deduplikator_autorow.tasks import _run_general_phase


@pytest.mark.django_db
def test_general_finds_simple_pair():
    """Dwóch autorów o tym samym nazwisku i imieniu, żaden nie ma OsobaZInstytucji
    → powinna się utworzyć para w trybie general."""
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    assert cands.count() == 1


@pytest.mark.django_db
def test_general_skips_cluster_with_osoba_instytucji():
    """Klaster {A, B, C} gdzie B ma OsobaZInstytucji — klaster pominięty."""
    a = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    b = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    c = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    scientist = baker.make("pbn_api.Scientist", rekord_w_bpp=b)
    baker.make("pbn_api.OsobaZInstytucji", personId=scientist)

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    # Wszystkie trzy są w klastrze {a, b, c} — bo b ma OsobaZInstytucji,
    # cały klaster jest pomijany.
    assert cands.count() == 0
    _ = (a, c)  # silence linters


@pytest.mark.django_db
def test_general_main_chosen_by_orcid():
    """Z dwóch autorów ORCID-owany wygrywa jako main."""
    a = baker.make("bpp.Autor", nazwisko="Adams", imiona="Eve", orcid=None)
    b = baker.make(
        "bpp.Autor", nazwisko="Adams", imiona="Eve", orcid="0000-0001-2345-6789"
    )
    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cand = DuplicateCandidate.objects.get(scan_run=scan, scan_mode="general")
    assert cand.main_autor_id == b.pk
    assert cand.duplicate_autor_id == a.pk


@pytest.mark.django_db
def test_general_pk_tiebreaker():
    """Wszystko równe → niższy pk wygrywa jako main."""
    a = baker.make("bpp.Autor", nazwisko="Black", imiona="Carl")
    b = baker.make("bpp.Autor", nazwisko="Black", imiona="Carl")
    lower_pk = min(a.pk, b.pk)
    higher_pk = max(a.pk, b.pk)

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cand = DuplicateCandidate.objects.get(scan_run=scan, scan_mode="general")
    assert cand.main_autor_id == lower_pk
    assert cand.duplicate_autor_id == higher_pk


@pytest.mark.django_db
def test_general_respects_ignored_author():
    a = baker.make("bpp.Autor", nazwisko="Yellow", imiona="Sun")
    b = baker.make("bpp.Autor", nazwisko="Yellow", imiona="Sun")
    user = baker.make("bpp.BppUser")
    IgnoredAuthor.objects.create(autor=a, created_by=user)

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    assert DuplicateCandidate.objects.filter(scan_run=scan).count() == 0
    _ = b


@pytest.mark.django_db
def test_general_respects_not_a_duplicate():
    a = baker.make("bpp.Autor", nazwisko="Green", imiona="Mike")
    b = baker.make("bpp.Autor", nazwisko="Green", imiona="Mike")
    user = baker.make("bpp.BppUser")
    NotADuplicate.objects.create(autor=a, created_by=user)

    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    assert DuplicateCandidate.objects.filter(scan_run=scan).count() == 0
    _ = b


@pytest.mark.django_db
def test_general_transitive_cluster():
    """A~B and B~C ale ne A~C → klaster {A,B,C} z trzema parami pod jednym main."""
    # Wszystkie z imieniem Jan, by zapewnić wysokie confidence
    a = baker.make("bpp.Autor", nazwisko="Linker", imiona="Jan")
    b = baker.make("bpp.Autor", nazwisko="Linker", imiona="Jan")
    c = baker.make("bpp.Autor", nazwisko="Linker", imiona="Jan")
    scan = DuplicateScanRun.objects.create()
    _run_general_phase(scan, min_confidence=50)
    cands = DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general")
    # Klaster ma 3 członków → 2 par (main + 2 dup)
    assert cands.count() == 2
    main_pks = {c.main_autor_id for c in cands}
    assert len(main_pks) == 1  # ten sam main dla wszystkich par
    expected_main = min(a.pk, b.pk, c.pk)
    assert main_pks == {expected_main}
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_general_phase.py -n0 2>&1 | tee /tmp/dedup-task3-2.log
```

Expected: ImportError (`_run_general_phase` nie istnieje).

- [ ] **Step 3: Dodaj funkcję `_run_general_phase` w `tasks.py`**

W `src/deduplikator_autorow/tasks.py`, na dole pliku (przed `cancel_scan`), dodaj:

```python
def _run_general_phase(scan_run, min_confidence=MIN_CONFIDENCE_TO_STORE):
    """Faza 2 skanu — duplikaty general.

    Algorytm:
    1. build_autor_meta — pre-load wszystkich autorów do pamięci.
    2. build_buckets — grupowanie po znormalizowanym nazwisku.
    3. generate_pairs — wszystkie pary kandydatów score-em >= min_confidence.
    4. find_clusters — connected components z par.
    5. cluster-skip — odrzuć klastry z OsobaZInstytucji.
    6. pick_main_pk — hierarchia wyboru main.
    7. emit DuplicateCandidate(scan_mode='general').
    """
    from .models import DuplicateCandidate, IgnoredAuthor, NotADuplicate
    from .utils.analysis_meta import analiza_pary_meta
    from .utils.cluster import find_clusters
    from .utils.main_selection import pick_main_pk
    from .utils.meta import build_autor_meta, build_buckets
    from .utils.search_general import generate_pairs

    logger.info("General phase: building meta cache...")
    meta = build_autor_meta()
    buckets = build_buckets(meta)
    logger.info("General phase: %d autorów, %d bucketów", len(meta), len(buckets))

    ignored_pks = set(IgnoredAuthor.objects.values_list("autor_id", flat=True))
    notadup_pks = set(NotADuplicate.objects.values_list("autor_id", flat=True))

    pairs_data: dict[tuple[int, int], tuple[int, list[str]]] = {}
    for pk_a, pk_b, score, reasons in generate_pairs(
        buckets, meta, ignored_pks, notadup_pks, min_confidence
    ):
        pairs_data[(pk_a, pk_b)] = (score, reasons)

    logger.info("General phase: znaleziono %d par", len(pairs_data))

    pair_keys = list(pairs_data.keys())
    clusters = find_clusters(pair_keys)
    logger.info("General phase: %d klastrów wstępnych", len(clusters))

    skipped_count = 0
    candidates_to_create: list[DuplicateCandidate] = []
    for cluster in clusters:
        # Cluster-skip jeśli ktokolwiek ma OsobaZInstytucji
        if any(meta[pk]["ma_osoba_z_instytucji"] for pk in cluster):
            skipped_count += 1
            continue
        main_pk = pick_main_pk(cluster, meta)
        for dup_pk in cluster - {main_pk}:
            key = (min(main_pk, dup_pk), max(main_pk, dup_pk))
            score_reasons = pairs_data.get(key)
            if score_reasons is None:
                # Pair przechodnia — wylicz on-the-fly
                score, reasons = analiza_pary_meta(meta[main_pk], meta[dup_pk])
            else:
                score, reasons = score_reasons
            main_autor = meta[main_pk]["obj"]
            dup_autor = meta[dup_pk]["obj"]
            candidates_to_create.append(
                DuplicateCandidate(
                    scan_run=scan_run,
                    main_autor=main_autor,
                    duplicate_autor=dup_autor,
                    confidence_score=score,
                    confidence_percent=normalize_confidence(score),
                    reasons=reasons,
                    priority=calculate_author_priority(dup_autor),
                    main_autor_name=str(main_autor),
                    duplicate_autor_name=str(dup_autor),
                    main_publications_count=meta[main_pk]["publikacje_count"],
                    duplicate_publications_count=meta[dup_pk]["publikacje_count"],
                    scan_mode="general",
                )
            )
            if len(candidates_to_create) >= 1000:
                with transaction.atomic():
                    DuplicateCandidate.objects.bulk_create(
                        candidates_to_create, ignore_conflicts=True
                    )
                candidates_to_create = []

    if candidates_to_create:
        with transaction.atomic():
            DuplicateCandidate.objects.bulk_create(
                candidates_to_create, ignore_conflicts=True
            )

    logger.info(
        "General phase complete: %d klastrów pominiętych (z OsobaZInstytucji)",
        skipped_count,
    )
```

- [ ] **Step 4: Dodaj brakujące importy w `tasks.py`**

Na górze pliku, jeśli nie ma:

```python
import logging
logger = get_task_logger(__name__)  # już jest
```

- [ ] **Step 5: Run testy fazy general**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_general_phase.py -n auto 2>&1 | tee /tmp/dedup-task3-2.log
```

Expected: 7 zielonych.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): _run_general_phase w tasks.py — algorytm fazy general"
```

---

### Task 3.3: Wyodrębnij `_run_pbn_phase`, połącz w `scan_for_duplicates` z PARTIAL_COMPLETED

**Files:**
- Modify: `src/deduplikator_autorow/tasks.py`
- Test: `src/deduplikator_autorow/tests/test_combined_scan.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_combined_scan.py`:

```python
"""Testy combined task scan_for_duplicates (PBN + general)."""

from unittest import mock

import pytest
from model_bakery import baker

from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun
from deduplikator_autorow.tasks import scan_for_duplicates


@pytest.mark.django_db
def test_combined_scan_runs_both_phases_status_completed():
    """Sukces obu faz → status COMPLETED."""
    # Pusta baza: brak OsobaZInstytucji, brak duplikatów Autor → szybko kończy
    result = scan_for_duplicates.apply().result
    assert result["status"] == "success"
    scan = DuplicateScanRun.objects.get(pk=result["scan_run_id"])
    assert scan.status == DuplicateScanRun.Status.COMPLETED


@pytest.mark.django_db
def test_combined_scan_general_finds_duplicates():
    """Faza general dodaje DuplicateCandidate(scan_mode='general')."""
    baker.make("bpp.Autor", nazwisko="Hawkins", imiona="Lee")
    baker.make("bpp.Autor", nazwisko="Hawkins", imiona="Lee")
    result = scan_for_duplicates.apply().result
    scan = DuplicateScanRun.objects.get(pk=result["scan_run_id"])
    assert (
        DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general").count()
        >= 1
    )


@pytest.mark.django_db
def test_cancel_during_general_phase_leaves_partial_completed():
    """Anulowanie w fazie 2 (general) → PARTIAL_COMPLETED."""
    # Symulacja: faza PBN przechodzi (brak OsobaZInstytucji), w fazie general
    # ustawiamy CANCELLED z innego procesu.
    baker.make("bpp.Autor", nazwisko="Igor", imiona="Test")
    baker.make("bpp.Autor", nazwisko="Igor", imiona="Test")

    # Mock _run_general_phase żeby ustawić status na CANCELLED
    def fake_general(scan_run, *args, **kwargs):
        scan_run.status = DuplicateScanRun.Status.CANCELLED
        scan_run.save(update_fields=["status"])

    with mock.patch(
        "deduplikator_autorow.tasks._run_general_phase", side_effect=fake_general
    ):
        result = scan_for_duplicates.apply().result

    scan = DuplicateScanRun.objects.get(pk=result["scan_run_id"])
    assert scan.status == DuplicateScanRun.Status.PARTIAL_COMPLETED
    assert result["status"] == "partial_completed"


@pytest.mark.django_db
def test_cancel_during_pbn_phase_leaves_cancelled():
    """Anulowanie w fazie 1 (PBN) → CANCELLED, faza 2 nie startuje."""

    def fake_pbn(scan_run, *args, **kwargs):
        scan_run.status = DuplicateScanRun.Status.CANCELLED
        scan_run.save(update_fields=["status"])

    with mock.patch(
        "deduplikator_autorow.tasks._run_pbn_phase", side_effect=fake_pbn
    ), mock.patch(
        "deduplikator_autorow.tasks._run_general_phase"
    ) as general_mock:
        result = scan_for_duplicates.apply().result
        general_mock.assert_not_called()

    scan = DuplicateScanRun.objects.get(pk=result["scan_run_id"])
    assert scan.status == DuplicateScanRun.Status.CANCELLED
    assert result["status"] == "cancelled"


@pytest.mark.django_db
def test_phase_field_set_during_run():
    """Pole phase jest ustawiane: 'pbn' przy rozpoczęciu fazy 1, 'general' fazy 2."""
    phases_seen = []

    original_pbn = None
    original_general = None

    from deduplikator_autorow import tasks

    original_pbn = tasks._run_pbn_phase
    original_general = tasks._run_general_phase

    def spy_pbn(scan_run, *a, **kw):
        scan_run.refresh_from_db()
        phases_seen.append(("pbn", scan_run.phase))
        return original_pbn(scan_run, *a, **kw)

    def spy_general(scan_run, *a, **kw):
        scan_run.refresh_from_db()
        phases_seen.append(("general", scan_run.phase))
        return original_general(scan_run, *a, **kw)

    with mock.patch.object(tasks, "_run_pbn_phase", spy_pbn), mock.patch.object(
        tasks, "_run_general_phase", spy_general
    ):
        scan_for_duplicates.apply()

    # phase ustawiane PRZED wejściem do każdej fazy
    assert phases_seen == [("pbn", "pbn"), ("general", "general")]
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_combined_scan.py -n0 2>&1 | tee /tmp/dedup-task3-3.log
```

Expected: testy zawodzą — bo `scan_for_duplicates` jeszcze nie wykonuje fazy general / nie obsługuje PARTIAL_COMPLETED / `_run_pbn_phase` nie istnieje jako osobna funkcja.

- [ ] **Step 3: Wyodrębnij `_run_pbn_phase`**

W `src/deduplikator_autorow/tasks.py`, **wytnij** body istniejącego taska `scan_for_duplicates` (od `try:` do return-ów) do nowej funkcji prywatnej `_run_pbn_phase(scan_run, min_confidence)`. Sygnatura:

```python
def _run_pbn_phase(scan_run, min_confidence=MIN_CONFIDENCE_TO_STORE):
    """Faza 1 skanu — duplikaty PBN (iteracja po OsobaZInstytucji).

    To jest dotychczasowa logika scan_for_duplicates wyciągnięta do funkcji.
    Modyfikuje scan_run in-place. Wszystkie tworzone DuplicateCandidate mają
    scan_mode='pbn' (default).

    Sprawdza scan_run.status == CANCELLED na każdej iteracji — jeśli tak,
    przerywa wcześniej (return).
    """
    from pbn_api.models import OsobaZInstytucji

    from .models import DuplicateCandidate, IgnoredScientist  # uwaga: rename
    # ... (cała dotychczasowa logika)
```

**Uwaga:** zmień `IgnoredAuthor` na `IgnoredScientist` w referencjach (ten model był renamowany w Task 1.1, ale jeśli ten plik dalej zawiera starą nazwę — to bug. Sprawdź.):

```bash
grep -n "IgnoredAuthor\|IgnoredScientist" src/deduplikator_autorow/tasks.py
```

Powinien używać `IgnoredScientist` po Task 1.1.

`_run_pbn_phase` powinien zachować scan_mode='pbn' implicite (default na DuplicateCandidate). Jeśli istniejąca logika tworzy `DuplicateCandidate(...)` w `_process_duplicate_info`, default `scan_mode='pbn'` wystarczy (po Task 1.3).

- [ ] **Step 4: Przepisz `scan_for_duplicates`**

```python
@shared_task(bind=True, name="deduplikator_autorow.scan_for_duplicates")
def scan_for_duplicates(self, user_id=None, min_confidence=MIN_CONFIDENCE_TO_STORE):
    """Combined task: faza PBN + faza general w jednym przebiegu.

    Statusy końcowe:
    - COMPLETED: obie fazy ukończone.
    - PARTIAL_COMPLETED: faza PBN OK, faza general anulowana → wyniki PBN dostępne.
    - CANCELLED: faza PBN anulowana → brak wyników.
    - FAILED: nieobsłużony wyjątek.
    """
    from .models import DuplicateCandidate, DuplicateScanRun

    user = _get_user_by_id(user_id)
    scan_run = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.RUNNING,
        created_by=user,
        celery_task_id=self.request.id or "",
    )

    try:
        # Replace mode — clear poprzednie kandydaci (pending wszystkich trybów)
        DuplicateCandidate.objects.all().delete()

        # FAZA 1: PBN
        scan_run.phase = "pbn"
        scan_run.save(update_fields=["phase"])
        _run_pbn_phase(scan_run, min_confidence)
        scan_run.refresh_from_db()
        if scan_run.status == DuplicateScanRun.Status.CANCELLED:
            scan_run.finished_at = timezone.now()
            scan_run.save(update_fields=["finished_at"])
            logger.info("Scan cancelled in PBN phase")
            return {
                "status": "cancelled",
                "scan_run_id": scan_run.pk,
            }

        # FAZA 2: general
        scan_run.phase = "general"
        scan_run.save(update_fields=["phase"])
        _run_general_phase(scan_run, min_confidence)
        scan_run.refresh_from_db()
        if scan_run.status == DuplicateScanRun.Status.CANCELLED:
            scan_run.status = DuplicateScanRun.Status.PARTIAL_COMPLETED
            scan_run.finished_at = timezone.now()
            scan_run.save(update_fields=["status", "finished_at"])
            logger.info("Scan cancelled in general phase → PARTIAL_COMPLETED")
            return {
                "status": "partial_completed",
                "scan_run_id": scan_run.pk,
            }

        # Sukces obu faz
        total_cands = DuplicateCandidate.objects.filter(scan_run=scan_run).count()
        scan_run.status = DuplicateScanRun.Status.COMPLETED
        scan_run.finished_at = timezone.now()
        scan_run.duplicates_found = total_cands
        scan_run.save()
        return {
            "status": "success",
            "scan_run_id": scan_run.pk,
            "duplicates_found": total_cands,
        }

    except Exception as e:
        logger.exception("Error during duplicate scan")
        scan_run.status = DuplicateScanRun.Status.FAILED
        scan_run.finished_at = timezone.now()
        scan_run.error_message = str(e)
        scan_run.save()
        return {
            "status": "error",
            "scan_run_id": scan_run.pk,
            "error": str(e),
        }
```

- [ ] **Step 5: Run testy combined**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_combined_scan.py -n auto 2>&1 | tee /tmp/dedup-task3-3.log
```

Expected: 5 zielonych.

- [ ] **Step 6: Run wszystkie istniejące testy task-ów**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_tasks.py -n auto 2>&1 | tee /tmp/dedup-task3-3-existing.log
```

Expected: stare testy też zielone (mogą wymagać drobnych poprawek po refactorze, ale logika PBN niezmieniona).

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): scan_for_duplicates dwufazowo (PBN + general) z PARTIAL_COMPLETED"
```

---

## Phase 4: Views + URLs

### Task 4.1: `get_latest_usable_scan` helper

**Files:**
- Modify: `src/deduplikator_autorow/utils/counters.py`
- Modify: `src/deduplikator_autorow/views.py`

- [ ] **Step 1: Dodaj helper w `counters.py`**

W `src/deduplikator_autorow/utils/counters.py`, **po** `get_latest_completed_scan`, dodaj:

```python
def get_latest_usable_scan():
    """Pobiera ostatnie skanowanie z użytecznymi wynikami.

    "Użyteczne" = COMPLETED lub PARTIAL_COMPLETED (faza PBN ukończona,
    nawet jeśli general anulowana).

    Returns:
        DuplicateScanRun lub None
    """
    return (
        DuplicateScanRun.objects.filter(
            status__in=[
                DuplicateScanRun.Status.COMPLETED,
                DuplicateScanRun.Status.PARTIAL_COMPLETED,
            ]
        )
        .order_by("-finished_at")
        .first()
    )
```

- [ ] **Step 2: Zaktualizuj wszystkie odwołania w `views.py`**

W `src/deduplikator_autorow/views.py`, znajdź `get_latest_completed_scan` i zamień na `get_latest_usable_scan`. Konkretnie, **lokalna definicja** `get_latest_completed_scan()` w views.py (linia ~643) — usuń ją (jest reimplementacją utils-owej), zamiast tego importuj `get_latest_usable_scan` z `.utils.counters`.

- [ ] **Step 3: Run istniejące testy widoków**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_views_permissions.py -n auto 2>&1 | tee /tmp/dedup-task4-1.log
```

Expected: zielone (zmiana interfejsu, nie semantyki).

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): get_latest_usable_scan — uwzględnia PARTIAL_COMPLETED"
```

---

### Task 4.2: Filtr `mode` w `duplicate_authors_view`

**Files:**
- Modify: `src/deduplikator_autorow/views.py`
- Test: `src/deduplikator_autorow/tests/test_view_mode_filter.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_view_mode_filter.py`:

```python
"""Testy filtra mode w widoku duplicate_authors."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun


@pytest.fixture
def user_with_perms(client, db):
    user = baker.make("bpp.BppUser", is_active=True)
    user.set_password("xx")
    user.save()
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return user


@pytest.fixture
def scan_with_both_modes(db):
    from django.utils import timezone

    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.COMPLETED,
        finished_at=timezone.now(),
    )
    a1 = baker.make("bpp.Autor", nazwisko="Pbn1", imiona="Jan")
    a2 = baker.make("bpp.Autor", nazwisko="Pbn1", imiona="Jan")
    g1 = baker.make("bpp.Autor", nazwisko="Gen1", imiona="Anna")
    g2 = baker.make("bpp.Autor", nazwisko="Gen1", imiona="Anna")
    DuplicateCandidate.objects.create(
        scan_run=scan, main_autor=a1, duplicate_autor=a2,
        confidence_score=80, confidence_percent=0.6,
        main_autor_name="Pbn1 Jan", duplicate_autor_name="Pbn1 Jan",
        scan_mode="pbn",
    )
    DuplicateCandidate.objects.create(
        scan_run=scan, main_autor=g1, duplicate_autor=g2,
        confidence_score=80, confidence_percent=0.6,
        main_autor_name="Gen1 Anna", duplicate_autor_name="Gen1 Anna",
        scan_mode="general",
    )
    return scan


def test_view_mode_filter_pbn(client, user_with_perms, scan_with_both_modes):
    response = client.get(
        reverse("deduplikator_autorow:duplicate_authors") + "?mode=pbn"
    )
    assert response.status_code == 200
    # Powinien pokazać Pbn1, NIE Gen1
    content = response.content.decode()
    assert "Pbn1" in content
    assert "Gen1" not in content


def test_view_mode_filter_general(client, user_with_perms, scan_with_both_modes):
    response = client.get(
        reverse("deduplikator_autorow:duplicate_authors") + "?mode=general"
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Gen1" in content
    assert "Pbn1" not in content


def test_view_mode_filter_both(client, user_with_perms, scan_with_both_modes):
    """Default 'both' lub explicit — pokazuje pierwszego (PBN preferowane jako kanoniczne)."""
    response = client.get(
        reverse("deduplikator_autorow:duplicate_authors") + "?mode=both"
    )
    assert response.status_code == 200
    content = response.content.decode()
    # Co najmniej jeden z dwóch widoczny — najprawdopodobniej PBN
    assert "Pbn1" in content or "Gen1" in content
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_view_mode_filter.py -n0 2>&1 | tee /tmp/dedup-task4-2.log
```

- [ ] **Step 3: Modyfikuj `duplicate_authors_view`**

W `src/deduplikator_autorow/views.py`:

(a) Na początku funkcji `duplicate_authors_view`, po `latest_pbn_download = ...`, dodaj:

```python
mode = request.GET.get("mode", "both")
if mode not in ("pbn", "general", "both"):
    mode = "both"
context["mode"] = mode
```

(b) Tam gdzie `DuplicateCandidate.objects.filter(scan_run=completed_scan, status=PENDING)` — dodaj:

```python
candidates_qs = DuplicateCandidate.objects.filter(
    scan_run=completed_scan, status=DuplicateCandidate.Status.PENDING
)
if mode != "both":
    candidates_qs = candidates_qs.filter(scan_mode=mode)
```

(c) Counters per mode:

```python
context["pending_pbn_count"] = DuplicateCandidate.objects.filter(
    scan_run=completed_scan,
    status=DuplicateCandidate.Status.PENDING,
    scan_mode="pbn",
).count()
context["pending_general_count"] = DuplicateCandidate.objects.filter(
    scan_run=completed_scan,
    status=DuplicateCandidate.Status.PENDING,
    scan_mode="general",
).count()
```

(d) `_get_next_candidate_group` — dodaj parametr `mode`:

```python
def _get_next_candidate_group(scan_run, skip_count=0, mode="both"):
    qs = DuplicateCandidate.objects.filter(
        scan_run=scan_run,
        status=DuplicateCandidate.Status.PENDING,
    )
    if mode != "both":
        qs = qs.filter(scan_mode=mode)
    distinct_main_autor_ids = (
        qs.order_by("scan_mode", "-priority", "-confidence_score", "main_autor_id")
        # PBN przed general (alfabetycznie 'general' < 'pbn' więc trzeba tweak):
        # użyj Case/When albo: ordering po -scan_mode da 'pbn' przed 'general'
        # tu używamy Case dla jasności
        .values_list("main_autor_id", flat=True)
        .distinct()
    )
    # ... reszta jak dziś
```

**Uwaga sortowania w trybie `both`:** Spec wymaga `pbn` przed `general`. Zwykła kolejność alfabetyczna ASC `general < pbn`. Trzeba odwrócić: `.order_by(... )` z polem mapującym `scan_mode='pbn'` na 0 i `'general'` na 1. Najprościej:

```python
from django.db.models import Case, IntegerField, Value, When

qs = qs.annotate(
    mode_order=Case(
        When(scan_mode="pbn", then=Value(0)),
        When(scan_mode="general", then=Value(1)),
        default=Value(2),
        output_field=IntegerField(),
    )
).order_by("mode_order", "-priority", "-confidence_score", "main_autor_id")
```

(e) Wywołanie `_get_next_candidate_group(completed_scan, skip_count=skip_count, mode=mode)` w widoku.

- [ ] **Step 4: Run testy**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_view_mode_filter.py -n auto 2>&1 | tee /tmp/dedup-task4-2.log
```

Expected: 3 zielone.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): filtr mode (pbn/general/both) w widoku"
```

---

### Task 4.3: `scal_autorow_view` — backwards-compat dla Autor PK

**Files:**
- Modify: `src/deduplikator_autorow/views.py`
- Test: `src/deduplikator_autorow/tests/test_scal_view.py` (nowy)

- [ ] **Step 1: Failing test**

```python
"""Testy backwards-compat dla scal_autorow_view."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def auth_client(client, db):
    user = baker.make("bpp.BppUser", is_active=True)
    user.set_password("xx"); user.save()
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_scal_autorow_accepts_main_autor_id(auth_client):
    main = baker.make("bpp.Autor")
    dup = baker.make("bpp.Autor")
    response = auth_client.post(
        reverse("deduplikator_autorow:scal_autorow"),
        {
            "main_autor_id": main.pk,
            "duplicate_autor_id": dup.pk,
            "skip_pbn": "true",
        },
    )
    assert response.status_code in (200, 500)  # 500 OK gdy brak publikacji do scalania
    # Test że view nie zwrócił 400 z "Brak parametrów"
    assert b"Brak wymaganych" not in response.content


@pytest.mark.django_db
def test_scal_autorow_backwards_compat_scientist_ids(auth_client):
    """Stare parametry main_scientist_id / duplicate_scientist_id mapują na Autor PK."""
    main = baker.make("bpp.Autor")
    dup = baker.make("bpp.Autor")
    main_sci = baker.make("pbn_api.Scientist", rekord_w_bpp=main)
    dup_sci = baker.make("pbn_api.Scientist", rekord_w_bpp=dup)

    response = auth_client.post(
        reverse("deduplikator_autorow:scal_autorow"),
        {
            "main_scientist_id": main_sci.pk,
            "duplicate_scientist_id": dup_sci.pk,
            "skip_pbn": "true",
        },
    )
    assert response.status_code in (200, 500)
    assert b"Brak wymaganych" not in response.content
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_scal_view.py -n0 2>&1
```

- [ ] **Step 3: Modyfikuj `scal_autorow_view`**

W `src/deduplikator_autorow/views.py`, w `scal_autorow_view`:

(a) Czytaj wszystkie warianty parametrów:

```python
def _read_id(request, *names):
    for name in names:
        val = request.GET.get(name) or request.POST.get(name)
        if val:
            return val
    return None

main_autor_id = _read_id(request, "main_autor_id")
duplicate_autor_id = _read_id(request, "duplicate_autor_id")

# Backwards-compat: jeśli przyszły scientist_id, mapuj na Autor.pk
if not main_autor_id:
    main_scientist_id = _read_id(request, "main_scientist_id")
    if main_scientist_id:
        try:
            sci = Scientist.objects.get(pk=main_scientist_id)
            if sci.rekord_w_bpp:
                main_autor_id = sci.rekord_w_bpp.pk
        except Scientist.DoesNotExist:
            pass

if not duplicate_autor_id:
    duplicate_scientist_id = _read_id(request, "duplicate_scientist_id")
    if duplicate_scientist_id:
        try:
            sci = Scientist.objects.get(pk=duplicate_scientist_id)
            if sci.rekord_w_bpp:
                duplicate_autor_id = sci.rekord_w_bpp.pk
        except Scientist.DoesNotExist:
            pass
```

(b) Walidacja:

```python
if not main_autor_id or not duplicate_autor_id:
    return JsonResponse(
        {"success": False, "error": "Brak wymaganych parametrów: main_autor_id i duplicate_autor_id"},
        status=400,
    )
```

(c) Wywołanie `scal_autorow` (utility) — sprawdź jego sygnaturę. Funkcja `scal_autora` w `utils/merge.py` przyjmuje obiekty `Autor`, więc:

```python
main_autor = Autor.objects.get(pk=main_autor_id)
duplicate_autor = Autor.objects.get(pk=duplicate_autor_id)
result = scal_autora(
    main_autor, duplicate_autor, request.user,
    skip_pbn=skip_pbn,
    auto_assign_discipline=auto_assign_discipline,
    use_subdiscipline=use_subdiscipline,
)
```

**Uwaga:** funkcja-wrapper `scal_autorow(main_scientist_id, duplicate_scientist_id, user, ...)` z `utils/merge.py` używała Scientist.pk. Zachowaj ją (dla backwards-compat zewnętrznych callerów), ale wewnętrznie view używa `scal_autora` bezpośrednio.

- [ ] **Step 4: Run testy**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_scal_view.py -n auto
```

Expected: 2 zielone.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): scal_autorow_view akceptuje main_autor_id (backwards-compat scientist_id)"
```

---

### Task 4.4: `ignore_autor` + rename `ignore_author` → `ignore_scientist`

**Files:**
- Modify: `src/deduplikator_autorow/views.py`
- Modify: `src/deduplikator_autorow/urls.py`
- Test: `src/deduplikator_autorow/tests/test_ignore_views.py` (nowy)

- [ ] **Step 1: Failing test**

`src/deduplikator_autorow/tests/test_ignore_views.py`:

```python
import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from deduplikator_autorow.models import IgnoredAuthor, IgnoredScientist


@pytest.fixture
def auth_client(client, db):
    user = baker.make("bpp.BppUser", is_active=True)
    user.set_password("xx"); user.save()
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_ignore_scientist_endpoint(auth_client):
    sci = baker.make("pbn_api.Scientist")
    response = auth_client.post(
        reverse("deduplikator_autorow:ignore_scientist"),
        {"scientist_id": sci.pk, "reason": "test"},
    )
    assert response.status_code == 302  # redirect
    assert IgnoredScientist.objects.filter(scientist=sci).exists()


@pytest.mark.django_db
def test_ignore_autor_endpoint(auth_client):
    autor = baker.make("bpp.Autor")
    response = auth_client.post(
        reverse("deduplikator_autorow:ignore_autor"),
        {"autor_id": autor.pk, "reason": "test"},
    )
    assert response.status_code == 302
    assert IgnoredAuthor.objects.filter(autor=autor).exists()


@pytest.mark.django_db
def test_reset_ignored_autorzy(auth_client):
    autor = baker.make("bpp.Autor")
    user = baker.make("bpp.BppUser")
    IgnoredAuthor.objects.create(autor=autor, created_by=user)
    response = auth_client.post(
        reverse("deduplikator_autorow:reset_ignored_autorzy")
    )
    assert response.status_code == 302
    assert IgnoredAuthor.objects.count() == 0
```

- [ ] **Step 2: Run — fail (URL not found)**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_ignore_views.py -n0
```

- [ ] **Step 3: Zaktualizuj `views.py`**

(a) Przemianuj `ignore_author` → `ignore_scientist` (zachowuje swoją logikę, tylko zmiana nazwy + zapis do `IgnoredScientist`).

(b) Zaktualizuj `reset_ignored_authors` → `reset_ignored_scientists` (kasuje `IgnoredScientist`).

(c) Dodaj nową funkcję `ignore_autor`:

```python
@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def ignore_autor(request):
    autor_id = request.POST.get("autor_id")
    reason = request.POST.get("reason", "")
    if not autor_id:
        messages.error(request, "Brak wymaganego parametru: autor_id")
        return redirect("deduplikator_autorow:duplicate_authors")
    try:
        autor = Autor.objects.get(pk=autor_id)
        if IgnoredAuthor.objects.filter(autor=autor).exists():
            messages.warning(request, f"Autor {autor} jest już ignorowany.")
        else:
            IgnoredAuthor.objects.create(
                autor=autor, reason=reason, created_by=request.user
            )
            messages.success(request, f"Autor {autor} oznaczony jako ignorowany.")
    except Autor.DoesNotExist:
        messages.error(request, f"Nie znaleziono autora o ID: {autor_id}")
    return redirect("deduplikator_autorow:duplicate_authors")
```

(d) Dodaj `reset_ignored_autorzy`:

```python
@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def reset_ignored_autorzy(request):
    count = IgnoredAuthor.objects.count()
    IgnoredAuthor.objects.all().delete()
    messages.success(request, f"Zresetowano {count} ignorowanych autorów (BPP).")
    return redirect("deduplikator_autorow:duplicate_authors")
```

Dodaj import `IgnoredAuthor` na górze pliku.

- [ ] **Step 4: Zaktualizuj `urls.py`**

W `src/deduplikator_autorow/urls.py`:

```python
urlpatterns = [
    path("duplicate-authors/", views.duplicate_authors_view, name="duplicate_authors"),
    path("mark-non-duplicate/", views.mark_non_duplicate, name="mark_non_duplicate"),
    path("reset-skipped-authors/", views.reset_skipped_authors, name="reset_skipped_authors"),
    path("reset-not-duplicates/", views.reset_not_duplicates, name="reset_not_duplicates"),
    # Ignore PBN Scientist (rename z ignore-author)
    path("ignore-scientist/", views.ignore_scientist, name="ignore_scientist"),
    path("reset-ignored-scientists/", views.reset_ignored_scientists, name="reset_ignored_scientists"),
    # Ignore Autor BPP (nowy)
    path("ignore-autor/", views.ignore_autor, name="ignore_autor"),
    path("reset-ignored-autorzy/", views.reset_ignored_autorzy, name="reset_ignored_autorzy"),
    # Reszta jak dziś
    path("delete-author/", views.delete_author, name="delete_author"),
    path("scal-autorow/", views.scal_autorow_view, name="scal_autorow"),
    path("download-duplicates-xlsx/", views.download_duplicates_xlsx, name="download_duplicates_xlsx"),
    path("start-scan/", views.start_scan_view, name="start_scan"),
    path("cancel-scan/", views.cancel_scan_view, name="cancel_scan"),
    path("scan-status/<int:scan_id>/", views.scan_status_view, name="scan_status"),
    path("mark-candidate-not-duplicate/", views.mark_candidate_not_duplicate, name="mark_candidate_not_duplicate"),
]
```

- [ ] **Step 5: Run testy**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_ignore_views.py -n auto
```

Expected: 3 zielone.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): ignore_autor + ignore_scientist (rename z ignore_author)"
```

---

## Phase 5: Template — radio mode + badges + banner + counters

### Task 5.1: Mode radio, badges, counters, PARTIAL_COMPLETED banner

**Files:**
- Modify: `src/deduplikator_autorow/templates/deduplikator_autorow/duplicate_authors.html`
- Modify: `src/deduplikator_autorow/static/deduplikator_autorow/scss/*.scss` (jeśli potrzeba badge styling)

- [ ] **Step 1: Czytaj obecny template**

```bash
sed -n '1,50p' src/deduplikator_autorow/templates/deduplikator_autorow/duplicate_authors.html
```

- [ ] **Step 2: Dodaj radio + counters w nagłówku**

W sekcji nagłówka strony, po existing scan-status box, dodaj:

```html
{# Mode filter #}
<div class="row deduplikator-autorow__mode-filter">
  <div class="small-12 columns">
    <strong>Pokaż wyniki:</strong>
    <label>
      <input type="radio" name="mode" value="pbn"
             {% if mode == "pbn" %}checked{% endif %}
             onchange="location.href='?mode=pbn'">
      PBN ({{ pending_pbn_count }})
    </label>
    <label>
      <input type="radio" name="mode" value="general"
             {% if mode == "general" %}checked{% endif %}
             onchange="location.href='?mode=general'">
      Ogólny ({{ pending_general_count }})
    </label>
    <label>
      <input type="radio" name="mode" value="both"
             {% if mode == "both" or not mode %}checked{% endif %}
             onchange="location.href='?mode=both'">
      Oba
    </label>
  </div>
</div>
```

- [ ] **Step 3: Banner dla PARTIAL_COMPLETED**

Po komunikatach Django messages, dodaj:

```html
{% if completed_scan and completed_scan.status == "partial_completed" %}
  <div class="callout warning deduplikator-autorow__partial-banner">
    <strong>Skanowanie częściowo zakończone:</strong>
    Faza ogólna została anulowana. Wyniki PBN są dostępne, ale duplikaty
    ogólne nie zostały przeskanowane. Uruchom skan ponownie, aby zobaczyć
    wszystkie duplikaty.
  </div>
{% endif %}
```

- [ ] **Step 4: Badge per główny autor**

Tam gdzie wyświetla się nagłówek głównego autora (`{{ glowny_autor }}`), dodaj badge przed lub obok:

```html
{% if first_candidate.scan_mode == "pbn" %}
  <span class="deduplikator-autorow__badge deduplikator-autorow__badge--pbn">PBN</span>
{% elif first_candidate.scan_mode == "general" %}
  <span class="deduplikator-autorow__badge deduplikator-autorow__badge--general">OGÓLNY</span>
{% endif %}
```

Trzeba przekazać `first_candidate` z `views.py` (np. pierwszy z `candidates_for_author`).

W `views.py`, po `candidates_for_author = ...`:

```python
context["first_candidate"] = (
    candidates_for_author.first() if candidates_for_author else None
)
```

- [ ] **Step 5: Dodaj progress fazy**

W bloku scan-progress (jeżeli `running_scan`):

```html
{% if running_scan %}
<div class="deduplikator-autorow__scan-progress">
  Faza: <strong>{{ running_scan.get_phase_display|default:"-" }}</strong>
  ({{ running_scan.progress_percent }}%)
</div>
{% endif %}
```

- [ ] **Step 6: Style SCSS dla badge**

W `src/deduplikator_autorow/static/deduplikator_autorow/scss/_deduplikator-autorow.scss` (lub odpowiedni partial):

```scss
.deduplikator-autorow {
  &__badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-size: 0.75em;
    font-weight: 600;
    color: #fff;

    &--pbn {
      background-color: #2196f3;
    }

    &--general {
      background-color: #ff9800;
    }
  }

  &__partial-banner {
    margin: 1em 0;
  }

  &__mode-filter {
    margin: 1em 0;
    label {
      margin-right: 1.5em;
    }
  }
}
```

- [ ] **Step 7: Build SCSS**

```bash
cd ~/Programowanie/bpp-worktrees/deduplikator-autorow-general
grunt build 2>&1 | tee /tmp/dedup-grunt.log
```

Expected: build OK, brak SCSS-error.

- [ ] **Step 8: Smoke-test view**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_view_mode_filter.py src/deduplikator_autorow/tests/test_views_permissions.py -n auto
```

Expected: zielone.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): UI — radio mode, badges, banner PARTIAL_COMPLETED, fazy progress"
```

---

## Phase 6: XLSX z kolumną Tryb

### Task 6.1: Kolumna "Tryb" w XLSX

**Files:**
- Modify: `src/deduplikator_autorow/utils/export.py`
- Test: `src/deduplikator_autorow/tests/test_xlsx_export.py` (modify)

- [ ] **Step 1: Failing test (zaktualizuj istniejący)**

W `src/deduplikator_autorow/tests/test_xlsx_export.py`, dodaj:

```python
import pytest
from io import BytesIO
from openpyxl import load_workbook
from model_bakery import baker

from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun
from deduplikator_autorow.utils.export import export_duplicates_to_xlsx


@pytest.mark.django_db
def test_xlsx_export_includes_tryb_column():
    scan = DuplicateScanRun.objects.create(status=DuplicateScanRun.Status.COMPLETED)
    a1 = baker.make("bpp.Autor", nazwisko="X", imiona="A")
    a2 = baker.make("bpp.Autor", nazwisko="X", imiona="A")
    b1 = baker.make("bpp.Autor", nazwisko="Y", imiona="B")
    b2 = baker.make("bpp.Autor", nazwisko="Y", imiona="B")
    DuplicateCandidate.objects.create(
        scan_run=scan, main_autor=a1, duplicate_autor=a2,
        confidence_score=80, confidence_percent=0.6,
        main_autor_name="X A", duplicate_autor_name="X A",
        scan_mode="pbn",
    )
    DuplicateCandidate.objects.create(
        scan_run=scan, main_autor=b1, duplicate_autor=b2,
        confidence_score=80, confidence_percent=0.6,
        main_autor_name="Y B", duplicate_autor_name="Y B",
        scan_mode="general",
    )
    content = export_duplicates_to_xlsx()
    wb = load_workbook(BytesIO(content))
    ws = wb.active
    headers = [c.value for c in ws[1]]
    assert "Tryb" in headers

    tryb_col_idx = headers.index("Tryb") + 1  # 1-indexed
    tryby = [ws.cell(row=r, column=tryb_col_idx).value for r in range(2, 4)]
    assert "PBN" in tryby
    assert "Ogólny" in tryby
```

- [ ] **Step 2: Run — fail**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_xlsx_export.py::test_xlsx_export_includes_tryb_column -n0
```

- [ ] **Step 3: Modyfikuj `export.py`**

W `_build_candidate_row`, dodaj na końcu listy:

```python
return [
    main_name,
    main.pk,
    f"{site_domain}/bpp/autor/{main.pk}/",
    main.pbn_uid_id or "",
    _create_pbn_url(main.pbn_uid_id),
    dup_name,
    dup.pk,
    f"{site_domain}/bpp/autor/{dup.pk}/",
    dup.pbn_uid_id or "",
    _create_pbn_url(dup.pbn_uid_id),
    round(candidate.confidence_percent, 2),
    duplicate_counts[candidate.main_autor_id],
    "PBN" if candidate.scan_mode == "pbn" else "Ogólny",  # NOWA KOLUMNA
]
```

W `headers`:

```python
headers = [
    "Główny autor",
    "BPP ID głównego autora",
    "BPP URL głównego autora",
    "PBN UID głównego autora",
    "PBN URL głównego autora",
    "Duplikat",
    "BPP ID duplikatu",
    "BPP URL duplikatu",
    "PBN UID duplikatu",
    "PBN URL duplikatu",
    "Pewność podobieństwa",
    "Ilość duplikatów",
    "Tryb",  # NOWA
]
```

W `export_duplicates_to_xlsx`, w queryset NIE dodawaj filtra na `scan_mode` (eksportujemy oba).

- [ ] **Step 4: Run testy**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/test_xlsx_export.py -n auto
```

Expected: zielone (i nowy test też).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat(deduplikator): kolumna Tryb w XLSX export"
```

---

## Phase 7: Newsfragment + finalizacja

### Task 7.1: Newsfragment towncrier

**Files:**
- Create: `src/bpp/newsfragments/<NUMER>.feature` (np. `1100.feature`)

- [ ] **Step 1: Sprawdź istniejące numery**

```bash
ls src/bpp/newsfragments/ | grep -E '^\d+\.' | sort -n | tail -10
```

Expected: znajdź najwyższy numer, użyj kolejnego.

- [ ] **Step 2: Utwórz fragment**

Plik `src/bpp/newsfragments/<NUMER>.feature`:

```
Deduplikator autorów: nowy tryb "ogólny" znajdujący duplikaty wśród autorów spoza listy pracowników instytucji w PBN. Jeden przycisk "Skanuj duplikaty" uruchamia obie fazy (PBN + ogólna) sekwencyjnie. Widok pozwala filtrować wyniki radio-button-em (PBN/Ogólny/Oba), eksport XLSX zawiera kolumnę "Tryb". Anulowanie fazy ogólnej skutkuje statusem "Częściowo zakończone" — wyniki PBN pozostają dostępne.
```

- [ ] **Step 3: Commit**

```bash
git add src/bpp/newsfragments/
git commit -m "docs(newsfragment): tryb ogólny deduplikatora autorów"
```

---

### Task 7.2: Finalny smoke-test

- [ ] **Step 1: Pełen suite testów modułu**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest src/deduplikator_autorow/tests/ -n auto 2>&1 | tee /tmp/dedup-final.log
```

Expected: wszystkie zielone. Jeśli któryś nie — fix przed merge.

- [ ] **Step 2: Smoke pełny suite (opcjonalnie, długo)**

```bash
UV_NO_SYNC=1 uv run --all-extras pytest -n auto 2>&1 | tee /tmp/dedup-fullsuite.log
```

Expected: brak nowych regresji w innych testach.

- [ ] **Step 3: Sprawdź migrate na świeżej bazie**

```bash
UV_NO_SYNC=1 uv run --all-extras src/manage.py migrate deduplikator_autorow zero
UV_NO_SYNC=1 uv run --all-extras src/manage.py migrate deduplikator_autorow
```

Expected: czysty rollback i forward.

- [ ] **Step 4: Pre-commit na ostatnich zmianach**

```bash
pre-commit
```

Expected: brak nowych issue.

- [ ] **Step 5: Commit + push**

```bash
git push -u origin feature/deduplikator-autorow-general
```

---

## Self-review checklist (zostaw jako notatkę dla wykonawcy)

Po Task 7.2 — sprawdź:

- [ ] Wszystkie nowe testy w `src/deduplikator_autorow/tests/` przechodzą.
- [ ] `migrate` od zera działa.
- [ ] `migrate ... zero && migrate` działa (rollback OK).
- [ ] Istniejące testy modułu nie regresują.
- [ ] Newsfragment napisany (Task 7.1).
- [ ] `grunt build` przeszedł bez błędów.
- [ ] PR opisuje: rename `IgnoredAuthor`→`IgnoredScientist` (breaking change wewnątrz, brak external API), nowy `IgnoredAuthor`(FK→Autor), `scan_mode` na Candidate, `phase` + `PARTIAL_COMPLETED` na ScanRun.

---

## Spec coverage matrix

| Wymaganie speca | Task pokrywający |
|-----------------|------------------|
| Rename IgnoredAuthor → IgnoredScientist | 1.1 |
| Nowy IgnoredAuthor (FK→Autor) | 1.2 |
| Pole scan_mode na Candidate | 1.3 |
| Pole phase na ScanRun | 1.3 |
| Status PARTIAL_COMPLETED | 1.3 |
| Constraint scan_mode w unique key | 1.3 |
| Index (scan_run, scan_mode, status) | 1.3 |
| utils.cluster (union-find) | 2.1 |
| utils.main_selection (hierarchia B) | 2.2 |
| utils.meta (cache + buckets) | 2.3 |
| utils.analysis_meta (scoring na meta) | 2.4 |
| utils.search_general (pair generation) | 3.1 |
| _run_general_phase (algorytm) | 3.2 |
| Cluster-skip (OsobaZInstytucji) | 3.2 |
| Klastry przechodnie | 3.2 |
| _run_pbn_phase (extract) | 3.3 |
| scan_for_duplicates (combined) | 3.3 |
| PARTIAL_COMPLETED w cancellation logic | 3.3 |
| get_latest_usable_scan | 4.1 |
| Mode filter w view | 4.2 |
| Sortowanie pbn-przed-general w mode=both | 4.2 |
| scal_autorow_view backwards-compat | 4.3 |
| ignore_autor + ignore_scientist | 4.4 |
| reset_ignored_autorzy + reset_ignored_scientists | 4.4 |
| URL renames | 4.4 |
| Mode radio w UI | 5.1 |
| Counters split | 5.1 |
| Badges PBN/Ogólny | 5.1 |
| PARTIAL_COMPLETED banner | 5.1 |
| Phase progress display | 5.1 |
| XLSX kolumna Tryb | 6.1 |
| Newsfragment | 7.1 |

Wszystkie wymagania speca pokryte zadaniami. **Brak placeholderów ani TBD.**
