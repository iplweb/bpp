# Soft-delete — Faza 04: Guardy PROTECT (autor + książka-matka)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Wykonuj zadania po kolei; po każdym zadaniu uruchom podaną komendę i zacommituj.

**Goal:** Dodać dwuwarstwową ochronę przed kasowaniem rekordów z zależnościami: (1) flip FK `CASCADE→PROTECT` na powiązaniach autora (`Wydawnictwo_*_Autor.autor`, `Praca_Doktorska.autor`) oraz na self-FK rozdziałów (`Wydawnictwo_Zwarte.wydawnictwo_nadrzedne`) — obrona przed hard-delete; (2) guard w soft-`delete()` modeli `Autor` i `Wydawnictwo_Zwarte`, liczący dzieci przez `global_objects` (widzi też kaskadowo-skasowane autorstwa z fazy 02) i rzucający `ProtectedError`. Autor bez prac → soft-delete (husk); książka bez rozdziałów → soft-delete. `Praca_Habilitacyjna.autor` już jest `PROTECT` — bez zmian.

**Architecture:** Warstwa 1 to migracje **state-only** (`migrations.AlterField` — Django implementuje `on_delete` w ORM, nie jako constraint DB, więc brak zmiany schematu; NIE modyfikujemy istniejących migracji). Warstwa 2 to override `delete(self, *args, user=None, reason="", **kwargs)` wołający helper `raise_if_has_protected_children(instance, relations, label)` z `src/bpp/models/soft_delete.py`. Guard MUSI liczyć przez `global_objects` (nie `objects`), bo `objects` ukrywa kaskadowo-skasowane `*_Autor` (faza 02) i autor „cały w koszu" fałszywie wyglądałby na pustego (spec §3.2, §9). Override `Autor.delete()` **nie kaskaduje** do `*_Autor` (spec §1, §10.1). Override `Wydawnictwo_Zwarte.delete()` dokłada guard **PRZED** kaskadą na `*_Autor` z fazy 02 — kaskady NIE gubimy.

**Tech Stack:** Django, `django-soft-delete>=1.0.23` (`SoftDeleteModel`, menedżery `objects`/`global_objects`/`deleted_objects`, sygnały `post_soft_delete`/`post_restore`), `django.db.models.ProtectedError`, pytest + `model_bakery.baker`, `uv run` dla wszystkich komend Python.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md) — §1 (asymetria), §2.6 (self-FK rozdziały → PROTECT), §3 (autor: dwie warstwy + soft-delete husków), §9 (ryzyka), §10.1/§10.11 (decyzje).
**Plan-indeks:** [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md) — kontrakty PINNED (helper `raise_if_has_protected_children`, sygnatura `delete(self, *args, user=None, reason="", **kwargs)`).

**Zależy od:** Faza 02 (modele `Wydawnictwo_Ciagle`/`Wydawnictwo_Zwarte`/`Praca_Doktorska`/`Praca_Habilitacyjna`/`Patent` + 3 through-modele `*_Autor` są już `SoftDeleteModel`; menedżer `global_objects` dostępny; override `Wydawnictwo_Zwarte.delete()` z wąską kaskadą na `*_Autor` już istnieje — faza 04 dokłada do niego guard). Moduł `src/bpp/models/soft_delete.py` istnieje (utworzony fazą 01/04 — tu dopisujemy helper).

---

## Reguły BPP (obowiązują w każdym zadaniu)

- **Wszystkie komendy Python przez `uv run`** (np. `uv run pytest ...`). Nigdy goły `python`.
- **NIE modyfikuj istniejących migracji** w `src/*/migrations/`. Nowe migracje tworzymy ręcznie / przez `makemigrations`.
- **Max długość linii 88 znaków** (ruff). Komentarze/komunikaty po polsku.
- **Testy:** pytest-only, standalone funkcje (bez klas `unittest.TestCase`), `@pytest.mark.django_db`, `model_bakery.baker.make`. Fixtury z `src/fixtures/` (`autor_jan_nowak`, `autor_jan_kowalski`, `jednostka`, `typy_odpowiedzialnosci`, `wydawnictwo_zwarte`, `wydawnictwo_ciagle`, `praca_doktorska`, `patent`).
- **Kontrakt z reversion (NIE łamać):** override `delete()`/`restore()` idzie per-instancja przez `self.save()` / `super().delete()` — **nigdy** bulk `queryset.update(deleted_at=...)`. Faza 04 nie ustawia `deleted_at` ręcznie; deleguje do `super().delete()` pakietu.
- **Po każdym zadaniu:** `ruff format src/bpp` + `ruff check src/bpp` (tylko zmienione), komenda testu z zadania na zielono, commit.

