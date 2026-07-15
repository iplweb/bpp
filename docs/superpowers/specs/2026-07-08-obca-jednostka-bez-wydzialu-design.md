# Obca jednostka bez wymogu podpięcia do wydziału

Data: 2026-07-08
Obszar: `src/pbn_import/`
Issue źródłowy: zgłoszenie użytkownika (uczelnia MWSL, konfiguracja bez wydziałów)

## Problem

Gate-check `sprawdz_obca_jednostka` przed importem PBN wymaga, aby obca
jednostka uczelni była podpięta do wydziału tej uczelni (przez metryczkę
`Jednostka_Rodzic`). Uczelnie, które **nie używają wydziałów**, dostają
fałszywy alert „Obca jednostka nie jest podpięta do żadnego wydziału tej
uczelni", mimo że FK `Uczelnia.obca_jednostka` jest poprawnie ustawiony.

Dodatkowo komunikat myli użytkownika: ustawienie w adminie „Jednostki
nadrzędnej" (`Jednostka.parent`, MPTT) nie tworzy wiersza `Jednostka_Rodzic`,
więc ręczna próba naprawy nie skutkuje.

## Ustalenie kluczowe: 4. warunek to martwy kod obronny

Docstring `sprawdz_obca_jednostka` (`institution_import.py:173-174`)
uzasadnia wymóg wydziału zdaniem: „inaczej import trafiłby na trigger przy
linkowaniu". To **nieaktualne**:

