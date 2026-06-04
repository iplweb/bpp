# ewaluacja_metryki per-uczelnia — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zawęzić liczenie i odczyt metryk ewaluacyjnych (`MetrykaAutora`) per
uczelnia w instalacji wielouczelnianej, naprawiając przy okazji uśpiony bug R2
(globalna agregacja slotów + globalny destrukcyjny delete).

**Architecture:** Mirror wzorca R2 (`ewaluacja_liczba_n` per-uczelnia). FK
`uczelnia` na `MetrykaAutora` i `StatusGenerowania`; pipeline zapisu zawężony
per uczelnia (bulk dziedziczy uczelnię z wiersza `IloscUdzialow`, pin/unpin z
`autor.aktualna_jednostka.uczelnia`); odczyty filtrowane hybrydą
`uczelnia_dla_odczytu` z guardem single-install `tylko_jedna_uczelnia()`.

**Tech Stack:** Django 5.2, pytest + model_bakery, testcontainers (PG/Redis),
Celery (chord/group), `fixtures.conftest_multisite` (uczelnia1/2, site1/2).

**Spec:** `docs/superpowers/specs/2026-06-04-ewaluacja-metryki-per-uczelnia-design.md`

**Reguły wykonawcze:**
- `uv run` przy KAŻDEJ komendzie Pythona; testy z `-p no:cacheprovider`.
- NIE modyfikować istniejących migracji.
- Po każdym tasku: `uv run ruff check <pliki>` ORAZ `uv run ruff format <pliki>`
  (format wolno; `check --fix` NIE — fix ręcznie).
- Guard musi zostać zielony bez nowych wpisów:
  `uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q`.
- Commit po każdym tasku (na branchu `feature/multi-hosted-config`).

---

## File Structure

- `src/ewaluacja_metryki/models.py` — FK `uczelnia` na `MetrykaAutora` +
  `StatusGenerowania`; koniec singletonu.
- `src/ewaluacja_metryki/migrations/0006_*`, `0007_*`, `0008_*` — nowe migracje.
- `src/ewaluacja_metryki/uczelnia_scope.py` — NOWY helper read-side
  (`scope_metryki(qs, uczelnia)`), analogiczny do `bpp.util.uczelnia_scope`.
- `src/ewaluacja_metryki/utils.py` — pipeline zapisu zawężony per uczelnia.
- `src/ewaluacja_metryki/tasks.py` — taski Celery + status per-uczelnia.
- `src/ewaluacja_metryki/management/commands/oblicz_metryki.py` — CLI scoping.
- `src/ewaluacja_metryki/views/{generation,statistics,list,detail,export,pin_unpin}.py`
  — read-side + uruchamianie generowania per uczelnia.
- `src/ewaluacja_metryki/export_helpers.py` — helpery przyjmują `base_qs`.
- `src/ewaluacja_metryki/admin.py` — `uczelnia` w adminie.
- `src/ewaluacja_metryki/tests/test_per_uczelnia.py` — NOWY plik testów izolacji.

---

## Task 1: FK `uczelnia` na `MetrykaAutora` + migracja 0006

**Files:**
- Modify: `src/ewaluacja_metryki/models.py:9-121` (MetrykaAutora)
- Create: `src/ewaluacja_metryki/migrations/0006_metrykaautora_uczelnia.py`
- Test: `src/ewaluacja_metryki/tests/test_per_uczelnia.py`

- [ ] **Step 1: Write failing test**

```python
# src/ewaluacja_metryki/tests/test_per_uczelnia.py
from decimal import Decimal

import pytest
from model_bakery import baker

from ewaluacja_metryki.models import MetrykaAutora


def _make_metryka(autor, dyscyplina, uczelnia, **kw):
    defaults = dict(
        slot_maksymalny=Decimal("4.0"),
        slot_nazbierany=Decimal("2.0"),
        punkty_nazbierane=Decimal("100.0"),
        slot_wszystkie=Decimal("3.0"),
        punkty_wszystkie=Decimal("150.0"),
    )
    defaults.update(kw)
    return MetrykaAutora.objects.create(
        autor=autor, dyscyplina_naukowa=dyscyplina, uczelnia=uczelnia, **defaults
    )


@pytest.mark.django_db
def test_metryka_ma_uczelnia(autor_jan_kowalski, dyscyplina1):
    u = baker.make("bpp.Uczelnia")
    m = _make_metryka(autor_jan_kowalski, dyscyplina1, u)
    assert m.uczelnia_id == u.pk


@pytest.mark.django_db
def test_metryka_unique_together_z_uczelnia(autor_jan_kowalski, dyscyplina1):
    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    # ta sama (autor, dyscyplina), różne uczelnie → OK (rozłączne metryki)
    _make_metryka(autor_jan_kowalski, dyscyplina1, u1)
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)
    assert MetrykaAutora.objects.count() == 2
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: FAIL — `MetrykaAutora() got unexpected keyword 'uczelnia'`.

- [ ] **Step 3: Add FK + unique_together + index to model**

W `src/ewaluacja_metryki/models.py`, w klasie `MetrykaAutora` po polu
`jednostka` (linia ~23) dodać:

```python
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Uczelnia, dla której policzono metrykę (multi-hosted)",
    )
```

W `class Meta` zmienić `unique_together` i dodać indeks:

```python
        unique_together = [("autor", "dyscyplina_naukowa", "uczelnia")]
        ordering = ["-srednia_za_slot_nazbierana", "autor__nazwisko", "autor__imiona"]
        indexes = [
            models.Index(fields=["-srednia_za_slot_nazbierana"]),
            models.Index(fields=["jednostka", "-srednia_za_slot_nazbierana"]),
            models.Index(fields=["dyscyplina_naukowa", "-srednia_za_slot_nazbierana"]),
            models.Index(fields=["uczelnia", "-srednia_za_slot_nazbierana"]),
        ]
```

- [ ] **Step 4: Create migration 0006 (backfill clear-on-multi)**

```python
# src/ewaluacja_metryki/migrations/0006_metrykaautora_uczelnia.py
import django.db.models.deletion
from django.db import migrations, models


