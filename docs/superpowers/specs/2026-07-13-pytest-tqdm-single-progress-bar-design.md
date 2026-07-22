# pytest-tqdm — jeden zagregowany pasek postępu dla całej suity

- **Data:** 2026-07-13
- **Status:** design zaakceptowany, przed planem implementacji
- **Typ:** nowa, samodzielna paczka pytest (publikowana na PyPI), konsumowana
  przez BPP jako dev-dependency
- **Kontekst:** BPP odpala testy pod `pytest-xdist` (`-n auto
  --dist=worksteal`) z `pytest-sugar`. Pod xdist rendering paska sugara się
  rozjeżdża — user widzi „dużo pasków". Cel: **jeden** sticky pasek
  tqdm-owy dla całej suity, z ETA/throughput, a nad paskiem tylko błędy
  (pełne tracebacki). Tylko w trybie interaktywnym (TTY).

## 1. Problem

`pytest-sugar` renderuje pasek per-plik i pod xdist (wiele workerów
raportujących nierównolegle) daje wizualny bałagan. Brakuje:

- **jednego** paska agregującego wszystkie workery,
- ETA + throughput (it/s) dla całego przebiegu,
- czystego „nad paskiem drukuj tylko failures (pełny traceback)".

## 2. Cele i nie-cele

**Cele:**

- Jeden sticky pasek `tqdm` na dole terminala: `count/total`, `%`, ETA,
  throughput, live tally ✓/✗/s, bieżący `nodeid` w postfixie.
- Domyślnie: nad paskiem drukowane są **tylko** testy FAILED/ERROR, i to
  z **pełnym** tracebackiem, w momencie wystąpienia.
- Agregacja poprawna pod `pytest-xdist` (kontroler widzi raporty wszystkich
  workerów) oraz w trybie serialnym (bez xdist).
- Aktywacja automatyczna tylko w TTY; poza TTY (CI, `run-site`, pipe) plugin
  jest no-op.
- Przełączniki CLI zmieniające zachowanie (patrz §5).
- Samodzielna paczka na PyPI (entry-point `pytest11`), wpięta do BPP jako
  dev-dependency.

**Nie-cele (YAGNI):**

- Brak raportu HTML/TUI po runie (to robi `pytest-tui` — inny problem).
- Brak własnych podsumowań/tabel na koniec — zostawiamy natywne podsumowanie
  pytest (failures recap, `--durations`, totals).
