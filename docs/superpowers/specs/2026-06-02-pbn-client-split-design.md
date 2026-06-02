# Spec: rozbicie `PBNClient` na warstwę reusable + warstwę BPP

Data: 2026-06-02. Gałąź bazowa: `feature/multi-hosted-config`.
Powiązany audyt: `docs/deweloper/audyt-multihosted-pbn.md`.

## Problem

`pbn_api.client.PBNClient` jest dziś **mieszanką dwóch odpowiedzialności**:

1. cienka warstwa HTTP nad REST API PBN (transport, auth, 8 mixinów
   słownikowo-CRUD, silnik diff/DELETE/POST oświadczeń) — **w 100% czyste PBN,
   zero importów `bpp`**;
2. orchestracja synchronizacji BPP↔PBN (`publication_sync.py`, 44 KB +
   `DisciplinesMixin`), która importuje `bpp.models.Uczelnia`/`Rekord`, czyta
   flagi uczelni, woła adaptery i — co gorsza — **`Uczelnia.objects.get_default()`
   wewnątrz klienta** (`publication_sync.py:287, 1046`; `adapters/wydawnictwo.py:94`).

Konsekwencja dla multi-hosted: `PBNClient` nie zna swojej `Uczelnia`, więc
logika w środku zgaduje ją przez `get_default()` (pierwsza z brzegu) — czyta
flagi/sterowanie payloadem z **niewłaściwej** uczelni.

## Cel

Rozciąć klienta dokładnie po granicy odpowiedzialności na dwa pakiety:

- **`src/pbn_client/`** — Warstwa 1, reusable, **kandydat do ekstrakcji jako
  osobny pakiet PyPI w przyszłości**. Wie tylko o pojęciach PBN: tokeny, URL-e,
  PBN UID instytucji (goła wartość), JSON-y, flagi `bool`. **Nie wolno jej
  importować `bpp.models`** (ani niczego z projektu poza `pbn_api.const`-owym
  odpowiednikiem, który też się przenosi).
- **`src/pbn_client_bpp/`** — Warstwa 2, „nasza", BPP-aware. Klasa
  `BppPBNClient(uczelnia)` budowana **z** obiektu `Uczelnia`; trzyma
  orchestrację, adaptery (most rekord BPP → PBN JSON) i odczyt flag uczelni.
  **Tu — i tylko tu — żyje wiedza o `Uczelnia`.** `get_default()` znika
  z podsystemu.

Po splicie pytanie „czy `PBNClient` potrzebuje uczelni" znika: czysty klient
nigdy jej nie zna, `BppPBNClient` zawsze ma ją z konstrukcji.

## Trójpodział odpowiedzialności (cel)

Dziś `pbn_api` to worek z trzema rolami. Split rozdziela je po naturalnych
szwach:

- **`pbn_client`** — *protokół* PBN (reusable, do ekstrakcji). Bez Django-modeli.
  Najczystszy, ekstrahowalny pierwszy.
- **`pbn_api`** — *dane domenowe PBN*: lustro encji PBN (Publication,
  Institution, Journal, Scientist, Publisher, Conference, Discipline,
  Language, Country) + słowniki + admin do przeglądania. **Własny
  reusable-kandydat** — ekstrahowalny **po** odseparowaniu resztkowego
  sklejenia z BPP (osobny przyszły tor).
- **`pbn_client_bpp`** — *logika integracji* BPP↔PBN: `BppPBNClient` +
  orchestracja + **adaptery** (rekord BPP → PBN JSON). Wie o `Uczelnia`.
  Z natury projektowy (klej), nie-reusable.

Zakres tego speca to **Poziom 1**: split klienta + przeniesienie `adapters/`
do `pbn_client_bpp`. **Modele zostają w `pbn_api`** — to ich właściwy dom
(dane PBN), nie materiał dla warstwy kleju. Nie ma „Poziomu 2 = przenieś
modele do `pbn_client_bpp`" — to byłby zły kierunek.

### Nalecialości BPP w `pbn_api` (osobny przyszły tor, nie ten spec)

Sklejenie modeli `pbn_api` z BPP jest realne, ale skoncentrowane:

