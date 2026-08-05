# Import pracowników/jednostek — scoping do uczelni z requestu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Na multi-hosted import pracowników i jednostek działa wyłącznie w
zakresie uczelni bieżącego requestu; brak uczelni → redirect na home; profile
mapowania są per-uczelnia.

**Architecture:** View-mixin (`WymagajUczelniZRequestuMixin`) bramkuje wszystkie
widoki modułu (brak `get_for_request` → redirect) i sprawdza przynależność
obiektu do bieżącej uczelni (obcy → 404). Zbiory (lista importów, pule profili)
filtrowane managerem/classmethodą o semantyce `uczelnia_do_integracji`
(multi-tenant ściśle `uczelnia=U`; single-tenant także legacy `NULL`).
`ProfilMapowania` dostaje FK `uczelnia` + `unique_together`.

**Tech Stack:** Django, braces `GroupRequiredMixin`, model_bakery, pytest.

## Global Constraints

- Python: `uv run` przed KAŻDYM poleceniem python/pytest. Nigdy goły `python`.
- Max line length: 88 znaków (ruff).
- Testy: pytest, standalone funkcje, `@pytest.mark.django_db`, `baker.make`.
  Uruchamiaj z `-n auto`, output do pliku w scratchpad + grep (nigdy 2×).
- NIE modyfikować WYDANYCH migracji; nowe migracje na `dev` można edytować.
- Django `{# #}` jednoliniowe (nie dotyczy tego zadania — brak zmian w szablonach).
- Baseline: `make baseline-update` TYLKO przy scalaniu do `dev`, nie w tej gałęzi.
- Komentarze/docstringi po polsku, zwięźle (konwencja modułu).
- Gałąź: `feat/import-multihosted-uczelnia-scoping` (już utworzona z `dev`).
- Newsfragment po każdej zmianie feature/bugfix (`src/bpp/newsfragments/`).

## Kontekst — punkty w istniejącym kodzie

`src/import_pracownikow/views.py` — klasy widoków (wszystkie za
`GroupRequiredMixin`, owner-scoped):

- `ListaImportowView` (118) — `get_queryset` 130-133 `filter(owner=user)`.
- `NowyImportView` (136) — `form_valid` 160-174 ustawia `uczelnia =
  get_for_request` (169).
- `MapowanieView` (186) — `object` 194-198 (`owner=user`); `get_form_kwargs`
  234-247 woła `dopasuj_profil`/`wybierz_profil_fallback` (237-239);
  `form_valid` 259-313 zapisuje profil (295-302) i stempluje 306-310.
- `_ImportPodgladMixin` (316) — `parent_object` 325-330 (owner-or-super).
  Dzieci: `_WierszImportuMixin`, `WybierzKandydataView`, `DopasujAutoraView`,
  `PrzelaczUtworzNowegoView`, `PrzepnijPraceView`,
  `ZaznaczWszystkiePrzepieciaView`, `PrzelaczOdpiecieView`,
  `ZaznaczOdpieciaView`.
- `ImportPracownikowResultsView` (650) — `parent_object` 662-667 (owner-or-super).
- `PodgladImportuView` (736) — `get_object` 750-754 (owner-or-super).
- `OdpieciaView` (833) — `parent_object` 845-850 (owner-or-super).
- `LogZmianView` (866) — `parent_object` 882-887 (owner-or-super).
- `WeryfikacjaJednostekView` (910), `WeryfikacjaTytulowView` (1075),
  `WeryfikacjaStopniView` (1188), `WeryfikacjaStanowiskView` (1286) —
  każdy `parent_object` (owner-or-super), identyczny wzorzec.
- `_PkOwnerRestartMixin` (1386) — `get_object` 1401-1404 (`owner=user`).
  Dzieci: `ZatwierdzImportView`, `RestartAnalizaView`.
- `_pobierz_wlasny_import` (1576) — funkcja modułowa (owner-or-super);
  używana przez `PobierzOryginalView` (1584), `PobierzPoImporcieView` (1601).

Import strony głównej: `django_bpp/urls.py:356` `name="root"`.

`src/import_pracownikow/mapping.py` — `dopasuj_profil(naglowki)` (271),
`wybierz_profil_fallback(naglowki, prog=0.5)` (294). Jedyny prod-caller:
`views.py:237`.

`src/import_pracownikow/models.py` — `ProfilMapowania` (1440-1461):
`nazwa` (unique=True), `mapowanie`, `ostatnio_uzyty`, `utworzony_przez`.
`ImportPracownikow.uczelnia_do_integracji()` (684-699).

Ostatnia migracja: `import_pracownikow/migrations/0026_importpracownikow_uczelnia.py`.

---

### Task 1: `ProfilMapowania` per-uczelnia — model + manager + migracja + backfill

**Files:**
- Modify: `src/import_pracownikow/models.py` (`ProfilMapowania` 1440-1461; dodaj import `Q` jeśli brak)
- Create: `src/import_pracownikow/migrations/0027_profil_uczelnia.py`
- Test: `src/import_pracownikow/tests/test_models/test_profil_uczelnia.py`

**Interfaces:**
- Produces: `ProfilMapowania.uczelnia` (FK, null=True); manager
  `ProfilMapowania.objects.dla_uczelni(uczelnia) -> QuerySet`;
  `Meta.unique_together = (("uczelnia", "nazwa"),)`.

- [ ] **Step 1: Napisz failing testy managera + unique_together**

`src/import_pracownikow/tests/test_models/test_profil_uczelnia.py`:

