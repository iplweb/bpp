# Soft-delete — Faza 01: `*_Autor` → SoftDeleteModel + widoki źródłowe + trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> ⚠️ **AKTUALIZACJA ZAKRESU (decyzja użytkownika 2026-06-04) — CZYTAJ PRZED STARTEM:**
> 1. **NIE ruszamy funkcji `bpp_refresh_cache()`.** Zmieniamy **wyłącznie widoki
>    źródłowe** (`bpp_*_autorzy`, ew. `bpp_rekord`) — filtr `deleted_at IS NULL`.
>    Każde zadanie tego planu dotyczące **trigger-skip** / modyfikacji kopii
>    `0399` / fixu utajonego buga z krotkami — **POMIŃ** (zostaje równoległej
>    optymalizacji triggera).
> 2. **BLOKER:** funkcja `bpp_refresh_cache()` jest równolegle optymalizowana w
>    osobnej gałęzi. Tej fazy **NIE startować**, dopóki ta gałąź nie wyląduje i
>    `feat/soft-delete` nie zostanie na nią zaktualizowana. Po aktualizacji
>    zweryfikować inwariant: trigger na `UPDATE/INSERT` robi **bezwarunkowy
>    `DELETE` z `_mat` przed re-insertem/upsertem** (na tym wisi wystarczalność
>    filtra widoku). Jeśli inwariant zniknie → dopiero wtedy rozważyć trigger-skip.

**Goal:** Uczynić 3 through-modele `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` modelami `SoftDeleteModel` (przez wspólną bazę `BazaModeluOdpowiedzialnosciAutorow`), dodać im pola `deleted_at`/`restored_at`/`transaction_id` + indeks na `deleted_at`, oraz wpiąć filtr `deleted_at IS NULL` do widoków źródłowych PostgreSQL (`bpp_*_autorzy` + gałęzie UNION `bpp_rekord`) tak, by soft-deletowane autorstwa znikały z materializowanego cache (`bpp_autorzy_mat`, model `Autorzy`) i wracały po `restore`. Opcjonalnie: trigger-skip w `bpp_refresh_cache()`. Faza najwrażliwsza — robiona pierwsza; gwarantuje spójność cache zanim cokolwiek innego (publikacje, admin) zacznie soft-deletować.

**Architecture:** Mechanizm nadrzędny to **filtr widoku (#1)** — każda tabela `bpp_*_autor` ma własną kolumnę `deleted_at`, a widoki źródłowe `bpp_wydawnictwo_ciagle_autorzy` / `bpp_wydawnictwo_zwarte_autorzy` / `bpp_patent_autorzy` (`0001_widoki_autorzy.sql`) dostają `AND <tabela>.deleted_at IS NULL` po **własnej** kolumnie (bez JOIN do rekordu nadrzędnego). To pokrywa WSZYSTKIE ścieżki: re-insert triggera `bpp_refresh_cache()`, bezpośredni odczyt `Rekord`/`RekordView` z widoku `bpp_rekord`, oraz pełną re-projekcję cache. Gałęzie `UNION` w `bpp_rekord` (`0001_widoki_rekord.sql`) per typ publikacji NIE filtrują po `*_autor.deleted_at` (rekord publikacji żyje niezależnie od soft-delete pojedynczego autorstwa — soft-delete publikacji to faza 02), ale dla spójności kontraktu dodajemy filtr `deleted_at IS NULL` na poziomie tabeli autorskiej tylko w widokach `bpp_*_autorzy`. Trigger-skip (#2) to opcjonalna optymalizacja w gałęzi `UPDATE/INSERT` funkcji `bpp_refresh_cache()` (aktualna wersja: `0399_fix_refresh_cache_upsert.sql`): gdy `TD['new']['deleted_at'] is not None` → pomiń upsert (delete-only). Nie zastępuje #1.

**Tech Stack:** Django 4.2, PostgreSQL (`plpython3u` trigger + widoki), `django-soft-delete>=1.0.23` (`SoftDeleteModel`, `SoftDeleteManager`/`GlobalManager`/`DeletedManager`), pytest + model_bakery, `denorm` (django-denorm-iplweb). Python wyłącznie przez `uv run`.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md) (§1, §2.1, §2.2, §8 pkt 1). Indeks: [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md).

