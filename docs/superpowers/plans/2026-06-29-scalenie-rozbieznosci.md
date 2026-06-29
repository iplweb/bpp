# Scalenie „rozbieżności punktacji/kwartyli" — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zastąpić dwie osobne opcje menu („rozbieżności punktacji IF" i „rozbieżności punktacji MNiSW") jedną opcją „rozbieżności punktacji/kwartyli", obejmującą 4 metryki (IF, punkty MNiSW, kwartyl Scopus, kwartyl WoS), z domyślnym filtrem ukrywającym rekordy, w których źródło ma `0` lub brak wartości.

**Architecture:** Nowa aplikacja `src/rozbieznosci/` z rejestrem metryk (dataclass), uogólnionymi widokami klasowymi czytającymi metrykę ze sluga w URL-u, wspólnymi modelami z dyskryminatorem `metryka`, jednym kompletem szablonów z zakładkami. Stare aplikacje `rozbieznosci_if` i `rozbieznosci_pk` usuwane (start od zera, bez migracji danych).

**Tech Stack:** Django, class-based views (`ListView`, `View`), `braces.GroupRequiredMixin`, Celery (`shared_task`), HTMX (polling statusu), openpyxl (eksport XLSX), pytest + model_bakery.

## Global Constraints

- Python ≥3.10,<3.15; max długość linii **88 znaków** (ruff).
- Wszystkie polecenia Pythona przez **`uv run`**. Nigdy goły `python`/`pytest`.
- Testy: pytest, **bez klas**; `@pytest.mark.django_db`; `model_bakery.baker.make`.
- **NIGDY nie edytuj istniejących migracji** w `src/*/migrations/`. Tylko nowe.
- Django: komentarze `{# … #}` jedno-liniowe (każda linia własne `{# #}`).
- Ikony w publicznym frontendzie (Foundation): `<span class="fi-…"></span>`.
- Obsługa wyjątków: zakaz `except Exception: pass`; łapać wąsko, a nieoczekiwane
  → `rollbar.report_exc_info()` + re-raise/policz.
- `pre-commit` bez argumentów; `ruff check` bez `--fix` (poprawki ręcznie).
- Stałe (zachowane): `DEFAULT_ROK_OD = 2022`, `CURRENT_YEAR = datetime.now().year`,
  `OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE = 20`, `DEFAULT_SORT = "-ostatnio_zmieniony"`,
  progres Celery co 5 elementów.
- `const.KWARTYLE = [(None, "brak"), (1, "Q1"), (2, "Q2"), (3, "Q3"), (4, "Q4")]`
  (`src/bpp/const.py:111`) — kwartyle nullable, „0" nie występuje.
- Grupa uprawnień widoków: `group_required = "wprowadzanie danych"`
  (`bpp.const.GR_WPROWADZANIE_DANYCH`).

**Uruchamianie testów aplikacji:** `uv run pytest src/rozbieznosci/`

---

## Mapa plików

Nowa aplikacja `src/rozbieznosci/`:
- `__init__.py`
- `apps.py` — `RozbieznosciConfig` (`default_auto_field`, `name = "rozbieznosci"`).
- `metryki.py` — rejestr metryk (dataclass `Metryka`, lista `METRYKI`, słownik
  `METRYKI_BY_SLUG`, `DEFAULT_METRYKA`, `METRYKA_CHOICES`).
- `models.py` — `IgnorowanaRozbieznosc`, `RozbieznoscLog`.
- `core.py` — logika domeny niezależna od HTTP: `get_base_queryset_for_metryka`,
  `apply_filters`, `apply_sorting`, `get_valid_sort_fields`, `ustaw_ze_zrodla`.
- `forms.py` — `FilterForm`, `SetForm`, `IgnoreForm`.
- `views.py` — `MetrykaMixin`, `RozbieznosciView`, `RozbieznosciExportView`,
  `UstawWszystkieView`, `TaskStatusView`.
- `tasks.py` — `task_ustaw_ze_zrodla`.
- `admin.py` — admin `IgnorowanaRozbieznosc`, `RozbieznoscLog`.
- `urls.py` — `app_name = "rozbieznosci"`, 4 ścieżki z `<slug:metryka>`.
- `migrations/0001_initial.py` — 2 modele (autogenerowane).
- `templates/rozbieznosci/`: `index.html`, `ustaw_wszystkie_confirm.html`,
  `task_status.html`, `_progress.html`.
- `tests/` — `conftest.py`, `test_metryki.py`, `test_models.py`,
  `test_core.py`, `test_views.py`, `test_bulk.py`, `test_templates.py`.

Pliki modyfikowane (Zadanie 8):
- `src/django_bpp/settings/base.py:437-438` (INSTALLED_APPS), `:960-961`
  (TABULAR_PERMISSIONS_CONFIG).
- `src/django_bpp/urls.py:218-219`.
- `src/django_bpp/templates/top_bar.html:200-203`.
- `src/bpp/templates/browse/uczelnia.html:720`.
- `pyproject.toml:204`.
- `src/django_bpp/django_compat.py:14` (komentarz).
- Migracja sprzątająca + baseline (Zadanie 9, gated).

---

### Task 1: Rejestr metryk (`metryki.py`)

**Files:**
- Create: `src/rozbieznosci/__init__.py` (pusty)
- Create: `src/rozbieznosci/apps.py`
- Create: `src/rozbieznosci/metryki.py`
- Test: `src/rozbieznosci/tests/__init__.py` (pusty),
  `src/rozbieznosci/tests/test_metryki.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Metryka` z polami `slug: str`,
    `field_name: str`, `label: str`, `is_quartile: bool`,
    `recalculates_disciplines: bool`, `decimal_places: int`.
  - `METRYKI: list[Metryka]` (kolejność = kolejność zakładek).
  - `METRYKI_BY_SLUG: dict[str, Metryka]`.
  - `DEFAULT_METRYKA: Metryka` (= `METRYKI[0]`).
  - `METRYKA_CHOICES: list[tuple[str, str]]` (`[(slug, label), …]`).

- [ ] **Step 1: Utwórz `apps.py`**

```python
from django.apps import AppConfig


class RozbieznosciConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "rozbieznosci"
```

- [ ] **Step 2: Napisz failing test** (`src/rozbieznosci/tests/test_metryki.py`)

```python
from rozbieznosci.metryki import (
    DEFAULT_METRYKA,
    METRYKA_CHOICES,
    METRYKI,
    METRYKI_BY_SLUG,
)


def test_cztery_metryki_w_kolejnosci():
    assert [m.slug for m in METRYKI] == ["if", "mnisw", "kw_scopus", "kw_wos"]


def test_pola_metryk():
    by = METRYKI_BY_SLUG
    assert by["if"].field_name == "impact_factor"
    assert by["if"].is_quartile is False
    assert by["if"].recalculates_disciplines is False
    assert by["mnisw"].field_name == "punkty_kbn"
    assert by["mnisw"].recalculates_disciplines is True
    assert by["kw_scopus"].field_name == "kwartyl_w_scopus"
    assert by["kw_scopus"].is_quartile is True
    assert by["kw_wos"].field_name == "kwartyl_w_wos"
    assert by["kw_wos"].is_quartile is True


def test_default_metryka_to_if():
    assert DEFAULT_METRYKA.slug == "if"


def test_choices():
    assert METRYKA_CHOICES[0] == ("if", "Impact Factor")
    assert dict(METRYKA_CHOICES)["mnisw"] == "Punkty MNiSW"
```

- [ ] **Step 3: Uruchom test — ma PAŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_metryki.py -v`
Expected: FAIL (`ModuleNotFoundError: rozbieznosci.metryki`)

- [ ] **Step 4: Implementacja `metryki.py`**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Metryka:
    slug: str
    field_name: str
    label: str
    is_quartile: bool
    recalculates_disciplines: bool
    decimal_places: int


METRYKI: list[Metryka] = [
    Metryka("if", "impact_factor", "Impact Factor", False, False, 3),
    Metryka("mnisw", "punkty_kbn", "Punkty MNiSW", False, True, 2),
    Metryka("kw_scopus", "kwartyl_w_scopus", "Kwartyl Scopus", True, False, 0),
    Metryka("kw_wos", "kwartyl_w_wos", "Kwartyl WoS", True, False, 0),
]

METRYKI_BY_SLUG: dict[str, Metryka] = {m.slug: m for m in METRYKI}
DEFAULT_METRYKA: Metryka = METRYKI[0]
METRYKA_CHOICES: list[tuple[str, str]] = [(m.slug, m.label) for m in METRYKI]
```

