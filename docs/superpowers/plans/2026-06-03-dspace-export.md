# DSpace Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eksport rekordów publikacji BPP do zewnętrznych instalacji DSpace 9.x przez REST API, wachlarzem per-uczelnia (afiliacje autorów), z routingiem po `Charakter_Formalny` na kolekcje DSpace.

**Architecture:** Nowa app `src/dspace_api/` lustrzana do `pbn_api`: adaptery serializują rekord do dict Dublin Core, `DSpaceClient` (otoczka na `dspace-rest-client`) gada z API, `SentToDSpace` śledzi stan per (rekord, uczelnia). Konfiguracja = pola `dspace_*` na `Uczelnia` (hasło szyfrowane współdzielonym `EncryptedTextField`). Wyzwalanie: akcje admina jak PBN. MVP = eksport metadanowy; upload bitstreamów to bramkowana faza 10.

**Tech Stack:** Django, `dspace-rest-client` (BSD-3), `cryptography` (Fernet), Celery (`django_bpp.celery_tasks.app`), pytest + model_bakery.

**Spec:** `docs/superpowers/specs/2026-06-03-dspace-export-design.md`

**Konwencje repo (KRYTYCZNE):**
- Zawsze `uv run` przed komendami Pythona. Nigdy gołe `python`.
- Max 88 znaków/linia (ruff). Brak `except: pass`.
- NIGDY nie modyfikuj istniejących migracji. Nowe migracje `bpp` od numeru **0421**; migracje `dspace_api` od `0001`.
- Po każdym zadaniu uruchom testy zanim zacommitujesz.
- Pre-commit: napraw ręcznie Edit-em, NIE `ruff check --fix`.

---

## Mapa plików

**Tworzone:**
- `src/dspace_api/__init__.py`
- `src/dspace_api/apps.py` — AppConfig
- `src/dspace_api/conf/__init__.py`, `src/dspace_api/conf/settings.py`
- `src/dspace_api/selectors.py` — `uczelnie_rekordu(rec)`
- `src/dspace_api/adapters/__init__.py` — `adapter_for(rec)`
- `src/dspace_api/adapters/base.py` — wspólne DC
- `src/dspace_api/adapters/wydawnictwo_ciagle.py`
- `src/dspace_api/adapters/wydawnictwo_zwarte.py`
- `src/dspace_api/adapters/patent.py`
- `src/dspace_api/adapters/prace.py` — doktorska + habilitacyjna
- `src/dspace_api/models/__init__.py`
- `src/dspace_api/models/mapowanie.py` — `Mapowanie_DSpace`
- `src/dspace_api/models/sentdata.py` — `SentToDSpace` + manager
- `src/dspace_api/client.py` — `DSpaceClient`
- `src/dspace_api/eksport.py` — `eksportuj_rekord(rec, request=None)` fan-out
- `src/dspace_api/admin.py`
- `src/dspace_api/actions.py` — akcje admina
- `src/dspace_api/tasks.py` — celery batch
- `src/dspace_api/management/commands/dspace_wyslij.py`
- `src/dspace_api/migrations/__init__.py` (+ generowane)
- `src/dspace_api/tests/__init__.py` (+ pliki testów)
- `src/bpp/fields.py` — `EncryptedTextField` (WSPÓŁDZIELONY)

**Modyfikowane:**
- `pyproject.toml` — zależności
- `src/django_bpp/settings/base.py:402` — `INSTALLED_APPS` += `"dspace_api"`; sekcja settings DSpace
- `src/bpp/models/uczelnia.py:~369` — pola `dspace_*`
- `src/bpp/admin/uczelnia.py:72` — fieldset „DSpace"
- `src/django_bpp/menu.py:64` — wpis w `SYSTEM_MENU`
- `src/bpp/admin/wydawnictwo_ciagle.py:303` — `actions` += akcje DSpace
- `src/bpp/admin/wydawnictwo_zwarte.py` — `actions` += akcje DSpace

---

## FAZA 0 — Zależności i szkielet appki

### Task 1: Dodaj zależności i zarejestruj app

**Files:**
- Modify: `pyproject.toml`
- Create: `src/dspace_api/__init__.py`, `src/dspace_api/apps.py`
- Modify: `src/django_bpp/settings/base.py:402`

- [ ] **Step 1: Dodaj zależności**

W `pyproject.toml`, w sekcji `[project] dependencies` dodaj:
```toml
    "dspace-rest-client>=0.1.12",
    "cryptography",
```

- [ ] **Step 2: Zainstaluj**

Run: `uv sync`
Expected: instaluje `dspace-rest-client` i `cryptography` bez błędów.

- [ ] **Step 3: Utwórz szkielet app**

`src/dspace_api/__init__.py`:
```python
default_app_config = "dspace_api.apps.DspaceApiConfig"
```

`src/dspace_api/apps.py`:
```python
from django.apps import AppConfig


class DspaceApiConfig(AppConfig):
    name = "dspace_api"
    verbose_name = "DSpace API"
    default_auto_field = "django.db.models.BigAutoField"
```

Utwórz puste: `src/dspace_api/models/__init__.py`,
`src/dspace_api/migrations/__init__.py`, `src/dspace_api/tests/__init__.py`,
`src/dspace_api/conf/__init__.py`, `src/dspace_api/adapters/__init__.py`,
`src/dspace_api/management/__init__.py`,
`src/dspace_api/management/commands/__init__.py`.

- [ ] **Step 4: Zarejestruj w INSTALLED_APPS**

W `src/django_bpp/settings/base.py` tuż po linii `"pbn_api",` (~402) dodaj:
```python
    "dspace_api",
```

- [ ] **Step 5: Sprawdź że Django się ładuje**

Run: `uv run python src/manage.py check`
Expected: `System check identified no issues`.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src/dspace_api src/django_bpp/settings/base.py
git commit -m "feat(dspace): szkielet aplikacji dspace_api + zależności"
```

---

## FAZA 1 — EncryptedTextField (współdzielony)

### Task 2: Ustawienie klucza Fernet

**Files:**
- Modify: `src/django_bpp/settings/base.py`

- [ ] **Step 1: Dodaj odczyt klucza z env**

W `src/django_bpp/settings/base.py` (sekcja z innymi `env(...)`, np. blisko innych sekretów) dodaj:
```python
# Klucz Fernet do szyfrowania sekretów integracji (DSpace itd.).
# Wygeneruj: python -c "from cryptography.fernet import Fernet;
#   print(Fernet.generate_key().decode())"
DSPACE_CREDENTIALS_KEY = env("DSPACE_CREDENTIALS_KEY", default="")
```

- [ ] **Step 2: Sprawdź**

Run: `uv run python src/manage.py check`
Expected: bez błędów.

- [ ] **Step 3: Commit**

```bash
git add src/django_bpp/settings/base.py
git commit -m "feat(dspace): ustawienie DSPACE_CREDENTIALS_KEY (Fernet)"
```

### Task 3: EncryptedTextField

**Files:**
- Create: `src/bpp/fields.py`
- Test: `src/bpp/tests/test_encrypted_field.py`

- [ ] **Step 1: Napisz test (failing)**

`src/bpp/tests/test_encrypted_field.py`:
```python
import pytest
from cryptography.fernet import Fernet
from django.db import connection

from bpp.fields import EncryptedTextField


@pytest.fixture
def fernet_key(settings):
    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()
    return settings.DSPACE_CREDENTIALS_KEY


def test_roundtrip_in_python(fernet_key):
    f = EncryptedTextField()
    stored = f.get_prep_value("tajne-haslo")
    assert stored != "tajne-haslo"  # zaszyfrowane
    back = f.from_db_value(stored, None, connection)
    assert back == "tajne-haslo"


def test_empty_passes_through(fernet_key):
    f = EncryptedTextField()
    assert f.get_prep_value("") == ""
    assert f.get_prep_value(None) is None


def test_each_encryption_differs(fernet_key):
    f = EncryptedTextField()
    assert f.get_prep_value("x") != f.get_prep_value("x")  # losowy IV
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/bpp/tests/test_encrypted_field.py -v`
Expected: FAIL — `ModuleNotFoundError: bpp.fields` / `ImportError`.

- [ ] **Step 3: Implementacja**

`src/bpp/fields.py`:
```python
from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models


