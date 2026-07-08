# Opis bibliograficzny z dysku zamiast dbtemplates — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wyrwać `opis_bibliograficzny.html` z django-dbtemplates — dysk staje się jedynym źródłem prawdy; mapowanie per-model przeżywa jako nazwa pliku; migracja kasuje wiersz i przebudowuje denorm (FD#329 naprawia się samo przy podbiciu wydania); przy okazji naprawić mylący `compare_dbtemplates`.

**Architecture:** Model `SzablonDlaOpisuBibliograficznego.template` (FK→`dbtemplates.Template`, PROTECT) zamieniony na `nazwa_szablonu` (CharField). Render dalej przez `get_template(name)` — po skasowaniu wiersza dbtemplates dysk wygrywa. Współdzielona funkcja `usun_dbtemplate_i_przebuduj(name, modele, *, flush)` (guard dysk-existence + log treści + delete + czyszczenie cache + rebuild denorma) używana przez migrację (async flush) i `drop_dbtemplate` (sync flush). Nowy helper `disk_template_source(name)` czyta źródło z dysku z pominięciem loadera dbtemplates — używany przez naprawę `compare_dbtemplates`.

**Tech Stack:** Django 5.2, django-dbtemplates, django-denorm (async przez kolejkę `denorm`), pytest + pytest-django + model_bakery, towncrier.

## Global Constraints

- **Wszystkie polecenia Pythona przez `uv run`** (nigdy goły `python`).
- **Max 88 znaków/linia** (ruff).
- **NIE modyfikować istniejących migracji** — tylko nowy plik migracji.
- **Testy: pytest, bez klas**, `@pytest.mark.django_db`, `model_bakery.baker.make`.
- **`pre-commit` bez argumentów**; ruff bez `--fix` — poprawki ręczne (Edit).
- Praca w worktree `~/Programowanie/bpp-fix-fd329-opis-z-dysku` (gałąź `fix-fd329-opis-z-dysku`).
- Commit trailer: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Po scaleniu (osobno, nie w tym planie): `make baseline-update`.

---

### Task 1: Helper `disk_template_source` — źródło szablonu z dysku (bez dbtemplates)

**Files:**
- Create: `src/bpp/util/dbtemplates_disk.py`
- Test: `src/bpp/tests/test_dbtemplates_disk.py`

**Interfaces:**
- Produces: `disk_template_source(name: str) -> str | None` — źródło szablonu `name` z dysku (filesystem + app_directories), z pominięciem loadera dbtemplates; `None` gdy brak pliku na dysku.

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_dbtemplates_disk.py
from bpp.util.dbtemplates_disk import disk_template_source


def test_disk_template_source_zwraca_zrodlo_z_dysku():
    # opis_bibliograficzny.html na pewno jest w src/bpp/templates/ (app dir)
    src = disk_template_source("opis_bibliograficzny.html")
    assert src is not None
    # gałąź #329 z dysku (dowód, że to DYSK, nie stary wiersz DB):
    assert "book_title" in src


