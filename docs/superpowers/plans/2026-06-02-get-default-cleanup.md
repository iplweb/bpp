# Wytępienie `get_default` z runtime (multi-hosted) — plan implementacji

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Usunąć „zgadywanie" uczelni przez `Uczelnia.objects.get_default()` /
`.objects.default` ze wszystkich ścieżek runtime, tak by w instalacji
wielouczelnianej każda operacja używała WŁAŚCIWEJ uczelni (z requestu, z
argumentu, z obiektu nadrzędnego), a `get_default` pozostał wyłącznie tam, gdzie
jest świadomym, udokumentowanym wyborem albo strażowanym single-install.

**Architecture:** Trzy docelowe wzorce, dobierane per call-site:
1. **`get_for_request(request)`** — gdy w zasięgu jest request (widoki, formularze).
2. **Jawna `uczelnia` jako argument** — threadowana od wołającego, który ją zna
   (zadania Celery z `uczelnia_id`, `ImportSession.uczelnia`, FK na obiekcie).
3. **`Uczelnia.objects.get()`** — „jedyna albo wyjątek"; TYLKO dla CLI bez
   `--uczelnia-id` i testów single-install. Django samo rzuca
   `MultipleObjectsReturned` przy >1 (głośne ujawnienie braku przekazania
   uczelni) i `DoesNotExist` przy 0.

**Tech Stack:** Django 5.2, pytest + model_bakery, ruff (E/F/I/UP/B/W/C90/DJ).

---

## Reguła binarna (ustalona z userem 2026-06-02)

Każdy call-site trafia do JEDNEGO z dwóch kubełków — bez agonizowania:

1. **NIE MA PRAWA** mieć `get_default` — miejsca runtime, które budują klienta
   PBN / wpis kolejki / linkują dane do konkretnej uczelni, ALBO mają w zasięgu
   `request`. Fix: **jawna uczelnia** (threading od wołającego albo
   `get_for_request(request)`).
2. **Akceptowalne** — cała reszta (CLI bez `--uczelnia-id`, config-reads bez
   sensownego źródła uczelni, fallback adaptera). Cel: **`Uczelnia.objects.get()`
   i tyle.** Zwraca jedyną uczelnię; przy >1 rzuca `MultipleObjectsReturned`,
   przy 0 `DoesNotExist` — to GŁOŚNE ujawnienie, że (a) instalacja jest
   multi-hosted i (b) to miejsce trzeba awansować do kubełka „NIE MA PRAWA".

To rozstrzyga wszystkie wcześniejsze „DECYZJE" w tym dokumencie:
- **DECYZJA 1 (Faza 4 config-reads):** akceptowalne → `.get()`. Nie threadujemy
  na siłę; jeśli `.get()` kiedyś rzuci na multi-hosted, awansujemy to miejsce.
- **DECYZJA 2 (adapter fallback):** → `.get()` (nie usuwamy fallbacku, nie
  zostawiamy `get_default` — zamieniamy na `.get()`). Testy adaptera
  single-uczelnia dalej działają.
- **DECYZJA 3 (CLI):** → `.get()`.

---

## Zasada przewodnia (uzasadnienie całości)

`get_default()` = `self.all().first()` — **pierwsza-z-brzegu** uczelnia. W
single-install jest dokładnie jedna, więc to przypadkiem działa. W multi-hosted
to losowy strzał: operacja czyta konfigurację / linkuje dane / buduje klienta
PBN dla NIEWŁAŚCIWEJ uczelni. To nie jest teoretyczne — to było źródłem błędu
„403 token aplikacji null".

**Dlaczego NIE jeden globalny refactor „zamień get_default na get()":** w
hot-pathach bez requestu (np. sygnał denormalizacji przy KAŻDYM zapisie
publikacji) `Uczelnia.objects.get()` rzuciłby `MultipleObjectsReturned` na
multi-hosted instalacji → **crash przy zapisie**. Te miejsca wymagają
*threadingu* uczelni od wołającego, a nie podmiany akcesora. Dlatego plan jest
podzielony per-kategoria, z różnymi wzorcami i różnym ryzykiem.

**Kryterium ukończenia każdej fazy:** zielony `ruff check` na zmienionych
plikach + `manage.py check` + celowany podzbiór testów + (gdzie to ma sens)
test regresji multi-hosted w stylu `src/pbn_api/tests/test_multihosted.py`
(dwie uczelnie → właściwa steruje wynikiem; failowałby przed fixem).

