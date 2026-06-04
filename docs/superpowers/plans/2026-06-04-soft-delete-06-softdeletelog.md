# Soft-delete — Faza 06: SoftDeleteLog + receivery sygnałów + atrybucja usera

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zbudować dedykowany audyt soft-delete: model `SoftDeleteLog` (kto / kiedy / dlaczego / status PBN) zasilany przez receivery sygnałów pakietu `django-soft-delete` (`post_soft_delete`, `post_restore`, `post_hard_delete`). Receiver `DELETE` dla publikacji z `pbn_uid` kolejkuje wycofanie oświadczeń PBN (`zakolejkuj_wycofanie` z fazy 05) i podpina wpis kolejki do logu; `RESTORE` kolejkuje ponowną wysyłkę (`zakolejkuj_wysylke`). Atrybucja „kto" rozwiązana przez thread-local context manager ustawiany w override `delete(user=, reason=)`/`restore(user=)` (fazy 02/04) — sygnał pakietu sam nie niesie usera.

**Architecture:** Pakiet `django-soft-delete` wysyła `post_soft_delete`/`post_hard_delete`/`post_restore` z `sender`+`instance` (zweryfikowane: `models.py:174,85,234`), ale BEZ usera/powodu. Override `delete()`/`restore()` (fazy 02/04) ustawia thread-local przez context manager `soft_delete_context(user=, reason=)` tuż przed wywołaniem pakietowego `super().delete()`. Receivery (jeden punkt podpięcia dla WSZYSTKICH soft-deletowalnych modeli) czytają thread-local i tworzą `SoftDeleteLog`. Receiver `DELETE`/`RESTORE` woła funkcje kolejkujące PBN z fazy 05 i zapisuje `pbn_queue_entry` + `pbn_status` na logu. Rejestracja w `BppConfig.ready()` (`src/bpp/apps.py:8`).

**Tech Stack:** Django 4.2, `django-soft-delete>=1.0.23`, `pbn_export_queue` (faza 05), pytest + model_bakery. Python przez `uv run`. Max 88 znaków (ruff). Polski w komunikatach/verbose_name.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md) (§5)
**Plan-indeks (kontrakty PINNED):** [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md)

**Zależności:** Faza 02 (modele publikacji emitują sygnały + override `delete(user=, reason=)`/`restore(user=)`), Faza 05 (funkcje kolejkujące PBN). Patrz „Kontrakty z fazami 02 i 05" niżej.

---

## Kontrakty z fazami 02 i 05 (czytaj PRZED implementacją)

### Co ta faza DOSTARCZA fazom 02/04 (one tego importują)
- `src/bpp/models/soft_delete_context.py` — context manager + akcesory:
  ```python
  from contextlib import contextmanager
  import threading

  _ctx = threading.local()

  @contextmanager
  def soft_delete_context(user=None, reason=""):
      """Ustawia thread-local user/reason na czas pakietowego
      delete()/restore(). Receiver post_* czyta to przez
      current_soft_delete_user()/current_soft_delete_reason()."""
      prev_user = getattr(_ctx, "user", None)
      prev_reason = getattr(_ctx, "reason", "")
      _ctx.user = user
      _ctx.reason = reason
      try:
          yield
      finally:
          _ctx.user = prev_user
          _ctx.reason = prev_reason

  def current_soft_delete_user():
      return getattr(_ctx, "user", None)

  def current_soft_delete_reason():
      return getattr(_ctx, "reason", "")
  ```
- **Faza 02/04 owija** wnętrze swojego override `delete()`/`restore()`:
  ```python
  def delete(self, *args, user=None, reason="", **kwargs):
      with soft_delete_context(user=user, reason=reason):
          return super().delete(*args, **kwargs)  # tu leci post_soft_delete
  ```
  Dzięki temu, gdy pakiet wyśle `post_soft_delete` (wewnątrz `super().delete()`),
  thread-local wciąż jest ustawiony i receiver odczyta usera. Reentrancja jest
  bezpieczna (zapamiętanie prev_*), więc wąska kaskada na `*_Autor`
  (faza 02) dziedziczy ten sam kontekst.
- Operacje BEZ usera (merge autorów, celery, `.delete()` w kodzie bez kontekstu)
  → thread-local nieustawiony → `current_soft_delete_user()` zwraca `None`.

> **Realny stan na dziś:** `src/bpp/models/soft_delete_context.py` NIE istnieje
> (zweryfikowano — w `src/bpp/models/` jest tylko `soft_delete.py` z fazy 01,
> managery). Tę fazę tworzy plik od zera; fazy 02/04 już go importują (są
> przed 06 w kolejce, ale plik dostarcza 06 — jeśli fazy 02/04 były robione
> wcześniej i dodały tymczasowy stub, scal go z tym kontraktem VERBATIM).

