# Obca jednostka w multi-hosted — provisioning + gate-check importu PBN

Data: 2026-06-18
Branch: `feature/multi-hosted-config`
Status: zatwierdzony design, przed planem implementacji

## Problem

Import PBN (`src/pbn_import/`) failuje na kroku `institution_setup`
komunikatem z triggera bazodanowego:

```
AssertionError: Uczelnia jednostki i wydzialu musi byc identyczna
(funkcja PL/pgSQL bpp_jednostka_wydzial_sprawdz_uczelnia_id)
```

### Diagnoza (root cause)

Wątek `uczelnia` jest przekazywany **poprawnie**: `ImportManager` →
`_execute_step(uczelnia=self.uczelnia)` → `InstitutionImporter.run()`
(`import_manager.py:237-242`, `institution_import.py:159-160`). To NIE jest
błąd przekazywania uczelni.

Faktyczna przyczyna jest w `institution_import.py:196`:

```python
obca_jednostka, created = Jednostka.objects.get_or_create(
    nazwa="Obca jednostka",                       # lookup TYLKO po nazwie
    defaults={"skrot": "O", "uczelnia": uczelnia, "skupia_pracownikow": False},
)
```

Dwa fakty się zderzają:

1. `Jednostka.nazwa` oraz `Jednostka.skrot` są `unique=True` **globalnie**
   (`jednostka.py:113-114`), a w multi-hosted wszystkie uczelnie współdzielą
   jedną bazę. Nazwa `"Obca jednostka"` może więc istnieć tylko **raz w całym
   systemie**.
2. `get_or_create(nazwa=…, defaults={…})` szuka **wyłącznie** po `nazwa`.
   Zawartość `defaults` (w tym `uczelnia`) jest stosowana tylko przy INSERT.
   Przy trafieniu zwraca istniejący rekord z **cudzą** uczelnią.

Scenariusz awarii (MWSL jako druga uczelnia w instalacji): pierwsza/oryginalna
uczelnia już ma `"Obca jednostka"`. Import MWSL tworzy własny wydział i jednostkę
domyślną (scoped per-uczelnia, OK), ale `get_or_create(nazwa="Obca jednostka")`
trafia w jednostkę **innej** uczelni (`created=False`, `defaults` zignorowane).
Potem `Jednostka_Wydzial.get_or_create(jednostka=obca[inna uczelnia],
wydzial=wydzial[MWSL])` → trigger → assertion (`institution_import.py:209`).

Latentny błąd obok: nawet gdyby trigger nie zadziałał, kod ustawiłby
`MWSL.obca_jednostka = <jednostka innej uczelni>` (`institution_import.py:216`).

### Drugi, latentny błąd tej samej klasy

`znajdz_lub_utworz_wydzial_domyslny(uczelnia)` TWORZY z globalnie unikalną nazwą
`"Wydział Domyślny"` (`institution_import.py:42-47`). Druga uczelnia potrzebująca
domyślnego wydziału dostałaby `IntegrityError` na unikalnej nazwie/skrócie.

## Cel

1. Obca jednostka ma być **per-uczelnia**, z nazwą `"Obca jednostka " +
   uczelnia.skrot` (np. `"Obca jednostka UML"`, `"Obca jednostka UAFM"`).
2. Provisioning (utworzenie + podpięcie do wydziału + ustawienie FK) ma być
   **idempotentny** i dostępny jako osobne polecenie `create_obca_jednostka`
   działające dla **wszystkich** uczelni.
3. Brak/niespójność obcej jednostki ma być **zgłaszana użytkownikowi wcześnie** —
   przy wejściu na stronę importu i przy submicie formularza nowego importu.
4. Import (krok `institution_setup`) ma **auto-tworzyć** obcą jednostkę przez ten
   sam helper (Option A) — kolizja zniknie na każdej ścieżce wejścia (web i CLI).

## Źródło prawdy

Kanonicznym wyznacznikiem „która jednostka jest obcą jednostką tej uczelni" jest
FK `Uczelnia.obca_jednostka` (`uczelnia.py:252-262`). NIE używamy zapytania
`skupia_pracownikow=False` jako detektora — wg `help_text` modelu
(`jednostka.py:140-146`) ta flaga jest też zdejmowana dla Studentów /
Doktorantów / Emerytów, więc dałaby fałszywe trafienia. `Uczelnia.clean()`
(`uczelnia.py:726-730`) już wymusza `obca_jednostka.skupia_pracownikow == False`
— nasz provisioning honoruje ten invariant, a walidator może się na nim oprzeć.

## Architektura — 5 komponentów

Wszystkie czytają/zapisują jedno źródło prawdy: `Uczelnia.obca_jednostka`.