- Brak kolorowych motywów/konfiguracji wyglądu poza tym, co daje tqdm.
- Brak integracji z Notion/zdalnymi dashboardami.
- Brak trybu „pasek per-worker" — celem jest dokładnie jeden pasek.
- **Brak „agent mode" / redukcji tokenów pod LLM.** Wykrywanie uruchomienia
  spod Claude Code / Cursor / Aider i emitowanie token-minimal output jest
  poza zakresem — u usera robi to już RTK (CLI proxy, `rtk pytest`, 60–90%
  redukcji na wszystkich komendach). W kodzie zostawiamy tylko *seam*
  (warstwa aktywacji §5 rozstrzyga pojedynczy fakt „aktywny/nie") tak, by
  ewentualny tryb agenta dało się dołożyć później bez przebudowy. Patrz §14.

## 3. Krajobraz — dlaczego build, nie buy

Przegląd PyPI + GitHub (2026-07-13):

| Plugin | Co robi | Dlaczego nie wystarcza |
|---|---|---|
| `pytest-tqdm` | — | Nie istnieje (PyPI 404). Nazwa wolna → bierzemy ją. |
| `pytest-progress` 1.4.0 | Tekstowe liczniki, „test/linia" w `-v` | Scrollujące linie, nie sticky bar; brak ETA/throughput; brak agregacji-jako-jeden-pasek |
| `pytest-sugar` | Pasek per-plik + instant failures | Rozjeżdża się pod xdist (obecny ból) |
| `pytest-rich` 0.2.0 | Sesja przez `rich`, ma pasek | Autor: „proof of concept, szukam maintainera"; brak udokumentowanej agregacji xdist; ostatni release 2024-12 |
| `pytest-pretty` 1.3.0 | Ładne podsumowania + linia „running" | Summary-plugin, brak paska N/total z ETA |
| `pytest-tui` 2.1.0 | TUI/HTML **po** runie | Nie live podczas runu |

Żaden nie pokrywa kombinacji: *jeden zagregowany pasek pod xdist + tylko
failures z pełnym tracebackiem nad paskiem + gate TTY + przełączniki CLI*.
Jedyny z prawdziwym live-paskiem (`pytest-rich`) jest jawnie porzucony.
Wniosek: budujemy dedykowaną, małą paczkę.

## 4. Kształt paczki i dystrybucja

- **Repo:** samodzielne, siostrzane `~/Programowanie/pytest-tqdm`
  (poza drzewem BPP — zgodnie z regułą worktree/repo). Publiczne, MIT.
- **Nazwa PyPI / import:** `pytest-tqdm` / moduł `pytest_tqdm`.
- **Rejestracja:** entry-point `pytest11` w `pyproject.toml`
  (`[project.entry-points.pytest11] tqdm = "pytest_tqdm.plugin"`).
- **Zależności runtime:** tylko `tqdm`. `pytest` jako peer (>=8, bez górnego
  capa poza rozsądkiem).
- **Build:** `uv` + `pyproject.toml`, ruff, pre-commit, GitHub Actions
  (matryca Python × pytest). Wzorzec jak inne paczki usera.
- **Dev-loop na BPP:** `pip install -e ~/Programowanie/pytest-tqdm` do
  środowiska BPP, iteracja na prawdziwej suicie ~7000 testów; po
  ustabilizowaniu — release na PyPI + dodanie do `pyproject.toml` BPP w
  dependency-group `dev` (obok `pytest-sugar` / docelowo zamiast).
- **Rozmiar:** ~150 linii logiki + testy.

## 5. Powierzchnia CLI / konfiguracja

Default = auto-on w TTY, pasek + tylko failures z pełnym tracebackiem.

| Flaga | `pytest.ini` / env | Efekt |
|---|---|---|
| *(brak)* | — | Auto-on w TTY (kontroler), failures-only, pełny traceback |
| `--tqdm` | `PYTEST_TQDM=1` | Wymuś ON nawet bez TTY (np. w logu z zachowanym ANSI) |
| `--no-tqdm` | `PYTEST_TQDM=0` | Wymuś OFF (fallback do sugara/domyślnego reportera) |
| `--tqdm-names` | `tqdm_names` (ini) | Dodatkowo streamuj **każdy** ukończony test nad paskiem (PASSED/FAILED/SKIPPED per linia) — opcjonalne „listing test names ABOVE" |
| `--tqdm-tb=full\|line\|no` | `tqdm_tb` (ini) | Verbosity tracebacku nad paskiem: pełny (default) / jednolinijkowy `FAILED nodeid` / nic |

Priorytet rozstrzygania aktywności: `--tqdm`/`--no-tqdm` > `PYTEST_TQDM` >
auto-detekcja TTY. Gdy nieaktywny → plugin nie rejestruje żadnych hooków
renderujących (pełny no-op, zero narzutu).

**Seam pod przyszły „agent mode":** rozstrzyganie aktywności zamykamy w
jednej funkcji `resolve_mode(config) -> Mode` zwracającej enum
(`OFF` / `BAR`). To jeden punkt, w którym da się później dołożyć wariant
`AGENT` (detekcja `CLAUDECODE` / `AI_AGENT` / `CURSOR_*` / `AIDER_*` →
token-minimal output) bez ruszania reszty. W v1 `resolve_mode` zwraca
wyłącznie `OFF`/`BAR`.

## 6. Renderowanie paska

Format linii (tqdm `bar_format` + `set_postfix_str`):

```
 42%|███████▏       | 512/1210 [00:37<00:48, 14.3it/s] ✓510 ✗2 s0 ▸ nodeid
```

- `total` = liczba zebranych itemów na kontrolerze (po
  `pytest_collection_modifyitems`, po deselekcji).
- Advance o 1 na finalny wynik każdego testu (patrz §8 rerun).
- Postfix: `✓{passed} ✗{failed} s{skipped} ▸ {short_nodeid}` — aktualizowany
  na bieżąco.
- Strumień: **stderr** (nie łapie się w capture stdout testów). Gate
  `isatty()` sprawdzany na tym samym strumieniu, na który pisze tqdm.
- `dynamic_ncols=True`, `leave=False` (po zakończeniu pasek znika, żeby nie
  śmiecić przed natywnym podsumowaniem).
- **Linia podsumowania na koniec:** przy zamknięciu paska (`close_bar`)
  drukujemy JEDNĄ linię totals nad miejscem po pasku:
  ```
  pytest-tqdm ▸ 1210 tests in 01:25  ·  14.2 tests/s  ·  ✓1180 ✗2 s28  ·  8 workers
  ```
  Zawiera: liczbę testów, czas (`tqdm.format_interval`), throughput,
  tally ✓/✗/skip, liczbę workerów xdist (`serial` gdy bez `-n`; liczone po
  distinct `report.node.gateway.id`).

## 7. Wyjście nad paskiem

Cały tekst „nad paskiem" idzie przez `tqdm.write()` (czyści pasek, drukuje,
przerysowuje pasek pod spodem).

