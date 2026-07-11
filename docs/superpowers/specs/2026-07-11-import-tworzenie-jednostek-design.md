# Tworzenie brakujących jednostek podczas importu pracowników

Data: 2026-07-11
Status: zaakceptowany (design), do implementacji
Gałąź: `feat/import-pracownikow-tworzenie-jednostek`

## 1. Problem i kontekst

Faza analizy importu pracowników (`import_pracownikow.pipeline.analyze`) matchuje
jednostkę każdego wiersza przez `matchuj_jednostke`. Gdy jednostki nie ma w bazie,
`_matchuj_jednostke_lub_wyjatek` **rzuca** `XLSMatchError`, który propaguje przez
`_przetworz_wiersz` → `analizuj` → `LiveOperation.run` → runner liveops. Efekt:
cała operacja pada na pierwszym niedopasowanym wierszu (`stage -1`, ~1 s),
`finished_successfully=False`, a traceback ląduje wyłącznie w kolumnie
`traceback` obiektu (niewidoczny na konsoli ani — dziś — w adminie).

Zaobserwowane na produkcyjnym zrzucie IHIT (operacja
`63d66aae-15a6-40fe-aed5-ff7bb618e4cd`, plik `pracownicy IHIT 31_12_2025
afiliacje.csv`): baza po `--from-dump` ma tylko 3 jednostki (`Wydział Domyślny`
[root], `Jednostka Domyślna`, `Obca jednostka`), więc **prawie każdy** wiersz to
"brak dopasowania". Pierwszy taki wiersz (`Zakład Transfuzjologii`) wywala import.

Cel: import ma **nie wywalać się** na braku jednostki, a zamiast tego pozwolić
użytkownikowi **utworzyć brakujące jednostki** (albo zmapować na istniejące)
podczas importu, spójnie z istniejącym flow "utwórz nowego autora".

## 2. Zasada architektoniczna (bez zmian)

