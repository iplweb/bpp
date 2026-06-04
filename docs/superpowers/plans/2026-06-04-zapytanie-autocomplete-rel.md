# Zapytanie: pickery `__rel` + wyjaśnienie „0 wyników" — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dodać w djangoql-iplweb addytywny kwarg `AutocompleteField(lookup_name=…)` + idiom `<fk>__rel` (PR 1), a w BPP użyć go w widoku „Szukaj zapytaniem": pickery autocomplete `autorzy.autor__rel`, `autorzy.jednostka__rel`, `tytul__rel`, `aktualna_jednostka__rel` obok zachowanej trawersacji z kropką, plus rozbicie `explain_empty()` „dlaczego 0 wyników" (PR 2).

**Architecture:** Dwie nazwy: kropka = domyślna trawersacja FK (bez zmian), `<fk>__rel` = picker (leaf `AutocompleteField`) filtrujący realny FK przez nowy `lookup_name`. Schemat BPP (`BppZapytanieSchema(ExtrasSchema)`) dorzuca syntetyczne nazwy `*__rel` w `get_fields` i mapuje je w `autocomplete`. „0 wyników" liczy `explain_empty()` raz, gdy `count == 0`.

**Tech Stack:** Django, djangoql-iplweb (0.22 → 0.23), pytest + model_bakery (bpp), Django `TestCase` + pytest-django (djangoql `test_project`), Foundation CSS (frontend).

**Repozytoria / gałęzie:**
- djangoql-iplweb: `~/Programowanie/djangoql-iplweb`, gałąź `feat/autocomplete-lookup-name` (już istnieje, ma commit specu `d4b7990`).
- bpp: `~/Programowanie/bpp`, gałąź `bpp-zapytanie-autocomplete-rel` (już istnieje, ma commit specu `0cc3cd473`).

**Kolejność / zależność (decyzja użytkownika):** Najpierw djangoql → release na PyPI → bpp pinuje wersję. Oba PR-y otwiera Claude (`gh pr create`); tag/PyPI-release djangoql jest po stronie użytkownika. Faza B implementowana lokalnie przeciw editable-checkoutowi djangoql (krok B0), a `pyproject` bumpuje się do wydanej wersji dopiero w B7.

**Uwaga o repo djangoql:** `master` ma niezacommitowany WIP (refactor tłumaczeń). Pracujemy WYŁĄCZNIE na gałęzi `feat/autocomplete-lookup-name`, commitujemy TYLKO swoje pliki (pathspec), nie ruszamy WIP.

---

## FAZA A — djangoql-iplweb (PR 1)

Komendy uruchamiać **z** `~/Programowanie/djangoql-iplweb`, z jawnym
`DJANGO_SETTINGS_MODULE=test_project.settings` (zmienna z profilu bpp potrafi
wyciekać do środowiska).

### Task A1: kwarg `lookup_name` + remap lookupu na realny FK

**Files:**
- Modify: `~/Programowanie/djangoql-iplweb/djangoql/extras.py` (klasa `AutocompleteField`, `__init__` ok. linii 523–555)
- Test: `~/Programowanie/djangoql-iplweb/test_project/core/tests/test_autocomplete.py`

- [ ] **Step 1: Dopisz testy (na koniec pliku testowego)**

```python
class RelAndPickerSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    """`author` zostaje relacją (trawersacja z kropką), a `author__rel` to
    picker filtrujący realny FK `author` przez lookup_name."""

    include = (Book, User)
    autocomplete = {
        Book: {
            'author__rel': {
                'lookup_name': 'author',
                'queryset': lambda s: User.objects.filter(
                    username__icontains=s
                ).order_by('username'),
                'search_fields': ['username'],
                'label': lambda u: u.username,
            },
        },
    }

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        if model is Book:
            fields.append('author__rel')
        return fields


class LookupNameTest(TestCase):
    def test_lookup_name_defaults_to_field_name(self):
        field = AutocompleteField(model=Book, name='author__rel')
        self.assertEqual(field.get_lookup_name(), 'author__rel')

    def test_lookup_name_overrides_lookup(self):
        field = AutocompleteField(
            model=Book, name='author__rel', lookup_name='author'
        )
        self.assertEqual(field.get_lookup_name(), 'author')


class RelAndPickerCoexistTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.kow = User.objects.create(username='Jan Kowalski')
        cls.nowak = User.objects.create(username='Anna Nowak')
        cls.b1 = Book.objects.create(name='b1', author=cls.kow)
        cls.b2 = Book.objects.create(name='b2', author=cls.nowak)

    def _search(self, q):
        return apply_search(Book.objects.all(), q, schema=RelAndPickerSchema)

    def test_picker_filters_real_fk_by_pk(self):
        qs = self._search('author__rel = "Jan Kowalski [%d]"' % self.kow.pk)
        sql = str(qs.query)
        self.assertIn('author_id', sql)
        self.assertNotIn('author__rel', sql)
        self.assertEqual(list(qs), [self.b1])

    def test_picker_in_filters_by_pks(self):
        qs = self._search(
            'author__rel in ("Jan Kowalski [%d]", "Anna Nowak [%d]")'
            % (self.kow.pk, self.nowak.pk)
        )
        self.assertEqual(sorted(b.pk for b in qs), [self.b1.pk, self.b2.pk])

    def test_picker_free_text_fallback_targets_real_fk(self):
        qs = self._search('author__rel = "kowal"')
        sql = str(qs.query).lower()
        self.assertIn('username', sql)
        self.assertIn('like', sql)
        self.assertEqual(list(qs), [self.b1])

    def test_dot_traversal_still_works(self):
        qs = self._search('author.username = "Jan Kowalski"')
        self.assertEqual(list(qs), [self.b1])

    def test_both_idioms_in_one_query(self):
        qs = self._search(
            'author.username = "Jan Kowalski" '
            'and author__rel = "Jan Kowalski [%d]"' % self.kow.pk
        )
        self.assertEqual(list(qs), [self.b1])

    def test_picker_is_value_field_relation_is_relation(self):
        schema = RelAndPickerSchema(Book)
        fields = schema.models['core.book']
        self.assertIsInstance(fields['author__rel'], AutocompleteField)
        self.assertIsInstance(fields['author'], RelationField)
        self.assertEqual(fields['author'].type, 'relation')
```

