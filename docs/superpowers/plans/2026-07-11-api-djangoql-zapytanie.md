# API DjangoQL `/api/v1/zapytanie/` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wystawić silnik DjangoQL BPP jako autoryzowany, read-only endpoint REST
API dla `bpp.Rekord`, `bpp.Autor`, `bpp.Autorzy`, z kompaktowymi wynikami.

**Architecture:** Trzy per-model viewsety DRF (`GenericViewSet + ListModelMixin`)
na wspólnej bazie: wykonują `djangoql.queryset.apply_search(qs, q,
schema=RekordLLMSchema).distinct()`, gate'owane `user_can_use_query_editor`,
owinięte w `statement_timeout`. „Dwa wejścia" (Session + bearer MCP) są już
globalnym defaultem DRF — nadpisujemy tylko `permission_classes`.

**Tech Stack:** Django, DRF, django-oauth-toolkit, djangoql-iplweb, pytest,
model_bakery.

## Global Constraints

- Python >=3.10,<3.15. Max line length: 88 (ruff).
- **ALWAYS `uv run`** prefix dla komend Pythona. Testy: `uv run pytest`.
- NIE modyfikować istniejących migracji. Ta funkcja **nie zmienia schematu
  bazy** → bez `makemigrations`, bez odświeżania baseline.
- Testy: pytest-only (funkcje, bez `unittest.TestCase`), `@pytest.mark.django_db`,
  `model_bakery.baker` do fixtur.
- NIGDY bare `except:` / `except Exception: pass`.
- Newsfragment towncrier w `changes/newsfragments/` (format `+slug.feature.rst`).
- Schemat walidacji: **`RekordLLMSchema`** (`bpp.djangoql_schema`), nie goły
  `BppQLSchema`.
- Gałąź: `feat-api-zapytanie` (już utworzona od `dev`).

---

### Task 1: Wydziel helpery błędów DjangoQL do współdzielonego modułu

Widok web `bpp/views/zapytanie.py` ma prywatne `_format_error_text`,
`_locate_token`, `_error_location`, `_error_payload`. API potrzebuje ich też —
DRY: przenosimy do `bpp/djangoql_errors.py`, widok importuje. Istniejące testy
`src/bpp/tests/test_zapytanie.py` są siatką bezpieczeństwa.

**Files:**
- Create: `src/bpp/djangoql_errors.py`
- Modify: `src/bpp/views/zapytanie.py` (usuń 4 lokalne funkcje, dodaj import-aliasy)

**Interfaces:**
- Produces: `format_error_text(exc) -> str`, `locate_token(query, needle) ->
  tuple|None`, `error_location(exc, query) -> (line, column, mark)`,
  `error_payload(exc, query) -> dict`.

- [ ] **Step 1: Utwórz `src/bpp/djangoql_errors.py`** (przeniesione ciało, nazwy publiczne)

```python
"""Wspólne mapowanie wyjątków DjangoQL na payload JSON z lokalizacją błędu.

Trzon dzielony przez web-owy edytor „Szukaj zapytaniem" (``bpp.views.zapytanie``)
i API DjangoQL (``api_v1.viewsets.zapytanie``). Most między wyjątkami Pythona a
czerwoną falką nakładki ``highlight.js`` (idiom z ``djangoql/example_project``).
"""

import re

from django.core.exceptions import ValidationError


def format_error_text(exc):
    """Czytelny komunikat błędu zapytania (łączy komunikaty ValidationError)."""
    if isinstance(exc, ValidationError):
        return "; ".join(exc.messages)
    return str(exc)


def locate_token(query, needle):
    """1-based ``(line, column)`` wystąpienia ``needle`` w ``query`` albo None."""
    match = re.search(r"(?<![\w.])" + re.escape(needle) + r"(?![\w])", query)
    pos = match.start() if match else query.find(needle)
    if pos < 0:
        return None
    line = query.count("\n", 0, pos) + 1
    column = pos - query.rfind("\n", 0, pos)
    return line, column


def error_location(exc, query):
    """``(line, column, mark)`` wskazujące miejsce błędu, albo ``(None,)*3``."""
    line = getattr(exc, "line", None)
    column = getattr(exc, "column", None)
    if line and column:
        return line, column, "to_end"
    value = getattr(exc, "value", None)
    if value:
        loc = locate_token(query, str(value))
        if loc:
            return loc[0], loc[1], "token"
    return None, None, None


def error_payload(exc, query):
    """Słownik odpowiedzi JSON błędu: ``{error[, line, column, mark]}``."""
    payload = {"error": format_error_text(exc)}
    line, column, mark = error_location(exc, query)
    if line and column:
        payload.update(line=line, column=column, mark=mark)
    return payload
```

