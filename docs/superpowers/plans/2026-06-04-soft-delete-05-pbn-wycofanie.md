# Soft-delete — Faza 05: PBN wycofanie przez kolejkę

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. TDD: każdy krok najpierw PRAWDZIWY failing test → komenda + FAIL → PRAWDZIWA implementacja → komenda + PASS → commit.

**Goal:** Rozszerzyć `pbn_export_queue` o operację `WYCOFANIE` (obok dotychczasowej `WYSYLKA`), tak by soft-delete publikacji mógł asynchronicznie wycofać oświadczenia dyscyplin z profilu instytucji PBN przez `client.delete_all_publication_statements(pbn_uid)`, z retry/locking/błędami jak istniejąca ścieżka wysyłki. Dostarczyć publiczne funkcje zakolejkowujące (`zakolejkuj_wycofanie`, `zakolejkuj_wysylke`) wołane potem z fazy 06, oraz zaktualizować `SentData` po udanym wycofaniu (`submitted_successfully=False` + znacznik `withdrawn_at`), bez kasowania wiersza.

**Architecture:** Nowe pole `operacja` (`TextChoices` `WYSYLKA="wysylka"`/`WYCOFANIE="wycofanie"`, default `WYSYLKA` dla kompatybilności wstecznej) na `PBN_Export_Queue`. `send_to_pbn()` rozgałęzia się na początku: `WYCOFANIE` → nowa metoda `withdraw_from_pbn()` (GET klienta jak w wysyłce, `delete_all_publication_statements` z retry, aktualizacja `SentData`, status przez istniejące `_handle_successful_send`-analog / `error()`); `WYSYLKA` → dotychczasowa ścieżka bez zmian. Gate zakolejkowania: wycofanie tylko gdy rekord ma `pbn_uid_id`.

**Tech Stack:** Django, PostgreSQL, Celery + `pbn_export_queue`, `pbn_api` (`PBNClient`, `SentData`), pytest + model_bakery + `unittest.mock`.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md) (§4 całość) · Indeks: [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md) (kontrakt `pbn_export_queue` rozszerzenie + `SentData`).

**Zależność:** Faza 02 (publikacje `SoftDeleteModel`). Faza 06 woła `zakolejkuj_wycofanie`/`zakolejkuj_wysylke` z receiverów sygnałów — tu budujemy mechanizm + funkcje, NIE podpinamy sygnałów.

---

## Reguły BPP (obowiązują w każdym kroku)

- Wszystkie komendy Pythona przez `uv run` (np. `uv run pytest ...`).
- Testy: pytest, standalone functions / klasy bez `unittest.TestCase`, `@pytest.mark.django_db`, `model_bakery.baker.make`, mock klienta PBN przez `unittest.mock`.
- Max długość linii 88 znaków (ruff). Komentarze/teksty po polsku.
- **NIE modyfikować istniejących migracji** w `src/*/migrations/`. Ostatnia migracja `pbn_export_queue`: `0007_reclassify_doiorwwwmissing_errors.py` → nowe to `0008_*`.
- Po każdym kroku z kodem produkcyjnym: `ruff check` + `ruff format` na dotkniętych plikach, potem commit.

---

## Stan zastany (zweryfikowany w kodzie — używać tych nazw VERBATIM)