- Migracja **0455 (Faza B / #438)** zdjęła wszystkie trzy triggery spójności
  uczelni (`bpp_jednostka_wydzial_sprawdz_uczelnia_id`,
  `bpp_jednostka_sprawdz_uczelnia_id`,
  `bpp_jednostka_ustaw_wydzial_aktualna`) **bez zamiennika** — Zasada #4
  federacji dopuszcza krawędzie między-uczelniane.
- Tabela `Jednostka_Rodzic` (którą check odpytuje) **nie ma żadnego triggera**.
- `Jednostka_Rodzic.clean()` (`jednostka.py:724-730`) jawnie dopuszcza
  krawędzie między-uczelniane.
- Jednostka-root (`parent=NULL`, denorm `wydzial=NULL`) to w pełni poprawny
  stan po Fazie B.

Wniosek: usunięcie 4. warunku jest bezpieczne — żaden mechanizm „w dole"
importu już go nie wymaga.

## Wymaganie

Obca jednostka jest **wymagana**, ale jej pozycja w strukturze
(wydział / rodzic) **przestaje nas obchodzić**. Wystarczy, że FK jest
ustawiony na sensowną jednostkę tej uczelni.

## Zmiany

Trzy skoordynowane zmiany, wszystkie w `src/pbn_import/`.

### 1. Gate-check `sprawdz_obca_jednostka` — usuń 4. warunek

Plik: `src/pbn_import/utils/institution_import.py` (obecnie linie 160-199).

Zostają warunki 1-3 (sanity, łapią realne pomyłki konfiguracji):

| # | Warunek                                    | Los            |
|---|--------------------------------------------|----------------|
| 1 | `obca_jednostka` FK ustawiony              | **zostaje**    |
| 2 | obca należy do TEJ uczelni                 | **zostaje**    |
| 3 | `skupia_pracownikow is False`              | **zostaje**    |
| 4 | podpięta do wydziału (`Jednostka_Rodzic`)  | **USUWAMY**    |

Dodatkowo:
- usuń blok `podpieta = Jednostka_Rodzic.objects.filter(...)` i towarzyszący
  `if not podpieta: return ...`,
- popraw docstring: usuń nieaktualne uzasadnienie o triggerze i 4. punkt
  z listy sprawdzeń,
- `Jednostka_Rodzic` zostaje importowane (używane w
  `znajdz_lub_utworz_obca_jednostke`), więc importu nie ruszamy.

### 1b. Sprzątanie nieaktualnych komentarzy o triggerze (comment-rot)

Po zdjęciu triggerów w migracji 0455 kilka miejsc opisuje nieistniejące
zachowanie. Po tej zmianie stają się aktywnie mylące — poprawić:

- `src/pbn_import/views.py:103-105` — komentarz „obca jednostka MUSI być
  podpięta do wydziału … inaczej import padnie na triggerze spójności".
- `src/pbn_import/views.py:200-204` — docstring `_bledy_kontekstu_uczelni`:
  „krok institution_setup padłby na triggerze
  `bpp_jednostka_wydzial_sprawdz_uczelnia_id`".
- `src/pbn_import/management/commands/create_obca_jednostka.py:4-7` —
  docstring modułu („podpięta do wydziału … inaczej import PBN wywala się
  na triggerze") oraz `:21-22` — `help` komendy („podpiętą do wydziału
  domyślnego"). Po zmianie #2 komenda już nie tworzy wydziału/linku, więc
  oba teksty trzeba urealnić.

Wewnątrz `znajdz_lub_utworz_obca_jednostke` docstring do aktualizacji leży
w liniach ~113-114 (zdanie o triggerze `bpp_jednostka_wydzial_
sprawdz_uczelnia_id`) — poza zakresem podanym w sekcji 2, ale należy do
tej samej funkcji; poprawić przy okazji zmiany #2.

### 2. `znajdz_lub_utworz_obca_jednostke` — linkuj do wydziału tylko gdy jawnie podano

Plik: `src/pbn_import/utils/institution_import.py` (obecnie linie 118-157).

Obecny blok linkujący (linie 144-151: `if wydzial is None:
znajdz_lub_utworz_wydzial_domyslny(...)`, potem `wezel`, potem
`Jednostka_Rodzic.objects.get_or_create(...)`) wykonuje się **tylko gdy
`wydzial is not None`**.

Semantyka po zmianie:

- **Ścieżka polecenia** (`create_obca_jednostka`, woła bez `wydzial`) →
  zapewnia obcą jednostkę + FK, **nie** tworzy „Wydziału Domyślnego" ani
  linku `Jednostka_Rodzic`. Obca zostaje czystym węzłem-root (`parent=NULL`).
- **Ścieżka importera** (`InstitutionImporter.run`, linia 325, woła
  z `wydzial=wydzial`) → zachowanie **bez zmian**: importer buduje realne
  drzewo wydział+jednostka i podpięcie obcej pod nie jest spójne.

Wybór projektowy: linkowanie **warunkowe od obecności argumentu `wydzial`**,
nie flaga boolean ani całkowite usunięcie. Jedna funkcja obsługuje dwa
konteksty (gołe provisioning z CLI vs. pełny setup importera); sygnał
„czy linkować" niesie sama obecność `wydzial`. Minimalny diff, importer
i jego testy nietknięte.

Zaktualizować docstring funkcji (opis kroku podpięcia → „opcjonalny,
tylko gdy podano `wydzial`").

### 3. Dashboard — bez zmian w szablonie

Ustalenie z review: statyczny tekst w `dashboard.html:36-38` **nie wspomina
o wydziale** („Obca jednostka skupia autorów spoza uczelni i jest wymagana
do importu. Administrator powinien uruchomić polecenie …"). Jedyna wzmianka
o wydziale przychodziła dynamicznie przez `{{ obca_jednostka_problem }}`
(komunikat 4. warunku), która znika wraz z warunkiem. **Zmiana szablonu
jest zbędna** — nic tam nie ruszamy.

### 4. Testy (TDD — najpierw czerwone)

- `test_institution_import.py:235` `test_sprawdz_obca_jednostka_bez_wydzialu`
  — **odwraca semantykę**: check ma teraz **przejść** (`None`) mimo braku
  wydziału. Zmienić nazwę na `test_sprawdz_obca_jednostka_bez_wydzialu_
  przechodzi`.
- `test_institution_import.py:132-135`
  `test_obca_jednostka_helper_creates_uczelnia_scoped` — **odwrócić asercję**:
  dziś JAWNIE asertuje istnienie `Jednostka_Rodzic.objects.filter(
  jednostka=obca, parent__uczelnia=uczelnia).exists()`. Po zmianie helper
  wołany bez `wydzial` **nie** tworzy linku → asercja ma sprawdzać, że
  linku **nie ma** (rozdzielić: bez `wydzial` brak linku).
- Nowy test: `znajdz_lub_utworz_obca_jednostke(uczelnia, wydzial=w)`
  **tworzy** link `Jednostka_Rodzic` (zachowana ścieżka importera).
- `test_create_obca_jednostka.py` — po komendzie `sprawdz_obca_jednostka`
  nadal `None` (komenda woła bez `wydzial` → brak linku, a check i tak
  przechodzi na warunkach 1-3). Przechodzi bez zmian, ale zweryfikować.
- Zachować testy warunków 2-3: obca z innej uczelni
  (`test_sprawdz_obca_jednostka_cudza_uczelnia`) oraz
  `skupia_pracownikow=True` (`test_sprawdz_obca_jednostka_skupia_pracownikow`)
  nadal wywalają check.
- 6 wywołań helpera w `test_views_dashboard.py` służy tylko przejściu
  gate-checku (który po zmianie przechodzi na warunkach 1-3) — nietknięte.

## Poza zakresem (YAGNI)

- Nie ruszamy `znajdz_lub_utworz_wydzial_domyslny` ani ścieżki jednostki
  domyślnej — ta legalnie potrzebuje wydziału jako korzenia drzewa
  (`views.py:128`, `run()` linia 292).
- Nie ruszamy zachowania importera (`InstitutionImporter.run`) — nadal
  podpina obcą pod wydział, bo ma realny wydział w kontekście.
- Bez migracji bazodanowych — zmiana wyłącznie w logice Pythona + testy.

## Ryzyka

- Niski. Zmiana rozluźnia walidację (mniej fałszywych negatywów), nie
  zaostrza. Ścieżki, które dotąd przechodziły, dalej przechodzą.
- Jedyny realny wektor: gdyby jakiś dalszy krok importu zakładał, że obca
  jednostka MA wpis `Jednostka_Rodzic`. Zweryfikowano: importer sam podpina
  (przekazuje `wydzial`), więc w ścieżce importu link istnieje; ścieżka
  CLI provisioningu nie prowadzi importu, więc brak linku jej nie dotyczy.

## Weryfikacja

- `uv run pytest src/pbn_import/tests/test_institution_import.py
  src/pbn_import/tests/test_create_obca_jednostka.py
  src/pbn_import/tests/test_views_dashboard.py`
- Ręcznie: uczelnia bez wydziałów + `create_obca_jednostka` →
  `sprawdz_obca_jednostka` zwraca `None`, dashboard bez alertu.
