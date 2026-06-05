# Maksymalizacja przekładalności Multiseek → DjangoQL

Data: 2026-06-05
Branch: `feature/multiseek-to-djangoql`
Status: zaakceptowany (design)

## Cel

Konwerter „formularz Multiseek → DjangoQL" (już istniejący) zostawia zbyt
wiele *rodzajów* pól jako **nieprzekładalne**. Zadanie: doprowadzić do
sytuacji, w której jak najmniej rodzajów pól jest nieprzekładalnych, bo
większość z nich ma czysty odpowiednik w DjangoQL nad `Rekord`.

Dyrektywy użytkownika:

1. **Brak wartości → `""` / `None`**, nie „nieprzekładalny". Puste pole
   tekstowe/value-list emituje literał `""`; pusty autocomplete (FK bez
   wybranego obiektu) emituje `<ścieżka>__rel = None` (is-null).
2. **VALUE_LIST to lista stringów** → tłumaczymy na **porównanie stringa**
   (`<ścieżka>.nazwa = "wartość"`), a nie na resolucję pk/`__rel`.
3. **AUTOCOMPLETE → `<ścieżka>__rel`** (utrwalony wzorzec) wskazujący na
   właściwą relację.

## Kluczowa obserwacja: `field_name` ≠ ścieżka ORM

Atrybut `field_name` w wielu QueryObjectach **nie** jest ścieżką ORM —
prawdziwa ścieżka żyje w `real_query`. Przykłady:

- `WydzialQueryObject.field_name = "wydzial"`, a `real_query` filtruje
  `autorzy__jednostka__wydzial`.
- `Typ_OdpowiedzialnosciQueryObject.field_name = "typ_odpowiedzialnosci"`,
  ścieżka realna: `autorzy__typ_odpowiedzialnosci`.
- `DyscyplinaQueryObject.field_name = "nazwa"` (!), ścieżka realna:
  `autorzy__dyscyplina_naukowa`.

Dlatego pola te lądują dziś jako „nieprzekładalne": domyślny leaf emituje
`wydzial__rel`, co nie waliduje się względem schematu `Rekord`. Naprawa
wymaga, by pole **deklarowało** swoją realną ścieżkę DjangoQL.

## A. Dwie nowe mechaniki w silniku konwertera

Plik: `src/bpp/multiseek_registry/djangoql_export.py`.

### A1. Deklaratywny override ścieżki — `djangoql_field_name`

`_default_leaf` preferuje opcjonalny atrybut klasy `djangoql_field_name`
(realna ścieżka ORM, np. `"autorzy__jednostka__wydzial"`), z fallbackiem na
`field_name`. Reszta bez zmian (`__` → `.`). Naprawia każde pole, którego
`field_name` ≠ ścieżka ORM, **bez** pisania metody.

```python
def _djangoql_path(field):
    name = getattr(field, "djangoql_field_name", None) or getattr(
        field, "field_name", None
    )
    return _orm_path_to_djangoql(name) if name else None
```

### A2. Gałąź VALUE_LIST w `_default_leaf`

Gdy `field.type == VALUE_LIST`: emituj porównanie stringa na polu-nazwie:
`<ścieżka>.<value_field> <op> "<wartość>"`. Domyślnie `value_field =
"nazwa"`, nadpisywalne atrybutem `djangoql_value_field`. Mapowanie
operatorów reużywa istniejącej skalarnej mapy (`EQUAL`→`=`, `DIFFERENT`→
`!=`, `UNION*`→`=`).

```python
VALUE_LIST  # z multiseek.logic
# w _default_leaf, przed gałęzią skalarną:
if getattr(field, "type", None) == VALUE_LIST:
    return _value_list_leaf(field, value, operation)
```

`_value_list_leaf`:

- pusta wartość → `<ścieżka>.<value_field> = ""`,
- operator skalarny z mapy (EQUAL/DIFFERENT/UNION),
- zwraca `f'{path}.{value_field} {op} {render_value(value)}'`.

### A3. Pusty autocomplete

