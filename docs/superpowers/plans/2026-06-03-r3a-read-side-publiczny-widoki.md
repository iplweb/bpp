# R3a — read-side publiczny (widoki Rekord/Sumy) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zawęzić pięć publicznych widoków czytających `Rekord`/`Sumy` do uczelni oglądającego (domena→Site→Uczelnia), bez regresji na single-install.

**Architecture:** Jeden współdzielony helper `scope_rekord_do_uczelni(qs, uczelnia)` z guardem `tylko_jedna_uczelnia()` (short-circuit single-install, pomija kosztowny JOIN+DISTINCT). Reguła rekordowa = strona główna (`autorzy__jednostka__uczelnia`, bez `skupia_pracownikow`). Ranking osobno (lookup `autor__aktualna_jednostka__uczelnia`, ten sam guard).

**Tech Stack:** Django, pytest + model_bakery, testcontainers (PG/Redis), `uv run`.

Spec: `docs/superpowers/specs/2026-06-03-r3a-read-side-publiczny-widoki-design.md`.

## Infrastruktura testowa (KLUCZOWE — czytaj przed Taskiem 1)

Multi-site fixtury są zarejestrowane jako pytest plugin (`src/conftest.py` →
`pytest_plugins = [... "fixtures.conftest_multisite"]`), więc dostępne wszędzie.
Plik: `src/fixtures/conftest_multisite.py`. Używaj ich zamiast ręcznego setupu:

- `uczelnia1`/`uczelnia2` — Uczelnie powiązane z `site1`/`site2` (FK `site`).
- `wydzial_uczelnia1/2`, `jednostka_uczelnia1/2` — struktura per uczelnia
  (jednostki mają `uczelnia=...`; **NIE** mają `skupia_pracownikow` ustawionego
  jawnie — domyślna wartość modelu; reguła rekordowa i tak go nie wymaga).
- `autor_uczelnia1/2` — autorzy z `aktualna_jednostka=jednostka_uczelniaN`
  ORAZ wpisem `Autor_Jednostka` (historia) w tej jednostce.
- `make_request_for_site(site, path="/", user=None)` — tworzy `RequestFactory`
  request z `HTTP_HOST=site.domain` i **odpala `SiteResolutionMiddleware`**, więc
  `request._uczelnia` jest ustawione. To deterministyczny szew: `get_for_request`
  zwróci uczelnię tego site (bez zależności od `SITE_ID`/ALLOWED_HOSTS).

Wzorzec testu widoku (queryset bez HTTP):
```python
view = LataView()
view.request = make_request_for_site(site1)
view.kwargs = {}
result = view.get_queryset()
```
Tworzenie pracy w jednostce: `wc = baker.make("bpp.Wydawnictwo_Ciagle", rok=2020); wc.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)`.
`Rekord` to widok SQL — odzwierciedla pracę natychmiast (brak rebuildu).

**Reguły wykonawcze (per HANDOFF):**
- Testy: `uv run pytest <ścieżka> -q -p no:cacheprovider` (Docker musi działać).
- Guard get_default: `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q` po każdym tasku.
- Lint: `uv run ruff check <pliki>` (NIE `--fix`).
- Commit po każdym tasku. Push dopiero na prośbę usera.

---

### Task 1: Helper `scope_rekord_do_uczelni` + guard `tylko_jedna_uczelnia`

**Files:**
- Create: `src/bpp/util/uczelnia_scope.py`
- Create: `src/bpp/tests/test_util/__init__.py` (jeśli brak)
- Test: `src/bpp/tests/test_util/test_uczelnia_scope.py`

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_util/test_uczelnia_scope.py
import pytest
from model_bakery import baker

from bpp.models import Rekord
from bpp.util.uczelnia_scope import scope_rekord_do_uczelni, tylko_jedna_uczelnia


@pytest.mark.django_db
def test_tylko_jedna_uczelnia_true_dla_jednej(uczelnia1):
    assert tylko_jedna_uczelnia() is True