- [ ] **Step 2: Uruchom testy — muszą paść (RED)**

Run: `cd ~/Programowanie/djangoql-iplweb && DJANGO_SETTINGS_MODULE=test_project.settings uv run pytest test_project/core/tests/test_autocomplete.py -k "LookupName or RelAndPicker" -v 2>&1 | tee /tmp/dq_a1.log`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'lookup_name'` (w testach budujących `AutocompleteField(... lookup_name=...)` i w `RelAndPickerSchema`).

- [ ] **Step 3: Dodaj kwarg `lookup_name` w `AutocompleteField.__init__`**

W `djangoql/extras.py`, w sygnaturze `__init__` dodaj parametr po `id_of=None,`:

```python
        id_of=None,
        lookup_name=None,
        search_param='q',
```

i w ciele `__init__`, po `self.id_of = id_of`:

```python
        self.id_of = id_of
        self._lookup_name = lookup_name
```

- [ ] **Step 4: Dodaj metodę `get_lookup_name` (w sekcji „lookup / filtering")**

W `AutocompleteField`, tuż przed `get_lookup_value` (albo zaraz po komentarzu
`# -- lookup / filtering`), dodaj:

```python
    def get_lookup_name(self):
        # `<fk>__rel` (alt-nazwa pickera) filtruje realny FK podany w
        # lookup_name; bez niego zachowanie = self.name (non-breaking).
        return self._lookup_name or self.name
```

- [ ] **Step 5: Uruchom testy — muszą przejść (GREEN)**

Run: `cd ~/Programowanie/djangoql-iplweb && DJANGO_SETTINGS_MODULE=test_project.settings uv run pytest test_project/core/tests/test_autocomplete.py -v 2>&1 | tee /tmp/dq_a1.log`
Expected: PASS (wszystkie, łącznie z istniejącymi — regresja zachowana).

- [ ] **Step 6: Commit (tylko swoje pliki)**

```bash
cd ~/Programowanie/djangoql-iplweb
git add djangoql/extras.py test_project/core/tests/test_autocomplete.py
git commit -m "feat(extras): AutocompleteField lookup_name (picker pod alt-nazwą filtruje realny FK)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- djangoql/extras.py test_project/core/tests/test_autocomplete.py
```

### Task A2: dokumentacja idiomu `<fk>__rel` + CHANGES

**Files:**
- Modify: `~/Programowanie/djangoql-iplweb/docs/integrating-django-autocomplete-light.md`
- Modify: `~/Programowanie/djangoql-iplweb/CHANGES.rst`

- [ ] **Step 1: Dopisz `lookup_name` do tabeli „Configuration reference"**

W `docs/integrating-django-autocomplete-light.md`, w tabeli pod
`## Configuration reference`, po wierszu `id_of`, dodaj wiersz:

```markdown
| `lookup_name` | `None` | real model field to filter on (default: the field's own name); lets a picker live under a second name like `<fk>__rel` |
```

- [ ] **Step 2: Dodaj sekcję o idiomie (przed `## Limitations`)**

```markdown
## Exposing a FK as both a navigable relation and a value picker

By default a FK is a **navigable relation** — you traverse into it
(`author.last_name`, `author.country.code`). The picker above instead exposes it
as a **value field** under the *same* name, which removes traversal. To keep
**both**, expose the picker under a *second* name and point it back at the real
FK with `lookup_name`. The recommended convention is `<fk>__rel` (double
underscore, consistent with the derived-field family `__count` / `__sum` / …):

```python
from django.contrib.auth.models import User
from djangoql.extras import AutocompleteSchemaMixin
from djangoql.schema import DjangoQLSchema

from .models import Book


