# NEXT SESSION — ewaluacja_metryki per-uczelnia (spec D) — do wklejenia po resecie

> Wklej sekcję „PROMPT DO WKLEJENIA" jako pierwszą wiadomość po resecie sesji.
> Reszta to kontekst, który agent doczyta.

---

## PROMPT DO WKLEJENIA

Jesteś świeżą sesją. Repo: `~/Programowanie/bpp-multi-hosted-config`, gałąź
`feature/multi-hosted-config` (BPP, Django, instalacja wielouczelniana). Cały
read-side publiczny (R3a widoki + R3b autocomplety), sloty write/read (R1),
ewaluacja_liczba_n (R2), integrator, HST, verify.py oraz drobiazgi audytowe
(B1–B5) są ZROBIONE i wypushowane — pełny stan w
`docs/superpowers/HANDOFF-multi-hosted.md` (przeczytaj NAJPIERW).

Teraz nowy wątek: **ewaluacja_metryki per-uczelnia (wątek D)**. Chcę, żeby
liczenie „liczby N" ORAZ metryki ewaluacyjne były per-uczelnia. To wymaga
**spec-a** — przejdź ścieżką brainstorming → spec → plan → subagent-driven
(jak poprzednie wątki). Zacznij od `superpowers:brainstorming`. NIE pisz kodu
przed zatwierdzeniem spec-a.

Zanim zadasz pytania, zrób krótki recon (read-only): `src/ewaluacja_metryki/`
(modele, `utils.py`, `tasks.py`, `views/`, `management/commands/oblicz_metryki.py`,
`export_helpers.py`) — żeby pytania były konkretne. Najważniejsze fakty (do
potwierdzenia w kodzie) są w sekcji KONTEKST niżej.

Reguły: `uv run` zawsze; testy `-p no:cacheprovider` (testcontainers, Docker
musi działać); guard `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q`;
lint `uv run ruff check` ORAZ `uv run ruff format --check` (NIE `--fix`);
commit/push tylko na moją prośbę.

---

## KONTEKST (stan na 2026-06-04, agent może doczytać)

### Co to za wątek i dlaczego
`ewaluacja_metryki` liczy metryki ewaluacyjne autorów (m.in. „liczba N",
średnie udziały, bonusy). R2 (`ewaluacja_liczba_n`) zawęził już **źródło**
udziałów per-uczelnia (FK `uczelnia` na `IloscUdzialowDlaAutoraZaRok/ZaCalosc`,
cały pipeline `ewaluacja_liczba_n/utils.py`). ALE **konsument** w
`ewaluacja_metryki` czyta te udziały i pisze metryki **globalnie** — więc w
multi-install metryki mieszają uczelnie.

### Luki (zweryfikowane — Audyt 2 + 4c)
1. **`MetrykaAutora` (`ewaluacja_metryki/models.py:9`) NIE ma FK `uczelnia`.**
   `unique_together = [("autor", "dyscyplina_naukowa")]` (models.py:115) — bez
   uczelni. W multi-install autor afiliowany do >1 uczelni nie ma rozłącznych
   metryk per uczelnia (kolizja unique_together). Pola: `autor`,
   `dyscyplina_naukowa`, `jednostka` (FK), brak `uczelnia`.
2. **Globalne odczyty `IloscUdzialowDlaAutoraZaCalosc.objects.all()`:**
   `tasks.py:231`, `tasks.py:357`, `utils.py:277`, `oblicz_metryki.py:132`,
   `views/generation.py:74` — liczą metryki ze WSZYSTKICH uczelni naraz.
3. **Globalny rebuild `MetrykaAutora.objects.all().delete()`:** `utils.py:556`,
   `tasks.py:245-246` — kasuje metryki wszystkich uczelni przy przeliczaniu jednej.
4. **Globalne odczyty `MetrykaAutora.objects.all()`** (eksport/statystyki):
   `export_helpers.py:11,357`, `views/statistics.py:50`. Te są read-side widoków
   — powinny filtrować po uczelni oglądającego (`get_for_request`).
   Uwaga: liczne `MetrykaAutora.objects.filter(autor=...)` (per-autor, transitive,
   np. `views/detail.py`, `views/list.py`, `export.py`, `pin_unpin.py`) są
   prawdopodobnie OK (zawężone przez autora) — do oceny w recon.

