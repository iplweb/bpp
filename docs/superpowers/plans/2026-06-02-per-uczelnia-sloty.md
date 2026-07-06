# Per-uczelnia liczenie slotów/punktacji (write-side) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Liczyć i zapisywać cache slotów/punktacji osobno per uczelnia, każda na subsetcie swoich autorów (autor → jednostka → uczelnia), zachowując identyczne liczby w instalacji jednouczelnianej.

**Architecture:** `ISlot(publikacja, uczelnia=None)` — opcjonalna uczelnia; gdy `None`, ISlot ją rozstrzyga (jedna w systemie / praca z jednej uczelni) albo rzuca `CannotAdapt` przy pracy cross-uczelnia (bez zgadywania). `SlotMixin` filtruje autorów po `jednostka__uczelnia`, gdy uczelnia ustawiona. `IPunktacjaCacher(original)` (bez parametru uczelni) kasuje cały rekord i odbudowuje per uczelnia: fast-track gdy `Uczelnia.objects.count()==1`, inaczej pętla po `uczelnie_rekordu()` z `ISlot(original, uczelnia=U)`. `Cache_Punktacja_Dyscypliny` zyskuje FK `uczelnia` (klucz partycji); `Cache_Punktacja_Autora` trzyma uczelnię wyprowadzaną z `jednostka`. Widok SQL dostaje join po uczelni. Callerzy `IPunktacjaCacher`/`przelicz_punkty_dyscyplin` — bez zmian.

**Tech Stack:** Django, PostgreSQL, pytest + model_bakery, django-denorm, testcontainers.

**Spec:** `docs/superpowers/specs/2026-06-02-per-uczelnia-sloty-design.md`

---

## Uwagi wykonawcze (przeczytaj przed startem)

- Komenda testowa: `uv run pytest <ścieżka> -q -p no:cacheprovider` (testcontainers
  same stawiają PG/Redis; Docker musi działać).
- **NIGDY nie edytuj istniejących migracji.** Nowe pliki.
- Lint: `uv run ruff check <pliki>` (NIE `--fix` — popraw ręcznie). Max 88 znaków.
- Po każdym Tasku: testy zielone → commit.
- Invariant single-install: istniejący zestaw `test_sloty/` musi pozostać zielony
  (ochrona regresji liczb) — sprawdzane w Tasku 9.
- Kolejność ma znaczenie: `uczelnie_rekordu()` (Task 3) jest wymagane przez
  `_rozstrzygnij_uczelnie` w `ISlot` (Task 4).

---

## Task 1: FK `uczelnia` na `Cache_Punktacja_Dyscypliny` + serialize + migracja

**Files:**
- Modify: `src/bpp/models/cache/punktacja.py`
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py` (create)
- Migration: wygenerowana przez `makemigrations`

- [ ] **Step 1: Napisz failing test**

Utwórz `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`:

```python
import pytest

from bpp.models.cache import Cache_Punktacja_Dyscypliny


@pytest.mark.django_db
def test_cache_punktacja_dyscypliny_ma_uczelnia(uczelnia, dyscyplina1):
    obj = Cache_Punktacja_Dyscypliny(
        rekord_id=[1, 1],
        dyscyplina=dyscyplina1,
        pkd=10,
        slot=1,
        uczelnia=uczelnia,
    )
    assert obj.uczelnia_id == uczelnia.pk
    assert obj.serialize()[-1] == uczelnia.pk