`src/pbn_export_queue/models.py`:
- `PBN_Export_Queue`: `object_id`, `content_type`, `rekord_do_wysylki` (GFK), `zamowil` (FK user, `on_delete=CASCADE`), `zamowiono`, `wysylke_podjeto`, `wysylke_zakonczono`, `ilosc_prob`, `zakonczono_pomyslnie` (`BooleanField(null=True, default=None)`), `komunikat`, `retry_after_user_authorised`, `rodzaj_bledu` (`RodzajBledu.TECHNICZNY/MERYTORYCZNY`), `wykluczone`.
- Manager `PBN_Export_QueueManager`: `filter_rekord_do_wysylki(rekord)` (filtr `wysylke_zakonczono=None`), `sprobuj_utowrzyc_wpis(user, rekord)` (rzuca `AlreadyEnqueuedError` gdy już w kolejce).
- Metody: `send_to_pbn()` (`refresh_from_db`; jeśli `wysylke_zakonczono` → `FINISHED_OKAY`; gdy rekord zniknął → `error(...)`; inkrementuje `ilosc_prob`; woła `sprobuj_wyslac_do_pbn_celery(user=self.zamowil.get_pbn_user(), obj=self.rekord_do_wysylki, force_upload=True)`; `_handle_pbn_exception(exc)` na wyjątek; `_handle_successful_send(sent_data, notificator)` na sukces), `error(msg, rodzaj=None)` (ustawia `wysylke_zakonczono`, `zakonczono_pomyslnie=False`, zwraca `SendStatus.FINISHED_ERROR`), `dopisz_komunikat(msg)`, `check_if_record_still_exists()`, `prepare_for_resend(user, message_suffix)`, `sprobuj_wyslac_do_pbn()` (deleguje `task_sprobuj_wyslac_do_pbn.delay(self.pk)`).
- `SendStatus` (Enum): `RETRY_SOON`, `RETRY_LATER`, `RETRY_MUCH_LATER`, `RETRY_AFTER_USER_AUTHORISED`, `WYKLUCZONE`, `FINISHED_OKAY`, `FINISHED_ERROR`.

`src/pbn_export_queue/tasks.py`:
- `task_sprobuj_wyslac_do_pbn(pk)` — lock przez `cache.add(LOCK_PREFIX+pk)`, `wait_for_object`, `p.send_to_pbn()`, `match` na `SendStatus` (RETRY_* → `apply_async(countdown=...)`, `FINISHED_OKAY` → `check_and_send_next_in_queue()`). Lock zwalniany w `finally`. **Ta sama maszyneria obsłuży WYCOFANIE bez zmian** — `send_to_pbn()` zwraca `SendStatus`.

`src/pbn_api/client/mixins/institutions.py`:
- `delete_all_publication_statements(publicationId)` (`:87`) — DELETE; może rzucić `ResourceLockedException`, `CannotDeleteStatementsException` (gdy PBN: "nie istnieją oświadczenia"), `HttpException`.

`src/pbn_api/client/publication_sync.py`:
- `_delete_statements_with_retry(pbn_uid_id, max_tries=5)` (`:411`) — pętla: `delete_all_publication_statements` → przy `CannotDeleteStatementsException` retry (5 prób, `sleep(0.5)`), inne wyjątki lecą w górę. Wzorzec retry dla wycofania.

`src/pbn_api/models/sentdata.py`:
- `SentDataManager`: `get_for_rec(rec)` (rzuca `SentData.DoesNotExist`), `mark_as_successful(rec, pbn_uid_id=None, api_response_status="")` (ustawia `submitted_successfully=True`, `uploaded_okay=True`), `mark_as_failed(...)`, `create_or_update_before_upload(...)`.
- `SentData` pola: `content_type`/`object_id`/`object` (GFK), `submitted_successfully` (`BooleanField`), `submitted_at`, `api_response_status` (`TextField`), `uploaded_okay`, `pbn_uid` (FK `pbn_api.Publication`, `SET_NULL`).

`src/bpp/admin/helpers/pbn_api/cli.py`:
- `sprobuj_wyslac_do_pbn_celery(user, obj, force_upload=False, pbn_client=None)` — buduje `pbn_client = uczelnia.pbn_client(user.pbn_token)`. Wzorzec pozyskania klienta dla wycofania.

`src/bpp/models/abstract/pbn.py`: rekordy mają `pbn_uid = OneToOneField("pbn_api.Publication")` → `rec.pbn_uid_id` to PBN UID (string id publikacji w PBN).

---

## Decyzja: znacznik wycofania w `SentData` — nowe pole `withdrawn_at`

**Wybór: dodać nowe pole `withdrawn_at = models.DateTimeField(null=True, blank=True)` na `SentData`** (migracja `pbn_api/migrations/0XXX`).