### Kształt rozwiązania (wzorzec R2 — `ewaluacja_liczba_n`)
To jest **write+read**, bliżej R2 niż filtrów odczytu. Analogicznie do R2:
- **FK `uczelnia` na `MetrykaAutora`** (+ poprawić `unique_together` na
  `("autor","dyscyplina_naukowa","uczelnia")`) + migracja + backfill: single →
  domyślna uczelnia; multi-z-danymi → **fail** (jak mig `0009` w R2 / `0425`
  w write-side). NIGDY nie modyfikuj istniejących migracji.
- **Pipeline liczenia** (`utils.py`, `tasks.py`, `oblicz_metryki.py`) zawężony
  per uczelnia: odczyt `IloscUdzialow*` po `uczelnia`, atrybucja autora przez
  `aktualna_jednostka.uczelnia` (reguła R2, niżej), delete/rebuild scoped per
  uczelnia (naprawić globalny `objects.all().delete()`).
- **Generation task** (`generuj_metryki_task` w `tasks.py`) — przyjmuje
  `uczelnia_id` (część liczba_n już go ma; rozszerzyć na metryki). Tło →
  `Uczelnia.objects.get_for_pbn_background(uczelnia_id)` / `.get()` single-or-fail,
  NIGDY `get_default`/`get_for_request`.
- **Widoki read-side** (list/detail/statistics/export, `export_helpers.py`)
  filtrują `MetrykaAutora` po `uczelnia_dla_odczytu(request)` (helper z R1,
  hybryda site+superuser; `src/raport_slotow/uczelnia_helper.py`).

### Reguła atrybucji autora do uczelni (binarna, projektowa)
`autor.aktualna_jednostka.uczelnia`, tylko gdy `jednostka.skupia_pracownikow=True`
(NULL/obca jednostka → autor wykluczony). To reguła R2/verify; dla METRYK
(write-side liczenia) prawdopodobnie ta sama. Read-side widoków → filtr po
uczelni oglądającego.

### Niezmiennik
Single-install: backfill wpisuje domyślną uczelnię, filtry stają się no-op →
liczby/metryki identyczne jak dziś. Wszystkie testy regresyjne metryk muszą
przejść. Wzorzec guardu `Uczelnia.objects.count()==1` jak w R3a
(`bpp/util/uczelnia_scope.tylko_jedna_uczelnia`).

### Infrastruktura testowa (gotowa, używaj jej)
`fixtures.conftest_multisite` (zarejestrowana jako pytest plugin w
`src/conftest.py`): fixtury `uczelnia1/2`, `site1/2`, `jednostka_uczelnia1/2`,
`autor_uczelnia1/2`, helper `make_request_for_site(site)` (odpala
`SiteResolutionMiddleware` → ustawia `request._uczelnia`; w testach widoków
ustaw `settings.ALLOWED_HOSTS=["*"]`). Wzorzec testu izolacji: 2 uczelnie,
asercja pozytywna+negatywna (moja jest, obca nie).

### Dokumenty referencyjne
- Spec R2 (wzorzec): `specs/2026-06-03-ewaluacja-liczba-n-per-uczelnia-design.md`
- Plan R2: `plans/2026-06-03-ewaluacja-liczba-n-per-uczelnia-R2.md`
- Write-side (FK+backfill+migracja 0425 wzorzec): `specs/2026-06-02-per-uczelnia-sloty-design.md`
- Audyty (znaleziska D): `2026-06-03-audyty-multihosted-4x.md` (Audyt 2 #5, Audyt 4c)
- Master: `HANDOFF-multi-hosted.md`

### Decyzje do rozstrzygnięcia w brainstormingu (przykładowe pytania)
- Czy „liczba N" w tytule = to co R2 (`LiczbaNDlaUczelni`, już per-uczelnia) czy
  coś jeszcze w metrykach? (potwierdzić zakres — może część już zrobiona w R2).
- Czy `MetrykaAutora.jednostka` wystarcza do wyprowadzenia uczelni (jednostka→uczelnia)
  zamiast nowego FK? (rozważyć — ale unique_together i tak wymaga uczelni jawnie;
  jednostka może być NULL).
- Read-side eksportów/statystyk: filtr po uczelni oglądającego czy zostawić
  globalne dla superusera (jak hybryda R1)?
- Zakres widoków: które `MetrykaAutora.objects.filter(autor=...)` są już-zawężone
  (transitive) a które wymagają jawnej uczelni.