def test_disk_template_source_none_gdy_brak_pliku():
    assert disk_template_source("nie-ma-takiego-pliku-xyz.html") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_dbtemplates_disk.py -v`
Expected: FAIL — `ModuleNotFoundError: bpp.util.dbtemplates_disk`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/bpp/util/dbtemplates_disk.py
"""Ładowanie ŹRÓDŁA szablonu z dysku z pominięciem loadera dbtemplates.

``get_template`` z Django idzie łańcuchem loaderów, w którym dbtemplates stoi
pierwszy — więc dla nazwy istniejącej w bazie zwraca treść z DB, nie z dysku.
Ten helper konstruuje własny ``Engine`` wyłącznie z loaderami dyskowymi, żeby
odpowiedzieć na pytanie „co jest NA DYSKU pod tą nazwą"."""

from django.conf import settings
from django.template import Engine, TemplateDoesNotExist

_disk_engine = None


def _get_disk_engine():
    global _disk_engine
    if _disk_engine is None:
        dirs = []
        for cfg in settings.TEMPLATES:
            if cfg.get("BACKEND", "").endswith("DjangoTemplates"):
                dirs = list(cfg.get("DIRS", []))
                break
        # Jawne loadery dyskowe (bez cached, bez dbtemplates) — świeży odczyt
        # z dysku przy każdym wywołaniu. NIE 'loaders=[...] + app_dirs=True'
        # (ImproperlyConfigured w Dj5.2).
        # libraries/builtins skopiowane z domyślnego Engine — inaczej surowy
        # Engine nie zna custom tag-libów ({% load prace %} w opisie), bo tylko
        # backend DjangoTemplates auto-odkrywa je z INSTALLED_APPS.
        default = Engine.get_default()
        _disk_engine = Engine(
            dirs=dirs,
            loaders=[
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            libraries=default.libraries,
            builtins=default.builtins,
        )
    return _disk_engine


def disk_template_source(name):
    try:
        template = _get_disk_engine().get_template(name)
    except TemplateDoesNotExist:
        return None
    return template.source
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_dbtemplates_disk.py -v`
Expected: PASS (oba testy).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/util/dbtemplates_disk.py src/bpp/tests/test_dbtemplates_disk.py
git commit -m "feat(dbtemplates): helper disk_template_source — źródło z dysku bez dbtemplates (#329)"
```

---

### Task 2: Naprawa `compare_dbtemplates` (czytał DB zamiast dysku)

**Files:**
- Modify: `src/bpp/management/commands/compare_dbtemplates.py:322-377` (metoda `get_filesystem_template_content`)
- Test: `src/bpp/tests/test_management_commands_compare_dbtemplates.py` (dopisz repro-test)

**Interfaces:**
- Consumes: `disk_template_source` (Task 1).

- [ ] **Step 1: Write the failing repro test**

Dopisz na końcu `src/bpp/tests/test_management_commands_compare_dbtemplates.py`:

```python
import pytest
from dbtemplates.models import Template
from django.core.management import call_command
from io import StringIO


@pytest.mark.django_db
def test_compare_wykrywa_rozjazd_db_vs_dysk():
    """Regresja: dawniej compare czytał 'dysk' przez get_template (loader
    dbtemplates pierwszy) => DB-vs-DB => zawsze 'match'. Teraz czyta faktyczny
    dysk => rozjazd MUSI być widoczny."""
    Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": "TRESC-DB-INNA-NIZ-DYSK"},
    )
    out = StringIO()
    call_command("compare_dbtemplates", "opis_bibliograficzny.html", stdout=out)
    output = out.getvalue()
    assert "match" not in output.lower()
    assert "TRESC-DB-INNA-NIZ-DYSK" in output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_management_commands_compare_dbtemplates.py::test_compare_wykrywa_rozjazd_db_vs_dysk -v`
Expected: FAIL — obecny kod raportuje „All templates match" (czyta treść z DB po obu stronach).

- [ ] **Step 3: Zastąp `get_filesystem_template_content`**

Zamień CAŁĄ metodę `get_filesystem_template_content` (linie ~322-377) na:

```python
    def get_filesystem_template_content(self, template_name):
        """Źródło szablonu z DYSKU (z pominięciem loadera dbtemplates).

        Dawniej używała ``get_template()``, który idzie łańcuchem loaderów z
        dbtemplates na pierwszym miejscu — więc dla nazwy istniejącej w bazie
        zwracała treść z DB i porównanie było DB-vs-DB (zawsze 'match')."""
        from bpp.util.dbtemplates_disk import disk_template_source

        return disk_template_source(template_name)
```

Usuń teraz-nieużywane importy w nagłówku pliku, jeśli zostały osierocone:
`from django.template import TemplateDoesNotExist`, `from pathlib import Path`,
`from bpp.util import zaloguj_polkniety_wyjatek`, `import logging`, `import sys`
(sprawdź, czy `sys`/`logging` nie są używane gdzie indziej w pliku — `sys.stdout.isatty()`
w `_colorize` używa `sys`; zostaw `import sys`). Uruchom ruff, poprawki ręcznie.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_management_commands_compare_dbtemplates.py -v`
Expected: PASS (nowy repro + istniejące testy pliku).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/management/commands/compare_dbtemplates.py src/bpp/tests/test_management_commands_compare_dbtemplates.py
git commit -m "fix(dbtemplates): compare_dbtemplates czytał DB zamiast dysku (#329)"
```

---

### Task 3: Współdzielona funkcja `usun_dbtemplate_i_przebuduj`

**Files:**
- Modify: `src/bpp/dbtemplates_sync.py` (dopisz funkcję)
- Test: `src/bpp/tests/test_dbtemplates_sync.py`

**Interfaces:**
- Consumes: `disk_template_source` (Task 1); `wyczysc_cache_dbtemplate` (istnieje w tym pliku); `rebuild_instances_of_models` (`bpp.util`).
- Produces: `usun_dbtemplate_i_przebuduj(name: str, modele: list, *, flush: bool = False, log=None) -> bool` — GUARD: kasuje wiersz dbtemplate `name` tylko gdy `disk_template_source(name) is not None` (zwraca `False` gdy pominięto). Przed delete loguje treść. Po delete czyści cache dbtemplates (synchronicznie). Oznacza `modele` dirty; `flush=True` → synchroniczny `denorms.flush()`.

- [ ] **Step 1: Write the failing tests**

```python
# src/bpp/tests/test_dbtemplates_sync.py
import pytest
from dbtemplates.models import Template