- [ ] **Step 5: Uruchom test — ma PRZEJŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_metryki.py -v`
Expected: PASS (4 testy)

- [ ] **Step 6: Commit**

```bash
git add src/rozbieznosci/__init__.py src/rozbieznosci/apps.py \
        src/rozbieznosci/metryki.py src/rozbieznosci/tests/
git commit -m "feat(rozbieznosci): rejestr metryk (IF, MNiSW, kwartyle)"
```

---

### Task 2: Modele + migracja + admin

**Files:**
- Create: `src/rozbieznosci/models.py`
- Create: `src/rozbieznosci/admin.py`
- Create: `src/rozbieznosci/migrations/__init__.py` (pusty)
- Create: `src/rozbieznosci/migrations/0001_initial.py` (autogenerowane)
- Test: `src/rozbieznosci/tests/test_models.py`

**Interfaces:**
- Consumes: `METRYKA_CHOICES` z `rozbieznosci.metryki`.
- Produces:
  - `IgnorowanaRozbieznosc(metryka: str, rekord: FK→bpp.Wydawnictwo_Ciagle,
    created_on)`, `unique_together = (metryka, rekord)`.
  - `RozbieznoscLog(metryka: str, rekord: FK, zrodlo: FK→bpp.Zrodlo (SET_NULL),
    wartosc_przed: Decimal(10,3) null, wartosc_po: Decimal(10,3) null,
    user: FK→bpp.BppUser (SET_NULL), created_on)`, `ordering = ["-created_on"]`.

**Uwaga:** tymczasowo trzeba dodać `"rozbieznosci"` do `INSTALLED_APPS`, żeby
`makemigrations` i testy widziały aplikację. Dopisz wpis `"rozbieznosci",`
w `src/django_bpp/settings/base.py` tuż za `"rozbieznosci_pk",` (linia ~438).
Stare appy zostają na razie obok — usuniemy je w Zadaniu 8/9.

- [ ] **Step 1: Dodaj app do INSTALLED_APPS** (`base.py`, po `"rozbieznosci_pk",`)

```python
    "rozbieznosci_if",
    "rozbieznosci_pk",
    "rozbieznosci",
```

- [ ] **Step 2: Napisz failing test** (`tests/test_models.py`)

```python
import pytest
from model_bakery import baker

from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


@pytest.mark.django_db
def test_ignorowana_rozbieznosc_str():
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    ign = IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc)
    assert str(wc.pk) in str(ign)
    assert "if" in str(ign)


@pytest.mark.django_db
def test_unique_metryka_rekord():
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc)
    # ta sama metryka + rekord => konflikt
    with pytest.raises(Exception):
        IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc)
    # inna metryka => OK
    IgnorowanaRozbieznosc.objects.create(metryka="mnisw", rekord=wc)
    assert IgnorowanaRozbieznosc.objects.filter(rekord=wc).count() == 2


@pytest.mark.django_db
def test_log_str():
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    log = RozbieznoscLog.objects.create(
        metryka="if", rekord=wc, wartosc_przed=1, wartosc_po=2
    )
    assert "if" in str(log)
```

- [ ] **Step 3: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_models.py -v`
Expected: FAIL (`ModuleNotFoundError: rozbieznosci.models`)

- [ ] **Step 4: Implementacja `models.py`**

```python
from django.db import models

from rozbieznosci.metryki import METRYKA_CHOICES


class IgnorowanaRozbieznosc(models.Model):
    metryka = models.CharField("Metryka", max_length=16, choices=METRYKA_CHOICES)
    rekord = models.ForeignKey(
        "bpp.Wydawnictwo_Ciagle",
        on_delete=models.CASCADE,
        verbose_name="Rekord",
    )
    created_on = models.DateTimeField("Utworzono", auto_now_add=True)

    class Meta:
        unique_together = [("metryka", "rekord")]
        verbose_name = "ignorowana rozbieżność"
        verbose_name_plural = "ignorowane rozbieżności"

    def __str__(self):
        return f"Ignoruj rozbieżność {self.metryka} dla rekordu {self.rekord_id}"


class RozbieznoscLog(models.Model):
    metryka = models.CharField("Metryka", max_length=16, choices=METRYKA_CHOICES)
    rekord = models.ForeignKey(
        "bpp.Wydawnictwo_Ciagle",
        on_delete=models.CASCADE,
        verbose_name="Rekord",
    )
    zrodlo = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Źródło",
    )
    wartosc_przed = models.DecimalField(
        "Wartość przed zmianą", max_digits=10, decimal_places=3, null=True
    )
    wartosc_po = models.DecimalField(
        "Wartość po zmianie", max_digits=10, decimal_places=3, null=True
    )
    user = models.ForeignKey(
        "bpp.BppUser",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Użytkownik",
    )
    created_on = models.DateTimeField("Kiedy", auto_now_add=True)

    class Meta:
        ordering = ["-created_on"]
        verbose_name = "log zmiany punktacji"
        verbose_name_plural = "logi zmian punktacji"

    def __str__(self):
        return (
            f"Zmiana {self.metryka}: rekord {self.rekord_id} "
            f"({self.wartosc_przed} -> {self.wartosc_po})"
        )
```

- [ ] **Step 5: Implementacja `admin.py`**

```python
from django.contrib import admin

from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


@admin.register(IgnorowanaRozbieznosc)
class IgnorowanaRozbieznoscAdmin(admin.ModelAdmin):
    list_display = ["metryka", "rekord", "created_on"]
    list_filter = ["metryka", "created_on"]
    search_fields = ["rekord__tytul_oryginalny"]


@admin.register(RozbieznoscLog)
class RozbieznoscLogAdmin(admin.ModelAdmin):
    list_display = [
        "metryka",
        "rekord",
        "zrodlo",
        "wartosc_przed",
        "wartosc_po",
        "user",
        "created_on",
    ]
    list_filter = ["metryka", "created_on", "user"]
    search_fields = ["rekord__tytul_oryginalny", "zrodlo__nazwa"]
    readonly_fields = [
        "metryka",
        "rekord",
        "zrodlo",
        "wartosc_przed",
        "wartosc_po",
        "user",
        "created_on",
    ]
    date_hierarchy = "created_on"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
```

- [ ] **Step 6: Wygeneruj migrację**

Run: `uv run python src/manage.py makemigrations rozbieznosci`
Expected: utworzony `src/rozbieznosci/migrations/0001_initial.py` z 2 modelami.
(Upewnij się, że istnieje `src/rozbieznosci/migrations/__init__.py`.)

- [ ] **Step 7: Uruchom test — ma PRZEJŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_models.py -v`
Expected: PASS (3 testy)

- [ ] **Step 8: Commit**

```bash
git add src/rozbieznosci/models.py src/rozbieznosci/admin.py \
        src/rozbieznosci/migrations/ src/rozbieznosci/tests/test_models.py \
        src/django_bpp/settings/base.py
git commit -m "feat(rozbieznosci): wspólne modele IgnorowanaRozbieznosc i RozbieznoscLog"
```

---

### Task 3: Logika domeny — queryset + filtr zer/NULL (`core.py`)

**Files:**
- Create: `src/rozbieznosci/core.py`
- Test: `src/rozbieznosci/tests/conftest.py`,
  `src/rozbieznosci/tests/test_core.py`

**Interfaces:**
- Consumes: `Metryka` (z `metryki`), `IgnorowanaRozbieznosc` (z `models`).
- Produces:
  - `get_valid_sort_fields(metryka: Metryka) -> list[str]`
  - `get_base_queryset_for_metryka(metryka: Metryka, pokaz_puste_zrodla: bool
    = False) -> QuerySet` — anotuje pole `punktacja_zrodla_<field_name>`.
  - `apply_filters(qs, rok_od, rok_do, tytul="") -> QuerySet`
  - `apply_sorting(qs, sort, metryka) -> QuerySet`
  - `ustaw_ze_zrodla(pks, metryka, user_id=None) -> tuple[int, int]`
    (updated, errors). Loguje do `RozbieznoscLog`. Dla
    `metryka.recalculates_disciplines` woła `wc.przelicz_punkty_dyscyplin()`.

**Wzorzec queryset (zachowany z `rozbieznosci_if`):** INNER JOIN po roku +
wykluczenie równości pola + wykluczenie ignorowanych + anotacja wartości źródła.

- [ ] **Step 1: conftest fixtures** (`tests/conftest.py`)

```python
import pytest
from django.contrib.auth.models import Group

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def wprowadzanie_danych_group(db):
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    return group


