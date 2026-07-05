# Konsolidacja Wydział→Jednostka — Faza A (addytywna) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Addytywna, w pełni wdrażalna-przy-starym-kodzie faza konsolidacji: wprowadza `RodzajJednostki`, `Jednostka.rodzaj` FK (obok stringa), pola per-węzeł, `legacy_wydzial_id`, poszerzenie sluga, naprawę wycieku `widoczna`, oraz konwersję `Wydzial`→ukryte węzły `Jednostka`. NIC nie jest usuwane — PR zielony, deploy bezpieczny.

**Architecture:** Strangler, faza A ze spec-u `docs/superpowers/specs/2026-07-02-konsolidacja-wydzial-jednostka-design.md`. Każda zmiana schematu jest addytywna; węzły-wydziały powstają UKRYTE (`widoczna=False`, `aktualna=False`), więc nie wyciekają do starego kodu. Fazy B (atomowy release) i C (sprzątanie) to OSOBNE plany/PR-y.

**Tech Stack:** Django, django-mptt, pytest + model_bakery, `uv run`.

## Global Constraints

- **`uv run` przed KAŻDYM poleceniem Pythona.** Nigdy `python`/`pytest` bezpośrednio.
- **Max długość linii: 88 znaków** (ruff).
- **NIGDY nie modyfikuj istniejących migracji** w `src/*/migrations/`. Tylko nowe.
- Testy: pytest, standalone functions, `@pytest.mark.django_db`, `model_bakery.baker.make`. Zero `unittest.TestCase`.
- Numer następnej migracji bpp: **0445** (ostatnia to 0444). Kolejne zadania: 0445, 0446, …
- Model `Wydzial` pozostaje NIETKNIĘTY przez całą fazę A.
- Nazwa modelu `Jednostka` bez zmian.
- Po zmianach schematu: **NIE** odświeżaj baseline (robione raz przy scalaniu).
- Commituj często; każdy task = osobny, testowalny commit.

---

### Task 1: Model `RodzajJednostki` + seed + admin

**Files:**
- Create: `src/bpp/models/rodzaj_jednostki.py`
- Modify: `src/bpp/models/__init__.py` (dodać eksport, wg wzoru istniejących importów)
- Create: `src/bpp/migrations/0445_rodzajjednostki.py` (przez `makemigrations`)
- Create: `src/bpp/migrations/0446_seed_rodzajjednostki.py` (data migration, ręcznie)
- Modify: `src/bpp/admin/__init__.py` (rejestracja admina)
- Create: `src/bpp/admin/rodzaj_jednostki.py`
- Test: `src/bpp/tests/test_models/test_rodzaj_jednostki.py`

**Interfaces:**
- Produces: `bpp.models.RodzajJednostki` z polami `nazwa` (unique CharField), `skrot` (CharField, blank), `kolejnosc` (PositiveIntegerField), `wyklucz_z_rankingu_autorow` (Bool, default False), `pokazuj_jako_odrebna_sekcje` (Bool, default False). Seed tworzy wiersze o `nazwa` = `"Standard"`, `"Koło naukowe"`, `"Wydział"`.

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_models/test_rodzaj_jednostki.py
import pytest

from bpp.models import RodzajJednostki


@pytest.mark.django_db
def test_rodzajjednostki_pola_i_defaulty():
    r = RodzajJednostki.objects.create(nazwa="Instytut")
    assert r.wyklucz_z_rankingu_autorow is False
    assert r.pokazuj_jako_odrebna_sekcje is False
    assert r.kolejnosc == 0
    assert str(r) == "Instytut"


@pytest.mark.django_db
def test_rodzajjednostki_nazwa_unique():
    RodzajJednostki.objects.create(nazwa="Katedra")
    with pytest.raises(Exception):
        RodzajJednostki.objects.create(nazwa="Katedra")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_models/test_rodzaj_jednostki.py -v`
Expected: FAIL — `ImportError: cannot import name 'RodzajJednostki'`.

- [ ] **Step 3: Create the model**

```python
# src/bpp/models/rodzaj_jednostki.py
from django.db import models


