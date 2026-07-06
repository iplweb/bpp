# Audyt multi-hosted: PBN i `Uczelnia.get_default`

Data: 2026-06-02. Gałąź: `feature/multi-hosted-config`.

Cel: w instalacji **wielouczelnianej** (jedna instancja BPP obsługuje wiele
obiektów `Uczelnia`, każda z własną konfiguracją PBN: `pbn_app_name`,
`pbn_app_token`, `pbn_api_root`, token użytkownika) żadna ścieżka runtime nie
może „zgadywać" uczelni. Audyt wynajduje miejsca, które:

- **(A)** wołają `Uczelnia.pbn_client(...)` / `get_pbn_client(...)`,
- **(B)** budują połączenie do PBN „poza" obiektem `Uczelnia` (ręczna
  instancja `PBNClient(RequestsTransport(...))`),
- **(C)** „zgadują" uczelnię przez `get_default()` / `objects.default` /
  `.first()`.

## Kontekst API

- `Uczelnia.pbn_client(pbn_user_token=None)` — metoda **instancji**: buduje
  klienta PBN z konfiguracji **tej** uczelni. Wywołanie na złej uczelni =
  połączenie ze złym kontem PBN.
- `UczelniaManager.get_default()` → `self.all().first()` — **pierwsza
  z brzegu**. W multi-hosted to losowy/błędny strzał.
- Poprawne resolvery (już istnieją): `get_for_request(request)`,
  `get_for_pbn_background(uczelnia_id)` (rzuca `ValueError` przy `None`),
  `get_for_site(site)`.

## Ustalenie kluczowe

`PBNClient` **nie zna swojej `Uczelnia`** (`client/__init__.py` trzyma tylko
`self.transport`). Dlatego nawet gdy klient zbudowano z właściwej uczelni, kod
*wewnątrz* klienta (`publication_sync.py`, adapter) **ponownie zgaduje**
uczelnię przez `get_default()`. To źródło kilku WYSOKICH ryzyk i główny motyw
rozbicia `PBNClient` na dwie warstwy (osobny spec:
`docs/superpowers/specs/2026-06-02-pbn-client-split-design.md`).

---

## Tier 🔴 WYSOKIE — runtime buduje ZŁEGO klienta PBN/OAuth lub wpis kolejki bez uczelni

| Miejsce | Wzorzec | Problem |
|---|---|---|
| `pbn_api/adapters/wydawnictwo.py:94` ← `pbn_api/client/publication_sync.py:191, 622` | C | Adapter wysyłki instancjonowany w środku klienta **bez** uczelni → `get_default()` czyta flagi payloadu (`pbn_api_nie_wysylaj_prac_bez_pk`, `pbn_wysylaj_bez_oswiadczen`) z losowej uczelni |
| `pbn_import/utils/import_manager.py:108→125` + `initial_setup.py:23→31` | A+C | `tasks.py` poprawnie wybiera uczelnię, ale `ImportManager` **nie propaguje** jej do kroków → `get_default()` **nadpisuje** `self.client` klientem złej uczelni (regresja na już-poprawionej ścieżce) |
| `importer_publikacji/providers/pbn.py:42, 214` + `views/pbn_check.py:131` | A+B+C | `_get_pbn_client()` buduje klienta **ręcznie** (`PBNClient(RequestsTransport(...))`) z `get_default()`, mimo że oba wywołania siedzą w widokach z `request`. Jedyny produkcyjny wzorzec (B) |
| `importer_publikacji/tasks.py` → `bpp/admin/helpers/pbn_api/gui.py:87` → `cli.py:43` | C | `create_publication_task` tworzy `_PbnRequestStub` bez `_uczelnia`; wpis `PBN_Export_Queue` powstaje z `uczelnia=None`; wysyłka z kolejki znów spada do `get_default()`. Docstring wprost zakłada „fallback OK" — błędne w multi-hosted |
| `orcid_integration/views.py:29` (`_get_orcid_client`) | B+C | Buduje `OrcidClient` z credentiali uczelni przez `get_default()`, mimo dostępnego `request` → logowanie do złego konta ORCID |
| `pbn_integrator/utils/scientists.py:61/156` | A+C | Buduje klienta z `get_default()` gdy `uczelnia=None` (w praktyce łagodzone — zwykle przekazuje się gotowy klient) |