@pytest.fixture
def client_with_group(client, admin_user, wprowadzanie_danych_group):
    admin_user.groups.add(wprowadzanie_danych_group)
    client.force_login(admin_user)
    return client
```

- [ ] **Step 2: Napisz failing testy** (`tests/test_core.py`)

```python
import pytest
from model_bakery import baker

from rozbieznosci.core import get_base_queryset_for_metryka, ustaw_ze_zrodla
from rozbieznosci.metryki import METRYKI_BY_SLUG
from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog


def _wc_ze_zrodlem(rok, praca_val, zrodlo_val, field):
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make(
        "bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=rok, **{field: zrodlo_val}
    )
    return baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=rok, **{praca_field(field): praca_val}
    )


def praca_field(field):
    return field


@pytest.mark.django_db
def test_if_rozbieznosc_wykrywana():
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor")
    qs = get_base_queryset_for_metryka(m)
    assert wc in list(qs)


@pytest.mark.django_db
def test_if_zero_zrodla_domyslnie_ukryte():
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(2023, praca_val="1.500", zrodlo_val="0.000", field="impact_factor")
    # domyślnie (pokaz_puste_zrodla=False) rekord ze źródłem 0 jest ukryty
    assert wc not in list(get_base_queryset_for_metryka(m))
    # po odsłonięciu — widoczny
    assert wc in list(get_base_queryset_for_metryka(m, pokaz_puste_zrodla=True))


@pytest.mark.django_db
def test_kwartyl_null_zrodla_domyslnie_ukryty():
    m = METRYKI_BY_SLUG["kw_scopus"]
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=None)
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, kwartyl_w_scopus=2
    )
    assert wc not in list(get_base_queryset_for_metryka(m))
    assert wc in list(get_base_queryset_for_metryka(m, pokaz_puste_zrodla=True))


@pytest.mark.django_db
def test_ignorowane_wykluczone_per_metryka():
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor")
    IgnorowanaRozbieznosc.objects.create(metryka="if", rekord=wc)
    assert wc not in list(get_base_queryset_for_metryka(m))
    # ignor dla innej metryki nie wpływa
    assert wc in list(get_base_queryset_for_metryka(METRYKI_BY_SLUG["if"])) is False


@pytest.mark.django_db
def test_ustaw_ze_zrodla_aktualizuje_i_loguje():
    m = METRYKI_BY_SLUG["if"]
    wc = _wc_ze_zrodlem(2023, praca_val="1.500", zrodlo_val="2.500", field="impact_factor")
    updated, errors = ustaw_ze_zrodla([wc.pk], m)
    assert (updated, errors) == (1, 0)
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.500"
    assert RozbieznoscLog.objects.filter(metryka="if", rekord=wc).count() == 1


@pytest.mark.django_db
def test_ustaw_mnisw_wola_przelicz(monkeypatch):
    m = METRYKI_BY_SLUG["mnisw"]
    wc = _wc_ze_zrodlem(2023, praca_val="10.00", zrodlo_val="40.00", field="punkty_kbn")
    called = {"n": 0}
    from bpp.models import Wydawnictwo_Ciagle

    monkeypatch.setattr(
        Wydawnictwo_Ciagle,
        "przelicz_punkty_dyscyplin",
        lambda self: called.__setitem__("n", called["n"] + 1),
    )
    ustaw_ze_zrodla([wc.pk], m)
    assert called["n"] == 1
```

> Uwaga dla implementującego: jeśli `baker.make("bpp.Punktacja_Zrodla", …)` lub
> pola modeli wymagają dodatkowych wymaganych pól, uzupełnij fixtury minimalnie
> (np. `baker.make` sam wypełni). Zweryfikuj nazwy pól wartości: `impact_factor`,
> `punkty_kbn`, `kwartyl_w_scopus`, `kwartyl_w_wos` istnieją zarówno na
> `Punktacja_Zrodla` jak i `Wydawnictwo_Ciagle`.

- [ ] **Step 3: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_core.py -v`
Expected: FAIL (`ModuleNotFoundError: rozbieznosci.core`)

- [ ] **Step 4: Implementacja `core.py`**

```python
from django.db.models import F

from bpp.models import Wydawnictwo_Ciagle
from rozbieznosci.models import IgnorowanaRozbieznosc, RozbieznoscLog

DEFAULT_SORT = "-ostatnio_zmieniony"


def get_valid_sort_fields(metryka):
    field = metryka.field_name
    annotated = f"punktacja_zrodla_{field}"
    return [
        "rok",
        "-rok",
        field,
        f"-{field}",
        annotated,
        f"-{annotated}",
        "ostatnio_zmieniony",
        "-ostatnio_zmieniony",
    ]


def get_base_queryset_for_metryka(metryka, pokaz_puste_zrodla=False):
    field = metryka.field_name
    annotated = f"punktacja_zrodla_{field}"
    src = f"zrodlo__punktacja_zrodla__{field}"

    qs = (
        Wydawnictwo_Ciagle.objects.exclude(zrodlo=None)
        .filter(zrodlo__punktacja_zrodla__rok=F("rok"))
        .exclude(**{src: F(field)})
        .exclude(
            pk__in=IgnorowanaRozbieznosc.objects.filter(
                metryka=metryka.slug
            ).values_list("rekord_id", flat=True)
        )
        .select_related("zrodlo")
        .annotate(**{annotated: F(src)})
    )

    if not pokaz_puste_zrodla:
        if metryka.is_quartile:
            qs = qs.exclude(**{f"{src}__isnull": True})
        else:
            qs = qs.exclude(**{src: 0})

    return qs


def apply_filters(queryset, rok_od, rok_do, tytul=""):
    queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)
    if tytul:
        queryset = queryset.filter(tytul_oryginalny__icontains=tytul)
    return queryset


def apply_sorting(queryset, sort, metryka):
    if sort in get_valid_sort_fields(metryka):
        return queryset.order_by(sort)
    return queryset.order_by(DEFAULT_SORT)


def ustaw_ze_zrodla(pks, metryka, user_id=None):
    """Aktualizuje pole metryki z punktacji źródła. Zwraca (updated, errors)."""
    import rollbar

    from bpp.models import BppUser

    field = metryka.field_name
    updated = 0
    errors = 0

    user = None
    if user_id:
        try:
            user = BppUser.objects.get(pk=user_id)
        except BppUser.DoesNotExist:
            user = None

    for pk in pks:
        try:
            wc = Wydawnictwo_Ciagle.objects.get(pk=pk)
        except Wydawnictwo_Ciagle.DoesNotExist:
            errors += 1
            continue

        try:
            punktacja = wc.punktacja_zrodla()
            if punktacja is None:
                continue
            old_value = getattr(wc, field)
            new_value = getattr(punktacja, field)
            if old_value == new_value:
                continue

            setattr(wc, field, new_value)
            wc.save()
            if metryka.recalculates_disciplines:
                wc.przelicz_punkty_dyscyplin()

            RozbieznoscLog.objects.create(
                metryka=metryka.slug,
                rekord=wc,
                zrodlo=wc.zrodlo,
                wartosc_przed=old_value,
                wartosc_po=new_value,
                user=user,
            )
            updated += 1
        except Exception:
            rollbar.report_exc_info()
            errors += 1

    return updated, errors
```

> Uwaga: `wc.punktacja_zrodla()` może rzucić `Punktacja_Zrodla.DoesNotExist`
> (metoda robi `.get(rok=self.rok)`). Złap to wąsko jako brak punktacji
> (kontynuuj, nie licz jako błąd) — jeśli zajdzie w testach, dodaj
> `except Punktacja_Zrodla.DoesNotExist: continue` wokół `wc.punktacja_zrodla()`.