class RodzajJednostki(models.Model):
    """Słownik rodzajów jednostki organizacyjnej (per-tenant edytowalny).

    Zastępuje dawny CharField Jednostka.rodzaj_jednostki. Behawior wyłącznie
    we flagach, nie w nazwie — 'Wydział' to zwykła etykieta.
    """

    nazwa = models.CharField(max_length=200, unique=True)
    skrot = models.CharField(max_length=50, blank=True, default="")
    kolejnosc = models.PositiveIntegerField(default=0)
    wyklucz_z_rankingu_autorow = models.BooleanField(default=False)
    pokazuj_jako_odrebna_sekcje = models.BooleanField(default=False)

    class Meta:
        verbose_name = "rodzaj jednostki"
        verbose_name_plural = "rodzaje jednostek"
        ordering = ["kolejnosc", "nazwa"]
        app_label = "bpp"

    def __str__(self):
        return self.nazwa
```

Dodać do `src/bpp/models/__init__.py` eksport wg wzoru innych modeli, np.:
```python
from .rodzaj_jednostki import RodzajJednostki  # noqa
```
(umieść przy pozostałych importach modeli struktury; jeśli jest `__all__`, dopisz `"RodzajJednostki"`.)

- [ ] **Step 4: Generate schema migration**

Run: `uv run python src/manage.py makemigrations bpp --name rodzajjednostki`
Expected: tworzy `src/bpp/migrations/0445_rodzajjednostki.py`. Zweryfikuj, że numer to 0445 (jeśli inny — OK, zapamiętaj rzeczywisty do zależności `dependencies` w 0446).

- [ ] **Step 5: Write the seed data migration**

```python
# src/bpp/migrations/0446_seed_rodzajjednostki.py
from django.db import migrations

SEED = [
    # nazwa, wyklucz_z_rankingu_autorow, pokazuj_jako_odrebna_sekcje, kolejnosc
    ("Standard", False, False, 0),
    ("Koło naukowe", True, True, 1),
    ("Wydział", False, False, 2),
]


def seed(apps, schema_editor):
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    for nazwa, wyklucz, sekcja, kolejnosc in SEED:
        RodzajJednostki.objects.update_or_create(
            nazwa=nazwa,
            defaults={
                "wyklucz_z_rankingu_autorow": wyklucz,
                "pokazuj_jako_odrebna_sekcje": sekcja,
                "kolejnosc": kolejnosc,
            },
        )


def unseed(apps, schema_editor):
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    RodzajJednostki.objects.filter(
        nazwa__in=[n for n, *_ in SEED]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("bpp", "0445_rodzajjednostki")]
    operations = [migrations.RunPython(seed, unseed)]
```

- [ ] **Step 6: Write seed test**

```python
# dopisz do src/bpp/tests/test_models/test_rodzaj_jednostki.py
@pytest.mark.django_db
def test_seed_rodzajow_obecny():
    kolo = RodzajJednostki.objects.get(nazwa="Koło naukowe")
    assert kolo.wyklucz_z_rankingu_autorow is True
    assert kolo.pokazuj_jako_odrebna_sekcje is True
    assert RodzajJednostki.objects.get(nazwa="Standard")
    assert RodzajJednostki.objects.get(nazwa="Wydział")
```

- [ ] **Step 7: Create the admin**

```python
# src/bpp/admin/rodzaj_jednostki.py
from django.contrib import admin

from bpp.models import RodzajJednostki


class RodzajJednostkiAdmin(admin.ModelAdmin):
    list_display = [
        "nazwa",
        "skrot",
        "kolejnosc",
        "wyklucz_z_rankingu_autorow",
        "pokazuj_jako_odrebna_sekcje",
    ]
    list_editable = ["kolejnosc"]
    search_fields = ["nazwa", "skrot"]
