# PBN Import — rozdzielenie pobierania od przetwarzania — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rozdzielić każdy rozdzielalny krok importu PBN na dwie niezależnie
uruchamiane fazy — pobieranie (download → lustro `pbn_api.*`) i przetwarzanie
(process → modele BPP) — z dwukolumnowym formularzem i zgodnością wsteczną.

**Architecture:** `ImportStepBase` zyskuje metody `download()`/`process()`,
a `run()` = obie po kolei. Sześć importerów (źródła, wydawcy, konferencje,
autorzy, publikacje, oświadczenia) rozbijamy na te metody; reszta bez zmian.
`step_definitions.py` przechodzi na model **faz** (każda faza ma własny
`form_field`/`disable_key`/`method`), a `ImportManager` wykonuje fazy płasko,
zachowując kolejność per-encja (download→process). Config to JSONField bez
migracji; resolver zgodności wstecznej tłumaczy stary `disable_<encja>` na obie
fazy. Dodajemy brakującą integrację konferencji (`integruj_konferencje`).

**Tech Stack:** Django, pytest + model_bakery, pbn_integrator, Foundation CSS
(panel admin importu), HTMX/JS w `dashboard.html`.

**Spec:** `docs/superpowers/specs/2026-06-07-pbn-import-rozdzielenie-pobierania-od-przetwarzania-design.md`

---

## Uwagi wykonawcze (przeczytaj przed startem)

- **Wszystkie komendy Pythona przez `uv run`.** Nigdy gołe `python`/`pytest`.
- **Max 88 znaków/linia** (ruff). Po każdym tasku z kodem: `ruff format <pliki>`
  i `ruff check <pliki>` — naprawiaj ręcznie (NIE `--fix`).
- **Nie modyfikuj istniejących migracji.** Tu i tak nie ma zmian w modelach.
- Testy korzystają z testcontainers (wymagany Docker). Jeśli masz własne
  usługi: `PYTEST_TESTCONTAINERS_DISABLE=1 uv run pytest …`.
- Każdy task kończy się commitem. Wiadomości commitów po polsku, z trailerem
  `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Pracujesz w worktree `~/Programowanie/bpp-pbn-import-split` na branchu
  `feature/pbn-import-rozdziel-pobieranie`.

---

## Task 1: `ImportStepBase` — metody faz i wywołanie per-metoda

Dodaje `download()`/`process()`/`run()` oraz `__call__(method=…)`, nie psując
istniejących importerów (które wciąż mają własne `run()`).

**Files:**
- Modify: `src/pbn_import/utils/base.py`
- Test: `src/pbn_import/tests/test_step_phase_dispatch.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# src/pbn_import/tests/test_step_phase_dispatch.py
"""Testy dyspozytora faz w ImportStepBase (download/process/run/__call__)."""

import pytest
from model_bakery import baker

from pbn_import.utils.base import ImportStepBase


class _DummyStep(ImportStepBase):
    step_name = "dummy"
    step_description = "Dummy"

    def __init__(self, session):
        super().__init__(session)
        self.calls = []

    def download(self):
        self.calls.append("download")
        return {"phase": "download"}

    def process(self):
        self.calls.append("process")
        return {"phase": "process"}


@pytest.fixture
def session(db):
    user = baker.make("auth.User")
    return baker.make("pbn_import.ImportSession", user=user)


def test_call_default_runs_both_phases(session):
    step = _DummyStep(session)
    result = step()  # default method="run"
    assert step.calls == ["download", "process"]
    assert result == {"phase": "process"}


def test_call_download_only(session):
    step = _DummyStep(session)
    result = step(method="download")
    assert step.calls == ["download"]
    assert result == {"phase": "download"}


def test_call_process_only(session):
    step = _DummyStep(session)
    result = step(method="process")
    assert step.calls == ["process"]
    assert result == {"phase": "process"}


def test_base_download_process_not_implemented(session):
    class _Bare(ImportStepBase):
        step_name = "bare"

    bare = _Bare(session)
    with pytest.raises(NotImplementedError):
        bare.download()
    with pytest.raises(NotImplementedError):
        bare.process()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_step_phase_dispatch.py -v`
Expected: FAIL — `TypeError: __call__() got an unexpected keyword argument 'method'`
(oraz brak `download`/`process` w bazie).

- [ ] **Step 3: Implement in `base.py`**

W `ImportStepBase` zastąp obecne `run()` i `__call__()` poniższym. Zostaw
istniejący `run()` z `@transaction.atomic` jako `run()` domyślny, ale zmień
jego ciało na sekwencję faz. Dodaj `download()`/`process()`.

```python
    def download(self):
        """Faza pobierania danych z PBN do lustra. Nadpisz w podklasie."""
        raise NotImplementedError("Krok nie implementuje fazy pobierania")

    def process(self):
        """Faza przetwarzania lustra do modeli BPP. Nadpisz w podklasie."""
        raise NotImplementedError("Krok nie implementuje fazy przetwarzania")

    @transaction.atomic
    def run(self):
        """Domyślnie: pobierz, potem przetwórz (zgodność wsteczna)."""
        self.download()
        return self.process()

    def __call__(self, method: str = "run"):
        """Uruchom wskazaną fazę (run/download/process) z obwiednią start/finish."""
        self.start()
        try:
            result = getattr(self, method)()
            self.finish()
            return result
        except Exception as e:
            # handle_error robi raport do Rollbara + log; mark_failed robi ImportManager
            self.handle_error(e, f"Krytyczny błąd w {self.step_name}")
            raise
```

Uwaga: usuń poprzednią definicję `def run(self): raise NotImplementedError(...)`
oraz poprzedni `def __call__(self):` — zastępujemy je powyższymi.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_step_phase_dispatch.py -v`
Expected: PASS (4 testy).

- [ ] **Step 5: Sanity — istniejące importery wciąż działają przez `run`**

Run: `uv run pytest src/pbn_import/tests/test_importer_wrappers.py src/pbn_import/tests/test_step_constructor_contract.py -v`
Expected: PASS (importery z własnym `run()` nadpisują bazowy — bez regresji).

- [ ] **Step 6: Lint + commit**

```bash
ruff format src/pbn_import/utils/base.py src/pbn_import/tests/test_step_phase_dispatch.py
ruff check src/pbn_import/utils/base.py src/pbn_import/tests/test_step_phase_dispatch.py
git add src/pbn_import/utils/base.py src/pbn_import/tests/test_step_phase_dispatch.py
git commit -m "feat(pbn-import): ImportStepBase — fazy download/process i __call__(method)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: `integruj_konferencje` — nowa integracja lustro → BPP

Mapuje `pbn_api.Conference` na `bpp.Konferencja` (idempotentnie).

**Files:**
- Modify: `src/pbn_integrator/utils/conferences.py`
- Modify: `src/pbn_integrator/utils/__init__.py` (eksport + `__all__`)
- Test: `src/pbn_integrator/tests/test_integruj_konferencje.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# src/pbn_integrator/tests/test_integruj_konferencje.py
"""Testy integracji konferencji PBN → BPP."""

import datetime

import pytest
from model_bakery import baker

from bpp.models import Konferencja
from pbn_api.models import Conference
from pbn_integrator.utils import integruj_konferencje


def _make_conference(mongo_id, obj):
    """Utwórz lustro Conference z podanym JSON-em 'object'."""
    return baker.make(
        Conference,
        mongoId=mongo_id,
        versions=[{"current": True, "object": obj}],
        status="ACTIVE",
    )


@pytest.mark.django_db
def test_tworzy_konferencje_z_lustra():
    _make_conference(
        "c1",
        {
            "fullName": "Międzynarodowa Konferencja XYZ",
            "startDate": "2023-09-01",
            "endDate": "2023-09-03",
            "city": "Kraków",
            "country": "Polska",
            "abbreviation": "MKXYZ",
        },
    )

    liczba = integruj_konferencje()

    assert liczba == 1
    k = Konferencja.objects.get()
    assert k.nazwa == "Międzynarodowa Konferencja XYZ"
    assert k.rozpoczecie == datetime.date(2023, 9, 1)
    assert k.zakonczenie == datetime.date(2023, 9, 3)
    assert k.miasto == "Kraków"
    assert k.panstwo == "Polska"
    assert k.skrocona_nazwa == "MKXYZ"
    assert k.pbn_uid_id == "c1"


@pytest.mark.django_db
def test_idempotentne_po_pbn_uid():
    _make_conference(
        "c1", {"fullName": "Konf A", "startDate": "2022-01-01"}
    )
    integruj_konferencje()
    integruj_konferencje()
    assert Konferencja.objects.filter(pbn_uid_id="c1").count() == 1


@pytest.mark.django_db
def test_dowiazuje_istniejaca_po_nazwie_i_dacie():
    # Konferencja wprowadzona ręcznie, bez pbn_uid
    Konferencja.objects.create(
        nazwa="Konf B", rozpoczecie=datetime.date(2021, 5, 5)
    )
    _make_conference(
        "c2", {"fullName": "Konf B", "startDate": "2021-05-05", "city": "Łódź"}
    )

    integruj_konferencje()

    assert Konferencja.objects.count() == 1
    k = Konferencja.objects.get()
    assert k.pbn_uid_id == "c2"
    assert k.miasto == "Łódź"