`_autocomplete_leaf`: gdy `value` jest puste/None (brak wybranego obiektu)
→ zwróć `f"{rel_path} = None"` (lub `!= None` dla operatorów różności)
zamiast `None` (nieprzekładalne). Niepuste — bez zmian.

## B. Plan per-pole

### B1 — Deklaratywny `djangoql_field_name`, AUTOCOMPLETE → `__rel`

| Pole | DjangoQL |
|---|---|
| `WydzialQueryObject` | `autorzy.jednostka.wydzial__rel` |
| `AktualnaJednostkaAutoraQueryObject` | `autorzy.autor.aktualna_jednostka__rel` |
| `DyscyplinaQueryObject` | `autorzy.dyscyplina_naukowa__rel` |
| `KierunekStudiowQueryObject` | `autorzy.kierunek_studiow__rel` |

`PierwszaJednostka`/`PierwszyWydzial` (kolejnosc=0) — patrz F (lossy).

### B2 — Deklaratywny VALUE_LIST → `<ścieżka>.nazwa = "wartość"`

| Pole | DjangoQL |
|---|---|
| `JezykQueryObject` | `jezyk.nazwa = "..."` |
| `TypKBNQueryObject` | `typ_kbn.nazwa = "..."` |
| `OpenaccessWersjaTekstuQueryObject` | `openaccess_wersja_tekstu.nazwa = "..."` |
| `OpenaccessLicencjaQueryObject` | `openaccess_licencja.nazwa = "..."` |
| `OpenaccessCzasPublikacjiQueryObject` | `openaccess_czas_publikacji.nazwa = "..."` |
| `Typ_OdpowiedzialnosciQueryObject` | `autorzy.typ_odpowiedzialnosci.nazwa = "..."` |

`CharakterFormalnyQueryObject` **nie** jest czysto deklaratywne (patrz B3):
wartość niesie prefiks wcięcia MPTT (`DEFAULT_LEVEL_INDICATOR = "---"`);
`value_from_web` robi `value.lstrip("-").lstrip(" ")`. Realizacja: albo
metoda `to_djangoql` (normalizuje wartość, potem `charakter_formalny.nazwa =
"<znormalizowana>"`), albo deklaratywny hak `djangoql_value_transform`
(callable wartość→wartość) konsumowany przez `_value_list_leaf`. Wybór:
**`to_djangoql`** (mniej nowych mechanik, semantyka MPTT-descendants i tak
wymaga warninga z F).

### B3 — `to_djangoql` (semantyka niestandardowa)

| Pole | DjangoQL |
|---|---|
| `CharakterOgolnyQueryObject` | `charakter_formalny.charakter_ogolny = "<const>"` |
| `TypRekorduObject` | `charakter_formalny.publikacja = True` / `.streszczenie = True` / `(.publikacja = False and .streszczenie = False)` |
| `RodzajKonferenckjiQueryObject` | `konferencja.typ_konferencji = <N>` |
| `RodzajJednostkiQueryObject` | `autorzy.jednostka.rodzaj_jednostki = <N>` |
| `TypOgolnyAutorQueryObject` i podklasy | `autorzy.autor__rel = "L [pk]" and autorzy.typ_odpowiedzialnosci.typ_ogolny = <N>` |
| `CharakterFormalnyQueryObject` | `charakter_formalny.nazwa = "<bez prefiksu --->"` (+ warning gdy ma potomków, F) |
| `ObcaJednostkaQueryObject` | `autorzy.jednostka.skupia_pracownikow = <not value>` |
| `AfiliujeQueryObject` | `autorzy.afiliuje = <bool>` |
| `OswiadczenieKENQueryObject` | `autorzy.oswiadczenie_ken = <bool>` |
| `DyscyplinaUstawionaQueryObject` | `autorzy.dyscyplina_naukowa != None` (lub `= None`) |
| `LicencjaOpenAccessUstawionaQueryObject` | `openaccess_licencja != None` (lub `= None`) |
| `PublicDostepDniaQueryObject` | `public_dostep_dnia != None` (lub `= None`) |
| `StronaWWWUstawionaQueryObject` | `(www != "" or public_www != "")` (lub negacja) |