```

Rejestracja w `src/bpp/admin/__init__.py` (wg istniejącego wzoru rejestracji):
```python
from .rodzaj_jednostki import RodzajJednostkiAdmin  # noqa
admin.site.register(RodzajJednostki, RodzajJednostkiAdmin)
```
(Import `RodzajJednostki` musi być dostępny w tym pliku — dodaj do istniejącego importu z `bpp.models` lub osobno.)

- [ ] **Step 8: Run migrations + full task test**

Run: `uv run python src/manage.py migrate bpp && uv run pytest src/bpp/tests/test_models/test_rodzaj_jednostki.py -v`
Expected: wszystkie PASS. Also: `uv run python src/manage.py check` → brak błędów.

- [ ] **Step 9: Commit**

```bash
git add src/bpp/models/rodzaj_jednostki.py src/bpp/models/__init__.py \
  src/bpp/migrations/0445_rodzajjednostki.py \
  src/bpp/migrations/0446_seed_rodzajjednostki.py \
  src/bpp/admin/rodzaj_jednostki.py src/bpp/admin/__init__.py \
  src/bpp/tests/test_models/test_rodzaj_jednostki.py
git commit -m "feat(438): model RodzajJednostki + seed + admin (faza A)"
```

---

### Task 2: `Jednostka.rodzaj` FK (addytywne, obok `rodzaj_jednostki`) + backfill

**Files:**
- Modify: `src/bpp/models/jednostka.py` (dodać pole `rodzaj`)
- Create: `src/bpp/migrations/0447_jednostka_rodzaj.py` (schema, przez makemigrations)
- Create: `src/bpp/migrations/0448_backfill_jednostka_rodzaj.py` (data, ręcznie)
- Test: `src/bpp/tests/test_models/test_jednostka_rodzaj_fk.py`

**Interfaces:**
- Consumes: `RodzajJednostki` (Task 1).
- Produces: `Jednostka.rodzaj` (FK→RodzajJednostki, `null=True`, `on_delete=PROTECT`). Backfill mapuje `rodzaj_jednostki="normalna"`→"Standard", `"kolo_naukowe"`→"Koło naukowe". `rodzaj_jednostki` CharField pozostaje (usuwany dopiero w fazie B).

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_models/test_jednostka_rodzaj_fk.py
import pytest
from model_bakery import baker

from bpp.models import Jednostka, RodzajJednostki


@pytest.mark.django_db
def test_rodzaj_fk_da_sie_przypisac():
    std = RodzajJednostki.objects.get(nazwa="Standard")
    j = baker.make(Jednostka, rodzaj=std)
    j.refresh_from_db()
    assert j.rodzaj == std


@pytest.mark.django_db
def test_rodzaj_domyslnie_null_dla_nowego_obiektu():
    # W fazie A rodzaj FK jest addytywne; stary kod ustawia tylko string.
    # Nowy obiekt bez jawnego rodzaj ma NULL (re-backfill dopiero w fazie B).
    j = baker.make(Jednostka, rodzaj=None, rodzaj_jednostki="normalna")
    j.refresh_from_db()
    assert j.rodzaj is None
```

> Uwaga: mapowanie string→FK NIE jest save-hookiem — to migracja backfillu
> istniejących wierszy (Step 5). Nowe obiekty tworzone starym kodem w oknie
> A→B mają `rodzaj=NULL` do re-backfillu w fazie B. Realny backfill sprawdza
> test w Step 6.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_models/test_jednostka_rodzaj_fk.py -v`
Expected: FAIL — `Jednostka has no field named 'rodzaj'` / AttributeError.

- [ ] **Step 3: Add the field**

W `src/bpp/models/jednostka.py`, obok `rodzaj_jednostki`:
```python
    rodzaj = models.ForeignKey(
        "bpp.RodzajJednostki",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="jednostki",
    )
```

- [ ] **Step 4: Generate schema migration**

Run: `uv run python src/manage.py makemigrations bpp --name jednostka_rodzaj`
Expected: `0447_jednostka_rodzaj.py`.

- [ ] **Step 5: Write backfill data migration**

```python
# src/bpp/migrations/0448_backfill_jednostka_rodzaj.py
from django.db import migrations

MAPA = {"normalna": "Standard", "kolo_naukowe": "Koło naukowe"}