### Czego ta faza WYMAGA od fazy 05 (PINNED — VERBATIM nazwy)
Faza 05 dostarcza w `src/pbn_export_queue/operacje.py` (lub `tasks.py`):
```python
def zakolejkuj_wycofanie(instance, user=None):
    """Tworzy PBN_Export_Queue(operacja=WYCOFANIE) dla publikacji z pbn_uid.
    Zwraca utworzony PBN_Export_Queue albo None (gdy brak pbn_uid)."""

def zakolejkuj_wysylke(instance, user=None):
    """Tworzy PBN_Export_Queue(operacja=WYSYLKA) dla publikacji z pbn_uid.
    Zwraca utworzony PBN_Export_Queue albo None (gdy brak pbn_uid)."""
```
- Obie przyjmują `instance` (rekord publikacji) + `user` (może być `None`).
- Obie zwracają instancję `PBN_Export_Queue` (do podpięcia w `SoftDeleteLog.
  pbn_queue_entry`) albo `None` gdy gate `pbn_uid` nie spełniony.
- **Jeśli faza 05 jeszcze nie istnieje w worktree** — task 5 niżej zawiera
  cienki shim, który faza 05 zastąpi pełną implementacją. Receiver woła te
  funkcje przez import w środku, więc shim nie blokuje testów fazy 06.

### Detekcja „publikacja z `pbn_uid`" (zweryfikowane)
Receiver NIE zna typu instancji. Gate uniwersalny:
`getattr(instance, "pbn_uid_id", None) is not None`. Publikacje
(`Wydawnictwo_*`) mają `pbn_uid` (FK, `pbn_uid_id`); `Autor` i `*_Autor` nie
mają → `getattr(..., None)` zwraca `None` → PBN pomijamy automatycznie.
(Zweryfikowano: `src/bpp/models/abstract/pbn.py:35` `hasattr(self, "pbn_uid")`.)

### Sygnatury sygnałów pakietu (zweryfikowane w `django_softdelete/models.py`)
- `post_soft_delete.send(sender=cls, instance=self, using=using)` (`:174`).
- `post_hard_delete.send(sender=cls, instance=self)` (`:85`) — BEZ `using`.
- `post_restore.send(sender=cls, instance=self, transaction_id=...)` (`:234`)
  — BEZ `using`, ZA TO z `transaction_id`.
- **Wniosek dla receiverów:** sygnatura `def receiver(sender, instance,
  **kwargs)` — `**kwargs` połyka `using`/`transaction_id` (różnią się między
  sygnałami). Nie polegaj na `using`/`transaction_id`.

---

## Wspólne kontrakty (PINNED — VERBATIM z indeksu 00)

### `SoftDeleteLog` — `src/bpp/models/soft_delete_log.py`
Pola DOKŁADNIE:
- `content_type` — `FK(ContentType, on_delete=CASCADE)`,
- `object_id` — `PositiveIntegerField(db_index=True)`,
- `content_object` — `GenericForeignKey("content_type", "object_id")`,
- `akcja` — `CharField(choices=Akcja.choices)` gdzie
  `class Akcja(models.TextChoices): DELETE="delete"; RESTORE="restore";
  HARD_DELETE="hard_delete"`,
- `user` — `FK(AUTH_USER_MODEL, null=True, blank=True, on_delete=SET_NULL)`,
- `timestamp` — `DateTimeField(auto_now_add=True, db_index=True)`,
- `powod` — `TextField(blank=True, default="")`,
- `pbn_queue_entry` — `FK("pbn_export_queue.PBN_Export_Queue", null=True,
  blank=True, on_delete=SET_NULL)`,
- `pbn_status` — `CharField(max_length=50, blank=True, default="")`.

### Receivery — `src/bpp/receivers/soft_delete.py`
- `post_soft_delete` → `SoftDeleteLog(akcja=DELETE, user, powod)`; jeśli
  publikacja z `pbn_uid` → `zakolejkuj_wycofanie(instance, user)` i podepnij
  `pbn_queue_entry` + ustaw `pbn_status="WYCOFANIE"`.
- `post_restore` → `SoftDeleteLog(akcja=RESTORE)`; jeśli z `pbn_uid` →
  `zakolejkuj_wysylke(instance, user)` + `pbn_queue_entry` + `pbn_status=
  "WYSYLKA"`.
- `post_hard_delete` → `SoftDeleteLog(akcja=HARD_DELETE)` (bez PBN — rekord
  fizycznie znika).
- Rejestracja w `src/bpp/apps.py` → `BppConfig.ready()`.

### Kontrakt z reversion (NIE łamać)
Punkt wstrzyknięcia usera (`soft_delete_context`) to JEDEN hook — ten sam
moment, w którym przyszła integracja `reversion.set_user` doczepi usera.
Receivery NIE robią bulk-update i nie omijają `post_save` (tylko czytają
sygnały + tworzą wiersze logu).

---

## Tasks

### Task 1: Context manager atrybucji usera (thread-local)

**Files:**
- Create: `src/bpp/models/soft_delete_context.py`
- Test: `src/bpp/tests/test_soft_delete/test_soft_delete_context.py`

**Step 1 — Failing test:**
- [ ] Utwórz `src/bpp/tests/test_soft_delete/__init__.py` (pusty) jeśli katalog
  nie istnieje.
