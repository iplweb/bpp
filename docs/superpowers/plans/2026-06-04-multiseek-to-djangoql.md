# Konwerter „formularz Multiseek → zapytanie DjangoQL” — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Na stronie formularza Multiseek dodać przycisk, który dla uprawnionego użytkownika tłumaczy zbudowany formularz na równoważne zapytanie DjangoQL nad `Rekord` i pokazuje je w szufladzie (kopiuj + „Otwórz w edytorze zapytań”).

**Architecture:** Konwersja server-side. Czysta funkcja `multiseek_form_to_djangoql(form_json, registry)` chodzi po ramkach `form_data` (jak `get_query_recursive`), renderując liście jako fragmenty DjangoQL. Domyślny dispatcher tłumaczy typowe pola; trudne pola (Jednostka) nadpisują `to_djangoql`. Każdy fragment jest walidowany przeciw `BppQLSchema(Rekord)` — niepoprawne lądują jako warning, więc wynik zawsze się parsuje. Semantykę „+ podrzędne” odwzorowuje nowe wirtualne pole DjangoQL `jednostka_z_podjednostkami__rel` (MPTT `get_family()`), użyteczne też w samym edytorze. Endpoint `POST /multiseek/do-djangoql/` (gated) i przycisk + drawer w `index.html`.

**Tech Stack:** Django, multiseek, djangoql, pytest, model_bakery, Foundation CSS, jQuery.

---

## Ustalenia z kodu (fakty, nie zgadywanie)

- Registry: `bpp.multiseek_registry.registry` (obiekt `MultiseekRegistry`). Mapa label→QueryObject: `registry.field_by_name` (dict). Pola: `registry.fields` (lista).
- `QueryObject`: `real_query(value, operation) -> Q`; `value_from_web(value)`; dla autocomplete `value_from_web` zwraca `self.model.objects.get(pk=...)` (instancję). `field_name` = ścieżka ORM (np. `rok`, `doi`, `autorzy__autor__orcid`), `type` (np. `AUTOCOMPLETE`), `label`.
- Operatory multiseek to **leniwe** `_()` proxy w `multiseek.logic` (np. `EQUAL = _("equals")`). W `form_data` `operator` to string z aktywnej lokalizacji. Dlatego mapę operatorów budujemy z importowanych stałych i porównujemy przez `str(...)`.
- Stałe: `AND="and"`, `OR="or"`, `ANDNOT="andnot"`. `EQUALITY_OPS_ALL`, `DIFFERENT_ALL`, `GREATER_OPS_ALL`, `LESSER_OPS_ALL`, `GREATER_OR_EQUAL_OPS_ALL`, `LESSER_OR_EQUAL_OPS_ALL`, `CONTAINS`, `NOT_CONTAINS`, `STARTS_WITH`, `NOT_STARTS_WITH`, `IN_RANGE`, `NOT_IN_RANGE`, `AUTOCOMPLETE`.
- `form_data` (z `formAsJSON()`): `[null_or_op, leaf_or_frame, ...]`. Liść: `{"field": label, "operator": op, "value": v, "prev_op": "and"|"or"|"andnot"|null}`. Ramka zagnieżdżona: lista `[op, leaf/frame, ...]`. `formAsJSON()` zwraca `JSON.stringify({form_data, ordering, report_type})`. Istniejący submit POST-uje to jako pole `json`.
- Edytor: `/zapytanie/`, param `?model=rekord&query=...`. Schemat `BppQLSchema` (alias `BppZapytanieSchema`) w `src/bpp/djangoql_schema.py`. Gate: `WprowadzanieDanychOrSuperuserMixin.test_func` (`zapytanie.py:275`): `user.is_superuser or (user.is_staff and groups.filter(name=GR_WPROWADZANIE_DANYCH))`. `GR_WPROWADZANIE_DANYCH="wprowadzanie danych"` (`bpp.const`).
- `__rel` pickery: `AutocompleteField` (`djangoql/extras.py`), wartość `"Label [pk]"`, `get_lookup` parsuje pk i filtruje przez `lookup_name`. `JednostkaQueryObject` (`unit_fields.py:48`) filtruje `autorzy__jednostka`; „+podrzędne” = `Q(autorzy__jednostka__in=value.get_family())`. `Jednostka` to `MPTTModel`.
- Strona formularza renderowana przez pakietowy `multiseek.views.MultiseekFormPage` (TemplateView) → button-visibility robimy filtrem szablonowym, nie nadpisując widoku.

---

## Struktura plików

- **Create** `src/bpp/multiseek_registry/djangoql_export.py` — silnik konwersji + dispatcher + walidacja fragmentów.
- **Modify** `src/bpp/multiseek_registry/fields/unit_fields.py` — `to_djangoql` na `JednostkaQueryObject`.
- **Modify** `src/bpp/djangoql_schema.py` — wirtualne pole `jednostka_z_podjednostkami__rel` na `Rekord`.
- **Modify** `src/bpp/views/zapytanie.py` — wyłuskanie predykatu `user_can_use_query_editor(user)`.
- **Modify** `src/bpp/views/mymultiseek.py` — widok endpointu `MultiseekToDjangoQLView`.
- **Modify** `src/django_bpp/urls.py` — URL `multiseek/do-djangoql/`.
- **Create** `src/bpp/templatetags/query_editor.py` — filtr `can_use_query_editor`.
- **Modify** `src/django_bpp/templates/multiseek/index.html` — przycisk + drawer + JS.
- **Create** testy: `src/bpp/tests/test_multiseek_djangoql_export.py`, `src/bpp/tests/test_jednostka_podjednostki_field.py`, `src/bpp/tests/test_multiseek_djangoql_endpoint.py`.

---

## Task 1: Predykat uprawnień do edytora zapytań (refaktor, single source of truth)

**Files:**
- Modify: `src/bpp/views/zapytanie.py` (klasa `WprowadzanieDanychOrSuperuserMixin`, ~`:275`)
- Test: `src/bpp/tests/test_zapytanie.py` (dopisanie testu)

- [ ] **Step 1: Test funkcji predykatu (failing)**

Dopisz w `src/bpp/tests/test_zapytanie.py`:

```python
import pytest
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.views.zapytanie import user_can_use_query_editor


@pytest.mark.django_db
def test_user_can_use_query_editor_superuser():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=False)
    assert user_can_use_query_editor(u) is True


@pytest.mark.django_db
def test_user_can_use_query_editor_staff_in_group():
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=True)
    grp = baker.make("auth.Group", name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grp)
    assert user_can_use_query_editor(u) is True


@pytest.mark.django_db
def test_user_can_use_query_editor_plain_logged_in():
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=False)
    assert user_can_use_query_editor(u) is False
```