class BookSchema(AutocompleteSchemaMixin, DjangoQLSchema):
    include = (Book, User)
    autocomplete = {
        Book: {
            # picker; `author` itself stays a navigable relation
            'author__rel': {
                'lookup_name': 'author',           # filters the real FK
                'url': 'user-autocomplete',
                'search_fields': ['username'],
            },
        },
    }

    def get_fields(self, model):
        # `author__rel` is synthetic (not a real model field), so it must be
        # added explicitly or it won't be introspected / suggested.
        fields = list(super().get_fields(model))
        if model is Book:
            fields.append('author__rel')
        return fields
```

Now both work side by side:

- `author.username = "kowalski"` — traversal into the related model (unchanged);
- `author__rel = "Jan Kowalski [42]"` — picker, filters `author_id = 42`
  (with the usual `icontains` free-text fallback over `search_fields`).
```

(Uwaga: w docu komentarze i fence-bloki jak wyżej; zachowaj istniejący styl.)

- [ ] **Step 3: Dodaj wpis w `CHANGES.rst` (na górze, nad `0.22.1`)**

```rst
0.23.0 (unreleased)
-------------------

* Add an additive, non-breaking ``lookup_name`` kwarg to
  ``djangoql.extras.AutocompleteField``. It overrides ``get_lookup_name()`` so a
  picker can live under a second field name (e.g. ``<fk>__rel``) while still
  filtering the **real** foreign key — letting a FK be exposed *both* as a
  navigable relation (dot traversal) *and* as a value picker. Default ``None``
  preserves current behavior. New docs section "Exposing a FK as both a
  navigable relation and a value picker" documents the ``<fk>__rel`` idiom.

```

- [ ] **Step 4: (opcjonalnie) zbuduj docs lokalnie dla sanity**

Run: `cd ~/Programowanie/djangoql-iplweb && uv run mkdocs build -q 2>&1 | tail -5`
Expected: brak błędów (lub pomiń, jeśli mkdocs nie jest w dev-deps).

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/djangoql-iplweb
git add docs/integrating-django-autocomplete-light.md CHANGES.rst
git commit -m "docs(extras): document <fk>__rel idiom (relation + picker side by side)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- docs/integrating-django-autocomplete-light.md CHANGES.rst
```

### Task A3: pełny test djangoql + push + PR 1

- [ ] **Step 1: Pełny zestaw testów autocomplete (GREEN)**

Run: `cd ~/Programowanie/djangoql-iplweb && DJANGO_SETTINGS_MODULE=test_project.settings uv run pytest test_project/core/tests/test_autocomplete.py -v 2>&1 | tee /tmp/dq_full.log`
Expected: PASS (wszystkie).

- [ ] **Step 2: Push gałęzi**

```bash
cd ~/Programowanie/djangoql-iplweb
git push -u origin feat/autocomplete-lookup-name
```

- [ ] **Step 3: Otwórz PR 1**

```bash
cd ~/Programowanie/djangoql-iplweb
gh pr create --base master --head feat/autocomplete-lookup-name \
  --title "feat(extras): AutocompleteField lookup_name + idiom <fk>__rel" \
  --body "$(cat <<'EOF'
Addytywny, non-breaking kwarg `lookup_name` na `AutocompleteField` (domyślnie
`None` = bez zmian). Pozwala wystawić picker pod drugą nazwą `<fk>__rel`
filtrujący realny FK, obok relacji z kropką do trawersacji. Plus sekcja w docach
dokumentująca idiom.

Spec: `docs/superpowers/specs/2026-06-04-autocomplete-lookup-name-rel-idiom-design.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 4: ⛳ CHECKPOINT — release djangoql**

Po zmergowaniu PR 1 użytkownik (lub osobny proces) taguje i publikuje
djangoql-iplweb **0.23.0** na PyPI. Faza B implementowana jest równolegle
przeciw editable-checkoutowi (B0); finalny pin (`B7`) i PR 2 idą po publikacji.

---

## FAZA B — bpp (PR 2)

Komendy z `~/Programowanie/bpp`. Testy: `UV_NO_SYNC=1 uv run --all-extras pytest …`
(testcontainers z optional.dev; bez tego `uv run` zdejmie zależność). Wyniki
piszemy do `/tmp` i grepujemy (nie uruchamiamy testów dwa razy).

### Task B0: dev-setup — lokalny djangoql z `lookup_name`

- [ ] **Step 1: Zainstaluj editable djangoql do venva bpp (tymczasowo, NIE commitujemy)**

```bash
cd ~/Programowanie/bpp
uv pip install -e ~/Programowanie/djangoql-iplweb
```

- [ ] **Step 2: Zweryfikuj, że `lookup_name` jest dostępne**

Run:
```bash
cd ~/Programowanie/bpp
UV_NO_SYNC=1 uv run python -c "import inspect; from djangoql.extras import AutocompleteField; print('lookup_name' in inspect.signature(AutocompleteField.__init__).parameters)"
```
Expected: `True`

(Wszystkie kolejne komendy testowe w fazie B uruchamiamy z prefiksem
`UV_NO_SYNC=1`, żeby `uv run` nie przeładował zależności i nie zdjął editable.)

### Task B1: `BppZapytanieSchema` z pickerami `__rel`

**Files:**
- Modify: `~/Programowanie/bpp/src/bpp/views/zapytanie.py`
- Test: `~/Programowanie/bpp/src/bpp/tests/test_zapytanie.py`

- [ ] **Step 1: Dopisz testy schematu (na koniec test_zapytanie.py)**

```python
@pytest.mark.django_db
def test_tytul_rel_picker_filters_by_pk():
    from djangoql.queryset import apply_search

    from bpp.models import Autor
    from bpp.models.autor import Tytul
    from bpp.views.zapytanie import BppZapytanieSchema

    prof = baker.make(Tytul, nazwa="profesor", skrot="prof.")
    dr = baker.make(Tytul, nazwa="doktor", skrot="dr")
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", tytul=prof)
    baker.make("bpp.Autor", nazwisko="Nowak", tytul=dr)

    qs = apply_search(
        Autor.objects.all(),
        'tytul__rel = "profesor [%d]"' % prof.pk,
        schema=BppZapytanieSchema,
    )
    assert list(qs) == [a1]


