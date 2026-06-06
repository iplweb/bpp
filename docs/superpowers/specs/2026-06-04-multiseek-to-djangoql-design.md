# Konwerter „formularz Multiseek → zapytanie DjangoQL”

Data: 2026-06-04
Status: design (zatwierdzony do napisania planu)

## Cel

Na stronie formularza Multiseek dodać przycisk, który dla uprawnionego,
zalogowanego użytkownika tłumaczy aktualnie zbudowany formularz wyszukiwania
na równoważne zapytanie DjangoQL nad modelem `Rekord`. Wynik pokazujemy w
szufladzie (drawer) z polem do skopiowania kodu oraz przyciskiem
„Otwórz w edytorze zapytań”, który przenosi do istniejącego edytora
`/zapytanie/?model=rekord&query=...`.

Motywacja: Multiseek i edytor DjangoQL (`bpp.views.zapytanie.ZapytanieView`)
przeszukują **dokładnie ten sam model** — `bpp.models.cache.Rekord`. Konwerter
pozwala płynnie przejść od formularza (łatwy start) do edytora zapytań (pełna
moc i ręczne dostrojenie).

## Kluczowe ustalenia (z analizy kodu)

- **Multiseek registry**: `src/bpp/multiseek_registry/` — `create_registry(Rekord, ...)`.
  Każde pole to klasa `QueryObject` z metodą
  `real_query(self, value, operation) -> django.db.models.Q`
  (baza: `multiseek/logic.py`; `query_for` = `real_query(value_from_web(value), op)`).
- **Struktura zapytania Multiseek**: JSON budowany na froncie przez `formAsJSON()`
  (`templates/multiseek/index.html`), POST-owany jako parametr `json`. Kształt:
  ```json
  {
    "form_data": [null, {"field": "...", "operator": "...", "value": ..., "prev_op": null}, ...],
    "ordering": {...},
    "report_type": "0"
  }
  ```
  Ramki mogą być zagnieżdżone (lista zaczynająca się od operatora `and`/`or`/`andnot`).
  Rekurencyjne łączenie warunków: `multiseek/logic.py::get_query_recursive`.
- **Edytor DjangoQL**: `src/bpp/views/zapytanie.py::ZapytanieView`, URL `/zapytanie/`,
  parametry `?model=rekord&query=<djangoql>`. Dostęp: zalogowany **oraz**
  (superuser **lub** (`is_staff` i grupa „wprowadzanie danych”)).
- **Schemat DjangoQL**: `src/bpp/djangoql_schema.py::BppQLSchema`
  (`RelPickerSchemaMixin` + `ExtrasSchema`). Auto-pickery `<fk>__rel`
  (`AutocompleteField` z `lookup_name`) — filtrują po pk wybranego obiektu,
  format wartości: `"Etykieta [pk]"`. Punkt rozszerzeń pola:
  `DjangoQLField.get_lookup(path, operator, value) -> Q` i `get_operator()`.
- **Operatory DjangoQL są stałe** (gramatyka w `djangoql/lexer.py` + `parsetab.py`
  oraz kopia w JS widgetu). **Nie** dodajemy nowych tokenów-operatorów.
  Rozszerzamy zamiast tego pola (`get_lookup`) — tak jak już robią `__rel`.
- **Hierarchia jednostek**: `Jednostka` jest `MPTTModel`
  (`src/bpp/models/jednostka.py`, `parent = TreeForeignKey("self", ...)`).
  „+ podrzędne” w Multiseek to:
  ```python
  # JednostkaQueryObject.real_query, EQUAL_PLUS_SUB_FEMALE:
  Q(autorzy__jednostka__in=value.get_family())
  ```
  `get_family()` (MPTT) = przodkowie + sam węzeł + potomkowie.

## Architektura

### 1. Silnik konwersji (server-side, Python)

Nowy moduł `src/bpp/multiseek_registry/djangoql_export.py`.

Funkcja czysta:
```python
def multiseek_form_to_djangoql(form_json: dict, registry) -> ConversionResult
```
zwracająca `ConversionResult(query: str, warnings: list[str])`.

Działanie:
- Parsuje `form_data` rekurencyjnie, **odzwierciedlając strukturę ramek**
  `get_query_recursive`: liście łączone fragmentami DjangoQL spojonymi
  `and` / `or`; zagnieżdżone ramki w nawiasach.
- `prev_op`:
  - `and` → `and`
  - `or` → `or`
  - `andnot` → negację wpychamy do **pojedynczej** liścia (De Morgan: zamiana
    operatora na zaprzeczony — `=`→`!=`, `~`→`!~`, `in`→`not in`, itd.).
    Dla zaprzeczonej **ramki** (grupy) — brak odpowiednika w DjangoQL →
    warning, warunek pomijany.