**Fakty z kodu (zweryfikowane, NIE zmieniać bez ponownej weryfikacji):**
- `BazaModeluOdpowiedzialnosciAutorow` jest `models.Model` (abstract), `src/bpp/models/abstract/authors.py:16`. Po niej dziedziczą wszystkie 3 through-modele.
- `Wydawnictwo_Ciagle_Autor(DirtyFieldsMixin, BazaModeluOdpowiedzialnosciAutorow)` — `src/bpp/models/wydawnictwo_ciagle.py:52`. FK `rekord` → `Wydawnictwo_Ciagle`, `related_name="autorzy_set"`, `src/bpp/models/wydawnictwo_ciagle.py:58`.
- `Wydawnictwo_Zwarte_Autor(DirtyFieldsMixin, BazaModeluOdpowiedzialnosciAutorow)` — `src/bpp/models/wydawnictwo_zwarte.py:60`. FK `rekord`, `related_name="autorzy_set"`, `:67`.
- `Patent_Autor(BazaModeluOdpowiedzialnosciAutorow)` — `src/bpp/models/patent.py:32`. FK `rekord`, `related_name="autorzy_set"`, `:35`.
- Wszystkie 3 mają `Meta.unique_together` (NIE ruszamy; `deleted_at` nie wchodzi w `unique_together` — autorstwa nie mają warunkowego unique w tej fazie, sług to faza 02).
- `BazaModeluOdpowiedzialnosciAutorow.objects` NIE jest jawnie zdefiniowany → po wpięciu `SoftDeleteModel` domyślne `objects` = `SoftDeleteManager` (z pakietu). Nadpiszemy je naszymi `Bpp*` z `src/bpp/models/soft_delete.py`.
- `SoftDeleteModel.delete()` (pakiet, `django_softdelete/models.py`) robi **refleksyjną kaskadę** po reverse relacjach — dla `*_Autor` reverse relacji do soft-delete dzieci NIE ma (ich dzieci to nie-soft `Autor`/`Jednostka` przez FK forward), więc kaskada jest no-op. `delete()` woła `self.save(update_fields=['deleted_at','restored_at','transaction_id'])` → odpala trigger `bpp_*_autor_cache_trigger` jako `UPDATE`. To jest pożądane.
- Widok `bpp_autorzy_mat` (model `Autorzy`, `src/bpp/models/cache/autorzy.py:39`, `db_table="bpp_autorzy_mat"`) zasilany triggerem z `bpp_autorzy` (UNION `bpp_*_autorzy`).
- Aktualna funkcja triggera to `0399_fix_refresh_cache_upsert.sql` (NIE `0001_cache_functions.sql` — ta jest baseline, nadpisana przez 0399). Trigger-skip dopisujemy do **kopii treści 0399** w nowym pliku SQL.
- `transactional_db` fixture wymagany dla testów dotykających trigger/cache (trigger działa tylko z prawdziwym commitem). Fixture `denorms` (`src/fixtures/conftest_system.py:193`) daje `denorms.flush()`. Fixtury: `wydawnictwo_ciagle_z_dwoma_autorami`, `wydawnictwo_ciagle_z_autorem`, `autor_jan_kowalski`, `jednostka`, `standard_data`, `typy_odpowiedzialnosci`.
- Jedyny liść migracji `bpp`: `0420_autor_pokazuj_siec_powiazan_and_more`. Nowe migracje od niego zależą i są łańcuchowane: `0421 → 0422 (SQL)`.

**Kontrakt z reversion (PINNED):** soft-delete idzie WYŁĄCZNIE per-instancja przez `.delete()`/`.save()` (nigdy `queryset.update(deleted_at=...)`). `BppSoftDeleteQuerySet.update()` to egzekwuje fail-fast (gate). W tej fazie testujemy gate i kaskadę queryset-ową.

---

## Task 1 — Moduł `src/bpp/models/soft_delete.py` (queryset gate + managery)

Tworzy współdzielony fundament menedżerów dla całego wdrożenia. Guard zależności (`raise_if_has_protected_children`) dopisuje faza 04 — tu tylko QuerySet + 3 managery (PINNED z indeksu §39-69).

**Files:**
- Create: `src/bpp/models/soft_delete.py`
- Test (create): `src/bpp/tests/test_soft_delete/__init__.py`, `src/bpp/tests/test_soft_delete/test_managers.py`

**Steps:**

- [ ] Utwórz katalog testowy i pusty `__init__.py`:
  ```bash
  mkdir -p src/bpp/tests/test_soft_delete && touch src/bpp/tests/test_soft_delete/__init__.py
  ```

- [ ] Napisz failing test gate'a `update()` — `src/bpp/tests/test_soft_delete/test_managers.py`:
  ```python
  """Testy menedżerów i queryset-gate'a soft-delete."""

  import pytest

  from bpp.models.soft_delete import (
      BppGlobalManager,
      BppSoftDeleteManager,
      BppSoftDeleteQuerySet,
  )


  def test_queryset_gate_blokuje_deleted_at():
      """update(deleted_at=...) musi rzucić RuntimeError (omija post_save,
      kaskadę *_Autor, SoftDeleteLog i reversion)."""
      from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor

      qs = BppSoftDeleteQuerySet(Wydawnictwo_Ciagle_Autor)
      with pytest.raises(RuntimeError, match="Nie ustawiaj deleted_at"):
          qs.update(deleted_at="2026-06-04")


  def test_queryset_gate_blokuje_restored_at():
      from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor

      qs = BppSoftDeleteQuerySet(Wydawnictwo_Ciagle_Autor)
      with pytest.raises(RuntimeError, match="Nie ustawiaj deleted_at"):
          qs.update(restored_at="2026-06-04")


  def test_queryset_gate_przepuszcza_inne_pola():
      """update() na zwykłym polu działa normalnie (nie rzuca)."""
      from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor

      qs = BppSoftDeleteQuerySet(Wydawnictwo_Ciagle_Autor).none()
      assert qs.update(kolejnosc=5) == 0  # pusty QS, ale nie rzuca


  def test_managery_sa_wlasciwych_klas():
      assert issubclass(BppSoftDeleteManager.__bases__[0].__mro__[0], object)
      assert isinstance(
          BppSoftDeleteManager().get_queryset.__func__.__qualname__, str
      )
  ```