- **Default (`--tqdm-tb=full`):** dla FAILED/ERROR, w momencie finalnego
  wyniku:
  ```
  ── FAILED src/bpp/tests/test_x.py::test_foo ──
  <report.longreprtext>            # honoruje -l / --tb z konfiguracji
  ```
- `--tqdm-tb=line`: tylko `FAILED nodeid` (jedna linia).
- `--tqdm-tb=no`: nic nad paskiem (pełne tracebacki i tak w natywnym
  podsumowaniu na końcu).
- `--tqdm-names`: dodatkowo każdy ukończony test jako linia
  `PASSED|FAILED|SKIPPED nodeid` (niezależnie od `--tqdm-tb`).

## 8. Współpraca z innymi pluginami

- **pytest-sugar:** gdy nasz plugin jest aktywny, w `pytest_configure`
  wykrywamy zarejestrowanego sugara i **wyrejestrowujemy** go
  (`config.pluginmanager.unregister(...)`), żeby dwa reportery nie biły się
  o terminal.
- **Domyślny TerminalReporter:** wyciszamy jego per-test progress (kropki /
  procenty), np. przez podniesienie „quiet" dla fazy runtest, ale
  **zostawiamy** końcowe sekcje (errors/failures recap, `--durations=50`,
  linia totals) — drukują się po zamknięciu paska.
- Kolejność: pasek zamyka się w `pytest_sessionfinish` (lub
  `pytest_runtestloop` teardown) **przed** natywnym podsumowaniem.

## 9. Mechanika xdist

- **Tylko kontroler:** jeśli `hasattr(config, "workerinput")` → worker →
  plugin no-op. Cała agregacja na kontrolerze, bo xdist forwarduje
  `pytest_runtest_logreport` z workerów do kontrolera.
- **Total:** z `pytest_collection_modifyitems` na kontrolerze (kontroler
  zbiera pełną listę do dystrybucji). Fallback: gdy total nieznany (0),
  tqdm działa w trybie bez `total` (licznik + throughput, bez %/ETA).
- **worksteal / loadscope:** kolejność raportów nieuporządkowana — nie ma
  znaczenia, liczymy zdarzenia, nie pozycje.
- **Serial (bez xdist / `-p no:xdist`):** te same hooki, działa identycznie.

## 10. Przypadki brzegowe

- **pytest-rerunfailures:** test może wygenerować wiele raportów. Advance
  paska i drukowanie tracebacku **tylko na finalnym wyniku**; raporty
  pośrednie (`report.outcome == "rerun"`) ignorujemy. Dedupe advance po
  `nodeid`, żeby retry nie przeskoczył paska podwójnie.
- **skip/xfail/xpass:** advance paska; osobny licznik `s`. xfail liczony jako
  „nie-fail" (nie drukuje tracebacku).
- **Faza raportu:** advance na `when == "call"` dla testów, ale skipy z
  `setup` (np. `pytest.skip` w fixture) też muszą policzyć — reguła:
  advance gdy `report.when == "call"` **lub** (`when == "setup"` i wynik
  skipped/error i nie będzie fazy call).
- **pytest-timeout:** zabity test i tak generuje raport (error) → policzony,
  traceback nad paskiem.
- **Błędy kolekcji / puste zebranie:** total=0 → pasek się nie pokazuje,
  plugin nie przeszkadza w raporcie błędów kolekcji.
