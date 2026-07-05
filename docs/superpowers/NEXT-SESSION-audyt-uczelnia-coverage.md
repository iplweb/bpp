# NEXT SESSION — audyt pokrycia multi-hosted (get_default + brakująca uczelnia)

> Cel sesji: **zweryfikować, że WSZYSTKIE miejsca, gdzie był `Uczelnia.objects.get_default()`/`.default`
> ALBO gdzie uczelnia NIE była podawana mimo że potrzebna, są naprawione** —
> a to co zostaje, jest świadomie odłożone (z uzasadnieniem), nie zapomniane.
> Wklej sekcję „PROMPT DO WKLEJENIA" jako pierwszą wiadomość po resecie.

---

## PROMPT DO WKLEJENIA

Jesteś świeżą sesją. Repo: `~/Programowanie/bpp-multi-hosted-config`, gałąź
`feature/multi-hosted-config` (BPP, Django, instalacja **wielouczelniana** —
jedna instancja obsługuje wiele `Uczelnia`; żaden runtime nie może „zgadywać"
uczelni przez `get_default()` = pierwsza-z-brzegu, tylko używać właściwej; a
liczby/raporty mają być liczone i pokazywane **per uczelnia**).

Duże wątki są ZROBIONE i w PR #189 (→ `dev`): split PBN client, cleanup
`get_default` (+guard), write-side sloty, read-side R1, liczba_n R2, R3a/R3b
read-side publiczny, integrator, drobiazgi B1–B6, oraz najnowszy **D
(ewaluacja_metryki per-uczelnia)**. Pełny stan: `docs/superpowers/HANDOFF-multi-hosted.md`
(**przeczytaj NAJPIERW**).

**Twoje zadanie: AUDYT POKRYCIA, nie implementacja.** Zweryfikuj systematycznie,
że nie ma niezałatanego buga multi-hosted. To audyt **read-only** — NIE pisz kodu
ani nie commituj bez mojej zgody. Produkt końcowy: **raport** w
`docs/superpowers/2026-06-XX-audyt-uczelnia-coverage.md` z tabelą znalezisk
podzielonych na: ✅ naprawione / 🟡 świadomie odłożone (z uzasadnieniem) /
🔴 LUKA (zapomniane, wymaga naprawy) — z `plik:linia` dla każdego.

Są **DWIE klasy** buga, audytuj OBIE:

**Klasa 1 — `get_default()` / `objects.default` (łapie guard, ale zweryfikuj wpisy).**
Guard `src/bpp/tests/test_multihosted_get_default_guard.py` zamraża whitelistę
10 plików (każdy = świadoma decyzja). Dla KAŻDEGO wpisu whitelisty otwórz plik,
przeczytaj użycie i oceń, czy uzasadnienie nadal trzyma (świadomy fallback bez
requestu / None-tolerant warstwa modelu / display / guarded count==1 / komentarz),
czy to ukryta luka runtime która powinna dostać jawną uczelnię. Uruchom guard:
`uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q -p no:cacheprovider`
(musi być zielony). Sprawdź też, czy poza whitelistą faktycznie nic nie ma
(guard to robi, ale potwierdź regexem, że nie ma wariantów typu
`Uczelnia.objects.get_default ` z innym formatowaniem, albo aliasów managera).

**Klasa 2 — brakująca uczelnia tam, gdzie potrzebna (NIC tego nie łapie automatycznie).**
To trudniejsza, cichsza klasa. Szukaj w ścieżkach **runtime** (widoki, taski,
komendy, serializery API, context processors) wzorców:
- `<Model>.objects.all()` / `.filter(...)` BEZ filtra uczelni na modelach które
  są **partycjonowane per-uczelnia** — sprawdź które modele mają FK `uczelnia`
  (grep `uczelnia = models.ForeignKey` / `models.OneToOneField`) i prześledź ich
  odczyty/zapisy. Znane partycjonowane: `Cache_Punktacja_Dyscypliny`,
  `IloscUdzialowDlaAutoraZaRok/ZaCalosc`, `LiczbaNDlaUczelni`,
  `DyscyplinaNieRaportowana`, `MetrykaAutora`, `StatusGenerowania`,
  `PBN_Export_Queue`, `RaportSlotowUczelnia` (+ inne — zweryfikuj grepem).