def _fernet() -> Fernet:
    key = getattr(settings, "DSPACE_CREDENTIALS_KEY", "")
    if not key:
        raise ImproperlyConfigured(
            "DSPACE_CREDENTIALS_KEY nie jest ustawiony — nie mogę "
            "szyfrować/odszyfrować pól EncryptedTextField."
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


class EncryptedTextField(models.TextField):
    """TextField szyfrujący wartość (Fernet) w drodze do bazy.

    W DB leży base64 szyfrogramu, w Pythonie zwraca plaintext.
    Pola NIE da się filtrować/sortować po wartości (każdy szyfrogram inny).
    """

    def get_prep_value(self, value):
        if value is None or value == "":
            return value
        return _fernet().encrypt(str(value).encode()).decode()

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        return _fernet().decrypt(value.encode()).decode()
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/bpp/tests/test_encrypted_field.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/fields.py src/bpp/tests/test_encrypted_field.py
git commit -m "feat(bpp): EncryptedTextField (Fernet) — współdzielone pole sekretów"
```

---

## FAZA 2 — Konfiguracja DSpace na Uczelni

### Task 4: Pola dspace_* na Uczelnia

**Files:**
- Modify: `src/bpp/models/uczelnia.py` (po `pbn_app_token`, ~linia 369)
- Create: `src/bpp/migrations/0421_uczelnia_dspace.py` (przez makemigrations)
- Test: `src/bpp/tests/test_uczelnia_dspace.py`

- [ ] **Step 1: Napisz test (failing)**

`src/bpp/tests/test_uczelnia_dspace.py`:
```python
import pytest
from cryptography.fernet import Fernet
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_uczelnia_dspace_password_encrypted(fernet_key):
    from bpp.models import Uczelnia

    u = baker.make(Uczelnia)
    u.dspace_api_password = "sekret"
    u.save()

    # w surowej kolumnie NIE ma plaintextu
    from django.db import connection

    with connection.cursor() as c:
        c.execute(
            "SELECT dspace_api_password FROM bpp_uczelnia WHERE id=%s", [u.id]
        )
        raw = c.fetchone()[0]
    assert raw != "sekret"

    # ORM odszyfrowuje
    assert Uczelnia.objects.get(pk=u.pk).dspace_api_password == "sekret"


@pytest.mark.django_db
def test_uczelnia_dspace_defaults(fernet_key):
    from bpp.models import Uczelnia

    u = baker.make(Uczelnia)
    assert u.dspace_aktywny is False
    assert u.dspace_api_endpoint == ""
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/bpp/tests/test_uczelnia_dspace.py -v`
Expected: FAIL — `AttributeError: ... dspace_api_password`.

- [ ] **Step 3: Dodaj pola do modelu**

W `src/bpp/models/uczelnia.py` po polu `pbn_app_token` (~369) dodaj. Na górze pliku dodaj import:
```python
from bpp.fields import EncryptedTextField
```
Pola:
```python
    dspace_aktywny = models.BooleanField(
        "Włącz eksport do DSpace",
        default=False,
        help_text="Gdy włączone, rekordy afiliowane do tej uczelni można "
        "wysyłać do jej instalacji DSpace.",
    )
    dspace_api_endpoint = models.URLField(
        "Adres API DSpace",
        blank=True,
        default="",
        help_text="np. https://repozytorium.uczelnia.pl/server/api",
    )
    dspace_api_username = models.CharField(
        "Użytkownik API DSpace", max_length=255, blank=True, default=""
    )
    dspace_api_password = EncryptedTextField(
        "Hasło API DSpace", blank=True, default=""
    )
    dspace_domyslny_jezyk_dc = models.CharField(
        "Domyślny język dc.language.iso",
        max_length=8,
        blank=True,
        default="pl",
    )
```

- [ ] **Step 4: Wygeneruj migrację**

Run: `uv run python src/manage.py makemigrations bpp`
Expected: tworzy `src/bpp/migrations/0421_*.py` z 5 polami. (Numer może się różnić jeśli baza ma nowsze — użyj faktycznego.)

- [ ] **Step 5: Uruchom — ma PASS**

Run: `uv run pytest src/bpp/tests/test_uczelnia_dspace.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bpp/models/uczelnia.py src/bpp/migrations/0421_*.py \
        src/bpp/tests/test_uczelnia_dspace.py
git commit -m "feat(dspace): pola konfiguracji DSpace na Uczelni (hasło szyfrowane)"
```

### Task 5: Fieldset DSpace w adminie Uczelni

**Files:**
- Modify: `src/bpp/admin/uczelnia.py:72` (krotka `fieldsets`)

- [ ] **Step 1: Dodaj fieldset**

W `src/bpp/admin/uczelnia.py`, w krotce `fieldsets` (po sekcji „ORCID", ~210) dodaj:
```python
        (
            "DSpace",
            {
                "classes": ("grp-collapse", "grp-closed"),
                "fields": (
                    "dspace_aktywny",
                    "dspace_api_endpoint",
                    "dspace_api_username",
                    "dspace_api_password",
                    "dspace_domyslny_jezyk_dc",
                ),
            },
        ),
```

- [ ] **Step 2: Sprawdź ładowanie admina**

Run: `uv run python src/manage.py check`
Expected: bez błędów.

- [ ] **Step 3: Commit**

```bash
git add src/bpp/admin/uczelnia.py
git commit -m "feat(dspace): fieldset DSpace w adminie Uczelni"
```

---

## FAZA 3 — Model mapowania kolekcji

### Task 6: Model Mapowanie_DSpace

**Files:**
- Create: `src/dspace_api/models/mapowanie.py`
- Modify: `src/dspace_api/models/__init__.py`
- Create: migracja `dspace_api/migrations/0001_*`
- Test: `src/dspace_api/tests/test_mapowanie.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_mapowanie.py`:
```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_mapowanie_unikalne_per_uczelnia_charakter():
    from django.db import IntegrityError

    from dspace_api.models import Mapowanie_DSpace

    uczelnia = baker.make("bpp.Uczelnia")
    charakter = baker.make("bpp.Charakter_Formalny")
    baker.make(
        Mapowanie_DSpace,
        uczelnia=uczelnia,
        charakter_formalny=charakter,
        collection_uuid="11111111-1111-1111-1111-111111111111",
    )
    with pytest.raises(IntegrityError):
        Mapowanie_DSpace.objects.create(
            uczelnia=uczelnia,
            charakter_formalny=charakter,
            collection_uuid="22222222-2222-2222-2222-222222222222",
        )
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_mapowanie.py -v`
Expected: FAIL — `ImportError: cannot import name 'Mapowanie_DSpace'`.

- [ ] **Step 3: Implementacja modelu**

`src/dspace_api/models/mapowanie.py`:
```python
from django.db import models


class Mapowanie_DSpace(models.Model):
    """Mapuje (Uczelnia, Charakter_Formalny) na kolekcję DSpace."""

    uczelnia = models.ForeignKey(
        "bpp.Uczelnia", on_delete=models.CASCADE, verbose_name="Uczelnia"
    )
    charakter_formalny = models.ForeignKey(
        "bpp.Charakter_Formalny",
        on_delete=models.CASCADE,
        verbose_name="Charakter formalny",
    )
    collection_uuid = models.UUIDField("UUID kolekcji DSpace")
    opis = models.CharField("Opis", max_length=255, blank=True, default="")

    class Meta:
        verbose_name = "Mapowanie DSpace"
        verbose_name_plural = "Mapowania DSpace"
        unique_together = (("uczelnia", "charakter_formalny"),)

    def __str__(self):
        return f"{self.uczelnia} / {self.charakter_formalny} → {self.collection_uuid}"
```

`src/dspace_api/models/__init__.py`:
```python
from dspace_api.models.mapowanie import Mapowanie_DSpace

__all__ = ["Mapowanie_DSpace"]
```

- [ ] **Step 4: Migracja**

Run: `uv run python src/manage.py makemigrations dspace_api`
Expected: `0001_initial.py` z modelem `Mapowanie_DSpace`.

- [ ] **Step 5: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_mapowanie.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dspace_api/models src/dspace_api/migrations/0001_*.py \
        src/dspace_api/tests/test_mapowanie.py
git commit -m "feat(dspace): model Mapowanie_DSpace (charakter→kolekcja per uczelnia)"
```

### Task 7: Admin mapowania + wpis w „Dane systemowe"

**Files:**
- Create: `src/dspace_api/admin.py`
- Modify: `src/django_bpp/menu.py:64` (`SYSTEM_MENU`)

- [ ] **Step 1: Admin**

`src/dspace_api/admin.py`:
```python
from django.contrib import admin

from dspace_api.models import Mapowanie_DSpace


@admin.register(Mapowanie_DSpace)
class Mapowanie_DSpaceAdmin(admin.ModelAdmin):
    list_display = ["uczelnia", "charakter_formalny", "collection_uuid", "opis"]
    list_filter = ["uczelnia"]
    autocomplete_fields = ["charakter_formalny"]
    search_fields = ["opis"]
```

- [ ] **Step 2: Wpis w menu „Dane systemowe"**

W `src/django_bpp/menu.py`, w liście `SYSTEM_MENU` (po „Charakter PBN", ~46) dodaj krotkę:
```python
    ("Mapowania DSpace", "/admin/dspace_api/mapowanie_dspace/"),
```

- [ ] **Step 3: Sprawdź**

Run: `uv run python src/manage.py check`
Expected: bez błędów.

Uwaga: `autocomplete_fields=["charakter_formalny"]` wymaga, by
`Charakter_FormalnyAdmin` miał `search_fields` (ma — `["skrot","nazwa"]`).

- [ ] **Step 4: Commit**

```bash
git add src/dspace_api/admin.py src/django_bpp/menu.py
git commit -m "feat(dspace): admin Mapowanie_DSpace w sekcji Dane systemowe"
```

---

## FAZA 4 — Śledzenie wysyłki (SentToDSpace)

### Task 8: Model SentToDSpace + manager

**Files:**
- Create: `src/dspace_api/models/sentdata.py`
- Modify: `src/dspace_api/models/__init__.py`
- Create: migracja `0002_*`
- Test: `src/dspace_api/tests/test_sentdata.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_sentdata.py`:
```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_check_if_upload_needed_lifecycle():
    from dspace_api.models import SentToDSpace

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    uczelnia = baker.make("bpp.Uczelnia")
    data = {"dc.title": [{"value": "T"}]}

    # nic nie wysłano → potrzeba
    assert SentToDSpace.objects.check_if_upload_needed(rec, uczelnia, data)

    SentToDSpace.objects.create_or_update_before_upload(rec, uczelnia, data)
    SentToDSpace.objects.mark_as_successful(
        rec, uczelnia, dspace_uuid="33333333-3333-3333-3333-333333333333"
    )

    # te same dane + sukces → NIE trzeba
    assert not SentToDSpace.objects.check_if_upload_needed(rec, uczelnia, data)

    # zmienione dane → trzeba znów
    assert SentToDSpace.objects.check_if_upload_needed(
        rec, uczelnia, {"dc.title": [{"value": "INNE"}]}
    )


@pytest.mark.django_db
def test_per_uczelnia_isolation():
    from dspace_api.models import SentToDSpace

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    data = {"x": 1}

    SentToDSpace.objects.create_or_update_before_upload(rec, u1, data)
    SentToDSpace.objects.mark_as_successful(rec, u1, dspace_uuid=None)

    # u1 wysłane, u2 nie
    assert not SentToDSpace.objects.check_if_upload_needed(rec, u1, data)
    assert SentToDSpace.objects.check_if_upload_needed(rec, u2, data)
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_sentdata.py -v`
Expected: FAIL — `ImportError: SentToDSpace`.

- [ ] **Step 3: Implementacja (wzorzec pbn_api.SentData)**

`src/dspace_api/models/sentdata.py`:
```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import JSONField
from django.utils import timezone


class SentToDSpaceManager(models.Manager):
    def get_for_rec(self, rec, uczelnia):
        return self.get(
            object_id=rec.pk,
            content_type=ContentType.objects.get_for_model(rec),
            uczelnia=uczelnia,
        )

    def check_if_upload_needed(self, rec, uczelnia, data: dict):
        try:
            sd = self.get_for_rec(rec, uczelnia)
            if sd.data_sent == data and sd.submitted_successfully:
                return False
        except SentToDSpace.DoesNotExist:
            pass
        return True

    def create_or_update_before_upload(self, rec, uczelnia, data: dict):
        try:
            sd = self.get_for_rec(rec, uczelnia)
            sd.submitted_successfully = False
            sd.submitted_at = timezone.now()
            sd.api_response_status = ""
            sd.exception = ""
            sd.data_sent = data
            sd.save()
            return sd
        except SentToDSpace.DoesNotExist:
            return self.create(
                object=rec,
                uczelnia=uczelnia,
                data_sent=data,
                submitted_successfully=False,
                submitted_at=timezone.now(),
            )

    def mark_as_successful(
        self, rec, uczelnia, dspace_uuid=None, api_response_status=""
    ):
        sd = self.get_for_rec(rec, uczelnia)
        sd.submitted_successfully = True
        sd.dspace_uuid = dspace_uuid
        sd.api_response_status = api_response_status
        sd.exception = ""
        sd.save()

    def mark_as_failed(self, rec, uczelnia, exception="", api_response_status=""):
        sd = self.get_for_rec(rec, uczelnia)
        sd.submitted_successfully = False
        sd.exception = str(exception) if exception else ""
        sd.api_response_status = api_response_status
        sd.save()


class SentToDSpace(models.Model):
    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField(db_index=True)
    object = GenericForeignKey()

    uczelnia = models.ForeignKey("bpp.Uczelnia", on_delete=models.CASCADE)

    dspace_uuid = models.UUIDField(
        "UUID itemu w DSpace", null=True, blank=True
    )
    data_sent = JSONField("Wysłane dane")
    submitted_successfully = models.BooleanField(
        "Wysłano pomyślnie", default=False, db_index=True
    )
    submitted_at = models.DateTimeField("Data wysyłki", null=True, blank=True)
    exception = models.TextField("Kod błędu", blank=True, default="")
    api_response_status = models.TextField(
        "Status odpowiedzi API", blank=True, default=""
    )
    last_updated_on = models.DateTimeField("Data operacji", auto_now=True)

    objects = SentToDSpaceManager()

    class Meta:
        verbose_name = "Informacja o wysłaniu do DSpace"
        verbose_name_plural = "Informacje o wysłaniu do DSpace"
        unique_together = (("content_type", "object_id", "uczelnia"),)

    def __str__(self):
        status = "OK" if self.submitted_successfully else "ERR"
        return (
            f"DSpace[{self.uczelnia_id}] rekord "
            f"({self.content_type_id},{self.object_id}) — {status}"
        )
```

Dopisz do `src/dspace_api/models/__init__.py`:
```python
from dspace_api.models.mapowanie import Mapowanie_DSpace
from dspace_api.models.sentdata import SentToDSpace

__all__ = ["Mapowanie_DSpace", "SentToDSpace"]
```

- [ ] **Step 4: Migracja**

Run: `uv run python src/manage.py makemigrations dspace_api`
Expected: `0002_*.py` z `SentToDSpace`.

- [ ] **Step 5: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_sentdata.py -v`
Expected: 2 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/dspace_api/models src/dspace_api/migrations/0002_*.py \
        src/dspace_api/tests/test_sentdata.py
git commit -m "feat(dspace): model SentToDSpace + manager (stan wysyłki per uczelnia)"
```

---

## FAZA 5 — Selektor uczelni rekordu

### Task 9: uczelnie_rekordu(rec)

**Files:**
- Create: `src/dspace_api/selectors.py`
- Test: `src/dspace_api/tests/test_selectors.py`

Uwaga o kształtach danych:
- Ciągłe/Zwarte/Patent: autorzy przez `rec.autorzy_set` → `.jednostka.uczelnia`.
- Doktorska/Habilitacyjna: brak through-modelu; rekord ma własny `jednostka` FK → `rec.jednostka.uczelnia`.

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_selectors.py`:
```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_uczelnie_z_autorzy_set():
    from dspace_api.selectors import uczelnie_rekordu

    u1 = baker.make("bpp.Uczelnia")
    u2 = baker.make("bpp.Uczelnia")
    j1 = baker.make("bpp.Jednostka", uczelnia=u1)
    j2 = baker.make("bpp.Jednostka", uczelnia=u2)

    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j1)
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j2)

    assert uczelnie_rekordu(rec) == {u1, u2}