## Tier 🟠 ŚREDNIE — runtime zgaduje uczelnię dla DANYCH, nie dla klienta

Skutkuje złym `pbn_uid`, błędnymi filtrami/flagami, ale **nie** łączy się ze
złym kontem PBN.

| Miejsce | Co zgaduje |
|---|---|
| `pbn_api/client/publication_sync.py:287, 1046` | flaga `pbn_kasuj_dyscypliny_selektywnie` (strategia DELETE oświadczeń) |
| `importer_autorow_pbn/views.py:69` | `objects.default` do filtra listy naukowców po `pbn_uid_id` |
| `pbn_import/utils/{author_import.py:18, publication_import.py:79, institution_import.py:101}` | `pbn_uid_id`, `obca_jednostka` w ścieżce Celery |
| `pbn_integrator/utils/scientists.py:435`, `institutions.py:64/86`, `importer/authors.py:89+` | `pbn_uid_id`, `obca_jednostka` przy imporcie |
| `pbn_integrator/management/commands/pbn_integrator.py:217` | `pbn_uid_id` mimo dostępnej `uczelnia` w `handle()` |
| `zglos_publikacje/forms.py:316`, `models.py:254` | flagi formularza zgłoszeń (wizard nie przekazuje uczelni) |
| `importer_publikacji/views/{steps.py:336, publikacja.py:125}` | flagi `pbn_integracja`/`pbn_aktualizuj_na_biezaco`, `obca_jednostka` |
| `bpp/models/sloty/core.py:34`, `abstract/disciplines.py:18`, `jednostka.py:46`, `multiseek_registry/fields/numeric_fields.py:71`, `abstract/pbn.py:23/89` | per-uczelnia ustawienia: ukryte statusy, sortowanie, index copernicus, liczenie slotów, linki PBN |

## Tier 🟢 OK / NISKIE — jawny resolver albo świadomy fallback

- Jawny `get_for_request`/`pbn_client` tej uczelni: `crossref_bpp/views.py:124`,
  `bpp/views/api/pbn_get_by_parameter.py:56/62`,
  `bpp/views/autocomplete/{pbn_api.py:82, wydawnictwo_nadrzedne_w_pbn.py:172}`,
  `bpp/admin/helpers/pbn_api/gui.py:137`, `bpp/admin/uczelnia.py:307`.
- Już naprawione ścieżki Celery (ostatnie commity) przez
  `get_for_pbn_background(uczelnia_id)`: `pbn_downloader_app/tasks.py`,
  `pbn_wysylka_oswiadczen/tasks.py`, `pbn_export_queue` (FK na wpisie),
  `pbn_import/tasks.py:78/82`.
- Wzorcowa warstwa management commands:
  `pbn_api/management/commands/util.py:_resolve_uczelnia` — `get_default()`
  TYLKO gdy `count==1`, inaczej `CommandError`.
- Świadome, udokumentowane fallbacki: `bpp/middleware.py:295` (Site bez
  Uczelni), `bpp/util/bpp_specific.py:104` (CLI/Celery bez requestu),
  `do_roku_default`. Migracje backfill i testy.

---

## Audyt wewnętrzny `PBNClient` — gdzie potrzebna jest `Uczelnia`

Pełny audyt linia-po-linii w `src/pbn_api/client/` + `src/pbn_api/adapters/`.

### Kontrakt: pola `Uczelnia` faktycznie używane przez warstwę klienta