```

- [ ] **Step 2: Uruchom test — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL (`TypeError: unexpected keyword 'uczelnia'` lub brak uczelnia_id).

- [ ] **Step 3: Dodaj pole + serialize + indeks**

W `src/bpp/models/cache/punktacja.py`, klasa `Cache_Punktacja_Dyscypliny`,
dodaj pole `uczelnia`, indeks i zaktualizuj `serialize`:

```python
    uczelnia = ForeignKey("bpp.Uczelnia", models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ("dyscyplina__nazwa",)
        indexes = [
            models.Index(fields=["uczelnia", "dyscyplina"]),
        ]

    def serialize(self):
        return [
            self.rekord_id,
            self.dyscyplina_id,
            str(self.pkd),
            str(self.slot),
            self.uczelnia_id,
        ]
```

(Pole wstaw po `zapisani_autorzy_z_dyscypliny`. Indeks tylko na zwykłych FK —
`rekord_id` (TupleField) ma już własny `db_index=True`.)

- [ ] **Step 4: Wygeneruj migrację**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp`
Expected: plik `src/bpp/migrations/0424_*.py` z `AddField` + `AddIndex`.
**Zapamiętaj nazwę pliku** (potrzebna w Tasku 7).

- [ ] **Step 5: Uruchom test — ma PRZEJŚĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/bpp/models/cache/punktacja.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git add src/bpp/models/cache/punktacja.py src/bpp/migrations/0424_*.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "feat(multi-hosted): FK uczelnia na Cache_Punktacja_Dyscypliny + serialize"
```

---

## Task 2: `SlotMixin` + `Zwarte_Baza` — parametr `uczelnia` i filtr autorów

**Files:**
- Modify: `src/bpp/models/sloty/common.py`
- Modify: `src/bpp/models/sloty/wydawnictwo_zwarte.py:17`
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`

- [ ] **Step 1: Dodaj fixture'y dwóch uczelni + test scopingu (failing)**

Dopisz w `test_per_uczelnia.py` (importy + fixture'y + test):

```python
from bpp.models import (
    Autor_Dyscyplina,
    Charakter_Formalny,
    Jednostka,
    Uczelnia,
    Wydzial,
)


@pytest.fixture
def druga_uczelnia(db):
    from django.contrib.sites.models import Site

    site, _ = Site.objects.get_or_create(
        domain="druga.testserver", defaults={"name": "druga"}
    )
    return Uczelnia.objects.create(skrot="DR", nazwa="Druga uczelnia", site=site)


@pytest.fixture
def jednostka_drugiej_uczelni(druga_uczelnia, db):
    wydzial = Wydzial.objects.create(
        uczelnia=druga_uczelnia, skrot="W2", nazwa="Wydział II"
    )
    return Jednostka.objects.create(
        nazwa="Jedn. Drugiej Ucz.",
        skrot="JDU",
        wydzial=wydzial,
        uczelnia=druga_uczelnia,
    )


@pytest.fixture
def zwarte_dwie_uczelnie(
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    jednostka_drugiej_uczelni,
    dyscyplina1,
    rodzaj_autora_n,
    charaktery_formalne,
    wydawca,
    typy_odpowiedzialnosci,
    rok,
):
    # Obaj autorzy w TEJ SAMEJ dyscyplinie, ale w różnych uczelniach.
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, dyscyplina_naukowa=dyscyplina1, rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1, rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka_drugiej_uczelni, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_zwarte.punkty_kbn = 20
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(skrot="KSP")
    wydawnictwo_zwarte.save()
    return wydawnictwo_zwarte


@pytest.mark.django_db
def test_slotmixin_wszyscy_scoped_po_uczelni(zwarte_dwie_uczelnie, jednostka):
    from bpp.models.sloty.wydawnictwo_zwarte import (
        SlotKalkulator_Wydawnictwo_Zwarte_Prog3,
    )

    kalk_all = SlotKalkulator_Wydawnictwo_Zwarte_Prog3(
        zwarte_dwie_uczelnie, tryb_kalkulacji=None
    )
    kalk_u1 = SlotKalkulator_Wydawnictwo_Zwarte_Prog3(
        zwarte_dwie_uczelnie, tryb_kalkulacji=None, uczelnia=jednostka.uczelnia
    )
    assert kalk_all.wszyscy() == 2
    assert kalk_u1.wszyscy() == 1
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_slotmixin_wszyscy_scoped_po_uczelni -q -p no:cacheprovider`
Expected: FAIL (`TypeError: unexpected keyword 'uczelnia'`).

- [ ] **Step 3: Parametryzuj `SlotMixin`**

W `src/bpp/models/sloty/common.py` zamień `__init__`, dodaj `_autorzy_qs`,
przepnij `wszyscy`, `autorzy_z_dyscypliny`, `dyscypliny`:

```python
    def __init__(self, original, uczelnia=None):
        self.original = original
        self.uczelnia = uczelnia

    def _autorzy_qs(self):
        qs = self.original.autorzy_set.all()
        if self.uczelnia is not None:
            qs = qs.filter(jednostka__uczelnia=self.uczelnia)
        return qs

    def wszyscy(self):
        return self._autorzy_qs().count()

    def autorzy_z_dyscypliny(self, dyscyplina_naukowa, typ_ogolny=None):
        ret = []

        elem_kw = {}
        if typ_ogolny is not None:
            elem_kw = {"typ_odpowiedzialnosci__typ_ogolny": typ_ogolny}

        for elem in self._autorzy_qs().filter(
            afiliuje=True,
            przypieta=True,
            dyscyplina_naukowa=dyscyplina_naukowa,
            **elem_kw,
        ):
            if not elem.rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow():
                continue
            ret.append(elem)
        return ret
```

I `dyscypliny`:

```python
    @cached_property
    def dyscypliny(self):
        if not self.original.pk:
            return set()

        ret = set()
        for wa in self._autorzy_qs():
            d = wa.okresl_dyscypline()
            if d is None:
                continue
            ret.add(d)
        return ret
```

- [ ] **Step 4: Parametryzuj `Zwarte_Baza`**

W `src/bpp/models/sloty/wydawnictwo_zwarte.py` zamień `__init__`:

```python
    def __init__(
        self, original, tryb_kalkulacji, wiele_hst=False, poziom_wydawcy=None,
        uczelnia=None,
    ):
        self.original = original
        self.tryb_kalkulacji = tryb_kalkulacji
        self.wiele_hst = wiele_hst
        self.poziom_wydawcy = poziom_wydawcy
        self.uczelnia = uczelnia
```

- [ ] **Step 5: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_slotmixin_wszyscy_scoped_po_uczelni -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/bpp/models/sloty/common.py src/bpp/models/sloty/wydawnictwo_zwarte.py
git add src/bpp/models/sloty/common.py src/bpp/models/sloty/wydawnictwo_zwarte.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "feat(multi-hosted): SlotMixin/Zwarte_Baza filtruja autorow po uczelni"
```

---

## Task 3: `uczelnie_rekordu()` na modelu

**Files:**
- Modify: `src/bpp/models/abstract/disciplines.py`
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`

- [ ] **Step 1: Napisz failing test**

```python
@pytest.mark.django_db
def test_uczelnie_rekordu_zwraca_obie(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia
):
    assert set(zwarte_dwie_uczelnie.uczelnie_rekordu()) == {
        jednostka.uczelnia,
        druga_uczelnia,
    }
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_uczelnie_rekordu_zwraca_obie -q -p no:cacheprovider`
Expected: FAIL (`AttributeError: 'uczelnie_rekordu'`).

- [ ] **Step 3: Dodaj metodę**

W `src/bpp/models/abstract/disciplines.py`, klasa `ModelZPrzeliczaniemDyscyplin`,
dodaj (np. po `wszystkie_dyscypliny_rekordu`):

```python
    def uczelnie_rekordu(self):
        """Distinct uczelnie wśród afiliujących, przypiętych autorów rekordu
        (autor → jednostka → uczelnia). Luźny nadzbiór wystarcza."""
        from bpp.models.uczelnia import Uczelnia

        if not self.pk:
            return Uczelnia.objects.none()

        uczelnia_ids = (
            self.autorzy_set.filter(afiliuje=True, przypieta=True)
            .values_list("jednostka__uczelnia_id", flat=True)
            .distinct()
        )
        return Uczelnia.objects.filter(pk__in=list(uczelnia_ids))
```

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_uczelnie_rekordu_zwraca_obie -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/bpp/models/abstract/disciplines.py
git add src/bpp/models/abstract/disciplines.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "feat(multi-hosted): uczelnie_rekordu() na ModelZPrzeliczaniemDyscyplin"
```

---

## Task 4: `ISlot(original, uczelnia=None)` — opcjonalna uczelnia, rozstrzyganie, helper

**Files:**
- Modify: `src/bpp/models/sloty/core.py:26-293`
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`

- [ ] **Step 1: Napisz failing testy (scoped + rozstrzyganie + ambiguous)**

```python
@pytest.mark.django_db
def test_islot_jawna_uczelnia_scoped(zwarte_dwie_uczelnie, jednostka):
    from bpp.models.sloty.core import ISlot

    kalk = ISlot(zwarte_dwie_uczelnie, uczelnia=jednostka.uczelnia)
    assert kalk.uczelnia == jednostka.uczelnia
    assert kalk.wszyscy() == 1


@pytest.mark.django_db
def test_islot_none_cross_uczelnia_failuje(zwarte_dwie_uczelnie, druga_uczelnia):
    # 2 uczelnie w systemie + praca cross-uczelnia => niejednoznaczne => CannotAdapt
    from bpp.models.sloty.core import CannotAdapt, ISlot

    with pytest.raises(CannotAdapt):
        ISlot(zwarte_dwie_uczelnie)


@pytest.mark.django_db
def test_islot_none_jedna_uczelnia_systemu_rozstrzyga(
    zwarte_z_dyscyplinami, uczelnia
):
    # tylko jedna uczelnia w systemie => ISlot(obj) rozstrzyga ją
    from bpp.models.sloty.core import ISlot

    kalk = ISlot(zwarte_z_dyscyplinami)
    assert kalk.uczelnia == uczelnia
```

(`zwarte_z_dyscyplinami` — istniejący fixture z `conftest.py`, jedna uczelnia.)

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py -k islot -q -p no:cacheprovider`
Expected: FAIL (kalk nie ma `.uczelnia` / brak rozstrzygania / brak wyjątku).

- [ ] **Step 3: Refaktor `ISlot` + helpery**

W `src/bpp/models/sloty/core.py`. Najpierw dodaj import na górze (jeśli brak):
`from .exceptions import CannotAdapt` jest już; dodasz użycie `Uczelnia` lokalnie.

Zamień funkcję `ISlot` (linie 26-293) na `ISlot` + `_rozstrzygnij_uczelnie` +
`_dopasuj_kalkulator`:

```python
def _rozstrzygnij_uczelnie(original):  # noqa
    """ISlot bez jawnej uczelni: zwróć jednoznaczną uczelnię albo CannotAdapt."""
    from bpp.models.uczelnia import Uczelnia

    if Uczelnia.objects.count() == 1:
        return Uczelnia.objects.get()

    uczelnie = list(original.uczelnie_rekordu())
    if len(uczelnie) == 1:
        return uczelnie[0]
    if len(uczelnie) == 0:
        raise CannotAdapt("Rekord nie ma afiliujących autorów z uczelnią.")
    raise CannotAdapt(
        "Rekord ma autorów z wielu uczelni — podaj uczelnię jawnie "
        "(ISlot(rekord, uczelnia=...)); bez niej wynik jest niejednoznaczny."
    )


def ISlot(original, uczelnia=None):  # noqa
    if isinstance(original, Patent):
        raise CannotAdapt("Sloty dla patentów nie są liczone")

    if hasattr(original, "typ_kbn") and original.typ_kbn.skrot == "PW":
        raise CannotAdapt("Sloty dla prac wieloośrodkowych nie są liczone.")

    if hasattr(original, "rok") and original.rok is None:
        raise CannotAdapt("Rekord nie ma ustawionego roku — sloty nie są liczone.")

    if uczelnia is None:
        uczelnia = _rozstrzygnij_uczelnie(original)

    if (
        hasattr(original, "status_korekty_id")
        and original.status_korekty_id in uczelnia.ukryte_statusy("sloty")
    ):
        raise CannotAdapt(
            "Sloty nie będą liczone, zgodnie z ustawieniami obiektu Uczelnia dla ukrywanych "
            "statusów korekt. "
        )

    kalkulator = _dopasuj_kalkulator(original)
    kalkulator.uczelnia = uczelnia
    return kalkulator
```

Następnie utwórz `_dopasuj_kalkulator(original)` zawierający DOKŁADNIE dotychczasową
logikę selekcji — blok od `if isinstance(original, Wydawnictwo_Ciagle):`
(obecna linia 54) do końcowych `raise CannotAdapt(...)` (linie 288-293), bez zmian
wewnętrznych (konstrukcje kalkulatorów zostają `(original)` / `(original, tryb, ...)`).
Usuwasz przy okazji stary blok `if uczelnia is None: uczelnia = Uczelnia.objects.get_default()`
(linie 33-39) — przeniesione/zastąpione przez `_rozstrzygnij_uczelnie`.

```python
def _dopasuj_kalkulator(original):  # noqa
    if isinstance(original, Wydawnictwo_Ciagle):
        ...  # 1:1 przeniesione linie 54-... (cala logika ciagle)
    elif isinstance(original, Wydawnictwo_Zwarte):
        ...  # 1:1 logika zwarte
    if hasattr(original, "rok") and hasattr(original, "punkty_kbn"):
        raise CannotAdapt(
            f"Nie umiem policzyc dla {original} rok {original.rok} punkty_kbn {original.punkty_kbn}"
        )
    raise CannotAdapt(f"Nie umiem policzyć dla obiektu: {original!r}")
```

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py -k islot -q -p no:cacheprovider`
Expected: PASS (3 testy).

- [ ] **Step 5: Sanity — istniejące testy slotów dalej zielone**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_sloty.py src/bpp/tests/test_models/test_sloty/test_sloty_wydawnictwo_zwarte.py src/bpp/tests/test_models/test_sloty/test_sloty_wydawnictwo_ciagle.py -q -p no:cacheprovider`
Expected: PASS (refaktor zachowawczy; single-uczelnia rozstrzyga jak get_default).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/bpp/models/sloty/core.py
git add src/bpp/models/sloty/core.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "refactor(multi-hosted): ISlot opcjonalna uczelnia + rozstrzyganie + helper"
```

---

## Task 5: `IPunktacjaCacher` — bez uczelni, pętla per uczelnia, tag, det. serialize

**Files:**
- Modify: `src/bpp/models/sloty/core.py` (klasa `IPunktacjaCacher`)
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`

- [ ] **Step 1: Napisz failing test (rebuild per uczelnia)**

```python
@pytest.mark.django_db
def test_rebuild_tworzy_wiersze_per_uczelnia(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia
):
    from bpp.models.cache import (
        Cache_Punktacja_Autora,
        Cache_Punktacja_Dyscypliny,
    )
    from bpp.models.sloty.core import IPunktacjaCacher

    cacher = IPunktacjaCacher(zwarte_dwie_uczelnie)
    cacher.removeEntries()
    cacher.rebuildEntries()

    cpd = Cache_Punktacja_Dyscypliny.objects.filter(
        rekord_id=[cacher.ctype, zwarte_dwie_uczelnie.pk]
    )
    assert cpd.count() == 2
    assert set(cpd.values_list("uczelnia_id", flat=True)) == {
        jednostka.uczelnia_id,
        druga_uczelnia.pk,
    }
    for row in cpd:
        assert len(row.autorzy_z_dyscypliny) == 1

    cpa = Cache_Punktacja_Autora.objects.filter(
        rekord_id=[cacher.ctype, zwarte_dwie_uczelnie.pk]
    )
    assert cpa.count() == 2
    assert {c.jednostka.uczelnia_id for c in cpa} == {
        jednostka.uczelnia_id,
        druga_uczelnia.pk,
    }
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_rebuild_tworzy_wiersze_per_uczelnia -q -p no:cacheprovider`
Expected: FAIL (1 wiersz dyscypliny / `uczelnia_id` None / `cross-uczelnia` CannotAdapt w canAdapt).

- [ ] **Step 3: Przepisz `IPunktacjaCacher`**

W `src/bpp/models/sloty/core.py`, klasa `IPunktacjaCacher`. `__init__` traci
`uczelnia`; `canAdapt` opiera się o `_dopasuj_kalkulator` (uczelnia-niezależne,
nie wpada w rozstrzyganie); `removeEntries` kasuje cały rekord; nowe
`rebuildEntries` + `_uczelnie_do_przeliczenia` + `_zapisz`; `serialize`
deterministyczny.

```python
    def __init__(self, original):
        self.original = original

    def canAdapt(self):
        try:
            _dopasuj_kalkulator(self.original)
            return True
        except CannotAdapt:
            return False
```

`removeEntries` (kasuje całość po rekord_id — sprząta sieroty):

```python
    @transaction.atomic
    def removeEntries(self):
        self.cache_punktacja_dyscypliny.delete()
        self.cache_punktacja_autora.delete()
```

`serialize` (deterministyczny — uczelnia + pk jako tie-breaker):

```python
    def serialize(self):
        ret1 = [
            elem.serialize()
            for elem in self.cache_punktacja_autora.order_by(
                "jednostka__uczelnia_id", "autor__nazwisko", "dyscyplina__nazwa", "pk"
            )
        ]
        ret2 = [
            elem.serialize()
            for elem in self.cache_punktacja_dyscypliny.order_by(
                "uczelnia_id", "dyscyplina__nazwa", "pk"
            )
        ]
        return ret1, ret2
```

`rebuildEntries` + helpery:

```python
    def _uczelnie_do_przeliczenia(self):
        from bpp.models.uczelnia import Uczelnia

        if Uczelnia.objects.count() == 1:  # fast-track single-install
            return Uczelnia.objects.all()
        return self.original.uczelnie_rekordu()

    @transaction.atomic
    def rebuildEntries(self):
        for uczelnia in self._uczelnie_do_przeliczenia():
            try:
                kalk = ISlot(self.original, uczelnia=uczelnia)
            except CannotAdapt:
                continue  # nie liczy się (typ/punkty/rok) lub ukryty status
            self._zapisz(kalk, uczelnia)

    def _zapisz(self, kalk, uczelnia):
        pk = self.get_pk()

        for dyscyplina in kalk.dyscypliny:
            azd = kalk.autorzy_z_dyscypliny(dyscyplina)
            if not azd:
                continue
            Cache_Punktacja_Dyscypliny.objects.create(
                rekord_id=[pk[0], pk[1]],
                dyscyplina=dyscyplina,
                uczelnia=uczelnia,
                pkd=kalk.punkty_pkd(dyscyplina),
                slot=kalk.slot_dla_dyscypliny(dyscyplina),
                autorzy_z_dyscypliny=[a.pk for a in azd],
                zapisani_autorzy_z_dyscypliny=[a.zapisany_jako for a in azd],
            )

        if not self.original.pk:
            return

        for wa in self.original.autorzy_set.filter(jednostka__uczelnia=uczelnia):
            if (
                not wa.afiliuje
                or not wa.jednostka.skupia_pracownikow
                or not wa.przypieta
                or not wa.rodzaj_autora_uwzgledniany_w_kalkulacjach_slotow()
            ):
                continue

            dyscyplina = wa.okresl_dyscypline()
            if dyscyplina is None:
                continue

            pkdaut = kalk.pkd_dla_autora(wa)
            if pkdaut is None:
                continue
            Cache_Punktacja_Autora.objects.create(
                rekord_id=[pk[0], pk[1]],
                autor_id=wa.autor_id,
                jednostka_id=wa.jednostka_id,
                dyscyplina_id=dyscyplina.pk,
                pkdaut=pkdaut,
                slot=kalk.slot_dla_autora_z_dyscypliny(dyscyplina),
            )
```

USUŃ stare `rebuildEntries` i (jeśli był) atrybut `self.slot`/`self.uczelnia`.
Zostaw właściwości `ctype`, `cache_punktacja_autora`, `cache_punktacja_dyscypliny`,
`get_pk`.

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_rebuild_tworzy_wiersze_per_uczelnia -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/bpp/models/sloty/core.py
git add src/bpp/models/sloty/core.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "feat(multi-hosted): IPunktacjaCacher petla per uczelnia + tag + det. serialize"
```

---

## Task 6: `przelicz_punkty_dyscyplin` — bez parametru, bez `get_default`

**Files:**
- Modify: `src/bpp/models/abstract/disciplines.py:12-27`
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`

- [ ] **Step 1: Napisz failing testy (per uczelnia, dzielnik, determinizm)**

```python
@pytest.mark.django_db
def test_przelicz_per_uczelnia_dzielnik_k1(zwarte_dwie_uczelnie):
    from bpp.models.cache import Cache_Punktacja_Autora

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()

    cpa_nowak = Cache_Punktacja_Autora.objects.get(autor__nazwisko="Nowak")
    cpa_kowalski = Cache_Punktacja_Autora.objects.get(autor__nazwisko="Kowalski")
    # k=1 w obrębie każdej uczelni => każdy ma pełny slot, suma = 2.0
    assert cpa_nowak.slot == cpa_kowalski.slot
    assert cpa_nowak.slot + cpa_kowalski.slot == 2


@pytest.mark.django_db
def test_przelicz_zwrotka_deterministyczna(zwarte_dwie_uczelnie):
    a = zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    b = zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    assert str(a) == str(b)
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py -k przelicz -q -p no:cacheprovider`
Expected: FAIL (stary `przelicz` ma get_default/uczelnia=None single-pass).

- [ ] **Step 3: Przepisz `przelicz_punkty_dyscyplin`**

W `src/bpp/models/abstract/disciplines.py` zamień metodę (usuń blok
`Uczelnia.objects.get_default()`):

```python
    def przelicz_punkty_dyscyplin(self):
        from bpp.models.sloty.core import IPunktacjaCacher

        ipc = IPunktacjaCacher(self)
        ipc.removeEntries()
        if ipc.canAdapt():
            ipc.rebuildEntries()
        return ipc.serialize()
```

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py -k przelicz -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/bpp/models/abstract/disciplines.py
git add src/bpp/models/abstract/disciplines.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "feat(multi-hosted): przelicz_punkty_dyscyplin bez parametru, bez get_default"
```

---

## Task 7: Migracja widoku SQL — join po uczelni

**Files:**
- Create: `src/bpp/migrations/0425_per_uczelnia_cache_view.py`
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`

- [ ] **Step 1: Napisz failing test (brak kartezjańskiej duplikacji)**

```python
@pytest.mark.django_db
def test_widok_nie_duplikuje_miedzy_uczelniami(zwarte_dwie_uczelnie):
    from django.contrib.contenttypes.models import ContentType

    from bpp.models.cache import Cache_Punktacja_Autora_Query_View

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    ctype = ContentType.objects.get_for_model(zwarte_dwie_uczelnie).pk

    rows = Cache_Punktacja_Autora_Query_View.objects.filter(
        rekord_id=[ctype, zwarte_dwie_uczelnie.pk]
    )
    # 2 autorow x 2 dyscyplina-agregaty bez joina po uczelni = 4 (kartezjan).
    # Z naprawą: 2.
    assert rows.count() == 2
```

- [ ] **Step 2: Uruchom — ma FAILOWAĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_widok_nie_duplikuje_miedzy_uczelniami -q -p no:cacheprovider`
Expected: FAIL (`assert 4 == 2`).

- [ ] **Step 3: Utwórz migrację widoku**

Utwórz `src/bpp/migrations/0425_per_uczelnia_cache_view.py`. **Ustaw `dependencies`
na faktyczną nazwę migracji z Tasku 1** (zamień `0424_...`):

```python
from django.db import migrations

DROP = "DROP VIEW IF EXISTS bpp_cache_punktacja_autora_view;"

CREATE_NEW = """
CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT a.id,
       a.rekord_id,
       a.pkdaut,
       a.slot,
       a.autor_id,
       a.dyscyplina_id,
       a.jednostka_id,
       d.autorzy_z_dyscypliny,
       d.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora a
JOIN bpp_jednostka j ON j.id = a.jednostka_id
JOIN bpp_cache_punktacja_dyscypliny d
  ON a.rekord_id = d.rekord_id
 AND a.dyscyplina_id = d.dyscyplina_id
 AND d.uczelnia_id = j.uczelnia_id;
"""

CREATE_OLD = """
CREATE VIEW bpp_cache_punktacja_autora_view AS
SELECT bpp_cache_punktacja_autora.id,
       bpp_cache_punktacja_autora.rekord_id,
       bpp_cache_punktacja_autora.pkdaut,
       bpp_cache_punktacja_autora.slot,
       bpp_cache_punktacja_autora.autor_id,
       bpp_cache_punktacja_autora.dyscyplina_id,
       bpp_cache_punktacja_autora.jednostka_id,
       bpp_cache_punktacja_dyscypliny.autorzy_z_dyscypliny,
       bpp_cache_punktacja_dyscypliny.zapisani_autorzy_z_dyscypliny
FROM bpp_cache_punktacja_autora,
     bpp_cache_punktacja_dyscypliny
WHERE bpp_cache_punktacja_autora.rekord_id = bpp_cache_punktacja_dyscypliny.rekord_id
  AND bpp_cache_punktacja_autora.dyscyplina_id = bpp_cache_punktacja_dyscypliny.dyscyplina_id;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("bpp", "0424_..."),  # <- nazwa wygenerowana w Tasku 1
    ]

    operations = [
        migrations.RunSQL(sql=DROP + CREATE_NEW, reverse_sql=DROP + CREATE_OLD),
    ]
```

- [ ] **Step 4: Uruchom — ma PRZEJŚĆ**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py::test_widok_nie_duplikuje_miedzy_uczelniami -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Brak dryfu migracji**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: "No changes detected".

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff check src/bpp/migrations/0425_per_uczelnia_cache_view.py
git add src/bpp/migrations/0425_per_uczelnia_cache_view.py src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "feat(multi-hosted): widok cache_punktacja_autora joinuje po uczelni"
```

---

## Task 8: Testy graniczne — ukryte_statusy, wypadnięcie uczelni, invariant

**Files:**
- Test: `src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py`

- [ ] **Step 1: Test — `ukryte_statusy` gatuje jedną uczelnię**

Sprawdź w `src/bpp/models/uczelnia.py` API `ukryte_statusy("sloty")` i ustaw
ukryty status dla `druga_uczelnia`. Asercja: po przeliczeniu są wiersze dla
`jednostka.uczelnia`, NIE ma dla `druga_uczelnia`.

```python
@pytest.mark.django_db
def test_ukryte_statusy_gatuje_jedna_uczelnie(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia
):
    from bpp.models.cache import Cache_Punktacja_Dyscypliny
    from bpp.models.sloty.core import IPunktacjaCacher

    # Ukryj status korekty pracy dla slotów w drugiej uczelni.
    # API ustawiania sprawdź w uczelnia.py (np. pole/relacja statusów); poniżej
    # zastąp realnym mechanizmem:
    status = zwarte_dwie_uczelnie.status_korekty
    druga_uczelnia.ukryj_status_dla_slotow(status)  # <- realne API z uczelnia.py

    ctype = IPunktacjaCacher(zwarte_dwie_uczelnie).ctype
    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()

    uczelnie = set(
        Cache_Punktacja_Dyscypliny.objects.filter(
            rekord_id=[ctype, zwarte_dwie_uczelnie.pk]
        ).values_list("uczelnia_id", flat=True)
    )
    assert jednostka.uczelnia_id in uczelnie
    assert druga_uczelnia.pk not in uczelnie
```

Jeśli `ukryte_statusy` nie ma wygodnego settera — odczytaj implementację i ustaw
stan ręcznie. NIE pomijaj testu (kluczowy wymóg spec).

- [ ] **Step 2: Test — wypadnięcie uczelni (brak sierot)**

```python
@pytest.mark.django_db
def test_wypadniecie_uczelni_kasuje_sieroty(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia
):
    from bpp.models.cache import Cache_Punktacja_Dyscypliny
    from bpp.models.sloty.core import IPunktacjaCacher

    ctype = IPunktacjaCacher(zwarte_dwie_uczelnie).ctype
    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    assert (
        Cache_Punktacja_Dyscypliny.objects.filter(
            rekord_id=[ctype, zwarte_dwie_uczelnie.pk]
        ).count()
        == 2
    )

    wa = zwarte_dwie_uczelnie.autorzy_set.get(autor__nazwisko="Kowalski")
    wa.jednostka = jednostka
    wa.save()

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    uczelnie = set(
        Cache_Punktacja_Dyscypliny.objects.filter(
            rekord_id=[ctype, zwarte_dwie_uczelnie.pk]
        ).values_list("uczelnia_id", flat=True)
    )
    assert uczelnie == {jednostka.uczelnia_id}  # brak sieroty druga_uczelnia
```

- [ ] **Step 3: Test — invariant single-install (k=2 w jednej uczelni)**

```python
@pytest.mark.django_db
def test_invariant_jedna_uczelnia_k2(
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    rodzaj_autora_n,
    charaktery_formalne,
    wydawca,
    typy_odpowiedzialnosci,
    rok,
):
    from bpp.models.cache import Cache_Punktacja_Autora

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, dyscyplina_naukowa=dyscyplina1, rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1, rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_zwarte.punkty_kbn = 20
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(skrot="KSP")
    wydawnictwo_zwarte.save()

    wydawnictwo_zwarte.przelicz_punkty_dyscyplin()
    slots = list(
        Cache_Punktacja_Autora.objects.filter(
            autor__in=[autor_jan_nowak, autor_jan_kowalski]
        ).values_list("slot", flat=True)
    )
    assert len(slots) == 2
    assert sum(slots) == 1  # k=2 w jednej uczelni: po pół slotu, suma 1.0
```

- [ ] **Step 4: Uruchom wszystkie nowe testy graniczne**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff check src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git add src/bpp/tests/test_models/test_sloty/test_per_uczelnia.py
git commit -m "test(multi-hosted): ukryte_statusy/wypadniecie uczelni/invariant single-install"
```

---

## Task 9: Regresja całościowa + dokumentacja backfillu

**Files:**
- Modify: `docs/deweloper/audyt-multihosted-pbn.md`

- [ ] **Step 1: Pełna regresja slotów i cache (invariant liczb)**

Run: `uv run pytest src/bpp/tests/test_models/test_sloty/ src/bpp/tests/test_cache/ -q -p no:cacheprovider`
Expected: PASS. Jeśli istniejący test asertuje stary `Cache_Punktacja_Dyscypliny.serialize()`
(4 elementy) — zaktualizuj o `uczelnia_id` (oczekiwana zmiana kontraktu).

- [ ] **Step 2: Regresja konsumentów write-path (admin/pin-unpin/optymalizuj)**

Run: `uv run pytest src/ewaluacja_metryki/ src/ewaluacja_optymalizuj_publikacje/ -q -p no:cacheprovider`
Expected: PASS (single-install: `IPunktacjaCacher(x).removeEntries();
rebuildEntries()` liczy tę jedną uczelnię, identycznie).

- [ ] **Step 3: Regresja modułu optymalizacji (symulacje konstruują cacher)**

Run: `uv run pytest src/ewaluacja_optymalizacja/ -q -p no:cacheprovider`
Expected: PASS (callerzy `IPunktacjaCacher(x)` bez zmian; single-install OK).

- [ ] **Step 4: System check + brak dryfu migracji**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run`
Expected: "No changes detected".

- [ ] **Step 5: Udokumentuj backfill (deploy)**

W `docs/deweloper/audyt-multihosted-pbn.md` dopisz sekcję:

```markdown
## Backfill per-uczelnia cache (write-side)

Migracje dodają nullable `uczelnia` na Cache_Punktacja_Dyscypliny i naprawiają
widok. Po deployu należy **przeliczyć cache** pełnym denorm rebuildem — nowy kod
zapisze wiersze per uczelnia. Single-install: liczby identyczne.

Wyzwolenie: rebuild pól denorm (`cached_punkty_dyscyplin`) — komendą denorm
rebuild używaną w projekcie lub `denorms.flush()` w shellu. Konkretną komendę
potwierdzić w środowisku docelowym.

Opcjonalnie później: migracja zacieśniająca `uczelnia` do `null=False`.
```

- [ ] **Step 6: Commit**

```bash
git add docs/deweloper/audyt-multihosted-pbn.md
git commit -m "docs(multi-hosted): backfill per-uczelnia cache + regresja write-side"
```

---

## Self-review (autor planu)

**Spec coverage:**
- Schemat (uczelnia FK + index + serialize) → Task 1 ✓
- SlotMixin/Zwarte filtr autorów → Task 2 ✓
- uczelnie_rekordu → Task 3 ✓
- ISlot opcjonalna uczelnia + _rozstrzygnij_uczelnie + gate + bez get_default → Task 4 ✓
- IPunktacjaCacher bez uczelni + pętla + fast-track + tag + det. serialize → Task 5 ✓
- przelicz_punkty_dyscyplin bez parametru → Task 6 ✓
- Widok SQL join po uczelni → Task 7 ✓
- Testy: 2-uczelnie/dzielnik, rozstrzyganie/ambiguous, ukryte_statusy, widok, wypadnięcie, invariant, determinizm → Task 2/4/5/6/7/8 ✓
- Migracja + backfill → Task 1 (nullable) + Task 9 (doc) ✓
- Callerzy bez zmian (brak parametru uczelni) → potwierdzone; regresja Task 9 ✓

**Type/nazwy — spójność:**
- `ISlot(original, uczelnia=None)`, `_rozstrzygnij_uczelnie`, `_dopasuj_kalkulator`,
  `IPunktacjaCacher(original)`, `_uczelnie_do_przeliczenia`, `_zapisz(kalk, uczelnia)`,
  `uczelnie_rekordu()`, `Cache_Punktacja_Dyscypliny.uczelnia` — używane spójnie.

**Znane luki / uwagi wykonawcy:**
- Task 7 zależność migracji: wstaw realną nazwę `0424_*` z Tasku 1.
- Task 4 Step 3: `_dopasuj_kalkulator` to przeniesienie 1:1 linii 54-293 — NIE
  zmieniaj treści, tylko wytnij do osobnej funkcji.
- Task 8 Step 1: API `ukryte_statusy` sprawdź w `uczelnia.py`; placeholder
  `ukryj_status_dla_slotow` zastąp realnym. Testu NIE pomijać.
- Task 9 Step 1: część istniejących testów może asertować stary `serialize()` —
  aktualizacja o `uczelnia_id` oczekiwana.
- `canAdapt()` przez `_dopasuj_kalkulator` jest uczelnia-niezależne (nie wpada w
  rozstrzyganie); dla rekordu PW może zwrócić True, a `rebuildEntries` i tak nic
  nie zapisze (ISlot rzuci CannotAdapt w pętli) — zachowanie poprawne.
