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

**Wariant B (decyzja 2026-06-02):** rozcinamy na DWIE warstwy; nie tworzymy
osobnego pakietu `pbn_client_bpp`.

- **`src/pbn_client/`** — Warstwa 1, reusable, kandydat do ekstrakcji jako
  osobny pakiet PyPI. Wie tylko o pojęciach PBN: tokeny, URL-e, PBN UID, JSON-y,
  flagi `bool`. **Nie importuje `bpp` ani `pbn_api`.** Klasa `PBNClient` =
  kompozycja czystych mixinów (+ `StatementsMixin`), bez orchestracji.
- **`BppPBNClient` w `pbn_api/client`** — Warstwa 2, BPP-aware:
  `BppPBNClient(PBNClient, PublicationSyncMixin, DisciplinesMixin)` z
  `__init__(transport, uczelnia)`. Trzyma orchestrację i odczyt flag uczelni;
  **tu — i tylko tu — żyje wiedza o `Uczelnia`.** `get_default()` znika
  z podsystemu (zastąpione przez `self.uczelnia`).

Orchestracja i adaptery **ZOSTAJĄ w `pbn_api`**. Wyniesienie ich do osobnego
pakietu rozwiązywałoby problem, którego jeszcze nie mamy (ekstrakcja
`pbn_api`), a ta jest i tak zablokowana przez sklejenie modeli z BPP (patrz
„Nalecialości"). Konieczne jest tylko **odpięcie orchestracji od czystego
`PBNClient`** — nie jej fizyczne przeniesienie poza `pbn_api`.

Po splicie pytanie „czy `PBNClient` potrzebuje uczelni" znika: czysty
`pbn_client.PBNClient` nigdy jej nie zna, `BppPBNClient` zawsze ma ją
z konstrukcji.

## Dwupodział odpowiedzialności (cel)

- **`pbn_client`** — *protokół* PBN (reusable, do ekstrakcji). Bez Django-modeli,
  bez `bpp`, bez `pbn_api`.
- **`pbn_api`** — wszystko BPP↔PBN: *dane domenowe PBN* (lustro encji
  Publication/Institution/Journal/Scientist/Publisher/Conference/Discipline/
  Language/Country + słowniki + admin) ORAZ *logika integracji* (`BppPBNClient`
  + orchestracja + adaptery, znające `Uczelnia`/`Rekord`). Przyszły
  reusable-kandydat — dopiero po odseparowaniu sklejenia z BPP (osobny tor;
  orchestracja to tylko część tego sklejenia, modele to druga część).

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

### `BppPBNClient` w `pbn_api/client` (Warstwa 2, BPP-aware)

Brak osobnego pakietu. Pod Wariantem B:

- `pbn_client.PBNClient` = czysta kompozycja (pure mixiny + `StatementsMixin`),
  **bez** `PublicationSyncMixin`/`DisciplinesMixin`. Ląduje w
  `pbn_client/client.py`.
- `publication_sync.py` (orchestracja) + `disciplines.py` (`DisciplinesMixin`)
  **zostają** w `pbn_api/client`.
- `adapters/` **zostają** w `pbn_api/adapters` (bez przenoszenia). Zmiana tylko
  behawioralna: orchestracja przekazuje `uczelnia=self.uczelnia` do adaptera.
  Wewnętrzny `get_default()` adaptera (`wydawnictwo.py:94`) **zostaje jako
  fallback** — ścieżka `publication_sync` już go nie dotyka (jawna uczelnia),
  ale inni callerzy adaptera (`pbn_wysylka_oswiadczen/tasks`, management
  commands) wciąż na nim polegają. Ich migracja + usunięcie fallbacku = Phase 7.
- `pbn_api/client/__init__.py` definiuje `BppPBNClient` i re-eksportuje całość.

`BppPBNClient` **dziedziczy** po `PBNClient` (nie kompozycja delegująca), bo
call-site'y wołają na tym samym obiekcie i metody czyste (`get_journals`), i
orchestrację (`sync_publication`). Dziedziczenie = zero delegacji ~50 metod.

```python
# pbn_api/client/__init__.py
from pbn_client import PBNClient

from .disciplines import DisciplinesMixin
from .publication_sync import PublicationSyncMixin


class BppPBNClient(PBNClient, PublicationSyncMixin, DisciplinesMixin):
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
  (cykl `bpp.models.uczelnia → pbn_api.client → adapters → bpp.models`).
- `pbn_api.client` re-eksportuje **CAŁY dotychczasowy publiczny zestaw**
  (`__all__`): `PBNClient` (z `pbn_client`), `BppPBNClient` (zdefiniowany
  tutaj), `OAuthMixin`, wszystkie 9 klas mixinów,
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
- `BppPBNClient` żyje w `pbn_api/client` — **żadnej nowej appki Django**, zero
  zmian w `INSTALLED_APPS`, zero migracji. `pbn_api` pozostaje appką jak dziś.
- **Testy:** istniejące `pbn_api/tests/test_client*.py` zostają, importując
  przez shim `pbn_api.client` — dzięki temu „zielone" przez całą migrację.
  Relokacja testów czystych do `pbn_client/tests/` jest opcjonalna i późniejsza.
- **Baseline:** przed i po KAŻDEJ fazie odpalać celowany podzbiór
  (`uv run pytest src/pbn_api/tests/ src/pbn_integrator/tests/ -p no:cacheprovider`)
  jako bramkę regresji, niezależnie od pełnego suite'u.

## Ryzyka i mitygacje

| Ryzyko | Mitygacja |
|---|---|
| Cykl importów `bpp.models.uczelnia → pbn_api.client → adapters → bpp.models` | `Uczelnia.pbn_client()` importuje `BppPBNClient` **lokalnie w metodzie** |
| Pęknięcie 35 importów `pbn_api.client.PBNClient` | `pbn_api.client` re-eksportuje pełny `__all__` (`PBNClient` z `pbn_client` + `BppPBNClient`) |
| CLI `get_client` → orchestracja na czystym `PBNClient` (brak metod) | `get_client` zwraca `BppPBNClient` z `_resolve_uczelnia` |
| Czysty `PBNClient` instancjonowany wprost (`importer_publikacji`) i wołający orchestrację | Sprawdzić: te call-site'y wołają tylko czyste metody; orchestracja idzie przez fabrykę (`BppPBNClient`) |
| Brak pokrycia multi-hosted | Dodać fixture `dwie_uczelnie` + test: właściwy `pbn_app_token` w transporcie i flagi z właściwej uczelni |

## Plan etapowy (kolejność krytyczna)

1. ✅ **W1 bez ruszania zachowania:** `src/pbn_client/`, czyste moduły
   przeniesione, `pbn_api.client` re-eksportuje. (Faza 1, zrobione.)
2. ✅ **`StatementsMixin`** wycięty z `publication_sync.py` do
   `pbn_client/statements.py`. (Faza 2, zrobione.)
3. **Czysty `PBNClient` → `pbn_client/client.py`:** klasa = pure mixiny +
   `StatementsMixin` (bez `PublicationSyncMixin`/`DisciplinesMixin`).
   `pbn_client.__init__` eksportuje `PBNClient`. Zielone testy.
4. **`BppPBNClient` w `pbn_api/client/__init__.py`:**
   `BppPBNClient(PBNClient, PublicationSyncMixin, DisciplinesMixin)` z
   `__init__(transport, uczelnia)`. `pbn_api.client` re-eksportuje pełny `__all__`
   (`PBNClient` + `BppPBNClient` + reszta). Zielone testy.
5. ✅ **Fix multi-hosted (3B, zmiana zachowania):** w `publication_sync.py`
   `get_default()` → `self.uczelnia` (2 miejsca); orchestracja przekazuje
   `uczelnia=self.uczelnia` do `WydawnictwoPBNAdapter` (3 miejsca). Fabryki
   zwracają `BppPBNClient` (zrobione w 3A). Wewnętrzny `get_default()` adaptera
   zostaje jako fallback dla nie-zmigrowanych callerów (Phase 7).
6. ✅ **Test multi-hosted** (`test_multihosted.py`): dwie uczelnie z różnymi
   flagami; klient związany z drugą wybiera batch/selective wg SWOJEJ uczelni,
   nie `get_default()` (pierwszej). Failowałby przed 3B.
7. **(poza tym specem)** pozostałe znaleziska audytu Tier 🔴/🟠 nie-PBN
   (ORCID, `importer_publikacji/providers/pbn.py`, `importer_autorow_pbn`) oraz
   wątek `get_default` jako follow-up.

## Poza zakresem

- Szeroki refaktor `get_default` (osobny, **następny** wątek; patrz audyt).
- Izolacja nalecialości BPP w `pbn_api` (orchestracja + adaptery + FK
  `uczelnia`/`Rekord` w modelach + `matchuj_*` + `LinkDoPBNMixin`) — warunek
  ekstrakcji `pbn_api`, osobny przyszły tor. W tym specu nic z `pbn_api` nie
  jest wynoszone do osobnego pakietu.
- Fizyczna ekstrakcja `pbn_client` / `pbn_api` do osobnych repo/PyPI (dopiero
  gdy warstwy są stabilne i odseparowane).
