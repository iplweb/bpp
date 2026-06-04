# Self-review — per-uczelnia sloty (write-side)

> **⚠️ SUPERSEDED (2026-06-04).** Ten self-review jest PRZETERMINOWANY — opisuje
> stan na swoją datę. Jego otwarte MEDIUM/LOW zostały od tego czasu domknięte:
> NOT NULL na `Cache_Punktacja_Dyscypliny.uczelnia` (commit `6c888f245`, mig
> `0428`), indeks `(rekord_id, uczelnia, dyscyplina)` (mig `0427`), ekspozycja
> `uczelnia` w widoku (mig `0426`), `wiele_hst`/HST per-uczelnia (`c687ceb07`).
> Twierdzenia „NOT NULL niemożliwe" / „widok nie eksponuje uczelni" / „brak
> indeksu" już NIE są prawdą. Aktualny przegląd całości: Audyt 4a w
> `docs/superpowers/2026-06-03-audyty-multihosted-4x.md`. Trzymane jako zapis
> historyczny.

Data: 2026-06-03. Gałąź: `feature/multi-hosted-config`.
Zakres: `git diff 58daf3e1c..HEAD` na `src/bpp/models/sloty/`,
`src/bpp/models/cache/punktacja.py`, `src/bpp/models/abstract/disciplines.py`,
migracje `0424` (FK uczelnia) i `0425` (widok SQL).

Metoda: trzy niezależne przebiegi — (a) inline adversarial (main agent),
(b) subagent `feature-dev:code-reviewer`, (c) headless `claude -p`. Codex padł
na konfiguracji konta (model `gpt-5.3-codex` niedostępny), opencode wygenerował
treść ale nie zapisał pliku (nie uszanował write-directive) — pominięte.

Spec: `docs/superpowers/specs/2026-06-02-per-uczelnia-sloty-design.md`.

---

## Werdykt

Write-side jest **poprawny i zgodny ze spec**. Brak bugów CRITICAL/HIGH.
Partycja dzielnika `k`/`m` jest szczelna, invariant single-install trzyma.
Jeden konkretny **łamacz reguły projektu** (edycja zacommitowanej migracji) do
naprawy. Reszta to hardening pod nadchodzącą fazę multi-install/read-side.

## Konsensus (potwierdzone niezależnie przez 2–3 źródła) — POPRAWNE

1. **Partycja dzielnika k/m — szczelna.** Każdy odczyt autorów idzie przez
   `SlotMixin._autorzy_qs()` (filtr `jednostka__uczelnia` gdy uczelnia ustawiona);
   jedyny bezpośredni `autorzy_set` w `_zapisz` (core.py:414) też ma filtr.
   `grep autorzy_set src/bpp/models/sloty/` → tylko te dwa miejsca. (3/3)