@pytest.mark.django_db
def test_uczelnie_z_jednostki_rekordu_doktorat():
    from dspace_api.selectors import uczelnie_rekordu

    u = baker.make("bpp.Uczelnia")
    j = baker.make("bpp.Jednostka", uczelnia=u)
    rec = baker.make("bpp.Praca_Doktorska", jednostka=j)

    assert uczelnie_rekordu(rec) == {u}
```

Uwaga: w `Wydawnictwo_Ciagle_Autor` pole FK do rekordu nazywa się `rekord`
(related_name `autorzy_set`). Zweryfikuj nazwę argumentu w `baker.make`
(może być `rekord` — sprawdź definicję through-modelu jeśli baker zgłosi błąd).

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_selectors.py -v`
Expected: FAIL — `ModuleNotFoundError: dspace_api.selectors`.

- [ ] **Step 3: Implementacja**

`src/dspace_api/selectors.py`:
```python
def uczelnie_rekordu(rec):
    """Zwróć zbiór Uczelni, do których rekord jest afiliowany.

    Dwa kształty:
    - rekordy z autorami przez through-model (`autorzy_set`): bierzemy
      uczelnię z jednostki każdego powiązania autora,
    - rekordy z własnym FK `jednostka` (doktoraty, habilitacje).
    """
    uczelnie = set()

    autorzy_set = getattr(rec, "autorzy_set", None)
    if autorzy_set is not None and hasattr(autorzy_set, "all"):
        qs = autorzy_set.select_related("jednostka__uczelnia").all()
        for powiazanie in qs:
            jednostka = getattr(powiazanie, "jednostka", None)
            if jednostka and jednostka.uczelnia_id:
                uczelnie.add(jednostka.uczelnia)
        if uczelnie:
            return uczelnie

    jednostka = getattr(rec, "jednostka", None)
    if jednostka and getattr(jednostka, "uczelnia_id", None):
        uczelnie.add(jednostka.uczelnia)

    return uczelnie
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_selectors.py -v`
Expected: 2 PASS. (Jeśli FAIL na `autorzy_set` property doktoratu —
patrz uwaga: doktorat ma property `autorzy_set` zwracającą sztuczny set;
wtedy `hasattr(autorzy_set, "all")` jest False i wpadamy w gałąź `jednostka` —
co jest poprawne. Zweryfikuj na realnym modelu.)

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/selectors.py src/dspace_api/tests/test_selectors.py
git commit -m "feat(dspace): selektor uczelnie_rekordu (afiliacje autorów)"
```

---

## FAZA 6 — Adaptery (rekord → Dublin Core dict)

Format pola DC (zgodnie z `dspace-rest-client`): słownik `"dc.xxx" ->
[ {"value": ..., "language": ..., "authority": None, "confidence": -1} ]`.

### Task 10: Adapter bazowy + Wydawnictwo_Ciagle

**Files:**
- Create: `src/dspace_api/adapters/base.py`
- Create: `src/dspace_api/adapters/wydawnictwo_ciagle.py`
- Test: `src/dspace_api/tests/test_adapter_ciagle.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_adapter_ciagle.py`:
```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_adapter_ciagle_metadata():
    from dspace_api.adapters.wydawnictwo_ciagle import WydawnictwoCiagleDSpaceAdapter

    jezyk = baker.make("bpp.Jezyk", skrot="pl")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="Tytuł pracy",
        rok=2024,
        streszczenie="Streszczenie pracy",
        jezyk=jezyk,
    )
    d = WydawnictwoCiagleDSpaceAdapter(rec).to_dspace_dict()

    assert d["dc.title"][0]["value"] == "Tytuł pracy"
    assert d["dc.date.issued"][0]["value"] == "2024"
    assert d["dc.description.abstract"][0]["value"] == "Streszczenie pracy"
    assert d["dc.language.iso"][0]["value"] == "pl"
    assert d["dc.type"][0]["value"] == "article"


