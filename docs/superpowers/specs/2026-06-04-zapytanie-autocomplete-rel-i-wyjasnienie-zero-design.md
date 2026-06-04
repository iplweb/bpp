# Zapytanie DjangoQL: pickery `__rel` (autocomplete) + wyjaśnienie „0 wyników"

Data: 2026-06-04
Status: **Do akceptacji.**

## Problem

Widok „Szukaj zapytaniem" (`/bpp/zapytanie/`, `ZapytanieView`) pozwala pisać
zapytania DjangoQL po modelach `Rekord` i `Autor`. Dwa braki:

1. **Brak wygodnego wyboru obiektu.** Żeby zawęzić do konkretnego autora trzeba
   pisać `autorzy.autor.nazwisko = "Kowalski" and autorzy.autor.imiona = "Jan"`
   — łatwo o literówkę (URL użytkownika z `imiona = "asdfo"` zwraca 0), a
   nazwisko nie jest unikalne. Tak samo jednostka i tytuł naukowy.
2. **Brak informacji „dlaczego 0".** Gdy poprawne składniowo zapytanie zwraca 0
   rekordów, użytkownik nie wie, który warunek wyzerował wynik.

djangoql-iplweb 0.22 dostarcza oba klocki:
- `djangoql.extras.AutocompleteField` + `AutocompleteSchemaMixin` — pole-picker,
  które podpowiada wartości z dowolnego źródła (np. endpoint DAL) i filtruje po
  pk wybranego obiektu (`= pk`, `!=`, `in`), z fallbackiem free-text
  (icontains po `search_fields`).
- `djangoql.breakdown.explain_empty(queryset, search, schema=…, max_nodes=50)` —
  dla zapytania zwracającego 0 wierszy zwraca drzewko
  `{text, count, role, children}` wskazujące „zabójczy" `AND` (`killer_and`) i
  martwe gałęzie `OR` (`dead_or_branch`).

## Decyzja kluczowa (potwierdzona z użytkownikiem)

`AutocompleteField` zamienia FK w **liść-picker** — pod jego nazwą nie da się
już trawersować w podpola. To świadoma decyzja projektowa djangoql-iplweb
(spec `autocomplete-value-fields-design.md:36-37`, doc
`integrating-django-autocomplete-light.md:37-39`): *„Need both → use a second
field name."*

Wybrano **drogę A — dwie nazwy** (zamiast „drogi B": jedna nazwa robi oba —
odrzuconej):

- **Notacja z kropką zostaje domyślna dla każdego FK** (trawersacja bez zmian:
  `autorzy.autor.nazwisko`, `tytul.skrot`, `aktualna_jednostka.nazwa`, … —
  wszystkie obecne przykłady i URL użytkownika działają dalej).
