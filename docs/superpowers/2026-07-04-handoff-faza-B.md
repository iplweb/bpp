# Handoff — Konsolidacja Wydział→Jednostka, FAZA B (#438)

**Skopiuj poniższy prompt do nowej sesji Claude Code.** Faza A jest gotowa i
zmergowalna (PR #442, zielony). Faza B robisz **na tej samej gałęzi**
`feat/438-konsolidacja-wydzial-jednostka`.

---

## PROMPT DO WKLEJENIA

Kontynuujesz issue #438 (konsolidacja Wydział→Jednostka w BPP, Django).
Faza A jest zrobiona; masz zrobić **Fazę B**. Pracuj **na istniejącej gałęzi
`feat/438-konsolidacja-wydzial-jednostka`** (NIE zakładaj nowej) w worktree
`~/Programowanie/bpp-438-konsolidacja`.

### Zanim cokolwiek zrobisz — przeczytaj (to źródło prawdy)
- **Spec/design:** `docs/superpowers/specs/2026-07-02-konsolidacja-wydzial-jednostka-design.md`
  — czytaj CAŁOŚĆ, a zwłaszcza sekcje: „Plan migracji danych" (Faza B: kroki
  B0–B10), „Pułapki implementacyjne", „Decyzje z recenzji adwersaryjnej",
  „Zasady niepodważalne" (#4 = federacja), „Routing zgłoszeń", „Multiseek/DjangoQL".
- **Plan Fazy A (zrobiony):** `docs/superpowers/plans/2026-07-04-konsolidacja-faza-A.md`
- **Ledger poprzedniej sesji:** `.superpowers/sdd/progress.md` (gitignored, w worktree)
  — historia Fazy A + lista rzeczy deferowanych do Fazy B.

### Metoda pracy (obowiązkowa)
1. Najpierw `superpowers:writing-plans` dla Fazy B. **Faza B jest duża i
   ryzykowna** (atomowy release kod+schemat, ścisła kolejność migracji, drop
   kolumn/triggerów, przepisanie 4 podsystemów raportowych) — rozważ podział na
   2–4 pod-plany zamiast jednego mega-planu, ALE pamiętaj że kroki B4→B6 muszą
   lecieć w jednym release (patrz niżej).
2. Potem `superpowers:subagent-driven-development` (implementer→task-review→fix
   per zadanie; standardowe modele Opus/Sonnet/Haiku; NIE fable dla implementacji).
3. **Przed implementacją migracji** — puść adwersaryjne review kolejności B0–B10
   czystym subagentem fable (kolejność jest krytyczna, łatwo o subtelny błąd).