Wartości `<const>`/`<N>` brać z definicji klasy (`bpp.const`,
`Konferencja.TK_*`, `Jednostka.RODZAJ_JEDNOSTKI`, `charakter_ogolny`).

### B4 — Już działają (bez zmian)

Bezpośrednie pola skalarne (`tytul_oryginalny`, liczby, `rok`, daty,
zakresy), bezpośrednie FK-autocomplete (`zrodlo`, `wydawnictwo_nadrzedne`,
`status_korekty`, `konferencja`), bazowe `NazwiskoIImieQueryObject` i
`JednostkaQueryObject` (mają już `to_djangoql`), proste booleany
(`recenzowana`, `konferencja__baza_wos/scopus`), `ORCIDQueryObject`
(`autorzy.autor.orcid`).

## C. Pusta wartość — reguła „'' / None"

- string / value-list → literał: `tytul_oryginalny ~ ""`, `jezyk.nazwa = ""`.
- autocomplete bez obiektu → `<ścieżka>__rel = None` (is-null);
  dla operatorów różności → `!= None`.

## D. Siatka bezpieczeństwa

Każdy fragment nadal przechodzi przez `is_valid_rekord_djangoql` względem
`BppQLSchema(Rekord)`. Jeśli zadeklarowana ścieżka nie jest wystawiona przez
schemat, fragment auto-degraduje do warninga — best-effort nie może
wyprodukować niepoprawnego DjangoQL. **Implikacja:** testy round-trip muszą
potwierdzić, że zamierzone ścieżki faktycznie się walidują (inaczej cicho
staną się warningami i cel nie zostanie osiągnięty).

## E. Pozostałe szczere warningi (powinno być mało)

- `SlowaKluczoweQueryObject`, `ZewnetrznaBazaDanychQueryObject` — match
  przez dedykowane widoki SQL (`pk__in` subquery). Próbujemy
  `slowa_kluczowe…` / relacji do zewn. bazy, jeśli schemat ją wystawia;
  inaczej warning.
- `NOT_IN_RANGE` i zanegowane *grupy* — DjangoQL nie ma `not(...)`
  (bez zmian, warning).

## F. Best-effort + warning (pola stratne)

Tłumaczone przybliżenie + **warning** wyjaśniający rozbieżność:

- **UNION** (`równy+wspólny` itd.) → identycznie jak EQUAL; gubiona jest
  dystynkcja „inny wiersz autora" (ograniczenie gramatyki DjangoQL).
- **CharakterFormalny descendants** (MPTT) → tylko dokładny węzeł, bez
  poddrzewa. Warning gdy węzeł ma potomków.
- **kolejnosc-ranged autorzy** (`Pierwsze/Ostatnie nazwisko i imię`,
  `Pierwsza jednostka/wydział`) → `kolejnosc` jest per-wiersz; best-effort
  pomija je, z warningiem.

## G. Podgląd w szufladzie: formatowanie + podświetlanie składni

Dyrektywa: zapytanie DjangoQL pokazywane userowi ma być **sformatowane**
i **podświetlone składniowo**; oba mechanizmy bierzemy z DjangoQL.

### Co naprawdę daje DjangoQL

`completion.js` to widget autouzupełniania (lexuje zapytanie, podpowiada
pola/operatory), ale **nie koloruje** textarea. Reużywalny jest natomiast
**lexer**: zainicjowana instancja niesie `.lexer`, a
`dql.lexer.setInput(q).lexAll()` zwraca tokeny z `.name`/`.value`/`.start`/
`.end` (`NAME`, `DOT`, `AND`, `OR`, `NOT`, `IN`, `EQUALS`, `NOT_EQUALS`,
`CONTAINS`, `STRING_VALUE`, `INT_VALUE`, `FLOAT_VALUE`, `TRUE`/`FALSE`/
`NONE`, `PAREN_L`/`PAREN_R`, …). To jest „podświetlanie składni dostępne
w DjangoQL" — kolorujemy po `token.name`.

### Newline'e