from bpp.dbtemplates_sync import usun_dbtemplate_i_przebuduj
from bpp.models import Wydawnictwo_Zwarte
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)
from pbn_api.models import Publication


@pytest.mark.django_db
def test_usun_guard_nie_kasuje_gdy_brak_pliku_na_dysku():
    """DB-only custom bez pliku na dysku — NIE kasować (inaczej dyndająca
    nazwa -> TemplateDoesNotExist -> opis wybucha przy flushu denorma)."""
    Template.objects.create(name="tylko-w-bazie-xyz.html", content="treść")
    wynik = usun_dbtemplate_i_przebuduj("tylko-w-bazie-xyz.html", [])
    assert wynik is False
    assert Template.objects.filter(name="tylko-w-bazie-xyz.html").exists()


@pytest.mark.django_db
def test_usun_kasuje_gdy_plik_na_dysku_i_odswieza_opis(wydawnictwo_zwarte):
    """opis_bibliograficzny.html JEST na dysku -> kasuj wiersz; po rebuildzie
    opis pokazuje rodzica z PBN object.book (dowód naprawy FD#329)."""
    pbn_pub = Publication.objects.create(
        mongoId="sync-rozdzial",
        versions=[
            {"current": True, "object": {"book": {"title": "Rodzic Z Dysku"}}}
        ],
    )
    wydawnictwo_zwarte.pbn_uid = pbn_pub
    wydawnictwo_zwarte.wydawnictwo_nadrzedne = None
    wydawnictwo_zwarte.wydawnictwo_nadrzedne_w_pbn = None
    wydawnictwo_zwarte.informacje = ""
    wydawnictwo_zwarte.zrodlo = None
    wydawnictwo_zwarte.save()

    # Funkcja robi template.delete(); w produkcji leci PO usunięciu FK
    # (migracja RemoveField przed purge; drop_dbtemplate — post-migracja), więc
    # nic go nie PROTECT-uje. Odwzoruj ten warunek: usuń zasiane powiązania
    # SzablonDlaOpisu (seed z 0295/baseline chroni wiersz -> ProtectedError,
    # artefakt świata sprzed migracji).
    SzablonDlaOpisuBibliograficznego.objects.all().delete()

    Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": "STARY-SZABLON-MARKER"},
    )

    wynik = usun_dbtemplate_i_przebuduj(
        "opis_bibliograficzny.html", [Wydawnictwo_Zwarte], flush=True
    )

    assert wynik is True
    assert not Template.objects.filter(name="opis_bibliograficzny.html").exists()
    wydawnictwo_zwarte.refresh_from_db()
    assert "W: Rodzic Z Dysku." in wydawnictwo_zwarte.opis_bibliograficzny_cache
    assert "STARY-SZABLON-MARKER" not in wydawnictwo_zwarte.opis_bibliograficzny_cache
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/bpp/tests/test_dbtemplates_sync.py -v`
Expected: FAIL — `ImportError: cannot import name 'usun_dbtemplate_i_przebuduj'`.

- [ ] **Step 3: Dopisz funkcję do `src/bpp/dbtemplates_sync.py`**

```python
def usun_dbtemplate_i_przebuduj(name, modele, *, flush=False, log=None):
    """Skasuj wiersz dbtemplate ``name`` (render spadnie na dysk) i oznacz
    ``modele`` do przebudowy denorma. Współdzielone przez migrację i komendę
    ``drop_dbtemplate``.

    GUARD: kasuje TYLKO gdy nazwa ma odpowiednik na dysku
    (``disk_template_source(name) is not None``). Wiersz DB-only bez pliku na
    dysku zostaje nietknięty — inaczej ``nazwa_szablonu`` zostałaby dyndająca i
    ``get_template`` rzucałby ``TemplateDoesNotExist`` przy każdym renderze /
    flushu denorma. Zwraca ``False`` gdy pominięto (guard), ``True`` gdy
    skasowano lub wiersza nie było mimo pliku na dysku.

    ``flush=True`` → synchroniczny ``denorms.flush()`` (komenda deployowa chce
    odświeżyć od ręki); ``flush=False`` → tylko oznaczenie dirty (async kolejka
    ``denorm`` dokończy — użycie w migracji)."""
    from dbtemplates.models import Template

    from bpp.util import rebuild_instances_of_models
    from bpp.util.dbtemplates_disk import disk_template_source

    log = log or (lambda msg: None)

    if disk_template_source(name) is None:
        log(
            f"[guard] '{name}' nie ma pliku na dysku — NIE kasuję wiersza "
            f"dbtemplate (zostawiam, by nie zdyndać nazwy_szablonu)."
        )
        return False

    tpl = Template.objects.filter(name=name).first()
    if tpl is not None:
        log(f"[usuwam dbtemplate '{name}'] backup treści:\n{tpl.content}")
        tpl.delete()
        # Cache dbtemplates nie znika sam (delete modelem historycznym nie
        # odpala sygnałów); czyścimy synchronicznie jak drop_dbtemplate.
        wyczysc_cache_dbtemplate(name)

    if modele:
        rebuild_instances_of_models(list(modele))
        if flush:
            from denorm import denorms

            denorms.flush()

    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_dbtemplates_sync.py -v`
Expected: PASS (oba).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/dbtemplates_sync.py src/bpp/tests/test_dbtemplates_sync.py
git commit -m "feat(dbtemplates): usun_dbtemplate_i_przebuduj — guard + rebuild denorma (#329)"
```

