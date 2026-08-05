# Import pracowników: opcja „Nadpisuj daty zatrudnienia (od/do) wartościami z pliku"

Data: 2026-07-26
Status: projekt (do akceptacji)

## 1. Problem

Scenariusz zgłoszony przez użytkownika: tydzień temu wykonano import
pracowników z pliku **bez dat** — wszyscy zaimportowani dostali „datę od"
= 19 lipca (patrz §2.4: fallback „data zmian → dziś" dla nowych okresów).
Teraz jest do zaimportowania poprawiony plik, w którym „data od" bywa
np. 5 lat wcześniejsza.

Pytanie brzmiało: czy ponowny import **zmodyfikuje** istniejącą datę, czy
**doda nowe miejsce pracy** (w tej samej jednostce)? Odpowiedź (zweryfikowana
w kodzie, §2): **ani jedno, ani drugie** — import wyceluje w istniejący
otwarty okres, pokaże różnicę dat w podglądzie, ale przy zapisie jej
**nie zastosuje**. Poprawiony plik niczego więc nie naprawi.

Pierwotny pomysł („wyczyść daty od/do w całej bazie" + import wypełnia
NULL-e) odrzucono na rzecz bezpieczniejszej opcji **nadpisywania dat
wartościami z pliku** — dotyka wyłącznie osób obecnych w pliku, nikt inny
nie traci dat (decyzja użytkownika w rozmowie projektowej).

## 2. Aktualne zachowanie (stan na dziś, zweryfikowane w kodzie)

### 2.1. Skąd biorą się daty w wierszu importu

Kolumny pliku mapują się (ekran mapowania) na pola wewnętrzne
`data_zatrudnienia` („Data zatrudnienia") i `data_końca_zatrudnienia`
(„Data końca zatrudnienia") — `mapping.py:29-30`; „Data od"/„Data do" to
synonimy nagłówków kolumn pliku (`mapping.py:116-117`). Wiersz odczytuje
je przez `_plik_od()` / `_plik_do()`
(`src/import_pracownikow/models.py:1020-1033`) — kontrakt: zawsze
`date | None`, nigdy string.

### 2.2. Wybór okresu docelowego (resolver)

`rozwiaz_okres_zatrudnienia(autor, jednostka, plik_od)`
(`src/import_pracownikow/okresy.py:73-123`) — „data od" jest TOŻSAMOŚCIĄ
okresu (spójne z `unique_together = (autor, jednostka, rozpoczal_prace)`).
Kolejność rozstrzygania przy niepustym `plik_od`:

1. **Dokładne trafienie** — istnieje AJ z `rozpoczal_prace == plik_od`
   → celuj w niego (`okresy.py:98-100`).
2. **Okres niedatowany** — istnieje AJ z `rozpoczal_prace IS NULL`
   → celuj w niego („do wypełnienia", `okresy.py:101-106`).
3. **Okres OTWARTY** (`zakonczyl_prace IS NULL`) — celuj w najświeższy
   aktywny okres; różnica „daty od" jest POKAZYWANA w podglądzie, ale NIE
   powstaje nowy okres i stary NIE jest domykany (świadoma decyzja „nowy
   okres tylko gdy stary zamknięty", `okresy.py:107-115`).
4. **Wszystkie okresy zamknięte** (osoba odeszła i wraca) → NOWY okres
   z datą z pliku (`okresy.py:116-118`).

Pusty `plik_od` → celuj w najświeższy aktywny/istniejący okres, a bez
żadnego → nowy okres bez daty (`okresy.py:120-123`).

### 2.3. Zapis dat na istniejącym okresie: wypełnij-tylko-NULL

`_integruj_daty_aj` (`src/import_pracownikow/models.py:1333-1357`):

- „Data od": zapis **wyłącznie gdy** `rozpoczal_prace IS NULL` w bazie
  a plik niesie datę. Istniejąca data **nigdy nie jest nadpisywana**.
- „Data do": identycznie — wstaw-tylko-gdy-pusta; różnica wobec
  istniejącej daty jest pokazywana w porównywarce, ale nie zapisywana.
- Pusta komórka w pliku → nic nie zmieniaj (nawet nie wypełnia NULL-a
  „datą zmian").

Po ustawieniu dat, PRZED save, walidowany jest niezmiennik
`rozpoczal_prace < zakonczyl_prace` (`models.py:1370-1388`) — naruszenie
→ `BPPDatabaseError` → wiersz izolowany (reszta importu idzie dalej).
Walidacja celowo w Pythonie przed save, bo DB-owy CHECK
(`poczatek_przed_koncem`, mig. bpp 0469) wewnątrz transakcji dałby
nieizolowany `CheckViolation`.

### 2.4. Nowe okresy i pochodzenie „19 lipca"

Nowy AJ tworzy `_materializuj_diff`
(`src/import_pracownikow/pipeline/integrate.py:67-126`). Gdy plik nie
niesie „daty od", nowy okres dostaje fallback **`data_zmian_personalnych`
importu, a w jej braku — dzisiejszą datę** (`integrate.py:98-106`).
Dokładnie stąd wszyscy z zeszłotygodniowego importu (plik bez dat) mają
`rozpoczal_prace` = 19 lipca. Świeży AJ ma od razu konkretną datę, więc
gałąź „wypełnij NULL" z §2.3 już go nie stempluje.

### 2.5. Podgląd (porównywarka)

`_porownaj_data` (`models.py:1001-1018`) oznacza pole jako „zmienione"
(`rozne=True`) także wtedy, gdy obie strony są niepuste i różne — z
docstringiem wprost: „różnica pokazana **bez nadpisania**". UWAGA:
„zmienione" obejmuje też wypełnienie NULL-a i nowy okres (`models.py:1017`,
ekstraktory `_stan_data_od/_do` w `roznice.py:65-84`) — to istotne dla
liczenia N w §3.5. Stany pól zasilają siatkę porównań i filtr stanu
(`stany_pol`, `models.py:1204-1219`; liczenie `stany_pol_live`
`models.py:1177-1190`); zamrożenie w `stany_pol_snapshot` następuje NA
POCZĄTKU integracji, przed zmianą bazy (`integrate.py:203`), i stan „po
integracji" jest serwowany z tego snapshotu.

### 2.5a. Bramka „zmiany potrzebne" (kluczowe dla projektu)

Integracja wiersza wykonuje się tylko, gdy analiza uznała, że są zmiany
do zapisania: `_check_autor_jednostka_needs_update` (`models.py:1259-1266`)
liczy daty **wyłącznie jako wypełnienie NULL-a** — różnica „baza ma datę,
plik ma inną" NIE ustawia `zmiany_potrzebne` (`analyze.py:766`,
`pewnosc.py:134-137`), wiersz nie wchodzi do `zmiany_potrzebne_set`
(`models.py:399-400`), a nawet włączony do integracji odpadłby na świeżym
re-checku (`integrate.py:227` → `pominiety_bo_nieaktualny`). Wniosek:
samo nadpisywanie w `_integruj_daty_aj` NIE wystarczy — bramka musi być
świadoma flagi (§3.3a).

### 2.6. Constrainty bazodanowe na `Autor_Jednostka`

`src/bpp/models/autor.py:769-809`:

- `unique_together (autor, jednostka, rozpoczal_prace)`;
- częściowy `UniqueConstraint` „jeden niedatowany okres na parę"
  (`rozpoczal_prace IS NULL`);
- `ExclusionConstraint` `bpp_autor_jednostka_okresy_bez_nakladan`:
  datowane okresy tej samej pary autor+jednostka NIE mogą się nakładać
  (GiST, `daterange(rozpoczal_prace, zakonczyl_prace)` z `&&`).

`daterange(rozpoczal_prace, zakonczyl_prace)` w constraincie ma granice
DOMKNIĘTE `'[]'` (`autor.py:713-732`), a `zakonczyl_prace IS NULL` daje
przedział otwarty w prawo `[od, ∞)`.

Konsekwencja dla projektu: cofnięcie „daty od" wstecz może najechać na
wcześniejszy zamknięty okres → trzeba to walidować w Pythonie PRZED save
(jak w §2.3 — naruszenie constraintu psuje transakcję i izolację wiersza).

### 2.6a. Inne miejsca pipeline'u dotykające dat AJ

- **Odpięcia** (`integrate.py:264-313`, `_wykonaj_odpiecia`) ustawiają
  `zakonczyl_prace` (= wczoraj) parom autor+jednostka SPOZA pliku —
  rozłączne z projektowaną flagą (guard G1 pomija pary obecne w pliku).
- **Defragmentacja** (`Autor.save()` → `defragmentuj_jednostke`,
  `autor.py:431-438`, scalanie `autor.py:620-710`) modyfikuje daty i
  KASUJE przyległe AJ; biegnie wewnątrz integracji (`_integrate_autor` →
  `a.save()`) tuż PRZED `_integruj_daty_aj`. Interakcja z flagą: gdy
  nadpisana „data od" uczyni okres przyległym (dzień-po-dniu) do
  zamkniętego okresu, przejdzie constraint i pre-check, a scalenie nastąpi
  przy najbliższym `Autor.save()` — akceptowalne (dla świeżych okresów
  istnieje już mechanizm `_przepnij_aj_po_defragmentacji`,
  `models.py:1451-1484`).
- `pewnosc.odtworz_autor_jednostka` nie pisze dat na istniejących AJ
  (odkłada tylko datę nowego okresu w diffie, `pewnosc.py:142`) — bez
  konfliktu.

### 2.7. Wniosek

W scenariuszu z §1 (otwarty okres z 19 lipca, plik z datą wcześniejszą):
resolver celuje w istniejący okres (§2.2 pkt 3), podgląd pokazuje różnicę
(§2.5), integracja daty nie zmienia (§2.3). **Potrzebna jest opcja
nadpisywania.**

## 3. Projektowane rozwiązanie

### 3.1. Model i migracja

Nowe pole `ImportPracownikow.nadpisuj_daty_zatrudnienia`
(`BooleanField`, `default=False`, verbose_name „Nadpisuj daty zatrudnienia
(od/do) wartościami z pliku") + migracja `import_pracownikow.0028`.
Flaga per-import → zakres z natury ograniczony do osób z pliku (bez ryzyka
multi-hosted). Baseline odświeżamy raz, przy scalaniu (polityka repo).

### 3.2. Formularz nowego importu: szuflada + popup

- Pole dochodzi do `NowyImportForm` (`src/import_pracownikow/forms.py`)
  i ląduje w istniejącym zwiniętym `<details>` obok
  `przepnij_wszystkie_prace`; nagłówek szuflady zmienia się na ogólne
  „Opcje zaawansowane".
- W `src/import_pracownikow/templates/import_pracownikow/`
  `importpracownikow_form.html` rozszerzamy istniejący wzorzec JS
  (`importpracownikow_form.html:26-45`, confirm na
  `id_przepnij_wszystkie_prace`): przy ZAZNACZANIU checkboxa `confirm(...)`
  z ostrzeżeniem; anulowanie odznacza pole. Odznaczanie — bez pytania.

### 3.3. Semantyka integracji (`_integruj_daty_aj`)

Flaga czytana z `self.parent.nadpisuj_daty_zatrudnienia`:

- **OFF** → zachowanie dzisiejsze, bit w bit (§2.3).
- **ON** → gdy plik NIESIE datę różną od bazy, data na okresie docelowym
  zostaje nadpisana — osobno „od", osobno „do" — z wpisem w `log_zmian`
  („data rozpoczęcia pracy: X → Y (nadpisano z pliku)").
- Pusta komórka w pliku NIGDY nie kasuje daty z bazy (zasada „import
  ustawia, nigdy nie kasuje" — spójna z tytułem/stopniem, §11.2 starego
  specu).
- Wybór okresu docelowego (resolver, §2.2) — BEZ ZMIAN. W scenariuszu
  z §1: data 19 lipca na istniejącym otwartym okresie zostaje zastąpiona
  datą z pliku; nie powstaje duplikat miejsca pracy.
- Gałąź „nowy okres" (§2.2 pkt 4 i §2.4) — BEZ ZMIAN (nowy AJ i tak
  dostaje daty z pliku).

### 3.3a. Bramka `zmiany_potrzebne` świadoma flagi (WARUNEK KONIECZNY)

Bez tej zmiany feature jest martwy dla scenariusza tytułowego (§2.5a):
wiersz, którego JEDYNĄ różnicą jest data, ma dziś `zmiany_potrzebne=False`
i integracja go pomija. Zmiany:

- `_check_autor_jednostka_needs_update` (`models.py:1259-1266`): przy
  fladze ON różnica dat „obie strony niepuste i różne" liczy się jako
  zmiana potrzebna (przy OFF — jak dziś: tylko wypełnienie NULL-a);
- przez to samo przechodzi analiza (`analyze.py:766`, `pewnosc.py:134-137`)
  i świeży re-check przy integracji (`integrate.py:227`) — wiersz z samą
  korektą dat wchodzi do `zmiany_potrzebne_set` (`models.py:399-400`)
  i nie kończy jako `pominiety_bo_nieaktualny`.

### 3.4. Walidacja przed zapisem

- Istniejący check `od < do` (§2.3) obejmuje wartości po nadpisaniu —
  bez zmian, tylko test.
- NOWY pythonowy pre-check nakładania się okresów: po nadpisaniu dat
  porównaj przedział z pozostałymi datowanymi okresami tej samej pary
  autor+jednostka — lustro `ExclusionConstraint` z §2.6 z IDENTYCZNĄ
  semantyką granic: przedziały DOMKNIĘTE `[od, do]`, a `zakonczyl_prace
  IS NULL` = otwarty w prawo `[od, ∞)`. Kolizja → `BPPDatabaseError`
  z komunikatem wskazującym kolidujący okres → wiersz izolowany, reszta
  importu idzie dalej.
- Warunek uruchomienia pre-checku (jednoznacznie): TYLKO gdy flaga ON
  faktycznie NADPISAŁA niepustą wartość w bazie inną wartością z pliku.
  Wypełnienie NULL-a (także przy fladze ON) idzie dzisiejszą ścieżką BEZ
  pre-checku — to zachowanie istnieje dziś i celowo go nie zmieniamy.

### 3.5. Ostrzeżenie w końcowym formularzu zapisu

`src/import_pracownikow/templates/import_pracownikow/przeglad.html`,
sekcja zapisu osób (Krok 2):

- Gdy flaga ON: callout alert (Foundation; ikona `fi-icon`, NIE emoji —
  to publiczny frontend): „Włączono nadpisywanie dat zatrudnienia:
  **N** wierszy ma daty różne od bazy — zostaną nadpisane wartościami
  z pliku."
- Liczenie N — UWAGA na semantykę: stan „zmienione" ze `stany_pol`
  obejmuje też wypełnienia NULL-i i nowe okresy (§2.5), które NIE są
  nadpisaniami. N liczymy jako „obie strony niepuste i różne" (dla
  `data_od` lub `data_do`), w widoku podglądu (`PodgladImportuView`,
  `views.py:944-1039`), live z `wstepnie_zaladuj_okresy` (przeciw N+1;
  `stany_pol_snapshot` bywa NULL do backfillu — `views.py:826-828` —
  więc SQL po snapshotcie by niedoszacował).
- `onsubmit`-owy `confirm` przycisku końcowego zapisu dostaje tę samą
  treść, połączoną z istniejącym ostrzeżeniem o pominiętych wierszach
  (`przeglad.html:205`).

### 3.6. Testy

Pytest (funkcje, `baker`, bez klas):

1. flaga ON: „data od" i „data do" nadpisane na istniejącym otwartym
   okresie (scenariusz §1: 19 lipca → data sprzed lat), wpisy w
   `log_zmian`;
2. bramka (§3.3a): wiersz z JEDYNĄ różnicą w datach — przy ON
   `zmiany_potrzebne=True`, integracja go wykonuje (nie kończy jako
   `pominiety_bo_nieaktualny`); przy OFF `zmiany_potrzebne=False` jak
   dziś;
3. flaga OFF: zachowanie dzisiejsze (data zostaje);
4. pusta komórka przy ON: data w bazie NIE jest kasowana;
5. kolizja przedziałów przy ON (wcześniejszy zamknięty okres) →
   `BPPDatabaseError`, wiersz izolowany; wypełnienie NULL-a nie odpala
   pre-checku;
6. `od >= do` po nadpisaniu → `BPPDatabaseError` (istniejący mechanizm);
7. formularz: pole w szufladzie, default OFF;
8. podgląd: callout z poprawnym N (tylko realne nadpisania: obie strony
   niepuste i różne; NIE wypełnienia NULL-i ani nowe okresy) renderuje
   się tylko przy fladze ON;
9. confirm końcowego zapisu zawiera ostrzeżenie przy fladze ON.

### 3.7. Drobiazgi

- Newsfragment `feature` po polsku w `src/bpp/newsfragments/`
  (kanoniczny katalog).
- Dokumentacja użytkownika importu — jeśli istnieje strona o imporcie
  pracowników w `docs/`, dopisać akapit o opcji.

## 4. Poza zakresem (YAGNI)

- Czyszczenie dat całej bazy/uczelni (pierwotny pomysł — zbędny przy
  nadpisywaniu; kasowałby daty osobom spoza pliku).
- Per-wierszowe decyzje „nadpisz/nie nadpisuj".
- Zmiany w resolverze okresów (`okresy.py`) i w fallbacku „data zmian →
  dziś" dla nowych okresów.
- Kasowanie dat pustą komórką pliku.

## 5. Decyzje projektowe (z rozmowy)

1. Nadpisywanie datami z pliku zamiast czyszczenia całej bazy —
   wybór użytkownika po przedstawieniu zweryfikowanego zachowania (§2).
2. Opcja umieszczona w szufladzie formularza NOWEGO importu (nie w
   końcowym formularzu) — spójne z `przepnij_wszystkie_prace`; podgląd
   od początku wie, że różnice dat będą nadpisane.
3. Potwierdzenie: popup przy zaznaczaniu + callout i confirm w końcowym
   formularzu zapisu osób.