## Stan zweryfikowany w kodzie (punkt wyjścia)

- `Wydawnictwo_*_Autor.autor = ForeignKey("bpp.Autor", CASCADE)` — w abstrakcie `BazaModeluOdpowiedzialnosciAutorow` (`src/bpp/models/abstract/authors.py:22`), dziedziczą `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor`. **Bez `related_name`** → reverse default `autor.wydawnictwo_ciagle_autor_set` / `wydawnictwo_zwarte_autor_set` / `patent_autor_set`.
- `Praca_Doktorska.autor = ForeignKey(Autor, CASCADE)` (`src/bpp/models/praca_doktorska.py:136`), reverse default `autor.praca_doktorska_set`.
- `Praca_Habilitacyjna.autor = OneToOneField(Autor, PROTECT)` (`src/bpp/models/praca_habilitacyjna.py:42`) — **już PROTECT, nie ruszamy**; reverse `autor.praca_habilitacyjna`.
- `Wydawnictwo_Zwarte.wydawnictwo_nadrzedne = ForeignKey("self", CASCADE, related_name="wydawnictwa_powiazane_set")` (`src/bpp/models/wydawnictwo_zwarte.py:202`) — rozdziały → książka-matka.
- `Autor` (`src/bpp/models/autor.py:81`) dziedziczy `LinkDoPBNMixin, ModelZAdnotacjami, ModelZPBN_ID` — **brak custom `delete()`**. Faza 04 dorzuca `SoftDeleteModel` do bazy i override `delete()`.
- Merge (`src/deduplikator_autorow/utils/merge.py`) przenosi przed `autor.delete()` WSZYSTKIE 5 typów: `Wydawnictwo_Ciagle_Autor` (:191/:223), `Wydawnictwo_Zwarte_Autor` (:265/:317), `Patent_Autor` (:335), `Praca_Habilitacyjna` (:410), `Praca_Doktorska` (:430). Po transferze husk jest pusty → guard go przepuści (test w Zadaniu 6).

**Mapowanie relacji liczonych przez guard (model docelowy → pole FK do autora):**

| relacja (label) | model | pole FK do autora |
|---|---|---|
| autorstwo ciągłe | `Wydawnictwo_Ciagle_Autor` | `autor` |
| autorstwo zwarte | `Wydawnictwo_Zwarte_Autor` | `autor` |
| autorstwo patentu | `Patent_Autor` | `autor` |
| doktorat | `Praca_Doktorska` | `autor` |
| habilitacja | `Praca_Habilitacyjna` | `autor` (O2O) |

Helper liczy przez `Model.global_objects.filter(<pole>=instance)`, więc operuje na **modelach docelowych**, nie reverse-managerach (reverse manager nie wystawia `global_objects`).

---

## Tasks

### Zadanie 1 — Helper `raise_if_has_protected_children` w `soft_delete.py`

**Files:**
- `src/bpp/models/soft_delete.py` — dopisz funkcję `raise_if_has_protected_children` (po istniejących klasach menedżerów z fazy 01).
- Test path: `src/bpp/tests/test_models/test_soft_delete_guards.py` (nowy plik).

Helper przyjmuje listę krotek `(model, pole_fk)` lub listę nazw — wg PINNED kontraktu sygnatura to `raise_if_has_protected_children(instance, relations, label)`, gdzie `relations` to lista `(Model, "pole_fk")`. Liczy sumę dzieci przez `Model.global_objects.filter(**{pole: instance})`; jeśli >0 — rzuca `django.db.models.ProtectedError` z czytelnym komunikatem PL zawierającym `label`, liczbę dzieci i nazwę instancji.