@pytest.mark.django_db
def test_tylko_jedna_uczelnia_false_dla_dwoch(uczelnia1, uczelnia2):
    assert tylko_jedna_uczelnia() is False


@pytest.mark.django_db
def test_scope_none_uczelnia_zwraca_qs_bez_zmian(uczelnia1):
    qs = Rekord.objects.all()
    assert scope_rekord_do_uczelni(qs, None) is qs


@pytest.mark.django_db
def test_scope_single_install_short_circuit(uczelnia1):
    # jedna uczelnia => guard zwraca ten sam obiekt qs (brak JOIN)
    qs = Rekord.objects.all()
    assert scope_rekord_do_uczelni(qs, uczelnia1) is qs


@pytest.mark.django_db
def test_scope_dwie_uczelnie_filtruje(
    uczelnia1, uczelnia2, jednostka_uczelnia1, jednostka_uczelnia2,
    autor_uczelnia1, autor_uczelnia2,
):
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="MOJA")
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="OBCA")
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)

    tytuly = set(
        scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia1).values_list(
            "tytul_oryginalny", flat=True
        )
    )
    assert "MOJA" in tytuly
    assert "OBCA" not in tytuly
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_util/test_uczelnia_scope.py -q -p no:cacheprovider`
Expected: FAIL (ModuleNotFoundError: `bpp.util.uczelnia_scope`)

- [ ] **Step 3: Write minimal implementation**

```python
# src/bpp/util/uczelnia_scope.py
"""Zawężanie querysetów Rekordów do uczelni oglądającego (multi-hosted, read-side).

Jedno źródło reguły rekordowej + guard single-install. Reguła atrybucji =
strona główna (``get_uczelnia_context_data``): rekord należy do uczelni, gdy
którakolwiek z jednostek zapisanych na autorstwie należy do tej uczelni.
BEZ ``skupia_pracownikow`` (włącznie z obcą jednostką) — świadoma decyzja
(spec R3a).
"""


def tylko_jedna_uczelnia() -> bool:
    """True, gdy w systemie jest dokładnie jedna uczelnia.

    Fast-track jak ``IPunktacjaCacher._uczelnie_do_przeliczenia``: przy jednej
    uczelni filtr per-uczelnia jest no-op, więc pomijamy go (i kosztowny JOIN).
    """
    from bpp.models import Uczelnia

    return Uczelnia.objects.count() == 1


def scope_rekord_do_uczelni(qs, uczelnia):
    """Zawęź queryset ``Rekord`` do uczelni oglądającego.

    No-op (zwraca ten sam qs) gdy brak uczelni (brak mapowania Site→Uczelnia)
    albo gdy w systemie jest dokładnie jedna uczelnia — wynik identyczny,
    a unikamy JOIN-a przez M2M ``autorzy`` + ``DISTINCT``.
    """
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(autorzy__jednostka__uczelnia=uczelnia).distinct()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_util/test_uczelnia_scope.py -q -p no:cacheprovider`
Expected: PASS (5 passed).

- [ ] **Step 5: Lint + guard + commit**

```bash
uv run ruff check src/bpp/util/uczelnia_scope.py src/bpp/tests/test_util/test_uczelnia_scope.py
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
git add src/bpp/util/uczelnia_scope.py src/bpp/tests/test_util/
git commit -m "feat(multi-hosted): helper scope_rekord_do_uczelni + guard single-install (R3a)"
```

---

### Task 2: Raport „cała uczelnia" zawężony (`nowe_raporty/poziomy.py`)

**Files:**
- Modify: `src/nowe_raporty/poziomy.py` (funkcja `_base_uczelnia` ~`:38-41`; import)
- Test: `src/nowe_raporty/tests/test_poziom_uczelnia_per_uczelnia.py`

- [ ] **Step 1: Write the failing test**

```python
# src/nowe_raporty/tests/test_poziom_uczelnia_per_uczelnia.py
import pytest
from model_bakery import baker