---

### Task 4: Model `SzablonDlaOpisuBibliograficznego` — FK→`nazwa_szablonu` + migracja

**Files:**
- Modify: `src/bpp/models/szablondlaopisubibliograficznego.py` (całość — pola, manager, render, `__str__`, `clean`)
- Create: `src/bpp/migrations/0468_szablon_nazwa_szablonu.py`
- Modify: `src/bpp/tests/test_opis_bibliograficzny.py` (usuń `_sync`; `template=`→`nazwa_szablonu=`)

**Interfaces:**
- Consumes: `usun_dbtemplate_i_przebuduj` (Task 3).
- Produces: pole `nazwa_szablonu` (CharField); `manager.get_for_model(model) -> str | None`; `manager.get_models_for_szablon(nazwa) -> list`; `manager.all_templated_models`; instancja: `.render(praca)`, `.get_models_for_this_szablon()`, `.clean()`.

- [ ] **Step 1: Napisz/zmigruj testy (failing)**

W `src/bpp/tests/test_opis_bibliograficzny.py`:
1. Usuń funkcję `_sync_opis_template_z_dysku` (linie ~16-31) i jej wywołanie (linia ~145).
2. Zamień wszystkie `template=<X>` w `SzablonDlaOpisuBibliograficznego.objects.create(...)` / `sz.template = <X>` na `nazwa_szablonu=<X>.name` / `sz.nazwa_szablonu = <X>.name`. Konkretnie:
   - linia ~47: `create(nazwa_szablonu=test_template.name)`
   - linia ~50: `create(nazwa_szablonu=test_template.name)`
   - linia ~63: `sz.nazwa_szablonu = test_template.name`
   - linia ~66: `create(nazwa_szablonu=test_template.name)`
   - linia ~74: `nazwa_szablonu=second_template.name`
   (Wiersze dbtemplates `test`/`2nd` nadal są tworzone — loader dbtemplates serwuje je po nazwie, więc `opis_bibliograficzny()` zwróci ich treść.)
3. Dopisz test na `clean()`:

```python
@pytest.mark.django_db
def test_clean_odrzuca_nieistniejacy_szablon():
    from django.core.exceptions import ValidationError

    sz = SzablonDlaOpisuBibliograficznego(nazwa_szablonu="nie-istnieje-xyz.html")
    with pytest.raises(ValidationError):
        sz.clean()


@pytest.mark.django_db
def test_clean_przepuszcza_szablon_z_dysku():
    sz = SzablonDlaOpisuBibliograficznego(
        nazwa_szablonu="opis_bibliograficzny.html"
    )
    sz.clean()  # nie rzuca
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/bpp/tests/test_opis_bibliograficzny.py -v`
Expected: FAIL — `nazwa_szablonu` nie istnieje na modelu / brak kolumny (migracji jeszcze nie ma).