- [ ] **Failing test** — napisz `test_raise_if_has_protected_children_blokuje_gdy_sa_dzieci` i `test_raise_if_has_protected_children_przepuszcza_gdy_brak`:
  ```python
  import pytest
  from django.db.models import ProtectedError
  from model_bakery import baker

  from bpp.models import (
      Autor,
      Wydawnictwo_Ciagle_Autor,
      Praca_Doktorska,
  )
  from bpp.models.soft_delete import raise_if_has_protected_children


  @pytest.mark.django_db
  def test_raise_if_has_protected_children_przepuszcza_gdy_brak():
      autor = baker.make(Autor)
      # Nie rzuca — brak dzieci w podanych relacjach.
      raise_if_has_protected_children(
          autor,
          [(Wydawnictwo_Ciagle_Autor, "autor"), (Praca_Doktorska, "autor")],
          label="autora",
      )


  @pytest.mark.django_db
  def test_raise_if_has_protected_children_blokuje_gdy_sa_dzieci():
      autor = baker.make(Autor)
      baker.make(Wydawnictwo_Ciagle_Autor, autor=autor)
      with pytest.raises(ProtectedError):
          raise_if_has_protected_children(
              autor,
              [(Wydawnictwo_Ciagle_Autor, "autor")],
              label="autora",
          )
  ```
- [ ] **Run → FAIL:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k raise_if_has_protected_children` — `ImportError` / `AttributeError` (helper nie istnieje).
- [ ] **Implementacja** — dopisz w `src/bpp/models/soft_delete.py`:
  ```python
  from django.db.models import ProtectedError


  def raise_if_has_protected_children(instance, relations, label):
      """Blokuje soft-delete `instance`, jeśli ma „chronione" dzieci.

      `relations` to lista krotek ``(Model, "pole_fk")`` — liczymy dzieci
      przez ``Model.global_objects`` (nie ``objects``!), żeby widzieć także
      rekordy soft-deletowane kaskadą z fazy 02 (autor „cały w koszu" nadal
      jest chroniony — spec §3.2). Rzuca ``ProtectedError`` z czytelnym
      komunikatem PL, jeśli jest co najmniej jedno dziecko.
      """
      protected = []
      for model, pole in relations:
          qs = model.global_objects.filter(**{pole: instance})
          protected.extend(qs)

      if protected:
          raise ProtectedError(
              f"Nie można usunąć {label} „{instance}" — rekord ma "
              f"{len(protected)} powiązanych prac (autorstwa / doktorat / "
              f"habilitacja / rozdziały). Najpierw przenieś lub usuń te "
              f"powiązania.",
              protected,
          )
  ```
  Uwaga: `ProtectedError(msg, protected_objects)` — drugi argument to iterowalny zbiór chronionych obiektów (kontrakt Django). Importuj `ProtectedError` z `django.db.models`.
- [ ] **Run → PASS:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k raise_if_has_protected_children`
- [ ] `ruff format src/bpp/models/soft_delete.py src/bpp/tests/test_models/test_soft_delete_guards.py` + `ruff check` na tych plikach.
- [ ] **Commit:** `feat(soft-delete): helper raise_if_has_protected_children (guard PROTECT)`

---

### Zadanie 2 — Flip FK `CASCADE→PROTECT` na powiązaniach autora i rozdziałów (migracja state-only)

**Files:**
- `src/bpp/models/abstract/authors.py:22` — `autor = ForeignKey("bpp.Autor", CASCADE)` → `PROTECT`.
- `src/bpp/models/praca_doktorska.py:136` — `autor = ForeignKey(Autor, CASCADE)` → `PROTECT`.
- `src/bpp/models/wydawnictwo_zwarte.py:202` — `wydawnictwo_nadrzedne = ForeignKey("self", CASCADE, ...)` → `PROTECT` (zachowaj `blank`, `null`, `help_text`, `related_name="wydawnictwa_powiazane_set"`).
- Nowa migracja: `src/bpp/migrations/0XXX_soft_delete_protect_fk.py` (numer = następny wolny; `migrations.AlterField` × 4 — bo `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` dziedziczą pole z abstraktu, więc każdy konkretny model dostaje własny `AlterField`).
- Test path: `src/bpp/tests/test_models/test_soft_delete_guards.py`.

