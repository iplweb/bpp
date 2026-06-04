# Soft-delete — Faza 07: Admin superuser-only (kosz / przywróć / usuń trwale / powód)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dać superuserowi w adminie BPP odwracalny „kosz" dla 5 typów publikacji + `Autor`: „Usuń" = soft-delete (z powodem do `SoftDeleteLog`), filtr „Pokaż skasowane", akcja „Przywróć", osobna jawna akcja „Usuń trwale" (tylko superuser) — wszystko przez JEDEN punkt wstrzyknięcia `request.user`.

**Architecture:** Nowy mixin `BppSoftDeleteAdminMixin` w `src/bpp/admin/helpers/mixins.py` komponuje się PRZED istniejącymi klasami admina (`Wydawnictwo_CiagleAdmin`, `Wydawnictwo_ZwarteAdmin`, `Patent_Admin`, `Praca_DoktorskaAdmin`, `Praca_HabilitacyjnaAdmin`, `AutorAdmin`). Mixin: (a) `get_queryset()` → `global_objects` (otwieranie/przywracanie skasowanych); (b) jeden hook usera `_soft_delete_user_context(request)` ustawiający thread-local z fazy 06, używany przez `delete_model`/`delete_queryset`/akcje; (c) akcje `przywroc_zaznaczone`, `usun_trwale_zaznaczone` (superuser-only); (d) filtr `SoftDeleteFilter` (pakiet) → „Pokaż skasowane"; (e) pole „powód" przez intermediate-page (jak Django delete confirmation). NIE używamy `GlobalObjectsModelAdmin`/`SoftDeletedModelAdmin` z pakietu — wołają `obj.delete()` bez `user=` (łamią kontrakt jednego hooka).

**Tech Stack:** Django admin, `django-soft-delete>=1.0.23` (`global_objects`, `deleted_objects`, `SoftDeleteFilter`, `.delete()/.restore()/.hard_delete()`), pytest + model_bakery, `django.test.Client`.

**Zależy od:** faza 04 (guardy/PROTECT + `Autor` jest `SoftDeleteModel`), faza 06 (`delete(self, *args, user=None, reason="", **kwargs)` / `restore(self, *args, user=None, **kwargs)`, `SoftDeleteLog`, thread-local `set_soft_delete_user`/`get_soft_delete_user`).

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md) §6. Indeks: [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md).

---

## Reguły BPP (obowiązują w każdym kroku)