- Dla każdego liścia: odnajduje `QueryObject` po `label` (registry mapuje
  label→obiekt) i prosi o fragment DjangoQL (patrz §2). `None` → warning
  „pominięto warunek X (nieprzekładalny)”.
- Buduje `editor_url = /zapytanie/?model=rekord&query=<urlencoded>`.

`ordering` i `report_type` nie są filtrami — pomijane (DjangoQL nie ma
składni sortowania). Nie generujemy z tego warningów (to nie jest „utrata
warunku”).

### 2. Tłumaczenie per-pole — każdy QueryObject zna swoje mapowanie

Mixin `MultiseekDjangoQLMixin` z metodą:
```python
def to_djangoql(self, value, operation) -> str | None
```
Domyślna implementacja (w mixinie) obsługuje typowe przypadki na podstawie
`field_name`, `type` (`STRING`/`INTEGER`/`DECIMAL`/`DATE`/`VALUE_LIST`/
`AUTOCOMPLETE`) i `operation`:
- string/int/decimal/date → `field_name <op> <wartość>`; mapowanie operatorów
  Multiseek → DjangoQL (`CONTAINS`→`~`, `NOT_CONTAINS`→`!~`, `STARTS_WITH`→
  `startswith`, `GREATER`→`>`, `GREATER_OR_EQUAL`→`>=`, równość/płcie→`=`,
  różność/płcie→`!=`, `IN_RANGE`→ rozbicie na `>=` … `and` … `<=`).
- AUTOCOMPLETE → `value` to pk; resolwujemy pk→obiekt (przez `model`/
  `value_from_web`), etykieta przez to samo pole co picker, emitujemy
  `field_name__rel = "Etykieta [pk]"`. (Jeśli `field_name` celuje w ścieżkę
  relacyjną, używamy odpowiedniego `__rel` na tej ścieżce, np.
  `autorzy.jednostka__rel`.)
- VALUE_LIST → `field_name = <wartość>` (lub mapowanie etykieta→wartość pola).
- Operacje/pola bez sensownego odpowiednika → `None`.

Tylko „trudne” pola nadpisują `to_djangoql` (np. `JednostkaQueryObject`,
pola autorów na ścieżce odwrotnej `autorzy.…`). Celem jest, by większość pól
działała z domyślnej logiki bez kodu per-klasa.

### 3. Pole-gwiazda: `jednostka_z_podjednostkami__rel` w `BppQLSchema`

W `src/bpp/djangoql_schema.py` rejestrujemy na modelu `Rekord` wirtualne
pole (dedykowana podklasa `AutocompleteField`), którego `get_lookup` zwraca:
```python
Q(autorzy__jednostka__in=value.get_family())
```
— co do joty Q z Multiseek `EQUAL_PLUS_SUB_FEMALE`. Picker (autocomplete po
`Jednostka`, format `"Nazwa [pk]"`), operator dla użytkownika to zwykłe `=`.

Mapowanie w `JednostkaQueryObject.to_djangoql`:
- `EQUAL_FEMALE` → `autorzy.jednostka__rel = "Nazwa [pk]"`
- `DIFFERENT_FEMALE` → `autorzy.jednostka__rel != "Nazwa [pk]"`
- `EQUAL_PLUS_SUB_FEMALE` → `jednostka_z_podjednostkami__rel = "Nazwa [pk]"`
- `UNION_FEMALE` / `EQUAL_PLUS_SUB_UNION_FEMALE` → albo dodatkowe wirtualne
  pole o analogicznej semantyce (`pk__in=Autorzy.filter(...).values("rekord_id")`),
  albo — jeśli zbiór wyników jest identyczny — to samo pole; do rozstrzygnięcia
  w planie na podstawie testu równoważności zbiorów. Gdy semantyka różni się
  realnie, a nie chcemy mnożyć pól → warning.

Korzyść poboczna: nowe pole(a) są od razu używalne w samym edytorze
`/zapytanie/` i w wyszukiwarce DjangoQL adminów — ten sam kod podnosi jakość
edytora, nie tylko konwertera.

### 4. Endpoint + UI (tylko strona formularza)

- **Uprawnienia, współdzielone**: wyciągamy regułę dostępu z `ZapytanieView`
  do wspólnego predykatu (np. `bpp.views.zapytanie.user_can_use_query_editor(user)`
  albo test do `UserPassesTestMixin`), używanego przez: (a) `ZapytanieView`,
  (b) nowy endpoint, (c) warunek renderowania przycisku w szablonie.
- **Endpoint** `POST /multiseek/do-djangoql/` (`login_required` + ten predykat).
  Wejście: ten sam payload `json` co `formAsJSON()`. Wyjście JSON:
  `{"query": str, "warnings": [str], "editor_url": str}`.