---

## Mapa plików (co i dlaczego dotykamy)

**Zostają nietknięte (świadome/strażowane) — UZASADNIENIE, czemu to NIE bug:**
- `bpp/models/uczelnia.py:31` — *definicja* `get_default` oraz `:44/70/75/81`
  (wewnętrzne resolwery `get_for_request`/`get_for_site`/`default`/
  `do_roku_default`). To źródło, nie call-site.
- `pbn_api/management/commands/util.py:54` — strażowane `if count == 1:`,
  inaczej `CommandError`. To jest WZORZEC, który chcemy replikować w CLI.
- `bpp/middleware.py:295` — fallback gdy `Site` istnieje, ale nie ma powiązanej
  `Uczelni`. Świadomy edge-case przy rozwiązywaniu uczelni Z requestu (to nie
  jest „zgadywanie zamiast requestu" — to ostatnia deska gdy mapowanie
  Site→Uczelnia jest niekompletne).
- `bpp/util/bpp_specific.py:104` — `site_url_for_request`, request-first, fallback
  tylko gdy NIE ma requestu (CLI/Celery budujące absolutny URL). Udokumentowane.

**Fałszywy traf (NIE dotykać):** `bpp/admin/templates.py:57` —
`Engine.get_default()` to silnik szablonów Django, nie model `Uczelnia`.

---

## Faza 1 — Widoki i formularze z dostępem do requestu (niskie ryzyko)

**Uzasadnienie:** te call-site'y mają `request` (albo obiekt z `request`)
w bezpośrednim zasięgu. Zamiana na `get_for_request(request)` jest poprawna,
mechaniczna i nie zmienia zachowania single-install (get_for_request spada do
get_default gdy brak `request._uczelnia`). Zysk: multi-hosted czyta config
hosta, nie pierwszej uczelni.

**Files:**
- Modify: `src/importer_publikacji/views/steps.py:336`
- Modify: `src/zglos_publikacje/forms.py:316`
- Modify: `src/zglos_publikacje/models.py:254`
- Modify: `src/nowe_raporty/forms.py:92`
- Modify: `src/pbn_export_queue/views/detail_views.py:152`
- Modify: `src/pbn_api/models/publikacja_instytucji.py:68`
- Test: odpowiednie `tests/` w każdej z aplikacji

- [ ] **Step 1: Zlokalizuj źródło requestu w każdym pliku.**
  Dla każdego sprawdź, czy w funkcji/metodzie jest `request`/`self.request`
  (widoki, `detail_views`), `self.instance`+`request` (formularze), albo czy
  obiekt ma własny request. UWAGA per-plik:
  - `steps.py:336` (`_review_context`) — to funkcja widoku; potwierdź dostęp do
    `request` w sygnaturze i przekaż `get_for_request(request)`.
  - `forms.py:316` / `models.py:254` — formularz/`clean()`. Form NIE ma requestu
    domyślnie. Sprawdź, czy wizard wstrzykuje `self._uczelnia`/`request`
    (w `zglos_publikacje` może być `self.instance._uczelnia`). Jeśli NIE ma
    skąd wziąć — to NIE jest Faza 1, przenieś do Fazy 4 (decyzja).
  - `detail_views.py:152` — display-only URL do promptu AI; `self.request`
    dostępny → `get_for_request(self.request)`.
  - `publikacja_instytucji.py:68` — `self.uczelnia or get_default()`. To model
    z FK `uczelnia`; jeśli `self.uczelnia` jest, fallback nie odpala. Zostaw
    `self.uczelnia` a fallback usuń (gdy None — zwróć link bez api_root albo
    `None`), BO to tylko budowa URL-a do wyświetlenia.

- [ ] **Step 2: Napisz test regresji (przykład dla `detail_views`).**

```python
@pytest.mark.django_db
def test_detail_view_pbn_url_uzywa_uczelni_z_requestu(rf, admin_user):
    u1 = baker.make(Uczelnia, pbn_api_root="https://pbn-1/")  # „pierwsza"
    u2 = baker.make(Uczelnia, pbn_api_root="https://pbn-2/")
    assert Uczelnia.objects.get_default() == u1
    request = rf.get("/")
    request.user = admin_user
    request._uczelnia = u2  # host = u2
    # ... wywołaj kod budujący URL ...
    # assert że użyto pbn-2 (u2), nie pbn-1 (get_default)
```