```python
"""``ProfilMapowania`` per-uczelnia: manager ``dla_uczelni`` + unique_together."""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.models import ProfilMapowania


@pytest.mark.django_db
def test_dla_uczelni_multi_tenant_sciśle():
    """>1 uczelnia: ``dla_uczelni(A)`` zwraca tylko profile A (nie B, nie NULL)."""
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    p_a = baker.make(ProfilMapowania, nazwa="A", uczelnia=a)
    baker.make(ProfilMapowania, nazwa="B", uczelnia=b)
    baker.make(ProfilMapowania, nazwa="Legacy", uczelnia=None)
    wynik = set(ProfilMapowania.objects.dla_uczelni(a))
    assert wynik == {p_a}


@pytest.mark.django_db
def test_dla_uczelni_single_tenant_zawiera_null():
    """Jedna uczelnia: ``dla_uczelni(A)`` zwraca profile A ORAZ legacy NULL."""
    a = baker.make(Uczelnia)
    Uczelnia.objects.exclude(pk=a.pk).delete()
    p_a = baker.make(ProfilMapowania, nazwa="A", uczelnia=a)
    p_legacy = baker.make(ProfilMapowania, nazwa="Legacy", uczelnia=None)
    wynik = set(ProfilMapowania.objects.dla_uczelni(a))
    assert wynik == {p_a, p_legacy}


@pytest.mark.django_db
def test_ta_sama_nazwa_na_dwoch_uczelniach():
    """``unique_together (uczelnia, nazwa)`` dopuszcza tę samą nazwę na 2 uczelniach."""
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    baker.make(ProfilMapowania, nazwa="Kwartalny", uczelnia=a)
    baker.make(ProfilMapowania, nazwa="Kwartalny", uczelnia=b)  # nie rzuca
    assert ProfilMapowania.objects.filter(nazwa="Kwartalny").count() == 2
```

- [ ] **Step 2: Uruchom — ma paść (brak `uczelnia`/`dla_uczelni`)**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_profil_uczelnia.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t1.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t1.log | tail -3`
Expected: FAIL (`ProfilMapowania() got unexpected keyword 'uczelnia'` / brak `dla_uczelni`).

- [ ] **Step 3: Dodaj FK, manager, unique_together do modelu**

W `src/import_pracownikow/models.py` — upewnij się, że `Q` jest zaimportowane
(`from django.db.models import ... Q`). Zamień klasę `ProfilMapowania`
(1440-1461) na:

```python
class ProfilMapowaniaManager(models.Manager):
    def dla_uczelni(self, uczelnia):
        """Profile widoczne dla danej uczelni. Multi-tenant: ściśle
        ``uczelnia=U``. Single-tenant: także legacy ``NULL`` (jak
        ``ImportPracownikow.uczelnia_do_integracji`` — NULL należy do jedynej
        uczelni). Bez ``uczelnia`` (None) → pusty zbiór (bramka i tak blokuje)."""
        from bpp.models import Uczelnia

        if uczelnia is None:
            return self.none()
        if Uczelnia.objects.exclude(pk=uczelnia.pk).exists():
            return self.filter(uczelnia=uczelnia)
        return self.filter(Q(uczelnia=uczelnia) | Q(uczelnia__isnull=True))


class ProfilMapowania(models.Model):
    """Zapisywalne mapowanie nagłówków pliku → pola systemowe, do reużycia
    przy powtarzalnych plikach (ta sama uczelnia co kwartał).

    Multi-hosted: profil należy do KONKRETNEJ uczelni (FK ``uczelnia``) —
    auto-dopasowanie i „ostatnio użyty" (``mapping.dopasuj_profil`` /
    ``wybierz_profil_fallback``) widzą wyłącznie profile bieżącej uczelni
    (zero przecieku między uczelniami). ``NULL`` = legacy (sprzed migracji
    0027) / single-tenant."""

    nazwa = models.CharField(max_length=200)
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="uczelnia",
        help_text="Uczelnia, do której należy profil (multi-hosted). NULL dla "
        "profili sprzed migracji 0027 / instalacji single-tenant.",
    )
    mapowanie = models.JSONField(default=dict)
    ostatnio_uzyty = models.DateTimeField(null=True, blank=True)
    utworzony_przez = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    objects = ProfilMapowaniaManager()

    class Meta:
        verbose_name = "profil mapowania importu pracowników"
        verbose_name_plural = "profile mapowania importu pracowników"
        ordering = ["nazwa"]
        unique_together = (("uczelnia", "nazwa"),)

    def __str__(self):
        return self.nazwa
```

- [ ] **Step 4: Wygeneruj migrację i dopisz backfill**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations import_pracownikow --name profil_uczelnia`

Następnie ROZSZERZ wygenerowany plik `0027_profil_uczelnia.py`: między
`AddField(uczelnia)` a `AlterUniqueTogether`/`AlterField(nazwa)` wstaw
`RunPython` backfill. Docelowa kolejność operacji:

```python
from django.db import migrations, models
import django.db.models.deletion


def backfill_uczelnia(apps, schema_editor):
    """Single-tenant: przypisz jedyną uczelnię wszystkim NULL-owym
    ProfilMapowania i ImportPracownikow (bez tego ścisłe filtrowanie po
    uczelni ukryłoby legacy-rekordy). 0 lub >1 uczelni → no-op (rekordy nowe
    są już ostemplowane, a jednoznacznej uczelni brak)."""
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    if Uczelnia.objects.count() != 1:
        return
    u = Uczelnia.objects.get()
    apps.get_model("import_pracownikow", "ProfilMapowania").objects.filter(
        uczelnia__isnull=True
    ).update(uczelnia=u)
    apps.get_model("import_pracownikow", "ImportPracownikow").objects.filter(
        uczelnia__isnull=True
    ).update(uczelnia=u)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0001_initial"),  # zamień na realny ostatni bpp wg autogen (patrz niżej)
        ("import_pracownikow", "0026_importpracownikow_uczelnia"),
    ]
    operations = [
        migrations.AddField(
            model_name="profilmapowania",
            name="uczelnia",
            field=models.ForeignKey(
                blank=True,
                help_text="Uczelnia, do której należy profil (multi-hosted). "
                "NULL dla profili sprzed migracji 0027 / instalacji single-tenant.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.uczelnia",
                verbose_name="uczelnia",
            ),
        ),
        migrations.RunPython(backfill_uczelnia, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="profilmapowania",
            name="nazwa",
            field=models.CharField(max_length=200),
        ),
        migrations.AlterUniqueTogether(
            name="profilmapowania",
            unique_together={("uczelnia", "nazwa")},
        ),
    ]
```