def backfill(apps, schema_editor):
    Jednostka = apps.get_model("bpp", "Jednostka")
    RodzajJednostki = apps.get_model("bpp", "RodzajJednostki")
    cache = {n: RodzajJednostki.objects.get(nazwa=n) for n in MAPA.values()}
    for kod, nazwa in MAPA.items():
        Jednostka.objects.filter(rodzaj_jednostki=kod, rodzaj__isnull=True).update(
            rodzaj=cache[nazwa]
        )


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0447_jednostka_rodzaj"),
        ("bpp", "0446_seed_rodzajjednostki"),
    ]
    operations = [migrations.RunPython(backfill, noop)]
```

- [ ] **Step 6: Write backfill-of-existing test**

```python
# dopisz do test_jednostka_rodzaj_fk.py
from django.core.management import call_command


@pytest.mark.django_db
def test_istniejace_jednostki_bez_rodzaju_daja_sie_zbackfillowac():
    # symulacja: jednostka z NULL rodzaj (jak wiersz sprzed migracji)
    j = baker.make(Jednostka, rodzaj_jednostki="normalna")
    Jednostka.objects.filter(pk=j.pk).update(rodzaj=None)
    # ręczny backfill jak w migracji
    std = RodzajJednostki.objects.get(nazwa="Standard")
    Jednostka.objects.filter(rodzaj_jednostki="normalna", rodzaj__isnull=True).update(
        rodzaj=std
    )
    j.refresh_from_db()
    assert j.rodzaj == std
```

- [ ] **Step 7: Run migrations + tests**

Run: `uv run python src/manage.py migrate bpp && uv run pytest src/bpp/tests/test_models/test_jednostka_rodzaj_fk.py -v`
Expected: PASS. `uv run python src/manage.py check` → OK.

- [ ] **Step 8: Commit**

```bash
git add src/bpp/models/jednostka.py \
  src/bpp/migrations/0447_jednostka_rodzaj.py \
  src/bpp/migrations/0448_backfill_jednostka_rodzaj.py \
  src/bpp/tests/test_models/test_jednostka_rodzaj_fk.py
git commit -m "feat(438): Jednostka.rodzaj FK obok rodzaj_jednostki + backfill (faza A)"
```

---

### Task 3: Pola per-węzeł + poszerzenie `slug` + `legacy_wydzial_id`

**Files:**
- Modify: `src/bpp/models/jednostka.py`
- Create: `src/bpp/migrations/0449_jednostka_pola_faza_a.py` (przez makemigrations)
- Test: `src/bpp/tests/test_models/test_jednostka_pola_faza_a.py`

**Interfaces:**
- Produces na `Jednostka`: `zezwalaj_na_ranking_autorow` (Bool, default True), `poprzednie_nazwy` (CharField, blank, default ""), `skrot_nazwy` (CharField 250, null, blank), `legacy_wydzial_id` (IntegerField, null, db_index=True). `slug` poszerzony do `max_length=512`.

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_models/test_jednostka_pola_faza_a.py
import pytest
from model_bakery import baker

from bpp.models import Jednostka


def test_defaulty_nowych_pol():
    # baker losowo wypełnia BooleanField — default testujemy przez _meta.
    assert Jednostka._meta.get_field("zezwalaj_na_ranking_autorow").default is True
    assert Jednostka._meta.get_field("poprzednie_nazwy").default == ""


@pytest.mark.django_db
def test_pola_nullowalne_domyslnie_puste():
    j = baker.make(Jednostka, skrot_nazwy=None, legacy_wydzial_id=None)
    j.refresh_from_db()
    assert j.skrot_nazwy is None
    assert j.legacy_wydzial_id is None


@pytest.mark.django_db
def test_slug_przyjmuje_dluga_nazwe():
    dluga = "Wydział " + "x" * 200
    j = baker.make(Jednostka, nazwa=dluga)
    j.refresh_from_db()
    assert len(j.slug) > 50  # nie ucięte do 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_models/test_jednostka_pola_faza_a.py -v`
Expected: FAIL — brak pól / `slug` ucięty.

- [ ] **Step 3: Add fields + widen slug**