- [ ] **Step 3: Zamień `Uczelnia.objects.get_default()` →
  `Uczelnia.objects.get_for_request(request)`** w każdym pliku (z właściwym
  źródłem requestu ustalonym w Step 1).

- [ ] **Step 4: Uruchom testy + ruff.**
  Run: `uv run pytest src/zglos_publikacje/ src/nowe_raporty/ src/pbn_export_queue/tests/ -q`
  oraz `uv run ruff check <zmienione pliki>`. Expected: PASS / All checks passed.

- [ ] **Step 5: Commit.**

```bash
git add src/importer_publikacji/views/steps.py src/zglos_publikacje/ \
  src/nowe_raporty/forms.py src/pbn_export_queue/views/detail_views.py \
  src/pbn_api/models/publikacja_instytucji.py
git commit -m "fix(multi-hosted): widoki/formularze czytaja uczelnie z requestu"
```

---

## Faza 2 — `importer_publikacji` dokończenie (wykorzystuje `ImportSession.uczelnia`)

**Uzasadnienie:** w Phase 7/pkt 2 dodaliśmy `ImportSession.uczelnia` (FK,
ustawiane z requestu). Dwa miejsca w `importer_publikacji` jeszcze go nie
wykorzystują, bo są w ścieżce Celery (bez requestu) — ale mają `session`
w zasięgu (bezpośrednio lub przez `_create_publication(session)`).

**Files:**
- Modify: `src/importer_publikacji/views/publikacja.py:125` (`_add_authors_to_record`)
- Modify: `src/importer_publikacji/views/steps.py:336` (jeśli nie pokryte Fazą 1)

- [ ] **Step 1:** Prześledź, czy `_add_authors_to_record` dostaje `session`
  lub `uczelnia`. `_create_publication(session)` → woła `_add_authors_to_record`.
  Przekaż `session.uczelnia` w dół (dodaj parametr `uczelnia` do
  `_add_authors_to_record`, przekazany z `_create_publication`).
- [ ] **Step 2:** Test: `create_publication_task` z `session.uczelnia=u2` →
  `obca_jednostka` brane z `u2`, nie z `get_default()=u1`.
- [ ] **Step 3:** `uczelnia = Uczelnia.objects.get_default()` →
  `uczelnia = session.uczelnia` (z fallbackiem tylko jeśli `session.uczelnia`
  może być None dla starych sesji — wtedy `or Uczelnia.objects.get()`? NIE —
  zostaw None i niech kod obsłuży brak, jak w innych miejscach).
- [ ] **Step 4:** Run: `uv run pytest src/importer_publikacji/tests/ -q`. PASS.
- [ ] **Step 5:** Commit `fix(multi-hosted): importer_publikacji uzywa session.uczelnia`.

---

## Faza 3 — Runtime PBN: `ImportManager` propaguje uczelnię (audyt WYSOKIE)

**Uzasadnienie:** to najgroźniejsza regresja z audytu. Zadanie `run_pbn_import`
POPRAWNIE wybiera uczelnię (`get_for_pbn_background(uczelnia_id)`,
`tasks.py:78/82`) i buduje klienta, ALE `ImportManager` nie przechowuje tej
uczelni. W efekcie `_execute_step` woła kroki bez uczelni →
`initial_setup.py:23` robi `get_default()` i **przebudowuje `self.client` na
klienta PIERWSZEJ uczelni**, a `import_manager.py:108`
(`_refresh_pbn_client_after_setup`) analogicznie. To NADPISUJE jawnie wybraną
uczelnię — czyli kasuje fix z `tasks.py`. Dodatkowo `author_import:18`,
`publication_import:79`, `institution_import:101` (dane: `pbn_uid_id`,
`obca_jednostka`) zgadują tą samą drogą.

**Files:**
- Modify: `src/pbn_import/utils/import_manager.py` (`__init__`, `_execute_step`,
  `_refresh_pbn_client_after_setup`, `:108`)
- Modify: `src/pbn_import/utils/initial_setup.py:23,31`
- Modify: `src/pbn_import/utils/author_import.py:18`
- Modify: `src/pbn_import/utils/publication_import.py:79`
- Modify: `src/pbn_import/utils/institution_import.py:101`
- Modify: `src/pbn_import/tasks.py` (przekaż uczelnię do `ImportManager`)
- Test: `src/pbn_import/tests/`