@pytest.mark.django_db
def test_pomija_status_deleted():
    baker.make(
        Conference,
        mongoId="c3",
        versions=[{"current": True, "object": {"fullName": "Konf C"}}],
        status="DELETED",
    )
    assert integruj_konferencje() == 0
    assert Konferencja.objects.count() == 0


@pytest.mark.django_db
def test_zla_data_daje_none_bez_bledu():
    _make_conference(
        "c4", {"fullName": "Konf D", "startDate": "niepoprawna-data"}
    )
    assert integruj_konferencje() == 1
    k = Konferencja.objects.get(pbn_uid_id="c4")
    assert k.rozpoczecie is None


@pytest.mark.django_db
def test_pomija_rekord_bez_nazwy():
    _make_conference("c5", {"startDate": "2020-01-01"})
    assert integruj_konferencje() == 0
    assert Konferencja.objects.count() == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_integrator/tests/test_integruj_konferencje.py -v`
Expected: FAIL — `ImportError: cannot import name 'integruj_konferencje'`.

- [ ] **Step 3: Implement `integruj_konferencje` w `conferences.py`**

Dopisz na końcu `src/pbn_integrator/utils/conferences.py` (dołóż importy u góry):

```python
import datetime
import logging

from bpp.models import Konferencja

logger = logging.getLogger("pbn_integrator")


def _parse_pbn_date(value):
    """Sparsuj 'YYYY-MM-DD' na date; None gdy brak/niepoprawne."""
    if not value:
        return None
    try:
        return datetime.date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        logger.debug("Niepoprawna data konferencji PBN: %r", value)
        return None


def integruj_konferencje(callback=None):
    """Integruj lustro pbn_api.Conference → bpp.Konferencja.

    Re-entrant: dopasowuje po pbn_uid, potem po (nazwa, rozpoczecie).
    Aktualizuje pola pochodzące z PBN; nie nadpisuje pól, których PBN nie
    dostarcza (typ_konferencji, bazy indeksujące). Zwraca liczbę
    utworzonych/zaktualizowanych konferencji.
    """
    qs = Conference.objects.all()
    total = qs.count()
    przetworzone = 0

    for i, conf in enumerate(qs.iterator(), 1):
        if callback is not None:
            callback.update(i, total, "Integracja konferencji")

        if conf.status == "DELETED":
            logger.info("Pomijam usuniętą konferencję PBN %s", conf.mongoId)
            continue

        nazwa = conf.fullName()
        if not nazwa:
            logger.info("Pomijam konferencję PBN %s bez nazwy", conf.mongoId)
            continue

        rozpoczecie = _parse_pbn_date(conf.startDate())
        zakonczenie = _parse_pbn_date(conf.endDate())
        miasto = conf.city() or None
        panstwo = conf.country() or None
        skrot = conf.value("object", "abbreviation", return_none=True)

        konferencja = Konferencja.objects.filter(pbn_uid_id=conf.pk).first()
        if konferencja is None:
            konferencja = Konferencja.objects.filter(
                nazwa=nazwa, rozpoczecie=rozpoczecie
            ).first()

        if konferencja is None:
            konferencja = Konferencja(nazwa=nazwa, rozpoczecie=rozpoczecie)

        konferencja.pbn_uid_id = conf.pk
        konferencja.nazwa = nazwa
        konferencja.rozpoczecie = rozpoczecie
        konferencja.zakonczenie = zakonczenie
        konferencja.miasto = miasto
        konferencja.panstwo = panstwo
        if skrot:
            konferencja.skrocona_nazwa = skrot
        konferencja.save()
        przetworzone += 1

    return przetworzone
```

- [ ] **Step 4: Eksportuj funkcję w `utils/__init__.py`**

W `src/pbn_integrator/utils/__init__.py` rozszerz import konferencji i `__all__`:

```python
from pbn_integrator.utils.conferences import (  # noqa
    integruj_konferencje,
    pobierz_konferencje,
)
```

oraz w liście `__all__` obok `"pobierz_konferencje"` dodaj:

```python
    "integruj_konferencje",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/pbn_integrator/tests/test_integruj_konferencje.py -v`
Expected: PASS (6 testów).

Jeśli `versions`/`value("object", …)` w teście nie odwzorowuje realnego
kształtu (sprawdź `src/pbn_api/models/base.py` metodę `value`), dostosuj
`_make_conference` tak, by `conf.fullName()` zwracało wartość — kontrakt
produkcyjny (`value("object", key)`) zostaje bez zmian.

- [ ] **Step 6: Lint + commit**

```bash
ruff format src/pbn_integrator/utils/conferences.py src/pbn_integrator/utils/__init__.py src/pbn_integrator/tests/test_integruj_konferencje.py
ruff check src/pbn_integrator/utils/conferences.py src/pbn_integrator/utils/__init__.py src/pbn_integrator/tests/test_integruj_konferencje.py
git add src/pbn_integrator/utils/conferences.py src/pbn_integrator/utils/__init__.py src/pbn_integrator/tests/test_integruj_konferencje.py
git commit -m "feat(pbn-integrator): integruj_konferencje — lustro Conference → BPP Konferencja

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: `ConferenceImporter` — split download/process

**Files:**
- Modify: `src/pbn_import/utils/conference_import.py`
- Test: `src/pbn_import/tests/test_conference_importer_split.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# src/pbn_import/tests/test_conference_importer_split.py
"""ConferenceImporter: download woła pobierz, process woła integruj."""

import pytest
from model_bakery import baker

from pbn_import.utils import conference_import


@pytest.fixture
def step(db):
    user = baker.make("auth.User")
    session = baker.make("pbn_import.ImportSession", user=user)
    return conference_import.ConferenceImporter(session, client=object())


def test_download_calls_pobierz_not_integruj(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        conference_import, "pobierz_konferencje",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        conference_import, "integruj_konferencje",
        lambda *a, **k: called.append("integruj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_calls_integruj_not_pobierz(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        conference_import, "pobierz_konferencje",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        conference_import, "integruj_konferencje",
        lambda *a, **k: called.append("integruj") or 3,
    )
    step.process()
    assert called == ["integruj"]


def test_process_warns_when_mirror_empty(step, monkeypatch):
    monkeypatch.setattr(
        conference_import, "integruj_konferencje", lambda *a, **k: 0
    )
    step.process()
    warnings = step.session.logs.filter(level="warning")
    assert warnings.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_conference_importer_split.py -v`
Expected: FAIL — `AttributeError: 'ConferenceImporter' object has no attribute 'download'`.

- [ ] **Step 3: Rewrite `conference_import.py`**

```python
"""Conference import utilities"""

from pbn_api.models import Conference
from pbn_integrator.utils import integruj_konferencje, pobierz_konferencje

from .base import ImportStepBase


class ConferenceImporter(ImportStepBase):
    """Import conferences from PBN"""

    step_name = "conference_import"
    step_description = "Import konferencji"

    def download(self):
        """Pobierz konferencje z PBN do lustra."""
        self.update_progress(0, 1, "Pobieranie konferencji z PBN")
        self.log("info", "Pobieranie konferencji z PBN")
        subtask_callback = self.create_subtask_progress("Pobieranie konferencji")
        try:
            pobierz_konferencje(self.client, callback=subtask_callback)
            self.log("success", "Konferencje pobrane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać konferencji")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono pobieranie konferencji")
        return {"conferences_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zintegruj lustro konferencji do BPP."""
        if not Conference.objects.exists():
            self.log(
                "warning",
                "Brak pobranych konferencji — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )
        self.update_progress(0, 1, "Integracja konferencji")
        subtask_callback = self.create_subtask_progress("Integracja konferencji")
        try:
            liczba = integruj_konferencje(callback=subtask_callback)
            self.log("success", f"Zintegrowano {liczba} konferencji")
        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować konferencji")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono integrację konferencji")
        return {"conferences_integrated": True, "error_count": len(self.errors)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_conference_importer_split.py -v`
Expected: PASS (3 testy).

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/pbn_import/utils/conference_import.py src/pbn_import/tests/test_conference_importer_split.py
ruff check src/pbn_import/utils/conference_import.py src/pbn_import/tests/test_conference_importer_split.py
git add src/pbn_import/utils/conference_import.py src/pbn_import/tests/test_conference_importer_split.py
git commit -m "feat(pbn-import): ConferenceImporter — split download/process

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: `SourceImporter` — split download/process

