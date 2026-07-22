# Przebudowa strony rezultatów importu pracowników — filtry + karta rekordu

Data: 2026-07-13
Branch: `feat/import-rezultaty-filtry`
Widok: `ImportPracownikowResultsView` → `/import_pracownikow/<pk>/rezultaty/`

## Cel

Uczytelnić stronę wyników importu: uporządkować pasek filtrów, dodać licznik
przefiltrowanych rekordów, nie pokazywać pól, których w pliku nie ma, oraz
przebudować „kartę rekordu" (dwuwierszowy `<tbody>`) tak, by kontrolki autora
i porównania plik→baza były czytelne.

## Stan obecny (co przebudowujemy)

- `importpracownikowrow_list.html` — pasek filtrów `#filtr-roznic`: pole „Szukaj"
  + po jednym `<fieldset>` na KAŻDE pole z `POLA_ROZNIC` (8 pól), radia
  ułożone pionowo. Filtrowanie czysto po froncie (JS czyta `data-diff-*`
  z 1. `<tr>` każdej karty; tekst z `textContent` 1. `<tr>`).
- `_wiersz_preview_kom.html` — karta = dwa `<tr>` w `<tbody id="wiersz-{pk}">`:
  - `<tr>` #1: Poz, Osoba (plik), Pewność, Autor (BPP), Jednostka.
  - `<tr>` #2 (colspan=5): blok akcji dopasowania autora (`import-blok-akcje`)
    + pionowa lista porównań plik→baza (`import-blok-porownania`) + przepięcie.
- `_porownanie_kom.html` — komórka porównania: gdy różnica, żółta plakietka
  z wartością z pliku + `baza: <stara wartość>` pod spodem.
- `roznice.py::POLA_ROZNIC` — rejestr 8 pól (klucz, etykieta, ekstraktor).
- `mapowanie_kolumn` (JSONField na `ImportPracownikow`) = `{nagłówek: pole}` —
  jedyne źródło prawdy o tym, JAKIE kolumny plik zawiera.

## Zakres zmian

### 1. Pasek filtrów: widoczne + collapsible, radia poziomo

- **Zawsze widoczne** (kolejność): `jednostka` (Jednostka), `tytul`
  (Tytuł naukowy), `data_od` (Data od), `data_do` (Data do).
- **Zwijane** (`<details><summary>Więcej filtrów…</summary>`): `email`
  (E-mail), `stopien` (Stopień służbowy), `funkcja` (Funkcja w jednostce),
  `stanowisko` (Stanowisko dydaktyczne).
- „Szukaj:" bez zmian, zostaje na górze paska.
- Radia w każdym fieldsecie **poziomo** (SCSS: `label { display:block }` →
  inline/flex-row).
- `<details>` musi być WEWNĄTRZ `<form id="filtr-roznic">`, żeby radia
  zwiniętych filtrów nadal działały (JS `querySelectorAll` je znajduje
  niezależnie od stanu open/closed).

Podział pól robimy w widoku (`get_context_data`): dwie listy kontekstu
`pola_glowne` i `pola_dodatkowe` (zamiast jednego `pola_roznic`), każda w
formacie `[(klucz, etykieta), …]`. Kolejność „głównych" jawnie ustalona
(nie kolejność z `POLA_ROZNIC`).

### 2. Licznik „Pokazano X z Y rekordów"

- Element nad tabelą (np. `<p id="filtr-licznik">`). Aktualizowany w JS
  `filtruj()`: `Y` = liczba kart (`<tbody>` rekordów), `X` = liczba
  nieukrytych. Zero zapytań do bazy, czysty front. Aktualizowany też po
  `htmx:afterSettle` (po swapie karty).
- **Edge case (review):** gałąź `{% empty %}` renderuje własny `<tbody>` z
  wierszem „Żadnych wierszy…". Liczenie `Y` musi go pomijać — realne karty
  oznaczyć np. `<tbody data-rekord>` i liczyć `querySelectorAll('tbody[data-rekord]')`
  (albo licznik tylko gdy `object_list` niepuste) — inaczej przy 0 rekordach
  `Y=1` (fałszywy rekord).

### 3. Warunkowe ukrywanie Stopnia służbowego / Stanowiska dydaktycznego

Gdy plik NIE zawiera danej kolumny — pole znika **i z karty, i z filtra**.