def backfill_uczelnia(apps, schema_editor):
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    MetrykaAutora = apps.get_model("ewaluacja_metryki", "MetrykaAutora")

    null_qs = MetrykaAutora.objects.filter(uczelnia__isnull=True)
    if not null_qs.exists():
        return

    uczelnie = list(Uczelnia.objects.all()[:2])
    if len(uczelnie) == 1:
        null_qs.update(uczelnia=uczelnie[0])
        return

    # MetrykaAutora to regenerowalny cache (delete+create przy generowaniu);
    # przy >1 uczelni nie da się zdeterministycznie przypisać legacy wierszy,
    # więc czyścimy — odtworzą się przy najbliższym generuj_metryki per uczelnia.
    null_qs.delete()


def backfill_uczelnia_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0428_cpd_uczelnia_not_null"),
        ("ewaluacja_metryki", "0005_alter_metrykaautora_rodzaj_autora_and_more"),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="metrykaautora",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="metrykaautora",
            name="uczelnia",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.uczelnia",
            ),
        ),
        migrations.AlterUniqueTogether(
            name="metrykaautora",
            unique_together={("autor", "dyscyplina_naukowa", "uczelnia")},
        ),
        migrations.AddIndex(
            model_name="metrykaautora",
            index=models.Index(
                fields=["uczelnia", "-srednia_za_slot_nazbierana"],
                name="ewaluacja_m_uczelni_idx",
            ),
        ),
        migrations.RunPython(backfill_uczelnia, backfill_uczelnia_reverse),
    ]
```

UWAGA: zależności (`bpp` ostatnia migracja, dokładny `name` indeksu, numer
poprzedniej migracji metryki) **zweryfikować** komendą w Step 5 — jeśli
`makemigrations --check` zgłosi rozjazd, dostosuj `dependencies`/`name`.

- [ ] **Step 5: Verify migration graph spójny**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run ewaluacja_metryki`
Expected: "No changes detected" (model = migracja). Jeśli wskazuje brakującą
migrację — znaczy że nazwa indeksu/pole nie zgadza się z modelem; dostosuj.

- [ ] **Step 6: Run tests, verify pass**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS (2 testy).

- [ ] **Step 7: Commit**

```bash
git add src/ewaluacja_metryki/models.py src/ewaluacja_metryki/migrations/0006_metrykaautora_uczelnia.py src/ewaluacja_metryki/tests/test_per_uczelnia.py
git commit -m "feat(metryki): FK uczelnia + unique_together per uczelnia (D, task 1)"
```

---

## Task 2: `StatusGenerowania` per-uczelnia + migracja 0007

**Files:**
- Modify: `src/ewaluacja_metryki/models.py:179-282` (StatusGenerowania)
- Create: `src/ewaluacja_metryki/migrations/0007_statusgenerowania_uczelnia.py`
- Test: `src/ewaluacja_metryki/tests/test_per_uczelnia.py`

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.django_db
def test_status_generowania_per_uczelnia():
    from ewaluacja_metryki.models import StatusGenerowania

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    s1 = StatusGenerowania.get_or_create(uczelnia=u1)
    s2 = StatusGenerowania.get_or_create(uczelnia=u2)
    assert s1.pk != s2.pk
    assert s1.uczelnia_id == u1.pk
    assert s2.uczelnia_id == u2.pk
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py::test_status_generowania_per_uczelnia -q -p no:cacheprovider`
Expected: FAIL — `get_or_create() got unexpected keyword 'uczelnia'`.

- [ ] **Step 3: Update model**

W `StatusGenerowania` dodać pole (po `task_id`, linia ~217):

```python
    uczelnia = models.ForeignKey(
        "bpp.Uczelnia",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        unique=True,
        help_text="Uczelnia, której dotyczy ten status (multi-hosted)",
    )
```

Zmienić `save()` (usunąć wymuszanie singletonu) — linia ~231:

```python
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
```

Zmienić `get_or_create` (linia ~236):

```python
    @classmethod
    def get_or_create(cls, uczelnia=None):
        """Pobierz lub utwórz status dla danej uczelni (per-uczelnia, multi-hosted)."""
        obj, created = cls.objects.get_or_create(uczelnia=uczelnia)
        return obj
```

- [ ] **Step 4: Create migration 0007**

```python
# src/ewaluacja_metryki/migrations/0007_statusgenerowania_uczelnia.py
import django.db.models.deletion
from django.db import migrations, models


def backfill_status_uczelnia(apps, schema_editor):
    Uczelnia = apps.get_model("bpp", "Uczelnia")
    StatusGenerowania = apps.get_model("ewaluacja_metryki", "StatusGenerowania")

    null_qs = StatusGenerowania.objects.filter(uczelnia__isnull=True)
    if not null_qs.exists():
        return

    uczelnie = list(Uczelnia.objects.all()[:2])
    if len(uczelnie) == 1:
        null_qs.update(uczelnia=uczelnie[0])
        return

    # Status to ulotny stan postępu, nie dane — usuń osierocony singleton.
    null_qs.delete()


def backfill_status_uczelnia_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0428_cpd_uczelnia_not_null"),
        ("ewaluacja_metryki", "0006_metrykaautora_uczelnia"),
    ]

    operations = [
        migrations.AddField(
            model_name="statusgenerowania",
            name="uczelnia",
            field=models.ForeignKey(
                blank=True,
                null=True,
                unique=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="bpp.uczelnia",
            ),
        ),
        migrations.RunPython(
            backfill_status_uczelnia, backfill_status_uczelnia_reverse
        ),
    ]