@pytest.mark.django_db
def test_tytul_dot_traversal_still_works():
    from djangoql.queryset import apply_search

    from bpp.models import Autor
    from bpp.models.autor import Tytul
    from bpp.views.zapytanie import BppZapytanieSchema

    prof = baker.make(Tytul, nazwa="profesor", skrot="prof.")
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", tytul=prof)

    qs = apply_search(
        Autor.objects.all(), 'tytul.skrot = "prof."', schema=BppZapytanieSchema
    )
    assert list(qs) == [a1]


@pytest.mark.django_db
def test_aktualna_jednostka_rel_picker_filters_by_pk():
    from djangoql.queryset import apply_search

    from bpp.models import Autor, Jednostka
    from bpp.views.zapytanie import BppZapytanieSchema

    j = baker.make(Jednostka, nazwa="Katedra X")
    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", aktualna_jednostka=j)
    baker.make("bpp.Autor", nazwisko="Nowak")

    qs = apply_search(
        Autor.objects.all(),
        'aktualna_jednostka__rel = "Katedra X [%d]"' % j.pk,
        schema=BppZapytanieSchema,
    )
    assert list(qs) == [a1]


@pytest.mark.django_db
def test_autor_schema_has_rel_fields_and_keeps_relations():
    from bpp.models import Autor
    from bpp.views.zapytanie import BppZapytanieSchema

    schema = BppZapytanieSchema(Autor)
    fields = schema.models["bpp.autor"]
    assert "tytul__rel" in fields
    assert "aktualna_jednostka__rel" in fields
    assert fields["tytul"].type == "relation"  # trawersacja zachowana


@pytest.mark.django_db
def test_rekord_schema_has_autorzy_rel_pickers():
    from bpp.models.cache import Autorzy, Rekord
    from bpp.views.zapytanie import BppZapytanieSchema

    schema = BppZapytanieSchema(Rekord)
    autorzy_fields = schema.models[schema.model_label(Autorzy)]
    assert "autor__rel" in autorzy_fields
    assert "jednostka__rel" in autorzy_fields
    assert autorzy_fields["autor"].type == "relation"


@pytest.mark.django_db
def test_rekord_autorzy_autor_rel_filters_real_fk():
    from djangoql.queryset import apply_search

    from bpp.models.cache import Rekord
    from bpp.views.zapytanie import BppZapytanieSchema

    qs = apply_search(
        Rekord.objects.all(),
        'autorzy.autor__rel = "X [1]"',
        schema=BppZapytanieSchema,
    )
    sql = str(qs.query).lower()
    assert "autor__rel" not in sql  # remap zadziałał (nie filtruje alt-nazwy)
    assert "autor_id" in sql
```

- [ ] **Step 2: Uruchom — RED**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py -k "rel or traversal or schema" -v 2>&1 | tee /tmp/bpp_b1.log`
Expected: FAIL — `ImportError: cannot import name 'BppZapytanieSchema'`.

- [ ] **Step 3: Dodaj `BppZapytanieSchema` w `zapytanie.py`**

W `src/bpp/views/zapytanie.py` zmień import djangoql (jest `from djangoql.extras
import ExtrasSchema`) — zostaw `ExtrasSchema`, dodaj importy modeli i klasę.
Tuż po istniejących importach modeli (`from bpp.models import Autor`,
`from bpp.models.cache import Rekord`) dodaj:

```python
from bpp.models.autor import Tytul
from bpp.models.cache import Autorzy
```

A po stałych `MODELS = {...}` (przed klasą `WprowadzanieDanychOrSuperuserMixin`)
dodaj:

