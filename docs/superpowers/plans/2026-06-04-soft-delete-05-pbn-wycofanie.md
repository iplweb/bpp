# Soft-delete — Faza 05: propagacja usunięcia na zewnątrz (PBN + nagrobki)

> 🔁 **ROZSZERZENIE ZAKRESU 2026-08-08 (decyzja właściciela).**
> Do tej fazy dochodzą **NAGROBKI** — ogłaszanie usunięć konsumentom
> przyrostowym. Powód: to ten sam motyw co wycofanie z PBN — *systemy
> zewnętrzne dowiadują się, że coś zniknęło*. Inny odbiorca, ta sama
> historia. Trzymane osobno przepadłyby między fazami, bo żaden plan ich nie
> obejmował, a handoff fazy 02 (§3.1) traktował je jako bramkę wydania.
>
> **Zakres nagrobków:**
> - **OAI-PMH**: `<header status="deleted">` w `src/cerif_export` (serwuje
>   `ListRecords`/`ListIdentifiers`/`resumptionToken`; **dziś ZERO obsługi
>   `deleted`**), respektujące `from`/`until`;
> - **CERIF**: odpowiednik nagrobka w formacie rekordu;
> - **`/api/v1/`**: sposób odkrycia usuniętych (endpoint „usunięte od…”
>   albo parametr).
>
> **Fundament jest gotowy** — soft-delete bumpuje `ostatnio_zmieniony`
> (kontrakt PINNED z fazy 01), więc lista nagrobków to po prostu
> `Model.deleted_objects.filter(ostatnio_zmieniony__gte=X)`. Nie trzeba
> `SoftDeleteLog` z fazy 06. Brakuje wyłącznie ekspozycji.
>
> ⚠️ **Termin:** nagrobki muszą być gotowe przed **fazą 07**, nie przed 04.
> Dopóki kasowanie jest rzadkie, luka w OAI-PMH jest teoretyczna; faza 07
> czyni kasowanie rutynowym i dopiero wtedy zaczyna realnie boleć.

