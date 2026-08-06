# Soft-delete — Faza 01: `*_Autor` → SoftDeleteModel + widoki źródłowe + trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> 🔄 **AKTUALIZACJA ZAKRESU 2026-08-06 — CZYTAJ PRZED STARTEM. Zastępuje
> poprzedni box „decyzja użytkownika 2026-06-04".**
>
> **BLOKER ZDJĘTY.** Optymalizacja triggera wylądowała (PR #363, migracje
> `0421`/`0429`/`0432`/`0433`), gałąź jest zrebasowana na `dev`.
>
> **Ale inwariant, o który pytał poprzedni box, NIE przetrwał** — i to
> ROZSZERZA tę fazę. Zweryfikowane empirycznie
> (`src/bpp/tests/test_cache/test_soft_delete_preconditions.py`, oba kanarki
> zielone na obecnym kodzie):
> 1. funkcja refresh to **czysty upsert bez `DELETE`** → odfiltrowanie wiersza
>    z widoku daje **no-op**, stary wiersz przeżywa w `_mat`;
> 2. **bramka `WHEN`** (migracja `0433`) nie zna `deleted_at`, a
>    `django-soft-delete` zapisuje przez `save(update_fields=[...])` → UPDATE
>    soft-delete **w ogóle nie dochodzi do funkcji triggera**.
>
> **Filtr widoku sam NIE wystarcza.** Ta faza robi trzy rzeczy, nie jedną —
> patrz „Architecture" niżej. Wszystkie obowiązkowe.

**Goal:** Uczynić 3 through-modele `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` modelami `SoftDeleteModel` (przez mixin `BppAutorstwoSoftDeleteMixin` wpinany w **3 KONKRETNE** klasy — NIE w abstrakt `BazaModeluOdpowiedzialnosciAutorow`, patrz Task 2), dodać im pola `deleted_at`/`restored_at`/`transaction_id` + indeks na `deleted_at`, i doprowadzić do tego, by soft-deletowane autorstwa **znikały** z materializowanego cache (`bpp_autorzy_mat`, model `Autorzy`) i **wracały** po `restore`. Faza najwrażliwsza — robiona pierwsza; gwarantuje spójność cache zanim cokolwiek innego (publikacje, admin) zacznie soft-deletować.

**Architecture — trzy elementy, wszystkie obowiązkowe** (żaden nie wystarcza sam; uzasadnienie: §2.1 specu):

1. **Filtr `deleted_at IS NULL` w widokach źródłowych** `bpp_wydawnictwo_ciagle_autorzy` / `bpp_wydawnictwo_zwarte_autorzy` / `bpp_patent_autorzy` — po **własnej** kolumnie tabeli `*_autor` (bez JOIN do rekordu nadrzędnego). Rola: (a) karmi `pg_depend` dla punktu 3, (b) chroni pełne przebudowy i odczyt przez `bpp_autorzy`. **Nie sprząta `_mat`** — to robi punkt 2.
2. **Gałąź kasująca w 3 funkcjach `bpp_refresh_autor_<model>()`** (`0432_cache_trigger_plpgsql.py`): prolog `IF NEW.deleted_at IS NOT NULL THEN DELETE FROM bpp_autorzy_mat WHERE id = ARRAY[ct, NEW.id]::integer[]; RETURN NULL; END IF;`. Wzorzec jest już w kodzie — gałąź doktorat/habilitacja w `_create_rekord_function` robi dokładnie `DELETE` + `INSERT`, bo tam wiersz też może wypaść ze źródła. Restore (`deleted_at → NULL`) przechodzi dalej do normalnego upsertu — symetria za darmo.
3. **Regeneracja bramki `WHEN`** na 3 triggerach `*_cache_upd` — `RunPython` wołający logikę `forward()` z `0433_cache_trigger_when_gate.py`. `deleted_at` wejdzie do bramki **sama**, przez `pg_depend`, bo punkt 1 wstawił ją do `WHERE` widoku. **Kolejność w migracji: punkt 1 → punkt 3** (bramka czyta definicję widoku).

Gałęzie `UNION` w `bpp_rekord` per typ publikacji NIE filtrują po `*_autor.deleted_at` — rekord publikacji żyje niezależnie od soft-delete pojedynczego autorstwa (soft-delete publikacji to faza 02).

**Tech Stack:** Django 4.2, PostgreSQL (triggery **PL/pgSQL** + widoki), `django-soft-delete>=1.0.23` (`SoftDeleteModel`, `SoftDeleteManager`/`GlobalManager`/`DeletedManager`), pytest + model_bakery, `denorm` (django-denorm-iplweb). Python wyłącznie przez `uv run`.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md) (§1, §2.1, §2.2, §8 pkt 1). Indeks: [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md).