from nowe_raporty.poziomy import _base_uczelnia


@pytest.mark.django_db
def test_base_uczelnia_wyklucza_obca_uczelnie(
    uczelnia1, uczelnia2, jednostka_uczelnia1, jednostka_uczelnia2,
    autor_uczelnia1, autor_uczelnia2,
):
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="MOJA")
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="OBCA")
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)

    tytuly = set(
        _base_uczelnia(uczelnia1, tylko_afiliowane=False).values_list(
            "tytul_oryginalny", flat=True
        )
    )
    assert "MOJA" in tytuly
    assert "OBCA" not in tytuly
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/nowe_raporty/tests/test_poziom_uczelnia_per_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL ("OBCA" w wyniku — `_base_uczelnia` zwraca `Rekord.objects.all()`).

- [ ] **Step 3: Write minimal implementation**

W `src/nowe_raporty/poziomy.py` dodaj import (przy innych z `bpp`):

```python
from bpp.util.uczelnia_scope import scope_rekord_do_uczelni
```

Zamień `_base_uczelnia`:

```python
def _base_uczelnia(obiekt, tylko_afiliowane):
    if tylko_afiliowane:
        qs = Rekord.objects.filter(autorzy__afiliuje=True)
    else:
        qs = Rekord.objects.all()
    return scope_rekord_do_uczelni(qs, obiekt)
```

`obiekt` to Uczelnia (z `views.py:284` `get_object` → `get_for_request`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/nowe_raporty/tests/test_poziom_uczelnia_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS. Regresja: `uv run pytest src/nowe_raporty/ -q -p no:cacheprovider`.

- [ ] **Step 5: Lint + guard + commit**

```bash
uv run ruff check src/nowe_raporty/poziomy.py src/nowe_raporty/tests/test_poziom_uczelnia_per_uczelnia.py
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
git add src/nowe_raporty/poziomy.py src/nowe_raporty/tests/test_poziom_uczelnia_per_uczelnia.py
git commit -m "feat(multi-hosted): raport poziom-uczelnia zawężony per uczelnia (R3a)"
```

---

### Task 3: Browse lata/rok zawężone (`bpp/views/browse.py`)

**Files:**
- Modify: `src/bpp/views/browse.py` (`LataView` ~`:485-518`, `RokView` ~`:520-556`; importy)
- Test: `src/bpp/tests/test_views/test_browse/test_lata_rok_per_uczelnia.py`

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_views/test_browse/test_lata_rok_per_uczelnia.py
import pytest
from model_bakery import baker

from bpp.views.browse import LataView, RokView
from fixtures.conftest_multisite import make_request_for_site


def _dwie_prace(jednostka_uczelnia1, jednostka_uczelnia2,
                autor_uczelnia1, autor_uczelnia2):
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", rok=2020)
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", rok=2021)
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)


@pytest.mark.django_db
def test_lata_view_liczy_tylko_swoja_uczelnie(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, jednostka_uczelnia2,
    autor_uczelnia1, autor_uczelnia2,
):
    _dwie_prace(jednostka_uczelnia1, jednostka_uczelnia2,
                autor_uczelnia1, autor_uczelnia2)
    view = LataView()
    view.request = make_request_for_site(site1)
    view.kwargs = {}
    lata = {y["year"] for y in view.get_queryset()}
    assert 2020 in lata
    assert 2021 not in lata


@pytest.mark.django_db
def test_rok_view_listuje_tylko_swoja_uczelnie(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, jednostka_uczelnia2,
    autor_uczelnia1, autor_uczelnia2,
):
    _dwie_prace(jednostka_uczelnia1, jednostka_uczelnia2,
                autor_uczelnia1, autor_uczelnia2)
    view = RokView()
    view.request = make_request_for_site(site1)
    view.kwargs = {"rok": 2021}
    view.object_list = view.get_queryset()
    ctx = view.get_context_data()
    assert ctx["total_count"] == 0  # praca 2021 należy do uczelni2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_views/test_browse/test_lata_rok_per_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL (2021 w latach; total_count == 1).