```

- [ ] **Step 5: Verify migration graph + run test**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run ewaluacja_metryki`
Expected: "No changes detected".

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ewaluacja_metryki/models.py src/ewaluacja_metryki/migrations/0007_statusgenerowania_uczelnia.py src/ewaluacja_metryki/tests/test_per_uczelnia.py
git commit -m "feat(metryki): StatusGenerowania per uczelnia, koniec singletonu (D, task 2)"
```

---

## Task 3: Pipeline zapisu `utils.py` zawężony per uczelnia

**Files:**
- Modify: `src/ewaluacja_metryki/utils.py` (cały pipeline)
- Test: `src/ewaluacja_metryki/tests/test_per_uczelnia.py`

Naprawiamy 3 luki: knapsack leak (brak `uczelnia_id` w `zbieraj_sloty`),
globalna agregacja slotu w `oblicz_metryki_dla_autora`, globalny delete/odczyt
w `generuj_metryki`.

- [ ] **Step 1: Write failing test (izolacja + brak sumowania slotów)**

```python
@pytest.mark.django_db
def test_oblicz_metryki_dla_autora_nie_sumuje_slotow_z_innej_uczelni(
    autor_jan_kowalski, dyscyplina1
):
    """Regresja R2: slot_maksymalny nie może sumować udziałów wszystkich uczelni."""
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
    from ewaluacja_metryki.utils import oblicz_metryki_dla_autora

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None, ilosc_udzialow=Decimal("4.0"), uczelnia=u1,
    )
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None, ilosc_udzialow=Decimal("9.0"), uczelnia=u2,
    )
    metryka, _ = oblicz_metryki_dla_autora(
        autor=autor_jan_kowalski, dyscyplina=dyscyplina1, uczelnia=u1
    )
    # slot_maksymalny = 4.0 (tylko u1), NIE 13.0 (suma u1+u2)
    assert metryka.slot_maksymalny == Decimal("4.0")
    assert metryka.uczelnia_id == u1.pk
```

- [ ] **Step 2: Run test, verify it fails**

Run: `uv run pytest "src/ewaluacja_metryki/tests/test_per_uczelnia.py::test_oblicz_metryki_dla_autora_nie_sumuje_slotow_z_innej_uczelni" -q -p no:cacheprovider`
Expected: FAIL — `oblicz_metryki_dla_autora() got unexpected keyword 'uczelnia'`
(albo slot_maksymalny == 13.0).

- [ ] **Step 3: Update `oblicz_metryki_dla_autora`**

Sygnatura (linia 32) — dodać `uczelnia` jako parametr po `dyscyplina`:

```python
def oblicz_metryki_dla_autora(
    autor,
    dyscyplina,
    uczelnia,
    rok_min=2022,
    rok_max=2025,
    minimalny_pk=Decimal("0.01"),
    slot_maksymalny=None,
):
```

Agregacja slotu (linia ~59) — dodać filtr `uczelnia`:

```python
        aggregated = IloscUdzialowDlaAutoraZaCalosc.objects.filter(
            autor=autor, dyscyplina_naukowa=dyscyplina, uczelnia=uczelnia
        ).aggregate(total_slots=Sum("ilosc_udzialow"))