Uwaga: `dependencies` na `bpp` skopiuj z tego, co wygeneruje `makemigrations`
(autogen wstawi realny ostatni numer migracji `bpp` z powodu FK do `bpp.Uczelnia`).
NIE zgaduj — użyj wartości z autogen.

- [ ] **Step 5: Uruchom testy — mają przejść**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_profil_uczelnia.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t1.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t1.log | tail -3`
Expected: 3 passed.

- [ ] **Step 6: Test backfillu (osobny, bo zależy od migracji)**

Dopisz do `test_profil_uczelnia.py`:

```python
@pytest.mark.django_db
def test_backfill_single_tenant(django_assert_num_queries=None):
    """Symulacja backfillu: jedna uczelnia + NULL profil/import → przypisane."""
    from import_pracownikow.migrations import _backfill_helpers  # noqa
```

UWAGA: testowanie `RunPython` bezpośrednio jest kruche. Zamiast tego przetestuj
LOGIKĘ backfillu przez wydzielenie jej — jeśli nie chcesz importować z migracji,
pomiń ten krok i polegaj na `make baseline-update` (waliduje migrację na czystym
kontenerze) przy merge. **Zalecane: pomiń Step 6**, backfill zweryfikuje
`baseline-update` przy scalaniu. Skreśl ten test.

- [ ] **Step 7: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/migrations/0027_profil_uczelnia.py src/import_pracownikow/tests/test_models/test_profil_uczelnia.py
git commit -m "feat(import): ProfilMapowania per-uczelnia (FK + manager dla_uczelni + backfill)"
```

---

### Task 2: `mapping.py` — profile filtrowane po uczelni

**Files:**
- Modify: `src/import_pracownikow/mapping.py` (`dopasuj_profil` 271-291;
  `wybierz_profil_fallback` 294-317)
- Test: `src/import_pracownikow/tests/test_mapping_profil_uczelnia.py`

**Interfaces:**
- Consumes: `ProfilMapowania.objects.dla_uczelni(uczelnia)` (Task 1).
- Produces: `dopasuj_profil(naglowki, uczelnia) -> ProfilMapowania | None`;
  `wybierz_profil_fallback(naglowki, uczelnia, prog=0.5) -> ProfilMapowania | None`.

- [ ] **Step 1: Failing test — profil innej uczelni nie jest zwracany**

`src/import_pracownikow/tests/test_mapping_profil_uczelnia.py`:

```python
"""``dopasuj_profil`` / ``wybierz_profil_fallback`` respektują uczelnię."""

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.mapping import dopasuj_profil, wybierz_profil_fallback
from import_pracownikow.models import ProfilMapowania

MAPOWANIE = {"nazwisko": "nazwisko", "imię": "imię", "jednostka": "nazwa_jednostki"}
NAGLOWKI = ["nazwisko", "imię", "jednostka"]


@pytest.mark.django_db
def test_dopasuj_profil_tylko_biezaca_uczelnia():
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    p_a = baker.make(ProfilMapowania, nazwa="A", uczelnia=a, mapowanie=MAPOWANIE)
    baker.make(ProfilMapowania, nazwa="B", uczelnia=b, mapowanie=MAPOWANIE)
    assert dopasuj_profil(NAGLOWKI, a) == p_a
    assert dopasuj_profil(NAGLOWKI, b) != p_a


@pytest.mark.django_db
def test_fallback_ostatnio_uzyty_per_uczelnia():
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    baker.make(
        ProfilMapowania, nazwa="B", uczelnia=b, mapowanie=MAPOWANIE,
        ostatnio_uzyty=timezone.now(),
    )
    # Najnowszy globalnie jest B, ale dla A nie wolno go podnieść:
    assert wybierz_profil_fallback(NAGLOWKI, a) is None
```

- [ ] **Step 2: Uruchom — ma paść (sygnatura bez `uczelnia`)**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping_profil_uczelnia.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t2.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t2.log | tail -3`
Expected: FAIL (`dopasuj_profil() takes 1 positional argument but 2 were given`).

- [ ] **Step 3: Dodaj parametr `uczelnia` i filtrowanie**

W `mapping.py` — `dopasuj_profil` (271): zmień sygnaturę i źródło iteracji:

```python
def dopasuj_profil(naglowki, uczelnia):
    """Zwraca ``ProfilMapowania`` bieżącej uczelni, którego zbiór kluczy
    mapowania pokrywa ≥90% znormalizowanych nagłówków pliku (najlepsze
    pokrycie), albo ``None``. Pula zawężona do uczelni (multi-hosted)."""
    from import_pracownikow.models import ProfilMapowania

    zbior_naglowkow = set(naglowki)
    if not zbior_naglowkow:
        return None

    najlepszy = None
    najlepsze_pokrycie = 0.0
    for profil in ProfilMapowania.objects.dla_uczelni(uczelnia):
        klucze = set(profil.mapowanie.keys())
        if not klucze:
            continue
        pokrycie = len(zbior_naglowkow & klucze) / len(zbior_naglowkow)
        if pokrycie >= 0.9 and pokrycie > najlepsze_pokrycie:
            najlepszy = profil
            najlepsze_pokrycie = pokrycie
    return najlepszy