- [ ] **Failing test** — `test_fk_autora_jest_protect` i `test_wydawnictwo_nadrzedne_jest_protect`, sprawdzające `on_delete` przez introspekcję pola:
  ```python
  from django.db.models import PROTECT

  from bpp.models import (
      Patent_Autor,
      Praca_Doktorska,
      Wydawnictwo_Ciagle_Autor,
      Wydawnictwo_Zwarte,
      Wydawnictwo_Zwarte_Autor,
  )


  def test_fk_autora_jest_protect():
      for model in (
          Wydawnictwo_Ciagle_Autor,
          Wydawnictwo_Zwarte_Autor,
          Patent_Autor,
          Praca_Doktorska,
      ):
          field = model._meta.get_field("autor")
          assert field.remote_field.on_delete is PROTECT, model


  def test_wydawnictwo_nadrzedne_jest_protect():
      field = Wydawnictwo_Zwarte._meta.get_field("wydawnictwo_nadrzedne")
      assert field.remote_field.on_delete is PROTECT
  ```
- [ ] **Run → FAIL:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k "protect"` — `on_delete` to nadal `CASCADE`.
- [ ] **Implementacja (modele):**
  - `src/bpp/models/abstract/authors.py:22` — zmień `from django.db.models import CASCADE, ...` jeśli trzeba dołożyć `PROTECT`; `autor = models.ForeignKey("bpp.Autor", models.PROTECT)`.
  - `src/bpp/models/praca_doktorska.py:136` — `autor = models.ForeignKey(Autor, PROTECT)` (zadbaj o import `PROTECT`).
  - `src/bpp/models/wydawnictwo_zwarte.py:202` — pierwszy arg pozycyjny `CASCADE` → `PROTECT` (zachowaj resztę kwargs i `related_name`).
- [ ] **Implementacja (migracja):** `uv run python src/manage.py makemigrations bpp --name soft_delete_protect_fk`, potem otwórz wygenerowany plik i **dodaj `state_operations` wrapper**, żeby była state-only (bez DDL — `on_delete` żyje tylko w ORM):
  ```python
  from django.db import migrations, models
  import django.db.models.deletion


  class Migration(migrations.Migration):
      dependencies = [
          ("bpp", "0XXX_poprzednia"),  # ostatnia migracja bpp
      ]

      operations = [
          migrations.SeparateDatabaseAndState(
              database_operations=[],
              state_operations=[
                  migrations.AlterField(
                      model_name="wydawnictwo_ciagle_autor",
                      name="autor",
                      field=models.ForeignKey(
                          on_delete=django.db.models.deletion.PROTECT,
                          to="bpp.autor",
                      ),
                  ),
                  migrations.AlterField(
                      model_name="wydawnictwo_zwarte_autor",
                      name="autor",
                      field=models.ForeignKey(
                          on_delete=django.db.models.deletion.PROTECT,
                          to="bpp.autor",
                      ),
                  ),
                  migrations.AlterField(
                      model_name="patent_autor",
                      name="autor",
                      field=models.ForeignKey(
                          on_delete=django.db.models.deletion.PROTECT,
                          to="bpp.autor",
                      ),
                  ),
                  migrations.AlterField(
                      model_name="praca_doktorska",
                      name="autor",
                      field=models.ForeignKey(
                          on_delete=django.db.models.deletion.PROTECT,
                          to="bpp.autor",
                      ),
                  ),
                  migrations.AlterField(
                      model_name="wydawnictwo_zwarte",
                      name="wydawnictwo_nadrzedne",
                      field=models.ForeignKey(
                          blank=True,
                          null=True,
                          on_delete=django.db.models.deletion.PROTECT,
                          related_name="wydawnictwa_powiazane_set",
                          to="bpp.wydawnictwo_zwarte",
                          help_text=(
                              "Jeżeli dodajesz rozdział,\n        tu wybierz "
                              "pracę, w ramach której dany rozdział występuje."
                          ),
                      ),
                  ),
              ],
          ),
      ]
  ```
  Dopasuj `help_text` 1:1 do tekstu z modelu (skopiuj dokładnie, żeby `makemigrations --check` nie wykrył driftu). Jeśli auto-wygenerowany `AlterField` różni się polami od powyższego — użyj wygenerowanego (jest source-of-truth dla state), tylko owiń w `SeparateDatabaseAndState(database_operations=[], state_operations=[...])`.
- [ ] **Run → PASS:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k "protect"`
- [ ] **Sanity (brak driftu schematu):** `uv run python src/manage.py makemigrations bpp --check --dry-run` → „No changes detected".
- [ ] `ruff format` + `ruff check` na zmienionych plikach modeli i migracji.
- [ ] **Commit:** `feat(soft-delete): flip FK autor/doktorat/rozdziały CASCADE→PROTECT (state-only)`