```

Oba wywołania `autor.zbieraj_sloty(...)` (linie ~96 i ~123) — dodać
`uczelnia_id=uczelnia.pk`.

Blok create (linia ~169) — scope delete + tag uczelnia:

```python
    with transaction.atomic():
        MetrykaAutora.objects.filter(
            autor=autor, dyscyplina_naukowa=dyscyplina, uczelnia=uczelnia
        ).delete()

        metryka = MetrykaAutora.objects.create(
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            uczelnia=uczelnia,
            jednostka=jednostka,
            # ... reszta pól bez zmian
```

- [ ] **Step 4: Update `przelicz_metryki_dla_publikacji` (pin/unpin path)**

W pętli (linia ~239) wyprowadź uczelnię z `aktualna_jednostka` i pomiń autora
bez home-uczelni (reguła R2):

```python
    for autor, dyscyplina in autorzy_do_przeliczenia:
        jednostka = autor.aktualna_jednostka
        if jednostka is None or not jednostka.skupia_pracownikow:
            continue  # reguła R2: brak home-uczelni → brak metryki
        uczelnia = jednostka.uczelnia
        try:
            metryka, _ = oblicz_metryki_dla_autora(
                autor=autor,
                dyscyplina=dyscyplina,
                uczelnia=uczelnia,
                rok_min=rok_min,
                rok_max=rok_max,
            )
            results.append((autor, dyscyplina, metryka))
        except Exception as e:
            logger.info(
                f"Pominięto przeliczanie metryki dla {autor} - {dyscyplina.nazwa}: {e}"
            )
            continue
```

- [ ] **Step 5: Update `generuj_metryki` + helpery (bulk path)**

`_get_ilosc_udzialow_queryset` (linia ~272) — przyjmuje `uczelnia`:

```python
def _get_ilosc_udzialow_queryset(ilosc_udzialow_queryset, uczelnia=None):
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc

    if ilosc_udzialow_queryset is not None:
        return ilosc_udzialow_queryset
    qs = IloscUdzialowDlaAutoraZaCalosc.objects.all()
    if uczelnia is not None:
        qs = qs.filter(uczelnia=uczelnia)
    return qs
```

`_create_or_update_metryka` (linia ~389) — dodać `uczelnia` jako parametr i do
lookupu + defaults:

```python
def _create_or_update_metryka(
    autor, dyscyplina, uczelnia, jednostka, slot_maksymalny,
    metrics_data, rok_min, rok_max, rodzaj_autora_skrot,
):
    return MetrykaAutora.objects.update_or_create(
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        uczelnia=uczelnia,
        defaults={
            "jednostka": jednostka,
            # ... reszta defaults bez zmian
        },
    )
```

`_calculate_metrics_data` (linia ~322) — dodać `uczelnia` parametr i przekazać
`uczelnia_id=uczelnia.pk` do obu `zbieraj_sloty`.

`_process_single_author` (linia ~420) — uczelnia z wiersza:

```python
    autor = ilosc_udzialow.autor
    dyscyplina = ilosc_udzialow.dyscyplina_naukowa
    uczelnia = ilosc_udzialow.uczelnia
    slot_maksymalny = ilosc_udzialow.ilosc_udzialow
```

...przekazać `uczelnia` do `_calculate_metrics_data` i `_create_or_update_metryka`.

`generuj_metryki` (linia ~514) — nowy param `uczelnia=None`; przekazać do
`_get_ilosc_udzialow_queryset`; scoped delete:

```python
def generuj_metryki(
    rok_min=2022, rok_max=2025, minimalny_pk=Decimal("0.01"), nadpisz=True,
    rodzaje_autora=None, progress_callback=None, logger_output=None,
    ilosc_udzialow_queryset=None, uczelnia=None,
):
    ...
    ilosc_udzialow_qs = _get_ilosc_udzialow_queryset(ilosc_udzialow_queryset, uczelnia)
    ...
    if nadpisz:
        qs = MetrykaAutora.objects.all()
        if uczelnia is not None:
            qs = qs.filter(uczelnia=uczelnia)
        qs.delete()
```

- [ ] **Step 6: Run test + existing utils tests**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py src/ewaluacja_metryki/tests/test_commands.py -q -p no:cacheprovider`
Expected: PASS (nowy + brak regresji).

- [ ] **Step 7: Commit**

```bash
git add src/ewaluacja_metryki/utils.py src/ewaluacja_metryki/tests/test_per_uczelnia.py
git commit -m "fix(metryki): pipeline utils zawężony per uczelnia, naprawa knapsack leak + global delete (D, task 3)"
```

---

## Task 4: `tasks.py` — taski Celery + status per-uczelnia

**Files:**
- Modify: `src/ewaluacja_metryki/tasks.py`
- Test: `src/ewaluacja_metryki/tests/test_tasks.py` (rozszerzyć)

- [ ] **Step 1: Write failing test**

```python
# dopisać do src/ewaluacja_metryki/tests/test_per_uczelnia.py
@pytest.mark.django_db
def test_generuj_metryki_task_scope_per_uczelnia(autor_jan_kowalski, dyscyplina1):
    """Task generuje metryki tylko dla swojej uczelni, nie wyciera innej."""
    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
    from ewaluacja_metryki.models import MetrykaAutora
    from ewaluacja_metryki.tasks import generuj_metryki_task

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    # istniejąca metryka u2 (nie ruszać)
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None, ilosc_udzialow=Decimal("4.0"), uczelnia=u1,
    )
    generuj_metryki_task(
        uczelnia_id=u1.pk, przelicz_liczbe_n=False, rodzaje_autora=[" "]
    )
    # metryka u2 nadal istnieje (scoped delete nie wyciera obcej uczelni)
    assert MetrykaAutora.objects.filter(uczelnia=u2).exists()
```

- [ ] **Step 2: Run, verify fails**

Run: `uv run pytest "src/ewaluacja_metryki/tests/test_per_uczelnia.py::test_generuj_metryki_task_scope_per_uczelnia" -q -p no:cacheprovider`
Expected: FAIL — metryka u2 skasowana przez globalny `MetrykaAutora.objects.all().delete()`.

- [ ] **Step 3: Update `generuj_metryki_task`**

W `generuj_metryki_task` (linia ~305): rozstrzygnij uczelnię raz, użyj do
statusu, queryset, przekaż do `generuj_metryki`:

```python
    uczelnia = (
        Uczelnia.objects.get(pk=uczelnia_id)
        if uczelnia_id
        else Uczelnia.objects.get()
    )
    status = StatusGenerowania.get_or_create(uczelnia=uczelnia)
    ...
    # Krok 1 liczba_n: użyj już-rozstrzygniętej `uczelnia` zamiast ponownego get()
    if przelicz_liczbe_n:
        oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia=uczelnia)
    ...
    queryset = IloscUdzialowDlaAutoraZaCalosc.objects.filter(uczelnia=uczelnia)
    if rodzaje_autora:
        queryset = queryset.filter(rodzaj_autora__skrot__in=rodzaje_autora)
    total_count = queryset.count()
    ...
    wynik = generuj_metryki(
        rok_min=rok_min, rok_max=rok_max, minimalny_pk=Decimal(str(minimalny_pk)),
        nadpisz=nadpisz, rodzaje_autora=rodzaje_autora,
        progress_callback=update_progress, uczelnia=uczelnia,
    )
```

Błędna ścieżka `except` (linia ~423) — `status` już ma uczelnię.

- [ ] **Step 4: Update `generuj_metryki_task_parallel` + `finalizuj_generowanie_metryk`**

`generuj_metryki_task_parallel` (linia ~177): rozstrzygnij `uczelnia`,
`StatusGenerowania.get_or_create(uczelnia=uczelnia)`; queryset
`.filter(uczelnia=uczelnia)`; scoped delete; przekaż `uczelnia_id` do callbacku:

```python
        if nadpisz:
            qs = MetrykaAutora.objects.filter(uczelnia=uczelnia)
            deleted_count = qs.count()
            qs.delete()
        ...
        job = chord(task_group)(
            finalizuj_generowanie_metryk.s(uczelnia_id=uczelnia.pk)
        )
```

`finalizuj_generowanie_metryk` (linia ~118) — dodać `uczelnia_id`:

```python
@shared_task
def finalizuj_generowanie_metryk(results, uczelnia_id=None):
    from bpp.models import Uczelnia

    uczelnia = (
        Uczelnia.objects.get(pk=uczelnia_id) if uczelnia_id
        else Uczelnia.objects.get()
    )
    status = StatusGenerowania.get_or_create(uczelnia=uczelnia)
    status.refresh_from_db()
    ...
```

UWAGA: subtask `oblicz_metryki_dla_autora_task` czyta uczelnię z wiersza
`IloscUdzialow` przez `_process_single_author` (Task 3) — bez zmian sygnatury.
`StatusGenerowania.objects.update(...)` (linie ~76, ~93, ~107) zawęzić do
`StatusGenerowania.objects.filter(uczelnia=uczelnia).update(...)` — ale subtask
nie zna uczelni; zamiast tego przekaż `uczelnia_id` do
`oblicz_metryki_dla_autora_task.s(...)` i filtruj po nim. Dodać `uczelnia_id`
parametr do subtaska i `StatusGenerowania.objects.filter(uczelnia_id=uczelnia_id)`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py src/ewaluacja_metryki/tests/test_tasks.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ewaluacja_metryki/tasks.py src/ewaluacja_metryki/tests/test_per_uczelnia.py
git commit -m "feat(metryki): taski Celery scope per uczelnia + status per uczelnia (D, task 4)"
```

---

## Task 5: CLI `oblicz_metryki` scope per uczelnia

**Files:**
- Modify: `src/ewaluacja_metryki/management/commands/oblicz_metryki.py:69-161`
- Test: `src/ewaluacja_metryki/tests/test_commands.py` (rozszerzyć)

- [ ] **Step 1: Write failing test**

```python
@pytest.mark.django_db
def test_command_oblicz_metryki_scope_uczelnia(autor_jan_kowalski, dyscyplina1):
    from django.core.management import call_command

    from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
    from ewaluacja_metryki.models import MetrykaAutora

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)
    IloscUdzialowDlaAutoraZaCalosc.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=None, ilosc_udzialow=Decimal("4.0"), uczelnia=u1,
    )
    call_command(
        "oblicz_metryki", "--bez-liczby-n", "--nadpisz",
        "--uczelnia-id", str(u1.pk), "--rodzaje-autora", " ",
    )
    assert MetrykaAutora.objects.filter(uczelnia=u2).exists()  # u2 nietknięta