- Nowe property na modelu `ImportPracownikow`:
  ```python
  @property
  def ma_kolumne_stopnia(self):
      return "stopień_służbowy" in (self.mapowanie_kolumn or {}).values()

  @property
  def ma_kolumne_stanowiska(self):
      return "stanowisko_dydaktyczne" in (self.mapowanie_kolumn or {}).values()
  ```
  (`mapowanie_kolumn` = `{nagłówek: pole_docelowe}`, więc sprawdzamy wartości.)
- Widok: z `pola_dodatkowe` usuwa `stopien`/`stanowisko`, gdy odpowiednie
  property = False (to wystarcza dla FILTRA — pasek renderuje się tylko w
  `importpracownikowrow_list.html`, gdzie `parent_object` jest w kontekście).
- `_wiersz_preview_kom.html`: `import-porownanie-item` dla Stopnia / Stanowiska
  owinięte **`{% if parent_object.ma_kolumne_stopnia %}`** /
  `{% if parent_object.ma_kolumne_stanowiska %}` — WYŁĄCZNIE przez
  `parent_object`, NIGDY gołą zmienną kontekstu.
  **[BLOKER z review]** Ten partial jest re-renderowany przez widoki akcji HTMX
  (`_WierszImportuMixin._render_wiersz`, `views.py:~359`) z kontekstem TYLKO
  `{"row", "parent_object"}`. Goła `{% if ma_kolumne_stopnia %}` byłaby po
  KAŻDYM swapie (wybór kandydata / dopasuj-autora / przepnij / utwórz-nowego)
  undefined → wiersze „Stopień sł."/„Stanowisko dyd." znikałyby z karty MIMO
  obecnej kolumny. `parent_object.ma_kolumne_*` jest w OBU kontekstach (lista +
  akcje) → odporne na swap.

### 4. „Zmień autora" pod dopasowanym autorem

- Kontrolki dopasowania autora (link „zmień autora" / dropdown kandydatów dla
  `wielu` / „dopasuj do istniejącego" + „utwórz nowego" dla `brak`) przenosimy
  z `<tr>` #2 do komórki **„Autor (BPP)"** w `<tr>` #1, tuż pod
  `_autor_dane.html`. Widoczne tylko w `edytowalny_podglad`.
- `<tr>` #2 po zmianie zawiera: log audytu (`sformatowany_log_zmian`, tylko
  gdy NIE `edytowalny_podglad`) + siatkę porównań + blok przepięcia.
- Leniwy Select2 + jego `<script>` (guard `window.__bppImportAutorPicker`,
  rejestrowany raz globalnie, event-delegation) przenosi się razem z
  kontrolkami — działa niezależnie od miejsca w DOM.