Lexer **Pythona** ignoruje newline'e (`t_newline` je odrzuca) → wieloliniowe,
sformatowane zapytanie parsuje się tak samo i działa w edytorze oraz w
`is_valid_rekord_djangoql`. Lexer **JS** w regule whitespace NIE ma `\n`,
więc formatowania NIE robimy przez wstrzykiwanie newline'ów do lexera —
lexujemy **jednoliniowe** zapytanie, a łamanie linii i wcięcia nakładamy
na etapie renderu (po granicach tokenów).

### Mechanika (klient)

Nowy moduł `src/bpp/static/bpp/js/djangoql-pretty.js`:
`formatAndHighlight(query, lexer) -> htmlString`:

1. `tokens = lexer.setInput(query).lexAll()` (wejście jednoliniowe).
2. Render do HTML: każdy token w `<span class="dql-<kategoria>">`
   (kategorie: `keyword` and/or/not/in, `op`, `name`, `dot`, `str`, `num`,
   `bool`, `none`, `paren`). Wartości HTML-escapowane.
3. Formatowanie po granicach tokenów: licz głębokość nawiasów; przed
   top-level `and`/`or` wstaw `\n` + wcięcie wg głębokości; zawartość grup
   `( … )` wcinaj o poziom.

Lexer pozyskujemy z instancji DjangoQL zainicjowanej na ukrytej/roboczej
textarea z istniejącym endpointem introspekcji `rekord`
(`bpp:zapytanie_introspect 'rekord'`) — ten sam, którego używa edytor.

### Szuflada (UI)

- Wyświetlanie: `<pre class="djangoql-pretty"><code id="djangoqlPretty">`
  z wstawionym HTML-em (zamiast czystej `readonly` textarea).
- Surowe (jednoliniowe) zapytanie trzymamy w ukrytym polu / zmiennej JS
  na potrzeby „Kopiuj" i linku „Otwórz w edytorze".
- „Kopiuj": kopiuje wersję **sformatowaną** (wieloliniową) — parsuje się
  poprawnie po stronie serwera.
- „Otwórz w edytorze": przekazuje zapytanie (sformatowane jest OK; serwer
  ignoruje newline'y).
- Skrypty (`completion.js` + `djangoql-pretty.js`) ładowane **tylko** gdy
  przycisk jest renderowany (user przechodzi gate edytora) — bez zmian w
  bramce uprawnień.
- CSS: klasy `.dql-*` w SCSS/inline; kolory spójne z motywem (frontend
  Foundation — monochrom + akcenty, bez nadpisywania siatki Foundation).

### Test

- JS jednostkowo nie jest tu wymagane (brak harnessu JS w repo); pokrycie
  przez Playwright: po kliknięciu przycisku szuflada pokazuje
  podświetlony, wieloliniowy `<pre>` (sprawdzenie obecności `span.dql-*`
  i newline'ów), a „Otwórz w edytorze" niesie poprawny `href`.

## Testowanie (TDD)

- Testy jednostkowe per grupa pól: asercja na dokładny output
  `to_djangoql`/deklaratywny.
- Testy round-trip: porównanie zbioru pk `Rekord` z multiseekowego `Q`
  vs ze skonwertowanego DjangoQL na zbakowanych danych — tam, gdzie
  semantyka jest dokładna (B1/B2/większość B3).
- Testy warningów: pola z F dają fragment **oraz** warning; pola z E dają
  warning bez fragmentu (lub fragment, jeśli schemat wspiera ścieżkę).
- Test reguły pustej wartości (C).

## Pliki

- `src/bpp/multiseek_registry/djangoql_export.py` — A1/A2/A3.
- `src/bpp/multiseek_registry/fields/*.py` — atrybuty deklaratywne (B1/B2)
  i metody `to_djangoql` (B3/F) per pole.
- `src/bpp/static/bpp/js/djangoql-pretty.js` — formatter + highlighter (G).
- `src/django_bpp/templates/multiseek/index.html` — szuflada: `<pre>`
  podglądu, ładowanie skryptów, integracja kopiowania/edytora (G).
- SCSS/CSS: klasy `.dql-*` (G).
- Testy: `src/bpp/tests/test_multiseek_djangoql_*.py` (rozbudowa) +
  Playwright na podgląd szuflady (G).