```

- [ ] **Step 2: Run, verify fails**

Run: `uv run pytest "src/ewaluacja_metryki/tests/test_commands.py::test_command_oblicz_metryki_scope_uczelnia" -q -p no:cacheprovider`
Expected: FAIL — globalny delete wyciera u2.

- [ ] **Step 3: Update command `handle`**

Rozstrzygnij uczelnię na początku (single-or-fail), użyj jej do scope i
przekaż do `generuj_metryki`. W `handle` (linia ~69):

```python
        uczelnia_id = options.get("uczelnia_id")
        uczelnia = (
            Uczelnia.objects.get(pk=uczelnia_id)
            if uczelnia_id
            else Uczelnia.objects.get()
        )
```

(`--bez-liczby-n` nie wymaga już osobnego leniwego rozwiązywania — uczelnia
rozstrzygana raz na górze; jeśli `Uczelnia.objects.get()` rzuca przy 0/>1
uczelni bez `--uczelnia-id`, to świadomy single-or-fail.)

`ilosc_udzialow_qs` (linia ~132): `IloscUdzialowDlaAutoraZaCalosc.objects.filter(uczelnia=uczelnia)`.

Wywołanie `generuj_metryki(...)` (linia ~153): dodać `uczelnia=uczelnia`.

- [ ] **Step 4: Run tests**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_commands.py src/ewaluacja_metryki/tests/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/ewaluacja_metryki/management/commands/oblicz_metryki.py src/ewaluacja_metryki/tests/test_commands.py
git commit -m "feat(metryki): CLI oblicz_metryki scope per uczelnia single-or-fail (D, task 5)"
```

---

## Task 6: Helper read-side + `views/generation.py`

**Files:**
- Create: `src/ewaluacja_metryki/uczelnia_scope.py`
- Modify: `src/ewaluacja_metryki/views/generation.py`
- Test: `src/ewaluacja_metryki/tests/test_per_uczelnia.py`

- [ ] **Step 1: Create read-side helper**

```python
# src/ewaluacja_metryki/uczelnia_scope.py
"""Zawężanie querysetów MetrykaAutora do uczelni oglądającego (read-side).

Hybryda uczelni z `raport_slotow.uczelnia_helper.uczelnia_dla_odczytu`
(site + superuser ?uczelnia=) + guard single-install (no-op przy 1 uczelni).
"""

from bpp.util.uczelnia_scope import tylko_jedna_uczelnia


def scope_metryki(qs, uczelnia):
    """Zawęź queryset MetrykaAutora do uczelni; no-op przy single-install/None."""
    if uczelnia is None or tylko_jedna_uczelnia():
        return qs
    return qs.filter(uczelnia=uczelnia)
```

- [ ] **Step 2: Write failing test (generation view przekazuje uczelnia_id)**

```python
@pytest.mark.django_db
def test_scope_metryki_single_install_noop(autor_jan_kowalski, dyscyplina1):
    from ewaluacja_metryki.models import MetrykaAutora
    from ewaluacja_metryki.uczelnia_scope import scope_metryki

    u = baker.make("bpp.Uczelnia")  # dokładnie 1 uczelnia
    _make_metryka(autor_jan_kowalski, dyscyplina1, u)
    qs = scope_metryki(MetrykaAutora.objects.all(), u)
    assert qs.count() == 1  # no-op, nie filtruje


@pytest.mark.django_db
def test_scope_metryki_multi_filtruje(autor_jan_kowalski, dyscyplina1):
    from ewaluacja_metryki.models import MetrykaAutora
    from ewaluacja_metryki.uczelnia_scope import scope_metryki

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    _make_metryka(autor_jan_kowalski, dyscyplina1, u1)
    _make_metryka(autor_jan_kowalski, dyscyplina1, u2)
    qs = scope_metryki(MetrykaAutora.objects.all(), u1)
    assert list(qs.values_list("uczelnia_id", flat=True)) == [u1.pk]
```

- [ ] **Step 3: Run, verify fails**

Run: `uv run pytest "src/ewaluacja_metryki/tests/test_per_uczelnia.py::test_scope_metryki_single_install_noop" "src/ewaluacja_metryki/tests/test_per_uczelnia.py::test_scope_metryki_multi_filtruje" -q -p no:cacheprovider`
Expected: FAIL (helper nie istnieje) → po Step 1 PASS.

- [ ] **Step 4: Update `generation.py`**

`UruchomGenerowanieView.post` — uczelnia z requestu, status per-uczelnia,
total_count scoped:

```python
        from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

        uczelnia = uczelnia_dla_odczytu(request)
        status = StatusGenerowania.get_or_create(uczelnia=uczelnia)
        if status.w_trakcie:
            ...
        ...
        from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaCalosc
        total_count = IloscUdzialowDlaAutoraZaCalosc.objects.filter(
            uczelnia=uczelnia
        ).count() if uczelnia else IloscUdzialowDlaAutoraZaCalosc.objects.count()

        result = generuj_metryki_task_parallel.delay(
            rok_min=rok_min, rok_max=rok_max, minimalny_pk=minimalny_pk,
            nadpisz=nadpisz, przelicz_liczbe_n=True, rodzaje_autora=rodzaje_autora,
            uczelnia_id=uczelnia.pk if uczelnia else None,
        )
        status.rozpocznij_generowanie(
            task_id=str(result.id), liczba_do_przetworzenia=total_count
        )
```

