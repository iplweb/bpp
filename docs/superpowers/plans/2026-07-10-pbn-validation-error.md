# PBNValidationError Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zamienić walidacyjne odrzucenia PBN (HTTP 4xx z listą błędów pól) z szumu w Rollbarze na czytelny komunikat dla użytkownika, przez dedykowany wyjątek `PBNValidationError`.

**Architecture:** Nowy `PBNValidationError(HttpException)` z hostile-input-safe helperem `parse_pbn_validation_details`. Podnoszony w jednym chokepoincie `transport._check_error_response` (POST/DELETE) dla 4xx rozpoznanych jako walidacja — bez raportu do Rollbara. Ścieżka admina (`sprobuj_wyslac_do_pbn`) dostaje własny handler z czytelną listą; pętle retry oświadczeń przerywają się natychmiast na walidacji; ścieżka kolejkowa klasyfikuje bez zmian (MERYTORYCZNY) dzięki dziedziczeniu po `HttpException` i zachowaniu tuplowego `str()`.

**Tech Stack:** Python 3.10+, Django, pytest, model_bakery, pytest-mock (`mocker`).

## Global Constraints

- Max line length: 88 znaków (ruff).
- `uv run` przed każdą komendą Pythona/pytest. NIGDY goły `python`/`pytest`.
- Testy: konwencja pytest (funkcje, bez `unittest.TestCase`), `@pytest.mark.django_db` dla DB, `model_bakery.baker.make`.
- NIE nadpisywać `__str__` w `PBNValidationError` — `str(exc)` MUSI dawać odziedziczoną tuplę `(status, url, content)` (kolejka parsuje `SentData.exception` przez `looks_like_tuple`).
- `parse_pbn_validation_details` MUSI być hostile-input-safe: żadne wejście z PBN nie może z niej wyrzucić wyjątku.
- Bramka detekcji walidacji: `400 <= status < 500 and status not in (401, 403, 423)`.
- NIE modyfikować istniejących plików migracji.
- Praca w worktree `~/Programowanie/bpp-pbn-validation-error`, branch `fix-rollbar443-pbn-validation-error` (od `dev`).

Spec źródłowy: `docs/superpowers/specs/2026-07-10-pbn-validation-error-design.md`

---

### Task 1: `parse_pbn_validation_details` + `PBNValidationError`

**Files:**
- Modify: `src/pbn_client/exceptions.py` (dodać funkcję + klasę; obok istniejącej `HttpException` na linii 29)
- Create: `src/pbn_client/tests/__init__.py` (pusty — katalog testów nie istnieje)
- Test: `src/pbn_client/tests/test_pbn_validation_error.py`

**Interfaces:**
- Produces:
  - `parse_pbn_validation_details(parsed_json) -> list[str] | None` — zdeduplikowana lista komunikatów walidacyjnych (kolejność wg wejścia) albo `None` gdy to nie walidacja. Hostile-input-safe.
  - `class PBNValidationError(HttpException)` z `self.messages: list[str]` i metodą `user_messages() -> list[str]`. Bez `__str__` (dziedziczy tuplę).

- [ ] **Step 1: Write the failing tests**

Utwórz `src/pbn_client/tests/__init__.py` jako pusty plik, oraz `src/pbn_client/tests/test_pbn_validation_error.py`:

```python
import pytest

from pbn_client.exceptions import (
    HttpException,
    PBNValidationError,
    parse_pbn_validation_details,
)


def test_parse_format1_values_dedup_preserve_order():
    j = {"details": {"a": "Wymagane!", "b": "Wymagane!", "c": "Inne!"}}
    assert parse_pbn_validation_details(j) == ["Wymagane!", "Inne!"]


def test_parse_format2_description_fallback():
    # Realny Format 2 (migracja 0006): element ma "code" i "description",
    # NIE ma "message" — czytelny tekst musi pochodzić z description.
    j = [
        {
            "requestPosition": 0,
            "code": "NOT_UNIQUE_PUBLICATION_ISBN_ISMN",
            "description": "Publikacja o identycznym ISBN już istnieje.",
        }
    ]
    assert parse_pbn_validation_details(j) == [
        "Publikacja o identycznym ISBN już istnieje."
    ]


def test_parse_format2_message_wins_over_description():
    j = [{"message": "M", "description": "D", "code": "C"}]
    assert parse_pbn_validation_details(j) == ["M"]


def test_parse_hostile_list_value_does_not_crash():
    # PBN potrafi zwrócić listę jako wartość details — naiwny dict.fromkeys
    # rzuciłby TypeError: unhashable type: 'list'.
    j = {"details": {"x": ["a", "b"]}}
    assert parse_pbn_validation_details(j) == ["a, b"]


def test_parse_hostile_dict_and_none_values():
    j = {"details": {"x": {"k": "v"}, "y": None}}
    # Nie wybucha; wartości skoercowane do str.
    result = parse_pbn_validation_details(j)
    assert result is not None
    assert len(result) == 2


def test_parse_format2_nondict_element_skipped():
    j = ["goły string", {"code": "C"}]
    assert parse_pbn_validation_details(j) == ["C"]


def test_parse_non_validation_returns_none():
    assert parse_pbn_validation_details({"message": "Forbidden"}) is None
    assert parse_pbn_validation_details({"details": {}}) is None
    assert parse_pbn_validation_details(None) is None
    assert parse_pbn_validation_details("jakis string") is None
    assert parse_pbn_validation_details([]) is None


def test_pbnvalidationerror_user_messages():
    e = PBNValidationError(
        400,
        "/api/v1/publications",
        '{"details": {"openAccess.releaseDate": "Data ... wymagana!"}}',
    )
    assert e.user_messages() == ["Data ... wymagana!"]


def test_pbnvalidationerror_str_is_tuple_not_overridden():
    # KRYTYCZNE: str() musi dawać tuplę (kolejka parsuje SentData.exception).
    e = PBNValidationError(
        400, "/api/v1/publications", '{"details": {"a": "b"}}'
    )
    s = str(e)
    assert s.startswith("(")
    assert "/api/v1/publications" in s
    assert '"details"' in s  # surowy JSON body zachowany w tracebacku
    assert isinstance(e, HttpException)  # podklasa — wsteczna zgodność
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/pbn_client/tests/test_pbn_validation_error.py -v`
Expected: FAIL — `ImportError: cannot import name 'PBNValidationError'` / `parse_pbn_validation_details`.

- [ ] **Step 3: Implement in `src/pbn_client/exceptions.py`**

Dodaj na końcu istniejącego bloku wyjątków (po `class HttpException` / w dogodnym miejscu pliku), zachowując istniejący `import json` na górze pliku:

```python
def parse_pbn_validation_details(parsed_json):
    """Zwraca zdeduplikowaną listę komunikatów walidacyjnych PBN, albo None
    gdy ``parsed_json`` nie jest odpowiedzią walidacyjną.

    Rozpoznaje dwa formaty odpowiedzi PBN:
    - Format 1: {"details": {pole: komunikat, ...}} — dict z niepustym details.
    - Format 2: [{"code": ..., "description": ...}, ...] — lista dict-ów;
      dla każdego elementu fallback message -> description -> code.

    Hostile-input-safe: wartości są koercowane do str (listy spłaszczane),
    elementy nie-dict w Format 2 pomijane. Żadne wejście nie wyrzuca wyjątku.
    Deduplikacja zachowuje pierwszą kolejność wystąpienia.
    """

    def _coerce(val):
        if isinstance(val, (list, tuple)):
            return ", ".join(str(v) for v in val)
        return str(val)

    messages = []
    if isinstance(parsed_json, dict):
        details = parsed_json.get("details")
        if isinstance(details, dict) and details:
            messages = [_coerce(v) for v in details.values()]
    elif isinstance(parsed_json, list) and parsed_json:
        for el in parsed_json:
            if not isinstance(el, dict):
                continue
            text = el.get("message") or el.get("description") or el.get("code")
            if text:
                messages.append(_coerce(text))

    if not messages:
        return None
    return list(dict.fromkeys(messages))


class PBNValidationError(HttpException):
    """PBN odrzucił dane (Validation failed). Błąd merytoryczny — dane do
    poprawienia przez użytkownika, NIE bug w kodzie.

    NIE nadpisujemy __str__: str(exc) musi dawać odziedziczoną tuplę
    (status, url, content), bo kolejka parsuje SentData.exception przez
    looks_like_tuple, a traceback ma zachować surowy JSON body.
    """

    def __init__(self, status_code, url, content):
        super().__init__(status_code, url, content)
        self.messages = parse_pbn_validation_details(self.json) or []

    def user_messages(self):
        """Zdeduplikowana lista czytelnych komunikatów dla użytkownika."""
        return self.messages
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/pbn_client/tests/test_pbn_validation_error.py -v`
Expected: PASS (wszystkie 9).