- [ ] **Step 2: Przełącz `zapytanie.py` na import z nowego modułu**

W `src/bpp/views/zapytanie.py` USUŃ definicje `_format_error_text`,
`_locate_token`, `_error_location`, `_error_payload` (oraz teraz-zbędny
`import re`, jeśli nieużywany gdzie indziej — sprawdź: `re` jest używane tylko w
`_locate_token`, więc usuń jego import). Dodaj po istniejących importach:

```python
from bpp.djangoql_errors import (
    error_location as _error_location,
    error_payload as _error_payload,
    format_error_text as _format_error_text,
)
```

Aliasy zachowują wszystkie istniejące wywołania (`_error_payload`,
`_error_location`, `_format_error_text`) bez zmian.

- [ ] **Step 3: Uruchom testy web-widoku (regresja)**

Run: `uv run pytest src/bpp/tests/test_zapytanie.py -q`
Expected: PASS (bez zmian zachowania).

- [ ] **Step 4: Ruff**

Run: `uv run ruff check src/bpp/djangoql_errors.py src/bpp/views/zapytanie.py && uv run ruff format --check src/bpp/djangoql_errors.py`
Expected: brak błędów. (Jeśli format zgłosi — `uv run ruff format` na tych plikach.)

- [ ] **Step 5: Commit**

```bash
git add src/bpp/djangoql_errors.py src/bpp/views/zapytanie.py
git commit -m "refactor(djangoql): wydziel helpery błędów do bpp.djangoql_errors"
```

---

### Task 2: Współdzielony context manager `statement_timeout`

Guardrail: patologiczne DjangoQL ma ubić własny request (503), nie męczyć bazę.
Wzorzec z `powiazania_autorow/queries.py::_limit_czasu`, ale jako publiczny util.

**Files:**
- Create: `src/bpp/util/statement_timeout.py`
- Test: `src/bpp/tests/test_statement_timeout.py`

**Interfaces:**
- Produces: `statement_timeout(ms: int)` — context manager; wewnątrz ustawia
  `SET LOCAL statement_timeout = ms` w `transaction.atomic`. Przekroczenie →
  `django.db.utils.OperationalError`.

- [ ] **Step 1: Napisz failing test**

```python
import pytest
from django.db import connection
from django.db.utils import OperationalError

from bpp.util.statement_timeout import statement_timeout


@pytest.mark.django_db(transaction=False)
def test_statement_timeout_ubija_dlugie_zapytanie():
    with pytest.raises(OperationalError):
        with statement_timeout(50):  # 50 ms
            with connection.cursor() as c:
                c.execute("SELECT pg_sleep(1)")  # 1 s > 50 ms


@pytest.mark.django_db(transaction=False)
def test_statement_timeout_przepuszcza_szybkie_zapytanie():
    with statement_timeout(5000):
        with connection.cursor() as c:
            c.execute("SELECT 1")
            assert c.fetchone()[0] == 1
```

- [ ] **Step 2: Uruchom — ma failować (ModuleNotFound)**

Run: `uv run pytest src/bpp/tests/test_statement_timeout.py -q`
Expected: FAIL (`ModuleNotFoundError: bpp.util.statement_timeout`).

- [ ] **Step 3: Implementacja**

```python
"""Ogranicznik czasu pojedynczego zapytania (Postgres ``statement_timeout``).

``SET LOCAL`` żyje tylko w obrębie transakcji — całość owijamy w
``transaction.atomic()``, więc po wyjściu limit znika. Przekroczenie →
``OperationalError`` (łapane wyżej, np. zwracamy 503).
"""

from contextlib import contextmanager

from django.db import connection, transaction


@contextmanager
def statement_timeout(ms):
    with transaction.atomic():
        with connection.cursor() as c:
            c.execute("SET LOCAL statement_timeout = %s", [ms])
        yield
```