```

`wybierz_profil_fallback` (294): dodaj `uczelnia` i zawęź bazowy queryset:

```python
def wybierz_profil_fallback(naglowki, uczelnia, prog=0.5):
    """NAJNOWSZY ostemplowany profil BIEŻĄCEJ UCZELNI jako fallback — zwracany
    TYLKO gdy pokrywa ≥ ``prog`` swoich kluczy w nagłówkach pliku. Pula
    zawężona do uczelni (multi-hosted) chroni przed nałożeniem cudzego profilu."""
    from import_pracownikow.models import ProfilMapowania

    zbior = set(naglowki)
    if not zbior:
        return None
    profil = (
        ProfilMapowania.objects.dla_uczelni(uczelnia)
        .filter(ostatnio_uzyty__isnull=False)
        .order_by("-ostatnio_uzyty")
        .first()
    )
    if profil is None:
        return None
    klucze = set(profil.mapowanie.keys())
    if not klucze:
        return None
    pokrycie = len(zbior & klucze) / len(klucze)
    return profil if pokrycie >= prog else None
```

- [ ] **Step 4: Uruchom — mają przejść**

Run: `uv run pytest src/import_pracownikow/tests/test_mapping_profil_uczelnia.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t2.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t2.log | tail -3`
Expected: 2 passed.

- [ ] **Step 5: Napraw istniejące testy profili (sygnatura)**

Istniejący `test_profil_ostatnio_uzyty.py` i `test_mapping.py` wołają
`dopasuj_profil(naglowki)` / `wybierz_profil_fallback(naglowki)` bez uczelni.
Znajdź i zaktualizuj:

Run: `grep -rn "dopasuj_profil(\|wybierz_profil_fallback(" src/import_pracownikow/tests/`

Dla każdego wywołania dodaj argument uczelni. Wzorzec: utwórz/pobierz uczelnię
w teście (`u = baker.make(Uczelnia)`; profile twórz z `uczelnia=u`) i wołaj
`dopasuj_profil(naglowki, u)`. Uruchom te pliki i potwierdź zieleń:

Run: `uv run pytest src/import_pracownikow/tests/test_profil_ostatnio_uzyty.py src/import_pracownikow/tests/test_mapping.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t2b.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t2b.log | tail -3`
Expected: wszystkie passed.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/mapping.py src/import_pracownikow/tests/
git commit -m "feat(import): dopasuj_profil/wybierz_profil_fallback filtrują po uczelni"
```

---

### Task 3: `ImportPracownikow.widoczne_dla_uczelni` classmethod

**Files:**
- Modify: `src/import_pracownikow/models.py` (klasa `ImportPracownikow`, dodaj classmethod; upewnij się o imporcie `Q`)
- Test: `src/import_pracownikow/tests/test_models/test_widoczne_dla_uczelni.py`

**Interfaces:**
- Produces: `ImportPracownikow.widoczne_dla_uczelni(uczelnia) -> QuerySet`
  (multi-tenant: `filter(uczelnia=U)`; single-tenant: `Q(uczelnia=U) |
  Q(uczelnia__isnull=True)`).

- [ ] **Step 1: Failing test**

`src/import_pracownikow/tests/test_models/test_widoczne_dla_uczelni.py`:

```python
"""``ImportPracownikow.widoczne_dla_uczelni`` — scoping listy do uczelni."""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_multi_tenant_sciśle():
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    imp_a = baker.make(ImportPracownikow, uczelnia=a)
    baker.make(ImportPracownikow, uczelnia=b)
    baker.make(ImportPracownikow, uczelnia=None)  # legacy — ukryty na multi
    assert set(ImportPracownikow.widoczne_dla_uczelni(a)) == {imp_a}


@pytest.mark.django_db
def test_single_tenant_zawiera_null():
    a = baker.make(Uczelnia)
    Uczelnia.objects.exclude(pk=a.pk).delete()
    imp_a = baker.make(ImportPracownikow, uczelnia=a)
    imp_legacy = baker.make(ImportPracownikow, uczelnia=None)
    assert set(ImportPracownikow.widoczne_dla_uczelni(a)) == {imp_a, imp_legacy}
```

- [ ] **Step 2: Uruchom — ma paść (brak classmethody)**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_widoczne_dla_uczelni.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t3.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t3.log | tail -3`
Expected: FAIL (`AttributeError: ... has no attribute 'widoczne_dla_uczelni'`).

- [ ] **Step 3: Dodaj classmethod (obok `uczelnia_do_integracji`, ~699)**

W `ImportPracownikow`:

```python
    @classmethod
    def widoczne_dla_uczelni(cls, uczelnia):
        """Importy należące do danej uczelni — ORM-owy odpowiednik
        ``uczelnia_do_integracji``. Multi-tenant: ściśle ``uczelnia=U``.
        Single-tenant: także legacy ``NULL`` (należy do jedynej uczelni)."""
        from bpp.models import Uczelnia

        if Uczelnia.objects.exclude(pk=uczelnia.pk).exists():
            return cls.objects.filter(uczelnia=uczelnia)
        return cls.objects.filter(
            Q(uczelnia=uczelnia) | Q(uczelnia__isnull=True)
        )
