# Soft-delete — Faza 08: pełna suita regresji E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Domknąć soft-delete suitą regresji E2E, która udowadnia, że
skasowane publikacje/autorstwa nie wyciekają do cache, ewaluacji, API,
dashboardu, importu ani PBN, a wszystkie przepływy (wycofanie/restore PBN,
merge autorów, guardy PROTECT, log audytu) działają end-to-end.

**Architecture:** Faza testowa. Zależy od pełnej implementacji faz 01–07
(`*_Autor` + 5 publikacji jako `SoftDeleteModel`, override
`delete()`/`restore()` z wąską kaskadą, filtr `deleted_at IS NULL` w widokach
źródłowych, audyt kat. B na `global_objects`, guardy PROTECT, operacja
`WYCOFANIE` w `pbn_export_queue`, `SoftDeleteLog` + receivery sygnałów, admin
superusera). Testy używają realnych fixture'ów z `src/conftest.py` /
`src/fixtures/`, `model_bakery.baker.make`, materializowanego cache (`Rekord`,
`Autorzy`) i mocków klienta PBN. Tam, gdzie test ujawnia lukę produkcyjną
(np. dashboard liczący przez surowy SQL omijający menedżer `objects`),
dorzucamy minimalną poprawkę produkcyjną wraz z testem.

**Tech Stack:** pytest + `model_bakery`, Django, PostgreSQL (triggery
materializujące cache), `django-soft-delete`, `pbn_export_queue` (Celery),
`unittest.mock` dla klienta PBN.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md)
(§8 fazy, §9 ryzyka), indeks [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md).

---

## Uruchamianie suity

- **Pełna suita** (do ~10 min): `uv run pytest` — wszystko, w tym Playwright.
- **Szybciej, bez przeglądarki**: `make tests-without-playwright`.
- **Sama regresja soft-delete** (te pliki): `uv run pytest -k soft_delete_regresja`.
- Pojedynczy plik: `uv run pytest src/<app>/tests/test_soft_delete_regresja.py -v`.
- Wszystkie testy poniżej są `@pytest.mark.django_db` (część wymaga
  `transactional_db`, bo dotyka triggerów materializujących cache — fixture
  `denorms`/`transactional_db` jak w `src/bpp/tests/test_cache/test_cache.py`).
- Reguły BPP: `uv run pytest`, `baker.make`, linie ≤88 znaków, polskie nazwy
  i docstringi, funkcje testowe bez klas, `ruff format .` + `ruff check .`
  po każdym tasku.

---

## File Structure

**Tworzone (pliki testowe):**
- `src/bpp/tests/test_soft_delete/__init__.py` — pakiet testów regresji cache.
- `src/bpp/tests/test_soft_delete/test_soft_delete_regresja_cache.py` —
  spójność `Rekord`/`Autorzy`/`Cache_Punktacja_*` + `verify_cache`.
- `src/bpp/tests/test_soft_delete/test_soft_delete_regresja_guardy.py` —
  guardy PROTECT (autor z pracami, książka-matka z rozdziałami) + admin.
- `src/bpp/tests/test_soft_delete/test_soft_delete_regresja_log.py` —
  `SoftDeleteLog` (delete/restore/hard-delete + user).
- `src/pbn_integrator/tests/test_soft_delete_regresja.py` — PBN: wycofanie
  oświadczeń, restore→WYSYLKA, sync/re-import bez duplikatów.
- `src/import_common/tests/test_soft_delete_regresja.py` — re-import matchuje
  soft-deletowaną publikację (`global_objects`), nie duplikuje.
- `src/ewaluacja_optymalizacja/tests/test_soft_delete_regresja.py` —
  ewaluacja pomija prace w koszu (pinning/unpinning), restore przywraca.
- `src/deduplikator_autorow/tests/test_soft_delete_regresja.py` — merge
  husk-duplikat soft-deletowany i odwracalny; PROTECT nie psuje merge.
- `src/api_v1/tests/test_soft_delete_regresja.py` — skasowane rekordy /
  autorstwa nie wyciekają przez API.
- `src/admin_dashboard/tests/test_soft_delete_regresja.py` — liczniki
  dashboardu pomijają skasowane.

**Modyfikowane (drobne poprawki produkcyjne, jeśli test ujawni lukę):**
- `src/admin_dashboard/views/charakter_stats.py` — `_get_charakter_counts`
  (jeśli liczy przez surowy SQL/agregację omijającą filtr `deleted_at`).

---

## Task 1: Regresja cache — soft-delete publikacji znika z Rekord/Autorzy

**Files:**
- Create: `src/bpp/tests/test_soft_delete/__init__.py`
- Create: `src/bpp/tests/test_soft_delete/test_soft_delete_regresja_cache.py`

- [ ] **Step 1: Utwórz pakiet testowy**

```bash
touch src/bpp/tests/test_soft_delete/__init__.py
```

- [ ] **Step 2: Napisz failing test — soft-delete znika z Rekord i Autorzy, restore wraca**

`src/bpp/tests/test_soft_delete/test_soft_delete_regresja_cache.py`:

```python
"""Regresja E2E soft-delete: spójność materializowanego cache.

Skasowana publikacja MUSI zniknąć z ``Rekord``/``Autorzy``
(mat-view zasilany triggerem), a restore — przywrócić ją wraz z
``*_Autor``. Patrz spec §2.1, §9 (ryzyko cache/trigger).
"""

import pytest

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.cache import Autorzy, Rekord


@pytest.mark.django_db
def test_soft_delete_publikacji_znika_z_rekord_i_autorzy(
    wydawnictwo_ciagle_z_dwoma_autorami, denorms
):
    denorms.flush()
    assert Rekord.objects.count() == 1
    assert Autorzy.objects.count() == 2

    wydawnictwo_ciagle_z_dwoma_autorami.delete()
    denorms.flush()

    assert Rekord.objects.count() == 0
    assert Autorzy.objects.count() == 0


@pytest.mark.django_db
def test_restore_publikacji_wraca_do_rekord_i_autorzy(
    wydawnictwo_ciagle_z_dwoma_autorami, denorms
):
    wydawnictwo_ciagle_z_dwoma_autorami.delete()
    denorms.flush()
    assert Rekord.objects.count() == 0

    wydawnictwo_ciagle_z_dwoma_autorami.restore()
    denorms.flush()

    assert Rekord.objects.count() == 1
    assert Autorzy.objects.count() == 2


@pytest.mark.django_db
def test_kaskada_autor_soft_deletowany_razem_z_publikacja(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """Wąska kaskada §2.2 — *_Autor soft-deletowane razem z rodzicem,
    domyślny menedżer ``objects`` je ukrywa, ``global_objects`` widzi."""
    wydawnictwo_ciagle_z_dwoma_autorami.delete()

    assert Wydawnictwo_Ciagle_Autor.objects.count() == 0
    assert Wydawnictwo_Ciagle_Autor.global_objects.count() == 2
    for wca in Wydawnictwo_Ciagle_Autor.global_objects.all():
        assert wca.deleted_at is not None
```