- [ ] **Step 4: Testy przechodzą**

Run: `uv run pytest src/bpp/tests/test_statement_timeout.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/util/statement_timeout.py src/bpp/tests/test_statement_timeout.py
git commit -m "feat(util): statement_timeout — context manager SET LOCAL"
```

---

### Task 3: Permission `MoznaUzywacZapytania`

Gate API = ten sam predykat co web-edytor: `user_can_use_query_editor`.

**Files:**
- Create: `src/api_v1/permissions.py`
- Test: `src/api_v1/tests/test_zapytanie_api.py` (start pliku)

**Interfaces:**
- Consumes: `bpp.views.zapytanie.user_can_use_query_editor(user) -> bool`.
- Produces: `MoznaUzywacZapytania` (DRF `BasePermission`); `has_permission`
  zwraca `user_can_use_query_editor(request.user)`.

- [ ] **Step 1: Napisz failing test**

```python
import pytest
from django.contrib.auth.models import AnonymousUser
from model_bakery import baker

from api_v1.permissions import MoznaUzywacZapytania
from bpp.const import GR_WPROWADZANIE_DANYCH


class _FakeRequest:
    def __init__(self, user):
        self.user = user


@pytest.mark.django_db
def test_gate_anon_odrzucony():
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(AnonymousUser()), None) is False


@pytest.mark.django_db
def test_gate_superuser_przechodzi():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is True


@pytest.mark.django_db
def test_gate_staff_w_grupie_przechodzi():
    from django.contrib.auth.models import Group

    u = baker.make("bpp.BppUser", is_staff=True, is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grupa)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is True


@pytest.mark.django_db
def test_gate_zwykly_zalogowany_odrzucony():
    u = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    assert MoznaUzywacZapytania().has_permission(_FakeRequest(u), None) is False
```

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py -q`
Expected: FAIL (`ModuleNotFoundError: api_v1.permissions`).

- [ ] **Step 3: Implementacja**

```python
from rest_framework.permissions import BasePermission

from bpp.views.zapytanie import user_can_use_query_editor


class MoznaUzywacZapytania(BasePermission):
    """Dostęp do DjangoQL po API = ten sam kontrakt co web-edytor:
    superuser albo staff w grupie „wprowadzanie danych"."""

    message = (
        "Wymagane konto redaktora (staff w grupie „wprowadzanie danych") "
        "lub superusera."
    )

    def has_permission(self, request, view):
        return user_can_use_query_editor(request.user)
```

- [ ] **Step 4: Testy przechodzą**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/api_v1/permissions.py src/api_v1/tests/test_zapytanie_api.py
git commit -m "feat(api_v1): permission MoznaUzywacZapytania (gate edytora zapytań)"
```

---

### Task 4: Kompaktowe serializery Autor i Autorzy

Płaskie projekcje (relacje jako string+URL). Rekord reuse `SzukajSerializer`
(bez nowego kodu). Tu Autor + Autorzy.

**Files:**
- Create: `src/api_v1/serializers/zapytanie.py`
- Test: `src/api_v1/tests/test_zapytanie_serializers.py`

**Interfaces:**
- Consumes: `api_v1.viewsets.szukaj.MODELE_DETAIL_VIEWNAME` (mapa model→viewname
  detalu), kontekst `request` + `contenttype_to_viewname` (jak w `SzukajViewSet`).
- Produces: `AutorKompaktSerializer`, `AutorzyKompaktSerializer`.

- [ ] **Step 1: Napisz failing test**