`StatusGenerowaniaView.get` i `StatusGenerowaniaPartialView.get` —
`uczelnia = uczelnia_dla_odczytu(request)` + `StatusGenerowania.get_or_create(uczelnia=uczelnia)`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ewaluacja_metryki/uczelnia_scope.py src/ewaluacja_metryki/views/generation.py src/ewaluacja_metryki/tests/test_per_uczelnia.py
git commit -m "feat(metryki): helper scope_metryki + generation view per uczelnia (D, task 6)"
```

---

## Task 7: Read-side `views/statistics.py` + `views/list.py`

**Files:**
- Modify: `src/ewaluacja_metryki/views/statistics.py`, `src/ewaluacja_metryki/views/list.py`
- Test: `src/ewaluacja_metryki/tests/test_per_uczelnia.py`

- [ ] **Step 1: Write failing test (widok listy nie pokazuje obcej uczelni)**

```python
@pytest.mark.django_db
def test_lista_metryk_filtruje_po_uczelni(client, settings, django_user_model,
                                          autor_jan_kowalski, dyscyplina1,
                                          uczelnia1, uczelnia2, site1):
    from ewaluacja_metryki.models import MetrykaAutora

    settings.ALLOWED_HOSTS = ["*"]
    _make_metryka(autor_jan_kowalski, dyscyplina1, uczelnia1)
    autor2 = baker.make("bpp.Autor")
    _make_metryka(autor2, dyscyplina1, uczelnia2)

    su = django_user_model.objects.create_superuser("su", "su@x.pl", "x")
    client.force_login(su)
    resp = client.get("/ewaluacja_metryki/", HTTP_HOST=site1.domain)
    metryki = resp.context["metryki"]
    uczelnie = {m.uczelnia_id for m in metryki}
    assert uczelnie == {uczelnia1.pk}  # tylko uczelnia z site1
```

(URL i `context_object_name="metryki"` zweryfikuj w `urls.py`; dostosuj ścieżkę.)

- [ ] **Step 2: Run, verify fails**

Run: `uv run pytest "src/ewaluacja_metryki/tests/test_per_uczelnia.py::test_lista_metryk_filtruje_po_uczelni" -q -p no:cacheprovider`
Expected: FAIL — widać metryki obu uczelni.

- [ ] **Step 3: Update `list.py`**

W `get_queryset` (linia ~122) zawęź bazę po uczelni:

```python
    def get_queryset(self):
        from django.db.models import Count, OuterRef, Subquery

        from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

        from ..uczelnia_scope import scope_metryki

        uczelnia = uczelnia_dla_odczytu(self.request)
        discipline_count = (...)  # bez zmian
        queryset = scope_metryki(
            super().get_queryset()
            .select_related("autor", "dyscyplina_naukowa", "jednostka", "jednostka__wydzial")
            .annotate(autor_discipline_count=Subquery(discipline_count)),
            uczelnia,
        )
        queryset = self._apply_filters(queryset)
        queryset = self._apply_sorting(queryset)
        return queryset
```

`_get_status_context` (linia ~227) — status per-uczelnia:

```python
        from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

        uczelnia = uczelnia_dla_odczytu(self.request)
        status = StatusGenerowania.get_or_create(uczelnia=uczelnia)
```

- [ ] **Step 4: Update `statistics.py`**

W `StatystykiView` rozstrzygnij uczelnię raz i zbuduj `base`; wszystkie
`MetrykaAutora.objects.all()`/`.select_related(...)`/`.values(...)` zastąp
`base = scope_metryki(MetrykaAutora.objects.all(), uczelnia)` jako źródłem:

```python
    def get_queryset(self):
        from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

        from ..uczelnia_scope import scope_metryki

        uczelnia = uczelnia_dla_odczytu(self.request)
        return scope_metryki(
            MetrykaAutora.objects.select_related(
                "autor", "dyscyplina_naukowa", "jednostka"
            ),
            uczelnia,
        ).order_by("-srednia_za_slot_nazbierana")[:20]
```

W `get_context_data` rozstrzygnij `uczelnia` raz na górze i każde
`MetrykaAutora.objects.<...>` zamień na `scope_metryki(MetrykaAutora.objects.<...>, uczelnia)`
(top_autorzy_sloty, statystyki_globalne `wszystkie`, bottom_*, autorzy_zerowi_raw,
jednostki_stats, dyscypliny_stats, wykorzystanie_ranges). `wszystkie` policz raz:
`wszystkie = scope_metryki(MetrykaAutora.objects.all(), uczelnia)`.

- [ ] **Step 5: Run tests**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py src/ewaluacja_metryki/tests/test_views.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ewaluacja_metryki/views/statistics.py src/ewaluacja_metryki/views/list.py src/ewaluacja_metryki/tests/test_per_uczelnia.py
git commit -m "feat(metryki): read-side lista + statystyki filtrowane per uczelnia (D, task 7)"
```

---

## Task 8: Read-side `views/export.py` + `export_helpers.py` (Opcja A)

**Files:**
- Modify: `src/ewaluacja_metryki/export_helpers.py`, `src/ewaluacja_metryki/views/export.py`
- Test: `src/ewaluacja_metryki/tests/test_per_uczelnia.py`

- [ ] **Step 1: Write failing test (eksport globalny widzi tylko swoją uczelnię)**

```python
@pytest.mark.django_db
def test_export_globalne_stats_scoped(autor_jan_kowalski, dyscyplina1, uczelnia1, uczelnia2):
    from openpyxl import Workbook

    from ewaluacja_metryki.export_helpers import export_globalne_stats
    from ewaluacja_metryki.models import MetrykaAutora
    from ewaluacja_metryki.uczelnia_scope import scope_metryki

    _make_metryka(autor_jan_kowalski, dyscyplina1, uczelnia1)
    autor2 = baker.make("bpp.Autor")
    _make_metryka(autor2, dyscyplina1, uczelnia2)

    base = scope_metryki(MetrykaAutora.objects.all(), uczelnia1)
    ws = Workbook().active
    export_globalne_stats(ws, None, None, None, base_qs=base)
    # wiersz "Liczba autorów" == 1 (tylko uczelnia1)
    assert ws.cell(row=3, column=2).value == 1
```

- [ ] **Step 2: Run, verify fails**