**Uzasadnienie (dlaczego NIE `api_response_status`):** `api_response_status` to swobodny `TextField` nadpisywany przy KAŻDEJ operacji (`mark_as_successful`/`mark_as_failed`/`create_or_update_before_upload` go czyszczą/ustawiają surową odpowiedzią API). Użycie go jako znacznika stanu byłoby kruche — pierwsza kolejna wysyłka by go skasowała, a parsowanie statusu z tekstu odpowiedzi PBN jest nieodporne. Dedykowane `withdrawn_at` (timestamp) daje: (1) jednoznaczny, kwerowalny stan "rekord wycofany w PBN dnia X", (2) audyt kiedy, (3) symetrię: restore→`WYSYLKA`→`mark_as_successful` musi je wyzerować (`withdrawn_at=None`). Wiersza `SentData` NIE kasujemy (zostaje dla re-matchingu przy restore i dla `SoftDeleteLog` w fazie 06).

---

## Tasks

### Task 05.1 — Pole `operacja` na `PBN_Export_Queue` + migracja

**Files:**
- `src/pbn_export_queue/models.py` (klasa `PBN_Export_Queue`, dodać `Operacja` TextChoices + pole `operacja`)
- `src/pbn_export_queue/migrations/0008_pbn_export_queue_operacja.py` (NOWA)
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
- [ ] **Migracja:** `uv run python src/manage.py makemigrations pbn_export_queue --name pbn_export_queue_operacja`. Zweryfikuj, że plik to `0008_pbn_export_queue_operacja.py` i dodaje wyłącznie pole `operacja` (`AddField`, default `wysylka`). NIE edytować wcześniejszych migracji.
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_operacja_default_wysylka -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/models.py src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/models.py src/pbn_export_queue/migrations/0008_pbn_export_queue_operacja.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit:** `git add -A && git commit -m "feat(pbn_export_queue): pole operacja (WYSYLKA|WYCOFANIE) + migracja"`

---

### Task 05.2 — `withdrawn_at` na `SentData` + symetria w managerze