- [ ] **Step 5: Commit**

```bash
git add src/pbn_client/exceptions.py src/pbn_client/tests/__init__.py \
        src/pbn_client/tests/test_pbn_validation_error.py
git commit -m "feat(pbn): PBNValidationError + hostile-input-safe parser walidacji"
```

---

### Task 2: Transport podnosi `PBNValidationError` bez Rollbara

**Files:**
- Modify: `src/pbn_client/transport.py` (import na linii 17-24; `_check_error_response` na linii 167)
- Test: `src/pbn_client/tests/test_pbn_validation_error.py` (dopisać)

**Interfaces:**
- Consumes: `PBNValidationError` z Task 1.
- Produces: `_check_error_response(ret, url)` podnosi `PBNValidationError` (zamiast `HttpException`) i pomija `rollbar.report_message` dla 4xx (bez 401/403/423) rozpoznanych jako walidacja.

- [ ] **Step 1: Write the failing tests**

Dopisz do `src/pbn_client/tests/test_pbn_validation_error.py`:

```python
from pbn_api.tests.utils import MockTransport


class _FakeResponse:
    def __init__(self, status_code, content, headers=None):
        self.status_code = status_code
        self.content = content.encode() if isinstance(content, str) else content
        self.headers = headers or {}


def test_transport_validation_400_raises_pbnvalidationerror_no_rollbar(mocker):
    report = mocker.patch("pbn_client.transport.rollbar.report_message")
    t = MockTransport()
    ret = _FakeResponse(
        400,
        '{"code":400,"message":"Bad Request","description":"Validation failed.",'
        '"details":{"openAccess.releaseDate":"Data ... wymagana!"}}',
    )
    with pytest.raises(PBNValidationError) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert ei.value.user_messages() == ["Data ... wymagana!"]
    report.assert_not_called()


def test_transport_validation_409_format2_no_rollbar(mocker):
    report = mocker.patch("pbn_client.transport.rollbar.report_message")
    t = MockTransport()
    ret = _FakeResponse(
        409,
        '[{"requestPosition":0,"code":"NOT_UNIQUE_PUBLICATION_ISBN_ISMN",'
        '"description":"Publikacja o identycznym ISBN już istnieje."}]',
    )
    with pytest.raises(PBNValidationError) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert ei.value.user_messages() == [
        "Publikacja o identycznym ISBN już istnieje."
    ]
    report.assert_not_called()


def test_transport_400_without_details_is_plain_httpexception(mocker):
    report = mocker.patch("pbn_client.transport.rollbar.report_message")
    t = MockTransport()
    ret = _FakeResponse(400, '{"message":"Bad Request"}')
    with pytest.raises(HttpException) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert not isinstance(ei.value, PBNValidationError)
    report.assert_called_once()


def test_transport_500_with_details_shape_still_reports_rollbar(mocker):
    report = mocker.patch("pbn_client.transport.rollbar.report_message")
    t = MockTransport()
    ret = _FakeResponse(500, '{"details":{"x":"y"}}')
    with pytest.raises(HttpException) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert not isinstance(ei.value, PBNValidationError)
    report.assert_called_once()


@pytest.mark.parametrize("status", [401, 403, 423])
def test_transport_auth_and_locked_not_validation(mocker, status):
    report = mocker.patch("pbn_client.transport.rollbar.report_message")
    t = MockTransport()
    ret = _FakeResponse(status, '{"details":{"x":"y"}}')
    with pytest.raises(HttpException) as ei:
        t._check_error_response(ret, "/api/v1/publications")
    assert not isinstance(ei.value, PBNValidationError)
    report.assert_called_once()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/pbn_client/tests/test_pbn_validation_error.py -k transport -v`
Expected: FAIL — obecny `_check_error_response` podnosi `HttpException` (nie `PBNValidationError`) i zawsze woła `report_message`.

- [ ] **Step 3: Modify `src/pbn_client/transport.py`**

3a. Dodaj `PBNValidationError` do importu (linie 17-24):

```python
from pbn_client.exceptions import (
    AccessDeniedException,
    HttpException,
    NeedsPBNAuthorisationException,
    PBNValidationError,
    PraceSerwisoweException,
    ResourceLockedException,
)
```