Run: `uv run pytest "src/ewaluacja_metryki/tests/test_per_uczelnia.py::test_export_globalne_stats_scoped" -q -p no:cacheprovider`
Expected: FAIL — `export_globalne_stats() got unexpected keyword 'base_qs'`.

- [ ] **Step 3: Update `export_helpers.py` (każdy export_* przyjmuje base_qs)**

Każda funkcja `export_*` dostaje parametr `base_qs` i używa go zamiast
wewnętrznego `MetrykaAutora.objects.all()`/`.objects.<...>`. Wzorzec dla
`export_globalne_stats`:

```python
def export_globalne_stats(ws, header_font, header_fill, header_alignment, base_qs=None):
    from django.db.models import Avg, Count, Sum

    from .models import MetrykaAutora

    wszystkie = base_qs if base_qs is not None else MetrykaAutora.objects.all()
    ws.title = "Statystyki globalne"
    stats = wszystkie.aggregate(...)  # bez zmian
```

Analogicznie: `export_top_autorzy`, `export_top_sloty`, `export_bottom_pkd`,
`export_bottom_sloty`, `export_zerowi`, `export_jednostki`, `export_dyscypliny`,
`export_wykorzystanie` — wszystkie zamieniają `MetrykaAutora.objects` na
`base_qs` (gdzie robią `.select_related/.values/.filter`, startują od `base_qs`).

- [ ] **Step 4: Update `views/export.py`**

`ExportStatystykiXLSX.get` i `ExportListaXLSX.get` — rozstrzygnij uczelnię,
zbuduj `base_qs = scope_metryki(MetrykaAutora.objects.all(), uczelnia)` i
przekaż `base_qs=` do każdego wywołania helpera. Dla `ExportListaXLSX` (jeśli
buduje własny queryset `MetrykaAutora.objects.select_related(...)`) — owinąć w
`scope_metryki(..., uczelnia)`.

```python
        from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

        from ..uczelnia_scope import scope_metryki

        uczelnia = uczelnia_dla_odczytu(request)
        base_qs = scope_metryki(MetrykaAutora.objects.all(), uczelnia)
        # ...przy każdym export_*(ws, ..., base_qs=base_qs)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py src/ewaluacja_metryki/tests/test_views.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ewaluacja_metryki/export_helpers.py src/ewaluacja_metryki/views/export.py src/ewaluacja_metryki/tests/test_per_uczelnia.py
git commit -m "feat(metryki): eksporty XLSX scoped per uczelnia (base_qs, Opcja A) (D, task 8)"
```

---

## Task 9: Read-side `views/detail.py` + `views/pin_unpin.py`

**Files:**
- Modify: `src/ewaluacja_metryki/views/detail.py`, `src/ewaluacja_metryki/views/pin_unpin.py`
- Test: `src/ewaluacja_metryki/tests/test_per_uczelnia.py`

- [ ] **Step 1: Write failing test (ranking w jednostce nie miesza uczelni)**

```python
@pytest.mark.django_db
def test_detail_pozycja_w_jednostce_per_uczelnia(autor_jan_kowalski, dyscyplina1,
                                                  uczelnia1, uczelnia2):
    """_get_position_context liczy pozycję tylko w obrębie uczelni metryki."""
    from ewaluacja_metryki.models import MetrykaAutora
    from ewaluacja_metryki.views.detail import MetrykaDetailView

    jedn = baker.make("bpp.Jednostka", uczelnia=uczelnia1)
    m1 = _make_metryka(autor_jan_kowalski, dyscyplina1, uczelnia1, jednostka=jedn,
                       srednia_za_slot_nazbierana=Decimal("5.0"))
    # obca metryka w tej samej jednostce-id ale uczelnia2 (sztuczny edge)
    autor2 = baker.make("bpp.Autor")
    _make_metryka(autor2, dyscyplina1, uczelnia2, jednostka=jedn,
                  srednia_za_slot_nazbierana=Decimal("9.0"))

    view = MetrykaDetailView()
    ctx = view._get_position_context(m1)
    # liczba_w_jednostce liczona w obrębie uczelnia1 → 1 (tylko m1)
    assert ctx["liczba_w_jednostce"] == 1
```

- [ ] **Step 2: Run, verify fails**

Run: `uv run pytest "src/ewaluacja_metryki/tests/test_per_uczelnia.py::test_detail_pozycja_w_jednostce_per_uczelnia" -q -p no:cacheprovider`
Expected: FAIL — liczy 2 (miesza uczelnie).

- [ ] **Step 3: Update `detail.py`**

`_get_position_context` (linia ~366) — dodać `uczelnia=metryka.uczelnia` do obu
filtrów:

```python
        if metryka.jednostka:
            context["pozycja_w_jednostce"] = (
                MetrykaAutora.objects.filter(
                    jednostka=metryka.jednostka,
                    dyscyplina_naukowa=metryka.dyscyplina_naukowa,
                    uczelnia=metryka.uczelnia,
                    srednia_za_slot_nazbierana__gt=metryka.srednia_za_slot_nazbierana,
                ).count() + 1
            )
            context["liczba_w_jednostce"] = MetrykaAutora.objects.filter(
                jednostka=metryka.jednostka,
                dyscyplina_naukowa=metryka.dyscyplina_naukowa,
                uczelnia=metryka.uczelnia,
            ).count()
```

`get_context_data` `inne_dyscypliny` (linia ~396) — dodać `uczelnia=metryka.uczelnia`:

```python
        inne_dyscypliny = (
            MetrykaAutora.objects.filter(autor=metryka.autor, uczelnia=metryka.uczelnia)
            .exclude(pk=metryka.pk)
            .select_related("dyscyplina_naukowa")
            .order_by("dyscyplina_naukowa__nazwa")
        )
```

(`get_object` zostaje po `autor__slug`+`dyscyplina_naukowa__kod` — jeśli autor
ma metryki na >1 uczelni, dodać `.filter(uczelnia=uczelnia_dla_odczytu(request))`
do `queryset` w `get_object`, by pokazać metrykę uczelni oglądającego. Transitive
`Cache_Punktacja_Autora_Query` queries po `autor_id`+`dyscyplina_id` zostają.)