- Python wyłącznie przez `uv run` (`uv run pytest ...`). NIGDY gołe `python`/`pytest`.
- Max długość linii **88** znaków (ruff). Po implementacji `ruff format .` + `ruff check .` (ręcznie fixować, NIE `--fix`).
- Komentarze/komunikaty po polsku.
- Admin templates: **emoji**, NIE Foundation-Icons. (Etykiety akcji: „🗑️ Usuń do kosza", „♻️ Przywróć", „❌ Usuń trwale".)
- NIE modyfikować istniejących plików migracji.
- Komentarze Django `{# #}` — każda linia własne `{# ... #}`.

---

## Kontrakty z fazą 06 (PINNED — używaj VERBATIM)

Faza 06 dostarcza (zakładamy, że istnieją; jeśli nazwa się różni — to bug fazy 06, NIE zmieniaj go tutaj, zgłoś):

```python
# src/bpp/models/soft_delete.py  (thread-local hook usera, faza 06)
def set_soft_delete_user(user):
    """Ustawia użytkownika dla bieżącego wątku; czytany przez receivery
    sygnałów post_soft_delete/post_restore/post_hard_delete (faza 06)."""

def get_soft_delete_user():
    """Zwraca usera ustawionego przez set_soft_delete_user lub None."""

def clear_soft_delete_user():
    """Czyści thread-local (wołać w finally)."""
```

Sygnatury modeli (faza 06, na 5 publikacjach + `Autor`):
```python
def delete(self, *args, user=None, reason="", **kwargs): ...
def restore(self, *args, user=None, **kwargs): ...
def hard_delete(self, *args, user=None, reason="", **kwargs): ...
```

`SoftDeleteLog` (`src/bpp/models/soft_delete_log.py`) — pole `powod` (TextField), `user` (FK), zasilane przez receivery sygnałów. Admin **nie zapisuje** `SoftDeleteLog` bezpośrednio — tylko przekazuje `user`/`reason` do `model.delete(...)`, receiver robi resztę.

> **Jeden hook usera (kontrakt reversion #2).** Punkt wstrzyknięcia `request.user`
> to JEDNA metoda `BppSoftDeleteAdminMixin._soft_delete_user_context(request)`
> (context manager owijający thread-local). `delete_model`, `delete_queryset`,
> `przywroc_zaznaczone`, `usun_trwale_zaznaczone` — WSZYSTKIE wołają ten sam
> punkt. Reversion (odłożone) doczepi tu w przyszłości `reversion.set_user`.
> SZEW: w `_soft_delete_user_context` zostaw komentarz `# SZEW reversion`.

> **Świadomość recover (kontrakt reversion #3).** Reversion „recover deleted"
> (odłożone) wskrzeszałby rekord poza przepływem soft-delete (bez `WYSYLKA`,
> bez `SoftDeleteLog`, łamiąc warunkowy unique `slug`). SZEW: w mixinie
> `get_urls()` zostaw komentarz, że recover-URL reversion ma być tu w
> przyszłości ukryty/przekierowany na `restore()`.

---

## Stan zastany (zweryfikowany w kodzie — nie zgaduj)

- **Wszystkie 5 adminów publikacji dziedziczą finalnie po `admin.ModelAdmin`:**
  - `Wydawnictwo_CiagleAdmin` (`src/bpp/admin/wydawnictwo_ciagle.py:262`) — wprost `..., RestrictDeletionWhenPBNUIDSetMixin, admin.ModelAdmin`.
  - `Wydawnictwo_ZwarteAdmin` (`wydawnictwo_zwarte.py:438`) → `Wydawnictwo_ZwarteAdmin_Baza` (`:76` `BaseBppAdminMixin, admin.ModelAdmin`).
  - `Patent_Admin` (`patent.py:83`) → `Wydawnictwo_ZwarteAdmin_Baza`.
  - `Praca_DoktorskaAdmin` (`praca_doktorska.py:197`) → `Praca_Doktorska_Habilitacyjna_Admin_Base` (`:57` `AdnotacjeZDatamiMixin, BaseBppAdminMixin, admin.ModelAdmin`).
  - `Praca_HabilitacyjnaAdmin` (`praca_habilitacyjna.py:172`) → ten sam base.
  - `AutorAdmin` (`autor.py:192`) — wprost `..., BaseBppAdminMixin, DynamicColumnsMixin, admin.ModelAdmin`.
- **`RestrictDeletionWhenPBNUIDSetMixin`** (`helpers/mixins.py:87`) nadpisuje `has_delete_permission`: zwraca `False` gdy `obj.pbn_uid_id is not None`. Jest na `Wydawnictwo_Ciagle/Zwarte`. **UWAGA MRO:** nasz mixin musi stać PRZED nim, ale `has_delete_permission` ma wołać `super()` — to znaczy, że dla rekordu z PBN superuser nadal nie usunie (zgodne ze spec — soft-delete z `pbn_uid` to osobny, wrażliwy przypadek; obrona PBN zostaje). Soft-delete rekordu z `pbn_uid` realizujemy mimo to, bo `has_soft_delete_permission` (nasza) jest niezależna od `has_delete_permission`. Patrz Task 4 — rozdzielamy uprawnienia.
- **Pakiet `django_softdelete.admin`** (`.venv/.../django_softdelete/admin.py`): `GlobalObjectsModelAdmin.get_queryset` → `global_objects`; `SoftDeleteFilter` (param `is_deleted`, lookupy `true`/`false`). Akcje pakietu (`soft_delete_selected`, `hard_delete_selected`, `restore_selected`) wołają `obj.delete()`/`queryset.restore()` **bez `user=`** → NIE używamy ich (łamią jeden-hook). `SoftDeleteFilter.queryset` filtruje po `deleted_at__isnull`.
- **Fixtures (`src/conftest.py`):** `superuser` (`:172`, `create_superuser`, login `user`/`foo`), `superuser_client` (`:191`), `test_user` (`:162`, zwykły user — **NIE staff**), `client` (pytest-django). Brak gotowego „staff-not-superuser" — **dodajemy** w Task 8.
- **Wzorce superuser-only:** `oplaty_log.py:58-65` (`has_*_permission` → `False`), `__init__.py:265` (`has_delete_permission` z logiką), `uczelnia.py:31`.

---

## File Structure

**Modyfikowane:**
- `src/bpp/admin/helpers/mixins.py` — NOWY `BppSoftDeleteAdminMixin` + formularz `PowodSoftDeleteForm` (intermediate page).
- `src/bpp/admin/wydawnictwo_ciagle.py:262` — wpięcie mixinu w `Wydawnictwo_CiagleAdmin`.
- `src/bpp/admin/wydawnictwo_zwarte.py:438` — wpięcie w `Wydawnictwo_ZwarteAdmin`.
- `src/bpp/admin/patent.py:83` — wpięcie w `Patent_Admin`.
- `src/bpp/admin/praca_doktorska.py:197` — wpięcie w `Praca_DoktorskaAdmin`.
- `src/bpp/admin/praca_habilitacyjna.py:172` — wpięcie w `Praca_HabilitacyjnaAdmin`.
- `src/bpp/admin/autor.py:192` — wpięcie w `AutorAdmin`.

**Tworzone:**
- `templates/admin/bpp/soft_delete_powod.html` — intermediate page „podaj powód" (emoji).
- `src/bpp/tests/test_admin_soft_delete.py` — testy fazy.
- (Task 8) fixture `staff_user` / `staff_client` w `src/conftest.py` jeśli nie istnieje.

> **Decyzja: jeden mixin, sześć adminów.** Mixin nie zna konkretnego modelu —
> używa `self.model.global_objects` / `self.model.deleted_objects`. Działa dla
> publikacji i `Autor` identycznie. `Autor.delete()` z guardem (faza 04) rzuca
> `ProtectedError` gdy ma prace → mixin łapie i pokazuje komunikat (Task 7).

---

## Task 1: Mixin szkielet + `get_queryset` → `global_objects` + filtr „Pokaż skasowane"

**Files:**
- Modify: `src/bpp/admin/helpers/mixins.py` (dopisz na końcu).
- Test: `src/bpp/tests/test_admin_soft_delete.py` (utwórz).

- [ ] **Step 1: Write the failing test**

```python
# src/bpp/tests/test_admin_soft_delete.py
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_changelist_pokazuje_nieskasowane_domyslnie(superuser_client):
    żywy = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(user=None, reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url)
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Żywa praca" in content
    # global_objects pozwala otworzyć skasowany rekord po ID, ale changelist
    # domyślnie filtruje (SoftDeleteFilter default = nieskasowane):
    assert "Praca w koszu" not in content
    assert żywy.pk is not None


@pytest.mark.django_db
def test_filtr_pokaz_skasowane_pokazuje_kosz(superuser_client):
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Żywa praca")
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(user=None, reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.get(url, {"is_deleted": "true"})
    content = resp.content.decode("utf-8")

    assert resp.status_code == 200
    assert "Praca w koszu" in content


@pytest.mark.django_db
def test_changeform_otwiera_skasowany_rekord(superuser_client):
    skasowany = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca w koszu")
    skasowany.delete(user=None, reason="test")

    url = reverse(
        "admin:bpp_wydawnictwo_ciagle_change", args=[skasowany.pk]
    )
    resp = superuser_client.get(url)
    # get_queryset = global_objects → da się otworzyć skasowany rekord:
    assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py -v`
Expected: FAIL — `test_filtr_pokaz_skasowane_pokazuje_kosz` i `test_changeform_otwiera_skasowany_rekord` padają (domyślny `objects` ukrywa skasowane, brak filtra `is_deleted`).

- [ ] **Step 3: Write minimal implementation — mixin szkielet w `helpers/mixins.py`**

Dopisz na końcu `src/bpp/admin/helpers/mixins.py`:

```python
from django.contrib import admin, messages  # noqa: E402  (na górze pliku)
from django.db.models import ProtectedError  # noqa: E402
from django_softdelete.filters import SoftDeleteFilter  # noqa: E402


class BppSoftDeleteAdminMixin:
    """Admin superuser-only dla modeli SoftDeleteModel (5 publikacji + Autor).

    Zapewnia:
    - get_queryset -> global_objects (otwieranie/przywracanie skasowanych),
    - filtr "Pokaż skasowane" (SoftDeleteFilter, param is_deleted),
    - JEDEN hook usera (_soft_delete_user_context) dla delete/restore/hard,
    - akcje "Przywróć" i "Usuń trwale" (ta druga superuser-only).

    Komponuj PRZED istniejącymi klasami admina (przed admin.ModelAdmin).
    """

    def get_queryset(self, request):
        # global_objects: zawiera skasowane, żeby dało się je otworzyć
        # i przywrócić. SoftDeleteFilter (default) i tak ukrywa kosz na
        # liście, póki użytkownik nie wybierze "Pokaż skasowane".
        qs = self.model.global_objects.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_list_filter(self, request):
        list_filter = super().get_list_filter(request) or []
        list_filter = list(list_filter)
        if SoftDeleteFilter not in list_filter:
            list_filter = [SoftDeleteFilter] + list_filter
        return list_filter
```

> Uwaga: `SoftDeleteFilter.queryset` traktuje brak parametru (`None`) jak
> `'all'`... a faktycznie zwraca `'ALL'` tylko dla `'all'`; dla `None` mapuje
> na `'all'` → `'ALL'` → zwraca cały queryset. To znaczy: **bez parametru
> pokazuje wszystko** (żywe + kosz). Spec wymaga „domyślnie ukryj kosz".
> Dlatego w Step 5 nadpisujemy zachowanie własnym filtrem (Task 1b).

- [ ] **Step 4: Run partial — sprawdź changeform i filtr**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_changeform_otwiera_skasowany_rekord -v`
Expected: PASS (po dodaniu `get_queryset` — ale dopiero gdy mixin wpięty; jeśli jeszcze nie wpięty do `Wydawnictwo_CiagleAdmin`, to nadal FAIL — wpinamy w Task 4). Tymczasowo: dopnij mixin do `Wydawnictwo_CiagleAdmin` na czas tego testu **albo** wykonaj Task 4 przed re-runem. **Decyzja porządkująca:** wpięcie do `Wydawnictwo_CiagleAdmin` robimy już teraz minimalnie (jedna linia + import), pełne 6 adminów w Task 4.

Minimalne wpięcie teraz — `src/bpp/admin/wydawnictwo_ciagle.py`:
```python
from .helpers.mixins import (  # dołącz do istniejącego importu z .helpers.mixins
    BppSoftDeleteAdminMixin,
    OptionalPBNSaveMixin,
    RestrictDeletionWhenPBNUIDSetMixin,
)
```
```python
class Wydawnictwo_CiagleAdmin(
    BppSoftDeleteAdminMixin,  # <-- PIERWSZY
    ConstanceScoringFieldsMixin,
    # ... reszta bez zmian ...
    RestrictDeletionWhenPBNUIDSetMixin,
    admin.ModelAdmin,
):
```

- [ ] **Step 5: Własny filtr „Pokaż skasowane" z domyślnym ukrywaniem kosza (Task 1b)**

Dopisz w `helpers/mixins.py` PRZED `BppSoftDeleteAdminMixin` i podmień w `get_list_filter`:

```python
class PokazSkasowaneFilter(SoftDeleteFilter):
    """Jak SoftDeleteFilter, ale DOMYŚLNIE (brak parametru) ukrywa kosz.

    Pakietowy SoftDeleteFilter bez parametru pokazuje wszystko; spec wymaga,
    by changelist domyślnie pokazywał tylko żywe rekordy.
    """

    title = "Stan (kosz)"

    def lookups(self, request, model_admin):
        return (
            ("false", "🗑️ Tylko skasowane"),
            ("all", "Wszystkie (z koszem)"),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value is None:
            # Domyślnie: tylko żywe.
            return queryset.filter(deleted_at__isnull=True)
        if value == "all":
            return queryset
        if value == "false":
            # Etykieta "Tylko skasowane" -> deleted_at NOT NULL.
            return queryset.filter(deleted_at__isnull=False)
        return queryset
```

> **Uwaga na semantykę pakietu:** w pakietowym `SoftDeleteFilter` lookup
> `'true'`→"Deleted Softly" mapuje przez `{'true': False}` na
> `deleted_at__isnull=False`. Mylące. Dlatego pełnym własnym filtrem
> `PokazSkasowaneFilter` (powyżej) jawnie sterujemy: `value="false"` w naszym
> filtrze = pokaż kosz. Test używa `is_deleted=true`? — NIE. Poprawiamy test
> w Step 6, żeby używał naszego kontraktu.

Podmień w `BppSoftDeleteAdminMixin.get_list_filter`: `SoftDeleteFilter` → `PokazSkasowaneFilter`.

- [ ] **Step 6: Popraw test filtra na nasz kontrakt parametru**

W `test_filtr_pokaz_skasowane_pokazuje_kosz` zamień `{"is_deleted": "true"}` na `{"is_deleted": "false"}` (etykieta „🗑️ Tylko skasowane"). Param `is_deleted` zachowany (dziedziczony `parameter_name`).

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py -v`
Expected: PASS (3 testy).

- [ ] **Step 8: Lint**

Run: `uv run ruff format src/bpp/admin/helpers/mixins.py src/bpp/admin/wydawnictwo_ciagle.py src/bpp/tests/test_admin_soft_delete.py && uv run ruff check src/bpp/admin/helpers/mixins.py src/bpp/admin/wydawnictwo_ciagle.py src/bpp/tests/test_admin_soft_delete.py`
Expected: brak błędów (przenieś importy z `noqa: E402` na górę pliku `mixins.py`; usuń `noqa` po przeniesieniu).

- [ ] **Step 9: Commit**

```bash
git add src/bpp/admin/helpers/mixins.py src/bpp/admin/wydawnictwo_ciagle.py \
    src/bpp/tests/test_admin_soft_delete.py
git commit -m "feat(soft-delete): admin mixin get_queryset global_objects + filtr kosza"
```

---

## Task 2: Jeden hook usera — `_soft_delete_user_context` + `delete_model`/`delete_queryset` = soft-delete

**Files:**
- Modify: `src/bpp/admin/helpers/mixins.py` (`BppSoftDeleteAdminMixin`).
- Test: `src/bpp/tests/test_admin_soft_delete.py`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_delete_w_adminie_soft_deletuje_i_zapisuje_usera(superuser, superuser_client):
    from bpp.models import SoftDeleteLog

    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Do kosza")
    pk = obj.pk
    url = reverse("admin:bpp_wydawnictwo_ciagle_delete", args=[pk])

    # GET = strona potwierdzenia
    resp_get = superuser_client.get(url)
    assert resp_get.status_code == 200

    # POST = wykonaj soft-delete (Django delete confirmation: post=yes)
    resp = superuser_client.post(url, {"post": "yes"})
    assert resp.status_code == 302

    # Zniknął z objects, jest w global_objects z deleted_at:
    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    g = Wydawnictwo_Ciagle.global_objects.get(pk=pk)
    assert g.deleted_at is not None

    # SoftDeleteLog (faza 06 receiver) ma usera = superuser:
    log = SoftDeleteLog.objects.filter(object_id=pk).latest("timestamp")
    assert log.user_id == superuser.pk
    assert log.akcja == "delete"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_delete_w_adminie_soft_deletuje_i_zapisuje_usera -v`
Expected: FAIL — domyślny `delete_model` robi hard-delete (rekord znika z `global_objects`) i `log.user_id` to `None` (brak hooka).

- [ ] **Step 3: Write implementation — hook usera + delete_model/delete_queryset**

Dopisz import na górze `helpers/mixins.py`:
```python
from contextlib import contextmanager

from bpp.models.soft_delete import (
    clear_soft_delete_user,
    set_soft_delete_user,
)
```

W `BppSoftDeleteAdminMixin`:
```python
    @contextmanager
    def _soft_delete_user_context(self, request):
        """JEDEN punkt wstrzyknięcia request.user dla całego przepływu
        soft-delete/restore/hard-delete w adminie.

        Ustawia thread-local (faza 06) czytany przez receivery sygnałów,
        które zapisują SoftDeleteLog.user. To samo miejsce w przyszłości
        zasili reversion.set_user.
        """
        set_soft_delete_user(request.user)
        # SZEW reversion: tu w przyszłości reversion.set_user(request.user)
        # (django-reversion, odłożone — patrz overview "Kontrakty z reversion").
        try:
            yield
        finally:
            clear_soft_delete_user()

    def _powod_z_requestu(self, request):
        """Powód kasowania z intermediate-page (Task 5). Domyślnie pusty."""
        return request.POST.get("powod", "")

    def delete_model(self, request, obj):
        # "Usuń" w adminie = soft-delete (kosz), NIE hard-delete.
        with self._soft_delete_user_context(request):
            obj.delete(user=request.user, reason=self._powod_z_requestu(request))

    def delete_queryset(self, request, queryset):
        # Akcja "delete_selected" przechodzi tędy: per-instancja soft-delete.
        with self._soft_delete_user_context(request):
            powod = self._powod_z_requestu(request)
            for obj in queryset:
                obj.delete(user=request.user, reason=powod)
```

> **Dlaczego per-instancja w `delete_queryset`?** Kontrakt reversion #1 +
> kaskada `*_Autor` (faza 02) + `SoftDeleteLog` wymagają `post_save`/sygnałów
> per obiekt. `BppSoftDeleteQuerySet.update()` (faza 01) i tak blokuje bulk
> ustawienie `deleted_at`. NIE wołaj `queryset.delete()` zbiorczo bez usera.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_delete_w_adminie_soft_deletuje_i_zapisuje_usera -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
uv run ruff check src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
git add src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
git commit -m "feat(soft-delete): jeden hook usera + delete_model/delete_queryset = kosz"
```

---

## Task 3: Akcja „Przywróć" (restore) przez ten sam hook usera

**Files:**
- Modify: `src/bpp/admin/helpers/mixins.py` (`BppSoftDeleteAdminMixin`).
- Test: `src/bpp/tests/test_admin_soft_delete.py`.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_akcja_przywroc_dziala_i_zapisuje_usera(superuser, superuser_client):
    from bpp.models import SoftDeleteLog

    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Wraca z kosza")
    pk = obj.pk
    obj.delete(user=None, reason="test")
    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    resp = superuser_client.post(
        url,
        {
            "action": "przywroc_zaznaczone",
            "_selected_action": [str(pk)],
        },
    )
    assert resp.status_code in (200, 302)

    # Wrócił do objects, deleted_at = NULL:
    assert Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    g = Wydawnictwo_Ciagle.global_objects.get(pk=pk)
    assert g.deleted_at is None

    log = SoftDeleteLog.objects.filter(object_id=pk, akcja="restore").latest(
        "timestamp"
    )
    assert log.user_id == superuser.pk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_akcja_przywroc_dziala_i_zapisuje_usera -v`
Expected: FAIL — akcja `przywroc_zaznaczone` nie istnieje (`'przywroc_zaznaczone' is not a registered action`).

- [ ] **Step 3: Write implementation — akcja restore**

W `BppSoftDeleteAdminMixin` dopisz akcję i zarejestruj ją w `get_actions`:

```python
    @admin.action(description="♻️ Przywróć zaznaczone (z kosza)")
    def przywroc_zaznaczone(self, request, queryset):
        # queryset z global_objects może zawierać też nieskasowane — restore
        # nieskasowanego jest no-op po stronie pakietu, więc bezpieczne.
        with self._soft_delete_user_context(request):
            przywrocono = 0
            for obj in queryset:
                if obj.deleted_at is not None:
                    obj.restore(user=request.user)
                    przywrocono += 1
        self.message_user(
            request,
            f"Przywrócono z kosza: {przywrocono}.",
            level=messages.SUCCESS,
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions["przywroc_zaznaczone"] = self.get_action("przywroc_zaznaczone")
        return actions
```

> `self.get_action(name)` zwraca krotkę `(func, name, description)` wymaganą
> przez Django dla `get_actions`. Działa, bo `przywroc_zaznaczone` jest metodą
> klasy z dekoratorem `@admin.action`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_akcja_przywroc_dziala_i_zapisuje_usera -v`
Expected: PASS.

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
uv run ruff check src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
git add src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
git commit -m "feat(soft-delete): akcja admina Przywróć przez jeden hook usera"
```

---

## Task 4: Akcja „Usuń trwale" (hard_delete) — TYLKO superuser

**Files:**
- Modify: `src/bpp/admin/helpers/mixins.py` (`BppSoftDeleteAdminMixin`).
- Test: `src/bpp/tests/test_admin_soft_delete.py`.

- [ ] **Step 1: Write the failing test (superuser może; staff dostaje odmowę)**

```python
@pytest.mark.django_db
def test_usun_trwale_dostepne_dla_superusera(superuser, superuser_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Do trwałego usunięcia")
    pk = obj.pk
    obj.delete(user=None, reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    # Akcja widoczna dla superusera:
    resp_list = superuser_client.get(url, {"is_deleted": "false"})
    assert b"usun_trwale_zaznaczone" in resp_list.content

    resp = superuser_client.post(
        url,
        {
            "action": "usun_trwale_zaznaczone",
            "_selected_action": [str(pk)],
        },
    )
    assert resp.status_code in (200, 302)
    # Zniknął z global_objects (hard-delete):
    assert not Wydawnictwo_Ciagle.global_objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_usun_trwale_niedostepne_dla_staff(staff_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Próba przez staff")
    pk = obj.pk
    obj.delete(user=None, reason="test")

    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")
    # Akcja NIE jest oferowana staffowi:
    resp_list = staff_client.get(url, {"is_deleted": "false"})
    assert b"usun_trwale_zaznaczone" not in resp_list.content

    # Nawet wymuszony POST nie usuwa trwale:
    resp = staff_client.post(
        url,
        {
            "action": "usun_trwale_zaznaczone",
            "_selected_action": [str(pk)],
        },
    )
    # Django odrzuca nieznaną/niedozwoloną akcję (brak na liście get_actions):
    assert resp.status_code in (200, 302, 403)
    assert Wydawnictwo_Ciagle.global_objects.filter(pk=pk).exists()
```

> Fixture `staff_client` dodajemy w Task 8 (Step 0 poniżej najpierw upewnij się,
> że istnieje — jeśli nie, Task 8 musi iść PRZED tym testem; w praktyce dodaj
> fixture teraz w `conftest.py`, bo Task 4 go potrzebuje).

- [ ] **Step 2: Dodaj fixture `staff_user`/`staff_client` (jeśli brak)**

W `src/conftest.py` (po `superuser_client`, `:196`):

```python
@pytest.fixture
def staff_user(db):
    """Staff (dostęp do admina), ale NIE superuser."""
    u = User.objects.create_user(
        username="staff",
        password="staffpass",
        email="staff@example.com",
    )
    u.is_staff = True
    u.save()
    return u


@pytest.fixture
def staff_client(client, staff_user):
    """Zalogowany staff (nie-superuser)."""
    if not client.login(username="staff", password="staffpass"):
        raise Exception("Cannot login staff")
    return client
```

> Staff bez `is_superuser` i bez uprawnień modelowych nie zobaczy changelisty
> w ogóle (403/redirect). Aby test sprawdzał *akcję* a nie brak dostępu, nadaj
> staffowi uprawnienia do modelu w fixture lub w teście. Dopisz w `staff_user`:
> ```python
> from django.contrib.auth.models import Permission
> u.user_permissions.add(
>     *Permission.objects.filter(
>         content_type__app_label="bpp",
>         content_type__model="wydawnictwo_ciagle",
>     )
> )
> ```
> (zapewnia `view/change/delete` na `wydawnictwo_ciagle`, więc changelist się
> renderuje, ale `usun_trwale_zaznaczone` jest superuser-only przez `get_actions`).

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_usun_trwale_dostepne_dla_superusera src/bpp/tests/test_admin_soft_delete.py::test_usun_trwale_niedostepne_dla_staff -v`
Expected: FAIL — akcja `usun_trwale_zaznaczone` nie istnieje.

- [ ] **Step 4: Write implementation — akcja hard-delete superuser-only**

W `BppSoftDeleteAdminMixin`:

```python
    @admin.action(description="❌ Usuń TRWALE (nieodwracalnie, tylko superuser)")
    def usun_trwale_zaznaczone(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Trwałe usuwanie jest dostępne wyłącznie dla superużytkownika.",
                level=messages.ERROR,
            )
            return
        with self._soft_delete_user_context(request):
            powod = self._powod_z_requestu(request)
            usunieto = 0
            for obj in queryset:
                obj.hard_delete(user=request.user, reason=powod)
                usunieto += 1
        self.message_user(
            request,
            f"Usunięto trwale: {usunieto}.",
            level=messages.SUCCESS,
        )
```

Rozszerz `get_actions` (z Task 3) — dodaj akcję hard-delete TYLKO dla superusera:

```python
    def get_actions(self, request):
        actions = super().get_actions(request)
        actions["przywroc_zaznaczone"] = self.get_action("przywroc_zaznaczone")
        if request.user.is_superuser:
            actions["usun_trwale_zaznaczone"] = self.get_action(
                "usun_trwale_zaznaczone"
            )
        else:
            # Staff nie dostaje ani trwałego usuwania, ani domyślnego
            # delete_selected (które i tak idzie przez nasz soft-delete).
            actions.pop("usun_trwale_zaznaczone", None)
        return actions
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py -v`
Expected: PASS (wszystkie dotychczasowe).

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff format src/bpp/admin/helpers/mixins.py src/conftest.py \
    src/bpp/tests/test_admin_soft_delete.py
uv run ruff check src/bpp/admin/helpers/mixins.py src/conftest.py \
    src/bpp/tests/test_admin_soft_delete.py
git add src/bpp/admin/helpers/mixins.py src/conftest.py \
    src/bpp/tests/test_admin_soft_delete.py
git commit -m "feat(soft-delete): akcja Usuń trwale superuser-only + fixture staff"
```

---

## Task 5: Pole „powód" przy kasowaniu — intermediate page → `SoftDeleteLog.powod`

**Files:**
- Modify: `src/bpp/admin/helpers/mixins.py` (formularz + nadpisany przepływ delete).
- Create: `templates/admin/bpp/soft_delete_powod.html`.
- Test: `src/bpp/tests/test_admin_soft_delete.py`.

> **Decyzja UX.** Pojedynczy „Usuń" (changeform delete) i akcja zbiorcza
> „delete_selected" przechodzą przez stronę pośrednią pytającą o powód. Powód
> ląduje w `SoftDeleteLog.powod` (przez `reason=` → receiver fazy 06). Aby nie
> przepisywać całego Django delete-confirmation, dla pojedynczego rekordu
> czytamy `powod` z POST formularza potwierdzenia (Django renderuje własny
> `delete_confirmation.html`). Najprościej: własna akcja `usun_do_kosza` z
> intermediate page (analogicznie do pakietowego wzorca), a domyślne
> `delete_selected`/`delete_model` zostają jako soft-delete bez wymuszonego
> powodu (powód opcjonalny).

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_akcja_usun_do_kosza_z_powodem_trafia_do_logu(superuser, superuser_client):
    from bpp.models import SoftDeleteLog

    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Z powodem")
    pk = obj.pk
    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")

    # Krok 1: wybór akcji bez 'powod_potwierdzony' -> intermediate page:
    resp1 = superuser_client.post(
        url,
        {
            "action": "usun_do_kosza",
            "_selected_action": [str(pk)],
        },
    )
    assert resp1.status_code == 200
    assert b"powod" in resp1.content  # formularz z polem powodu

    # Krok 2: potwierdzenie z powodem:
    resp2 = superuser_client.post(
        url,
        {
            "action": "usun_do_kosza",
            "_selected_action": [str(pk)],
            "powod_potwierdzony": "1",
            "powod": "Duplikat rekordu",
        },
    )
    assert resp2.status_code in (200, 302)

    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    log = SoftDeleteLog.objects.filter(object_id=pk, akcja="delete").latest(
        "timestamp"
    )
    assert log.powod == "Duplikat rekordu"
    assert log.user_id == superuser.pk
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_akcja_usun_do_kosza_z_powodem_trafia_do_logu -v`
Expected: FAIL — brak akcji `usun_do_kosza` / brak template.

- [ ] **Step 3: Write template**

`templates/admin/bpp/soft_delete_powod.html`:

```django
{% extends "admin/base_site.html" %}
{% load i18n admin_urls %}

{% block content %}
{# Strona pośrednia: podaj powód usunięcia do kosza. #}
<p>🗑️ Zaznaczone rekordy zostaną przeniesione do kosza (soft-delete).</p>
<p>Operacja jest odwracalna (akcja „♻️ Przywróć").</p>

<ul>
  {% for obj in obiekty %}
    <li>{{ obj }}</li>
  {% endfor %}
</ul>

<form method="post">{% csrf_token %}
  {% for pk in wybrane_pk %}
    <input type="hidden" name="_selected_action" value="{{ pk }}">
  {% endfor %}
  <input type="hidden" name="action" value="usun_do_kosza">
  <input type="hidden" name="powod_potwierdzony" value="1">

  <p>
    <label for="id_powod">Powód usunięcia (trafi do dziennika):</label><br>
    <textarea name="powod" id="id_powod" rows="3" cols="60"></textarea>
  </p>

  <input type="submit" value="🗑️ Przenieś do kosza">
  <a href="{% url opts|admin_urlname:'changelist' %}">Anuluj</a>
</form>
{% endblock %}
```

- [ ] **Step 4: Write implementation — akcja `usun_do_kosza` z intermediate page**

W `helpers/mixins.py` dodaj import:
```python
from django.contrib.admin import helpers as admin_helpers
from django.template.response import TemplateResponse
```

W `BppSoftDeleteAdminMixin`:

```python
    @admin.action(description="🗑️ Usuń do kosza (z powodem)")
    def usun_do_kosza(self, request, queryset):
        if request.POST.get("powod_potwierdzony"):
            with self._soft_delete_user_context(request):
                powod = request.POST.get("powod", "")
                usunieto = 0
                for obj in queryset:
                    obj.delete(user=request.user, reason=powod)
                    usunieto += 1
            self.message_user(
                request,
                f"Przeniesiono do kosza: {usunieto}.",
                level=messages.SUCCESS,
            )
            return None

        # Pierwszy krok: strona pośrednia z polem 'powod'.
        context = {
            **self.admin_site.each_context(request),
            "title": "Usuń do kosza",
            "obiekty": list(queryset),
            "wybrane_pk": [str(o.pk) for o in queryset],
            "opts": self.model._meta,
            "action_checkbox_name": admin_helpers.ACTION_CHECKBOX_NAME,
        }
        return TemplateResponse(
            request, "admin/bpp/soft_delete_powod.html", context
        )
```

Dodaj do `get_actions` (rozszerz istniejące):
```python
        actions["usun_do_kosza"] = self.get_action("usun_do_kosza")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_akcja_usun_do_kosza_z_powodem_trafia_do_logu -v`
Expected: PASS.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff format src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
uv run ruff check src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
git add src/bpp/admin/helpers/mixins.py templates/admin/bpp/soft_delete_powod.html \
    src/bpp/tests/test_admin_soft_delete.py
git commit -m "feat(soft-delete): akcja Usuń do kosza z powodem -> SoftDeleteLog"
```

---

## Task 6: Wpięcie mixinu do pozostałych 5 adminów (MRO) + recover-szew

**Files:**
- Modify: `src/bpp/admin/wydawnictwo_zwarte.py:438`, `patent.py:83`, `praca_doktorska.py:197`, `praca_habilitacyjna.py:172`, `autor.py:192`.
- Modify: `src/bpp/admin/helpers/mixins.py` (`get_urls` szew recover).
- Test: `src/bpp/tests/test_admin_soft_delete.py`.

> **MRO — reguła:** `BppSoftDeleteAdminMixin` jest **PIERWSZY** na liście baz
> każdego admina, żeby jego `get_queryset`/`get_actions`/`delete_model`/
> `get_list_filter` wygrywały. Wszystkie 6 adminów kończą się na
> `admin.ModelAdmin` (bezpośrednio lub przez `Wydawnictwo_ZwarteAdmin_Baza` /
> `Praca_Doktorska_Habilitacyjna_Admin_Base`), więc `super()` w naszych
> metodach trafia poprawnie w łańcuch i finalnie w `ModelAdmin`. Mixin nie
> definiuje `__init__` ani `Meta`, więc nie psuje istniejących mixinów.

- [ ] **Step 1: Write the failing test (parametryzowany po 5 pozostałych modelach)**

```python
import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Zwarte,
)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,admin_slug",
    [
        (Wydawnictwo_Zwarte, "wydawnictwo_zwarte"),
        (Patent, "patent"),
        (Praca_Doktorska, "praca_doktorska"),
        (Praca_Habilitacyjna, "praca_habilitacyjna"),
        (Autor, "autor"),
    ],
)
def test_soft_delete_w_adminie_dla_kazdego_modelu(
    model, admin_slug, superuser, superuser_client
):
    obj = baker.make(model)
    pk = obj.pk
    obj.delete(user=None, reason="test")

    # Changeform otwiera skasowany (global_objects):
    url_change = reverse(f"admin:bpp_{admin_slug}_change", args=[pk])
    assert superuser_client.get(url_change).status_code == 200

    # Filtr kosza pokazuje skasowany:
    url_list = reverse(f"admin:bpp_{admin_slug}_changelist")
    resp = superuser_client.get(url_list, {"is_deleted": "false"})
    assert resp.status_code == 200

    # Restore działa:
    resp_r = superuser_client.post(
        url_list,
        {"action": "przywroc_zaznaczone", "_selected_action": [str(pk)]},
    )
    assert resp_r.status_code in (200, 302)
    assert model.objects.filter(pk=pk).exists()
```

> `baker.make(Autor)` daje autora **bez prac** → soft-delete dozwolony (guard
> fazy 04 nie blokuje). Test guarda autora-z-pracami jest w Task 7.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest "src/bpp/tests/test_admin_soft_delete.py::test_soft_delete_w_adminie_dla_kazdego_modelu" -v`
Expected: FAIL — pozostałe 5 adminów nie mają mixinu (`change` na skasowanym → 404, brak akcji `przywroc_zaznaczone`).

- [ ] **Step 3: Wpięcie mixinu — `wydawnictwo_zwarte.py`**

```python
from .helpers.mixins import (
    BppSoftDeleteAdminMixin,
    OptionalPBNSaveMixin,
    RestrictDeletionWhenPBNUIDSetMixin,
)
```
```python
class Wydawnictwo_ZwarteAdmin(
    BppSoftDeleteAdminMixin,  # <-- PIERWSZY
    ConstanceScoringFieldsMixin,
    # ... reszta bez zmian ...
    RestrictDeletionWhenPBNUIDSetMixin,
    Wydawnictwo_ZwarteAdmin_Baza,
):
```

- [ ] **Step 4: Wpięcie — `patent.py`**

```python
from .helpers.mixins import BppSoftDeleteAdminMixin
```
```python
class Patent_Admin(
    BppSoftDeleteAdminMixin,  # <-- PIERWSZY
    ConstanceScoringFieldsMixin,
    AdnotacjeZDatamiMixin,
    EksportDanychZFormatowanieMixin,
    ExportActionsMixin,
    Wydawnictwo_ZwarteAdmin_Baza,
):
```

- [ ] **Step 5: Wpięcie — `praca_doktorska.py`**

```python
from .helpers.mixins import (
    BppSoftDeleteAdminMixin,
    DomyslnyStatusKorektyMixin,
    Wycinaj_W_z_InformacjiMixin,
)
```
```python
class Praca_DoktorskaAdmin(
    BppSoftDeleteAdminMixin,  # <-- PIERWSZY
    ConstanceScoringFieldsMixin,
    EksportDanychZFormatowanieMixin,
    ExportActionsMixin,
    Praca_Doktorska_Habilitacyjna_Admin_Base,
):
```

- [ ] **Step 6: Wpięcie — `praca_habilitacyjna.py`**

```python
from .helpers.mixins import (
    BppSoftDeleteAdminMixin,
    DomyslnyStatusKorektyMixin,
    Wycinaj_W_z_InformacjiMixin,
)
```
```python
class Praca_HabilitacyjnaAdmin(
    BppSoftDeleteAdminMixin,  # <-- PIERWSZY
    ConstanceScoringFieldsMixin,
    EksportDanychZFormatowanieMixin,
    ExportActionsMixin,
    Praca_Doktorska_Habilitacyjna_Admin_Base,
):
```

- [ ] **Step 7: Wpięcie — `autor.py`**

```python
from .core import BaseBppAdminMixin
from .helpers.mixins import BppSoftDeleteAdminMixin
```
```python
class AutorAdmin(
    BppSoftDeleteAdminMixin,  # <-- PIERWSZY
    DjangoQLSearchMixin,
    ZapiszZAdnotacjaMixin,
    EksportDanychMixin,
    BaseBppAdminMixin,
    DynamicColumnsMixin,
    admin.ModelAdmin,
):
```

> `AutorAdmin.get_actions` (`autor.py:475`) nadpisuje `get_actions` i zmienia
> opis `delete_selected`. Nasz mixin też nadpisuje `get_actions`. Ponieważ
> mixin jest PIERWSZY, jego `get_actions` woła `super().get_actions()` → trafia
> w `AutorAdmin.get_actions` (które woła swój `super()` itd.). Kolejność OK:
> najpierw zostaje ustawiony opis `delete_selected` (Autor), potem mixin dokłada
> `przywroc_zaznaczone`/`usun_do_kosza`/(superuser) `usun_trwale_zaznaczone`.
> **Zweryfikuj w teście Task 6**, że akcje współistnieją.

- [ ] **Step 8: Recover-szew w `get_urls`**

W `BppSoftDeleteAdminMixin` dopisz:
```python
    def get_urls(self):
        urls = super().get_urls()
        # SZEW reversion (odłożone): gdy włączymy django-reversion, jego
        # "recover deleted" URL (recover/) musi tu być UKRYTY albo
        # przekierowany na restore() — recover wskrzeszałby rekord poza
        # przepływem soft-delete (bez WYSYLKA do PBN, bez SoftDeleteLog,
        # łamiąc warunkowy unique slug). Patrz overview "Kontrakty z reversion".
        return urls
```

- [ ] **Step 9: Run test to verify it passes**

Run: `uv run pytest "src/bpp/tests/test_admin_soft_delete.py::test_soft_delete_w_adminie_dla_kazdego_modelu" -v`
Expected: PASS (5 parametryzacji).

- [ ] **Step 10: Run full faza-07 suite + lint**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py -v`
Expected: PASS (wszystkie).

```bash
uv run ruff format src/bpp/admin/wydawnictwo_zwarte.py src/bpp/admin/patent.py \
    src/bpp/admin/praca_doktorska.py src/bpp/admin/praca_habilitacyjna.py \
    src/bpp/admin/autor.py src/bpp/admin/helpers/mixins.py
uv run ruff check src/bpp/admin/wydawnictwo_zwarte.py src/bpp/admin/patent.py \
    src/bpp/admin/praca_doktorska.py src/bpp/admin/praca_habilitacyjna.py \
    src/bpp/admin/autor.py src/bpp/admin/helpers/mixins.py
```

- [ ] **Step 11: Commit**

```bash
git add src/bpp/admin/wydawnictwo_zwarte.py src/bpp/admin/patent.py \
    src/bpp/admin/praca_doktorska.py src/bpp/admin/praca_habilitacyjna.py \
    src/bpp/admin/autor.py src/bpp/admin/helpers/mixins.py \
    src/bpp/tests/test_admin_soft_delete.py
git commit -m "feat(soft-delete): wpięcie BppSoftDeleteAdminMixin do 5 adminów + Autor"
```

---

## Task 7: Guard `Autor` z pracami — czytelny komunikat zamiast 500

**Files:**
- Modify: `src/bpp/admin/helpers/mixins.py` (`delete_queryset` / `usun_do_kosza` / `delete_model` łapią `ProtectedError`).
- Test: `src/bpp/tests/test_admin_soft_delete.py`.

> Faza 04: `Autor.delete()` rzuca `django.db.models.ProtectedError` (lub
> `ValidationError`) gdy autor ma JAKIEKOLWIEK autorstwo/doktorat/habilitację
> (liczone przez `global_objects`). Admin musi to złapać i pokazać komunikat,
> a NIE wywalić 500.

- [ ] **Step 1: Write the failing test**

```python
@pytest.mark.django_db
def test_soft_delete_autora_z_pracami_pokazuje_komunikat(superuser, superuser_client):
    from bpp.models import Wydawnictwo_Ciagle_Autor

    autor = baker.make(Autor)
    # Autor z autorstwem -> guard fazy 04 zablokuje soft-delete:
    baker.make(Wydawnictwo_Ciagle_Autor, autor=autor)

    url = reverse("admin:bpp_autor_changelist")
    resp = superuser_client.post(
        url,
        {
            "action": "usun_do_kosza",
            "_selected_action": [str(autor.pk)],
            "powod_potwierdzony": "1",
            "powod": "próba",
        },
        follow=True,
    )
    assert resp.status_code == 200
    # Autor NIE został skasowany:
    assert Autor.objects.filter(pk=autor.pk).exists()
    # Komunikat o blokadzie:
    content = resp.content.decode("utf-8")
    assert "nie można usunąć" in content.lower() or "prac" in content.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_soft_delete_autora_z_pracami_pokazuje_komunikat -v`
Expected: FAIL — `ProtectedError` przepada jako 500 albo wyjątek wycieka.

- [ ] **Step 3: Write implementation — łap ProtectedError w przepływach kasowania**

Dodaj helper w `BppSoftDeleteAdminMixin` i użyj go w `delete_model`, `delete_queryset`, `usun_do_kosza`:

```python
    def _soft_delete_jeden(self, request, obj, powod):
        """Soft-delete jednego obiektu z obsługą guarda (faza 04).

        Zwraca True przy sukcesie, False gdy guard zablokował (komunikat
        pokazany użytkownikowi)."""
        try:
            obj.delete(user=request.user, reason=powod)
            return True
        except ProtectedError:
            self.message_user(
                request,
                f"Nie można usunąć „{obj}" — rekord ma powiązane prace "
                "(autorstwa / doktorat / habilitacja). Najpierw usuń lub "
                "przenieś powiązane prace.",
                level=messages.ERROR,
            )
            return False
```

Podmień ciało pętli w `delete_queryset` i `usun_do_kosza` na:
```python
            for obj in queryset:
                if self._soft_delete_jeden(request, obj, powod):
                    usunieto += 1
```

W `delete_model` (pojedynczy „Usuń" z changeform):
```python
    def delete_model(self, request, obj):
        with self._soft_delete_user_context(request):
            self._soft_delete_jeden(request, obj, self._powod_z_requestu(request))
```

> `delete_model` przy zablokowaniu nie kasuje, ale Django i tak zrobi redirect
> z komunikatem błędu — akceptowalne (autor zostaje, error widoczny).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_soft_delete_autora_z_pracami_pokazuje_komunikat -v`
Expected: PASS.

> Jeśli faza 04 rzuca `ValidationError` zamiast `ProtectedError` — rozszerz
> `except` o `from django.core.exceptions import ValidationError` i łap oba.
> Zweryfikuj realny typ wyjątku z fazy 04 PRZED implementacją (przeczytaj
> `Autor.delete()` w `src/bpp/models/autor.py` po fazie 04).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
uv run ruff check src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
git add src/bpp/admin/helpers/mixins.py src/bpp/tests/test_admin_soft_delete.py
git commit -m "feat(soft-delete): admin łapie guard autora-z-pracami (czytelny komunikat)"
```

---

## Task 8: Test odmowy dla staff na pojedynczym hard-delete + domknięcie suity

**Files:**
- Test: `src/bpp/tests/test_admin_soft_delete.py`.

- [ ] **Step 1: Write the test — staff może soft-deletować, ale nie hard**

```python
@pytest.mark.django_db
def test_staff_moze_soft_delete_ale_nie_widzi_usun_trwale(staff_client):
    obj = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Staff soft")
    pk = obj.pk
    url = reverse("admin:bpp_wydawnictwo_ciagle_changelist")

    # delete_selected (domyślna) przechodzi przez nasz delete_queryset = kosz:
    resp = staff_client.post(
        url,
        {"action": "delete_selected", "_selected_action": [str(pk)], "post": "yes"},
        follow=True,
    )
    assert resp.status_code == 200
    # Soft-delete (rekord w global_objects, nie w objects):
    assert not Wydawnictwo_Ciagle.objects.filter(pk=pk).exists()
    assert Wydawnictwo_Ciagle.global_objects.filter(pk=pk).exists()

    # "Usuń trwale" niedostępne staffowi:
    resp_list = staff_client.get(url, {"is_deleted": "false"})
    assert b"usun_trwale_zaznaczone" not in resp_list.content
```

> Jeśli staff nie ma uprawnienia `delete_wydawnictwo_ciagle`, `delete_selected`
> nie pojawi się. Fixture `staff_user` (Task 4) nadaje uprawnienia modelowe →
> `delete_selected` dostępne, a idzie przez nasz soft `delete_queryset`.

- [ ] **Step 2: Run test**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py::test_staff_moze_soft_delete_ale_nie_widzi_usun_trwale -v`
Expected: PASS (cała logika już istnieje z Task 2/4).

- [ ] **Step 3: Run CAŁĄ suitę fazy + smoke adminów**

Run: `uv run pytest src/bpp/tests/test_admin_soft_delete.py -v`
Expected: PASS (wszystkie testy fazy 07).

Smoke regresji adminów publikacji/autora (że MRO nic nie zepsuło):
Run: `uv run pytest src/bpp/tests/ -k "admin" -q`
Expected: PASS (brak regresji w istniejących testach adminowych).

- [ ] **Step 4: Lint całości fazy**

Run: `uv run ruff format . && uv run ruff check .`
Expected: brak błędów w plikach fazy.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/tests/test_admin_soft_delete.py
git commit -m "test(soft-delete): staff soft-delete OK, hard-delete superuser-only"
```

---

## Self-Review (wykonaj po napisaniu kodu wszystkich tasków)

**1. Spec coverage (§6):**
- „Usuń" = soft-delete → Task 2 (`delete_model`/`delete_queryset`) + Task 5 (`usun_do_kosza`). ✅
- „Usuń trwale" superuser-only → Task 4. ✅
- Filtr „Pokaż skasowane" → Task 1 (`PokazSkasowaneFilter`). ✅
- Akcja „Przywróć" → Task 3. ✅
- Pole „powód" → `SoftDeleteLog` → Task 5. ✅
- `get_queryset` → `global_objects` → Task 1. ✅
- Jeden hook usera (`_soft_delete_user_context`) → Task 2, używany przez wszystkie ścieżki. ✅
- MRO/kompozycja z 6 adminami → Task 1 (Ciagle) + Task 6 (pozostałe). ✅
- Guard autora z pracami → czytelny komunikat → Task 7. ✅
- Szwy reversion (jeden hook + recover) → Task 2 (`# SZEW reversion`) + Task 6 (`get_urls`). ✅

**2. Placeholder scan:** brak „TODO/TBD"; każdy krok ma realny kod + komendę + oczekiwany wynik.

**3. Type consistency:** `_soft_delete_user_context` (Task 2), `_soft_delete_jeden` (Task 7), `_powod_z_requestu` (Task 2), `przywroc_zaznaczone`/`usun_trwale_zaznaczone`/`usun_do_kosza` (Task 3/4/5), `PokazSkasowaneFilter` (Task 1) — nazwy spójne we wszystkich taskach. `delete(user=, reason=)`/`restore(user=)`/`hard_delete(user=, reason=)` zgodne z kontraktem fazy 06.

---

## Założenia (zweryfikuj przed startem; jeśli nie zachodzą — to bug wcześniejszej fazy)

1. **Faza 06 dostarcza** `set_soft_delete_user`/`get_soft_delete_user`/`clear_soft_delete_user` w `src/bpp/models/soft_delete.py` oraz receivery, które na podstawie thread-local zapisują `SoftDeleteLog.user`. Jeśli mechanizm „kto" jest inny (np. argument do sygnału), dostosuj `_soft_delete_user_context` — ale **JEDEN punkt** pozostaje.
2. **Faza 06 modele** mają sygnatury `delete(self, *args, user=None, reason="", **kwargs)`, `restore(self, *args, user=None, **kwargs)`, `hard_delete(self, *args, user=None, reason="", **kwargs)` na 5 publikacjach + `Autor`. `SoftDeleteLog` ma pola `user`, `powod`, `akcja` (wartości `"delete"`/`"restore"`/`"hard_delete"`), `object_id`, `timestamp`.
3. **Faza 04** sprawia, że `Autor.delete()` rzuca `ProtectedError` (lub `ValidationError`) gdy autor ma prace; `Autor` jest `SoftDeleteModel` z `global_objects`/`deleted_objects`. `baker.make(Autor)` daje autora bez prac (soft-delete dozwolony).
4. **Faza 01/02** — 5 publikacji + `Autor` mają `global_objects`/`deleted_objects` (z `BppGlobalManager`), a `objects` ukrywa skasowane. `Wydawnictwo_Ciagle.delete(user=None, reason=...)` działa w teście (kaskada `*_Autor` jest no-op bez autorów).
5. **`request.user` w adminie** to instancja `AUTH_USER_MODEL` — bezpośrednio przekazywalny do `delete(user=...)`. Operacje systemowe (merge/celery) używają `user=None` (poza tą fazą).
6. **`SoftDeleteFilter`/`PokazSkasowaneFilter`** używają `parameter_name = "is_deleted"`; testy używają `is_deleted=false` = „pokaż kosz" (nasz kontrakt, nie pakietu).