W `src/bpp/models/jednostka.py`:
```python
    zezwalaj_na_ranking_autorow = models.BooleanField(
        "Zezwalaj na generowanie rankingu autorów dla tej jednostki",
        default=True,
    )
    poprzednie_nazwy = models.CharField(max_length=4096, blank=True, default="")
    skrot_nazwy = models.CharField(max_length=250, blank=True, null=True)
    legacy_wydzial_id = models.IntegerField(null=True, blank=True, db_index=True)
```
Znajdź istniejące `slug = AutoSlugField(...)` i zmień/dodaj `max_length=512`:
```python
    slug = AutoSlugField(populate_from="nazwa", max_length=512, unique=True)
```
(Zachowaj pozostałe istniejące argumenty `AutoSlugField`, zmień tylko `max_length`.)

- [ ] **Step 4: Generate migration**

Run: `uv run python src/manage.py makemigrations bpp --name jednostka_pola_faza_a`
Expected: `0449_jednostka_pola_faza_a.py` z AddField×4 + AlterField(slug).

- [ ] **Step 5: Run migration + tests**

Run: `uv run python src/manage.py migrate bpp && uv run pytest src/bpp/tests/test_models/test_jednostka_pola_faza_a.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bpp/models/jednostka.py \
  src/bpp/migrations/0449_jednostka_pola_faza_a.py \
  src/bpp/tests/test_models/test_jednostka_pola_faza_a.py
git commit -m "feat(438): pola per-węzeł + slug 512 + legacy_wydzial_id (faza A)"
```

---

### Task 4: Naprawa wycieku `widoczna` (A4) — API / sitemap / autocomplete

**Files:**
- Modify: `src/api_v1/viewsets/struktura.py:11` (`JednostkaViewSet.queryset`)
- Modify: `src/django_bpp/sitemaps.py` (`JednostkaSitemap` — override `items()`)
- Modify: `src/bpp/views/autocomplete/units.py` (`JednostkaAutocomplete.qset`)
- Test: `src/bpp/tests/test_views/test_widocznosc_faza_a.py`

**Interfaces:**
- Consumes: istniejący manager `Jednostka.objects.widoczne()`.
- Produces: żaden z tych trzech kanałów nie zwraca jednostek `widoczna=False`.

> **Uwaga dla implementera:** przed zmianą `JednostkaAutocomplete` sprawdź w `src/bpp/urls.py` / `src/bpp/views/autocomplete/urls.py`, czy `JednostkaAutocomplete` (bazowa, `.all()`) jest podpięta pod endpoint **edytorski/adminowy**, który MUSI widzieć ukryte jednostki. Jeśli tak — NIE zmieniaj bazowej, tylko utwórz wariant `widoczne()` dla publicznego endpointu. Jeśli bazowa jest publiczna — zmień `.all()`→`.widoczne()`. Test niżej zakłada, że publiczny kanał filtruje.

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_views/test_widocznosc_faza_a.py
import pytest
from model_bakery import baker

from bpp.models import Jednostka
from django_bpp.sitemaps import JednostkaSitemap


@pytest.mark.django_db
def test_sitemap_pomija_niewidoczne():
    baker.make(Jednostka, widoczna=False, nazwa="Ukryta")
    widoczna = baker.make(Jednostka, widoczna=True, nazwa="Jawna")
    items = list(JednostkaSitemap().items())
    assert widoczna in items
    assert all(j.widoczna for j in items)


@pytest.mark.django_db
def test_api_jednostka_pomija_niewidoczne(client):
    baker.make(Jednostka, widoczna=False, nazwa="UkrytaAPI")
    resp = client.get("/api/v1/jednostka/")
    assert resp.status_code == 200
    nazwy = [r["nazwa"] for r in resp.json()["results"]]
    assert "UkrytaAPI" not in nazwy
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_views/test_widocznosc_faza_a.py -v`
Expected: FAIL — niewidoczna jednostka obecna w sitemap/API.

- [ ] **Step 3: Fix API viewset**

W `src/api_v1/viewsets/struktura.py`, `JednostkaViewSet`:
```python
class JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Jednostka.objects.widoczne()
    serializer_class = JednostkaSerializer