```python
import pytest
from model_bakery import baker
from rest_framework.test import APIRequestFactory

from api_v1.serializers.zapytanie import (
    AutorKompaktSerializer,
    AutorzyKompaktSerializer,
)


@pytest.mark.django_db
def test_autor_kompakt_ma_plaskie_pola():
    tytul = baker.make("bpp.Tytul", skrot="prof.")
    jedn = baker.make("bpp.Jednostka", nazwa="Kardiologii")
    autor = baker.make(
        "bpp.Autor", nazwisko="Kowalski", imiona="Jan", tytul=tytul,
        aktualna_jednostka=jedn, orcid="0000-0001",
    )
    req = APIRequestFactory().get("/")
    data = AutorKompaktSerializer(autor, context={"request": req}).data
    assert data["nazwisko"] == "Kowalski"
    assert data["tytul"] == "prof."
    assert data["aktualna_jednostka"] == "Kardiologii"
    assert data["orcid"] == "0000-0001"
    assert data["autor_url"].endswith(f"/autor/{autor.pk}/")
    assert isinstance(data["absolute_url"], str)


@pytest.mark.django_db
def test_autor_kompakt_bez_tytulu_i_jednostki():
    autor = baker.make("bpp.Autor", nazwisko="Nowak", tytul=None,
                       aktualna_jednostka=None)
    req = APIRequestFactory().get("/")
    data = AutorKompaktSerializer(autor, context={"request": req}).data
    assert data["tytul"] == ""
    assert data["aktualna_jednostka"] is None
```

(Uwaga: `Autorzy` to mat-view `managed=False` — testu serializera Autorzy nie
budujemy `baker.make` bezpośrednio; pokrycie Autorzy idzie przez test
end-to-end viewsetu w Tasku 6, gdzie mat-view zostaje wypełniony przez realny
rekord+autora. Tutaj serializer Autorzy tylko implementujemy.)

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_serializers.py -q`
Expected: FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implementacja**

```python
"""Kompaktowe, płaskie projekcje wyników DjangoQL po API.

Rekord reuse ``SzukajSerializer`` (Faza 0). Tu Autor i Autorzy — relacje jako
string (etykieta) + URL do detalu API, bez chodzenia po hyperlinkach.
"""

from django.urls import reverse
from rest_framework import serializers

from api_v1.viewsets.szukaj import MODELE_DETAIL_VIEWNAME


class AutorKompaktSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    nazwisko = serializers.CharField()
    imiona = serializers.CharField()
    tytul = serializers.SerializerMethodField()
    orcid = serializers.CharField()
    aktualna_jednostka = serializers.SerializerMethodField()
    autor_url = serializers.SerializerMethodField()
    absolute_url = serializers.SerializerMethodField()

    def get_tytul(self, obj):
        return obj.tytul.skrot if obj.tytul_id else ""

    def get_aktualna_jednostka(self, obj):
        return obj.aktualna_jednostka.nazwa if obj.aktualna_jednostka_id else None

    def get_autor_url(self, obj):
        request = self.context["request"]
        return request.build_absolute_uri(
            reverse("api_v1:autor-detail", args=[obj.pk])
        )

    def get_absolute_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())


class AutorzyKompaktSerializer(serializers.Serializer):
    """Wpis autorstwa (autor-na-rekordzie). ``id`` = TupleField ``"<ct>-<pk>"``."""

    id = serializers.SerializerMethodField()
    zapisany_jako = serializers.CharField()
    kolejnosc = serializers.IntegerField()
    autor_url = serializers.SerializerMethodField()
    rekord = serializers.SerializerMethodField()
    typ_odpowiedzialnosci = serializers.SerializerMethodField()
    jednostka = serializers.SerializerMethodField()
    dyscyplina = serializers.SerializerMethodField()

    def get_id(self, obj):
        return f"{obj.id[0]}-{obj.id[1]}"

    def get_autor_url(self, obj):
        request = self.context["request"]
        return request.build_absolute_uri(
            reverse("api_v1:autor-detail", args=[obj.autor_id])
        )

    def get_rekord(self, obj):
        request = self.context["request"]
        rek = obj.rekord
        viewname = self.context["contenttype_to_viewname"].get(rek.id[0])
        rekord_url = None
        if viewname is not None:
            rekord_url = request.build_absolute_uri(
                reverse(viewname, args=(rek.id[1],))
            )
        return {"tytul": rek.tytul_oryginalny, "rekord_url": rekord_url}

    def get_typ_odpowiedzialnosci(self, obj):
        return obj.typ_odpowiedzialnosci.skrot if obj.typ_odpowiedzialnosci_id else None

    def get_jednostka(self, obj):
        return obj.jednostka.nazwa if obj.jednostka_id else None

    def get_dyscyplina(self, obj):
        return obj.dyscyplina_naukowa.nazwa if obj.dyscyplina_naukowa_id else None