3b. W `_check_error_response` (linia 167) wstaw blok detekcji PO guardzie `423 Locked`, a PRZED `logger.error(...)`:

```python
    def _check_error_response(self, ret, url):
        """Check and handle error responses."""
        if ret.status_code >= 400:
            if ret.status_code == 423 and smart_content(ret.content) == "Locked":
                raise ResourceLockedException(
                    ret.status_code, url, smart_content(ret.content)
                )

            # Błąd walidacji PBN (details / lista z code) to błąd danych
            # użytkownika, NIE problem techniczny — nie raportujemy do Rollbara,
            # podnosimy dedykowany, samo-opisujący typ. Bramka: 4xx bez
            # 401/403/423 (5xx = awaria PBN warta Rollbara; 401/403 = autoryzacja;
            # 423 = blokada zasobu).
            if 400 <= ret.status_code < 500 and ret.status_code not in (
                401,
                403,
                423,
            ):
                validation_exc = PBNValidationError(
                    ret.status_code, url, smart_content(ret.content)
                )
                if validation_exc.user_messages():
                    logger.info(
                        "PBN validation rejected %s: %s", url, validation_exc
                    )
                    raise validation_exc

            # Diagnostyka: logger.error dla widoczności w konsoli/plikach
            # logów, rollbar.report_message dla zdalnego trackingu (oba przy
            # każdym 4xx/5xx — szczegóły body i headers przydają się przy
            # debugowaniu enigmatycznych odpowiedzi typu „400 Bad Request"
            # bez body).
            logger.error(
                "PBN %s on %s: headers=%r body_len=%d body=%r",
                ret.status_code,
                url,
                dict(ret.headers),
                len(ret.content),
                ret.content[:4000],
            )
            rollbar.report_message(
                f"PBN {ret.status_code} on {url}",
                level="error" if ret.status_code >= 500 else "warning",
                extra_data={
                    "status_code": ret.status_code,
                    "url": url,
                    "headers": dict(ret.headers),
                    "body_len": len(ret.content),
                    "body": smart_content(ret.content[:4000]),
                },
            )
            raise HttpException(ret.status_code, url, smart_content(ret.content))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/pbn_client/tests/test_pbn_validation_error.py -v`
Expected: PASS (Task 1 + Task 2, razem 14).

Regresja transportu:
Run: `uv run pytest src/pbn_api/tests/test_client_extended.py -v`
Expected: PASS (bez zmian w istniejących testach).

- [ ] **Step 5: Commit**

```bash
git add src/pbn_client/transport.py src/pbn_client/tests/test_pbn_validation_error.py
git commit -m "feat(pbn): transport podnosi PBNValidationError bez raportu do Rollbara"
```

---

### Task 3: Pętle retry oświadczeń przerywają się na walidacji

**Files:**
- Modify: `src/pbn_api/client/publication_sync.py` (import linia 21-27; `_post_statements_with_retry` pętla linia 368-385)
- Modify: `src/pbn_client/statements.py` (import linia 28-33; `_delete_statements_selective` linia 313-335; `_delete_statements_batch` linia 345-364)
- Test: `src/pbn_api/tests/test_client_sync.py` (dopisać)

**Interfaces:**
- Consumes: `PBNValidationError` z Task 1.
- Produces: pętle retry oświadczeń (`_post_statements_with_retry`, `_delete_statements_selective`, `_delete_statements_batch`) re-raise'ują `PBNValidationError` natychmiast (bez ponawiania, bez `_report_statements_failure_and_raise`).

- [ ] **Step 1: Write the failing test**

Dopisz do `src/pbn_api/tests/test_client_sync.py` (plik ma już fixture `pbn_client`; jeśli brak importu — dodaj):

