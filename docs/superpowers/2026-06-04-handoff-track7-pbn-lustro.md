# Handoff — Track 7: pbn_api „lustro PBN" per-uczelnia

Kontynuacja audytu uczelnia (multi-hosted). Gałąź `feature/multi-hosted-config`.
Poprzednik: `docs/superpowers/2026-06-04-audyt-uczelnia-coverage.md`
(Track 1–6 ZROBIONE, w tym Track 4 SentData per-uczelnia).

## TL;DR — kluczowa zasada (to było mylone)

Trzy modele-lustra PBN (`OsobaZInstytucji`, `PublikacjaInstytucji(_V2)`,
`OswiadczenieInstytucji`) **już niosą UID instytucji PBN** w polu
`institutionId` (FK → `pbn_api.Institution`). `Uczelnia` ma swój odpowiednik
PBN: `Uczelnia.pbn_uid` (FK → `pbn_api.Institution`, `uczelnia.py:135`).

**Zatem `row.institutionId_id == uczelnia.pbn_uid_id` — przypisanie wiersza do
uczelni jest DETERMINISTYCZNE i nie wymaga niczego się domyślać ani przewlekać
`client.uczelnia` przez integrator.** Mapowanie już istnieje w kodzie:

```python
# src/pbn_api/models/institution.py:60 — Institution.rekord_w_bpp
Uczelnia.objects.get(pbn_uid_id=self.pk)   # Institution → Uczelnia
```

Czyli dla dowolnego wiersza lustra:
```python
uczelnia = Uczelnia.objects.get(pbn_uid_id=row.institutionId_id)
```

To NIE jest „first()/get_default/domyślanie się" — to twarda krotka po
istniejącym FK. Wynika z tego, że:

1. **Odczyty i delete można zawęzić JUŻ TERAZ, bez migracji i bez tagu FK** —
   przez `institutionId`: `filter(institutionId_id=uczelnia.pbn_uid_id)`.
2. FK `uczelnia` na lustrze to tylko **denormalizacja dla wygody filtrowania**.
   Backfill + write-side tag to „nice to have" (krótszy join), nie warunek
   poprawności. Można go zrobić, ale priorytet ma scope odczytów/delete.

## Stan: co jest gotowe w schemacie

FK `uczelnia` (nullable) **już istnieje** na wszystkich czterech modelach
(`OsobaZInstytucji`, `PublikacjaInstytucji`, `PublikacjaInstytucji_V2`,
`OswiadczenieInstytucji`) + `SentData`:
- dodane: `src/pbn_api/migrations/0069_add_uczelnia_fk.py`
- backfill: `src/pbn_api/migrations/0070_link_pbn_to_uczelnia.py`

**⚠️ Bug w 0070:** backfill ustawia `uczelnia = Uczelnia.objects.first()` dla
wszystkich wierszy (założenie single-install z czasu pisania). W multi-install
to przypisuje WSZYSTKIE lustra do pierwszej-z-brzegu uczelni — błędnie.
Nowa migracja Track 7 musi **re-mapować po `institutionId`** (poprawnie),
a nie kopiować ten wzorzec. Istniejących migracji NIE wolno edytować —
dopisz nową data-migration.

## Zakres Track 7 — w kolejności priorytetu

### A. Scope odczytów/delete przez `institutionId` (BEZ migracji, korektność)

To jest właściwy fix integralności. Wszystkie globalne `.all()` / cross-uczelnia
delete na lustrze zawęź przez `institutionId_id=uczelnia.pbn_uid_id`
(lub `institutionId_id__in=[pbn_uid-y uczelni z requestu]`):