### 1. Helper provisioningu — `institution_import.py`

```python
def znajdz_lub_utworz_obca_jednostke(uczelnia) -> tuple[Jednostka, bool]:
```

Idempotentny, w kolejności (pierwsze trafienie wygrywa):

1. `uczelnia.obca_jednostka_id` ustawiony i jego target ma `uczelnia_id ==
   uczelnia.pk` → użyj go.
2. `Jednostka.objects.filter(uczelnia=uczelnia, skupia_pracownikow=False,
   nazwa__istartswith="Obca jednostka").first()` → użyj (matchuje też legacy
   `"Obca jednostka"` bez sufiksu).
3. utwórz: `nazwa=f"Obca jednostka {uczelnia.skrot}"`,
   `skrot=f"Obca {uczelnia.skrot}"`, `skupia_pracownikow=False`,
   `uczelnia=uczelnia`.

Następnie (zawsze, idempotentnie):

- zapewnij domyślny wydział uczelni przez **poprawiony**
  `znajdz_lub_utworz_wydzial_domyslny` (patrz pkt 2),
- utwórz `Jednostka_Wydzial(jednostka=obca, wydzial=wydzial_domyslny)` jeśli brak
  (oba należą do tej samej uczelni → trigger przechodzi),
- ustaw `uczelnia.obca_jednostka` jeśli jeszcze nie wskazuje tej jednostki
  (`save(update_fields=["obca_jednostka"])`).

Zwraca `(obca_jednostka, created)`.

### 2. Poprawka `znajdz_lub_utworz_wydzial_domyslny` — `institution_import.py`

Ścieżka FIND bez zmian (`nazwa__istartswith`, scoped per-uczelnia — backward
compatible, zero churnu na istniejących instalacjach). Ścieżka CREATE dostaje
nazwy unikalne per-uczelnia:

- `nazwa=f"{nazwa_domyslna} {uczelnia.skrot}"` (np. `"Wydział Domyślny UML"`),
- `skrot=f"WD-{uczelnia.skrot}"` (≤128 znaków, unikalne dzięki sufiksowi).

### 3. Walidator pre-import — `institution_import.py`

```python
def sprawdz_obca_jednostka(uczelnia) -> str | None:
```

Zwraca czytelny opis problemu albo `None` gdy OK. Sprawdza:

- `uczelnia.obca_jednostka` ustawione,
- target należy do `uczelnia` (`uczelnia_id == uczelnia.pk`),
- `skupia_pracownikow is False`,
- podpięta do wydziału tej samej uczelni (istnieje `Jednostka_Wydzial` z
  `wydzial.uczelnia_id == uczelnia.pk`).

Komunikat problemu kieruje do `manage.py create_obca_jednostka`.

### 4. Integracja z widokami — `views.py`

- `StartImportView.post` (`views.py:171`): dorzuć wynik `sprawdz_obca_jednostka(
  uczelnia)` do istniejącej listy `errors` (`views.py:198`). Blokuje start
  importu, pokazuje `messages.error`, działa też dla HX-Request (jak obecnie).
- `ImportDashboardView.get_context_data` (`views.py:57`): policz ten sam
  walidator dla `Uczelnia.objects.get_for_request(request)`, wystaw
  `context["obca_jednostka_problem"]`; szablon dashboardu renderuje baner
  ostrzegawczy przy wejściu na stronę.

### 5. Polecenie — `src/bpp/management/commands/create_obca_jednostka.py`

Iteruje `Uczelnia.objects.all()`; dla każdej woła helper z pkt 1 (idempotent) i
wypisuje per-uczelnia co zrobił (utworzono / podpięto / już OK).

Flagi:

- `--dry-run` — tylko raport (przez `sprawdz_obca_jednostka`), bez zapisów; exit
  code ≠ 0 jeśli którakolwiek uczelnia wymaga naprawy (health-check do CI),
- pozycyjny opcjonalny argument (slug lub pk uczelni) — ogranicza do jednej.

Inwokacja w dokumentacji/komunikatach: `python src/manage.py create_obca_jednostka`.

### 6. Naprawa źródła (`institution_setup`) — `institution_import.py:196-219`

Zastąp kolidujący blok `get_or_create(nazwa="Obca jednostka", …)` + ręczne
linkowanie + ustawianie FK **jednym** wywołaniem:

```python
obca_jednostka, created = znajdz_lub_utworz_obca_jednostke(uczelnia)
if created:
    self.log("info", f"Utworzono obcą jednostkę: {obca_jednostka.nazwa}")
```