---

### Zadanie 3 — `Autor` → `SoftDeleteModel` + override soft `delete()` z guardem

**Files:**
- `src/bpp/models/autor.py:81` — dodaj `SoftDeleteModel` do bazy klasy `Autor`; override `delete(self, *args, user=None, reason="", **kwargs)`.
- Nowa migracja: `src/bpp/migrations/0XXX_autor_soft_delete.py` (`deleted_at`, `restored_at`, `transaction_id` + indeks — wg pól `SoftDeleteModel`; menedżery `objects`/`global_objects`/`deleted_objects` pakietu).
- Test path: `src/bpp/tests/test_models/test_soft_delete_guards.py`.

Uwaga MRO: `Autor` ma własny menedżer `objects = AutorManager()` (`src/bpp/models/autor.py:200`) i własny `save()`. `SoftDeleteModel` wnosi własne menedżery. Tu **zachowujemy** semantykę: `objects` ma nadal działać jak dotąd dla widoków, ale musi ukrywać skasowane. Najprościej: dodać `SoftDeleteModel` jako bazę, a `objects = AutorManager()` zostaje jako menedżer publiczny — pod warunkiem, że `AutorManager` po fazie 02/04 przepleciony jest z filtrem `deleted_at__isnull=True`. **W tej fazie skupiamy się na guardzie**; jeśli przeplecenie menedżera `AutorManager` nie zostało zrobione w fazie 02, dodaj `global_objects`/`deleted_objects` z pakietu i upewnij się, że `objects` filtruje skasowane (przez `BppSoftDeleteManager` z fazy 01 lub przepleciony `AutorManager`). To zadanie traktuje przeplecenie menedżera jako warunek wstępny; jeśli go brak — najpierw dorób (poza-zakresowy hot-fix odnotuj w commicie).

- [ ] **Failing test** — autor bez prac soft-deletuje się (husk):
  ```python
  @pytest.mark.django_db
  def test_autor_bez_prac_soft_delete_ok(autor_jan_nowak):
      autor_jan_nowak.delete()
      autor_jan_nowak.refresh_from_db()
      assert autor_jan_nowak.deleted_at is not None
      assert not Autor.objects.filter(pk=autor_jan_nowak.pk).exists()
      assert Autor.global_objects.filter(pk=autor_jan_nowak.pk).exists()
  ```
- [ ] **Run → FAIL:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k test_autor_bez_prac_soft_delete_ok` — `AttributeError: deleted_at` lub `global_objects` (Autor nie jest jeszcze SoftDeleteModel).
- [ ] **Implementacja (model):**
  - Import: `from django_softdelete.models import SoftDeleteModel`.
  - Baza klasy: `class Autor(LinkDoPBNMixin, ModelZAdnotacjami, ModelZPBN_ID, SoftDeleteModel):`.
  - Override (po `save()`):
    ```python
    def delete(self, *args, user=None, reason="", **kwargs):
        """Soft-delete autora — DOZWOLONY tylko dla autora bez prac (husk).

        Guard liczy WSZYSTKIE powiązania przez global_objects (także
        kaskadowo-skasowane autorstwa z fazy 02), spec §3.2. NIE kaskaduje
        do *_Autor (spec §1). Autor z jakąkolwiek pracą → ProtectedError.
        """
        from bpp.models import (
            Patent_Autor,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Wydawnictwo_Ciagle_Autor,
            Wydawnictwo_Zwarte_Autor,
        )
        from bpp.models.soft_delete import raise_if_has_protected_children

        raise_if_has_protected_children(
            self,
            [
                (Wydawnictwo_Ciagle_Autor, "autor"),
                (Wydawnictwo_Zwarte_Autor, "autor"),
                (Patent_Autor, "autor"),
                (Praca_Doktorska, "autor"),
                (Praca_Habilitacyjna, "autor"),
            ],
            label="autora",
        )
        return super().delete(*args, **kwargs)
    ```
    `user`/`reason` przyjmujemy w sygnaturze (kontrakt PINNED dla fazy 06/07) — w tej fazie nie używamy ich dalej; `super().delete()` pakietu nie przyjmuje tych kwargs, więc NIE przekazujemy ich w `**kwargs` do super (odfiltrowane przez nazwane parametry).
- [ ] **Implementacja (migracja):** `uv run python src/manage.py makemigrations bpp --name autor_soft_delete`. Sprawdź, że dodaje `deleted_at`, `restored_at`, `transaction_id` (oraz ewentualne menedżery). Pola domyślnie `NULL` — bez backfillu (spec §9, duże tabele).
- [ ] **Run → PASS:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k test_autor_bez_prac_soft_delete_ok`
- [ ] `uv run python src/manage.py makemigrations bpp --check --dry-run` → „No changes detected".
- [ ] `ruff format` + `ruff check` na `autor.py`, migracji, teście.
- [ ] **Commit:** `feat(soft-delete): Autor → SoftDeleteModel + guard soft-delete (husk only)`