```

- [ ] **Step 4: Fix sitemap**

W `src/django_bpp/sitemaps.py`, `JednostkaSitemap` — dodać override:
```python
class JednostkaSitemap(BppSitemap):
    changefreq = "yearly"
    klass = Jednostka
    url = "bpp:browse_jednostka"
    url_obj_field = "slug"

    def items(self):
        return self.klass.objects.widoczne()
```

- [ ] **Step 5: Fix autocomplete (wg wyniku weryfikacji z nagłówka)**

Jeśli bazowa jest publiczna — w `src/bpp/views/autocomplete/units.py`:
```python
    qset = Jednostka.objects.widoczne().select_related("wydzial")
```
Jeśli bazowa jest edytorska — zostaw ją i upewnij się, że publiczny endpoint używa `WidocznaJednostkaAutocomplete`/`PublicJednostkaAutocomplete` (już filtrują). Odnotuj decyzję w commit message.

- [ ] **Step 6: Run tests**

Run: `uv run pytest src/bpp/tests/test_views/test_widocznosc_faza_a.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/api_v1/viewsets/struktura.py src/django_bpp/sitemaps.py \
  src/bpp/views/autocomplete/units.py \
  src/bpp/tests/test_views/test_widocznosc_faza_a.py
git commit -m "fix(438): niewidoczne jednostki nie wyciekaja do API/sitemap/autocomplete (faza A)"
```

---

### Task 5: Komenda walidacji przed-konwersyjnej (A2)

**Files:**
- Create: `src/bpp/management/commands/waliduj_konwersje_wydzialow.py`
- Test: `src/bpp/tests/test_management_commands/test_waliduj_konwersje_wydzialow.py`

**Interfaces:**
- Produces: management command `waliduj_konwersje_wydzialow` — skan read-only, wypisuje kolizje `nazwa`/`skrot`/`slug` między `Wydzial` a `Jednostka`, ujemne `Wydzial.kolejnosc`, `Wydzial.zamkniecie` w przyszłości. Zwraca liczbę problemów (nonzero exit gdy >0, przez `CommandError` opcjonalnie — tu tylko raport).

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_management_commands/test_waliduj_konwersje_wydzialow.py
import pytest
from io import StringIO
from django.core.management import call_command
from model_bakery import baker

from bpp.models import Jednostka, Wydzial


@pytest.mark.django_db
def test_wykrywa_kolizje_nazwy():
    baker.make(Wydzial, nazwa="Kolizja", skrot="K1")
    baker.make(Jednostka, nazwa="Kolizja")
    out = StringIO()
    call_command("waliduj_konwersje_wydzialow", stdout=out)
    assert "Kolizja" in out.getvalue()


@pytest.mark.django_db
def test_czysto_gdy_brak_problemow():
    baker.make(Wydzial, nazwa="Wydzial A", skrot="WA")
    out = StringIO()
    call_command("waliduj_konwersje_wydzialow", stdout=out)
    assert "0 problem" in out.getvalue().lower() or "brak" in out.getvalue().lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_management_commands/test_waliduj_konwersje_wydzialow.py -v`
Expected: FAIL — `Unknown command`.

- [ ] **Step 3: Write the command**