- [ ] Napisz `src/bpp/tests/test_soft_delete/test_soft_delete_context.py`:
```python
from bpp.models.soft_delete_context import (
    current_soft_delete_reason,
    current_soft_delete_user,
    soft_delete_context,
)


def test_context_brak_usera_domyslnie():
    assert current_soft_delete_user() is None
    assert current_soft_delete_reason() == ""


def test_context_ustawia_i_czysci(django_user_model, db):
    u = django_user_model.objects.create(username="ktos")
    with soft_delete_context(user=u, reason="literówka"):
        assert current_soft_delete_user() == u
        assert current_soft_delete_reason() == "literówka"
    assert current_soft_delete_user() is None
    assert current_soft_delete_reason() == ""


def test_context_zagniezdzony_przywraca_zewnetrzny(django_user_model, db):
    a = django_user_model.objects.create(username="a")
    b = django_user_model.objects.create(username="b")
    with soft_delete_context(user=a, reason="zewn"):
        with soft_delete_context(user=b, reason="wewn"):
            assert current_soft_delete_user() == b
            assert current_soft_delete_reason() == "wewn"
        assert current_soft_delete_user() == a
        assert current_soft_delete_reason() == "zewn"
    assert current_soft_delete_user() is None
```
**Step 2 — Run → FAIL:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_context.py`
  → FAIL (ModuleNotFoundError: `bpp.models.soft_delete_context`).
**Step 3 — Implementation:**
- [ ] Utwórz `src/bpp/models/soft_delete_context.py` z treścią VERBATIM jak
  w sekcji „Co ta faza DOSTARCZA fazom 02/04" wyżej (`soft_delete_context`,
  `current_soft_delete_user`, `current_soft_delete_reason`, `threading.local`).
**Step 4 — Run → PASS:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_context.py`
  → 3 passed.
- [ ] `ruff check src/bpp/models/soft_delete_context.py && ruff format
  --check src/bpp/models/soft_delete_context.py`
**Step 5 — Commit:**
- [ ] `git add src/bpp/models/soft_delete_context.py
  src/bpp/tests/test_soft_delete/` i commit:
  `feat(soft-delete): context manager atrybucji usera (thread-local)`

---

### Task 2: Model `SoftDeleteLog` + migracja

**Files:**
- Create: `src/bpp/models/soft_delete_log.py`
- Modify: `src/bpp/models/__init__.py` (dopisz import, wzorzec `oplaty_log`
  na `:52`)
- Create: `src/bpp/migrations/0421_softdeletelog.py` (NUMER: sprawdź najwyższą
  istniejącą migrację `bpp` przez `ls src/bpp/migrations/ | grep -E '^04' |
  sort | tail -1` i nadaj kolejny — **NIE modyfikuj istniejących migracji**)
- Test: `src/bpp/tests/test_soft_delete/test_soft_delete_log_model.py`

**Step 1 — Failing test:**
- [ ] Napisz `test_soft_delete_log_model.py`:
```python
import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models.soft_delete_log import SoftDeleteLog


@pytest.mark.django_db
def test_softdeletelog_gfk_wskazuje_na_rekord(wydawnictwo_ciagle):
    log = SoftDeleteLog.objects.create(
        content_type=ContentType.objects.get_for_model(wydawnictwo_ciagle),
        object_id=wydawnictwo_ciagle.pk,
        akcja=SoftDeleteLog.Akcja.DELETE,
        powod="test",
    )
    assert log.content_object == wydawnictwo_ciagle
    assert log.timestamp is not None
    assert log.user is None
    assert log.pbn_queue_entry is None
    assert log.pbn_status == ""


@pytest.mark.django_db
def test_softdeletelog_akcja_choices():
    assert SoftDeleteLog.Akcja.DELETE == "delete"
    assert SoftDeleteLog.Akcja.RESTORE == "restore"
    assert SoftDeleteLog.Akcja.HARD_DELETE == "hard_delete"


@pytest.mark.django_db
def test_softdeletelog_user_set_null(wydawnictwo_ciagle, django_user_model):
    u = baker.make(django_user_model)
    log = SoftDeleteLog.objects.create(
        content_type=ContentType.objects.get_for_model(wydawnictwo_ciagle),
        object_id=wydawnictwo_ciagle.pk,
        akcja=SoftDeleteLog.Akcja.DELETE,
        user=u,
    )
    u.delete()
    log.refresh_from_db()
    assert log.user is None
```
**Step 2 — Run → FAIL:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_log_model.py`
  → FAIL (ImportError SoftDeleteLog).
**Step 3 — Implementation:**
- [ ] Utwórz `src/bpp/models/soft_delete_log.py` (wzorzec `oplaty_log.py`):
```python
"""Dedykowany audyt operacji soft-delete (kto / kiedy / dlaczego / PBN)."""

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from django_bpp.settings.base import AUTH_USER_MODEL

__all__ = ["SoftDeleteLog"]


class SoftDeleteLog(models.Model):
    """Wpis audytu pojedynczej operacji soft-delete / restore / hard-delete."""

    class Akcja(models.TextChoices):
        DELETE = "delete", "Usunięcie (kosz)"
        RESTORE = "restore", "Przywrócenie"
        HARD_DELETE = "hard_delete", "Usunięcie trwałe"

    content_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, verbose_name="Typ rekordu"
    )
    object_id = models.PositiveIntegerField(db_index=True, verbose_name="ID obiektu")
    content_object = GenericForeignKey("content_type", "object_id")

    akcja = models.CharField(
        max_length=20, choices=Akcja.choices, db_index=True, verbose_name="Akcja"
    )
    user = models.ForeignKey(
        AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Użytkownik",
    )
    timestamp = models.DateTimeField(
        auto_now_add=True, db_index=True, verbose_name="Data operacji"
    )
    powod = models.TextField(blank=True, default="", verbose_name="Powód")

    pbn_queue_entry = models.ForeignKey(
        "pbn_export_queue.PBN_Export_Queue",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name="Wpis kolejki PBN",
    )
    pbn_status = models.CharField(
        max_length=50, blank=True, default="", verbose_name="Status PBN"
    )

    class Meta:
        verbose_name = "Log operacji soft-delete"
        verbose_name_plural = "Logi operacji soft-delete"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.get_akcja_display()}: {self.content_object} ({self.timestamp})"