- funkcje/metody liczące „per uczelnia", które NIE przyjmują `uczelnia`/`uczelnia_id`
  albo przyjmują, ale wołający go nie przekazuje (jak bug D: `generuj_metryki_task`
  miał `uczelnia_id`, ale nie przekazywał do `generuj_metryki` → globalny delete).
- globalne `.delete()` / `.update()` na partycjonowanych modelach (klasyczny
  data-corruption multi-hosted — patrz Audyt C niżej).
- widoki czytające bez `get_for_request` / `uczelnia_dla_odczytu`.

Reguły rozstrzygania uczelni (z poprzednich wątków — sprawdzaj zgodność):
- **runtime z requestem** → `Uczelnia.objects.get_for_request(request)` (write)
  / `uczelnia_dla_odczytu(request)` (read, hybryda + superuser `?uczelnia=`).
- **tło/CLI/Celery** → `Uczelnia.objects.get(pk=uczelnia_id) if uczelnia_id else
  Uczelnia.objects.get()` (single-or-fail) albo `get_for_pbn_background(id)`.
  NIGDY `get_default()` w runtime.
- **read-side** → guard single-install `tylko_jedna_uczelnia()` → filtr no-op
  przy 1 uczelni (wzorzec `bpp.util.uczelnia_scope`,
  `ewaluacja_metryki.uczelnia_scope.scope_metryki`,
  `raport_slotow.uczelnia_helper.uczelnia_dla_odczytu`).
- **atrybucja autora→uczelnia** (write liczeń) → `autor.aktualna_jednostka.uczelnia`
  tylko gdy `jednostka.skupia_pracownikow=True` (NULL/obca → wykluczony).

Najpierw zrób recon (read-only): przeczytaj HANDOFF + Audyt 4x
(`docs/superpowers/2026-06-03-audyty-multihosted-4x.md`) + guard. Następnie
**dispatch równoległych subagentów-audytorów** (np. po obszarach: `bpp/views`,
`bpp/models`, `api_v1`, `pbn_api`+`pbn_integrator`, `raport_slotow`+`ewaluacja_*`,
`powiazania_autorow`+reszta) — każdy zwraca strukturalną listę znalezisk klasy 2
ze statusem. Zsyntezuj w jeden raport. Skoryguj fałszywe alarmy (np. odczyt
zawężony tranzytywnie przez `autor_id`+`dyscyplina_id` jest OK; multiseek wyniki
świadomie NIE filtrowane — patrz R3a).

Reguły: `uv run` zawsze; audyt read-only (bez kodu/commitów bez zgody); raport
po polsku; ścieżki jako `plik:linia`.

---

## KONTEKST (stan 2026-06-04, agent doczyta)

### Co odróżnia tę sesję od poprzednich
Poprzednie wątki naprawiały **konkretne obszary** (sloty, liczba_n, metryki,
read-side publiczny, integrator). Ta sesja to **audyt poprzeczny**: czy gdzieś
między obszarami została luka — zwłaszcza klasy 2 (cicha brakująca uczelnia),
której żaden guard nie łapie. Bug D (znaleziony dopiero przy implementacji
metryk: `oblicz_metryki_dla_autora` sumował sloty wszystkich uczelni, bo R2
rozbił źródło, a konsument nie był zaktualizowany) to **dowód, że takie luki
istnieją na styku wątków** — szukaj analogicznych „konsument nie nadążył za
partycjonowaniem źródła".

### Guard get_default — whitelista do weryfikacji (10 wpisów, `src/bpp/tests/test_multihosted_get_default_guard.py`)
1. `bpp/middleware.py` (1) — świadomy fallback: Site istnieje, brak Uczelni.
2. `bpp/util/bpp_specific.py` (2) — docstring + fallback CLI/Celery bez requestu.
3. `bpp/models/abstract/pbn.py` (2) — linki PBN, metoda modelu bez requestu.
4. `bpp/models/jednostka.py` (1) — sortowanie (display).
5. `bpp/multiseek_registry/fields/numeric_fields.py` (1) — toggle IC, None-tolerant.
6. `ewaluacja2021/util.py` (1) — komentarz (nie kod; ewaluacja2021 = husk/wygaszane).
7. `pbn_api/management/commands/util.py` (1) — GUARDED count==1.
8. `pbn_import/templatetags/pbn_import_tags.py` (1) — request-first, fallback bez requestu.
9. `pbn_import/utils/command_helpers.py` (1) — CLI None-tolerant + CommandError.
(`bpp/models/sloty/core.py` i `abstract/disciplines.py` — get_default USUNIĘTY,
brak wpisu = świadomie; guard złapie powrót.)