**Files:**
- Modify: `src/pbn_import/utils/source_import.py`
- Test: `src/pbn_import/tests/test_source_importer_split.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# src/pbn_import/tests/test_source_importer_split.py
"""SourceImporter: download woła pobierz, process woła importuj."""

import pytest
from model_bakery import baker

from pbn_import.utils import source_import


@pytest.fixture
def step(db):
    user = baker.make("auth.User")
    session = baker.make("pbn_import.ImportSession", user=user)
    return source_import.SourceImporter(session, client=object())


def test_download_calls_pobierz_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        source_import, "pobierz_zrodla_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        source_import.importer, "importuj_zrodla",
        lambda *a, **k: called.append("importuj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_calls_importuj_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        source_import, "pobierz_zrodla_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        source_import.importer, "importuj_zrodla",
        lambda *a, **k: called.append("importuj") or 5,
    )
    step.process()
    assert called == ["importuj"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_source_importer_split.py -v`
Expected: FAIL — brak metody `download`.

- [ ] **Step 3: Rewrite `source_import.py`**

```python
"""Source (journal) import utilities"""

from pbn_api.models import Journal
from pbn_integrator import importer
from pbn_integrator.utils import pobierz_zrodla_mnisw

from .base import ImportStepBase


class SourceImporter(ImportStepBase):
    """Import sources/journals from PBN"""

    step_name = "source_import"
    step_description = "Import źródeł (czasopism)"

    def download(self):
        """Pobierz źródła z PBN (MNiSW) do lustra."""
        self.update_progress(0, 1, "Pobieranie źródeł z PBN")
        self.log("info", "Pobieranie źródeł z MNiSW")
        subtask_callback = self.create_subtask_progress("Pobieranie źródeł MNiSW")
        try:
            pobierz_zrodla_mnisw(self.client, callback=subtask_callback)
            self.log("success", "Źródła pobrane pomyślnie")
        except Exception as e:
            self.handle_pbn_error(e, "Nie udało się pobrać źródeł")
            self.log("warning", "Kontynuacja z częściowymi danymi")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono pobieranie źródeł")
        return {"sources_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zaimportuj źródła z lustra do BPP."""
        if not Journal.objects.exists():
            self.log(
                "warning",
                "Brak pobranych źródeł — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )
        self.update_progress(0, 1, "Importowanie źródeł do bazy danych")
        self.log("info", "Importowanie źródeł do bazy danych")
        try:
            result = importer.importuj_zrodla()
            if hasattr(self.session, "statistics") and isinstance(
                result, (int, float)
            ):
                stats = self.session.statistics
                stats.journals_imported = int(result)
                stats.save()
            self.log("success", "Źródła zaimportowane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się zaimportować źródeł")
            raise
        self.update_progress(1, 1, "Zakończono import źródeł")
        return {"sources_imported": True, "error_count": len(self.errors)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_source_importer_split.py src/pbn_import/tests/test_source_scoring_import.py -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/pbn_import/utils/source_import.py src/pbn_import/tests/test_source_importer_split.py
ruff check src/pbn_import/utils/source_import.py src/pbn_import/tests/test_source_importer_split.py
git add src/pbn_import/utils/source_import.py src/pbn_import/tests/test_source_importer_split.py
git commit -m "feat(pbn-import): SourceImporter — split download/process

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: `PublisherImporter` — split download/process

**Files:**
- Modify: `src/pbn_import/utils/publisher_import.py`
- Test: `src/pbn_import/tests/test_publisher_importer_split.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# src/pbn_import/tests/test_publisher_importer_split.py
"""PublisherImporter: download woła pobierz, process woła importuj."""

import pytest
from model_bakery import baker

from pbn_import.utils import publisher_import


@pytest.fixture
def step(db):
    user = baker.make("auth.User")
    session = baker.make("pbn_import.ImportSession", user=user)
    return publisher_import.PublisherImporter(session, client=object())