```python
class BppZapytanieSchema(ExtrasSchema):
    """ExtrasSchema z pickerami ``<fk>__rel`` obok trawersacji z kropką.

    Notacja z kropką (``autorzy.autor.nazwisko``, ``tytul.skrot``) zostaje
    domyślna dla FK. ``<fk>__rel`` to picker autocomplete: wybierasz konkretny
    obiekt z podpowiedzi i filtruje po jego pk (``lookup_name`` wskazuje realny
    FK), z fallbackiem free-text (icontains po ``search_fields``).
    """

    autocomplete = {
        Autorzy: {
            "autor__rel": {
                "lookup_name": "autor",
                "url": "bpp:public-autor-autocomplete",
                "search_fields": ["nazwisko", "imiona"],
            },
            "jednostka__rel": {
                "lookup_name": "jednostka",
                "url": "bpp:jednostka-autocomplete",
                "search_fields": ["nazwa", "skrot"],
            },
        },
        Autor: {
            "tytul__rel": {
                "lookup_name": "tytul",
                "queryset": Tytul.objects.all(),
                "search_fields": ["nazwa", "skrot"],
            },
            "aktualna_jednostka__rel": {
                "lookup_name": "aktualna_jednostka",
                "url": "bpp:jednostka-autocomplete",
                "search_fields": ["nazwa", "skrot"],
            },
        },
    }

    # Nazwy syntetyczne (nie ma ich w modelu) — bez tego nie zostaną
    # zintrospektowane ani podpowiedziane.
    _REL_FIELDS = {
        Autorzy: ["autor__rel", "jednostka__rel"],
        Autor: ["tytul__rel", "aktualna_jednostka__rel"],
    }

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        fields += self._REL_FIELDS.get(model, [])
        return fields
```

- [ ] **Step 4: Uruchom — GREEN**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py -k "rel or traversal or schema" -v 2>&1 | tee /tmp/bpp_b1.log`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/bpp
git add src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
git commit -m "feat(zapytanie): BppZapytanieSchema — pickery <fk>__rel obok trawersacji

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
```

### Task B2: podepnij schemat do widoku (apply_search / introspect / suggestions)

**Files:**
- Modify: `~/Programowanie/bpp/src/bpp/views/zapytanie.py`
- Test: `~/Programowanie/bpp/src/bpp/tests/test_zapytanie.py`

- [ ] **Step 1: Dopisz test widoku (przez klienta)**

```python
@pytest.mark.django_db
def test_zapytanie_view_tytul_rel_picker(superuser_client):
    from bpp.models.autor import Tytul

    prof = baker.make(Tytul, nazwa="profesor", skrot="prof.")
    baker.make("bpp.Autor", nazwisko="Kowalski", tytul=prof)

    response = superuser_client.get(
        reverse(URL),
        {"model": "autor", "query": 'tytul__rel = "profesor [%d]"' % prof.pk},
    )
    assert response.status_code == 200
    assert response.context["error"] is None
    assert response.context["count"] == 1
```

- [ ] **Step 2: Uruchom — RED**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py::test_zapytanie_view_tytul_rel_picker -v 2>&1 | tee /tmp/bpp_b2.log`
Expected: FAIL — `Unknown field: tytul__rel` (widok wciąż używa `ExtrasSchema`, który nie zna `__rel`).

- [ ] **Step 3: Zamień `ExtrasSchema` → `BppZapytanieSchema` w 3 miejscach**

W `src/bpp/views/zapytanie.py`:
- w `ZapytanieView.render_results`:
  `queryset = apply_search(queryset, query, schema=ExtrasSchema)` →
  `queryset = apply_search(queryset, query, schema=BppZapytanieSchema)`
- w `ZapytanieIntrospectView.get`:
  `schema = ExtrasSchema(model)` → `schema = BppZapytanieSchema(model)`
- w `ZapytanieSuggestionsView.get`:
  `view = SuggestionsAPIView.as_view(schema=ExtrasSchema(model))` →
  `view = SuggestionsAPIView.as_view(schema=BppZapytanieSchema(model))`

- [ ] **Step 4: Uruchom — GREEN**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py::test_zapytanie_view_tytul_rel_picker -v 2>&1 | tee /tmp/bpp_b2.log`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/bpp
git add src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
git commit -m "feat(zapytanie): podepnij BppZapytanieSchema w widoku i endpointach

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
```

### Task B3: endpoint sugestii zwraca opcje pickera

**Files:**
- Test: `~/Programowanie/bpp/src/bpp/tests/test_zapytanie.py`

(Implementacja już gotowa po B2 — to test regresyjny wiązania endpointu sugestii
z pickerami: deterministycznie dla `tytul__rel` (queryset), smoke dla
`autorzy.autor__rel` (provider DAL in-process; fulltext autora bywa niedet.).)

- [ ] **Step 1: Dopisz testy**

```python
@pytest.mark.django_db
def test_zapytanie_suggestions_tytul_rel_returns_options(superuser_client):
    from bpp.models.autor import Tytul

    prof = baker.make(Tytul, nazwa="profesor", skrot="prof.")
    url = reverse("bpp:zapytanie_suggestions", kwargs={"model_key": "autor"})
    response = superuser_client.get(url, {"field": "tytul__rel", "search": "prof"})
    assert response.status_code == 200
    data = response.json()
    assert any("[%d]" % prof.pk in item for item in data["items"])


@pytest.mark.django_db
def test_zapytanie_suggestions_autor_rel_dal_smoke(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    url = reverse("bpp:zapytanie_suggestions", kwargs={"model_key": "rekord"})
    response = superuser_client.get(
        url, {"field": "autorzy.autor__rel", "search": "Kowal"}
    )
    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)