```python
from unittest.mock import MagicMock

from pbn_client.exceptions import PBNValidationError


@pytest.mark.django_db
def test_post_statements_with_retry_reraises_validation_immediately(
    pbn_client, mocker
):
    # Walidacja się nie naprawi przez retry — musi przerwać natychmiast.
    exc = PBNValidationError(
        400, "/api/v2/institution-profile/statements", '{"details":{"x":"y"}}'
    )
    mocker.patch.object(
        pbn_client, "_build_post_statements_payload", return_value={"stmt": 1}
    )
    post = mocker.patch.object(
        pbn_client, "post_discipline_statements", side_effect=exc
    )
    report = mocker.patch.object(
        pbn_client, "_report_statements_failure_and_raise"
    )

    with pytest.raises(PBNValidationError):
        pbn_client._post_statements_with_retry(
            rec=MagicMock(), objectId="123", publication_pk=1
        )

    assert post.call_count == 1  # brak ponawiania
    report.assert_not_called()  # nie raportuje do Rollbara


@pytest.mark.django_db
def test_delete_statements_batch_reraises_validation_immediately(
    pbn_client, mocker
):
    exc = PBNValidationError(
        400, "/api/v2/institution-profile/statements", '{"details":{"x":"y"}}'
    )
    delete = mocker.patch.object(
        pbn_client, "delete_all_publication_statements", side_effect=exc
    )
    report = mocker.patch.object(
        pbn_client, "_report_statements_failure_and_raise"
    )

    with pytest.raises(PBNValidationError):
        pbn_client._delete_statements_batch("123", publication_pk=1)

    assert delete.call_count == 1
    report.assert_not_called()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/pbn_api/tests/test_client_sync.py -k reraises_validation -v`
Expected: FAIL — obecnie `except Exception` łapie `PBNValidationError`, ponawia 3× (`call_count == 3`) i woła `_report_statements_failure_and_raise`.

- [ ] **Step 3: Add guards**

3a. `src/pbn_api/client/publication_sync.py` — dodaj `PBNValidationError` do importu (linia 21-27, lista z `HttpException`):

```python
from pbn_api.exceptions import (
    ...,
    HttpException,
    PBNValidationError,
    ...,
)
```

W `_post_statements_with_retry` (pętla linia 368) dodaj `except PBNValidationError` PRZED `except Exception`:

```python
        for attempt in range(max_tries):
            try:
                self.post_discipline_statements(body)
                return
            except PBNValidationError:
                # Walidacja się nie naprawi przez retry — przerwij natychmiast,
                # propaguj (kolejka sklasyfikuje MERYTORYCZNY, admin pokaże
                # czytelny komunikat).
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "Błąd POST oświadczeń dla %s, próba %d/%d: %s",
                    objectId,
                    attempt + 1,
                    max_tries,
                    e,
                    exc_info=True,
                )
                if attempt < max_tries - 1:
                    time.sleep(self._STATEMENT_RETRY_DELAYS[attempt])
```

3b. `src/pbn_client/statements.py` — dodaj `PBNValidationError` do importu (linia 28-33, lista z `HttpException`).

W `_delete_statements_selective` (wewnętrzna pętla linia 313), dodaj `except PBNValidationError: raise` PRZED `except Exception as e:`:

```python
            for attempt in range(max_tries):
                try:
                    self.delete_publication_statement(str(objectId), person_id, role)
                    success = True
                    break
                except PBNValidationError:
                    raise
                except Exception as e:
                    last_error = e
                    logger.warning(
                        "Błąd DELETE oświadczenia (%s, %s) dla %s, próba %d/%d: %s",
                        person_id,
                        role,
                        objectId,
                        attempt + 1,
                        max_tries,
                        e,
                        exc_info=True,
                    )
                    if attempt < max_tries - 1:
                        time.sleep(self._STATEMENT_RETRY_DELAYS[attempt])
```

W `_delete_statements_batch` (pętla linia 345) dodaj `except PBNValidationError: raise` PRZED `except Exception as e:` (po istniejącym `except CannotDeleteStatementsException: raise`):

```python
        for attempt in range(max_tries):
            try:
                self.delete_all_publication_statements(str(objectId))
                return
            except CannotDeleteStatementsException:
                raise
            except PBNValidationError:
                raise
            except Exception as e:
                last_error = e
                logger.warning(
                    "Błąd batch DELETE oświadczeń dla %s, próba %d/%d: %s",
                    objectId,
                    attempt + 1,
                    max_tries,
                    e,
                    exc_info=True,
                )
                if attempt < max_tries - 1:
                    time.sleep(self._STATEMENT_RETRY_DELAYS[attempt])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/pbn_api/tests/test_client_sync.py -k reraises_validation -v`
Expected: PASS.

Regresja synchronizacji:
Run: `uv run pytest src/pbn_api/tests/test_client_sync.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/pbn_api/client/publication_sync.py src/pbn_client/statements.py \
        src/pbn_api/tests/test_client_sync.py
git commit -m "feat(pbn): pętle retry oświadczeń przerywają się natychmiast na walidacji"
```