| plik:linia | operacja | uwaga |
|---|---|---|
| `pbn_api/models/oswiadczenie_instytucji.py:217` | `SentData.objects.filter(pbn_uid_id=self.publicationId_id).delete()` | **leftover Track 4.** Teraz można zawęzić: `SentData` po `pbn_uid_id` ORAZ `uczelnia=Uczelnia.objects.get(pbn_uid_id=self.institutionId_id)`. `OswiadczenieInstytucji` MA `institutionId` (linia 28) — uczelnię wyprowadzasz z niego, nie z (NULL-owego) `self.uczelnia`. **To domyka świadomie zostawioną globalność z Track 4.** |
| `pbn_api/client/publication_sync.py:249` | `OswiadczenieInstytucji.objects.filter(publicationId_id=pub.pk).delete()` | przy sync per-uczelnia (`self.uczelnia` jest w scope, Track 4) zawęź też `institutionId_id=self.uczelnia.pbn_uid_id` — żeby sync uczelni A nie kasował oświadczeń uczelni B dla tej samej publikacji |
| `pbn_integrator/utils/statements.py:320,349` | `OswiadczenieInstytucji.objects.all()` iteracja | `integruj_oswiadczenia_*` — zawęź po uczelni z kontekstu integracji |
| `pbn_integrator/utils/statements.py:472,499,516` | global `.all()` / `.filter(publicationId...)` delete/iteracja | `usun_*_oswiadczenia` — zawęź |
| `pbn_integrator/utils/integration.py:313` | `OswiadczenieInstytucji.objects.all()` | `integruj_rekordy_z_uczelni` (ma „z_uczelni" w nazwie — sprawdź czy ma uczelnię w scope) |
| `komparator_pbn/views.py:95,293,327,365` | `.filter(year...)` bez uczelni | publiczne/adminowe widoki komparatora — scope przez `institutionId` uczelni z requestu |
| `komparator_pbn_udzialy/utils.py:245` | `OswiadczenieInstytucji.objects...all` iteracja w `KomparatorDyscyplinPBN.run()` | task globalny — patrz sekcja C |

**Read paths na `PublikacjaInstytucji_V2` / `OsobaZInstytucji`** (autocomplete
autorów `bpp/views/autocomplete/authors.py:59`, `bpp/models/autor.py:415`,
`bpp/models/abstract/pbn.py:124,128,168`) — filtrują po `personId`/`objectId`
bez uczelni. **Decyzja produktowa do potwierdzenia z userem:** te lookupy są
„czy autor/publikacja jest w PBN instytucji" — czy mają być per-uczelnia
oglądającego, czy globalne? (Prawdopodobnie per-uczelnia: `institutionId_id=
uczelnia_z_requestu.pbn_uid_id`.) NIE zakładaj — zapytaj.

### B. (Opcjonalne) Poprawny tag FK `uczelnia` na lustrze — wygoda + spójność

Jeśli chcemy mieć tani filtr `filter(uczelnia=...)` zamiast joinu przez
`institutionId`:

- **Data-migration (backfill, poprawia bug 0070):** dla każdego wiersza lustra
  `uczelnia = map_institutionId_to_uczelnia(row.institutionId_id)` przez
  `Uczelnia.objects.filter(pbn_uid_id=row.institutionId_id)`. Wiersze, których
  `institutionId` nie mapuje na żadną uczelnię (obce instytucje — współautorstwa
  z innych uczelni są w PBN!), zostają `uczelnia=NULL` — to poprawne, nie błąd.
  Wzorzec migracji jak Track 4 `0072` (data-only, reverse no-op, single+multi
  bezpieczny).
- **Write-side tag** (przy upsercie ustaw `uczelnia` z `institutionId`):
  - `PublikacjaInstytucji_V2` — `pbn_integrator/utils/publications.py:124`
    (`update_or_create(uuid=, objectId=, defaults={...})`) → dodaj do defaults
    `uczelnia=` wyprowadzone z `elem`/`client`. **uczelnia w scope:** `client`
    (`client.uczelnia`) LUB z `objectId`/institutionId elementu.
  - `PublikacjaInstytucji` — `pbn_integrator/utils/mongodb_ops.py:198`
    (`get_or_create`) → analogicznie.
  - `OswiadczenieInstytucji` — `pbn_integrator/utils/mongodb_ops.py:304`
    (`update_or_create(id=elem["id"], defaults=elem)`) → wyprowadź uczelnię z
    `elem["institutionId"]` przed upsertem i wstrzyknij do defaults.
  - `OsobaZInstytucji` — `pbn_integrator/utils/scientists.py:86`
    (`_zapisz_osobe_z_instytucji`) → uczelnia z `institutionId` osoby (jest w
    `person` dict) albo przekaż z `pobierz_ludzi_z_uczelni` (scientists.py:205,
    `uczelnia` w scope).

  **Preferuj wyprowadzenie z `institutionId` wiersza, nie z `client.uczelnia`** —
  jest odporne na przypadek, gdy element dotyczy obcej instytucji (współautor).

### C. Komparator udziałów (`komparator_pbn_udzialy`) — federacja-adjacent

`porownaj_dyscypliny_pbn_task` (`tasks.py:13`) nie ma `uczelnia_id`, iteruje
`OswiadczenieInstytucji.objects.all()` (`utils.py:245`), a modele wynikowe
(`RozbieznoscDyscyplinPBN`, `BrakAutoraWPublikacji`, `models.py:7,107`) **nie
mają FK `uczelnia`** — wiążą się przez `oswiadczenie_instytucji` FK.
Global `.all().delete()` w `clear_discrepancies()` (`utils.py:46`).

To większy kawałek (sygnatura taska + scope iteracji + ewentualnie FK na
modelach wynikowych). **Zrobić osobno**, po A/B. Minimalnie: dodać `uczelnia_id`
do taska i zawęzić `run()` przez `institutionId`. Pełny per-uczelnia wymaga
przemyślenia, czy wyniki komparatora mają być izolowane per-uczelnia (prawdop.
tak).

## STAN: Track 7-A ZROBIONE (scope po institutionId, bez migracji)

Commit `e729c4456` (audyt uczelnia, track 7a), review: spec ✅ + quality ✅.
- `OswiadczenieInstytucji.delete()` — `SentData` kasowane per-uczelnia
  wyprowadzonej z `self.institutionId` (domknięty leftover Track 4).
- `publication_sync.py` download_statements delete — zawężony po
  `self.uczelnia.pbn_uid_id`.
- Iteracje integratora (`usun_wszystkie/zerowe_oswiadczenia`,
  `integruj_oswiadczenia_pbn_first_import`, `integruj_oswiadczenia_z_instytucji`,
  `integruj_publikacje_instytucji`) — zawężone po `institutionId` uczelni
  klienta (None-guard); dwie funkcje dostały kwarg `uczelnia=`, threading z
  callerów; multiprocessing scope na zewnętrznym querysecie.
- Autocomplete autora `ma_osobe_z_instytucji` — zawężony po uczelni z requestu.
- Inwariant single-install: filtr `institutionId` = no-op przy 1 uczelni.

Wszystko po istniejącym FK `institutionId` — **bez migracji, bez tagu FK
`uczelnia`**. Tag FK (B) wciąż otwarty (patrz sekcja B) — potrzebny dla `_V2`
(`link_do_pi`), bo `PublikacjaInstytucji_V2` NIE ma `institutionId`.

### 🐛 Pre-existing bug do osobnego fixu (nie z Track 7-A)
`pbn_integrator/management/commands/pbn_integrator.py:336`:
`integruj_publikacje_instytucji(dm, skip_pages=skip_pages)` — `dm` ląduje
pozycyjnie jako `skip_pages`, a `skip_pages=` to drugi raz ten sam arg →
`TypeError: multiple values for 'skip_pages'`. Istnieje w bazie sprzed 7-A
(stage integracji publikacji jest tym zepsuty). Fix: usunąć pozycyjny `dm`
(prawdop. leftover po refaktorze sygnatury `integruj_publikacje_instytucji`).

## ⚠️ Federacyjna wysyłka/kasowanie oświadczeń — uprawnienia per-uczelnia (LATER)

Decyzja usera (2026-06-04): zalogowany autor ma uprawnienia (token PBN) **tylko
z jednej uczelni**. Więc nie da się wysłać/skasować oświadczeń instytucji za
wszystkie uczelnie pracy wielo-uczelnianej z jednego konta — chyba że ma
uprawnienia do danej.

Docelowe zachowanie (do zrobienia później, na razie tylko notka):
- Praca wielo-uczelniana → próba wysyłki/kasowania dla uczelni **„głównej"
  (z requestu)** ORAZ dla **obcych (federacyjnych)**.
- Porażka na uczelni głównej = istotna (raportuj).
- **Porażka na federacyjnych = NIE jest dramatem** — toleruj (brak tokenu/
  uprawnień do obcej uczelni jest oczekiwany). Loguj, nie wywalaj całości.

Miejsca dotknięte (push + delete oświadczeń):
- `OswiadczenieInstytucji.sprobuj_skasowac_z_pbn` (`oswiadczenie_instytucji.py`)
  — używa `request.user.pbn_token` jednej uczelni.
- `pbn_integrator/utils/statements.py` `usun_wszystkie/zerowe_oswiadczenia(client)`
  — kasowanie po stronie PBN per `client` (jedna uczelnia).
- Ścieżka wysyłki oświadczeń (`pbn_wysylka_oswiadczen/`).

To ORTOGONALNE do Track 7-A (lokalny scope wierszy lustra) — dotyczy
orkiestracji wywołań API PBN per-uprawnienia, nie filtrowania lokalnej bazy.

## ⚠️ Jedyny realny konflikt strukturalny: `OsobaZInstytucji.personId` OneToOne

`OsobaZInstytucji.personId` to **OneToOneField** (`osoba_z_instytucji.py:5`).
Ta sama osoba zatrudniona w 2 uczelniach (PBN zwróci ją w obu listach
„ludzie z instytucji", różne `institutionId`) → przy `update_or_create` po
`personId` **ostatnia uczelnia nadpisuje wiersz** (institutionId się zmienia).
Tag `uczelnia` tego nie naprawi — to konflikt KLUCZA, nie brak kolumny.

- Dotyczy **wyłącznie** `OsobaZInstytucji`. Pozostałe trzy modele NIE mają tego
  problemu: każda instytucja ma własny wiersz (naturalny klucz zawiera
  `institutionId` lub PBN UID statementu/publikacji jest per-instytucja).
- Fix (jeśli realny w praktyce klienta): zmienić `personId` OneToOne→FK i klucz
  na `unique_together=(personId, institutionId)` + write `update_or_create`
  keyed na `(personId, institutionId)`. **To zmiana schematu + ryzyko —
  potwierdź z userem czy multi-uczelnia współdzieli osoby w praktyce.** Jeśli w
  praktyce uczelnie są rozłączne kadrowo → niski priorytet, udokumentować.

## Helpery / wzorce do użycia

- `Uczelnia.pbn_uid` (FK → Institution), `uczelnia.py:135`.
- `Institution.rekord_w_bpp` (cached_property), `institution.py:60` —
  Institution → Jednostka|Uczelnia po `pbn_uid_id`.
- `Uczelnia.objects.get_for_request(request)` (write), `uczelnia.py:40`.
- `raport_slotow.uczelnia_helper.uczelnia_dla_odczytu(request)` (read).
- `bpp.util.uczelnia_scope.tylko_jedna_uczelnia()` / `scope_rekord_do_uczelni`.
- Integrator niesie uczelnię: `BppPBNClient.uczelnia` (`client/__init__.py:95`),
  `Uczelnia.pbn_client(token)` (`uczelnia.py:646`),
  `Uczelnia.objects.get_for_pbn_background(uczelnia_id)` (`uczelnia.py:46`).

## Guard (regresja) — pamiętaj

`src/bpp/tests/test_multihosted_get_default_guard.py` pilnuje teraz DWÓCH
footgunów: `Uczelnia.objects.get_default()/.default` (`APPROVED`) oraz
`Uczelnia.objects.first()/all()[0]` (`APPROVED_FIRST`). Skanuje `src/` przez
`rglob`, pomija `test_*.py`/`tests.py`. Jeśli w Track 7 dodasz jawne `first()`
gdziekolwiek — guard złapie; użyj jawnej uczelni z `institutionId`.

## Plan TDD (sugestia)

1. **A najpierw** (korektność, bez migracji): per call-site test — pod 2
   uczelniami `OswiadczenieInstytucji.delete()` / sync / komparator-view nie
   przecieka między uczelniami; scope przez `institutionId`. RED→GREEN.
2. Domknij leftover Track 4: `oswiadczenie_instytucji.delete()` zawęża `SentData`
   po `institutionId`-uczelni (zaktualizuj komentarz, usuń „Track 7 TODO").
3. **B opcjonalnie**: backfill-migration (re-map po institutionId, naprawia 0070)
   + write-side tag; test single+multi; `makemigrations --check` zielony.
4. **C osobno**: komparator udziałów per-uczelnia.
5. Pełna regresja `pbn_api` + `pbn_integrator` + `komparator_*` + guard.

## Pytania do usera przed startem

1. Read paths autocomplete/abstract (`personId`/`objectId` bez uczelni) — mają
   być per-uczelnia oglądającego czy globalne? (sekcja A, koniec)
2. `OsobaZInstytucji.personId` OneToOne — czy uczelnie w praktyce współdzielą
   osoby (czy warto ruszać schemat)? (sekcja konfliktu strukturalnego)
3. Robimy tylko A (scope, korektność) teraz, czy też B (tag FK) od razu?