@pytest.mark.django_db
def test_adapter_ciagle_authors():
    from dspace_api.adapters.wydawnictwo_ciagle import WydawnictwoCiagleDSpaceAdapter

    rec = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="X", rok=2024)
    autor = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, autor=autor)

    d = WydawnictwoCiagleDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.contributor.author"][0]["value"] == "Kowalski, Jan"
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_adapter_ciagle.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implementacja bazy**

`src/dspace_api/adapters/base.py`:
```python
class BaseDSpaceAdapter:
    """Bazowy adapter: rekord BPP → słownik metadanych Dublin Core."""

    dc_type = None  # nadpisywane w podklasach

    def __init__(self, rec, domyslny_jezyk="pl"):
        self.rec = rec
        self.domyslny_jezyk = domyslny_jezyk

    # --- helpery budujące pola DC ---
    def _val(self, value, language=None):
        return [
            {
                "value": value,
                "language": language,
                "authority": None,
                "confidence": -1,
            }
        ]

    def _multi(self, values, language=None):
        return [
            {
                "value": v,
                "language": language,
                "authority": None,
                "confidence": -1,
            }
            for v in values
        ]

    def _jezyk_iso(self):
        jezyk = getattr(self.rec, "jezyk", None)
        if jezyk and getattr(jezyk, "skrot", ""):
            return jezyk.skrot
        return self.domyslny_jezyk

    def _autorzy_wg_typu(self, skrot_typu):
        """Nazwiska autorów o danym typie odpowiedzialności (np. 'aut.')."""
        wynik = []
        qs = self.rec.autorzy_set.select_related(
            "autor", "typ_odpowiedzialnosci"
        ).order_by("kolejnosc")
        for p in qs:
            typ = getattr(p.typ_odpowiedzialnosci, "skrot", "")
            if skrot_typu is None or typ == skrot_typu:
                wynik.append(f"{p.autor.nazwisko}, {p.autor.imiona}")
        return wynik

    # --- wspólne metadane ---
    def common_dict(self):
        rec = self.rec
        d = {}
        if getattr(rec, "tytul_oryginalny", ""):
            d["dc.title"] = self._val(rec.tytul_oryginalny)
        if getattr(rec, "rok", None):
            d["dc.date.issued"] = self._val(str(rec.rok))
        if getattr(rec, "streszczenie", ""):
            d["dc.description.abstract"] = self._val(rec.streszczenie)
        if getattr(rec, "doi", ""):
            d["dc.identifier.doi"] = self._val(rec.doi)
        d["dc.language.iso"] = self._val(self._jezyk_iso())
        if self.dc_type:
            d["dc.type"] = self._val(self.dc_type)
        slowa = []
        if getattr(rec, "slowa_kluczowe", None) is not None:
            slowa += [t.name for t in rec.slowa_kluczowe.all()]
        eng = getattr(rec, "slowa_kluczowe_eng", None) or []
        slowa += list(eng)
        if slowa:
            d["dc.subject"] = self._multi(slowa)
        return d

    def to_dspace_dict(self):
        raise NotImplementedError
```

`src/dspace_api/adapters/wydawnictwo_ciagle.py`:
```python
from dspace_api.adapters.base import BaseDSpaceAdapter


class WydawnictwoCiagleDSpaceAdapter(BaseDSpaceAdapter):
    dc_type = "article"

    def to_dspace_dict(self):
        d = self.common_dict()
        rec = self.rec
        autorzy = self._autorzy_wg_typu(None)
        if autorzy:
            d["dc.contributor.author"] = self._multi(autorzy)
        if getattr(rec, "issn", ""):
            d["dc.identifier.issn"] = self._val(rec.issn)
        if getattr(rec, "zrodlo_id", None):
            d["dc.relation.ispartof"] = self._val(str(rec.zrodlo))
        return d
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_adapter_ciagle.py -v`
Expected: 2 PASS. (Jeśli test autora łapie też typ odpowiedzialności —
domyślnie `_autorzy_wg_typu(None)` bierze wszystkich, więc OK.)

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/adapters/base.py \
        src/dspace_api/adapters/wydawnictwo_ciagle.py \
        src/dspace_api/tests/test_adapter_ciagle.py