```

- [ ] **Step 4: Testy Autora przechodzą**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_serializers.py -q`
Expected: PASS (2 passed).

- [ ] **Step 5: Ruff + commit**

```bash
uv run ruff check src/api_v1/serializers/zapytanie.py
git add src/api_v1/serializers/zapytanie.py src/api_v1/tests/test_zapytanie_serializers.py
git commit -m "feat(api_v1): kompaktowe serializery Autor/Autorzy dla /zapytanie/"
```

---

### Task 5: Bazowy viewset + endpoint `zapytanie/rekord/` + rejestracja URL

Serce: `apply_search` + gate + błędy 400 + puste `q`. Timeout dokładamy w Tasku 7.

**Files:**
- Create: `src/api_v1/viewsets/zapytanie.py`
- Modify: `src/api_v1/urls.py` (import + 3 rejestracje — na razie tylko rekord aktywny; autor/autorzy w Tasku 6, ale rejestrujemy komplet od razu jest ryzykowne bez viewsetów — więc rejestruj TYLKO rekord tutaj)
- Test: `src/api_v1/tests/test_zapytanie_api.py` (dopisz)

**Interfaces:**
- Consumes: `bpp.djangoql_errors.error_payload`, `MoznaUzywacZapytania`,
  `bpp.djangoql_schema.RekordLLMSchema`, `SzukajSerializer` +
  `MODELE_DETAIL_VIEWNAME` (kontekst contenttype→viewname), `apply_search`.
- Produces: `ZapytanieAPIBaseViewSet` (atrybuty: `model`, `serializer_class`;
  `get_queryset`, `get_serializer_context`, `list`), `ZapytanieRekordViewSet`.

- [ ] **Step 1: Napisz failing testy endpointu Rekord**

```python
# dopisz do src/api_v1/tests/test_zapytanie_api.py
from django.contrib.auth.models import Group
from model_bakery import baker
from rest_framework.test import APIClient

from bpp.const import GR_WPROWADZANIE_DANYCH


def _staff_client():
    u = baker.make("bpp.BppUser", is_staff=True, is_superuser=True)
    c = APIClient()
    c.force_authenticate(user=u)
    return c


@pytest.mark.django_db
def test_zapytanie_rekord_anon_403():
    resp = APIClient().get("/api/v1/zapytanie/rekord/", {"q": "rok = 2024"})
    assert resp.status_code in (401, 403)


@pytest.mark.django_db
def test_zapytanie_rekord_puste_q_zwraca_pusto():
    resp = _staff_client().get("/api/v1/zapytanie/rekord/", {"q": ""})
    assert resp.status_code == 200
    assert resp.data["results"] == []


@pytest.mark.django_db
def test_zapytanie_rekord_bledne_q_400():
    resp = _staff_client().get(
        "/api/v1/zapytanie/rekord/", {"q": "nieistniejace_pole = 1"}
    )
    assert resp.status_code == 400
    assert "error" in resp.data
```

- [ ] **Step 2: Uruchom — ma failować (404, brak endpointu)**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py -q -k rekord`
Expected: FAIL (404 zamiast 200/400/403).

- [ ] **Step 3: Implementuj bazowy viewset + Rekord**

`src/api_v1/viewsets/zapytanie.py`:

```python
"""Autoryzowane wyszukiwanie DjangoQL po API — ``GET /api/v1/zapytanie/<model>/``.

Wystawia istniejący silnik ``apply_search`` (schemat ``RekordLLMSchema``) w
warstwie DRF, read-only, gate'owane ``MoznaUzywacZapytania``. Kształt wyników:
kompaktowa płaska projekcja per model.
"""

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import FieldError, ValidationError
from djangoql.exceptions import DjangoQLError
from djangoql.queryset import apply_search
from rest_framework import mixins, viewsets
from rest_framework.response import Response

from api_v1.permissions import MoznaUzywacZapytania
from api_v1.serializers.szukaj import SzukajSerializer
from api_v1.viewsets.szukaj import MODELE_DETAIL_VIEWNAME
from bpp.djangoql_errors import error_payload
from bpp.djangoql_schema import RekordLLMSchema
from bpp.models.cache import Rekord