- [ ] Uruchom (oczekiwany FAIL — `ModuleNotFoundError: bpp.models.soft_delete`):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_managers.py -q
  ```

- [ ] Minimalna implementacja — `src/bpp/models/soft_delete.py` (VERBATIM z indeksu §40-69):
  ```python
  """Wspólny fundament soft-delete dla BPP: queryset-gate blokujący bulk
  ustawienie deleted_at/restored_at + managery przepleciające filtr soft-delete
  z naszą podklasą queryset (gate). Guard zależności (PROTECT) dokłada faza 04.
  """

  from django_softdelete.managers import (
      GlobalManager,
      SoftDeleteManager,
      SoftDeleteQuerySet,
  )


  class BppSoftDeleteQuerySet(SoftDeleteQuerySet):
      """Gate: blokuje bulk-ustawienie deleted_at/restored_at przez .update()
      (omijałoby post_save, kaskadę *_Autor, SoftDeleteLog i reversion)."""

      def update(self, **kwargs):
          if "deleted_at" in kwargs or "restored_at" in kwargs:
              raise RuntimeError(
                  "Nie ustawiaj deleted_at/restored_at przez .update() — "
                  "użyj .delete()/.restore(). Bulk update omija post_save, "
                  "kaskadę *_Autor, SoftDeleteLog i reversion."
              )
          return super().update(**kwargs)


  class BppSoftDeleteManager(SoftDeleteManager):
      def get_queryset(self):
          return BppSoftDeleteQuerySet(self.model, using=self._db).filter(
              deleted_at__isnull=True
          )


  class BppGlobalManager(GlobalManager):
      def get_queryset(self):
          return BppSoftDeleteQuerySet(self.model, using=self._db)
  ```

- [ ] Uruchom (oczekiwany PASS):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_managers.py -q
  ```

- [ ] Commit:
  ```bash
  git add src/bpp/models/soft_delete.py src/bpp/tests/test_soft_delete/
  git commit -m "feat(soft-delete): moduł soft_delete.py — gate na update() + managery

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 2 — `BazaModeluOdpowiedzialnosciAutorow` dziedziczy `SoftDeleteModel` + migracja pól

Wpięcie `SoftDeleteModel` w abstrakcyjną bazę → Django doda `deleted_at`/`restored_at`/`transaction_id` do WSZYSTKICH 3 konkretnych tabel `*_autor`. Nadpisujemy managery (`objects`/`global_objects`/`deleted_objects`) naszymi `Bpp*` z Task 1, żeby gate był aktywny. Migracja dodaje 3 pola × 3 tabele + indeks na `deleted_at` × 3.

**Files:**
- Modify: `src/bpp/models/abstract/authors.py:16` (deklaracja klasy + managery), import `:1-13`.
- Create: `src/bpp/migrations/0421_autor_soft_delete_fields.py`
- Test (create): `src/bpp/tests/test_soft_delete/test_autor_softdelete_model.py`

**Steps:**

- [ ] Napisz failing test — `src/bpp/tests/test_soft_delete/test_autor_softdelete_model.py`:
  ```python
  """*_Autor jako SoftDeleteModel: pola, managery, soft-delete/restore per
  instancja (bez sprawdzania cache — to Task 4)."""

  import pytest
  from django_softdelete.models import SoftDeleteModel

  from bpp.models.patent import Patent_Autor
  from bpp.models.soft_delete import BppGlobalManager, BppSoftDeleteManager
  from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
  from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor

  THROUGH_MODELE = [
      Wydawnictwo_Ciagle_Autor,
      Wydawnictwo_Zwarte_Autor,
      Patent_Autor,
  ]


  @pytest.mark.parametrize("klass", THROUGH_MODELE)
  def test_through_jest_softdeletemodel(klass):
      assert issubclass(klass, SoftDeleteModel)


  @pytest.mark.parametrize("klass", THROUGH_MODELE)
  def test_through_ma_pola_soft_delete(klass):
      nazwy = {f.name for f in klass._meta.get_fields()}
      assert {"deleted_at", "restored_at", "transaction_id"} <= nazwy


  @pytest.mark.parametrize("klass", THROUGH_MODELE)
  def test_through_ma_nasze_managery(klass):
      assert isinstance(klass.objects, BppSoftDeleteManager)
      assert isinstance(klass.global_objects, BppGlobalManager)


  @pytest.mark.django_db
  def test_soft_delete_ukrywa_w_objects_widoczne_w_global(
      wydawnictwo_ciagle_z_autorem,
  ):
      wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
      pk = wca.pk
      wca.delete()
      assert not Wydawnictwo_Ciagle_Autor.objects.filter(pk=pk).exists()
      assert Wydawnictwo_Ciagle_Autor.global_objects.filter(pk=pk).exists()
      assert Wydawnictwo_Ciagle_Autor.deleted_objects.filter(pk=pk).exists()


  @pytest.mark.django_db
  def test_restore_przywraca_do_objects(wydawnictwo_ciagle_z_autorem):
      wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
      pk = wca.pk
      wca.delete()
      Wydawnictwo_Ciagle_Autor.global_objects.get(pk=pk).restore()
      assert Wydawnictwo_Ciagle_Autor.objects.filter(pk=pk).exists()
  ```

- [ ] Uruchom (oczekiwany FAIL — `test_through_jest_softdeletemodel`: brak `SoftDeleteModel` w MRO; brak pól):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_autor_softdelete_model.py -q
  ```

- [ ] Zmodyfikuj import w `src/bpp/models/abstract/authors.py` — dodaj po linii `from django.db.models import CASCADE, SET_NULL, Q, Sum` (`:10`):
  ```python
  from django_softdelete.models import SoftDeleteModel

  from bpp.models.soft_delete import (
      BppGlobalManager,
      BppSoftDeleteManager,
  )
  from django_softdelete.managers import DeletedManager
  ```
  (UWAGA na cykl importów: `soft_delete.py` nie importuje modeli BPP, więc bezpieczne. `authors.py` już importuje z `bpp.models.dyscyplina_naukowa` — kolejność OK.)

- [ ] Zmień deklarację klasy `src/bpp/models/abstract/authors.py:16` z:
  ```python
  class BazaModeluOdpowiedzialnosciAutorow(models.Model):
  ```
  na:
  ```python
  class BazaModeluOdpowiedzialnosciAutorow(SoftDeleteModel):
  ```