- [ ] **Step 3: Zmień model** `src/bpp/models/szablondlaopisubibliograficznego.py`

Zamień zawartość na (zachowując importy + dopisując `ValidationError`, `TemplateDoesNotExist`):

```python
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils.functional import cached_property


class SzablonDlaOpisuBibliograficznegoManager(models.Manager):
    def get_for_model(self, model):
        model = ContentType.objects.get_for_model(model)
        try:
            return self.get(model=model).nazwa_szablonu
        except SzablonDlaOpisuBibliograficznego.DoesNotExist:
            try:
                return self.get(model=None).nazwa_szablonu
            except SzablonDlaOpisuBibliograficznego.DoesNotExist:
                return

    @cached_property
    def all_templated_models(self):
        from bpp.models.patent import Patent
        from bpp.models.praca_doktorska import Praca_Doktorska
        from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
        from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
        from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

        return [
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Patent,
        ]

    def get_models_for_szablon(self, nazwa_szablonu):
        """Lista modeli mapowanych na dany szablon (po nazwie)."""
        res = list(
            self.filter(nazwa_szablonu=nazwa_szablonu)
            .values_list("model", flat=True)
            .distinct()
        )
        if None in res:
            return self.all_templated_models
        return [ContentType.objects.get_for_id(id).model_class() for id in res]


class SzablonDlaOpisuBibliograficznego(models.Model):
    objects = SzablonDlaOpisuBibliograficznegoManager()

    model = models.OneToOneField(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(
            app_label="bpp",
            model__in=[
                "wydawnictwo_ciagle",
                "wydawnictwo_zwarte",
                "praca_doktorska",
                "praca_habilitacyjna",
                "patent",
            ],
        ),
        null=True,
        blank=True,
    )

    nazwa_szablonu = models.CharField(
        max_length=255,
        default="opis_bibliograficzny.html",
        help_text=(
            "Nazwa szablonu Django ładowanego z dysku, "
            "np. opis_bibliograficzny.html"
        ),
    )

    def __str__(self):
        if self.model_id is not None:
            return (
                f"Powiązanie szablonu {self.nazwa_szablonu} z modelem {self.model}"
            )
        return f"Powiązanie szablonu {self.nazwa_szablonu} z każdym modelem"

    class Meta:
        verbose_name = "powiązanie szablonu dla opisu bibliograficznego"
        verbose_name_plural = "powiązania szablonów dla opisu bibliograficznego"

    def clean(self):
        try:
            get_template(self.nazwa_szablonu)
        except TemplateDoesNotExist:
            raise ValidationError(
                {
                    "nazwa_szablonu": (
                        f"Szablon '{self.nazwa_szablonu}' nie istnieje "
                        f"(ani na dysku, ani w dbtemplates)."
                    )
                }
            )

    def render(self, praca):
        template = get_template(self.nazwa_szablonu)

        return (
            template.render(
                dict(praca=praca, autorzy=praca.autorzy_set.all().select_related())
            )
            .replace("\r\n", "")
            .replace("\n", "")
            .replace(".</b>[", ".</b> [")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace(" , ", ", ")
            .replace(" . ", ". ")
            .replace(". . ", ". ")
            .replace(". , ", ". ")
            .replace("., ", ". ")
            .replace(" .", ".")
        )

    def get_models_for_this_szablon(self):
        return SzablonDlaOpisuBibliograficznego.objects.get_models_for_szablon(
            self.nazwa_szablonu
        )
```

- [ ] **Step 4: Utwórz migrację** `src/bpp/migrations/0468_szablon_nazwa_szablonu.py`