**Files:**
- `src/pbn_api/models/sentdata.py` (pole `withdrawn_at`; manager: `mark_as_withdrawn`; reset `withdrawn_at` w `mark_as_successful`)
- `src/pbn_api/migrations/0XXX_sentdata_withdrawn_at.py` (NOWA — numer wg `makemigrations`)
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
      def mark_as_withdrawn(self, rec, api_response_status=""):
          """Oznacza rekord jako wycofany z PBN (oświadczenia usunięte).

          Wiersza SentData NIE kasujemy — zostaje dla audytu i
          re-matchingu przy restore. submitted_successfully=False, bo
          rekord nie jest już "wystawiony" w PBN.
          """
          sd = self.get_for_rec(rec)
          sd.submitted_successfully = False
          sd.withdrawn_at = timezone.now()
          if api_response_status:
              sd.api_response_status = api_response_status
          sd.save()
          return sd
  ```
- [ ] **Implementacja — symetria w `mark_as_successful`.** W `SentDataManager.mark_as_successful`, po `sd.submitted_successfully = True`, dodaj `sd.withdrawn_at = None` (restore→WYSYLKA czyści znacznik wycofania). (`timezone` jest już zaimportowany w pliku.)
- [ ] **Migracja:** `uv run python src/manage.py makemigrations pbn_api --name sentdata_withdrawn_at`. Zweryfikuj, że dodaje wyłącznie pole `withdrawn_at`.
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_sentdata_mark_as_withdrawn -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_api/models/sentdata.py src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_api/models/sentdata.py src/pbn_api/migrations/*sentdata_withdrawn_at*.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit:** `git add -A && git commit -m "feat(pbn_api): SentData.withdrawn_at + mark_as_withdrawn; reset przy mark_as_successful"`

---

### Task 05.3 — `withdraw_from_pbn()` + rozgałęzienie w `send_to_pbn()`

Gałąź `WYCOFANIE` woła `client.delete_all_publication_statements(pbn_uid)` z retry analogicznym do `_delete_statements_with_retry` (obsługa `CannotDeleteStatementsException` jako sukces "nic do wycofania"), aktualizuje `SentData` i zwraca `SendStatus`. `WYSYLKA` → ścieżka bez zmian. Lock/retry/`ilosc_prob`/`task_sprobuj_wyslac_do_pbn` działają niezmienione (zwracamy ten sam typ `SendStatus`).

**Files:**
- `src/pbn_export_queue/models.py` (`send_to_pbn` rozgałęzienie; nowa `withdraw_from_pbn`; helper `_pozyskaj_klienta_pbn`)
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — WYCOFANIE woła `delete_all_publication_statements` z właściwym pbn_uid + oznacza SentData.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_wycofanie_wola_delete_all_statements(wydawnictwo_ciagle, admin_user):
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
      )

      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
          operacja=PBN_Export_Queue.Operacja.WYCOFANIE,
          wysylke_zakonczono=None,
      )

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
- [ ] **Implementacja — helper klienta.** W `PBN_Export_Queue` dodaj metodę pozyskania klienta (wzorzec z `cli.py`):
  ```python
      def _pozyskaj_klienta_pbn(self):
          """Buduje klienta PBN dla użytkownika, który zlecił operację.

          Analogicznie do sprobuj_wyslac_do_pbn_celery: token z konta PBN
          zamawiającego, klient z parametrów Uczelni.
          """
          from bpp.models import Uczelnia

          pbn_user = self.zamowil.get_pbn_user()
          uczelnia = Uczelnia.objects.get_default()
          return uczelnia.pbn_client(pbn_user.pbn_token)
  ```
- [ ] **Implementacja — `withdraw_from_pbn`.** Dodaj metodę (retry wzorowany na `_delete_statements_with_retry`, ale `CannotDeleteStatementsException` traktujemy jako sukces — nic nie ma do wycofania):
  ```python
      def withdraw_from_pbn(self):
          """Wycofuje oświadczenia dyscyplin publikacji z profilu instytucji.

          Gałąź operacji WYCOFANIE: woła delete_all_publication_statements
          z retry. CannotDeleteStatementsException = oświadczeń już nie ma
          → traktujemy jako sukces (idempotencja). Po sukcesie oznacza
          SentData jako wycofany. :return: SendStatus
          """
          import time

          from pbn_api.exceptions import (
              CannotDeleteStatementsException,
              ResourceLockedException,
          )

          rec = self.rekord_do_wysylki
          pbn_uid = getattr(rec, "pbn_uid_id", None)
          if not pbn_uid:
              # Gate obronny: nic do wycofania (rekord nigdy nie poszedł
              # do PBN). Nie powinno się zdarzyć — zakolejkuj_wycofanie
              # nie tworzy takich wpisów — ale na wszelki wypadek.
              self.wysylke_zakonczono = timezone.now()
              self.zakonczono_pomyslnie = True
              self.dopisz_komunikat(
                  "Wycofanie pominięte: rekord nie ma PBN UID."
              )
              self.save()
              return SendStatus.FINISHED_OKAY

          try:
              client = self._pozyskaj_klienta_pbn()
          except Exception as exc:
              return self._handle_pbn_exception(exc)

          no_tries = 5
          while True:
              try:
                  client.delete_all_publication_statements(pbn_uid)
                  break
              except CannotDeleteStatementsException:
                  # Oświadczeń już nie ma w PBN — cel osiągnięty.
                  break
              except ResourceLockedException as exc:
                  self.dopisz_komunikat(
                      f"{exc}, ponawiam wycofanie za kilka minut..."
                  )
                  self.save()
                  return SendStatus.RETRY_LATER
              except Exception as exc:
                  if no_tries <= 0:
                      return self._handle_pbn_exception(exc)
                  no_tries -= 1
                  time.sleep(0.5)

          from pbn_api.models.sentdata import SentData

          try:
              SentData.objects.mark_as_withdrawn(rec)
          except SentData.DoesNotExist:
              # Brak wiersza SentData (rekord nigdy realnie nie wysłany,
              # mimo pbn_uid) — nie jest błędem wycofania.
              pass

          self.wysylke_zakonczono = timezone.now()
          self.zakonczono_pomyslnie = True
          self.dopisz_komunikat(
              f"Wycofano oświadczenia dyscyplin z PBN (UID={pbn_uid})."
          )
          self.save()
          return SendStatus.FINISHED_OKAY
  ```
- [ ] **Implementacja — rozgałęzienie w `send_to_pbn`.** Na początku `send_to_pbn`, PO `self.refresh_from_db()` i PO wczesnym zwrocie `if self.wysylke_zakonczono is not None: return SendStatus.FINISHED_OKAY`, ale PRZED `check_if_record_still_exists`/inkrementacją prób, dodaj:
  ```python
          if not self.check_if_record_still_exists():
              return self.error(
                  "Rekord został usunięty nim wysyłka była możliwa.",
                  rodzaj=RodzajBledu.TECHNICZNY,
              )

          self.wysylke_podjeto = timezone.now()
          if self.retry_after_user_authorised:
              self.retry_after_user_authorised = None
          self.ilosc_prob += 1
          self.save()

          if self.operacja == self.Operacja.WYCOFANIE:
              return self.withdraw_from_pbn()
  ```
  (Przenieś istniejący blok `check_if_record_still_exists` + `wysylke_podjeto`/`ilosc_prob` tak, by gałąź WYCOFANIE następowała PO inkrementacji prób — wycofanie ma korzystać z tego samego licznika `ilosc_prob` i tego samego guardu "rekord zniknął". Reszta `send_to_pbn` — ścieżka WYSYLKA — bez zmian.)
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wycofanie_wola_delete_all_statements -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/models.py && uv run ruff format src/pbn_export_queue/models.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit:** `git add -A && git commit -m "feat(pbn_export_queue): withdraw_from_pbn + gałąź WYCOFANIE w send_to_pbn"`

---

### Task 05.4 — WYSYLKA dalej działa (regresja rozgałęzienia)

Upewnij się, że dodanie gałęzi WYCOFANIE nie zmieniło ścieżki WYSYLKA: wpis z domyślną operacją nadal woła `sprobuj_wyslac_do_pbn_celery`, NIE `delete_all_publication_statements`.

**Files:**
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — WYSYLKA nie woła delete_all_statements.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_wysylka_nie_wola_delete_all_statements(wydawnictwo_ciagle, admin_user):
      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
          operacja=PBN_Export_Queue.Operacja.WYSYLKA,
          wysylke_zakonczono=None,
      )

      sent_data = MagicMock()
      with patch.object(admin_user, "get_pbn_user"), patch(
          "pbn_export_queue.models.PBN_Export_Queue._pozyskaj_klienta_pbn"
      ) as mock_klient, patch(
          "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery",
          return_value=(sent_data, ["ok"]),
      ) as mock_send:
          result = wpis.send_to_pbn()

      assert result == SendStatus.FINISHED_OKAY
      mock_send.assert_called_once()
      mock_klient.assert_not_called()
  ```