- [ ] **Step 5: Uruchom testy — mają PRZEJŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_core.py -v`
Expected: PASS. Jeśli `test_ignorowane…` ma dziwną asercję — popraw na
czytelną: po dodaniu ignoru `assert wc not in list(...)`; bez ignoru (nowy
rekord) `assert wc in list(...)`. (Asercja `is False` w szkicu jest celowo
do poprawienia na jasną formę.)

- [ ] **Step 6: Commit**

```bash
git add src/rozbieznosci/core.py src/rozbieznosci/tests/conftest.py \
        src/rozbieznosci/tests/test_core.py
git commit -m "feat(rozbieznosci): queryset rozbieżności + filtr zer/NULL + ustaw_ze_zrodla"
```

---

### Task 4: Formularze + widok listy z zakładkami (`forms.py`, `views.py` część 1)

**Files:**
- Create: `src/rozbieznosci/forms.py`
- Create: `src/rozbieznosci/views.py` (część: `MetrykaMixin`, `RozbieznosciView`)
- Create: `src/rozbieznosci/urls.py` (wstępnie: tylko `index`)
- Modify: `src/django_bpp/urls.py` (dodaj include `rozbieznosci/` OBOK starych)
- Create: szablon-zaślepka `templates/rozbieznosci/index.html` (pełny w Task 7)
- Test: `src/rozbieznosci/tests/test_views.py`

**Interfaces:**
- Consumes: `core.*`, `metryki.*`.
- Produces:
  - `FilterForm` z polami `rok_od`, `rok_do`, `tytul`, **`pokaz_puste_zrodla`
    = BooleanField(required=False)**; `clean_rok_od`→`DEFAULT_ROK_OD`,
    `clean_rok_do`→`CURRENT_YEAR`, `clean_tytul`→`""`.
  - `SetForm(_set: int)`, `IgnoreForm(_ignore: int)`.
  - `MetrykaMixin.setup()` ustawia `self.metryka` z `kwargs["metryka"]` lub 404.
  - `RozbieznosciView` (URL name `index`) — `<slug:metryka>/`.
  - `get_filter_params(self, source)` → `(rok_od, rok_do, tytul, sort,
    pokaz_puste_zrodla)`.

- [ ] **Step 1: Napisz failing testy** (`tests/test_views.py`)

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from rozbieznosci.models import IgnorowanaRozbieznosc


@pytest.mark.django_db
def test_index_200_dla_kazdej_metryki(client_with_group):
    for slug in ["if", "mnisw", "kw_scopus", "kw_wos"]:
        url = reverse("rozbieznosci:index", kwargs={"metryka": slug})
        assert client_with_group.get(url).status_code == 200


@pytest.mark.django_db
def test_index_404_dla_zlej_metryki(client_with_group):
    # 'foo' nie jest slugiem metryki
    resp = client_with_group.get("/rozbieznosci/foo/")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_set_aktualizuje_z_zrodla(client_with_group):
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, impact_factor="2.500")
    wc = baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.500")
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    client_with_group.get(f"{url}?_set={wc.pk}")
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.500"


@pytest.mark.django_db
def test_ignore_dodaje_per_metryka(client_with_group):
    wc = baker.make("bpp.Wydawnictwo_Ciagle")
    url = reverse("rozbieznosci:index", kwargs={"metryka": "kw_wos"})
    client_with_group.get(f"{url}?_ignore={wc.pk}")
    assert IgnorowanaRozbieznosc.objects.filter(metryka="kw_wos", rekord=wc).exists()
```

- [ ] **Step 2: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_views.py -v`
Expected: FAIL (brak URL / modułu).

- [ ] **Step 3: Implementacja `forms.py`**

```python
from datetime import datetime

from django import forms

DEFAULT_ROK_OD = 2022
CURRENT_YEAR = datetime.now().year


class SetForm(forms.Form):
    _set = forms.IntegerField(min_value=0)


class IgnoreForm(forms.Form):
    _ignore = forms.IntegerField(min_value=0)


class FilterForm(forms.Form):
    rok_od = forms.IntegerField(
        min_value=1900, max_value=2100, required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    rok_do = forms.IntegerField(
        min_value=1900, max_value=2100, required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    tytul = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj w tytule..."}),
    )
    pokaz_puste_zrodla = forms.BooleanField(required=False)

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or CURRENT_YEAR

    def clean_tytul(self):
        return self.cleaned_data.get("tytul") or ""
```

- [ ] **Step 4: Implementacja `views.py` (część 1)**

```python
from urllib.parse import quote

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.urls import reverse
from django.views.generic import ListView

from bpp.models import Wydawnictwo_Ciagle
from rozbieznosci.core import (
    DEFAULT_SORT,
    apply_filters,
    apply_sorting,
    get_base_queryset_for_metryka,
    get_valid_sort_fields,
    ustaw_ze_zrodla,
)
from rozbieznosci.forms import (
    CURRENT_YEAR,
    DEFAULT_ROK_OD,
    FilterForm,
    IgnoreForm,
    SetForm,
)
from rozbieznosci.metryki import METRYKI, METRYKI_BY_SLUG
from rozbieznosci.models import IgnorowanaRozbieznosc


class MetrykaMixin:
    group_required = "wprowadzanie danych"

    def setup(self, request, *args, **kwargs):
        super().setup(request, *args, **kwargs)
        self.metryka = METRYKI_BY_SLUG.get(kwargs.get("metryka"))
        if self.metryka is None:
            raise Http404("Nieznana metryka")


def _filter_params(source, metryka):
    form = FilterForm(source)
    if form.is_valid():
        rok_od = form.cleaned_data["rok_od"]
        rok_do = form.cleaned_data["rok_do"]
        tytul = form.cleaned_data["tytul"]
        pokaz = form.cleaned_data["pokaz_puste_zrodla"]
    else:
        rok_od, rok_do, tytul, pokaz = DEFAULT_ROK_OD, CURRENT_YEAR, "", False
    sort = source.get("sort", DEFAULT_SORT)
    if sort not in get_valid_sort_fields(metryka):
        sort = DEFAULT_SORT
    return rok_od, rok_do, tytul, sort, pokaz


def _query_string(rok_od, rok_do, tytul, pokaz):
    params = []
    if rok_od != DEFAULT_ROK_OD:
        params.append(f"rok_od={rok_od}")
    if rok_do != CURRENT_YEAR:
        params.append(f"rok_do={rok_do}")
    if tytul:
        params.append(f"tytul={quote(tytul)}")
    if pokaz:
        params.append("pokaz_puste_zrodla=1")
    return "&".join(params)


class RozbieznosciView(MetrykaMixin, GroupRequiredMixin, ListView):
    template_name = "rozbieznosci/index.html"
    paginate_by = 25

    def get_queryset(self):
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(
            self.request.GET, self.metryka
        )
        qs = get_base_queryset_for_metryka(self.metryka, pokaz_puste_zrodla=pokaz)
        qs = apply_filters(qs, rok_od, rok_do, tytul)
        qs = apply_sorting(qs, sort, self.metryka)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(
            self.request.GET, self.metryka
        )
        field = self.metryka.field_name
        context.update(
            {
                "metryka": self.metryka,
                "metryki": METRYKI,
                "page_title": f"Rozbieżności: {self.metryka.label}",
                "rok_od": rok_od,
                "rok_do": rok_do,
                "tytul": tytul,
                "current_sort": sort,
                "pokaz_puste_zrodla": pokaz,
                "field_name": field,
                "field_label": self.metryka.label,
                "annotated_field": f"punktacja_zrodla_{field}",
                "sort_field": field,
                "sort_field_desc": f"-{field}",
                "sort_field_zrodla": f"punktacja_zrodla_{field}",
                "sort_field_zrodla_desc": f"-punktacja_zrodla_{field}",
                "filter_query_string": _query_string(rok_od, rok_do, tytul, pokaz),
            }
        )
        return context

    def _handle_ignore(self, request):
        frm = IgnoreForm(request.GET)
        if not frm.is_valid():
            return
        pk = frm.cleaned_data["_ignore"]
        try:
            wc = Wydawnictwo_Ciagle.objects.get(pk=pk)
        except Wydawnictwo_Ciagle.DoesNotExist:
            messages.error(request, f"Rekord (ID: {pk}) nie istnieje.")
            return
        _, created = IgnorowanaRozbieznosc.objects.get_or_create(
            metryka=self.metryka.slug, rekord=wc
        )
        if created:
            messages.info(
                request,
                f'Rekord "{wc.tytul_oryginalny}" (ID: {pk}) dodany do '
                f"ignorowanych ({self.metryka.label}).",
            )
        else:
            messages.warning(
                request, f"Rekord (ID: {pk}) był już ignorowany."
            )

    def _handle_set(self, request):
        frm = SetForm(request.GET)
        if not frm.is_valid():
            return
        pk = frm.cleaned_data["_set"]
        IgnorowanaRozbieznosc.objects.filter(
            metryka=self.metryka.slug, rekord_id=pk
        ).delete()
        updated, errors = ustaw_ze_zrodla([pk], self.metryka, user_id=request.user.id)
        if updated:
            messages.success(
                request, f"Rekord (ID: {pk}): {self.metryka.label} ustawiony "
                f"wg źródła."
            )
        elif errors:
            messages.error(request, f"Rekord (ID: {pk}): błąd aktualizacji.")
        else:
            messages.info(
                request, f"Rekord (ID: {pk}): {self.metryka.label} bez zmian."
            )

    def get(self, request, *args, **kwargs):
        if "_ignore" in request.GET:
            self._handle_ignore(request)
        if "_set" in request.GET:
            self._handle_set(request)
        return super().get(request, *args, **kwargs)
```

- [ ] **Step 5: `urls.py` (wstępnie) + szablon-zaślepka + include**

`src/rozbieznosci/urls.py`:

```python
from django.urls import path

from rozbieznosci.views import RozbieznosciView

app_name = "rozbieznosci"

urlpatterns = [
    path("<slug:metryka>/", RozbieznosciView.as_view(), name="index"),
]
```

Zaślepka `src/rozbieznosci/templates/rozbieznosci/index.html` (pełny w Task 7):

```django
{% extends "base.html" %}
{% block content %}<h1>{{ page_title }}</h1>{% endblock %}
```

`src/django_bpp/urls.py` — dodaj OBOK starych (linia ~219):

```python
        path("rozbieznosci_if/", include("rozbieznosci_if.urls")),
        path("rozbieznosci_pk/", include("rozbieznosci_pk.urls")),
        path("rozbieznosci/", include("rozbieznosci.urls")),
```

- [ ] **Step 6: Uruchom testy — mają PRZEJŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_views.py -v`
Expected: PASS (4 testy).

- [ ] **Step 7: Commit**

```bash
git add src/rozbieznosci/forms.py src/rozbieznosci/views.py \
        src/rozbieznosci/urls.py src/rozbieznosci/templates \
        src/rozbieznosci/tests/test_views.py src/django_bpp/urls.py
git commit -m "feat(rozbieznosci): widok listy z metryką w URL, akcje set/ignore"
```

---

### Task 5: Eksport XLSX + bulk + Celery + status (`views.py` część 2, `tasks.py`)

**Files:**
- Modify: `src/rozbieznosci/views.py` (dodaj `RozbieznosciExportView`,
  `UstawWszystkieView`, `TaskStatusView`)
- Create: `src/rozbieznosci/tasks.py`
- Modify: `src/rozbieznosci/urls.py` (dodaj `export`, `ustaw_wszystkie`,
  `task_status`)
- Test: `src/rozbieznosci/tests/test_bulk.py`

**Interfaces:**
- Consumes: `core.*`, `metryki.*`.
- Produces:
  - URL names: `export`, `ustaw_wszystkie`, `task_status` (z `<str:task_id>`).
  - `task_ustaw_ze_zrodla(self, pks, metryka_slug, user_id=None) -> dict`
    (`{"updated", "errors", "total"}`), progres co 5.

- [ ] **Step 1: Napisz failing testy** (`tests/test_bulk.py`)

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from rozbieznosci.tasks import task_ustaw_ze_zrodla


def _rozbiezny(field, praca, zrodlo_val, rok=2023):
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=rok, **{field: zrodlo_val})
    return baker.make(
        "bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=rok, **{field: praca}
    )


