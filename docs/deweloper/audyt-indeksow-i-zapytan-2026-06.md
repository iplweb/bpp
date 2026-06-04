# Audyt indeksów i zapytań (czerwiec 2026)

Audyt przeprowadzony na zrzucie produkcyjnym `db-backup-20260603-023000`
(258 tabel, 1048 indeksów, 478 FK, ~830 MB danych skompresowanych).
Analiza schematu: `pg_restore --schema-only` + parser w Pythonie
(duplikaty / redundantne prefiksy / nieindeksowane FK), rozmiary tabel
z `.dat.gz` przez `pg_restore -l`.

> Uwaga metodologiczna: statystyki **użycia** indeksów
> (`pg_stat_user_indexes.idx_scan`) to stan runtime — **nie ma** ich w
> zrzucie. Ten audyt wykrywa redundancję **strukturalną** (duplikaty,
> prefiksy, brakujące FK), niezależną od ruchu. Analiza „idx_scan=0"
> była robiona osobno na żywej bazie (PR #315).

## Wnioski ogólne

- Baza jest **prze-zaindeksowana**, nie pod-zaindeksowana. Na 478 FK tylko
  **2** nie mają wspierającego indeksu (oba na tabelach `*_mat`
  przebudowywanych triggerem — patrz niżej).
- Źródło redundancji: powtarzalny anty-wzorzec w modelach —
  `Meta.indexes = [models.Index(fields=["<fk>"])]` dla kolumn, które Django
  **już** indeksuje (FK ma domyślnie `db_index=True`), albo które pokrywa
  `unique_together`/`UniqueConstraint`. Efekt: 2 identyczne indeksy lub
  jednokolumnowy indeks będący redundantnym **prefiksem** złożonego.
- Każdy zbędny indeks = narzut na `INSERT/UPDATE/DELETE` (write
  amplification) + miejsce, przy zerowej korzyści przy odczycie.

## Reguły naprawy (wzorzec)

| Sytuacja | Naprawa | Migracja Django generuje |
|---|---|---|
| Duplikat z `models.Index(fields=[fk])` | usuń linię z `Meta.indexes` (auto-indeks FK zostaje) | `RemoveIndex` |
| Auto-indeks FK = redundantny prefiks złożonego | `db_index=False` na `ForeignKey` | `AlterField` |
| Indeks osierocony (nie ma w stanie modeli) | raw `DROP INDEX CONCURRENTLY IF EXISTS` | `SeparateDatabaseAndState` |

`db_index=False` na FK jest bezpieczne także dla `CASCADE`/`PROTECT`: złożony
indeks z FK jako kolumną wiodącą obsługuje i lookup, i skan wierszy-dzieci
przy usuwaniu / sprawdzaniu integralności.

`AlterField` (drop przez introspekcję) jest **odporniejszy** niż raw
`DROP INDEX IF EXISTS <nazwa>`: Django znajduje faktyczny indeks na kolumnie
niezależnie od jego nazwy (starych hashy `_e76def89` itp.), więc nie
„przegapi" go po cichu na innym wdrożeniu.

## Zrobione (zweryfikowane: `makemigrations --check` czysto, `manage.py check` OK)

- **`ewaluacja_optymalizacja` → migracja `0015_…`** — usuwa **10** indeksów
  (7 duplikatów z `Meta.indexes` + 3 prefiksy FK przez `db_index=False`):
  `disciplineswapopportunity` (uczelnia/current/target_discipline),
  `optimizationauthorresult` (optimization_run+autor / autor /
  optimization_run prefix), `optimizationpublication` (author_result /
  rekord_id), `optimizationrun` (dyscyplina_naukowa prefix),
  `unpinningopportunity` (uczelnia prefix).
- **`bpp` core → migracja `0423_…`** — `db_index=False` na FK `rekord` w
  `Wydawnictwo_Ciagle_Autor` (7.6 MB, hot), `Wydawnictwo_Zwarte_Autor`
  (4.2 MB), `Patent_Autor` — redundantne prefiksy `unique_together`.

## Batch 2 (czerwiec 2026) — wykonane

Druga seria, ~35 redundantnych indeksów usuniętych przez edycje modeli
(`db_index=False` / usunięcie `Meta.Index`) + raw SQL dla nieosiągalnych
przez ORM. Wszystkie zweryfikowane: `makemigrations --check` czysto,
migracje aplikują się pod testcontainers, testy zielone.

**Apki Django (migracje per-apka):** `deduplikator_autorow` (5),
`deduplikator_publikacji` (3), `komparator_pbn_udzialy` (5),
`pbn_komparator_zrodel` (5), `pbn_import` (3), `pbn_wysylka_oswiadczen` (2),
`przemapuj_zrodlo` (2), `powiazania_autorow` (1), `ewaluacja_liczba_n` (4),
`ewaluacja_metryki` (3), `importer_publikacji` (1), `zglos_publikacje` (1).

**`bpp` core (migracja `0424`):** `autor_dyscyplina` (przez raw-indeks
`_autor_rok_idx`), `autor_jednostka`, `dyscyplina_zrodla`,
`punktacja_zrodla`, `nagroda`, `opi_2012`, `oplatypublikacjilog`,
`publikacja_habilitacyjna`, `ukryj_status_korekty`, `wydawca` w abstrakcie
`Wydawnictwo_Zwarte_Baza` (→ wydawnictwo_zwarte + praca_doktorska +
praca_habilitacyjna), `cache_punktacja_autora.rekord_id`.

**`bpp` raw SQL (migracja `0425`, wzorzec 0422):** `bpp_autorzy_mat_2`
(managed=False), osierocone `bpp_praca_doktorska_52be3978` /
`bpp_praca_habilitacyjna_52be3978`. (`bpp_autorzy_mat_6` — już w 0422.)

**Retencja logów logowania:** task Celery
`bpp.tasks.usun_stare_logi_logowania_easyaudit` + wpis w
`CELERYBEAT_SCHEDULE` (1. dnia miesiąca, 2:00) — kasuje `LoginEvent`
starsze niż **24 mies.** (RODO). CRUDEvent (historia edycji) nietknięty.

### Świadomie pominięte w Batch 2 (z powodem)

- **`grant_rekordu`, `poziom_wydawcy`** — tabele KB (zysk znikomy), a pliki
  `grant.py`/`wydawca.py` mają **pre-existing** dług lintera (DJ001
  `null=True` na TextField → wymaga migracji schematu; DJ012 kolejność
  metod). Nie naprawiamy cudzego długu drive-by → do osobnego PR-a
  lint-cleanup razem z edycją indeksu.
- **`konferencja.nazwa`** — plain-btree redundantny, ALE `db_index=True` na
  polu tekstowym tworzy też wariant `_like` (text_pattern_ops),
  nie-pokryty przez unique_together. Drop dotknąłby `_like` (nie
  udowodniony jako zbędny). Mała tabela → zostawione.
- **`ewaluacja2021`** — modele już usunięte (migracja 0020), tabele znikną.
- **`favicon`, `flexible_reports`, `formdefaults`, `dynamic_columns`** —
  **pakiety zewnętrzne** (site-packages); poprawka należy do upstream.
- **`import_dyscyplin`, `bppuser_*`** — auto-tabele M2M (brak modelu z
  `db_index`); raw-drop ze starą nazwą zbyt kruchy za zerowy zysk.

### Znaleziony przy okazji pre-existing drift (NIE w tym PR)

`makemigrations` (bez filtra apek) generuje
`raport_slotow.0020_alter_raportslotowuczelnia_do_roku` — model
`RaportSlotowUczelnia.do_roku` rozjechał się ze stanem migracji (commit
`a3a5ffff6 "Fix 923"` zmienił pole bez migracji). Osobny problem na `dev`,
do naprawy niezależnie.

## Do zrobienia — checklist (≈60 indeksów, pogrupowane)

Ten sam wzorzec naprawy. Pominąć **pakiety zewnętrzne** (ich indeksy
pochodzą z własnych migracji — nie edytować modeli): `taggit_taggeditem`,
`robots_rule_*`, `reversion_version`, `django_template_sites`,
`celeryui_report`.

### Modele Django (czyste `db_index=False` / usunięcie `Meta.Index`)
- `pbn_komparator_zrodel.RozbieznoscZrodlaPbn` (8 — w tym duplikaty
  `Meta.indexes` na FK + prefiksy `zrodlo_id`)
- `komparator_pbn_udzialy.BrakAutorawPublikacji` (5),
  `…RozbieznoscDyscyplinPbn` (4)
- `deduplikator_publikacji.PublicationDuplicateCandidate` (4),
  `deduplikator_autorow.DuplicateCandidate` (3), `…LogScalania` (2),
  `deduplikator_zrodel.NotaDuplicate` (1)
- `przemapuj_zrodlo.PrzemapowaZrodla` (4)
- `ewaluacja_metryki.MetrykaAutora` (3 — prefiksy FK autor/dyscyplina/jednostka)
- `ewaluacja2021.*`, `ewaluacja_liczba_n.*` (po 1 — prefiks FK przed
  `unique_together`)
- `pbn_wysylka_oswiadczen.PbnWysylkaLog` (2), `pbn_import.*` (3),
  `powiazania_autorow.AuthorConnection` (1),
  `importer_publikacji.ImportedAuthor` (1), `import_dyscyplin.*` (1),
  `flexible_reports.*` (2), `formdefaults.*` (1), `dynamic_columns.*` (1),
  `favicon.FaviconImg` (1), `zglos_publikacje.*` (1),
  `bpp.Ukryj_Status_Korekty` (1)

### `bpp` core — wymagają ostrożności (abstrakty / indeksy osierocone)
- `bpp_wydawnictwo_zwarte.wydawca` (20 MB) — FK `wydawca` w abstrakcie
  `Wydawnictwo_Zwarte_Baza`; prefiks `(wydawca, rok)`. **Sprawdzić wszystkie
  konkretne podklasy** zanim ustawi się `db_index=False` w bazie (czy każda
  ma złożony `(wydawca, rok)`).
- `bpp_praca_doktorska` / `bpp_praca_habilitacyjna` — FK `wydawca` (prefiks)
  w `Praca_Doktorska_Baza` **oraz osierocone** `…_52be3978` na `autor_id`
  (duplikat OneToOne/FK; nie ma w stanie modeli → raw
  `DROP INDEX CONCURRENTLY`).

### Tabele `*_mat` (raw SQL, `managed=False`) — osobny mechanizm
Indeksy zarządzane surowym SQL-em w migracjach (nie przez `Meta`):
- `bpp_autorzy_mat`: `_2 (autor_id)` ⊂ `_4 (autor, jednostka)`;
  `_6 (dyscyplina)` ⊂ `_8 (dyscyplina, rekord)` — prefiksy do usunięcia
  raw-em.
- **Brakujące FK** (jedyne 2 w całej bazie):
  `bpp_autorzy_mat.typ_odpowiedzialnosci_id` →
  `bpp_typ_odpowiedzialnosci`, `bpp_rekord_mat.konferencja_id` →
  `bpp_konferencja`. Ocenić, czy potrzebne (tabele przebudowywane
  triggerem; FK bez indeksu spowalnia kaskady/joiny, ale przy pełnej
  przebudowie może nie mieć znaczenia).

## Audyt zapytań — multiseek / front / admin

Hot-paths są **dobrze zoptymalizowane** — brak oczywistych N+1:

- **multiseek** (`bpp/views/mymultiseek.py`): `.only("id",
  "opis_bibliograficzny_cache")` (pomija ciężki `VectorField` w widoku
  listy), `select_related("charakter_formalny", "typ_kbn")` dla raportów
  tabelarycznych, sumy przez `aggregate(Sum(...))` po stronie DB. Opis
  bibliograficzny jest precomputowany (`opis_bibliograficzny_cache` na
  `bpp_rekord_mat`).
  - *Code smell (drobny):* linia ~74 — `sql = str(ret.query)` i podstring
    `"bpp_autorzy_mat" in sql` żeby zdecydować o `.distinct()`; kompilacja
    całego SQL-a na każdy request. Komentarz sam przyznaje „not ideal".
- **front** (`bpp/views/browse.py`): listy (`AutorzyView`, `ZrodlaView`,
  `JednostkiView`) używają `.only()` + `select_related`. Strona autora
  doładowuje listę publikacji AJAX-em (brak dużej pętli server-side); pętle
  w szablonie (`metryki`, `praca_doktorska_set`, `jednostki…`,
  `prace_w_latach`) są ograniczone per-autor.

### Admin — znalezione N+1

- **NAPRAWIONE:** `Autor_DyscyplinaAdmin` (`bpp/admin/autor_dyscyplina.py`) —
  `list_display` miał 4 kolumny FK (`autor`, `rodzaj_autora`,
  `dyscyplina_naukowa`, `subdyscyplina_naukowa`) + metody `orcid`/
  `pbn_uid_id` czytające `obj.autor.*`, bez `list_select_related` → ~5
  zapytań × 100 wierszy/stronę. Dodano `list_select_related`.
- **Do rozważenia (admin-only, niższy priorytet):**
  - Admin-y `pbn_api` (`scientist` 337 MB, `journal` 128 MB, `publisher`,
    `publication`): metody `rekord_w_bpp` / `from_institution_api` w
    `list_display` robią per-wiersz lookup cross-model. Nie naprawi tego
    proste `list_select_related` (to reverse-lookup; trzeba prefetch /
    annotate / cache). Admin = niski ruch, ale tabele ogromne.
  - `oplaty_log` admin: `get_publikacja` (GenericFK) + `changed_by` (User
    FK) bez `list_select_related`.

## Znaleziska poboczne

- **Zepsuty pakiet w venv:** `djangoql-iplweb==0.21.0` (release 2026-06-03)
  zainstalował się niekompletnie (tylko `extras.py` + `locale/`, bez
  `__init__.py`/`admin.py`) → `manage.py` w ogóle nie wstawał.
  `uv pip install --reinstall-package djangoql-iplweb` naprawił. **Sprawdzić,
  czy wheel na PyPI nie jest wadliwy** (jeśli CI/prod zainstaluje tak samo —
  wybuchnie).
- **Retencja logów (decyzje usera):** logi edycji (`easyaudit_crudevent`
  108 MB, `reversion_version`, admin `LogEntry`) — zostają **na zawsze**.
  Logi logowania (`easyaudit_loginevent`) — **24 miesiące** (do
  zaimplementowania: zadanie Celery beat). Obecnie **brak** jakiejkolwiek
  retencji.
- **Brak ochrony przed brute-force** na klasycznym logowaniu (brak
  django-axes/defender/ratelimit; DRF throttling zakomentowany od 2020).
  Rekomendacja: `django-axes`, `FAILURE_LIMIT=5`, lockout po `(login, IP)`,
  `COOLOFF=1h`. (Wdrażane osobno.)