Tylko **trzy** flagi `bool` przepływają do logiki klienta:

| Flaga | Gdzie | Cel | Typ do W1 |
|---|---|---|---|
| `pbn_kasuj_dyscypliny_selektywnie` | `publication_sync.py:289, 1048` | strategia DELETE oświadczeń: per-osoba vs batch | `bool` |
| `pbn_wysylaj_bez_oswiadczen` | `adapters/wydawnictwo.py:100` | praca bez statements → inny endpoint + pre-clear | `bool` (przez obecność `statements` w JSON) |
| `pbn_api_nie_wysylaj_prac_bez_pk` | `adapters/wydawnictwo.py:97` | blokuje eksport prac z `punkty_kbn==0` | `bool` (już jako `export_pk_zero`) |

Cała reszta sprzężenia to rekord BPP (do adaptera) i modele persystencji
(`SentData`, `Rekord`, `Publication`, `OswiadczenieInstytucji`,
`PBNOdpowiedziNiepozadane`, `PublikacjaInstytucji_V2`, `Dyscyplina_Naukowa`,
`TlumaczDyscyplin`).

**Kontrakt W2→W1 dla sync publikacji:**
`(pbn_publication_json, statements_intended, pbn_uid, kasuj_selektywnie: bool,
bez_oswiadczen: bool)`.

### Czyste (Warstwa 1) vs BPP-aware (Warstwa 2)

- **Czyste PBN (zostają w `pbn_client`):** `transport`, `auth` (OAuth),
  `pagination`, `utils`, wszystkie 8 mixinów słownikowo-CRUD (`conferences`,
  `dictionaries`, `institutions`, `journals`, `person`, `publications`,
  `publishers`, `search`) — **zero importów `bpp`**. Plus z `publication_sync`:
  silnik oświadczeń (`_diff_statements`, `_delete_statements_*`,
  `_get_pbn_statements_with_retry`, `post_publication*`, `get_publication_fee*`,
  `convert_json_with_statements_to_no_statements`, `_convert_stmt_for_api`).
- **BPP-orchestracja (→ `pbn_client_bpp`):** `sync_publication`,
  `upload_publication`, `_prepare_publication_json`, `_check_upload_needed`,
  `_pre_upload_clear_pbn_statements_if_any`, `download_publication`,
  `download_statements_of_publication`, `pobierz_publikacje_instytucji_v2`,
  `_build_post_statements_payload`, `_handle_uid_change/_handle_uid_conflict`,
  `eventually_coerce_to_publication`, `upload_publication_fee`, oraz **cały**
  `DisciplinesMixin` (`sync_disciplines`). Plus wszystkie `adapters/*`.
- **Mieszane (rozcięcie):** `_post_statements_with_retry`,
  `_sync_statements_with_pbn` — W2 dostarcza gotowy payload / „intencję"
  (listy dict z adaptera) + flagi, W1 robi czyste HTTP/diff.

### Skala migracji call-site'ów

- Metody orchestracji woła się **tylko w 6 miejscach** (poza klientem/testami):
  `bpp/admin/helpers/pbn_api/common.py:155`,
  `pbn_import/utils/initial_setup.py:73`,
  `pbn_integrator/management/commands/pbn_integrator.py:182`,
  `pbn_integrator/utils/synchronization.py:91, 277, 321`.
- `from pbn_api.client import PBNClient`: 35 importów (utrzymać re-eksportem).
- Budowa klienta przez `Uczelnia.pbn_client(...)`: ~20 call-site'ów — jedna
  fabryka.

---

## Decyzja w sprawie `get_default`

(Patrz dyskusja z 2026-06-02.)

- **Produkcja (runtime: widoki, zadania, sygnały)** — nigdy nie zgaduje;
  uczelnia przychodzi jawnie (`get_for_request`, argument, `self.uczelnia` w W2).
