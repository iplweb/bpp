# Maksymalizacja przekładalności Multiseek → DjangoQL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sprawić, by konwerter formularza Multiseek → DjangoQL przekładał (best-effort) niemal każde pole rejestru, z dokładną semantyką tam, gdzie się da, a w szufladzie pokazywał zapytanie sformatowane i podświetlone składniowo.

**Architecture:** Silnik `djangoql_export.py` zyskuje (a) honorowanie deklaratywnej ścieżki `djangoql_field_name`, (b) gałąź value-list emitującą `<ścieżka>.nazwa = "wartość"` (opt-in przez `djangoql_value_field`), (c) obsługę pustej wartości (`= ""` / `__rel = None`), (d) kontrakt liścia mogący nieść ostrzeżenie. Pola dostają deklaratywne atrybuty lub metody `to_djangoql`. Nowe pole wirtualne `charakter_z_podrzednymi__rel` (MPTT) odwzorowuje „+ podrzędne" dla charakteru. UI: moduł JS formatuje + podświetla zapytanie używając lexera DjangoQL.

**Tech Stack:** Django, multiseek, djangoql (`DjangoQLParser`, `AutocompleteField`, `apply_search`), django-mptt, model_bakery, pytest, Foundation/SCSS, Playwright.

**Spec:** `docs/superpowers/specs/2026-06-05-multiseek-djangoql-translatability-design.md`

---

## File Structure

- `src/bpp/multiseek_registry/djangoql_export.py` — silnik: `_orm_name`, `_value_list_leaf`, kontrakt ostrzeżeń, pusta wartość.
- `src/bpp/djangoql_schema.py` — pole wirtualne `charakter_z_podrzednymi__rel` + wpięcie.
- `src/bpp/multiseek_registry/fields/*.py` — atrybuty deklaratywne i metody `to_djangoql`.
- `src/bpp/static/bpp/js/djangoql-pretty.js` — formatter + highlighter (UI).
- `src/django_bpp/templates/multiseek/index.html` — szuflada (UI).
- Testy: `src/bpp/tests/test_multiseek_djangoql_*.py` (rozbudowa), nowy `test_multiseek_djangoql_value_list.py`, `test_charakter_podrzedne_field.py`, `test_multiseek_djangoql_coverage.py`, Playwright w `test_multiseek_djangoql_button.py`.

### Konwencja kontraktu liścia (obowiązuje cały plan)

Metoda `to_djangoql(value, operation)` oraz wewnętrzne helpery liścia mogą zwrócić:
- `str` — sam fragment DjangoQL,
- `(str, str)` — `(fragment, ostrzeżenie)`,
- `None` — nieprzekładalne.

`leaf_to_djangoql(registry, leaf, warnings=None)` normalizuje to: rozpakowuje krotkę, dokleja ostrzeżenie do `warnings` (jeśli podano), waliduje fragment względem schematu i zwraca `str | None`.

---

## PHASE 1 — Silnik (`djangoql_export.py`)

### Task 1: Deklaratywna ścieżka `djangoql_field_name` (A1)

**Files:**
- Modify: `src/bpp/multiseek_registry/djangoql_export.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_export.py`

- [ ] **Step 1: Write the failing test**

Dopisz na końcu `test_multiseek_djangoql_export.py`:

```python
def test_orm_name_prefers_djangoql_field_name():
    from bpp.multiseek_registry.djangoql_export import _orm_name

    class F:
        field_name = "wydzial"
        djangoql_field_name = "autorzy__jednostka__wydzial"

    assert _orm_name(F()) == "autorzy__jednostka__wydzial"


def test_orm_name_falls_back_to_field_name():
    from bpp.multiseek_registry.djangoql_export import _orm_name

    class F:
        field_name = "rok"

    assert _orm_name(F()) == "rok"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py::test_orm_name_prefers_djangoql_field_name -v`
Expected: FAIL — `ImportError: cannot import name '_orm_name'`.

- [ ] **Step 3: Add `_orm_name` and use it in leaf helpers**

W `djangoql_export.py` dodaj helper i podmień `field.field_name` w `_autocomplete_leaf` oraz `_default_leaf` na `_orm_name(field)`:

```python
def _orm_name(field):
    """Realna ścieżka ORM pola: djangoql_field_name (override) albo field_name."""
    return getattr(field, "djangoql_field_name", None) or getattr(
        field, "field_name", None
    )
```

W `_autocomplete_leaf` zmień:
```python
    rel_path = _orm_path_to_djangoql(field.field_name) + "__rel"
```
na:
```python
    name = _orm_name(field)
    if not name:
        return None
    rel_path = _orm_path_to_djangoql(name) + "__rel"
```

W `_default_leaf` zmień `name = getattr(field, "field_name", None)` na `name = _orm_name(field)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -v`
Expected: PASS (nowe + dotychczasowe).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/djangoql_export.py src/bpp/tests/test_multiseek_djangoql_export.py
git commit -m "feat(djangoql-export): honoruj djangoql_field_name jako ścieżkę ORM"
```

---

### Task 2: Kontrakt liścia z ostrzeżeniem (warning-tuple)

**Files:**
- Modify: `src/bpp/multiseek_registry/djangoql_export.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_export.py`

- [ ] **Step 1: Write the failing test**

```python
def test_leaf_to_djangoql_collects_warning_from_tuple(monkeypatch):
    from bpp.multiseek_registry import djangoql_export as dx

    class Fake:
        type = None
        field_name = "rok"

        def to_djangoql(self, value, operation):
            return ("rok = 2024", "uwaga testowa")

    reg = type("R", (), {"field_by_name": {"X": Fake()}})()
    warnings = []
    frag = dx.leaf_to_djangoql(
        reg, {"field": "X", "operator": "equals", "value": 2024}, warnings
    )
    assert frag == "rok = 2024"
    assert warnings == ["uwaga testowa"]


def test_leaf_to_djangoql_str_still_works():
    from bpp.multiseek_registry import djangoql_export as dx
    from multiseek.logic import CONTAINS

    frag = dx.leaf_to_djangoql(
        registry,
        {"field": "Tytuł pracy", "operator": str(CONTAINS), "value": "x"},
    )
    assert frag == 'tytul_oryginalny ~ "x"'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest "src/bpp/tests/test_multiseek_djangoql_export.py::test_leaf_to_djangoql_collects_warning_from_tuple" -v`
Expected: FAIL — `leaf_to_djangoql()` przyjmuje 2 argumenty / nie zbiera ostrzeżenia.

- [ ] **Step 3: Extend `leaf_to_djangoql` and thread warnings**

Zmień sygnaturę i logikę `leaf_to_djangoql`:

```python
def leaf_to_djangoql(registry, leaf, warnings=None):
    """Fragment DjangoQL dla pojedynczego warunku, albo None (nieprzekładalny).

    Wartość z dispatchera może być str, (str, warning) albo None. Ostrzeżenie
    (jeśli jest i podano `warnings`) trafia do listy. None gdy: nieznane pole,
    nieobsługiwana operacja, albo fragment nie waliduje się względem schematu.
    """
    if not isinstance(leaf, dict):
        return None
    field = registry.field_by_name.get(leaf.get("field"))
    if field is None:
        return None
    value = leaf.get("value")
    operation = leaf.get("operator")
    if operation is None:
        return None
    override = getattr(field, "to_djangoql", None)
    if callable(override):
        result = override(value, operation)
    else:
        result = _default_leaf(field, value, operation)
    frag, warn = result if isinstance(result, tuple) else (result, None)
    if warn and warnings is not None:
        warnings.append(warn)
    if frag is None:
        return None
    return frag if is_valid_rekord_djangoql(frag) else None
```

W `_append_leaf` przekaż `warnings` do obu wywołań `leaf_to_djangoql(registry, leaf)` → `leaf_to_djangoql(registry, leaf, warnings)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/djangoql_export.py src/bpp/tests/test_multiseek_djangoql_export.py
git commit -m "feat(djangoql-export): liść może nieść ostrzeżenie (str|tuple|None)"
```

---

### Task 3: Gałąź value-list `<ścieżka>.nazwa = "wartość"` (A2)

**Files:**
- Modify: `src/bpp/multiseek_registry/djangoql_export.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_value_list.py` (nowy)

Aktywacja opt-in: tylko gdy pole ma `djangoql_value_field` (NIE po `type`, bo
booleany też mają `type == 'value-list'`).

- [ ] **Step 1: Write the failing test**

Utwórz `src/bpp/tests/test_multiseek_djangoql_value_list.py`:

```python
from multiseek.logic import DIFFERENT, EQUAL