```

(Jeśli `Q` nie jest importowane w models.py — dodaj do importów `django.db.models`.)

- [ ] **Step 4: Uruchom — mają przejść**

Run: `uv run pytest src/import_pracownikow/tests/test_models/test_widoczne_dla_uczelni.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t3.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t3.log | tail -3`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/models.py src/import_pracownikow/tests/test_models/test_widoczne_dla_uczelni.py
git commit -m "feat(import): ImportPracownikow.widoczne_dla_uczelni (scoping listy)"
```

---

### Task 4: `WymagajUczelniZRequestuMixin` + bramka na liście/nowym imporcie

**Files:**
- Modify: `src/import_pracownikow/views.py` (importy; nowy mixin; `ListaImportowView` 118-133; `NowyImportView` 136-174)
- Test: `src/import_pracownikow/tests/test_views_gate_uczelnia.py`
- Test helper: `src/import_pracownikow/tests/_helpers.py` (dopisz `ustaw_biezaca_uczelnie`)

**Interfaces:**
- Consumes: `Uczelnia.objects.get_for_request`;
  `ImportPracownikow.widoczne_dla_uczelni` (Task 3).
- Produces: `WymagajUczelniZRequestuMixin` z `uczelnia_biezaca`
  (cached_property), `dispatch` (redirect gdy None), `sprawdz_uczelnie(obj)`
  (Http404 gdy `obj.uczelnia_do_integracji() != uczelnia_biezaca`).
- Produces (test): `ustaw_biezaca_uczelnie(uczelnia, settings, host="testserver")`
  — wiąże `uczelnia.site.domain` z hostem klienta, dopisuje do ALLOWED_HOSTS,
  zwraca host do przekazania jako `HTTP_HOST`.

- [ ] **Step 1: Dodaj helper testowy**

W `src/import_pracownikow/tests/_helpers.py` dopisz:

```python
def ustaw_biezaca_uczelnie(uczelnia, settings, host="testserver"):
    """Zwiąż uczelnię z hostem testowego klienta → SiteResolutionMiddleware
    ustawi ``request._uczelnia = uczelnia`` (jak produkcyjne domena→Site→Uczelnia).
    Zwraca host do przekazania jako ``HTTP_HOST`` w client.get/post."""
    uczelnia.site.domain = host
    uczelnia.site.save(update_fields=["domain"])
    if host not in settings.ALLOWED_HOSTS:
        settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + [host]
    return host
```

- [ ] **Step 2: Failing testy bramki**

`src/import_pracownikow/tests/test_views_gate_uczelnia.py`:

```python
"""Bramka „brak uczelni z requestu" — redirect na home dla WSZYSTKICH."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia
from import_pracownikow.models import ImportPracownikow
from import_pracownikow.tests._helpers import ustaw_biezaca_uczelnie


@pytest.mark.django_db
def test_lista_redirect_gdy_brak_uczelni(admin_client):
    """>1 uczelnia + żadna nie zmapowana na host → lista redirectuje na home."""
    baker.make(Uczelnia)
    baker.make(Uczelnia)  # get_for_request → None (brak mapowania, >1)
    resp = admin_client.get(reverse("import_pracownikow:index"))
    assert resp.status_code == 302
    assert resp.url == "/"


@pytest.mark.django_db
def test_lista_ok_gdy_uczelnia_zmapowana(admin_client, settings):
    """Uczelnia zmapowana na host klienta → lista działa (200)."""
    u = baker.make(Uczelnia)
    baker.make(Uczelnia)  # druga, ale host wskazuje na u
    host = ustaw_biezaca_uczelnie(u, settings)
    resp = admin_client.get(reverse("import_pracownikow:index"), HTTP_HOST=host)
    assert resp.status_code == 200


@pytest.mark.django_db
def test_lista_scoped_do_biezacej_uczelni(admin_client, admin_user, settings):
    """Lista pokazuje tylko importy bieżącej uczelni (nie innej)."""
    u = baker.make(Uczelnia)
    inna = baker.make(Uczelnia)
    host = ustaw_biezaca_uczelnie(u, settings)
    moj = baker.make(ImportPracownikow, owner=admin_user, uczelnia=u)
    baker.make(ImportPracownikow, owner=admin_user, uczelnia=inna)
    resp = admin_client.get(reverse("import_pracownikow:index"), HTTP_HOST=host)
    assert list(resp.context["object_list"]) == [moj]
```

- [ ] **Step 3: Uruchom — ma paść (brak bramki: 200 zamiast 302 / zła lista)**

Run: `uv run pytest src/import_pracownikow/tests/test_views_gate_uczelnia.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t4.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t4.log | tail -3`
Expected: FAIL (test_lista_redirect_gdy_brak_uczelni: 200 != 302; scoped: obie na liście).

- [ ] **Step 4: Dodaj mixin + wepnij w listę i nowy import**

W `views.py` dodaj do importów z `django.shortcuts`: `redirect`
(`from django.shortcuts import get_object_or_404, redirect, render`).

Po `GROUP_REQUIRED = "wprowadzanie danych"` (66) dodaj mixin:

```python
class WymagajUczelniZRequestuMixin:
    """Bramka multi-hosted: import działa TYLKO w zakresie uczelni z requestu.

    ``dispatch``: brak uczelni z requestu (``get_for_request`` → None: domena
    bez mapowania Site→Uczelnia albo 0 uczelni) → redirect na home + komunikat.
    Dla WSZYSTKICH (też superusera) — kolejność MRO: ``GroupRequiredMixin`` →
    ten mixin → widok, więc auth/grupa lecą pierwsze.

    ``sprawdz_uczelnie(obj)``: obiekt spoza bieżącej uczelni → Http404
    (semantyka jak ``uczelnia_do_integracji`` — single-tenant łapie legacy NULL)."""

    @cached_property
    def uczelnia_biezaca(self):
        return Uczelnia.objects.get_for_request(self.request)

    def dispatch(self, request, *args, **kwargs):
        if self.uczelnia_biezaca is None:
            messages.error(
                request,
                "Nie ustalono uczelni dla tej domeny — import pracowników i "
                "jednostek jest niedostępny.",
            )
            return redirect("root")
        return super().dispatch(request, *args, **kwargs)

    def sprawdz_uczelnie(self, obj):
        if obj.uczelnia_do_integracji() != self.uczelnia_biezaca:
            raise Http404
```