Import jest dwufazowy: **analiza = dry-run** (nic nie zapisuje do domeny, odkłada
braki do `diff_do_utworzenia` / modeli-decyzji) oraz **integracja = commit**
(materializuje odroczone create'y). Nowa funkcja **respektuje ten podział**:
analiza tylko klasyfikuje i odracza, integracja tworzy jednostki.

Wzorzec do naśladowania — istniejący flow autora (`import_pracownikow.pewnosc`):
`twardy` (dopasowanie pewne), `zgadywanie` (jeden kandydat fuzzy, wybrany
automatycznie), `wielu`, `brak` (utwórz nowego). To samo słownictwo statusów
reużywamy dla jednostki (bez nowej enumeracji).

## 3. Klasyfikacja dopasowania jednostki (zamiast wyjątku)

Zastępujemy `_matchuj_jednostke_lub_wyjatek` klasyfikatorem, który **nigdy nie
rzuca** na braku/wielości — zwraca `(jednostka_or_None, status)`:

1. **Dopasowanie dokładne** (istniejąca logika `matchuj_jednostke`: `nazwa`/`skrot`
   iexact, `istartswith`, dezambiguacja przez wydział) → `(jednostka, "twardy")`.
   `row.jednostka` ustawione jak dziś.
2. **Brak dokładnego** → liczymy najlepsze podobieństwo **trigramowe**
   (`django.contrib.postgres.search.TrigramSimilarity`, `pg_trgm` jest w bazie)
   nad znormalizowaną `Jednostka.nazwa` oraz `Jednostka.skrot`:
   - `sim >= PRÓG_ZGADYWANIA` (stała, domyślnie **0.7**) → `(najlepsza, "zgadywanie")`
     — jednostka wybrana automatycznie, **oflagowana jako auto** (patrz §4).
   - w przeciwnym razie → `(None, "brak")` — odroczone utworzenie.

Nazwy normalizujemy istniejącym `normalize_nazwa_jednostki` przed porównaniem.
`PRÓG_ZGADYWANIA` ląduje jako stała modułowa (łatwa do strojenia), nie magic
number w kodzie.

**Kluczowe:** twardy crash znika **niezależnie od jakiegokolwiek przełącznika** —
niedopasowana jednostka staje się oflagowanym/pomijalnym wierszem, nigdy
`XLSMatchError` ubijającym cały run. To samo w sobie naprawia zgłoszony bug.

## 4. Model danych

### 4.1. `ImportPracownikowRow` — nowe pola
- `jednostka_status` — `CharField(choices=STATUS_CHOICES, null=True, blank=True)`,
  status dopasowania **jednostki** (odrębny od autorskiego `confidence`).
- `zrodlo_jednostki` — `ForeignKey(ImportPracownikowJednostka, null=True,
  on_delete=CASCADE)`, wskaźnik na decyzję o źródłowej nazwie jednostki
  (wiersze o tej samej nazwie źródłowej współdzielą jedną decyzję).
  `row.jednostka` pozostaje `None` do czasu rozstrzygnięcia w integracji.

Dla statusu `twardy` decyzja nie powstaje — `row.jednostka` ustawiane wprost jak
dziś, `zrodlo_jednostki=None`.

### 4.2. Nowy model `ImportPracownikowJednostka` (decyzja per unikalna nazwa)
Jednostki są współdzielone przez wielu pracowników, więc decyzje **deduplikujemy
po znormalizowanej nazwie źródłowej** (wzorzec `ImportPracownikowOdpiecie`):

- `parent` → `ImportPracownikow` (`related_name="jednostki_do_decyzji"`)
- `nazwa_zrodlowa` — znormalizowana nazwa z pliku (unikalna w obrębie `parent`)
- `skrot_sugerowany` — auto-generowany skrót (patrz §6)
- `tryb` — `"zgadywanie"` | `"brak"` (ustawia analiza)
- `auto_jednostka` — `FK Jednostka, null` — dopasowanie automatyczne do przeglądu
  (dla `tryb="brak"` = null)
- `auto_similarity` — `FloatField, null` — wartość podobieństwa (do pokazania userowi)
- `wybrany_parent` — `FK Jednostka, null` — miejsce w drzewie dla nowej jednostki.
  **Semantyka `None` zależy od `uczelnia.uzywaj_wydzialow`** (rozstrzyga się w
  integracji, bo domyślny wydział może jeszcze nie istnieć w analizie):
  - `uzywaj_wydzialow == False` → `None` = **root** (`parent=None`);
  - `uzywaj_wydzialow == True` → `None` = **Wydział Domyślny** (utworzony w
    integracji, jeśli go nie ma).

  Gdy user jawnie wskaże istniejący parent w pickerze, FK jest ustawione wprost i
  ta reguła nie działa.
- `decyzja` — `"akceptuj"` | `"mapuj"` | `"pomin"` (default `"akceptuj"`)
- `wybrana_jednostka` — `FK Jednostka, null` — cel, gdy user wybrał `"mapuj"`
- `utworzona` — `FK Jednostka, null` — jednostka utworzona przez integrację
  (guard idempotencji przy restarcie)

`Meta.unique_together = (parent, nazwa_zrodlowa)`, `ordering = ["nazwa_zrodlowa"]`.

### 4.3. Migracje / baseline
Nowe pola + model = jedna migracja `import_pracownikow`. Po scaleniu odświeżyć
baseline (`make baseline-update`) — **nie** w tej gałęzi, jeśli równolegle biegną
inne (konflikt na `baseline.sql`); baseline odświeża się raz przy merge.

## 5. Ekran "Jednostki: weryfikacja"

Nowy URL `<uuid:pk>/jednostki/` (widok `WeryfikacjaJednostekView`, grupa
uprawnień jak reszta importu). Wchodzi do flow **po analizie**, **blokując
`zatwierdz`** dopóki są nierozstrzygnięte decyzje (analogicznie do wierszy
`brak`/`wielu` autora). Dwie sekcje:

```
DOPASOWANE AUTOMATYCZNIE (zweryfikuj)                       [tryb=zgadywanie]
 «Zakład Hematologii Eksperymentalnej»  →  auto: «Zakład Hematologii» (0.82)
    (•) Zaakceptuj    ( ) Zmień na… [picker jednostki]    ( ) Utwórz nową zamiast

DO UTWORZENIA                                                    [tryb=brak]
 «Zakład Transfuzjologii»            (12 osób)
    (•) Utwórz nową   parent: [Wydział Domyślny ▾]   ( ) Mapuj na… [picker]   ( ) Pomiń
```

Reguły miejsca w drzewie:
- `uczelnia.uzywaj_wydzialow == False` → brak pickera parenta; nowe jednostki
  tworzone w **root** (`parent=None`).
- `== True` i w bazie **są** wydziały → picker parenta (jednostki-korzenie /
  wydziały), default = `Wydział Domyślny` jeśli istnieje.
- `== True` i w bazie **brak** wydziałów → baner informacyjny + opcja
  "Utwórz «Wydział Domyślny»" (tworzona w integracji, gdy zaakceptowana).

Bezpieczeństwo/UX nazw: renderowanie przez `{{ }}` (auto-escape — HTML w nazwie
neutralizowany), plus **skracanie** długich nazw do wyświetlenia z pełnym tekstem
w `title=` (tooltip). Żadnego `|safe`/`mark_safe` na danych z pliku.

Rozstrzyganie decyzji: lekkie widoki POST (htmx, jak istniejące
`WybierzKandydataView`/`PrzelaczOdpiecieView`) ustawiające `decyzja`,
`wybrany_parent`, `wybrana_jednostka` na obiekcie decyzji.

## 6. Integracja (nowa pierwsza faza w `integruj`)

Przed istniejącą pętlą `zmiany_potrzebne_set`:

1. **Wydział Domyślny (opcjonalnie):** gdy `uczelnia.uzywaj_wydzialow` i istnieje
   jakaś akceptowana decyzja `tryb="brak"` z `wybrany_parent IS NULL` (czyli
   "pod domyślny wydział"), a w bazie nie ma jeszcze roota "Wydział Domyślny" —
   utwórz go (`nazwa="Wydział Domyślny"`, `skrot="WD"` z uniknięciem kolizji,
   `uczelnia`, `parent=None`). `get_or_create` po nazwie. Wynik = `parent_domyslny`.
2. **Dla każdej decyzji `ImportPracownikowJednostka`:**
   - `decyzja="akceptuj"` + `tryb="brak"` → wylicz efektywny parent
     (`resolve_parent`): jawny `wybrany_parent`, a dla `None` — root gdy
     `uzywaj_wydzialow=False`, w przeciwnym razie `parent_domyslny` (§6.1).
     Utwórz `Jednostka(nazwa=nazwa_zrodlowa, skrot=skrot_sugerowany, uczelnia,
     parent=efektywny_parent)`; zapisz do `utworzona`.
   - `decyzja="akceptuj"` + `tryb="zgadywanie"` → użyj `auto_jednostka`.
   - `decyzja="mapuj"` → użyj `wybrana_jednostka`.
   - `decyzja="pomin"` → wiersze zostają niedopasowane (liczone/raportowane,
     nie integrowane).
3. **Podłączenie wierszy:** dla każdego wiersza z `zrodlo_jednostki` ustaw
   `row.jednostka` na rozstrzygniętą jednostkę i przelicz `zmiany_potrzebne` /
   `autor_jednostka` (jak w `_przetworz_wiersz`).

Dalej — istniejąca integracja bez zmian (materializacja diff, `integrate()`,
odpięcia §9, przepięcia §10).

**Idempotencja / restart:** tworzenie jednostek przez `get_or_create` po nazwie +
guard `utworzona is not None` (drugi przebieg nie duplikuje). Spójne z istniejącym
guardem `log_zmian is not None` w `_integruj_wiersz`.

**Generowanie `skrot`** (unikalny, ≤128): akronim z wielkich liter słów nazwy
(`Zakład Transfuzjologii` → `ZT`); gdy pusty/za krótki — przycięta nazwa; kolizja
`skrot` → sufiks numeryczny. Funkcja czysta, testowalna.

## 7. Przełącznik

Per-import opcja **"Twórz brakujące jednostki"** (`BooleanField`, default **True**
— dla IHIT niezbędne). Umiejscowienie: ekran mapowania (`MapowanieView`, obok
zapisu profilu) albo nowego importu. OFF → niedopasowane jednostki są
pomijane/raportowane (wiersze bez jednostki), wciąż **bez crasha**. ON →
generujemy decyzje i pokazujemy ekran weryfikacji.

## 8. Interakcje brzegowe (§9 odpięcia / §10 przepięcia)

Jednostki powstają w integracji **przed** fazami odpięć/przepięć, więc
`pary_z_pliku` jest do tego czasu poprawne. W analizie wiersze odroczone mają
`jednostka=None`, więc `_materializuj_odpiecia` ich nie zalicza do par z pliku —
ale te jednostki jeszcze nie istnieją, więc żadne `Autor_Jednostka` ich nie
wskazuje → brak fałszywych odpięć. Guard **G1** w `_wykonaj_odpiecia` (pomija
odpięcie, gdy para `(autor, jednostka)` trafiła do wierszy po rozstrzygnięciu)
pokrywa przypadek po utworzeniu. Do potwierdzenia dedykowanym testem.

## 9. Testy (pytest + model_bakery, bez unittest.TestCase)

- brak dopasowania → powstaje decyzja `ImportPracownikowJednostka(tryb="brak")`,
  wiersz odroczony (`jednostka=None`, `jednostka_status="brak"`), analiza **nie
  rzuca**;
- integracja `akceptuj`+`brak` → tworzy `Jednostka` + podłącza wszystkie wiersze
  o tej nazwie;
- auto-podobne → `tryb="zgadywanie"`, `auto_jednostka` ustawione, `auto_similarity`
  zapisane; `akceptuj` używa auto, `mapuj` używa wybranej, `pomin` pomija;
- `uzywaj_wydzialow=True` bez wydziałów → tworzy `Wydział Domyślny` i pod nim
  jednostki; `=False` → jednostki w root;
- `skrot`: akronim, fallback, kolizja → sufiks; unikalność;
- idempotencja: drugi przebieg integracji nie duplikuje jednostek (guard
  `utworzona`);
- **regresja bugu:** plik IHIT (fixture z niedopasowaną jednostką) przechodzi
  analizę bez `XLSMatchError`;
- escaping nazwy na ekranie weryfikacji (nazwa z `<script>` renderowana
  bezpiecznie).

## 10. Poza zakresem tego speca (osobne follow-upy)

1. **Read-only admin** dla `ImportPracownikow` + wierszy + traceback (widoczność
   błędów w adminie).
2. **Ręczny picker profili mapowania** (dziś tylko auto-match po nagłówkach przez
   `dopasuj_profil`).
3. **Skracanie/higiena nagłówków** w ekranie mapowania (poza minimalnym
   skracaniem nazw jednostek potrzebnym tutaj).

Każdy z nich to osobny cykl spec→plan→implementacja.