@pytest.mark.django_db
def test_bulk_sync_maly_batch(client_with_group):
    wc = _rozbiezny("impact_factor", "1.000", "2.000")
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "if"})
    # POST z filtrami => synchronicznie (1 < 20)
    resp = client_with_group.post(url, {"rok_od": 2022, "rok_do": 2026})
    assert resp.status_code in (301, 302)
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.000"


@pytest.mark.django_db
def test_task_aktualizuje(celery_eager_or_direct=None):
    wc = _rozbiezny("impact_factor", "1.000", "2.000")
    result = task_ustaw_ze_zrodla(pks=[wc.pk], metryka_slug="if")
    assert result["updated"] == 1
    wc.refresh_from_db()
    assert str(wc.impact_factor) == "2.000"


@pytest.mark.django_db
def test_confirm_get_pokazuje_liczbe(client_with_group):
    _rozbiezny("punkty_kbn", "10.00", "40.00")
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "mnisw"})
    resp = client_with_group.get(f"{url}?rok_od=2022&rok_do=2026")
    assert resp.status_code == 200
    assert b"1" in resp.content
```

> Uwaga: `task_ustaw_ze_zrodla` wołamy bezpośrednio (jako funkcję) z
> `bind=True` — w teście wywołanie `task_ustaw_ze_zrodla(pks=…, metryka_slug=…)`
> działa, bo `self` jest wstrzykiwany przez Celery tylko przy `.delay()`. Jeśli
> bezpośrednie wywołanie wymaga `self`, użyj `.apply(args=[...], kwargs={...})`
> lub `.run(...)`. Dostosuj sygnaturę testu do faktycznego API (sprawdź wzorzec
> z istniejących testów `rozbieznosci_if/tests.py`).

- [ ] **Step 2: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_bulk.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementacja `tasks.py`**

```python
from celery import shared_task


@shared_task(bind=True)
def task_ustaw_ze_zrodla(self, pks, metryka_slug, user_id=None):
    """Aktualizuje metrykę z punktacji źródła. Progres przez update_state."""
    from rozbieznosci.core import ustaw_ze_zrodla
    from rozbieznosci.metryki import METRYKI_BY_SLUG

    metryka = METRYKI_BY_SLUG[metryka_slug]
    total = len(pks)
    updated = 0
    errors = 0

    for idx, pk in enumerate(pks, 1):
        u, e = ustaw_ze_zrodla([pk], metryka, user_id=user_id)
        updated += u
        errors += e
        if idx % 5 == 0 or idx == total:
            self.update_state(
                state="PROGRESS",
                meta={
                    "current": idx,
                    "total": total,
                    "updated": updated,
                    "errors": errors,
                    "progress": int((idx / total) * 100) if total else 100,
                },
            )

    return {"updated": updated, "errors": errors, "total": total}
```

- [ ] **Step 4: Implementacja `views.py` (część 2)** — dopisz klasy

```python
from io import BytesIO

from celery.result import AsyncResult
from django.http import HttpResponse
from django.shortcuts import redirect, render
from openpyxl import Workbook

from bpp.util import worksheet_columns_autosize, worksheet_create_table
from rozbieznosci.forms import OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE  # patrz niżej


class RozbieznosciExportView(MetrykaMixin, GroupRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(
            request.GET, self.metryka
        )
        qs = get_base_queryset_for_metryka(self.metryka, pokaz_puste_zrodla=pokaz)
        qs = apply_filters(qs, rok_od, rok_do, tytul)
        qs = apply_sorting(qs, sort, self.metryka)

        field = self.metryka.field_name
        annotated = f"punktacja_zrodla_{field}"
        label = self.metryka.label

        wb = Workbook()
        ws = wb.active
        ws.title = label[:31]
        ws.append(
            ["Tytuł", "Rok", "Źródło", f"{label} pracy", f"{label} źródła",
             "Ostatnio zmieniony"]
        )
        for elem in qs:
            v = getattr(elem, field)
            vz = getattr(elem, annotated)
            ws.append([
                elem.tytul_oryginalny,
                elem.rok,
                elem.zrodlo.nazwa if elem.zrodlo else "",
                float(v) if v else 0,
                float(vz) if vz else 0,
                elem.ostatnio_zmieniony.strftime("%Y-%m-%d %H:%M")
                if elem.ostatnio_zmieniony else "",
            ])

        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title=f"Rozbieznosci_{self.metryka.slug}")

        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
        filename = f"rozbieznosci_{self.metryka.slug}_{rok_od}_{rok_do}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        vb = BytesIO()
        wb.save(vb)
        vb.seek(0)
        response.write(vb.getvalue())
        return response