---

### Zadanie 4 — Testy guarda `Autor.delete()` dla każdego typu pracy + przypadek „tylko w koszu"

**Files:**
- Test path: `src/bpp/tests/test_models/test_soft_delete_guards.py` (dopisz funkcje).

Pokrywamy: ciągłe / zwarte / patent / doktorat / habilitacja → `ProtectedError`; oraz krytyczny przypadek z §3.2 — praca soft-deletowana (kaskada fazy 02) nadal blokuje, bo guard liczy przez `global_objects`.

- [ ] **Failing test** — pięć przypadków + przypadek „tylko w koszu":
  ```python
  @pytest.mark.django_db
  def test_autor_z_praca_ciagla_protect(
      wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
  ):
      wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
      with pytest.raises(ProtectedError):
          autor_jan_kowalski.delete()


  @pytest.mark.django_db
  def test_autor_z_praca_zwarta_protect(
      wydawnictwo_zwarte, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
  ):
      wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
      with pytest.raises(ProtectedError):
          autor_jan_kowalski.delete()


  @pytest.mark.django_db
  def test_autor_z_patentem_protect(
      patent, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
  ):
      patent.dodaj_autora(autor_jan_kowalski, jednostka)
      with pytest.raises(ProtectedError):
          autor_jan_kowalski.delete()


  @pytest.mark.django_db
  def test_autor_z_doktoratem_protect(autor_jan_nowak):
      baker.make(Praca_Doktorska, autor=autor_jan_nowak)
      with pytest.raises(ProtectedError):
          autor_jan_nowak.delete()


  @pytest.mark.django_db
  def test_autor_z_habilitacja_protect(autor_jan_nowak):
      baker.make(Praca_Habilitacyjna, autor=autor_jan_nowak)
      with pytest.raises(ProtectedError):
          autor_jan_nowak.delete()


  @pytest.mark.django_db
  def test_autor_z_praca_tylko_w_koszu_nadal_protect(
      wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
  ):
      # Praca + jej *_Autor są soft-deletowane (kaskada fazy 02).
      wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
      wydawnictwo_ciagle.delete()
      # objects ukrywa kaskadowo-skasowane autorstwo, ale guard liczy
      # przez global_objects → autor nadal chroniony (spec §3.2).
      assert not Wydawnictwo_Ciagle_Autor.objects.filter(
          autor=autor_jan_kowalski
      ).exists()
      assert Wydawnictwo_Ciagle_Autor.global_objects.filter(
          autor=autor_jan_kowalski
      ).exists()
      with pytest.raises(ProtectedError):
          autor_jan_kowalski.delete()
  ```
  Dodaj brakujące importy do nagłówka pliku: `Praca_Habilitacyjna`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor`, `Wydawnictwo_Ciagle_Autor`.
- [ ] **Run → FAIL (najpierw napisz, potem uruchom):** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k "protect"` — przy poprawnym guardzie z Zadania 3 powinny przejść; jeśli któryś `FAIL`, debuguj guard/relacje (np. zła nazwa pola FK, użyto `objects` zamiast `global_objects`). To zadanie jest „dowodem regresji" guarda — przy błędzie w guardzie tu pęka.
- [ ] **Run → PASS:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k "protect"`
- [ ] `ruff format` + `ruff check` na teście.
- [ ] **Commit:** `test(soft-delete): guard Autor.delete() — ciągłe/zwarte/patent/doktorat/habilitacja + kosz`

---

### Zadanie 5 — `Wydawnictwo_Zwarte.delete()` guard na rozdziały (PRZED kaskadą fazy 02)

**Files:**
- `src/bpp/models/wydawnictwo_zwarte.py` — w istniejącym override `delete()` (z fazy 02, wąska kaskada na `*_Autor`) dodaj guard **na samym początku**, PRZED ustawieniem `deleted_at` i PRZED kaskadą na `*_Autor`.
- Test path: `src/bpp/tests/test_models/test_soft_delete_guards.py`.

Guard liczy rozdziały (dzieci self-FK) przez `global_objects` (spec §2.6 — soft-deletowane rozdziały też blokują). Reverse `related_name="wydawnictwa_powiazane_set"`, ale liczymy spójnie helperem przez model docelowy: `(Wydawnictwo_Zwarte, "wydawnictwo_nadrzedne")`.

- [ ] **Failing test** — książka z rozdziałem → `ProtectedError`; bez rozdziałów → soft-delete OK:
  ```python
  @pytest.mark.django_db
  def test_ksiazka_matka_z_rozdzialem_protect(wydawnictwo_zwarte):
      rozdzial = baker.make(
          Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wydawnictwo_zwarte
      )
      assert rozdzial.wydawnictwo_nadrzedne_id == wydawnictwo_zwarte.pk
      with pytest.raises(ProtectedError):
          wydawnictwo_zwarte.delete()
      wydawnictwo_zwarte.refresh_from_db()
      assert wydawnictwo_zwarte.deleted_at is None  # guard zablokował


  @pytest.mark.django_db
  def test_ksiazka_bez_rozdzialow_soft_delete_ok(wydawnictwo_zwarte):
      wydawnictwo_zwarte.delete()
      wydawnictwo_zwarte.refresh_from_db()
      assert wydawnictwo_zwarte.deleted_at is not None


  @pytest.mark.django_db
  def test_ksiazka_matka_z_rozdzialem_w_koszu_nadal_protect(wydawnictwo_zwarte):
      rozdzial = baker.make(
          Wydawnictwo_Zwarte, wydawnictwo_nadrzedne=wydawnictwo_zwarte
      )
      rozdzial.delete()  # rozdział w koszu
      assert not Wydawnictwo_Zwarte.objects.filter(pk=rozdzial.pk).exists()
      with pytest.raises(ProtectedError):
          wydawnictwo_zwarte.delete()  # soft-deletowany rozdział też blokuje
  ```
- [ ] **Run → FAIL:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k "ksiazka"` — bez guarda książka-matka skasuje się mimo rozdziału (test PROTECT pęka) lub `deleted_at` zostanie ustawione.
- [ ] **Implementacja** — w `Wydawnictwo_Zwarte.delete()` (z fazy 02) dodaj na początku:
  ```python
  def delete(self, *args, user=None, reason="", **kwargs):
      from bpp.models.soft_delete import raise_if_has_protected_children

      raise_if_has_protected_children(
          self,
          [(Wydawnictwo_Zwarte, "wydawnictwo_nadrzedne")],
          label="książki (ma rozdziały)",
      )
      # ... istniejąca logika fazy 02: ustaw deleted_at, kaskada na *_Autor ...
      return super().delete(*args, **kwargs)  # lub istniejący return fazy 02
  ```
  **NIE gub kaskady na `*_Autor` z fazy 02** — guard wstawiamy WYŁĄCZNIE przed nią; reszta ciała `delete()` bez zmian.