- [ ] Dodaj jawne managery w ciele klasy `BazaModeluOdpowiedzialnosciAutorow`, tuż przed `class Meta:` (`:92`). Wstaw przed linią `    class Meta:`:
  ```python
      # Nadpisujemy managery pakietu naszymi (gate na update()).
      # Kolejność: pierwszy zdefiniowany manager = _default_manager.
      objects = BppSoftDeleteManager()
      global_objects = BppGlobalManager()
      deleted_objects = DeletedManager()

  ```

- [ ] Uruchom `makemigrations` — wygeneruje migrację dla 3 konkretnych modeli:
  ```bash
  uv run python src/manage.py makemigrations bpp --name autor_soft_delete_fields
  ```
  (Spodziewany plik: `src/bpp/migrations/0421_autor_soft_delete_fields.py`, 3 pola × 3 modele = 9 `AddField`. Manager-y są `use_in_migrations=False` domyślnie, więc nie pojawią się w migracji.)

- [ ] Zweryfikuj treść wygenerowanej migracji — musi zawierać `AddField` `deleted_at`/`restored_at`/`transaction_id` dla `wydawnictwo_ciagle_autor`, `wydawnictwo_zwarte_autor`, `patent_autor`. Jeśli Django dorzuciło `AlterModelManagers` — usuń tę operację ręcznie (Edit), bo managery soft-delete nie idą do schematu. Dependency MUSI być `("bpp", "0420_autor_pokazuj_siec_powiazan_and_more")`.

- [ ] Dodaj indeks na `deleted_at` do każdej z 3 tabel. Dopisz do `operations` w `0421_autor_soft_delete_fields.py` (po `AddField`-ach), używając `AddIndex`:
  ```python
          migrations.AddIndex(
              model_name="wydawnictwo_ciagle_autor",
              index=models.Index(
                  fields=["deleted_at"],
                  name="wc_autor_deleted_at_idx",
              ),
          ),
          migrations.AddIndex(
              model_name="wydawnictwo_zwarte_autor",
              index=models.Index(
                  fields=["deleted_at"],
                  name="wz_autor_deleted_at_idx",
              ),
          ),
          migrations.AddIndex(
              model_name="patent_autor",
              index=models.Index(
                  fields=["deleted_at"],
                  name="patent_autor_deleted_at_idx",
              ),
          ),
  ```
  (Nazwy indeksów ≤ 30 znaków — wymóg PostgreSQL/Django. Jeśli `makemigrations` samo dodało `Meta.indexes` przez zmianę modelu — nie dublować; w tej fazie indeks definiujemy WYŁĄCZNIE w migracji, bo `Meta.indexes` w abstrakcyjnej bazie dałby kolizję nazw między 3 tabelami.)

- [ ] Uruchom `makemigrations --check` (oczekiwane: brak nowych zmian — model i migracja zgodne):
  ```bash
  uv run python src/manage.py makemigrations bpp --check --dry-run
  ```

- [ ] Uruchom test (oczekiwany PASS):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_autor_softdelete_model.py -q
  ```

- [ ] Sanity: czy nie rozjechały się inne testy modeli/adminu autorstwa (manager `objects` zmienił klasę):
  ```bash
  uv run pytest src/bpp/tests/test_cache/ -q
  ```
  (Oczekiwany PASS — filtr `deleted_at__isnull=True` na świeżych danych = no-op.)

- [ ] Commit:
  ```bash
  git add src/bpp/models/abstract/authors.py src/bpp/migrations/0421_autor_soft_delete_fields.py src/bpp/tests/test_soft_delete/test_autor_softdelete_model.py
  git commit -m "feat(soft-delete): *_Autor → SoftDeleteModel + migracja pól deleted_at + indeks

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 3 — Migracja SQL: filtr `deleted_at IS NULL` w widokach `bpp_*_autorzy` + trigger-skip