> ✂️ **PODZIAŁ ZAKRESU 2026-08-10 (decyzja właściciela).** Ten plan realizuje
> **wyłącznie wycofanie z PBN** (Taski 05.0–05.9). **Nagrobki wychodzą do
> osobnej fazy 05b** i dostają własny cykl brainstorming → spec → plan → PR.
>
> Powód: to dwa niezależne podsystemy, które łączy tylko motyw („systemy
> zewnętrzne dowiadują się, że coś zniknęło"), a nie wspólny kod. Wycofanie
> z PBN ma gotowy, drobiazgowy plan; nagrobki miały **zero tasków** — sam
> baner rozszerzenia zakresu z 2026-08-08 nigdy nie doczekał się projektu.
> Wrzucenie obu w jeden PR dałoby PR-a nie do przejrzenia. Termin nagrobków
> (przed fazą 07) jest zachowany — nie zwalniamy z nich, tylko rozdzielamy.

---

## ⚠️ REWIZJA 2026-08-10 — DWA BLOKERY, których ten plan nie znał

> Ten plan powstał **2026-06-04**, a jego rewizje (08-06, 08-07) sprawdzały
> kolejkę i klienta PBN. Żadna nie sprawdziła, **co faza 02 dopisała do
> `check_if_record_still_exists()`** — a to przesądza o wykonalności Taska
> 05.3. Oba blokery mają jedną przyczynę: predykat „czy rekord nadal
> istnieje" nie wie, po co pytamy.

`src/pbn_export_queue/models.py:190` (commit `2e3b38611`, faza 02, PR #741):

```python
if getattr(obiekt, "deleted_at", None) is not None:
    return False
```

Wycofanie oświadczeń zlecamy **wyłącznie dla rekordów, które właśnie trafiły
do kosza**. Ten guard odrzuca więc dokładnie te wpisy, które faza 05 tworzy.

**Bloker #1 — gałąź WYCOFANIE nigdy się nie wykona.** `send_to_pbn()`
(`:473`) woła guard **przed** `_zajmij_atomowo()` (`:479`), a Task 05.3 każe
wstawić rozgałęzienie *po* `_zajmij_atomowo()`. Każdy wpis `WYCOFANIE`
kończyłby się na `error("Rekord został usunięty nim wysyłka była możliwa.")`
→ `FINISHED_ERROR`, a `withdraw_from_pbn()` byłby martwym kodem.

**Bloker #2 — sprzątaczka kasuje zlecenia wycofania (CICHY).**
`kolejka_wyczysc_wpisy_bez_rekordow()` (`tasks.py:105`) iteruje po CAŁEJ
kolejce i `delete()`-uje wpisy, dla których guard zwraca `False`. Wpis
`WYCOFANIE` znika z kolejki, oświadczenia zostają w PBN, nie ma po tym
śladu. Wyścig między beatem sprzątającym a workerem, rozstrzygany losowo.
Ten jest gorszy od #1, bo #1 zostawia przynajmniej `FINISHED_ERROR`
z komunikatem.

**ROZSTRZYGNIĘCIE (Opcja A): guard staje się świadomy operacji.**
Odrzucenie soft-deleted obowiązuje tylko dla `WYSYLKA`:

```python
if (
    self.operacja != self.Operacja.WYCOFANIE
    and getattr(obiekt, "deleted_at", None) is not None
):
    return False
```

Dlaczego tak, a nie „rozgałęzienie na starcie `send_to_pbn()`":

- naprawia **oba** blokery jedną zmianą — sprzątaczka woła tę samą metodę na
  instancji, więc dziedziczy świadomość operacji **za darmo**; wariant
  z wczesnym rozgałęzieniem leczy tylko #1 i zostawia #2 cichym,
- ścieżka `WYSYLKA` nietknięta (default pola to `WYSYLKA`), istniejący
  `test_check_if_record_still_exists_with_deleted_record`
  (`test_pbn_queue_status.py:97`) zostaje zielony bez zmian,
- kolejność wstawki w `send_to_pbn()` **dokładnie jak w oryginalnym Tasku
  05.3** — wycofanie nadal dziedziczy `_zajmij_atomowo()`, `ilosc_prob`
  i ochronę przed dwoma workerami,
- brak duplikacji `_zajmij_atomowo()` i drugiego guardu „rekord zniknął".

**Świadomie zaakceptowana konsekwencja:** wpis `WYCOFANIE` dla rekordu
skasowanego **twardo** (wiersza nie ma) nadal kończy się `FINISHED_ERROR` —
bez wiersza nie odczytamy `pbn_uid`. Oświadczenia zostają wtedy w PBN.
To poprawna „głośna porażka", ale należy ją odnotować w handoffie fazy 06:
`SoftDeleteLog` i tak ma nieść `pbn_status`, więc to on jest właściwym
miejscem na przechowanie `pbn_uid` niezależnie od rekordu.

**Odrzucona opcja C:** trzymać `pbn_uid` na samym wpisie kolejki (nowe pole
+ migracja), żeby wycofanie w ogóle nie zależało od rekordu. Przeżyłoby
twarde kasowanie, ale rozjeżdża się z kontraktem, którego oczekuje faza 06,
a twarde kasowanie publikacji jest po fazach 02/04 zablokowane guardami.

**Zmiany w tym planie wynikające z rewizji:** Task 05.3 dostaje krok
„guard świadomy operacji" **przed** krokiem z rozgałęzieniem; dochodzi
**Task 05.3a** (regresja sprzątaczki). Numery linii w „Stanie zastanym"
dryfnęły o ~10 w górę względem 2026-08-07 — patrz nagłówek tej sekcji.

---

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. TDD: każdy krok najpierw PRAWDZIWY failing test → komenda + FAIL → PRAWDZIWA implementacja → komenda + PASS → commit.

**Goal:** Rozszerzyć `pbn_export_queue` o operację `WYCOFANIE` (obok dotychczasowej `WYSYLKA`), tak by soft-delete publikacji mógł asynchronicznie wycofać oświadczenia dyscyplin z profilu instytucji PBN przez `client.delete_all_publication_statements(pbn_uid)`, z retry/locking/błędami jak istniejąca ścieżka wysyłki. Dostarczyć publiczne funkcje zakolejkowujące (`zakolejkuj_wycofanie`, `zakolejkuj_wysylke`) wołane potem z fazy 06, oraz zaktualizować `SentData` po udanym wycofaniu (`submitted_successfully=False` + znacznik `withdrawn_at`), bez kasowania wiersza.

> 🔄 **Zmiana zakresu 2026-08-06 (decyzja #16).** Wycofanie musi działać **dwoma wejściami**, nie jednym: rekord bywa wysyłany do PBN także **synchronicznie, bez kolejki** (`synchronizuj_publikacje`, `src/pbn_integrator/utils/synchronization.py:180`). Dlatego logika wycofania ma mieszkać w **wolnostojącej funkcji-prymitywie**, a `withdraw_from_pbn()` na modelu kolejki jest tylko jej cienkim wywołaniem. Patrz Task 05.0 i 05.9.

**Architecture:** Nowe pole `operacja` (`TextChoices` `WYSYLKA="wysylka"`/`WYCOFANIE="wycofanie"`, default `WYSYLKA` dla kompatybilności wstecznej) na `PBN_Export_Queue`. `send_to_pbn()` rozgałęzia się **po** atomowym zajęciu wiersza (`_zajmij_atomowo()`): `WYCOFANIE` → nowa metoda `withdraw_from_pbn()`, będąca **cienkim wywołaniem prymitywu** `wycofaj_oswiadczenia()` (klient PBN z `self.uczelnia`, klasyfikacja wyjątków przez istniejące `_handle_pbn_exception`); `WYSYLKA` → dotychczasowa ścieżka bez zmian. Gate zakolejkowania: wycofanie tylko gdy rekord ma `pbn_uid_id`; `zamowil` dla operacji systemowych to konto techniczne (Task 05.4a).

> 📌 **Rewizja 2026-08-07 (dług dokumentacyjny).** Plan opisywał kod sprzed
> przebudowy kolejki (`_zajmij_atomowo`, `LOCKED_ELSEWHERE`, FK `uczelnia`),
> sprzed wyprowadzenia klienta PBN do pakietu `pbn-client` i sprzed
> uczelnia-scopingu `SentData`; numery migracji były o trzy do tyłu;
> Task 05.3 łamał decyzję #16, a Task 05.5 rozjeżdżał się kontraktem
> z fazą 06 i kasował zabezpieczenie TOCTOU. Doszedł **Task 05.4a**
> (konto techniczne + rozróżnienie `IntegrityError`), bo bez niego
> systemowy soft-delete **po cichu** nie wycofywał oświadczeń z PBN.

**Tech Stack:** Django, PostgreSQL, Celery + `pbn_export_queue`, `pbn_api` (`PBNClient`, `SentData`), pytest + model_bakery + `unittest.mock`.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md) (§4 całość) · Indeks: [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md) (kontrakt `pbn_export_queue` rozszerzenie + `SentData`).

**Zależność:** Faza 02 (publikacje `SoftDeleteModel`). Faza 06 woła `zakolejkuj_wycofanie`/`zakolejkuj_wysylke` z receiverów sygnałów — tu budujemy mechanizm + funkcje, NIE podpinamy sygnałów.

---

## Reguły BPP (obowiązują w każdym kroku)

- Wszystkie komendy Pythona przez `uv run` (np. `uv run pytest ...`).
- Testy: pytest, standalone functions / klasy bez `unittest.TestCase`, `@pytest.mark.django_db`, `model_bakery.baker.make`, mock klienta PBN przez `unittest.mock`.
- Max długość linii 88 znaków (ruff). Komentarze/teksty po polsku.
- **NIE modyfikować istniejących migracji** w `src/*/migrations/`. Stan na
  2026-08-07: ostatnia migracja `pbn_export_queue` to
  `0010_atomowa_kolejka_pbn.py` → nowa będzie **`0011_*`** (a NIE `0008_*`, jak
  pisała pierwsza wersja planu: `0008`/`0009` dołożyły FK `uczelnia`, `0010` —
  częściowy unikat aktywnego wpisu). Ostatnia migracja `pbn_api` to
  `0079_constraint_publikacja_instytucji.py` → nowa **`0080_*`**. **Przed
  pisaniem sprawdź `ls` obu katalogów** — numery mogły znów urosnąć.
- Po każdym kroku z kodem produkcyjnym: `ruff check` + `ruff format` na dotkniętych plikach, potem commit.
- Commituj **po jawnych ścieżkach** (`git add <plik> …`), nie `git add -A` —
  na tej gałęzi bywa równolegle więcej niż jeden wykonawca.

---

## Stan zastany (zweryfikowany w kodzie 2026-08-07 — używać tych nazw VERBATIM)

> ⚠️ **Poprzednia wersja tej sekcji opisywała kod, którego już nie ma.**
> Kolejka została przebudowana na atomowy row-claim, doszedł FK `uczelnia`,
> a klient PBN wyprowadzono do zewnętrznego pakietu. Poniżej stan faktyczny;
> wszystkie cytaty `plik:linia` zweryfikowane.

`src/pbn_export_queue/models.py`:
- `PBN_Export_Queue` pola: `object_id`, `content_type`, `rekord_do_wysylki`
  (GFK), `zamowil` (FK user, `on_delete=CASCADE`, **NOT NULL** — `:101`),
  **`uczelnia`** (FK `bpp.Uczelnia`, `null=True`, `related_name=
  "pbn_export_queue"` — `:103`), `zamowiono`, `wysylke_podjeto`,
  `wysylke_zakonczono`, `ilosc_prob`, `zakonczono_pomyslnie`, `komunikat`,
  `retry_after_user_authorised`, `rodzaj_bledu`
  (`RodzajBledu.TECHNICZNY/MERYTORYCZNY`), `wykluczone`.
- `Meta.constraints` (`:146-155`): częściowy unikat
  **`pbn_export_queue_jeden_aktywny_wpis_na_rekord`** na
  `(content_type, object_id)` `WHERE wysylke_zakonczono IS NULL`.
- Manager `PBN_Export_QueueManager` (`:34`):
  - `filter_rekord_do_wysylki(rekord)` (filtr `wysylke_zakonczono=None`),
  - **`sprobuj_utowrzyc_wpis(user, rekord, uczelnia=None)`** (`:42`) — szybka
    ścieżka `exists()` → `AlreadyEnqueuedError`, a następnie
    `with transaction.atomic(): self.create(...)` z `except IntegrityError`
    tłumaczonym na `AlreadyEnqueuedError` (`:53-63`, zabezpieczenie TOCTOU).
    **Tej metody NIE przepisujemy od zera** — rozszerzamy o `operacja`
    (Task 05.5) i uszczelniamy rozpoznanie wyjątku (Task 05.4a). Savepoint
    + tłumaczenie kolizji unikatu MUSZĄ zostać.
- `SendStatus` (Enum, `:66`): `RETRY_SOON`, `RETRY_LATER`, `RETRY_MUCH_LATER`,
  `RETRY_AFTER_USER_AUTHORISED`, `WYKLUCZONE`, `FINISHED_OKAY`,
  `FINISHED_ERROR`, **`LOCKED_ELSEWHERE`** (`:80` — dodany przy row-claimie).
- **`_zajmij_atomowo()` (`:419`)** — `select_for_update(skip_locked=True)`
  w krótkiej transakcji; ustawia `wysylke_podjeto`, zeruje
  `retry_after_user_authorised`, inkrementuje `ilosc_prob`
  (`save(update_fields=[...])`), na końcu `refresh_from_db()`. Zwraca `False`,
  gdy wiersz trzyma inny worker. ⚠️ **Bloku
  „`wysylke_podjeto`/`ilosc_prob`" wewnątrz `send_to_pbn()` JUŻ NIE MA** —
  nie ma czego „przenosić" (Task 05.3 dawniej tak kazał).
- **`send_to_pbn()` (`:466` — plan pisał `:456`)**, kolejność:
  `refresh_from_db()` → wczesny zwrot
  `FINISHED_OKAY` gdy `wysylke_zakonczono is not None` →
  **`check_if_record_still_exists()` (`:473` — ⚠️ BLOKER #1, patrz rewizja
  2026-08-10)** → `error(...)` →
  `if not self._zajmij_atomowo(): return SendStatus.LOCKED_ELSEWHERE` →
  import + `sprobuj_wyslac_do_pbn_celery(user=self.zamowil.get_pbn_user(),
  obj=self.rekord_do_wysylki, force_upload=True, **uczelnia=self.uczelnia**)`
  → `_handle_pbn_exception(exc)` / `error(...)` gdy `sent_data is None` /
  `_handle_successful_send(sent_data, notificator)`.
- Pozostałe: `error(msg, rodzaj=None)` (`:241`), **`exclude(msg)`** (`:249` →
  `SendStatus.WYKLUCZONE`), `dopisz_komunikat` (`:232`),
  `check_if_record_still_exists` (`:170`), `prepare_for_resend` (`:188`),
  `sprobuj_wyslac_do_pbn()` (`:227`), `_handle_retry_exception` (`:284` —
  `PraceSerwisowe`→RETRY_MUCH_LATER, `NeedsPBNAuthorisation`→
  RETRY_AFTER_USER_AUTHORISED, `ResourceLocked`/HTTP 423→RETRY_LATER,
  `StatementsResendFailed`→RETRY_LATER), `_handle_exclude_exception` (`:329`),
  `_handle_pbn_exception` (`:351`), `_handle_successful_send` (`:402`).
  **`_handle_pbn_exception` jest wspólną klasyfikacją błędów dla obu
  operacji** — wycofanie ma z niej korzystać, nie budować własnej drabinki
  `except`.

⚠️ **`check_if_record_still_exists()` (`:170`) ma DWÓCH konsumentów, nie
jednego.** Poza `send_to_pbn()` woła go `kolejka_wyczysc_wpisy_bez_rekordow()`
(`tasks.py:105`, BLOKER #2) oraz renderer alarmu Rollbara (`tasks.py:301`,
etykieta `<rekord usunięty>` — po zmianie wpis WYCOFANIE pokaże prawdziwe
`str(rekord)`, co jest ulepszeniem: widać, czego dotyczy błąd). Każda zmiana
tego predykatu dotyka wszystkich trzech.

📌 **GFK rozwiązuje rekord z kosza — sprawdzone w źródle Django, nie
założone.** `GenericForeignKey.__get__` (`contenttypes/fields.py:262`) woła
`ct.get_object_for_this_type()`, a ta (`contenttypes/models.py:179`) idzie
przez `_base_manager`, który faza 04 przypięła jako **niefiltrujący**
(handoff fazy 04, §4). Dlatego `self.rekord_do_wysylki` w gałęzi wycofania
zwróci soft-skasowaną publikację razem z jej `pbn_uid_id`.

`src/pbn_export_queue/tasks.py`:
- `task_sprobuj_wyslac_do_pbn(pk)` — lock przez `cache.add(LOCK_PREFIX+pk)`,
  `wait_for_object`, `p.send_to_pbn()`, `match` na `SendStatus` (RETRY_* →
  `apply_async(countdown=...)`, `FINISHED_OKAY` → `check_and_send_next_in_queue()`,
  `LOCKED_ELSEWHERE` obsłużony razem z `FINISHED_ERROR` — `:63-69`). Lock
  zwalniany w `finally`. **Ta sama maszyneria obsłuży WYCOFANIE bez zmian** —
  `send_to_pbn()` zwraca `SendStatus`.

**Klient PBN to ZEWNĘTRZNY PAKIET `pbn-client`, nie kod repo.**
`src/pbn_api/client/mixins/` zawiera dziś wyłącznie `__pycache__` —
**każdy cytat `src/pbn_api/client/mixins/institutions.py:87` (w tym planie,
w specu §4.1 i w indeksie 00) jest martwy.** Realne lokalizacje:
- `delete_all_publication_statements(publicationId)` —
  **`pbn_client/mixins/institutions.py:87`** (site-packages). Sam mapuje
  HTTP 400 z PBN na `CannotDeleteStatementsException` /
  `ResourceLockedException` — wołający NIE parsuje treści odpowiedzi.
- `_delete_statements_with_retry(pbn_uid_id, max_tries=5)` —
  **`pbn_client/statements.py:211`** (site-packages), ponawia **wyłącznie**
  na `CannotDeleteStatementsException`. ⚠️ To NIE jest wzorzec dla naszego
  wycofania: u nas `CannotDeleteStatementsException` = „nie ma czego
  kasować" = **sukces**, nie powód do retry.
- W repo zostały tylko BPP-owe mixiny: `src/pbn_api/client/publication_sync.py`
  (`_pre_upload_clear_pbn_statements_if_any` `:95`, `_post_statements_with_retry`
  `:331`, `_download_statements_with_retry` `:498` — `_delete_statements_with_retry`
  tam **nie istnieje**) oraz `disciplines.py`; `BppPBNClient` sklejany
  w `src/pbn_api/client/__init__.py:85` (zna swoją `uczelnia`).
- **Wzorzec obsługi wyjątków do przejęcia:**
  `src/pbn_wysylka_oswiadczen/tasks.py::_delete_existing_statements`
  (`:54-76`) — `CannotDeleteStatementsException` → `pass` (OK, nic nie było),
  `PraceSerwisoweException` → `raise`, `HttpException` → zapis błędu.
- Wyjątki importuje się z `pbn_api.exceptions` (re-eksport) — tak jak robi to
  już `pbn_export_queue/models.py:17-29`.

`src/pbn_api/models/sentdata.py` — ⚠️ **`SentData` jest scope'owane po
uczelni** (multi-hosted). Wszystkie metody managera mają `uczelnia=None`:
`get_for_rec(rec, uczelnia=None)` (`:23`), `mark_as_successful(rec,
pbn_uid_id=None, api_response_status="", uczelnia=None)` (`:85`),
`mark_as_failed(rec, exception="", api_response_status="", uczelnia=None)`
(`:97`), `create_or_update_before_upload(...)` (`:57`). Model ma FK `uczelnia`
(`:206`). **Gdy dla `(object_id, content_type)` istnieją ≥2 wiersze, lookup
BEZ `uczelnia` rzuca `MultipleObjectsReturned`** — dlatego `mark_as_withdrawn`
MUSI przyjmować `uczelnia` (Task 05.2), a prymityw MUSI je przekazywać.
Pola: `content_type`/`object_id`/`object` (GFK), `uczelnia`,
`submitted_successfully`, `submitted_at`, `api_response_status`, `api_url`,
`uploaded_okay`, `exception`, `fee_sent`, `fee_uploaded_okay`, `pbn_uid`
(FK `pbn_api.Publication`). Pola `withdrawn_at` **nie ma**
(`grep -rn withdrawn_at src/` → 0 trafień).

`src/bpp/admin/helpers/pbn_api/cli.py:36`:
- `sprobuj_wyslac_do_pbn_celery(user, obj, force_upload=False,
  pbn_client=None, **uczelnia=None**)` — buduje
  `pbn_client = uczelnia.pbn_client(user.pbn_token)`; bez `uczelnia` robi
  `Uczelnia.objects.get()` (przy >1 rzuca — multi-hosted MUSI podać jawnie).

**Uczelnia: `Uczelnia.objects.get_default()` NIE ISTNIEJE.** Została trwale
usunięta w audycie multi-hosted i jest pilnowana testem-guardem
`src/bpp/tests/test_multihosted_get_default_guard.py::test_get_default_usuniete_na_trwale`
(0 dozwolonych wystąpień w `src/`, **także w komentarzach**). Kod z jej użyciem
wywali CI. Dostępne API (`src/bpp/models/uczelnia.py`):
`get_for_request(request)`, `get_for_pbn_background(uczelnia_id)` (`:144` —
rzuca `ValueError` gdy `None`, świadomie BEZ fallbacku),
`get_single_uczelnia_or_none()` (`:48`), `get_single_uczelnia_or_fail()`
(`:59`), `Uczelnia.pbn_client(token)` (`:936`, zwraca `BppPBNClient`).

`src/bpp/models/profile.py`: `BppUser.pbn_token` (`CharField`, default `""`),
`get_pbn_user()` (`:207`) — zwraca `przedstawiaj_w_pbn_jako`, gdy ustawione,
inaczej `self`. Istotne dla konta technicznego (Task 05.4a).

`src/bpp/models/abstract/pbn.py`: rekordy mają `pbn_uid = OneToOneField("pbn_api.Publication")` → `rec.pbn_uid_id` to PBN UID (string id publikacji w PBN).

---

## Decyzja: znacznik wycofania w `SentData` — nowe pole `withdrawn_at`

**Wybór: dodać nowe pole `withdrawn_at = models.DateTimeField(null=True, blank=True)` na `SentData`** (migracja `pbn_api/migrations/0XXX`).

**Uzasadnienie (dlaczego NIE `api_response_status`):** `api_response_status` to swobodny `TextField` nadpisywany przy KAŻDEJ operacji (`mark_as_successful`/`mark_as_failed`/`create_or_update_before_upload` go czyszczą/ustawiają surową odpowiedzią API). Użycie go jako znacznika stanu byłoby kruche — pierwsza kolejna wysyłka by go skasowała, a parsowanie statusu z tekstu odpowiedzi PBN jest nieodporne. Dedykowane `withdrawn_at` (timestamp) daje: (1) jednoznaczny, kwerowalny stan "rekord wycofany w PBN dnia X", (2) audyt kiedy, (3) symetrię: restore→`WYSYLKA`→`mark_as_successful` musi je wyzerować (`withdrawn_at=None`). Wiersza `SentData` NIE kasujemy (zostaje dla re-matchingu przy restore i dla `SoftDeleteLog` w fazie 06).

⚠️ **Wycofanie jest per-uczelnia, nie globalne.** `SentData` ma FK `uczelnia`
i dwie uczelnie wysyłające ten sam rekord BPP mają DWA niezależne wiersze.
Wycofanie zleca konkretna uczelnia (`PBN_Export_Queue.uczelnia`), więc
`withdrawn_at` ustawiamy **tylko na jej wierszu** — każde dotknięcie
`SentData` w tej fazie przekazuje `uczelnia=` w dół. Wołanie
`get_for_rec(rec)` bez `uczelnia` przy ≥2 wierszach rzuci
`MultipleObjectsReturned`.

---

## Tasks

### Task 05.0 — Prymityw `wycofaj_oswiadczenia()` (jedno miejsce prawdy)

> Dodane 2026-08-06 (decyzja #16). **Rób to PRZED 05.3** — `withdraw_from_pbn()`
> ma być cienkim wywołaniem tego prymitywu, nie własną implementacją.
>
> ⚠️ **Kolejność:** prymityw woła `SentData.objects.mark_as_withdrawn(...)`,
> którą dostarcza dopiero **Task 05.2**. Zrób więc 05.2 **przed** 05.0
> (albo scal oba w jeden krok) — inaczej testy 05.0 padną na `AttributeError`
> z powodu, który nie jest przedmiotem testu.

Cała logika wycofania mieszka w wolnostojącej funkcji, żeby wejście
asynchroniczne (kolejka) i synchroniczne (`synchronizuj_publikacje`)
zostawiały **identyczny** stan `SentData` i identyczną klasyfikację błędów.

**Files:**
- Create: `src/pbn_api/wycofanie.py` (lub `src/pbn_export_queue/wycofanie.py` —
  wybierz tak, by NIE powstał cykl importów: prymityw nie może importować
  modelu kolejki)
- Test: `src/pbn_api/tests/test_wycofanie.py`

Kontrakt (PINNED — pozostałe taski cytują te nazwy):

```python
class StatusWycofania(models.TextChoices):
    WYCOFANO = "wycofano"        # DELETE poszedł, oświadczenia usunięte
    BRAK_OSWIADCZEN = "brak"     # PBN: nie było czego usuwać — też sukces
    POMINIETO = "pominieto"      # brak pbn_uid — klienta w ogóle nie wołamy


@dataclass
class WynikWycofania:
    status: StatusWycofania
    komunikat: str


def wycofaj_oswiadczenia(publikacja, client, uczelnia=None) -> WynikWycofania:
    """Wycofuje oświadczenia dyscyplin publikacji z profilu instytucji PBN.

    Gate: publikacja bez pbn_uid -> WynikWycofania(POMINIETO) (nie błąd),
    bez dotykania SentData i bez wołania klienta.
    Obiektu publikacji w PBN NIE kasujemy (jest współdzielony).
    Po sukcesie aktualizuje SentData WIERSZA TEJ UCZELNI:
    submitted_successfully=False + withdrawn_at (SentData.DoesNotExist ->
    nie jest błędem, po prostu nie ma czego oznaczać).

    Wyjątki PBN (PraceSerwisowe / ResourceLocked / Http / …) PROPAGUJE —
    klasyfikuje je wywołujący (kolejka: _handle_pbn_exception, ścieżka
    synchroniczna: własna obsługa). Prymityw odpowiada za semantykę
    „co znaczy sukces" i za stan SentData, NIE za politykę retry.
    """
```

> **Podział odpowiedzialności (ważne dla 05.3 i 05.9):** prymityw = gate +
> wywołanie klienta + idempotencja (`CannotDeleteStatementsException`) +
> `SentData`. Wywołujący = klasyfikacja wyjątku i decyzja o ponowieniu.
> Dzięki temu kolejka reużywa istniejące `_handle_pbn_exception`
> (`models.py:351`) zamiast dublować drabinkę `except`.

- [ ] **Krok 05.0.1 — testy obsługi wyjątków (wzorzec do przejęcia:
  `src/pbn_wysylka_oswiadczen/tasks.py:54-76`).** Przypadki:
  - `CannotDeleteStatementsException` → **SUKCES** `BRAK_OSWIADCZEN`
    (oświadczeń nie było — stan docelowy osiągnięty), `SentData` oznaczone
    jak przy `WYCOFANO`. To NIE jest błąd; zaległa pułapka.
  - `PraceSerwisoweException` → propaguj (retry ma sens, PBN w oknie
    serwisowym); `SentData` NIE dotknięte.
  - `HttpException` (w tym 423) → propaguj; `SentData` NIE dotknięte.
    ⚠️ Zmiana względem pierwszej wersji planu („błąd zaklasyfikowany"):
    klasyfikacja należy do wywołującego, inaczej kolejka miałaby dwie
    rozjeżdżające się tabele wyjątków.
  - `pbn_uid is None` → `POMINIETO`, bez wołania klienta i bez `SentData`.
  - `SentData.DoesNotExist` (rekord ma `pbn_uid`, ale nigdy nie było wiersza)
    → nadal `WYCOFANO`, bez wyjątku.
- [ ] **Krok 05.0.2 — implementacja** + aktualizacja `SentData` wewnątrz
  prymitywu (NIE u wywołującego), z przekazaniem `uczelnia=` do
  `mark_as_withdrawn`.
- [ ] **Krok 05.0.3 — PASS** + commit (jawne ścieżki).

---

### Task 05.1 — Pole `operacja` na `PBN_Export_Queue` + migracja

**Files:**
- `src/pbn_export_queue/models.py` (klasa `PBN_Export_Queue`, dodać `Operacja` TextChoices + pole `operacja`)
- `src/pbn_export_queue/migrations/0011_pbn_export_queue_operacja.py` (NOWA —
  numer wg `ls src/pbn_export_queue/migrations/`; ostatnia dziś to `0010_*`)
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py` (NOWY)

- [ ] **Failing test — pole `operacja` istnieje z defaultem `WYSYLKA`.** W nowym pliku `src/pbn_export_queue/tests/test_operacja_wycofanie.py`:
  ```python
  from unittest.mock import MagicMock, patch

  import pytest
  from model_bakery import baker

  from pbn_export_queue.models import (
      PBN_Export_Queue,
      SendStatus,
  )


  @pytest.mark.django_db
  def test_operacja_default_wysylka(wydawnictwo_ciagle, admin_user):
      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
      )
      wpis.refresh_from_db()
      assert wpis.operacja == PBN_Export_Queue.Operacja.WYSYLKA
      assert PBN_Export_Queue.Operacja.WYSYLKA == "wysylka"
      assert PBN_Export_Queue.Operacja.WYCOFANIE == "wycofanie"
  ```
- [ ] **Komenda + FAIL:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_operacja_default_wysylka -x` → `AttributeError`/`FieldError` (brak `operacja`).
- [ ] **Implementacja — TextChoices + pole.** W `src/pbn_export_queue/models.py`, w klasie `PBN_Export_Queue` (po polach, przed `objects = ...`):
  ```python
      class Operacja(models.TextChoices):
          WYSYLKA = "wysylka", "Wysyłka"
          WYCOFANIE = "wycofanie", "Wycofanie oświadczeń"

      operacja = models.CharField(
          max_length=16,
          choices=Operacja.choices,
          default=Operacja.WYSYLKA,
          db_index=True,
          verbose_name="Operacja",
      )
  ```
- [ ] **Migracja:** `uv run python src/manage.py makemigrations pbn_export_queue --name pbn_export_queue_operacja`. Zweryfikuj, że plik to `0011_pbn_export_queue_operacja.py` (kolejny po `0010_atomowa_kolejka_pbn.py`) i dodaje wyłącznie pole `operacja` (`AddField`, default `wysylka`). NIE edytować wcześniejszych migracji.
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_operacja_default_wysylka -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/models.py src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/models.py src/pbn_export_queue/migrations/0011_pbn_export_queue_operacja.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit** (jawne ścieżki): `git commit -m "feat(pbn_export_queue): pole operacja (WYSYLKA|WYCOFANIE) + migracja"`

---

### Task 05.2 — `withdrawn_at` na `SentData` + symetria w managerze

**Files:**
- `src/pbn_api/models/sentdata.py` (pole `withdrawn_at`; manager: `mark_as_withdrawn`; reset `withdrawn_at` w `mark_as_successful`)
- `src/pbn_api/migrations/0080_sentdata_withdrawn_at.py` (NOWA — numer wg
  `makemigrations`; ostatnia dziś to `0079_constraint_publikacja_instytucji.py`)
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — `mark_as_withdrawn` ustawia stan, `mark_as_successful` go zeruje.** Dopisz do `test_operacja_wycofanie.py`:
  ```python
  @pytest.mark.django_db
  def test_sentdata_mark_as_withdrawn(wydawnictwo_ciagle):
      from pbn_api.models.sentdata import SentData

      SentData.objects.create(
          object=wydawnictwo_ciagle,
          data_sent={},
          submitted_successfully=True,
          uploaded_okay=True,
      )

      SentData.objects.mark_as_withdrawn(wydawnictwo_ciagle)

      sd = SentData.objects.get_for_rec(wydawnictwo_ciagle)
      assert sd.submitted_successfully is False
      assert sd.withdrawn_at is not None

      # restore → ponowna wysyłka zeruje znacznik wycofania
      SentData.objects.mark_as_successful(wydawnictwo_ciagle)
      sd = SentData.objects.get_for_rec(wydawnictwo_ciagle)
      assert sd.submitted_successfully is True
      assert sd.withdrawn_at is None
  ```
- [ ] **Komenda + FAIL:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_sentdata_mark_as_withdrawn -x` → `AttributeError` (`mark_as_withdrawn`/`withdrawn_at`).
- [ ] **Implementacja — pole.** W `src/pbn_api/models/sentdata.py`, w klasie `SentData` (przy polach śledzenia, po `api_url`):
  ```python
      withdrawn_at = models.DateTimeField(
          "Data wycofania oświadczeń",
          null=True,
          blank=True,
          db_index=True,
          help_text="Ustawiane po udanym wycofaniu oświadczeń z PBN "
          "(soft-delete publikacji). Zerowane przy ponownej wysyłce.",
      )
  ```
- [ ] **Implementacja — manager `mark_as_withdrawn`.** W `SentDataManager` dodaj:
  ```python
      def mark_as_withdrawn(self, rec, api_response_status="", uczelnia=None):
          """Oznacza rekord jako wycofany z PBN (oświadczenia usunięte).

          ``uczelnia`` obowiązkowe w praktyce (multi-hosted): wycofanie
          dotyczy profilu KONKRETNEJ uczelni, a przy ≥2 wierszach
          ``get_for_rec`` bez niej rzuci MultipleObjectsReturned. Default
          ``None`` tylko dla zgodności z resztą managera.

          Wiersza SentData NIE kasujemy — zostaje dla audytu i
          re-matchingu przy restore. submitted_successfully=False, bo
          rekord nie jest już "wystawiony" w PBN.
          """
          sd = self.get_for_rec(rec, uczelnia)
          sd.submitted_successfully = False
          sd.withdrawn_at = timezone.now()
          if api_response_status:
              sd.api_response_status = api_response_status
          sd.save()
          return sd
  ```
  ⚠️ Sygnatura idzie **za** konwencją reszty `SentDataManager`
  (`uczelnia=None` jako OSTATNI kwarg — `get_for_rec` `:23`,
  `mark_as_successful` `:85`, `mark_as_failed` `:97`). Nie wymyślaj innej.
- [ ] **Implementacja — symetria w `mark_as_successful`.** W `SentDataManager.mark_as_successful`, po `sd.submitted_successfully = True`, dodaj `sd.withdrawn_at = None` (restore→WYSYLKA czyści znacznik wycofania). (`timezone` jest już zaimportowany w pliku.)
- [ ] **Test symetrii per-uczelnia (dopisz):** dwa wiersze `SentData` dla
  tego samego rekordu i dwóch uczelni; `mark_as_withdrawn(rec,
  uczelnia=u1)` ustawia `withdrawn_at` **tylko** na wierszu `u1`, a wiersz
  `u2` zostaje `submitted_successfully=True`. Bez tego testu regresja
  „wycofanie jednej uczelni kasuje stan drugiej" przejdzie niezauważona.
- [ ] **Migracja:** `uv run python src/manage.py makemigrations pbn_api --name sentdata_withdrawn_at`. Zweryfikuj, że dodaje wyłącznie pole `withdrawn_at`.
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_sentdata_mark_as_withdrawn -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_api/models/sentdata.py src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_api/models/sentdata.py src/pbn_api/migrations/*sentdata_withdrawn_at*.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit** (jawne ścieżki): `git commit -m "feat(pbn_api): SentData.withdrawn_at + mark_as_withdrawn; reset przy mark_as_successful"`

---

### Task 05.3 — `withdraw_from_pbn()` (CIENKI wrapper na prymityw) + rozgałęzienie w `send_to_pbn()`

> ⚠️ **Przepisane 2026-08-07.** Poprzednia wersja tego tasku: (a) łamała
> decyzję #16 i niezmiennik §4.2 specu — re-implementowała retry, wołała
> `delete_all_publication_statements` bezpośrednio i sama aktualizowała
> `SentData`, zamiast użyć prymitywu z 05.0; (b) kazała „przenieść blok
> `wysylke_podjeto`/`ilosc_prob`", którego w `send_to_pbn()` **nie ma** —
> zastąpił go `_zajmij_atomowo()` (`models.py:419`); (c) pozyskiwała uczelnię
> przez **nieistniejące** `Uczelnia.objects.get_default()`, co dodatkowo
> wywala guard-test multi-hosted.

Gałąź `WYCOFANIE` **nie zawiera logiki wycofania**: pozyskuje klienta PBN,
woła `wycofaj_oswiadczenia()` (Task 05.0) i tłumaczy wynik/wyjątek na
`SendStatus` — wyjątki przez istniejące `_handle_pbn_exception`
(`ResourceLocked`→`RETRY_LATER`, `PraceSerwisowe`→`RETRY_MUCH_LATER`,
HTTP 423→`RETRY_LATER`, reszta→`error(...)`). `WYSYLKA` → ścieżka bez zmian.
Lock/`ilosc_prob`/`task_sprobuj_wyslac_do_pbn` działają niezmienione
(zwracamy ten sam typ `SendStatus`).

**Files:**
- `src/pbn_export_queue/models.py` (`send_to_pbn` rozgałęzienie; nowa `withdraw_from_pbn`; helper `_pozyskaj_klienta_pbn`)
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — WYCOFANIE woła `delete_all_publication_statements` z właściwym pbn_uid + oznacza SentData.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_wycofanie_wola_delete_all_statements(
      wydawnictwo_ciagle, admin_user, uczelnia
  ):
      from pbn_api.models import Publication
      from pbn_api.models.sentdata import SentData

      pub = baker.make(Publication, pk="PBN-UID-123")
      wydawnictwo_ciagle.pbn_uid = pub
      wydawnictwo_ciagle.save()
      SentData.objects.create(
          object=wydawnictwo_ciagle,
          data_sent={},
          submitted_successfully=True,
          uploaded_okay=True,
          uczelnia=uczelnia,
      )

      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
          uczelnia=uczelnia,
          operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
          wysylke_zakonczono=None,
      )

      # ⚠️ KLUCZOWE (rewizja 2026-08-10): rekord MUSI być w koszu.
      # Wycofania zlecamy wyłącznie dla soft-skasowanych publikacji, więc
      # test bez tego kroku NIE odtwarza blokera #1 — przeszedłby także
      # przed poprawką guardu i niczego by nie pilnował.
      wydawnictwo_ciagle.delete()

      mock_client = MagicMock()
      with patch.object(
          PBN_Export_Queue, "_pozyskaj_klienta_pbn", return_value=mock_client
      ):
          result = wpis.send_to_pbn()

      assert result == SendStatus.FINISHED_OKAY
      mock_client.delete_all_publication_statements.assert_called_once_with(
          "PBN-UID-123"
      )
      wpis.refresh_from_db()
      assert wpis.zakonczono_pomyslnie is True
      sd = SentData.objects.get_for_rec(wydawnictwo_ciagle)
      assert sd.submitted_successfully is False
      assert sd.withdrawn_at is not None
  ```
  (Uwaga: `Publication.pk` jest stringiem — `pbn_uid_id` to ten string. Jeśli baker nie pozwoli ustawić `pk`, użyj `baker.make(Publication, mongoId="PBN-UID-123")` i odczytaj `wydawnictwo_ciagle.pbn_uid_id` w asercji zamiast literału — dostosuj po sprawdzeniu modelu `Publication`.)
- [ ] **Komenda + FAIL:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wycofanie_wola_delete_all_statements -x` → FAIL (`send_to_pbn` idzie ścieżką wysyłki / brak `_pozyskaj_klienta_pbn`).
- [ ] **Implementacja — helper klienta.** W `PBN_Export_Queue` dodaj metodę pozyskania klienta (wzorzec z `pbn_wysylka_oswiadczen/tasks.py::get_pbn_client` — uczelnia JAWNA, nigdy „domyślna"):
  ```python
      def _pozyskaj_klienta_pbn(self):
          """Buduje klienta PBN dla TEGO wpisu kolejki.

          Uczelnia z FK wpisu (``self.uczelnia``) — NIE „domyślna": taki
          byt nie istnieje (dawne API „uczelni domyślnej" zostało trwale
          usunięte i jest pilnowane guardem
          ``test_multihosted_get_default_guard.py``). Dla wpisów legacy
          (``uczelnia_id is None``) jedyny dozwolony fallback to
          „jedyna-albo-głośny-błąd".

          Token: z konta PBN zamawiającego (``get_pbn_user()`` respektuje
          ``przedstawiaj_w_pbn_jako``) — jak w wysyłce.
          """
          from bpp.models import Uczelnia

          pbn_user = self.zamowil.get_pbn_user()
          uczelnia = self.uczelnia or Uczelnia.objects.get_single_uczelnia_or_fail()
          return uczelnia.pbn_client(pbn_user.pbn_token)
  ```
  ⚠️ **Nie** wołaj tu `Uczelnia.objects.get_default()` ani
  `Uczelnia.objects.first()` — oba są zakazane guard-testem multi-hosted
  (`src/bpp/tests/test_multihosted_get_default_guard.py`). ⚠️ Guard skanuje
  pliki `.py` **regexem, razem z komentarzami i docstringami** — nie
  przepisuj tych dwóch nazw nawet do dokumentacji w kodzie (dlatego
  docstring wyżej mówi opisowo „dawne API uczelni domyślnej").
- [ ] **Implementacja — `withdraw_from_pbn` jako CIENKI wrapper.** Cała
  logika (retry-semantyka, idempotencja, `SentData`) siedzi w prymitywie
  z 05.0; tutaj wyłącznie klient → prymityw → `SendStatus`:
  ```python
      def withdraw_from_pbn(self):
          """Gałąź WYCOFANIE — cienkie wywołanie prymitywu (decyzja #16).

          NIE woła klienta PBN bezpośrednio i NIE dotyka SentData — robi to
          wycofaj_oswiadczenia(), wspólne z wejściem synchronicznym (05.9).
          Tu tylko: pozyskanie klienta, wywołanie prymitywu i tłumaczenie
          wyniku/wyjątku na SendStatus. Klasyfikacja wyjątków PBN idzie
          przez wspólne _handle_pbn_exception (ResourceLocked → RETRY_LATER,
          PraceSerwisowe → RETRY_MUCH_LATER, HTTP 423 → RETRY_LATER, …).

          :return: SendStatus
          """
          from pbn_api.wycofanie import wycofaj_oswiadczenia

          try:
              client = self._pozyskaj_klienta_pbn()
          except Exception as exc:
              return self._handle_pbn_exception(exc)

          try:
              wynik = wycofaj_oswiadczenia(
                  self.rekord_do_wysylki, client, uczelnia=self.uczelnia
              )
          except Exception as exc:
              zaloguj_polkniety_wyjatek(
                  "Błąd podczas wycofywania oświadczeń z PBN z kolejki "
                  f"eksportu (PBN_Export_Queue pk={self.pk})",
                  logger=logger,
                  do_rollbar=False,  # Rollbar w _handle_pbn_exception
              )
              return self._handle_pbn_exception(exc)

          self.wysylke_zakonczono = timezone.now()
          self.zakonczono_pomyslnie = True
          self.dopisz_komunikat(wynik.komunikat)
          self.save()
          return SendStatus.FINISHED_OKAY
  ```
  (`POMINIETO` też kończy wpis sukcesem — prymityw zwraca wtedy komunikat
  „rekord nie ma PBN UID". To gate obronny: `zakolejkuj_wycofanie` takich
  wpisów nie tworzy.)
- [ ] ⚠️ **Implementacja — guard świadomy operacji (BLOKER #1, rewizja
  2026-08-10). ZRÓB TO PRZED ROZGAŁĘZIENIEM** — bez tego gałąź niżej jest
  martwym kodem. W `check_if_record_still_exists()` (`models.py:190`) zawęź
  warunek odrzucający rekordy z kosza:
  ```python
          # Dla WYCOFANIA soft-delete to stan OCZEKIWANY, nie powód
          # przerwania: wycofujemy oświadczenia z PBN właśnie dlatego, że
          # operator usunął rekord. Wiersz w bazie nadal jest (kasowanie
          # miękkie to UPDATE deleted_at), więc pbn_uid da się odczytać —
          # GenericForeignKey idzie przez _base_manager, który NIE filtruje.
          #
          # Dla WYSYŁKI przesłanka jest ta sama, a wniosek przeciwny:
          # rekordu w koszu nie pchamy do PBN. Stąd warunek na operacji.
          if (
              self.operacja != self.Operacja.WYCOFANIE
              and getattr(obiekt, "deleted_at", None) is not None
          ):
              return False
  ```
  Twardo skasowany rekord (`ObjectDoesNotExist`) nadal daje `False` dla obu
  operacji — bez wiersza nie ma `pbn_uid`, więc nie ma czego wycofać.
- [ ] **Implementacja — rozgałęzienie w `send_to_pbn`.** ⚠️ **Niczego nie
  przenosimy.** Wstaw DOKŁADNIE dwie linie między `_zajmij_atomowo()`
  (`models.py:479-482`) a importem `sprobuj_wyslac_do_pbn_celery`
  (`models.py:484`):
  ```python
          if not self._zajmij_atomowo():
              # Inny worker zdążył zająć ten wiersz (row lock) albo go zakończył.
              # On dokończy — bieżące zadanie kończymy bez ponawiania.
              return SendStatus.LOCKED_ELSEWHERE

          if self.operacja == self.Operacja.WYCOFANIE:
              return self.withdraw_from_pbn()

          from bpp.admin.helpers.pbn_api.cli import sprobuj_wyslac_do_pbn_celery
  ```
  Dzięki umieszczeniu PO `_zajmij_atomowo()` wycofanie dziedziczy za darmo:
  guard „rekord zniknął", licznik `ilosc_prob`, `wysylke_podjeto` i ochronę
  przed dwoma workerami. Reszta `send_to_pbn` — ścieżka WYSYLKA — bez zmian.
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wycofanie_wola_delete_all_statements -x` → PASS.
- [ ] **Guard multi-hosted (obowiązkowy po tym tasku):**
  `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -x` →
  PASS (pilnuje, że `_pozyskaj_klienta_pbn` nie wprowadził
  `get_default()`/`first()`).
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/models.py && uv run ruff format src/pbn_export_queue/models.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit** (jawne ścieżki): `git commit -m "feat(pbn_export_queue): withdraw_from_pbn + gałąź WYCOFANIE w send_to_pbn"`

---

### Task 05.3a — Sprzątaczka nie kasuje zleceń wycofania (BLOKER #2)

> **Dodane 2026-08-10.** Tego tasku nie było w planie, bo plan nie wiedział
> o drugim konsumencie `check_if_record_still_exists()`.

`kolejka_wyczysc_wpisy_bez_rekordow()` (`tasks.py:105`) iteruje po CAŁEJ
kolejce i kasuje wpisy, dla których guard zwraca `False`. Przed poprawką
z Taska 05.3 każdy wpis `WYCOFANIE` (rekord z definicji w koszu) padał jej
ofiarą: zlecenie znikało, oświadczenia zostawały w PBN, śladu brak.

Poprawka guardu z 05.3 rozbraja to **automatycznie** — sprzątaczka woła tę
samą metodę na instancji wpisu. Ten task **nie dokłada implementacji**;
dokłada test, który to przypina, żeby przyszła zmiana guardu nie wskrzesiła
cichej utraty zleceń.

**Files:**
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Test regresyjny — wpis WYCOFANIE przeżywa sprzątaczkę, wpis WYSYLKA
  nie.** Jeden test, dwie asercje — bo dowodem jest RÓŻNICA między
  operacjami, nie samo przetrwanie:
  ```python
  @pytest.mark.django_db
  def test_sprzataczka_nie_kasuje_zlecen_wycofania(
      wydawnictwo_ciagle, wydawnictwo_zwarte, admin_user, uczelnia
  ):
      """Regresja blokera #2 (rewizja planu 2026-08-10).

      kolejka_wyczysc_wpisy_bez_rekordow() kasuje wpisy, których rekord
      „już nie istnieje". Zanim guard poznał operację, soft-delete
      publikacji sprawiał, że sprzątaczka kasowała WŁAŚNIE UTWORZONE
      zlecenie wycofania — oświadczenia zostawały w PBN, a wyścig
      z workerem celery rozstrzygał się losowo.
      """
      from pbn_export_queue.tasks import kolejka_wyczysc_wpisy_bez_rekordow

      wycofanie = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
          uczelnia=uczelnia,
          operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
          wysylke_zakonczono=None,
      )
      wysylka = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_zwarte,
          zamowil=admin_user,
          uczelnia=uczelnia,
          operacja=PBN_Export_Queue.Operacja.WYSYLKA,
          wysylke_zakonczono=None,
      )

      wydawnictwo_ciagle.delete()
      wydawnictwo_zwarte.delete()

      kolejka_wyczysc_wpisy_bez_rekordow()

      assert PBN_Export_Queue.objects.filter(pk=wycofanie.pk).exists(), (
          "sprzątaczka skasowała zlecenie WYCOFANIA — oświadczenia "
          "zostaną w PBN i nikt się o tym nie dowie"
      )
      assert not PBN_Export_Queue.objects.filter(pk=wysylka.pk).exists(), (
          "wpis WYSYLKA rekordu z kosza ma nadal znikać — to zachowanie "
          "z fazy 02, którego nie wolno zepsuć przy okazji"
      )
  ```
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_sprzataczka_nie_kasuje_zlecen_wycofania -x` → PASS (poprawka guardu z 05.3 już to załatwia).
- [ ] **Dowód, że test faktycznie pilnuje (mutacja obowiązkowa):** tymczasowo
  cofnij warunek `self.operacja != self.Operacja.WYCOFANIE` w
  `check_if_record_still_exists()` → test MUSI paść na pierwszej asercji.
  Przywróć. Test, który przechodzi także bez poprawki, nie jest regresją.
- [ ] **Lint + Commit** (jawne ścieżki): `git commit -m "test(pbn_export_queue): sprzataczka kolejki nie kasuje zlecen wycofania"`

---

### Task 05.4 — WYSYLKA dalej działa (regresja rozgałęzienia)

Upewnij się, że dodanie gałęzi WYCOFANIE nie zmieniło ścieżki WYSYLKA: wpis z domyślną operacją nadal woła `sprobuj_wyslac_do_pbn_celery`, NIE `delete_all_publication_statements`.

**Files:**
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — WYSYLKA nie woła delete_all_statements.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_wysylka_nie_wola_delete_all_statements(
      wydawnictwo_ciagle, admin_user, uczelnia
  ):
      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
          uczelnia=uczelnia,
          operacja=PBN_Export_Queue.Operacja.WYSYLKA,
          wysylke_zakonczono=None,
      )

      sent_data = MagicMock()
      with patch.object(
          PBN_Export_Queue, "_pozyskaj_klienta_pbn"
      ) as mock_klient, patch(
          "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery",
          return_value=(sent_data, ["ok"]),
      ) as mock_send:
          result = wpis.send_to_pbn()

      assert result == SendStatus.FINISHED_OKAY
      mock_send.assert_called_once()
      # ścieżka WYSYLKA przekazuje uczelnię wpisu (multi-hosted)
      assert mock_send.call_args.kwargs["uczelnia"] == uczelnia
      mock_klient.assert_not_called()
  ```
  Uwagi do patchowania (zweryfikowane w kodzie):
  - `sprobuj_wyslac_do_pbn_celery` jest importowane **wewnątrz**
    `send_to_pbn()` (`models.py:474`), więc patchujemy je w module
    źródłowym `bpp.admin.helpers.pbn_api.cli` — NIE w `pbn_export_queue.models`.
  - **Nie** patchuj `admin_user.get_pbn_user` przez `patch.object(admin_user, …)`:
    `send_to_pbn()` robi `refresh_from_db()` i sięga po `self.zamowil`, czyli
    po INNĄ instancję użytkownika. Bez patcha `get_pbn_user()` po prostu
    zwraca `self` (`profile.py:207`) i nic nie woła po sieci.
  - `_zajmij_atomowo()` używa `select_for_update` — test musi być
    `@pytest.mark.django_db` (transakcja pytest-django wystarcza).
- [ ] **Komenda:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wysylka_nie_wola_delete_all_statements -x`. Jeśli przechodzi od razu — to dowód regresyjny, że ścieżka WYSYLKA jest nietknięta; zostaw test jako guard (nie wymaga zmian implementacji). Jeśli FAIL — popraw rozgałęzienie w 05.3, by WYSYLKA nie wpadała w gałąź wycofania.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit** (jawne ścieżki): `git commit -m "test(pbn_export_queue): guard regresyjny — WYSYLKA nie woła delete_all_statements"`

---

### Task 05.4a — Konto techniczne dla `zamowil` + rozróżnienie `IntegrityError`

> **Dodane 2026-08-07. To NIE jest kosmetyka — to cichy błąd czekający na
> uruchomienie fazy.** Spec §4.2 przypisywał konto techniczne do „fazy
> 05/06", plan 05 pisał „rozwiązuje faza 06/07", plan 06 pisał „to dług fazy
> 05" — czyli **nikt tego nie robił**. Przypinamy jawnie do **fazy 05**,
> bo to ta faza dostarcza `zakolejkuj_*`.

**Na czym polega cichy błąd (zweryfikowany w kodzie):**
`PBN_Export_Queue.zamowil` jest NOT NULL (`models.py:101`), a
`sprobuj_utowrzyc_wpis` łapie **każdy** `IntegrityError` i przemianowuje go
na `AlreadyEnqueuedError` (`models.py:53-63`). Systemowy soft-delete
publikacji z `pbn_uid` (sygnał, celery, merge — bez `request.user`) trafi
więc w naruszenie NOT NULL na `zamowil`, dostanie „już w kolejce",
`zakolejkuj_wycofanie` zwróci `None`, `SoftDeleteLog.pbn_status` zostanie
pusty — a **oświadczenia w PBN nigdy nie zostaną wycofane**. Operator
zobaczy komunikat sugerujący, że wszystko jest w porządku.

**Files:**
- `src/pbn_export_queue/operacje.py` (NOWY — wspólny z Taskiem 05.5:
  `pobierz_konto_techniczne()`)
- `src/pbn_export_queue/models.py` (`sprobuj_utowrzyc_wpis`: rozróżnienie
  wyjątku)
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — prawdziwy `IntegrityError` NIE udaje „już w kolejce".**
  ```python
  @pytest.mark.django_db
  def test_integrity_error_zamowil_nie_udaje_already_enqueued(
      wydawnictwo_ciagle,
  ):
      from django.db import IntegrityError

      # zamowil = NULL łamie NOT NULL, a NIE unikat aktywnego wpisu —
      # to MUSI polecieć w górę jako IntegrityError, inaczej systemowe
      # wycofanie z PBN cicho zniknie pod komunikatem "już w kolejce".
      with pytest.raises(IntegrityError):
          PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
              None, wydawnictwo_ciagle
          )
  ```
- [ ] **Komenda + FAIL:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_integrity_error_zamowil_nie_udaje_already_enqueued -x`
  → FAIL: podnosi się `AlreadyEnqueuedError` zamiast `IntegrityError`.
- [ ] **Implementacja — rozróżnienie w `sprobuj_utowrzyc_wpis`.** W
  `src/pbn_export_queue/models.py`, przy managerze:
  ```python
  #: Nazwa częściowego unikatu z Meta.constraints — jedyny IntegrityError,
  #: który wolno przetłumaczyć na domenowe „już w kolejce".
  NAZWA_UNIKATU_AKTYWNEGO_WPISU = "pbn_export_queue_jeden_aktywny_wpis_na_rekord"


  def _to_kolizja_aktywnego_wpisu(exc):
      """Czy ten IntegrityError NAPRAWDĘ znaczy „już w kolejce"?

      psycopg wystawia nazwę naruszonego ograniczenia w
      ``exc.__cause__.diag.constraint_name``; gdy jej nie ma (inny
      sterownik/backend) — fallback na tekst wyjątku. Tłumaczenie „w
      ciemno" połykało naruszenie NOT NULL na ``zamowil`` (operacja
      systemowa bez usera) i zamieniało brak wycofania oświadczeń w PBN
      w niewinny komunikat „już w kolejce".
      """
      diag = getattr(getattr(exc, "__cause__", None), "diag", None)
      nazwa = getattr(diag, "constraint_name", None)
      if nazwa:
          return nazwa == NAZWA_UNIKATU_AKTYWNEGO_WPISU
      return NAZWA_UNIKATU_AKTYWNEGO_WPISU in str(exc)
  ```
  a w samym `except IntegrityError as e:` (`models.py:60-63`):
  ```python
          except IntegrityError as e:
              if not _to_kolizja_aktywnego_wpisu(e):
                  raise
              raise AlreadyEnqueuedError(
                  "ten rekord jest już w kolejce do wysyłki"
              ) from e
  ```
- [ ] **Regresja istniejącego zachowania:**
  `uv run pytest src/pbn_export_queue/tests/test_pbn_queue_atomicity.py src/pbn_export_queue/tests/test_pbn_queue_manager.py -x`
  → PASS. Wyścig na aktywnym wpisie MUSI nadal dawać `AlreadyEnqueuedError`
  (`test_sprobuj_utowrzyc_wpis_wyscig_daje_alreadyenqueued`).
- [ ] **Failing test — konto techniczne dla operacji bez usera.**
  ```python
  @pytest.mark.django_db
  def test_zakolejkuj_wycofanie_bez_usera_uzywa_konta_technicznego(
      wydawnictwo_ciagle, uczelnia
  ):
      from pbn_api.models import Publication
      from pbn_export_queue.operacje import (
          NAZWA_KONTA_TECHNICZNEGO,
          zakolejkuj_wycofanie,
      )

      wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
      wydawnictwo_ciagle.save()

      with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"):
          wpis = zakolejkuj_wycofanie(
              wydawnictwo_ciagle, user=None, uczelnia=uczelnia
          )

      assert wpis is not None, (
          "systemowy soft-delete MUSI utworzyć wpis wycofania — "
          "zwrot None znaczy, że oświadczenia zostaną w PBN"
      )
      assert wpis.zamowil.username == NAZWA_KONTA_TECHNICZNEGO
      assert wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE
  ```
- [ ] **Implementacja — `pobierz_konto_techniczne()`** w
  `src/pbn_export_queue/operacje.py`:
  ```python
  #: Login konta używanego jako ``zamowil`` przy operacjach systemowych.
  NAZWA_KONTA_TECHNICZNEGO = "bpp-system"


  def pobierz_konto_techniczne():
      """Konto ``zamowil`` dla operacji bez zalogowanego użytkownika.

      ``PBN_Export_Queue.zamowil`` jest NOT NULL, a soft-delete zlecony
      sygnałem/celery nie ma requestu. Świadomie NIE robimy ``zamowil``
      nullable (spec §4.2) — psułoby to założenia kolejki i raportów.

      Konto jest nieaktywne i bez hasła: ma istnieć jako podmiot audytu,
      nie jako sposób logowania.
      """
      from django.contrib.auth import get_user_model

      user, utworzono = get_user_model().objects.get_or_create(
          username=NAZWA_KONTA_TECHNICZNEGO,
          defaults={
              "first_name": "Konto",
              "last_name": "systemowe BPP",
              "is_active": False,
              "is_staff": False,
              "is_superuser": False,
          },
      )
      if utworzono:
          user.set_unusable_password()
          user.save(update_fields=["password"])
      return user
  ```
- [ ] ⚠️ **Krok obowiązkowy — token PBN konta technicznego.** Konto
  techniczne nie ma `pbn_token` (`BppUser.pbn_token` default `""`), więc
  `_pozyskaj_klienta_pbn()` → `uczelnia.pbn_client("")` →
  `UczelniaTransport.authorize` rzuci `WillNotExportError`
  (`src/bpp/models/uczelnia.py:936+`). **To jest akceptowalne tylko dlatego,
  że kończy się GŁOŚNO** (`_handle_pbn_exception` → `error(...,
  MERYTORYCZNY)`), a nie cicho. Wymagane:
  - dopisz test: wpis WYCOFANIE zamówiony przez konto techniczne **bez**
    tokenu kończy się `SendStatus.FINISHED_ERROR` z komunikatem wskazującym
    konfigurację (NIE `FINISHED_OKAY`, NIE cichym `None`);
  - udokumentuj obejście produkcyjne: administrator ustawia kontu
    technicznemu `przedstawiaj_w_pbn_jako` na konto z ważnym tokenem PBN
    (`get_pbn_user()` — `profile.py:207` — sam podmieni użytkownika, żaden
    kod się nie zmienia).
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py -k "konta_technicznego or integrity_error" -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/models.py src/pbn_export_queue/operacje.py src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/models.py src/pbn_export_queue/operacje.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit** (jawne ścieżki): `git commit -m "fix(pbn_export_queue): konto techniczne dla zamowil + IntegrityError nie udaje AlreadyEnqueued"`
- [ ] **Newsfragment:** `src/bpp/newsfragments/soft-delete-konto-techniczne.bugfix.rst`
  — „Systemowe (bez zalogowanego użytkownika) usunięcie publikacji nie
  powodowało już cichego pominięcia wycofania oświadczeń z PBN."

---

### Task 05.5 — Funkcje zakolejkowujące + gate na `pbn_uid`

> ⚠️ **Kontrakt PRZYPIĘTY 2026-08-07 — jedno miejsce, jedna sygnatura.**
> Poprzednia wersja tego tasku dostarczała **metody managera**
> (`PBN_Export_Queue.objects.zakolejkuj_wycofanie(...)`), podczas gdy faza 06
> sprawdza istnienie **funkcji modułowych** (`uv run python -c "from
> pbn_export_queue.operacje import zakolejkuj_wycofanie, zakolejkuj_wysylke"`,
> plan 06 Task 5) i tak je woła w receiverach. Check fazy 06 nigdy by nie
> przeszedł → powstałby shim → dwie rozbieżne implementacje.
> **Wybór: funkcje modułowe w `src/pbn_export_queue/operacje.py`** (wersja
> fazy 06 — plan 06 NIE wymaga zmian). Manager dostaje tylko rozszerzenie
> `sprobuj_utowrzyc_wpis(..., operacja=...)`; metod `zakolejkuj_*` na
> managerze **nie dodajemy** (jedno miejsce prawdy).
>
> Konsekwencja dla fazy 06: jej **Task 5 (shim) należy POMINĄĆ** — ten task
> go zastępuje. Shim z planu 06 tworzy wpisy przez gołe
> `PBN_Export_Queue.objects.create(...)`, więc omija `sprobuj_utowrzyc_wpis`
> (TOCTOU, `uczelnia`, `operacja`) — gdyby powstał wcześniej, MUSI zniknąć
> przy scalaniu, nie zostać obok.

`zakolejkuj_wycofanie(instance, user=None, uczelnia=None)` i
`zakolejkuj_wysylke(instance, user=None, uczelnia=None)` — publiczne funkcje
modułowe, wołane potem z fazy 06 (receivery sygnałów). Tworzą wpis przez
`sprobuj_utowrzyc_wpis` (z odpowiednią `operacja`) i delegują do
`task_sprobuj_wyslac_do_pbn.delay(pk)`. Gate: wycofanie tylko gdy
`instance.pbn_uid_id` ustawione (brak PBN UID → no-op, brak wpisu).
Idempotencja: jeśli rekord już w kolejce (`AlreadyEnqueuedError`) → `None`.
`user=None` → konto techniczne (Task 05.4a), **nigdy** `zamowil=None`.
Trzeci kwarg `uczelnia` jest opcjonalny i domyślnie `None`, więc wywołania
z fazy 06 (`zakolejkuj_wycofanie(instance, user)`) pozostają poprawne.

**Files:**
- `src/pbn_export_queue/operacje.py` (funkcje `zakolejkuj_wycofanie`,
  `zakolejkuj_wysylke` — ten sam plik co `pobierz_konto_techniczne`
  z Taska 05.4a)
- `src/pbn_export_queue/models.py` (rozszerz `sprobuj_utowrzyc_wpis`
  o argument `operacja` — **bez** przepisywania metody)
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — gate + utworzenie wpisu WYCOFANIE.** Dopisz
  (patch celuje w `pbn_export_queue.tasks…`, bo tam realnie żyje symbol;
  `operacje.py` importuje go lokalnie w funkcji, żeby nie robić cyklu —
  `tasks.py` importuje `models`):
  ```python
  @pytest.mark.django_db
  def test_zakolejkuj_wycofanie_gate_brak_pbn_uid(wydawnictwo_ciagle, admin_user):
      from pbn_export_queue.operacje import zakolejkuj_wycofanie

      assert wydawnictwo_ciagle.pbn_uid_id is None
      with patch(
          "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"
      ) as mock_task:
          wpis = zakolejkuj_wycofanie(wydawnictwo_ciagle, user=admin_user)
      assert wpis is None
      assert PBN_Export_Queue.objects.filter_rekord_do_wysylki(
          wydawnictwo_ciagle
      ).count() == 0
      mock_task.delay.assert_not_called()


  @pytest.mark.django_db
  def test_zakolejkuj_wycofanie_tworzy_wpis(
      wydawnictwo_ciagle, admin_user, uczelnia
  ):
      from pbn_api.models import Publication
      from pbn_export_queue.operacje import zakolejkuj_wycofanie

      pub = baker.make(Publication)
      wydawnictwo_ciagle.pbn_uid = pub
      wydawnictwo_ciagle.save()

      with patch(
          "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"
      ) as mock_task:
          wpis = zakolejkuj_wycofanie(
              wydawnictwo_ciagle, user=admin_user, uczelnia=uczelnia
          )

      assert wpis is not None
      assert wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE
      assert wpis.uczelnia == uczelnia
      mock_task.delay.assert_called_once_with(wpis.pk)


  @pytest.mark.django_db
  def test_zakolejkuj_wysylke_tworzy_wpis(wydawnictwo_ciagle, admin_user):
      from pbn_export_queue.operacje import zakolejkuj_wysylke

      with patch(
          "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"
      ) as mock_task:
          wpis = zakolejkuj_wysylke(wydawnictwo_ciagle, user=admin_user)
      assert wpis is not None
      assert wpis.operacja == PBN_Export_Queue.Operacja.WYSYLKA
      mock_task.delay.assert_called_once_with(wpis.pk)


  @pytest.mark.django_db
  def test_zakolejkuj_idempotentne(wydawnictwo_ciagle, admin_user):
      from pbn_api.models import Publication
      from pbn_export_queue.operacje import zakolejkuj_wycofanie

      wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
      wydawnictwo_ciagle.save()
      with patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"):
          first = zakolejkuj_wycofanie(wydawnictwo_ciagle, user=admin_user)
          second = zakolejkuj_wycofanie(wydawnictwo_ciagle, user=admin_user)
      assert first is not None
      assert second is None
      assert PBN_Export_Queue.objects.filter_rekord_do_wysylki(
          wydawnictwo_ciagle
      ).count() == 1
  ```
  ⚠️ **Gate `pbn_uid` w `zakolejkuj_wysylke`:** faza 06 pisze w kontrakcie
  PINNED „None gdy brak pbn_uid" **dla obu** funkcji, ale restore rekordu,
  który nigdy nie poszedł do PBN, i tak powinien go wysłać (wysyłka sama
  nadaje `pbn_uid`). **Rozstrzygnięcie: `zakolejkuj_wysylke` NIE ma gate'u
  na `pbn_uid`** — gate ma tylko wycofanie. Docstring w kodzie musi to
  mówić wprost, żeby nikt nie „naprawił" tego pod docstring z planu 06.
- [ ] **Komenda + FAIL:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py -k zakolejkuj -x` → `ModuleNotFoundError`/`ImportError` (`pbn_export_queue.operacje`).
- [ ] **Implementacja — rozszerz `sprobuj_utowrzyc_wpis` o `operacja`.**
  ⚠️ **Minimalna zmiana istniejącej metody (`models.py:42-63`) — NIE
  przepisywać jej.** Zachować MUSZĄ: parametr `uczelnia`, savepoint
  `transaction.atomic()` i tłumaczenie kolizji unikatu (z rozróżnieniem
  z Taska 05.4a). Dopisujemy wyłącznie `operacja`:
  ```python
      def sprobuj_utowrzyc_wpis(self, user, rekord, uczelnia=None, operacja=None):
          # Szybka ścieżka (przyjazny błąd bez trafiania w constraint bazy).
          if self.filter_rekord_do_wysylki(rekord).exists():
              raise AlreadyEnqueuedError("ten rekord jest już w kolejce do wysyłki")

          kwargs = {
              "rekord_do_wysylki": rekord,
              "zamowil": user,
              "uczelnia": uczelnia,
          }
          if operacja is not None:
              kwargs["operacja"] = operacja

          # (komentarz o TOCTOU — zostawić bez zmian)
          try:
              with transaction.atomic():
                  return self.create(**kwargs)
          except IntegrityError as e:
              if not _to_kolizja_aktywnego_wpisu(e):  # Task 05.4a
                  raise
              raise AlreadyEnqueuedError(
                  "ten rekord jest już w kolejce do wysyłki"
              ) from e
  ```
  (`operacja` opcjonalna → wszystkie dotychczasowe wywołania —
  `bpp/admin/helpers/pbn_api/gui.py:92`, `pbn_export_queue/tasks.py:165`,
  `przemapuj_zrodlo/views.py:159`, `przemapuj_zrodla_pbn/views.py:509` —
  działają bez zmian i dostają default modelu `WYSYLKA`.)
- [ ] **Implementacja — `zakolejkuj_wycofanie` / `zakolejkuj_wysylke`**
  w `src/pbn_export_queue/operacje.py` (funkcje MODUŁOWE — kontrakt fazy 06):
  ```python
  def _zakolejkuj(instance, operacja, user=None, uczelnia=None):
      from pbn_api.exceptions import AlreadyEnqueuedError

      from pbn_export_queue import tasks
      from pbn_export_queue.models import PBN_Export_Queue

      try:
          wpis = PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
              user or pobierz_konto_techniczne(),
              instance,
              uczelnia=uczelnia,
              operacja=operacja,
          )
      except AlreadyEnqueuedError:
          # Rekord czeka już w kolejce — idempotencja, nie błąd.
          return None
      tasks.task_sprobuj_wyslac_do_pbn.delay(wpis.pk)
      return wpis


  def zakolejkuj_wysylke(instance, user=None, uczelnia=None):
      """Tworzy wpis WYSYLKA i uruchamia wysyłkę w tle.

      Wołane m.in. przy restore publikacji (faza 06). BEZ gate'u na
      pbn_uid — rekord bez PBN UID też ma prawo pojechać do PBN (wysyłka
      dopiero go nada). Idempotentne: gdy rekord już w kolejce → None.
      user=None → konto techniczne (zamowil jest NOT NULL).
      """
      return _zakolejkuj(
          instance,
          PBN_Export_Queue.Operacja.WYSYLKA,
          user=user,
          uczelnia=uczelnia,
      )


  def zakolejkuj_wycofanie(instance, user=None, uczelnia=None):
      """Tworzy wpis WYCOFANIE i uruchamia wycofanie w tle.

      Gate: tylko gdy rekord ma PBN UID (inaczej nic nie poszło do PBN —
      no-op, zwraca None). Idempotentne: gdy rekord już w kolejce → None.
      user=None → konto techniczne (zamowil jest NOT NULL); NIGDY nie
      przekazujemy None do zamowil, bo IntegrityError udawałby wtedy
      „już w kolejce" i wycofanie zniknęłoby po cichu.
      """
      if not getattr(instance, "pbn_uid_id", None):
          return None
      return _zakolejkuj(
          instance,
          PBN_Export_Queue.Operacja.WYCOFANIE,
          user=user,
          uczelnia=uczelnia,
      )
  ```
  (Import `PBN_Export_Queue` na poziomie modułu jest OK — `operacje.py`
  nie jest importowane przez `models.py`; cykl groziłby tylko przy
  `tasks`, dlatego `tasks` importujemy w środku funkcji.)
- [ ] **Check zgodności z fazą 06:**
  `uv run python -c "from pbn_export_queue.operacje import zakolejkuj_wycofanie, zakolejkuj_wysylke"`
  → bez błędu (to dokładnie ten check, który wykonuje Task 5 planu 06,
  żeby pominąć swój shim).
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py -k zakolejkuj -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/models.py src/pbn_export_queue/operacje.py src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/models.py src/pbn_export_queue/operacje.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit** (jawne ścieżki): `git commit -m "feat(pbn_export_queue): zakolejkuj_wycofanie/zakolejkuj_wysylke + gate pbn_uid"`

---

### Task 05.6 — Idempotencja/retry wycofania (ResourceLocked + CannotDelete)

> Oba testy sprawdzają zachowanie, które po przepisaniu 05.3 pochodzi z
> **dwóch różnych warstw**: `CannotDeleteStatementsException` obsługuje
> prymityw (05.0, sukces `BRAK_OSWIADCZEN`), a `ResourceLockedException`
> klasyfikuje wspólne `_handle_pbn_exception` (`models.py:299`). Gdy któryś
> padnie — popraw TĘ warstwę, nie dokładaj drugiej drabinki `except`
> w `withdraw_from_pbn`.

**Files:**
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — `CannotDeleteStatementsException` traktowany jak sukces.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_wycofanie_brak_oswiadczen_to_sukces(
      wydawnictwo_ciagle, admin_user, uczelnia
  ):
      from pbn_api.exceptions import CannotDeleteStatementsException
      from pbn_api.models import Publication
      from pbn_api.models.sentdata import SentData

      wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
      wydawnictwo_ciagle.save()
      SentData.objects.create(
          object=wydawnictwo_ciagle,
          data_sent={},
          submitted_successfully=True,
          uploaded_okay=True,
          uczelnia=uczelnia,
      )
      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
          uczelnia=uczelnia,
          operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
          wysylke_zakonczono=None,
      )

      mock_client = MagicMock()
      mock_client.delete_all_publication_statements.side_effect = (
          CannotDeleteStatementsException("brak oświadczeń")
      )
      with patch.object(
          PBN_Export_Queue, "_pozyskaj_klienta_pbn", return_value=mock_client
      ):
          result = wpis.send_to_pbn()

      assert result == SendStatus.FINISHED_OKAY
      wpis.refresh_from_db()
      assert wpis.zakonczono_pomyslnie is True
      assert SentData.objects.get_for_rec(
          wydawnictwo_ciagle, uczelnia
      ).withdrawn_at is not None
  ```
- [ ] **Komenda:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wycofanie_brak_oswiadczen_to_sukces -x` → powinien przejść (prymityw z 05.0 zwraca `BRAK_OSWIADCZEN` = sukces). Jeśli FAIL — popraw **prymityw**, nie `withdraw_from_pbn`.

- [ ] **Failing test — `ResourceLockedException` → RETRY_LATER, bez oznaczenia SentData.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_wycofanie_locked_retry_later(
      wydawnictwo_ciagle, admin_user, uczelnia
  ):
      from pbn_api.exceptions import ResourceLockedException
      from pbn_api.models import Publication
      from pbn_api.models.sentdata import SentData

      wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
      wydawnictwo_ciagle.save()
      SentData.objects.create(
          object=wydawnictwo_ciagle,
          data_sent={},
          submitted_successfully=True,
          uploaded_okay=True,
          uczelnia=uczelnia,
      )
      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
          uczelnia=uczelnia,
          operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
          wysylke_zakonczono=None,
      )

      mock_client = MagicMock()
      mock_client.delete_all_publication_statements.side_effect = (
          ResourceLockedException("zablokowane")
      )
      with patch.object(
          PBN_Export_Queue, "_pozyskaj_klienta_pbn", return_value=mock_client
      ):
          result = wpis.send_to_pbn()

      assert result == SendStatus.RETRY_LATER
      wpis.refresh_from_db()
      # wycofanie nie zakończone — zostanie ponowione
      assert wpis.wysylke_zakonczono is None
      assert SentData.objects.get_for_rec(
          wydawnictwo_ciagle, uczelnia
      ).withdrawn_at is None
  ```
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wycofanie_locked_retry_later -x` → PASS (prymityw propaguje `ResourceLockedException`, a `_handle_pbn_exception` → `_handle_retry_exception` (`models.py:299`) zwraca `RETRY_LATER` bez ustawiania `wysylke_zakonczono`). Jeśli FAIL — sprawdź, czy prymityw nie połyka wyjątku.
- [ ] **Test dopełniający — `PraceSerwisoweException` → `RETRY_MUCH_LATER`.**
  Ta sama konstrukcja; dowodzi, że wycofanie dziedziczy CAŁĄ tabelę
  klasyfikacji z wysyłki, a nie tylko dwa przypadki.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit** (jawne ścieżki): `git commit -m "test(pbn_export_queue): wycofanie — idempotencja CannotDelete + retry ResourceLocked"`

---

### Task 05.7 — Admin: kolumna `operacja` widoczna w kolejce

Drobne wsparcie operacyjne: pokaż operację na liście kolejki, by superuser odróżnił wpisy wycofania od wysyłki.

**Files:**
- `src/pbn_export_queue/admin.py` (`list_display`, `list_filter`, `readonly_fields`)
- Test path: `src/pbn_export_queue/tests/test_admin.py` (dopisać 1 asercję) lub `test_operacja_wycofanie.py`

- [ ] **Failing test — `operacja` w `list_display`.** Dopisz do `test_operacja_wycofanie.py`:
  ```python
  def test_admin_pokazuje_operacje():
      from pbn_export_queue.admin import PBN_Export_QueueAdmin

      assert "operacja" in PBN_Export_QueueAdmin.list_display
      assert "operacja" in PBN_Export_QueueAdmin.list_filter
  ```
- [ ] **Komenda + FAIL:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_admin_pokazuje_operacje -x` → AssertionError.
- [ ] **Implementacja — admin.** W `src/pbn_export_queue/admin.py`: dodaj `"operacja"` do `list_display` (`:55`, np. zaraz po `"rekord_do_wysylki"`), do `list_filter` (`:68` — tam pierwszy element to `ZamowilUniqueFilter`, więc `"operacja"` dopisz PO nim) i do `readonly_fields` (`:76`).
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_admin_pokazuje_operacje -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/admin.py && uv run ruff format src/pbn_export_queue/admin.py`
- [ ] **Commit** (jawne ścieżki): `git commit -m "feat(pbn_export_queue): admin pokazuje kolumnę/filtr operacja"`

---

### Task 05.9 — Wejście synchroniczne (poza kolejką)

> Dodane 2026-08-06 (decyzja #16).

Rekord bywa wysyłany do PBN bez kolejki — ta sama ścieżka musi umieć wycofać.

**Files:**
- Modify: `src/pbn_integrator/utils/synchronization.py` (i/lub miejsce, które
  faktycznie robi synchroniczną wysyłkę — **zweryfikuj wywołujących**:
  `grep -rn --include='*.py' "synchronizuj_publikacje" src/`)
- Test: `src/pbn_integrator/tests/test_wycofanie_sync.py`

- [ ] **Krok 05.9.1 — ustal realny zbiór ścieżek synchronicznych.** Nie zgaduj;
  wypisz wywołujących i rozstrzygnij, które z nich mogą wystąpić w kontekście
  soft-delete (management command? admin action? import?). Stan na 2026-08-07
  (`grep`): `synchronizuj_publikacje` definiowana w
  `src/pbn_integrator/utils/synchronization.py:180`, wołana z
  `src/pbn_integrator/management/commands/pbn_uploader.py:12` i
  `src/pbn_integrator/management/commands/pbn_integrator.py:392` (oba to
  komendy CLI) — zweryfikuj, czy nie doszło nic nowego.
- [ ] **Krok 05.9.2 — test: ścieżka synchroniczna woła prymityw i zostawia
  `SentData` w tym samym stanie co kolejka.** Kluczowa asercja — **równoważność
  obu wejść**:
  ```python
  # po wycofaniu synchronicznym i po wycofaniu przez kolejkę
  # SentData ma być nieodróżnialne (submitted_successfully, withdrawn_at)
  ```
- [ ] **Krok 05.9.3 — implementacja: wywołanie `wycofaj_oswiadczenia()`.**
  ⚠️ **NIE** wołaj `client.delete_all_publication_statements()` bezpośrednio —
  to złamałoby niezmiennik z §4.2 specu (rozjazd `SentData`/`SoftDeleteLog`
  między wejściami).
- [ ] **Krok 05.9.4 — grep kontrolny:** poza prymitywem i testami nie ma
  wywołań `delete_all_publication_statements`, z wyjątkiem
  `pbn_wysylka_oswiadczen` i `pbn_api/management/` (istniejące, wsadowe,
  poza zakresem soft-delete):
  ```bash
  grep -rn --include='*.py' "delete_all_publication_statements" src/ | grep -v tests
  ```
  Baseline (2026-08-07, przed fazą 05) — dokładnie te 3 wiersze produkcyjne:
  `pbn_api/management/commands/pbn_test_wysylka_interaktywna.py:453`,
  `pbn_api/management/commands/pbn_wyslij_oswiadczenia_instytucji.py:192`,
  `pbn_wysylka_oswiadczen/tasks.py:68`. **Po fazie 05 mogą dojść wyłącznie
  wystąpienia w prymitywie** — żadne w `pbn_export_queue/` ani
  `pbn_integrator/`. (`pbn_client` jest w site-packages, więc się tu nie
  pokaże — to poprawne.)

---

### Task 05.8 — Pełna weryfikacja fazy + brak driftu migracji

**Files:** —

- [ ] **Cały plik testowy fazy:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py -x` → wszystkie PASS.
- [ ] **Testy prymitywu:** `uv run pytest src/pbn_api/tests/test_wycofanie.py -x` → PASS.
- [ ] **Regresja całego app kolejki + sentdata:** `uv run pytest src/pbn_export_queue/ src/pbn_api/tests/ -q` → zielono (gałąź WYCOFANIE nie zepsuła istniejących testów wysyłki/managerów/admina; szczególnie `test_pbn_queue_atomicity.py` i `test_pbn_queue_manager.py` po zmianie `sprobuj_utowrzyc_wpis`).
- [ ] **Guardy multi-hosted (obowiązkowo — ta faza dotyka klienta PBN i `SentData`):**
  `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py src/pbn_api/tests/test_multihosted.py -q` → zielono.
- [ ] **Baseline po migracjach (`0011` w kolejce + `0080` w pbn_api):**
  `make baseline-update`, commit `baseline-sql/baseline.sql` +
  `baseline-sql/baseline.meta.json`. ⚠️ Wg CLAUDE.md: **nie** odświeżaj
  baseline w równoległych feature-branchach — jeśli gałąź soft-delete ma
  inne otwarte fazy z migracjami, zrób to RAZ przy scalaniu.
- [ ] **Brak driftu migracji:** `uv run python src/manage.py makemigrations --check --dry-run` → "No changes detected".
- [ ] **Lint całości fazy:** `uv run ruff check src/pbn_export_queue/ src/pbn_api/models/sentdata.py src/pbn_api/wycofanie.py` → czysto.
- [ ] **Newsfragment fazy:** `src/bpp/newsfragments/soft-delete-pbn-wycofanie.feature.rst`
  — „Usunięcie publikacji wysłanej do PBN wycofuje jej oświadczenia dyscyplin
  z profilu instytucji; przywrócenie publikacji wysyła je ponownie."
- [ ] **Commit (jeśli cokolwiek dopięte, jawne ścieżki):** `git commit -m "chore(soft-delete): faza 05 PBN wycofanie — weryfikacja końcowa"`

---

## Podsumowanie zakresu (co ta faza dostarcza fazie 06)

- Prymityw `pbn_api.wycofanie.wycofaj_oswiadczenia(publikacja, client,
  uczelnia=None) -> WynikWycofania` — JEDYNE miejsce wołające
  `delete_all_publication_statements` w kontekście soft-delete.
- `PBN_Export_Queue.Operacja` (`WYSYLKA`/`WYCOFANIE`) + pole `operacja` (default `WYSYLKA`).
- **`pbn_export_queue.operacje.zakolejkuj_wycofanie(instance, user=None,
  uczelnia=None)` i `zakolejkuj_wysylke(instance, user=None, uczelnia=None)`
  — FUNKCJE MODUŁOWE** (nie metody managera), publiczny kontrakt dla
  receiverów fazy 06 (`post_soft_delete`→wycofanie, `post_restore`→wysyłka).
  Gate `pbn_uid_id` **tylko** dla wycofania; obie idempotentne.
  ⇒ **Faza 06 pomija swój Task 5 (shim)** — te funkcje już istnieją pod
  ścieżką, której szuka jej check.
- `pbn_export_queue.operacje.pobierz_konto_techniczne()` +
  `NAZWA_KONTA_TECHNICZNEGO` — `zamowil` dla operacji systemowych
  (`user=None`), zamiast cichego `IntegrityError` udającego „już w kolejce".
  **To zamyka dług, który spec §4.2 i plany 05/06 przerzucały między sobą.**
- Po udanym wycofaniu: `SentData.withdrawn_at` ustawione,
  `submitted_successfully=False`, wiersz NIE skasowany — **na wierszu TEJ
  uczelni**. Restore→WYSYLKA→`mark_as_successful` zeruje `withdrawn_at`.

- **Guard `check_if_record_still_exists()` jest świadomy operacji** —
  soft-delete blokuje WYSYŁKĘ, ale nie WYCOFANIE. Faza 06, dokładając
  receivery sygnałów, dostaje to gotowe; nie musi omijać sprzątaczki
  kolejki ani duplikować `_zajmij_atomowo()`.

## Otwarte / do zgłoszenia poza tą fazą

- **Spec §4.1 i indeks 00 cytują martwą ścieżkę**
  `src/pbn_api/client/mixins/institutions.py:87` (katalog zawiera dziś tylko
  `__pycache__`; kod jest w pakiecie `pbn-client`, plik
  `pbn_client/mixins/institutions.py:87`). Spec §4.2 wskazuje też
  `retry w pbn_api/client/publication_sync.py`, gdzie
  `_delete_statements_with_retry` już nie mieszka. Poprawka specu/indeksu —
  poza zakresem tego planu (inny właściciel plików).
- **Nagrobki (OAI-PMH / CERIF / REST) wyszły do fazy 05b** — decyzja
  właściciela 2026-08-10, patrz baner „PODZIAŁ ZAKRESU" na górze. Termin
  (przed fazą 07) bez zmian. Punkt startowy dla 05b: `const.DELETED_RECORD`
  = `"no"` w `src/cerif_export/const.py:115` (repozytorium **deklaruje
  w `Identify`**, że usunięć nie ogłasza — zmiana tej wartości to zmiana
  kontraktu wobec harvesterów, nie tylko dopisanie atrybutu do nagłówka).
  Architektura providerów jest gotowa: `ProviderEncji.strona()` stronicuje
  keysetem po `(COALESCE(ostatnio_zmieniony, EPOKA), pk)`, a soft-delete
  bumpuje `ostatnio_zmieniony` — brakuje tylko poszerzenia `queryset()`
  o kosz i flagi „to nagrobek" na obiekcie.
- **Twarde skasowanie publikacji zostawia oświadczenia w PBN na zawsze.**
  Wycofanie czyta `pbn_uid` z rekordu, więc bez wiersza nie ma czego wołać
  (kończy się `FINISHED_ERROR` — głośno, ale bezradnie). Właściwe
  rozwiązanie to `SoftDeleteLog` fazy 06 niosący `pbn_uid` niezależnie od
  rekordu. Po fazach 02/04 twarde kasowanie publikacji jest zablokowane
  guardami, więc dziś to teoretyczne.
- **Plan 06** nie wymaga zmian sygnatur (przypięliśmy jego wariant), ale jego
  **Task 5 (shim `operacje.py`) jest teraz martwy** i jego uwaga
  „`zamowil`… **To dług fazy 05**" jest już spełniona przez Task 05.4a —
  warto to tam odnotować przy okazji.