> Uwaga: model usera to `bpp.BppUser` (potwierdź `AUTH_USER_MODEL`; jeśli inny, użyj go w `baker.make`).

- [ ] **Step 2: Run — fail (ImportError)**

Run: `uv run pytest src/bpp/tests/test_zapytanie.py -k user_can_use_query_editor -q`
Expected: FAIL — `ImportError: cannot import name 'user_can_use_query_editor'`.

- [ ] **Step 3: Wyłuskaj predykat i przepnij mixin**

W `src/bpp/views/zapytanie.py`, tuż przed `class WprowadzanieDanychOrSuperuserMixin`:

```python
def user_can_use_query_editor(user):
    """Czy user widzi/uzywa edytora zapytan DjangoQL.

    Superuser, albo staff w grupie 'wprowadzanie danych'. Jedno zrodlo
    prawdy dla: mixinu widoku, endpointu konwertera i filtru szablonowego.
    """
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.is_staff and user.groups.filter(
        name=GR_WPROWADZANIE_DANYCH
    ).exists()
```

I zmień `test_func`:

```python
    def test_func(self):
        return user_can_use_query_editor(self.request.user)
```

- [ ] **Step 4: Run — pass**

Run: `uv run pytest src/bpp/tests/test_zapytanie.py -k user_can_use_query_editor -q`
Expected: PASS (3).

- [ ] **Step 5: Regresja istniejących testów edytora**

Run: `uv run pytest src/bpp/tests/test_zapytanie.py -q`
Expected: PASS (bez nowych failów).

- [ ] **Step 6: Commit**

```bash
git add src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
git commit -m "refactor(zapytanie): wyodrebnij user_can_use_query_editor predicate"
```

---

## Task 2: Wirtualne pole DjangoQL `jednostka_z_podjednostkami__rel`

**Files:**
- Modify: `src/bpp/djangoql_schema.py`
- Test: `src/bpp/tests/test_jednostka_podjednostki_field.py` (create)

- [ ] **Step 1: Test pola (failing)**

Create `src/bpp/tests/test_jednostka_podjednostki_field.py`:

```python
import pytest
from djangoql.queryset import apply_search
from model_bakery import baker

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Jednostka, Rekord


@pytest.mark.django_db
def test_jednostka_z_podjednostkami_matches_family(denorma):
    parent = baker.make(Jednostka, nazwa="Parent")
    child = baker.make(Jednostka, nazwa="Child", parent=parent)
    # Rekord publikacji z autorem w child-unit -> ma trafic przy pytaniu o parent
    wc = baker.make(
        "bpp.Wydawnictwo_Ciagle", tytul_oryginalny="Pub w child"
    )
    autor = baker.make("bpp.Autor")
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=wc, autor=autor, jednostka=child)

    query = f'jednostka_z_podjednostkami__rel = "Parent [{parent.pk}]"'
    qs = apply_search(Rekord.objects.all(), query, schema=BppQLSchema).distinct()
    titles = set(qs.values_list("tytul_oryginalny", flat=True))
    assert "Pub w child" in titles


@pytest.mark.django_db
def test_jednostka_z_podjednostkami_in_schema():
    schema = BppQLSchema(Rekord)
    fields = schema.models[BppQLSchema.model_label(Rekord)]
    assert "jednostka_z_podjednostkami__rel" in fields
```

> `denorma` to istniejący fixture odświeżający cache `Rekord` (sprawdź w `src/conftest.py`; jeśli nazwa inna — np. `denorms` — użyj właściwej). Jeśli `Wydawnictwo_Ciagle_Autor` ma inne pole na jednostkę/rekord, dostosuj `baker.make`.

- [ ] **Step 2: Run — fail (Unknown field)**

Run: `uv run pytest src/bpp/tests/test_jednostka_podjednostki_field.py -q`
Expected: FAIL — `DjangoQLSchemaError: Unknown field: jednostka_z_podjednostkami__rel`.

- [ ] **Step 3: Dodaj wirtualne pole**

W `src/bpp/djangoql_schema.py`:

```python
from django.db.models import Q
from djangoql.extras import AutocompleteField, ExtrasSchema

from bpp.models import Jednostka

_SUBUNITS_FIELD = "jednostka_z_podjednostkami__rel"


class JednostkaZPodjednostkamiField(AutocompleteField):
    """Picker po Jednostce, ktory dopasowuje rekordy autorow z tej jednostki
    ORAZ wszystkich jednostek z jej rodziny MPTT (przodkowie+sam+potomkowie).

    Odwzorowuje multiseek EQUAL_PLUS_SUB_FEMALE:
        Q(autorzy__jednostka__in=value.get_family())
    """

    def get_lookup(self, path, operator, value):
        parsed = self.parse_id(value)
        if not isinstance(parsed, int):
            # free-text fallback po nazwie jednostki (best-effort)
            return Q(autorzy__jednostka__nazwa__icontains=str(value))
        try:
            jednostka = Jednostka.objects.get(pk=parsed)
        except Jednostka.DoesNotExist:
            return Q(pk__in=[])  # nic nie pasuje
        q = Q(autorzy__jednostka__in=jednostka.get_family())
        return ~q if operator in ("!=", "not in") else q
```

I wepnij pole do schematu **tylko dla modelu z relacją `autorzy`** (Rekord). W `RelPickerSchemaMixin`:

```python
    def get_fields(self, model):
        fields = list(super().get_fields(model))
        fields += [f.name + _REL_SUFFIX for f in _picker_fks(model)]
        if _has_autorzy_jednostka(model):
            fields.append(_SUBUNITS_FIELD)
        return fields

    def get_field_instance(self, model, field_name):
        if field_name == _SUBUNITS_FIELD:
            return JednostkaZPodjednostkamiField(
                model=model,
                name=_SUBUNITS_FIELD,
                nullable=True,
                queryset=_visible_qs(Jednostka),
                search_fields=_label_fields(Jednostka),
            )
        # ... istniejaca logika __rel ...
```

oraz helper na poziomie modułu:

```python
def _has_autorzy_jednostka(model):
    """True, gdy model ma odwrotna relacje 'autorzy' z FK 'jednostka'
    (czyli Rekord / cache)."""
    try:
        rel = model._meta.get_field("autorzy")
    except FieldDoesNotExist:
        return False
    related = getattr(rel, "related_model", None)
    if related is None:
        return False
    return "jednostka" in {
        f.name for f in related._meta.get_fields() if isinstance(f, models.Field)
    }
```

