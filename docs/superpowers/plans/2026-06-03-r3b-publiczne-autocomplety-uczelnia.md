# R3b — publiczne autocomplety per-uczelnia Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zawęzić trzy publiczne autocomplety (jednostka, wydział, autor) do uczelni oglądającego, żeby pickery w Multiseeku/rankingu nie podpowiadały bytów innych uczelni. Bez regresji na single-install, bez dotykania autocompletów admina/edytora.

**Architecture:** Jeden wspólny mixin `UczelniaScopedAutocompleteMixin` (w `bpp/views/autocomplete/mixins.py`) nadpisuje `get_queryset`: woła `super().get_queryset()`, a potem — gdy jest uczelnia z requestu i NIE single-install (guard `tylko_jedna_uczelnia` z R3a) — filtruje przez OR listy lookupów `uczelnia_lookups` + `.distinct()`. Trzy publiczne klasy dodają mixin (pierwszy w MRO) i ustawiają `uczelnia_lookups`. Admin/edytor używają innych klas — nietknięte.

**Tech Stack:** Django, django-autocomplete-light (dal), pytest + model_bakery, testcontainers, `uv run`.

Spec: `docs/superpowers/specs/2026-06-03-r3b-publiczne-autocomplety-uczelnia-design.md`. Zależy od R3a (helper `bpp.util.uczelnia_scope.tylko_jedna_uczelnia`, już na origin).

## Reguły wykonawcze (per HANDOFF + nauki z R3a)
- Testy: `uv run pytest <ścieżka> -q -p no:cacheprovider` (Docker działa).
- Lint: `uv run ruff check <pliki>` ORAZ `uv run ruff format --check <pliki>` przed commitem. Jeśli format-check zgłasza plik → `uv run ruff format <plik>` (to projektowy formatter z pre-commit hooka, NIE zakazany `ruff check --fix`), potem re-weryfikuj oba.
- Guard: `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q` po każdym tasku.
- `make_request_for_site(site)` z `fixtures.conftest_multisite` odpala `SiteResolutionMiddleware` (woła `get_host()`) → w testach ustaw `settings.ALLOWED_HOSTS = ["*"]` (fixtura `settings`), inaczej `DisallowedHost`.
- Test autocompletu: instancjonuj widok, ustaw `view.request = make_request_for_site(site1)` i `view.q = ""`, wołaj `view.get_queryset()` (dal czyta `self.q`; przy bezpośrednim wywołaniu ustaw je ręcznie). Asercje na pk/zawartości zwróconego querysetu.
- Commit po każdym tasku. Push tylko na prośbę.

## Kontekst klas (zweryfikowany)
- **jednostka** (multiseek): `WidocznaJednostkaAutocomplete` (`bpp/views/autocomplete/units.py:26`), `qset = Jednostka.objects.widoczne()`, dziedziczy `get_queryset` z `JednostkaAutocomplete` (filtr po `self.q`, `order_by`). `Jednostka.uczelnia` to FK. Używana TYLKO przez multiseek (`unit_fields.py:46,84`), nie przez admina.
- **wydział**: `PublicWydzialAutocomplete` (`bpp/views/autocomplete/simple.py:199`), `qset = Wydzial.objects.filter(widoczny=True)`, `get_queryset` z `NazwaLubSkrotMixin`. `Wydzial.uczelnia` to FK (`wydzial.py:24`).
- **autor**: `PublicAutorAutocomplete` (`bpp/views/autocomplete/authors.py:182`) dziedziczy `AutorAutocompleteBase`. Jego `get_queryset` (`authors.py:42-87`) JUŻ anotuje grupy per-uczelnia (`aktualna_jednostka` vs `autor_jednostka` history) i sortuje — ale NIE filtruje. Zwraca pełny queryset Autor (nie sliced). Reguła „kiedykolwiek związany" = grupy 1+2 = `aktualna_jednostka__uczelnia` OR `autor_jednostka__jednostka__uczelnia`.

---

### Task 1: Mixin `UczelniaScopedAutocompleteMixin` + zastosowanie do jednostki