```

- [ ] **Step 2: Uruchom — GREEN (test potwierdza wiązanie z B2)**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py -k suggestions -v 2>&1 | tee /tmp/bpp_b3.log`
Expected: PASS. (Jeśli `tytul__rel` padnie z „doesn't support suggestions" — sprawdź, że config ma `queryset`; jeśli `autorzy.autor__rel` padnie na resolve url — sprawdź nazwę `bpp:public-autor-autocomplete`.)

- [ ] **Step 3: Commit**

```bash
cd ~/Programowanie/bpp
git add src/bpp/tests/test_zapytanie.py
git commit -m "test(zapytanie): endpoint sugestii zwraca opcje pickerow __rel

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- src/bpp/tests/test_zapytanie.py
```

### Task B4: `explain_empty()` — kontekst „dlaczego 0"

**Files:**
- Modify: `~/Programowanie/bpp/src/bpp/views/zapytanie.py`
- Test: `~/Programowanie/bpp/src/bpp/tests/test_zapytanie.py`

- [ ] **Step 1: Dopisz testy**

```python
def _breakdown_leaves(node):
    if not node["children"]:
        yield node
    for ch in node["children"]:
        yield from _breakdown_leaves(ch)


@pytest.mark.django_db
def test_zapytanie_breakdown_explains_zero(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    response = superuser_client.get(
        reverse(URL),
        {
            "model": "autor",
            "query": 'nazwisko = "Kowalski" and imiona = "asdfo"',
        },
    )
    assert response.status_code == 200
    assert response.context["count"] == 0
    breakdown = response.context["breakdown"]
    assert breakdown is not None
    assert breakdown["count"] == 0
    leaves = {leaf["text"]: leaf["count"] for leaf in _breakdown_leaves(breakdown)}
    assert any("asdfo" in t and c == 0 for t, c in leaves.items())


@pytest.mark.django_db
def test_zapytanie_no_breakdown_when_results(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski")
    response = superuser_client.get(
        reverse(URL), {"model": "autor", "query": 'nazwisko = "Kowalski"'}
    )
    assert response.context["count"] == 1
    assert response.context["breakdown"] is None
```

- [ ] **Step 2: Uruchom — RED**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py -k breakdown -v 2>&1 | tee /tmp/bpp_b4.log`
Expected: FAIL — `KeyError: 'breakdown'` (kontekst nie ma jeszcze klucza).

- [ ] **Step 3: Podłącz `explain_empty` w `render_results`**

W `src/bpp/views/zapytanie.py`:

Na górze pliku dodaj importy:
```python
import logging

from djangoql.breakdown import explain_empty
```
i pod importami zdefiniuj logger:
```python
logger = logging.getLogger(__name__)
```

W `ZapytanieView.render_results`, po bloku `try/except` (po tym jak ustalone
są `count`, `error`), a przed budową `context`, dodaj:

```python
        breakdown = None
        if error is None and count == 0:
            try:
                breakdown = explain_empty(
                    model.objects.all(), query, schema=BppZapytanieSchema
                )
            except (DjangoQLError, FieldError, ValidationError, ValueError):
                logger.exception(
                    "explain_empty zawiodlo dla zapytania %r (model=%s)",
                    query,
                    model_key,
                )
                breakdown = None
```

i dorzuć `breakdown=breakdown` do wywołania `self.get_context_data(...)`:

```python
        context = self.get_context_data(
            form=form,
            results=results_page,
            count=count,
            error=error,
            model_key=model_key,
            query=query,
            breakdown=breakdown,
        )
```

- [ ] **Step 4: Uruchom — GREEN**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py -k breakdown -v 2>&1 | tee /tmp/bpp_b4.log`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/bpp
git add src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
git commit -m "feat(zapytanie): explain_empty — rozbicie 'dlaczego 0 wynikow'

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- src/bpp/views/zapytanie.py src/bpp/tests/test_zapytanie.py
```

### Task B5: szablon — render rozbicia

**Files:**
- Create: `~/Programowanie/bpp/src/bpp/templates/bpp/_zapytanie_breakdown.html`
- Modify: `~/Programowanie/bpp/src/bpp/templates/bpp/zapytanie.html` (linia ~435)
- Test: `~/Programowanie/bpp/src/bpp/tests/test_zapytanie.py`

- [ ] **Step 1: Dopisz test renderu HTML**

```python
@pytest.mark.django_db
def test_zapytanie_breakdown_rendered_in_html(superuser_client):
    baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    response = superuser_client.get(
        reverse(URL),
        {
            "model": "autor",
            "query": 'nazwisko = "Kowalski" and imiona = "asdfo"',
        },
    )
    html = response.content.decode("utf-8")
    assert "Dlaczego 0 wynikow" in html
    assert "asdfo" in html
```

- [ ] **Step 2: Uruchom — RED**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py::test_zapytanie_breakdown_rendered_in_html -v 2>&1 | tee /tmp/bpp_b5.log`
Expected: FAIL — brak „Dlaczego 0 wynikow" w HTML.

- [ ] **Step 3: Utwórz partial `_zapytanie_breakdown.html`**

Treść pliku `src/bpp/templates/bpp/_zapytanie_breakdown.html`:

```django
{# Rekurencyjny widok rozbicia "dlaczego 0 wynikow". #}
{# Oczekuje `node` (dict: text, count, role, children, truncated) i `is_root`. #}
{% if is_root %}
    <div class="callout warning zapytanie-breakdown-box" role="status">
        <h3><span class="fi-info"></span> Dlaczego 0 wynikow?</h3>
        {% if node.truncated %}
            <p><em>Pokazano tylko warunki najwyzszego poziomu (zapytanie zbyt zlozone, aby rozbic w calosci).</em></p>
        {% endif %}
    </div>
{% endif %}
<ul class="zapytanie-breakdown role-{{ node.role }}">
    <li>
        <code>{{ node.text }}</code> &rarr; <strong>{{ node.count }}</strong> trafien
        {% if node.role == "killer_and" %}
            <span class="label alert">tu koncza sie dane: po polaczeniu zostaje 0</span>
        {% elif node.role == "dead_or_branch" %}
            <span class="label secondary">ta galaz OR nic nie wnosi (0 trafien)</span>
        {% endif %}
        {% for child in node.children %}
            {% include "bpp/_zapytanie_breakdown.html" with node=child is_root=False %}
        {% endfor %}
    </li>
</ul>
```

- [ ] **Step 4: Wstaw include w `zapytanie.html` (po „Brak rekordow…")**

Zmień blok (ok. linii 434-436):

```django
            {% else %}
                <p><em>Brak rekordow pasujacych do zapytania.</em></p>
            {% endif %}
```

na:

```django
            {% else %}
                <p><em>Brak rekordow pasujacych do zapytania.</em></p>
                {% if breakdown %}
                    {% include "bpp/_zapytanie_breakdown.html" with node=breakdown is_root=True %}
                {% endif %}
            {% endif %}
```

- [ ] **Step 5: Uruchom — GREEN**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py::test_zapytanie_breakdown_rendered_in_html -v 2>&1 | tee /tmp/bpp_b5.log`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
cd ~/Programowanie/bpp
git add src/bpp/templates/bpp/_zapytanie_breakdown.html src/bpp/templates/bpp/zapytanie.html src/bpp/tests/test_zapytanie.py
git commit -m "feat(zapytanie): szablon rozbicia 'dlaczego 0 wynikow'

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- src/bpp/templates/bpp/_zapytanie_breakdown.html src/bpp/templates/bpp/zapytanie.html src/bpp/tests/test_zapytanie.py
```

### Task B6: przykłady pickerów + news fragment

**Files:**
- Modify: `~/Programowanie/bpp/src/bpp/views/zapytanie.py` (`EXAMPLES`)
- Create: `~/Programowanie/bpp/src/bpp/newsfragments/+zapytanie-autocomplete-rel.feature.rst`

- [ ] **Step 1: Dodaj przykłady pickerów w `EXAMPLES` (forma free-text)**

W `EXAMPLES`, w poziomie 1 (`"level": 1`), do grupy Rekord (`"model": MODEL_REKORD`)
dodaj na końcu listy `items`:
```python
                    ("Po autorze (autocomplete)", 'autorzy.autor__rel = "Kowalski"'),
                    ("Po jednostce (autocomplete)", 'autorzy.jednostka__rel = "Kardiologii"'),
```
a do grupy Autor (`"model": MODEL_AUTOR`) dodaj na końcu listy `items`:
```python
                    ("Po tytule (autocomplete)", 'tytul__rel = "prof."'),
                    ("Po jednostce (autocomplete)", 'aktualna_jednostka__rel = "Kardiologii"'),
```

- [ ] **Step 2: Uruchom testy przykładów — GREEN**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py -k "examples" -v 2>&1 | tee /tmp/bpp_b6.log`
Expected: PASS (przykłady parsowalne; brak unary `not`; oba modele pokryte).

- [ ] **Step 3: Utwórz news fragment**

Plik `src/bpp/newsfragments/+zapytanie-autocomplete-rel.feature.rst`:
```rst
Widok „Szukaj zapytaniem": pola ``<fk>__rel`` z autocomplete (wybór autora,
jednostki, tytułu naukowego z podpowiedzi i filtrowanie po wybranym obiekcie),
obok dotychczasowej składni z kropką. Gdy zapytanie zwróci 0 rekordów, widok
pokazuje teraz rozbicie wyjaśniające, który warunek wyzerował wynik.
```

- [ ] **Step 4: Commit**

```bash
cd ~/Programowanie/bpp
git add src/bpp/views/zapytanie.py src/bpp/newsfragments/+zapytanie-autocomplete-rel.feature.rst
git commit -m "feat(zapytanie): przyklady pickerow __rel + news fragment

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- src/bpp/views/zapytanie.py src/bpp/newsfragments/+zapytanie-autocomplete-rel.feature.rst
```

### Task B7: bump zależności na wydaną wersję djangoql (po release)

**Files:**
- Modify: `~/Programowanie/bpp/pyproject.toml`
- Modify: `~/Programowanie/bpp/uv.lock`

⚠️ Wykonać **po** opublikowaniu djangoql-iplweb 0.23.0 na PyPI (checkpoint po A3).

- [ ] **Step 1: Podnieś minimalną wersję**

W `pyproject.toml` zmień `"djangoql-iplweb>=0.22.0",` na `"djangoql-iplweb>=0.23.0",`
(dostosuj numer, jeśli release dostał inną wersję).

- [ ] **Step 2: Odśwież lock + zdejmij editable**

```bash
cd ~/Programowanie/bpp
uv lock
uv sync --all-extras
```

- [ ] **Step 3: Zweryfikuj, że venv ma wydaną wersję (nie editable)**

Run:
```bash
cd ~/Programowanie/bpp
uv run python -c "import djangoql, os; p=os.path.dirname(djangoql.__file__); print('local-editable' if 'Programowanie/djangoql-iplweb' in p else 'pypi-wheel', getattr(djangoql,'__version__','?'))"
```
Expected: `pypi-wheel 0.23.0` (lub wyższa).

- [ ] **Step 4: Commit**

```bash
cd ~/Programowanie/bpp
git add pyproject.toml uv.lock
git commit -m "build(deps): wymagaj djangoql-iplweb>=0.23.0 (lookup_name dla pickerow __rel)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" -- pyproject.toml uv.lock
```

### Task B8: pełna weryfikacja + push + PR 2

- [ ] **Step 1: Pełny zestaw testów zapytania (GREEN)**

Run: `cd ~/Programowanie/bpp && UV_NO_SYNC=1 uv run --all-extras pytest src/bpp/tests/test_zapytanie.py -n auto -v 2>&1 | tee /tmp/bpp_zapytanie_full.log; grep -E "passed|failed|error" /tmp/bpp_zapytanie_full.log | tail -3`
Expected: wszystkie PASS, 0 failed.

- [ ] **Step 2: pre-commit na zmienionych plikach (bez argumentów)**

Run: `cd ~/Programowanie/bpp && pre-commit run 2>&1 | tee /tmp/bpp_precommit.log`
Expected: Passed/Skipped. Jeśli coś zgłosi — popraw ręcznie Editem (NIE `ruff --fix` batch), commit poprawki.

- [ ] **Step 3: Push gałęzi**

```bash
cd ~/Programowanie/bpp
git push -u origin bpp-zapytanie-autocomplete-rel
```

- [ ] **Step 4: Otwórz PR 2**

```bash
cd ~/Programowanie/bpp
gh pr create --base dev --head bpp-zapytanie-autocomplete-rel \
  --title "feat(zapytanie): pickery __rel (autocomplete) + wyjaśnienie 0 wyników" \
  --body "$(cat <<'EOF'
Widok „Szukaj zapytaniem": pola `<fk>__rel` z autocomplete (autor, jednostka,
tytuł naukowy) obok zachowanej trawersacji z kropką, plus rozbicie
`explain_empty()` gdy zapytanie zwraca 0 rekordów.