> Zachowaj istniejące `get_field_instance` dla `__rel` — dodaj tylko gałąź `if field_name == _SUBUNITS_FIELD` na początku.

- [ ] **Step 4: Run — pass**

Run: `uv run pytest src/bpp/tests/test_jednostka_podjednostki_field.py -q`
Expected: PASS (2).

- [ ] **Step 5: Regresja schematu/edytora**

Run: `uv run pytest src/bpp/tests/test_zapytanie.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bpp/djangoql_schema.py src/bpp/tests/test_jednostka_podjednostki_field.py
git commit -m "feat(djangoql): pole jednostka_z_podjednostkami__rel (MPTT get_family)"
```

---

## Task 3: Silnik — renderowanie wartości i mapa operatorów (skalary)

**Files:**
- Create: `src/bpp/multiseek_registry/djangoql_export.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_export.py` (create)

- [ ] **Step 1: Test render + scalar op (failing)**

Create `src/bpp/tests/test_multiseek_djangoql_export.py`:

```python
import pytest
from multiseek.logic import (
    CONTAINS,
    DIFFERENT,
    EQUAL,
    GREATER_OR_EQUAL,
    NOT_STARTS_WITH,
)

from bpp.multiseek_registry.djangoql_export import (
    render_value,
    scalar_operator_to_djangoql,
)


def test_render_value_str_quotes_and_escapes():
    assert render_value('on rzekł "tak"') == r'"on rzekł \"tak\""'


def test_render_value_int():
    assert render_value(2024) == "2024"


def test_scalar_operator_mapping():
    assert scalar_operator_to_djangoql(str(EQUAL)) == "="
    assert scalar_operator_to_djangoql(str(DIFFERENT)) == "!="
    assert scalar_operator_to_djangoql(str(CONTAINS)) == "~"
    assert scalar_operator_to_djangoql(str(GREATER_OR_EQUAL)) == ">="
    assert scalar_operator_to_djangoql(str(NOT_STARTS_WITH)) == "not startswith"


def test_scalar_operator_unknown_returns_none():
    assert scalar_operator_to_djangoql("zupełnie nieznany") is None
```

- [ ] **Step 2: Run — fail (ImportError)**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -q`
Expected: FAIL — `ImportError`.

- [ ] **Step 3: Implementacja render + mapy**

Create `src/bpp/multiseek_registry/djangoql_export.py`:

```python
"""Konwersja formularza Multiseek -> zapytanie DjangoQL nad Rekord.

Czysta funkcja `multiseek_form_to_djangoql(form_json, registry)` chodzi po
ramkach `form_data` (jak multiseek.logic.get_query_recursive) i renderuje
liscie jako fragmenty DjangoQL. Domyslny dispatcher tlumaczy typowe pola;
pola trudne nadpisuja metode `to_djangoql(value, operation)`. Kazdy fragment
jest walidowany przeciw BppQLSchema(Rekord) — niepoprawne -> warning.
"""

from decimal import Decimal

from multiseek.logic import (
    CONTAINS,
    DIFFERENT_ALL,
    EQUALITY_OPS_ALL,
    GREATER_OPS_ALL,
    GREATER_OR_EQUAL_OPS_ALL,
    IN_RANGE,
    LESSER_OPS_ALL,
    LESSER_OR_EQUAL_OPS_ALL,
    NOT_CONTAINS,
    NOT_IN_RANGE,
    NOT_STARTS_WITH,
    STARTS_WITH,
)


def _build_scalar_op_map():
    m = {}
    equals = [o for o in EQUALITY_OPS_ALL if o not in DIFFERENT_ALL]
    for o in equals:
        m[str(o)] = "="
    for o in DIFFERENT_ALL:
        m[str(o)] = "!="
    for o in GREATER_OPS_ALL:
        m[str(o)] = ">"
    for o in GREATER_OR_EQUAL_OPS_ALL:
        m[str(o)] = ">="
    for o in LESSER_OPS_ALL:
        m[str(o)] = "<"
    for o in LESSER_OR_EQUAL_OPS_ALL:
        m[str(o)] = "<="
    m[str(CONTAINS)] = "~"
    m[str(NOT_CONTAINS)] = "!~"
    m[str(STARTS_WITH)] = "startswith"
    m[str(NOT_STARTS_WITH)] = "not startswith"
    return m


_SCALAR_OP_MAP = _build_scalar_op_map()
_RANGE_OPS = {str(IN_RANGE), str(NOT_IN_RANGE)}


def scalar_operator_to_djangoql(operator):
    """DjangoQL-owy operator dla skalarnej operacji multiseek, lub None."""
    return _SCALAR_OP_MAP.get(str(operator))


def render_value(value):
    """Literal DjangoQL dla wartosci skalarnej."""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (int, Decimal, float)):
        return str(value)
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'
```

- [ ] **Step 4: Run — pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -q`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/djangoql_export.py src/bpp/tests/test_multiseek_djangoql_export.py
git commit -m "feat(djangoql-export): render_value + mapa operatorow skalarnych"
```

---

## Task 4: Silnik — translacja pojedynczego liścia (dispatcher + walidacja)

**Files:**
- Modify: `src/bpp/multiseek_registry/djangoql_export.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_export.py`

- [ ] **Step 1: Testy liścia (failing)**

Dopisz do `test_multiseek_djangoql_export.py`:

```python
import pytest

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql


@pytest.mark.django_db
def test_leaf_scalar_string_contains():
    frag = leaf_to_djangoql(
        registry, {"field": "Tytuł pracy", "operator": "contains", "value": "nowotwor"}
    )
    assert frag == 'tytul_oryginalny ~ "nowotwor"'


@pytest.mark.django_db
def test_leaf_year_gte():
    frag = leaf_to_djangoql(
        registry, {"field": "Rok", "operator": "greater or equal to", "value": 2020}
    )
    assert frag == "rok >= 2020"


@pytest.mark.django_db
def test_leaf_unknown_field_returns_none():
    frag = leaf_to_djangoql(
        registry, {"field": "Nie ma takiego pola", "operator": "equals", "value": "x"}
    )
    assert frag is None
```

> Operatory w testach wpisz w języku, w jakim działa testowa lokalizacja (domyślnie `pl`). Jeśli testy działają po polsku, użyj polskich etykiet operatorów (np. `"zawiera"`, `"większy lub równy"`) — sprawdź `str(CONTAINS)` w `uv run python -c "..."`. Najbezpieczniej: w teście buduj operator przez `str(CONTAINS)` zamiast literału.

Zalecana wersja odporna na lokalizację:

```python
@pytest.mark.django_db
def test_leaf_scalar_string_contains():
    from multiseek.logic import CONTAINS
    frag = leaf_to_djangoql(
        registry,
        {"field": "Tytuł pracy", "operator": str(CONTAINS), "value": "nowotwor"},
    )
    assert frag == 'tytul_oryginalny ~ "nowotwor"'