**Files:**
- Modify: `src/bpp/views/autocomplete/mixins.py` (dodaj mixin)
- Modify: `src/bpp/views/autocomplete/units.py` (`WidocznaJednostkaAutocomplete`)
- Test: `src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py` (nowy)

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
import pytest

from fixtures.conftest_multisite import make_request_for_site


@pytest.mark.django_db
def test_jednostka_autocomplete_zawezony_do_uczelni(
    uczelnia1, uczelnia2, site1, jednostka_uczelnia1, jednostka_uczelnia2, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.views.autocomplete.units import WidocznaJednostkaAutocomplete

    view = WidocznaJednostkaAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert jednostka_uczelnia1.pk in pks
    assert jednostka_uczelnia2.pk not in pks
```

Uwaga: fixtury `jednostka_uczelnia1/2` tworzą jednostki przez `Jednostka.objects.create(...)`. Sprawdź czy są „widoczne" (`Jednostka.objects.widoczne()`); jeśli `widoczne()` wymaga flagi (np. `widoczna=True`/`pokazuj_*`) której fixtura nie ustawia, jednostka może nie wejść do `qset` NIEZALEŻNIE od uczelni — wtedy ustaw wymaganą flagę w teście (`jednostka_uczelnia1.widoczna = True; jednostka_uczelnia1.save()`), żeby test mierzył filtr uczelni, a nie widoczność. Zajrzyj do `Jednostka.objects.widoczne()` definicji.

- [ ] **Step 2: Run test, verify it FAILS** (jednostka_uczelnia2 obecna)

Run: `uv run pytest src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py -q -p no:cacheprovider`

- [ ] **Step 3: Write minimal implementation**

W `src/bpp/views/autocomplete/mixins.py` dodaj na końcu:

```python
class UczelniaScopedAutocompleteMixin:
    """Publiczny autocomplete zawężony do uczelni oglądającego (multi-hosted).

    No-op gdy brak uczelni w requeście (brak mapowania Site→Uczelnia) albo gdy
    w systemie jest jedna uczelnia (guard ``tylko_jedna_uczelnia`` z R3a) —
    podpowiedzi i wydajność wtedy identyczne jak dawniej.

    Podklasy ustawiają ``uczelnia_lookups`` — krotkę ścieżek ORM od modelu do
    ``Uczelnia``; są łączone przez OR. ``.distinct()`` zawsze (joiny po historii
    mnożą wiersze; dla FK jest nieszkodliwe).
    """

    uczelnia_lookups = ("uczelnia",)

    def get_queryset(self):
        qs = super().get_queryset()

        from django.db.models import Q

        from bpp.models import Uczelnia
        from bpp.util.uczelnia_scope import tylko_jedna_uczelnia

        uczelnia = Uczelnia.objects.get_for_request(self.request)
        if uczelnia is not None and not tylko_jedna_uczelnia():
            warunek = Q()
            for lookup in self.uczelnia_lookups:
                warunek |= Q(**{lookup: uczelnia})
            qs = qs.filter(warunek).distinct()
        return qs
```

W `src/bpp/views/autocomplete/units.py` zmień import i `WidocznaJednostkaAutocomplete`:

```python
from .mixins import SanitizedAutocompleteMixin, UczelniaScopedAutocompleteMixin
```
```python
class WidocznaJednostkaAutocomplete(
    UczelniaScopedAutocompleteMixin, JednostkaAutocomplete
):
    """Autocomplete for visible organizational units (per-uczelnia, multi-hosted)."""

    qset = Jednostka.objects.widoczne().select_related("wydzial")
    # uczelnia_lookups domyślne ("uczelnia",) — Jednostka.uczelnia to FK
```

MRO: mixin PIERWSZY → jego `get_queryset` woła `super().get_queryset()` = `JednostkaAutocomplete.get_queryset` (filtr `self.q` + order_by), a potem filtruje po uczelni.

- [ ] **Step 4: Run test, verify it PASSES.** Regresja autocomplete jednostki: `uv run pytest src/bpp/tests/test_views/ -k "jednostka or autocomplete" -q -p no:cacheprovider` (i `uv run pytest src/bpp/tests/test_multiseek/ -q -p no:cacheprovider` jeśli istnieje).

- [ ] **Step 5: Lint + format + guard + commit**

```bash
uv run ruff check src/bpp/views/autocomplete/mixins.py src/bpp/views/autocomplete/units.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
uv run ruff format --check src/bpp/views/autocomplete/mixins.py src/bpp/views/autocomplete/units.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
git add src/bpp/views/autocomplete/mixins.py src/bpp/views/autocomplete/units.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
git commit -m "feat(multi-hosted): mixin UczelniaScopedAutocomplete + jednostka autocomplete per uczelnia (R3b)"
```

---

### Task 2: Wydział autocomplete per-uczelnia

**Files:**
- Modify: `src/bpp/views/autocomplete/simple.py` (`PublicWydzialAutocomplete` + import)
- Test: dopisz do `src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py`

- [ ] **Step 1: Write the failing test** (dopisz funkcję)

```python
@pytest.mark.django_db
def test_wydzial_autocomplete_zawezony_do_uczelni(
    uczelnia1, uczelnia2, site1, wydzial_uczelnia1, wydzial_uczelnia2, settings
):
    settings.ALLOWED_HOSTS = ["*"]
    from bpp.views.autocomplete.simple import PublicWydzialAutocomplete

    view = PublicWydzialAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert wydzial_uczelnia1.pk in pks
    assert wydzial_uczelnia2.pk not in pks
```

Uwaga: `PublicWydzialAutocomplete.qset = Wydzial.objects.filter(widoczny=True)`. Fixtury `wydzial_uczelnia1/2` tworzą wydziały przez `Wydzial.objects.create(...)` — jeśli `widoczny` domyślnie False, ustaw `wydzial_uczelnia1.widoczny = True; .save()` (i analogicznie u2, by test mierzył filtr uczelni nie widoczności). Sprawdź default pola `Wydzial.widoczny`.

- [ ] **Step 2: Run test, verify it FAILS** (wydzial_uczelnia2 obecny)

Run: `uv run pytest src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py::test_wydzial_autocomplete_zawezony_do_uczelni -q -p no:cacheprovider`

- [ ] **Step 3: Write minimal implementation**

W `src/bpp/views/autocomplete/simple.py` zaimportuj mixin (przy istniejącym imporcie z `.mixins`):
```python
from .mixins import SanitizedAutocompleteMixin, UczelniaScopedAutocompleteMixin
```
(jeśli import z `.mixins` ma inną formę — dostosuj, nie duplikuj.)

Zmień klasę:
```python
class PublicWydzialAutocomplete(
    UczelniaScopedAutocompleteMixin,
    SanitizedAutocompleteMixin,
    NazwaLubSkrotMixin,
    autocomplete.Select2QuerySetView,
):
    """Public autocomplete for visible departments (per-uczelnia, multi-hosted)."""

    qset = Wydzial.objects.filter(widoczny=True)
    # uczelnia_lookups domyślne ("uczelnia",) — Wydzial.uczelnia to FK
```

MRO: mixin pierwszy → `super().get_queryset()` schodzi do `NazwaLubSkrotMixin.get_queryset`.

- [ ] **Step 4: Run test, verify it PASSES.** Regresja: `uv run pytest src/bpp/tests/test_views/ -k "wydzial or autocomplete" -q -p no:cacheprovider`.

- [ ] **Step 5: Lint + format + guard + commit**

```bash
uv run ruff check src/bpp/views/autocomplete/simple.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
uv run ruff format --check src/bpp/views/autocomplete/simple.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
git add src/bpp/views/autocomplete/simple.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
git commit -m "feat(multi-hosted): wydzial autocomplete per uczelnia (R3b)"
```

---

### Task 3: Autor autocomplete „kiedykolwiek związany" per-uczelnia

**Files:**
- Modify: `src/bpp/views/autocomplete/authors.py` (`PublicAutorAutocomplete` + import)
- Test: dopisz do `src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py`

Reguła (decyzja usera): public autor picker = autor związany z uczelnią OBECNIE lub w PRZESZŁOŚCI → `aktualna_jednostka__uczelnia` OR `autor_jednostka__jednostka__uczelnia`. To grupy 1+2 z istniejącego grupowania w `AutorAutocompleteBase`; grupa 3 (zewnętrzni) odpada. NIE samo `aktualna_jednostka` (to byłaby tylko „obecnie zatrudniony").

- [ ] **Step 1: Write the failing test** (dopisz; uwzględnij autora HISTORYCZNEGO — aktualna jednostka gdzie indziej, ale historia w U1)

```python
@pytest.mark.django_db
def test_autor_autocomplete_kiedykolwiek_zwiazany(
    uczelnia1, uczelnia2, site1,
    jednostka_uczelnia1, jednostka_uczelnia2,
    autor_uczelnia1, autor_uczelnia2, settings,
):
    settings.ALLOWED_HOSTS = ["*"]
    from model_bakery import baker

    from bpp.views.autocomplete.authors import PublicAutorAutocomplete

    # autor historyczny: aktualna jednostka w U2, ale wpis Autor_Jednostka w U1
    autor_hist = baker.make("bpp.Autor", aktualna_jednostka=jednostka_uczelnia2)
    baker.make("bpp.Autor_Jednostka", autor=autor_hist, jednostka=jednostka_uczelnia1)

    view = PublicAutorAutocomplete()
    view.request = make_request_for_site(site1)
    view.q = ""
    pks = set(view.get_queryset().values_list("pk", flat=True))
    assert autor_uczelnia1.pk in pks          # obecny pracownik U1
    assert autor_hist.pk in pks               # historycznie związany z U1
    assert autor_uczelnia2.pk not in pks      # tylko U2 → zewnętrzny dla U1
```

- [ ] **Step 2: Run test, verify it FAILS** (autor_uczelnia2 obecny — base nie filtruje, tylko grupuje)

Run: `uv run pytest src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py::test_autor_autocomplete_kiedykolwiek_zwiazany -q -p no:cacheprovider`

- [ ] **Step 3: Write minimal implementation**

W `src/bpp/views/autocomplete/authors.py` zaimportuj mixin:
```python
from .mixins import UczelniaScopedAutocompleteMixin
```
(dostosuj do istniejących importów z `.mixins`/`.` — nie duplikuj.)

Zmień `PublicAutorAutocomplete`:
```python
class PublicAutorAutocomplete(UczelniaScopedAutocompleteMixin, AutorAutocompleteBase):
    """Public author autocomplete — autorzy związani z uczelnią obecnie lub w
    przeszłości (multi-hosted). Grupowanie/sortowanie z bazy zachowane."""

    uczelnia_lookups = (
        "aktualna_jednostka__uczelnia",
        "autor_jednostka__jednostka__uczelnia",
    )

    def get_text_for_result(self, result):
        return str(result)
```

WAŻNE: zachowaj istniejące ciało `PublicAutorAutocomplete` (jeśli ma metodę zwracającą `str(result)` — `authors.py:185-187` — przenieś ją bez zmian; nie usuwaj). MRO: mixin pierwszy → `super().get_queryset()` = `AutorAutocompleteBase.get_queryset` (grupowanie + order_by), potem filtr OR + distinct. `.distinct()` współgra z anotacjami/`order_by("grupa_uczelnia",...)` (Postgres: kolumny order_by są w SELECT, dedup po pełnych wierszach).

- [ ] **Step 4: Run test, verify it PASSES.** Regresja autorów: `uv run pytest src/bpp/tests/test_views/ -k "autor or autocomplete" -q -p no:cacheprovider` (zwróć uwagę czy jakiś istniejący test zakładał, że publiczny autocomplete pokazuje autorów zewnętrznych — jeśli tak, to był single-install i guard go nie rusza; jeśli multi-uczelnia i pada, zgłoś jako koncept do rozstrzygnięcia, nie nadpisuj testu po cichu).

- [ ] **Step 5: Lint + format + guard + commit**

```bash
uv run ruff check src/bpp/views/autocomplete/authors.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
uv run ruff format --check src/bpp/views/autocomplete/authors.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
git add src/bpp/views/autocomplete/authors.py src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
git commit -m "feat(multi-hosted): autor autocomplete kiedykolwiek-zwiazany per uczelnia (R3b)"
```

---

### Task 4: Regresja całościowa + admin nietknięty + HANDOFF

**Files:** brak zmian kodu (weryfikacja + doc).

- [ ] **Step 1: Regresja dotkniętych obszarów + autocomplete admina**

Run:
```bash
uv run pytest src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py \
  src/bpp/tests/test_views/ -k "autocomplete or jednostka or wydzial or autor" \
  src/bpp/tests/test_multisite/ \
  -q -p no:cacheprovider
```
Expected: zielone. Jeśli istnieją testy multiseek (`src/bpp/tests/test_multiseek/`), dorzuć je. Każda regresja przy jednej uczelni = guard no-op, więc istniejące testy single-install muszą przejść.

- [ ] **Step 2: Potwierdź, że admin/edytor autocomplety NIE są zawężone**

Szybka asercja, że `JednostkaAutocomplete` (admin) i `WydzialAutocomplete` (admin) NIE dziedziczą `UczelniaScopedAutocompleteMixin` (czyli pokazują wszystkie uczelnie). Dopisz do pliku testowego:
```python
def test_admin_autocomplety_nie_sa_zawezone():
    from bpp.views.autocomplete.mixins import UczelniaScopedAutocompleteMixin
    from bpp.views.autocomplete.units import JednostkaAutocomplete
    from bpp.views.autocomplete.simple import WydzialAutocomplete

    assert not issubclass(JednostkaAutocomplete, UczelniaScopedAutocompleteMixin)
    assert not issubclass(WydzialAutocomplete, UczelniaScopedAutocompleteMixin)
```
Run ten test; commituj go razem z krokiem 3 (lub osobno).

- [ ] **Step 3: Guard get_default**

Run: `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q` → PASS.

- [ ] **Step 4: Migracje bez dryfu** (R3b nie zmienia modeli)

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: brak nowych migracji dla `bpp` z R3b (pre-existing/third-party drift z R3a-Task6 może się powtórzyć — nie z R3b).

- [ ] **Step 5: Aktualizacja HANDOFF + commit**

W `docs/superpowers/HANDOFF-multi-hosted.md` (sekcja AUDYTY 4×, bullet A) oznacz R3b ZROBIONE (analogicznie do R3a). Commit:
```bash
git add docs/superpowers/HANDOFF-multi-hosted.md src/bpp/tests/test_views/test_autocomplete_per_uczelnia.py
git commit -m "docs(multi-hosted): HANDOFF - R3b autocomplety ZROBIONE; test admin-nietkniety"
```

---

## Notatki wykonawcze
- Mixin MUSI być PIERWSZY w MRO każdej z trzech klas, inaczej `super().get_queryset()` nie złapie istniejącej logiki filtra-tekstowego/grupowania.
- Reguła autora to OR dwóch lookupów (obecnie LUB w przeszłości) — świadome uściślenie spec (sam `autor_jednostka` zgubiłby obecnego pracownika bez wiersza historii). Udokumentowane w docstringu klasy.
- `.distinct()` zawsze (mixin) — konieczne dla joinu po historii autora; nieszkodliwe dla FK jednostki/wydziału.
- Guard `tylko_jedna_uczelnia()` (z R3a) → single-install: mixin nie filtruje, podpowiedzi identyczne, zero narzutu. Autor: istniejące grupowanie i tak działa tylko gdy `request._uczelnia` ustawione — bez zmian.
- Admin/edytor autocomplety (`JednostkaAutocomplete`, `WydzialAutocomplete`, `AutorAutocomplete`) NIE dostają mixinu — pełny dostęp zachowany (Task 4 Step 2 to pilnuje).
- Jeśli `widoczne()`/`widoczny=True` wymaga flag których fixtury nie ustawiają — ustaw je w teście, żeby mierzyć filtr UCZELNI, nie widoczność (patrz uwagi w Taskach 1–2).