- [ ] **Run → PASS:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k "ksiazka"`
- [ ] **Regresja kaskady fazy 02:** `uv run pytest src/bpp/tests/test_models/test_wydawnictwo_zwarte.py` — kaskada na `*_Autor` nadal działa dla książki bez rozdziałów.
- [ ] `ruff format` + `ruff check` na `wydawnictwo_zwarte.py`, teście.
- [ ] **Commit:** `feat(soft-delete): guard Wydawnictwo_Zwarte.delete() blokuje gdy ma rozdziały`

---

### Zadanie 6 — Symulacja merge: husk po transferze prac soft-deletuje się

**Files:**
- Test path: `src/bpp/tests/test_models/test_soft_delete_guards.py`.

Weryfikuje spec §3.3 / overview: merge przenosi wszystkie typy prac na autora głównego, potem woła `autor.delete()` na pustym duplikacie — guard go przepuszcza. Test symuluje to bez wołania całego merge'a (przenosi `Wydawnictwo_Ciagle_Autor` na głównego, potem usuwa husk).

- [ ] **Failing test** — (powinien przejść od razu, bo guard z Zadania 3 już działa; pełni rolę dowodu „merge nie jest zablokowany"):
  ```python
  @pytest.mark.django_db
  def test_husk_po_transferze_prac_soft_delete_ok(
      wydawnictwo_ciagle,
      autor_jan_kowalski,
      autor_jan_nowak,
      jednostka,
      typy_odpowiedzialnosci,
  ):
      # duplikat ma pracę
      wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)
      wca = Wydawnictwo_Ciagle_Autor.global_objects.get(autor=autor_jan_nowak)
      # merge: przenieś autorstwo na autora głównego (jak utils/merge.py:223)
      wca.autor = autor_jan_kowalski
      wca.save()
      # husk (autor_jan_nowak) jest teraz pusty → guard przepuszcza
      autor_jan_nowak.delete()
      autor_jan_nowak.refresh_from_db()
      assert autor_jan_nowak.deleted_at is not None
  ```
- [ ] **Run → PASS:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -k test_husk_po_transferze`
- [ ] **Regresja merge (smoke):** `uv run pytest src/deduplikator_autorow/` — merge nadal przechodzi (PROTECT nie psuje, bo husk pusty w chwili `delete()`).
- [ ] `ruff format` + `ruff check` na teście.
- [ ] **Commit:** `test(soft-delete): husk autora po transferze prac soft-deletuje się (merge)`