- [ ] **Step 3: Uruchom — oczekuj PASS (implementacja faz 01–02 gotowa)**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_regresja_cache.py -v`
Expected: 3 PASS. Jeśli `test_soft_delete_publikacji_znika_z_rekord_i_autorzy`
FAIL (rekord wraca do mat-view) → **luka w fazie 01**: filtr `deleted_at IS
NULL` nie pokrywa wszystkich gałęzi UNION `bpp_rekord` / `bpp_*_autorzy`.
Zadanie naprawcze: dopisz brakujący `WHERE deleted_at IS NULL` w
`src/bpp/migrations/0XXX_soft_delete_views.sql` (NOWA migracja, nie modyfikuj
istniejących) i ponów.

- [ ] **Step 4: Commit**

```bash
git add src/bpp/tests/test_soft_delete/
git commit -m "test(soft-delete): regresja spójności cache Rekord/Autorzy"
```

---

## Task 2: Regresja cache — Cache_Punktacja_* + verify_cache czysty

**Files:**
- Modify: `src/bpp/tests/test_soft_delete/test_soft_delete_regresja_cache.py`

- [ ] **Step 1: Sprawdź realny mechanizm weryfikacji cache**

Run: `uv run python src/manage.py help | grep -iE "cache|rebuild|refresh"`
Run: `uv run python src/manage.py verify_cache --help 2>&1 | head -5`
Oczekiwane: ustal, czy `verify_cache` jest sprawny. **Znana luka:**
`src/bpp/management/commands/verify_cache.py` to dziś stub
(`raise NotImplementedError`, twarde `psycopg2.connect(database="b_med",
host="linux-dev")`) — NIE da się go uruchomić w teście. Weryfikację spójności
robimy przez `Rekord.objects.full_refresh()` (`src/bpp/models/cache/rekord.py:117`),
która jest realnym, testowalnym odpowiednikiem „re-projekcji ze źródła"
opisanym w spec §2.1. (Patrz „Luki wykryte" na końcu — `verify_cache` należy
naprawić osobnym zadaniem, poza zakresem soft-delete.)

- [ ] **Step 2: Napisz failing test — full_refresh nie wskrzesza skasowanych + Cache_Punktacja_* znika**

Dopisz do `test_soft_delete_regresja_cache.py`:

```python
from bpp.models.cache.punktacja import Cache_Punktacja_Dyscypliny