```
- [ ] Dopisz w `src/bpp/models/__init__.py` (po linii z `oplaty_log`):
  `from .soft_delete_log import *  # noqa`
- [ ] Wygeneruj migrację: `uv run python src/manage.py makemigrations bpp`
  (sprawdź, że dependency na `pbn_export_queue` jest w wygenerowanej migracji —
  Django doda je automatycznie przez FK; jeśli nie, dopisz ręcznie
  `("pbn_export_queue", "<ostatnia>")` do `dependencies`).
**Step 4 — Run → PASS:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_log_model.py`
  → 3 passed.
- [ ] `uv run python src/manage.py makemigrations --check --dry-run bpp`
  → „No changes detected" (migracja kompletna).
- [ ] `ruff check src/bpp/models/soft_delete_log.py`
**Step 5 — Commit:**
- [ ] Commit: `feat(soft-delete): model SoftDeleteLog + migracja`

---

### Task 3: Receiver `post_hard_delete` → log HARD_DELETE

(robiony pierwszy z receiverów — najprostszy, bez PBN, bez kolejki)

**Files:**
- Create: `src/bpp/receivers/__init__.py` (pusty)
- Create: `src/bpp/receivers/soft_delete.py`
- Modify: `src/bpp/apps.py` (`BppConfig.ready()` — rejestracja)
- Test: `src/bpp/tests/test_soft_delete/test_receivers.py`

**Step 1 — Failing test:**
- [ ] Napisz `test_receivers.py` (pierwszy test):
```python
import pytest
from django.contrib.contenttypes.models import ContentType

from bpp.models.soft_delete_context import soft_delete_context
from bpp.models.soft_delete_log import SoftDeleteLog


def _logi(instance, akcja):
    return SoftDeleteLog.objects.filter(
        content_type=ContentType.objects.get_for_model(instance),
        object_id=instance.pk,
        akcja=akcja,
    )


@pytest.mark.django_db
def test_hard_delete_tworzy_log(wydawnictwo_ciagle, superuser):
    pk = wydawnictwo_ciagle.pk
    ct = ContentType.objects.get_for_model(wydawnictwo_ciagle)
    with soft_delete_context(user=superuser, reason="trwałe"):
        wydawnictwo_ciagle.hard_delete()
    log = SoftDeleteLog.objects.get(
        content_type=ct, object_id=pk, akcja=SoftDeleteLog.Akcja.HARD_DELETE
    )
    assert log.user == superuser
    assert log.powod == "trwałe"
    assert log.pbn_queue_entry is None
```
**Step 2 — Run → FAIL:**
- [ ] `uv run pytest "src/bpp/tests/test_soft_delete/test_receivers.py::test_hard_delete_tworzy_log"`
  → FAIL (brak receiverów → log nie powstaje → `SoftDeleteLog.DoesNotExist`).
**Step 3 — Implementation:**
- [ ] Utwórz `src/bpp/receivers/__init__.py` (pusty).
- [ ] Utwórz `src/bpp/receivers/soft_delete.py`:
```python
"""Receivery sygnałów django-soft-delete → zasilanie SoftDeleteLog + PBN."""

from django.contrib.contenttypes.models import ContentType

from bpp.models.soft_delete_context import (
    current_soft_delete_reason,
    current_soft_delete_user,
)
from bpp.models.soft_delete_log import SoftDeleteLog


def _utworz_log(instance, akcja, pbn_queue_entry=None, pbn_status=""):
    return SoftDeleteLog.objects.create(
        content_type=ContentType.objects.get_for_model(instance),
        object_id=instance.pk,
        akcja=akcja,
        user=current_soft_delete_user(),
        powod=current_soft_delete_reason(),
        pbn_queue_entry=pbn_queue_entry,
        pbn_status=pbn_status,
    )


def on_post_hard_delete(sender, instance, **kwargs):
    """Hard-delete: rekord fizycznie znika, więc bez operacji PBN."""
    _utworz_log(instance, SoftDeleteLog.Akcja.HARD_DELETE)


def register():
    from django_softdelete.signals import (
        post_hard_delete,
        post_restore,
        post_soft_delete,
    )

    post_hard_delete.connect(
        on_post_hard_delete, dispatch_uid="bpp.soft_delete.post_hard_delete"
    )