- [ ] **Step 3: Write minimal implementation**

W `src/bpp/views/browse.py` dodaj importy (przy istniejących z `bpp`):

```python
from bpp.models import Uczelnia
from bpp.util.uczelnia_scope import scope_rekord_do_uczelni
```

`LataView.get_queryset`:

```python
    def get_queryset(self):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        qs = scope_rekord_do_uczelni(Rekord.objects.all(), uczelnia)
        return [
            {"year": row["rok"], "count": row["count"]}
            for row in qs.values("rok")
            .annotate(count=Count("*"))
            .filter(count__gt=0)
            .order_by("-rok")
        ]
```

`LataView.get_context_data` — zamień `Rekord.objects.count()`:

```python
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        context["total_publications"] = scope_rekord_do_uczelni(
            Rekord.objects.all(), uczelnia
        ).count()
```

`RokView.get_queryset` — owiń zwracany queryset:

```python
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        return scope_rekord_do_uczelni(
            Rekord.objects.filter(rok=year), uczelnia
        ).order_by("-ostatnio_zmieniony")
```

`RokView.get_context_data` — owiń prev/next/total:

```python
        uczelnia = Uczelnia.objects.get_for_request(self.request)

        def _scoped(qs):
            return scope_rekord_do_uczelni(qs, uczelnia)

        if _scoped(Rekord.objects.filter(rok=year - 1)).exists():
            context["prev_year"] = year - 1
        if _scoped(Rekord.objects.filter(rok=year + 1)).exists():
            context["next_year"] = year + 1
        context["total_count"] = _scoped(Rekord.objects.filter(rok=year)).count()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_views/test_browse/test_lata_rok_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS. Regresja: `uv run pytest src/bpp/tests/test_views/test_browse/ src/bpp/tests/test_views/test_views_browse.py -q -p no:cacheprovider`.

- [ ] **Step 5: Lint + guard + commit**

```bash
uv run ruff check src/bpp/views/browse.py src/bpp/tests/test_views/test_browse/test_lata_rok_per_uczelnia.py
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
git add src/bpp/views/browse.py src/bpp/tests/test_views/test_browse/test_lata_rok_per_uczelnia.py
git commit -m "feat(multi-hosted): browse lata/rok zawężone per uczelnia (R3a)"
```

---

### Task 4: OAI-PMH zawężony (`bpp/views/oai.py`)

**Files:**
- Modify: `src/bpp/views/oai.py` (`OAIView.get`, konstrukcja `BPPOAIDatabase` ~`:243-247`; import)
- Test: `src/bpp/tests/test_views/test_oai_per_uczelnia.py`

Uzasadnienie chokepointu: `BPPOAIDatabase` trzyma `self.original` i używa go we WSZYSTKICH metodach (`record_count`, `oai_earliest_datestamp`, `oai_query`). Zawężenie bazowego querysetu RAZ przy konstrukcji pokrywa cały feed.

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_views/test_oai_per_uczelnia.py
import pytest
from model_bakery import baker
from django.urls import reverse


@pytest.mark.django_db
def test_oai_listrecords_wyklucza_obca_uczelnie(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, jednostka_uczelnia2,
    autor_uczelnia1, autor_uczelnia2, client, settings,
):
    settings.ALLOWED_HOSTS = ["*"]  # pozwól na HTTP_HOST domeny uczelni
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="PRACA-MOJA", rok=2020)
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="PRACA-OBCA", rok=2020)
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)

    url = reverse("bpp:oai") + "?verb=ListRecords&metadataPrefix=oai_dc"
    body = client.get(url, HTTP_HOST=site1.domain).content.decode("utf-8")
    assert "PRACA-MOJA" in body
    assert "PRACA-OBCA" not in body
```

