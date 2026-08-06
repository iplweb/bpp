# Soft-delete publikacji + autorów — Plan-indeks (00)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement these plans task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wdrożyć odwracalny soft-delete dla 5 typów publikacji + wąską kaskadę na `*_Autor`, soft-delete autora bez prac (z PROTECT dla autora/książki z zależnościami), wycofanie z PBN przez kolejkę, audyt `SoftDeleteLog` i wsparcie w adminie superusera.

**Architecture:** `django-soft-delete` (`SoftDeleteModel`) na 5 modelach publikacji + 3 through-modelach `*_Autor`. Spójność cache wymaga **trzech** elementów naraz (filtr w widoku źródłowym + gałąź kasująca w funkcji refresh + regeneracja bramki `WHEN`) — patrz box „Koordynacja" niżej; wersja „jeden mechanizm wystarczy" została obalona 2026-08-06. Override `delete()` robi wąską kaskadę na `*_Autor`. PBN-wycofanie: jeden prymityw, dwa wejścia (kolejka + synchroniczne). `SoftDeleteLog` zasilany sygnałami pakietu; on też kasuje/przelicza `Cache_Punktacja_*`.

**Tech Stack:** Django, PostgreSQL (triggery **PL/pgSQL** + widoki), `django-soft-delete>=1.0.23`, `django-denorm-iplweb`, Celery + `pbn_export_queue`, pytest + model_bakery.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md)

---

## Plany fazowe (wykonywać w kolejności)

| # | Plik | Zakres | Zależy od |
|---|---|---|---|
| 01 | `2026-06-04-soft-delete-01-autor-trigger-widoki.md` | `*_Autor` → SoftDeleteModel; widoki `bpp_*_autorzy` + **gałąź kasująca w funkcjach refresh** + **regeneracja bramki `WHEN`**; spójność weryfikowana surowym SQL-em (NIE `full_refresh()`) | — |
| 02 | `2026-06-04-soft-delete-02-publikacje.md` | 5 modeli → SoftDeleteModel; override `delete()`/`restore()` z wąską kaskadą na `*_Autor`; `slug` warunkowy unique; przeplecenie menedżerów | 01 |
| 03 | `2026-06-04-soft-delete-03-audyt-kategorii-b.md` | przełączenie import/dedup/PBN-matching na `global_objects`; jawny `.hard_delete()` w `pbn_import`; audyt 128 miejsc `*_Autor.objects` | 02 |
| 04 | `2026-06-04-soft-delete-04-guardy-protect.md` | flip FK `CASCADE→PROTECT` (autor, doktorat, `wydawnictwo_nadrzedne`); guard w soft `delete()` (autor + książka-matka); soft-delete husku autora | 02 |
| 05 | `2026-06-04-soft-delete-05-pbn-wycofanie.md` | prymityw `wycofaj_oswiadczenia()`; `pbn_export_queue.operacja = WYSYLKA\|WYCOFANIE` (wejście async) + wywołanie bezpośrednie (sync); restore → `WYSYLKA`; integracja `SentData` | 02 |
| 06 | `2026-06-04-soft-delete-06-softdeletelog.md` | model `SoftDeleteLog`; receivery `post_soft_delete`/`post_restore`/`post_hard_delete`; wstrzykiwanie `user`; **kasowanie/przeliczanie `Cache_Punktacja_*`** | 02, 05 |
| 07 | `2026-06-04-soft-delete-07-admin.md` | admin superuser-only: kosz/filtr/przywróć/usuń-trwale/powód (5 modeli + Autor); jeden hook usera | 04, 06 |
| 08 | `2026-06-04-soft-delete-08-testy-regresji.md` | pełna suita regresji: PBN duplikaty/wycofanie, dashboard, import, ewaluacja, merge autorów, API | 01–07 |

---

## ✅ Koordynacja: trigger cache — BLOKER ZDJĘTY (2026-08-06)

Optymalizacja triggera **wylądowała** (PR #363: `0421_cache_trigger_pk_filter`,
`0429_cache_trigger_v3`, `0432_cache_trigger_plpgsql`,
`0433_cache_trigger_when_gate`). Gałąź `perf/cache-trigger-pk-filter` już nie
istnieje; ta gałąź jest zrebasowana na `dev`.

**Inwariant, o którego przetrwanie pytał poprzedni box, NIE przetrwał** —
i to zmienia zakres fazy 01:

| Poprzednie założenie | Stan faktyczny (zweryfikowany testem) |
|---|---|
| trigger robi bezwarunkowy `DELETE` przed upsertem | **NIE** — funkcja refresh to czysty `INSERT ... SELECT ... ON CONFLICT DO UPDATE`; odfiltrowanie wiersza z widoku daje no-op, stary wiersz przeżywa w `_mat` |
| UPDATE ustawiający `deleted_at` doleci do triggera | **NIE** — bramka `WHEN` z `0433` zna tylko kolumny zasilające widok, a `django-soft-delete` zapisuje przez `save(update_fields=[...])` |

Dowód: `src/bpp/tests/test_cache/test_soft_delete_preconditions.py` — dwa
kanarki, **zielone na obecnym kodzie** (przypinają stan „soft-delete by nie
zadziałał"). Faza 01 odwraca ich asercje.

**NOWY ZAKRES FAZY 01 — trzy elementy zamiast jednego, wszystkie obowiązkowe:**

1. filtr `deleted_at IS NULL` w widokach źródłowych `bpp_*_autorzy`,
2. **gałąź kasująca** w funkcjach refresh (`IF NEW.deleted_at IS NOT NULL THEN
   DELETE ... RETURN NULL`) — wzorzec już w kodzie: gałąź doktorat/habilitacja
   w `_create_rekord_function` (`0432`),
3. **regeneracja bramki `WHEN`** — `RunPython` wołający logikę `forward()`
   z `0433`; `deleted_at` wejdzie do bramki sam, przez `pg_depend`, bo punkt 1
   wstawił ją do `WHERE` widoku. **Kolejność: 1 → 3.**

Szczegóły i uzasadnienie: §2.1 specu.

---

## Wspólne kontrakty (PINNED — wszystkie fazy używają tych nazw VERBATIM)

### Pakiet `django-soft-delete` (punkt wyjścia, nie zmieniamy)
- `SoftDeleteModel` — abstrakcyjny; pola `deleted_at`, `restored_at`, `transaction_id`.
- Menedżery: `objects` (`SoftDeleteManager`, ukrywa skasowane), `global_objects` (`GlobalManager`, wszystkie), `deleted_objects` (`DeletedManager`, tylko skasowane).
- Metody instancji: `.delete()` (soft, woła `self.save(update_fields=[...])` + `post_soft_delete`), `.hard_delete()`, `.restore()`.
- `SoftDeleteQuerySet.delete()` iteruje per-instancję (`for obj in self.iterator(): obj.delete()`) — bezpieczny dla sygnałów. **NIE** robi bulk update.
- Sygnały (`django_softdelete/signals.py`): `post_soft_delete`, `post_hard_delete`, `post_restore`.
- ⚠️ **`strict` jest ASYMETRYCZNE:** `delete(strict=False)`, ale `restore(strict=True)`. Czyli domyślna kaskada `delete()` **nie krzyknie** na nie-soft dzieciach — po cichu po nich przejedzie. Kolejny powód, by nie polegać na kaskadzie pakietu (§2.2 specu).
- ⚠️ **`delete()` zapisuje przez `save(update_fields=['deleted_at','restored_at','transaction_id'])`** — to jest przyczyna, dla której bramka `WHEN` triggera cache nie przepuszcza soft-delete (i dla której `ostatnio_zmieniony`/`auto_now` NIE jest bumpowany).

### Nowy moduł `src/bpp/models/soft_delete.py` (tworzy faza 01)
```python
from django_softdelete.managers import (
    SoftDeleteQuerySet, SoftDeleteManager, DeletedManager, GlobalManager,
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
- Tu też ląduje **guard zależności** (faza 04):
```python
def raise_if_has_protected_children(instance, relations: list[str], label: str):
    """relations: nazwy reverse-managerów liczone przez global_objects.
    Rzuca django.db.models.ProtectedError gdy są dzieci."""
```

### `SoftDeleteLog` — `src/bpp/models/soft_delete_log.py` (tworzy faza 06)
Pola PINNED: `content_type` (FK ContentType), `object_id` (PositiveIntegerField, db_index), `content_object` (GenericForeignKey), `akcja` (`models.TextChoices`: `DELETE="delete"`, `RESTORE="restore"`, `HARD_DELETE="hard_delete"`), `user` (FK `AUTH_USER_MODEL`, null=True, on_delete=SET_NULL), `timestamp` (DateTimeField auto_now_add, db_index), `powod` (TextField blank, default=""), `pbn_queue_entry` (FK `pbn_export_queue.PBN_Export_Queue`, null=True, on_delete=SET_NULL), `pbn_status` (CharField blank).

### `pbn_export_queue` rozszerzenie (faza 05)
- Nowe pole na `PBN_Export_Queue`: `operacja = models.CharField(choices=Operacja.choices, default=Operacja.WYSYLKA)` gdzie `class Operacja(models.TextChoices): WYSYLKA="wysylka"; WYCOFANIE="wycofanie"`.
- Gałąź w logice wysyłki: `WYCOFANIE` → `client.delete_all_publication_statements(pbn_uid)` (`src/pbn_api/client/mixins/institutions.py:87`).

### Wstrzykiwanie `user` (PINNED — API thread-local, faza 06 tworzy, 07 używa)
- Override sygnatury: `delete(self, *args, user=None, reason="", **kwargs)` i `restore(self, *args, user=None, **kwargs)`.
- **Kanoniczne API (faza 06, `src/bpp/models/soft_delete_context.py`):** context manager `soft_delete_context(user=None, reason="")` (thread-local, reentrant — wąska kaskada `*_Autor` dziedziczy kontekst rodzica) + akcesory `get_soft_delete_user()` / `get_soft_delete_reason()`. Receivery sygnałów czytają akcesory (sygnał nie niesie usera).
- **Faza 07 (admin) używa `soft_delete_context`** — jeden hook (`delete_model`/`delete_queryset`/akcja „Przywróć") owija operację w `with soft_delete_context(user=request.user, reason=...):`. Ten sam moment ma w przyszłości zasilić `reversion.set_user` (patrz „Kontrakty z reversion"). NIE wymyślać osobnego `set/get/clear_soft_delete_user` — używać `soft_delete_context`.
- **`zamowil` w `pbn_export_queue` jest NOT NULL** — gdy `user is None` (operacje systemowe/celery), zakolejkowanie używa konta technicznego (`get_or_create`), nie `None`.
- Operacje systemowe (merge autora, celery): `user=None` w `SoftDeleteLog` (FK nullable), konto techniczne tylko dla `zamowil` kolejki.

### Punkty zaczepienia w istniejącym kodzie (zweryfikowane)
- Rejestracja sygnałów: `src/bpp/apps.py` → `BppConfig.ready()` (linia 8).
- Menedżery publikacji: `src/bpp/models/wydawnictwo_ciagle.py:87` (`Wydawnictwo_Ciagle_Manager`), `wydawnictwo_zwarte.py:167` (`Wydawnictwo_Zwarte_Manager`), oba po `ManagerModeliZOplataZaPublikacjeMixin` (`src/bpp/models/abstract/fees.py`).
- Through-model FK autora: `src/bpp/models/abstract/authors.py:25` (`autor = models.ForeignKey("bpp.Autor", CASCADE)`).
- Doktorat FK: `src/bpp/models/praca_doktorska.py:153` (CASCADE). Habilitacja: `praca_habilitacyjna.py:47` (O2O PROTECT, bez zmian).
- Self-FK rozdziałów: `src/bpp/models/wydawnictwo_zwarte.py:212` (`wydawnictwo_nadrzedne`, CASCADE).
- `unique_together` na through: `src/bpp/models/wydawnictwo_ciagle.py:73-77` (analogicznie zwarte/patent) — do zamiany na warunkowy `UniqueConstraint`, §2.2b specu.
- **Trigger (AKTUALNY):** `src/bpp/migrations/0432_cache_trigger_plpgsql.py` — generator 8 funkcji refresh + 8 delete (PL/pgSQL, upsert bez DELETE); `0433_cache_trigger_when_gate.py` — generator bramki `WHEN` z `pg_depend`. ⚠️ Funkcja `bpp_refresh_cache()` **nie istnieje** (DROP w `0432`); `0399`/`0001_cache_functions.sql` to historia.
- Widoki źródłowe: definicje odtwarzane wielokrotnie; **ostatnia wersja per-typ w `0421_cache_trigger_pk_filter.sql`** (dodaje `object_id_raw`). `bpp_rekord` = UNION 5 widoków per-typ.
- `Rekord` czyta **tabelę `bpp_rekord_mat`**: `src/bpp/models/cache/rekord.py:382-386`. Widok `bpp_rekord` → `RekordView`, `:394-396`.
- `full_refresh()` = `denorm.rebuildall`, NIE re-projekcja `_mat`: `src/bpp/models/cache/rekord.py:121-127`.
- `Cache_Punktacja_Autora`/`_Dyscypliny`: `src/bpp/models/cache/punktacja.py`; zapis w `src/bpp/models/sloty/core.py:401,439`; odczyt m.in. `ewaluacja_optymalizacja/utils.py:182`, `.../evaluation_browser/prefetch.py:41`, `oswiadczenia/views.py:353`.
- `verify_cache`: `src/bpp/management/commands/verify_cache.py` — **martwy stub**, nie używać.
- Wzorzec testów cache: `src/bpp/tests/test_cache/test_cache_plpgsql_port.py`. Kanarki soft-delete: `test_soft_delete_preconditions.py`.
- Admin tych modeli: `src/bpp/admin/{wydawnictwo_ciagle,wydawnictwo_zwarte,patent,praca_doktorska,praca_habilitacyjna,autor}.py`; mixiny `src/bpp/admin/helpers/mixins.py`.
- PBN klient: `src/pbn_api/client/mixins/institutions.py:87`. `SentData`: `src/pbn_api/models/sentdata.py`. Kolejka: `src/pbn_export_queue/{models,tasks,admin}.py`.
- Merge autorów: `src/deduplikator_autorow/views/merge.py:155`, `utils/merge.py:191,284,354`.
- Precedens wzorca: `src/zglos_publikacje/models.py` (`Zgłoszenie_Publikacji` już `SoftDeleteModel`).

---

## Kontrakty z django-reversion (NIE implementujemy — odłożone; tylko nie łamiemy)

Równoległy spec [`../specs/2026-06-04-historia-zmian-reversion-design.md`](../specs/2026-06-04-historia-zmian-reversion-design.md) (odłożony do PO soft-delete) wymaga zostawienia czystych szwów:

1. **`save()` per-instancja (twardy warunek).** Override `delete()`/`restore()` oraz kaskada na `*_Autor` MUSZĄ iść przez per-instancję `.delete()`/`save()`, **nigdy** bulk `queryset.update(deleted_at=...)`. Inaczej `post_save` nie odpali → przyszła historia reversion cicho zniknie. Gate w `BppSoftDeleteQuerySet.update()` to egzekwuje fail-fast.
2. **Jeden hook usera.** Punkt wstrzyknięcia `request.user` w adminie (faza 07) ma być jedną metodą, którą reversion później doczepi do `set_user`.
3. **Świadomość recover.** Warstwa admina (faza 07) zostawia miejsce na późniejsze ukrycie reversion „recover deleted" (recover po `hard_delete` wskrzeszałby rekord poza przepływem — bez `WYSYLKA`, bez `SoftDeleteLog`, łamiąc warunkowy unique `slug`).

---

## Mapa plików (tworzonych/modyfikowanych w całym wdrożeniu)

**Tworzone:**
- `src/bpp/models/soft_delete.py` (queryset+gate, managery, guard helper) — faza 01/04
- `src/bpp/models/soft_delete_log.py` (model `SoftDeleteLog`) — faza 06
- `src/bpp/migrations/0XXX_*` — migracje pól soft-delete (`*_Autor`, 5 publikacji), `slug` constraint, FK flips, `SoftDeleteLog`, `pbn_export_queue.operacja`
- `src/bpp/migrations/0XXX_soft_delete_*_views.py` — `RunPython`: filtr `deleted_at` w widokach źródłowych + gałąź kasująca w funkcjach refresh + regeneracja bramki `WHEN` (faza 01 dla `bpp_*_autorzy`, faza 02 dla `bpp_*_view`)
- `src/bpp/receivers/soft_delete.py` (lub w istniejącym module sygnałów) — receivery — faza 06

**Modyfikowane (główne):**
- modele: `wydawnictwo_ciagle.py`, `wydawnictwo_zwarte.py`, `patent.py`, `praca_doktorska.py`, `praca_habilitacyjna.py`, `autor.py`, `abstract/authors.py`
- admin: jw. 6 plików + `admin/helpers/mixins.py`
- `pbn_export_queue/models.py`, `tasks.py`, `admin.py`
- `pbn_api/models/sentdata.py`
- `pbn_import/utils/publication_import.py` (jawny `.hard_delete()`)
- `import_common/`, `crossref_bpp/`, `deduplikator_publikacji/`, `pbn_integrator/`, `ewaluacja_optymalizacja/` (audyt `global_objects`)
- `src/bpp/apps.py` (rejestracja receiverów)

---

## Wykonanie

Fazy 01→08 sekwencyjnie. Po każdej fazie: pełne testy danej fazy zielone + `ruff check`/`format` + commit. Trigger/cache (01) najwrażliwsze — testy spójności przed czymkolwiek innym. Gałąź: `feat/soft-delete` (ten worktree).