```
> **UWAGA `pk` przy hard-delete:** `post_hard_delete` jest wysyłany PO
> `super().delete()` (pakiet, `models.py:84-85`). Django zeruje `instance.pk`
> dopiero gdy delete idzie przez kolektor — `SoftDeleteModel.hard_delete`
> woła `models.Model.delete()`, które ustawia `pk=None` po usunięciu. Test
> wyżej zapisuje `pk = ...` PRZED `hard_delete()`. W receiverze
> `instance.pk` może być `None` → **zapisz `object_id` z `instance.pk` jeśli
> nie-None, inaczej trzeba przekazać pk inaczej.** Zweryfikuj w teście: jeśli
> `instance.pk is None` w receiverze, zmień `on_post_hard_delete` by czytał pk
> z `instance.pk or kwargs`. Jeśli pakiet zachowuje pk (bo `hard_delete`
> nie czyści atrybutu instancji) — zostaw prosto. **Dostosuj implementację do
> faktycznego zachowania potwierdzonego testem, nie zgaduj.**
- [ ] W `src/bpp/apps.py`, w `BppConfig.ready()` (po `configure_rollbar()`,
  linia ~34) dopisz:
```python
        # Receivery soft-delete → SoftDeleteLog + kolejka PBN
        from bpp.receivers import soft_delete as soft_delete_receivers

        soft_delete_receivers.register()
```
**Step 4 — Run → PASS:**
- [ ] `uv run pytest "src/bpp/tests/test_soft_delete/test_receivers.py::test_hard_delete_tworzy_log"`
  → passed. Jeśli FAIL przez `pk is None` — popraw wg uwagi wyżej, ponów do PASS.
- [ ] `ruff check src/bpp/receivers/soft_delete.py src/bpp/apps.py`
**Step 5 — Commit:**
- [ ] Commit: `feat(soft-delete): receiver post_hard_delete → log HARD_DELETE`

---

### Task 4: Receiver `post_soft_delete` → log DELETE + atrybucja usera (bez PBN)

(PBN dochodzi w Tasku 6 — tu izolujemy log + usera/powód dla DELETE)

**Files:**
- Modify: `src/bpp/receivers/soft_delete.py`
- Test: `src/bpp/tests/test_soft_delete/test_receivers.py`

**Step 1 — Failing test:**
- [ ] Dopisz testy:
```python
@pytest.mark.django_db
def test_soft_delete_tworzy_log_z_userem(wydawnictwo_ciagle, superuser):
    with soft_delete_context(user=superuser, reason="duplikat"):
        wydawnictwo_ciagle.delete()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user == superuser
    assert log.powod == "duplikat"


@pytest.mark.django_db
def test_soft_delete_bez_usera_loguje_none(wydawnictwo_ciagle):
    wydawnictwo_ciagle.delete()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user is None
    assert log.powod == ""
```
> **Założenie:** `wydawnictwo_ciagle.delete()` emituje `post_soft_delete`
> (faza 02 wpięła `SoftDeleteModel` + override owijający `soft_delete_context`).
> Jeśli faza 02 NIE jest jeszcze w worktree, fixture `wydawnictwo_ciagle` nie
> jest `SoftDeleteModel` → `.delete()` zrobi hard delete bez sygnału.
> Wtedy w teście wyślij sygnał ręcznie przez
> `post_soft_delete.send(sender=type(wc), instance=wc)` wewnątrz
> `soft_delete_context(...)`, by testować SAM receiver w izolacji. Wybierz
> wariant zgodny ze stanem worktree i udokumentuj w docstringu testu.
**Step 2 — Run → FAIL:**
- [ ] `uv run pytest "src/bpp/tests/test_soft_delete/test_receivers.py::test_soft_delete_tworzy_log_z_userem" "src/bpp/tests/test_soft_delete/test_receivers.py::test_soft_delete_bez_usera_loguje_none"`
  → FAIL (brak receivera DELETE → brak logu).
**Step 3 — Implementation:**
- [ ] Dodaj do `src/bpp/receivers/soft_delete.py`:
```python
def on_post_soft_delete(sender, instance, **kwargs):
    _utworz_log(instance, SoftDeleteLog.Akcja.DELETE)
```
- [ ] W `register()` dopisz:
```python
    post_soft_delete.connect(
        on_post_soft_delete, dispatch_uid="bpp.soft_delete.post_soft_delete"
    )
```
**Step 4 — Run → PASS:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_receivers.py` → all passed.
- [ ] `ruff check src/bpp/receivers/soft_delete.py`
**Step 5 — Commit:**
- [ ] Commit: `feat(soft-delete): receiver post_soft_delete → log DELETE + user`

---

### Task 5: Shim funkcji kolejkujących PBN (kontrakt z fazą 05)

> Cienka warstwa, by faza 06 była testowalna niezależnie od kolejności
> wykonania faz. **Jeśli faza 05 już istnieje** (`zakolejkuj_wycofanie`/
> `zakolejkuj_wysylke` w `src/pbn_export_queue/`) — POMIŃ ten task, użyj
> realnych funkcji. Sprawdź: `uv run python -c "from pbn_export_queue.operacje
> import zakolejkuj_wycofanie, zakolejkuj_wysylke"`.

**Files:**
- Create (tylko jeśli brak fazy 05): `src/pbn_export_queue/operacje.py`
- Test: `src/bpp/tests/test_soft_delete/test_pbn_queue_shim.py`