- **Twarde FK** (na modelach „instytucji/wysyłki"): `uczelnia` FK
  (`oswiadczenie_instytucji`, `osoba_z_instytucji`, `publikacja_instytucji`,
  `sentdata`), `content_type`→`Rekord` GenericFK (`sentdata`,
  `pbn_odpowiedzi_niepozadane`), `dyscyplina_w_bpp` OneToOne
  (`tlumacz_dyscyplin`).
- **Miękkie**: behawioralny `LinkDoPBNMixin` + metody `matchuj_*` z leniwymi
  importami `from bpp.models...`.

Izolacja tego (np. przeniesienie modeli „wysyłki" jak `SentData` do warstwy
projektowej, wstrzykiwanie matchera) to warunek ekstrakcji `pbn_api` — ale
osobny, późniejszy wątek, poza tym specem.

## Architektura docelowa

### `src/pbn_client/` (Warstwa 1, reusable)

```
src/pbn_client/
  __init__.py        # eksport PBNClient + publiczne nazwy
  client.py          # PBNClient = kompozycja CZYSTYCH mixinów
  transport.py       # RequestsTransport, PBNClientTransport
  auth.py            # OAuthMixin
  pagination.py
  utils.py
  const.py           # URL-e, komunikaty PBN (z pbn_api/const.py — część PBN-owa)
  exceptions.py      # wyjątki PBN (z pbn_api/exceptions.py)
  conf.py            # ustawienia PBN (PBN_CLIENT_*), bez sięgania do bpp
  statements.py      # CZYSTY StatementsMixin wyjęty z publication_sync
  mixins/            # mixiny słownikowo-CRUD (8 plików, 9 klas)
```

`PBNClient` przyjmuje tokeny / PBN UID-y (string) / JSON-y / flagi `bool`,
zwraca JSON. Testowalny **bez bazy** (mock transport).

`statements.py` to **mixin** (`StatementsMixin`), nie luźne funkcje — woła
`self.transport` i `self.delete_publication_statement`/`get_institution_statements`
(z `InstitutionsProfileMixin`), więc musi być wmieszany w `PBNClient` przez MRO
(zależy od `InstitutionsProfileMixin`, też w W1). Z `publication_sync`
przenoszone tu: `_diff_statements`, `_statement_key_*`, `_convert_stmt_for_api`,
`_delete_statements_{with_retry,selective,batch}`, `_get_pbn_statements_with_retry`,
`convert_json_with_statements_to_no_statements`, `_post_publication_data`,
`post_publication{,_no_statements}`, `post_publication_fee`, `get_publication_fee{,s_batch}`.

### `src/pbn_client_bpp/` (Warstwa 2, BPP-aware)

```
src/pbn_client_bpp/
  __init__.py
  client.py          # BppPBNClient(PBNClient) — patrz niżej
  publication_sync.py# orchestracja: sync_publication, upload_publication, ...
  disciplines.py     # sync_disciplines (BPP-aware)
  adapters/          # PRZENIESIONE z pbn_api: rekord BPP → PBN JSON
  # modele persystencji (Publication, SentData, ...) zostają w pbn_api,
  # importowane lokalnie w metodach (mniejszy churn, brak migracji)
```

Przeniesienie `adapters/` (Poziom 1): ~5 call-site'ów do aktualizacji importu
(`pbn_wysylka_oswiadczen/tasks.py`, `pbn_api/management/commands/`
`{pbn_show_json, pbn_test_wysylka_interaktywna, pbn_wyslij_oswiadczenia_instytucji}.py`,
oraz wewnętrzny `publication_sync`). Czysty kod — **bez migracji**. Domyka fix
`adapters/wydawnictwo.py:94` (`get_default` → `uczelnia` podane przez
`BppPBNClient`). Dla kompatybilności wstecznej zostaje cienki re-eksport w
`pbn_api/adapters/__init__.py`.

`BppPBNClient` **dziedziczy** po `PBNClient` (a nie kompozycja), bo call-site'y
wołają na tym samym obiekcie i metody czyste (`get_journals`), i orchestrację
(`sync_publication`). Dziedziczenie = zero delegacji ~50 metod.

```python
class BppPBNClient(
    PBNClient,                       # czyste metody HTTP (W1)
    PublicationSyncOrchestrationMixin,
    DisciplinesBppMixin,
):
    def __init__(self, transport, uczelnia):
        super().__init__(transport)
        self.uczelnia = uczelnia     # JEDYNE źródło prawdy o uczelni
```

Orchestracja czyta flagi z `self.uczelnia` (nie `get_default()`) i przekazuje
je do czystych metod W1 jako gołe boole.

## Kontrakt W2 → W1

Audyt potwierdził, że granica jest wąska. Czyste metody W1 dla sync publikacji
przyjmują:

```
(pbn_publication_json: dict,
 statements_intended: list[dict],
 pbn_uid: str,
 kasuj_selektywnie: bool,
 bez_oswiadczen: bool)
```

W1 **nigdy** nie widzi `Uczelnia`, `rec` (rekordu BPP) ani `get_default`.
Trzy flagi uczelni (`pbn_kasuj_dyscypliny_selektywnie`, `pbn_wysylaj_bez_oswiadczen`,
`pbn_api_nie_wysylaj_prac_bez_pk`) odczytuje W2 i podaje jako parametry.

## Fabryka i kompatybilność wsteczna

- `Uczelnia.pbn_client(token)` buduje transport i zwraca
  `BppPBNClient(transport, uczelnia=self)`. To usuwa `get_default()`
  z `publication_sync.py:287/1046` i `adapters/wydawnictwo.py:94` —
  uczelnia jest jawna. **Import `BppPBNClient` musi być lokalny w metodzie**
  (cykl `bpp.models.uczelnia → pbn_client_bpp → adapters → bpp.models`).
- `pbn_api.client` zostaje **shimem re-eksportującym CAŁY dotychczasowy
  publiczny zestaw** (`__all__`): `PBNClient` (z `pbn_client`), `BppPBNClient`
  (z `pbn_client_bpp`), `OAuthMixin`, wszystkie 9 klas mixinów,
  `RequestsTransport`, `PBNClientTransport`, `PageableResource`, `smart_content`
  oraz stałe `PBN_*`/`DEFAULT_BASE_URL`/`NEEDS_PBN_AUTH_MSG`. Inaczej pękną
  importy typu `from pbn_api.client import RequestsTransport`. 35 importów
  `PBNClient` nie pęka; adnotacje `client: PBNClient = uczelnia.pbn_client()`
  pozostają poprawne (`BppPBNClient` *is-a* `PBNClient`).
- `pbn_api/.../util.py` `PBNBaseCommand.get_client(...)` zwraca `BppPBNClient`
  zbudowany z uczelni rozwiązanej przez `_resolve_uczelnia` (guard `count==1`).
  Pokrywa CLI-owe `sync_disciplines` (`pbn_integrator.py:182`).

### Call-site'y do migracji (z audytu: 6 orchestracji + fabryki)

`bpp/admin/helpers/pbn_api/common.py:155`, `pbn_import/utils/initial_setup.py:73`,
`pbn_integrator/management/commands/pbn_integrator.py:182`,
`pbn_integrator/utils/synchronization.py:91, 277, 321` — wszystkie dostają
klienta z fabryki (`Uczelnia.pbn_client` / `get_client`), więc po zmianie
fabryki działają bez modyfikacji, otrzymując poprawną uczelnię „za darmo".

## Przepływ danych (upload publikacji, po splicie)

```
Widok/zadanie  ──get_for_request/uczelnia_id──▶  Uczelnia
   Uczelnia.pbn_client(token)  ──▶  BppPBNClient(transport, uczelnia)
      BppPBNClient.upload_publication(rec)         [W2]
        ├─ WydawnictwoPBNAdapter(rec, uczelnia=self.uczelnia).pbn_get_json()
        ├─ flagi = (self.uczelnia.pbn_kasuj_dyscypliny_selektywnie, ...)
        └─ self.post_publication(json, pbn_uid, *flagi)   [W1, czyste HTTP]
```

## INSTALLED_APPS / pakiet Django

- `pbn_client` to **czysta biblioteka** (bez modeli/migracji) — nie musi być
  appką Django ani trafiać do `INSTALLED_APPS`. Konfiguracja PBN przez własny
  `conf.py` (czyta Django `settings`, ale nie modele).
- `pbn_client_bpp` **dodajemy do `INSTALLED_APPS`** z własnym `apps.py`
  (`AppConfig`) — może mieć szablony/adminy/testy; modele na razie zostają
  w `pbn_api`.
- **Testy:** istniejące `pbn_api/tests/test_client*.py` zostają, importując
  przez shim `pbn_api.client` — dzięki temu „zielone" przez całą migrację.
  Relokacja testów czystych do `pbn_client/tests/` jest opcjonalna i późniejsza.
- **Baseline:** przed i po KAŻDEJ fazie odpalać celowany podzbiór
  (`uv run pytest src/pbn_api/tests/ src/pbn_integrator/tests/ -p no:cacheprovider`)
  jako bramkę regresji, niezależnie od pełnego suite'u.

## Ryzyka i mitygacje

| Ryzyko | Mitygacja |
|---|---|
| Cykl importów `pbn_client_bpp` ↔ `pbn_api` (modele/adaptery) | Importy lokalne w metodach (jak dziś w `publication_sync.py`) |
| Pęknięcie 35 importów `pbn_api.client.PBNClient` | Shim re-eksportujący w `pbn_api/client/__init__.py` |
| CLI `get_client` → orchestracja na czystym `PBNClient` (brak metod) | `get_client` zwraca `BppPBNClient` z `_resolve_uczelnia` |
| Regresja w cięciu `statements.py` | Najpierw wydzielić W1 z re-eksportem i **zielonymi testami**, dopiero potem wyciąć orchestrację |
| Brak pokrycia multi-hosted | Dodać fixture `dwie_uczelnie` + test: właściwy `pbn_app_token` w transporcie i flagi z właściwej uczelni |

## Plan etapowy (kolejność krytyczna)

1. **W1 bez ruszania zachowania:** utwórz `src/pbn_client/`, przenieś czyste
   moduły (transport, auth, pagination, utils, const/exceptions/conf — część
   PBN, 8 mixinów). `pbn_api.client` re-eksportuje. Zielone testy.
2. **Wytnij `statements.py`** (czysty silnik) z `publication_sync.py` do W1.
   Zielone testy.
3. **W2:** utwórz `src/pbn_client_bpp/` z `BppPBNClient(PBNClient)` +
   orchestracją (BPP-owe części `publication_sync` + `DisciplinesMixin`).
   `get_default()` w orchestracji zastąpiony przez `self.uczelnia`.
4. **Przenieś `adapters/`** z `pbn_api` do `pbn_client_bpp`; zaktualizuj ~5
   importów; re-eksport w `pbn_api/adapters/__init__.py`. Adapter dostaje
   `uczelnia=self.uczelnia` z `BppPBNClient`; `get_default()` z adaptera
   usunięty. Zielone testy.
5. **Fabryki:** `Uczelnia.pbn_client()` i `get_client()` zwracają
   `BppPBNClient`. Shim re-eksportuje `BppPBNClient`.
6. **Fixture + testy multi-hosted.** Weryfikacja, że właściwa uczelnia steruje
   payloadem (token w transporcie + 3 flagi + adapter).
7. **(poza tym specem)** pozostałe znaleziska audytu Tier 🔴/🟠 nie-PBN
   (ORCID, `importer_publikacji/providers/pbn.py`, `importer_autorow_pbn`) oraz
   wątek `get_default` jako follow-up.

## Poza zakresem

- Szeroki refaktor `get_default` (osobny, **następny** wątek; patrz audyt).
- Izolacja nalecialości BPP w `pbn_api` (FK `uczelnia`/`Rekord`, `matchuj_*`,
  `LinkDoPBNMixin`) — warunek ekstrakcji `pbn_api`, osobny przyszły tor.
  Modele **nie** są przenoszone do `pbn_client_bpp`.
- Fizyczna ekstrakcja `pbn_client` / `pbn_api` do osobnych repo/PyPI (dopiero
  gdy warstwy są stabilne i odseparowane).