- [ ] **Komenda:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wysylka_nie_wola_delete_all_statements -x`. Jeśli przechodzi od razu — to dowód regresyjny, że ścieżka WYSYLKA jest nietknięta; zostaw test jako guard (nie wymaga zmian implementacji). Jeśli FAIL — popraw rozgałęzienie w 05.3, by WYSYLKA nie wpadała w gałąź wycofania.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit:** `git add -A && git commit -m "test(pbn_export_queue): guard regresyjny — WYSYLKA nie woła delete_all_statements"`

---

### Task 05.5 — Funkcje zakolejkowujące + gate na `pbn_uid`

`zakolejkuj_wycofanie(rekord, user=None)` i `zakolejkuj_wysylke(rekord, user=None)` — publiczne, wołane potem z fazy 06 (receivery sygnałów). Tworzą wpis przez manager z odpowiednią `operacja` i delegują do `task_sprobuj_wyslac_do_pbn.delay(pk)`. Gate: wycofanie tylko gdy `rekord.pbn_uid_id` ustawione (brak PBN UID → no-op, brak wpisu). Idempotencja: jeśli rekord już w kolejce (`AlreadyEnqueuedError`) → no-op.

**Files:**
- `src/pbn_export_queue/models.py` (manager `PBN_Export_QueueManager`: metody `zakolejkuj_wycofanie`, `zakolejkuj_wysylke`; rozszerz `sprobuj_utowrzyc_wpis` o argument `operacja`)
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — gate + utworzenie wpisu WYCOFANIE.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_zakolejkuj_wycofanie_gate_brak_pbn_uid(wydawnictwo_ciagle, admin_user):
      assert wydawnictwo_ciagle.pbn_uid_id is None
      with patch(
          "pbn_export_queue.models.task_sprobuj_wyslac_do_pbn"
      ) as mock_task:
          wpis = PBN_Export_Queue.objects.zakolejkuj_wycofanie(
              wydawnictwo_ciagle, user=admin_user
          )
      assert wpis is None
      assert PBN_Export_Queue.objects.filter_rekord_do_wysylki(
          wydawnictwo_ciagle
      ).count() == 0
      mock_task.delay.assert_not_called()


  @pytest.mark.django_db
  def test_zakolejkuj_wycofanie_tworzy_wpis(wydawnictwo_ciagle, admin_user):
      from pbn_api.models import Publication

      pub = baker.make(Publication)
      wydawnictwo_ciagle.pbn_uid = pub
      wydawnictwo_ciagle.save()

      with patch(
          "pbn_export_queue.models.task_sprobuj_wyslac_do_pbn"
      ) as mock_task:
          wpis = PBN_Export_Queue.objects.zakolejkuj_wycofanie(
              wydawnictwo_ciagle, user=admin_user
          )

      assert wpis is not None
      assert wpis.operacja == PBN_Export_Queue.Operacja.WYCOFANIE
      mock_task.delay.assert_called_once_with(wpis.pk)


  @pytest.mark.django_db
  def test_zakolejkuj_wysylke_tworzy_wpis(wydawnictwo_ciagle, admin_user):
      with patch(
          "pbn_export_queue.models.task_sprobuj_wyslac_do_pbn"
      ) as mock_task:
          wpis = PBN_Export_Queue.objects.zakolejkuj_wysylke(
              wydawnictwo_ciagle, user=admin_user
          )
      assert wpis is not None
      assert wpis.operacja == PBN_Export_Queue.Operacja.WYSYLKA
      mock_task.delay.assert_called_once_with(wpis.pk)


  @pytest.mark.django_db
  def test_zakolejkuj_idempotentne(wydawnictwo_ciagle, admin_user):
      from pbn_api.models import Publication

      wydawnictwo_ciagle.pbn_uid = baker.make(Publication)
      wydawnictwo_ciagle.save()
      with patch("pbn_export_queue.models.task_sprobuj_wyslac_do_pbn"):
          first = PBN_Export_Queue.objects.zakolejkuj_wycofanie(
              wydawnictwo_ciagle, user=admin_user
          )
          second = PBN_Export_Queue.objects.zakolejkuj_wycofanie(
              wydawnictwo_ciagle, user=admin_user
          )
      assert first is not None
      assert second is None
      assert PBN_Export_Queue.objects.filter_rekord_do_wysylki(
          wydawnictwo_ciagle
      ).count() == 1
  ```