**Step 1 — Failing test:**
- [ ] Napisz test (gate `pbn_uid`):
```python
import pytest
from model_bakery import baker

from pbn_export_queue.operacje import zakolejkuj_wycofanie, zakolejkuj_wysylke
from pbn_export_queue.models import PBN_Export_Queue


@pytest.mark.django_db
def test_zakolejkuj_wycofanie_bez_pbn_uid_zwraca_none(autor):
    # autor nie ma pbn_uid_id → None
    assert zakolejkuj_wycofanie(autor) is None


@pytest.mark.django_db
def test_zakolejkuj_wycofanie_z_pbn_uid_tworzy_wpis(
    wydawnictwo_ciagle, superuser
):
    wydawnictwo_ciagle.pbn_uid_id = "00000000-0000-0000-0000-000000000001"
    wydawnictwo_ciagle.save()
    wpis = zakolejkuj_wycofanie(wydawnictwo_ciagle, user=superuser)
    assert isinstance(wpis, PBN_Export_Queue)
    assert wpis.object_id == wydawnictwo_ciagle.pk


@pytest.mark.django_db
def test_zakolejkuj_wysylke_z_pbn_uid_tworzy_wpis(wydawnictwo_ciagle, superuser):
    wydawnictwo_ciagle.pbn_uid_id = "00000000-0000-0000-0000-000000000002"
    wydawnictwo_ciagle.save()
    wpis = zakolejkuj_wysylke(wydawnictwo_ciagle, user=superuser)
    assert isinstance(wpis, PBN_Export_Queue)
```
> **Uwaga do fazy 02/05:** `pbn_uid_id` musi przyjąć wartość. Jeśli FK celuje
> w `pbn_api.Publication`, baker/`save()` z surowym UUID-em może wymagać
> istniejącego rekordu — wtedy w teście stwórz `baker.make("pbn_api.
> Publication")` i przypisz `wydawnictwo_ciagle.pbn_uid = pub`. Dostosuj do
> realnego typu FK potwierdzonego w `wydawnictwo_ciagle.py`.
**Step 2 — Run → FAIL:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_pbn_queue_shim.py`
  → FAIL (ModuleNotFoundError `pbn_export_queue.operacje`).
**Step 3 — Implementation (shim — faza 05 nadpisze pełną logiką):**
- [ ] Utwórz `src/pbn_export_queue/operacje.py`:
```python
"""Operacje kolejkowania PBN dla soft-delete (WYCOFANIE / WYSYLKA).

UWAGA: cienki shim z fazy 06. Faza 05 nadpisuje go pełną implementacją
(pole `operacja`, gałąź `delete_all_publication_statements`, integracja
SentData). Tu utrzymujemy wyłącznie kontrakt sygnatur + gate `pbn_uid`.
"""

from contextlib import suppress

from pbn_export_queue.models import PBN_Export_Queue


def _ma_pbn_uid(instance):
    return getattr(instance, "pbn_uid_id", None) is not None


def _utworz_wpis(instance, user):
    return PBN_Export_Queue.objects.create(
        rekord_do_wysylki=instance,
        zamowil=user,
    )


def zakolejkuj_wycofanie(instance, user=None):
    """Kolejkuje wycofanie oświadczeń PBN. None gdy brak pbn_uid."""
    if not _ma_pbn_uid(instance):
        return None
    return _utworz_wpis(instance, user)


def zakolejkuj_wysylke(instance, user=None):
    """Kolejkuje ponowną wysyłkę do PBN. None gdy brak pbn_uid."""
    if not _ma_pbn_uid(instance):
        return None
    return _utworz_wpis(instance, user)
```
> **Niuans `zamowil`:** `PBN_Export_Queue.zamowil` to `FK(AUTH_USER_MODEL,
> on_delete=CASCADE)` BEZ `null=True` (zweryfikowano `models.py:79`). Dla
> operacji systemowych `user=None` ten FK się wywali. Faza 05 to rozwiąże
> (np. konto techniczne lub `null=True`). W teście Tasku 5 przekazuj
> `user=superuser`. W receiverze (Task 6) gate `pbn_uid` i tak zwykle idzie
> z akcji admina (user jest). Jeśli `user is None` w receiverze przy
> publikacji z `pbn_uid` — owiń wywołanie w `suppress(...)`/log, NIE wywal
> całej operacji delete. **To dług fazy 05; udokumentuj `# TODO(faza 05)`.**
> Usuń niewykorzystany import `suppress`, jeśli go nie użyjesz.
**Step 4 — Run → PASS:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_pbn_queue_shim.py`
  → passed.
- [ ] `ruff check src/pbn_export_queue/operacje.py`
**Step 5 — Commit:**
- [ ] Commit: `feat(soft-delete): shim zakolejkuj_wycofanie/wysylke (kontrakt 05)`

---

### Task 6: PBN w receiverach — DELETE→WYCOFANIE, RESTORE→WYSYLKA, podpięcie kolejki

**Files:**
- Modify: `src/bpp/receivers/soft_delete.py`
- Test: `src/bpp/tests/test_soft_delete/test_receivers.py`

**Step 1 — Failing test:**
- [ ] Dopisz testy (publikacja z `pbn_uid` + restore):
```python
@pytest.mark.django_db
def test_soft_delete_z_pbn_uid_kolejkuje_wycofanie(
    wydawnictwo_ciagle, superuser
):
    wydawnictwo_ciagle.pbn_uid_id = "00000000-0000-0000-0000-000000000010"
    wydawnictwo_ciagle.save()
    with soft_delete_context(user=superuser, reason="x"):
        wydawnictwo_ciagle.delete()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.pbn_queue_entry is not None
    assert log.pbn_status == "WYCOFANIE"