```python
# src/bpp/management/commands/waliduj_konwersje_wydzialow.py
from django.core.management.base import BaseCommand
from django.utils import timezone

from bpp.models import Jednostka, Wydzial


class Command(BaseCommand):
    help = "Read-only skan kolizji/anomalii przed konwersją Wydzial→Jednostka."

    def handle(self, *args, **options):
        problemy = 0
        dzis = timezone.now().date()

        jedn_nazwy = set(Jednostka.objects.values_list("nazwa", flat=True))
        jedn_skroty = set(Jednostka.objects.values_list("skrot", flat=True))
        jedn_slugi = set(Jednostka.objects.values_list("slug", flat=True))

        for w in Wydzial.objects.all():
            if w.nazwa in jedn_nazwy:
                problemy += 1
                self.stdout.write(f"KOLIZJA nazwa: {w.nazwa}")
            if w.skrot in jedn_skroty:
                problemy += 1
                self.stdout.write(f"KOLIZJA skrot: {w.skrot}")
            if w.slug in jedn_slugi:
                problemy += 1
                self.stdout.write(f"KOLIZJA slug: {w.slug}")
            if w.kolejnosc < 0:
                problemy += 1
                self.stdout.write(f"UJEMNA kolejnosc: {w.nazwa} = {w.kolejnosc}")
            if w.zamkniecie and w.zamkniecie > dzis:
                problemy += 1
                self.stdout.write(f"ZAMKNIECIE w przyszlosci: {w.nazwa}")

        self.stdout.write(f"Znaleziono {problemy} problemow.")
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest src/bpp/tests/test_management_commands/test_waliduj_konwersje_wydzialow.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/management/commands/waliduj_konwersje_wydzialow.py \
  src/bpp/tests/test_management_commands/test_waliduj_konwersje_wydzialow.py
git commit -m "feat(438): komenda waliduj_konwersje_wydzialow (A2)"
```

---

### Task 6: Konwersja `Wydzial`→ukryte węzły `Jednostka` (A3, idempotentna)

**Files:**
- Create: `src/bpp/management/commands/konwertuj_wydzialy_na_jednostki.py`
- Test: `src/bpp/tests/test_management_commands/test_konwertuj_wydzialy.py`

**Interfaces:**
- Consumes: `RodzajJednostki` "Wydział" (Task 1), pola `legacy_wydzial_id`/`rodzaj`/nowe pola (Tasks 2-3).
- Produces: komenda `konwertuj_wydzialy_na_jednostki`. Dla każdego `Wydzial` tworzy `Jednostka` z `widoczna=False`, `aktualna=False`, `rodzaj`=Wydział, `legacy_wydzial_id=W.id`, kopiuje `nazwa`/`skrot`/`skrot_nazwy`/`opis`/`poprzednie_nazwy`/`pbn_id`(jeśli jest)/`zezwalaj_na_ranking_autorow`/`pokazuj_opis`/`zarzadzaj_automatycznie`/`widoczny`→(zapis do późniejszego flipu; tu węzeł zostaje `widoczna=False`), `kolejnosc`=max(0, W.kolejnosc). Idempotentna po `legacy_wydzial_id`. Węzły to rooty MPTT (`parent=None`).

> **Uwaga:** tworzenie węzła przez `Jednostka.objects.create(...)` z MPTT ustawia lft/rght/tree_id/level automatycznie (żywy model, nie migracja historyczna) — dlatego to komenda, nie data-migration. `pbn_uid`/`pbn_id` skopiuj tylko jeśli oba modele je mają (sprawdź `ModelZPBN_ID`).

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_management_commands/test_konwertuj_wydzialy.py
import pytest
from django.core.management import call_command
from model_bakery import baker

from bpp.models import Jednostka, RodzajJednostki, Wydzial


@pytest.mark.django_db
def test_kazdy_wydzial_daje_ukryty_wezel():
    w = baker.make(Wydzial, nazwa="Wydz Lekarski", skrot="WL", kolejnosc=3)
    call_command("konwertuj_wydzialy_na_jednostki")
    j = Jednostka.objects.get(legacy_wydzial_id=w.id)
    assert j.widoczna is False
    assert j.aktualna is False
    assert j.rodzaj == RodzajJednostki.objects.get(nazwa="Wydział")
    assert j.nazwa == "Wydz Lekarski"
    assert j.parent_id is None


@pytest.mark.django_db
def test_idempotentna():
    w = baker.make(Wydzial, nazwa="Wydz X", skrot="WX")
    call_command("konwertuj_wydzialy_na_jednostki")
    call_command("konwertuj_wydzialy_na_jednostki")
    assert Jednostka.objects.filter(legacy_wydzial_id=w.id).count() == 1