git commit -m "feat(dspace): adapter bazowy + Wydawnictwo_Ciagle → Dublin Core"
```

### Task 11: Adapter Wydawnictwo_Zwarte

**Files:**
- Create: `src/dspace_api/adapters/wydawnictwo_zwarte.py`
- Test: `src/dspace_api/tests/test_adapter_zwarte.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_adapter_zwarte.py`:
```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_adapter_zwarte_book():
    from dspace_api.adapters.wydawnictwo_zwarte import WydawnictwoZwarteDSpaceAdapter

    rec = baker.make(
        "bpp.Wydawnictwo_Zwarte",
        tytul_oryginalny="Książka",
        rok=2023,
        isbn="978-83-000-0000-0",
    )
    d = WydawnictwoZwarteDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.title"][0]["value"] == "Książka"
    assert d["dc.identifier.isbn"][0]["value"] == "978-83-000-0000-0"
    assert d["dc.type"][0]["value"] == "book"
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_adapter_zwarte.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementacja**

`src/dspace_api/adapters/wydawnictwo_zwarte.py`:
```python
from dspace_api.adapters.base import BaseDSpaceAdapter


class WydawnictwoZwarteDSpaceAdapter(BaseDSpaceAdapter):
    dc_type = "book"

    def to_dspace_dict(self):
        d = self.common_dict()
        rec = self.rec
        autorzy = self._autorzy_wg_typu(None)
        if autorzy:
            d["dc.contributor.author"] = self._multi(autorzy)
        if getattr(rec, "isbn", ""):
            d["dc.identifier.isbn"] = self._val(rec.isbn)
        if getattr(rec, "wydawca_id", None):
            d["dc.publisher"] = self._val(str(rec.wydawca))
        elif getattr(rec, "wydawca_opis", ""):
            d["dc.publisher"] = self._val(rec.wydawca_opis)
        return d
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_adapter_zwarte.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/adapters/wydawnictwo_zwarte.py \
        src/dspace_api/tests/test_adapter_zwarte.py
git commit -m "feat(dspace): adapter Wydawnictwo_Zwarte → Dublin Core"
```

### Task 12: Adapter Patent

**Files:**
- Create: `src/dspace_api/adapters/patent.py`
- Test: `src/dspace_api/tests/test_adapter_patent.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_adapter_patent.py`:
```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_adapter_patent():
    from dspace_api.adapters.patent import PatentDSpaceAdapter

    rec = baker.make(
        "bpp.Patent",
        tytul_oryginalny="Wynalazek",
        rok=2022,
        numer_prawa_wylacznego="PL12345",
    )
    d = PatentDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.title"][0]["value"] == "Wynalazek"
    assert d["dc.type"][0]["value"] == "patent"
    assert d["dc.identifier"][0]["value"] == "PL12345"
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_adapter_patent.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementacja**

`src/dspace_api/adapters/patent.py`:
```python
from dspace_api.adapters.base import BaseDSpaceAdapter


class PatentDSpaceAdapter(BaseDSpaceAdapter):
    dc_type = "patent"

    def to_dspace_dict(self):
        d = self.common_dict()
        rec = self.rec
        autorzy = self._autorzy_wg_typu(None)
        if autorzy:
            d["dc.contributor.author"] = self._multi(autorzy)
        numer = (
            getattr(rec, "numer_prawa_wylacznego", "")
            or getattr(rec, "numer_zgloszenia", "")
        )
        if numer:
            d["dc.identifier"] = self._val(numer)
        return d
```

Uwaga: Patent nie ma `jezyk` FK ani `streszczenie` — `common_dict()` to
obsłuży (getattr z fallbackiem na `domyslny_jezyk`).

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_adapter_patent.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/adapters/patent.py \
        src/dspace_api/tests/test_adapter_patent.py
git commit -m "feat(dspace): adapter Patent → Dublin Core"
```

### Task 13: Adaptery Praca_Doktorska + Praca_Habilitacyjna

**Files:**
- Create: `src/dspace_api/adapters/prace.py`
- Test: `src/dspace_api/tests/test_adapter_prace.py`

Uwaga: te modele mają pojedynczy `autor` FK (nie through-model). Adapter
nie używa `_autorzy_wg_typu` (brak `autorzy_set` querysetu).

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_adapter_prace.py`:
```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_adapter_doktorska():
    from dspace_api.adapters.prace import PracaDoktorskaDSpaceAdapter

    autor = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    rec = baker.make(
        "bpp.Praca_Doktorska", tytul_oryginalny="Rozprawa", rok=2021, autor=autor
    )
    d = PracaDoktorskaDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.title"][0]["value"] == "Rozprawa"
    assert d["dc.type"][0]["value"] == "doctoralThesis"
    assert d["dc.contributor.author"][0]["value"] == "Nowak, Anna"


@pytest.mark.django_db
def test_adapter_habilitacyjna():
    from dspace_api.adapters.prace import PracaHabilitacyjnaDSpaceAdapter

    autor = baker.make("bpp.Autor", nazwisko="Lis", imiona="Ewa")
    rec = baker.make(
        "bpp.Praca_Habilitacyjna",
        tytul_oryginalny="Habilitacja",
        rok=2020,
        autor=autor,
    )
    d = PracaHabilitacyjnaDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.type"][0]["value"] == "Thesis"
    assert d["dc.contributor.author"][0]["value"] == "Lis, Ewa"
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_adapter_prace.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementacja**

`src/dspace_api/adapters/prace.py`:
```python
from dspace_api.adapters.base import BaseDSpaceAdapter


class _PracaJednoautorskaAdapter(BaseDSpaceAdapter):
    def to_dspace_dict(self):
        d = self.common_dict()
        autor = getattr(self.rec, "autor", None)
        if autor:
            d["dc.contributor.author"] = self._val(
                f"{autor.nazwisko}, {autor.imiona}"
            )
        promotor = getattr(self.rec, "promotor", None)
        if promotor:
            d["dc.contributor.advisor"] = self._val(
                f"{promotor.nazwisko}, {promotor.imiona}"
            )
        return d


class PracaDoktorskaDSpaceAdapter(_PracaJednoautorskaAdapter):
    dc_type = "doctoralThesis"


class PracaHabilitacyjnaDSpaceAdapter(_PracaJednoautorskaAdapter):
    dc_type = "Thesis"
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_adapter_prace.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/adapters/prace.py \
        src/dspace_api/tests/test_adapter_prace.py
git commit -m "feat(dspace): adaptery Praca_Doktorska + Habilitacyjna"
```

### Task 14: Rejestr adapterów (adapter_for)

**Files:**
- Modify: `src/dspace_api/adapters/__init__.py`
- Test: `src/dspace_api/tests/test_adapter_registry.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_adapter_registry.py`:
```python
import pytest
from model_bakery import baker


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,expected_type",
    [
        ("bpp.Wydawnictwo_Ciagle", "article"),
        ("bpp.Wydawnictwo_Zwarte", "book"),
        ("bpp.Patent", "patent"),
        ("bpp.Praca_Doktorska", "doctoralThesis"),
        ("bpp.Praca_Habilitacyjna", "Thesis"),
    ],
)
def test_adapter_for(model, expected_type):
    from dspace_api.adapters import adapter_for

    rec = baker.make(model, tytul_oryginalny="X", rok=2024)
    adapter = adapter_for(rec)
    assert adapter.dc_type == expected_type


@pytest.mark.django_db
def test_adapter_for_nieobslugiwany():
    from dspace_api.adapters import adapter_for

    rec = baker.make("bpp.Autor")
    with pytest.raises(ValueError):
        adapter_for(rec)
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_adapter_registry.py -v`
Expected: FAIL — `ImportError: adapter_for`.

- [ ] **Step 3: Implementacja**