@pytest.mark.django_db
def test_soft_delete_bez_pbn_uid_nie_kolejkuje(wydawnictwo_ciagle, superuser):
    # brak pbn_uid → log bez wpisu kolejki
    with soft_delete_context(user=superuser):
        wydawnictwo_ciagle.delete()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.DELETE).get()
    assert log.pbn_queue_entry is None
    assert log.pbn_status == ""


@pytest.mark.django_db
def test_restore_z_pbn_uid_kolejkuje_wysylke(wydawnictwo_ciagle, superuser):
    wydawnictwo_ciagle.pbn_uid_id = "00000000-0000-0000-0000-000000000011"
    wydawnictwo_ciagle.save()
    with soft_delete_context(user=superuser):
        wydawnictwo_ciagle.delete()
    with soft_delete_context(user=superuser):
        wydawnictwo_ciagle.restore()
    log = _logi(wydawnictwo_ciagle, SoftDeleteLog.Akcja.RESTORE).get()
    assert log.pbn_queue_entry is not None
    assert log.pbn_status == "WYSYLKA"
```
> Jeśli faza 02 nie wpięła `SoftDeleteModel`/override — testuj receiver
> przez ręczny `post_soft_delete.send(...)` / `post_restore.send(...)`
> wewnątrz `soft_delete_context`, jak w uwadze Tasku 4.
**Step 2 — Run → FAIL:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_receivers.py`
  → FAIL (receivery nie kolejkują PBN, brak receivera RESTORE).
**Step 3 — Implementation:**
- [ ] Przebuduj receivery w `src/bpp/receivers/soft_delete.py`:
```python
def _kolejkuj_pbn(instance, operacja):
    """Woła funkcję kolejkującą z fazy 05. Zwraca (wpis, status_str)."""
    from pbn_export_queue.operacje import (
        zakolejkuj_wycofanie,
        zakolejkuj_wysylke,
    )

    user = current_soft_delete_user()
    if operacja == "WYCOFANIE":
        wpis = zakolejkuj_wycofanie(instance, user=user)
        return wpis, ("WYCOFANIE" if wpis is not None else "")
    wpis = zakolejkuj_wysylke(instance, user=user)
    return wpis, ("WYSYLKA" if wpis is not None else "")


def on_post_soft_delete(sender, instance, **kwargs):
    wpis, status = _kolejkuj_pbn(instance, "WYCOFANIE")
    _utworz_log(
        instance,
        SoftDeleteLog.Akcja.DELETE,
        pbn_queue_entry=wpis,
        pbn_status=status,
    )


def on_post_restore(sender, instance, **kwargs):
    wpis, status = _kolejkuj_pbn(instance, "WYSYLKA")
    _utworz_log(
        instance,
        SoftDeleteLog.Akcja.RESTORE,
        pbn_queue_entry=wpis,
        pbn_status=status,
    )
```
- [ ] W `register()` dopisz `post_restore.connect(on_post_restore,
  dispatch_uid="bpp.soft_delete.post_restore")`.
- [ ] Import `post_restore` jest już w lokalnym imporcie `register()`.
**Step 4 — Run → PASS:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/test_receivers.py` → all passed.
- [ ] `ruff check src/bpp/receivers/soft_delete.py`
**Step 5 — Commit:**
- [ ] Commit: `feat(soft-delete): receivery kolejkują PBN (WYCOFANIE/WYSYLKA)`

---

### Task 7: Test integracyjny end-to-end + weryfikacja rejestracji w apps.ready

**Files:**
- Test: `src/bpp/tests/test_soft_delete/test_receivers.py` (dopisz)

**Step 1 — Failing test (lub regresyjny — guard rejestracji):**
- [ ] Dopisz test sprawdzający, że receivery są PODŁĄCZONE przez
  `apps.ready()` (nie tylko gdy test wywoła `register()` ręcznie):
```python
@pytest.mark.django_db
def test_receivery_zarejestrowane_przez_apps_ready():
    from django_softdelete.signals import (
        post_hard_delete,
        post_restore,
        post_soft_delete,
    )

    def _uids(sig):
        return {
            r[0][0]
            for r in sig.receivers
            if isinstance(r[0], tuple)
        }

    assert "bpp.soft_delete.post_soft_delete" in _uids(post_soft_delete)
    assert "bpp.soft_delete.post_restore" in _uids(post_restore)
    assert "bpp.soft_delete.post_hard_delete" in _uids(post_hard_delete)
```
> `Signal.receivers` to lista `((dispatch_uid, sender_id), ref)`. Sprawdź
> realny kształt przez `uv run python -c "..."` jeśli asercja nie trafia —
> dostosuj ekstrakcję uid. Cel: udowodnić, że `BppConfig.ready()` faktycznie
> woła `register()`.
**Step 2 — Run:**
- [ ] `uv run pytest "src/bpp/tests/test_soft_delete/test_receivers.py::test_receivery_zarejestrowane_przez_apps_ready"`
  — jeśli FAIL, popraw `register()`/`apps.py` lub ekstrakcję uid; jeśli PASS
  od razu (bo Task 3/4/6 już wpięły rejestrację) — to regresyjny strażnik.
**Step 3 — Implementation:**
- [ ] Jeśli test FAIL z powodu kształtu `receivers` — popraw asercję
  (NIE produkcję, chyba że rejestracja faktycznie brakuje).
**Step 4 — Run → PASS + cała faza:**
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/` → wszystkie zielone.
- [ ] `ruff check src/bpp/ src/pbn_export_queue/operacje.py`
- [ ] `ruff format --check src/bpp/models/soft_delete_log.py
  src/bpp/models/soft_delete_context.py src/bpp/receivers/soft_delete.py`