- [ ] **Komenda + FAIL:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py -k zakolejkuj -x` → `AttributeError` (`zakolejkuj_wycofanie`).
- [ ] **Implementacja — import tasku w models.py.** Na górze `withdraw_from_pbn`/managerze potrzebny `task_sprobuj_wyslac_do_pbn`. Żeby testy mogły patchować `pbn_export_queue.models.task_sprobuj_wyslac_do_pbn`, zaimportuj go **lokalnie w funkcji** i przypisz do nazwy modułowej — najprościej: w metodach managera użyj importu modułu i odwołania, które patch przechwyci. Wzorzec (unikamy cyklicznego importu na top-level — `tasks.py` importuje `models`):
  ```python
      def _delay_task(self, pk):
          from pbn_export_queue import tasks

          tasks.task_sprobuj_wyslac_do_pbn.delay(pk)
  ```
  ORAZ w testach patchuj `pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn` zamiast `pbn_export_queue.models...` — **popraw ścieżki patcha w testach 05.5 na `pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn`** (zaktualizuj literały w testach przy pierwszym uruchomieniu, gdy zobaczysz gdzie realnie żyje symbol). Cel: brak cyklicznego importu top-level.
- [ ] **Implementacja — rozszerz `sprobuj_utowrzyc_wpis` o `operacja`.** W managerze:
  ```python
      def sprobuj_utowrzyc_wpis(self, user, rekord, operacja=None):
          if self.filter_rekord_do_wysylki(rekord).exists():
              raise AlreadyEnqueuedError(
                  "ten rekord jest już w kolejce do wysyłki"
              )
          kwargs = {"rekord_do_wysylki": rekord, "zamowil": user}
          if operacja is not None:
              kwargs["operacja"] = operacja
          return self.create(**kwargs)
  ```
  (Zachowuje dotychczasową sygnaturę dla istniejących wywołań — `operacja` opcjonalna, default modelu `WYSYLKA`.)
- [ ] **Implementacja — `zakolejkuj_wycofanie` / `zakolejkuj_wysylke`.** W managerze:
  ```python
      def zakolejkuj_wysylke(self, rekord, user=None):
          """Tworzy wpis WYSYLKA i uruchamia wysyłkę w tle.

          Wołane m.in. przy restore publikacji (faza 06). Idempotentne —
          gdy rekord już w kolejce, zwraca None.
          """
          from pbn_api.exceptions import AlreadyEnqueuedError

          try:
              wpis = self.sprobuj_utowrzyc_wpis(
                  user, rekord, operacja=self.model.Operacja.WYSYLKA
              )
          except AlreadyEnqueuedError:
              return None
          self._delay_task(wpis.pk)
          return wpis

      def zakolejkuj_wycofanie(self, rekord, user=None):
          """Tworzy wpis WYCOFANIE i uruchamia wycofanie w tle.

          Gate: tylko gdy rekord ma PBN UID (inaczej nic nie poszło do
          PBN — no-op, zwraca None). Idempotentne — gdy rekord już
          w kolejce, zwraca None.
          """
          from pbn_api.exceptions import AlreadyEnqueuedError

          if not getattr(rekord, "pbn_uid_id", None):
              return None
          try:
              wpis = self.sprobuj_utowrzyc_wpis(
                  user, rekord, operacja=self.model.Operacja.WYCOFANIE
              )
          except AlreadyEnqueuedError:
              return None
          self._delay_task(wpis.pk)
          return wpis
  ```
  (`user=None` dozwolone — operacje systemowe/celery; pole `zamowil` jest `on_delete=CASCADE` i NOT NULL, więc gdy `user is None` ścieżka wymaga konta technicznego. **Zweryfikuj w fazie 06**, czy receiver zawsze poda usera; tu zostawiamy sygnaturę `user=None` zgodną z kontraktem PINNED, a faktyczne wymaganie NOT NULL na `zamowil` rozwiązuje faza 06/07 przekazując konto. Jeśli test z `user=None` jest potrzebny — dodać dopiero gdy faza 06 ustali konto techniczne.)
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py -k zakolejkuj -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/models.py src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/models.py src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit:** `git add -A && git commit -m "feat(pbn_export_queue): zakolejkuj_wycofanie/zakolejkuj_wysylke + gate pbn_uid"`

---

### Task 05.6 — Idempotencja/retry wycofania (ResourceLocked + CannotDelete)

**Files:**
- Test path: `src/pbn_export_queue/tests/test_operacja_wycofanie.py`

- [ ] **Failing test — `CannotDeleteStatementsException` traktowany jak sukces.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_wycofanie_brak_oswiadczen_to_sukces(wydawnictwo_ciagle, admin_user):
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
      )
      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
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
          wydawnictwo_ciagle
      ).withdrawn_at is not None
  ```