4. Po implementacji: PR (ten sam, #442, albo nowy — decyzja usera), weryfikacja
   CI do zielonego (realne gejty: `Tests (sharded)`, `Build test-runner image`,
   `Lint changed files`), potem czyste code-review PR-a przez fable.

### Co Faza A już zrobiła (stan gałęzi, migracje 0448–0452)
- Model `RodzajJednostki` (słownik + flagi `wyklucz_z_rankingu_autorow`,
  `pokazuj_jako_odrebna_sekcje`) + seed (Standard/Koło naukowe/Wydział) + admin.
- `Jednostka.rodzaj` (FK→RodzajJednostki, `on_delete=PROTECT`) **obok** starego
  `rodzaj_jednostki` (CharField, ZOSTAJE do Fazy B) + backfill istniejących wierszy.
- Pola per-węzeł na `Jednostka`: `zezwalaj_na_ranking_autorow` (default True),
  `poprzednie_nazwy`, `skrot_nazwy`, `legacy_wydzial_id` (nullable, indeks);
  `slug` poszerzony do 512.
- Fix wycieku `widoczna=False`: API `JednostkaViewSet`→`widoczne()`,
  `JednostkaSitemap`→`widoczne()`, oraz `JednostkaAutocomplete` (edytorski,
  `/bpp/jednostka-autocomplete/`) dostał `LoginRequiredMixin`. Publiczne warianty
  (`WidocznaJednostkaAutocomplete`, `PublicJednostkaAutocomplete`) dziedziczą z
  ungated `_JednostkaAutocompleteBase` + mają `UczelniaScopedAutocompleteMixin`.
- Komendy: `waliduj_konwersje_wydzialow` (read-only skan kolizji
  nazwa/skrot/slug/skrot_nazwy/pbn_id + ujemna kolejnosc + zamkniecie w
  przyszłości; wyklucza już-skonwertowane po `legacy_wydzial_id`),
  `konwertuj_wydzialy_na_jednostki` (idempotentna po `legacy_wydzial_id`,
  tworzy UKRYTE węzły `widoczna=False/aktualna=False`, MPTT-poprawnie).
- **`Wydzial` NIETKNIĘTY.** Nic nie usunięto. Węzły-wydziały są ukryte.

### Faza B — zakres (z spec, kolejność KRYTYCZNA)
To atomowy release kod+schemat. Skrót kroków (szczegóły w spec):
- **B0:** DROP wszystkich 3 triggerów struktury PRZED konwersją historii
  (trigger przeżywa RenameModel i wywali pierwszy zapis). + re-run A2/A3 dla
  obiektów z okna A→B.
- **B1:** `Jednostka_Wydzial` → `Jednostka_Rodzic`: `RenameModel` + AddField
  `parent` (FK→Jednostka, nullable) + backfill po `legacy_wydzial_id` +
  RemoveField `wydzial`. `related_name` zmienia się (`jednostka_wydzial_set`→
  `jednostka_rodzic_set`; użycia w `fixtures/conftest_models.py` + testy).
- **B2:** `parent` tylko gdy `IS NULL` + reguła konfliktu; `otwarcie`/`zamkniecie`
  wydziału → WŁASNY wpis `Jednostka_Rodzic` węzła (`parent=NULL`, od/do);
  historia sub-jednostek przepisana na krawędź faktycznego rodzica z zachowaniem
  od/do (NIE kasować, NIE zostawiać na wydziale). Inwariant: bieżący wpis
  (`do IS NULL`).parent == żywy MPTT parent.
- **B3:** przepięcie 8 FK konsumentów na `węzeł(legacy_wydzial_id)`:
  `Kierunek_Studiow` (PROTECT — PRZED czymkolwiek), `Patent`, `opi_2012`,
  `Zgloszenie`, `Obslugujacy_Zgloszenia_Wydzialow`, `import_dyscyplin`.
- **B4:** redefinicja **6 widoków sum** (`bpp_nowe_sumy_*_view` + unia) PRZED
  RemoveField (JOIN-ują `bpp_wydzial`/`wydzial_id`). `Nowe_Sumy_View.unique_together` też.
- **B5:** `denorm drop` + **usuń `wydzial_id` z `@depend_on_related` w
  `praca_doktorska.py:76`**. **NIE odtwarzaj walidacji uczelni** (federacja,
  Zasada #4 — jednostka może przechodzić między uczelniami).
- **B6:** re-backfill `rodzaj` (`WHERE rodzaj IS NULL`) → potem `RemoveField
  Jednostka.wydzial` + usunięcie `rodzaj_jednostki` (CharField). RAZEM z kodem
  przestającym je czytać (default manager `select_related("wydzial")`,
  `__str__`, admin, cache, raporty, multiseek). To sedno atomowości.
- **B7:** `denorm init` (regeneracja bez `wydzial_id`).
- **B8:** `przelicz_aktualna` (brak historii → True) + flip `widoczna` wg
  `Wydzial.widoczny` (JOIN po `legacy_wydzial_id`) + `Jednostka.aktualna`
  default→True + seed `wchodzi_do_raportow=True` dla byłych wydziałów.
- **B9:** migracja WARTOŚCI zapisanych multiseek (PK wydziału→PK węzła po
  `legacy_wydzial_id`; `RodzajJednostkiQueryObject` mapuje LABELS nie kody).
- **B10:** przepisanie konsumentów: raporty (`get_descendants`, „rozbij na
  bezpośrednie dzieci"/rooty uczelni bo Uczelnia NIE jest węzłem MPTT, filtr
  sekcji po `wchodzi_do_raportow` NIE po rodzaju), admin (filtr `parent`),
  browse (301 z `bpp:browse_wydzial`), API (`/api/v1/wydzial/` deprecated),
  `system.py` (grupy uprawnień bez Wydzial + wyczyść osierocone ContentType/
  Permission), routing zgłoszeń (`emaile_dla_wydzialu(jednostka.wydzial)` →
  po korzeniu drzewa **pierwszej jednostki autora z `skupia_pracownikow=True`**,
  `get_root()`), usunięcie bramkowania `uzywaj_wydzialow` (pole modelu
  `Uczelnia.uzywaj_wydzialow` + env `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW`;
  `__str__` dokleja skrót RODZICA gated tylko `SKROT_WYDZIALU_W_NAZWIE`).
- **Faza C (osobno, później):** drop `Wydzial`, drop `legacy_wydzial_id` (dopiero
  po końcu deprecation API), rebuild cache, baseline.

### Decyzje już zamrożone (nie otwieraj ich ponownie)
- **Federacja:** brak constraintu „uczelnia rodzica == dziecka".
- **`aktualna` derywowana z dat historii** (nie manualna); brak historii → True.
  Trzy OSOBNE osie: `aktualna` (derywowana) / `widoczna` (ręczna) / `wchodzi_do_raportow` (ręczna).
- **Marker wydziału NIE ISTNIEJE** — raporty biorą poddrzewo wybranego węzła;
  filtr sekcji po `wchodzi_do_raportow`, nie po rodzaju.
- **Flaga `uzywaj_wydzialow` USUWANA** całkowicie.

### Deferowane z Fazy A do wchłonięcia w Fazie B
- `nowe_raporty/poziomy.py` — `_pole()` ma `queryset=model.objects.all()`; anonim
  może POST-em wskazać pk ukrytej jednostki (walidacyjny wyciek, pre-existing).
  Zawęzić do `widoczne()`. (Sam widget URL już naprawiony w Fazie A na
  `public-jednostka-autocomplete`.)
- `Jednostka.rodzaj` bez `verbose_name`; nowe pola per-węzeł nieeksponowane w
  `JednostkaAdmin` — dodać.
- `konwertuj_wydzialy_na_jednostki`: `exists()` per wydział (N+1) + brak listy
  pominiętych w output — kosmetyka.

### PUŁAPKI PROCESOWE (nauczone w Fazie A — MUSISZ o nich pamiętać)
1. **`dev` to RUCHOMY CEL.** W trakcie Fazy A `origin/dev` pojechał 312 commitów
   do przodu, a PR #440 (fd390) wmergował się w połowie pracy → **dwukrotny
   konflikt liści migracji na CI**. ZANIM zaczniesz: `git fetch origin dev &&
   git merge origin/dev`. Przed KAŻDYM pushem sprawdź, czy dev nie doszedł;
   jeśli tak — re-merge + ewentualna renumeracja migracji. Lokalny `dev` usera
   bywa nieaktualny — ufaj `origin/dev`, nie lokalnemu.
2. **Numeracja migracji:** Faza A kończy na `0452`. Najświeższy liść na
   `origin/dev` to obecnie `0447_fd390_aktualna_jednostka_demote_obca` (sprawdź
   `ls src/bpp/migrations/ | tail` na aktualnym dev — mógł się zmienić!). Twoje
   migracje Fazy B numeruj PO faktycznym liściu; przy kolizji przenumeruj
   (descending `git mv` + popraw `dependencies`), jak robił to dev dla fd390.
3. **Pełna suita lokalnie to nieodzowny gejt** — per-task review NIE łapie
   błędów integracyjnych. W Fazie A pełna suita złapała: (a) kolizję kolekcji
   pytest (moduł `test_x.py` vs pakiet `test_x/` o tej samej nazwie — NIE twórz
   `test_management_commands/`), (b) ruff I001 (import sort) na zmienionych
   plikach. Odpalaj `make tests-without-playwright` przed pushem.
4. **CI: nie ciesz się z zielonego, dopóki `Tests (sharded)` (wszystkie shardy),
   `Build test-runner image` i `Lint changed files` nie są `success`.** Skip <1min
   ≠ pass. `pull_request`-owy workflow NIE ruszy przy konflikcie merge (DIRTY) —
   bo GitHub nie tworzy merge-refa; jak `Tests` nie startuje, sprawdź mergeState.
5. **`uv run` przed KAŻDYM Pythonem.** Testy same stawiają PG/Redis
   (testcontainers) — NIE `docker compose up`, nie zostawiaj kontenerów.
6. **Baseline:** NIE odświeżaj w trakcie; `make baseline-update` RAZ, przy
   scalaniu całości (Faza B mocno zmienia schemat).
7. **Nie modyfikuj istniejących migracji.** Tylko nowe.

### Środowisko (skrót)
- Worktree: `~/Programowanie/bpp-438-konsolidacja`, gałąź
  `feat/438-konsolidacja-wydzial-jednostka`.
- Testy: `uv run pytest <ścieżka>`; pełna suita: `make tests-without-playwright`.
- Migracje/check: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp --check --dry-run` / `... check`.
- Lint: `git diff --name-only origin/dev...HEAD -- '*.py' | xargs uv run ruff check` (+ `ruff format --check`).

Zacznij od przeczytania spec-a (Faza B) i `superpowers:writing-plans`.