- [ ] `uv run python src/manage.py makemigrations --check --dry-run`
  → „No changes detected".
**Step 5 — Commit:**
- [ ] Commit: `test(soft-delete): e2e + guard rejestracji receiverów (apps.ready)`

---

## Definition of Done (faza 06)

- [ ] `SoftDeleteLog` (pola PINNED VERBATIM) + migracja; `makemigrations
  --check` czyste.
- [ ] `soft_delete_context` (thread-local CM) + akcesory; reentrancja OK.
- [ ] Trzy receivery (`post_soft_delete`→DELETE, `post_restore`→RESTORE,
  `post_hard_delete`→HARD_DELETE) zarejestrowane w `BppConfig.ready()`.
- [ ] DELETE publikacji z `pbn_uid` → log DELETE + `zakolejkuj_wycofanie` +
  `pbn_queue_entry` podpięty + `pbn_status="WYCOFANIE"`.
- [ ] RESTORE → log RESTORE + `zakolejkuj_wysylke` + `pbn_status="WYSYLKA"`.
- [ ] HARD_DELETE → log HARD_DELETE, bez PBN.
- [ ] User poprawnie z `soft_delete_context`; brak kontekstu → `user=None`,
  `powod=""`.
- [ ] Publikacja bez `pbn_uid` / `Autor` → log bez wpisu kolejki.
- [ ] `uv run pytest src/bpp/tests/test_soft_delete/` zielone; `ruff
  check`/`format` czyste; commit per task.

---

## Podsumowanie (3 punkty) + założenia

**1. Co robi ta faza.** Tworzy `SoftDeleteLog` (GFK + akcja + user + powód +
podpięcie do `PBN_Export_Queue` + status PBN) i trzy receivery sygnałów
pakietu `django-soft-delete`, zarejestrowane w jednym punkcie
(`BppConfig.ready()`). Atrybucję „kto" rozwiązuje thread-local context
manager `soft_delete_context(user=, reason=)` ustawiany w override
`delete()`/`restore()` (fazy 02/04) — sygnał pakietu usera nie niesie. Receiver
DELETE kolejkuje wycofanie z PBN, RESTORE — ponowną wysyłkę (gate `pbn_uid`).

**2. Kluczowe ustalenia z weryfikacji kodu.** (a) Sygnały mają RÓŻNE kwargs:
`post_soft_delete` niesie `using`, `post_restore` — `transaction_id`,
`post_hard_delete` — nic poza `instance`; stąd receivery używają
`**kwargs`. (b) `post_hard_delete` leci PO `Model.delete()` → `instance.pk`
może być `None` (uwaga w Tasku 3 — dostosować do faktu, nie zgadywać).
(c) `PBN_Export_Queue.zamowil` jest `NOT NULL` (`on_delete=CASCADE`) — operacje
systemowe bez usera to dług fazy 05 (oznaczone `TODO(faza 05)`). (d) Detekcja
publikacji = `getattr(instance, "pbn_uid_id", None)` (Autor/`*_Autor` nie mają
→ None → PBN pomijane).

**3. Kontrakt z reversion zachowany.** Jeden hook usera (`soft_delete_context`)
to dokładnie ten sam moment, w który przyszły `reversion.set_user` się wepnie;
receivery tylko czytają sygnały i tworzą wiersze logu — bez bulk-update, bez
omijania `post_save`.

**Założenia:** (i) **Faza 05 dostarcza** `zakolejkuj_wycofanie`/
`zakolejkuj_wysylke` w `src/pbn_export_queue/operacje.py` (sygnatury PINNED) —
jeśli jeszcze nie istnieją, Task 5 daje shim, który faza 05 nadpisze; jeśli
istnieją, Task 5 pomijamy. (ii) **Faza 02 wpina** `SoftDeleteModel` + override
owijający `soft_delete_context` na publikacjach — jeśli nie ma jeszcze tego
w worktree, testy receiverów Tasków 4/6 idą przez ręczny
`post_soft_delete.send(...)` w izolacji (wariant udokumentowany w docstringu
testu). (iii) Numer migracji `0421_*` orientacyjny — wykonawca nadaje kolejny
po sprawdzeniu `ls src/bpp/migrations/`. (iv) `soft_delete_context.py` tworzy
ta faza; gdy fazy 02/04 dodały wcześniej stub — scalić VERBATIM z kontraktem.

---

**Ścieżka tego planu:**
`/Users/mpasternak/Programowanie/bpp-soft-delete/docs/superpowers/plans/2026-06-04-soft-delete-06-softdeletelog.md`
`file:///Volumes/mpasternak/Programowanie/bpp-soft-delete/docs/superpowers/plans/2026-06-04-soft-delete-06-softdeletelog.md`