- [ ] **Komenda:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wycofanie_brak_oswiadczen_to_sukces -x` → powinien przejść (logika z 05.3 traktuje `CannotDeleteStatementsException` jako break/sukces). Jeśli FAIL — dopracuj `withdraw_from_pbn`.

- [ ] **Failing test — `ResourceLockedException` → RETRY_LATER, bez oznaczenia SentData.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_wycofanie_locked_retry_later(wydawnictwo_ciagle, admin_user):
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
      )
      wpis = baker.make(
          PBN_Export_Queue,
          rekord_do_wysylki=wydawnictwo_ciagle,
          zamowil=admin_user,
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
          wydawnictwo_ciagle
      ).withdrawn_at is None
  ```
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_wycofanie_locked_retry_later -x` → PASS (logika z 05.3 zwraca `RETRY_LATER` na `ResourceLockedException` bez ustawiania `wysylke_zakonczono`). Jeśli FAIL — popraw kolejność `except` w `withdraw_from_pbn`.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/tests/test_operacja_wycofanie.py && uv run ruff format src/pbn_export_queue/tests/test_operacja_wycofanie.py`
- [ ] **Commit:** `git add -A && git commit -m "test(pbn_export_queue): wycofanie — idempotencja CannotDelete + retry ResourceLocked"`

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
- [ ] **Implementacja — admin.** W `src/pbn_export_queue/admin.py`: dodaj `"operacja"` do `list_display` (np. zaraz po `"rekord_do_wysylki"`), do `list_filter` i do `readonly_fields`.
- [ ] **Komenda + PASS:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py::test_admin_pokazuje_operacje -x` → PASS.
- [ ] **Lint:** `uv run ruff check src/pbn_export_queue/admin.py && uv run ruff format src/pbn_export_queue/admin.py`
- [ ] **Commit:** `git add -A && git commit -m "feat(pbn_export_queue): admin pokazuje kolumnę/filtr operacja"`

---

### Task 05.8 — Pełna weryfikacja fazy + brak driftu migracji

**Files:** —

- [ ] **Cały plik testowy fazy:** `uv run pytest src/pbn_export_queue/tests/test_operacja_wycofanie.py -x` → wszystkie PASS.
- [ ] **Regresja całego app kolejki + sentdata:** `uv run pytest src/pbn_export_queue/ src/pbn_api/tests/ -q` → zielono (gałąź WYCOFANIE nie zepsuła istniejących testów wysyłki/managerów/admina).
- [ ] **Brak driftu migracji:** `uv run python src/manage.py makemigrations --check --dry-run` → "No changes detected".
- [ ] **Lint całości fazy:** `uv run ruff check src/pbn_export_queue/ src/pbn_api/models/sentdata.py` → czysto.
- [ ] **Commit (jeśli cokolwiek dopięte):** `git add -A && git commit -m "chore(soft-delete): faza 05 PBN wycofanie — weryfikacja końcowa"`

---

## Podsumowanie zakresu (co ta faza dostarcza fazie 06)

- `PBN_Export_Queue.Operacja` (`WYSYLKA`/`WYCOFANIE`) + pole `operacja` (default `WYSYLKA`).
- `PBN_Export_Queue.objects.zakolejkuj_wycofanie(rekord, user=None)` i `zakolejkuj_wysylke(rekord, user=None)` — publiczny kontrakt dla receiverów fazy 06 (`post_soft_delete`→wycofanie, `post_restore`→wysyłka). Gate wycofania na `pbn_uid_id`, idempotentne.
- Po udanym wycofaniu: `SentData.withdrawn_at` ustawione, `submitted_successfully=False`, wiersz NIE skasowany. Restore→WYSYLKA→`mark_as_successful` zeruje `withdrawn_at`.