---

### Task 4: Handler `PBNValidationError` w ścieżce admina

**Files:**
- Modify: `src/bpp/admin/helpers/pbn_api/common.py` (import linia 8-17; nowy handler przed `except Exception` na linii 234; import `escape` na górze)
- Test: `src/pbn_api/tests/test_bpp_admin_helpers.py` (dopisać, wzorzec `test_sprobuj_wyslac_do_pbn_access_denied` linia 115)

**Interfaces:**
- Consumes: `PBNValidationError` z Task 1; fixtures `pbn_client`, `pbn_uczelnia`, `pbn_wydawnictwo_zwarte_z_charakterem`, `rf`, `middleware` (istniejące).
- Produces: `sprobuj_wyslac_do_pbn` obsługuje `PBNValidationError` — `notificator.warning` z czytelną listą, BEZ `rollbar.report_exc_info`, respektuje `raise_exceptions`.

- [ ] **Step 1: Write the failing tests**

Dopisz do `src/pbn_api/tests/test_bpp_admin_helpers.py` (dodaj import `from pbn_api.exceptions import PBNValidationError` obok istniejącego importu `AccessDeniedException`):

```python
@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_validation_error_czytelny_komunikat_bez_rollbar(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia, mocker
):
    req = rf.get("/")

    report = mocker.patch(
        "bpp.admin.helpers.pbn_api.common.rollbar.report_exc_info"
    )
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = (
        PBNValidationError(
            400,
            "/api/v1/publications",
            '{"details":{"openAccess.releaseDate":'
            '"Data udostępnienia w otwartym dostępie jest wymagana!"}}',
        )
    )

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    msg = get_messages(req)
    text = list(msg)[0].message
    assert "odrzucona przez PBN" in text
    assert "Data udostępnienia w otwartym dostępie jest wymagana!" in text
    report.assert_not_called()  # walidacja to NIE błąd kodu — bez Rollbara


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_validation_error_escapuje_html(
    pbn_wydawnictwo_zwarte_z_charakterem, pbn_client, rf, pbn_uczelnia, mocker
):
    req = rf.get("/")

    mocker.patch("bpp.admin.helpers.pbn_api.common.rollbar.report_exc_info")
    pbn_client.transport.return_values[PBN_POST_PUBLICATION_NO_STATEMENTS_URL] = (
        PBNValidationError(
            400,
            "/api/v1/publications",
            '{"details":{"x":"<script>alert(1)</script>"}}',
        )
    )

    with middleware(req):
        sprobuj_wyslac_do_pbn_gui(
            req, pbn_wydawnictwo_zwarte_z_charakterem, pbn_client=pbn_client
        )

    text = list(get_messages(req))[0].message
    assert "<script>" not in text
    assert "&lt;script&gt;" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/pbn_api/tests/test_bpp_admin_helpers.py -k validation_error -v`
Expected: FAIL — obecnie `PBNValidationError` wpada w `except Exception`: komunikat „Nie można zsynchronizować" (bez „odrzucona przez PBN") i `rollbar.report_exc_info` JEST wołany.

- [ ] **Step 3: Modify `src/bpp/admin/helpers/pbn_api/common.py`**

3a. Dodaj import `escape` na górze pliku (obok istniejących importów Django):

```python
from django.utils.html import escape
```

3b. Dodaj `PBNValidationError` do importu z `pbn_api.exceptions` (linia 8-17):

```python
from pbn_api.exceptions import (
    AccessDeniedException,
    BrakZdefiniowanegoObiektuUczelniaWSystemieError,
    CharakterFormalnyNieobslugiwanyError,
    NeedsPBNAuthorisationException,
    PBNValidationError,
    PKZeroExportDisabled,
    PraceSerwisoweException,
    ResourceLockedException,
    SameDataUploadedRecently,
)
```

3c. Dodaj handler `except PBNValidationError` BEZPOŚREDNIO PRZED `except Exception as e:` (linia 234):

```python
    except PBNValidationError as e:
        komunikaty = "".join(f"<li>{escape(m)}</li>" for m in e.user_messages())
        notificator.warning(
            f'Publikacja "{link_do_obiektu(obj)}" została odrzucona przez PBN '
            f"z powodu błędów walidacji danych: <ul>{komunikaty}</ul>"
            f"Popraw dane rekordu i spróbuj ponownie. "
            f"{open_in_pbn_link}{open_in_pi_link}"
        )
        if raise_exceptions:
            raise e

        return

    except Exception as e:
        ...  # istniejący handler bez zmian
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/pbn_api/tests/test_bpp_admin_helpers.py -k validation_error -v`
Expected: PASS.