- [ ] **Step 1: Test (failujący przed fixem).** Dwie uczelnie; `run_pbn_import`
  z `uczelnia_id=u2.pk`; po `InitialSetup` `manager.client` ma transport z
  tokenem `u2`, nie `u1`. (Asercja na `client.transport`/`client.uczelnia`.)
- [ ] **Step 2:** `ImportManager.__init__(self, ..., uczelnia)` — przechowuje
  `self.uczelnia`. `_execute_step` przekazuje `self.uczelnia` do `step()`.
  `_refresh_pbn_client_after_setup()` używa `self.uczelnia` zamiast
  `get_default()`.
- [ ] **Step 3:** `InitialSetup.run(uczelnia=...)` — gdy `uczelnia` podana,
  NIE woła `get_default()`. `author/publication/institution_import` przyjmują
  `uczelnia` (już mają parametr `uczelnia=None` + `or get_default()` — usuń
  fallback, wymuś przekazanie z managera).
- [ ] **Step 4:** `pbn_import/tasks.py` — `ImportManager(..., uczelnia=uczelnia)`
  (uczelnia z `get_for_pbn_background(uczelnia_id)`, już jest na `:78`).
- [ ] **Step 5:** Run: `uv run pytest src/pbn_import/tests/ -q`. PASS.
- [ ] **Step 6:** Commit `fix(multi-hosted): ImportManager propaguje uczelnie do krokow importu`.

---

## Faza 4 — bpp config-reads w hot-pathach ⚠️ DECYZJA WYMAGANA

**To jest sedno „wolumenu" i NIE jest mechaniczne.** Te funkcje czytają
per-uczelnia config (`ukryte_statusy`, `sortuj_jednostki_alfabetycznie`,
`pokazuj_index_copernicus`, ustawienia liczenia slotów, `pbn_api_root` do
linków) i przyjmują `uczelnia=None` z fallbackiem `get_default()`. Część jest
w hot-pathie BEZ requestu.

**Files (call-site → dlaczego trudny):**
- `src/bpp/models/abstract/disciplines.py:18` (`przelicz_punkty_dyscyplin`) —
  **najtrudniejszy**: wołany z sygnału denormalizacji przy KAŻDYM zapisie
  publikacji. Brak requestu. `.get()` → crash na multi-hosted.
- `src/bpp/models/sloty/core.py:34` (`ISlot`) — liczenie slotów, brak requestu.
- `src/bpp/models/jednostka.py:46` (`get_default_ordering`) — sortowanie listy
  jednostek; wołane przy renderowaniu.
- `src/bpp/multiseek_registry/fields/numeric_fields.py:71` (`option_enabled`).
- `src/bpp/models/abstract/pbn.py:23,89` (`link_do_pbn`, `_format_link_pi`) —
  budują URL z `pbn_api_root`.

**❓ DECYZJA 1 — czym jest „uczelnia rekordu" w multi-hosted?**
Żeby threadować uczelnię do `przelicz_punkty_dyscyplin(rec)`/`ISlot(rec)`, musi
istnieć deterministyczne `rec → uczelnia`. Opcje:
- (a) **Dane są partycjonowane per-uczelnia** → uczelnia rekordu wynika z
  jego struktury (autor→jednostka→wydział→uczelnia). Wtedy threadujemy
  `rec.uczelnia` (wymaga zdefiniowania tej własności).