Wymaga djangoql-iplweb >= 0.23.0 (kwarg `lookup_name`).

Spec: `docs/superpowers/specs/2026-06-04-zapytanie-autocomplete-rel-i-wyjasnienie-zero-design.md`
Plan: `docs/superpowers/plans/2026-06-04-zapytanie-autocomplete-rel.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

---

## Notatki / ryzyka

- **Rekord to widok zmaterializowany** (`managed=False`). Testy pickerów dla
  Rekord (B1) sprawdzają resolve + SQL (bez realnych wierszy), bo budowanie
  Rekordu wymaga `transactional_db` + `denorms.flush()`. Jeśli zechcesz test
  end-to-end na realnych danych Rekord — użyj fixture'ów `transactional_db`,
  `denorms`, `make_ciagle`, `autor`, `jednostka` (wzorzec z
  `src/bpp/tests/test_cache/test_cache.py`) i `denorms.flush()`.
- **DAL `public-autor-autocomplete`** używa `fulltext_filter` — w testach treść
  wyników bywa niedeterministyczna (tsvector), stąd dla `autorzy.autor__rel`
  test sugestii jest smoke (status + lista), a twardą asercję treści robimy na
  `tytul__rel` (provider queryset, deterministyczny icontains).
- **Picker tylko filtruje po pk** (`= pk`, `!=`, `in`) + fallback free-text
  icontains; operatory na podpolach (`startswith` itp.) zostają na ścieżce z
  kropką (niezmienione).
- **`explain_empty` liczy 1×`count()` na węzeł AST** (guard `max_nodes=50`).
  Dla Rekord to kilka dodatkowych count-ów na ścieżce „dało 0" — akceptowalne.
- **Editable djangoql w fazie B** jest tylko do dev-loopu (B0); commitowana
  zależność to bump wersji w B7. Wszystkie komendy testowe fazy B mają
  `UV_NO_SYNC=1`, żeby `uv run` nie zdjął editable.
- **Komentarze Django** w partialu: każdy `{# … #}` w jednej linii (reguła
  projektu). Ikony: Foundation (`fi-info`) — `zapytanie.html` dziedziczy po
  `base.html`.