- **Szablon** `templates/multiseek/index.html`: przycisk przy istniejących
  akcjach (renderowany **tylko** dla użytkownika przechodzącego predykat).
  Klik → `formAsJSON()` → `fetch` POST → otwarcie szuflady Foundation
  (reveal/off-canvas) z:
  - polem (textarea/`<pre>`) z zapytaniem + przyciskiem „Kopiuj”
    (reużycie istniejącej logiki schowka z `multiseek/common-results.html`),
  - listą ostrzeżeń (jeśli są),
  - linkiem „Otwórz w edytorze zapytań” → `editor_url`.

Decyzja (zatwierdzona): przycisk renderowany wyłącznie dla użytkowników
spełniających regułę dostępu do edytora (superuser lub `is_staff` + grupa
„wprowadzanie danych”). Output jest „akcjonowalny” tylko dla nich.

## Przepływ danych

```
[formularz Multiseek]
   │ formAsJSON()            (istniejący JS)
   ▼
POST /multiseek/do-djangoql/  (json=<form_data...>)
   │ user_can_use_query_editor?  → 403 jeśli nie
   ▼
multiseek_form_to_djangoql(form_json, registry)
   │ walk ramek → QueryObject.to_djangoql(value, op) → fragmenty
   ▼
{query, warnings, editor_url}
   │
   ▼
[drawer]  ── „Kopiuj”
          └─ „Otwórz w edytorze zapytań” → /zapytanie/?model=rekord&query=...
```

## Obsługa błędów / przypadki brzegowe

- Pole nierozpoznane / operacja nieobsługiwana → warning, warunek pomijany;
  pozostałe warunki nadal tłumaczone (best-effort).
- `andnot` na ramce → warning (brak `not(expr)` w DjangoQL).
- Pusty formularz → `query == ""`, brak warningów; przycisk „Otwórz w
  edytorze” prowadzi do pustego edytora.
- AUTOCOMPLETE z `value` wskazującym nieistniejący/niewidoczny obiekt →
  warning (nie wstawiamy „martwego” pk).
- Endpoint waliduje JSON; błędny payload → 400 z komunikatem (nie cichy fail).

## Plan testów (pytest + model_bakery)

- **Per-pole**: dla reprezentatywnych `QueryObject` (string, int, decimal,
  date, value-list, autocomplete) — `to_djangoql(value, op)` zwraca oczekiwany
  fragment; warianty płciowe operatorów kolapsują do `=`/`!=`.
- **Ramki**: `and`/`or`, zagnieżdżenie, `andnot` na liściu (inwersja operatora),
  `andnot` na ramce (warning).
- **Pole `jednostka_z_podjednostkami__rel`**: `get_lookup` zwraca Q równe
  `Q(autorzy__jednostka__in=value.get_family())`; wynik zapytania na zbiorze
  baked == wynik Multiseek `EQUAL_PLUS_SUB_FEMALE`.
- **Round-trip fidelity** (najważniejszy): dla zapytań w pełni przekładalnych —
  uruchom `Q` z Multiseek **oraz** skonwertowane DjangoQL na zbiorze baked i
  asercja, że wybierają **identyczny** zbiór `Rekord`.
- **Warningi**: pola z genuine-residue (np. `ZewnetrznaBazaDanychQueryObject`,
  oparte o widok SQL) → warning, brak crasha.
- **Endpoint**: gating uprawnień (403 dla nieuprawnionego, 200 dla uprawnionego),
  happy-path zwraca `{query, warnings, editor_url}`, błędny JSON → 400.

## Poza zakresem (YAGNI)

- Tłumaczenie `ordering` / `report_type` (DjangoQL nie sortuje).
- Konwersja w drugą stronę (DjangoQL → Multiseek).
- Konwersja po stronie JS (cała logika i resolucja pk→etykieta jest serwerowa).
- Przycisk na stronie wyników (`common-results.html`) — tylko formularz.

## Pliki (orientacyjnie)

- Nowy: `src/bpp/multiseek_registry/djangoql_export.py` (silnik + mixin).
- Zmiana: `src/bpp/djangoql_schema.py` (pole `jednostka_z_podjednostkami__rel`).
- Zmiana: `src/bpp/multiseek_registry/fields/unit_fields.py` (+ ew. inne pola
  z nadpisanym `to_djangoql`).
- Zmiana: `src/bpp/views/zapytanie.py` (wyłuskanie predykatu uprawnień).
- Nowy: widok endpointu (np. `src/bpp/views/mymultiseek.py` lub nowy moduł) + URL.
- Zmiana: `templates/multiseek/index.html` (przycisk + drawer + JS).
- Nowe testy: `src/bpp/tests/` (per-pole, ramki, pole MPTT, round-trip, endpoint).