- **Legalny przypadek „jest jedna uczelnia" (testy + single-install CLI)** —
  `Uczelnia.objects.get()` (Django rzuca `MultipleObjectsReturned` przy >1,
  `DoesNotExist` przy 0). Bez nowej metody typu `get_single_fail_if_more`.
- **`get_default`** — nie wołać w nowym kodzie; legalnych callerów migrować na
  `.get()`; docelowo zostawić tylko świadomy „dowolna" (ewentualny
  `get_arbitrary()` dla `middleware` Site-bez-uczelni) albo wycofać.

### Status: ZREALIZOWANE (2026-06-02, Fazy 1–9)

Cleanup wykonany. Pozostały po nim **tylko świadome użycia** `get_default`/
`objects.default` (15 plików), pilnowane przez sentinel-test
`src/bpp/tests/test_multihosted_get_default_guard.py` (nowy `get_default`
w runtime → fail CI). Kategorie pozostałych:

- **Świadome fallbacki bez requestu:** `middleware.py` (Site bez Uczelni),
  `util/bpp_specific.py` (CLI/Celery bez requestu), `pbn_import_tags.py`
  (template tag, request-first), `command_helpers.py` (CLI + `CommandError`).
- **None-tolerant warstwa modelu/wyświetlanie:** `jednostka.py` (sortowanie),
  `multiseek .../numeric_fields.py` (index copernicus), `abstract/pbn.py`
  (root linków).
- **GUARDED:** `pbn_api/.../util.py` (`count==1` else `CommandError`).
- **Test-only:** `adapters/wydawnictwo.py` (runtime przekazuje jawną uczelnię).
- **PARKED z TODO (deeper redesign per-uczelnia):** `sloty/core.py`,
  `abstract/disciplines.py` (sloty/punktacja per-uczelnia — cache per
  rekord×uczelnia), oraz integrator (`scientists.py`, `importer/authors.py`,
  `pbn_integrator.py` — threading uczelni docelowej przez pipeline).

Reszta runtime została przepięta na jawną uczelnię: `get_for_request` (widoki,
ORCID, importer steps/detail), `session.uczelnia` (importer_publikacji),
`self.uczelnia` w `BppPBNClient`/`ImportManager` (PBN sync, import), oraz
`Uczelnia.objects.get()` w fallbackach single-install (komendy CLI, taski
z `uczelnia_id`).

**Następny, osobny wątek (brainstorm):** per-uczelnia liczenie slotów/punktacji
(parked TODO) — `Cache_Punktacja_*` z `uczelnia_id`, liczenie+zapis per
uczelnia autora, odczyty filtrowane po uczelni oglądającego.

## Backfill per-uczelnia cache (write-side)

Migracje dodają nullable `uczelnia` na `Cache_Punktacja_Dyscypliny`
(`0424_cache_punktacja_dyscypliny_uczelnia_and_more`) i naprawiają widok
`bpp_cache_punktacja_autora_view` tak, by joinował po uczelni
(`0425_per_uczelnia_cache_view`).

Po deployu należy **przeliczyć cache** pełnym przeliczeniem punktów dyscyplin —
nowy kod (`IPunktacjaCacher.rebuildEntries`) zapisze wiersze osobno per uczelnia.
W instalacji jednouczelnianej liczby pozostają identyczne (fast-track: jedna
uczelnia w systemie ⇒ liczenie jak dotychczas, tylko z otagowaniem uczelnią).

Wyzwolenie pełnego przeliczenia: rebuild pól `@denormalized cached_punkty_dyscyplin`
(np. denorm rebuild używany w projekcie lub `denorms.flush()` w shellu), który
woła `przelicz_punkty_dyscyplin()` per rekord. Konkretną komendę denorm rebuild
potwierdzić w środowisku docelowym.

Opcjonalnie, po przeliczeniu, można dodać migrację zacieśniającą
`Cache_Punktacja_Dyscypliny.uczelnia` do `null=False`.