- HTMX target `#wiersz-{pk}` obejmuje CAŁY `<tbody>` (oba `<tr>`), więc swap
  innerHTML nadal odświeża i kontrolki (w #1), i porównania (w #2). Bez zmian
  w widokach akcji.

**Konsekwencja dla filtra tekstowego** (ważne): dziś JS szuka w
`textContent` całego 1. `<tr>`, świadomie POMIJAJĄC 2. `<tr>` (bo tam był
skrypt Select2 zaśmiecający dopasowania). Po przeniesieniu kontrolek do #1
ta ochrona znika. Rozwiązanie: `data-szukaj` na przeszukiwalnych fragmentach +
w JS czytać `tbody.querySelectorAll('[data-szukaj]')` zamiast całego `<tr>`.
- **TWARDY WYMÓG (review):** `data-szukaj` owija WYŁĄCZNIE: (a) `<td>` „Osoba
  z pliku" (nazwisko/imię), (b) osobny `<span data-szukaj>` wokół samego wyniku
  `_autor_dane` (nazwa autora), (c) `<td>` „Jednostka". Kontrolki dopasowania
  autora (`.import-autor-zmien`, dropdown kandydatów `{{ k.autor }}`, „utwórz
  nowego", kontener Select2) MUSZĄ być RODZEŃSTWEM POZA elementem `data-szukaj`
  — inaczej nazwiska kandydatów i tekst Select2 wyciekają do wyszukiwania
  (dokładnie problem, który obchodził stary kod pomijając 2. `<tr>`).
- **Zamierzona regresja zakresu (review):** dziś `textContent` 1. `<tr>` łapie
  też badge „Pewność" i „Poz" (arkusz/wiersz). Po `data-szukaj` przestają być
  przeszukiwalne — zgodne z placeholderem „nazwisko / jednostka…", ale to
  świadoma zmiana zachowania.

### 5. Porównania plik→baza jako siatka 2–3 kolumn

- `import-blok-porownania` z pionowej listy → responsywny CSS grid
  (`display:grid; grid-template-columns: repeat(auto-fit, minmax(…))`,
  do 3 kolumn na szerokim, zawija na wąskim).
- Kolejność pól: E-mail · Tytuł nauk. · Stopień sł.* · Funkcja ·
  Stanowisko dyd.* · Data od · Data do (`*` = warunkowe wg pkt 3).
- Zbliżone do szkicu użytkownika:
  ```
  E-mail:        Tytuł nauk.:   Funkcja:
  Stanowisko d.: Data od:       Data do:
  ```

### 6. Etykieta „baza:" → „obecnie:"

- `_porownanie_kom.html`: `baza: {{ pole.baza }}` → `obecnie: {{ pole.baza }}`.

## Poza zakresem (YAGNI)

- Bez zmian w logice dopasowania jednostek/autorów, bez migracji, bez zmian
  w `roznice.py` (`POLA_ROZNIC` zostaje jednym rejestrem — podział na
  główne/dodatkowe robi widok).
- Bez paginacji / server-side filtrowania — front-only zostaje.

## Testy

- **Aktualizacja istniejącego testu (review):**
  `test_podglad_ma_pasek_filtrow_radia` (`test_views_preview_render.py:~190`)
  tworzy import bez `mapowanie_kolumn` (`{}`) i asertuje `name="filtr-stopien"`
  + `filtr-stanowisko`. Po warunkowym ukrywaniu te radia znikną (pusty dict →
  False) → test RED. Nadać w nim `mapowanie_kolumn` z obiema kolumnami (albo
  rozbić na przypadki z/bez). (`test_podglad_wiersz_ma_atrybuty_data_diff`
  zostaje zielony — `data-diff-*` nie są ukrywane.)
- `models`: `ma_kolumne_stopnia` / `ma_kolumne_stanowiska` — True/False wg
  zawartości `mapowanie_kolumn` (w tym pusty dict → False).
- `views`: `get_context_data` daje `pola_glowne` = 4 pozycje w ustalonej
  kolejności; `pola_dodatkowe` bez `stopien`/`stanowisko`, gdy brak kolumn;
  z nimi, gdy kolumny są; flagi `ma_kolumne_*` w kontekście.
- `render` (istniejące `test_views_*_render.py` jako wzór): karta nie renderuje
  wiersza „Stopień sł."/„Stanowisko dyd.", gdy brak kolumny; kontrolka „zmień
  autora" w komórce Autora; etykieta „obecnie:".
- Regresja: filtr tekstowy nadal działa (szuka po `data-szukaj`), licznik
  liczy poprawnie (smoke, jeśli testujemy JS — inaczej ręcznie w run-site).

## Frontend

- Zmiany w `_import-pracownikow.scss` → `grunt build` (albo `make assets`):
  - filtr: radia poziomo (`label` inline zamiast `display:block`),
  - siatka porównań (`import-blok-porownania` → grid),
  - **kontrolki autora w komórce „Autor" (review):** dziś szerokość dają im
    `.import-blok-akcje { flex: 2 1 22rem }`; po przeniesieniu do wąskiego
    `<td>` w 1. `<tr>` trzeba dać własną rezerwację szerokości/układu (dropdown
    kandydatów + Select2 „220px" + „utwórz nowego" nie mogą ścisnąć kolumny).
  - **NIE** nadpisywać klas grida Foundation (reguła projektu — zmieniać klasy
    w HTML, nie w SCSS).
- **Komentarze Django `{# #}` jednoliniowe** (reguła CLAUDE.md, powtarzalny
  błąd): nowy `<details>` i owijki `data-szukaj` — każda linia komentarza
  z własnym `{# … #}`; bloki przez `{% comment %}…{% endcomment %}`.
- Weryfikacja wizualna: `run-site` (uwaga: serwuje z GŁÓWNEGO drzewa, nie
  z worktree — przy weryfikacji trzeba wskazać worktree albo scalić).

## Newsfragment

`src/bpp/newsfragments/<slug>.feature.rst` — po polsku, jedno zdanie o
przebudowie strony rezultatów importu.