```

- [ ] **Step 2: Run — fail**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -k leaf -q`
Expected: FAIL — `ImportError: leaf_to_djangoql`.

- [ ] **Step 3: Implementacja dispatchera + walidacji**

Dopisz do `djangoql_export.py`:

```python
from multiseek.logic import AUTOCOMPLETE

from djangoql.exceptions import DjangoQLError
from djangoql.parser import DjangoQLParser

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Rekord

_parser = DjangoQLParser()


def _orm_path_to_djangoql(field_name):
    """field_name multiseek (ORM, '__') -> sciezka DjangoQL ('.')."""
    return field_name.replace("__", ".")


def is_valid_rekord_djangoql(fragment):
    """Czy fragment parsuje sie i waliduje wzgledem BppQLSchema(Rekord)."""
    try:
        ast = _parser.parse(fragment)
        BppQLSchema(Rekord).validate(ast)
        return True
    except (DjangoQLError, Exception):  # noqa: BLE001 — best-effort gate
        return False


def _default_leaf(field, value, operation):
    op = str(operation)
    if getattr(field, "type", None) == AUTOCOMPLETE:
        return _autocomplete_leaf(field, value, operation)
    name = getattr(field, "field_name", None)
    if not name:
        return None
    if op in _RANGE_OPS:
        return _range_leaf(name, value, operation)
    dql_op = scalar_operator_to_djangoql(op)
    if dql_op is None:
        return None
    return f"{_orm_path_to_djangoql(name)} {dql_op} {render_value(value)}"


def _autocomplete_leaf(field, value, operation):
    """value to pk; resolwujemy obiekt i emitujemy '<sciezka>__rel = \"L [pk]\"'."""
    op = str(operation)
    if op in {str(o) for o in DIFFERENT_ALL}:
        rel_op = "!="
    elif op in {str(o) for o in EQUALITY_OPS_ALL}:
        rel_op = "="
    else:
        return None
    try:
        obj = field.value_from_web(value)
    except Exception:  # noqa: BLE001 — nieistniejacy/uszkodzony pk -> warning
        return None
    if obj is None:
        return None
    rel_path = _orm_path_to_djangoql(field.field_name) + "__rel"
    label = str(obj).replace("\\", "\\\\").replace('"', '\\"')
    return f'{rel_path} {rel_op} "{label} [{obj.pk}]"'


def _range_leaf(name, value, operation):
    """IN_RANGE/NOT_IN_RANGE: value to [low, high]."""
    if not (isinstance(value, (list, tuple)) and len(value) == 2):
        return None
    low, high = value
    path = _orm_path_to_djangoql(name)
    inner = f"{path} >= {render_value(low)} and {path} <= {render_value(high)}"
    if str(operation) == str(NOT_IN_RANGE):
        return None  # brak unary not(...) w DjangoQL -> warning
    return f"({inner})"


def leaf_to_djangoql(registry, leaf):
    """Fragment DjangoQL dla pojedynczego warunku, albo None (nieprzekladalny).

    None gdy: nieznane pole, nieobslugiwana operacja, albo fragment nie
    waliduje sie wzgledem schematu Rekord.
    """
    field = registry.field_by_name.get(leaf["field"])
    if field is None:
        return None
    override = getattr(field, "to_djangoql", None)
    if callable(override):
        frag = override(leaf["value"], leaf["operator"])
    else:
        frag = _default_leaf(field, leaf["value"], leaf["operator"])
    if frag is None:
        return None
    return frag if is_valid_rekord_djangoql(frag) else None
```

> `is_valid_rekord_djangoql` celowo łapie szeroko (best-effort bramka poprawności) — to wyjątek od reguły „no bare except”: NIE tłumi błędu logiki, tylko klasyfikuje fragment jako nieprzekładalny. Zostaw komentarz `# best-effort gate`.

- [ ] **Step 4: Run — pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -k leaf -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/djangoql_export.py src/bpp/tests/test_multiseek_djangoql_export.py
git commit -m "feat(djangoql-export): dispatcher liscia + walidacja fragmentu wzgledem schematu"
```

---

## Task 5: Silnik — chodzenie po ramkach (`form_data`) + warningi

**Files:**
- Modify: `src/bpp/multiseek_registry/djangoql_export.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_export.py`

- [ ] **Step 1: Testy ramek (failing)**

Dopisz:

```python
import pytest
from multiseek.logic import AND, CONTAINS, EQUAL, OR

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import multiseek_form_to_djangoql