Krok nadal provisionuje obcą jednostkę (Option A), ale przez bezpieczny,
idempotentny, współdzielony kod. Web i CLI nie kolidują.

## Ścieżki wejścia (dlaczego Option A)

```
Web:  user → dashboard (GET, baner) → submit (POST, gate) → task → institution_setup
CLI:  admin → manage.py pbn_importuj_uid → ImportManager → institution_setup
```

Gate w widokach chroni ścieżkę web (wczesny, przyjazny feedback). Ścieżka CLI
nie dotyka formularza, więc `institution_setup` woła helper (self-heal) — żadna
ścieżka nie kończy się kolizją.

## Obsługa błędów

- Helper jest idempotentny: ponowne wywołanie gdy jednostka istnieje to tani
  no-op (find, bez create).
- Provisioning honoruje `Uczelnia.clean()` (skupia_pracownikow=False).
- Walidator nigdy nie tworzy — tylko raportuje (czysty podział check vs provision).
- Brak `uczelnia.skrot` nie wystąpi w praktyce (`Uczelnia` dziedziczy
  `NazwaISkrot`, skrot unikalny) — sufiks daje globalną unikalność nazw.

## Testy (TDD)

Trigger jest triggerem bazodanowym → wymagany PostgreSQL (testcontainers).

- **Repro**: dwie uczelnie współdzielące jedną legacy `"Obca jednostka"`;
  `InstitutionImporter` dla drugiej — przed fixem assertion, po fixie zielono.
- Helper: idempotencja; poprawne nazwy per-uczelnia (`"Obca jednostka {skrot}"`);
  FK ustawiony; link `Jednostka_Wydzial` utworzony; honoruje istniejący FK.
- `znajdz_lub_utworz_wydzial_domyslny`: CREATE daje nazwę z sufiksem; FIND wciąż
  matchuje legacy `"Wydział Domyślny"`.
- Walidator: zwraca właściwy problem/`None` w stanach (brak FK, cudza uczelnia,
  skupia_pracownikow=True, brak linku do wydziału, OK).
- Polecenie: `--dry-run` raportuje i nie zapisuje (exit ≠ 0 gdy są braki); realny
  przebieg provisionuje wszystkie uczelnie; drugi przebieg to no-op; argument
  pozycyjny ogranicza do jednej uczelni.
- Widok: submit zablokowany z komunikatem gdy obca jednostka niespójna;
  dashboard wystawia `obca_jednostka_problem`.

## Zmiany w istniejących testach

`src/pbn_import/tests/test_institution_import.py:109`:
`assert obca_jednostka.nazwa == "Obca jednostka"` →
`assert obca_jednostka.nazwa == f"Obca jednostka {uczelnia.skrot}"`
(po zmianie ścieżka CREATE zawsze sufiksuje). Sprawdzić też ewentualne
asercje na `obca_jednostka.skrot == "O"`.

## Decyzje as-built (uściślenia względem pierwotnego designu)

- **Skróty przycinane do limitu kolumny.** `Wydzial.skrot` to `varchar(10)`,
  `Jednostka.skrot` to `varchar(128)`. Sufiks `uczelnia.skrot` (max 128) nie
  zawsze się mieści, więc generowany skrót przycinamy (`[:10]` / `[:128]`).
  Realne skróty uczelni są krótkie, więc forma czytelna przeżywa; przycięcie to
  zabezpieczenie przed patologicznie długim skrótem (i przed `baker` generującym
  skróty max-length w testach).
- **Walidator broni przed dryfem, nie przed stanem persystentnym.**
  `Uczelnia.save()` sam egzekwuje `obca_jednostka.skupia_pracownikow == False`,
  więc sprawdzenie tej flagi w `sprawdz_obca_jednostka` łapie tylko dryf
  (przestawienie flagi na samej Jednostce bez rewalidacji Uczelni).
- **Domyślna jednostka też naprawiona.** `znajdz_lub_utworz_jednostke_domyslna`
  miała tę samą latentną kolizję na create-path ("Jednostka Domyślna"/"JD"
  globalnie unikalne) — dashboard importu (GET) auto-tworzy ją dla uczelni bez
  jednostek, więc druga uczelnia dostawała `IntegrityError` (500). Create-path
  sufiksujemy skrótem uczelni tak samo jak wydział.

## Poza zakresem (YAGNI)

- Migracja danych zmieniająca nazwy istniejących `"Obca jednostka"` na
  sufiksowane — niepotrzebna; FIND po prefiksie matchuje legacy rekordy.
- Zmiana globalnego `unique=True` na `unique_together(uczelnia, nazwa)` — duża,
  ryzykowna zmiana schematu; rozwiązujemy problem nazewnictwem, nie schematem.