Dla każdego: czy to naprawdę „display/fallback/CLI" czy ukryta ścieżka runtime?
ewaluacja2021 — potwierdź, że to martwy kod (web URL-e wyłączone wg HANDOFF).

### Znane ODŁOŻONE luki (status 🟡 — potwierdź, że nadal świadomie odłożone, nie zapomniane)
Z Audytu 4x (`docs/superpowers/2026-06-03-audyty-multihosted-4x.md`, sekcja C)
i HANDOFF:
- **Federacja `ewaluacja_optymalizacja`** (decyzja usera: OLANA jako logika
  federacyjna, ale **bugi KORUPCJI DANYCH** to integralność, nie federacja):
  - `OptimizationRun.delete()` cross-uczelnia (`tasks/optimization.py:73`),
  - `reset_all_pins_task`/`optimize_and_unpin` globalne querysety,
  - komparatory PBN globalny `.delete()`.
  - `StatusGenerowania.get_or_create()` **no-arg** w `ewaluacja_optymalizacja/
    views/unpinning_analysis.py:39,149` i `unpinning_list.py:137` (czyta wiersz
    `uczelnia=None`; to dlatego `StatusGenerowania.uczelnia` ZOSTAŁ nullable w D).
  Oceń: które z nich to czysta korupcja danych (do naprawy scope-fixem niezależnie
  od logiki federacyjnej), a które wymagają decyzji federacyjnej.
- **Multiseek wyniki** świadomie NIE filtrowane per-uczelnia (decyzja R3a) — OK.
- **`MetrykaAutora` transitive `Cache_Punktacja_Autora_Query`** (autor_id+dyscyplina_id)
  — świadomie zawężone tranzytywnie, rewizja należy do federacji (komentarze w
  `ewaluacja_metryki/views/detail.py`).

### Dokumenty referencyjne (źródła prawdy o tym co już zrobione)
- Master: `docs/superpowers/HANDOFF-multi-hosted.md` (sekcje „CO ZROBIONE",
  „ROADMAPA", „AUDYTY 4×", „Guard get_default: nadal szczelny").
- Audyt 4x: `docs/superpowers/2026-06-03-audyty-multihosted-4x.md`.
- Cleanup get_default (plan + reguła binarna): `plans/2026-06-02-get-default-cleanup.md`,
  `docs/deweloper/audyt-multihosted-pbn.md`.
- Specy per-obszar (wzorce poprawnego scopingu): write-side
  `specs/2026-06-02-per-uczelnia-sloty-design.md`; R1
  `specs/2026-06-03-per-uczelnia-sloty-read-side-design.md`; R2
  `specs/2026-06-03-ewaluacja-liczba-n-per-uczelnia-design.md`; R3a/b
  `specs/2026-06-03-r3a-*`, `specs/2026-06-03-r3b-*`; integrator
  `specs/2026-06-03-integrator-per-uczelnia-design.md`; D
  `specs/2026-06-04-ewaluacja-metryki-per-uczelnia-design.md`.
- Helpery scopingu (wzorzec do naśladowania/sprawdzania): `bpp/util/uczelnia_scope.py`,
  `raport_slotow/uczelnia_helper.py`, `ewaluacja_metryki/uczelnia_scope.py`.

### Definicja „done" tej sesji
Raport, w którym KAŻDE miejsce dotykające uczelni (oba klasy) ma jednoznaczny
status ✅/🟡/🔴 z `plik:linia`, lista 🔴 (luki do naprawy) jest jawna i
priorytetyzowana, a lista 🟡 (odłożone) ma uzasadnienie. Jeśli 🔴 = puste →
potwierdzenie, że pokrycie multi-hosted jest pełne (modulo świadomie odłożona
federacja). Implementację ewentualnych 🔴 ustalamy PO raporcie (osobny wątek
spec→plan→subagent jak poprzednio).