```python
from django.db import migrations, models


def backfill_nazwa(apps, schema_editor):
    Szablon = apps.get_model("bpp", "SzablonDlaOpisuBibliograficznego")
    Template = apps.get_model("dbtemplates", "Template")
    for row in Szablon.objects.all():
        if row.template_id:
            row.nazwa_szablonu = Template.objects.get(pk=row.template_id).name
            row.save(update_fields=["nazwa_szablonu"])


def purge_opis_dbtemplate(apps, schema_editor):
    # Konkretne klasy modeli (denorm rebuild jak w drop_dbtemplate). Import w
    # ciele funkcji — bezpieczny w tym punkcie migracji.
    from bpp.dbtemplates_sync import usun_dbtemplate_i_przebuduj
    from bpp.models.patent import Patent
    from bpp.models.praca_doktorska import Praca_Doktorska
    from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
    from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
    from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

    modele = [
        Wydawnictwo_Ciagle,
        Wydawnictwo_Zwarte,
        Praca_Doktorska,
        Praca_Habilitacyjna,
        Patent,
    ]
    Szablon = apps.get_model("bpp", "SzablonDlaOpisuBibliograficznego")
    nazwy = {n for n in Szablon.objects.values_list("nazwa_szablonu", flat=True) if n}
    for name in sorted(nazwy):
        # guard (dysk) + log + delete + czyszczenie cache + oznaczenie dirty.
        # flush=False -> async kolejka denorm dokończy (migracja nieblokująca).
        usun_dbtemplate_i_przebuduj(name, modele, flush=False, log=print)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ("bpp", "0467_seed_crossref_mapper_rows"),
        ("dbtemplates", "0002_alter_template_creation_date_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="szablondlaopisubibliograficznego",
            name="nazwa_szablonu",
            field=models.CharField(
                default="opis_bibliograficzny.html", max_length=255
            ),
        ),
        migrations.RunPython(backfill_nazwa, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="szablondlaopisubibliograficznego",
            name="template",
        ),
        migrations.RunPython(purge_opis_dbtemplate, migrations.RunPython.noop),
    ]
```

- [ ] **Step 5: Sanity — brak dryfu migracji poza naszą**

Run: `uv run python src/manage.py makemigrations --check --dry-run bpp`
Expected: brak nowych migracji do wygenerowania (nasz plik pokrywa zmianę modelu). Jeśli Django chce dogenerować `AlterField`/help_text — dopisz brakującą operację do 0468.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_opis_bibliograficzny.py -v`
Expected: PASS (render #329 bez `_sync`; `clean()`; rozne_opisy; nulltest).

- [ ] **Step 7: Commit**

```bash
git add src/bpp/models/szablondlaopisubibliograficznego.py \
  src/bpp/migrations/0468_szablon_nazwa_szablonu.py \
  src/bpp/tests/test_opis_bibliograficzny.py
git commit -m "feat(opis): SzablonDlaOpisu FK->nazwa_szablonu + migracja kasująca wiersz (#329)"
```

---

### Task 5: `drop_dbtemplate` — odsprzęgnięcie od FK + współdzielona funkcja

**Files:**
- Modify: `src/bpp/management/commands/drop_dbtemplate.py`
- Modify: `src/bpp/tests/test_management_commands_drop_dbtemplate.py`

**Interfaces:**
- Consumes: `usun_dbtemplate_i_przebuduj` (Task 3); `get_models_for_szablon` (Task 4).

- [ ] **Step 1: Zmigruj testy (failing)**

W `src/bpp/tests/test_management_commands_drop_dbtemplate.py`:
1. `test_drop_dbtemplate_usuwa_wiersz_i_chroniacy_szablon` — po zmianie `SzablonDlaOpisu` NIE jest już kasowany (nie ma FK). Przepisz asercje:

```python
@pytest.mark.django_db
def test_drop_dbtemplate_usuwa_wiersz_zostawia_mapowanie():
    """Po odsprzęgnięciu: kasujemy wiersz dbtemplate, ale wpis SzablonDlaOpisu
    (mapowanie po nazwie) ZOSTAJE — jego nazwa_szablonu rozwiązuje się z dysku."""
    Template.objects.update_or_create(
        name="opis_bibliograficzny.html", defaults={"content": "stara treść"}
    )
    SzablonDlaOpisuBibliograficznego.objects.get_or_create(
        model=None, defaults={"nazwa_szablonu": "opis_bibliograficzny.html"}
    )

    call_command("drop_dbtemplate", "opis_bibliograficzny.html", "--skip-rebuild")

    assert not Template.objects.filter(name="opis_bibliograficzny.html").exists()
    assert SzablonDlaOpisuBibliograficznego.objects.filter(
        nazwa_szablonu="opis_bibliograficzny.html"
    ).exists()