@pytest.mark.django_db
def test_two_conditions_and():
    form = {
        "form_data": [
            None,
            {"field": "Tytuł pracy", "operator": str(CONTAINS), "value": "covid", "prev_op": None},
            {"field": "Rok", "operator": str(EQUAL), "value": 2023, "prev_op": str(AND)},
        ],
        "ordering": {},
        "report_type": "0",
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == 'tytul_oryginalny ~ "covid" and rok = 2023'
    assert res.warnings == []


@pytest.mark.django_db
def test_untranslatable_condition_warns_and_skips():
    form = {
        "form_data": [
            None,
            {"field": "Rok", "operator": str(EQUAL), "value": 2023, "prev_op": None},
            {"field": "Nie ma pola", "operator": str(EQUAL), "value": "x", "prev_op": str(AND)},
        ],
        "ordering": {},
        "report_type": "0",
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == "rok = 2023"
    assert len(res.warnings) == 1
    assert "Nie ma pola" in res.warnings[0]


@pytest.mark.django_db
def test_empty_form():
    res = multiseek_form_to_djangoql({"form_data": [None], "ordering": {}}, registry)
    assert res.query == ""
    assert res.warnings == []
```

- [ ] **Step 2: Run — fail**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -k "two_conditions or untranslatable or empty_form" -q`
Expected: FAIL — `ImportError: multiseek_form_to_djangoql`.

- [ ] **Step 3: Implementacja walk + złączeń**

Dopisz do `djangoql_export.py`:

```python
from dataclasses import dataclass, field as dataclass_field
from urllib.parse import urlencode

from django.urls import reverse

from multiseek.logic import AND, ANDNOT, OR


@dataclass
class ConversionResult:
    query: str
    warnings: list = dataclass_field(default_factory=list)

    @property
    def editor_url(self):
        base = reverse("bpp:zapytanie")
        if not self.query:
            return f"{base}?{urlencode({'model': 'rekord'})}"
        return f"{base}?{urlencode({'model': 'rekord', 'query': self.query})}"


_JOIN = {str(AND): "and", str(OR): "or"}


def _leaf_label(leaf):
    return f"{leaf.get('field')} {leaf.get('operator')}".strip()


def _walk_frame(registry, frame, warnings):
    """Frame: lista [op_or_null, element, element, ...] gdzie element to
    leaf (dict) albo zagniezdzona ramka (list). Zwraca fragment DjangoQL
    (string) albo '' gdy nic przekladalnego."""
    parts = []  # list[(joiner, fragment)]; joiner dla pierwszego = None
    for idx, element in enumerate(frame):
        if idx == 0:
            continue  # pierwszy element to operator ramki (lub None) — nieuzywany tu
        if isinstance(element, dict):
            prev_op = element.get("prev_op")
            frag = leaf_to_djangoql(registry, element)
            if frag is None:
                warnings.append(
                    f"Pominięto warunek: {_leaf_label(element)} (nieprzekładalny)"
                )
                continue
            joiner = _resolve_joiner(prev_op, element, frag, warnings)
            if joiner is False:
                continue  # andnot na liscu nie do odwrocenia -> juz zwarningowany
            parts.append((joiner, frag))
        elif isinstance(element, list):
            sub = _walk_frame(registry, element, warnings)
            if not sub:
                continue
            prev_op = element[0]
            joiner = _JOIN.get(str(prev_op)) if prev_op else None
            if str(prev_op) == str(ANDNOT):
                warnings.append(
                    "Pominięto zanegowaną grupę warunków "
                    "(DjangoQL nie ma `not(...)`)"
                )
                continue
            parts.append((joiner, f"({sub})"))
    return _join_parts(parts)


def _resolve_joiner(prev_op, leaf, frag, warnings):
    """Zwraca 'and'/'or'/None (joiner) albo False gdy warunek nalezy pominac.
    Dla ANDNOT na liscu probujemy inwersji operatora (De Morgan)."""
    if prev_op is None:
        return None
    if str(prev_op) in _JOIN:
        return _JOIN[str(prev_op)]
    if str(prev_op) == str(ANDNOT):
        # leaf juz zostal zrenderowany; inwersje robimy na poziomie operatora
        # przez ponowne wygenerowanie z zanegowana operacja, jezeli to mozliwe.
        # Best-effort: jezeli fragment ma '=' -> '!=', '~' -> '!~'. W innym
        # wypadku ostrzegamy i pomijamy.
        return False  # patrz Step 3b — pelna inwersja w osobnym kroku
    return None


def _join_parts(parts):
    if not parts:
        return ""
    out = parts[0][1]
    for joiner, frag in parts[1:]:
        out = f"{out} {joiner or 'and'} {frag}"
    return out


def multiseek_form_to_djangoql(form_json, registry):
    """Glowne API. form_json: dict z kluczem 'form_data'."""
    warnings = []
    form_data = form_json.get("form_data") or [None]
    query = _walk_frame(registry, form_data, warnings)
    return ConversionResult(query=query, warnings=warnings)
```

> Uwaga: w tym kroku `andnot` na liściu jest pomijany z ostrzeżeniem (zwracamy `False`). Pełną inwersję De Morgana dodajemy w Tasku 6, żeby nie mieszać dwóch zmian w jednym teście.

Dopisz w `_walk_frame`, gdy `joiner is False`, ostrzeżenie:

```python
            if joiner is False:
                warnings.append(
                    f"Pominięto zanegowany warunek: {_leaf_label(element)} "
                    "(andnot — patrz edytor)"
                )
                continue
```

- [ ] **Step 4: Run — pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -q`
Expected: PASS (wszystkie).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/djangoql_export.py src/bpp/tests/test_multiseek_djangoql_export.py
git commit -m "feat(djangoql-export): walk po ramkach form_data + warningi + ConversionResult"
```

---

## Task 6: `andnot` na liściu → inwersja operatora (De Morgan)

**Files:**
- Modify: `src/bpp/multiseek_registry/djangoql_export.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_export.py`

- [ ] **Step 1: Test inwersji (failing)**

```python
@pytest.mark.django_db
def test_andnot_leaf_inverts_operator():
    from multiseek.logic import ANDNOT, CONTAINS, EQUAL
    form = {
        "form_data": [
            None,
            {"field": "Rok", "operator": str(EQUAL), "value": 2023, "prev_op": None},
            {"field": "Tytuł pracy", "operator": str(CONTAINS), "value": "abc", "prev_op": str(ANDNOT)},
        ],
        "ordering": {},
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == 'rok = 2023 and tytul_oryginalny !~ "abc"'
    assert res.warnings == []
```

- [ ] **Step 2: Run — fail**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -k andnot_leaf -q`
Expected: FAIL — obecnie warning+skip.

- [ ] **Step 3: Implementacja inwersji**

Dodaj mapę inwersji i funkcję, i podłącz w `_walk_frame` zamiast `False`:

```python
_INVERT = {
    "=": "!=",
    "!=": "=",
    "~": "!~",
    "!~": "~",
    ">": "<=",
    ">=": "<",
    "<": ">=",
    "<=": ">",
    "startswith": "not startswith",
    "not startswith": "startswith",
}


def _invert_fragment(frag):
    """Zaneguj fragment przez podmiane operatora (De Morgan na liscu).
    Zwraca zanegowany fragment albo None gdy operatora nie da sie odwrocic."""
    # fragment ma postac '<lhs> <op> <rhs>'; op moze byc wieloczlonowy
    for op in sorted(_INVERT, key=len, reverse=True):
        token = f" {op} "
        if token in frag:
            lhs, rhs = frag.split(token, 1)
            return f"{lhs} {_INVERT[op]} {rhs}"
    return None
```

W `_walk_frame`, w gałęzi `dict`, zamień obsługę `prev_op == ANDNOT`:

```python
        if isinstance(element, dict):
            prev_op = element.get("prev_op")
            frag = leaf_to_djangoql(registry, element)
            if frag is None:
                warnings.append(
                    f"Pominięto warunek: {_leaf_label(element)} (nieprzekładalny)"
                )
                continue
            if prev_op is not None and str(prev_op) == str(ANDNOT):
                inverted = _invert_fragment(frag)
                if inverted is None:
                    warnings.append(
                        f"Pominięto zanegowany warunek: {_leaf_label(element)} "
                        "(nie da się odwrócić operatora)"
                    )
                    continue
                parts.append(("and", inverted))
                continue
            joiner = _JOIN.get(str(prev_op)) if prev_op else None
            parts.append((joiner, frag))
```

I usuń teraz nieużywaną `_resolve_joiner` (lub zostaw, jeśli używana gdzie indziej — w tym planie nie jest; usuń).

> Po inwersji walidacja fragmentu już była zrobiona w `leaf_to_djangoql`; `!~`/`!=` to legalne operatory DjangoQL, więc zanegowany fragment też się parsuje. (Opcjonalnie: dla bezpieczeństwa przepuść `inverted` przez `is_valid_rekord_djangoql`; jeśli False → warning.)

- [ ] **Step 4: Run — pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/djangoql_export.py src/bpp/tests/test_multiseek_djangoql_export.py
git commit -m "feat(djangoql-export): andnot na liscu -> inwersja operatora (De Morgan)"
```

---

## Task 7: `JednostkaQueryObject.to_djangoql` (+ round-trip fidelity)

**Files:**
- Modify: `src/bpp/multiseek_registry/fields/unit_fields.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_export.py`

- [ ] **Step 1: Test mapowania Jednostki + round-trip (failing)**

```python
@pytest.mark.django_db
def test_jednostka_equal_maps_to_autorzy_jednostka_rel():
    from multiseek.logic import EQUAL_FEMALE
    from model_bakery import baker
    from bpp.models import Jednostka

    j = baker.make(Jednostka, nazwa="Klinika X")
    field = registry.field_by_name["Jednostka"]
    frag = field.to_djangoql(j.pk, str(EQUAL_FEMALE))
    assert frag == f'autorzy.jednostka__rel = "Klinika X [{j.pk}]"'


@pytest.mark.django_db
def test_jednostka_plus_subunits_maps_to_virtual_field():
    from bpp.multiseek_registry.fields.constants import EQUAL_PLUS_SUB_FEMALE
    from model_bakery import baker
    from bpp.models import Jednostka

    j = baker.make(Jednostka, nazwa="Klinika X")
    field = registry.field_by_name["Jednostka"]
    frag = field.to_djangoql(j.pk, EQUAL_PLUS_SUB_FEMALE)
    assert frag == f'jednostka_z_podjednostkami__rel = "Klinika X [{j.pk}]"'


@pytest.mark.django_db
def test_roundtrip_jednostka_plus_subunits_same_rekordy(denorma):
    """Multiseek Q vs skonwertowane DjangoQL daja ten sam zbior Rekord."""
    from djangoql.queryset import apply_search
    from model_bakery import baker
    from bpp.djangoql_schema import BppQLSchema
    from bpp.models import Jednostka, Rekord
    from bpp.multiseek_registry.fields.constants import EQUAL_PLUS_SUB_FEMALE

    parent = baker.make(Jednostka, nazwa="Parent")
    child = baker.make(Jednostka, nazwa="Child", parent=parent)
    wc = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="P")
    autor = baker.make("bpp.Autor")
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=wc, autor=autor, jednostka=child)

    field = registry.field_by_name["Jednostka"]
    q = field.real_query(parent, EQUAL_PLUS_SUB_FEMALE)
    via_multiseek = set(Rekord.objects.filter(q).values_list("pk", flat=True))

    frag = field.to_djangoql(parent.pk, EQUAL_PLUS_SUB_FEMALE)
    via_djangoql = set(
        apply_search(Rekord.objects.all(), frag, schema=BppQLSchema)
        .distinct()
        .values_list("pk", flat=True)
    )
    assert via_multiseek == via_djangoql
```

- [ ] **Step 2: Run — fail**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -k jednostka -q`
Expected: FAIL — `JednostkaQueryObject` nie ma `to_djangoql`.

- [ ] **Step 3: Implementacja `to_djangoql`**

W `src/bpp/multiseek_registry/fields/unit_fields.py`, w `JednostkaQueryObject`:

```python
    def to_djangoql(self, value, operation):
        """Tlumaczenie na DjangoQL nad Rekord. Patrz real_query po semantyke.

        - rownosc/roznosc -> autorzy.jednostka__rel (picker po pk autora-jedn.)
        - '+ podrzedne' -> wirtualne pole jednostka_z_podjednostkami__rel
          (MPTT get_family, identyczne z real_query EQUAL_PLUS_SUB_FEMALE)
        - UNION / '+podrzedne+wspolna' -> None (warning): inny ksztalt zapytania,
          nie gwarantujemy rownowaznosci bez osobnego pola wirtualnego.
        """
        op = str(operation)
        try:
            obj = self.value_from_web(value)
        except Exception:  # noqa: BLE001 — uszkodzony/nieistniejacy pk -> warning
            return None
        if obj is None:
            return None
        label = str(obj).replace("\\", "\\\\").replace('"', '\\"')
        suffix = f'"{label} [{obj.pk}]"'

        if op == str(EQUAL_FEMALE):
            return f"autorzy.jednostka__rel = {suffix}"
        if op == str(DIFFERENT_FEMALE):
            return f"autorzy.jednostka__rel != {suffix}"
        if op == str(EQUAL_PLUS_SUB_FEMALE):
            return f"jednostka_z_podjednostkami__rel = {suffix}"
        # UNION_FEMALE, EQUAL_PLUS_SUB_UNION_FEMALE — nieprzekladalne 1:1
        return None
```

> `EQUAL_FEMALE`, `DIFFERENT_FEMALE` są już importowane na górze pliku; `EQUAL_PLUS_SUB_FEMALE` też (z `.constants`). Nie dubluj importów.

- [ ] **Step 4: Run — pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_export.py -k jednostka -q`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/multiseek_registry/fields/unit_fields.py src/bpp/tests/test_multiseek_djangoql_export.py
git commit -m "feat(djangoql-export): JednostkaQueryObject.to_djangoql (+ round-trip test)"
```

---

## Task 8: Endpoint `POST /multiseek/do-djangoql/`

**Files:**
- Modify: `src/bpp/views/mymultiseek.py`
- Modify: `src/django_bpp/urls.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_endpoint.py` (create)

- [ ] **Step 1: Test endpointu (failing)**

Create `src/bpp/tests/test_multiseek_djangoql_endpoint.py`:

```python
import json

import pytest
from django.urls import reverse
from model_bakery import baker
from multiseek.logic import CONTAINS

from bpp.const import GR_WPROWADZANIE_DANYCH


@pytest.fixture
def uprawniony(client):
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True)
    u.set_password("x")
    u.save()
    client.force_login(u)
    return u


@pytest.mark.django_db
def test_endpoint_requires_permission(client):
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=False)
    client.force_login(u)
    resp = client.post(reverse("bpp:multiseek-do-djangoql"), {"json": "{}"})
    assert resp.status_code == 403