Przedefiniowanie 3 widoków źródłowych (`bpp_wydawnictwo_ciagle_autorzy`, `bpp_wydawnictwo_zwarte_autorzy`, `bpp_patent_autorzy`) z filtrem po **własnej** kolumnie `deleted_at` tabeli `*_autor` (mechanizm #1, obowiązkowy). Po `DROP ... CASCADE` widoku `bpp_*_autorzy` trzeba odtworzyć też zależny `bpp_autorzy` (UNION). Dodatkowo trigger-skip (#2, opcjonalny) — przedefiniowanie `bpp_refresh_cache()` na bazie 0399 z regułą „deleted_at NOT NULL → delete-only". Migracja ładuje plik `.sql` wzorcem `0399`.

**Files:**
- Create: `src/bpp/migrations/0422_soft_delete_views.sql`
- Create: `src/bpp/migrations/0422_soft_delete_views.py`
- Test: pokrycie w Task 4 (testy spójności cache) — tu tylko migracja stosuje się czysto.

**Steps:**

- [ ] Napisz failing test smoke — dopisz do `src/bpp/tests/test_soft_delete/test_views_sql.py`:
  ```python
  """Widoki źródłowe bpp_*_autorzy filtrują po własnym deleted_at."""

  import pytest
  from django.db import connection


  WIDOKI = [
      "bpp_wydawnictwo_ciagle_autorzy",
      "bpp_wydawnictwo_zwarte_autorzy",
      "bpp_patent_autorzy",
  ]


  @pytest.mark.django_db
  @pytest.mark.parametrize("widok", WIDOKI)
  def test_widok_zrodlowy_ma_filtr_deleted_at(widok):
      """Definicja widoku w pg_get_viewdef musi zawierać 'deleted_at'
      (filtr po własnej kolumnie tabeli autorskiej)."""
      with connection.cursor() as cur:
          cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
          defn = cur.fetchone()[0]
      assert "deleted_at" in defn, f"{widok} nie filtruje po deleted_at"
  ```

- [ ] Uruchom (oczekiwany FAIL — widoki jeszcze bez `deleted_at`):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_views_sql.py -q
  ```

- [ ] Utwórz `src/bpp/migrations/0422_soft_delete_views.sql`. Treść = 3 widoki `bpp_*_autorzy` z dodanym `AND <tabela>.deleted_at IS NULL`, odtworzenie `bpp_autorzy` (UNION, bo `DROP CASCADE` go skasuje), oraz przedefiniowanie `bpp_refresh_cache()` skopiowane z `0399_fix_refresh_cache_upsert.sql` z dopisanym trigger-skip w gałęzi `UPDATE/INSERT`:
  ```sql
  BEGIN;

  -- ── Mechanizm #1 (OBOWIĄZKOWY): filtr deleted_at w widokach źródłowych ──
  -- Po DROP ... CASCADE widoku bpp_*_autorzy znika też zależny bpp_autorzy,
  -- więc odtwarzamy go niżej. Filtr po WŁASNEJ kolumnie deleted_at tabeli
  -- autorskiej (bez JOIN do rekordu nadrzędnego) — patrz spec §2.1.

  DROP VIEW IF EXISTS bpp_wydawnictwo_ciagle_autorzy CASCADE;
  CREATE OR REPLACE VIEW bpp_wydawnictwo_ciagle_autorzy AS
    select
      django_content_type.id::text || '_' || rekord_id::text || '_' || autor_id::text || '_' || typ_odpowiedzialnosci_id::text || '_' || kolejnosc::text AS fake_id,
      django_content_type.id::text || '_' || rekord_id::text AS fake_rekord_id,
      django_content_type.id AS content_type_id,
      rekord_id as object_id,
      autor_id,
      jednostka_id,
      kolejnosc,
      typ_odpowiedzialnosci_id,
      zapisany_jako
    from bpp_wydawnictwo_ciagle_autor, django_content_type
    WHERE django_content_type.model = 'wydawnictwo_ciagle'
      AND django_content_type.app_label = 'bpp'
      AND bpp_wydawnictwo_ciagle_autor.deleted_at IS NULL;

  DROP VIEW IF EXISTS bpp_wydawnictwo_zwarte_autorzy CASCADE;
  CREATE OR REPLACE VIEW bpp_wydawnictwo_zwarte_autorzy AS
    select
      django_content_type.id::text || '_' || rekord_id::text || '_' || autor_id::text || '_' || typ_odpowiedzialnosci_id::text || '_' || kolejnosc::text AS fake_id,
      django_content_type.id::text || '_' || rekord_id::text AS fake_rekord_id,
      django_content_type.id AS content_type_id,
      rekord_id as object_id,
      autor_id,
      jednostka_id,
      kolejnosc,
      typ_odpowiedzialnosci_id,
      zapisany_jako
    from bpp_wydawnictwo_zwarte_autor, django_content_type
    WHERE django_content_type.model = 'wydawnictwo_zwarte'
      AND django_content_type.app_label = 'bpp'
      AND bpp_wydawnictwo_zwarte_autor.deleted_at IS NULL;

  DROP VIEW IF EXISTS bpp_patent_autorzy CASCADE;
  CREATE OR REPLACE VIEW bpp_patent_autorzy AS
    select
      django_content_type.id::text || '_' || rekord_id::text || '_' || autor_id::text || '_' || typ_odpowiedzialnosci_id::text || '_' || kolejnosc::text AS fake_id,
      django_content_type.id::text || '_' || rekord_id::text AS fake_rekord_id,
      django_content_type.id AS content_type_id,
      rekord_id as object_id,
      autor_id,
      jednostka_id,
      kolejnosc,
      typ_odpowiedzialnosci_id,
      zapisany_jako
    from bpp_patent_autor, django_content_type
    WHERE django_content_type.model = 'patent'
      AND django_content_type.app_label = 'bpp'
      AND bpp_patent_autor.deleted_at IS NULL;

  -- Odtworzenie UNION bpp_autorzy (skasowany przez DROP ... CASCADE powyżej).
  -- bpp_praca_doktorska_autorzy / bpp_praca_habilitacyjna_autorzy NIE były
  -- ruszane (autorstwo doktoratu/habilitacji nie jest *_Autor SoftDeleteModel
  -- w tej fazie) — wciąż istnieją, więc UNION je dociągnie.
  DROP VIEW IF EXISTS bpp_autorzy;
  CREATE VIEW bpp_autorzy AS
    SELECT * FROM bpp_wydawnictwo_ciagle_autorzy
      UNION
        SELECT * FROM bpp_wydawnictwo_zwarte_autorzy
          UNION
            SELECT * FROM bpp_patent_autorzy
              UNION
                SELECT * FROM bpp_praca_doktorska_autorzy
                  UNION
                    SELECT * FROM bpp_praca_habilitacyjna_autorzy;

  -- ── Mechanizm #2 (OPCJONALNY): trigger-skip w bpp_refresh_cache() ──
  -- Kopia 0399_fix_refresh_cache_upsert.sql z jedną zmianą: w gałęzi
  -- UPDATE/INSERT, gdy nowy wiersz ma deleted_at IS NOT NULL, pomijamy upsert
  -- (zostaje samo DELETE z _mat). Filtr widoku #1 i tak pokrywa odczyt, ale to
  -- oszczędza no-op SELECT/INSERT przy kaskadzie soft-delete na *_Autor.
  CREATE OR REPLACE FUNCTION bpp_refresh_cache()
    RETURNS TRIGGER
    LANGUAGE plpython3u
    AS $$
      cache_key = "django_content_type_ver_1"
      columns_cache_key = "table_columns_ver_1"
      table_name = TD["table_name"]
      app_name, model_name = table_name.split("_", 1)

      refresh_rekord = True
      refresh_autor = False

      trigger_field_name = "new"
      if TD['event'] in ["DELETE", "UPDATE"]:
          trigger_field_name = "old"

      TABELE_AUTORSKIE = ['bpp_wydawnictwo_ciagle_autor', 'bpp_wydawnictwo_zwarte_autor', 'bpp_patent_autor']
      id_field_name = 'id'
      extra_where = ''
      if table_name in TABELE_AUTORSKIE:
          id_field_name = 'rekord_id'
          model_name = model_name.replace("_autor", "")
          refresh_autor = True
          refresh_rekord = False
          extra_where = ' AND autor_id = %s' % TD[trigger_field_name]['autor_id']

      object_id = TD[trigger_field_name][id_field_name]

      if GD.get(cache_key) is None:
          GD[cache_key] = {}

      if GD.get(columns_cache_key) is None:
          GD[columns_cache_key] = {}

      try:
          content_type_id = GD[cache_key][table_name]
      except KeyError:
          query = "SELECT id FROM django_content_type WHERE app_label = '%s' AND model = '%s'" % (app_name, model_name)
          res = plpy.execute(query)
          GD[cache_key][table_name] = res[0]['id']
          content_type_id = GD[cache_key][table_name]

      if TD["table_name"] in ["bpp_praca_doktorska", "bpp_praca_habilitacyjna"]:
          refresh_autor = True

      where = "WHERE %%s = ARRAY[%s, %s]::INTEGER[2]" % (content_type_id, object_id)
      where += extra_where

      # ── trigger-skip: soft-delete (UPDATE z deleted_at IS NOT NULL) ──
      # zachowuje się jak DELETE (samo wyczyszczenie _mat, bez re-insertu).
      skip_reinsert = (
          TD["event"] in ["UPDATE", "INSERT"]
          and TD["new"] is not None
          and TD["new"].get("deleted_at") is not None
      )

      refresh_tables = []
      if refresh_rekord:
          refresh_tables.append(("bpp_rekord_mat", "id"))
          refresh_tables.append(("bpp_autorzy_mat", "rekord_id"))
      if refresh_autor:
          if "bpp_autorzy_mat" not in [t for t, _ in refresh_tables]:
              refresh_tables.append(("bpp_autorzy_mat", "rekord_id"))

      def get_table_columns(mat_table):
          if mat_table not in GD[columns_cache_key]:
              query = """
                  SELECT column_name
                  FROM information_schema.columns
                  WHERE table_schema = 'public'
                  AND table_name = '%s'
                  ORDER BY ordinal_position
              """ % mat_table
              res = plpy.execute(query)
              GD[columns_cache_key][mat_table] = [row['column_name'] for row in res]
          return GD[columns_cache_key][mat_table]

      def get_unique_constraint_column(mat_table):
          return "id"

      with plpy.subtransaction():
          for table, id_col in refresh_tables:
            lock_key = hash(f"{table}_{content_type_id}_{object_id}") % (2**31)
            plpy.execute(f"SELECT pg_advisory_xact_lock({lock_key})")

            if TD["event"] == "DELETE" or skip_reinsert:
                query = "DELETE FROM " + table + " " + (where % id_col)
                plpy.execute(query)
            elif TD["event"] in ["UPDATE", "INSERT"]:
                source_view = table.replace("_mat", "")
                columns = get_table_columns(table)
                conflict_col = get_unique_constraint_column(table)
                columns_str = ", ".join(columns)
                update_columns = [col for col in columns if col != conflict_col]
                set_clause = ", ".join([f"{col} = EXCLUDED.{col}" for col in update_columns])
                delete_query = "DELETE FROM " + table + " " + (where % id_col)
                plpy.execute(delete_query)
                select_query = f"SELECT {columns_str} FROM {source_view} " + (where % id_col)
                upsert_query = f"""
                    INSERT INTO {table} ({columns_str})
                    {select_query}
                    ON CONFLICT ({conflict_col}) DO UPDATE SET {set_clause}
                """
                plpy.execute(upsert_query)
  $$;

  COMMIT;
  ```
  (UWAGA: `refresh_tables` w 0399 to lista krotek `(table, id_col)`, więc sprawdzenie `"bpp_autorzy_mat" not in refresh_tables` z 0399 było błędne dla krotek — tu poprawiamy na `not in [t for t, _ in refresh_tables]`. Reszta logiki 1:1 z 0399.)

- [ ] Utwórz `src/bpp/migrations/0422_soft_delete_views.py` (wzorzec `0399`):
  ```python
  from pathlib import Path

  from django.db import connection, migrations


  def load_sql(apps, schema_editor):
      sql_file = Path(__file__).parent / "0422_soft_delete_views.sql"
      with open(sql_file) as f:
          sql = f.read()
      # connection.cursor() zamiast schema_editor.execute(): schema_editor
      # interpretuje %s jako placeholdery parametrów (a w plpython3u są %s
      # w stringach SQL budowanych ręcznie).
      with connection.cursor() as cursor:
          cursor.execute(sql)


  class Migration(migrations.Migration):

      dependencies = [
          ("bpp", "0421_autor_soft_delete_fields"),
      ]

      operations = [
          migrations.RunPython(load_sql, migrations.RunPython.noop),
      ]
  ```

- [ ] Uruchom test smoke (oczekiwany PASS — migracja zastosuje się przy starcie testowej bazy, widoki będą miały `deleted_at`):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_views_sql.py -q
  ```

- [ ] Zweryfikuj brak driftu migracji i czystość modeli:
  ```bash
  uv run python src/manage.py makemigrations bpp --check --dry-run
  ```

- [ ] Commit:
  ```bash
  git add src/bpp/migrations/0422_soft_delete_views.sql src/bpp/migrations/0422_soft_delete_views.py src/bpp/tests/test_soft_delete/test_views_sql.py
  git commit -m "feat(soft-delete): filtr deleted_at w widokach bpp_*_autorzy + trigger-skip

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 4 — Testy spójności cache (mat-view) po soft-delete `*_Autor`

Główny gejt fazy: soft-delete wiersza `*_Autor` → znika z `bpp_autorzy_mat` (model `Autorzy`) i z `bpp_autorzy` (model `AutorzyView`); restore → wraca; edycja autorstwa skasowanej publikacji nie wskrzesza wiersza w cache; kaskada queryset-owa (`.delete()` na QS) działa per-instancja. Testy wymagają `transactional_db` (trigger działa tylko z prawdziwym commitem).

**Files:**
- Test (create): `src/bpp/tests/test_soft_delete/test_cache_consistency.py`
- Modify (jeśli testy ujawnią drift): brak planowanych — testy mają przejść na implementacji z Task 2-3.

**Steps:**

- [ ] Napisz testy spójności — `src/bpp/tests/test_soft_delete/test_cache_consistency.py`:
  ```python
  """Spójność materializowanego cache (bpp_autorzy_mat / model Autorzy) po
  soft-delete wierszy *_Autor. Wymaga transactional_db — trigger plpython3u
  odpala się dopiero przy realnym commicie."""

  import pytest

  from bpp.models.cache import Autorzy, AutorzyView
  from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor


  def _autorzy_mat_dla(wca):
      """Wiersze bpp_autorzy_mat (model Autorzy) wskazujące na danego autora
      w danym rekordzie."""
      return Autorzy.objects.filter(
          autor_id=wca.autor_id,
          rekord_id=[wca.rekord.content_type_id, wca.rekord_id],
      )


  def test_soft_delete_autorstwa_znika_z_mat(
      transactional_db, denorms, wydawnictwo_ciagle_z_dwoma_autorami
  ):
      wc = wydawnictwo_ciagle_z_dwoma_autorami
      denorms.flush()
      wca = wc.autorzy_set.first()
      autor_id = wca.autor_id

      # Przed: autor jest w bpp_autorzy_mat
      assert Autorzy.objects.filter(autor_id=autor_id).exists()
      # ... i w bpp_autorzy (widok źródłowy)
      assert AutorzyView.objects.filter(autor_id=autor_id).exists()

      wca.delete()  # soft-delete per instancja

      # Po: znika z mat-view (trigger + filtr widoku) ...
      assert not Autorzy.objects.filter(autor_id=autor_id).exists()
      # ... i z widoku źródłowego (mechanizm #1)
      assert not AutorzyView.objects.filter(autor_id=autor_id).exists()
      # Drugi autor pracy NIE zniknął
      assert Autorzy.objects.filter(rekord_id__isnull=False).exists()


  def test_restore_autorstwa_wraca_do_mat(
      transactional_db, denorms, wydawnictwo_ciagle_z_autorem
  ):
      wc = wydawnictwo_ciagle_z_autorem
      denorms.flush()
      wca = wc.autorzy_set.first()
      autor_id = wca.autor_id
      pk = wca.pk

      wca.delete()
      assert not Autorzy.objects.filter(autor_id=autor_id).exists()

      Wydawnictwo_Ciagle_Autor.global_objects.get(pk=pk).restore()

      # Restore → re-insert do mat-view
      assert Autorzy.objects.filter(autor_id=autor_id).exists()
      assert AutorzyView.objects.filter(autor_id=autor_id).exists()


  def test_edycja_skasowanego_autorstwa_nie_wskrzesza_w_mat(
      transactional_db, denorms, wydawnictwo_ciagle_z_autorem
  ):
      """Zapis skasowanego wiersza *_Autor (np. zmiana kolejnosc) NIE wraca
      do bpp_autorzy_mat — widok źródłowy go odfiltrowuje po własnym
      deleted_at (mechanizm #1)."""
      wc = wydawnictwo_ciagle_z_autorem
      denorms.flush()
      wca = wc.autorzy_set.first()
      autor_id = wca.autor_id
      pk = wca.pk

      wca.delete()
      assert not Autorzy.objects.filter(autor_id=autor_id).exists()

      # Edycja skasowanego wiersza (przez global_objects, bo objects ukrywa)
      skasowany = Wydawnictwo_Ciagle_Autor.global_objects.get(pk=pk)
      skasowany.kolejnosc = 99
      skasowany.save()  # odpala trigger jako UPDATE z deleted_at NOT NULL

      # Nadal nie ma go w mat-view (kluczowy przypadek brzegowy ze spec §2.1)
      assert not Autorzy.objects.filter(autor_id=autor_id).exists()


  def test_queryset_delete_kaskaduje_per_instancja(
      transactional_db, denorms, wydawnictwo_ciagle_z_dwoma_autorami
  ):
      """.delete() na QuerySet soft-deletuje per instancję (iterator) —
      wszystkie wiersze znikają z mat-view, gate update() nie blokuje QS-delete."""
      wc = wydawnictwo_ciagle_z_dwoma_autorami
      denorms.flush()
      assert Autorzy.objects.count() >= 2

      Wydawnictwo_Ciagle_Autor.objects.filter(rekord=wc).delete()

      # Wszystkie autorstwa tej pracy zniknęły z mat-view
      assert not Autorzy.objects.filter(
          rekord_id=[wc.content_type_id, wc.pk]
      ).exists()
      # ... ale wiersze fizycznie żyją (soft, nie hard)
      assert Wydawnictwo_Ciagle_Autor.global_objects.filter(rekord=wc).count() >= 2
  ```

- [ ] Uruchom (oczekiwany PASS — implementacja z Task 2+3 pokrywa wszystkie ścieżki):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_cache_consistency.py -q
  ```
  Jeśli `test_edycja_skasowanego_autorstwa_nie_wskrzesza_w_mat` FAIL → znaczy, że trigger-skip lub filtr widoku nie działa. Diagnoza: sprawdź `pg_get_viewdef('bpp_wydawnictwo_ciagle_autorzy')` (czy `deleted_at IS NULL` obecne) — to obowiązkowy mechanizm #1; trigger-skip sam nie wystarcza dla tej ścieżki (potwierdza spec §2.1). Użyj superpowers:systematic-debugging, NIE łataj testu.

- [ ] Commit:
  ```bash
  git add src/bpp/tests/test_soft_delete/test_cache_consistency.py
  git commit -m "test(soft-delete): spójność bpp_autorzy_mat po soft-delete/restore *_Autor

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 5 — Weryfikacja całości fazy (ruff + regresja cache/autorstwa)

Gejt zamykający fazę: lint czysty, brak driftu migracji, testy cache + admin autorstwa + API nie regresują przez zmianę domyślnego managera `objects` na `BppSoftDeleteManager`.

**Files:** brak (tylko uruchomienia).

**Steps:**

- [ ] Lint i format (NIE używaj `--fix`; fixy ręczne przez Edit):
  ```bash
  ruff format src/bpp/models/soft_delete.py src/bpp/models/abstract/authors.py src/bpp/tests/test_soft_delete/
  ruff check src/bpp/models/soft_delete.py src/bpp/models/abstract/authors.py src/bpp/tests/test_soft_delete/
  ```

- [ ] Brak driftu migracji:
  ```bash
  uv run python src/manage.py makemigrations --check --dry-run
  ```

- [ ] Pełna regresja podsystemów dotkniętych zmianą managera `*_Autor.objects` (cache, admin, API autorstwa). To wyłapie ewentualne miejsca, gdzie kod zakładał, że `objects` zwraca też „skasowane" (w tej fazie nic nie jest skasowane na świeżych fixtach → musi przejść):
  ```bash
  uv run pytest src/bpp/tests/test_cache/ src/bpp/tests/test_soft_delete/ src/api_v1/ -q
  ```

- [ ] Jeśli wszystko zielone — faza 01 gotowa. Commit jeśli ruff coś poprawił:
  ```bash
  git add -A
  git commit -m "chore(soft-delete): ruff + weryfikacja regresji fazy 01

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Założenia i ostrzeżenia między-fazowe (dla faz 02+)

1. **Domyślny manager `*_Autor.objects` zmienił klasę** na `BppSoftDeleteManager` (filtruje `deleted_at__isnull=True`). Faza 03 (audyt kat. B) MUSI przejść 90 miejsc `*_Autor.objects` — w fazie 01 nic nie jest skasowane, więc filtr jest no-op, ale od fazy 02 (kaskada soft-delete publikacji) zacznie ukrywać. Guard autora (faza 04) MUSI liczyć przez `global_objects` (spec §3.2).
2. **Trigger-skip oparty na 0399**, nie 0001. Każda przyszła zmiana `bpp_refresh_cache()` musi wychodzić od `0422_soft_delete_views.sql` (nie od 0399 ani 0001). Naprawiono przy okazji błąd `"bpp_autorzy_mat" not in refresh_tables` (lista krotek) z 0399 — zweryfikować, czy 0399 faktycznie nie dublował `bpp_autorzy_mat` (jeśli dublował, to drobny regres wydajności, nie poprawności).
3. **Widoki `bpp_praca_doktorska_autorzy` / `bpp_praca_habilitacyjna_autorzy` NIE filtrowane** — autorstwo doktoratu/habilitacji nie jest `*_Autor` SoftDeleteModel (autor doktoratu to FK `Praca_Doktorska.autor`, nie through). Faza 02 (soft-delete publikacji doktorat/habilitacja) musi zadbać o ich zniknięcie z `bpp_rekord` przez własne `deleted_at` na tabeli publikacji — to NIE jest pokryte tą fazą.
4. **Gałęzie UNION `bpp_rekord` NIE dotknięte** w fazie 01 — soft-delete publikacji (kolumna `deleted_at` na `bpp_wydawnictwo_ciagle` itd.) to faza 02; dopiero ona doda filtr `deleted_at IS NULL` do `bpp_*_view`. Faza 01 dotyka wyłącznie ścieżki autorstwa.
5. **`unique_together` na `*_Autor` zachowane bez `deleted_at`** — w tej fazie autorstwa nie mają warunkowego unique. Jeśli przyszła faza pozwoli na re-add tego samego autora po soft-delete (kolizja `(rekord, autor, typ_odpowiedzialnosci)`), trzeba będzie przejść na `UniqueConstraint(condition=Q(deleted_at__isnull=True))` — odłożone, poza zakresem 01.