- (b) **Config slotów/dyscyplin jest efektywnie globalny** (jedna polityka
  ewaluacji na instalację, niezależnie od hosta) → wtedy `get_default()` jest
  semantycznie OK i te miejsca **zostają** (z komentarzem „config globalny").
- (c) **Hybryda** — część (linki `pbn_api_root`) per-uczelnia, część (sloty)
  globalna.

**Rekomendacja do akceptacji:** dla `abstract/pbn.py` (linki) — per-uczelnia
(opcja a, ale tylko URL, niski koszt). Dla `sloty`/`disciplines`/`jednostka`/
`multiseek` — **prawdopodobnie opcja b** (config ewaluacyjny/wyświetlania jest
instalacyjny, nie per-host), więc zostają z jawnym komentarzem zamiast cichego
`get_default`. **Potrzebuję Twojego potwierdzenia, czy w docelowym
multi-hosted te ustawienia różnią się per uczelnia.**

- [ ] **Step 1:** Rozstrzygnij DECYZJĘ 1 (z userem).
- [ ] **Step 2:** Dla miejsc „globalnych" — zostaw `get_default()`, ale dodaj
  komentarz `# config instalacyjny, nie per-host — get_default OK` (żeby
  następny audyt nie zgłaszał).
- [ ] **Step 3:** Dla miejsc per-uczelnia — zdefiniuj `rec → uczelnia`
  i threaduj; test multi-hosted.
- [ ] **Step 4:** Commit per podgrupa.

---

## Faza 5 — Runtime PBN: pozostałe buildery klienta i kolejka

**Uzasadnienie:** miejsca, które budują klienta PBN lub wpis kolejki z
`get_default()` w ścieżce runtime — bezpośrednie ryzyko złego konta PBN.

**Files:**
- `src/bpp/admin/helpers/pbn_api/cli.py:43` — `uczelnia or get_default()`
  w `sprobuj_wyslac_do_pbn_celery`. Caller `PBN_Export_Queue.send_to_pbn` ma
  `self.uczelnia` (FK na wpisie). Fix: przekaż `self.uczelnia` z modelu kolejki;
  usuń fallback.
- `src/pbn_integrator/utils/scientists.py:61,156` — buduje klienta z
  `get_default()` gdy `uczelnia=None`. Fix: wymuś `uczelnia` (caller integratora
  ją rozwiązuje); usuń fallback budujący klienta.
- `src/pbn_api/adapters/wydawnictwo.py:94` — fallback adaptera (patrz osobna
  dyskusja). DECYZJA 2: usunąć (wymaga migracji testów adaptera + `pbn_wyslij`
  z naprawą C901) czy zostawić defensywnie. Rekomendacja: zostawić defensywnie
  TERAZ (wszystkie runtime callerzy przekazują jawną uczelnię), usunąć w
  osobnym kroku „test cleanup".

- [ ] **Step 1:** Test multi-hosted dla `cli.py` (wpis kolejki z `u2` → klient
  z tokenem `u2`).
- [ ] **Step 2:** `PBN_Export_Queue.send_to_pbn` → przekaż `self.uczelnia` do
  `sprobuj_wyslac_do_pbn_celery`; w `cli.py:43` usuń `or get_default()`.
- [ ] **Step 3:** `scientists.py` — sygnatury wymagają `uczelnia` (bez
  fallbacku budującego klienta); zaktualizuj callerów w integratorze.
- [ ] **Step 4:** Run: `uv run pytest src/pbn_export_queue/tests/ src/pbn_integrator/tests/ -q`. PASS.
- [ ] **Step 5:** Commit `fix(multi-hosted): buildery klienta PBN wymagaja jawnej uczelni`.

---

## Faza 6 — Zadania Celery (dane, nie klient)

**Uzasadnienie:** czytają uczelnię dla danych (pbn_uid, jednostki). Mają
`uczelnia_id`/kontekst zadania albo da się go dodać.

**Files:**
- `src/ewaluacja_metryki/tasks.py:219,346` — `... else Uczelnia.objects.get_default()`.
  Sprawdź, czy zadanie ma `uczelnia_id` w sygnaturze; jeśli nie — dodaj
  (jak w `pbn_downloader_app`/`pbn_wysylka` — wzorzec `get_for_pbn_background`).
- `src/oswiadczenia/tasks.py:562` — analogicznie.
- `src/pbn_import/utils/command_helpers.py:39` — util wołany z CLI/manager;
  przekaż uczelnię od wołającego.

- [ ] **Step 1–5:** Per zadanie: dodaj/wykorzystaj `uczelnia_id`, resolwuj przez
  `get_for_pbn_background`, threaduj; test multi-hosted; commit.

---

## Faza 7 — CLI management commands (single-install, niskie ryzyko)

**Uzasadnienie:** uruchamiane ręcznie przez operatora. Akceptowalny wzorzec:
`Uczelnia.objects.get()` (jedyna albo wyjątek) — głośno ujawnia, że w
multi-hosted trzeba podać uczelnię. Docelowo (opcjonalnie) dodać `--uczelnia-id`
jak w `PBNBaseCommand`, ale to osobny scope.

**❓ DECYZJA 3:** czy CLI ma:
- (a) `Uczelnia.objects.get()` — proste, rzuca przy >1 (rekomendacja),
- (b) `--uczelnia-id` + guard `count==1` (jak `PBNBaseCommand.util.py`) —
  więcej kodu, ale działa w multi-hosted bez modyfikacji wywołania.

**Files:** `ewaluacja2021/.../przelicz_liczbe_n_dla_uczelni.py:24` ·
`ewaluacja_liczba_n/.../przelicz_n.py:24` ·
`ewaluacja_metryki/.../oblicz_metryki.py:81` ·
`pbn_import/management/commands/{pbn_import.py:164, fix_pbn_import_oswiadczen_ksiazki.py:271}` ·
`bpp/management/commands/{wyczysc_baze.py:66, import_jednostki_ipis.py:32, fix_pbn_import_oswiadczen_ksiazki.py:270}` ·
`pbn_integrator/management/commands/pbn_integrator.py:217,442` ·
`pbn_api/management/commands/fix_from_institution_api_for_scientist.py:25`

- [ ] **Step 1:** Rozstrzygnij DECYZJĘ 3.
- [ ] **Step 2:** Zastosuj wybrany wzorzec we wszystkich; `pbn_integrator.py`
  ma już `uczelnia` w `handle()` (`:442`) — użyj jej zamiast `objects.default`
  na `:217`.
- [ ] **Step 3:** Run: testy każdej apki + `manage.py check`. Commit.

---

## Faza 8 — Porównania danych w integratorze

**Uzasadnienie:** `objects.default.pbn_uid_id` używane do porównania
„czy to nasza instytucja" przy imporcie. W multi-hosted porówanie musi
dotyczyć uczelni, do której importujemy.

**Files:** `pbn_integrator/utils/scientists.py:435` ·
`pbn_integrator/utils/institutions.py:64,86` ·
`pbn_integrator/importer/authors.py:89,102,111,117,131`

- [ ] **Step 1:** Ustal, skąd integrator zna „swoją" uczelnię (z polecenia /
  kontekstu integracji). Przekaż `uczelnia.pbn_uid_id` jako argument/atrybut
  zamiast `Uczelnia.objects.default.pbn_uid_id` w każdym z 8 miejsc.
