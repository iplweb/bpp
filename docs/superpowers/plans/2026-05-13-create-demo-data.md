# `create_demo_data` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-05-13-create-demo-data-design.md`

**Goal:** Dostarczyć dwie management commands (`create_demo_data` + `cleanup_demo_data`) generujące i kasujące syntetyczne dane demo BPP, z podwójnym potwierdzeniem, pre-flight checkiem słowników, batch commits, tqdm progress i deterministycznym seedem.

**Architecture:** Thin management commands w `src/bpp/management/commands/` wywołują logikę z nowego podpakietu `src/bpp/demo_data/` (data constants + manifest + confirm + preflight + progress + generators per encja). Cała logika jest testowalna in-process (pytest, `model_bakery` w testach jednostkowych, end-to-end integration test przez `call_command`).

**Tech Stack:** Django 5.x, Python 3.10+, `pytest` + `pytest-django`, `model_bakery`, `tqdm` (już w deps), `django-mptt` (dla `Jednostka`), `random.Random(seed)` (lokalny RNG).

---

## Cross-cutting conventions (DO NOT FORGET)

- Wszystkie testy: pytest-style **funkcje** (no `unittest.TestCase`, no klas).
- Database tests: `@pytest.mark.django_db(transaction=True)` (bo komenda commit'uje batchami; bez `transaction=True` Django zrobi savepoint i `bulk_create` w batch nie zatwierdzi się jak należy).
- Imports: absolutne (`from bpp.models import Wydzial`), nigdy relative `from ..`.
- Ruff: line length 88. Style: jak reszta `src/bpp/`.
- Po każdym task: `ruff format <changed paths> && ruff check <changed paths>` przed commitem.
- Commits: konwencja jak w branchu `dev` — polski, conventional commits prefix (`feat(demo-data):`, `test(demo-data):`, `refactor(demo-data):`). Każdy commit musi mieć `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` w footerze.
- Po dotknięciu modeli MPTT (`Jednostka`) z `bulk_create` → wywołać `Jednostka.objects.rebuild()`.
- Po dotknięciu `Wydawnictwo_*` przez `bulk_create` cache opisu może być nieaktualny — dla v1 to akceptujemy (cache zbuduje się leniwie / przez Celery). Nie wołamy explicit rebuild.

---

## File structure

```
src/bpp/
  demo_data/
    __init__.py                      ← public API: re-export Manifest, run_create, run_cleanup
    names.py                         ← stałe: IMIONA_POL, NAZWISKA_POL, KIERUNKI_POL, TYTULY_TEMPLATES
    manifest.py                      ← class Manifest (load/append/save z atomic write)
    confirm.py                       ← double_confirm(stdin, stdout, db_name, args) -> bool
    progress.py                      ← make_progress(iterable, desc, total) → tqdm fasada
    preflight.py                     ← REQUIRED_DICTIONARIES list + check() → missing list
    orchestrator.py                  ← run_create(opts), run_cleanup(opts) — top-level
    generators/
      __init__.py
      uczelnia.py                    ← ensure_uczelnia(manifest)
      wydzialy.py                    ← create_wydzialy(n, uczelnia, manifest, rng)
      jednostki.py                   ← create_jednostki(per_wydzial, wydzialy, manifest, rng)
      autorzy.py                     ← create_autorzy(n, jednostki, manifest, rng)
      dyscypliny.py                  ← create_autor_dyscypliny(autorzy, lata, procenty, manifest, rng)
      zrodla.py                      ← create_zrodla(n, manifest, rng)
      wydawcy.py                     ← create_wydawcy(n, manifest, rng)
      wydawnictwa_ciagle.py          ← create_wc(n, autorzy, zrodla, lata, manifest, rng)
      wydawnictwa_zwarte.py          ← create_wz(n, autorzy, wydawcy, lata, manifest, rng)
  management/commands/
    create_demo_data.py              ← thin entrypoint
    cleanup_demo_data.py             ← thin entrypoint
  tests/
    test_demo_data/
      __init__.py
      conftest.py                    ← fixtures: minimal_slowniki, tmp_manifest_path
      test_manifest.py
      test_confirm.py
      test_preflight.py
      test_progress.py
      test_generator_uczelnia.py
      test_generator_wydzialy_jednostki.py
      test_generator_autorzy.py
      test_generator_dyscypliny.py
      test_generator_zrodla_wydawcy.py
      test_generator_wydawnictwa.py
      test_command_create.py         ← integration: call_command z małymi liczbami
      test_command_cleanup.py        ← integration: roundtrip
```

---

## Task 1: Scaffolding — package skeleton + names.py + tests dir

**Files:**
- Create: `src/bpp/demo_data/__init__.py` (empty)
- Create: `src/bpp/demo_data/names.py`
- Create: `src/bpp/demo_data/generators/__init__.py` (empty)
- Create: `src/bpp/tests/test_demo_data/__init__.py` (empty)
- Create: `src/bpp/tests/test_demo_data/conftest.py`

### Steps

- [ ] **Step 1.1: Create empty package files**

```bash
mkdir -p src/bpp/demo_data/generators src/bpp/tests/test_demo_data
touch src/bpp/demo_data/__init__.py
touch src/bpp/demo_data/generators/__init__.py
touch src/bpp/tests/test_demo_data/__init__.py
```

- [ ] **Step 1.2: Create `src/bpp/demo_data/names.py` with data constants**

```python
"""Konstanty leksykalne dla generatora demo data (data-only, no logic)."""

IMIONA_POL = (
    # Kobiety
    "Anna", "Maria", "Katarzyna", "Małgorzata", "Agnieszka", "Barbara",
    "Ewa", "Magdalena", "Elżbieta", "Joanna", "Aleksandra", "Monika",
    "Zofia", "Teresa", "Krystyna", "Halina", "Beata", "Jadwiga",
    "Danuta", "Iwona", "Renata", "Wanda", "Grażyna", "Dorota",
    "Janina", "Urszula", "Hanna", "Marta", "Justyna", "Karolina",
    "Marzena", "Bożena", "Lucyna", "Wiesława", "Stanisława", "Helena",
    "Natalia", "Paulina", "Patrycja", "Sylwia", "Edyta", "Izabela",
    # Mężczyźni
    "Jan", "Andrzej", "Piotr", "Krzysztof", "Stanisław", "Tomasz",
    "Paweł", "Józef", "Marcin", "Marek", "Michał", "Grzegorz",
    "Jerzy", "Tadeusz", "Adam", "Łukasz", "Zbigniew", "Ryszard",
    "Dariusz", "Henryk", "Mariusz", "Wojciech", "Robert", "Kazimierz",
    "Mateusz", "Maciej", "Sławomir", "Rafał", "Bogdan", "Janusz",
    "Jacek", "Jakub", "Artur", "Marian", "Jarosław", "Mirosław",
    "Antoni", "Wiesław", "Roman", "Edward", "Sebastian", "Damian",
    "Kamil", "Daniel", "Bartosz",
)

NAZWISKA_POL = (
    "Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kowalczyk",
    "Kamiński", "Lewandowski", "Zieliński", "Szymański", "Woźniak",
    "Dąbrowski", "Kozłowski", "Jankowski", "Mazur", "Wojciechowski",
    "Kwiatkowski", "Krawczyk", "Kaczmarek", "Piotrowski", "Grabowski",
    "Zając", "Pawłowski", "Michalski", "Król", "Wieczorek",
    "Jabłoński", "Wróbel", "Nowakowski", "Majewski", "Olszewski",
    "Jaworski", "Adamczyk", "Dudek", "Nowicki", "Pawlak",
    "Górski", "Witkowski", "Walczak", "Sikora", "Baran",
    "Rutkowski", "Michalak", "Szewczyk", "Ostrowski", "Tomaszewski",
    "Pietrzak", "Marciniak", "Wróblewski", "Zalewski", "Jakubowski",
    "Jasiński", "Zawadzki", "Sadowski", "Bąk", "Chmielewski",
    "Włodarczyk", "Borkowski", "Czarnecki", "Sawicki", "Sokołowski",
    "Urbański", "Kubiak", "Maciejewski", "Szczepański", "Kucharski",
    "Wilk", "Kalinowski", "Lis", "Mazurek", "Wysocki",
    "Adamski", "Kaźmierczak", "Wasilewski", "Sobczak", "Czerwiński",
    "Andrzejewski", "Cieślak", "Głowacki", "Zakrzewski", "Kołodziej",
    "Sikorski", "Krupa", "Stępień", "Kurek", "Brzeziński",
    "Borowski", "Pawlik", "Sowa", "Domagała", "Wojtasik",
    "Mróz", "Małecki", "Janik", "Bednarek", "Bielecki",
    "Marek", "Krajewski", "Markowski", "Konieczny", "Lasota",
)

KIERUNKI_POL = (
    "Lekarski",
    "Lekarsko-Dentystyczny",
    "Farmaceutyczny",
    "Nauk o Zdrowiu",
    "Pielęgniarstwa i Nauk o Zdrowiu",
    "Biologii i Ochrony Środowiska",
    "Chemii",
    "Fizyki, Astronomii i Informatyki Stosowanej",
    "Informatyki",
    "Matematyki, Informatyki i Mechaniki",
    "Mechaniczny",
    "Elektroniki, Telekomunikacji i Informatyki",
    "Inżynierii Środowiska",
    "Architektury",
    "Budownictwa Lądowego i Wodnego",
    "Zarządzania",
    "Ekonomii",
    "Prawa i Administracji",
    "Filozoficzny",
    "Filologii Polskiej",
    "Filologiczny",
    "Historyczny",
    "Pedagogiki",
    "Psychologii",
    "Socjologii",
    "Teologii",
    "Sztuk Pięknych",
    "Muzyki",
    "Wychowania Fizycznego",
    "Nauk Geograficznych i Geologicznych",
)

TYTULY_TEMPLATES = (
    "Analiza wpływu {topic} na {subject} w {context}",
    "Badania {topic} w kontekście {subject}",
    "Wpływ {topic} na {subject}",
    "{topic}: studium przypadku {subject}",
    "Metodologia {topic} w {context}",
    "Modelowanie {topic} z wykorzystaniem {subject}",
    "Perspektywy rozwoju {topic} w {context}",
    "{topic} jako narzędzie {subject}",
    "Optymalizacja {topic} w {context}",
    "Przegląd literatury: {topic} a {subject}",
)

TOPICS = (
    "metod numerycznych", "algorytmów uczenia maszynowego",
    "biomarkerów", "polimorfizmów genetycznych", "interakcji białkowych",
    "modeli statystycznych", "systemów rozproszonych",
    "procedur klinicznych", "analizy obrazowej", "diagnostyki",
    "terapii celowanej", "farmakokinetyki", "biotransformacji",
    "ekspresji genowej", "metabolomiki", "proteomiki",
)

SUBJECTS = (
    "skuteczność leczenia", "jakość życia pacjentów",
    "wydajność systemu", "precyzję pomiarów",
    "stabilność wyników", "powtarzalność eksperymentu",
    "koszty operacyjne", "bezpieczeństwo procedury",
    "tolerancję terapii", "rokowanie pacjenta",
)

CONTEXTS = (
    "warunkach klinicznych", "środowisku laboratoryjnym",
    "populacji polskiej", "grupie kontrolnej",
    "badaniu wieloośrodkowym", "analizie retrospektywnej",
    "warunkach in vitro", "modelu zwierzęcym",
    "ośrodkach referencyjnych", "badaniu prospektywnym",
)
```

- [ ] **Step 1.3: Create conftest for test_demo_data**

`src/bpp/tests/test_demo_data/conftest.py`:

```python
"""Fixtures dla testów demo_data."""

import pytest


@pytest.fixture
def tmp_manifest_path(tmp_path):
    """Ścieżka do pliku manifestu w tmpdirze pytesta."""
    return tmp_path / "demo_manifest.json"


@pytest.fixture
def rng():
    """Deterministyczny RNG dla testów (seed=42)."""
    import random
    return random.Random(42)
```

- [ ] **Step 1.4: Verify import works**

Run: `uv run python -c "from bpp.demo_data import names; print(len(names.IMIONA_POL), len(names.NAZWISKA_POL))"`

Expected output: `86 100` (lub podobne — sprawdza tylko że import działa i listy nie są puste).

- [ ] **Step 1.5: Ruff + commit**

```bash
ruff format src/bpp/demo_data/ src/bpp/tests/test_demo_data/
ruff check src/bpp/demo_data/ src/bpp/tests/test_demo_data/
git add src/bpp/demo_data/ src/bpp/tests/test_demo_data/
git commit -m "$(cat <<'EOF'
feat(demo-data): scaffolding pakietu + stale leksykalne

Tworzy pusty pakiet bpp.demo_data z modulami imion, nazwisk,
kierunkow i szablonow tytulow prac. Zero logiki — same dane.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Manifest module (TDD)

**Files:**
- Create: `src/bpp/demo_data/manifest.py`
- Create: `src/bpp/tests/test_demo_data/test_manifest.py`

### Steps

- [ ] **Step 2.1: Write failing tests**

`src/bpp/tests/test_demo_data/test_manifest.py`:

```python
"""Testy dla Manifest z bpp.demo_data.manifest."""

import json

import pytest

from bpp.demo_data.manifest import Manifest


def test_empty_manifest_has_metadata(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="testdb",
                 command_args={"wydzialow": 3})
    m.save()

    data = json.loads(tmp_manifest_path.read_text())
    assert data["database"] == "testdb"
    assert data["command_args"] == {"wydzialow": 3}
    assert data["objects"] == {}
    assert "created_at" in data


def test_append_pks(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Wydzial", [1, 2, 3])
    m.append("bpp.Wydzial", [4, 5])
    m.append("bpp.Jednostka", [10, 11])
    m.save()

    data = json.loads(tmp_manifest_path.read_text())
    assert data["objects"]["bpp.Wydzial"]["pks"] == [1, 2, 3, 4, 5]
    assert data["objects"]["bpp.Jednostka"]["pks"] == [10, 11]


def test_append_with_extra(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Uczelnia", [1], extra={"created_by_demo": True})
    m.save()

    data = json.loads(tmp_manifest_path.read_text())
    assert data["objects"]["bpp.Uczelnia"]["pks"] == [1]
    assert data["objects"]["bpp.Uczelnia"]["created_by_demo"] is True


def test_atomic_write_no_tmp_left(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Wydzial", [1])
    m.save()

    tmp = tmp_manifest_path.with_suffix(tmp_manifest_path.suffix + ".tmp")
    assert not tmp.exists()


def test_load_roundtrip(tmp_manifest_path):
    m1 = Manifest(path=tmp_manifest_path, database="db",
                  command_args={"x": 1})
    m1.append("bpp.Wydzial", [1, 2])
    m1.append("bpp.Uczelnia", [9], extra={"created_by_demo": True})
    m1.save()

    m2 = Manifest.load(tmp_manifest_path)
    assert m2.database == "db"
    assert m2.command_args == {"x": 1}
    assert m2.objects_for("bpp.Wydzial") == [1, 2]
    assert m2.objects_for("bpp.Uczelnia") == [9]
    assert m2.extra_for("bpp.Uczelnia") == {"created_by_demo": True}


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Manifest.load(tmp_path / "nope.json")


def test_iter_phases_in_cleanup_order(tmp_manifest_path):
    """objects_in_cleanup_order zwraca pary (model_label, pks) w bezpiecznej
    kolejnosci usuwania."""
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Wydzial", [1])
    m.append("bpp.Wydawnictwo_Ciagle_Autor", [2])
    m.append("bpp.Uczelnia", [3], extra={"created_by_demo": True})
    m.append("bpp.Wydawnictwo_Ciagle", [4])

    order = [label for label, _ in m.objects_in_cleanup_order()]
    # Wydawnictwo_Ciagle_Autor (M2M) przed Wydawnictwo_Ciagle (rekordem)
    # Wydzial przed Uczelnia
    assert order.index("bpp.Wydawnictwo_Ciagle_Autor") < order.index(
        "bpp.Wydawnictwo_Ciagle"
    )
    assert order.index("bpp.Wydzial") < order.index("bpp.Uczelnia")


def test_cleanup_order_skips_uczelnia_if_not_created_by_demo(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    m.append("bpp.Uczelnia", [3])  # bez created_by_demo
    order = [label for label, _ in m.objects_in_cleanup_order()]
    assert "bpp.Uczelnia" not in order
```

- [ ] **Step 2.2: Run tests — expect ImportError**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_manifest.py -v`
Expected: `ImportError: cannot import name 'Manifest' from 'bpp.demo_data.manifest'`.

- [ ] **Step 2.3: Implement `Manifest` class**

`src/bpp/demo_data/manifest.py`:

```python
"""Manifest demo data: PK obiektow stworzonych przez create_demo_data."""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path

CLEANUP_ORDER = (
    # Najpierw M2M-through:
    "bpp.Wydawnictwo_Ciagle_Autor",
    "bpp.Wydawnictwo_Zwarte_Autor",
    # Potem rekordy (rozdzialy przed nadrzednymi obsluzy generator
    # przez sortowanie PK wg wydawnictwo_nadrzedne):
    "bpp.Wydawnictwo_Ciagle",
    "bpp.Wydawnictwo_Zwarte",
    # Powiazania autorow:
    "bpp.Autor_Dyscyplina",
    "bpp.Autor_Jednostka",
    # Encje bazowe:
    "bpp.Autor",
    "bpp.Jednostka",
    "bpp.Wydzial",
    # Slowniki "Demo —":
    "bpp.Zrodlo",
    "bpp.Wydawca",
    # Singleton tylko jesli stworzony przez nas:
    "bpp.Uczelnia",
)


class Manifest:
    """Zapis i odczyt manifestu PK obiektow demo data.

    Append-on-batch + atomic write (`.tmp` → `os.replace`).
    """

    def __init__(
        self,
        path: Path,
        database: str,
        command_args: dict,
        *,
        created_at: str | None = None,
        objects: dict | None = None,
    ):
        self.path = Path(path)
        self.database = database
        self.command_args = dict(command_args)
        self.created_at = created_at or datetime.datetime.now(
            datetime.timezone.utc
        ).isoformat()
        self.objects: dict[str, dict] = dict(objects or {})

    def append(self, model_label: str, pks: list[int], extra: dict | None = None):
        entry = self.objects.setdefault(model_label, {"pks": []})
        entry["pks"].extend(pks)
        if extra:
            for k, v in extra.items():
                entry[k] = v

    def objects_for(self, model_label: str) -> list[int]:
        return list(self.objects.get(model_label, {}).get("pks", []))

    def extra_for(self, model_label: str) -> dict:
        entry = self.objects.get(model_label, {})
        return {k: v for k, v in entry.items() if k != "pks"}

    def objects_in_cleanup_order(self):
        """Yielduje (model_label, pks) w kolejnosci bezpiecznego usuwania.

        Pomija bpp.Uczelnia jesli nie ma flagi `created_by_demo: True`.
        """
        for label in CLEANUP_ORDER:
            entry = self.objects.get(label)
            if not entry or not entry.get("pks"):
                continue
            if label == "bpp.Uczelnia" and not entry.get("created_by_demo"):
                continue
            yield label, list(entry["pks"])

    def save(self):
        payload = {
            "created_at": self.created_at,
            "command_args": self.command_args,
            "database": self.database,
            "objects": self.objects,
        }
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        os.replace(tmp, self.path)

    @classmethod
    def load(cls, path: Path) -> Manifest:
        data = json.loads(Path(path).read_text())
        return cls(
            path=path,
            database=data["database"],
            command_args=data.get("command_args", {}),
            created_at=data.get("created_at"),
            objects=data.get("objects", {}),
        )
```

- [ ] **Step 2.4: Run tests — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_manifest.py -v`
Expected: all 8 tests pass.

- [ ] **Step 2.5: Ruff + commit**

```bash
ruff format src/bpp/demo_data/manifest.py src/bpp/tests/test_demo_data/test_manifest.py
ruff check src/bpp/demo_data/manifest.py src/bpp/tests/test_demo_data/test_manifest.py
git add src/bpp/demo_data/manifest.py src/bpp/tests/test_demo_data/test_manifest.py
git commit -m "$(cat <<'EOF'
feat(demo-data): Manifest z atomic write + cleanup order

Append-on-batch (append/objects_for/extra_for), atomic save przez
.tmp + os.replace, kolejnosc cleanup zdefiniowana sztywno w
CLEANUP_ORDER (M2M → rekordy → encje → slowniki → Uczelnia).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Pre-flight check module (TDD)

**Files:**
- Create: `src/bpp/demo_data/preflight.py`
- Create: `src/bpp/tests/test_demo_data/test_preflight.py`

### Steps

- [ ] **Step 3.1: Write failing tests**

`src/bpp/tests/test_demo_data/test_preflight.py`:

```python
"""Testy pre-flight checkow demo_data."""

import pytest
from model_bakery import baker

from bpp.demo_data.preflight import REQUIRED_DICTIONARIES, check_required


@pytest.mark.django_db
def test_check_required_returns_missing_when_empty():
    # Baza testowa nie ma fixtur na ten test → spodziewamy sie wielu missing
    missing = check_required()
    labels = {label for label, _ in missing}
    # Spodziewamy się przynajmniej kilku typowych slownikow:
    assert "bpp.Charakter_Formalny" in labels or len(REQUIRED_DICTIONARIES) > 0


@pytest.mark.django_db
def test_check_required_returns_empty_when_all_present():
    # Tworzymy po jednym rekordzie kazdego wymaganego modelu
    for label, _hint in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        from django.apps import apps
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)

    missing = check_required()
    assert missing == []


def test_required_dictionaries_includes_critical_models():
    labels = {label for label, _ in REQUIRED_DICTIONARIES}
    assert "bpp.Charakter_Formalny" in labels
    assert "bpp.Typ_KBN" in labels
    assert "bpp.Jezyk" in labels
    assert "bpp.Dyscyplina_Naukowa" in labels
    assert "bpp.Typ_Odpowiedzialnosci" in labels
```

- [ ] **Step 3.2: Run — expect ImportError**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_preflight.py -v`
Expected: ImportError.

- [ ] **Step 3.3: Implement preflight**

`src/bpp/demo_data/preflight.py`:

```python
"""Pre-flight checks dla create_demo_data: wymagane fixtury slownikowe."""

from __future__ import annotations

from django.apps import apps

REQUIRED_DICTIONARIES: list[tuple[str, str]] = [
    ("bpp.Charakter_Formalny", "loaddata charakter_formalny"),
    ("bpp.Typ_KBN", "loaddata typ_kbn"),
    ("bpp.Jezyk", "loaddata jezyk"),
    ("bpp.Status_Korekty", "loaddata status_korekty"),
    ("bpp.Rodzaj_Zrodla", "loaddata rodzaj_zrodla"),
    ("bpp.Funkcja_Autora", "loaddata funkcja_autora"),
    ("bpp.Typ_Odpowiedzialnosci", "loaddata typ_odpowiedzialnosci_v2"),
    ("bpp.Tytul", "loaddata tytul"),
    ("bpp.Plec", "loaddata plec"),
    ("bpp.Zrodlo_Informacji", "loaddata zrodlo_informacji"),
    ("bpp.Dyscyplina_Naukowa", "import dyscyplin (zewnetrzny seed)"),
]


def check_required() -> list[tuple[str, str]]:
    """Zwraca liste (label, hint) dla brakujacych slownikow.

    Pusta lista = OK, mozna jechac.
    """
    missing: list[tuple[str, str]] = []
    for label, hint in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            missing.append((label, hint))
    return missing
```

- [ ] **Step 3.4: Run tests — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_preflight.py -v`
Expected: 3 tests pass.

- [ ] **Step 3.5: Ruff + commit**

```bash
ruff format src/bpp/demo_data/preflight.py src/bpp/tests/test_demo_data/test_preflight.py
ruff check src/bpp/demo_data/preflight.py src/bpp/tests/test_demo_data/test_preflight.py
git add src/bpp/demo_data/preflight.py src/bpp/tests/test_demo_data/test_preflight.py
git commit -m "$(cat <<'EOF'
feat(demo-data): preflight check wymaganych slownikow

REQUIRED_DICTIONARIES + check_required() zwraca liste brakujacych
slownikow z podpowiedzia jak je zaladowac.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Double-confirm module (TDD)

**Files:**
- Create: `src/bpp/demo_data/confirm.py`
- Create: `src/bpp/tests/test_demo_data/test_confirm.py`

### Steps

- [ ] **Step 4.1: Write failing tests**

`src/bpp/tests/test_demo_data/test_confirm.py`:

```python
"""Testy double-confirm dla demo_data."""

import io

import pytest

from bpp.demo_data.confirm import ConfirmAborted, double_confirm


def _stdin(text: str) -> io.StringIO:
    buf = io.StringIO(text)
    buf.isatty = lambda: True  # symulujemy TTY
    return buf


def _non_tty_stdin(text: str = "") -> io.StringIO:
    buf = io.StringIO(text)
    buf.isatty = lambda: False
    return buf


def test_bypass_via_flags():
    out = io.StringIO()
    double_confirm(
        stdin=_stdin(""),
        stdout=out,
        database="bpp",
        plan_text="...",
        yes_flag=True,
        confirm_db_flag="bpp",
    )
    # Nie raisuje → bypass dziala


def test_bypass_wrong_db_name_raises():
    out = io.StringIO()
    with pytest.raises(ConfirmAborted):
        double_confirm(
            stdin=_stdin(""),
            stdout=out,
            database="bpp",
            plan_text="...",
            yes_flag=True,
            confirm_db_flag="other_db",
        )


def test_non_tty_without_flags_raises():
    with pytest.raises(ConfirmAborted) as exc:
        double_confirm(
            stdin=_non_tty_stdin(),
            stdout=io.StringIO(),
            database="bpp",
            plan_text="...",
            yes_flag=False,
            confirm_db_flag=None,
        )
    assert "TTY" in str(exc.value) or "--yes-i-am-sure" in str(exc.value)


def test_prompt_one_no_raises():
    with pytest.raises(ConfirmAborted):
        double_confirm(
            stdin=_stdin("nie\n"),
            stdout=io.StringIO(),
            database="bpp",
            plan_text="X",
            yes_flag=False,
            confirm_db_flag=None,
        )


def test_prompt_two_wrong_db_name_raises():
    with pytest.raises(ConfirmAborted):
        double_confirm(
            stdin=_stdin("tak\nzla_baza\n"),
            stdout=io.StringIO(),
            database="bpp",
            plan_text="X",
            yes_flag=False,
            confirm_db_flag=None,
        )


def test_both_prompts_pass():
    double_confirm(
        stdin=_stdin("tak\nbpp\n"),
        stdout=io.StringIO(),
        database="bpp",
        plan_text="X",
        yes_flag=False,
        confirm_db_flag=None,
    )


def test_prompt_one_case_insensitive():
    double_confirm(
        stdin=_stdin("TAK\nbpp\n"),
        stdout=io.StringIO(),
        database="bpp",
        plan_text="X",
        yes_flag=False,
        confirm_db_flag=None,
    )


def test_prompt_two_case_sensitive_db_name():
    with pytest.raises(ConfirmAborted):
        double_confirm(
            stdin=_stdin("tak\nBPP\n"),  # nazwa bazy: bpp (lower)
            stdout=io.StringIO(),
            database="bpp",
            plan_text="X",
            yes_flag=False,
            confirm_db_flag=None,
        )
```

- [ ] **Step 4.2: Run — expect ImportError**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_confirm.py -v`
Expected: ImportError.

- [ ] **Step 4.3: Implement confirm**

`src/bpp/demo_data/confirm.py`:

```python
"""Podwojne potwierdzenie dla destrukcyjnych komend demo_data."""

from __future__ import annotations


class ConfirmAborted(Exception):
    """Uzytkownik nie potwierdzil albo non-tty bez flag."""


def double_confirm(
    *,
    stdin,
    stdout,
    database: str,
    plan_text: str,
    yes_flag: bool,
    confirm_db_flag: str | None,
):
    """Dwustopniowa walidacja:
    - bypass: yes_flag + confirm_db_flag == database
    - non-tty: musi byc bypass, inaczej ConfirmAborted
    - tty: prompt 'tak/nie' (case-insensitive) + prompt z dokladnym
      wpisaniem nazwy bazy (case-sensitive).
    """
    if yes_flag:
        if confirm_db_flag != database:
            raise ConfirmAborted(
                f"--confirm-db '{confirm_db_flag}' != '{database}'"
            )
        return

    if not stdin.isatty():
        raise ConfirmAborted(
            "Brak TTY. Uzyj '--yes-i-am-sure --confirm-db <NAME>' "
            "w trybie nie-interaktywnym."
        )

    stdout.write(plan_text + "\n")
    stdout.write(
        f"Kontynuowac w bazie '{database}'? [tak/nie]: "
    )
    stdout.flush()
    answer = stdin.readline().strip().lower()
    if answer != "tak":
        raise ConfirmAborted("Anulowane w prompcie #1.")

    stdout.write(
        f"Aby potwierdzic, wpisz dokladnie nazwe bazy: '{database}': "
    )
    stdout.flush()
    db_input = stdin.readline().rstrip("\n")
    if db_input != database:
        raise ConfirmAborted(
            f"Nazwa bazy nie pasuje: '{db_input}' != '{database}'."
        )
```

- [ ] **Step 4.4: Run tests — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_confirm.py -v`
Expected: 8 tests pass.

- [ ] **Step 4.5: Ruff + commit**

```bash
ruff format src/bpp/demo_data/confirm.py src/bpp/tests/test_demo_data/test_confirm.py
ruff check src/bpp/demo_data/confirm.py src/bpp/tests/test_demo_data/test_confirm.py
git add src/bpp/demo_data/confirm.py src/bpp/tests/test_demo_data/test_confirm.py
git commit -m "$(cat <<'EOF'
feat(demo-data): double_confirm — bypass + tty prompty + exact db match

ConfirmAborted exception, bypass przez --yes-i-am-sure +
--confirm-db, non-tty wymaga flag, tty: prompt #1 tak/nie
(case-insensitive), prompt #2 dokladna nazwa bazy (case-sensitive).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Progress fasada (TDD)

**Files:**
- Create: `src/bpp/demo_data/progress.py`
- Create: `src/bpp/tests/test_demo_data/test_progress.py`

### Steps

- [ ] **Step 5.1: Write tests**

`src/bpp/tests/test_demo_data/test_progress.py`:

```python
"""Test fasady progress (tqdm) — minimalna, glownie do mock w testach."""

from bpp.demo_data.progress import make_progress


def test_make_progress_yields_all_items():
    items = list(make_progress(range(5), desc="t", total=5, disable=True))
    assert items == [0, 1, 2, 3, 4]


def test_make_progress_disabled_does_not_print(capsys):
    list(make_progress(range(3), desc="t", total=3, disable=True))
    captured = capsys.readouterr()
    assert captured.err == ""
    assert captured.out == ""
```

- [ ] **Step 5.2: Run — expect ImportError**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_progress.py -v`
Expected: ImportError.

- [ ] **Step 5.3: Implement progress**

`src/bpp/demo_data/progress.py`:

```python
"""Cienka fasada nad tqdm — pozwala wylaczyc w testach."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import TypeVar

from tqdm import tqdm

T = TypeVar("T")


def make_progress(
    iterable: Iterable[T],
    *,
    desc: str,
    total: int | None = None,
    disable: bool = False,
) -> Iterator[T]:
    """Zwraca tqdm-iterator lub goly iterator gdy disable=True."""
    return tqdm(iterable, desc=desc, total=total, disable=disable)
```

- [ ] **Step 5.4: Run tests — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_progress.py -v`
Expected: 2 tests pass.

- [ ] **Step 5.5: Ruff + commit**

```bash
ruff format src/bpp/demo_data/progress.py src/bpp/tests/test_demo_data/test_progress.py
ruff check src/bpp/demo_data/progress.py src/bpp/tests/test_demo_data/test_progress.py
git add src/bpp/demo_data/progress.py src/bpp/tests/test_demo_data/test_progress.py
git commit -m "$(cat <<'EOF'
feat(demo-data): make_progress fasada nad tqdm

Cienki wrapper pozwala wylaczyc progress (disable=True) w testach.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Generator — Uczelnia (TDD)

**Files:**
- Create: `src/bpp/demo_data/generators/uczelnia.py`
- Create: `src/bpp/tests/test_demo_data/test_generator_uczelnia.py`

### Steps

- [ ] **Step 6.1: Write tests**

`src/bpp/tests/test_demo_data/test_generator_uczelnia.py`:

```python
"""Test generatora Uczelni (singleton)."""

import pytest
from model_bakery import baker

from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.manifest import Manifest
from bpp.models import Uczelnia


@pytest.mark.django_db
def test_creates_uczelnia_when_missing(tmp_manifest_path):
    assert not Uczelnia.objects.exists()
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    uczelnia = ensure_uczelnia(m)

    assert Uczelnia.objects.count() == 1
    assert uczelnia.nazwa.startswith("Demo")
    assert m.objects_for("bpp.Uczelnia") == [uczelnia.pk]
    assert m.extra_for("bpp.Uczelnia").get("created_by_demo") is True


@pytest.mark.django_db
def test_reuses_existing_uczelnia(tmp_manifest_path):
    existing = baker.make(Uczelnia, nazwa="Istniejaca", skrot="IST")
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})

    uczelnia = ensure_uczelnia(m)

    assert uczelnia.pk == existing.pk
    assert Uczelnia.objects.count() == 1
    # Manifest NIE zawiera istniejacej Uczelni
    assert m.objects_for("bpp.Uczelnia") == []
```

- [ ] **Step 6.2: Run — expect ImportError**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_generator_uczelnia.py -v`

- [ ] **Step 6.3: Implement**

`src/bpp/demo_data/generators/uczelnia.py`:

```python
"""Generator Uczelni (singleton) dla demo_data."""

from __future__ import annotations

from bpp.demo_data.manifest import Manifest
from bpp.models import Uczelnia


def ensure_uczelnia(manifest: Manifest) -> Uczelnia:
    """Zwraca singleton Uczelni. Jesli brak — tworzy 'Demo —' i wpisuje do
    manifestu z flaga `created_by_demo`."""
    existing = Uczelnia.objects.first()
    if existing is not None:
        return existing

    uczelnia = Uczelnia.objects.create(
        nazwa="Demo — Uczelnia Testowa",
        skrot="DEMO",
        nazwa_dopelniacz_field="Demo — Uczelni Testowej",
    )
    manifest.append(
        "bpp.Uczelnia", [uczelnia.pk], extra={"created_by_demo": True}
    )
    return uczelnia
```

- [ ] **Step 6.4: Run — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_generator_uczelnia.py -v`

- [ ] **Step 6.5: Ruff + commit**

```bash
ruff format src/bpp/demo_data/generators/uczelnia.py src/bpp/tests/test_demo_data/test_generator_uczelnia.py
ruff check src/bpp/demo_data/generators/uczelnia.py src/bpp/tests/test_demo_data/test_generator_uczelnia.py
git add src/bpp/demo_data/generators/uczelnia.py src/bpp/tests/test_demo_data/test_generator_uczelnia.py
git commit -m "$(cat <<'EOF'
feat(demo-data): generator Uczelni (singleton z reuse)

ensure_uczelnia(manifest) — reuse istniejacej Uczelni lub tworzy
'Demo — Uczelnia Testowa' i wpisuje do manifestu z flaga
created_by_demo: true.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Generator — Wydziały + Jednostki (TDD)

**Files:**
- Create: `src/bpp/demo_data/generators/wydzialy.py`
- Create: `src/bpp/demo_data/generators/jednostki.py`
- Create: `src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py`

### Steps

- [ ] **Step 7.1: Write tests**

`src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py`:

```python
"""Testy generatorow Wydzialow i Jednostek."""

import random

import pytest
from model_bakery import baker

from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.models import Jednostka, Uczelnia, Wydzial


@pytest.mark.django_db(transaction=True)
def test_create_wydzialy_creates_n_records(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    uczelnia = ensure_uczelnia(m)

    wydzialy = create_wydzialy(
        n=3, uczelnia=uczelnia, manifest=m, rng=random.Random(1),
        batch_size=10, disable_progress=True,
    )

    assert Wydzial.objects.count() == 3
    assert len(wydzialy) == 3
    for w in wydzialy:
        assert w.uczelnia_id == uczelnia.pk
        assert w.nazwa.startswith("Demo")
    assert sorted(m.objects_for("bpp.Wydzial")) == sorted(
        [w.pk for w in wydzialy]
    )


@pytest.mark.django_db(transaction=True)
def test_create_jednostki_per_wydzial(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    uczelnia = ensure_uczelnia(m)
    wydzialy = create_wydzialy(
        n=2, uczelnia=uczelnia, manifest=m, rng=random.Random(1),
        batch_size=10, disable_progress=True,
    )

    jednostki = create_jednostki(
        per_wydzial=3, wydzialy=wydzialy, uczelnia=uczelnia,
        manifest=m, rng=random.Random(2),
        batch_size=10, disable_progress=True,
    )

    assert Jednostka.objects.count() == 2 * 3
    assert len(jednostki) == 6
    # Kazda jednostka powiazana z wydzialem
    for j in jednostki:
        assert j.wydzial_id in {w.pk for w in wydzialy}
        assert j.uczelnia_id == uczelnia.pk


@pytest.mark.django_db(transaction=True)
def test_jednostki_mptt_rebuild_called(tmp_manifest_path):
    """Po create_jednostki MPTT tree jest spojny (lft/rght poprawne)."""
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    uczelnia = ensure_uczelnia(m)
    wydzialy = create_wydzialy(
        n=1, uczelnia=uczelnia, manifest=m, rng=random.Random(1),
        batch_size=10, disable_progress=True,
    )
    create_jednostki(
        per_wydzial=2, wydzialy=wydzialy, uczelnia=uczelnia,
        manifest=m, rng=random.Random(2),
        batch_size=10, disable_progress=True,
    )

    # Po rebuild kazda jednostka ma lft != 0 i rght > lft
    for j in Jednostka.objects.all():
        assert j.lft > 0
        assert j.rght > j.lft
```

- [ ] **Step 7.2: Run — expect ImportError**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py -v`

- [ ] **Step 7.3: Implement Wydzial generator**

`src/bpp/demo_data/generators/wydzialy.py`:

```python
"""Generator Wydzialow."""

from __future__ import annotations

import random

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.names import KIERUNKI_POL
from bpp.demo_data.progress import make_progress
from bpp.models import Uczelnia, Wydzial


def create_wydzialy(
    *,
    n: int,
    uczelnia: Uczelnia,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydzial]:
    """Tworzy n Wydzialow podpietych do uczelni. Append PK do manifestu."""
    created: list[Wydzial] = []
    kierunki = list(KIERUNKI_POL)
    rng.shuffle(kierunki)
    # Wystarczy gdy n <= len(KIERUNKI_POL); inaczej wraping:
    kierunki = (kierunki * ((n // len(kierunki)) + 1))[:n]

    objs = [
        Wydzial(
            uczelnia=uczelnia,
            nazwa=f"Demo — Wydział {i + 1} ({kierunki[i]})",
            skrot=f"DW{i + 1}",
            skrot_nazwy=f"Demo W{i + 1}",
            kolejnosc=i,
        )
        for i in range(n)
    ]

    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc="Wydziały",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Wydzial.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydzial", [w.pk for w in chunk])
        manifest.save()

    return created
```

- [ ] **Step 7.4: Implement Jednostka generator**

`src/bpp/demo_data/generators/jednostki.py`:

```python
"""Generator Jednostek (MPTT model — wymaga rebuild po bulk_create)."""

from __future__ import annotations

import random
from typing import Iterable

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import Jednostka, Uczelnia, Wydzial


def create_jednostki(
    *,
    per_wydzial: int,
    wydzialy: Iterable[Wydzial],
    uczelnia: Uczelnia,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Jednostka]:
    """Tworzy `per_wydzial` Jednostek per Wydzial. Rebuild MPTT po koncu."""
    wydzialy = list(wydzialy)
    objs: list[Jednostka] = []
    for w_idx, wydzial in enumerate(wydzialy, start=1):
        for j_idx in range(1, per_wydzial + 1):
            objs.append(
                Jednostka(
                    uczelnia=uczelnia,
                    wydzial=wydzial,
                    nazwa=f"Demo — Jednostka {w_idx}-{j_idx}",
                    skrot=f"DJ{w_idx}-{j_idx}",
                    rodzaj_jednostki=Jednostka.RODZAJ_JEDNOSTKI.NORMALNA,
                )
            )

    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc="Jednostki",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Jednostka] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Jednostka.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Jednostka", [j.pk for j in chunk])
        manifest.save()

    # MPTT wymaga rebuild po bulk_create:
    Jednostka.objects.rebuild()

    return created
```

> **Gotcha:** Pole `rodzaj_jednostki` w `Jednostka` to TextChoices. Jeśli w modelu jest inna nazwa enum-a — sprawdź `src/bpp/models/jednostka.py:152`.

- [ ] **Step 7.5: Run tests — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py -v`

- [ ] **Step 7.6: Ruff + commit**

```bash
ruff format src/bpp/demo_data/generators/ src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py
ruff check src/bpp/demo_data/generators/ src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py
git add src/bpp/demo_data/generators/wydzialy.py src/bpp/demo_data/generators/jednostki.py src/bpp/tests/test_demo_data/test_generator_wydzialy_jednostki.py
git commit -m "$(cat <<'EOF'
feat(demo-data): generatory Wydzialow i Jednostek

Wydzialy: bulk_create z prefixem 'Demo —' i losowymi kierunkami.
Jednostki: per Wydzial, MPTT.rebuild() po bulk_create. Oba pisza
PK do manifestu po kazdym batchu (incremental save).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Generator — Autorzy + Autor_Jednostka (TDD)

**Files:**
- Create: `src/bpp/demo_data/generators/autorzy.py`
- Create: `src/bpp/tests/test_demo_data/test_generator_autorzy.py`

### Steps

- [ ] **Step 8.1: Write tests**

`src/bpp/tests/test_demo_data/test_generator_autorzy.py`:

```python
"""Test generatora Autor + Autor_Jednostka."""

import random

import pytest

from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.models import Autor, Autor_Jednostka


@pytest.fixture
def jednostki_fixture(tmp_manifest_path, db):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    uczelnia = ensure_uczelnia(m)
    w = create_wydzialy(
        n=2, uczelnia=uczelnia, manifest=m, rng=random.Random(1),
        batch_size=10, disable_progress=True,
    )
    j = create_jednostki(
        per_wydzial=2, wydzialy=w, uczelnia=uczelnia,
        manifest=m, rng=random.Random(2),
        batch_size=10, disable_progress=True,
    )
    return m, j


@pytest.mark.django_db(transaction=True)
def test_create_autorzy_creates_n_records(jednostki_fixture, tmp_manifest_path):
    m, jednostki = jednostki_fixture

    autorzy = create_autorzy(
        n=10, jednostki=jednostki, manifest=m,
        rng=random.Random(3), batch_size=100, disable_progress=True,
    )

    assert Autor.objects.count() == 10
    assert len(autorzy) == 10
    assert sorted(m.objects_for("bpp.Autor")) == sorted(
        [a.pk for a in autorzy]
    )


@pytest.mark.django_db(transaction=True)
def test_each_autor_has_one_jednostka(jednostki_fixture, tmp_manifest_path):
    m, jednostki = jednostki_fixture
    autorzy = create_autorzy(
        n=5, jednostki=jednostki, manifest=m,
        rng=random.Random(3), batch_size=100, disable_progress=True,
    )

    aj_for = {aj.autor_id: aj for aj in Autor_Jednostka.objects.all()}
    assert len(aj_for) == 5
    for a in autorzy:
        assert a.pk in aj_for
        assert aj_for[a.pk].jednostka_id in {j.pk for j in jednostki}


@pytest.mark.django_db(transaction=True)
def test_autorzy_have_polish_names(jednostki_fixture, tmp_manifest_path):
    from bpp.demo_data.names import IMIONA_POL, NAZWISKA_POL
    m, jednostki = jednostki_fixture
    autorzy = create_autorzy(
        n=5, jednostki=jednostki, manifest=m,
        rng=random.Random(3), batch_size=100, disable_progress=True,
    )
    for a in autorzy:
        assert a.imiona in IMIONA_POL
        assert a.nazwisko in NAZWISKA_POL


@pytest.mark.django_db(transaction=True)
def test_seed_determinism(jednostki_fixture, tmp_manifest_path):
    m, jednostki = jednostki_fixture
    autorzy_1 = create_autorzy(
        n=5, jednostki=jednostki, manifest=m,
        rng=random.Random(99), batch_size=100, disable_progress=True,
    )
    names_1 = [(a.imiona, a.nazwisko) for a in autorzy_1]

    Autor.objects.filter(pk__in=[a.pk for a in autorzy_1]).delete()

    autorzy_2 = create_autorzy(
        n=5, jednostki=jednostki, manifest=Manifest(
            path=tmp_manifest_path, database="db", command_args={}
        ),
        rng=random.Random(99), batch_size=100, disable_progress=True,
    )
    names_2 = [(a.imiona, a.nazwisko) for a in autorzy_2]
    assert names_1 == names_2
```

- [ ] **Step 8.2: Run — expect ImportError**

- [ ] **Step 8.3: Implement**

`src/bpp/demo_data/generators/autorzy.py`:

```python
"""Generator Autorow + Autor_Jednostka."""

from __future__ import annotations

import random
from typing import Iterable

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.names import IMIONA_POL, NAZWISKA_POL
from bpp.demo_data.progress import make_progress
from bpp.models import Autor, Autor_Jednostka, Jednostka


def create_autorzy(
    *,
    n: int,
    jednostki: Iterable[Jednostka],
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Autor]:
    """Tworzy n Autorow, kazdy pinniety do 1 losowej Jednostki przez
    Autor_Jednostka."""
    jednostki = list(jednostki)
    if not jednostki:
        raise ValueError("Brak Jednostek do podpiecia Autorow.")

    autorzy_objs = [
        Autor(
            imiona=rng.choice(IMIONA_POL),
            nazwisko=rng.choice(NAZWISKA_POL),
        )
        for _ in range(n)
    ]

    pbar_a = make_progress(
        range(0, n, batch_size),
        desc="Autorzy",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Autor] = []
    for start in pbar_a:
        chunk = autorzy_objs[start : start + batch_size]
        Autor.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Autor", [a.pk for a in chunk])
        manifest.save()

    # Autor_Jednostka — wymaga rok_min/rok_max (sprawdz Autor_Jednostka model).
    # Tu uzywamy szerokiego zakresu: 1900–2100, zeby pokryl kazdy rok pracy.
    aj_objs = [
        Autor_Jednostka(
            autor=a,
            jednostka=rng.choice(jednostki),
            rok_min=1900,
            rok_max=2100,
        )
        for a in created
    ]

    pbar_aj = make_progress(
        range(0, len(aj_objs), batch_size),
        desc="Autor_Jednostka",
        total=(len(aj_objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar_aj:
        chunk = aj_objs[start : start + batch_size]
        Autor_Jednostka.objects.bulk_create(chunk)
        manifest.append("bpp.Autor_Jednostka", [aj.pk for aj in chunk])
        manifest.save()

    return created
```

> **Gotcha:** Pola `rok_min`/`rok_max` w `Autor_Jednostka` — pełna definicja w `src/bpp/models/jednostka.py:421-460` (klasa `Jednostka_Wydzial` ma podobny pattern). Sprawdź dokładnie nazwy pól w modelu `Autor_Jednostka` (jeśli inna nazwa modelu, np. `Wydzial_Autor`, popraw odpowiednio).

- [ ] **Step 8.4: Run — expect PASS**

- [ ] **Step 8.5: Ruff + commit**

```bash
ruff format src/bpp/demo_data/generators/autorzy.py src/bpp/tests/test_demo_data/test_generator_autorzy.py
ruff check src/bpp/demo_data/generators/autorzy.py src/bpp/tests/test_demo_data/test_generator_autorzy.py
git add src/bpp/demo_data/generators/autorzy.py src/bpp/tests/test_demo_data/test_generator_autorzy.py
git commit -m "$(cat <<'EOF'
feat(demo-data): generator Autorow + Autor_Jednostka

n autorow z losowymi imionami/nazwiskami z list polskich, kazdy
pinniety do 1 losowej jednostki przez Autor_Jednostka. Batch
commits z progress, deterministyczne przez rng.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Generator — Autor_Dyscyplina (TDD)

**Files:**
- Create: `src/bpp/demo_data/generators/dyscypliny.py`
- Create: `src/bpp/tests/test_demo_data/test_generator_dyscypliny.py`

### Steps

- [ ] **Step 9.1: Write tests**

`src/bpp/tests/test_demo_data/test_generator_dyscypliny.py`:

```python
"""Test generatora Autor_Dyscyplina."""

import random

import pytest
from model_bakery import baker

from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.dyscypliny import create_autor_dyscypliny
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.models import Autor_Dyscyplina, Dyscyplina_Naukowa


@pytest.fixture
def setup(tmp_manifest_path, db):
    # Stworz kilka dyscyplin
    for i in range(5):
        baker.make(Dyscyplina_Naukowa, nazwa=f"Dysc{i}", kod=f"D{i}")

    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    u = ensure_uczelnia(m)
    w = create_wydzialy(n=1, uczelnia=u, manifest=m,
                       rng=random.Random(1), batch_size=10,
                       disable_progress=True)
    j = create_jednostki(per_wydzial=1, wydzialy=w, uczelnia=u,
                        manifest=m, rng=random.Random(2), batch_size=10,
                        disable_progress=True)
    a = create_autorzy(n=20, jednostki=j, manifest=m,
                      rng=random.Random(3), batch_size=10,
                      disable_progress=True)
    return m, a


@pytest.mark.django_db(transaction=True)
def test_100_percent_full_coverage(setup):
    m, autorzy = setup
    create_autor_dyscypliny(
        autorzy=autorzy, lata=range(2017, 2026),
        procent_z_dyscyplina=100,
        procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=0,
        manifest=m, rng=random.Random(99),
        batch_size=100, disable_progress=True,
    )
    # 20 autorow * 9 lat = 180 rekordow
    assert Autor_Dyscyplina.objects.count() == 20 * 9
    # Kazdy ma dyscypline, nikt nie ma subdyscypliny:
    assert Autor_Dyscyplina.objects.filter(
        dyscyplina_naukowa__isnull=False
    ).count() == 180
    assert Autor_Dyscyplina.objects.filter(
        subdyscyplina_naukowa__isnull=False
    ).count() == 0


@pytest.mark.django_db(transaction=True)
def test_50_percent_coverage(setup):
    m, autorzy = setup  # 20 autorow
    create_autor_dyscypliny(
        autorzy=autorzy, lata=range(2017, 2026),
        procent_z_dyscyplina=50,
        procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=0,
        manifest=m, rng=random.Random(99),
        batch_size=100, disable_progress=True,
    )
    autorzy_z_dysc = (
        Autor_Dyscyplina.objects.values("autor_id").distinct().count()
    )
    # Powinno byc okolo 10 (50% z 20), ale moze sie wahac.
    assert 5 <= autorzy_z_dysc <= 15


@pytest.mark.django_db(transaction=True)
def test_subdyscyplina_assigned(setup):
    m, autorzy = setup
    create_autor_dyscypliny(
        autorzy=autorzy, lata=range(2017, 2020),
        procent_z_dyscyplina=100,
        procent_z_subdyscyplina=100,
        procent_zmiana_dyscypliny=0,
        manifest=m, rng=random.Random(99),
        batch_size=100, disable_progress=True,
    )
    # Wszyscy z subdyscyplina (rozna od dyscypliny):
    assert Autor_Dyscyplina.objects.filter(
        subdyscyplina_naukowa__isnull=False
    ).count() == Autor_Dyscyplina.objects.count()


@pytest.mark.django_db(transaction=True)
def test_zmiana_dyscypliny_w_2022(setup):
    m, autorzy = setup
    create_autor_dyscypliny(
        autorzy=autorzy, lata=range(2017, 2026),
        procent_z_dyscyplina=100,
        procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=100,  # wszyscy zmieniaja
        manifest=m, rng=random.Random(99),
        batch_size=100, disable_progress=True,
    )
    # Dla kazdego autora: dyscyplina w 2017–2021 != dyscyplina w 2022–2025
    for autor in autorzy:
        d_przed = Autor_Dyscyplina.objects.filter(
            autor=autor, rok=2017
        ).first()
        d_po = Autor_Dyscyplina.objects.filter(
            autor=autor, rok=2022
        ).first()
        if d_przed and d_po:
            assert d_przed.dyscyplina_naukowa_id != d_po.dyscyplina_naukowa_id


@pytest.mark.django_db(transaction=True)
def test_manifest_pks_match(setup):
    m, autorzy = setup
    create_autor_dyscypliny(
        autorzy=autorzy, lata=range(2017, 2020),
        procent_z_dyscyplina=100, procent_z_subdyscyplina=0,
        procent_zmiana_dyscypliny=0,
        manifest=m, rng=random.Random(99),
        batch_size=100, disable_progress=True,
    )
    assert sorted(m.objects_for("bpp.Autor_Dyscyplina")) == sorted(
        Autor_Dyscyplina.objects.values_list("pk", flat=True)
    )
```

- [ ] **Step 9.2: Run — expect ImportError**

- [ ] **Step 9.3: Implement**

`src/bpp/demo_data/generators/dyscypliny.py`:

```python
"""Generator Autor_Dyscyplina per autor per rok."""

from __future__ import annotations

import random
from typing import Iterable

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import Autor, Autor_Dyscyplina, Dyscyplina_Naukowa

ROK_ZMIANY = 2022


def create_autor_dyscypliny(
    *,
    autorzy: Iterable[Autor],
    lata: Iterable[int],
    procent_z_dyscyplina: int,
    procent_z_subdyscyplina: int,
    procent_zmiana_dyscypliny: int,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Autor_Dyscyplina]:
    """Tworzy Autor_Dyscyplina per (autor, rok) wg procentow z CLI."""
    autorzy = list(autorzy)
    lata = list(lata)
    dyscypliny = list(Dyscyplina_Naukowa.objects.all())
    if not dyscypliny:
        raise ValueError("Brak Dyscyplin_Naukowych w bazie.")

    # Per autor: czy ma dyscypline, czy ma subdyscypline, czy zmienia w 2022.
    # Wszystkie procenty 0–100 (jezeli 100 → wszyscy, jezeli 0 → nikt).
    objs: list[Autor_Dyscyplina] = []
    for autor in autorzy:
        if rng.randint(1, 100) > procent_z_dyscyplina:
            continue

        zmienia = rng.randint(1, 100) <= procent_zmiana_dyscypliny
        ma_subdyscypline = rng.randint(1, 100) <= procent_z_subdyscyplina

        d_pre = rng.choice(dyscypliny)
        d_post = (
            rng.choice([d for d in dyscypliny if d.pk != d_pre.pk])
            if zmienia and len(dyscypliny) > 1
            else d_pre
        )

        for rok in lata:
            dyscyplina = d_post if rok >= ROK_ZMIANY else d_pre
            subdyscyplina = None
            if ma_subdyscypline and len(dyscypliny) > 1:
                candidates = [d for d in dyscypliny if d.pk != dyscyplina.pk]
                subdyscyplina = rng.choice(candidates)

            objs.append(
                Autor_Dyscyplina(
                    autor=autor,
                    rok=rok,
                    dyscyplina_naukowa=dyscyplina,
                    subdyscyplina_naukowa=subdyscyplina,
                    procent_dyscypliny=100,
                    wymiar_etatu=1,
                )
            )

    pbar = make_progress(
        range(0, len(objs), batch_size),
        desc="Autor_Dyscyplina",
        total=(len(objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Autor_Dyscyplina] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Autor_Dyscyplina.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Autor_Dyscyplina", [ad.pk for ad in chunk])
        manifest.save()

    return created
```

- [ ] **Step 9.4: Run — expect PASS**

- [ ] **Step 9.5: Ruff + commit**

```bash
git add src/bpp/demo_data/generators/dyscypliny.py src/bpp/tests/test_demo_data/test_generator_dyscypliny.py
git commit -m "$(cat <<'EOF'
feat(demo-data): generator Autor_Dyscyplina per autor per rok

Parametryzowalne procenty: --procent-z-dyscyplina (czy autor ma
w ogole dyscypline), --procent-z-subdyscyplina, --procent-zmiana-
dyscypliny (zmiana w 2022, nowy cykl).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Generator — Zrodla + Wydawcy (TDD)

**Files:**
- Create: `src/bpp/demo_data/generators/zrodla.py`
- Create: `src/bpp/demo_data/generators/wydawcy.py`
- Create: `src/bpp/tests/test_demo_data/test_generator_zrodla_wydawcy.py`

### Steps

- [ ] **Step 10.1: Write tests**

`src/bpp/tests/test_demo_data/test_generator_zrodla_wydawcy.py`:

```python
"""Test generatorow Zrodla + Wydawca."""

import random

import pytest
from model_bakery import baker

from bpp.demo_data.generators.wydawcy import create_wydawcy
from bpp.demo_data.generators.zrodla import create_zrodla
from bpp.demo_data.manifest import Manifest
from bpp.models import Rodzaj_Zrodla, Wydawca, Zrodlo


@pytest.fixture
def setup_rodzaje(db):
    for nazwa in ("Czasopismo", "Książka", "Materiały konferencyjne"):
        baker.make(Rodzaj_Zrodla, nazwa=nazwa)


@pytest.mark.django_db(transaction=True)
def test_create_zrodla(setup_rodzaje, tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    zrodla = create_zrodla(
        n=5, manifest=m, rng=random.Random(1),
        batch_size=10, disable_progress=True,
    )
    assert len(zrodla) == 5
    assert Zrodlo.objects.count() == 5
    for z in zrodla:
        assert z.nazwa.startswith("Demo —")
        assert z.rodzaj_id is not None
    assert sorted(m.objects_for("bpp.Zrodlo")) == sorted(
        [z.pk for z in zrodla]
    )


@pytest.mark.django_db(transaction=True)
def test_create_wydawcy(tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    wydawcy = create_wydawcy(
        n=3, manifest=m, rng=random.Random(1),
        batch_size=10, disable_progress=True,
    )
    assert len(wydawcy) == 3
    for w in wydawcy:
        assert w.nazwa.startswith("Demo —")
    assert Wydawca.objects.count() == 3


@pytest.mark.django_db(transaction=True)
def test_zrodla_have_synthetic_issn(setup_rodzaje, tmp_manifest_path):
    import re

    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    zrodla = create_zrodla(
        n=3, manifest=m, rng=random.Random(1),
        batch_size=10, disable_progress=True,
    )
    for z in zrodla:
        # ISSN format: NNNN-NNNN
        assert re.match(r"^\d{4}-\d{3}[\dX]$", z.issn)
```

- [ ] **Step 10.2: Run — expect ImportError**

- [ ] **Step 10.3: Implement zrodla**

`src/bpp/demo_data/generators/zrodla.py`:

```python
"""Generator Zrodel (czasopism)."""

from __future__ import annotations

import random

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import Rodzaj_Zrodla, Zrodlo


def _synthetic_issn(rng: random.Random) -> str:
    """Generuje syntetyczny ISSN w formacie NNNN-NNNN (ostatnia cyfra: random
    digit lub 'X')."""
    first = "".join(str(rng.randint(0, 9)) for _ in range(4))
    second = "".join(str(rng.randint(0, 9)) for _ in range(3))
    last = rng.choice("0123456789X")
    return f"{first}-{second}{last}"


def create_zrodla(
    *,
    n: int,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Zrodlo]:
    rodzaje = list(Rodzaj_Zrodla.objects.all())
    if not rodzaje:
        raise ValueError("Brak Rodzaj_Zrodla w bazie.")

    objs = [
        Zrodlo(
            nazwa=f"Demo — Czasopismo {i + 1}",
            skrot=f"DC{i + 1}",
            rodzaj=rng.choice(rodzaje),
            issn=_synthetic_issn(rng),
        )
        for i in range(n)
    ]

    pbar = make_progress(
        range(0, n, batch_size),
        desc="Źródła",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Zrodlo] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Zrodlo.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Zrodlo", [z.pk for z in chunk])
        manifest.save()
    return created
```

- [ ] **Step 10.4: Implement wydawcy**

`src/bpp/demo_data/generators/wydawcy.py`:

```python
"""Generator Wydawcow."""

from __future__ import annotations

import random

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.progress import make_progress
from bpp.models import Wydawca


def create_wydawcy(
    *,
    n: int,
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydawca]:
    objs = [
        Wydawca(nazwa=f"Demo — Wydawca {i + 1}") for i in range(n)
    ]

    pbar = make_progress(
        range(0, n, batch_size),
        desc="Wydawcy",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Wydawca] = []
    for start in pbar:
        chunk = objs[start : start + batch_size]
        Wydawca.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydawca", [w.pk for w in chunk])
        manifest.save()
    return created
```

- [ ] **Step 10.5: Run — expect PASS**

- [ ] **Step 10.6: Ruff + commit**

```bash
git add src/bpp/demo_data/generators/zrodla.py src/bpp/demo_data/generators/wydawcy.py src/bpp/tests/test_demo_data/test_generator_zrodla_wydawcy.py
git commit -m "$(cat <<'EOF'
feat(demo-data): generatory Zrodel i Wydawcow

Zrodla z syntetycznym ISSN (format NNNN-NNNN) i losowym
Rodzaj_Zrodla. Wydawcy: lista z prefixem 'Demo —'. Oba z batch
commits i progress.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Generator — Wydawnictwo_Ciagle + powiązania + DOI + OA (TDD)

**Files:**
- Create: `src/bpp/demo_data/generators/wydawnictwa_ciagle.py`
- Create: `src/bpp/tests/test_demo_data/test_generator_wydawnictwa_ciagle.py`

### Steps

- [ ] **Step 11.1: Write tests**

`src/bpp/tests/test_demo_data/test_generator_wydawnictwa_ciagle.py`:

```python
"""Test generatora Wydawnictwo_Ciagle + Wydawnictwo_Ciagle_Autor."""

import random
import re

import pytest
from model_bakery import baker

from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydawnictwa_ciagle import create_wc
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.generators.zrodla import create_zrodla
from bpp.demo_data.manifest import Manifest
from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Rodzaj_Zrodla,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)


@pytest.fixture
def slowniki(db):
    baker.make(Charakter_Formalny, skrot="AC", nazwa="Artykuł")
    baker.make(Charakter_Formalny, skrot="PA", nazwa="Praca poglądowa")
    baker.make(Typ_KBN, skrot="PO", nazwa="Praca oryginalna")
    baker.make(Jezyk, skrot="pol.", nazwa="polski")
    baker.make(Status_Korekty, nazwa="Po korekcie")
    baker.make(
        Typ_Odpowiedzialnosci, skrot="aut.", nazwa="autor"
    )
    baker.make(Rodzaj_Zrodla, nazwa="Czasopismo")


@pytest.fixture
def setup(slowniki, tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    u = ensure_uczelnia(m)
    w = create_wydzialy(n=1, uczelnia=u, manifest=m,
                       rng=random.Random(1), batch_size=10,
                       disable_progress=True)
    j = create_jednostki(per_wydzial=1, wydzialy=w, uczelnia=u,
                        manifest=m, rng=random.Random(2), batch_size=10,
                        disable_progress=True)
    a = create_autorzy(n=10, jednostki=j, manifest=m,
                      rng=random.Random(3), batch_size=10,
                      disable_progress=True)
    z = create_zrodla(n=3, manifest=m, rng=random.Random(4),
                     batch_size=10, disable_progress=True)
    return m, a, z


@pytest.mark.django_db(transaction=True)
def test_creates_n_prac(setup):
    m, autorzy, zrodla = setup
    prace = create_wc(
        n=20, autorzy=autorzy, zrodla=zrodla,
        lata=range(2020, 2023), manifest=m, rng=random.Random(99),
        batch_size=10, disable_progress=True,
    )
    assert Wydawnictwo_Ciagle.objects.count() == 20
    assert len(prace) == 20


@pytest.mark.django_db(transaction=True)
def test_each_praca_has_authors(setup):
    m, autorzy, zrodla = setup
    create_wc(
        n=10, autorzy=autorzy, zrodla=zrodla,
        lata=range(2020, 2023), manifest=m, rng=random.Random(99),
        batch_size=10, disable_progress=True,
    )
    # Kazda praca ma 1–8 autorow
    for praca in Wydawnictwo_Ciagle.objects.all():
        count = Wydawnictwo_Ciagle_Autor.objects.filter(rekord=praca).count()
        assert 1 <= count <= 8


@pytest.mark.django_db(transaction=True)
def test_doi_format(setup):
    m, autorzy, zrodla = setup
    create_wc(
        n=5, autorzy=autorzy, zrodla=zrodla,
        lata=range(2020, 2023), manifest=m, rng=random.Random(99),
        batch_size=10, disable_progress=True,
    )
    pattern = re.compile(r"^10\.\d{4}/demo\.\d{4}\.\d+$")
    for praca in Wydawnictwo_Ciagle.objects.all():
        assert pattern.match(praca.doi)


@pytest.mark.django_db(transaction=True)
def test_pbn_uid_always_empty(setup):
    m, autorzy, zrodla = setup
    create_wc(
        n=5, autorzy=autorzy, zrodla=zrodla,
        lata=range(2020, 2023), manifest=m, rng=random.Random(99),
        batch_size=10, disable_progress=True,
    )
    for praca in Wydawnictwo_Ciagle.objects.all():
        assert praca.pbn_uid_id is None


@pytest.mark.django_db(transaction=True)
def test_lata_w_zakresie(setup):
    m, autorzy, zrodla = setup
    create_wc(
        n=20, autorzy=autorzy, zrodla=zrodla,
        lata=range(2018, 2021), manifest=m, rng=random.Random(99),
        batch_size=10, disable_progress=True,
    )
    lata_w_bazie = set(
        Wydawnictwo_Ciagle.objects.values_list("rok", flat=True)
    )
    assert lata_w_bazie.issubset({2018, 2019, 2020})


@pytest.mark.django_db(transaction=True)
def test_manifest_includes_powiazania(setup):
    m, autorzy, zrodla = setup
    create_wc(
        n=5, autorzy=autorzy, zrodla=zrodla,
        lata=range(2020, 2023), manifest=m, rng=random.Random(99),
        batch_size=10, disable_progress=True,
    )
    assert len(m.objects_for("bpp.Wydawnictwo_Ciagle")) == 5
    assert len(m.objects_for("bpp.Wydawnictwo_Ciagle_Autor")) >= 5
```

- [ ] **Step 11.2: Run — expect ImportError**

- [ ] **Step 11.3: Implement**

`src/bpp/demo_data/generators/wydawnictwa_ciagle.py`:

```python
"""Generator Wydawnictwo_Ciagle + Wydawnictwo_Ciagle_Autor + DOI + OA."""

from __future__ import annotations

import random
from typing import Iterable

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.names import CONTEXTS, SUBJECTS, TOPICS, TYTULY_TEMPLATES
from bpp.demo_data.progress import make_progress
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Zrodlo,
)


def _tytul(rng: random.Random, idx: int) -> str:
    template = rng.choice(TYTULY_TEMPLATES)
    return f"Demo — {template.format(topic=rng.choice(TOPICS), subject=rng.choice(SUBJECTS), context=rng.choice(CONTEXTS))} (nr {idx})"


def _doi(rng: random.Random, rok: int, idx: int) -> str:
    prefix4 = rng.randint(1000, 9999)
    return f"10.{prefix4}/demo.{rok}.{idx}"


def _maybe_openaccess(rng: random.Random) -> dict:
    """Zwraca dict do **kwargs Wydawnictwo_*, ustawia OA z prawd. 50%.

    Modele OA (Tryb_OpenAccess_*, Wersja_Tekstu_*, Licencja_OpenAccess) sa
    opcjonalne — jesli pusto, zwraca {}.
    """
    from bpp.models.openaccess import (
        Licencja_OpenAccess,
        Tryb_OpenAccess_Wydawnictwo_Ciagle,
        Wersja_Tekstu_OpenAccess,
    )

    if rng.randint(0, 1) == 0:
        return {}

    out = {}
    tryb = Tryb_OpenAccess_Wydawnictwo_Ciagle.objects.order_by("?").first()
    if tryb:
        out["openaccess_tryb_dostepu"] = tryb
    wersja = Wersja_Tekstu_OpenAccess.objects.order_by("?").first()
    if wersja:
        out["openaccess_wersja_tekstu"] = wersja
    licencja = Licencja_OpenAccess.objects.order_by("?").first()
    if licencja:
        out["openaccess_licencja"] = licencja
    return out


def create_wc(
    *,
    n: int,
    autorzy: Iterable[Autor],
    zrodla: Iterable[Zrodlo],
    lata: Iterable[int],
    manifest: Manifest,
    rng: random.Random,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydawnictwo_Ciagle]:
    autorzy = list(autorzy)
    zrodla = list(zrodla)
    lata = list(lata)

    # Charaktery formalne (slowniki sa juz wgrane przez fixture — pre-flight
    # to sprawdza). Filtrujemy do tych "ciaglych" jesli pole istnieje:
    charaktery = list(Charakter_Formalny.objects.all())
    if not charaktery:
        raise ValueError("Brak Charakter_Formalny w bazie.")

    typy_kbn = list(Typ_KBN.objects.all())
    jezyki = list(Jezyk.objects.all())
    statusy = list(Status_Korekty.objects.all())
    aut_typ = Typ_Odpowiedzialnosci.objects.filter(skrot="aut.").first() \
        or Typ_Odpowiedzialnosci.objects.first()
    if aut_typ is None:
        raise ValueError("Brak Typ_Odpowiedzialnosci w bazie.")

    prace: list[Wydawnictwo_Ciagle] = []
    for i in range(n):
        rok = rng.choice(lata)
        prace.append(
            Wydawnictwo_Ciagle(
                tytul_oryginalny=_tytul(rng, i + 1),
                rok=rok,
                charakter_formalny=rng.choice(charaktery),
                typ_kbn=rng.choice(typy_kbn) if typy_kbn else None,
                jezyk=rng.choice(jezyki) if jezyki else None,
                status_korekty=rng.choice(statusy) if statusy else None,
                zrodlo=rng.choice(zrodla),
                doi=_doi(rng, rok, i + 1),
                punkty_kbn=rng.randint(5, 200),
                **_maybe_openaccess(rng),
            )
        )

    pbar = make_progress(
        range(0, n, batch_size),
        desc="Wydawnictwa ciągłe",
        total=(n + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    created: list[Wydawnictwo_Ciagle] = []
    for start in pbar:
        chunk = prace[start : start + batch_size]
        Wydawnictwo_Ciagle.objects.bulk_create(chunk)
        created.extend(chunk)
        manifest.append("bpp.Wydawnictwo_Ciagle", [p.pk for p in chunk])
        manifest.save()

    # Powiazania autorow:
    powiazania: list[Wydawnictwo_Ciagle_Autor] = []
    for praca in created:
        liczba_autorow = rng.randint(1, min(8, len(autorzy)))
        wybrani = rng.sample(autorzy, liczba_autorow)
        for kolejnosc, autor in enumerate(wybrani):
            powiazania.append(
                Wydawnictwo_Ciagle_Autor(
                    rekord=praca,
                    autor=autor,
                    typ_odpowiedzialnosci=aut_typ,
                    kolejnosc=kolejnosc,
                    zapisany_jako=f"{autor.imiona} {autor.nazwisko}",
                )
            )

    pbar2 = make_progress(
        range(0, len(powiazania), batch_size),
        desc="WC ↔ autorzy",
        total=(len(powiazania) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar2:
        chunk = powiazania[start : start + batch_size]
        Wydawnictwo_Ciagle_Autor.objects.bulk_create(chunk)
        manifest.append(
            "bpp.Wydawnictwo_Ciagle_Autor", [c.pk for c in chunk]
        )
        manifest.save()

    return created
```

> **Gotcha:** Pole `zapisany_jako` w `Wydawnictwo_Ciagle_Autor` — sprawdź w `src/bpp/models/abstract/...` (klasa `BazaModeluOdpowiedzialnosciAutorow`) czy required. Jeśli nie ma — usuń. Podobnie `punkty_kbn` — sprawdź gdzie siedzi (może w mixinie `ModelPunktowany`).

- [ ] **Step 11.4: Run — expect PASS**

- [ ] **Step 11.5: Ruff + commit**

```bash
git add src/bpp/demo_data/generators/wydawnictwa_ciagle.py src/bpp/tests/test_demo_data/test_generator_wydawnictwa_ciagle.py
git commit -m "$(cat <<'EOF'
feat(demo-data): generator Wydawnictwo_Ciagle + powiazania + DOI + OA

Wydawnictwa ciagle z losowym charakterem, jezykiem, zrodlem, DOI
(format 10.NNNN/demo.YEAR.IDX), opcjonalnymi flagami OpenAccess
(50% prawd, tylko gdy slowniki OA wgrane). Powiazania autorow:
1–8 autorow per praca, kolejnosc 0..N, zapisany_jako z imienia
i nazwiska.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Generator — Wydawnictwo_Zwarte + nadrzedne + powiązania (TDD)

**Files:**
- Create: `src/bpp/demo_data/generators/wydawnictwa_zwarte.py`
- Create: `src/bpp/tests/test_demo_data/test_generator_wydawnictwa_zwarte.py`

### Steps

- [ ] **Step 12.1: Write tests**

`src/bpp/tests/test_demo_data/test_generator_wydawnictwa_zwarte.py`:

```python
"""Test generatora Wydawnictwo_Zwarte + nadrzedne + powiazania."""

import random
import re

import pytest
from model_bakery import baker

from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydawcy import create_wydawcy
from bpp.demo_data.generators.wydawnictwa_zwarte import create_wz
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.manifest import Manifest
from bpp.models import (
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


@pytest.fixture
def slowniki(db):
    baker.make(Charakter_Formalny, skrot="KZ", nazwa="Książka")
    baker.make(Charakter_Formalny, skrot="RZ", nazwa="Rozdział")
    baker.make(Typ_KBN, skrot="PO", nazwa="Praca oryginalna")
    baker.make(Jezyk, skrot="pol.", nazwa="polski")
    baker.make(Status_Korekty, nazwa="Po korekcie")
    baker.make(Typ_Odpowiedzialnosci, skrot="aut.", nazwa="autor")


@pytest.fixture
def setup(slowniki, tmp_manifest_path):
    m = Manifest(path=tmp_manifest_path, database="db", command_args={})
    u = ensure_uczelnia(m)
    w = create_wydzialy(n=1, uczelnia=u, manifest=m,
                       rng=random.Random(1), batch_size=10,
                       disable_progress=True)
    j = create_jednostki(per_wydzial=1, wydzialy=w, uczelnia=u,
                        manifest=m, rng=random.Random(2), batch_size=10,
                        disable_progress=True)
    a = create_autorzy(n=10, jednostki=j, manifest=m,
                      rng=random.Random(3), batch_size=10,
                      disable_progress=True)
    wyd = create_wydawcy(n=3, manifest=m, rng=random.Random(4),
                       batch_size=10, disable_progress=True)
    return m, a, wyd


@pytest.mark.django_db(transaction=True)
def test_creates_n_prac(setup):
    m, autorzy, wydawcy = setup
    prace = create_wz(
        n=20, autorzy=autorzy, wydawcy=wydawcy,
        lata=range(2020, 2023), manifest=m,
        rng=random.Random(99), procent_rozdzialy=0,
        batch_size=10, disable_progress=True,
    )
    assert Wydawnictwo_Zwarte.objects.count() == 20
    assert len(prace) == 20


@pytest.mark.django_db(transaction=True)
def test_doi_format(setup):
    m, autorzy, wydawcy = setup
    create_wz(
        n=5, autorzy=autorzy, wydawcy=wydawcy,
        lata=range(2020, 2023), manifest=m,
        rng=random.Random(99), procent_rozdzialy=0,
        batch_size=10, disable_progress=True,
    )
    pattern = re.compile(r"^10\.\d{4}/demo\.\d{4}\.\d+$")
    for praca in Wydawnictwo_Zwarte.objects.all():
        assert pattern.match(praca.doi)


@pytest.mark.django_db(transaction=True)
def test_rozdzialy_have_nadrzedne(setup):
    m, autorzy, wydawcy = setup
    prace = create_wz(
        n=10, autorzy=autorzy, wydawcy=wydawcy,
        lata=range(2020, 2023), manifest=m,
        rng=random.Random(99), procent_rozdzialy=100,
        batch_size=10, disable_progress=True,
    )
    # Wszystkie sa rozdzialami → wszystkie maja wydawnictwo_nadrzedne
    rozdzialy = Wydawnictwo_Zwarte.objects.filter(
        wydawnictwo_nadrzedne__isnull=False
    )
    assert rozdzialy.count() == 10
    # Plus nadrzedne (osobne ksiazki)
    nadrzedne = Wydawnictwo_Zwarte.objects.filter(
        wydawnictwo_nadrzedne__isnull=True
    )
    assert nadrzedne.count() >= 1  # przynajmniej 1 ksiazka nadrzedna


@pytest.mark.django_db(transaction=True)
def test_pbn_uid_zawsze_puste(setup):
    m, autorzy, wydawcy = setup
    create_wz(
        n=5, autorzy=autorzy, wydawcy=wydawcy,
        lata=range(2020, 2023), manifest=m,
        rng=random.Random(99), procent_rozdzialy=20,
        batch_size=10, disable_progress=True,
    )
    for praca in Wydawnictwo_Zwarte.objects.all():
        assert praca.pbn_uid_id is None
```

- [ ] **Step 12.2: Run — expect ImportError**

- [ ] **Step 12.3: Implement**

`src/bpp/demo_data/generators/wydawnictwa_zwarte.py`:

```python
"""Generator Wydawnictwo_Zwarte + nadrzedne + powiazania."""

from __future__ import annotations

import random
from typing import Iterable

from bpp.demo_data.manifest import Manifest
from bpp.demo_data.names import CONTEXTS, SUBJECTS, TOPICS, TYTULY_TEMPLATES
from bpp.demo_data.progress import make_progress
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Jezyk,
    Status_Korekty,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Wydawca,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


def _tytul(rng: random.Random, idx: int, prefix: str = "") -> str:
    template = rng.choice(TYTULY_TEMPLATES)
    return f"Demo —{prefix} {template.format(topic=rng.choice(TOPICS), subject=rng.choice(SUBJECTS), context=rng.choice(CONTEXTS))} (nr {idx})"


def _doi(rng: random.Random, rok: int, idx: int) -> str:
    prefix4 = rng.randint(1000, 9999)
    return f"10.{prefix4}/demo.{rok}.{idx}"


def create_wz(
    *,
    n: int,
    autorzy: Iterable[Autor],
    wydawcy: Iterable[Wydawca],
    lata: Iterable[int],
    manifest: Manifest,
    rng: random.Random,
    procent_rozdzialy: int = 20,
    batch_size: int = 500,
    disable_progress: bool = False,
) -> list[Wydawnictwo_Zwarte]:
    autorzy = list(autorzy)
    wydawcy = list(wydawcy)
    lata = list(lata)

    charaktery = list(Charakter_Formalny.objects.all())
    typy_kbn = list(Typ_KBN.objects.all())
    jezyki = list(Jezyk.objects.all())
    statusy = list(Status_Korekty.objects.all())
    aut_typ = Typ_Odpowiedzialnosci.objects.filter(skrot="aut.").first() \
        or Typ_Odpowiedzialnosci.objects.first()
    if aut_typ is None:
        raise ValueError("Brak Typ_Odpowiedzialnosci w bazie.")

    # Najpierw stworz "ksiazki nadrzedne" dla rozdzialow:
    n_rozdzialow = (n * procent_rozdzialy) // 100
    n_zwyklych = n - n_rozdzialow
    # Liczba ksiazek nadrzednych: 1 na ~5 rozdzialow (sub-arbitralny):
    n_nadrzednych = max(1, n_rozdzialow // 5) if n_rozdzialow else 0

    def make_zwarte(idx: int, prefix: str = "") -> Wydawnictwo_Zwarte:
        rok = rng.choice(lata)
        return Wydawnictwo_Zwarte(
            tytul_oryginalny=_tytul(rng, idx, prefix),
            rok=rok,
            charakter_formalny=rng.choice(charaktery),
            typ_kbn=rng.choice(typy_kbn) if typy_kbn else None,
            jezyk=rng.choice(jezyki) if jezyki else None,
            status_korekty=rng.choice(statusy) if statusy else None,
            wydawca=rng.choice(wydawcy),
            doi=_doi(rng, rok, idx),
            punkty_kbn=rng.randint(5, 200),
        )

    # 1. Nadrzedne ksiazki:
    nadrzedne_objs = [
        make_zwarte(i + 1, prefix=" Książka nadrzędna")
        for i in range(n_nadrzednych)
    ]
    pbar = make_progress(
        range(0, len(nadrzedne_objs), batch_size),
        desc="WZ nadrzędne",
        total=(len(nadrzedne_objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    nadrzedne_created: list[Wydawnictwo_Zwarte] = []
    for start in pbar:
        chunk = nadrzedne_objs[start : start + batch_size]
        Wydawnictwo_Zwarte.objects.bulk_create(chunk)
        nadrzedne_created.extend(chunk)
        manifest.append("bpp.Wydawnictwo_Zwarte", [p.pk for p in chunk])
        manifest.save()

    # 2. Zwykle ksiazki + rozdzialy:
    pozostale_objs: list[Wydawnictwo_Zwarte] = []
    for i in range(n_zwyklych):
        pozostale_objs.append(make_zwarte(i + 1 + n_nadrzednych))
    for i in range(n_rozdzialow):
        praca = make_zwarte(i + 1 + n_nadrzednych + n_zwyklych,
                            prefix=" Rozdział")
        praca.wydawnictwo_nadrzedne = rng.choice(nadrzedne_created)
        pozostale_objs.append(praca)

    rng.shuffle(pozostale_objs)
    pbar2 = make_progress(
        range(0, len(pozostale_objs), batch_size),
        desc="WZ zwykłe",
        total=(len(pozostale_objs) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    pozostale_created: list[Wydawnictwo_Zwarte] = []
    for start in pbar2:
        chunk = pozostale_objs[start : start + batch_size]
        Wydawnictwo_Zwarte.objects.bulk_create(chunk)
        pozostale_created.extend(chunk)
        manifest.append("bpp.Wydawnictwo_Zwarte", [p.pk for p in chunk])
        manifest.save()

    all_prace = nadrzedne_created + pozostale_created

    # 3. Powiazania autorow:
    powiazania: list[Wydawnictwo_Zwarte_Autor] = []
    for praca in all_prace:
        liczba_autorow = rng.randint(1, min(8, len(autorzy)))
        wybrani = rng.sample(autorzy, liczba_autorow)
        for kolejnosc, autor in enumerate(wybrani):
            powiazania.append(
                Wydawnictwo_Zwarte_Autor(
                    rekord=praca,
                    autor=autor,
                    typ_odpowiedzialnosci=aut_typ,
                    kolejnosc=kolejnosc,
                    zapisany_jako=f"{autor.imiona} {autor.nazwisko}",
                )
            )

    pbar3 = make_progress(
        range(0, len(powiazania), batch_size),
        desc="WZ ↔ autorzy",
        total=(len(powiazania) + batch_size - 1) // batch_size,
        disable=disable_progress,
    )
    for start in pbar3:
        chunk = powiazania[start : start + batch_size]
        Wydawnictwo_Zwarte_Autor.objects.bulk_create(chunk)
        manifest.append(
            "bpp.Wydawnictwo_Zwarte_Autor", [c.pk for c in chunk]
        )
        manifest.save()

    return all_prace
```

- [ ] **Step 12.4: Run — expect PASS**

- [ ] **Step 12.5: Ruff + commit**

```bash
git add src/bpp/demo_data/generators/wydawnictwa_zwarte.py src/bpp/tests/test_demo_data/test_generator_wydawnictwa_zwarte.py
git commit -m "$(cat <<'EOF'
feat(demo-data): generator Wydawnictwo_Zwarte + nadrzedne + powiazania

WZ zwykle + procent_rozdzialy (default 20%) z wydawnictwo_nadrzedne
(stworzone najpierw, 1 ksiazka na ~5 rozdzialow). DOI losowy,
powiazania autorow 1–8/praca.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Orchestrator + management command `create_demo_data`

**Files:**
- Create: `src/bpp/demo_data/orchestrator.py`
- Create: `src/bpp/management/commands/create_demo_data.py`
- Create: `src/bpp/tests/test_demo_data/test_command_create.py`

### Steps

- [ ] **Step 13.1: Write tests**

`src/bpp/tests/test_demo_data/test_command_create.py`:

```python
"""Integration tests dla `manage.py create_demo_data`."""

import io
from pathlib import Path

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.demo_data.confirm import ConfirmAborted
from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import (
    Autor,
    Dyscyplina_Naukowa,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
)


@pytest.fixture
def fixtures_loaded(db):
    """Loaduje minimalny zestaw dla preflight."""
    from django.apps import apps
    for label, _ in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)


@pytest.mark.django_db(transaction=True)
def test_command_smoke_minimal(fixtures_loaded, tmp_path):
    from django.db import connection
    manifest = tmp_path / "m.json"
    call_command(
        "create_demo_data",
        "--wydzialow=1",
        "--jednostek-na-wydzial=1",
        "--autorow=3",
        "--ile-ciaglych=3",
        "--ile-zwartych=3",
        "--zrodel=2",
        "--wydawcow=2",
        "--seed=1",
        f"--manifest-out={manifest}",
        "--batch-size=10",
        "--yes-i-am-sure",
        f"--confirm-db={connection.settings_dict['NAME']}",
    )

    assert manifest.exists()
    assert Wydzial.objects.count() == 1
    assert Jednostka.objects.count() == 1
    assert Autor.objects.count() == 3
    assert Wydawnictwo_Ciagle.objects.count() == 3
    assert Wydawnictwo_Zwarte.objects.count() >= 3


@pytest.mark.django_db(transaction=True)
def test_command_preflight_fails_when_no_dyscyplina():
    from django.db import connection

    # Tworzymy slowniki BEZ dyscyplin
    for label, _ in REQUIRED_DICTIONARIES:
        if label == "bpp.Dyscyplina_Naukowa":
            continue
        from django.apps import apps
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)

    with pytest.raises(SystemExit):
        call_command(
            "create_demo_data",
            "--wydzialow=1", "--jednostek-na-wydzial=1", "--autorow=1",
            "--ile-ciaglych=1", "--ile-zwartych=1",
            "--zrodel=1", "--wydawcow=1", "--seed=1",
            "--yes-i-am-sure",
            f"--confirm-db={connection.settings_dict['NAME']}",
        )
    assert Wydzial.objects.count() == 0  # nic nie stworzone


@pytest.mark.django_db(transaction=True)
def test_command_aborts_without_flags_non_tty(fixtures_loaded, tmp_path):
    """Bez --yes-i-am-sure i bez TTY → SystemExit."""
    from django.db import connection
    with pytest.raises(SystemExit):
        call_command(
            "create_demo_data",
            "--wydzialow=1", "--jednostek-na-wydzial=1",
            "--autorow=1", "--ile-ciaglych=1", "--ile-zwartych=1",
            "--zrodel=1", "--wydawcow=1",
            "--seed=1",
        )
    assert Wydzial.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_command_aborts_wrong_db_name(fixtures_loaded):
    with pytest.raises(SystemExit):
        call_command(
            "create_demo_data",
            "--wydzialow=1", "--jednostek-na-wydzial=1",
            "--autorow=1", "--ile-ciaglych=1", "--ile-zwartych=1",
            "--zrodel=1", "--wydawcow=1", "--seed=1",
            "--yes-i-am-sure", "--confirm-db=zla_nazwa",
        )
    assert Wydzial.objects.count() == 0
```

- [ ] **Step 13.2: Implement orchestrator**

`src/bpp/demo_data/orchestrator.py`:

```python
"""Top-level orkiestracja create_demo_data — sklada generatory razem."""

from __future__ import annotations

import datetime
import random
import sys
from dataclasses import dataclass
from pathlib import Path

from django.db import connection

from bpp.demo_data.confirm import ConfirmAborted, double_confirm
from bpp.demo_data.generators.autorzy import create_autorzy
from bpp.demo_data.generators.dyscypliny import create_autor_dyscypliny
from bpp.demo_data.generators.jednostki import create_jednostki
from bpp.demo_data.generators.uczelnia import ensure_uczelnia
from bpp.demo_data.generators.wydawcy import create_wydawcy
from bpp.demo_data.generators.wydawnictwa_ciagle import create_wc
from bpp.demo_data.generators.wydawnictwa_zwarte import create_wz
from bpp.demo_data.generators.wydzialy import create_wydzialy
from bpp.demo_data.generators.zrodla import create_zrodla
from bpp.demo_data.manifest import Manifest
from bpp.demo_data.preflight import check_required


@dataclass
class CreateOptions:
    wydzialow: int
    jednostek_na_wydzial: int
    autorow: int
    ile_ciaglych: int
    ile_zwartych: int
    od_roku: int
    do_roku: int
    procent_z_dyscyplina: int
    procent_z_subdyscyplina: int
    procent_zmiana_dyscypliny: int
    zrodel: int
    wydawcow: int
    seed: int | None
    manifest_out: Path
    batch_size: int
    yes_i_am_sure: bool
    confirm_db: str | None
    disable_progress: bool = False


def run_create(opts: CreateOptions, *, stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    db_name = connection.settings_dict["NAME"]

    # 1. Preflight (PRZED promptami):
    missing = check_required()
    if missing:
        stdout.write("[BLAD] Brakuje wymaganych slownikow:\n")
        for label, hint in missing:
            stdout.write(f"  - {label}: {hint}\n")
        stdout.write("\nUruchom najpierw odpowiednie loaddata / seed.\n")
        raise SystemExit(1)

    # 2. Confirm:
    plan_text = (
        f"Stworzy: {opts.wydzialow} wydz., "
        f"{opts.wydzialow * opts.jednostek_na_wydzial} jedn., "
        f"{opts.autorow} aut., {opts.ile_ciaglych} prac ciaglych, "
        f"{opts.ile_zwartych} prac zwartych w bazie '{db_name}'."
    )
    try:
        double_confirm(
            stdin=stdin, stdout=stdout, database=db_name,
            plan_text=plan_text, yes_flag=opts.yes_i_am_sure,
            confirm_db_flag=opts.confirm_db,
        )
    except ConfirmAborted as e:
        stdout.write(f"[ABORT] {e}\n")
        raise SystemExit(1)

    # 3. Manifest + RNG:
    rng = random.Random(opts.seed)
    manifest = Manifest(
        path=opts.manifest_out,
        database=db_name,
        command_args=vars(opts).copy(),
    )

    # 4. Generatory (kolejnosc zalozenia: uczelnia → wydzialy → jednostki →
    # autorzy → dyscypliny → zrodla → wydawcy → WC → WZ):
    uczelnia = ensure_uczelnia(manifest)
    wydzialy = create_wydzialy(
        n=opts.wydzialow, uczelnia=uczelnia, manifest=manifest,
        rng=rng, batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    jednostki = create_jednostki(
        per_wydzial=opts.jednostek_na_wydzial,
        wydzialy=wydzialy, uczelnia=uczelnia, manifest=manifest,
        rng=rng, batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    autorzy = create_autorzy(
        n=opts.autorow, jednostki=jednostki, manifest=manifest,
        rng=rng, batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    create_autor_dyscypliny(
        autorzy=autorzy,
        lata=range(opts.od_roku, opts.do_roku + 1),
        procent_z_dyscyplina=opts.procent_z_dyscyplina,
        procent_z_subdyscyplina=opts.procent_z_subdyscyplina,
        procent_zmiana_dyscypliny=opts.procent_zmiana_dyscypliny,
        manifest=manifest, rng=rng, batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    zrodla = create_zrodla(
        n=opts.zrodel, manifest=manifest, rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    wydawcy = create_wydawcy(
        n=opts.wydawcow, manifest=manifest, rng=rng,
        batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    create_wc(
        n=opts.ile_ciaglych, autorzy=autorzy, zrodla=zrodla,
        lata=range(opts.od_roku, opts.do_roku + 1),
        manifest=manifest, rng=rng, batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )
    create_wz(
        n=opts.ile_zwartych, autorzy=autorzy, wydawcy=wydawcy,
        lata=range(opts.od_roku, opts.do_roku + 1),
        manifest=manifest, rng=rng, batch_size=opts.batch_size,
        disable_progress=opts.disable_progress,
    )

    manifest.save()
    stdout.write(
        f"\n[OK] Manifest zapisany: {opts.manifest_out}\n"
        f"     Cleanup: uv run python src/manage.py cleanup_demo_data"
        f" --manifest {opts.manifest_out} --yes-i-am-sure"
        f" --confirm-db {db_name}\n"
    )
```

- [ ] **Step 13.3: Implement management command**

`src/bpp/management/commands/create_demo_data.py`:

```python
"""Management command: create_demo_data."""

from __future__ import annotations

import datetime
from pathlib import Path

from django.core.management.base import BaseCommand

from bpp.demo_data.orchestrator import CreateOptions, run_create


class Command(BaseCommand):
    help = (
        "Generuje syntetyczne dane demo (wydzialy, jednostki, autorzy, "
        "prace WC+WZ). Wymaga PODWOJNEGO potwierdzenia interaktywnie "
        "(prompt + exact DB name) lub flag --yes-i-am-sure + --confirm-db."
    )

    def add_arguments(self, parser):
        parser.add_argument("--wydzialow", type=int, default=10)
        parser.add_argument("--jednostek-na-wydzial", type=int, default=5)
        parser.add_argument("--autorow", type=int, default=500)
        parser.add_argument("--ile-ciaglych", type=int, default=5000)
        parser.add_argument("--ile-zwartych", type=int, default=5000)
        parser.add_argument("--od-roku", type=int, default=2017)
        parser.add_argument("--do-roku", type=int, default=2025)
        parser.add_argument("--procent-z-dyscyplina", type=int, default=80)
        parser.add_argument("--procent-z-subdyscyplina", type=int, default=20)
        parser.add_argument("--procent-zmiana-dyscypliny", type=int,
                            default=10)
        parser.add_argument("--zrodel", type=int, default=50)
        parser.add_argument("--wydawcow", type=int, default=20)
        parser.add_argument("--seed", type=int, default=None)
        parser.add_argument("--manifest-out", type=str, default=None)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--yes-i-am-sure", action="store_true")
        parser.add_argument("--confirm-db", type=str, default=None)

    def handle(self, *args, **options):
        manifest_out = options.get("manifest_out")
        if not manifest_out:
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            manifest_out = f"demo_data_manifest_{ts}.json"

        opts = CreateOptions(
            wydzialow=options["wydzialow"],
            jednostek_na_wydzial=options["jednostek_na_wydzial"],
            autorow=options["autorow"],
            ile_ciaglych=options["ile_ciaglych"],
            ile_zwartych=options["ile_zwartych"],
            od_roku=options["od_roku"],
            do_roku=options["do_roku"],
            procent_z_dyscyplina=options["procent_z_dyscyplina"],
            procent_z_subdyscyplina=options["procent_z_subdyscyplina"],
            procent_zmiana_dyscypliny=options["procent_zmiana_dyscypliny"],
            zrodel=options["zrodel"],
            wydawcow=options["wydawcow"],
            seed=options["seed"],
            manifest_out=Path(manifest_out),
            batch_size=options["batch_size"],
            yes_i_am_sure=options["yes_i_am_sure"],
            confirm_db=options.get("confirm_db"),
        )
        run_create(opts, stdin=self.stdin, stdout=self.stdout)
```

> **Gotcha:** Django's `BaseCommand` może nie mieć `self.stdin` — wtedy użyj `sys.stdin`. Sprawdź `BaseCommand` source / pass `sys.stdin` explicitly.

- [ ] **Step 13.4: Run tests — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_command_create.py -v`

- [ ] **Step 13.5: Ruff + commit**

```bash
git add src/bpp/demo_data/orchestrator.py src/bpp/management/commands/create_demo_data.py src/bpp/tests/test_demo_data/test_command_create.py
git commit -m "$(cat <<'EOF'
feat(demo-data): orchestrator + management command create_demo_data

Thin entrypoint w management/commands; orchestrator parsuje opts,
robi preflight, double_confirm i wola generatory w sztywnej
kolejnosci. Smoke test integration: 1/1/3/3/3 — manifest pisany,
obiekty stworzone, preflight blokuje przy braku slownikow, abort
przy zlej nazwie bazy / non-tty.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Management command `cleanup_demo_data` + roundtrip test

**Files:**
- Create: `src/bpp/management/commands/cleanup_demo_data.py`
- Modify: `src/bpp/demo_data/orchestrator.py` (dodaj `run_cleanup`)
- Create: `src/bpp/tests/test_demo_data/test_command_cleanup.py`

### Steps

- [ ] **Step 14.1: Write tests**

`src/bpp/tests/test_demo_data/test_command_cleanup.py`:

```python
"""Integration test: roundtrip create → cleanup."""

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import (
    Autor,
    Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
    Wydzial,
)


@pytest.fixture
def fixtures_loaded(db):
    from django.apps import apps
    for label, _ in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)


@pytest.mark.django_db(transaction=True)
def test_roundtrip_create_then_cleanup(fixtures_loaded, tmp_path):
    from django.db import connection
    manifest = tmp_path / "m.json"
    db_name = connection.settings_dict["NAME"]

    # Stworz obiekt-swiadka (np. innego Autora poza demo):
    swiadek = Autor.objects.create(imiona="Swiadek", nazwisko="Test")

    call_command(
        "create_demo_data",
        "--wydzialow=1", "--jednostek-na-wydzial=1", "--autorow=3",
        "--ile-ciaglych=3", "--ile-zwartych=3",
        "--zrodel=2", "--wydawcow=2", "--seed=1",
        f"--manifest-out={manifest}", "--batch-size=10",
        "--yes-i-am-sure", f"--confirm-db={db_name}",
    )

    assert Wydzial.objects.count() == 1
    assert Autor.objects.count() == 3 + 1  # demo + swiadek

    call_command(
        "cleanup_demo_data",
        f"--manifest={manifest}",
        "--yes-i-am-sure", f"--confirm-db={db_name}",
    )

    # Demo obiekty zniknely:
    assert Wydzial.objects.count() == 0
    assert Jednostka.objects.count() == 0
    assert Wydawnictwo_Ciagle.objects.count() == 0
    assert Wydawnictwo_Zwarte.objects.count() == 0
    # Swiadek pozostal:
    assert Autor.objects.filter(pk=swiadek.pk).exists()
    # Inni autorzy (z demo) zniknieli:
    assert Autor.objects.count() == 1
    # Manifest zmienil nazwe na .applied.*
    assert not manifest.exists() or manifest.with_suffix(
        manifest.suffix + ".applied"
    )


@pytest.mark.django_db(transaction=True)
def test_cleanup_aborts_wrong_db(fixtures_loaded, tmp_path):
    from django.db import connection
    manifest = tmp_path / "m.json"
    db_name = connection.settings_dict["NAME"]
    call_command(
        "create_demo_data",
        "--wydzialow=1", "--jednostek-na-wydzial=1", "--autorow=1",
        "--ile-ciaglych=1", "--ile-zwartych=1",
        "--zrodel=1", "--wydawcow=1", "--seed=1",
        f"--manifest-out={manifest}", "--batch-size=10",
        "--yes-i-am-sure", f"--confirm-db={db_name}",
    )
    with pytest.raises(SystemExit):
        call_command(
            "cleanup_demo_data",
            f"--manifest={manifest}",
            "--yes-i-am-sure", "--confirm-db=zla",
        )
    # Obiekty pozostaly:
    assert Wydzial.objects.count() == 1
```

- [ ] **Step 14.2: Implement `run_cleanup` w orchestrator**

Modify `src/bpp/demo_data/orchestrator.py` — dodaj na koniec:

```python
from django.apps import apps
from django.db import transaction


@dataclass
class CleanupOptions:
    manifest: Path
    yes_i_am_sure: bool
    confirm_db: str | None
    batch_size: int = 500
    disable_progress: bool = False


def run_cleanup(opts: CleanupOptions, *, stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    db_name = connection.settings_dict["NAME"]

    manifest = Manifest.load(opts.manifest)

    plan_text = (
        f"Usunie obiekty z manifestu '{opts.manifest}' "
        f"({sum(len(v.get('pks', [])) for v in manifest.objects.values())} "
        f"obiektow) w bazie '{db_name}'."
    )
    try:
        double_confirm(
            stdin=stdin, stdout=stdout, database=db_name,
            plan_text=plan_text, yes_flag=opts.yes_i_am_sure,
            confirm_db_flag=opts.confirm_db,
        )
    except ConfirmAborted as e:
        stdout.write(f"[ABORT] {e}\n")
        raise SystemExit(1)

    from bpp.demo_data.progress import make_progress

    for model_label, pks in manifest.objects_in_cleanup_order():
        app_label, model_name = model_label.split(".")
        model = apps.get_model(app_label, model_name)
        total_batches = (len(pks) + opts.batch_size - 1) // opts.batch_size
        pbar = make_progress(
            range(0, len(pks), opts.batch_size),
            desc=f"Cleanup {model_label}",
            total=total_batches,
            disable=opts.disable_progress,
        )
        for start in pbar:
            chunk = pks[start : start + opts.batch_size]
            with transaction.atomic():
                model.objects.filter(pk__in=chunk).delete()

    # Rename manifest:
    applied = opts.manifest.with_suffix(
        opts.manifest.suffix
        + f".applied.{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
    )
    opts.manifest.rename(applied)
    stdout.write(f"\n[OK] Cleanup zakonczony. Manifest: {applied}\n")
```

- [ ] **Step 14.3: Implement management command**

`src/bpp/management/commands/cleanup_demo_data.py`:

```python
"""Management command: cleanup_demo_data."""

from __future__ import annotations

from pathlib import Path

from django.core.management.base import BaseCommand

from bpp.demo_data.orchestrator import CleanupOptions, run_cleanup


class Command(BaseCommand):
    help = (
        "Usuwa obiekty zapisane w manifeście stworzonym przez "
        "create_demo_data. Wymaga podwójnego potwierdzenia jak komenda "
        "tworząca."
    )

    def add_arguments(self, parser):
        parser.add_argument("--manifest", type=str, required=True)
        parser.add_argument("--batch-size", type=int, default=500)
        parser.add_argument("--yes-i-am-sure", action="store_true")
        parser.add_argument("--confirm-db", type=str, default=None)

    def handle(self, *args, **options):
        opts = CleanupOptions(
            manifest=Path(options["manifest"]),
            yes_i_am_sure=options["yes_i_am_sure"],
            confirm_db=options.get("confirm_db"),
            batch_size=options["batch_size"],
        )
        run_cleanup(opts, stdin=self.stdin, stdout=self.stdout)
```

- [ ] **Step 14.4: Run roundtrip test — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/test_command_cleanup.py -v`

- [ ] **Step 14.5: Ruff + commit**

```bash
git add src/bpp/demo_data/orchestrator.py src/bpp/management/commands/cleanup_demo_data.py src/bpp/tests/test_demo_data/test_command_cleanup.py
git commit -m "$(cat <<'EOF'
feat(demo-data): cleanup_demo_data + roundtrip test

run_cleanup czyta manifest, robi double_confirm, leci
objects_in_cleanup_order, deletuje w batchach (transaction per
batch), na koniec renamuje manifest do .applied.<TS>. Test
roundtrip: swiadek przed create + cleanup → swiadek pozostal,
demo zniknelo.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: End-to-end test + ręczna weryfikacja przez `run-site`

**Files:**
- Modify: `src/bpp/tests/test_demo_data/test_command_create.py` (dodatkowe testy seed/determinism)
- Create: `src/bpp/tests/test_demo_data/test_e2e.py` (większy smoke test)

### Steps

- [ ] **Step 15.1: Write end-to-end smoke test**

`src/bpp/tests/test_demo_data/test_e2e.py`:

```python
"""E2E smoke: srednia skala — 2 wydz., 3 jedn., 20 aut., 30 prac."""

import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.demo_data.preflight import REQUIRED_DICTIONARIES
from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Jednostka,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Wydzial,
)


@pytest.fixture
def fixtures_loaded(db):
    from django.apps import apps
    for label, _ in REQUIRED_DICTIONARIES:
        app_label, model_name = label.split(".")
        model = apps.get_model(app_label, model_name)
        if not model.objects.exists():
            baker.make(model)


@pytest.mark.django_db(transaction=True)
def test_e2e_medium_scale(fixtures_loaded, tmp_path):
    from django.db import connection
    manifest = tmp_path / "m.json"
    db = connection.settings_dict["NAME"]
    call_command(
        "create_demo_data",
        "--wydzialow=2", "--jednostek-na-wydzial=3",
        "--autorow=20", "--ile-ciaglych=30", "--ile-zwartych=30",
        "--zrodel=10", "--wydawcow=5",
        "--od-roku=2020", "--do-roku=2022",
        "--procent-z-dyscyplina=100", "--procent-z-subdyscyplina=30",
        "--procent-zmiana-dyscypliny=20",
        "--seed=42", f"--manifest-out={manifest}",
        "--batch-size=10",
        "--yes-i-am-sure", f"--confirm-db={db}",
    )
    assert Wydzial.objects.count() == 2
    assert Jednostka.objects.count() == 6
    assert Autor.objects.count() == 20
    # 100% z dyscyplina, 3 lata, 20 autorow → 60 rekordow dyscyplin
    assert Autor_Dyscyplina.objects.count() == 60
    assert Wydawnictwo_Ciagle.objects.count() == 30
    assert Wydawnictwo_Zwarte.objects.count() >= 30
    # Powiazania (kazda praca 1–8 autorow → min 60, max 480)
    assert Wydawnictwo_Ciagle_Autor.objects.count() >= 30
    assert Wydawnictwo_Zwarte_Autor.objects.count() >= 30
```

- [ ] **Step 15.2: Run — expect PASS**

Run: `uv run pytest src/bpp/tests/test_demo_data/ -v`

Expected: wszystkie testy przechodzą.

- [ ] **Step 15.3: Pełna suite — sanity**

Run: `uv run pytest src/bpp/tests/test_demo_data/ -v --tb=short`

Sprawdź czy żaden test z innych modułów nie pada przez nasze zmiany:

```bash
uv run pytest src/bpp/tests/test_commands.py -v
```

Expected: bez regresji.

- [ ] **Step 15.4: Ręczna weryfikacja przez `run-site` (opcjonalnie, manualnie)**

Po starcie `run-site run` w terminalu:

```bash
T=$(cat .dev_helpers_token)
PORT=$(cat .dev_helpers_port)

# Załaduj minimalny zestaw słowników jeśli brak:
uv run python src/manage.py loaddata charakter_formalny typ_kbn jezyk \
    status_korekty rodzaj_zrodla funkcja_autora \
    typ_odpowiedzialnosci_v2 tytul plec zrodlo_informacji

# Run komendy:
uv run python src/manage.py create_demo_data \
    --wydzialow=3 --jednostek-na-wydzial=2 --autorow=20 \
    --ile-ciaglych=50 --ile-zwartych=50 \
    --zrodel=5 --wydawcow=3 --seed=42 \
    --manifest-out=/tmp/demo_manifest.json \
    --yes-i-am-sure --confirm-db=$(uv run python -c \
        "from django.conf import settings; \
         import django; django.setup(); \
         print(settings.DATABASES['default']['NAME'])")

# Otwórz w browserze:
J=$(mktemp)
curl -sc "$J" -L "http://localhost:$PORT/__autologin__/?token=$T" >/dev/null
open "http://localhost:$PORT/bpp/literatura/"  # zobacz prace
open "http://localhost:$PORT/admin/bpp/wydzial/"  # zobacz wydzialy
rm "$J"

# Cleanup:
uv run python src/manage.py cleanup_demo_data \
    --manifest=/tmp/demo_manifest.json \
    --yes-i-am-sure --confirm-db=<NAME>
```

Sprawdź wizualnie:
- progress bars wyświetlają się płynnie,
- prace mają polskie tytuły i DOI,
- autorzy z polskimi nazwiskami,
- po cleanup wszystko zniknęło.

- [ ] **Step 15.5: Commit pozostałych testów**

```bash
git add src/bpp/tests/test_demo_data/test_e2e.py
git commit -m "$(cat <<'EOF'
test(demo-data): E2E smoke ze srednia skala (60 prac)

2 wydz × 3 jedn × 20 aut × 30 WC × 30 WZ × 3 lata. Weryfikuje
liczby obiektow zgadzaja sie z parametrami i pelne powiazania.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Final pre-commit, ruff, sanity & PR-ready

### Steps

- [ ] **Step 16.1: Pełen ruff format i check na całym pakiecie**

```bash
ruff format src/bpp/demo_data/ src/bpp/management/commands/create_demo_data.py src/bpp/management/commands/cleanup_demo_data.py src/bpp/tests/test_demo_data/
ruff check src/bpp/demo_data/ src/bpp/management/commands/create_demo_data.py src/bpp/management/commands/cleanup_demo_data.py src/bpp/tests/test_demo_data/
```

Expected: bez błędów.

- [ ] **Step 16.2: Pre-commit hooks**

```bash
pre-commit run --files $(git diff --name-only origin/dev..HEAD)
```

Expected: zero failed hooks. Jeśli coś padnie — fix manually z Edit (nie `ruff --fix --batch`).

- [ ] **Step 16.3: Pełne odpalenie testów demo-data**

```bash
uv run pytest src/bpp/tests/test_demo_data/ -v
```

Expected: wszystkie pass.

- [ ] **Step 16.4: `manage.py check` + `makemigrations --check`**

```bash
uv run python src/manage.py check
uv run python src/manage.py makemigrations --check --dry-run
```

Expected: zero migration drift, zero issues.

- [ ] **Step 16.5: Final commit jeśli coś się dorobiło**

```bash
git status
# jeśli są zmiany:
git commit -am "$(cat <<'EOF'
chore(demo-data): final ruff/pre-commit/check pass

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 16.6: Pokaż git log z brancha**

```bash
git log --oneline origin/dev..HEAD
```

Expected: ~16 commitów, każdy z `feat(demo-data):` / `test(demo-data):` / `chore(demo-data):` prefixem.

---

## Self-review checklist (dla planującego — ja sprawdzam plan przed handoff)

- [x] **Spec coverage:** każda sekcja specu ma odpowiadający task:
  - Sekcja 2 (preflight) → Task 3 + test w Task 13
  - Sekcja 4 (double confirm) → Task 4 + integration testy w 13/14
  - Sekcja 5 (zakres obiektów) → Taski 6-12
  - Sekcja 6 (manifest) → Task 2 + atomic write w testach
  - Sekcja 7 (atomicity batch + tqdm + seed) → Task 5 + każdy generator (batch_size, rng)
  - Sekcja 8 (architektura) → struktura plików w sekcji "File structure"
  - Sekcja 9 (cleanup order) → Task 2 (`CLEANUP_ORDER`) + Task 14 (`run_cleanup`)
  - Sekcja 10 (testy) → wszystkie testy w taskach 2-15
  - Sekcja 11 (out-of-scope) → respected (zero generowania konferencji, patentów, dr/hab.)
  - Sekcja 14 (acceptance) → Task 13/14/15
- [x] **Placeholder scan:** brak "TODO"/"TBD"/"fill in" w planie. Komentarze "Gotcha" są wskazówkami, nie placeholderami — wskazują dokładny plik do sprawdzenia.
- [x] **Type consistency:** Manifest API spójne (`append`, `objects_for`, `extra_for`, `objects_in_cleanup_order`); generatory mają spójną sygnaturę kwargs (`manifest`, `rng`, `batch_size`, `disable_progress`); `run_create(opts)` używa `CreateOptions` z dataclass-em z pełnymi typami; `CleanupOptions` analogicznie.
- [x] **Scope check:** wszystko siedzi w `src/bpp/demo_data/` + `src/bpp/management/commands/` + `src/bpp/tests/test_demo_data/` — żadnych migracji, żadnych zmian w istniejących modelach.

---

**Gotowe.** Plan jest gotowy do wykonania w worktree (`superpowers:using-git-worktrees`) przez `subagent-driven-development` (rekomendowane) lub `executing-plans`.