- [ ] **Step 4: Update `pin_unpin.py` redirect lookup**

Oba widoki (`PrzypnijDyscyplineView`, `OdepnijDyscyplineView`) — redirect lookup
`MetrykaAutora.objects.filter(autor_id, dyscyplina_naukowa_id)` (linie ~74, ~147)
dodać uczelnię autora (defense-in-depth):

```python
            from ..uczelnia_scope import scope_metryki
            from raport_slotow.uczelnia_helper import uczelnia_dla_odczytu

            metryka = scope_metryki(
                MetrykaAutora.objects.filter(
                    autor_id=autor_id, dyscyplina_naukowa_id=dyscyplina_id
                ),
                uczelnia_dla_odczytu(request),
            ).first()
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest src/ewaluacja_metryki/tests/test_per_uczelnia.py src/ewaluacja_metryki/tests/test_views.py -q -p no:cacheprovider`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ewaluacja_metryki/views/detail.py src/ewaluacja_metryki/views/pin_unpin.py src/ewaluacja_metryki/tests/test_per_uczelnia.py
git commit -m "feat(metryki): detail ranking + pin/unpin redirect per uczelnia (D, task 9)"
```

---

## Task 10: Admin — `uczelnia` w `MetrykaAutoraAdmin`

**Files:**
- Modify: `src/ewaluacja_metryki/admin.py:9-69`

- [ ] **Step 1: Update admin (parytet R2)**

```python
    list_display = [
        "autor", "dyscyplina_naukowa", "uczelnia", "jednostka",
        "slot_maksymalny", "slot_nazbierany", "punkty_nazbierane",
        "srednia_za_slot_nazbierana", "procent_wykorzystania_slotow",
        "data_obliczenia",
    ]
    list_filter = ["uczelnia", "dyscyplina_naukowa", "jednostka", "procent_wykorzystania_slotow"]
```

Fieldset „Podstawowe informacje": `{"fields": ("autor", "dyscyplina_naukowa", "uczelnia", "jednostka")}`.

- [ ] **Step 2: Smoke check (admin import + system check)**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py check`
Expected: "System check identified no issues".

- [ ] **Step 3: Commit**

```bash
git add src/ewaluacja_metryki/admin.py
git commit -m "feat(metryki): admin pokazuje uczelnia (parytet R2) (D, task 10)"
```

---

## Task 11: Migracja 0008 NOT NULL + pełna regresja

**Files:**
- Modify: `src/ewaluacja_metryki/models.py` (usunąć `null=True, blank=True`)
- Create: `src/ewaluacja_metryki/migrations/0008_uczelnia_notnull.py`

- [ ] **Step 1: Make FK NOT NULL in models**

`MetrykaAutora.uczelnia`: usunąć `null=True, blank=True`.
`StatusGenerowania.uczelnia`: usunąć `null=True, blank=True` (zostaje `unique=True`).

- [ ] **Step 2: Generate migration**

Run: `PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations ewaluacja_metryki --name uczelnia_notnull`
Expected: utworzy `0008_uczelnia_notnull.py` z dwoma `AlterField` (null=False).
Zweryfikuj treść (dwa `AlterField`, brak innych zmian).

- [ ] **Step 3: Full regression `ewaluacja_metryki`**

Run: `uv run pytest src/ewaluacja_metryki/ -q -p no:cacheprovider`
Expected: PASS. Jeśli któryś istniejący test tworzy `MetrykaAutora`/`StatusGenerowania`
bez uczelni i `model_bakery` nie dofilluje (lub dofilluje spurious Uczelnia
psując asercje count) — popraw fixture/test, dodając jawną `uczelnia=...`.

- [ ] **Step 4: Guard + sloty invariant + makemigrations check**

```bash
uv run pytest src/bpp/tests/test_multihosted_get_default_guard.py -q
PYTEST_TESTCONTAINERS_DISABLE=1 DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run
```
Expected: guard zielony (bez nowych wpisów); "No changes detected".

- [ ] **Step 5: Lint całość**

```bash
uv run ruff check src/ewaluacja_metryki/
uv run ruff format --check src/ewaluacja_metryki/
```
Expected: clean (fix ręcznie jeśli zgłosi).

- [ ] **Step 6: Commit**

```bash
git add src/ewaluacja_metryki/models.py src/ewaluacja_metryki/migrations/0008_uczelnia_notnull.py
git commit -m "feat(metryki): uczelnia NOT NULL po backfillu (D, task 11)"
```

---

## Self-Review (autor planu)

**Spec coverage:**
- Schemat MetrykaAutora FK+unique+index → Task 1. ✓
- StatusGenerowania per-uczelnia → Task 2. ✓
- Migracje 0006/0007/0008 (backfill clear-on-multi, NOT NULL) → Task 1/2/11. ✓
- Knapsack leak (`zbieraj_sloty(uczelnia_id)`) → Task 3 (Step 3/5). ✓
- Globalny delete + odczyt źródła → Task 3 (generuj_metryki) + Task 4/5. ✓
- Bulk tag z wiersza / pin-unpin z aktualna_jednostka → Task 3 (Step 3-5). ✓
- Taski single-or-fail + status per-uczelnia + chord callback uczelnia_id → Task 4. ✓
- CLI scope → Task 5. ✓
- generation view + status views → Task 6. ✓
- Read-side statistics/list/export/detail/pin_unpin + helper → Task 6-9. ✓
- Admin → Task 10. ✓
- Testy izolacji/invariant/knapsack/read/pin-unpin/status → rozsiane TDD + Task 11 regresja. ✓

**Założenia do zweryfikowania w trakcie (flagi dla wykonawcy):**
- Numery migracji `bpp` w `dependencies` (0428) i poprzedniej migracji metryki
  (0005) — potwierdzić `ls migrations/` + `makemigrations --check`.
- URL listy metryk w teście Task 7 — sprawdzić `ewaluacja_metryki/urls.py`.
- `model_bakery` zachowanie przy NOT NULL FK (Task 11) — może dofillować Uczelnia.
- Subtask `oblicz_metryki_dla_autora_task` + `StatusGenerowania.update` w trybie
  parallel (Task 4 Step 4) — przekazać `uczelnia_id` do subtaska.