@pytest.mark.django_db
def test_full_refresh_nie_wskrzesza_skasowanej_publikacji(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """Re-projekcja ze źródła (full_refresh) respektuje deleted_at —
    inaczej skasowany rekord wróciłby do bpp_rekord_mat (spec §2.1)."""
    wydawnictwo_ciagle_z_dwoma_autorami.delete()
    assert Rekord.objects.count() == 0

    Rekord.objects.full_refresh()

    assert Rekord.objects.count() == 0
    assert Autorzy.objects.count() == 0


@pytest.mark.django_db
def test_soft_delete_usuwa_cache_punktacji_dyscyplin(zwarte_z_dyscyplinami):
    """Punktacja dyscyplin skasowanej pracy znika; restore ją przywraca."""
    zwarte_z_dyscyplinami.przelicz_punkty_dyscyplin()
    ct_pks = list(
        Cache_Punktacja_Dyscypliny.objects.filter(
            rekord_id=[zwarte_z_dyscyplinami.content_type_id, zwarte_z_dyscyplinami.pk]
        ).values_list("pk", flat=True)
    )
    assert len(ct_pks) > 0

    zwarte_z_dyscyplinami.delete()

    assert (
        Cache_Punktacja_Dyscypliny.objects.filter(pk__in=ct_pks).count() == 0
    )

    zwarte_z_dyscyplinami.restore()
    zwarte_z_dyscyplinami.przelicz_punkty_dyscyplin()

    assert (
        Cache_Punktacja_Dyscypliny.objects.filter(
            rekord_id=[
                zwarte_z_dyscyplinami.content_type_id,
                zwarte_z_dyscyplinami.pk,
            ]
        ).count()
        > 0
    )
```

- [ ] **Step 3: Uruchom — oczekuj PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_regresja_cache.py -k "full_refresh or cache_punktacji" -v`
Expected: PASS. Jeśli `Cache_Punktacja_Dyscypliny` wraca po delete →
sprawdź, czy override `delete()` (faza 02) czyści punktację dyscyplin albo
czy trigger usuwa wpisy `Cache_Punktacja_*` na podstawie `deleted_at`.
Jeśli pole `rekord_id` w `Cache_Punktacja_Dyscypliny` ma inną strukturę niż
`[content_type_id, pk]`, dostosuj filtr do realnego schematu modelu
(`src/bpp/models/cache/punktacja.py:18`) — sprawdź `uv run python
src/manage.py shell -c "from bpp.models.cache.punktacja import
Cache_Punktacja_Dyscypliny as C; print(C._meta.get_field('rekord_id'))"`.

- [ ] **Step 4: Commit**

```bash
git add src/bpp/tests/test_soft_delete/test_soft_delete_regresja_cache.py
git commit -m "test(soft-delete): regresja Cache_Punktacja + full_refresh"
```

---

## Task 3: Regresja guardy PROTECT — autor z pracami i książka-matka z rozdziałami

**Files:**
- Create: `src/bpp/tests/test_soft_delete/test_soft_delete_regresja_guardy.py`

- [ ] **Step 1: Napisz failing test — guard autora z pracami (soft + hard)**

```python
"""Regresja guardów PROTECT (spec §3, §2.6).

Autor z jakąkolwiek pracą oraz książka-matka z rozdziałami NIE mogą być
soft- ani hard-deletowane. Guard liczy przez ``global_objects`` (widzi też
kaskadowo-skasowane autorstwa) — patrz §3.2 i ryzyko w §9.
"""

import pytest
from django.db.models import ProtectedError

from bpp.models import (
    Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
)


@pytest.mark.django_db
def test_soft_delete_autora_z_pracami_odmowa(wydawnictwo_ciagle_z_dwoma_autorami):
    autor = wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.first().autor

    with pytest.raises(ProtectedError):
        autor.delete()

    assert Autor.objects.filter(pk=autor.pk).exists()
    assert autor.deleted_at is None


@pytest.mark.django_db
def test_guard_autora_widzi_kaskadowo_skasowane_autorstwa(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """Krytyczne §3.2: po soft-delete publikacji autorstwa są ukryte
    w ``objects``, ale guard liczy przez ``global_objects`` — autor nadal
    chroniony, NIE wygląda na pustego."""
    autor = wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.first().autor
    wydawnictwo_ciagle_z_dwoma_autorami.delete()

    with pytest.raises(ProtectedError):
        autor.delete()

    assert Autor.objects.filter(pk=autor.pk).exists()
```

- [ ] **Step 2: Uruchom — oczekuj PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_regresja_guardy.py -v`
Expected: PASS. Jeśli `test_guard_autora_widzi_kaskadowo_skasowane_autorstwa`
FAIL (autor da się skasować) → **luka w fazie 04**: guard używa `objects`
zamiast `global_objects`. To dokładnie ryzyko z §9. Zadanie naprawcze: w
`Autor.delete()` (guard) policz autorstwa przez `*_Autor.global_objects`.

- [ ] **Step 3: Napisz failing test — soft-delete autora-husku (bez prac) działa i jest odwracalny**

```python
@pytest.mark.django_db
def test_soft_delete_autora_husku_dziala_i_jest_odwracalny():
    husk = baker_autor_bez_prac()

    husk.delete()
    assert Autor.objects.filter(pk=husk.pk).count() == 0
    assert Autor.global_objects.filter(pk=husk.pk).count() == 1

    husk.restore()
    assert Autor.objects.filter(pk=husk.pk).count() == 1


def baker_autor_bez_prac():
    from model_bakery import baker

    return baker.make(Autor, nazwisko="Husk", imiona="Pusty")
```

- [ ] **Step 4: Napisz failing test — książka-matka z rozdziałami chroniona**

```python
@pytest.mark.django_db
def test_soft_delete_ksiazki_matki_z_rozdzialami_odmowa(jednostka):
    from model_bakery import baker

    matka = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Matka")
    baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Rozdzial",
        wydawnictwo_nadrzedne=matka,
    )

    with pytest.raises(ProtectedError):
        matka.delete()

    assert Wydawnictwo_Zwarte.objects.filter(pk=matka.pk).exists()
    assert matka.deleted_at is None
```

- [ ] **Step 5: Uruchom całość pliku — oczekuj PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_regresja_guardy.py -v`
Expected: PASS (4 testy). Jeśli książka-matka się kasuje → luka w fazie 04
(guard `wydawnictwo_nadrzedne` liczony przez `global_objects`, §2.6).

- [ ] **Step 6: Napisz test — guard przez admina (próba kasowania autora z pracami)**

Dopisz do pliku:

```python
from django.urls import reverse


@pytest.mark.django_db
def test_admin_nie_soft_deletuje_autora_z_pracami(
    superuser_client, wydawnictwo_ciagle_z_dwoma_autorami
):
    autor = wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.first().autor
    url = reverse("admin:bpp_autor_delete", args=(autor.pk,))

    resp = superuser_client.post(url, {"post": "yes"})

    # Admin nie kasuje (guard) — rekord nadal żywy, nie soft-deletowany.
    assert Autor.objects.filter(pk=autor.pk).exists()
    assert Autor.objects.get(pk=autor.pk).deleted_at is None
    assert resp.status_code in (200, 302)
```