`src/dspace_api/adapters/__init__.py`:
```python
from dspace_api.adapters.patent import PatentDSpaceAdapter
from dspace_api.adapters.prace import (
    PracaDoktorskaDSpaceAdapter,
    PracaHabilitacyjnaDSpaceAdapter,
)
from dspace_api.adapters.wydawnictwo_ciagle import WydawnictwoCiagleDSpaceAdapter
from dspace_api.adapters.wydawnictwo_zwarte import WydawnictwoZwarteDSpaceAdapter

_REJESTR = {
    "Wydawnictwo_Ciagle": WydawnictwoCiagleDSpaceAdapter,
    "Wydawnictwo_Zwarte": WydawnictwoZwarteDSpaceAdapter,
    "Patent": PatentDSpaceAdapter,
    "Praca_Doktorska": PracaDoktorskaDSpaceAdapter,
    "Praca_Habilitacyjna": PracaHabilitacyjnaDSpaceAdapter,
}


def adapter_for(rec, domyslny_jezyk="pl"):
    klasa = _REJESTR.get(type(rec).__name__)
    if klasa is None:
        raise ValueError(
            f"Brak adaptera DSpace dla modelu {type(rec).__name__}"
        )
    return klasa(rec, domyslny_jezyk=domyslny_jezyk)
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_adapter_registry.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/adapters/__init__.py \
        src/dspace_api/tests/test_adapter_registry.py
git commit -m "feat(dspace): rejestr adapterów adapter_for()"
```

---

## FAZA 7 — Klient DSpace (otoczka)

### Task 15: DSpaceClient

**Files:**
- Create: `src/dspace_api/client.py`
- Test: `src/dspace_api/tests/test_client.py`

Otoczka na `dspace_rest_client.DSpaceClient`. Tworzona z obiektu `Uczelnia`
(endpoint/login/hasło). Metody: `authenticate()`, `create_item(collection_uuid,
dc_dict)`, `patch_item(item_uuid, dc_dict)`.

- [ ] **Step 1: Napisz test (failing, mock biblioteki)**

`src/dspace_api/tests/test_client.py`:
```python
from unittest import mock

import pytest
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    from cryptography.fernet import Fernet

    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_client_authenticate_uzywa_pol_uczelni(fernet_key):
    from dspace_api.client import DSpaceClient

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.x/server/api"
    u.dspace_api_username = "api@x"
    u.dspace_api_password = "haslo"
    u.save()

    with mock.patch("dspace_api.client.RawDSpaceClient") as RawCls:
        raw = RawCls.return_value
        raw.authenticate.return_value = True

        client = DSpaceClient(u)
        assert client.authenticate() is True

        RawCls.assert_called_once_with(
            api_endpoint="https://repo.x/server/api",
            username="api@x",
            password="haslo",
        )


@pytest.mark.django_db
def test_client_create_item_zwraca_uuid(fernet_key):
    from dspace_api.client import DSpaceClient

    u = baker.make("bpp.Uczelnia")
    u.dspace_api_endpoint = "https://repo.x/server/api"
    u.save()

    with mock.patch("dspace_api.client.RawDSpaceClient") as RawCls, mock.patch(
        "dspace_api.client.Item"
    ) as ItemCls:
        raw = RawCls.return_value
        created = mock.Mock()
        created.uuid = "44444444-4444-4444-4444-444444444444"
        raw.create_item.return_value = created

        client = DSpaceClient(u)
        uuid = client.create_item(
            "55555555-5555-5555-5555-555555555555",
            {"dc.title": [{"value": "T"}]},
        )
        assert uuid == "44444444-4444-4444-4444-444444444444"
        ItemCls.assert_called_once()
        raw.create_item.assert_called_once()
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: dspace_api.client`.

- [ ] **Step 3: Implementacja**

`src/dspace_api/client.py`:
```python
from dspace_rest_client.client import DSpaceClient as RawDSpaceClient
from dspace_rest_client.models import Item


class DSpaceAuthError(RuntimeError):
    pass


class DSpaceClient:
    """Otoczka na dspace-rest-client skonfigurowana z obiektu Uczelnia."""

    def __init__(self, uczelnia):
        self.uczelnia = uczelnia
        self._raw = RawDSpaceClient(
            api_endpoint=uczelnia.dspace_api_endpoint,
            username=uczelnia.dspace_api_username,
            password=uczelnia.dspace_api_password,
        )

    def authenticate(self):
        ok = self._raw.authenticate()
        if not ok:
            raise DSpaceAuthError(
                f"Logowanie do DSpace {self.uczelnia.dspace_api_endpoint} "
                f"nie powiodło się."
            )
        return ok

    def create_item(self, collection_uuid, dc_dict):
        item = Item({"metadata": dc_dict, "inArchive": True})
        created = self._raw.create_item(parent=str(collection_uuid), item=item)
        return getattr(created, "uuid", None)

    def patch_item(self, item_uuid, dc_dict):
        item = Item(
            {"uuid": str(item_uuid), "metadata": dc_dict, "inArchive": True}
        )
        self._raw.update_item(item)
        return item_uuid
```

Uwaga: dokładna sygnatura `create_item`/`update_item`/konstruktora `Item`
w `dspace-rest-client` 0.1.x może się różnić (sprawdź `example.py` w paczce).
Test mockuje bibliotekę, więc przejdzie; **realna zgodność weryfikowana w
fazie 11 (smoke-test na DSpace 9.x).**

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_client.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/client.py src/dspace_api/tests/test_client.py
git commit -m "feat(dspace): DSpaceClient — otoczka na dspace-rest-client"
```

---

## FAZA 8 — Orkiestracja eksportu (wachlarz)

### Task 16: eksportuj_rekord(rec)

**Files:**
- Create: `src/dspace_api/eksport.py`
- Test: `src/dspace_api/tests/test_eksport.py`

Zwraca listę wyników per uczelnia: `[{"uczelnia", "status", "powod"}]`
gdzie status ∈ {"wyslano", "zaktualizowano", "pominieto", "blad", "bez_zmian"}.

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_eksport.py`:
```python
from unittest import mock

import pytest
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    from cryptography.fernet import Fernet

    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_wachlarz_jedna_skonfigurowana_druga_nie(fernet_key):
    from dspace_api.eksport import eksportuj_rekord
    from dspace_api.models import Mapowanie_DSpace

    u1 = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u1.dspace_api_endpoint = "https://repo1/server/api"
    u1.save()
    u2 = baker.make("bpp.Uczelnia", dspace_aktywny=False)  # nieaktywna

    j1 = baker.make("bpp.Jednostka", uczelnia=u1)
    j2 = baker.make("bpp.Jednostka", uczelnia=u2)
    charakter = baker.make("bpp.Charakter_Formalny")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="T",
        rok=2024,
        charakter_formalny=charakter,
    )
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j1)
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j2)

    Mapowanie_DSpace.objects.create(
        uczelnia=u1,
        charakter_formalny=charakter,
        collection_uuid="66666666-6666-6666-6666-666666666666",
    )

    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.create_item.return_value = "77777777-7777-7777-7777-777777777777"

        wyniki = eksportuj_rekord(rec)

    by_uczelnia = {w["uczelnia"]: w for w in wyniki}
    assert by_uczelnia[u1]["status"] == "wyslano"
    assert by_uczelnia[u2]["status"] == "pominieto"


@pytest.mark.django_db
def test_brak_mapowania_pomija_z_powodem(fernet_key):
    from dspace_api.eksport import eksportuj_rekord

    u = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    j = baker.make("bpp.Jednostka", uczelnia=u)
    rec = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="T", rok=2024)
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j)

    # brak Mapowanie_DSpace dla tej pary
    wyniki = eksportuj_rekord(rec)
    assert wyniki[0]["status"] == "pominieto"
    assert "mapowani" in wyniki[0]["powod"].lower()
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_eksport.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implementacja**

`src/dspace_api/eksport.py`:
```python
import traceback

from dspace_api.adapters import adapter_for
from dspace_api.client import DSpaceClient
from dspace_api.models import Mapowanie_DSpace, SentToDSpace
from dspace_api.selectors import uczelnie_rekordu