```

2. `test_drop_dbtemplate_przebudowuje_cache_z_dysku` — zamień
   `get_or_create(model=None, defaults={"template": tpl})` na
   `get_or_create(model=None, defaults={"nazwa_szablonu": "opis_bibliograficzny.html"})`.
   Reszta (asercje na cache) bez zmian.
3. `test_drop_dbtemplate_idempotentne_gdy_brak_wiersza` — bez zmian.

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest src/bpp/tests/test_management_commands_drop_dbtemplate.py -v`
Expected: FAIL — obecna komenda używa `filter(template=...)` / `get_models_for_template`, których już nie ma po Task 4 (albo asercje nie pasują).

- [ ] **Step 3: Przepisz `drop_dbtemplate.py`**

Zamień ciało `handle` (i importy) na wersję używającą współdzielonej funkcji:

```python
"""Usuń wiersz(e) dbtemplate z bazy (render spada na plik z dysku) i przebuduj
zależny ``opis_bibliograficzny_cache``.

Po wyrwaniu opisu z dbtemplates (#329) ``SzablonDlaOpisuBibliograficznego`` nie
ma już FK do ``Template`` — trzyma tylko ``nazwa_szablonu``. Komenda przestała
więc kasować powiązania; kasuje sam wiersz dbtemplate (z guardem dysk-existence)
i przebudowuje denorm dla modeli mapowanych na tę nazwę."""

from django.core.management.base import BaseCommand
from django.db import transaction

from bpp.dbtemplates_sync import usun_dbtemplate_i_przebuduj
from bpp.models.szablondlaopisubibliograficznego import (
    SzablonDlaOpisuBibliograficznego,
)


class Command(BaseCommand):
    help = (
        "Usuwa wiersz(e) dbtemplate z bazy (render spada na plik z dysku) i "
        "przebudowuje zależny opis_bibliograficzny_cache."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "template_names",
            nargs="+",
            help="Nazwy szablonów do usunięcia, np. opis_bibliograficzny.html",
        )
        parser.add_argument(
            "--skip-rebuild",
            action="store_true",
            help="Nie przebudowuj opis_bibliograficzny_cache (sam usuń wiersze).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        for name in options["template_names"]:
            modele = (
                []
                if options["skip_rebuild"]
                else SzablonDlaOpisuBibliograficznego.objects.get_models_for_szablon(
                    name
                )
            )
            usunieto = usun_dbtemplate_i_przebuduj(
                name, modele, flush=True, log=self.stdout.write
            )
            if usunieto:
                self.stdout.write(self.style.SUCCESS(f"Przetworzono '{name}'."))
            else:
                self.stderr.write(
                    self.style.WARNING(
                        f"'{name}' nie ma pliku na dysku — pominięto (guard)."
                    )
                )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_management_commands_drop_dbtemplate.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/management/commands/drop_dbtemplate.py src/bpp/tests/test_management_commands_drop_dbtemplate.py
git commit -m "refactor(drop_dbtemplate): odsprzęgnięcie od FK + współdzielona funkcja (#329)"
```

---

### Task 6: Admin — `list_display` + `template_updated`

**Files:**
- Modify: `src/bpp/admin/szablondlaopisubibliograficznego.py:9`
- Modify: `src/bpp/admin/templates.py:71`
- Test: `src/bpp/tests/test_admin/test_templateadmin.py` (zmigruj `template=`; dopisz smoke changelist)

**Interfaces:**
- Consumes: `get_models_for_szablon` (Task 4).

- [ ] **Step 1: Zmigruj/napisz test (failing)**

W `src/bpp/tests/test_admin/test_templateadmin.py` zamień `create(template=<X>)` na
`create(nazwa_szablonu=<X>.name)` (linie ~22, 62, 96 wg wcześniejszego sweepu — potwierdź `grep -n "template=" src/bpp/tests/test_admin/test_templateadmin.py`). Dopisz smoke:

```python
@pytest.mark.django_db
def test_szablon_admin_changelist_dziala(admin_client):
    from bpp.models.szablondlaopisubibliograficznego import (
        SzablonDlaOpisuBibliograficznego,
    )

    SzablonDlaOpisuBibliograficznego.objects.get_or_create(
        model=None, defaults={"nazwa_szablonu": "opis_bibliograficzny.html"}
    )
    resp = admin_client.get(
        "/admin/bpp/szablondlaopisubibliograficznego/"
    )
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_admin/test_templateadmin.py -v`
Expected: FAIL — `list_display=["model","template"]` odwołuje się do usuniętego pola → changelist 500 / błąd systemowy.

- [ ] **Step 3: Popraw adminy**

W `src/bpp/admin/szablondlaopisubibliograficznego.py:9`:

```python
    list_display = ["model", "nazwa_szablonu"]
```

