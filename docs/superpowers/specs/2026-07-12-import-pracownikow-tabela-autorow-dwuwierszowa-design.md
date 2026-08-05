# Import pracowników — dwuwierszowa „karta" rekordu + filtrowanie po stanie pól

Data: 2026-07-12
Moduł: `src/import_pracownikow/`
Szablon główny: `templates/import_pracownikow/importpracownikowrow_list.html`
(widok `ImportPracownikowResultsView`, `views.py:625`; URL
`/import_pracownikow/<uuid>/rezultaty/`)

Spec obejmuje **dwie sprzężone części**:

- **Część A** — przebudowa układu tabeli autorów na dwuwierszową „kartę".
- **Część B** — pasek filtrów „zmienione / zgodne / brak w pliku" per pole
  (6 pól, łączenie AND) + dorobienie brakujących kolumn `plik→baza` (tytuł
  naukowy, funkcja w jednostce).

Obie części dotykają tego samego szablonu/partiali — robimy je razem.

---

## Część A — Dwuwierszowa karta rekordu

### Problem

Tabela podglądu/audytu autorów (`#tabela-autorow`) ma **13 kolumn**:

`Arkusz · Wiersz · Imiona · Nazwisko · Tytuł · Pewność · Autor ·
Jednostka · E-mail(plik→baza) · Stopień(plik→baza) · Stanowisko(plik→baza)
· Akcje/zmiany · Przepnij prace`

Skutki: tabela znacznie szersza niż interfejs (Foundation) → poziomy scroll;
dwie najszersze, interaktywne kolumny (`Akcje/zmiany`, `Przepnij prace`) są
ostatnie → ściśnięte, „Przepnij prace" wyjeżdża poza prawą krawędź; Select2
wyboru autora nie ma się gdzie rozłożyć.

### Decyzja (zatwierdzona z użytkownikiem)

Każdy rekord = **jeden `<tbody>` z dwoma `<tr>`** o **wspólnym tle** (HTML
dopuszcza wiele `<tbody>` w jednej `<table>`):

- **Wiersz 1** — 5 wąskich kolumn, tylko odczyt: `Poz | Osoba (z pliku) |
  Pewność | Autor (BPP) | Jednostka`.
- **Wiersz 2** — `<td colspan="5">` na pełną szerokość, wspólne tło, bez górnej
  ramki (sklejenie): wszystkie szerokie/interaktywne treści.

**Rezygnujemy z DataTables** dla tej tabeli. Świadomie zaakceptowana
konsekwencja: brak klik-sortowania kolumn. Zostaje **kolejność serwera**
(niepewni na górze) + **pasek filtrów** (Część B) sterujący widocznością
rekordów czysto client-side. Kolumny wiersza 1 to osobne kolumny (nie złączone).