class UstawWszystkieView(MetrykaMixin, GroupRequiredMixin, View):
    confirm_template_name = "rozbieznosci/ustaw_wszystkie_confirm.html"

    def _redirect_back(self, rok_od, rok_do, tytul, pokaz):
        url = reverse("rozbieznosci:index", kwargs={"metryka": self.metryka.slug})
        qs = _query_string(rok_od, rok_do, tytul, pokaz)
        return HttpResponseRedirect(f"{url}?{qs}" if qs else url)

    def get(self, request, *args, **kwargs):
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(
            request.GET, self.metryka
        )
        qs = get_base_queryset_for_metryka(self.metryka, pokaz_puste_zrodla=pokaz)
        qs = apply_filters(qs, rok_od, rok_do, tytul)
        count = qs.count()
        if count == 0:
            messages.warning(request, "Brak rekordów do aktualizacji.")
            return self._redirect_back(rok_od, rok_do, tytul, pokaz)
        return render(request, self.confirm_template_name, {
            "metryka": self.metryka,
            "rok_od": rok_od, "rok_do": rok_do, "tytul": tytul,
            "pokaz_puste_zrodla": pokaz, "count": count,
            "field_label": self.metryka.label,
            "use_celery": count >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
        })

    def post(self, request, *args, **kwargs):
        rok_od, rok_do, tytul, sort, pokaz = _filter_params(
            request.POST, self.metryka
        )
        qs = get_base_queryset_for_metryka(self.metryka, pokaz_puste_zrodla=pokaz)
        qs = apply_filters(qs, rok_od, rok_do, tytul)
        pks = list(qs.values_list("pk", flat=True))
        count = len(pks)
        if count == 0:
            messages.warning(request, "Brak rekordów do aktualizacji.")
            return self._redirect_back(rok_od, rok_do, tytul, pokaz)
        if count >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
            from rozbieznosci.tasks import task_ustaw_ze_zrodla

            task = task_ustaw_ze_zrodla.delay(
                pks, self.metryka.slug, user_id=request.user.id
            )
            return redirect(
                "rozbieznosci:task_status",
                metryka=self.metryka.slug,
                task_id=task.id,
            )
        updated, errors = ustaw_ze_zrodla(
            pks, self.metryka, user_id=request.user.id
        )
        if errors:
            messages.warning(
                request, f"Zaktualizowano {updated}. Błędy: {errors}."
            )
        else:
            messages.success(request, f"Zaktualizowano {updated} rekordów.")
        return self._redirect_back(rok_od, rok_do, tytul, pokaz)


class TaskStatusView(MetrykaMixin, GroupRequiredMixin, View):
    template_name = "rozbieznosci/task_status.html"
    progress_template_name = "rozbieznosci/_progress.html"

    def get(self, request, metryka, task_id):
        task = AsyncResult(task_id)
        info = task.info if isinstance(task.info, dict) else {}
        context = {
            "metryka": self.metryka,
            "task_id": task_id,
            "task_ready": task.ready(),
            "page_title": f"Rozbieżności: {self.metryka.label}",
        }
        if not task.ready():
            context["info"] = info
        elif task.failed():
            context["error"] = str(task.info)
        elif task.successful():
            result = task.result
            updated = result.get("updated", 0)
            errors = result.get("errors", 0)
            messages.success(
                request,
                f"Zaktualizowano {updated} rekordów."
                + (f" Błędy: {errors}." if errors else ""),
            )
            index = reverse(
                "rozbieznosci:index", kwargs={"metryka": self.metryka.slug}
            )
            if request.headers.get("HX-Request"):
                resp = HttpResponse(status=200)
                resp["HX-Redirect"] = index
                return resp
            return redirect(index)
        if request.headers.get("HX-Request"):
            return render(request, self.progress_template_name, context)
        return render(request, self.template_name, context)
```

> **Stała `OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE = 20`** — dodaj ją do
> `forms.py` (obok `DEFAULT_ROK_OD`) albo `core.py` i zaimportuj. Zachowaj jedno
> miejsce definicji. (W szkicu wyżej importowana z `forms`.)

- [ ] **Step 5: `urls.py` — dopełnij ścieżki**

```python
from django.urls import path

from rozbieznosci.views import (
    RozbieznosciExportView,
    RozbieznosciView,
    TaskStatusView,
    UstawWszystkieView,
)

app_name = "rozbieznosci"

urlpatterns = [
    path("<slug:metryka>/", RozbieznosciView.as_view(), name="index"),
    path("<slug:metryka>/export/", RozbieznosciExportView.as_view(), name="export"),
    path(
        "<slug:metryka>/ustaw-wszystkie/",
        UstawWszystkieView.as_view(),
        name="ustaw_wszystkie",
    ),
    path(
        "<slug:metryka>/task-status/<str:task_id>/",
        TaskStatusView.as_view(),
        name="task_status",
    ),
]
```

> **Kolejność ścieżek:** `<slug:metryka>/` jako pierwsza złapie też
> `if/export/`? Nie — `export/` to dłuższy wzorzec; ale `<slug:metryka>/`
> z trailing `/` matchuje tylko jeden segment. `if/export/` ma dwa segmenty,
> więc trafi do `export`. OK. Zweryfikuj testem `test_export`.

- [ ] **Step 6: Uruchom testy — mają PRZEJŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_bulk.py -v`
Expected: PASS. Dostosuj wywołanie taska w teście do faktycznego API Celery
(patrz uwaga w Step 1).

- [ ] **Step 7: Commit**

```bash
git add src/rozbieznosci/views.py src/rozbieznosci/tasks.py \
        src/rozbieznosci/urls.py src/rozbieznosci/tests/test_bulk.py \
        src/rozbieznosci/forms.py
git commit -m "feat(rozbieznosci): eksport XLSX, bulk ustaw wszystkie, task Celery + status"
```

---

### Task 6: Szablony z zakładkami + threading filtra

**Files:**
- Modify: `src/rozbieznosci/templates/rozbieznosci/index.html` (pełna wersja)
- Create: `src/rozbieznosci/templates/rozbieznosci/ustaw_wszystkie_confirm.html`
- Create: `src/rozbieznosci/templates/rozbieznosci/task_status.html`
- Create: `src/rozbieznosci/templates/rozbieznosci/_progress.html`
- Test: `src/rozbieznosci/tests/test_templates.py`

**Interfaces:**
- Consumes kontekst z `RozbieznosciView` (`metryka`, `metryki`, `field_name`,
  `annotated_field`, `filter_query_string`, `pokaz_puste_zrodla`, etc.).

- [ ] **Step 1: Napisz failing testy** (`tests/test_templates.py`)

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_zakladki_renderowane(client_with_group):
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    html = client_with_group.get(url).content.decode()
    # wszystkie 4 etykiety zakładek
    for label in ["Impact Factor", "Punkty MNiSW", "Kwartyl Scopus", "Kwartyl WoS"]:
        assert label in html
    # link do innej metryki
    assert reverse("rozbieznosci:index", kwargs={"metryka": "mnisw"}) in html


@pytest.mark.django_db
def test_checkbox_pokaz_puste_zrodla_obecny(client_with_group):
    url = reverse("rozbieznosci:index", kwargs={"metryka": "if"})
    html = client_with_group.get(url).content.decode()
    assert "pokaz_puste_zrodla" in html


@pytest.mark.django_db
def test_confirm_threaduje_pokaz(client_with_group):
    # gdy pokaz_puste_zrodla=1 w GET, ekran confirm ma hidden z tą wartością
    from model_bakery import baker
    zrodlo = baker.make("bpp.Zrodlo")
    baker.make("bpp.Punktacja_Zrodla", zrodlo=zrodlo, rok=2023, impact_factor="0.000")
    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo, rok=2023, impact_factor="1.000")
    url = reverse("rozbieznosci:ustaw_wszystkie", kwargs={"metryka": "if"})
    html = client_with_group.get(
        f"{url}?rok_od=2022&rok_do=2026&pokaz_puste_zrodla=1"
    ).content.decode()
    assert 'name="pokaz_puste_zrodla"' in html