W `src/bpp/admin/templates.py:71` (metoda `template_updated`) zamień:

```python
        modele = SzablonDlaOpisuBibliograficznego.objects.get_models_for_template(obj)
```

na:

```python
        modele = SzablonDlaOpisuBibliograficznego.objects.get_models_for_szablon(
            obj.name
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_admin/test_templateadmin.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/admin/szablondlaopisubibliograficznego.py src/bpp/admin/templates.py src/bpp/tests/test_admin/test_templateadmin.py
git commit -m "fix(admin): SzablonDlaOpisu list_display + template_updated na nazwę (#329)"
```

---

### Task 7: Usuń martwą fixture `szablony`

**Files:**
- Modify: `src/fixtures/conftest.py:66-99`

- [ ] **Step 1: Potwierdź brak konsumentów**

Run: `git grep -nw "szablony" -- 'src/**/*.py' | grep -v "def szablony"`
Expected: brak wyników (fixture nieużywana).

- [ ] **Step 2: Usuń fixture**

Usuń całą definicję `@pytest.fixture def szablony(): ...` (linie ~66-99) z `src/fixtures/conftest.py`.

- [ ] **Step 3: Sanity — kolekcja testów nie pada**

Run: `uv run pytest src/bpp/tests/test_opis_bibliograficzny.py --collect-only -q`
Expected: kolekcja OK, brak błędu o brakującej fixture.

- [ ] **Step 4: Commit**

```bash
git add src/fixtures/conftest.py
git commit -m "chore(tests): usuń nieużywaną fixture szablony (#329)"
```

---

### Task 8: Newsfragment + weryfikacja całości

**Files:**
- Create: `src/bpp/newsfragments/+fd329.bugfix.md`

- [ ] **Step 1: Newsfragment (orphan `+`, bo FD, nie GH issue)**

```markdown
Rozdziały z wydawnictwem nadrzędnym pobranym z PBN pokazują teraz to
wydawnictwo w opisie bibliograficznym ("W: tytuł"). Opis bibliograficzny
przestał być trzymany w bazie (dbtemplates) — jest brany wprost z aktualnego
szablonu na dysku, więc poprawki szablonu działają od razu po aktualizacji,
bez ręcznej synchronizacji (FD#329).
```

- [ ] **Step 2: ruff + pre-commit (poprawki RĘCZNE)**

Run: `uv run ruff format src/bpp && uv run ruff check src/bpp`
Run: `pre-commit`
Expected: czysto. Błędy poprawiaj ręcznie (Edit), NIE `--fix`.

- [ ] **Step 3: Testy dotkniętych obszarów**

Run:
```
uv run pytest src/bpp/tests/test_dbtemplates_disk.py \
  src/bpp/tests/test_dbtemplates_sync.py \
  src/bpp/tests/test_opis_bibliograficzny.py \
  src/bpp/tests/test_management_commands_drop_dbtemplate.py \
  src/bpp/tests/test_management_commands_compare_dbtemplates.py \
  src/bpp/tests/test_admin/test_templateadmin.py -v
```
Expected: wszystko PASS.

- [ ] **Step 4: Migracja stosuje się na czysto (walidacja jak baseline-update)**

Run: `uv run python src/manage.py migrate bpp 0468 --plan`
Expected: plan pokazuje 0468 do zastosowania (bez błędu importu / zależności).

- [ ] **Step 5: Commit**

```bash
git add src/bpp/newsfragments/+fd329.bugfix.md
git commit -m "docs(newsfragment): opis nadrzędnego z PBN + opis z dysku (FD#329)"
```

---

## Self-Review (wykonane)

**Spec coverage:** §1 model→Task 4; §2 helper→Task 1; §3 compare→Task 2; §4 migracja+guard+denorm→Task 3+4; §5 drop_dbtemplate→Task 5; §6 konsumenci (admin/templates, list_display, testy, fixture, `_sync`)→Task 4/6/7; §Testy→rozłożone; newsfragment→Task 8. Brak luk.

**Placeholder scan:** brak TBD/„handle edge cases"/„similar to" — każdy krok ma realny kod/komendę.

**Type consistency:** `nazwa_szablonu` (pole), `disk_template_source(name)->str|None`, `usun_dbtemplate_i_przebuduj(name, modele, *, flush, log)->bool`, `get_models_for_szablon(nazwa)->list` — spójne między Task 1/3/4/5/6.