- [ ] **Step 2:** Test multi-hosted: import do `u2` porównuje z `u2.pbn_uid_id`.
- [ ] **Step 3:** Commit `fix(multi-hosted): integrator porownuje z uczelnia docelowa`.

---

## Faza 9 — Sprzątanie i guard

- [ ] **Step 1:** Sentinel-test: grep w teście, że w `src/` (poza definicją,
  util.py guard, middleware, bpp_specific, migracjami, testami) NIE ma
  `Uczelnia.objects.get_default()` / `.objects.default` — żeby regresje nie
  wracały. (Wzorzec jak istniejące sentinel-testy w repo.)
- [ ] **Step 2:** Zaktualizuj `docs/deweloper/audyt-multihosted-pbn.md` —
  oznacz rozwiązane.

---

## Self-Review (wykonane przy pisaniu)

- **Pokrycie:** wszystkie ~49 call-site'ów z audytu są przypisane do faz (1–8)
  albo do listy „zostają" (z uzasadnieniem). Faza 9 to guard.
- **Decyzje otwarte (do akceptacji usera PRZED implementacją danej fazy):**
  DECYZJA 1 (Faza 4 — czy config slotów/dyscyplin jest per-uczelnia czy
  globalny), DECYZJA 2 (Faza 5 — usuwać fallback adaptera teraz czy później),
  DECYZJA 3 (Faza 7 — `.get()` vs `--uczelnia-id` w CLI).
- **Kolejność ryzyka:** Faza 3 (ImportManager, WYSOKIE) i Faza 5 (buildery
  klienta) są najpilniejsze; Faza 7 (CLI) najmniej. Fazy 1–2 to szybkie wygrane.
- **Brak placeholderów w krokach mechanicznych;** Faza 4 świadomie zawiera
  DECYZJĘ zamiast kodu — bo bez rozstrzygnięcia „uczelnia rekordu" kod byłby
  zgadywaniem.

## Poza zakresem
- Pełne usunięcie fallbacku adaptera + refactor `pbn_wyslij` C901 (DECYZJA 2).
- Dodanie `--uczelnia-id` do CLI, jeśli wybrana opcja (b) w DECYZJI 3.