- [ ] **Step 7: Uruchom — oczekuj PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_regresja_guardy.py -k admin -v`
Expected: PASS. Jeśli admin twardo kasuje autora z pracami → luka w fazie 07
(admin musi respektować guard z fazy 04 w `delete_model`/`delete_queryset`).

- [ ] **Step 8: Commit**

```bash
git add src/bpp/tests/test_soft_delete/test_soft_delete_regresja_guardy.py
git commit -m "test(soft-delete): regresja guardów PROTECT (autor, ksiazka-matka, admin)"
```

---

## Task 4: Regresja SoftDeleteLog — delete/restore/hard-delete z userem

**Files:**
- Create: `src/bpp/tests/test_soft_delete/test_soft_delete_regresja_log.py`

- [ ] **Step 1: Napisz failing test — delete loguje DELETE z userem, restore RESTORE, hard-delete HARD_DELETE**

```python
"""Regresja SoftDeleteLog (spec §5).

Każde zdarzenie soft-delete / restore / hard-delete jest logowane przez
receiver sygnału z odpowiednią akcją; user wstrzykiwany z warstwy admina
(operacje systemowe → ``user=None``).
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.soft_delete_log import SoftDeleteLog


def _logi_dla(obj, akcja):
    return SoftDeleteLog.objects.filter(
        content_type=ContentType.objects.get_for_model(type(obj)),
        object_id=obj.pk,
        akcja=akcja,
    )


@pytest.mark.django_db
def test_soft_delete_loguje_delete(admin_user):
    wc = baker.make(Wydawnictwo_Ciagle)

    wc.delete(user=admin_user, reason="testowy powod")

    log = _logi_dla(wc, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user == admin_user
    assert log.powod == "testowy powod"


@pytest.mark.django_db
def test_restore_loguje_restore(admin_user):
    wc = baker.make(Wydawnictwo_Ciagle)
    wc.delete(user=admin_user)

    wc.restore(user=admin_user)

    assert _logi_dla(wc, SoftDeleteLog.Akcja.RESTORE).exists()


@pytest.mark.django_db
def test_hard_delete_loguje_hard_delete():
    wc = baker.make(Wydawnictwo_Ciagle)
    pk = wc.pk

    wc.hard_delete()

    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    assert SoftDeleteLog.objects.filter(
        content_type=ct, object_id=pk, akcja=SoftDeleteLog.Akcja.HARD_DELETE
    ).exists()


@pytest.mark.django_db
def test_operacja_systemowa_loguje_user_none():
    wc = baker.make(Wydawnictwo_Ciagle)

    wc.delete()

    log = _logi_dla(wc, SoftDeleteLog.Akcja.DELETE).get()
    assert log.user is None
```

- [ ] **Step 2: Uruchom — oczekuj PASS**

Run: `uv run pytest src/bpp/tests/test_soft_delete/test_soft_delete_regresja_log.py -v`
Expected: 4 PASS. Jeśli `SoftDeleteLog.Akcja` ma inne nazwy enuma niż
`DELETE/RESTORE/HARD_DELETE` — dostosuj do realnego modelu z fazy 06
(`src/bpp/models/soft_delete_log.py`; PINNED w overview: `DELETE="delete"`,
`RESTORE="restore"`, `HARD_DELETE="hard_delete"`). Jeśli sygnatura
`delete(user=..., reason=...)` nie istnieje → luka w fazie 06 (wstrzykiwanie
usera, PINNED kontrakt).

- [ ] **Step 3: Commit**

```bash
git add src/bpp/tests/test_soft_delete/test_soft_delete_regresja_log.py
git commit -m "test(soft-delete): regresja SoftDeleteLog (delete/restore/hard + user)"
```

---

## Task 5: Regresja PBN — wycofanie oświadczeń, restore→WYSYLKA, brak duplikatów

**Files:**
- Create: `src/pbn_integrator/tests/test_soft_delete_regresja.py`

- [ ] **Step 1: Ustal nazwy operacji i fixture publikacji z pbn_uid**

Run: `uv run python src/manage.py shell -c "from pbn_export_queue.models import PBN_Export_Queue as Q; print([f.name for f in Q._meta.fields]); from pbn_export_queue.models import Operacja; print(list(Operacja))"`
Expected: pole `operacja` z `Operacja.WYSYLKA`/`Operacja.WYCOFANIE` (faza 05).
Fixture `pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina` (z `fixtures.pbn_api`,
użyty w `src/pbn_integrator/tests/test_statements.py`) daje publikację, której
można nadać `pbn_uid`.

- [ ] **Step 2: Napisz failing test — soft-delete publikacji z pbn_uid kolejkuje WYCOFANIE**

```python
"""Regresja PBN dla soft-delete (spec §4).

Soft-delete publikacji z ``pbn_uid`` → wpis ``WYCOFANIE`` w
``pbn_export_queue`` wołający ``delete_all_publication_statements``; restore
→ ``WYSYLKA``; sync/re-import po soft-delete NIE tworzy duplikatów
(krytyczne, §9).
"""

from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from pbn_api.models import Publication
from pbn_export_queue.models import Operacja, PBN_Export_Queue


@pytest.mark.django_db
def test_soft_delete_z_pbn_uid_kolejkuje_wycofanie(wydawnictwo_ciagle, admin_user):
    wydawnictwo_ciagle.pbn_uid = baker.make(Publication, mongoId="pub-wycofanie")
    wydawnictwo_ciagle.save()

    wydawnictwo_ciagle.delete(user=admin_user)

    assert PBN_Export_Queue.objects.filter(
        operacja=Operacja.WYCOFANIE
    ).count() == 1


@pytest.mark.django_db
def test_soft_delete_bez_pbn_uid_nie_kolejkuje_nic(wydawnictwo_ciagle, admin_user):
    """Gate na pbn_uid — rekord, który nigdy nie poszedł do PBN, nic nie robi."""
    assert wydawnictwo_ciagle.pbn_uid is None

    wydawnictwo_ciagle.delete(user=admin_user)

    assert PBN_Export_Queue.objects.filter(operacja=Operacja.WYCOFANIE).count() == 0


@pytest.mark.django_db
def test_restore_kolejkuje_wysylke(wydawnictwo_ciagle, admin_user):
    wydawnictwo_ciagle.pbn_uid = baker.make(Publication, mongoId="pub-restore")
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)

    wydawnictwo_ciagle.restore(user=admin_user)

    assert PBN_Export_Queue.objects.filter(
        operacja=Operacja.WYSYLKA, rekord_do_wysylki_id=wydawnictwo_ciagle.pk
    ).exists()
```

- [ ] **Step 3: Uruchom — oczekuj PASS**

Run: `uv run pytest src/pbn_integrator/tests/test_soft_delete_regresja.py -k "kolejkuje or pbn_uid" -v`
Expected: PASS. Pole `rekord_do_wysylki_id` widoczne w
`test_pbn_queue_send.py` (`baker.make(PBN_Export_Queue,
rekord_do_wysylki=wydawnictwo_ciagle, ...)`). Jeśli GFK ma inną nazwę pola
ustal przez Step 1 i dostosuj filtr.

- [ ] **Step 4: Napisz failing test — wpis WYCOFANIE woła delete_all_publication_statements**

```python
@pytest.mark.django_db
def test_wycofanie_wola_delete_all_publication_statements(
    wydawnictwo_ciagle, admin_user
):
    pub = baker.make(Publication, mongoId="pub-call-check")
    wydawnictwo_ciagle.pbn_uid = pub
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete(user=admin_user)

    qi = PBN_Export_Queue.objects.get(operacja=Operacja.WYCOFANIE)

    fake_client = MagicMock()
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(admin_user, "get_pbn_user", lambda *a, **k: object())
        mp.setattr(
            "pbn_export_queue.models.PBN_Export_Queue.get_client",
            lambda self: fake_client,
            raising=False,
        )
        qi.send_to_pbn()

    fake_client.delete_all_publication_statements.assert_called_once_with(
        str(pub.mongoId)
    )
```

- [ ] **Step 5: Uruchom — oczekuj PASS lub dostosuj punkt wpięcia klienta**

Run: `uv run pytest src/pbn_integrator/tests/test_soft_delete_regresja.py -k delete_all -v`
Expected: PASS. Jeśli `send_to_pbn` pobiera klienta inaczej niż przez
`get_client` (sprawdź `src/pbn_export_queue/models.py:350`), zmień mock na
realny punkt wpięcia (wzorzec z `test_pbn_queue_send.py` — tam mockują
`admin_user.get_pbn_user` i `model_table_exists`). Argument: klient PBN
`delete_all_publication_statements(publicationId)`
(`src/pbn_api/client/mixins/institutions.py:87`).

- [ ] **Step 6: Napisz failing test — re-sync po soft-delete NIE tworzy duplikatu (KRYTYCZNE)**

```python
@pytest.mark.django_db
def test_resync_po_soft_delete_nie_tworzy_duplikatu(wydawnictwo_ciagle):
    """Matching po pbn_uid musi iść przez global_objects (spec §2.5).
    Inaczej soft-delete = generator duplikatów."""
    from bpp.models import Wydawnictwo_Ciagle

    pub = baker.make(Publication, mongoId="pub-resync")
    wydawnictwo_ciagle.pbn_uid = pub
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.delete()

    # Symulacja matchingu importera/synchronizatora po pbn_uid:
    znaleziony = Wydawnictwo_Ciagle.global_objects.filter(pbn_uid=pub).first()

    assert znaleziony is not None
    assert znaleziony.pk == wydawnictwo_ciagle.pk
    # Domyślny menedżer NIE widzi skasowanej — to właśnie pułapka duplikatu:
    assert Wydawnictwo_Ciagle.objects.filter(pbn_uid=pub).first() is None
```

- [ ] **Step 7: Uruchom — oczekuj PASS**

Run: `uv run pytest src/pbn_integrator/tests/test_soft_delete_regresja.py -k resync -v`
Expected: PASS. Ten test dokumentuje kontrakt kat. B (faza 03). Jeśli realny
kod synchronizacji (`pbn_integrator/utils/synchronization.py`) używa `objects`
zamiast `global_objects` przy matchingu po `pbn_uid` → luka w fazie 03,
zadanie naprawcze: przełącz matching na `global_objects`.

- [ ] **Step 8: Commit**

```bash
git add src/pbn_integrator/tests/test_soft_delete_regresja.py
git commit -m "test(soft-delete): regresja PBN wycofanie/restore + brak duplikatow sync"
```

---

## Task 6: Regresja import — re-import matchuje soft-deletowaną publikację

**Files:**
- Create: `src/import_common/tests/test_soft_delete_regresja.py`

- [ ] **Step 1: Napisz failing test — matchuj_publikacje znajduje soft-deletowaną (global_objects)**

```python
"""Regresja importu (spec §2.5, §3 fazy).