2. **Invariant single-install — trzyma, bo `Jednostka.uczelnia` jest NOT NULL**
   (jednostka.py:93). Przy jednej uczelni wszystkie jednostki (w tym „obce")
   wskazują na nią → filtr `jednostka__uczelnia` to no-op → `m` bez zmian →
   liczby identyczne. Fast-track `Uczelnia.objects.all()[:2]`/`len==1` bezpieczny.
   **To jest load-bearing**: gdyby FK kiedyś stał się nullable, invariant cicho
   pęka. (3/3)
3. **Sieroty — sprzątane.** `removeEntries()` kasuje cały rekord (obie tabele)
   przed rebuildem; `rebuildEntries()` liczy tylko bieżące `uczelnie_rekordu()`.
   Test „wypadnięcie uczelni" (`c769576c6`) pokrywa. (3/3)
4. **Determinizm `serialize()` — OK w praktyce.** `order_by(..., "pk")` jako
   tie-breaker; klucz `(rekord, uczelnia, dyscyplina)` unikalny, więc pk realnie
   nie rozstrzyga; string stabilny między rebuildami mimo nowych pk. Test
   `test_przelicz_zwrotka_deterministyczna`. (3/3)
5. **Write-path nigdy nie tworzy NULL uczelnia_id** — `_zazpisz` zawsze podaje
   `uczelnia=` z `_uczelnie_do_przeliczenia`. NULL pochodzi tylko z legacy/fixtures.
   (me + claude)

## Do naprawy / decyzji

### [RULE→ROZWIĄZANE 2026-06-03] Edycja zacommitowanej migracji 0425 (claude)
`0425_per_uczelnia_cache_view.py` powstała w `5c82a43cf` (strict join
`AND d.uczelnia_id = j.uczelnia_id`), a `c74e4aba5` ZMODYFIKOWAŁ ją na
`AND (d.uczelnia_id = j.uczelnia_id OR d.uczelnia_id IS NULL)` — łamiąc regułę
CLAUDE.md „NEVER modify existing migration files".
**Decyzja usera:** 0425 NIE jest nigdzie wypchnięte/zaaplikowane (multi-install
istnieją, ale bez publikacji), więc edycja in-place jest świadomie dozwolona dla
tego konkretnego przypadku. Zamiast band-aida `IS NULL` migracja ma „robić dobrze".
**Zrobione:** 0425 przebudowane na:
- `RunPython backfill_uczelnia`: 1 uczelnia → wpisz jej ID do
  `Cache_Punktacja_Dyscypliny.uczelnia_id IS NULL` (legacy); są NULL-e a uczelni
  ≠ 1 → `raise RuntimeError` (głośny fail, dzielnik per-uczelnia nie do zgadnięcia);
  świeża baza bez NULL-i → no-op (przechodzi),
- widok wraca do **STRICT** (`AND d.uczelnia_id = j.uczelnia_id`, bez `IS NULL`),
- fixture `raport_slotow/tests/conftest.py` ustawia teraz `uczelnia=jednostka.uczelnia`
  (jedyny runtime tworzący CPD bez uczelni; produkcyjny `_zapisz` zawsze ustawia).
Weryfikacja: 151 testów zielonych (raport_slotow + test_per_uczelnia + test_sloty),
`makemigrations --check` bez dryfu w `bpp`, ruff czysty. NOT NULL na `uczelnia`
nadal niemożliwe (fixtures tworzą NULL w runtime) — zostaje na read-side.

### [MEDIUM] `_dopasuj_kalkulator` liczy `wiele_hst`/próg globalnie (me + subagent)
`rodzaje_hst` z `wszystkie_dyscypliny_rekordu()` (WSZYSTKIE uczelnie), a kalkulator
używany per-uczelnia. Rekord cross-uczelnia mieszający HST/nie-HST ponad granicą
uczelni → każda uczelnia dziedziczy globalne `wiele_hst`, choć w jej obrębie
dyscypliny są jednorodne. Spec uznaje wybór progu za uczelnia-niezależny, ale
**brak testu** dla HST-U1 + nie-HST-U2 i efekt jest nieoczywisty (mnożnik HST).
Single-install bez wpływu. **Akcja:** test graniczny + jawny komentarz/decyzja
domenowa w read-side/federacji.

### [MEDIUM] Widok `OR uczelnia_id IS NULL` — nie wymuszony constraintem (me + subagent; claude: bezpieczny w normalnej pracy)
Bezpieczny dopóki per-rekord wiersze są jednego „pokolenia" (atomowy remove +
non-null rebuild gwarantuje). Ale mieszany stan (częściowy backfill / ręczna
ingerencja) → kartezjan w widoku; `test_widok_nie_duplikuje` nie pokrywa mieszanki.
**Akcja:** po backfillu migracja zacieśniająca `uczelnia` do NOT NULL + usunięcie
gałęzi `IS NULL` (przywraca strict), ewentualnie test mieszanego pokolenia.

### [MEDIUM] Brak indeksu złożonego `(rekord_id, uczelnia, dyscyplina)` (subagent)
0424 dodaje tylko `(uczelnia, dyscyplina)`; spec chciał `(rekord_id, uczelnia,
dyscyplina)` pod join widoku. To też naturalny klucz funkcjonalny tabeli.
**Akcja:** `UniqueConstraint`/`Index` w nowej migracji (przy okazji 0426).

### [LOW/design] Mutacja `kalk.uczelnia` po konstrukcji (subagent)
`ISlot` robi `kalkulator.uczelnia = uczelnia` po `_dopasuj_kalkulator`. Bezpieczne
TYLKO dlatego, że instancja jest świeża (brak skażenia `cached_property dyscypliny`
/ `_liczba_k_cache`). Tykająca mina, gdyby ktoś zmienił uczelnię po fakcie.
**Akcja (opcjonalna):** `uczelnia` jako wymagany arg konstruktora kalkulatora.

### [LOW/pre-existing] Asymetria `skupia_pracownikow` (subagent)
`_zapisz` filtruje `wa.jednostka.skupia_pracownikow` (CPA), ale `autorzy_z_dyscypliny`
(→ `k`, → `autorzy_z_dyscypliny` w CPD) nie. CPD może listować PK autora bez
odpowiadającego wiersza CPA. Pre-existing, nie wprowadzone tą zmianą; istotne dla
read-side (zaskoczenie konsumenta). **Akcja:** udokumentować albo zrównać.

## Pominięte/odrzucone
- pk-tie-breaker jako źródło „wiecznie brudnego" denorm — odrzucone: klucz
  unikalny, iteracja stabilna (konsensus 3/3, mój wcześniejszy LOW wycofany).