def eksportuj_rekord(rec):
    """Wachlarz: wyślij rekord do DSpace każdej afiliowanej, skonfigurowanej
    uczelni. Zwraca listę wyników per uczelnia (do raportu w UI/logu)."""
    wyniki = []
    for uczelnia in uczelnie_rekordu(rec):
        wyniki.append(_eksportuj_do_uczelni(rec, uczelnia))
    return wyniki


def _wynik(uczelnia, status, powod=""):
    return {"uczelnia": uczelnia, "status": status, "powod": powod}


def _eksportuj_do_uczelni(rec, uczelnia):
    if not uczelnia.dspace_aktywny or not uczelnia.dspace_api_endpoint:
        return _wynik(
            uczelnia, "pominieto", "brak/nieaktywna konfiguracja DSpace"
        )

    try:
        mapowanie = Mapowanie_DSpace.objects.get(
            uczelnia=uczelnia, charakter_formalny=rec.charakter_formalny
        )
    except Mapowanie_DSpace.DoesNotExist:
        return _wynik(
            uczelnia,
            "pominieto",
            f"charakter '{rec.charakter_formalny}' bez mapowania DSpace",
        )
    except AttributeError:
        return _wynik(uczelnia, "pominieto", "rekord bez charakteru formalnego")

    dc = adapter_for(
        rec, domyslny_jezyk=uczelnia.dspace_domyslny_jezyk_dc or "pl"
    ).to_dspace_dict()

    if not SentToDSpace.objects.check_if_upload_needed(rec, uczelnia, dc):
        return _wynik(uczelnia, "bez_zmian", "dane bez zmian")

    try:
        sent = SentToDSpace.objects.get_for_rec(rec, uczelnia)
        istnieje_uuid = sent.dspace_uuid
    except SentToDSpace.DoesNotExist:
        istnieje_uuid = None

    SentToDSpace.objects.create_or_update_before_upload(rec, uczelnia, dc)

    try:
        client = DSpaceClient(uczelnia)
        client.authenticate()
        if istnieje_uuid:
            client.patch_item(istnieje_uuid, dc)
            uuid, status = istnieje_uuid, "zaktualizowano"
        else:
            uuid = client.create_item(mapowanie.collection_uuid, dc)
            status = "wyslano"
        SentToDSpace.objects.mark_as_successful(rec, uczelnia, dspace_uuid=uuid)
        return _wynik(uczelnia, status)
    except Exception as e:
        SentToDSpace.objects.mark_as_failed(
            rec, uczelnia, exception=traceback.format_exc()
        )
        return _wynik(uczelnia, "blad", str(e))
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_eksport.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/eksport.py src/dspace_api/tests/test_eksport.py
git commit -m "feat(dspace): orkiestracja eksportu (wachlarz per uczelnia)"
```

---

## FAZA 9 — Akcje admina, celery, komenda

### Task 17: Akcje admina

**Files:**
- Create: `src/dspace_api/actions.py`
- Modify: `src/bpp/admin/wydawnictwo_ciagle.py` (import + `actions`)
- Modify: `src/bpp/admin/wydawnictwo_zwarte.py` (import + `actions`)
- Test: `src/dspace_api/tests/test_actions.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_actions.py`:
```python
from unittest import mock

import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_akcja_raportuje_pominiecia():
    from dspace_api.actions import wyslij_do_dspace

    rec = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="T", rok=2024)
    modeladmin = mock.Mock()
    request = mock.Mock()
    qs = type(rec).objects.filter(pk=rec.pk)

    with mock.patch(
        "dspace_api.actions.eksportuj_rekord",
        return_value=[
            {"uczelnia": mock.Mock(), "status": "pominieto", "powod": "brak mapowania"}
        ],
    ):
        wyslij_do_dspace(modeladmin, request, qs)

    assert modeladmin.message_user.called


@pytest.mark.django_db
def test_akcja_limit_10():
    from django.contrib import messages

    from dspace_api.actions import wyslij_do_dspace

    baker.make("bpp.Wydawnictwo_Ciagle", _quantity=11)
    modeladmin = mock.Mock()
    request = mock.Mock()
    qs = baker.models.Wydawnictwo_Ciagle.objects.all() if False else None
    from bpp.models import Wydawnictwo_Ciagle

    qs = Wydawnictwo_Ciagle.objects.all()

    wyslij_do_dspace(modeladmin, request, qs)
    # przy >10 rekordach woła message_user z poziomem ERROR i nie eksportuje
    args, kwargs = modeladmin.message_user.call_args
    assert messages.ERROR in args
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_actions.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementacja**

`src/dspace_api/actions.py`:
```python
from collections import Counter

from django.contrib import messages
from django.utils.translation import ngettext

from dspace_api.eksport import eksportuj_rekord
from dspace_api.tasks import queue_dspace_export_batch


def wyslij_do_dspace(modeladmin, request, queryset):
    count = queryset.count()
    if count > 10:
        modeladmin.message_user(
            request,
            f"Możesz wysłać maksymalnie 10 rekordów naraz. Wybrano {count}.",
            messages.ERROR,
        )
        return

    licznik = Counter()
    powody = []
    for rec in queryset:
        for w in eksportuj_rekord(rec):
            licznik[w["status"]] += 1
            if w["status"] in ("pominieto", "blad"):
                powody.append(f"{rec} → {w['uczelnia']}: {w['powod']}")

    podsumowanie = ", ".join(f"{k}: {v}" for k, v in licznik.items())
    modeladmin.message_user(request, f"DSpace — {podsumowanie}", messages.SUCCESS)
    if powody:
        modeladmin.message_user(
            request,
            "Pominięcia/błędy:\n" + "\n".join(powody),
            messages.WARNING,
        )


wyslij_do_dspace.short_description = "Wyślij do DSpace"


def wyslij_do_dspace_w_tle(modeladmin, request, queryset):
    count = queryset.count()
    if count > 2000:
        modeladmin.message_user(
            request,
            f"Możesz zakolejkować maksymalnie 2000 rekordów. Wybrano {count}.",
            messages.ERROR,
        )
        return

    model = queryset.model
    queue_dspace_export_batch.delay(
        app_label=model._meta.app_label,
        model_name=model._meta.model_name,
        record_ids=list(queryset.values_list("id", flat=True)),
        user_id=request.user.id,
    )
    modeladmin.message_user(
        request,
        f"Zakolejkowano {count} {ngettext('rekord', 'rekordów', count)} "
        f"do wysyłki do DSpace (w tle).",
        messages.SUCCESS,
    )


wyslij_do_dspace_w_tle.short_description = "Wyślij do DSpace w tle"
```

W `src/bpp/admin/wydawnictwo_ciagle.py`: dodaj import obok importu akcji PBN
(~58) i wpisy do `actions` (~303):
```python
from dspace_api.actions import wyslij_do_dspace, wyslij_do_dspace_w_tle
```
oraz w liście `actions = [...]` dopisz:
```python
        wyslij_do_dspace,
        wyslij_do_dspace_w_tle,
```
Analogicznie w `src/bpp/admin/wydawnictwo_zwarte.py`.

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_actions.py -v`
Expected: 2 PASS. (Wymaga Task 18 — `tasks.queue_dspace_export_batch` —
zaimplementuj Task 18 przed uruchomieniem, lub tymczasowo zaślepkę.)

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/actions.py src/bpp/admin/wydawnictwo_ciagle.py \
        src/bpp/admin/wydawnictwo_zwarte.py src/dspace_api/tests/test_actions.py
git commit -m "feat(dspace): akcje admina wyslij_do_dspace (+ w tle)"
```

### Task 18: Celery task batch

**Files:**
- Create: `src/dspace_api/tasks.py`
- Test: `src/dspace_api/tests/test_tasks.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_tasks.py`:
```python
from unittest import mock

import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_batch_task_eksportuje_kazdy_rekord():
    from dspace_api.tasks import queue_dspace_export_batch

    r1 = baker.make("bpp.Wydawnictwo_Ciagle")
    r2 = baker.make("bpp.Wydawnictwo_Ciagle")

    with mock.patch("dspace_api.tasks.eksportuj_rekord", return_value=[]) as m:
        queue_dspace_export_batch(
            app_label="bpp",
            model_name="wydawnictwo_ciagle",
            record_ids=[r1.id, r2.id],
            user_id=None,
        )
    assert m.call_count == 2
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_tasks.py -v`
Expected: FAIL.