Re-import soft-deletowanej publikacji MUSI zmatchować istniejący rekord
przez ``global_objects`` — inaczej powstaje duplikat (pułapka §9).
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from import_common.core import matchuj_publikacje


@pytest.mark.django_db
def test_matchuj_publikacje_matchuje_soft_deletowana(jezyki, typy_kbn):
    wc = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Bardzo specyficzny tytul do matchowania importu",
        rok=2020,
    )
    wc.delete()

    znaleziony = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Bardzo specyficzny tytul do matchowania importu",
        year=2020,
    )

    assert znaleziony is not None
    assert znaleziony.pk == wc.pk


@pytest.mark.django_db
def test_reimport_nie_tworzy_duplikatu_soft_deletowanej():
    wc = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Inny unikalny tytul publikacji importowanej",
        rok=2021,
    )
    wc.delete()

    przed = Wydawnictwo_Ciagle.global_objects.count()
    znaleziony = matchuj_publikacje(
        Wydawnictwo_Ciagle,
        title="Inny unikalny tytul publikacji importowanej",
        year=2021,
    )
    # Jeśli matchuje, importer nie utworzy nowego — liczba global bez zmian.
    assert znaleziony is not None
    assert Wydawnictwo_Ciagle.global_objects.count() == przed
```

- [ ] **Step 2: Uruchom — oczekuj PASS**

Run: `uv run pytest src/import_common/tests/test_soft_delete_regresja.py -v`
Expected: PASS. Jeśli `matchuj_publikacje` zwraca `None` dla skasowanej →
**luka w fazie 03**: `import_common/core/publikacja.py` (helpery
`_try_match_pub_by_*`) muszą szukać przez `klass.global_objects`, nie
`klass.objects`. Zadanie naprawcze: przełącz menedżer w funkcjach matchujących.
Jeśli fixture `typy_kbn` nie istnieje, usuń go z sygnatury — `baker.make`
dociągnie wymagane FK; sprawdź `uv run pytest --fixtures -k typy 2>/dev/null`.

- [ ] **Step 3: Commit**

```bash
git add src/import_common/tests/test_soft_delete_regresja.py
git commit -m "test(soft-delete): regresja importu matchuje soft-deletowana (bez duplikatow)"
```

---

## Task 7: Regresja ewaluacja — pomija prace w koszu, restore przywraca punktację

**Files:**
- Create: `src/ewaluacja_optymalizacja/tests/test_soft_delete_regresja.py`

- [ ] **Step 1: Ustal realny punkt wejścia ewaluacji liczący *_Autor**

Run: `grep -rln "Wydawnictwo_Ciagle_Autor.objects\|Wydawnictwo_Zwarte_Autor.objects" src/ewaluacja_optymalizacja/ | head`
Run: `grep -rn "def reset_pins\|def unpin_all\|def author_works" src/ewaluacja_optymalizacja/ | head`
Expected: ustal funkcję, która zlicza/iteruje autorstwa (spec §2.5 wymienia
`reset_pins`, `unpin_all_sensible`, `author_works`). Test ma dowieść, że po
soft-delete publikacji jej autorstwa znikają z liczenia (bo `*_Autor.objects`
je ukrywa).

- [ ] **Step 2: Napisz failing test — autorstwa skasowanej pracy znikają z liczenia**

```python
"""Regresja ewaluacji (spec §2.5, §3 fazy).

90 miejsc czyta ``*_Autor.objects`` bezpośrednio; po wpięciu
``SoftDeleteModel`` domyślny menedżer ukrywa kaskadowo-skasowane
autorstwa, więc ewaluacja pomija prace w koszu. Restore przywraca punktację.
"""