def test_download_calls_pobierz_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        publisher_import, "pobierz_wydawcow_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        publisher_import.importer, "importuj_wydawcow",
        lambda *a, **k: called.append("importuj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_calls_importuj_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        publisher_import, "pobierz_wydawcow_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        publisher_import.importer, "importuj_wydawcow",
        lambda *a, **k: called.append("importuj") or 7,
    )
    step.process()
    assert called == ["importuj"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_publisher_importer_split.py -v`
Expected: FAIL — brak metody `download`.

- [ ] **Step 3: Rewrite `publisher_import.py`**

```python
"""Publisher import utilities"""

from pbn_api.models import Publisher
from pbn_integrator import importer
from pbn_integrator.utils import pobierz_wydawcow_mnisw

from .base import ImportStepBase


class PublisherImporter(ImportStepBase):
    """Import publishers from PBN"""

    step_name = "publisher_import"
    step_description = "Import wydawców"

    def download(self):
        """Pobierz wydawców z PBN (MNiSW) do lustra."""
        self.update_progress(0, 1, "Pobieranie wydawców z PBN")
        self.log("info", "Pobieranie wydawców z MNiSW")
        try:
            pobierz_wydawcow_mnisw(self.client)
            self.log("success", "Wydawcy pobrani pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać wydawców")
        self.update_progress(1, 1, "Zakończono pobieranie wydawców")
        return {"publishers_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zaimportuj wydawców z lustra do BPP."""
        if not Publisher.objects.exists():
            self.log(
                "warning",
                "Brak pobranych wydawców — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )
        self.update_progress(0, 1, "Importowanie wydawców do bazy danych")
        self.log("info", "Importowanie wydawców do bazy danych")
        subtask_callback = self.create_subtask_progress("Importowanie wydawców")
        try:
            result = importer.importuj_wydawcow(callback=subtask_callback)
            if hasattr(self.session, "statistics") and isinstance(
                result, (int, float)
            ):
                stats = self.session.statistics
                stats.publishers_imported = int(result)
                stats.save()
            self.log("success", "Wydawcy zaimportowani pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się zaimportować wydawców")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono import wydawców")
        return {"publishers_imported": True, "error_count": len(self.errors)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_publisher_importer_split.py -v`
Expected: PASS (2 testy).

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/pbn_import/utils/publisher_import.py src/pbn_import/tests/test_publisher_importer_split.py
ruff check src/pbn_import/utils/publisher_import.py src/pbn_import/tests/test_publisher_importer_split.py
git add src/pbn_import/utils/publisher_import.py src/pbn_import/tests/test_publisher_importer_split.py
git commit -m "feat(pbn-import): PublisherImporter — split download/process

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: `AuthorImporter` — split download/process

**Files:**
- Modify: `src/pbn_import/utils/author_import.py`
- Test: `src/pbn_import/tests/test_author_importer_split.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# src/pbn_import/tests/test_author_importer_split.py
"""AuthorImporter: download woła pobierz, process woła integruj."""

import pytest
from model_bakery import baker

from pbn_import.utils import author_import


@pytest.fixture
def uczelnia(db):
    return baker.make("bpp.Uczelnia", pbn_uid_id="INST-1")


@pytest.fixture
def step(db, uczelnia):
    user = baker.make("auth.User")
    session = baker.make("pbn_import.ImportSession", user=user)
    return author_import.AuthorImporter(session, client=object(), uczelnia=uczelnia)


def test_download_calls_pobierz_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        author_import, "pobierz_ludzi_z_uczelni",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        author_import, "integruj_autorow_z_uczelni",
        lambda *a, **k: called.append("integruj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_calls_integruj_only(step, monkeypatch):
    called = []
    monkeypatch.setattr(
        author_import, "pobierz_ludzi_z_uczelni",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        author_import, "integruj_autorow_z_uczelni",
        lambda *a, **k: called.append("integruj"),
    )
    step.process()
    assert called == ["integruj"]


def test_download_skips_without_pbn_uid(db, monkeypatch):
    uczelnia = baker.make("bpp.Uczelnia", pbn_uid_id=None)
    user = baker.make("auth.User")
    session = baker.make("pbn_import.ImportSession", user=user)
    step = author_import.AuthorImporter(session, client=object(), uczelnia=uczelnia)
    called = []
    monkeypatch.setattr(
        author_import, "pobierz_ludzi_z_uczelni",
        lambda *a, **k: called.append("pobierz"),
    )
    result = step.download()
    assert called == []
    assert result["authors_imported"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_author_importer_split.py -v`
Expected: FAIL — brak metody `download`.

- [ ] **Step 3: Rewrite `author_import.py`**

```python
"""Author import utilities"""

from pbn_api.models import Scientist
from pbn_integrator.utils import integruj_autorow_z_uczelni, pobierz_ludzi_z_uczelni

from .base import ImportStepBase


class AuthorImporter(ImportStepBase):
    """Import authors from PBN"""

    step_name = "author_import"
    step_description = "Import autorów"

    def _resolve_uczelnia(self):
        """Zwróć uczelnię kontekstu importu lub None (z logiem) gdy brak pbn_uid."""
        uczelnia = self.uczelnia
        if not uczelnia or not uczelnia.pbn_uid_id:
            self.log(
                "warning",
                "Nie znaleziono Uczelni z PBN UID, pomijanie importu autorów",
            )
            return None
        return uczelnia

    def download(self):
        """Pobierz autorów uczelni z PBN do lustra."""
        uczelnia = self._resolve_uczelnia()
        if uczelnia is None:
            return {"authors_imported": False, "reason": "No Uczelnia PBN UID"}

        self.update_progress(0, 1, "Pobieranie autorów z PBN")
        self.log("info", f"Pobieranie autorów dla instytucji {uczelnia.pbn_uid_id}")
        subtask_callback = self.create_subtask_progress("Pobieranie autorów")
        try:
            pobierz_ludzi_z_uczelni(
                self.client, uczelnia.pbn_uid_id, callback=subtask_callback
            )
            self.log("success", "Autorzy pobrani pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać autorów")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono pobieranie autorów")
        return {"authors_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zintegruj autorów z lustra do BPP (z uczelnią)."""
        uczelnia = self._resolve_uczelnia()
        if uczelnia is None:
            return {"authors_imported": False, "reason": "No Uczelnia PBN UID"}

        if not Scientist.objects.exists():
            self.log(
                "warning",
                "Brak pobranych autorów — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )

        self.update_progress(0, 1, "Integrowanie autorów")
        self.log("info", "Integrating authors with university")
        integration_callback = self.create_subtask_progress(
            "Integrowanie autorów z uczelnią"
        )
        try:
            integruj_autorow_z_uczelni(
                self.client,
                uczelnia.pbn_uid_id,
                import_unexistent=True,
                callback=integration_callback,
            )
            self.clear_subtask_progress()
            if hasattr(self.session, "statistics"):
                from bpp.models import Autor

                stats = self.session.statistics
                stats.authors_imported = Autor.objects.filter(
                    pbn_uid_id__isnull=False
                ).count()
                stats.save()
            self.log("success", "Autorzy zintegrowani pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować autorów")
            if hasattr(self.session, "statistics"):
                self.session.statistics.authors_failed += 1
                self.session.statistics.save()
        self.update_progress(1, 1, "Zakończono import autorów")
        return {
            "authors_imported": True,
            "uczelnia_pbn_uid": uczelnia.pbn_uid_id,
            "error_count": len(self.errors),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_author_importer_split.py -v`
Expected: PASS (3 testy).

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/pbn_import/utils/author_import.py src/pbn_import/tests/test_author_importer_split.py
ruff check src/pbn_import/utils/author_import.py src/pbn_import/tests/test_author_importer_split.py
git add src/pbn_import/utils/author_import.py src/pbn_import/tests/test_author_importer_split.py
git commit -m "feat(pbn-import): AuthorImporter — split download/process

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 7: `PublicationImporter` — split download/process

`delete_existing` (kasowanie rekordów BPP) należy do fazy `process`.

**Files:**
- Modify: `src/pbn_import/utils/publication_import.py`
- Test: `src/pbn_import/tests/test_publication_importer_split.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# src/pbn_import/tests/test_publication_importer_split.py
"""PublicationImporter: rozdzielenie download (pobieranie) i process (import)."""

import pytest
from model_bakery import baker

from pbn_import.utils import publication_import
from pbn_import.utils.publication_import import PublicationImporter


@pytest.fixture
def uczelnia(db):
    return baker.make("bpp.Uczelnia", pbn_uid_id="INST-1")


@pytest.fixture
def session(db):
    user = baker.make("auth.User")
    return baker.make("pbn_import.ImportSession", user=user)


def _patch_setup(monkeypatch, importer_obj):
    """Pomiń realny setup uczelni/jednostki — zwróć uczelnię ze stepu."""
    monkeypatch.setattr(
        importer_obj, "_setup_uczelnia_and_jednostka",
        lambda *a, **k: importer_obj.uczelnia,
    )


def test_download_calls_only_download_helpers(session, uczelnia, monkeypatch):
    step = PublicationImporter(session, client=object(), uczelnia=uczelnia)
    _patch_setup(monkeypatch, step)
    called = []
    monkeypatch.setattr(
        step, "_download_publications",
        lambda *a, **k: called.append("dl") or None,
    )
    monkeypatch.setattr(
        step, "_download_publications_v2",
        lambda *a, **k: called.append("dl2") or None,
    )
    monkeypatch.setattr(
        step, "_import_publications",
        lambda *a, **k: called.append("import") or None,
    )
    step.download()
    assert called == ["dl", "dl2"]


def test_process_calls_only_import(session, uczelnia, monkeypatch):
    step = PublicationImporter(session, client=object(), uczelnia=uczelnia)
    _patch_setup(monkeypatch, step)
    called = []
    monkeypatch.setattr(
        step, "_download_publications",
        lambda *a, **k: called.append("dl") or None,
    )
    monkeypatch.setattr(
        step, "_import_publications",
        lambda *a, **k: called.append("import") or None,
    )
    step.process()
    assert called == ["import"]


def test_process_deletes_when_delete_existing(session, uczelnia, monkeypatch):
    step = PublicationImporter(
        session, client=object(), delete_existing=True, uczelnia=uczelnia
    )
    _patch_setup(monkeypatch, step)
    called = []
    monkeypatch.setattr(
        step, "_delete_existing_publications",
        lambda *a, **k: called.append("delete") or None,
    )
    monkeypatch.setattr(
        step, "_import_publications",
        lambda *a, **k: called.append("import") or None,
    )
    step.process()
    assert called == ["delete", "import"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_publication_importer_split.py -v`
Expected: FAIL — brak metody `download`.

- [ ] **Step 3: Refaktor `publication_import.py`**

Zastąp metodę `run()` (linie ~34–74) dwiema metodami. Pozostałe metody
prywatne (`_setup_uczelnia_and_jednostka`, `_delete_existing_publications`,
`_download_publications`, `_download_publications_v2`, `_import_publications`,
`_import_publications_with_cancellation`, `import_single_publication`)
ZOSTAJĄ bez zmian. Zmieniamy tylko sygnatury wewn. wywołań progresu na stałe
liczniki (każda faza liczy własne kroki).

```python
    def download(self):
        """Pobierz publikacje instytucji (v1 + v2) z PBN do lustra."""
        uczelnia = self._setup_uczelnia_and_jednostka()
        if uczelnia is None:
            return {"publications_imported": False, "reason": "No Uczelnia PBN UID"}

        result = self._download_publications(0, 2, uczelnia)
        if result:
            return result
        result = self._download_publications_v2(1, 2)
        if result:
            return result

        self.update_progress(2, 2, "Zakończono pobieranie publikacji")
        return {"publications_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Zaimportuj publikacje z lustra do BPP (opcjonalnie po skasowaniu)."""
        from pbn_api.models import Publication

        uczelnia = self._setup_uczelnia_and_jednostka()
        if uczelnia is None:
            return {"publications_imported": False, "reason": "No Uczelnia PBN UID"}

        if not Publication.objects.exists():
            self.log(
                "warning",
                "Brak pobranych publikacji — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )

        total_steps = 2 if self.delete_existing else 1
        current_step = 0
        if self.delete_existing:
            result = self._delete_existing_publications(current_step, total_steps)
            if result:
                return result
            current_step += 1

        result = self._import_publications(current_step, total_steps)
        if result:
            return result

        self.update_progress(total_steps, total_steps, "Zakończono import publikacji")
        return {
            "publications_imported": True,
            "default_jednostka": self.default_jednostka.nazwa,
            "error_count": len(self.errors),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_publication_importer_split.py src/pbn_import/tests/test_publication_import.py -v`
Expected: PASS (nowe + istniejące testy publikacji).

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/pbn_import/utils/publication_import.py src/pbn_import/tests/test_publication_importer_split.py
ruff check src/pbn_import/utils/publication_import.py src/pbn_import/tests/test_publication_importer_split.py
git add src/pbn_import/utils/publication_import.py src/pbn_import/tests/test_publication_importer_split.py
git commit -m "feat(pbn-import): PublicationImporter — split download/process

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 8: `StatementImporter` — split download/process

`_download_missing_publications` to dociąg sterowany integracją → faza `process`.

**Files:**
- Modify: `src/pbn_import/utils/statement_import.py`
- Test: `src/pbn_import/tests/test_statement_importer_split.py` (Create)

- [ ] **Step 1: Write the failing test**

```python
# src/pbn_import/tests/test_statement_importer_split.py
"""StatementImporter: download = pobierz oświadczenia, process = integracja."""

import pytest
from model_bakery import baker

from pbn_import.utils import statement_import
from pbn_import.utils.statement_import import StatementImporter


@pytest.fixture
def uczelnia(db):
    return baker.make("bpp.Uczelnia", pbn_uid_id="INST-1")


@pytest.fixture
def session(db):
    user = baker.make("auth.User")
    return baker.make("pbn_import.ImportSession", user=user)


def test_download_calls_only_pobierz_oswiadczenia(session, uczelnia, monkeypatch):
    step = StatementImporter(session, client=object(), uczelnia=uczelnia)
    called = []
    monkeypatch.setattr(
        statement_import, "pobierz_oswiadczenia_z_instytucji",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        statement_import, "integruj_oswiadczenia_z_instytucji",
        lambda *a, **k: called.append("integruj"),
    )
    step.download()
    assert called == ["pobierz"]


def test_process_integrates_without_redownloading_statements(
    session, uczelnia, monkeypatch
):
    step = StatementImporter(session, client=object(), uczelnia=uczelnia)
    called = []
    monkeypatch.setattr(
        statement_import, "pobierz_oswiadczenia_z_instytucji",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        statement_import, "integruj_oswiadczenia_z_instytucji",
        lambda *a, **k: called.append("integruj"),
    )
    monkeypatch.setattr(
        step.publication_importer, "_setup_uczelnia_and_jednostka",
        lambda *a, **k: uczelnia,
    )
    step.publication_importer.default_jednostka = baker.make("bpp.Jednostka")
    monkeypatch.setattr(
        step, "_download_missing_publications", lambda *a, **k: None
    )
    step.process()
    assert called == ["integruj"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_statement_importer_split.py -v`
Expected: FAIL — brak metody `download`.

- [ ] **Step 3: Refaktor `statement_import.py`**

Zastąp `run()` (linie ~90–174) dwiema metodami. `_create_inconsistency_callback`,
`_download_missing_publications` ZOSTAJĄ bez zmian.

```python
    def download(self):
        """Pobierz oświadczenia instytucji z PBN do lustra."""
        self.update_progress(0, 1, "Pobieranie oświadczeń z PBN")
        self.log("info", "Pobieranie oświadczeń z instytucji")
        subtask_callback = self.create_subtask_progress("Pobieranie oświadczeń")
        try:
            pobierz_oswiadczenia_z_instytucji(self.client, callback=subtask_callback)
            self.log("success", "Oświadczenia pobrane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się pobrać oświadczeń")
        finally:
            self.clear_subtask_progress()
        self.update_progress(1, 1, "Zakończono pobieranie oświadczeń")
        return {"statements_downloaded": True, "error_count": len(self.errors)}

    def process(self):
        """Dociągnij brakujące publikacje i zintegruj oświadczenia."""
        if not OswiadczenieInstytucji.objects.exists():
            self.log(
                "warning",
                "Brak pobranych oświadczeń — przetwarzam 0. Uruchom fazę "
                "pobierania, jeśli to nie zamierzone.",
            )

        uczelnia = self.publication_importer._setup_uczelnia_and_jednostka()
        if not uczelnia:
            self.log(
                "warning", "Brak Uczelni z PBN UID, pomijanie integracji oświadczeń"
            )
            return {"statements_imported": False, "reason": "No Uczelnia PBN UID"}

        default_jednostka = self.publication_importer.default_jednostka

        self.update_progress(0, 2, "Pobieranie brakujących publikacji")
        result = self._download_missing_publications(default_jednostka)
        if result:
            self.log(
                "info",
                f"Pobrano {result['downloaded']} brakujących publikacji "
                f"({result['failed']} błędów)",
            )

        self.update_progress(1, 2, "Integrowanie oświadczeń")
        self.log("info", "Integrowanie oświadczeń")
        try:
            inconsistency_callback = self._create_inconsistency_callback()
            integruj_oswiadczenia_z_instytucji(
                missing_publication_callback=None,
                inconsistency_callback=inconsistency_callback,
                default_jednostka=default_jednostka,
                uczelnia=uczelnia,
            )
            inconsistency_count = self.session.inconsistencies.count()
            if inconsistency_count > 0:
                self.log(
                    "warning",
                    f"Znaleziono {inconsistency_count} nieścisłości podczas "
                    f"integracji oświadczeń",
                )
            if hasattr(self.session, "statistics"):
                stats = self.session.statistics
                stats.statements_imported += 1
                stats.save()
            self.log("success", "Oświadczenia zintegrowane pomyślnie")
        except Exception as e:
            self.handle_error(e, "Nie udało się zintegrować oświadczeń")

        self.update_progress(2, 2, "Zakończono import oświadczeń")
        return {"statements_imported": True, "error_count": len(self.errors)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_statement_importer_split.py -v`
Expected: PASS (2 testy).

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/pbn_import/utils/statement_import.py src/pbn_import/tests/test_statement_importer_split.py
ruff check src/pbn_import/utils/statement_import.py src/pbn_import/tests/test_statement_importer_split.py
git add src/pbn_import/utils/statement_import.py src/pbn_import/tests/test_statement_importer_split.py
git commit -m "feat(pbn-import): StatementImporter — split download/process

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 9: Model faz w `step_definitions.py` + resolver zgodności wstecznej

Przebudowa `ALL_STEP_DEFINITIONS` na fazy i przepisanie helperów. Po tym tasku
`get_step_definitions` zwraca **płaską listę faz z `method` i `result_key`**.

**Files:**
- Modify: `src/pbn_import/utils/step_definitions.py`
- Test: `src/pbn_import/tests/test_step_definitions.py` (rozszerz istniejący)

- [ ] **Step 1: Write the failing tests** (dopisz do `test_step_definitions.py`)

```python
# --- dopisz na końcu src/pbn_import/tests/test_step_definitions.py ---
from pbn_import.utils.step_definitions import (
    get_all_disable_keys,
    get_form_steps,
    get_step_definitions,
)


def test_split_step_emits_two_phases_in_order():
    # Wszystko włączone (pusty config)
    defs = get_step_definitions({})
    keys = [d["result_key"] for d in defs]
    # download źródeł poprzedza process źródeł
    assert keys.index("source_import:download") < keys.index("source_import:process")
    # konferencje też rozdzielone
    assert "conference_import:download" in keys
    assert "conference_import:process" in keys


def test_each_phase_carries_method():
    defs = get_step_definitions({})
    by_key = {d["result_key"]: d for d in defs}
    assert by_key["source_import:download"]["method"] == "download"
    assert by_key["source_import:process"]["method"] == "process"
    # niepodzielny krok ma method "run"
    assert by_key["fee_import"]["method"] == "run"


def test_granular_disable_skips_one_phase_only():
    defs = get_step_definitions({"disable_zrodla_download": True})
    keys = [d["result_key"] for d in defs]
    assert "source_import:download" not in keys
    assert "source_import:process" in keys


def test_legacy_key_disables_both_phases():
    defs = get_step_definitions({"disable_zrodla": True})
    keys = [d["result_key"] for d in defs]
    assert "source_import:download" not in keys
    assert "source_import:process" not in keys


def test_granular_overrides_legacy():
    # legacy mówi "wyłącz oba", granular mówi "włącz process"
    defs = get_step_definitions(
        {"disable_zrodla": True, "disable_zrodla_process": False}
    )
    keys = [d["result_key"] for d in defs]
    assert "source_import:process" in keys
    assert "source_import:download" not in keys


def test_get_all_disable_keys_is_granular():
    mapping = get_all_disable_keys()
    assert mapping["zrodla_download"] == "disable_zrodla_download"
    assert mapping["zrodla_process"] == "disable_zrodla_process"
    # niepodzielny krok zachowuje stary klucz
    assert mapping["oplaty"] == "disable_oplaty"


def test_get_form_steps_returns_two_column_rows():
    rows = get_form_steps()
    by_name = {r["name"]: r for r in rows}
    zrodla = by_name["source_import"]
    assert zrodla["download"]["form_field"] == "zrodla_download"
    assert zrodla["process"]["form_field"] == "zrodla_process"
    # punktacja źródeł: tylko process
    punktacja = by_name["source_scoring_import"]
    assert punktacja["download"] is None
    assert punktacja["process"] is not None
    # opłaty: niepodzielne (single)
    oplaty = by_name["fee_import"]
    assert oplaty["single"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_step_definitions.py -v`
Expected: FAIL — `result_key`/`method` brak, `get_form_steps` ma inny kształt.

- [ ] **Step 3: Przepisz `step_definitions.py`**

Zastąp całą zawartość pliku poniższą (importy klas bez zmian; dochodzi
`integruj`-aware model faz). Zachowaj `STEP_ICONS`, `get_command_steps`,
`get_icon_for_step`, `_get_step_args` — uzupełnione o fazy.

```python
"""PBN import step definitions and configuration (model faz)."""

from .author_import import AuthorImporter
from .conference_import import ConferenceImporter
from .fee_import import FeeImporter
from .initial_setup import InitialSetup
from .institution_import import InstitutionImporter
from .publication_import import PublicationImporter
from .publisher_import import PublisherImporter
from .source_import import SourceImporter
from .source_scoring_import import SourceScoringImporter
from .statement_import import StatementImporter


def _split(entity, label):
    """Zbuduj dwie fazy (download/process) dla rozdzielanej encji."""
    return [
        {
            "phase": "download",
            "method": "download",
            "form_field": f"{entity}_download",
            "disable_key": f"disable_{entity}_download",
            "display": f"{label} — pobieranie",
            "column": "download",
            "legacy_key": f"disable_{entity}",
        },
        {
            "phase": "process",
            "method": "process",
            "form_field": f"{entity}_process",
            "disable_key": f"disable_{entity}_process",
            "display": f"{label} — przetwarzanie",
            "column": "process",
            "legacy_key": f"disable_{entity}",
        },
    ]


def _single(form_field, label, column):
    """Zbuduj pojedynczą fazę dla kroku niepodzielnego/jednofazowego."""
    return [
        {
            "phase": "single",
            "method": "run",
            "form_field": form_field,
            "disable_key": f"disable_{form_field}",
            "display": label,
            "column": column,
            "legacy_key": None,
        }
    ]


# Pojedyncze źródło prawdy o krokach importu.
ALL_STEP_DEFINITIONS = [
    {
        "name": "initial_setup",
        "display": "Konfiguracja początkowa",
        "class": InitialSetup,
        "icon": "fi-wrench",
        "required": True,
        "show_in_form": True,
        "phases": _single("initial", "Konfiguracja początkowa", "both"),
    },
    {
        "name": "institution_setup",
        "display": "Konfiguracja jednostek",
        "class": InstitutionImporter,
        "icon": "fi-home",
        "required": True,
        "show_in_form": True,
        "phases": _single("institutions", "Konfiguracja jednostek", "both"),
    },
    {
        "name": "source_import",
        "display": "Źródła",
        "class": SourceImporter,
        "icon": "fi-book",
        "required": False,
        "show_in_form": True,
        "phases": _split("zrodla", "Źródła"),
    },
    {
        "name": "source_scoring_import",
        "display": "Punktacja i dyscypliny źródeł",
        "class": SourceScoringImporter,
        "icon": "fi-graph-bar",
        "required": False,
        "show_in_form": True,
        "phases": _single(
            "punktacja_zrodel", "Synchronizacja punktów i dyscyplin źródeł", "process"
        ),
    },
    {
        "name": "publisher_import",
        "display": "Wydawcy",
        "class": PublisherImporter,
        "icon": "fi-page-multiple",
        "required": False,
        "show_in_form": True,
        "phases": _split("wydawcy", "Wydawcy"),
    },
    {
        "name": "conference_import",
        "display": "Konferencje",
        "class": ConferenceImporter,
        "icon": "fi-calendar",
        "required": False,
        "show_in_form": True,
        "phases": _split("konferencje", "Konferencje"),
    },
    {
        "name": "author_import",
        "display": "Autorzy",
        "class": AuthorImporter,
        "icon": "fi-torsos-all",
        "required": False,
        "show_in_form": True,
        "phases": _split("autorzy", "Autorzy"),
    },
    {
        "name": "publication_import",
        "display": "Publikacje",
        "class": PublicationImporter,
        "icon": "fi-page-copy",
        "required": False,
        "show_in_form": True,
        "phases": _split("publikacje", "Publikacje"),
    },
    {
        "name": "statement_import",
        "display": "Oświadczenia",
        "class": StatementImporter,
        "icon": "fi-clipboard-pencil",
        "required": False,
        "show_in_form": True,
        "phases": _split("oswiadczenia", "Oświadczenia"),
    },
    {
        "name": "fee_import",
        "display": "Opłaty",
        "class": FeeImporter,
        "icon": "fi-dollar",
        "required": False,
        "show_in_form": True,
        "phases": _single("oplaty", "Import opłat", "both"),
    },
]

STEP_ICONS = {step["name"]: step["icon"] for step in ALL_STEP_DEFINITIONS}


def _iter_phases():
    """Iteruj (step_def, phase_def) dla wszystkich kroków pokazywanych w formie."""
    for step in ALL_STEP_DEFINITIONS:
        if not step.get("show_in_form", True):
            continue
        for phase in step["phases"]:
            yield step, phase


def _phase_disabled(config, phase):
    """Czy faza wyłączona? granular > legacy > domyślnie włączona."""
    if phase["disable_key"] in config:
        return bool(config[phase["disable_key"]])
    legacy = phase.get("legacy_key")
    if legacy and legacy in config:
        return bool(config[legacy])
    return False


def get_form_steps():
    """Wiersze formularza: encja + komórki download/process/single."""
    rows = []
    for step in ALL_STEP_DEFINITIONS:
        if not step.get("show_in_form", True):
            continue
        row = {
            "name": step["name"],
            "display": step["display"],
            "icon": step["icon"],
            "required": step["required"],
            "download": None,
            "process": None,
            "single": None,
        }
        for phase in step["phases"]:
            cell = {"form_field": phase["form_field"], "display": phase["display"]}
            if phase["phase"] == "single":
                row["single"] = cell
            else:
                row[phase["phase"]] = cell
        rows.append(row)
    return rows


def get_command_steps():
    """Pary (form_field, display) dla CLI — jedna na fazę."""
    return [(phase["form_field"], phase["display"]) for _, phase in _iter_phases()]


def get_legacy_command_aliases():
    """Mapa legacy form_field → lista granularnych disable_key (dla CLI alias)."""
    aliases = {}
    for step in ALL_STEP_DEFINITIONS:
        phases = step["phases"]
        if len(phases) == 2:  # krok rozdzielany
            entity = phases[0]["form_field"].rsplit("_", 1)[0]
            aliases[entity] = [p["disable_key"] for p in phases]
    return aliases


def get_all_disable_keys():
    """Mapa form_field → disable_key (granularna, wszystkie fazy)."""
    return {phase["form_field"]: phase["disable_key"] for _, phase in _iter_phases()}


def _get_step_args(step_name, config):
    """Dynamiczne argumenty konstruktora kroku na podstawie config."""
    if step_name == "institution_setup":
        return {
            "wydzial_domyslny": config.get("wydzial_domyslny", "Wydział Domyślny"),
            "wydzial_domyslny_skrot": config.get("wydzial_domyslny_skrot"),
        }
    elif step_name == "publication_import":
        return {"delete_existing": config.get("delete_existing", False)}
    return {}


def get_step_definitions(config):
    """Płaska, uporządkowana lista faz do wykonania (po odfiltrowaniu)."""
    result = []
    for step in ALL_STEP_DEFINITIONS:
        for phase in step["phases"]:
            if _phase_disabled(config, phase):
                continue
            phase_name = phase["phase"]
            result_key = (
                step["name"]
                if phase_name == "single"
                else f"{step['name']}:{phase_name}"
            )
            result.append(
                {
                    "name": step["name"],
                    "phase": phase_name,
                    "display": phase["display"],
                    "class": step["class"],
                    "method": phase["method"],
                    "required": step["required"],
                    "args": _get_step_args(step["name"], config),
                    "result_key": result_key,
                }
            )
    return result


def get_icon_for_step(step_name):
    """Zwróć klasę ikony Foundation dla kroku."""
    return STEP_ICONS.get(step_name, "fi-download")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_step_definitions.py -v`
Expected: PASS (istniejące + 7 nowych).

Jeśli istniejące testy w tym pliku zakładały stary kształt `get_form_steps`
(płaska lista z `form_field`), zaktualizuj je do nowego kontraktu (wiersze
z `download`/`process`/`single`).

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/pbn_import/utils/step_definitions.py src/pbn_import/tests/test_step_definitions.py
ruff check src/pbn_import/utils/step_definitions.py src/pbn_import/tests/test_step_definitions.py
git add src/pbn_import/utils/step_definitions.py src/pbn_import/tests/test_step_definitions.py
git commit -m "feat(pbn-import): model faz w step_definitions + resolver zgodnosci wstecznej

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 10: `ImportManager` — wykonanie per faza

`get_step_definitions` zwraca teraz fazy; manager woła `step(method=…)` i
kluczuje `results` po `result_key`.

**Files:**
- Modify: `src/pbn_import/utils/import_manager.py`
- Test: `src/pbn_import/tests/test_import_manager.py` (rozszerz)

- [ ] **Step 1: Write the failing test** (dopisz)

```python
# --- dopisz do src/pbn_import/tests/test_import_manager.py ---
def test_manager_runs_only_download_phase(db, monkeypatch):
    from model_bakery import baker

    from pbn_import.utils import source_import
    from pbn_import.utils.import_manager import ImportManager

    called = []
    monkeypatch.setattr(
        source_import, "pobierz_zrodla_mnisw",
        lambda *a, **k: called.append("pobierz"),
    )
    monkeypatch.setattr(
        source_import.importer, "importuj_zrodla",
        lambda *a, **k: called.append("importuj"),
    )

    user = baker.make("auth.User")
    session = baker.make("pbn_import.ImportSession", user=user)

    class _Client:
        def get_languages(self):
            return []

    manager = ImportManager(
        session=session,
        client=_Client(),
        config={"disable_zrodla_process": True},  # tylko pobieranie źródeł
    )
    # Zostaw tylko fazę download źródeł
    manager.steps = [
        s for s in manager.steps if s["result_key"] == "source_import:download"
    ]
    manager.run()
    assert "pobierz" in called
    assert "importuj" not in called


def test_results_keyed_by_phase(db, monkeypatch):
    from pbn_import.utils.step_definitions import get_step_definitions

    defs = get_step_definitions({})
    keys = [d["result_key"] for d in defs]
    # klucze unikalne (brak kolizji download/process tej samej encji)
    assert len(keys) == len(set(keys))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_import_manager.py -v`
Expected: FAIL — `_execute_step` nie przekazuje `method`; `results` po `name`.

- [ ] **Step 3: Zmień `_execute_step` w `import_manager.py`**

W metodzie `_execute_step` (linie ~232–259) zmień wywołanie kroku i klucz
wyniku:

```python
    def _execute_step(
        self, idx, step_config, results, has_errors, critical_error, tb_string
    ):
        """Execute a single import step (faza)."""
        step_class = step_config["class"]
        step = step_class(
            session=self.session,
            client=self.client,
            uczelnia=self.uczelnia,
            **step_config["args"],
        )

        logger.info(
            f">>> Uruchamianie etapu {idx + 1}/{len(self.steps)}: "
            f"{step_config['display']}"
        )

        try:
            result = step(method=step_config["method"])
            results[step_config["result_key"]] = result

            if step_config["name"] == "initial_setup":
                self._refresh_pbn_client_after_setup()

            return has_errors, critical_error, tb_string, False, None

        except CancelledException:
            ImportLog.objects.create(
                session=self.session,
                level="warning",
                step=step_config["display"],
                message="Import został anulowany podczas wykonywania kroku",
            )
            logger.warning(
                f"Import {self.session.id} anulowany podczas kroku "
                f"{step_config['result_key']}"
            )
            return (
                has_errors,
                critical_error,
                tb_string,
                False,
                {"success": False, "cancelled": True, "results": results},
            )

        except Exception as e:
            return self._handle_step_error(
                e, step_config, results, has_errors, critical_error, tb_string
            )
```

W `_handle_step_error` (linie ~191–230) zmień zapisy do `results` z
`step_config["name"]` na `step_config["result_key"]` (3 wystąpienia).

W `_should_skip_step` (linie ~175–189) zmień zapis wyniku z
`results[step_config["name"]]` na `results[step_config["result_key"]]`
(zachowaj warunek po `step_config["name"]`, bo dotyczy on initial/institution).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_import_manager.py -v`
Expected: PASS.

- [ ] **Step 5: Regresja — pełny pakiet kroków/managera**

Run: `uv run pytest src/pbn_import/tests/test_import_manager.py src/pbn_import/tests/test_tasks.py src/pbn_import/tests/test_step_definitions.py -v`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
ruff format src/pbn_import/utils/import_manager.py src/pbn_import/tests/test_import_manager.py
ruff check src/pbn_import/utils/import_manager.py src/pbn_import/tests/test_import_manager.py
git add src/pbn_import/utils/import_manager.py src/pbn_import/tests/test_import_manager.py
git commit -m "feat(pbn-import): ImportManager wykonuje fazy per-metoda, results po result_key

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 11: CLI `pbn_import` — flagi granularne + legacy alias

**Files:**
- Modify: `src/pbn_import/management/commands/pbn_import.py`
- Test: `src/pbn_import/tests/test_command_pbn_import.py` (rozszerz)

- [ ] **Step 1: Write the failing tests** (dopisz)

```python
# --- dopisz do src/pbn_import/tests/test_command_pbn_import.py ---
from pbn_import.management.commands.pbn_import import build_config_from_options


def _base_options(**over):
    opts = {
        "app_id": None,
        "base_url": None,
        "delete_existing": False,
        "wydzial_domyslny": "X",
        "wydzial_domyslny_skrot": None,
    }
    opts.update(over)
    return opts


def test_granular_flag_disables_one_phase():
    cfg = build_config_from_options(_base_options(disable_zrodla_download=True))
    assert cfg["disable_zrodla_download"] is True
    assert cfg.get("disable_zrodla_process", False) is False


def test_legacy_flag_disables_both_phases():
    cfg = build_config_from_options(_base_options(disable_zrodla=True))
    assert cfg["disable_zrodla_download"] is True
    assert cfg["disable_zrodla_process"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_command_pbn_import.py -v`
Expected: FAIL — `build_config_from_options` nie zna legacy aliasów / granularnych kluczy.

- [ ] **Step 3: Zmień command**

W `pbn_import.py` zaktualizuj importy i logikę. `IMPORT_STEPS` = granularne
fazy (`get_command_steps`). Dodaj legacy flagi i ich obsługę.

W nagłówku:

```python
from pbn_import.utils.step_definitions import (
    get_command_steps,
    get_legacy_command_aliases,
)

IMPORT_STEPS = get_command_steps()
LEGACY_ALIASES = get_legacy_command_aliases()
```

`build_config_from_options` — zamień ciało budujące disable na granularne +
legacy:

```python
def build_config_from_options(options):
    """Zbuduj config sesji z opcji CLI (fazy granularne + legacy aliasy)."""
    config = {
        "app_id": options.get("app_id"),
        "base_url": options.get("base_url"),
        "delete_existing": options.get("delete_existing", False),
        "wydzial_domyslny": options.get("wydzial_domyslny"),
        "wydzial_domyslny_skrot": options.get("wydzial_domyslny_skrot"),
    }

    # Granularne flagi: --disable-{form_field}
    for form_field, _label in IMPORT_STEPS:
        config[f"disable_{form_field}"] = options.get(f"disable_{form_field}", False)

    # Legacy aliasy: --disable-{encja} wyłącza obie fazy encji
    for entity, disable_keys in LEGACY_ALIASES.items():
        if options.get(f"disable_{entity}"):
            for dk in disable_keys:
                config[dk] = True

    return config
```

W `add_arguments` — zostaw pętlę po `IMPORT_STEPS` (granularne flagi) i DODAJ
legacy flagi:

```python
        # Granularne flagi faz
        for key, label in IMPORT_STEPS:
            parser.add_argument(
                f"--disable-{key}",
                action="store_true",
                help=f"Pomiń: {label}",
            )
        # Legacy aliasy (wyłączają obie fazy encji) — zgodność wsteczna
        for entity in LEGACY_ALIASES:
            parser.add_argument(
                f"--disable-{entity}",
                action="store_true",
                help=f"Pomiń obie fazy: {entity}",
            )
```

W `run_interactive` — `choices` już iterują po `IMPORT_STEPS` (teraz fazy),
więc menu pokaże „Źródła — pobieranie" / „Źródła — przetwarzanie". Bez zmian
strukturalnych, ale upewnij się, że pętle po `IMPORT_STEPS` używają
`f"disable_{key}"` (klucz = granularny form_field) — tak jak teraz.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_command_pbn_import.py -v`
Expected: PASS.

- [ ] **Step 5: Smoke — komenda buduje parser bez błędu**

Run: `uv run python src/manage.py pbn_import --help`
Expected: lista flag zawiera `--disable-zrodla-download`, `--disable-zrodla-process`
oraz legacy `--disable-zrodla`.

- [ ] **Step 6: Lint + commit**

```bash
ruff format src/pbn_import/management/commands/pbn_import.py src/pbn_import/tests/test_command_pbn_import.py
ruff check src/pbn_import/management/commands/pbn_import.py src/pbn_import/tests/test_command_pbn_import.py
git add src/pbn_import/management/commands/pbn_import.py src/pbn_import/tests/test_command_pbn_import.py
git commit -m "feat(pbn-import): CLI — granularne flagi faz + legacy aliasy

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Presety — klucze granularne

`ImportPresetsView` musi używać kluczy granularnych, bo resolver preferuje je
nad legacy (inaczej `sources_only` zostawiłby źródła wyłączone).

**Files:**
- Modify: `src/pbn_import/views.py` (`ImportPresetsView`)
- Test: `src/pbn_import/tests/test_views_dashboard.py` (rozszerz — lub nowy
  `test_presets.py`)

- [ ] **Step 1: Write the failing test**

```python
# --- dopisz do src/pbn_import/tests/test_views_dashboard.py ---
import json as _json


def test_presets_sources_only_enables_both_source_phases(client, admin_user):
    client.force_login(admin_user)
    resp = client.get("/pbn_import/presets/")  # dostosuj URL do urls.py
    assert resp.status_code == 200
    presets = _json.loads(resp.content)["presets"]
    sources_only = next(p for p in presets if p["id"] == "sources_only")
    cfg = sources_only["config"]
    # źródła (obie fazy) włączone
    assert cfg.get("disable_zrodla_download", False) is False
    assert cfg.get("disable_zrodla_process", False) is False
    # a np. wydawcy (obie fazy) wyłączone
    assert cfg["disable_wydawcy_download"] is True
    assert cfg["disable_wydawcy_process"] is True
```

Uwaga: sprawdź realny URL presetów w `src/pbn_import/urls.py` (nazwa route
`presets`) i podstaw poprawną ścieżkę / `reverse("pbn_import:presets")`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_import/tests/test_views_dashboard.py -k presets -v`
Expected: FAIL — preset wciąż na legacy `disable_zrodla`.

- [ ] **Step 3: Zaktualizuj `ImportPresetsView`**

Zastąp słowniki `config` w presetach kluczami granularnymi. `all_disabled`
zbudowane z `get_all_disable_keys()` jest już granularne, więc wystarczy
nadpisać granularne klucze.

```python
        presets = [
            {
                "id": "full",
                "name": "Wszystko",
                "description": "Importuje wszystkie dane z PBN",
                "icon": "fi-download",
                "config": {},  # puste = wszystko włączone
            },
            {
                "id": "update",
                "name": "Aktualizacja",
                "description": "Aktualizuje autorów, publikacje, oświadczenia i opłaty",
                "icon": "fi-refresh",
                "config": {
                    "disable_initial": True,
                    "disable_institutions": True,
                    "disable_zrodla_download": True,
                    "disable_zrodla_process": True,
                    "disable_punktacja_zrodel": True,
                    "disable_wydawcy_download": True,
                    "disable_wydawcy_process": True,
                    "disable_konferencje_download": True,
                    "disable_konferencje_process": True,
                    # autorzy, publikacje, oswiadczenia, oplaty pozostają włączone
                    "delete_existing": False,
                },
            },
            {
                "id": "sources_only",
                "name": "Tylko źródła",
                "description": "Importuje i aktualizuje punktację źródeł",
                "icon": "fi-book",
                "config": {
                    **all_disabled,
                    "disable_zrodla_download": False,
                    "disable_zrodla_process": False,
                    "disable_punktacja_zrodel": False,
                    "delete_existing": False,
                },
            },
        ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_import/tests/test_views_dashboard.py -k presets -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
ruff format src/pbn_import/views.py src/pbn_import/tests/test_views_dashboard.py
ruff check src/pbn_import/views.py src/pbn_import/tests/test_views_dashboard.py
git add src/pbn_import/views.py src/pbn_import/tests/test_views_dashboard.py
git commit -m "feat(pbn-import): presety na kluczach granularnych faz

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 13: Formularz dwukolumnowy (dashboard.html + JS)

**Files:**
- Modify: `src/pbn_import/templates/pbn_import/dashboard.html`
- Test: ręczny smoke (frontend) + istniejący `test_views_dashboard.py`

- [ ] **Step 1: Zamień blok checkboxów na tabelę**

Zastąp blok (linie ~130–141, `<h4>Dane do importu</h4>` + pętla
`{% for step in import_steps %}`) poniższym. Każda linia komentarza Django
ma własne `{# #}`.

```django
            <h4>Dane do importu</h4>

            {# Tabela: wiersz = encja, kolumny = Pobieranie / Przetwarzanie #}
            <table class="pbn-import__steps-table">
                <thead>
                    <tr>
                        <th>Etap</th>
                        <th>Pobieranie</th>
                        <th>Przetwarzanie</th>
                    </tr>
                </thead>
                <tbody>
                    {% for step in import_steps %}
                    <tr>
                        <td>
                            <span class="{{ step.icon }}"></span> {{ step.display }}
                            {% if step.required %}<small class="text-muted">(wymagane)</small>{% endif %}
                        </td>
                        {% if step.single %}
                        {# Krok niepodzielny — jeden checkbox na obie kolumny #}
                        <td colspan="2">
                            <label>
                                <input type="checkbox" name="{{ step.single.form_field }}" checked>
                                {{ step.single.display }}
                            </label>
                        </td>
                        {% else %}
                        <td>
                            {% if step.download %}
                            <label>
                                <input type="checkbox" name="{{ step.download.form_field }}" checked>
                            </label>
                            {% else %}—{% endif %}
                        </td>
                        <td>
                            {% if step.process %}
                            <label>
                                <input type="checkbox" name="{{ step.process.form_field }}" checked>
                            </label>
                            {% else %}—{% endif %}
                        </td>
                        {% endif %}
                    </tr>
                    {% endfor %}
                </tbody>
            </table>

            {# Pole ukryte — nigdy nie pokazujemy opcji kasowania #}
            <input type="hidden" name="delete_existing" value="">
```

- [ ] **Step 2: Rozszerz `applyPresetConfig` o fallback legacy**

W funkcji `applyPresetConfig` (linie ~361–369) zamień blok `disable_`:

```javascript
        if (key.startsWith('disable_')) {
            const fieldName = key.replace('disable_', '');
            const input = form.querySelector(`[name="${fieldName}"]`);
            if (input && input.type === 'checkbox') {
                input.checked = !config[key];
            } else {
                // Legacy: disable_<encja> dotyczy obu faz encji
                ['_download', '_process'].forEach(suffix => {
                    const phaseInput = form.querySelector(`[name="${fieldName}${suffix}"]`);
                    if (phaseInput && phaseInput.type === 'checkbox') {
                        phaseInput.checked = !config[key];
                    }
                });
            }
        } else if (key === 'delete_existing') {
```

- [ ] **Step 3: Zbuduj frontend i odpal smoke**

```bash
make assets
uv run pytest src/pbn_import/tests/test_views_dashboard.py -v
```
Expected: testy dashboard PASS (kontekst `import_steps` to teraz wiersze).
Jeśli test asercjonował stary kształt, zaktualizuj go do nowych pól wiersza.

- [ ] **Step 4: Ręczny podgląd (zalecane)**

```bash
uv run run-site run --no-browser --no-celery
```
Otwórz dashboard importu PBN, kliknij „nowy import" — sprawdź tabelę
dwukolumnową; przełącz presety i zweryfikuj zaznaczanie checkboxów.

- [ ] **Step 5: Lint + commit**

```bash
git add src/pbn_import/templates/pbn_import/dashboard.html
git commit -m "feat(pbn-import): dwukolumnowy formularz importu (pobieranie/przetwarzanie)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 14: Styl tabeli (SCSS, opcjonalny ale zalecany)

**Files:**
- Modify: odpowiedni plik SCSS importu (znajdź:
  `grep -rl "pbn-import__" src/bpp/static --include=*.scss`)

- [ ] **Step 1: Dodaj minimalny styl (bez nadpisywania gridu Foundation)**

```scss
.pbn-import__steps-table {
    width: 100%;

    th, td {
        text-align: left;
        vertical-align: middle;
    }

    th:nth-child(2), th:nth-child(3),
    td:nth-child(2), td:nth-child(3) {
        text-align: center;
        width: 7rem;
    }

    label {
        margin: 0;
    }
}
```

- [ ] **Step 2: Zbuduj CSS**

```bash
grunt build
```

- [ ] **Step 3: Commit**

```bash
git add src/bpp/static
git commit -m "style(pbn-import): tabela kroków importu — wyrównanie kolumn faz

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Task 15: Regresja całości + sprzątanie wyświetlania wyników

`result_key` zmienił klucze w `results`; sprawdź konsumentów (`_display_results`
w CLI iteruje po `results.items()` — działa generycznie, ale klucze są teraz
`name:phase`). Upewnij się, że nic nie zakłada starych kluczy.

**Files:**
- Sprawdź: `src/pbn_import/management/commands/pbn_import.py` (`_display_results`)
- Sprawdź: `src/pbn_import/views.py`, `consumers.py`, szablony progresu

- [ ] **Step 1: Wyszukaj twarde odwołania do starych kluczy results**

```bash
grep -rnE "results\[|\.get\(\"source_import\"|\.get\('source_import'" src/pbn_import
```
Expected: brak miejsc zakładających `results["source_import"]` itp. Jeśli są —
zaktualizuj do `result_key` (`source_import:download`/`:process`).

- [ ] **Step 2: Pełny pakiet pbn_import + pbn_integrator**

Run:
```bash
uv run pytest src/pbn_import/ src/pbn_integrator/tests/test_integruj_konferencje.py -v
```
Expected: PASS w całości.

- [ ] **Step 3: Lint changed-files względem bazy**

```bash
git fetch origin
ruff check $(git diff --name-only origin/feature/multi-hosted-config...HEAD -- '*.py')
ruff format --check $(git diff --name-only origin/feature/multi-hosted-config...HEAD -- '*.py')
```
Expected: brak błędów.

- [ ] **Step 4: Commit (jeśli były poprawki)**

```bash
git add -A
git commit -m "chore(pbn-import): regresja faz — spójność kluczy results

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

- [ ] **Step 5: Szersza regresja (zalecane, do 10 min)**

Run: `make tests-without-playwright`
Expected: PASS. Przy błędach środowiskowych (Docker) — napraw warunki wstępne,
nie pomijaj.

---

## Mapa pokrycia specyfikacji

- Spec §4.2 (metody faz) → Task 1.
- Spec §5 (integruj_konferencje) → Task 2; ConferenceImporter §5.3 → Task 3.
- Spec §2.3 / §4.2 (6 splitów) → Tasks 3–8.
- Spec §4.1, §4.6 (model faz + resolver) → Task 9.
- Spec §4.3 (manager per faza, unikalne results) → Task 10.
- Spec §4.5 (CLI granular + legacy) → Task 11.
- Spec §4.4 (presety granularne) → Task 12; formularz dwukolumnowy + JS → Task 13–14.
- Spec §4.7 (miękkie ostrzeżenie) → Tasks 3–8 (każdy `process()`).
- Spec §8 (ryzyka: result_key, abbreviation, setup w obu fazach) → Tasks 10, 2, 6/7.
- Zgodność wsteczna (stare presety/CLI/sesje) → Tasks 9, 11, 12, 13.