```

- [ ] **Step 2: Uruchom — ma PAŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_templates.py -v`
Expected: FAIL (zaślepka index nie ma zakładek).

- [ ] **Step 3: `index.html` (pełny)**

Bazuj na obecnym `rozbieznosci_if/index.html`, z różnicami: (a) pasek zakładek
przed formularzem, (b) wszystkie `{% url %}` używają `rozbieznosci:…` z
`metryka=metryka.slug`, (c) pola tabeli generyczne (`elem|getattr` przez
`field_name`/`annotated_field` — użyj filtra `getattr` z `url_helpers` jeśli
istnieje; jeśli nie, dodaj prosty tag), (d) checkbox `pokaz_puste_zrodla` w
formularzu, (e) parametr przenoszony w `filter_query_string` (już zawiera
`pokaz_puste_zrodla=1`).

Pasek zakładek (Foundation):

```django
{# pasek zakładek metryk #}
<div class="row">
  <div class="medium-12 columns">
    <ul class="tabs">
      {% for m in metryki %}
        <li class="tabs-title {% if m.slug == metryka.slug %}is-active{% endif %}">
          <a href="{% url 'rozbieznosci:index' metryka=m.slug %}{% if filter_query_string %}?{{ filter_query_string }}{% endif %}"
             {% if m.slug == metryka.slug %}aria-selected="true"{% endif %}>
            {{ m.label }}
          </a>
        </li>
      {% endfor %}
    </ul>
  </div>
</div>
```

Checkbox w formularzu filtrów (dodaj kolumnę):

```django
{# filtr: pokaż też rekordy ze źródłem 0/brak #}
<div class="medium-4 columns">
  <label>
    <input type="checkbox" name="pokaz_puste_zrodla" value="1"
           {% if pokaz_puste_zrodla %}checked{% endif %}>
    Pokaż też rekordy ze źródłem 0/brak
  </label>
</div>
```

Komórki wartości w tabeli — wyświetlanie pola wskazanego przez `field_name`.
Najprościej: przekaż w widoku do każdego elementu pomocnicze atrybuty, albo
dodaj prosty template-filter. Zalecane: w `get_context_data` nic nie trzeba —
użyj w szablonie własnego filtra. Utwórz `templatetags/rozbieznosci_extras.py`:

```python
from django import template

register = template.Library()


@register.filter
def attr(obj, name):
    return getattr(obj, name, "")
```

I w szablonie:

```django
{% load rozbieznosci_extras %}
...
<td>{{ elem|attr:field_name }}</td>
<td>{{ elem|attr:annotated_field }}</td>
```

Akcje w wierszu (zachowaj OBIE — „zignoruj" i „ustaw wg źródła"), linki względne
`?{{ filter_query_string }}&sort={{ current_sort }}&_set=…` / `&_ignore=…`
(wzór jak w starym szablonie; `filter_query_string` już zawiera
`pokaz_puste_zrodla`). Link „pokaż ignorowane":

```django
<a href="{% url 'admin:rozbieznosci_ignorowanarozbieznosc_changelist' %}?metryka={{ metryka.slug }}">pokaż ignorowane rekordy</a>
```

- [ ] **Step 4: `ustaw_wszystkie_confirm.html`**

Bazuj na starym; zmień breadcrumbs/linki na `rozbieznosci:index metryka=metryka.slug`
i **dodaj hidden** `pokaz_puste_zrodla`:

```django
<form method="post">
  {% csrf_token %}
  <input type="hidden" name="rok_od" value="{{ rok_od }}">
  <input type="hidden" name="rok_do" value="{{ rok_do }}">
  <input type="hidden" name="tytul" value="{{ tytul }}">
  {% if pokaz_puste_zrodla %}
    <input type="hidden" name="pokaz_puste_zrodla" value="1">
  {% endif %}
  <button type="submit" class="button warning">
    <span class="fi-check"></span> Tak, zaktualizuj {{ count }}
  </button>
  <a href="{% url 'rozbieznosci:index' metryka=metryka.slug %}" class="button secondary">Anuluj</a>
</form>
```

- [ ] **Step 5: `task_status.html` i `_progress.html`**

Skopiuj z `rozbieznosci_if`, zmieniając `{% url 'rozbieznosci_if:… %}` na
`rozbieznosci:…` z `metryka=metryka.slug` oraz HTMX `hx-get` na
`{% url 'rozbieznosci:task_status' metryka=metryka.slug task_id %}`.
`_progress.html` jest niezależny od metryki — skopiuj 1:1.

- [ ] **Step 6: Uruchom testy — mają PRZEJŚĆ**

Run: `uv run pytest src/rozbieznosci/tests/test_templates.py -v`
Expected: PASS (3 testy).

- [ ] **Step 7: Pełna suita aplikacji**

Run: `uv run pytest src/rozbieznosci/ -v`
Expected: wszystkie testy PASS.

- [ ] **Step 8: Commit**

```bash
git add src/rozbieznosci/templates src/rozbieznosci/templatetags \
        src/rozbieznosci/tests/test_templates.py
git commit -m "feat(rozbieznosci): szablony z zakładkami + threading pokaz_puste_zrodla"
```

---

### Task 7: Podmiana menu i kafelka (przełączenie na nową opcję)

**Files:**
- Modify: `src/django_bpp/templates/top_bar.html:200-203`
- Modify: `src/bpp/templates/browse/uczelnia.html:720`

**Interfaces:** brak nowych — czysta zmiana linków UI.

- [ ] **Step 1: Podmień wpisy menu w `top_bar.html`**

Zamień dwa `<li>` (rozbieżności IF / MNiSW) na jeden:

```django
                                    <li><a href="{% url "rozbieznosci:index" metryka="if" %}"><i class="fi-graph-pie"></i> rozbieżności
                                        punktacji/kwartyli</a></li>
```

- [ ] **Step 2: Przepnij kafelek w `uczelnia.html:720`**

```javascript
                link: "/rozbieznosci/if/",
```

- [ ] **Step 3: Weryfikacja ręczna (smoke)**

Run: `uv run python src/manage.py check`
Expected: brak błędów; `reverse("rozbieznosci:index", kwargs={"metryka":"if"})`
działa (sprawdzone testami z Task 4).

- [ ] **Step 4: Commit**

```bash
git add src/django_bpp/templates/top_bar.html src/bpp/templates/browse/uczelnia.html
git commit -m "feat(rozbieznosci): jedna pozycja menu + kafelek -> scalona opcja"
```

---

### Task 8: Usunięcie starych aplikacji z konfiguracji

**Files:**
- Modify: `src/django_bpp/settings/base.py:437-438` (INSTALLED_APPS),
  `:960-961` (TABULAR_PERMISSIONS_CONFIG)
- Modify: `src/django_bpp/urls.py:218-219`
- Modify: `pyproject.toml:204`
- Modify: `src/django_bpp/django_compat.py:14` (komentarz)
- Delete (źródła aplikacji): `src/rozbieznosci_if/`, `src/rozbieznosci_pk/`
  **— UWAGA: migracje tych appów usuwamy dopiero po Task 9 (DROP). Patrz niżej.**

**Interfaces:** brak — usunięcie martwych referencji.

> **Kolejność względem Task 9:** najpierw Task 9 dodaje migrację DROP +
> sprzątanie (gdy stare appy jeszcze są w INSTALLED_APPS i baza je zna), POTEM
> Task 8 usuwa appy z kodu. Dlatego **wykonaj Task 9 PRZED Task 8** lub złącz je
> pod jedną bramką. Plan numeruje je osobno dla czytelności; **realnie 9 → 8**.

- [ ] **Step 1: INSTALLED_APPS** — usuń `"rozbieznosci_if",` i
  `"rozbieznosci_pk",`, zostaw `"rozbieznosci",`.

- [ ] **Step 2: TABULAR_PERMISSIONS_CONFIG (base.py ~960)** — usuń stare dwa,
  dodaj `"rozbieznosci",` w sekcji `["exclude"]["apps"]`.

- [ ] **Step 3: urls.py** — usuń dwa stare include, zostaw `rozbieznosci/`.

- [ ] **Step 4: pyproject.toml:204** — usuń `"rozbieznosci_if",`, dodaj
  `"rozbieznosci",` (zachowaj sortowanie listy pakietów).