- **`<fk>__rel` = picker** (podwójny underscore — spójnie z rodziną pól
  pochodnych `__count`/`__sum`/`__avg`/`__min`/`__max`; `rel` = „filtruj po
  całym obiekcie powiązanym"). Picker filtruje po pk wybranego rekordu, z
  fallbackiem free-text.

**Aktualizacja zakresu (po dalszej rozmowie):** `<fk>__rel` zostaje
udokumentowane jako **idiom djangoql-iplweb** „relacja z kropką + picker obok",
a do `AutocompleteField` dochodzi malutki, **addytywny** kwarg `lookup_name`
(domyślnie `None` → zachowanie identyczne jak dziś, nie psuje niczego). To NIE
jest odrzucona „droga B" — to tylko ergonomia wzorca dwóch nazw. Dzięki temu
BPP **nie potrzebuje własnej podklasy** — używa `AutocompleteField` wprost z
`lookup_name`. Szczegóły deliverable'u w pakiecie: osobny spec w repo
djangoql-iplweb (`docs/superpowers/specs/2026-06-04-autocomplete-lookup-name-rel-idiom-design.md`).

**Świadomie NIE** opieramy podpowiedzi na distinct-wartościach z bazy
(`StrField.get_options` z `.distinct()`) — przy dużych tabelach (autor,
jednostka) byłoby ich „mega dużo". Picker robi ograniczone zapytanie top-N
(`limit=50`) przez endpoint DAL albo mały queryset.

## Zakres pól

| Model | Trawersacja (zostaje, bez zmian) | Picker (nowy) | Źródło sugestii | `lookup_name` |
|---|---|---|---|---|
| `Rekord` → `Autorzy` | `autorzy.autor.*` | `autorzy.autor__rel` | DAL `bpp:public-autor-autocomplete` | `autor` |
| `Rekord` → `Autorzy` | `autorzy.jednostka.*` | `autorzy.jednostka__rel` | DAL `bpp:jednostka-autocomplete` | `jednostka` |
| `Autor` | `tytul.*` | `tytul__rel` | queryset `Tytul.objects.all()` | `tytul` |
| `Autor` | `aktualna_jednostka.*` | `aktualna_jednostka__rel` | DAL `bpp:jednostka-autocomplete` | `aktualna_jednostka` |

Uwagi:
- **Autor — autocomplete**: używamy `public-autor-autocomplete`
  (`PublicAutorAutocomplete`), nie `autor-autocomplete` (`AutorAutocomplete`).
  Ten drugi wymaga grupy `GR_WPROWADZANIE_DANYCH` (footgun dla superuserów
  spoza grupy, którzy mają dostęp do widoku) i dokleja do etykiet emoji
  📚PBN / 🏛️MNISW oraz opcję „utwórz" — co psułoby format `"Label [id]"`.
  `PublicAutorAutocomplete` zwraca czyste `str(autor)` bez grupy i bez markerów.
- **Tytuł — brak endpointu DAL**, więc picker korzysta z providera `queryset`
  (`Tytul.objects.all()`, `search_fields=['nazwa','skrot']`). Tabela jest
  malutka (~kilkanaście wierszy), więc to bez znaczenia wydajnościowo.
- **Jednostka** — picker w obu kontekstach; endpoint `jednostka-autocomplete`
  (`JednostkaAutocomplete`) nie ma wymogu grupy i zwraca czyste etykiety.
- Autor jako picker **nie** ma sensu w modelu `Autor` (tam pytamy o autorów
  wprost po `nazwisko`/`imiona`), więc go tam nie dodajemy.

## Architektura

### Zależność: djangoql-iplweb z kwargiem `lookup_name`

BPP wymaga wersji djangoql-iplweb z addytywnym kwargiem
`AutocompleteField(lookup_name=…)` (patrz osobny spec w repo pakietu). W trakcie
parallel-devu BPP korzysta z lokalnego editable checkoutu
(`~/Programowanie/djangoql-iplweb/`); docelowo `pyproject.toml` bumpuje minimalną
wersję djangoql-iplweb do tej z `lookup_name`. **Bez tego kwargu** picker pod
nazwą `autor__rel` filtrowałby nieistniejącą kolumnę `autor__rel` zamiast FK
`autor`.

### Schemat (po stronie BPP, w `src/bpp/views/zapytanie.py`)

`<fk>__rel` to nazwa syntetyczna (nie ma jej w modelu), więc filtruje realny FK
przez `lookup_name`. Nie potrzeba podklasy — wystarczy `AutocompleteField`
z kwargiem:

```python
from djangoql.extras import AutocompleteField, ExtrasSchema
from bpp.models import Autor, Tytul
from bpp.models.cache import Autorzy

class BppZapytanieSchema(ExtrasSchema):
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

    # Nazwy syntetyczne nie są realnymi polami modelu, więc muszą być dorzucone
    # do introspekcji, inaczej nie zostaną zbudowane ani podpowiedziane.
    _REL_FIELDS = {
        Autorzy: ["autor__rel", "jednostka__rel"],
        Autor: ["tytul__rel", "aktualna_jednostka__rel"],
    }

    def get_fields(self, model):
        fields = list(super().get_fields(model))
        fields += self._REL_FIELDS.get(model, [])
        return fields
```

Działanie lookupu (`AutocompleteField.get_lookup` / `_free_text_lookup` budują
ścieżkę z `path + [self.get_lookup_name()]`, a `get_lookup_name()` zwraca teraz
`lookup_name`):
- picker po pk: `autorzy.autor__rel = "Jan [42]"` → `autorzy__autor = 42`
  (Django filtruje FK po pk wprost),
- fallback free-text: `autorzy.autor__rel = "kowal"` →
  `autorzy__autor__nazwisko icontains "kowal"` OR `…__imiona icontains …`.

Pozostałe szczegóły schematu:
- `_build_autocomplete_field` robi `AutocompleteField(**config)` z dicta —
  `lookup_name` trafia do kwargów, `name` ustawia mixin na `"autor__rel"`.
- `get_fields` dorzuca syntetyczne nazwy → `introspect()` woła
  `get_field_instance(model, "autor__rel")` → `AutocompleteSchemaMixin`
  znajduje wpis w `autocomplete` i buduje `AutocompleteField`.
- Pole jest „suggested" (domyślnie) i `async_options=True` (brak choices), więc
  serializer wystawia `options: true` i widget pobiera podpowiedzi asynchronicznie
  przez istniejący endpoint — `__rel` jest **odkrywalne** w autocomplete obok
  zwykłej relacji `autor`.
- Schemat jest tworzony per-model (`BppZapytanieSchema(Rekord)` /
  `(Autor)`); `__rel` rejestrują się zawsze, gdy dany model jest introspektowany
  (Autorzy osiągany przez `autorzy`, Autor jako root lub przez `autorzy.autor`).

### 3. Podpięcie schematu w widoku

W `zapytanie.py` zamieniamy bezpośrednie użycia `ExtrasSchema` na
`BppZapytanieSchema` w trzech miejscach:
- `render_results`: `apply_search(queryset, query, schema=BppZapytanieSchema)`,
- `ZapytanieIntrospectView`: `BppZapytanieSchema(model)`,
- `ZapytanieSuggestionsView`: `SuggestionsAPIView.as_view(schema=BppZapytanieSchema(model))`.

### 4. Wyjaśnienie „0 wyników"

W `render_results`, gdy zapytanie jest poprawne i `count == 0`:

```python
from djangoql.breakdown import explain_empty

breakdown = None
if count == 0:
    try:
        breakdown = explain_empty(
            model.objects.all(), query, schema=BppZapytanieSchema
        )
    except (DjangoQLError, FieldError, ValidationError, ValueError):
        logger.exception("explain_empty zawiodło dla zapytania %r", query)
        breakdown = None  # degradacja: pokaż '0 wyników' bez rozbicia
```

- Wołane tylko dla `count == 0` (leniwie). `explain_empty` jest bezpieczne —
  query już przeszło `apply_search`, więc parse/validate się powiedzie; mimo to
  owijamy w try/except (logujemy, nie połykamy po cichu — zgodnie z regułami
  projektu) tak, że błąd rozbicia degraduje do zwykłego „0 wyników".
- `breakdown` trafia do kontekstu i renderuje się w szablonie.
- Koszt: jeden `count()` na węzeł AST (guard `max_nodes=50`). Typowe zapytania
  2–4 warunków = kilka `count()`. `Rekord` to duży widok zmaterializowany, ale
  to akceptowalne dla ścieżki „dało 0, wytłumacz dlaczego".

### 5. Szablon

Nowy partial `src/bpp/templates/bpp/_zapytanie_breakdown.html` renderowany pod
komunikatem „0 wyników" w `zapytanie.html` (rozszerza `base.html` → ikony
**Foundation Icons**, nie emoji). Rekurencyjnie pokazuje drzewko:
- każdy liść: `tekst warunku → N trafień`,
- `killer_and`: podświetlony („tu kończą się dane: po połączeniu warunków
  zostaje 0"),
- `dead_or_branch`: oznaczony („ta gałąź OR nic nie wnosi — 0 trafień"),
- `truncated` na korzeniu: dopisek, że rozbito tylko górne warunki (bez cichego
  ucinania).
- Mapowanie `role` → polskie etykiety po stronie szablonu/widoku.
- Komentarze Django wyłącznie jedno-liniowe `{# … #}` (reguła projektu) lub
  `{% comment %}`.

### 6. Przykłady (`EXAMPLES`)

Wszystkie obecne przykłady **zostają** (trawersacja działa). Dodajemy kilka z
pickerami. **Decyzja: przykłady używają formy free-text (bez sztucznego
`[id]`)** — jest poprawna składniowo, „kopiowalna", a realne `[id]` użytkownik
i tak dostaje z autocomplete (sztuczne `[1]` w przykładzie mogłoby trafić w
nieistniejący pk):
- Rekord: `autorzy.autor__rel = "Kowalski"`,
  `autorzy.jednostka__rel = "II WL" and rok >= 2022`,
- Autor: `tytul__rel = "prof."`,
  `aktualna_jednostka__rel = "Katedra" and orcid != ""`.

Każdy nowy przykład przejdzie `test_zapytanie_examples_are_valid_djangoql`
(walidacja składni `DjangoQLParser`, nie wykonania) oraz
`test_zapytanie_examples_no_unary_not`.

## Pliki do zmiany

### W repo djangoql-iplweb (osobny spec + TDD — patrz repo pakietu)

- `djangoql/extras.py` — addytywny kwarg `lookup_name` na `AutocompleteField`
  (+ `get_lookup_name()` → `self._lookup_name or self.name`).
- `docs/integrating-django-autocomplete-light.md` — nowa sekcja: idiom
  „relacja z kropką + picker `<fk>__rel` obok".
- `test_project/…`, `CHANGES.rst` — test kwargu + wpis (additive, non-breaking).
- release + wersja, do której BPP bumpuje minimalną zależność.

### W repo bpp

- `src/bpp/views/zapytanie.py` — `BppZapytanieSchema(ExtrasSchema)` (z mapą
  `autocomplete` + `get_fields`), podpięcie `explain_empty`, użycie schematu w
  3 miejscach (`render_results`, `ZapytanieIntrospectView`,
  `ZapytanieSuggestionsView`), nowe przykłady, `import logging` + `logger`.
- `src/bpp/templates/bpp/zapytanie.html` — sekcja „dlaczego 0" (include
  partiala) w gałęzi `count == 0`.
- `src/bpp/templates/bpp/_zapytanie_breakdown.html` — nowy partial (rekurencyjny).
- `pyproject.toml` — bump minimalnej wersji `djangoql-iplweb` do tej z
  `lookup_name`.
- `src/bpp/tests/test_zapytanie.py` — nowe testy.
- `src/bpp/newsfragments/+zapytanie-autocomplete-rel.feature.rst` — news fragment.

## Plan testów (pytest, model_bakery, `@pytest.mark.django_db`)

Pickery:
- `autorzy.autor__rel = "X [<pk>]"` filtruje `autorzy__autor = pk` (Rekord ma
  autora o tym pk → trafia; inny pk → 0).
- free-text fallback: `autorzy.autor__rel = "kowal"` → icontains po
  `autorzy__autor__nazwisko`/`imiona`.
- `tytul__rel = "prof. [<pk>]"` → `tytul_id = pk`; `aktualna_jednostka__rel`
  analogicznie.
- introspekcja/serializacja: schemat dla Rekord i Autor zawiera `*__rel` jako
  pola z `options: true`; trawersacja (`autorzy.autor.nazwisko`, `tytul.skrot`)
  **nadal** działa (regresja — kluczowe: nie wyłączyliśmy kropki).
- endpoint sugestii: `ZapytanieSuggestionsView` dla
  `field=autorzy.autor__rel&search=…` zwraca itemy `"… [id]"` (provider DAL
  wołany in-process z bieżącym requestem).

Wyjaśnienie „0":
- AND dwóch warunków, drugi daje 0 → `explain_empty` zwraca drzewo z
  `killer_and` i liściem `count == 0` (odtworzenie scenariusza z URL użytkownika:
  `nazwisko = "Kowalski"` → N, `imiona = "asdfo"` → 0).
- zapytanie z trafieniami → `count > 0` → brak rozbicia (None), brak sekcji.
- widok: GET z zapytaniem zwracającym 0 renderuje sekcję „dlaczego 0";
  z wynikami — nie renderuje.
- degradacja: gdy `explain_empty` rzuci (zamockowane) → strona renderuje „0
  wyników" bez rozbicia, log zawiera wpis (nie 500).

## Poza zakresem

- Zmiany w pakiecie djangoql-iplweb (to byłaby droga B: jedna nazwa robi oba —
  odrzucona na rzecz drogi A).
- Zmiany w completion-widgecie (JS) — feature jest w 100% server-side.
- Picker dla innych FK (charakter_formalny, zrodlo, wydawca, jezyk itd.) — można
  dodać później tym samym wzorcem, jeśli zajdzie potrzeba.
- Głęboka paginacja sugestii (djangoql v1 zwraca jedną stronę top-N).