@pytest.mark.django_db
def test_kolejnosc_ujemna_clampowana():
    w = baker.make(Wydzial, nazwa="Wydz Neg", skrot="WN", kolejnosc=-5)
    call_command("konwertuj_wydzialy_na_jednostki")
    j = Jednostka.objects.get(legacy_wydzial_id=w.id)
    assert j.kolejnosc == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_management_commands/test_konwertuj_wydzialy.py -v`
Expected: FAIL — `Unknown command`.

- [ ] **Step 3: Write the command**

```python
# src/bpp/management/commands/konwertuj_wydzialy_na_jednostki.py
from django.core.management.base import BaseCommand
from django.db import transaction

from bpp.models import Jednostka, RodzajJednostki, Wydzial


class Command(BaseCommand):
    help = "Konwertuje Wydzial na ukryte wezly Jednostka (faza A, idempotentne)."

    @transaction.atomic
    def handle(self, *args, **options):
        rodzaj_wydzial = RodzajJednostki.objects.get(nazwa="Wydział")
        utworzone = 0
        for w in Wydzial.objects.all():
            if Jednostka.objects.filter(legacy_wydzial_id=w.id).exists():
                continue
            Jednostka.objects.create(
                nazwa=w.nazwa,
                skrot=w.skrot,
                skrot_nazwy=w.skrot_nazwy,
                opis=w.opis,
                poprzednie_nazwy=w.poprzednie_nazwy,
                uczelnia=w.uczelnia,
                rodzaj=rodzaj_wydzial,
                legacy_wydzial_id=w.id,
                parent=None,
                widoczna=False,
                aktualna=False,
                zezwalaj_na_ranking_autorow=w.zezwalaj_na_ranking_autorow,
                pokazuj_opis=w.pokazuj_opis,
                zarzadzaj_automatycznie=w.zarzadzaj_automatycznie,
                kolejnosc=max(0, w.kolejnosc),
            )
            utworzone += 1
        self.stdout.write(f"Utworzono {utworzone} wezlow-wydzialow.")
```

> Jeśli `Jednostka` NIE ma któregoś pola (np. `pokazuj_opis`) — usuń tę linię. Jeśli `Wydzial`/`Jednostka` mają `pbn_id`/`pbn_uid` i chcemy przenieść — dodaj po sprawdzeniu nazw pól. Zweryfikuj `uv run python src/manage.py shell -c "from bpp.models import Jednostka, Wydzial; print([f.name for f in Jednostka._meta.fields]); print([f.name for f in Wydzial._meta.fields])"` przed pisaniem.

- [ ] **Step 4: Run tests**

Run: `uv run pytest src/bpp/tests/test_management_commands/test_konwertuj_wydzialy.py -v`
Expected: PASS.

- [ ] **Step 5: Full-suite smoke on struktura**

Run: `uv run pytest src/bpp/tests/test_models/ src/bpp/tests/test_management_commands/ -q`
Expected: brak nowych regresji (istniejące testy struktury zielone — węzły są ukryte, więc stary kod ich nie widzi).

- [ ] **Step 6: Commit**

```bash
git add src/bpp/management/commands/konwertuj_wydzialy_na_jednostki.py \
  src/bpp/tests/test_management_commands/test_konwertuj_wydzialy.py
git commit -m "feat(438): konwersja Wydzial na ukryte wezly Jednostka (A3, idempotentna)"
```

---

## Zakończenie fazy A

- [ ] **Pełna suita bez Playwrighta:** `make tests-without-playwright` → zielono.
- [ ] **System check:** `uv run python src/manage.py check` → brak błędów.
- [ ] **Newsfragment towncrier** (jeśli repo tego wymaga do PR): dodać `changes/438.feature` z krótkim opisem fazy A.
- [ ] **NIE** odświeżać baseline (robimy raz przy scalaniu całości).
- [ ] PR: `feat/438-konsolidacja-wydzial-jednostka` → `dev`, tytuł „Konsolidacja Wydział→Jednostka — Faza A (addytywna)".

**Fazy B i C = osobne plany/PR-y** (`2026-07-04-konsolidacja-faza-B.md`, `-faza-C.md`), pisane po zmergowaniu A.