- **Capture:** tqdm na stderr; nie kolidować z `capsys`/`capfd` testów.
- **`-s` / `--capture=no`:** testy piszące na stdout mogą wejść „w" pasek;
  akceptowalne — tqdm przerysowuje się przy kolejnym update. Nie walczymy z
  tym w v1.
- **Wąski terminal / brak ANSI:** `dynamic_ncols`; gdy brak TTY → i tak
  nieaktywne.

## 11. Architektura / komponenty

Moduł `pytest_tqdm/plugin.py`:

- `pytest_addoption(parser)` — flagi z §5 + wpisy ini.
- `pytest_configure(config)` — rozstrzygnij aktywność (§5); jeśli aktywny i
  kontroler: wyrejestruj sugara, wycisz per-test reporter, zarejestruj
  instancję `TqdmReporter` jako plugin. Jeśli nieaktywny: return (no-op).
- klasa `TqdmReporter`:
  - `pytest_collection_modifyitems(items)` → zapamiętaj `total`.
  - `pytest_runtest_logreport(report)` → logika finalnego wyniku, advance,
    tally, `tqdm.write` (traceback/nazwa).
  - `pytest_sessionfinish` → zamknij pasek (`bar.close()`).
- Pełna izolacja: cała logika w jednej klasie ze stanem (bar, liczniki, set
  widzianych nodeid); brak globali; testowalne w izolacji.

## 12. Strategia testów (pluginu)

Testy własne paczki przez fixture `pytester` (pytest):

- Generuj tymczasowe testy (pass/fail/skip/rerun) i odpalaj podproces
  pytest z pluginem, pod `-p no:xdist`, `-n0`, `-n2`.
- Asercje na **stderr**:
  - pasek pojawia się w TTY (symulacja `isatty` / `--tqdm`), nie pojawia się
    przy `--no-tqdm` / non-TTY,
  - FAILED drukuje traceback nad paskiem (default), `--tqdm-tb=line` tylko
    jednolinijkowy, `--tqdm-tb=no` nic,
  - `--tqdm-names` streamuje nazwy PASSED, bez flagi — nie,
  - rerun: pasek nie przeskakuje podwójnie, traceback tylko finalny,
  - total zgadza się z liczbą testów; przy pustej kolekcji brak paska.
- Test integracyjny sugara: gdy sugar zainstalowany i plugin aktywny,
  sugar jest wyrejestrowany.

## 13. Integracja z BPP

- Faza dev: `pip install -e ~/Programowanie/pytest-tqdm`; ręczne przebiegi
  `uv run pytest -n auto -m "not playwright"` do kalibracji renderu na
  prawdziwej suicie.
- Faza release: publikacja na PyPI → dodanie do BPP `pyproject.toml`
  (`[dependency-groups] dev`), decyzja czy **obok** czy **zamiast**
  `pytest-sugar` (rekomendacja: zamiast — sugar i tak wyłączamy gdy aktywni;
  w non-TTY oba i tak milczą, więc trzymanie obu nie daje wartości).
- Nic w `addopts` nie trzeba zmieniać — auto-on w TTY załatwia UX; make
  targety (`tests-without-playwright` itd.) działają bez zmian, a że lecą
  zwykle nie-w-TTY na CI, tam plugin milczy.

## 14. Otwarte kwestie / przyszłość

- **Agent mode (v2, świadomie odroczone).** Detekcja uruchomienia spod LLM
  przez env (`CLAUDECODE=1`, `AI_AGENT=claude-code_*`, `CURSOR_*`,
  `AIDER_*`) i token-minimal output (tylko finalne failures + 1 linia
  totals, reszta wyciszona). Krajobraz: dojrzałego pytest-*pluginu* z tą
  funkcją nie ma — ekosystem robi to warstwę wyżej (RTK, `token-saver`,
  `snip`) albo przez MCP (`build-output-tools-mcp`). U usera RTK już to
  pokrywa, więc v1 tego nie robi; `resolve_mode` (§5) trzyma seam.
- Czy `--tqdm-names` powinno też pokazywać czas per-test przy nazwie? (v2)
- Ewentualny tryb „pokaż też slowest N na żywo" — raczej nie, jest
  `--durations`. (v2/never)
- Kolizja z `-s` (testy piszące na stdout w pasek) — do obserwacji, może
  guard w v2. Na razie akceptowane.