from bpp.multiseek_registry.djangoql_export import _value_list_leaf
from bpp.multiseek_registry.fields.constants import UNION


class _VL:
    field_name = "jezyk"
    djangoql_value_field = "nazwa"


def test_value_list_equal():
    assert _value_list_leaf(_VL(), "polski", str(EQUAL)) == 'jezyk.nazwa = "polski"'


def test_value_list_different():
    assert _value_list_leaf(_VL(), "polski", str(DIFFERENT)) == 'jezyk.nazwa != "polski"'


def test_value_list_empty_value():
    assert _value_list_leaf(_VL(), "", str(EQUAL)) == 'jezyk.nazwa = ""'


def test_value_list_union_warns():
    frag, warn = _value_list_leaf(_VL(), "polski", str(UNION))
    assert frag == 'jezyk.nazwa = "polski"'
    assert "wspóln" in warn.lower()


def test_value_list_respects_djangoql_field_name():
    class VL2:
        field_name = "typ_odpowiedzialnosci"
        djangoql_field_name = "autorzy__typ_odpowiedzialnosci"
        djangoql_value_field = "nazwa"

    assert (
        _value_list_leaf(VL2(), "autor", str(EQUAL))
        == 'autorzy.typ_odpowiedzialnosci.nazwa = "autor"'
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_value_list.py -v`
Expected: FAIL — `ImportError: cannot import name '_value_list_leaf'`.

- [ ] **Step 3: Implement `_value_list_leaf` and route to it**

Dodaj import `UNION_OPS_ALL` (z `.fields.constants`) NIE — użyj lokalnej detekcji. Dodaj helpery i funkcję:

```python
def _is_union(operation):
    """True gdy operator multiseek to wariant UNION (równy+wspólny…)."""
    from bpp.multiseek_registry.fields.constants import UNION_OPS_ALL

    s = str(operation)
    return s in {str(o) for o in UNION_OPS_ALL}


_UNION_WARNING = (
    "Operator „wspólny" przełożono jak zwykłą równość — w DjangoQL może objąć "
    "inny wiersz autora niż pozostałe kryteria."
)


def _value_list_leaf(field, value, operation):
    """value-list (lista stringów) -> '<ścieżka>.<pole> = \"wartość\"'.

    Aktywne tylko dla pól z atrybutem `djangoql_value_field`. UNION → '='
    z ostrzeżeniem. Pusta wartość → '= \"\"'.
    """
    name = _orm_name(field)
    value_field = getattr(field, "djangoql_value_field", None)
    if not name or not value_field:
        return None
    op = str(operation)
    diff_strs = {str(o) for o in DIFFERENT_ALL}
    if op in diff_strs:
        dql_op = "!="
    elif op in {str(o) for o in EQUALITY_OPS_ALL} - diff_strs or _is_union(op):
        dql_op = "="
    else:
        return None
    path = _orm_path_to_djangoql(name)
    frag = f"{path}.{value_field} {dql_op} {render_value(value or '')}"
    if _is_union(op):
        return frag, _UNION_WARNING
    return frag
```

W `_default_leaf`, ZARAZ po gałęzi AUTOCOMPLETE, dodaj:

```python
    if getattr(field, "djangoql_value_field", None):
        return _value_list_leaf(field, value, operation)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_value_list.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/djangoql_export.py src/bpp/tests/test_multiseek_djangoql_value_list.py
git commit -m "feat(djangoql-export): gałąź value-list -> <ścieżka>.nazwa (opt-in)"
```

---

### Task 4: Pusta wartość autocomplete → `__rel = None` (A3)

**Files:**
- Modify: `src/bpp/multiseek_registry/djangoql_export.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_export.py`

- [ ] **Step 1: Write the failing test**

```python
def test_autocomplete_empty_value_is_null():
    from bpp.multiseek_registry.djangoql_export import _autocomplete_leaf
    from multiseek.logic import EQUAL_NONE

    class FK:
        field_name = "zrodlo"
        type = "autocomplete"

        def value_from_web(self, value):
            return None

    assert _autocomplete_leaf(FK(), None, str(EQUAL_NONE)) == "zrodlo__rel = None"


def test_autocomplete_empty_value_is_null_diff():
    from bpp.multiseek_registry.djangoql_export import _autocomplete_leaf
    from multiseek.logic import DIFFERENT_NONE

    class FK:
        field_name = "zrodlo"
        type = "autocomplete"

        def value_from_web(self, value):
            return None

    assert _autocomplete_leaf(FK(), None, str(DIFFERENT_NONE)) == "zrodlo__rel != None"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py::test_autocomplete_empty_value_is_null -v`
Expected: FAIL — zwraca `None` zamiast `"zrodlo__rel = None"`.

- [ ] **Step 3: Handle empty value in `_autocomplete_leaf`**

W `_autocomplete_leaf`, po ustaleniu `rel_op` i PRZED `obj = field.value_from_web(value)`, dodaj wyznaczenie ścieżki i obsługę pustki:

```python
    name = _orm_name(field)
    if not name:
        return None
    rel_path = _orm_path_to_djangoql(name) + "__rel"
    if value in (None, ""):
        return f"{rel_path} = None" if rel_op == "=" else f"{rel_path} != None"
```

Usuń późniejsze ponowne wyznaczanie `rel_path` (zostaw jedno). Zachowaj `if obj is None: return None` dla niepustej-ale-nierozwiązywalnej wartości.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/djangoql_export.py src/bpp/tests/test_multiseek_djangoql_export.py
git commit -m "feat(djangoql-export): pusty autocomplete -> __rel = None (is-null)"
```

---

## PHASE 2 — Pole wirtualne charakteru (`djangoql_schema.py`)

### Task 5: `CharakterZPodrzednymiField` + wpięcie (A4)

**Files:**
- Modify: `src/bpp/djangoql_schema.py`
- Test: `src/bpp/tests/test_charakter_podrzedne_field.py` (nowy)

- [ ] **Step 1: Write the failing test**

Utwórz `src/bpp/tests/test_charakter_podrzedne_field.py`:

```python
import pytest
from djangoql.queryset import apply_search
from model_bakery import baker

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Charakter_Formalny, Rekord

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_charakter_z_podrzednymi_field_present_on_rekord():
    s = BppQLSchema(Rekord)
    fields = s.get_fields(Rekord)
    assert "charakter_z_podrzednymi__rel" in fields


@pytest.mark.django_db
def test_charakter_z_podrzednymi_matches_descendants(
    wydawnictwo_ciagle, denorms
):
    parent = baker.make(Charakter_Formalny, nazwa="Artykuły", skrot="ART")
    child = baker.make(
        Charakter_Formalny, nazwa="Artykuł oryginalny", skrot="AO", parent=parent
    )
    Charakter_Formalny.objects.rebuild()
    wydawnictwo_ciagle.charakter_formalny = child
    wydawnictwo_ciagle.save()
    denorms.flush()

    frag = f'charakter_z_podrzednymi__rel = "Artykuły [{parent.pk}]"'
    pks = set(
        apply_search(Rekord.objects.all(), frag, schema=BppQLSchema)
        .distinct()
        .values_list("pk", flat=True)
    )
    assert wydawnictwo_ciagle.rekord_set.first().pk in pks
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_charakter_podrzedne_field.py -v`
Expected: FAIL — pole nieobecne / fragment nie waliduje.

- [ ] **Step 3: Implement the virtual field and wire it**

W `djangoql_schema.py`:

Import modelu (góra pliku, obok `from bpp.models import Jednostka`):
```python
from bpp.models import Charakter_Formalny, Jednostka
```

Stała obok `_SUBUNITS_FIELD`:
```python
#: Wirtualne pole: picker po Charakterze Formalnym dopasowujący MPTT-descendants.
_CHARAKTER_SUB_FIELD = "charakter_z_podrzednymi__rel"
```

Klasa (po `JednostkaZPodjednostkamiField`):
```python
class CharakterZPodrzednymiField(AutocompleteField):
    """Picker po Charakter_Formalny: dopasowuje rekordy o tym charakterze ORAZ
    wszystkich potomkach w drzewie MPTT (sam + descendants).

    Odwzorowuje CharakterFormalnyQueryObject.real_query:
        Q(charakter_formalny__in=value.get_descendants(include_self=True))
    """

    def get_lookup(self, path, operator, value):
        parsed = self.parse_id(value)
        if not isinstance(parsed, int):
            q = Q(charakter_formalny__nazwa__icontains=str(value))
            return ~q if operator in ("!=", "not in") else q
        try:
            ch = Charakter_Formalny.objects.get(pk=parsed)
        except Charakter_Formalny.DoesNotExist:
            return Q() if operator in ("!=", "not in") else Q(pk__in=[])
        q = Q(charakter_formalny__in=ch.get_descendants(include_self=True))
        return ~q if operator in ("!=", "not in") else q
```

Predykat obok `_has_autorzy_jednostka`:
```python
def _has_charakter_formalny(model):
    """True, gdy model ma FK 'charakter_formalny' (Rekord/cache)."""
    try:
        f = model._meta.get_field("charakter_formalny")
    except FieldDoesNotExist:
        return False
    return getattr(f, "many_to_one", False)
```

W `RelPickerSchemaMixin.get_fields`, po bloku `if _has_autorzy_jednostka(model):`:
```python
        if _has_charakter_formalny(model):
            fields.append(_CHARAKTER_SUB_FIELD)
```

W `RelPickerSchemaMixin.get_field_instance`, na początku (obok bloku `_SUBUNITS_FIELD`):
```python
        if field_name == _CHARAKTER_SUB_FIELD:
            return CharakterZPodrzednymiField(
                model=model,
                name=_CHARAKTER_SUB_FIELD,
                nullable=True,
                queryset=_visible_qs(Charakter_Formalny),
                search_fields=_label_fields(Charakter_Formalny),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_charakter_podrzedne_field.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/djangoql_schema.py src/bpp/tests/test_charakter_podrzedne_field.py
git commit -m "feat(djangoql-schema): pole wirtualne charakter_z_podrzednymi__rel (MPTT)"
```

---

## PHASE 3 — Pola rejestru

### Task 6: Deklaratywne ścieżki autocomplete (B1)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/unit_fields.py`, `author_fields.py`, `boolean_fields.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_fields_b1.py` (nowy)

Dodajemy `djangoql_field_name` (realna ścieżka ORM) do pól autocomplete, których `field_name` ≠ ścieżka. Domyślny dispatcher zrobi `<ścieżka>__rel`.

- [ ] **Step 1: Write the failing test**

Utwórz `src/bpp/tests/test_multiseek_djangoql_fields_b1.py`:

```python
import pytest
from model_bakery import baker
from multiseek.logic import EQUAL

from bpp.models import Kierunek_Studiow
from bpp.models.struktura import Wydzial
from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_wydzial_maps_to_nested_rel():
    w = baker.make(Wydzial, nazwa="Wydział Lekarski")
    frag = leaf_to_djangoql(
        registry, {"field": "Wydział", "operator": str(EQUAL), "value": w.pk}
    )
    assert frag == f'autorzy.jednostka.wydzial__rel = "Wydział Lekarski [{w.pk}]"'


@pytest.mark.django_db
def test_kierunek_maps_to_nested_rel():
    k = baker.make(Kierunek_Studiow, nazwa="Lekarski")
    frag = leaf_to_djangoql(
        registry, {"field": "Kierunek studiów", "operator": str(EQUAL), "value": k.pk}
    )
    assert frag == f'autorzy.kierunek_studiow__rel = "Lekarski [{k.pk}]"'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_fields_b1.py -v`
Expected: FAIL — fragmenty `wydzial__rel`/`nazwa__rel` nie walidują → `None`.

- [ ] **Step 3: Add `djangoql_field_name` attributes**

W `unit_fields.py`:
- `WydzialQueryObject`: dodaj atrybut klasy `djangoql_field_name = "autorzy__jednostka__wydzial"`.

W `boolean_fields.py`:
- `KierunekStudiowQueryObject`: dodaj `djangoql_field_name = "autorzy__kierunek_studiow"`.

W `author_fields.py`:
- `DyscyplinaQueryObject`: dodaj `djangoql_field_name = "autorzy__dyscyplina_naukowa"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_fields_b1.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/unit_fields.py src/bpp/multiseek_registry/fields/boolean_fields.py src/bpp/multiseek_registry/fields/author_fields.py src/bpp/tests/test_multiseek_djangoql_fields_b1.py
git commit -m "feat(multiseek): deklaratywne ścieżki djangoql_field_name (Wydział/Kierunek/Dyscyplina)"
```

---

### Task 7: Value-list deklaratywny `.nazwa` (B2)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/numeric_fields.py` (Język), `factories.py` (value-list factory), `publication_type_fields.py` (Typ odpowiedzialności)
- Test: `src/bpp/tests/test_multiseek_djangoql_value_list.py`

`create_valuelist_query_object` ma ustawiać `djangoql_value_field = "nazwa"` na wytwarzanych klasach (TypKBN, OpenAccess×3). Pola pisane ręcznie dostają atrybut wprost.

- [ ] **Step 1: Write the failing test**

Dopisz do `test_multiseek_djangoql_value_list.py`:

```python
import pytest
from model_bakery import baker
from multiseek.logic import EQUAL

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql


@pytest.mark.django_db
@pytest.mark.serial
def test_jezyk_maps_to_nazwa():
    frag = leaf_to_djangoql(
        registry, {"field": "Język", "operator": str(EQUAL), "value": "polski"}
    )
    assert frag == 'jezyk.nazwa = "polski"'


@pytest.mark.django_db
@pytest.mark.serial
def test_typ_kbn_maps_to_nazwa():
    from bpp.models.system import Typ_KBN

    baker.make(Typ_KBN, nazwa="PO")
    frag = leaf_to_djangoql(
        registry, {"field": "Typ MNiSW/MEiN", "operator": str(EQUAL), "value": "PO"}
    )
    assert frag == 'typ_kbn.nazwa = "PO"'


@pytest.mark.django_db
@pytest.mark.serial
def test_typ_odpowiedzialnosci_maps_to_nested_nazwa():
    frag = leaf_to_djangoql(
        registry,
        {"field": "Typ odpowiedzialności", "operator": str(EQUAL), "value": "autor"},
    )
    assert frag == 'autorzy.typ_odpowiedzialnosci.nazwa = "autor"'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_value_list.py::test_jezyk_maps_to_nazwa -v`
Expected: FAIL.

- [ ] **Step 3: Set `djangoql_value_field` (+ path where needed)**

W `numeric_fields.py`:
- `JezykQueryObject`: dodaj `djangoql_value_field = "nazwa"`.

W `factories.py` w `create_valuelist_query_object`, do `class_attrs` dodaj:
```python
        "djangoql_value_field": name_field,
```
(`name_field` to istniejący argument, domyślnie `"nazwa"`). Obejmuje TypKBN, OpenaccessWersjaTekstu/Licencja/CzasPublikacji.

W `publication_type_fields.py`:
- `Typ_OdpowiedzialnosciQueryObject`: dodaj `djangoql_field_name = "autorzy__typ_odpowiedzialnosci"` oraz `djangoql_value_field = "nazwa"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_value_list.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/numeric_fields.py src/bpp/multiseek_registry/fields/factories.py src/bpp/multiseek_registry/fields/publication_type_fields.py src/bpp/tests/test_multiseek_djangoql_value_list.py
git commit -m "feat(multiseek): value-list -> .nazwa (Język/TypKBN/OpenAccess/TypOdpowiedzialności)"
```

---

### Task 8: Deklaratywne booleany przez `autorzy` (B3-bool)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/boolean_fields.py`, `author_fields.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_fields_bool.py` (nowy)

`Afiliuje` i `Oświadczenie KEN` to booleany; wartość to bool. Wystarczy `djangoql_field_name` → skalarna gałąź da `autorzy.<pole> = True/False`.

- [ ] **Step 1: Write the failing test**

Utwórz `src/bpp/tests/test_multiseek_djangoql_fields_bool.py`:

```python
import pytest
from multiseek.logic import EQUAL

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_afiliuje_true():
    frag = leaf_to_djangoql(
        registry, {"field": "Afiliuje", "operator": str(EQUAL), "value": True}
    )
    assert frag == "autorzy.afiliuje = True"


@pytest.mark.django_db
def test_oswiadczenie_ken_false():
    frag = leaf_to_djangoql(
        registry,
        {"field": "Oświadczenie KEN", "operator": str(EQUAL), "value": False},
    )
    assert frag == "autorzy.oswiadczenie_ken = False"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_fields_bool.py -v`
Expected: FAIL — `afiliuje = True` nie waliduje (brak pola na Rekord) → None.

- [ ] **Step 3: Add `djangoql_field_name` to the two booleans**

W `boolean_fields.py`:
- `AfiliujeQueryObject`: dodaj `djangoql_field_name = "autorzy__afiliuje"`.

W `author_fields.py`:
- `OswiadczenieKENQueryObject`: dodaj `djangoql_field_name = "autorzy__oswiadczenie_ken"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_fields_bool.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/boolean_fields.py src/bpp/multiseek_registry/fields/author_fields.py src/bpp/tests/test_multiseek_djangoql_fields_bool.py
git commit -m "feat(multiseek): Afiliuje/Oświadczenie KEN -> autorzy.<pole> = bool"
```

---

### Task 9: Charakter formalny (+podrzędne), ogólny, typ rekordu (B3)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/publication_type_fields.py`
- Test: `src/bpp/tests/test_multiseek_charakter_to_djangoql.py` (nowy)

- [ ] **Step 1: Write the failing test**

Utwórz `src/bpp/tests/test_multiseek_charakter_to_djangoql.py`:

```python
import pytest
from model_bakery import baker
from multiseek.logic import DIFFERENT, EQUAL

from bpp.models import Charakter_Formalny
from bpp.multiseek_registry import registry

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_charakter_formalny_maps_to_virtual_field():
    ch = baker.make(Charakter_Formalny, nazwa="Artykuł", skrot="AC")
    Charakter_Formalny.objects.rebuild()
    field = registry.field_by_name["Charakter formalny"]
    frag = field.to_djangoql("Artykuł", str(EQUAL))
    assert frag == f'charakter_z_podrzednymi__rel = "Artykuł [{ch.pk}]"'


@pytest.mark.django_db
def test_charakter_formalny_strips_indent_prefix():
    ch = baker.make(Charakter_Formalny, nazwa="Artykuł", skrot="AC")
    Charakter_Formalny.objects.rebuild()
    field = registry.field_by_name["Charakter formalny"]
    frag = field.to_djangoql("--- Artykuł", str(EQUAL))
    assert frag == f'charakter_z_podrzednymi__rel = "Artykuł [{ch.pk}]"'


@pytest.mark.django_db
def test_charakter_formalny_different():
    ch = baker.make(Charakter_Formalny, nazwa="Artykuł", skrot="AC")
    Charakter_Formalny.objects.rebuild()
    field = registry.field_by_name["Charakter formalny"]
    frag = field.to_djangoql("Artykuł", str(DIFFERENT))
    assert frag == f'charakter_z_podrzednymi__rel != "Artykuł [{ch.pk}]"'


def test_charakter_ogolny_artykul():
    field = registry.field_by_name["Charakter formalny ogólny"]
    assert field.to_djangoql("artykuł", str(EQUAL)) == 'charakter_formalny.charakter_ogolny = "art"'


def test_charakter_ogolny_ksiazka():
    field = registry.field_by_name["Charakter formalny ogólny"]
    assert field.to_djangoql("książka", str(EQUAL)) == 'charakter_formalny.charakter_ogolny = "ksi"'


def test_typ_rekordu_publikacje():
    field = registry.field_by_name["Typ rekordu"]
    assert field.to_djangoql("publikacje", str(EQUAL)) == "charakter_formalny.publikacja = True"


def test_typ_rekordu_inne():
    field = registry.field_by_name["Typ rekordu"]
    assert (
        field.to_djangoql("inne", str(EQUAL))
        == "(charakter_formalny.publikacja = False and charakter_formalny.streszczenie = False)"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_charakter_to_djangoql.py -v`
Expected: FAIL — `to_djangoql` nieobecne / zwraca None.

- [ ] **Step 3: Implement the three `to_djangoql` methods**

W `publication_type_fields.py` dodaj importy stałych operatorów na górze:
```python
from multiseek.logic import DIFFERENT_ALL, EQUALITY_OPS_ALL
```
(`DIFFERENT`, `EQUAL`, `EQUALITY_OPS_ALL` częściowo już są — uzupełnij brakujące, unikaj duplikatów.)

`CharakterFormalnyQueryObject` — dodaj metodę:
```python
    def to_djangoql(self, value, operation):
        """charakter_z_podrzednymi__rel (MPTT: sam + potomkowie) — dokładne."""
        obj = self.value_from_web(value)
        if obj is None:
            return None
        op = str(operation)
        diff = {str(o) for o in DIFFERENT_ALL}
        if op in diff:
            rel_op = "!="
        elif op in {str(o) for o in EQUALITY_OPS_ALL} - diff:
            rel_op = "="
        else:
            return None
        label = str(obj.nazwa).replace("\\", "\\\\").replace('"', '\\"')
        return f'charakter_z_podrzednymi__rel {rel_op} "{label} [{obj.pk}]"'
```

`CharakterOgolnyQueryObject` — dodaj metodę:
```python
    _DJANGOQL_OGOLNY = {
        "artykuł": const.CHARAKTER_OGOLNY_ARTYKUL,
        "rozdział": const.CHARAKTER_OGOLNY_ROZDZIAL,
        "książka": const.CHARAKTER_OGOLNY_KSIAZKA,
        "inne": const.CHARAKTER_OGOLNY_INNE,
    }

    def to_djangoql(self, value, operation):
        kod = self._DJANGOQL_OGOLNY.get(value)
        if kod is None:
            return None
        op = "!=" if str(operation) in {str(o) for o in DIFFERENT_ALL} else "="
        return f'charakter_formalny.charakter_ogolny {op} "{kod}"'
```

`TypRekorduObject` — dodaj metodę:
```python
    def to_djangoql(self, value, operation):
        neg = str(operation) in {str(o) for o in DIFFERENT_ALL}
        if value == "publikacje":
            frag = "charakter_formalny.publikacja = True"
        elif value == "streszczenia":
            frag = "charakter_formalny.streszczenie = True"
        elif value == "inne":
            frag = (
                "(charakter_formalny.publikacja = False "
                "and charakter_formalny.streszczenie = False)"
            )
        else:
            return None
        if neg:
            return None  # negacja zbioru -> brak czystego not(...) w DjangoQL
        return frag
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_charakter_to_djangoql.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/publication_type_fields.py src/bpp/tests/test_multiseek_charakter_to_djangoql.py
git commit -m "feat(multiseek): Charakter formalny/ogólny/Typ rekordu -> DjangoQL"
```

---

### Task 10: Typ ogólny autora (autor + typ_odpowiedzialności) (B3 compound)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/author_fields.py`
- Test: `src/bpp/tests/test_multiseek_autor_to_djangoql.py` (rozbudowa)

`TypOgolnyAutorQueryObject` i 3 podklasy: `autorzy.autor__rel = "L [pk]" and autorzy.typ_odpowiedzialnosci.typ_ogolny = N` (same-row, dokładne).

- [ ] **Step 1: Write the failing test**

Dopisz do `test_multiseek_autor_to_djangoql.py`:

```python
@pytest.mark.django_db
def test_typ_ogolny_autor_compound():
    from bpp.models import Autor
    from bpp.multiseek_registry import registry

    a = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    field = registry.field_by_name["Autor"]
    frag = field.to_djangoql(a.pk, str(EQUAL))
    assert frag == (
        f'autorzy.autor__rel = "{a} [{a.pk}]" '
        "and autorzy.typ_odpowiedzialnosci.typ_ogolny = 0"
    )


@pytest.mark.django_db
def test_typ_ogolny_redaktor_compound():
    from bpp.models import Autor
    from bpp.multiseek_registry import registry

    a = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    field = registry.field_by_name["Redaktor"]
    frag = field.to_djangoql(a.pk, str(EQUAL))
    assert frag.endswith("and autorzy.typ_odpowiedzialnosci.typ_ogolny = 1")
```

(Upewnij się, że plik ma `import pytest`, `from model_bakery import baker`, `from multiseek.logic import EQUAL`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_autor_to_djangoql.py::test_typ_ogolny_autor_compound -v`
Expected: FAIL — odziedziczone `to_djangoql` z `NazwiskoIImieQueryObject` zwraca None dla podklas.

- [ ] **Step 3: Override `to_djangoql` on `TypOgolnyAutorQueryObject`**

W `author_fields.py`, w `TypOgolnyAutorQueryObject` dodaj metodę (po `real_query`):
```python
    def to_djangoql(self, value, operation):
        op = str(operation)
        diff = {str(o) for o in DIFFERENT_ALL}
        equal = {str(o) for o in EQUALITY_OPS_ALL} - diff
        if op in diff:
            return None  # negacja koniunkcji nie ma czystego not(...) w DjangoQL
        if op not in equal and not _is_union_value(op):
            return None
        try:
            obj = self.value_from_web(value)
        except Exception:  # noqa: BLE001 — uszkodzony pk -> nieprzekładalne
            return None
        if obj is None:
            return None
        label = str(obj).replace("\\", "\\\\").replace('"', '\\"')
        frag = (
            f'autorzy.autor__rel = "{label} [{obj.pk}]" '
            f"and autorzy.typ_odpowiedzialnosci.typ_ogolny = {self.typ_ogolny}"
        )
        if _is_union_value(op):
            return frag, (
                "Operator „wspólny" przełożono jak równość — w DjangoQL może "
                "objąć inny wiersz autora."
            )
        return frag
```

Dodaj na górze `author_fields.py` (jeśli brak) import i mały helper:
```python
from .constants import UNION_OPS_ALL


def _is_union_value(operation):
    return str(operation) in {str(o) for o in UNION_OPS_ALL}
```
(Jeśli `UNION_OPS_ALL` już importowane — nie duplikuj.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_autor_to_djangoql.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/author_fields.py src/bpp/tests/test_multiseek_autor_to_djangoql.py
git commit -m "feat(multiseek): Autor/Redaktor/Tłumacz/Recenzent -> autor + typ_ogolny"
```

---

### Task 11: Booleany isnull / inwersja / złożone (B3)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/boolean_fields.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_fields_bool.py`

- [ ] **Step 1: Write the failing test**

Dopisz do `test_multiseek_djangoql_fields_bool.py`:

```python
@pytest.mark.django_db
def test_obca_jednostka_inverts_value():
    # "Obca jednostka = True" oznacza skupia_pracownikow = False
    field = registry.field_by_name["Obca jednostka"]
    assert field.to_djangoql(True, str(EQUAL)) == "autorzy.jednostka.skupia_pracownikow = False"


@pytest.mark.django_db
def test_dyscyplina_ustawiona_true():
    field = registry.field_by_name["Dyscyplina ustawiona"]
    assert field.to_djangoql(True, str(EQUAL)) == "autorzy.dyscyplina_naukowa != None"


@pytest.mark.django_db
def test_dyscyplina_ustawiona_false():
    field = registry.field_by_name["Dyscyplina ustawiona"]
    assert field.to_djangoql(False, str(EQUAL)) == "autorzy.dyscyplina_naukowa = None"


@pytest.mark.django_db
def test_licencja_oa_ustawiona_true():
    field = registry.field_by_name["OpenAccess: licencja ustawiona"]
    assert field.to_djangoql(True, str(EQUAL)) == "openaccess_licencja != None"


@pytest.mark.django_db
def test_strona_www_ustawiona_true():
    field = registry.field_by_name["Strona WWW ustawiona"]
    assert field.to_djangoql(True, str(EQUAL)) == '(www != "" or public_www != "")'
```

(Import `EQUAL` z `multiseek.logic` na górze pliku — jeśli brak, dodaj.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_fields_bool.py::test_obca_jednostka_inverts_value -v`
Expected: FAIL.

- [ ] **Step 3: Implement the four `to_djangoql` methods**

W `boolean_fields.py` (importy: `from multiseek.logic import DIFFERENT_ALL` jeśli brak).

`ObcaJednostkaQueryObject`:
```python
    def to_djangoql(self, value, operation):
        skupia = not bool(value)  # real_query robi value = not value
        return f"autorzy.jednostka.skupia_pracownikow = {skupia}"
```

`DyscyplinaUstawionaQueryObject`:
```python
    def to_djangoql(self, value, operation):
        return (
            "autorzy.dyscyplina_naukowa != None"
            if value
            else "autorzy.dyscyplina_naukowa = None"
        )
```

`LicencjaOpenAccessUstawionaQueryObject`:
```python
    def to_djangoql(self, value, operation):
        return (
            "openaccess_licencja != None" if value else "openaccess_licencja = None"
        )
```

`PublicDostepDniaQueryObject`:
```python
    def to_djangoql(self, value, operation):
        return (
            "public_dostep_dnia != None" if value else "public_dostep_dnia = None"
        )
```

`StronaWWWUstawionaQueryObject`:
```python
    def to_djangoql(self, value, operation):
        if value:
            return '(www != "" or public_www != "")'
        return '(www = "" and public_www = "")'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_fields_bool.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/boolean_fields.py src/bpp/tests/test_multiseek_djangoql_fields_bool.py
git commit -m "feat(multiseek): booleany isnull/inwersja/WWW -> DjangoQL"
```

---

### Task 12: Rodzaj konferencji/jednostki, Słowa kluczowe, Zewn. baza (B3)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/publication_type_fields.py` (RodzajKonferencji), `unit_fields.py` (RodzajJednostki), `author_fields.py` (SlowaKluczowe), `openaccess_fields.py` (ZewnetrznaBazaDanych)
- Test: `src/bpp/tests/test_multiseek_djangoql_fields_misc.py` (nowy)

- [ ] **Step 1: Write the failing test**

Utwórz `src/bpp/tests/test_multiseek_djangoql_fields_misc.py`:

```python
import pytest
from model_bakery import baker
from multiseek.logic import EQUAL

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql

pytestmark = pytest.mark.serial


def test_rodzaj_konferencji_krajowa():
    field = registry.field_by_name["Rodzaj konferencji"]
    assert field.to_djangoql("krajowa", str(EQUAL)) == "konferencja.typ_konferencji = 1"


def test_rodzaj_jednostki_normalna():
    from bpp.models import Jednostka

    field = registry.field_by_name["Rodzaj jednostki"]
    val = Jednostka.RODZAJ_JEDNOSTKI.NORMALNA.label
    assert (
        field.to_djangoql(val, str(EQUAL))
        == 'autorzy.jednostka.rodzaj_jednostki = "normalna"'
    )


@pytest.mark.django_db
def test_slowa_kluczowe_maps_to_tag_name():
    field = registry.field_by_name["Słowa kluczowe"]
    assert field.to_djangoql("nowotwór", str(EQUAL)) == 'slowa_kluczowe.name = "nowotwór"'


@pytest.mark.django_db
def test_zewnetrzna_baza_maps_to_nested_rel():
    from bpp.models import Zewnetrzna_Baza_Danych

    z = baker.make(Zewnetrzna_Baza_Danych, nazwa="Scopus")
    frag = leaf_to_djangoql(
        registry,
        {"field": "Zewnętrzna baza danych", "operator": str(EQUAL), "value": z.pk},
    )
    assert frag == f'zewnetrzne_bazy.baza__rel = "Scopus [{z.pk}]"'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_fields_misc.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

W `publication_type_fields.py`, `RodzajKonferenckjiQueryObject`:
```python
    _DJANGOQL_TK = {"krajowa": 1, "międzynarodowa": 2, "lokalna": 3}

    def to_djangoql(self, value, operation):
        tk = self._DJANGOQL_TK.get(value)
        if tk is None:
            return None
        op = "!=" if str(operation) in {str(o) for o in DIFFERENT_ALL} else "="
        return f"konferencja.typ_konferencji {op} {tk}"
```

W `unit_fields.py`, `RodzajJednostkiQueryObject`: dodaj
```python
    djangoql_field_name = "autorzy__jednostka__rodzaj_jednostki"
    djangoql_value_field = "rodzaj_jednostki"
```
Uwaga: `value_from_web` zwraca string-label (np. „normalna"), a `rodzaj_jednostki` na modelu przechowuje tę samą wartość małymi literami z `.value`. Sprawdź roundtrip w Step 4; jeśli label≠value, użyj zamiast atrybutów metody:
```python
    def to_djangoql(self, value, operation):
        from bpp.models import Jednostka

        mapa = {
            Jednostka.RODZAJ_JEDNOSTKI.NORMALNA.label: Jednostka.RODZAJ_JEDNOSTKI.NORMALNA.value,
            Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE.label: Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE.value,
        }
        kod = mapa.get(value)
        if kod is None:
            return None
        return f'autorzy.jednostka.rodzaj_jednostki = "{kod}"'
```
(Preferuj metodę — pewniejsza co do mapowania label→value.)

W `author_fields.py`, `SlowaKluczoweQueryObject`:
```python
    def to_djangoql(self, value, operation):
        op = "!=" if str(operation) in {str(o) for o in DIFFERENT_ALL} else "="
        label = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'slowa_kluczowe.name {op} "{label}"'
```

W `openaccess_fields.py`, `ZewnetrznaBazaDanychQueryObject`: dodaj atrybut
```python
    djangoql_field_name = "zewnetrzne_bazy__baza"
```
(Pole jest `type = AUTOCOMPLETE`, wartość to pk → dispatcher zrobi `zewnetrzne_bazy.baza__rel`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_fields_misc.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/publication_type_fields.py src/bpp/multiseek_registry/fields/unit_fields.py src/bpp/multiseek_registry/fields/author_fields.py src/bpp/multiseek_registry/fields/openaccess_fields.py src/bpp/tests/test_multiseek_djangoql_fields_misc.py
git commit -m "feat(multiseek): Rodzaj konf./jedn., Słowa kluczowe, Zewn. baza -> DjangoQL"
```

---

### Task 13: Pola kolejnościowe (dokładne) + UNION jednostki (best-effort+warning) (F)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/author_fields.py`, `unit_fields.py`
- Test: `src/bpp/tests/test_multiseek_kolejnosc_to_djangoql.py` (nowy); update `test_multiseek_jednostka_to_djangoql.py`

Semantyka: koniunkcja `autorzy.X and autorzy.kolejnosc …` jest same-row → dokładna. `Ostatnie nazwisko` (F-expression) → best-effort+warning. UNION jednostki → best-effort+warning (zmiana istniejących testów „untranslatable").

- [ ] **Step 1: Write the failing test**

Utwórz `src/bpp/tests/test_multiseek_kolejnosc_to_djangoql.py`:

```python
import pytest
from model_bakery import baker
from multiseek.logic import EQUAL

from bpp.models import Autor
from bpp.multiseek_registry import registry

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_pierwsze_nazwisko_is_kolejnosc_zero():
    a = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    field = registry.field_by_name["Pierwsze nazwisko i imię"]
    frag = field.to_djangoql(a.pk, str(EQUAL))
    assert frag == (
        f'autorzy.autor__rel = "{a} [{a.pk}]" '
        "and autorzy.kolejnosc >= 0 and autorzy.kolejnosc < 1"
    )


@pytest.mark.django_db
def test_ostatnie_nazwisko_best_effort_warns():
    a = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    field = registry.field_by_name["Ostatnie nazwisko i imię"]
    result = field.to_djangoql(a.pk, str(EQUAL))
    assert isinstance(result, tuple)
    frag, warn = result
    assert frag == f'autorzy.autor__rel = "{a} [{a.pk}]"'
    assert "ostatni" in warn.lower() or "kolejn" in warn.lower()
```

Zmień w `test_multiseek_jednostka_to_djangoql.py` testy UNION (dotychczas `is None`):
```python
@pytest.mark.django_db
def test_jednostka_union_best_effort_warns():
    j = baker.make(Jednostka, nazwa="Klinika X")
    field = registry.field_by_name["Jednostka"]
    result = field.to_djangoql(j.pk, str(UNION_FEMALE))
    assert isinstance(result, tuple)
    frag, warn = result
    assert frag == f'autorzy.jednostka__rel = "Klinika X [{j.pk}]"'
    assert "wspóln" in warn.lower()
```
(Usuń `test_jednostka_union_is_untranslatable` i `test_jednostka_plus_subunits_union_is_untranslatable`; zastąp wariantem warning powyżej + analogiczny dla `EQUAL_PLUS_SUB_UNION_FEMALE` → `jednostka_z_podjednostkami__rel` + warning.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_multiseek_kolejnosc_to_djangoql.py -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

W `author_fields.py`:

Refaktor: w `NazwiskoIImieQueryObject` wydziel budowę bazowego fragmentu, by podklasy mogły go reużyć. Dodaj metodę:
```python
    def _autor_rel(self, value):
        """'autorzy.autor__rel = \"label [pk]\"' albo None."""
        try:
            obj = self.value_from_web(value)
        except Exception:  # noqa: BLE001 — uszkodzony pk -> nieprzekładalne
            return None
        if obj is None:
            return None
        label = str(obj).replace("\\", "\\\\").replace('"', '\\"')
        return f'autorzy.autor__rel = "{label} [{obj.pk}]"'
```
i w istniejącym `NazwiskoIImieQueryObject.to_djangoql` użyj go dla równości (zachowując `!=` dla różności).

`NazwiskoIImieWZakresieKolejnosci` — dodaj `to_djangoql` (dokładne, same-row):
```python
    def to_djangoql(self, value, operation):
        op = str(operation)
        equal = {str(o) for o in EQUALITY_OPS_ALL} - {str(o) for o in DIFFERENT_ALL}
        if op not in equal and not _is_union_value(op):
            return None
        base = self._autor_rel(value)
        if base is None:
            return None
        # kolejnosc__gte/__lt mogą być F() (Ostatnie) — wtedy best-effort.
        gte, lt = self.kolejnosc_gte, self.kolejnosc_lt
        if not isinstance(gte, int) or not isinstance(lt, int):
            return base, (
                "Filtr „ostatni/zakres kolejności" pominięto — zależy od liczby "
                "autorów (F-expression), nie do wyrażenia w DjangoQL."
            )
        frag = f"{base} and autorzy.kolejnosc >= {gte} and autorzy.kolejnosc < {lt}"
        if _is_union_value(op):
            return frag, "Operator „wspólny" przełożono jak równość."
        return frag
```

W `unit_fields.py`, `JednostkaQueryObject.to_djangoql` — rozszerz o UNION (best-effort+warning) zamiast `return None`:
```python
        if op == str(UNION_FEMALE):
            return (
                f"autorzy.jednostka__rel = {suffix}",
                "Operator „wspólna" przełożono jak równość — może objąć innego autora.",
            )
        if op == str(EQUAL_PLUS_SUB_UNION_FEMALE):
            return (
                f"jednostka_z_podjednostkami__rel = {suffix}",
                "Operator „wspólna" przełożono jak równość — może objąć innego autora.",
            )
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_kolejnosc_to_djangoql.py src/bpp/tests/test_multiseek_jednostka_to_djangoql.py src/bpp/tests/test_multiseek_autor_to_djangoql.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/author_fields.py src/bpp/multiseek_registry/fields/unit_fields.py src/bpp/tests/test_multiseek_kolejnosc_to_djangoql.py src/bpp/tests/test_multiseek_jednostka_to_djangoql.py
git commit -m "feat(multiseek): pola kolejnościowe (dokładne) + UNION best-effort+warning"
```

---

### Task 14: Round-trip + test pokrycia rejestru (E)

**Files:**
- Test: `src/bpp/tests/test_multiseek_djangoql_coverage.py` (nowy), `test_multiseek_djangoql_roundtrip.py` (nowy)

- [ ] **Step 1: Write the round-trip tests**

Utwórz `src/bpp/tests/test_multiseek_djangoql_roundtrip.py` — porównaj zbiór pk dla pól dokładnych:

```python
import pytest
from djangoql.queryset import apply_search
from multiseek.logic import EQUAL

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Rekord
from bpp.multiseek_registry import registry

pytestmark = pytest.mark.serial


def _pks_djangoql(frag):
    return set(
        apply_search(Rekord.objects.all(), frag, schema=BppQLSchema)
        .distinct()
        .values_list("pk", flat=True)
    )


@pytest.mark.django_db
def test_roundtrip_jezyk(wydawnictwo_ciagle, denorms):
    from bpp.models import Jezyk

    pol = Jezyk.objects.get_or_create(nazwa="polski", skrot="pol.")[0]
    wydawnictwo_ciagle.jezyk = pol
    wydawnictwo_ciagle.save()
    denorms.flush()
    field = registry.field_by_name["Język"]
    q = field.real_query("polski", EQUAL)
    via_ms = set(Rekord.objects.filter(q).values_list("pk", flat=True))
    via_dql = _pks_djangoql('jezyk.nazwa = "polski"')
    assert via_ms
    assert via_ms == via_dql
```

(Wzorzec round-trip jak w `test_multiseek_jednostka_to_djangoql.py::test_roundtrip_jednostka_plus_subunits_same_rekordy`.)

- [ ] **Step 2: Write the coverage invariant test**

Utwórz `src/bpp/tests/test_multiseek_djangoql_coverage.py`:

```python
import pytest

from bpp.multiseek_registry import registry

# Pola, których pojedynczy warunek może być nieprzekładalny tylko z powodu
# OPERACJI (nie pola) — dozwolone wyjątki inwariantu pokrycia.
_OPERATION_ONLY_GAPS = set()


def test_every_registry_field_has_translation_path():
    """Każde pole rejestru ma drogę przekładu: metodę to_djangoql LUB
    deklaratywne atrybuty (djangoql_value_field / autocomplete) LUB jest
    bezpośrednim polem skalarnym. Strażnik celu „nic nieprzekładalnego"."""
    from multiseek.logic import AUTOCOMPLETE

    missing = []
    for label, field in registry.field_by_name.items():
        has_method = callable(getattr(field, "to_djangoql", None))
        has_value_list = bool(getattr(field, "djangoql_value_field", None))
        is_autocomplete = getattr(field, "type", None) == AUTOCOMPLETE
        has_field_name = bool(getattr(field, "field_name", None))
        if not (has_method or has_value_list or is_autocomplete or has_field_name):
            missing.append(label)
    assert missing == [], f"Pola bez drogi przekładu: {missing}"
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_coverage.py src/bpp/tests/test_multiseek_djangoql_roundtrip.py -v`
Expected: PASS.

- [ ] **Step 4: Run the whole multiseek-djangoql suite**

Run: `uv run pytest src/bpp/tests/ -k "djangoql or multiseek" -v`
Expected: PASS (cała grupa).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/tests/test_multiseek_djangoql_coverage.py src/bpp/tests/test_multiseek_djangoql_roundtrip.py
git commit -m "test(multiseek-djangoql): round-trip + inwariant pokrycia rejestru"
```

---

## PHASE 4 — UI: formatowanie + podświetlanie (G)

### Task 15: Moduł `djangoql-pretty.js` (formatter + highlighter)

**Files:**
- Create: `src/bpp/static/bpp/js/djangoql-pretty.js`
- Test: weryfikacja w Task 17 (Playwright); tu — smoke przez ładowanie w przeglądarce.

- [ ] **Step 1: Implement the module**

Utwórz `src/bpp/static/bpp/js/djangoql-pretty.js`:

```javascript
/* Formatowanie + podświetlanie składni zapytania DjangoQL.
 *
 * Reużywa lexera DjangoQL (z zainicjowanej instancji: dql.lexer). Lexer JS
 * nie obsługuje newline'ów w regule whitespace, więc lexujemy zapytanie
 * JEDNOLINIOWE, a łamanie linii nakładamy na etapie renderu (po granicach
 * tokenów). HTML jest escapowany.
 */
(function () {
  "use strict";

  var TOKEN_CLASS = {
    AND: "dql-keyword", OR: "dql-keyword", NOT: "dql-keyword", IN: "dql-keyword",
    STARTSWITH: "dql-keyword", ENDSWITH: "dql-keyword",
    TRUE: "dql-bool", FALSE: "dql-bool", NONE: "dql-none",
    NAME: "dql-name", DOT: "dql-dot",
    STRING_VALUE: "dql-str", INT_VALUE: "dql-num", FLOAT_VALUE: "dql-num",
    PAREN_L: "dql-paren", PAREN_R: "dql-paren",
    EQUALS: "dql-op", NOT_EQUALS: "dql-op", GREATER: "dql-op",
    GREATER_EQUAL: "dql-op", LESS: "dql-op", LESS_EQUAL: "dql-op",
    CONTAINS: "dql-op", NOT_CONTAINS: "dql-op", COMMA: "dql-op",
  };

  function esc(s) {
    return String(s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function tokenText(tok) {
    if (tok.name === "STRING_VALUE") return '"' + tok.value + '"';
    return tok.value;
  }

  function span(cls, text) {
    return '<span class="' + cls + '">' + esc(text) + "</span>";
  }

  function nl(depth) {
    return "\n" + "  ".repeat(depth);
  }

  // Łączy tokeny w sformatowany, podświetlony HTML. Zwraca jeden string.
  // Zasady łamania: '(' otwiera wcięcie i nową linię; ')' zamyka;
  // 'and'/'or' zaczynają nową linię na bieżącym wcięciu.
  function render(tokens) {
    var parts = [];
    var depth = 0;
    var atLineStart = true;

    function emit(html, glue) {
      if (!glue && !atLineStart) {
        parts.push(" ");
      }
      parts.push(html);
      atLineStart = false;
    }

    for (var i = 0; i < tokens.length; i++) {
      var t = tokens[i];
      var prev = tokens[i - 1];
      var cls = TOKEN_CLASS[t.name] || "dql-name";

      if (t.name === "PAREN_L") {
        emit(span("dql-paren", "("), false);
        depth += 1;
        parts.push(nl(depth));
        atLineStart = true;
        continue;
      }
      if (t.name === "PAREN_R") {
        depth = depth > 0 ? depth - 1 : 0;
        parts.push(nl(depth));
        atLineStart = true;
        emit(span("dql-paren", ")"), true);
        continue;
      }
      if (t.name === "AND" || t.name === "OR") {
        parts.push(nl(depth));
        atLineStart = true;
        emit(span(cls, t.value), true);
        continue;
      }
      // Kropka klei się do sąsiadów (ścieżka pola), bez spacji.
      var glue = t.name === "DOT" || (prev && prev.name === "DOT");
      emit(span(cls, tokenText(t)), glue);
    }
    return parts.join("");
  }

  function formatAndHighlight(query, lexer) {
    if (!query) return "";
    var tokens;
    try {
      tokens = lexer.setInput(query).lexAll();
    } catch (e) {
      return span("dql-name", query);
    }
    return render(tokens);
  }

  window.djangoqlPretty = { formatAndHighlight: formatAndHighlight };
})();
```

Plik używa wyłącznie pojedynczych cudzysłowów dla HTML-owych atrybutów i podwójnych dla stringów JS — kopiuj verbatim.

- [ ] **Step 2: Lint/format the JS**

Run: `cd /Users/mpasternak/Programowanie/bpp && npx --no-install eslint src/bpp/static/bpp/js/djangoql-pretty.js || true`
Jeśli brak eslinta — pomiń; weryfikacja składni nastąpi przy ładowaniu strony w Task 17.

- [ ] **Step 3: Commit**

```bash
git add src/bpp/static/bpp/js/djangoql-pretty.js
git commit -m "feat(multiseek-ui): moduł djangoql-pretty (format + highlight przez lexer DjangoQL)"
```

---

### Task 16: Integracja szuflady (pre + CSS + skrypty)

**Files:**
- Modify: `src/django_bpp/templates/multiseek/index.html`
- Modify (CSS): inline `<style>` w szufladzie LUB `src/bpp/static/...scss` + `grunt build`
- Test: ręczny podgląd (Task 17 — Playwright)

- [ ] **Step 1: Add highlighting CSS**

W bloku stylów szuflady (lub istniejącym `<style>` strony) dodaj klasy:
```css
.djangoql-pretty {
    font-family: monospace; white-space: pre; overflow-x: auto;
    background: #f6f6f6; padding: .6rem; border-radius: 3px; line-height: 1.5;
}
.dql-keyword { color: #8959a8; font-weight: bold; }
.dql-op { color: #3e999f; }
.dql-name { color: #4271ae; }
.dql-dot { color: #999; }
.dql-str { color: #718c00; }
.dql-num { color: #f5871f; }
.dql-bool, .dql-none { color: #c82829; }
.dql-paren { color: #555; }
```

- [ ] **Step 2: Replace the readonly textarea display with a `<pre>` + hidden raw field**

W szufladzie (`id="djangoqlDrawer"`), zamień:
```html
<textarea id="djangoqlQuery" rows="4" readonly spellcheck="false" style="font-family:monospace;"></textarea>
```
na:
```html
<pre class="djangoql-pretty"><code id="djangoqlPretty"></code></pre>
{# Surowe zapytanie (jednoliniowe) do kopiowania i edytora #}
<input type="hidden" id="djangoqlQueryRaw" value="">
```

- [ ] **Step 3: Load scripts (tylko dla userów z gate'em — wewnątrz istniejącego bloku warunkowego przycisku)**

Tam, gdzie renderowany jest przycisk/szuflada (sekcja `can_use_query_editor`), po HTML szuflady dodaj:
```html
<script src="{% static 'djangoql/js/completion.js' %}"></script>
<script src="{% static 'bpp/js/djangoql-pretty.js' %}"></script>
<script>
(function () {
    var _lexerHolder = null;
    function getLexer() {
        if (_lexerHolder) return _lexerHolder.lexer;
        var ta = document.getElementById("djangoqlLexerProbe");
        if (!ta) {
            ta = document.createElement("textarea");
            ta.id = "djangoqlLexerProbe";
            ta.style.display = "none";
            document.body.appendChild(ta);
        }
        try {
            _lexerHolder = DjangoQL.init({
                introspections: "{% url 'bpp:zapytanie_introspect' 'rekord' %}",
                selector: ta,
                autoResize: false
            });
        } catch (e) { return null; }
        return _lexerHolder.lexer;
    }
    window.djangoqlRenderPretty = function (query) {
        var raw = document.getElementById("djangoqlQueryRaw");
        var pre = document.getElementById("djangoqlPretty");
        if (raw) raw.value = query || "";
        var lexer = getLexer();
        if (pre) {
            pre.innerHTML = (lexer && window.djangoqlPretty)
                ? window.djangoqlPretty.formatAndHighlight(query || "", lexer)
                : (query || "");
        }
    };
})();
</script>
```

- [ ] **Step 4: Hook rendering into the existing drawer-open flow**

W istniejącym JS szuflady (`openDjangoqlDrawer`, fetch `.then`), zamień:
```javascript
document.getElementById('djangoqlQuery').value = data.query || '';
```
na:
```javascript
if (window.djangoqlRenderPretty) { window.djangoqlRenderPretty(data.query || ''); }
```
W `copyDjangoqlQuery` zmień źródło kopiowania z `#djangoqlQuery` (textarea) na sformatowany tekst z `#djangoqlPretty` (`.textContent`), z fallbackiem na `#djangoqlQueryRaw`:
```javascript
var pre = document.getElementById('djangoqlPretty');
var raw = document.getElementById('djangoqlQueryRaw');
var text = (pre && pre.textContent) || (raw && raw.value) || '';
```
(Reszta logiki kopiowania bez zmian — operuj na `text`.)

- [ ] **Step 5: Verify template renders (smoke)**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_button.py -v`
Expected: PASS (asercje na obecność `id="toDjangoqlButton"` / `id="djangoqlDrawer"` nadal trzymają; w razie potrzeby zaktualizuj asercję dot. textarea → `id="djangoqlPretty"`).

- [ ] **Step 6: Commit**

```bash
git add src/django_bpp/templates/multiseek/index.html
git commit -m "feat(multiseek-ui): szuflada pokazuje sformatowane + podświetlone DjangoQL"
```

---

### Task 17: Playwright — podgląd szuflady

**Files:**
- Modify: `src/bpp/tests/test_multiseek_djangoql_button.py` (lub nowy Playwright test, jeśli plik nie jest browserowy)

- [ ] **Step 1: Write the Playwright test**

Dodaj test (wzorzec z `src/integration_tests/`), który:
- loguje użytkownika z grupy „wprowadzanie danych" / superusera,
- wchodzi na formularz multiseek z jednym kryterium (np. Tytuł pracy zawiera „x"),
- klika `#toDjangoqlButton`,
- czeka na `#djangoqlPretty span.dql-name`,
- asercje: `#djangoqlPretty` zawiera ≥1 `span.dql-*`; przy zapytaniu złożonym (dwa kryteria połączone OR) `textContent` zawiera newline (`\n`); `#djangoqlOpenEditor` ma `href` zaczynający się od URL edytora.

```python
def test_drawer_shows_highlighted_formatted_query(page, live_server, ...):
    # ... login + dodanie dwóch kryteriów + OR ...
    page.click("#toDjangoqlButton")
    page.wait_for_selector("#djangoqlPretty span.dql-name")
    spans = page.locator("#djangoqlPretty span.dql-op")
    assert spans.count() >= 1
    text = page.locator("#djangoqlPretty").inner_text()
    assert "\n" in text  # sformatowane wieloliniowo
```

(Dostosuj fixtures do istniejącego harnessu Playwright — patrz `src/integration_tests/test_global_search.py`.)

- [ ] **Step 2: Build assets and run**

Run:
```bash
make assets
uv run pytest src/bpp/tests/test_multiseek_djangoql_button.py -k highlighted -v
```
Expected: PASS (pierwszy cold-start może wymagać ponowienia).

- [ ] **Step 3: Commit**

```bash
git add src/bpp/tests/test_multiseek_djangoql_button.py
git commit -m "test(multiseek-ui): Playwright — podgląd szuflady (format + highlight)"
```

---

## Finał

- [ ] **Pełna grupa testów**

Run: `uv run pytest src/bpp/tests/ -k "djangoql or multiseek or charakter" -v`
Expected: PASS.

- [ ] **Pre-commit (bez argumentów; poprawki ręcznie, bez `ruff --fix`)**

Run: `pre-commit`
Napraw zgłoszone problemy ręcznie (Edit), commituj.

- [ ] **Aktualizacja PR #328** — push i sprawdzenie realnych gejtów (`Build test-runner image`, `Tests (sharded)`); nie cieszyć się zielenią <1 min (skip).

---

## Self-Review (zrealizowane przy pisaniu planu)

- **Pokrycie specu:** A1→T1, kontrakt warning (nowość konieczna pod F)→T2, A2→T3, A3→T4, A4→T5, B1→T6, B2→T7, B3(bool)→T8/T11, B3(charakter)→T9, B3(typ ogólny)→T10, B3(misc)→T12, F→T13, E(audyt/round-trip)→T14, G→T15-17.
- **Spójność nazw:** `_orm_name`, `_value_list_leaf`, `djangoql_field_name`, `djangoql_value_field`, `charakter_z_podrzednymi__rel`, `_CHARAKTER_SUB_FIELD`, `CharakterZPodrzednymiField`, `formatAndHighlight`, `window.djangoqlPretty` — użyte spójnie.
- **Znane ryzyka do weryfikacji w trakcie:** (a) `RodzajJednostkiQueryObject` label↔value (Task 12 ma fallback-metodę); (b) `is_valid_rekord_djangoql` jako siatka — jeśli któraś ścieżka nie waliduje, fragment cicho znika → round-trip/coverage to wychwycą; (c) JS w Task 15 — pilnować cudzysłowów/escapów.