`ListaImportowView` (118): dodaj mixin i przefiltruj listę:

```python
class ListaImportowView(
    GroupRequiredMixin, WymagajUczelniZRequestuMixin, ListView
):
    ...
    def get_queryset(self):
        return (
            ImportPracownikow.widoczne_dla_uczelni(self.uczelnia_biezaca)
            .filter(owner=self.request.user)
            .order_by("-created_on")
        )
```

`NowyImportView` (136): dodaj mixin; w `form_valid` (169) zamień źródło uczelni:

```python
class NowyImportView(
    GroupRequiredMixin, WymagajUczelniZRequestuMixin, CreateLiveOperationView
):
    ...
        self.object.uczelnia = self.uczelnia_biezaca  # bramka gwarantuje non-None
```

- [ ] **Step 5: Uruchom — mają przejść**

Run: `uv run pytest src/import_pracownikow/tests/test_views_gate_uczelnia.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t4.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t4.log | tail -3`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/tests/_helpers.py src/import_pracownikow/tests/test_views_gate_uczelnia.py
git commit -m "feat(import): bramka WymagajUczelniZRequestuMixin + scoping listy do uczelni"
```

---

### Task 5: Wepnij mixin we WSZYSTKIE widoki + `sprawdz_uczelnie` + profile w MapowanieView

**Files:**
- Modify: `src/import_pracownikow/views.py` (klasy: `MapowanieView`,
  `_ImportPodgladMixin`, `ImportPracownikowResultsView`, `PodgladImportuView`,
  `OdpieciaView`, `LogZmianView`, 4×`Weryfikacja*View`, `_PkOwnerRestartMixin`,
  `PobierzOryginalView`, `PobierzPoImporcieView`)
- Test: `src/import_pracownikow/tests/test_views_gate_uczelnia.py` (dopisz)

**Interfaces:**
- Consumes: `WymagajUczelniZRequestuMixin` (Task 4).

- [ ] **Step 1: Failing test — obcy import 404, profil stemplowany uczelnią**

Dopisz do `test_views_gate_uczelnia.py`:

```python
@pytest.mark.django_db
def test_obiekt_innej_uczelni_404(admin_client, admin_user, settings):
    """Import należący do innej uczelni → 404 (nawet dla superusera)."""
    u = baker.make(Uczelnia)
    inna = baker.make(Uczelnia)
    host = ustaw_biezaca_uczelnie(u, settings)
    obcy = baker.make(
        ImportPracownikow, owner=admin_user, uczelnia=inna,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY,
    )
    url = reverse("import_pracownikow:przeglad", kwargs={"pk": obcy.pk})
    resp = admin_client.get(url, HTTP_HOST=host)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_download_innej_uczelni_404(admin_client, admin_user, settings):
    u = baker.make(Uczelnia)
    inna = baker.make(Uczelnia)
    host = ustaw_biezaca_uczelnie(u, settings)
    obcy = baker.make(ImportPracownikow, owner=admin_user, uczelnia=inna)
    url = reverse("import_pracownikow:pobierz-oryginal", kwargs={"pk": obcy.pk})
    resp = admin_client.get(url, HTTP_HOST=host)
    assert resp.status_code == 404
```

- [ ] **Step 2: Uruchom — ma paść (obcy import wciąż 200/inny kod)**

Run: `uv run pytest src/import_pracownikow/tests/test_views_gate_uczelnia.py -k "innej_uczelni" -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t5.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t5.log | tail -3`
Expected: FAIL (obcy import nie daje 404).

- [ ] **Step 3: Dodaj mixin do baz wszystkich klas + wywołania `sprawdz_uczelnie`**

Do KAŻDEJ z klas wstaw `WymagajUczelniZRequestuMixin` między `GroupRequiredMixin`
a widok generyczny. Lista deklaracji do zmiany:

```python
class MapowanieView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, FormView):
class _ImportPodgladMixin(GroupRequiredMixin, WymagajUczelniZRequestuMixin, View):
class ImportPracownikowResultsView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, ListView):
class PodgladImportuView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, DetailView):
class OdpieciaView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, ListView):
class LogZmianView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, ListView):
class WeryfikacjaJednostekView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, View):
class WeryfikacjaTytulowView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, View):
class WeryfikacjaStopniView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, View):
class WeryfikacjaStanowiskView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, View):
class _PkOwnerRestartMixin(GroupRequiredMixin, WymagajUczelniZRequestuMixin, RestartView):
class PobierzOryginalView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, View):
class PobierzPoImporcieView(GroupRequiredMixin, WymagajUczelniZRequestuMixin, View):
```

W KAŻDYM miejscu, gdzie fetchowany jest obiekt importu, dodaj
`self.sprawdz_uczelnie(obj)` przed `return obj`. Konkretnie:

- `MapowanieView.object` (194-198): po `get_object_or_404(...)` przypisz do
  `obj`, `self.sprawdz_uczelnie(obj)`, `return obj`.
- `_ImportPodgladMixin.parent_object` (325-330): dodaj `self.sprawdz_uczelnie(obj)`
  przed `return obj`.
- `ImportPracownikowResultsView.parent_object` (662-667): j.w.
- `PodgladImportuView.get_object` (750-754): j.w.
- `OdpieciaView.parent_object` (845-850): j.w.
- `LogZmianView.parent_object` (882-887): j.w.
- 4× `Weryfikacja*View.parent_object` (923-927, 1090-1094, 1196-1200,
  1294-1298): j.w.
- `_PkOwnerRestartMixin.get_object` (1401-1404): przypisz do `obj`,
  `self.sprawdz_uczelnie(obj)`, `return obj`.

Wzorzec zamiany (dla `parent_object`/`get_object` z owner-or-super):

```python
    @cached_property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        self.sprawdz_uczelnie(obj)  # multi-hosted: obcy import → 404
        return obj