Uwaga wykonawcza: jeśli `client.get` z `HTTP_HOST` nie rozwiązuje uczelni przez
middleware (np. `SITE_ID` wymuszony) — przełącz test na bezpośredni szew:
zbuduj `request = make_request_for_site(site1, path=...)` i wywołaj
`OAIView().get(request, ...)`, asercja na `response.content`. Sens testu bez zmian:
feed domeny uczelnia1 zawiera „PRACA-MOJA", nie „PRACA-OBCA".

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_views/test_oai_per_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL ("PRACA-OBCA" w feedzie).

- [ ] **Step 3: Write minimal implementation**

W `src/bpp/views/oai.py` dodaj import helpera (obok istniejących; `Uczelnia` jest już importowane — użyte w `oai_query:186`):

```python
from bpp.util.uczelnia_scope import scope_rekord_do_uczelni
```

W `OAIView.get` zamień konstrukcję `BPPOAIDatabase`:

```python
        uczelnia = Uczelnia.objects.get_for_request(request)
        base_qs = scope_rekord_do_uczelni(
            Rekord.objects.all().exclude(charakter_formalny__nazwa_w_primo=""),
            uczelnia,
        )
        db = BPPOAIDatabase(base_qs, request=request)
```

(Istniejący filtr `ukryte_statusy("api")` w `oai_query` zostaje — działa na zawężonym `self.original`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_views/test_oai_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS. Regresja: `uv run pytest src/bpp/tests/test_views/test_oai.py -q -p no:cacheprovider`.

- [ ] **Step 5: Lint + guard + commit**

```bash
uv run ruff check src/bpp/views/oai.py src/bpp/tests/test_views/test_oai_per_uczelnia.py
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
git add src/bpp/views/oai.py src/bpp/tests/test_views/test_oai_per_uczelnia.py
git commit -m "feat(multi-hosted): OAI feed zawężony per uczelnia (R3a)"
```

---

### Task 5: Ranking autorów zawężony po aktualnej jednostce (`ranking_autorow/views.py`)

**Files:**
- Modify: `src/ranking_autorow/views.py` (`_apply_location_filters` ~`:221-232`; import)
- Test: `src/ranking_autorow/tests/test_ranking_per_uczelnia.py` (utwórz katalog `tests/` + `__init__.py` jeśli brak; obecne testy są w `tests.py` — nowy moduł nie koliduje)

Reguła: ranking = obecni pracownicy uczelni → `autor__aktualna_jednostka__uczelnia=U`, bezwarunkowo (gdy `not tylko_jedna_uczelnia()`). Istniejące `exclude(autor__aktualna_jednostka=None)` zostaje.

- [ ] **Step 1: Write the failing test**

```python
# src/ranking_autorow/tests/test_ranking_per_uczelnia.py
import pytest
from model_bakery import baker

from ranking_autorow.views import RankingAutorow
from fixtures.conftest_multisite import make_request_for_site


@pytest.mark.django_db
def test_ranking_listuje_tylko_aktualnych_pracownikow_uczelni(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, jednostka_uczelnia2,
    autor_uczelnia1, autor_uczelnia2,
):
    # praca każdego autora w jego jednostce (Sumy = widok po Rekord)
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", impact_factor=10, rok=2020)
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", impact_factor=10, rok=2020)
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)

    r = RankingAutorow(
        request=make_request_for_site(site1), kwargs=dict(od_roku=0, do_roku=3030)
    )
    autorzy = {row.autor_id for row in r.get_queryset()}
    assert autor_uczelnia1.pk in autorzy
    assert autor_uczelnia2.pk not in autorzy
```

Uwaga: `RankingAutorow.get_queryset()` grupuje `Sumy` po autorze; `row.autor_id`
jest dostępny. Jeśli atrybut inny — sprawdź `views.py:265-291` (`group_by("autor")`).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/ranking_autorow/tests/test_ranking_per_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL (autor_uczelnia2 w rankingu — filtr po uczelni dziś tylko przy ręcznym wyborze jednostki).

- [ ] **Step 3: Write minimal implementation**

W `src/ranking_autorow/views.py` dodaj import:

```python
from bpp.util.uczelnia_scope import tylko_jedna_uczelnia
```

W `_apply_location_filters`, przed `return qset`, dodaj:

```python
    def _apply_location_filters(self, qset):
        jednostki = self.get_jednostki()
        if jednostki:
            qset = qset.filter(jednostka__in=jednostki)

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia and uczelnia.uzywaj_wydzialow and not jednostki:
            wydzialy = self.get_wydzialy()
            if wydzialy:
                qset = qset.filter(jednostka__wydzial__in=wydzialy)

        # Multi-hosted: ranking = obecni pracownicy tej uczelni.
        # No-op na single-install (guard) — wynik bez zmian.
        if uczelnia is not None and not tylko_jedna_uczelnia():
            qset = qset.filter(autor__aktualna_jednostka__uczelnia=uczelnia)

        return qset
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/ranking_autorow/tests/test_ranking_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS. Regresja: `uv run pytest src/ranking_autorow/ -q -p no:cacheprovider`.

- [ ] **Step 5: Lint + guard + commit**

```bash
uv run ruff check src/ranking_autorow/views.py src/ranking_autorow/tests/test_ranking_per_uczelnia.py
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
git add src/ranking_autorow/views.py src/ranking_autorow/tests/
git commit -m "feat(multi-hosted): ranking autorów zawężony po aktualnej jednostce uczelni (R3a)"
```

---

### Task 6: Regresja całościowa + zamknięcie

**Files:** brak zmian kodu (weryfikacja).

- [ ] **Step 1: Pełna regresja dotkniętych obszarów**

Run:
```bash
uv run pytest src/bpp/tests/test_util/ src/nowe_raporty/ \
  src/bpp/tests/test_views/test_browse/ src/bpp/tests/test_views/test_views_browse.py \
  src/bpp/tests/test_views/test_oai.py src/bpp/tests/test_views/test_oai_per_uczelnia.py \
  src/ranking_autorow/ src/bpp/tests/test_multisite/ \
  -q -p no:cacheprovider
```
Expected: wszystko zielone (testy izolacji + istniejące = invariant single-install).

- [ ] **Step 2: Guard get_default**

Run: `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q`
Expected: PASS (R3a nie wprowadza `get_default`).

- [ ] **Step 3: Migracje bez dryfu** (R3a nie zmienia modeli — sanity)

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: brak nowych migracji dla `bpp`/`nowe_raporty`/`ranking_autorow`.

- [ ] **Step 4: Aktualizacja HANDOFF**

Dopisz w `docs/superpowers/HANDOFF-multi-hosted.md` (sekcja „AUDYTY 4×"): R3a (widoki) ZROBIONE, R3b następny. Commit:
```bash
git add docs/superpowers/HANDOFF-multi-hosted.md
git commit -m "docs(multi-hosted): HANDOFF - R3a read-side widoki ZROBIONE"
```

---

## Notatki wykonawcze
- Helper z Taska 1 jest też zależnością R3b (`tylko_jedna_uczelnia`) — R3a pierwszy.
- Reguła rekordowa NIE wymaga `skupia_pracownikow` (świadome, = homepage). Fixtury
  `jednostka_uczelnia1/2` mają `uczelnia` ustawioną — to wystarcza.
- `dodaj_autora(autor, jednostka)` to metoda `Wydawnictwo_Ciagle` (patrz
  `ranking_autorow/tests.py`). `Rekord`/`Sumy` to widoki SQL — odzwierciedlają
  dane natychmiast.
- Single-install invariant trzyma się na guardzie `tylko_jedna_uczelnia()`:
  dopóki testy regresyjne (istniejące, single-install) są zielone, zachowanie
  produkcyjne dla jednej uczelni jest niezmienione.
- Import `from fixtures.conftest_multisite import make_request_for_site` działa,
  bo `src/` jest na PYTHONPATH (pytest rootdir) i `fixtures` to pakiet.