#: Twardy cap paginacji — jedno żądanie nie ciągnie całej bazy.
MAKS_LIMIT = 100


class ZapytanieAPIBaseViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Baza: wykonuje DjangoQL, mapuje błędy na 400. Podklasa ustawia
    ``model`` i ``serializer_class``."""

    permission_classes = [MoznaUzywacZapytania]
    model = None

    def _q(self):
        return (self.request.query_params.get("q") or "").strip()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["contenttype_to_viewname"] = {
            ContentType.objects.get_for_model(m).pk: v
            for m, v in MODELE_DETAIL_VIEWNAME.items()
        }
        return context

    def get_queryset(self):
        q = self._q()
        qs = self.model.objects.all()
        if not q:
            return qs.none()
        # apply_search jest leniwe — DjangoQLError poleci dopiero na parsie
        # (tu), FieldError/ValidationError przy ewaluacji (w list()).
        return apply_search(qs, q, schema=RekordLLMSchema).distinct()

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
            return Response(error_payload(exc, self._q()), status=400)


class ZapytanieRekordViewSet(ZapytanieAPIBaseViewSet):
    model = Rekord
    serializer_class = SzukajSerializer
```

- [ ] **Step 4: Zarejestruj URL rekord**

W `src/api_v1/urls.py` dodaj import:

```python
from api_v1.viewsets.zapytanie import ZapytanieRekordViewSet
```

i rejestrację (obok `szukaj`):

```python
router.register(r"zapytanie/rekord", ZapytanieRekordViewSet, basename="zapytanie_rekord")
```

- [ ] **Step 5: Testy Rekord przechodzą**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py -q -k rekord`
Expected: PASS (3 passed).

- [ ] **Step 6: Ruff + commit**

```bash
uv run ruff check src/api_v1/viewsets/zapytanie.py src/api_v1/urls.py
git add src/api_v1/viewsets/zapytanie.py src/api_v1/urls.py src/api_v1/tests/test_zapytanie_api.py
git commit -m "feat(api_v1): endpoint /zapytanie/rekord/ (DjangoQL, gate, 400 na błąd)"
```

---

### Task 6: Endpointy `zapytanie/autor/` i `zapytanie/autorzy/`

**Files:**
- Modify: `src/api_v1/viewsets/zapytanie.py` (2 podklasy)
- Modify: `src/api_v1/urls.py` (2 rejestracje)
- Test: `src/api_v1/tests/test_zapytanie_api.py` (dopisz)

**Interfaces:**
- Consumes: `AutorKompaktSerializer`, `AutorzyKompaktSerializer`, `Autor`,
  `Autorzy`.
- Produces: `ZapytanieAutorViewSet`, `ZapytanieAutorzyViewSet`.

- [ ] **Step 1: Napisz failing testy (happy path per model, w tym round-trip Autorzy z mat-view)**

Wzorzec z Fazy 0 (`test_szukaj.py::piec_typow`): mat-view `bpp_rekord_mat`/
`bpp_autorzy_mat` wypełnia się przez realny rekord + `dodaj_autora` + jawne
`Rekord.objects.full_refresh()`. `Autor` to zwykła tabela → dla niego wystarczy
`baker.make` bez refresh.

```python
@pytest.mark.django_db
def test_zapytanie_autor_happy():
    baker.make("bpp.Autor", nazwisko="Kowalski")
    resp = _staff_client().get("/api/v1/zapytanie/autor/", {"q": 'nazwisko ~ "Kowal"'})
    assert resp.status_code == 200
    assert any(r["nazwisko"] == "Kowalski" for r in resp.data["results"])


@pytest.mark.django_db
def test_zapytanie_autorzy_happy(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
):
    wydawnictwo_ciagle.rok = 2023
    wydawnictwo_ciagle.tytul_oryginalny = "Praca X"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    from bpp.models import Rekord

    Rekord.objects.full_refresh()

    resp = _staff_client().get("/api/v1/zapytanie/autorzy/", {"q": "rekord.rok = 2023"})
    assert resp.status_code == 200
    assert len(resp.data["results"]) >= 1
    wpis = resp.data["results"][0]
    assert "zapisany_jako" in wpis and "rekord" in wpis
    assert wpis["rekord"]["rekord_url"] is not None
```

- [ ] **Step 2: Uruchom — ma failować (404)**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py -q -k "autor"`
Expected: FAIL (404).

- [ ] **Step 3: Dodaj podklasy viewsetów**

W `src/api_v1/viewsets/zapytanie.py` dopisz importy i klasy:

```python
from api_v1.serializers.zapytanie import (
    AutorKompaktSerializer,
    AutorzyKompaktSerializer,
)
from bpp.models import Autor
from bpp.models.cache import Autorzy
```

```python
class ZapytanieAutorViewSet(ZapytanieAPIBaseViewSet):
    model = Autor
    serializer_class = AutorKompaktSerializer


class ZapytanieAutorzyViewSet(ZapytanieAPIBaseViewSet):
    model = Autorzy
    serializer_class = AutorzyKompaktSerializer
```

- [ ] **Step 4: Zarejestruj URL-e**

W `src/api_v1/urls.py` rozszerz import:

```python
from api_v1.viewsets.zapytanie import (
    ZapytanieAutorViewSet,
    ZapytanieAutorzyViewSet,
    ZapytanieRekordViewSet,
)
```

i dodaj rejestracje:

```python
router.register(r"zapytanie/autor", ZapytanieAutorViewSet, basename="zapytanie_autor")
router.register(r"zapytanie/autorzy", ZapytanieAutorzyViewSet, basename="zapytanie_autorzy")
```

- [ ] **Step 5: Testy przechodzą**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py -q`
Expected: PASS (wszystkie).

- [ ] **Step 6: Ruff + commit**

```bash
uv run ruff check src/api_v1/viewsets/zapytanie.py src/api_v1/urls.py
git add src/api_v1/viewsets/zapytanie.py src/api_v1/urls.py src/api_v1/tests/test_zapytanie_api.py
git commit -m "feat(api_v1): endpointy /zapytanie/autor/ i /zapytanie/autorzy/"
```

---

### Task 7: Guardrail `statement_timeout` + cap paginacji + 503

**Files:**
- Modify: `src/api_v1/viewsets/zapytanie.py` (owiń `list` w timeout, dołóż
  paginację z capem)
- Test: `src/api_v1/tests/test_zapytanie_api.py` (dopisz)

**Interfaces:**
- Consumes: `bpp.util.statement_timeout.statement_timeout`.

- [ ] **Step 1: Napisz failing testy (cap limitu + 503)**

```python
from unittest import mock


@pytest.mark.django_db
def test_zapytanie_limit_ma_twardy_cap():
    from api_v1.viewsets.zapytanie import ZapytanieRekordViewSet

    v = ZapytanieRekordViewSet()
    assert v.paginator.max_limit == 100


@pytest.mark.django_db
def test_zapytanie_timeout_daje_503():
    from django.db.utils import OperationalError

    with mock.patch(
        "api_v1.viewsets.zapytanie.ZapytanieAPIBaseViewSet.get_queryset",
        side_effect=OperationalError("canceling statement due to statement timeout"),
    ):
        resp = _staff_client().get("/api/v1/zapytanie/rekord/", {"q": "rok = 2024"})
    assert resp.status_code == 503
    assert "error" in resp.data
```

- [ ] **Step 2: Uruchom — ma failować**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py -q -k "cap or 503 or timeout"`
Expected: FAIL (brak max_limit=100 / brak 503).

- [ ] **Step 3: Dołóż paginację z capem + owiń list w timeout**

W `src/api_v1/viewsets/zapytanie.py` dodaj importy:

```python
from django.db.utils import OperationalError
from rest_framework.pagination import LimitOffsetPagination

from bpp.util.statement_timeout import statement_timeout
```

Dodaj klasę paginacji i wepnij do bazy; zaktualizuj `list`:

```python
#: Twardy statement_timeout dla DjangoQL po API (ms).
ZAPYTANIE_TIMEOUT_MS = 8000


class _ZapytaniePagination(LimitOffsetPagination):
    max_limit = MAKS_LIMIT
```

W `ZapytanieAPIBaseViewSet` ustaw `pagination_class = _ZapytaniePagination` i
zamień `list` na:

```python
    pagination_class = _ZapytaniePagination

    def list(self, request, *args, **kwargs):
        try:
            with statement_timeout(ZAPYTANIE_TIMEOUT_MS):
                return super().list(request, *args, **kwargs)
        except (DjangoQLError, FieldError, ValidationError, ValueError) as exc:
            return Response(error_payload(exc, self._q()), status=400)
        except OperationalError:
            return Response(
                {"error": "Zapytanie trwało za długo — zawęź warunki."},
                status=503,
            )
```

Uwaga: `statement_timeout` owija CAŁE `super().list()` (count + slice +
serializacja), więc limit obejmuje wszystkie zapytania SQL requestu, nie tylko
leniwe `apply_search`.

- [ ] **Step 4: Testy przechodzą**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py -q`
Expected: PASS (wszystkie).

- [ ] **Step 5: Ruff + commit**

```bash
uv run ruff check src/api_v1/viewsets/zapytanie.py
git add src/api_v1/viewsets/zapytanie.py src/api_v1/tests/test_zapytanie_api.py
git commit -m "feat(api_v1): statement_timeout 8s → 503 + cap limitu 100 dla /zapytanie/"
```

---

### Task 8: Newsfragment + pełny przebieg testów + weryfikacja

**Files:**
- Create: `changes/newsfragments/+api-zapytanie-djangoql.feature.rst`

- [ ] **Step 1: Newsfragment**

`changes/newsfragments/+api-zapytanie-djangoql.feature.rst`:

```rst
Dodano autoryzowane wyszukiwanie DjangoQL po API: ``GET /api/v1/zapytanie/rekord/``,
``/zapytanie/autor/`` i ``/zapytanie/autorzy/`` (parametr ``q``), dostępne dla
zalogowanych redaktorów (staff w grupie „wprowadzanie danych") oraz przez token
MCP. Wyniki kompaktowe, stronicowane, read-only.
```

- [ ] **Step 2: Pełny przebieg testów DjangoQL-API + regresja web-widoku**

Run: `uv run pytest src/api_v1/tests/test_zapytanie_api.py src/api_v1/tests/test_zapytanie_serializers.py src/bpp/tests/test_zapytanie.py src/bpp/tests/test_statement_timeout.py -q`
Expected: PASS (wszystko).

- [ ] **Step 3: Cała sucha api_v1 (nic nie rozjechaliśmy)**

Run: `uv run pytest src/api_v1/ -q`
Expected: PASS.

- [ ] **Step 4: Pre-commit na zmienionych plikach**

Run: `uv run ruff check src/api_v1 src/bpp/djangoql_errors.py src/bpp/util/statement_timeout.py && uv run ruff format --check src/api_v1/viewsets/zapytanie.py src/api_v1/serializers/zapytanie.py`
Expected: brak błędów.

- [ ] **Step 5: Commit**

```bash
git add changes/newsfragments/+api-zapytanie-djangoql.feature.rst
git commit -m "docs(newsfragment): API DjangoQL /api/v1/zapytanie/"
```

---

## Otwarte punkty przeniesione ze specu (świadomie POZA tym planem)

- **Multi-uczelnia scoping** dla Rekord — v1 NIE zawęża (narzędzie redakcyjne,
  staff), zgodnie ze wstępną decyzją spec §8. Follow-up jeśli zajdzie potrzeba.
- **Throttling** — pominięty (reszta `api_v1` nie throttluje); follow-up.
- **„Nauczony" compact-schemat dla Autor/Autorzy** — dziś generujemy tylko dla
  Rekord; round-trip pełny dla Rekord, dla Autor/Autorzy endpoint działa, ale
  agent nie ma opisu pól. Osobny follow-up (rozszerzyć
  `opisz_schemat_djangoql_dla_llm`).
- **`doi` w projekcji Rekord** — `Rekord` (mat-view) nie ma kolumny `doi`;
  pominięte w v1 (reuse `SzukajSerializer` bez zmian).
- **Endpoint `/schema/`** self-describing — poza v1.