Regresja handlerów admina:
Run: `uv run pytest src/pbn_api/tests/test_bpp_admin_helpers.py -v`
Expected: PASS (istniejące branche access_denied / inny_exception / inny_blad bez zmian).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/admin/helpers/pbn_api/common.py \
        src/pbn_api/tests/test_bpp_admin_helpers.py
git commit -m "feat(pbn): czytelny komunikat walidacji na ścieżce admina, bez Rollbara"
```

---

### Task 5: Regresja kolejki + round-trip `str()` w parserze kolejki

**Files:**
- Test: `src/pbn_export_queue/tests/test_pbn_validation_error_queue.py` (nowy)

**Interfaces:**
- Consumes: `PBNValidationError` (Task 1); `PBN_Export_Queue._handle_pbn_exception`, `RodzajBledu` (istniejące); `parse_pbn_api_error` (istniejące).
- Produces: brak nowego kodu produkcyjnego — testy potwierdzają brak regresji (klasyfikacja MERYTORYCZNY + rozpoznanie tupli).

- [ ] **Step 1: Write the tests**

Utwórz `src/pbn_export_queue/tests/test_pbn_validation_error_queue.py`:

```python
import pytest
from model_bakery import baker

from pbn_client.exceptions import PBNValidationError
from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu
from pbn_export_queue.views.utils import parse_pbn_api_error

VALIDATION_BODY = (
    '{"code":400,"message":"Bad Request","description":"Validation failed.",'
    '"details":{"openAccess.releaseDate":"Data ... wymagana!"}}'
)


@pytest.mark.django_db
def test_queue_classifies_pbnvalidationerror_as_merytoryczny():
    rec = baker.make(PBN_Export_Queue)
    exc = PBNValidationError(400, "/api/v1/publications", VALIDATION_BODY)

    rec._handle_pbn_exception(exc)

    rec.refresh_from_db()
    assert rec.rodzaj_bledu == RodzajBledu.MERYTORYCZNY


def test_queue_parser_recognizes_pbnvalidationerror_str_small_body():
    # str(exc) = tupla → parse_pbn_api_error rozpoznaje przez looks_like_tuple.
    exc = PBNValidationError(400, "/api/v1/publications", VALIDATION_BODY)
    result = parse_pbn_api_error(str(exc))
    assert result["is_pbn_api_error"] is True


def test_queue_parser_512_boundary_large_body_not_recognized():
    # A3: parse_pbn_api_error ma guard len(message_part) > 512 → bez prefiksu
    # klasy zwraca is_pbn_api_error=False. Pre-existing (dotyczy też HttpException),
    # utrwalone jako świadoma granica — nie regresja tej zmiany.
    big_details = ",".join(f'"pole{i}":"Bardzo długi komunikat walidacji {i}"'
                           for i in range(30))
    body = '{"details":{' + big_details + "}}"
    exc = PBNValidationError(400, "/api/v1/publications", body)
    result = parse_pbn_api_error(str(exc))
    assert result["is_pbn_api_error"] is False