**Fakty z kodu (zweryfikowane, NIE zmieniać bez ponownej weryfikacji):**
- `BazaModeluOdpowiedzialnosciAutorow` jest `models.Model` (abstract), `src/bpp/models/abstract/authors.py:19`. ⚠️ Dziedziczą po niej **CZTERY** modele: 3 through-modele publikacji **oraz** `Zgloszenie_Publikacji_Autor` (`src/zglos_publikacje/models.py:315`) — ten ostatni jest POZA zakresem soft-delete. Dlatego NIE ruszamy abstraktu (Task 2).
- `Wydawnictwo_Ciagle_Autor(DirtyFieldsMixin, BazaModeluOdpowiedzialnosciAutorow)` — `src/bpp/models/wydawnictwo_ciagle.py:53`. FK `rekord` → `Wydawnictwo_Ciagle`, `related_name="autorzy_set"`, `src/bpp/models/wydawnictwo_ciagle.py:59`.
- `Wydawnictwo_Zwarte_Autor(DirtyFieldsMixin, BazaModeluOdpowiedzialnosciAutorow)` — `src/bpp/models/wydawnictwo_zwarte.py:60`. FK `rekord`, `related_name="autorzy_set"`, `:67`.
- `Patent_Autor(BazaModeluOdpowiedzialnosciAutorow)` — `src/bpp/models/patent.py:32`. FK `rekord`, `related_name="autorzy_set"`, `:35`.
- Wszystkie 3 mają `Meta.unique_together` — `("rekord","autor","typ_odpowiedzialnosci")` i `("rekord","autor","kolejnosc")`, np. `src/bpp/models/wydawnictwo_ciagle.py:73-77`. **W TEJ fazie NIE ruszamy**; zamiana na warunkowy `UniqueConstraint` (decyzja #13, §2.2b specu) idzie w fazie 02 razem ze slugiem.
- `BazaModeluOdpowiedzialnosciAutorow.objects` NIE jest jawnie zdefiniowany. Managery `Bpp*` wnosi mixin `BppAutorstwoSoftDeleteMixin` (Task 2); w MRO stoi PRZED bazą modelu, więc jego `objects` wygrywa.
- `SoftDeleteModel.delete()` (pakiet, `django_softdelete/models.py`) robi **refleksyjną kaskadę** po reverse relacjach — dla `*_Autor` reverse relacji do soft-delete dzieci NIE ma (ich dzieci to nie-soft `Autor`/`Jednostka` przez FK forward), więc kaskada jest no-op. `delete()` woła `self.save(update_fields=['deleted_at','restored_at','transaction_id'])`. ⚠️ **Ten UPDATE dotyka WYŁĄCZNIE tych 3 kolumn** — dlatego bramka `WHEN` musi znać `deleted_at` (punkt 3 „Architecture"), inaczej trigger się nie odpali. `ostatnio_zmieniony` (`auto_now`) też NIE jest bumpowany (`update_fields` filtruje `pre_save`).
- ⚠️ `strict` w pakiecie jest **asymetryczne**: `delete(strict=False)`, `restore(strict=True)`.
- Tabela `bpp_autorzy_mat` (model `Autorzy`, `src/bpp/models/cache/autorzy.py:39`, `db_table="bpp_autorzy_mat"`) zasilana triggerami z widoków `bpp_*_autorzy`.
- **Trigger (AKTUALNY, po PR #363):** `0432_cache_trigger_plpgsql.py` generuje 3 funkcje `bpp_refresh_autor_<model>()` (upsert **bez** DELETE, `_create_through_function`) + 3 `bpp_delete_autor_<model>()`, oraz triggery `<tabela>_cache_ins` / `_cache_del` / `_cache_upd`. `0433_cache_trigger_when_gate.py` nakłada bramkę `WHEN` na `_cache_upd`, z listą kolumn wyliczoną z `pg_depend`. ⚠️ **Funkcja `bpp_refresh_cache()` NIE ISTNIEJE** — `DROP` w `0432`. Nie kopiować `0399` ani `0001_cache_functions.sql`.
- Widoki `bpp_*_autorzy`: ostatnia wersja definicji w `0421_cache_trigger_pk_filter.sql` (dodaje `object_id_raw`). Odtwarzając widok, wychodź z `pg_get_viewdef()`, nie z `0001_widoki_autorzy.sql`.
- ⚠️ **`transactional_db` NIE jest wymagany** do oglądania efektów triggera — triggery bazodanowe działają wewnątrz transakcji testowej (dowód: kanarki `test_soft_delete_preconditions.py` chodzą pod zwykłym `django_db`). Używaj `django_db`; `transactional_db` tylko spowalnia. Fixture `denorms` (`src/fixtures/conftest_system.py:255`) daje `denorms.flush()`. Fixtury: `wydawnictwo_ciagle_z_dwoma_autorami`, `wydawnictwo_ciagle_z_autorem`, `autor_jan_kowalski`, `jednostka`, `standard_data`, `typy_odpowiedzialnosci`.
- ⚠️ **Numeracja migracji (stan 2026-08-06):** liść to `0487_api_v1_przelaczniki`. Nowe migracje tej fazy: `0488_autor_soft_delete_fields` → `0489_soft_delete_autorzy_views` (SQL + regeneracja bramki). **Przed startem zweryfikuj liść ponownie** (`ls src/bpp/migrations/*.py | tail -3`) — `dev` żyje, numery mogły się przesunąć. Wszystkie numery w tym planie są orientacyjne; kanoniczna jest kolejność, nie cyfra.

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


  def test_managery_zwracaja_bpp_queryset():
      """Oba managery MUSZĄ zwracać BppSoftDeleteQuerySet — inaczej gate
      na update() nie zadziała (pakietowy QuerySet go nie ma)."""
      from bpp.models.repozytorium import Element_Repozytorium

      for manager_cls in (BppSoftDeleteManager, BppGlobalManager):
          manager = manager_cls()
          manager.model = Element_Repozytorium
          manager._db = None
          assert isinstance(manager.get_queryset(), BppSoftDeleteQuerySet), (
              f"{manager_cls.__name__} nie zwraca BppSoftDeleteQuerySet"
          )
  ```

  > 🩹 **Poprawka 2026-08-06 (wykryta przy wykonaniu Task 1).** Pierwsza wersja
  > używała tu `Wydawnictwo_Ciagle_Autor` z notatką „budowa queryset-u jest
  > leniwa, więc `isinstance` przejdzie". **To nieprawda:** Django resolwuje
  > nazwy pól już w `Query.build_filter()`, przy wywołaniu `.filter()`, a nie
  > dopiero przy wykonaniu SQL-a. `BppSoftDeleteManager.get_queryset()` filtruje
  > po `deleted_at__isnull=True`, więc na modelu bez tej kolumny rzuca
  > `FieldError` **natychmiast** — test padłby, i to nie z powodu wadliwej
  > implementacji.
  >
  > Dlatego bierzemy model, który JUŻ jest `SoftDeleteModel`:
  > `Element_Repozytorium` (`src/bpp/models/repozytorium.py:18`) — trzeci
  > precedens soft-delete w repo, obok `Zgłoszenie_Publikacji`. Test dalej
  > weryfikuje dokładnie to, co ma: klasę zwracanego queryset-u.
  >
  > Ogólna zasada dla dalszych faz: **nie zakładaj, że `.filter()` jest
  > odroczone** — walidacja pól jest natychmiastowa, odroczone jest tylko
  > wykonanie zapytania.

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
- Modify: `src/bpp/models/soft_delete.py` (dopisz `BppAutorstwoSoftDeleteMixin`)
- Modify: `src/bpp/models/wydawnictwo_ciagle.py:53`, `wydawnictwo_zwarte.py` (`Wydawnictwo_Zwarte_Autor`), `patent.py:32` — wepnij mixin w bazy klas
- ⚠️ **NIE modyfikuj** `src/bpp/models/abstract/authors.py` — abstrakt ma czwartego potomka poza zakresem
- Create: `src/bpp/migrations/0488_autor_soft_delete_fields.py`
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

> 🩹 **Poprawka 2026-08-06 (self-review) — NIE ruszaj abstraktu.**
> Pierwsza wersja kazała zmienić `BazaModeluOdpowiedzialnosciAutorow(models.Model)`
> na `(SoftDeleteModel)`. To wciągnęłoby **czwarty** model, spoza zakresu
> soft-delete:
> ```
> src/zglos_publikacje/models.py:315:
>     class Zgloszenie_Publikacji_Autor(BazaModeluOdpowiedzialnosciAutorow):
> ```
> Skutki: nieplanowana migracja w aplikacji `zglos_publikacje`, podmieniony
> `objects` w module zgłoszeń (nieaudytowana zmiana zachowania) i dryf
> w `makemigrations --check`. **Wpinamy `SoftDeleteModel` w 3 konkretne
> modele**, dokładnie te z §2.2 specu.

- [ ] Dodaj wspólny mixin na końcu `src/bpp/models/soft_delete.py` (obok managerów z Task 1) — żeby nie powtarzać deklaracji managerów trzy razy:
  ```python
  class BppAutorstwoSoftDeleteMixin(SoftDeleteModel):
      """SoftDeleteModel + nasze managery dla through-modeli *_Autor.

      Wpinany w 3 KONKRETNE modele (Wydawnictwo_Ciagle_Autor,
      Wydawnictwo_Zwarte_Autor, Patent_Autor), NIE w abstrakt
      BazaModeluOdpowiedzialnosciAutorow — ten ma czwartego potomka,
      Zgloszenie_Publikacji_Autor, który jest poza zakresem soft-delete.
      """

      # Nadpisujemy managery pakietu naszymi (gate na update()).
      # Kolejność: pierwszy zdefiniowany manager = _default_manager.
      objects = BppSoftDeleteManager()
      global_objects = BppGlobalManager()
      deleted_objects = DeletedManager()

      class Meta:
          abstract = True
  ```
  Import w `soft_delete.py`: `from django_softdelete.models import SoftDeleteModel` oraz `from django_softdelete.managers import DeletedManager`.

- [ ] Wepnij mixin do **3 konkretnych** klas (kolejność baz: mixin PRZED bazą modelu, żeby jego managery wygrały MRO):
  - `src/bpp/models/wydawnictwo_ciagle.py:53` —
    `class Wydawnictwo_Ciagle_Autor(DirtyFieldsMixin, BppAutorstwoSoftDeleteMixin, BazaModeluOdpowiedzialnosciAutorow):`
  - `src/bpp/models/wydawnictwo_zwarte.py` (klasa `Wydawnictwo_Zwarte_Autor`) — analogicznie
  - `src/bpp/models/patent.py:32` —
    `class Patent_Autor(BppAutorstwoSoftDeleteMixin, BazaModeluOdpowiedzialnosciAutorow):`

- [ ] **Sanity: `Zgloszenie_Publikacji_Autor` NIE został ruszony.** Dopisz do
  `test_autor_softdelete_model.py`:
  ```python
  def test_zgloszenie_publikacji_autor_nie_jest_soft_delete():
      """Czwarty potomek abstraktu jest POZA zakresem soft-delete."""
      from django_softdelete.models import SoftDeleteModel

      from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

      assert not issubclass(Zgloszenie_Publikacji_Autor, SoftDeleteModel)
      assert not hasattr(Zgloszenie_Publikacji_Autor, "global_objects")
  ```

- [ ] Uruchom `makemigrations` — wygeneruje migrację dla 3 konkretnych modeli:
  ```bash
  uv run python src/manage.py makemigrations bpp --name autor_soft_delete_fields
  ```
  (Spodziewany plik: `src/bpp/migrations/0488_autor_soft_delete_fields.py`, 3 pola × 3 modele = 9 `AddField`. Manager-y są `use_in_migrations=False` domyślnie, więc nie pojawią się w migracji.)

- [ ] Zweryfikuj treść wygenerowanej migracji — musi zawierać `AddField` `deleted_at`/`restored_at`/`transaction_id` dla `wydawnictwo_ciagle_autor`, `wydawnictwo_zwarte_autor`, `patent_autor`. Jeśli Django dorzuciło `AlterModelManagers` — usuń tę operację ręcznie (Edit), bo managery soft-delete nie idą do schematu. Dependency MUSI wskazywać na **aktualny liść** migracji `bpp` (na 2026-08-06: `("bpp", "0487_api_v1_przelaczniki")`) — zweryfikuj `ls src/bpp/migrations/*.py | tail -3` przed commitem.

- [ ] Dodaj indeks na `deleted_at` do każdej z 3 tabel. Dopisz do `operations` w `0488_autor_soft_delete_fields.py` (po `AddField`-ach), używając `AddIndex`:
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
  git add src/bpp/models/abstract/authors.py src/bpp/migrations/0488_autor_soft_delete_fields.py src/bpp/tests/test_soft_delete/test_autor_softdelete_model.py
  git commit -m "feat(soft-delete): *_Autor → SoftDeleteModel + migracja pól deleted_at + indeks

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 3 — Widoki + gałąź kasująca w funkcjach refresh + regeneracja bramki

> 🔄 **Task przepisany 2026-08-06.** Poprzednia wersja tworzyła kopię
> `bpp_refresh_cache()` z `0399` z „trigger-skipem". **Tamta funkcja już nie
> istnieje** (`DROP` w `0432`), a sam filtr widoku nie sprząta `_mat`. Nowa
> wersja robi trzy rzeczy naraz — patrz „Architecture" na górze planu.

Jedna migracja, trzy zmiany, w **wymuszonej kolejności**:

1. przedefiniowanie 3 widoków `bpp_*_autorzy` z filtrem odcinającym
   soft-deletowane autorstwa. Używamy `CREATE OR REPLACE VIEW` (zachowuje
   listę i typy kolumn), więc zależny `bpp_autorzy` **NIE** jest kasowany
   i nie trzeba go odtwarzać — żadnego `DROP ... CASCADE`,
2. przedefiniowanie 3 funkcji `bpp_refresh_autor_<model>()` z prologiem
   kasującym,
3. regeneracja bramki `WHEN` na 3 triggerach `*_cache_upd` — **musi być po
   kroku 1**, bo bramka czyta kolumny z `pg_depend` po definicji widoku.

**Files:**
- Create: `src/bpp/migrations/0489_soft_delete_autorzy_views.py` (numer
  zweryfikuj — patrz „Fakty z kodu")
- Test: `src/bpp/tests/test_soft_delete/test_views_sql.py` (nowy),
  plus odwrócenie kanarków w
  `src/bpp/tests/test_cache/test_soft_delete_preconditions.py` (Task 4)

**Dlaczego migracja jest `RunPython`, a nie plik `.sql`:** definicje widoków
i funkcji są **generowane z introspekcji** (`information_schema.columns`,
`pg_depend`), a nie zapisane na sztywno. Kopiowanie ich do `.sql` odtworzyłoby
dokładnie ten problem, który `0432`/`0433` rozwiązały — patrz
`docs/superpowers/specs/2026-06-13-materialized-union-rekord-autorzy-design.md`.

**Steps:**

- [ ] Napisz failing testy — `src/bpp/tests/test_soft_delete/test_views_sql.py`:
  ```python
  """Kontrakt DDL po fazie 01: widok filtruje, funkcja kasuje, bramka przepuszcza."""

  import pytest
  from django.db import connection

  WIDOKI = [
      "bpp_wydawnictwo_ciagle_autorzy",
      "bpp_wydawnictwo_zwarte_autorzy",
      "bpp_patent_autorzy",
  ]
  FUNKCJE = [
      "bpp_refresh_autor_wydawnictwo_ciagle",
      "bpp_refresh_autor_wydawnictwo_zwarte",
      "bpp_refresh_autor_patent",
  ]
  TRIGGERY = [
      ("bpp_wydawnictwo_ciagle_autor", "bpp_wydawnictwo_ciagle_autor_cache_upd"),
      ("bpp_wydawnictwo_zwarte_autor", "bpp_wydawnictwo_zwarte_autor_cache_upd"),
      ("bpp_patent_autor", "bpp_patent_autor_cache_upd"),
  ]


  @pytest.mark.django_db
  @pytest.mark.parametrize("widok", WIDOKI)
  def test_widok_zrodlowy_filtruje_po_deleted_at(widok):
      with connection.cursor() as cur:
          cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
          defn = cur.fetchone()[0]
      assert "deleted_at" in defn, f"{widok} nie filtruje po deleted_at"


  @pytest.mark.django_db
  @pytest.mark.parametrize("fn", FUNKCJE)
  def test_funkcja_refresh_ma_galaz_kasujaca(fn):
      """Bez DELETE odfiltrowanie z widoku jest no-opem (upsert nic nie usuwa)."""
      with connection.cursor() as cur:
          cur.execute("SELECT pg_get_functiondef(%s::regproc)", [fn])
          src = cur.fetchone()[0]
      assert "NEW.deleted_at IS NOT NULL" in src, f"{fn}: brak gałęzi kasującej"
      assert "DELETE FROM bpp_autorzy_mat" in src, f"{fn}: brak DELETE"


  @pytest.mark.django_db
  @pytest.mark.parametrize("tabela,trigger", TRIGGERY)
  def test_bramka_when_zna_deleted_at(tabela, trigger):
      """Bez deleted_at w bramce UPDATE soft-delete nie dochodzi do funkcji."""
      with connection.cursor() as cur:
          cur.execute(
              "SELECT pg_get_triggerdef(t.oid) FROM pg_trigger t "
              "WHERE t.tgrelid = %s::regclass AND t.tgname = %s",
              [tabela, trigger],
          )
          row = cur.fetchone()
      assert row is not None, f"brak triggera {trigger}"
      assert "deleted_at" in row[0], f"{trigger}: bramka WHEN nie zna deleted_at"


  @pytest.mark.django_db
  def test_widok_odcina_WLASCIWY_wiersz_a_nie_cudzy(
      wydawnictwo_ciagle_z_dwoma_autorami, wydawnictwo_ciagle_z_autorem
  ):
      """Test SEMANTYCZNY klucza filtra — nie sam fakt obecności `deleted_at`.

      Łapie pomyłkę `object_id_raw` (id publikacji) vs `(id)[2]` (pk wiersza
      through): przy złym kluczu skasowane autorstwo zostaje w widoku, a
      wycięte zostają autorstwa INNEJ publikacji o zbieżnym numerze.
      """
      wca = wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.first()
      obcy = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
      wca.delete()

      with connection.cursor() as cur:
          cur.execute(
              "SELECT count(*) FROM bpp_wydawnictwo_ciagle_autorzy "
              "WHERE (id)[2] = %s",
              [wca.pk],
          )
          assert cur.fetchone()[0] == 0, (
              "skasowane autorstwo NADAL w widoku — filtr używa złego klucza"
          )
          cur.execute(
              "SELECT count(*) FROM bpp_wydawnictwo_ciagle_autorzy "
              "WHERE (id)[2] = %s",
              [obcy.pk],
          )
          assert cur.fetchone()[0] == 1, (
              "filtr wyciął autorstwo INNEJ publikacji — klucz porównuje "
              "id publikacji z id wiersza through"
          )
  ```

  ⚠️ Test `test_widok_zrodlowy_filtruje_po_deleted_at` (substring w
  `pg_get_viewdef`) i `test_bramka_when_zna_deleted_at` **przejdą także dla
  błędnego klucza** — `pg_depend` widzi `deleted_at` przez podzapytanie
  niezależnie od tego, czy porównanie ma sens. Powyższy test semantyczny jest
  jedyną realną wyrocznią tego kroku; **nie pomijaj go**.

- [ ] Uruchom (oczekiwany FAIL — wszystkie 9 przypadków):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_views_sql.py -q
  ```

- [ ] Zweryfikuj liść migracji i ustal numer:
  ```bash
  ls src/bpp/migrations/*.py | tail -3
  ```

- [ ] Utwórz `src/bpp/migrations/0489_soft_delete_autorzy_views.py`.
  **Reużyj generatorów z `0432`/`0433`** zamiast przepisywać SQL — nazwy
  modułów zaczynają się od cyfry, więc zwykły `import` nie zadziała; użyj
  `importlib.import_module` (moduły mają na poziomie modułu wyłącznie stałe
  i funkcje, więc import jest bezpieczny):

  ```python
  """Soft-delete autorstw: filtr w widokach + gałąź kasująca + bramka WHEN.

  Kolejność operacji jest WYMUSZONA:
    1) widoki (dodają deleted_at do WHERE)  ->
    2) funkcje refresh (gałąź kasująca)     ->
    3) regeneracja bramki WHEN (czyta pg_depend po definicji widoku z kroku 1)

  Odwrócenie 1<->3 daje bramkę bez deleted_at, czyli cichy staleness:
  soft-deletowane autorstwo zostaje w bpp_autorzy_mat.
  """

  import importlib

  from django.db import connection, migrations

  _p0432 = importlib.import_module("bpp.migrations.0432_cache_trigger_plpgsql")
  _p0433 = importlib.import_module("bpp.migrations.0433_cache_trigger_when_gate")

  THROUGH_SITES = _p0432.THROUGH_SITES  # [(tabela, model), ...]


  def _viewdef(cur, widok):
      cur.execute("SELECT pg_get_viewdef(%s::regclass, true)", [widok])
      return cur.fetchone()[0].rstrip().rstrip(";")


  def _filtruj_widok(cur, tabela, widok):
      """Odcina z widoku *_autorzy wiersze soft-deletowanych autorstw.

      Owijamy istniejącą definicję zamiast ją przepisywać: definicja jest
      generowana (0421) i przepisanie jej ręcznie rozjechałoby się przy
      następnej zmianie kolumn.

      ⚠️ KLUCZ: w widokach *_autorzy `object_id_raw` to `rekord_id`, czyli
      **id PUBLIKACJI**, a nie pk wiersza through. Pk wiersza through siedzi
      w drugim elemencie tablicy `id` (`ARRAY[ct, <through_pk>]`), stąd
      `(_orig.id)[2]`. Filtrowanie po `object_id_raw` porównywałoby id
      publikacji z id autorstwa — patrz komentarz niżej.
      """
      orig = _viewdef(cur, widok)
      cur.execute(
          f"CREATE OR REPLACE VIEW {widok} AS "
          f"SELECT * FROM ({orig}) _orig "
          f"WHERE NOT EXISTS ("
          f"    SELECT 1 FROM {tabela} _t "
          f"    WHERE _t.id = (_orig.id)[2] AND _t.deleted_at IS NOT NULL)"
      )
  ```

  > 🩹 **Poprawka 2026-08-06 (self-review).** Pierwsza wersja tego kroku
  > filtrowała `WHERE _orig.object_id_raw NOT IN (SELECT id FROM <through>
  > WHERE deleted_at IS NOT NULL)` — **błędnie**. Dowód z kodu
  > (`0421_cache_trigger_pk_filter.sql:315-321,336`):
  > ```sql
  > CREATE OR REPLACE VIEW bpp_wydawnictwo_ciagle_autorzy AS
  >  SELECT ARRAY[(...'wydawnictwo_ciagle'...), rekord_id] AS rekord_id,
  >         ARRAY[(...'wydawnictwo_ciagle'...), id]        AS id,     -- ← through pk
  >         ...
  >       , bpp_wydawnictwo_ciagle_autor.rekord_id AS object_id_raw   -- ← id PUBLIKACJI
  > ```
  > Skutki błędnej wersji (obie realne): soft-delete autorstwa **nie
  > odfiltrowałby** właściwego wiersza, a przy zbieżności numerów
  > **wyciąłby autorstwa cudzej publikacji**. Uwaga na przyszłość: w widokach
  > `bpp_<typ>_view` (faza 02) `object_id_raw` to id publikacji i tam jest
  > kluczem **poprawnym** — te dwa zestawy widoków mają różną semantykę
  > `object_id_raw`.

  ⚠️ **Do rozstrzygnięcia przy implementacji (nie zgaduj — zmierz):** czy
  owijanie widoku (`SELECT * FROM (orig) WHERE object_id_raw NOT IN ...`)
  zachowuje plan wykonania i czy `pg_depend` zarejestruje `deleted_at` jako
  kolumnę bazową. Jeśli którekolwiek nie — wygeneruj definicję widoku od nowa
  z listą kolumn i dopisz `AND <tabela>.deleted_at IS NULL` do `WHERE`
  wewnętrznego. **Test `test_bramka_when_zna_deleted_at` jest tu wyrocznią**:
  jeśli po regeneracji bramka nie zna `deleted_at`, to znaczy że `pg_depend`
  nie zobaczył kolumny przez owijkę.

- [ ] Dopisz gałąź kasującą do funkcji refresh. Ciało generujemy tak jak
  `_p0432._create_through_function`, ale z prologiem:

  ```python
  def _funkcja_z_galezia_kasujaca(cur, tabela, model):
      autorzy_view = tabela[: -len("_autor")] + "_autorzy"
      upsert = _p0432._upsert_sql(
          cur, "bpp_autorzy_mat", autorzy_view,
          "object_id_raw = NEW.rekord_id AND autor_id = NEW.autor_id",
      )
      ct_lookup = _p0432._ct_lookup(model)
      return f"""
  CREATE OR REPLACE FUNCTION bpp_refresh_autor_{model}() RETURNS trigger
  LANGUAGE plpgsql AS $bpp_body$
  DECLARE ct integer;
  BEGIN
        {ct_lookup}
        PERFORM pg_advisory_xact_lock(ct, NEW.rekord_id);
        IF NEW.deleted_at IS NOT NULL THEN
            DELETE FROM bpp_autorzy_mat WHERE id = ARRAY[ct, NEW.id]::integer[];
            RETURN NULL;
        END IF;
        {upsert};
        RETURN NULL;
  END $bpp_body$;
  """
  ```

  Uwagi:
  - klucz `ARRAY[ct, NEW.id]` jest identyczny jak w
    `_create_delete_through_function` (`0432`) — tam `OLD.id`, tu `NEW.id`;
    przy UPDATE to ten sam wiersz;
  - `pg_advisory_xact_lock` **przed** rozgałęzieniem — kasowanie musi brać ten
    sam lock co upsert, inaczej wraca wyścig z #309;
  - restore (`deleted_at` → NULL) leci normalną ścieżką upsertu — nic
    dodatkowego nie trzeba.

- [ ] Złóż `forward()` w wymuszonej kolejności i `backward()` przywracający
  stan sprzed migracji:

  ```python
  def forward(apps, schema_editor):
      with connection.cursor() as cur:
          for tabela, model in THROUGH_SITES:                      # 1) widoki
              _filtruj_widok(cur, tabela, tabela[: -len("_autor")] + "_autorzy")
          for tabela, model in THROUGH_SITES:                      # 2) funkcje
              cur.execute(_funkcja_z_galezia_kasujaca(cur, tabela, model))
      _regeneruj_bramke()                                          # 3) bramka


  def _regeneruj_bramke():
      """Ta sama logika co 0433.forward -- po zmianie widoku pg_depend zna
      juz deleted_at, wiec bramka wciagnie ja sama."""
      with connection.cursor() as cur:
          for tabela, refresh_fn, widoki in _p0433.GATED:
              if not tabela.endswith("_autor"):
                  continue                       # publikacje to faza 02
              kolumny = _p0433._gate_columns(cur, tabela, widoki)
              when = _p0433._when_clause(kolumny)
              cur.execute(f"DROP TRIGGER IF EXISTS {tabela}_cache_upd ON {tabela};")
              cur.execute(
                  f"CREATE TRIGGER {tabela}_cache_upd AFTER UPDATE ON {tabela} "
                  f"FOR EACH ROW WHEN ({when}) "
                  f"EXECUTE PROCEDURE {refresh_fn}();"
              )
  ```

  ⚠️ `_gate_columns` z `0433` **rzuca `RuntimeError`, gdy `pg_depend` nie
  zwróci kolumn** — to celowy bezpiecznik (nie tworzy niebramkowanego UPDATE).
  Nie obchodź go; jeśli wystąpi, znaczy że krok 1 nie zadziałał.

- [ ] `backward`: odtwórz widoki bez filtra (`pg_get_viewdef` sprzed owijki nie
  jest dostępny — wygeneruj z `_p0432`/`0421` albo zapisz oryginał w migracji),
  funkcje przez `_p0432._create_through_function`, bramkę przez ponowne
  `_regeneruj_bramke()` (po cofnięciu widoku `deleted_at` zniknie z `pg_depend`
  samo). **Migracja MUSI być odwracalna** — testy migracji w CI to sprawdzają.

- [ ] Uruchom testy kontraktu DDL (oczekiwany PASS — 9/9):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_views_sql.py -q
  ```

- [ ] Sprawdź brak driftu migracji:
  ```bash
  DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run
  ```

- [ ] Commit:
  ```bash
  git add src/bpp/migrations/0489_soft_delete_autorzy_views.py src/bpp/tests/test_soft_delete/test_views_sql.py
  git commit -m "feat(soft-delete): widoki + galaz kasujaca + bramka WHEN dla *_Autor

Trzy zmiany w jednej migracji, w wymuszonej kolejnosci: filtr deleted_at
w widokach bpp_*_autorzy -> galaz kasujaca w funkcjach bpp_refresh_autor_*
-> regeneracja bramki WHEN (pg_depend zna juz deleted_at).

Zadna z nich nie wystarcza sama: filtr widoku nie sprzata _mat (upsert bez
DELETE = no-op), a bez deleted_at w bramce UPDATE soft-delete w ogole nie
dochodzi do funkcji triggera.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 4 — Testy spójności cache (mat-view) po soft-delete `*_Autor`

Główny gejt fazy: soft-delete wiersza `*_Autor` → znika z `bpp_autorzy_mat` (model `Autorzy`) i z `bpp_autorzy` (model `AutorzyView`); restore → wraca; edycja autorstwa skasowanej publikacji nie wskrzesza wiersza w cache; kaskada queryset-owa (`.delete()` na QS) działa per-instancja. Testy wymagają `transactional_db` (trigger działa tylko z prawdziwym commitem).

**Files:**
- Test (create): `src/bpp/tests/test_soft_delete/test_cache_consistency.py`
- Test (modify): `src/bpp/tests/test_cache/test_soft_delete_preconditions.py` — **odwrócenie kanarków**
- Modify (jeśli testy ujawnią drift): brak planowanych — testy mają przejść na implementacji z Task 2-3.

**Steps:**

- [ ] **Odwróć kanarki warunków wstępnych.** `test_soft_delete_preconditions.py`
  przypina stan „soft-delete by nie zadziałał" i jest zielony PRZED tą fazą.
  Po Task 3 musi asertować stan docelowy:
  - `test_update_samego_deleted_at_nie_odpala_triggera` → **zmień na**
    `test_update_samego_deleted_at_odpala_trigger`: `ctid` ma zniknąć
    (wiersz usunięty z `_mat`), nie pozostać bez zmian;
  - `test_filtr_widoku_sam_nie_usuwa_wiersza_z_mat` → **zmień na**
    `test_soft_delete_usuwa_wiersz_z_mat`: po `UPDATE ... SET deleted_at`
    `_ctid(...)` ma być `None`.

  Testy operują na `bpp_wydawnictwo_ciagle` (publikacja), więc **naprawdę
  zazielenią się dopiero po fazie 02**. W fazie 01 napisz ich odpowiedniki
  dla `bpp_wydawnictwo_ciagle_autor` / `bpp_autorzy_mat` (kolumna `deleted_at`
  już istnieje po Task 2, więc pomocnicze `_dodaj_deleted_at` znika), a
  oryginalne zostaw jako czerwone-oczekiwane z `@pytest.mark.xfail(reason=
  "faza 02 — soft-delete publikacji")`. **NIE kasuj ich** — to jedyny
  regresyjny dowód, że bramka i gałąź kasująca działają.

- [ ] Napisz testy spójności — `src/bpp/tests/test_soft_delete/test_cache_consistency.py`:
  ```python
  """Spójność materializowanego cache (bpp_autorzy_mat / model Autorzy) po
  soft-delete wierszy *_Autor.

  UWAGA: zwykły django_db WYSTARCZA — triggery bazodanowe dzialaja wewnatrz
  transakcji testowej (kanarki test_soft_delete_preconditions.py to
  pokazuja). transactional_db jest tu zbedny i tylko spowalnia."""

  import pytest

  from bpp.models.cache import Autorzy, AutorzyView
  from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor


  def _autorzy_mat_dla(wca):
      """Wiersze bpp_autorzy_mat (model Autorzy) wskazujące na danego autora
      w danym rekordzie."""
      from django.contrib.contenttypes.models import ContentType

      ct = ContentType.objects.get_for_model(type(wca.rekord)).pk
      return Autorzy.objects.filter(
          autor_id=wca.autor_id,
          rekord_id=[ct, wca.rekord_id],
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
          rekord_id=[ContentType.objects.get_for_model(type(wc)).pk, wc.pk]
      ).exists()
      # ... ale wiersze fizycznie żyją (soft, nie hard)
      assert Wydawnictwo_Ciagle_Autor.global_objects.filter(rekord=wc).count() >= 2
  ```

- [ ] Uruchom (oczekiwany PASS — implementacja z Task 2+3 pokrywa wszystkie ścieżki):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete/test_cache_consistency.py -q
  ```
  Jeśli którykolwiek FAIL → **zdiagnozuj który z trzech elementów nie zadziałał**, w tej kolejności (każdy warunkuje następny):
  1. `SELECT pg_get_triggerdef(...)` — czy bramka `WHEN` zna `deleted_at`? Jeśli nie, trigger w ogóle się nie odpalił i reszta diagnostyki jest bez sensu (to najczęstsza przyczyna: krok 1 migracji nie wstawił kolumny do `pg_depend`).
  2. `SELECT pg_get_functiondef('bpp_refresh_autor_wydawnictwo_ciagle'::regproc)` — czy jest gałąź `IF NEW.deleted_at IS NOT NULL ... DELETE`? Bez niej upsert jest no-opem i wiersz zostaje.
  3. `SELECT pg_get_viewdef('bpp_wydawnictwo_ciagle_autorzy'::regclass, true)` — czy filtr `deleted_at` obecny?

  Użyj superpowers:systematic-debugging, NIE łataj testu.

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

1. **Domyślny manager `*_Autor.objects` zmienił klasę** na `BppSoftDeleteManager` (filtruje `deleted_at__isnull=True`). Faza 03 (audyt kat. B) MUSI przejść **128** miejsc `*_Autor.objects` (stan 2026-08-06; spec mówił „90" — przelicz przed startem fazy 03: `grep -rn --include='*.py' -E "(Wydawnictwo_Ciagle_Autor|Wydawnictwo_Zwarte_Autor|Patent_Autor)\.objects" src/ | wc -l`). W fazie 01 nic nie jest skasowane, więc filtr jest no-op, ale od fazy 02 (kaskada soft-delete publikacji) zacznie ukrywać. Guard autora (faza 04) MUSI liczyć przez `global_objects` (spec §3.2).
2. **Faza 02 powtarza ten sam trójskładnikowy wzorzec dla 5 tabel publikacji**: filtr `deleted_at` w `bpp_*_view` → gałąź kasująca w `bpp_refresh_rekord_<model>()` (`DELETE FROM bpp_rekord_mat`) → regeneracja bramki `WHEN`. Uwaga na doktorat/habilitację: ich funkcje refresh dotykają **obu** tabel `_mat` (`bpp_rekord_mat` i `bpp_autorzy_mat`, bo autor leży na wierszu publikacji) — gałąź kasująca musi czyścić obie.
3. **Każda przyszła zmiana definicji widoku źródłowego wymaga regeneracji bramki `WHEN`.** Bramka jest wypiekana z `pg_depend` w momencie migracji, więc nie zaktualizuje się sama. Pominięcie = cichy staleness. Testy `test_views_sql.py` i kanarki `test_soft_delete_preconditions.py` to wyłapią.
3. **Widoki `bpp_praca_doktorska_autorzy` / `bpp_praca_habilitacyjna_autorzy` NIE filtrowane** — autorstwo doktoratu/habilitacji nie jest `*_Autor` SoftDeleteModel (autor doktoratu to FK `Praca_Doktorska.autor`, nie through). Faza 02 (soft-delete publikacji doktorat/habilitacja) musi zadbać o ich zniknięcie z `bpp_rekord` przez własne `deleted_at` na tabeli publikacji — to NIE jest pokryte tą fazą.
4. **Gałęzie UNION `bpp_rekord` NIE dotknięte** w fazie 01 — soft-delete publikacji (kolumna `deleted_at` na `bpp_wydawnictwo_ciagle` itd.) to faza 02; dopiero ona doda filtr `deleted_at IS NULL` do `bpp_*_view`. Faza 01 dotyka wyłącznie ścieżki autorstwa.
6. **`unique_together` na `*_Autor` zachowane bez `deleted_at`** — w tej fazie autorstwa nie mają warunkowego unique. **Faza 02 MUSI to zmienić** (decyzja #13, spec §2.2b): soft-deletowany wiersz nadal zajmuje slot w `(rekord, autor, typ_odpowiedzialnosci)` / `(rekord, autor, kolejnosc)`, a `deduplikator_autorow` przenoszący autorstwa trafi wtedy w `IntegrityError` o niewidoczny rekord. Przejście na `UniqueConstraint(condition=Q(deleted_at__isnull=True))` — razem ze slugiem.
7. **`Cache_Punktacja_*` NIE są dotknięte** żadnym mechanizmem tej fazy (nie mają FK do publikacji ani triggerów cache). Domknięcie tej luki to faza 06 (decyzja #15, spec §2.5b) — do tego czasu soft-deletowana praca nadal liczyłaby się do ewaluacji.