import pytest

from bpp.models import Wydawnictwo_Ciagle_Autor


@pytest.mark.django_db
def test_ewaluacja_pomija_autorstwa_pracy_w_koszu(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    autor = wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.first().autor

    assert Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor).count() == 1

    wydawnictwo_ciagle_z_dwoma_autorami.delete()

    # Domyślny menedżer (używany przez ewaluację) NIE widzi skasowanych:
    assert Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor).count() == 0
    # global_objects nadal je trzyma (odwracalność):
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(autor=autor).count() == 1


@pytest.mark.django_db
def test_restore_przywraca_autorstwa_do_ewaluacji(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    autor = wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.first().autor
    wydawnictwo_ciagle_z_dwoma_autorami.delete()
    assert Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor).count() == 0

    wydawnictwo_ciagle_z_dwoma_autorami.restore()

    assert Wydawnictwo_Ciagle_Autor.objects.filter(autor=autor).count() == 1
```

- [ ] **Step 3: Uruchom — oczekuj PASS**

Run: `uv run pytest src/ewaluacja_optymalizacja/tests/test_soft_delete_regresja.py -v`
Expected: PASS. Jeśli skasowane autorstwa nadal są liczone przez `objects` →
**luka w fazie 01/02**: `*_Autor` nie jest poprawnie `SoftDeleteModel` albo
override `delete()` nie kaskaduje na `*_Autor`. To ryzyko „silent leak"
z §1/§9.

- [ ] **Step 4: Napisz test integracyjny — unpinning nie liczy skasowanej pracy**

Dopisz (dostosuj nazwę funkcji do ustalonej w Step 1; przykład z
`unpinning_opportunities` widocznym w
`src/ewaluacja_optymalizacja/tests/test_unpinning_opportunities.py`):

```python
@pytest.mark.django_db
def test_unpinning_nie_uwzglednia_pracy_w_koszu(
    wydawnictwo_ciagle_z_dwoma_autorami, denorms
):
    """Soft-deletowana praca nie pojawia się wśród kandydatów ewaluacji,
    bo Rekord/Autorzy ją odfiltrowuje (spec §2.1) i *_Autor.objects ukrywa."""
    from bpp.models.cache import Rekord

    denorms.flush()
    autor = wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.first().autor
    assert Rekord.objects.prace_autora(autor).count() == 1

    wydawnictwo_ciagle_z_dwoma_autorami.delete()
    denorms.flush()

    assert Rekord.objects.prace_autora(autor).count() == 0
```

- [ ] **Step 5: Uruchom — oczekuj PASS**

Run: `uv run pytest src/ewaluacja_optymalizacja/tests/test_soft_delete_regresja.py -k unpinning -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/ewaluacja_optymalizacja/tests/test_soft_delete_regresja.py
git commit -m "test(soft-delete): regresja ewaluacji pomija prace w koszu, restore przywraca"
```

---

## Task 8: Regresja merge autorów — husk soft-deletowany i odwracalny

**Files:**
- Create: `src/deduplikator_autorow/tests/test_soft_delete_regresja.py`

- [ ] **Step 1: Ustal funkcję merge i widok**

Run: `grep -n "def " src/deduplikator_autorow/utils/merge.py | head`
Run: `grep -n "\.delete()" src/deduplikator_autorow/views/merge.py`
Expected: merge przenosi wszystkie typy prac, potem woła `autor.delete()` na
pustym duplikacie (`views/merge.py:155`). Po fazie 04 husk staje się soft-
deletowany (odwracalny). PROTECT nie psuje merge, bo duplikat jest już pusty.

- [ ] **Step 2: Napisz failing test — po scaleniu duplikat soft-deletowany i odwracalny**

```python
"""Regresja merge autorów (spec §3.3).

Po scaleniu husk duplikata jest soft-deletowany (odwracalny, nie znika
bezpowrotnie). PROTECT nie psuje merge (duplikat jest pusty w chwili
delete). Patrz §3.3, §9 (ryzyko: merge musi przenieść WSZYSTKIE typy prac).
"""

import pytest
from model_bakery import baker

from bpp.models import Autor


@pytest.mark.django_db
def test_husk_duplikata_jest_soft_deletowany_i_odwracalny():
    """Pusty duplikat usunięty w merge → soft-delete, da się przywrócić."""
    duplikat = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")

    # Husk bez prac — usuwany jak w merge (utils/merge.py kończy delete()).
    duplikat.delete()

    assert Autor.objects.filter(pk=duplikat.pk).count() == 0
    assert Autor.global_objects.filter(pk=duplikat.pk).count() == 1

    duplikat.restore()
    assert Autor.objects.filter(pk=duplikat.pk).count() == 1
```

- [ ] **Step 3: Napisz test E2E przez widok merge (jeśli istnieje endpoint scalania)**

Run: `grep -rn "def merge\|name=\"" src/deduplikator_autorow/urls.py | head`
Dopisz test wołający realny przepływ scalania, jeśli jest dostępny URL.
Wzorzec z `src/deduplikator_autorow/tests/test_scal_view.py`. Jeśli przepływ
jest złożony (wymaga `DuplicateScanRun` itd.), wywołaj bezpośrednio funkcję
z `utils/merge.py`:

```python
@pytest.mark.django_db
def test_merge_przenosi_prace_i_soft_deletuje_duplikat(
    wydawnictwo_ciagle_z_dwoma_autorami, admin_user
):
    from deduplikator_autorow.utils.merge import merge_authors

    autorzy = list(
        a.autor for a in wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.all()
    )
    glowny, duplikat = autorzy[0], autorzy[1]

    # Przenieś prace duplikata na głównego + usuń husk:
    merge_authors(glowny, duplikat, user=admin_user)

    # Duplikat soft-deletowany (odwracalny), główny żyje:
    assert Autor.objects.filter(pk=glowny.pk).exists()
    assert Autor.objects.filter(pk=duplikat.pk).count() == 0
    assert Autor.global_objects.filter(pk=duplikat.pk).count() == 1