```

- [ ] **Step 2: Run tests to verify current behavior**

Run: `uv run pytest src/pbn_export_queue/tests/test_pbn_validation_error_queue.py -v`
Expected: PASS od razu (regresja — kod produkcyjny się nie zmienia; `PBNValidationError` jako podklasa `HttpException` z `details` klasyfikuje się MERYTORYCZNY, a tuplowy `str()` jest rozpoznawany). Jeśli którykolwiek FAIL — sygnał, że wcześniejsze zadanie złamało kontrakt (np. przypadkowo nadpisany `__str__`); napraw zanim pójdziesz dalej.

- [ ] **Step 3: Commit**

```bash
git add src/pbn_export_queue/tests/test_pbn_validation_error_queue.py
git commit -m "test(pbn): regresja kolejki — PBNValidationError MERYTORYCZNY + round-trip str()"
```

---

### Task 6: Pełna suita + newsfragment

**Files:**
- Create: `src/bpp/newsfragments/+pbn-validation-error-czytelny.bugfix.md`

Towncrier trzyma newsfragmenty w `src/bpp/newsfragments/` z konwencją nazwy
`+<slug>.<typ>.md` (typy: `bugfix`, `feature`, `doc`, `removal`). Przykłady w
repo: `+fd301.bugfix.md`, `+harden-oplata-adapter.bugfix.md`.

- [ ] **Step 1: Newsfragment**

Utwórz `src/bpp/newsfragments/+pbn-validation-error-czytelny.bugfix.md`:

```
Walidacyjne odrzucenia publikacji przez PBN (np. brak daty udostępnienia w
otwartym dostępie) pokazują teraz czytelny komunikat dla redaktora zamiast
surowego JSON-a, i nie zaśmiecają Rollbara (to błąd danych, nie kodu).
```

- [ ] **Step 2: Uruchom testy dotknięte zmianą**

Run:
```bash
uv run pytest src/pbn_client/tests/ \
              src/pbn_api/tests/test_bpp_admin_helpers.py \
              src/pbn_api/tests/test_client_sync.py \
              src/pbn_api/tests/test_client_extended.py \
              src/pbn_export_queue/tests/ -v
```
Expected: PASS (wszystkie).

- [ ] **Step 3: Ruff**

Run: `ruff format src/pbn_client src/pbn_api src/bpp/admin/helpers/pbn_api && ruff check src/pbn_client src/pbn_api src/bpp/admin/helpers/pbn_api`
Expected: brak błędów (max 88 znaków). Napraw ręcznie Edit-em, jeśli coś wyskoczy — bez `--fix`.

- [ ] **Step 4: Commit**

```bash
git add src/bpp/newsfragments/+pbn-validation-error-czytelny.bugfix.md
git commit -m "docs(pbn): newsfragment — czytelny błąd walidacji PBN (#443)"
```

---

## Opcjonalny Task 7 (NIE wymagany — do decyzji przy wykonaniu): matchery kolejki rozpoznają nowy typ

Kontekst (W3): warstwa prezentacji kolejki matchuje po dosłownym stringu
`"pbn_api.exceptions"`, który po splicie modułów jest martwy dla wszystkich
`HttpException` (klasy żyją w `pbn_client.exceptions`). Nie jest to regresja
tej zmiany (opieramy się na `looks_like_tuple`), ale rozszerzenie matcherów
odblokowałoby ładne formatowanie per-pole dla nowych rekordów.

**Files:**
- Modify: `src/pbn_export_queue/views/utils.py` (`has_pbn_prefix` linia 151; `_extract_exception_line` linia ~198)
- Modify: `src/pbn_export_queue/templatetags/pbn_queue_extras.py` (`_extract_exception_line` linia ~33, `_HTTP_EXCEPTION_PATTERN` ~188)
- Test: `src/pbn_export_queue/tests/test_pbn_validation_error_queue.py` (dopisać)

Zmiana: wszędzie gdzie sprawdzane jest `"pbn_api.exceptions" in text`, zamień na
`("pbn_api.exceptions" in text or "pbn_client.exceptions" in text)`. Dodaj test,
że traceback z `pbn_client.exceptions.PBNValidationError:` jest rozpoznawany.

> Decyzja domyślna: **pomiń** (poza rdzeniem #443). Zrób tylko jeśli user
> potwierdzi, że chce przy okazji naprawić prezentację kolejki.

---

## Self-Review (wykonane przy pisaniu planu)

- **Pokrycie specu:** parser hostile-input-safe (T1/B1) ✓, transport bramka+bez Rollbara (T2/W1/D3) ✓, retry oświadczeń (T3/B2) ✓, handler admina bez Rollbar + escaping (T4/B8) ✓, regresja kolejki MERYT + str() round-trip + granica 512 (T5/K1/A3) ✓, Format 2 `description` (T1/W2) ✓, `str()` nie nadpisany (Global Constraints + T1) ✓. W3 → opcjonalny T7. B3/B4/B7/D5 → udokumentowane jako poza zakresem w specu (bez zadań).
- **Placeholdery:** brak — każdy krok ma pełny kod i komendę z oczekiwanym wynikiem.
- **Spójność typów:** `parse_pbn_validation_details`/`PBNValidationError`/`user_messages()` użyte identycznie w T2–T5; `PBN_POST_PUBLICATION_NO_STATEMENTS_URL` i fixtures zgodne z istniejącym `test_bpp_admin_helpers.py`.