Odrzucone alternatywy: scalenie kolumn w jednym `<tr>` + DataTables (akcje wciąż
w wąskiej komórce); DataTables Responsive (szczegóły schowane za „+").

### Układ szczegółowo

**Wiersz 1 (5 kolumn, read-only):**

| Kolumna | Treść |
|---|---|
| **Poz** | `nr_arkusza / nr_wiersza` (drobne, wyszarzone) |
| **Osoba (z pliku)** | `nazwisko` (pogrubione) + `imię`; pod spodem `tytuł_stopień`. READ-ONLY z XLS. |
| **Pewność** | `row.confidence_badge` (Foundation label + ikona) |
| **Autor (BPP)** | `_autor_dane.html`; gdy brak — „— brak dopasowania" |
| **Jednostka** | gdy autor jest w innej: `obecna → **docelowa**`; inaczej docelowa; brak → „— (odroczona / brak)" |

**Wiersz 2 (`colspan=5`), trzy bloki (flex, zawijają się):**

*Tryb edytowalny* (`parent_object.edytowalny_podglad`):
1. **Dopasowanie autora** — istniejąca logika wg `row.confidence` (`wielu` →
   dropdown kandydatów + „inny autor…"; `brak` → „Dopasuj…" + checkbox „utwórz
   nowego"; twardy/zgadywanie → „zmień autora"). Select2 dostaje pełną szerokość.
2. **Dane plik → baza** — komparatory (patrz Część B): e-mail / tytuł naukowy /
   stopień służbowy / funkcja w jednostce / stanowisko dydaktyczne, poziomo,
   każdy przez `_porownanie_kom.html`.
3. **Przepnij prace** — checkbox `przepnij-prace` z pełną etykietą.

*Tryb audytu* (`zintegrowany`, `not edytowalny_podglad`): komparatory (read-only)
· `sformatowany_log_zmian` · plakietka wykonanego przepięcia.

### Zmiany w kodzie (Część A)

- **`partials/_wiersz_preview.html`** — wrapper `<tr id="wiersz-{{pk}}">` →
  `<tbody id="wiersz-{{pk}}">` obejmujący oba `<tr>`.
- **`partials/_wiersz_preview_kom.html`** — emituje **dwa `<tr>`** (zawartość
  `<tbody>`). Pozostaje `innerHTML`-em swapu HTMX.
- **`importpracownikowrow_list.html`** — nowy `<thead>` (5 kolumn), usunięcie
  inicjalizacji DataTables + bloku `htmx:afterSettle`/`dt.row().invalidate`,
  dodanie paska filtrów (Część B) i skryptu filtrującego `<tbody>`. Nagłówek
  „Lista modyfikacji do bazy danych…" **zostaje** (asercja `test_views_liveops`).

**HTMX:** cel swapów `#wiersz-{{pk}}` to teraz `<tbody>` (był `<tr>`), swap dalej
`innerHTML`. `_WierszImportuMixin._render_wiersz` (`views.py:347`) renderuje ten
sam partial — **bez zmian w widokach**. Znika gimnastyka DataTables↔HTMX (uwaga
reviewera #6).

### SCSS (Część A)

Partial SCSS importu (`grunt build` po zmianie):
- `#tabela-autorow > tbody:nth-of-type(odd)` — delikatny tint; oba `<tr>`
  dziedziczą wspólne tło.
- `<td>` w wierszu 2 — `border-top: none` (sklejenie); `tbody` — `border-top`
  (rozdzielenie kart).
- bloki wiersza 2 — `display:flex; gap; flex-wrap` z sensownymi `min-width`.
- **Nie** nadpisujemy klas gridu Foundation.

---

## Część B — Filtrowanie po stanie pól „zmienione / zgodne / brak"

### Cel

Pasek filtrów pozwalający pokazać autorów, u których dane pole jest
**zmienione**, **zgodne (bez zmian)** albo **puste w pliku (brak)**. Per pole,
kilka pól łączy się przez **AND**. Filtr natychmiastowy, bez przeładowania.

**6 pól objętych filtrem:** Jednostka · E-mail · Tytuł naukowy (dr/dr hab/prof) ·
Stopień służbowy (major/kapitan) · Funkcja w jednostce (wewn. `stanowisko` →
`funkcja_autora`) · Stanowisko dydaktyczne.

### Decyzje UX (trzymać się ich)

- **Trzy ROZŁĄCZNE stany na pole:** `zmienione` / `zgodne` / `brak` (puste w
  pliku). NIE scalać „zgodne" z „brak" — „brak w pliku" musi dać się wyłuskać
  osobno.
- **Radio per pole, 4 opcje:** `wszystkie` (domyślne) · `zmienione` · `zgodne` ·
  `brak w pliku`.
- **Łączenie pól = AND.**
- **Dorobić brakujące kolumny `plik→baza`** dla tytułu naukowego i funkcji w
  jednostce (dziś ich nie ma; e-mail/stopień/stanowisko już są — `_porownanie_kom.html`).
- Dostępność: radio w `<fieldset><legend>`; ikony Foundation (nie emoji); nie
  nadpisywać klas gridu Foundation.

### PUŁAPKA: tabela renderuje się w DWÓCH stanach

`{% if parent_object.finished_successfully %}` jest true **przed** integracją
(`edytowalny_podglad` = `przeanalizowany`/`struktura_zintegrowana`;
`porownaj_z_baza()` pokazuje OCZEKUJĄCE różnice) i **po** (`zintegrowany`; baza
już zaktualizowana → `porownaj_z_baza()` pokaże „zgodne", realne zmiany są w
`row.log_zmian`, `models.py:985`+). **Stan pola musi być poprawny w OBU
trybach** — nie liczyć „zmienione" wyłącznie z `porownaj_z_baza` po integracji.

### Skąd brać stan pola (pre-integracja, live)

Helpery bazowe: `_porownaj_email` (`models.py:715`) — `rozne` tylko gdy obie
strony niepuste. `_porownaj_fk` (`models.py:730`) — `rozne = plik_id is not None
and baza_id != plik_id` (ustawienie tam, gdzie baza pusta = już „zmienione").
„zgodne" = (nie brak) ∧ (nie zmienione).

- **jednostka**: zmienione = `row.autor and row.jednostka and
  row.autor.aktualna_jednostka_id != row.jednostka_id`; brak = `row.jednostka_id is None`.
- **e-mail**: zmienione = `porownaj_z_baza()["email"]["rozne"]`; brak = `not dane.get("email")`.
- **stopień służbowy**: zmienione = `porownaj_z_baza()["stopien"]["rozne"]`;
  brak = `not dane.get("stopień_służbowy")`.
- **stanowisko dydakt.**: zmienione = `porownaj_z_baza()["stanowisko"]["rozne"]`;
  brak = `not dane.get("stanowisko_dydaktyczne")`.
- **tytuł naukowy**: zmienione = `row.tytul_id is not None and row.autor and
  row.tytul_id != row.autor.tytul_id`; brak = `row.tytul_id is None`.
- **funkcja w jednostce**: zmienione = `row.funkcja_autora_id is not None and
  row.autor_jednostka and row.autor_jednostka.funkcja_id != row.funkcja_autora_id`;
  brak = `row.funkcja_autora_id is None`.

### Nowe kolumny komparatorów (tytuł, funkcja) — rozszerzenie `porownaj_z_baza`

`porownaj_z_baza()` (`models.py:745`) dziś zwraca `email`/`stopien`/`stanowisko`.
Dodać dwa wpisy przez ten sam `_porownaj_fk`:
- `tytul`: plik = `dane.get("tytuł_stopień")`, baza = `autor.tytul` (gdy
  `autor.tytul_id`), plik_id = `self.tytul_id`.
- `funkcja`: plik = `dane.get("stanowisko")`, baza = `aj.funkcja` (gdy
  `aj.funkcja_id`), plik_id = `self.funkcja_autora_id`.

Renderowane w wierszu 2 przez `_porownanie_kom.html` (razem z istniejącymi
email/stopień/stanowisko).

### Rekomendowana architektura (dodanie pola = 1 wpis)

1. **Deklaratywny rejestr `POLA_ROZNIC`** (nowy `roznice.py` w module): lista
   `(klucz, etykieta, ekstraktor)`, gdzie `ekstraktor(row) ->
   "zmienione"|"zgodne"|"brak"`. Jedno źródło prawdy dla modelu, filtra i paska.
2. **`ImportPracownikowRow.stany_pol() -> {klucz: stan}`**: live gdy
   `edytowalny_podglad`, ze **snapshotu** gdy `zintegrowany`.
   - **Snapshot:** nowe lekkie pole `stany_pol_snapshot = JSONField(null=True)`
     na `ImportPracownikowRow`. W `integruj()` (`models.py:985`, PRZED mutacjami
     bazy — wtedy `porownaj_z_baza`/`*_id` wciąż odzwierciedlają różnice)
     zapisujemy `stany_pol()` do pola. Filtr po integracji czyta stabilną
     wartość — bez parsowania stringów z `log_zmian`.
   - Nowe pole JSON = **nowa migracja** `import_pracownikow/0024_*` (nie ruszać
     wydanych). Baseline refresh przy scalaniu.
3. **Szablon**: na PIERWSZYM `<tr>` rekordu wyemituj `data-diff-<klucz>=
   "zmienione|zgodne|brak"` iterując `stany_pol()`. Pasek filtrów renderuj
   iterując `POLA_ROZNIC` (fieldset+legend+4 radia per pole).
4. **JS filtra** (bez DataTables — Część A go usuwa): jedna funkcja iterująca
   `#tabela-autorow > tbody`, czytająca `data-diff-*` z pierwszego `<tr>`
   rekordu; rekord widoczny gdy dla każdego pola radio = `wszystkie` LUB stan
   pasuje (**AND** po polach). Toggluje `tbody.hidden`. Zmiana radia → re-filtr.
   Ten sam skrypt obsługuje ewentualne pole szukania po tekście.
5. **HTMX-swap a świeżość atrybutów**: swap podmienia `innerHTML` `<tbody>`
   (oba `<tr>`), więc `data-diff-*` na pierwszym `<tr>` są renderowane od nowa z
   aktualnego `stany_pol()` — zawsze świeże. Po `htmx:afterSettle` wystarczy
   **ponownie zastosować bieżący filtr** (mały listener), bo zmiana dopasowania
   autora może zmienić stan jednostki/tytułu/funkcji.

### Funkcja w jednostce (nad tym trwają prace)

Kolumna pliku „Funkcja w jednostce" (`funkcja`/`funkcja_w_jednostce`/`stanowisko`)
→ wewn. `stanowisko` → `analyze.py:582` `matchuj_funkcja_autora` →
`row.funkcja_autora` → `integrate.py:100` `Autor_Jednostka.funkcja =
row.funkcja_autora`. Jeśli refaktor — zaadaptować tylko ekstraktor `funkcja` w
`POLA_ROZNIC` (1 linijka).

### Kryteria akceptacji (Część B)

Pasek radio per pole (wszystkie/zmienione/zgodne/brak), AND, filtr
natychmiastowy; widoczne kolumny plik→baza także dla tytułu i funkcji; stan
poprawny PRZED i PO integracji; „brak" rozłączny od „zgodne"; kolejne pole =
1 wpis w `POLA_ROZNIC`.

---

## Testy (pytest, baker, `@pytest.mark.django_db`)

- **`stany_pol()` per pole**: zmienione/zgodne/brak dla każdego z 6 pól (w tym
  autor niedopasowany, `utworz_nowego`, pusty plik).
- **Poprawność w stanie `zintegrowany`** (ze snapshotu) — regresja: nie polegać
  na `porownaj_z_baza` po integracji.
- **Rozszerzone `porownaj_z_baza`**: `tytul`/`funkcja` zwracają `{plik,baza,rozne}`.
- **Render**: pierwszy `<tr>` rekordu ma `data-diff-*`; pasek ma radia dla
  wszystkich pól; nowe komórki komparatorów w wierszu 2.
- **HTMX-swap**: po `dopasuj-autora`/`wybierz-kandydata`/`utworz-nowego`/
  `przepnij-prace` swap `#wiersz-{pk}` (teraz `<tbody>`) podmienia oba `<tr>`,
  pokazuje aktualne dane i świeże `data-diff-*`.
- **Smoke oba tryby**: edytowalny podgląd (Krok 1/2) i audyt.
- Opcjonalnie Playwright: radio zawęża wiersze, dwa pola = AND.

## Porządek / housekeeping

- Praca w worktree `~/Programowanie/bpp-tabela-dwuwierszowa`
  (branch `feat/import-pracownikow-tabela-dwuwierszowa`).
- `mapping.py` już zmodyfikowany w worktree (etykiety pól: „Tytuł / stopień
  naukowy (np. dr, dr hab, prof, etc)", „Stopień służbowy (np. major, kapitan,
  etc)") — commit razem z resztą.
- Nowe pole JSON → migracja `import_pracownikow/0024_*`; baseline refresh przy
  scalaniu (nie w trakcie równoległych branchy).
- Newsfragment `src/bpp/newsfragments/<slug>.feature.rst` (PL).
- Weryfikacja/aktualizacja testów asertujących markup tabeli.

## Poza zakresem

- Zmiany logiki dopasowania autora / przepięć / komparatorów (poza dodaniem
  `tytul`/`funkcja` do `porownaj_z_baza` i przełożeniem kontrolek do nowego
  układu).
- Inne tabele modułu (`odpiecia`, `audyt`, `weryfikacja_*`) — zostają na DataTables.
- Sortowanie kolumn (świadomie usunięte).