---

### Zadanie 7 — Pełny przebieg testów fazy + sanity migracji

**Files:** brak zmian; tylko weryfikacja.

- [ ] **Cały plik guardów:** `uv run pytest src/bpp/tests/test_models/test_soft_delete_guards.py -v` — wszystkie zielone.
- [ ] **Brak driftu migracji:** `uv run python src/manage.py makemigrations bpp --check --dry-run` → „No changes detected".
- [ ] **Regresja modeli + merge:** `uv run pytest src/bpp/tests/test_models/ src/deduplikator_autorow/` — zielone (PROTECT/guard nie psują istniejących ścieżek).
- [ ] `ruff check src/bpp` (zmienione) + `ruff format --check` na plikach fazy.
- [ ] **Commit (jeśli cokolwiek doszło):** `chore(soft-delete): zielona faza 04 — guardy PROTECT`

---

## Definicja ukończenia fazy 04

- Helper `raise_if_has_protected_children(instance, relations, label)` w `src/bpp/models/soft_delete.py` — liczy przez `global_objects`, rzuca `django.db.models.ProtectedError` z komunikatem PL.
- FK `CASCADE→PROTECT` (migracja state-only) na: `Wydawnictwo_Ciagle_Autor.autor`, `Wydawnictwo_Zwarte_Autor.autor`, `Patent_Autor.autor`, `Praca_Doktorska.autor`, `Wydawnictwo_Zwarte.wydawnictwo_nadrzedne`. Habilitacja bez zmian (już PROTECT).
- `Autor` jest `SoftDeleteModel`; override `delete(self, *args, user=None, reason="", **kwargs)` z guardem (5 relacji przez `global_objects`), bez kaskady do `*_Autor`. Autor bez prac → husk.
- `Wydawnictwo_Zwarte.delete()` ma guard na rozdziały PRZED kaskadą fazy 02 (kaskada zachowana).
- Testy: każdy typ pracy blokuje, praca-tylko-w-koszu blokuje, husk po merge przechodzi, książka z rozdziałem (też w koszu) blokuje, książka bez rozdziałów soft-deletuje się.
- `makemigrations --check --dry-run` czysty; regresja `test_models/` + `deduplikator_autorow/` zielona.