```

- [ ] **Step 4: Uruchom — oczekuj PASS, dostosuj sygnaturę merge**

Run: `uv run pytest src/deduplikator_autorow/tests/test_soft_delete_regresja.py -v`
Expected: PASS. Sygnatura `merge_authors` może się różnić — ustal przez Step 1
(`grep -n "def merge" src/deduplikator_autorow/utils/merge.py`) i dostosuj
wywołanie. Jeśli merge NIE przenosi któregoś typu prac przed `delete()` →
guard/PROTECT zablokuje usunięcie husku → test FAIL z `ProtectedError`. To
dokładnie ryzyko z §3.3/§9 — zadanie naprawcze: uzupełnij transfer brakującego
typu w `utils/merge.py` (ciągłe/zwarte/patent/doktorat/habilitacja).

- [ ] **Step 5: Commit**

```bash
git add src/deduplikator_autorow/tests/test_soft_delete_regresja.py
git commit -m "test(soft-delete): regresja merge autorow (husk odwracalny, PROTECT nie psuje)"
```

---

## Task 9: Regresja API — skasowane rekordy/autorstwa nie wyciekają

**Files:**
- Create: `src/api_v1/tests/test_soft_delete_regresja.py`

- [ ] **Step 1: Napisz failing test — soft-deletowana publikacja nie wyciekła w API list/detail**

```python
"""Regresja API v1 (spec §2.5 kat. A — wyświetlanie/eksport).

Skasowane publikacje i autorstwa NIE mogą wyciekać przez REST API.
Domyślny menedżer ``objects`` (używany przez viewsety) je ukrywa.
"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_api_list_pomija_soft_deletowana_publikacje(api_client, wydawnictwo_ciagle):
    res = api_client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
    assert res.json()["count"] == 1

    wydawnictwo_ciagle.delete()

    res = api_client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_api_detail_soft_deletowanej_daje_404(client, wydawnictwo_ciagle):
    pk = wydawnictwo_ciagle.pk
    url = reverse("api_v1:wydawnictwo_ciagle-detail", args=(pk,))
    assert client.get(url).status_code == 200

    wydawnictwo_ciagle.delete()

    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_api_rekord_pomija_soft_deletowana(api_client, wydawnictwo_ciagle, denorms):
    denorms.flush()
    res = api_client.get(reverse("api_v1:rekord-list"))
    assert res.json()["count"] == 1

    wydawnictwo_ciagle.delete()
    denorms.flush()

    res = api_client.get(reverse("api_v1:rekord-list"))
    assert res.json()["count"] == 0
```

- [ ] **Step 2: Uruchom — oczekuj PASS (dostosuj nazwę route rekord)**

Run: `uv run pytest src/api_v1/tests/test_soft_delete_regresja.py -v`
Expected: PASS. Nazwę route sprawdź: `grep -rn "rekord" src/api_v1/urls.py
src/api_v1/viewsets/*.py | grep -i basename`. Jeśli route nazywa się inaczej
(np. `api_v1:rekord_mat-list`), dostosuj `reverse`. Jeśli list/detail nadal
zwraca skasowaną → viewset używa `global_objects`/surowego querysetu zamiast
`objects` (kat. A) — luka, zadanie naprawcze: w
`src/api_v1/viewsets/` ustaw `queryset = Model.objects.all()`.

- [ ] **Step 3: Commit**

```bash
git add src/api_v1/tests/test_soft_delete_regresja.py
git commit -m "test(soft-delete): regresja API nie wycieka skasowanych rekordow"
```

---

## Task 10: Regresja dashboard — liczniki pomijają skasowane

**Files:**
- Create: `src/admin_dashboard/tests/test_soft_delete_regresja.py`
- Modify (jeśli test ujawni lukę): `src/admin_dashboard/views/charakter_stats.py`

- [ ] **Step 1: Sprawdź, jak dashboard liczy publikacje**

Run: `grep -rn "objects\|raw\|connection.cursor\|Count" src/admin_dashboard/views/charakter_stats.py`
Expected: `_get_charakter_counts` (`charakter_stats.py:41`). Jeśli używa
`Wydawnictwo_Ciagle.objects` — po fazie 02 automatycznie pomija skasowane
(kat. A czysta). Jeśli używa surowego SQL na `bpp_wydawnictwo_ciagle` z
`connection.cursor()` — omija menedżer i policzy skasowane → luka do naprawy.

- [ ] **Step 2: Napisz failing test — soft-delete zmniejsza licznik charakteru**

```python
"""Regresja dashboardu (spec §2.5 kat. A).