- [ ] **Step 5: django_compat.py:14** — zaktualizuj komentarz, by nie wskazywał
  usuniętej migracji `rozbieznosci_if/migrations/0002…` (opisz, że shim
  pozostaje dla historycznych migracji baseline).

- [ ] **Step 6: Usuń katalogi źródłowe**

```bash
git rm -r src/rozbieznosci_if src/rozbieznosci_pk
```

- [ ] **Step 7: Weryfikacja**

Run: `uv run python src/manage.py check`
Run: `uv run pytest src/rozbieznosci/ -v`
Expected: brak błędów importu (nic w repo nie importuje już starych appów —
zweryfikuj `grep -rn "rozbieznosci_if\|rozbieznosci_pk" src/` = brak poza
ewentualnymi historycznymi migracjami innych appów, których NIE ruszamy).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(rozbieznosci): usuń stare aplikacje rozbieznosci_if/pk z konfiguracji"
```

---

### Task 9: Migracje DROP + sprzątanie + baseline (BRAMKA — potwierdzenie z użytkownikiem)

> **STOP — to obszar wymagający potwierdzenia użytkownika przed wykonaniem
> migracji** (reguła CLAUDE.md: zakaz edycji istniejących migracji; ostrożność
> z baseline). Wykonaj **PRZED** Task 8 (gdy stare tabele jeszcze istnieją).

**Files:**
- Create: `src/rozbieznosci/migrations/0002_usun_stare_rozbieznosci.py`
  (migracja `RunSQL` DROP + `RunPython` sprzątające ContentType/Permission)

**Interfaces:** brak — operacja na schemacie/danych.

- [ ] **Step 1: Ustal nazwy tabel i etykiety**

```bash
uv run python src/manage.py sqlmigrate rozbieznosci_if 0001 | head
# tabele: rozbieznosci_if_ignorujrozbieznoscif, rozbieznosci_if_rozbieznosciiflog
#         rozbieznosci_pk_ignorujrozbieznoscpk, rozbieznosci_pk_rozbieznoscipklog
```

- [ ] **Step 2: Napisz migrację `0002_usun_stare_rozbieznosci.py`**

```python
from django.db import migrations


TABELE = [
    "rozbieznosci_if_ignorujrozbieznoscif",
    "rozbieznosci_if_rozbieznosciiflog",
    "rozbieznosci_pk_ignorujrozbieznoscpk",
    "rozbieznosci_pk_rozbieznoscipklog",
]
APP_LABELS = ["rozbieznosci_if", "rozbieznosci_pk"]


def sprzataj_metadane(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    ContentType.objects.filter(app_label__in=APP_LABELS).delete()
    # Permission znika kaskadą po ContentType.
    # Wpisy django_migrations dla usuniętych appów:
    schema_editor.execute(
        "DELETE FROM django_migrations WHERE app IN (%s, %s)"
        % ("'rozbieznosci_if'", "'rozbieznosci_pk'")
    )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [("rozbieznosci", "0001_initial")]

    operations = [
        migrations.RunSQL(
            sql=[f'DROP TABLE IF EXISTS "{t}" CASCADE;' for t in TABELE],
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunPython(sprzataj_metadane, noop_reverse),
    ]
```

> Uwaga: `DROP TABLE … CASCADE` usuwa też FK/constrainty. To operacja
> nieodwracalna (start od zera — akceptowane). Stare appy MUSZĄ być jeszcze w
> INSTALLED_APPS w momencie `migrate`, by Django nie protestowało o brakujące
> stany migracji innych appów — dlatego ta migracja idzie PRZED Task 8.

- [ ] **Step 3: POTWIERDZENIE UŻYTKOWNIKA** — przedstaw migrację i poczekaj na
  „tak" przed `migrate`.

- [ ] **Step 4: Zastosuj migracje na czystym kontenerze (walidacja)**

Run: `uv run python src/manage.py migrate rozbieznosci`
Expected: 0001 + 0002 zastosowane bez błędu.

- [ ] **Step 5: Odśwież baseline (pełny rebuild)**

Run: `make rebuild-baseline`
(po `uv sync --extra baseline-rebuild`; wymaga Dockera)
Expected: `baseline-sql/baseline.sql` bez tabel starych appów; w
`baseline.meta.json` zaktualizowany stan.

- [ ] **Step 6: Commit (baseline + migracja)**

```bash
git add src/rozbieznosci/migrations/0002_usun_stare_rozbieznosci.py \
        baseline-sql/baseline.sql baseline-sql/baseline.meta.json
git commit -m "feat(rozbieznosci): DROP starych tabel + sprzątanie metadanych + baseline"
```

> Po Task 9 → wykonaj Task 8 (usunięcie kodu starych appów). Następnie pełna
> walidacja: `uv run python src/manage.py makemigrations --check --dry-run`
> (brak driftu) i `uv run pytest src/rozbieznosci/`.

---

### Task 10: Newsfragment + finalna walidacja

**Files:**
- Create: `src/bpp/newsfragments/+scalenie-rozbieznosci.feature.md`

- [ ] **Step 1: Newsfragment (perspektywa użytkownika)**

```markdown
Funkcje „rozbieżności punktacji IF" i „rozbieżności punktacji MNiSW" zostały
połączone w jedną opcję „rozbieżności punktacji/kwartyli", rozszerzoną o
kwartyle Scopus i WoS. Domyślnie pomijane są rekordy, w których źródło ma
wartość 0 lub brak — można je odsłonić przełącznikiem.
```

- [ ] **Step 2: ruff + pre-commit**

Run: `ruff format src/rozbieznosci/`
Run: `ruff check src/rozbieznosci/`  (poprawki ręcznie)
Run: `pre-commit`  (bez argumentów)

- [ ] **Step 3: Pełna walidacja**

Run: `uv run pytest src/rozbieznosci/`
Run: `uv run python src/manage.py makemigrations --check --dry-run`
Expected: testy PASS, brak driftu migracji.

- [ ] **Step 4: Commit**

```bash
git add src/bpp/newsfragments/+scalenie-rozbieznosci.feature.md
git commit -m "docs(rozbieznosci): newsfragment scalenia rozbieżności punktacji/kwartyli"
```

---

## Self-Review (autor planu)

**Pokrycie specu:**
- Rejestr 4 metryk → Task 1. ✔
- Wspólne modele (FK zamiast GenericFK) → Task 2. ✔
- Queryset + filtr zer/NULL (skalar `=0`, kwartyl `isnull`) → Task 3. ✔
- Jednostronne ustawianie per-rekord + bulk, recalc tylko mnisw → Task 3/4/5. ✔
- Eksport XLSX, Celery, status HTMX z `task_id` → Task 5. ✔
- Zakładki + threading `pokaz_puste_zrodla` (FilterForm→linki→confirm→POST) →
  Task 4/5/6. ✔
- Akcja „zignoruj" zachowana → Task 4/6. ✔
- Menu jedno + kafelek uczelnia + INSTALLED_APPS + tabular perms + pyproject +
  django_compat → Task 7/8. ✔
- Usunięcie starych appów: DROP + sprzątanie ContentType/Permission/
  django_migrations + rebuild-baseline → Task 9. ✔
- Korekta obsługi błędów (rollbar zamiast cichego połykania) → Task 3
  (`ustaw_ze_zrodla`). ✔
- Pominięcie `pbn_queued` → Task 5 (`TaskStatusView` go nie używa). ✔
- Newsfragment → Task 10. ✔

**Spójność typów/nazw:** `ustaw_ze_zrodla(pks, metryka, user_id)` (core) vs
`task_ustaw_ze_zrodla(self, pks, metryka_slug, user_id)` (tasks) — task przyjmuje
slug i resolve'uje na `Metryka`, woła core. Spójne. `get_base_queryset_for_metryka`,
`apply_filters`, `apply_sorting` — jednolite w core i widokach.

**Uwagi dot. ryzyka (dla wykonawcy):**
- Wywołanie taska w teście (`bind=True`) — dostosuj do API Celery (patrz Task 5).
- `wc.punktacja_zrodla()` może rzucić `DoesNotExist` — złap wąsko (Task 3).
- Kolejność Task 9 → Task 8 (DROP zanim usuniesz kod appów).
- Filtr `pokaz_puste_zrodla` to też filtr w komórce tabeli przez prosty
  template-filter `attr` (Task 6) — alternatywnie anotuj wartości w widoku.