```

Dla `MapowanieView.object` i `_PkOwnerRestartMixin.get_object` (strict owner):

```python
    @cached_property
    def object(self):
        obj = get_object_or_404(
            ImportPracownikow, pk=self.kwargs["pk"], owner=self.request.user
        )
        self.sprawdz_uczelnie(obj)
        return obj
```

Dla pobierań: w `PobierzOryginalView.get` (1589) i `PobierzPoImporcieView.get`
(1623) po `obj = _pobierz_wlasny_import(request, pk)` dodaj `self.sprawdz_uczelnie(obj)`.

- [ ] **Step 4: Wepnij profile per-uczelnia w MapowanieView**

`get_form_kwargs` (237-239) — przekaż uczelnię:

```python
        profil = dopasuj_profil(
            self._naglowki, self.uczelnia_biezaca
        ) or wybierz_profil_fallback(self._naglowki, self.uczelnia_biezaca)
```

`form_valid` — zapis profilu (295-302) stempluje uczelnię:

```python
        if form.cleaned_data.get("zapisz_profil"):
            ProfilMapowania.objects.update_or_create(
                uczelnia=self.uczelnia_biezaca,
                nazwa=form.cleaned_data["nazwa_profilu"],
                defaults={
                    "mapowanie": obj.mapowanie_kolumn,
                    "utworzony_przez": self.request.user,
                    "ostatnio_uzyty": timezone.now(),
                },
            )
```

- [ ] **Step 5: Uruchom nowe testy — mają przejść**

Run: `uv run pytest src/import_pracownikow/tests/test_views_gate_uczelnia.py -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t5.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t5.log | tail -3`
Expected: wszystkie passed.

- [ ] **Step 6: Commit**

```bash
git add src/import_pracownikow/views.py src/import_pracownikow/tests/test_views_gate_uczelnia.py
git commit -m "feat(import): bramka uczelni na wszystkich widokach + profile per-uczelnia w mapowaniu"
```

---

### Task 6: Naprawa istniejących testów >1 uczelni (interakcja z bramką)

**Files:**
- Modify: `src/import_pracownikow/tests/test_views_uczelnia.py`
- Sprawdź/napraw: `src/import_pracownikow/tests/test_views_jednostki.py`,
  `test_views_slowniki.py`, `test_views_mapowanie.py`, `test_views_pobieranie.py`
  i inne, które tworzą >1 `Uczelnia` i wołają widok importu klientem.

**Interfaces:**
- Consumes: `ustaw_biezaca_uczelnie` (Task 4).

- [ ] **Step 1: Zinwentaryzuj testy z >1 uczelnią + dostępem do widoku**

Run: `grep -rln "baker.make(Uczelnia)" src/import_pracownikow/tests/ | xargs grep -l "admin_client\|client\." `

Dla każdego pliku sprawdź testy, które tworzą DWIE+ uczelnie i wołają
`client.get/post` na URL-u importu. Takie testy po dodaniu bramki dostaną
redirect (302) zamiast 200 — chyba że request rozstrzyga uczelnię importu.

- [ ] **Step 2: Zaktualizuj `test_views_uczelnia.py`**

- `test_nowy_import_lapie_uczelnie_z_requestu` (28): używa `_jedyna_uczelnia`
  (single-tenant) → bramka przechodzi (fallback), bez zmian. Zweryfikuj zieleń.
- `test_jednostki_ostrzega_gdy_uczelnia_nieokreslona` (44): 2 uczelnie +
  `imp.uczelnia=None` + brak mapowania → bramka daje redirect. **Przepisz na
  test bramki**:

```python
@pytest.mark.django_db
def test_jednostki_redirect_gdy_uczelnia_nieokreslona(admin_client, admin_user):
    """>1 uczelnia + brak mapowania domeny → wejście na /jednostki/ redirectuje
    na home (bramka „brak uczelni")."""
    baker.make(Uczelnia)
    baker.make(Uczelnia)
    imp = baker.make(
        ImportPracownikow, owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY, uczelnia=None,
    )
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url)
    assert resp.status_code == 302
    assert resp.url == "/"
```

- `test_jednostki_bez_ostrzezenia_gdy_uczelnia_znana` (71): dodaj mapowanie
  bieżącej uczelni na host i przekaż `HTTP_HOST`:

```python
@pytest.mark.django_db
def test_jednostki_bez_ostrzezenia_gdy_uczelnia_znana(admin_client, admin_user, settings):
    baker.make(Uczelnia)
    u = baker.make(Uczelnia)
    host = ustaw_biezaca_uczelnie(u, settings)
    imp = baker.make(
        ImportPracownikow, owner=admin_user,
        stan=ImportPracownikow.STAN_PRZEANALIZOWANY, uczelnia=u,
    )
    baker.make(
        ImportPracownikowJednostka, parent=imp,
        nazwa_zrodlowa="Zakład Do Utworzenia", tryb=BRAK, utworzona=None,
    )
    url = reverse("import_pracownikow:jednostki", kwargs={"pk": imp.pk})
    resp = admin_client.get(url, HTTP_HOST=host)
    assert resp.status_code == 200
    assert 'data-uczelnia-nieokreslona="1"' not in resp.content.decode()