Liczniki/statystyki MUSZĄ pomijać skasowane publikacje.
"""

import pytest
from model_bakery import baker

from admin_dashboard.views.charakter_stats import _get_charakter_counts
from bpp.models import Charakter_Formalny, Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_get_charakter_counts_pomija_soft_deletowana():
    cf = baker.make(Charakter_Formalny, nazwa="Artykul", skrot="AR")
    baker.make(Wydawnictwo_Ciagle, charakter_formalny=cf)
    wc2 = baker.make(Wydawnictwo_Ciagle, charakter_formalny=cf)

    przed = _licznik_dla(cf)
    assert przed == 2

    wc2.delete()

    assert _licznik_dla(cf) == 1


def _licznik_dla(cf):
    total = 0
    for row in _get_charakter_counts():
        # row: (nazwa, count, skrot, id, ciagle_count, zwarte_count)
        if row[2] == cf.skrot:
            total += row[4]  # ciagle_count
    return total
```

- [ ] **Step 3: Uruchom — oczekuj PASS lub napraw produkcyjnie**

Run: `uv run pytest src/admin_dashboard/tests/test_soft_delete_regresja.py -v`
Expected: PASS, jeśli `_get_charakter_counts` liczy przez `.objects`. Jeśli
FAIL (licznik nadal 2) → poprawka produkcyjna: w `charakter_stats.py`
zamień surowy SQL/agregację na ORM przez menedżer `objects`, np.:

```python
from django.db.models import Count

ciagle_counts = dict(
    Wydawnictwo_Ciagle.objects.values("charakter_formalny")
    .annotate(c=Count("id"))
    .values_list("charakter_formalny", "c")
)
```

albo (jeśli zostaje surowy SQL) dopisz `WHERE deleted_at IS NULL` do zapytania.
Dostosuj indeksy w `_licznik_dla` do realnego kształtu krotki zwracanej przez
`_get_charakter_counts` (sprawdź docstring funkcji w
`charakter_stats.py:41`).

- [ ] **Step 4: Napisz test widoku database_stats (rozkład typów pomija skasowane)**

```python
import json

from django.urls import reverse


@pytest.mark.django_db
def test_database_stats_rozklad_typow_pomija_skasowane(client, staff_user):
    cf = baker.make(Charakter_Formalny, nazwa="Ksiazka", skrot="KS")
    baker.make(Wydawnictwo_Ciagle, charakter_formalny=cf)
    wc = baker.make(Wydawnictwo_Ciagle, charakter_formalny=cf)
    wc.delete()

    client.force_login(staff_user)
    res = client.get(reverse("admin_dashboard:database_stats"))
    data = json.loads(res.content)

    ciagle = {
        e["charakter_formalny__nazwa"]: e["count"]
        for e in data["type_distribution"]["ciagle"]
    }
    assert ciagle.get("Ksiazka") == 1
```

- [ ] **Step 5: Uruchom — oczekuj PASS**

Run: `uv run pytest src/admin_dashboard/tests/test_soft_delete_regresja.py -k database_stats -v`
Expected: PASS (widok `database_stats` w `views/base.py:51` liczy przez
`Wydawnictwo_Ciagle.objects` → automatycznie czysty). Nazwę URL i klucze JSON
sprawdź: `grep -rn "database_stats\|type_distribution" src/admin_dashboard/`.
Jeśli fixture `staff_user` nie istnieje, użyj `admin_user` (superuser też
spełnia `staff_member_required`).

- [ ] **Step 6: Commit**

```bash
git add src/admin_dashboard/tests/test_soft_delete_regresja.py
git add src/admin_dashboard/views/charakter_stats.py 2>/dev/null || true
git commit -m "test(soft-delete): regresja dashboard liczniki pomijaja skasowane"
```

---

## Task 11: Pełna suita + ruff

**Files:** (brak nowych — gate jakości)

- [ ] **Step 1: Lint i format na wszystkich nowych plikach**

Run: `ruff format src/bpp/tests/test_soft_delete/ src/pbn_integrator/tests/test_soft_delete_regresja.py src/import_common/tests/test_soft_delete_regresja.py src/ewaluacja_optymalizacja/tests/test_soft_delete_regresja.py src/deduplikator_autorow/tests/test_soft_delete_regresja.py src/api_v1/tests/test_soft_delete_regresja.py src/admin_dashboard/tests/test_soft_delete_regresja.py`
Run: `ruff check src/bpp/tests/test_soft_delete/ src/pbn_integrator/tests/test_soft_delete_regresja.py src/import_common/tests/test_soft_delete_regresja.py src/ewaluacja_optymalizacja/tests/test_soft_delete_regresja.py src/deduplikator_autorow/tests/test_soft_delete_regresja.py src/api_v1/tests/test_soft_delete_regresja.py src/admin_dashboard/tests/test_soft_delete_regresja.py`
Expected: brak błędów (linie ≤88). Napraw ręcznie (Edit), NIE `--fix`.

- [ ] **Step 2: Uruchom całą regresję soft-delete**

Run: `uv run pytest -k soft_delete_regresja -v`
Expected: wszystkie PASS. Każdy FAIL przeanalizuj wg odpowiadającego Tasku —
część FAIL-i to luki w fazach 01–07 (opisane w krokach „oczekuj PASS").

- [ ] **Step 3: Uruchom pełną suitę bez Playwrighta (regresja całego systemu)**

Run: `make tests-without-playwright`
Expected: zielono. To gwarantuje, że wpięcie `SoftDeleteModel` nie zepsuło
istniejących testów cache/PBN/import/ewaluacja/API/dashboard. Jeśli istniejące
testy padają — to regresja wprowadzona w fazach 01–07; zlokalizuj i napraw
w odpowiedniej fazie.

- [ ] **Step 4: Uruchom pełną suitę (do ~10 min, łącznie z Playwright)**

Run: `uv run pytest`
Expected: zielono (timeout ≥600000 ms). Po zieleni — gotowe.

- [ ] **Step 5: Commit (jeśli były poprawki formatowania)**

```bash
git add -A
git commit -m "chore(soft-delete): ruff format/check suity regresji"
```

---

## Self-Review (wykonane przy pisaniu planu)

**Spec coverage (§8 pkt 8 + §9):**
- PBN duplikaty + wycofanie + restore → Task 5. ✅
- Cache/ewaluacja (Rekord/Autorzy/Cache_Punktacja, verify_cache, pinning) →
  Task 1, 2, 7. ✅
- Import bez duplikatów → Task 6. ✅
- Merge autorów (husk odwracalny, PROTECT) → Task 8. ✅
- API nie wycieka → Task 9. ✅
- Dashboard liczniki → Task 10. ✅
- Guardy (autor z pracami, książka-matka, przez admin) → Task 3. ✅
- SoftDeleteLog (delete/restore/hard + user) → Task 4. ✅

**Type/nazewnictwo:** `global_objects`/`objects`/`deleted_objects`,
`Operacja.WYSYLKA`/`WYCOFANIE`, `SoftDeleteLog.Akcja.{DELETE,RESTORE,
HARD_DELETE}`, sygnatura `delete(user=, reason=)` — zgodne z PINNED w
overview (00). Fixture `wydawnictwo_ciagle_z_dwoma_autorami`, `denorms`,
`api_client`, `admin_user`, `zwarte_z_dyscyplinami`,
`pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina` — zweryfikowane w
`src/conftest.py` / `src/fixtures/` / istniejących testach.