@pytest.mark.django_db
def test_endpoint_happy_path(client, uprawniony):
    form = {
        "form_data": [
            None,
            {"field": "Tytuł pracy", "operator": str(CONTAINS), "value": "covid", "prev_op": None},
        ],
        "ordering": {},
        "report_type": "0",
    }
    resp = client.post(
        reverse("bpp:multiseek-do-djangoql"), {"json": json.dumps(form)}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == 'tytul_oryginalny ~ "covid"'
    assert data["warnings"] == []
    assert data["editor_url"].startswith(reverse("bpp:zapytanie"))
    assert "model=rekord" in data["editor_url"]


@pytest.mark.django_db
def test_endpoint_bad_json(client, uprawniony):
    resp = client.post(
        reverse("bpp:multiseek-do-djangoql"), {"json": "to nie jest json"}
    )
    assert resp.status_code == 400
```

- [ ] **Step 2: Run — fail**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_endpoint.py -q`
Expected: FAIL — `NoReverseMatch: bpp:multiseek-do-djangoql`.

- [ ] **Step 3: Widok**

W `src/bpp/views/mymultiseek.py` dopisz:

```python
import json

from django.http import HttpResponseBadRequest, JsonResponse
from django.views.generic import View

from bpp.multiseek_registry import registry as multiseek_registry
from bpp.multiseek_registry.djangoql_export import multiseek_form_to_djangoql
from bpp.views.zapytanie import (
    WprowadzanieDanychOrSuperuserMixin,
    user_can_use_query_editor,  # noqa: F401 — re-export wygody
)


class MultiseekToDjangoQLView(WprowadzanieDanychOrSuperuserMixin, View):
    """Tlumaczy biezacy formularz Multiseek (POST 'json') na zapytanie
    DjangoQL nad Rekord. Zwraca {query, warnings, editor_url}."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        raw = request.POST.get("json")
        if not raw:
            return HttpResponseBadRequest("Brak parametru 'json'.")
        try:
            form_json = json.loads(raw)
        except (ValueError, TypeError):
            return HttpResponseBadRequest("Niepoprawny JSON formularza.")
        if not isinstance(form_json, dict):
            return HttpResponseBadRequest("Oczekiwano obiektu JSON.")
        result = multiseek_form_to_djangoql(form_json, multiseek_registry)
        return JsonResponse(
            {
                "query": result.query,
                "warnings": result.warnings,
                "editor_url": result.editor_url,
            }
        )
```

- [ ] **Step 4: URL**

W `src/django_bpp/urls.py`, w sekcji multiseek (obok `multiseek/results/`), dodaj **przed** ogólnym `r"^multiseek/"` include:

```python
        url(
            r"^multiseek/do-djangoql/$",
            MultiseekToDjangoQLView.as_view(),
            name="multiseek-do-djangoql",
        ),
```

oraz import na górze: `from bpp.views.mymultiseek import MultiseekToDjangoQLView` (dołącz do istniejącego importu z `mymultiseek`, jeśli jest). Upewnij się, że trasa jest w bloku `namespace="bpp"` lub że `name` rozwiązuje się jako `bpp:multiseek-do-djangoql` (sprawdź, jak zarejestrowany jest `bpp:zapytanie` — użyj tego samego patternu/bloku URL-i).

> Kolejność ma znaczenie: `r"^multiseek/"` include łapie wszystko po prefiksie; nowa, bardziej szczegółowa trasa musi być wyżej.

- [ ] **Step 5: Run — pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_endpoint.py -q`
Expected: PASS (3).

- [ ] **Step 6: Commit**

```bash
git add src/bpp/views/mymultiseek.py src/django_bpp/urls.py src/bpp/tests/test_multiseek_djangoql_endpoint.py
git commit -m "feat(multiseek): endpoint POST /multiseek/do-djangoql/"
```

---

## Task 9: Filtr szablonowy `can_use_query_editor`

**Files:**
- Create: `src/bpp/templatetags/query_editor.py`
- Test: `src/bpp/tests/test_multiseek_djangoql_endpoint.py` (dopisanie)

- [ ] **Step 1: Test filtra (failing)**

Dopisz do `test_multiseek_djangoql_endpoint.py`:

```python
@pytest.mark.django_db
def test_template_filter_can_use_query_editor():
    from django.template import Context, Template

    su = baker.make("bpp.BppUser", is_superuser=True)
    plain = baker.make("bpp.BppUser", is_superuser=False, is_staff=False)
    tpl = Template(
        "{% load query_editor %}{{ user|can_use_query_editor }}"
    )
    assert tpl.render(Context({"user": su})) == "True"
    assert tpl.render(Context({"user": plain})) == "False"
```

- [ ] **Step 2: Run — fail**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_endpoint.py -k template_filter -q`
Expected: FAIL — `'query_editor' is not a registered tag library`.

- [ ] **Step 3: Implementacja**

Create `src/bpp/templatetags/query_editor.py`:

```python
from django import template

from bpp.views.zapytanie import user_can_use_query_editor

register = template.Library()


@register.filter(name="can_use_query_editor")
def can_use_query_editor(user):
    """True, gdy user moze korzystac z edytora zapytan DjangoQL."""
    if user is None:
        return False
    return user_can_use_query_editor(user)
```

- [ ] **Step 4: Run — pass**

Run: `uv run pytest src/bpp/tests/test_multiseek_djangoql_endpoint.py -k template_filter -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/templatetags/query_editor.py src/bpp/tests/test_multiseek_djangoql_endpoint.py
git commit -m "feat(templatetags): filtr can_use_query_editor"
```

---

## Task 10: UI — przycisk + drawer + JS w `index.html`

**Files:**
- Modify: `src/django_bpp/templates/multiseek/index.html`
- Test: manualny (Playwright opcjonalnie poza zakresem tego planu)

- [ ] **Step 1: Załaduj filtr i dodaj przycisk**

Na górze `index.html` (po `{% extends %}`/istniejących `{% load %}`):

```django
{% load query_editor %}
```

W `<div class="cell button-group stacked-for-small">` (obok `id="saveFormButton"` itd.), dodaj — **tylko dla uprawnionych**:

```django
{% if request.user|can_use_query_editor %}
<button type="button" class="button secondary"
        data-action="to-djangoql"
        id="toDjangoqlButton">
    <i class="fi-clipboard-notes" aria-hidden="true"></i> Pokaż jako zapytanie DjangoQL
</button>
{% endif %}
```

- [ ] **Step 2: Drawer (Foundation reveal) + CSRF**

Tuż przed zamknięciem `</form>` (po sekcji `<script>` lub obok), dodaj markup szuflady i ukryty token CSRF:

```django
{% if request.user|can_use_query_editor %}
{% csrf_token %}
<div class="reveal" id="djangoqlDrawer" data-reveal>
    <h4>Zapytanie DjangoQL</h4>
    <p class="help-text">Równoważne zapytanie nad modelem Rekord.</p>
    <textarea id="djangoqlQuery" rows="4" readonly spellcheck="false"></textarea>
    <div id="djangoqlWarnings" class="callout warning" style="display:none"></div>
    <div class="button-group">
        <button type="button" class="button" id="djangoqlCopy">
            <i class="fi-clipboard" aria-hidden="true"></i> Kopiuj
        </button>
        <a class="button success" id="djangoqlOpenEditor" href="#" target="_blank">
            <i class="fi-arrow-right" aria-hidden="true"></i> Otwórz w edytorze zapytań
        </a>
    </div>
    <button class="close-button" data-close aria-label="Zamknij" type="button">
        <span aria-hidden="true">&times;</span>
    </button>
</div>
{% endif %}
```

- [ ] **Step 3: JS — fetch + wypełnienie drawera**

W bloku `<script>` (w handlerze event-delegation `document.addEventListener('click', ...)`), dołóż gałąź:

```javascript
                // Konwersja na DjangoQL
                btn = e.target.closest('[data-action="to-djangoql"]');
                if (btn) {
                    e.preventDefault();
                    openDjangoqlDrawer();
                    return;
                }
```

I dopisz funkcje (w tym samym `<script>`):

```javascript
            function getCsrfToken() {
                var el = document.querySelector('input[name="csrfmiddlewaretoken"]');
                return el ? el.value : '';
            }

            function openDjangoqlDrawer() {
                var payload = formAsJSON();  // JSON string
                var body = new URLSearchParams();
                body.append('json', payload);
                fetch('./do-djangoql/', {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCsrfToken(),
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: body.toString()
                }).then(function (r) {
                    if (!r.ok) { throw new Error('HTTP ' + r.status); }
                    return r.json();
                }).then(function (data) {
                    document.getElementById('djangoqlQuery').value = data.query || '';
                    document.getElementById('djangoqlOpenEditor').href = data.editor_url;
                    var w = document.getElementById('djangoqlWarnings');
                    if (data.warnings && data.warnings.length) {
                        w.innerHTML = '<strong>Uwaga:</strong><ul><li>' +
                            data.warnings.map(function (s) {
                                return $('<div>').text(s).html();
                            }).join('</li><li>') + '</li></ul>';
                        w.style.display = '';
                    } else {
                        w.style.display = 'none';
                    }
                    $('#djangoqlDrawer').foundation('open');
                }).catch(function (err) {
                    alert('Nie udało się przetłumaczyć formularza: ' + err.message);
                });
            }
```

I obsługa „Kopiuj”:

```javascript
            document.addEventListener('click', function (e) {
                var c = e.target.closest('#djangoqlCopy');
                if (c) {
                    e.preventDefault();
                    var ta = document.getElementById('djangoqlQuery');
                    navigator.clipboard.writeText(ta.value).then(function () {
                        c.classList.add('success');
                    });
                }
            });
```

> Foundation reveal wymaga zainicjalizowanego `$(document).foundation()` — w BPP jest globalnie. Jeśli drawer się nie otwiera, sprawdź, czy element `#djangoqlDrawer` istnieje w DOM przed inicjalizacją Foundation (jest renderowany statycznie, więc OK).

- [ ] **Step 4: Weryfikacja manualna (run-site)**

```bash
uv run run-site run --no-browser
```

Zaloguj się jako `admin/admin`, wejdź na `/multiseek/`, zbuduj kilka warunków (Tytuł zawiera…, Rok ≥…, Jednostka „+podrzędne”), kliknij „Pokaż jako zapytanie DjangoQL”. Sprawdź:
- drawer pokazuje poprawne zapytanie,
- „Kopiuj” działa,
- „Otwórz w edytorze zapytań” otwiera `/zapytanie/?model=rekord&query=…` i zwraca wyniki,
- niewidoczny dla niezalogowanego/nieuprawnionego (sprawdź wylogowany — przycisku brak).

- [ ] **Step 5: Commit**

```bash
git add src/django_bpp/templates/multiseek/index.html
git commit -m "feat(multiseek-ui): przycisk + drawer 'Pokaz jako zapytanie DjangoQL'"
```

---

## Task 11: Pre-commit + pełna regresja modułu

**Files:** — (bez nowych)

- [ ] **Step 1: Pre-commit na zmienionych plikach**

Run: `pre-commit`
Jeśli zgłosi uwagi — analizuj po kolei i poprawiaj ręcznie (Edit), bez `ruff --fix`.

- [ ] **Step 2: Testy modułu konwertera + edytora**

Run:
```bash
uv run pytest \
  src/bpp/tests/test_multiseek_djangoql_export.py \
  src/bpp/tests/test_multiseek_djangoql_endpoint.py \
  src/bpp/tests/test_jednostka_podjednostki_field.py \
  src/bpp/tests/test_zapytanie.py -q
```
Expected: PASS (wszystko zielone).

- [ ] **Step 3: Commit (jeśli pre-commit coś zmienił)**

```bash
git add -A
git commit -m "chore: pre-commit konwertera multiseek->djangoql"
```

---

## Notatki / ryzyka

- **Pokrycie pól value-list**: domyślny dispatcher obsługuje skalary, daty, autocomplete i (przez nadpisanie) Jednostkę. Pola `VALUE_LIST` (np. Typ rekordu, Charakter ogólny, Język) domyślnie lądują jako **warning**, bo etykieta z formularza nie zawsze == wartość w bazie. Jeśli zajdzie potrzeba, dodaj `to_djangoql` per-pole (wzorzec jak w Tasku 7) — walidacja fragmentu i tak chroni przed błędnym wyjściem. To świadomy, udokumentowany kompromis (best-effort + warn), zgodny ze specyfikacją.
- **Walidacja fragmentu** (`is_valid_rekord_djangoql`) gwarantuje, że wyjście zawsze się parsuje — pola, których `field_name` nie ma w schemacie Rekord (denorm-cache typu `naz_im_1_3`), automatycznie degradują do warningu zamiast psuć całe zapytanie.
- **UNION ops Jednostki**: świadomie nieprzekładane 1:1 (inny kształt zapytania). Jeśli okażą się potrzebne, rozwiązanie to drugie pole wirtualne (jak w spec §3) + test równoważności zbiorów.
- **Lokalizacja operatorów**: porównujemy przez `str(<stała multiseek>)`, więc działa niezależnie od aktywnego języka.