```

- `test_picker_pokazuje_tylko_jednostki_uczelni_importu` (95) i
  `test_post_odrzuca_mape_na_jednostke_innej_uczelni` (136): dodaj
  `host = ustaw_biezaca_uczelnie(u_import, settings)` po utworzeniu uczelni,
  dodaj `settings` do sygnatury, i przekaż `HTTP_HOST=host` do
  `admin_client.get/post`. Reszta asercji bez zmian.

Dopisz import na górze pliku:
`from import_pracownikow.tests._helpers import ustaw_biezaca_uczelnie`.

- [ ] **Step 3: Napraw pozostałe pliki z inwentaryzacji (Step 1)**

Dla każdego złapanego testu z >1 uczelnią + dostępem do widoku: albo zredukuj
do jednej uczelni (jeśli multi nie jest istotą testu — `_jedyna_uczelnia`
wzorzec / `Uczelnia.objects.exclude(pk=u.pk).delete()`), albo dodaj
`ustaw_biezaca_uczelnie(u_wlasciwa, settings)` + `HTTP_HOST`. Testy tworzące
JEDNĄ uczelnię (lub zero + ambient) NIE wymagają zmian (single-tenant fallback).

- [ ] **Step 4: Uruchom cały moduł — zieleń**

Run: `uv run pytest src/import_pracownikow/ -n auto -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t6.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t6.log | tail -3`
Expected: cały moduł passed (0 failed).

- [ ] **Step 5: Commit**

```bash
git add src/import_pracownikow/tests/
git commit -m "test(import): dostosuj testy >1 uczelni do bramki (ustaw_biezaca_uczelnie)"
```

---

### Task 7: Newsfragment + pełny lokalny przebieg

**Files:**
- Create: `src/bpp/newsfragments/import-uczelnia-scoping.bugfix.rst`

- [ ] **Step 1: Newsfragment**

`src/bpp/newsfragments/import-uczelnia-scoping.bugfix.rst`:

```rst
Import pracowników i jednostek na instalacjach multi-hosted działa teraz
ściśle w zakresie uczelni bieżącej domeny: lista importów, ekrany
poszczególnych importów i profile mapowania kolumn są ograniczone do uczelni
z requestu (import innej uczelni jest niewidoczny — także dla superusera),
a wejście pod domeną bez ustalonej uczelni przekierowuje na stronę główną.
```

- [ ] **Step 2: Pełny lokalny przebieg testów modułu + powiązanych**

Run: `uv run pytest src/import_pracownikow/ src/bpp/tests/test_middleware/ -n auto -p no:cacheprovider 2>&1 | tee /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t7.log; grep -E "passed|failed|error" /private/tmp/claude-501/-Users-mpasternak-Programowanie-bpp/6b4d19c4-2435-4542-9cf8-6976ddaf05e5/scratchpad/t7.log | tail -3`
Expected: passed, 0 failed.

- [ ] **Step 3: pre-commit (bez argumentów)**

Run: `pre-commit run --files $(git diff --name-only dev...HEAD)`
Napraw issue ręcznie (Edit), NIE `ruff --fix` masowo.

- [ ] **Step 4: Commit**

```bash
git add src/bpp/newsfragments/import-uczelnia-scoping.bugfix.rst
git commit -m "doc(import): newsfragment — scoping importu do uczelni z requestu"
```

---

## Przy scalaniu do `dev` (NIE w tej gałęzi)

- `make baseline-update` — odśwież baseline po migracji 0027 (waliduje też
  migrację + backfill na czystym kontenerze). Commituj `baseline.sql` +
  `baseline.meta.json`.
- Pełne `make tests` (lub `make tests-without-playwright`) po scaleniu.

## Uwaga projektowa (do świadomości reviewera)

Feature „ostrzeżenie, gdy uczelni nie da się ustalić" z poprzedniej iteracji
(`ImportPracownikow.uczelnia_nieokreslona_a_potrzebna` + blok
`data-uczelnia-nieokreslona` w szablonie `weryfikacja_jednostek.html`) staje
się **nieosiągalny**: na single-tenant `uczelnia_do_integracji()` nigdy nie
jest None, a na multi-tenant bramka/`sprawdz_uczelnie` zablokuje wejście, zanim
ostrzeżenie się wyrenderuje. Kod zostaje jako nieszkodliwy bezpiecznik (nie
usuwamy w tym zadaniu — poza zakresem), ale testy ostrzeżenia przechodzą teraz
na semantykę bramki (Task 6). Jeśli chcesz — osobny follow-up usuwający martwy
warning.

## Self-review (wykonane)

- **Pokrycie specu:** bramka (Task 4), scoping listy (Task 3/4), scoping
  obiektu+download (Task 5), profile per-uczelnia (Task 1/2/5), migracja+backfill
  (Task 1), baseline (sekcja merge), testy (Task 4/5/6), newsfragment (Task 7),
  menu bez zmian (celowo pominięte — decyzja użytkownika). ✔
- **Placeholdery:** brak „TBD/TODO"; jedyny świadomy skip to Task 1 Step 6
  (test backfillu) — uzasadniony (kruche testowanie RunPython; walidacja przez
  baseline-update). Zależność `bpp` w migracji: świadomie „skopiuj z autogen".
- **Spójność typów:** `dla_uczelni`, `widoczne_dla_uczelni`, `sprawdz_uczelnie`,
  `uczelnia_biezaca`, `ustaw_biezaca_uczelnie` — nazwy spójne między taskami.