- [ ] **Step 3: Implementacja**

`src/dspace_api/tasks.py`:
```python
import rollbar
from django.apps import apps

from django_bpp.celery_tasks import app
from dspace_api.eksport import eksportuj_rekord


@app.task
def queue_dspace_export_batch(app_label, model_name, record_ids, user_id=None):
    model = apps.get_model(app_label, model_name)
    for rec in model.objects.filter(id__in=record_ids):
        try:
            eksportuj_rekord(rec)
        except Exception:
            rollbar.report_exc_info()
            raise
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_tasks.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/dspace_api/tasks.py src/dspace_api/tests/test_tasks.py
git commit -m "feat(dspace): celery task queue_dspace_export_batch"
```

### Task 19: Management command

**Files:**
- Create: `src/dspace_api/management/commands/dspace_wyslij.py`
- Test: `src/dspace_api/tests/test_command.py`

- [ ] **Step 1: Napisz test (failing)**

`src/dspace_api/tests/test_command.py`:
```python
from unittest import mock

import pytest
from django.core.management import call_command
from model_bakery import baker


@pytest.mark.django_db
def test_command_wola_eksport_dla_id():
    rec = baker.make("bpp.Wydawnictwo_Ciagle")
    with mock.patch(
        "dspace_api.management.commands.dspace_wyslij.eksportuj_rekord",
        return_value=[],
    ) as m:
        call_command("dspace_wyslij", "wydawnictwo_ciagle", str(rec.id))
    assert m.called
```

- [ ] **Step 2: Uruchom — ma FAIL**

Run: `uv run pytest src/dspace_api/tests/test_command.py -v`
Expected: FAIL — `CommandError: Unknown command`.

- [ ] **Step 3: Implementacja**

`src/dspace_api/management/commands/dspace_wyslij.py`:
```python
from django.apps import apps
from django.core.management.base import BaseCommand

from dspace_api.eksport import eksportuj_rekord


class Command(BaseCommand):
    help = "Wyślij wybrane rekordy do DSpace (wachlarz per uczelnia)."

    def add_arguments(self, parser):
        parser.add_argument("model_name", help="np. wydawnictwo_ciagle")
        parser.add_argument("ids", nargs="+", help="ID rekordów")

    def handle(self, *args, **options):
        model = apps.get_model("bpp", options["model_name"])
        for rec in model.objects.filter(id__in=options["ids"]):
            for w in eksportuj_rekord(rec):
                self.stdout.write(
                    f"{rec.id} → {w['uczelnia']}: {w['status']} {w['powod']}"
                )
```

- [ ] **Step 4: Uruchom — ma PASS**

Run: `uv run pytest src/dspace_api/tests/test_command.py -v`
Expected: PASS.

- [ ] **Step 5: Uruchom CAŁY moduł + lint**

Run:
```bash
uv run pytest src/dspace_api/ -v
ruff check src/dspace_api/ src/bpp/fields.py
ruff format --check src/dspace_api/ src/bpp/fields.py
```
Expected: wszystkie testy PASS, ruff czysto.

- [ ] **Step 6: Commit**

```bash
git add src/dspace_api/management src/dspace_api/tests/test_command.py
git commit -m "feat(dspace): management command dspace_wyslij"
```

---

## FAZA 10 — Upload bitstreamów (BRAMKOWANA — wymaga ustalenia storage)

> **STOP-GATE:** `Element_Repozytorium` nie ma `FileField` — trzyma tylko
> `nazwa_pliku`. Tej fazy NIE zaczynaj, dopóki Task 20 nie ustali, gdzie są
> bajty plików. Jeśli BPP nie przechowuje plików — ta faza odpada (zostaje
> eksport metadanowy z faz 1–9, w pełni działający).

### Task 20: Spike — gdzie są bajty plików repozytorium?

- [ ] **Step 1:** Ustal storage: przeszukaj kod pod kątem zapisu/odczytu
  plików powiązanych z `Element_Repozytorium` (grep `nazwa_pliku`,
  `MEDIA_ROOT`, `FileField`, `Storage`, `upload`, `repozytorium`). Sprawdź
  czy istnieje osobny model/serwis trzymający `FileField`, czy pliki są na
  dysku/S3 i jak `nazwa_pliku` mapuje na ścieżkę. Sprawdź `tryb_dostepu`
  enum (`bpp.const.TRYB_DOSTEPU.JAWNY == 2`).
- [ ] **Step 2:** Udokumentuj wynik w
  `docs/superpowers/specs/2026-06-03-dspace-export-design.md` (sekcja 11).
- [ ] **Step 3:** Decyzja: jeśli bajty dostępne → Task 21; jeśli nie →
  zamknij fazę, zaktualizuj spec (bitstreamy = niewykonalne obecnie).

### Task 21 (warunkowy): Upload jawnych plików jako bitstream

> Zaprojektuj po Task 20, gdy znasz API pobrania bajtów. Szkic:
> - `client.ensure_bundle(item_uuid, "ORIGINAL")` + `client.create_bitstream(...)`,
> - w `_eksportuj_do_uczelni`, po `create_item`, iteruj jawne pliki
>   (`tryb_dostepu == TRYB_DOSTEPU.JAWNY`) i wgrywaj,
> - TDD: mock klienta, asercja że dla pliku JAWNY wołane `create_bitstream`,
>   a dla NIEJAWNY/TYLKO_W_SIECI nie.

---

## FAZA 11 — Smoke-test end-to-end (manualny, poza CI)

### Task 22: Walidacja na testowej instalacji DSpace 9.x

- [ ] **Step 1:** Skonfiguruj testową `Uczelnia` (endpoint 9.x, konto API z
  prawami collection-admin, `dspace_aktywny=True`, `DSPACE_CREDENTIALS_KEY`
  w env). Dodaj `Mapowanie_DSpace` dla wybranego charakteru → realna kolekcja.
- [ ] **Step 2:** Uruchom `uv run python src/manage.py dspace_wyslij
  wydawnictwo_ciagle <ID>` na realnym rekordzie. Zweryfikuj item w DSpace
  (HAL-browser / UI). Potwierdź zgodność sygnatur `dspace-rest-client`
  (create_item/update_item/Item) — jeśli różne, popraw `client.py` (+ test).
- [ ] **Step 3:** Test re-wysyłki: zmień metadane, wyślij ponownie → PATCH,
  nie duplikat. Sprawdź `SentToDSpace` (status, dspace_uuid).

---

## Self-Review (do wykonania przez autora planu)

Pokrycie specu:
- §2 wachlarz per-uczelnia → Task 9 (selektor) + Task 16 (orkiestracja). ✓
- §2 config na Uczelni + szyfrowanie → Task 3,4,5. ✓
- §2 routing per uczelnia, brak mapy = warning → Task 16 + Task 17. ✓
- §2 pliki jawne / metadata-only → metadata-only faza 1–9; pliki faza 10 (bramkowane). ✓ (świadomy podział)
- §4 modele → Task 6,8. ✓
- §6 mapowanie DC + 5 typów → Task 10–14. ✓
- §7 akcje admina + command → Task 17–19. ✓
- §8 bezpieczeństwo (szyfrowanie, tylko jawne, brak except:pass) → Task 3; faza 10; `eksport.py` używa `traceback`+`mark_as_failed`+re-raise w tasku. ✓

Spójność typów: `to_dspace_dict()`, `adapter_for()`, `eksportuj_rekord()`,
`DSpaceClient(uczelnia)`, `SentToDSpace.objects.*(rec, uczelnia, ...)` —
nazwy spójne między taskami. ✓

Uwagi wykonawcze (zweryfikuj na realnych modelach przy implementacji):
- nazwa FK rekordu w through-modelach (`rekord` vs inna) — popraw `baker.make` jeśli trzeba,
- `Praca_Doktorska.autorzy_set` to property (nie queryset) — selektor to obsługuje gałęzią `jednostka`,
- sygnatury `dspace-rest-client` 0.1.x — finalna weryfikacja w fazie 11.
