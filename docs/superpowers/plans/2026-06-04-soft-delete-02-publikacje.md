# Soft-delete — Faza 02: Publikacje (5 modeli → SoftDeleteModel + wąska kaskada na `*_Autor`) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Każdy krok TDD: napisz padający test → uruchom (oczekiwany FAIL) → minimalna implementacja → uruchom (PASS) → commit.

> ⚠️ **OSTRZEŻENIE — CZYTAJ PRZED STARTEM (dopisane po naprawie blokerów
> fazy 01, 2026-08-06).** Faza 01 odkrywała konsumentów surowych tabel
> `*_autor` **pojedynczo, przez awarie** — najpierw bramka cache'u, potem
> bramka denorma, `unique_together`, legacy constraint z 2018, a na końcu
> finalna recenzja znalazła jeszcze trzy widoki pochodne czytające surowe
> tabele bez filtra na `deleted_at`. Faza 02 (soft-delete PUBLIKACJI:
> `bpp_wydawnictwo_ciagle`, `bpp_wydawnictwo_zwarte`, `bpp_patent`,
> `bpp_praca_doktorska`, `bpp_praca_habilitacyjna`) trafi na dokładnie ten
> sam problem, jeśli nie zaadresuje go z góry. Trzy obowiązkowe rzeczy:
>
> **(a) Rozszerz kanarka katalogowego o 5 tabel publikacji.** Test
> `src/bpp/tests/test_soft_delete/test_kanarek_katalogowy.py` (dodany razem
> z tym ostrzeżeniem) trzyma listę tabel objętych soft-delete jako stałą
> modułową `TABELE_SOFT_DELETE` — dopisanie 5 tabel publikacji ma być
> jednolinijkową zmianą (skonstruowaną tak celowo). Kanarek odpytuje żywy
> `pg_views` i pilnuje, że KAŻDY widok czytający którąkolwiek z tych tabel
> filtruje po `deleted_at`, chyba że jest na jawnej liście wyjątków z
> uzasadnieniem. Rozszerz listę na starcie fazy 02, ZANIM zaczniesz pisać
> DDL — kanarek od razu zacznie łapać widoki, które trzeba naprawić, zamiast
> odkrywać je po raz drugi przez awarie na produkcji.
>
> **(b) Sprawdź `count()`/agregaty w widokach pochodnych pod kątem
> `FILTER` vs warunek w `JOIN`/`WHERE`.** Wzorzec z migracji `0494`
> (`bpp/migrations/0494_liczba_autorow_bez_skasowanych.py`, faza 01):
> `bpp_<typ>_view` liczy `count(<tabela>_autor.autor_id) AS liczba_autorow`
> przez `LEFT JOIN` do tabeli `*_autor`. Dopisanie `deleted_at IS NULL` do
> `WHERE`/`JOIN ... ON` zamieniłoby `LEFT JOIN` w efektywny `INNER JOIN` dla
> publikacji, którym soft-deletowano WSZYSTKICH autorów — cała publikacja
> wypadłaby z widoku, więc z `bpp_rekord_mat` i z całego serwisu (dokładnie
> ten błąd, gdyby ktoś naiwnie dopisał warunek do `WHERE`). Właściwy wzorzec
> to `count(...) FILTER (WHERE ... deleted_at IS NULL)` — rusza wyłącznie
> licznik, nie krotność joina. Dla soft-delete PUBLIKACJI analogiczne
> ryzyko dotyczy każdego agregatu w `bpp_*_view`/`bpp_rekord` liczącego coś
> przez `LEFT JOIN` do tabeli publikacji.
>
> **(c) Przejrzyj `bpp_nowe_sumy_*` i `rozbieznosci_dyscyplin` pod kątem
> `deleted_at` PUBLIKACJI** (nie tylko autora — to już zrobione w fazie 01,
> migracje `0495_nowe_sumy_bez_skasowanych` i
> `rozbieznosci_dyscyplin/0022_rozbieznosci_zrodel_bez_skasowanych`). Te
> same widoki (i prawdopodobnie inne w `ranking_autorow`) czytają też
> kolumny/joiny do tabel publikacji — sprawdź `pg_depend`, nie tylko grep,
> czy po dodaniu `deleted_at` na `bpp_wydawnictwo_ciagle` itd. te widoki
> wymagają analogicznej poprawki.
>
> Raport z naprawy blokerów fazy 01 (metoda, mutation test kanarka, pełna
> lista sprawdzonych widoków):
> `.superpowers/sdd/2026-06-04-soft-delete-01-autor-trigger-widoki/kanarek-report.md`.

**Goal:** Uczynić 5 modeli publikacji (`Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`, `Praca_Doktorska`, `Praca_Habilitacyjna`, `Patent`) `SoftDeleteModel`-ami z **wąską, kontrolowaną kaskadą** soft-delete na własne wiersze `*_Autor` (`Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor`) pod wspólnym `transaction_id`, **bez** refleksyjnej kaskady pakietu (która ruszyłaby `*_Streszczenie` itd.). Zamienić `slug unique=True` na warunkowy `UniqueConstraint` (reuse slug po soft-delete). Przepleść filtr soft-delete z istniejącymi menedżerami `Wydawnictwo_*_Manager` (mixin opłat) przez wspólny QuerySet/MRO, bez nadpisywania metod fees.

**Architecture:** `django-soft-delete` daje `SoftDeleteModel` (pola `deleted_at`/`restored_at`/`transaction_id`, menedżery `objects`/`global_objects`/`deleted_objects`, sygnały `post_soft_delete`/`post_restore`/`post_hard_delete`). Faza 01 utworzyła `src/bpp/models/soft_delete.py` z `BppSoftDeleteQuerySet` (gate na bulk `update(deleted_at=...)`), `BppSoftDeleteManager`, `BppGlobalManager` oraz uczyniła 3 modele `*_Autor` SoftDeleteModel-ami — wraz z DDL-em dla **ścieżki autorstwa** (widoki `bpp_*_autorzy` + gałąź kasująca w `bpp_refresh_autor_*` + bramka `WHEN`). ⚠️ **Dla 5 tabel publikacji ten sam DDL trzeba zrobić w TEJ fazie** — Task 2b. **Ta faza zależy od 01.** Tu nadpisujemy `delete()`/`restore()` na 5 modelach: per-instancja `save()` (NIGDY bulk `update`), jawna wąska kaskada na `autorzy_set` (related_name `*_Autor`→publikacja) przez `.delete(transaction_id=...)`/`.restore(transaction_id=...)` na każdym wierszu (kontrakt z reversion: zawsze per-instancja).

**Tech Stack:** Django, PostgreSQL, `django-soft-delete>=1.0.23`, `django-denorm-iplweb` (slug jest polem `@denormalized`!), pytest + `model_bakery.baker`. Python wyłącznie przez `uv run`. Linia ≤88 znaków (ruff). Komentarze/komunikaty po polsku.

**Spec źródłowy:** [`../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`](../specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md) (§2.2 wąska kaskada, §2.3 slug, §2.4 menedżery). **Indeks (kontrakty PINNED):** [`2026-06-04-soft-delete-00-overview.md`](2026-06-04-soft-delete-00-overview.md).

---

## 🧹 Sprzątanie `bpp_kronika_*` — jedno zadanie, nie po kawałku (decyzja 2026-08-07)

Próba usunięcia trzech martwych widoków `bpp_kronika_{wydawnictwo_ciagle,
wydawnictwo_zwarte,patent}_view` w fazie 01 została **zablokowana**: zależą od
nich dwa widoki nadrzędne, `bpp_kronika_all_unsorted_view` (UNION pięciu) i
`bpp_kronika_view` (`0443_drop_pl_PL_collation.sql:13-14,30-31`). Goły
`DROP VIEW` bez `CASCADE` nie przejdzie.

Zweryfikowano: **cała siódemka jest martwa** — zero konsumentów w kodzie,
szablonach, `Meta.db_table`, `flexible_reports` i surowym SQL-u.

**Decyzja: skasować wszystkie 7 naraz, w TEJ fazie**, bo faza 02 i tak dołoży
`bpp_kronika_praca_{doktorska,habilitacyjna}_view` do zakresu kanarka
(rozszerzenie `TABELE_SOFT_DELETE` o tabele publikacji) i wtedy trzeba by je
weryfikować osobno. Jedna migracja, jedna decyzja, pełny graf zależności:

```
bpp_kronika_view
  └── bpp_kronika_all_unsorted_view
        ├── bpp_kronika_wydawnictwo_ciagle_view
        ├── bpp_kronika_wydawnictwo_zwarte_view
        ├── bpp_kronika_patent_view
        ├── bpp_kronika_praca_doktorska_view      ← żywotność do potwierdzenia
        └── bpp_kronika_praca_habilitacyjna_view  ← żywotność do potwierdzenia
```

Kolejność `DROP`: od góry (parasole) w dół. Migracja **odwracalna** — `backward`
odtwarza całą siódemkę; wyjdź z `pg_get_viewdef()` przed skasowaniem.
Po zrobieniu: usuń wpisy z `WYJATKI` w `test_kanarek_katalogowy.py`.

Jeśli któryś z dwóch niezweryfikowanych okaże się mieć konsumenta — **nie
kasuj żadnego**, zostaw wyjątki i zgłoś.

---

## ⚠️ KOLEJNOŚĆ WYKONANIA (taski NIE stoją w dokumencie w kolejności wykonania)

Taski dopisywane po rewizjach wylądowały poza numeracją. Wykonuj w TEJ kolejności:

| # | Task | Dlaczego tu |
|---|---|---|
| 1 | Task 1 — mixin `delete()`/`restore()` | fundament |
| 2 | Task 2 — 5 modeli + migracja pól | kolumny muszą istnieć przed DDL |
| 3 | **Task 2b** — widoki + gałąź kasująca + bramka `WHEN` | czyta `deleted_at` z kroku 2 |
| 4 | **Task 2c** — bramka denorm | drugi system triggerów |
| ~~5~~ | ~~Task 3 — `slug` warunkowy unique~~ | **NIEWYKONANY świadomie** — slug zawiera `pk`, kolizja niemożliwa; patrz box przy tasku |
| 6 | **Task 3b** — `unique_together` na `*_Autor` | niezależny |
| **3.5** | **Task 2d — sumy + rozbieżności (6 widoków)** | **DOPISANY** — inwentaryzacja kanarka na starcie fazy; w planie był tylko ostrzeżeniem (c) |
| 7 | Task 4 — przeplecenie menedżerów | — |
| 8 | Task 5 — testy integracyjne | wymaga 1-7 |
| 9 | Task 6 — weryfikacja fazy | ostatni |

**Numery migracji nadawaj sekwencyjnie w KOLEJNOŚCI WYKONANIA**, nie wg numerów
z nagłówków tasków (te są orientacyjne i już się rozjechały). Przed każdą
migracją: `ls src/bpp/migrations/*.py | tail -3`.

---

## Założenia wejściowe (z fazy 01 — VERBATIM, nie zmieniać)

- `src/bpp/models/soft_delete.py` istnieje i eksportuje `BppSoftDeleteQuerySet`, `BppSoftDeleteManager`, `BppGlobalManager` (kod w indeksie §"Nowy moduł").
- `BppSoftDeleteQuerySet.update()` rzuca `RuntimeError`, gdy w kwargs jest `deleted_at` lub `restored_at` (gate fail-fast). **Z tego wynika twardy zakaz `.update(deleted_at=...)` w tej fazie — kaskada MUSI iść per-instancja.**
- `Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` są już `SoftDeleteModel` (mają `deleted_at`, `.delete()`/`.restore()`/`global_objects`/`deleted_objects`).
- Related name `*_Autor` → publikacja: `autorzy_set` (potwierdzone: `wydawnictwo_ciagle.py:59`, `wydawnictwo_zwarte.py:68`, `patent.py:35`).

## Fakty z kodu (zweryfikowane — używaj tych nazw VERBATIM)

- `Wydawnictwo_Ciagle` (`src/bpp/models/wydawnictwo_ciagle.py:91`): `objects = Wydawnictwo_Ciagle_Manager()` (`:185`). Manager `Wydawnictwo_Ciagle_Manager(ManagerModeliZOplataZaPublikacjeMixin, models.Manager)` (`:87`).
- `Wydawnictwo_Zwarte` (`:176`): `objects = Wydawnictwo_Zwarte_Manager()` (`:197`). Manager `Wydawnictwo_Zwarte_Manager(ManagerModeliZOplataZaPublikacjeMixin, models.Manager)` (`:167`) z metodą `wydawnictwa_nadrzedne_dla_innych()`. Self-FK `wydawnictwo_nadrzedne` (`:202`, CASCADE — flip na PROTECT robi faza 04, NIE tu).
- `ManagerModeliZOplataZaPublikacjeMixin` (`src/bpp/models/abstract/fees.py:9`) — czysty mixin (NIE Manager), jedyna metoda `rekordy_z_oplata(self)` → `self.exclude(opl_pub_cost_free=None)`. Operuje na queryset menedżera, więc działa poprawnie nad każdym QuerySet-em.
- `Patent`, `Praca_Doktorska`, `Praca_Habilitacyjna` — **NIE mają** własnego menedżera (używają domyślnego `models.Manager` jako `objects`).
- `Praca_Doktorska.autor` FK CASCADE (`praca_doktorska.py:136`), `Praca_Habilitacyjna.autor` O2O PROTECT (`praca_habilitacyjna.py:42`). Te FK to **faza 04** — NIE ruszamy tu.
- **`slug` jest polem `@denormalized(models.SlugField, max_length=400, unique=True, db_index=True, null=True, blank=True)`** (denorm z `django-denorm-iplweb`), w: `wydawnictwo_ciagle.py:246`, `wydawnictwo_zwarte.py:325` (w `Wydawnictwo_Zwarte`), `patent.py:180`, `praca_doktorska.py:105` (w `Praca_Doktorska_Baza` → dziedziczone przez `Praca_Doktorska` **i** `Praca_Habilitacyjna`). Denorm field jest fizyczną kolumną w DB → migracja zmiany `unique=True`→`UniqueConstraint` jest realną migracją schematu.
- `Praca_Habilitacyjna` i `Praca_Doktorska` dziedziczą slug z `Praca_Doktorska_Baza` (abstract) — zmiana atrybutu pola w abstrakcie dotyka OBU modeli; migracje per model (każdy ma własną kolumnę `slug`).
- ⚠️ **Numeracja migracji (stan po zakończeniu fazy 01, 2026-08-06):** faza
  01 zajęła ostatecznie `0488`-`0495` w `bpp` (nie tylko `0488`/`0489` —
  patrz naprawa blokerów finalnej recenzji) plus
  `rozbieznosci_dyscyplin/0022`, więc ta faza startuje od `0496` w `bpp`.
  **Zweryfikuj liść przed startem** (`ls src/bpp/migrations/*.py | tail -3`)
  — `dev` żyje. Numery w tym planie są orientacyjne; kanoniczna jest
  kolejność. NIE modyfikuj istniejących migracji.
- `Zgloszenie_Publikacji` (`src/zglos_publikacje/models.py:60`) — precedens: po prostu dziedziczy `SoftDeleteModel` bez własnego menedżera.

## Kontrakt z reversion (PINNED — NIE łamać)

- `delete()`/`restore()` i kaskada na `*_Autor` idą **wyłącznie** przez per-instancja `.delete()`/`.restore()`/`save()`. **NIGDY** `autorzy_set.update(deleted_at=...)` ani `autorzy_set.all().delete()` jeśli to bulk — używamy pętli per-instancja, żeby `post_save`/sygnały odpaliły. Gate w `BppSoftDeleteQuerySet.update()` egzekwuje to fail-fast (test to weryfikuje).
- Sygnatury override: `delete(self, *args, user=None, reason="", **kwargs)` i `restore(self, *args, user=None, **kwargs)`. `user`/`reason` na razie tylko przepuszczamy do `super()`/sygnałów (konsumuje je faza 06); tu MUSZĄ istnieć w sygnaturze.

---

## Task 1: Mixin `delete()`/`restore()` z wąską kaskadą — `BppPublikacjaSoftDeleteMixin`

**Files:**
- Modify: `src/bpp/models/soft_delete.py` (dodaj klasę mixinu na końcu)
- Test path: `src/bpp/tests/test_soft_delete_publikacje.py` (nowy plik)

Mixin dziedziczy `SoftDeleteModel` i nadpisuje `delete()`/`restore()`: per-instancja `save()` rodzica, jawna wąska kaskada na `autorzy_set` (każdy wiersz `*_Autor` przez `.delete(transaction_id=...)`), bez refleksyjnej kaskady pakietu (`super().delete()` nie wołamy — sami ustawiamy `deleted_at` + emitujemy sygnał, żeby NIE ruszać `*_Streszczenie`).

> 🩹 **Poprawka 2026-08-06 (self-review) — kaskada NIE jest jednolita dla 5 modeli.**
> Pierwsza wersja twierdziła „wszystkie 5 modeli mają `autorzy_set` (potwierdzone)".
> **Nieprawda.** Dla doktoratu i habilitacji `autorzy_set` to **property**
> zwracająca atrapy (`src/bpp/models/praca_doktorska.py:30-70`):
> ```python
> @property
> def autorzy_set(self):
>     class FakeAutorDoktoratuHabilitacji:
>         autor = self.autor
>         ...
>     class FakeSet(list):
>         def all(self):
>             return self
>     ...
>     return FakeSet([ret])
> ```
> `FakeSet` to podklasa `list` — nie ma `.model`, a `FakeAutorDoktoratuHabilitacji`
> nie ma `.delete()`. Kaskada verbatim wywaliłaby się `AttributeError` na
> obu modelach (`delete()` przy `autorstwo.delete(...)`, `restore()` przy
> `self.autorzy_set.model`). Dlatego mixin ma `_model_through()` /
> `_autorstwa_do_kaskady()`, które zwracają `None`/`[]` dla publikacji bez
> through-modelu. Autor doktoratu/habilitacji leży na wierszu publikacji, więc
> kaskada nie jest tam potrzebna — sam soft-delete rekordu wystarcza.

- [ ] **Krok 1.1 — padający test: soft-delete publikacji kaskaduje na `*_Autor` tym samym `transaction_id`.**
  Dopisz do `src/bpp/tests/test_soft_delete_publikacje.py`:
  ```python
  import pytest
  from model_bakery import baker

  from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor


  @pytest.mark.django_db
  def test_soft_delete_publikacji_kaskaduje_na_autor_wspolny_txid():
      wc = baker.make(Wydawnictwo_Ciagle)
      a1 = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc)
      a2 = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc)

      wc.delete()

      wc.refresh_from_db()
      assert wc.deleted_at is not None
      assert wc.transaction_id is not None

      for a in (a1, a2):
          row = Wydawnictwo_Ciagle_Autor.global_objects.get(pk=a.pk)
          assert row.deleted_at is not None, "autorstwo nie zostało soft-skasowane"
          assert row.transaction_id == wc.transaction_id, "różny transaction_id"
  ```
- [ ] **Krok 1.2 — uruchom, oczekiwany FAIL** (kaskady jeszcze nie ma; `*_Autor` zostaje nieskasowane):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete_publikacje.py::test_soft_delete_publikacji_kaskaduje_na_autor_wspolny_txid -x
  ```
  Oczekiwane: `AssertionError: autorstwo nie zostało soft-skasowane` (lub `Wydawnictwo_Ciagle` nie jest jeszcze SoftDeleteModel → `AttributeError`/błąd importu; obie wersje to FAIL przed implementacją — implementację robią Task 1+2 razem).
- [ ] **Krok 1.3 — minimalna implementacja: mixin.** Dopisz do `src/bpp/models/soft_delete.py`:
  ```python
  import uuid

  from django.db import transaction
  from django.utils import timezone
  from django_softdelete.models import SoftDeleteModel
  from django_softdelete.signals import post_restore, post_soft_delete


  class BppPublikacjaSoftDeleteMixin(SoftDeleteModel):
      """Wąska, kontrolowana kaskada soft-delete: rodzic + własne wiersze
      `*_Autor` (related_name `autorzy_set`) pod wspólnym `transaction_id`.

      NIE uzywa refleksyjnej kaskady pakietu. UWAGA: delete() pakietu ma
      DOMYSLNIE strict=False (a restore() -- strict=True), wiec kaskada NIE
      krzyknelaby SoftDeleteException na *_Streszczenie /
      *_Zewnetrzna_Baza_Danych / Publikacja_Habilitacyjna -- po cichu by po
      nich przejechala. Kaskada zatrzymuje sie na *_Autor. Kontrakt z
      reversion: zawsze per-instancja save()/delete(), NIGDY bulk
      update(deleted_at=...).
      """

      class Meta:
          abstract = True

      def _model_through(self):
          """Model *_Autor tej publikacji, albo None (doktorat/habilitacja).

          Praca_Doktorska/Praca_Habilitacyjna NIE mają through-modelu — autor
          leży na wierszu publikacji, a `autorzy_set` jest tam PROPERTY
          zwracającą FakeSet z atrapami (patrz box pod kodem).
          """
          if isinstance(type(self).__dict__.get("autorzy_set"), property):
              return None
          return self.autorzy_set.model

      def _autorstwa_do_kaskady(self):
          """Wiersze *_Autor do soft-delete; pusto dla doktorat/habilitacja."""
          if self._model_through() is None:
              return []
          return list(self.autorzy_set.all())

      def delete(self, *args, user=None, reason="", **kwargs):
          now = timezone.now()
          txid = kwargs.pop("transaction_id", None) or uuid.uuid4()
          with transaction.atomic():
              # 1. wąska kaskada na własne *_Autor (per-instancja!)
              #    ⚠️ TYLKO gdy autorzy_set to prawdziwy related manager —
              #    patrz _przez_through() i box-ostrzeżenie pod kodem.
              for autorstwo in self._autorstwa_do_kaskady():
                  autorstwo.delete(transaction_id=txid)
              # 2. własne deleted_at + save (NIGDY bulk update)
              self.deleted_at = now
              self.restored_at = None
              self.transaction_id = txid
              self.save(
                  update_fields=["deleted_at", "restored_at", "transaction_id"]
              )
              post_soft_delete.send(sender=self.__class__, instance=self)
          return 1, {self._meta.label: 1}

      delete.alters_data = True

      def restore(self, *args, user=None, **kwargs):
          txid = self.transaction_id
          with transaction.atomic():
              # przywróć własne *_Autor skasowane tym samym transaction_id
              through = self._model_through()
              if txid is not None and through is not None:
                  for autorstwo in through.deleted_objects.filter(
                      rekord=self, transaction_id=txid
                  ):
                      autorstwo.restore(transaction_id=txid)
              self.deleted_at = None
              self.restored_at = timezone.now()
              self.transaction_id = None
              self.save(
                  update_fields=["deleted_at", "restored_at", "transaction_id"]
              )
              post_restore.send(
                  sender=self.__class__, instance=self, transaction_id=txid
              )

      restore.alters_data = True
  ```
  > Uwaga: `self.autorzy_set.all()` używa **domyślnego** menedżera `*_Autor` (`objects` ukrywa już-skasowane) — przy delete to OK (skasowane drugi raz nie szkodzi, a zwykle nie ma takich). `restore()` celowo czyta przez `deleted_objects` po `transaction_id`, bo `objects` ukrywa skasowane. `*_Autor.restore()` pochodzi z `SoftDeleteModel` (faza 01) — bez własnej kaskady (liść).
- [ ] **Krok 1.4** — implementacja sama nie przejdzie testu, dopóki `Wydawnictwo_Ciagle` nie dziedziczy mixinu (Task 2). NIE uruchamiaj jeszcze testu na PASS — przejdź do Task 2 (mixin + model muszą być razem). Po Task 2 wrócimy.
- [ ] **Krok 1.5 — commit szkieletu mixinu:**
  ```bash
  git add src/bpp/models/soft_delete.py src/bpp/tests/test_soft_delete_publikacje.py
  git commit -m "feat(soft-delete): mixin waskiej kaskady delete/restore na *_Autor

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 2: 5 modeli dziedziczy mixin + migracje pól `deleted_at`/`restored_at`/`transaction_id` + indeks

**Files:**
- Modify: `src/bpp/models/wydawnictwo_ciagle.py:91` (klasa `Wydawnictwo_Ciagle` — dopisz `BppPublikacjaSoftDeleteMixin` do baz)
- Modify: `src/bpp/models/wydawnictwo_zwarte.py:176` (klasa `Wydawnictwo_Zwarte`)
- Modify: `src/bpp/models/patent.py:62` (klasa `Patent`)
- Modify: `src/bpp/models/praca_doktorska.py:135` (klasa `Praca_Doktorska`)
- Modify: `src/bpp/models/praca_habilitacyjna.py:41` (klasa `Praca_Habilitacyjna`)
- Create: `src/bpp/migrations/0490_publikacje_soft_delete_fields.py`
- Test path: `src/bpp/tests/test_soft_delete_publikacje.py`

> **Kolejność MRO:** mixin dopisujemy jako **pierwszą** bazę (przed pozostałymi mixinami modelu), żeby jego `delete()`/`restore()` wygrały w MRO nad `models.Model.delete()`. NIE jako ostatnią. `BppPublikacjaSoftDeleteMixin(SoftDeleteModel)` wnosi też pola `deleted_at`/`restored_at`/`transaction_id` i menedżery — ale menedżery dla `Wydawnictwo_*` nadpiszemy w Task 4 (interleaving fees); dla `Patent`/`Praca_*` zostaną menedżery z `SoftDeleteModel`.

- [ ] **Krok 2.1 — dopisz mixin do baz 5 modeli.** Import na górze każdego pliku:
  ```python
  from bpp.models.soft_delete import BppPublikacjaSoftDeleteMixin
  ```
  i dodaj `BppPublikacjaSoftDeleteMixin,` jako **pierwszą** bazę klasy modelu. Np. w `wydawnictwo_ciagle.py`:
  ```python
  class Wydawnictwo_Ciagle(
      BppPublikacjaSoftDeleteMixin,
      ZapobiegajNiewlasciwymCharakterom,
      Wydawnictwo_Baza,
      ...
  ```
  Analogicznie `Wydawnictwo_Zwarte`, `Patent`, `Praca_Doktorska`, `Praca_Habilitacyjna`.
  > Uwaga `Praca_Doktorska`/`Praca_Habilitacyjna`: dziedziczą po `Praca_Doktorska_Baza`. Dodaj mixin jako pierwszą bazę **konkretnej** klasy (`Praca_Doktorska`, `Praca_Habilitacyjna`), NIE do abstraktu `Praca_Doktorska_Baza` (inaczej `Praca_Habilitacyjna.autor` O2O PROTECT + abstrakt namieszają w MRO; trzymamy mixin na klasach konkretnych).
- [ ] **Krok 2.2 — wygeneruj migrację pól:**
  ```bash
  uv run python src/manage.py makemigrations bpp --name publikacje_soft_delete_fields
  ```
  Oczekiwane: nowa migracja `0490_publikacje_soft_delete_fields.py` z `AddField` `deleted_at`/`restored_at`/`transaction_id` dla 5 modeli. Zweryfikuj nazwę pliku (`0490_`); jeśli numer inny — użyj faktycznego.
- [ ] **Krok 2.3 — dopisz indeks per model na `deleted_at`.** Do wygenerowanej migracji dołóż operacje `AddIndex` (lub edytuj `Meta.indexes` modeli i przegeneruj). Ręcznie w migracji, po `AddField`-ach:
  ```python
  from django.db import migrations, models

  # w operations, dla każdego z 5 modeli:
  migrations.AddIndex(
      model_name="wydawnictwo_ciagle",
      index=models.Index(
          fields=["deleted_at"], name="wc_deleted_at_idx"
      ),
  ),
  # ... analogicznie: wz_deleted_at_idx, patent_deleted_at_idx,
  #     pdok_deleted_at_idx, phab_deleted_at_idx
  ```
  > Nazwy indeksów ≤30 znaków (limit Postgres dla auto-nazw nie obowiązuje przy jawnej nazwie, ale trzymaj krótkie i unikalne). Na produkcji rozważ `AddIndexConcurrently` (osobna migracja `atomic=False`) — dla dużych tabel; tu wystarcza zwykły `AddIndex` (decyzja deploymentu, poza zakresem testów).
- [ ] **Krok 2.4 — sprawdź spójność migracji:**
  ```bash
  uv run python src/manage.py makemigrations --check --dry-run bpp
  ```
  Oczekiwane: `No changes detected` (po dołożeniu indeksów ręcznie — jeśli zgłasza zmiany, dorównaj `Meta.indexes` modeli do migracji).
- [ ] **Krok 2.5 — uruchom test z Task 1 (teraz PASS):**
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete_publikacje.py::test_soft_delete_publikacji_kaskaduje_na_autor_wspolny_txid -x
  ```
  Oczekiwane: PASS.
- [ ] **Krok 2.6 — commit:**
  ```bash
  git add src/bpp/models/wydawnictwo_ciagle.py src/bpp/models/wydawnictwo_zwarte.py src/bpp/models/patent.py src/bpp/models/praca_doktorska.py src/bpp/models/praca_habilitacyjna.py src/bpp/migrations/0490_publikacje_soft_delete_fields.py
  git commit -m "feat(soft-delete): 5 modeli publikacji -> SoftDeleteModel + migracje pol/indeksow

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## ~~Task 3: `slug` — warunkowy `UniqueConstraint`~~ → ŚWIADOMIE NIEWYKONANY

> 🛑 **DECYZJA WŁAŚCICIELA, 2026-08-07: tego zadania NIE robimy.**
> `slug` zostaje `unique=True`, bezwarunkowo. To NIE jest dług ani
> przeoczenie — poniżej powód, żeby nikt nie „dokończył" tego w dobrej wierze.
>
> **Przesłanka zadania nie zachodzi.** `get_slug()`
> (`src/bpp/models/util.py:246-254`) skleja slug jako
> `tytuł-źródło-autorzy-<content_type_pk>-<pk>`. Slug **zawiera klucz
> główny**, więc dwa różne wiersze nie mogą mieć tego samego slugu, a
> skasowany rekord nie zablokuje nowego — nowy dostaje nowe `pk`, czyli inny
> slug. Kolizja, którą to zadanie miało rozwiązać, jest konstrukcyjnie
> niemożliwa. ID jest w slugu CELOWO, właśnie po to, żeby slug był unikalny.
>
> Plan pisano najwyraźniej przy założeniu slugu opartego wyłącznie na
> tytule. Przy obecnej formule zamiana `unique=True` na
> `UniqueConstraint(condition=Q(deleted_at__isnull=True))` **osłabiłaby**
> gwarancję (unikalność tylko wśród żywych) i wymagała przebudowy indeksu na
> pięciu dużych tabelach — w zamian za rozwiązanie nieistniejącego problemu.
>
> Wyszło przy pisaniu testów TDD do tego zadania: padły wszystkie dziesięć,
> w tym ten, który powinien przechodzić JESZCZE PRZED zmianą. Denorm
> dodatkowo nadpisuje ręcznie ustawiony slug, więc kolizji nie da się nawet
> wywołać sztucznie.
>
> Poniższa treść zostaje wyłącznie jako kontekst historyczny.

<details><summary>oryginalna treść tasku (nieaktualna)</summary>

**Files:**
- Modify: `src/bpp/models/wydawnictwo_ciagle.py:246` (denorm `slug`: `unique=True`→brak unique; `Meta.constraints`)
- Modify: `src/bpp/models/wydawnictwo_zwarte.py:325`
- Modify: `src/bpp/models/patent.py:180`
- Modify: `src/bpp/models/praca_doktorska.py:105` (w `Praca_Doktorska_Baza`)
- Create: `src/bpp/migrations/0491_publikacje_slug_warunkowy_unique.py`
- Test path: `src/bpp/tests/test_soft_delete_publikacje.py`

Zamiana `unique=True` na `models.UniqueConstraint(fields=["slug"], condition=Q(deleted_at__isnull=True), name="...")` per model. Skasowany rekord trzyma slug → nowy rekord z tym samym slug-iem nie koliduje (constraint pomija `deleted_at IS NOT NULL`).

> **Wrinkle denorm:** `slug` to `@denormalized(models.SlugField, ..., unique=True, ...)`. `unique=True` jest kwargiem przekazywanym do `SlugField`. Usuwamy `unique=True` z denormalized-deklaracji i dodajemy `UniqueConstraint` w `Meta`. Denorm regeneruje wartość pola po zapisie — sam constraint go nie dotyka, działa na poziomie DB. `Praca_Doktorska_Baza.slug` jest abstrakcyjny → constraint w `Meta` abstraktu **nie** propaguje automatycznie do konkretnych klas; dlatego `UniqueConstraint` dla `Praca_Doktorska`/`Praca_Habilitacyjna` dodaj w `Meta` KAŻDEJ konkretnej klasy (każda ma własną kolumnę `slug`).

- [ ] **Krok 3.1 — padający test: reuse slug po soft-delete.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_reuse_slug_po_soft_delete():
      wc1 = baker.make(Wydawnictwo_Ciagle)
      wc1.refresh_from_db()
      slug = wc1.slug
      assert slug

      wc1.delete()  # soft

      wc2 = baker.make(Wydawnictwo_Ciagle)
      wc2.slug = slug
      wc2.save(update_fields=["slug"])  # nie może rzucić IntegrityError
      wc2.refresh_from_db()
      assert wc2.slug == slug
  ```
- [ ] **Krok 3.2 — uruchom, oczekiwany FAIL** (`IntegrityError: duplicate key value violates unique constraint` na `slug`, bo `unique=True` jeszcze żyje):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete_publikacje.py::test_reuse_slug_po_soft_delete -x
  ```
- [ ] **Krok 3.3 — implementacja: usuń `unique=True`, dodaj constraint.** W każdym z 4 miejsc denorm-deklaracji `slug` usuń linię `unique=True,` (zostaw `db_index=True` — indeks nadal pożądany). W `Meta` każdego z 5 modeli (`Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`, `Patent`, `Praca_Doktorska`, `Praca_Habilitacyjna`) dodaj:
  ```python
  from django.db.models import Q  # jeśli brak importu w pliku

  class Meta:
      ...
      constraints = [
          models.UniqueConstraint(
              fields=["slug"],
              condition=Q(deleted_at__isnull=True),
              name="wc_slug_uniq_zywe",  # unikalna nazwa per model
          ),
      ]
  ```
  Nazwy: `wc_slug_uniq_zywe`, `wz_slug_uniq_zywe`, `patent_slug_uniq_zywe`, `pdok_slug_uniq_zywe`, `phab_slug_uniq_zywe`.
- [ ] **Krok 3.4 — migracja:**
  ```bash
  uv run python src/manage.py makemigrations bpp --name publikacje_slug_warunkowy_unique
  ```
  Oczekiwane: `RemoveField`/`AlterField` (zdjęcie `unique`) + `AddConstraint` dla 5 modeli. Zweryfikuj numer `0491_`.
- [ ] **Krok 3.5 — uruchom test (PASS) + check migracji:**
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete_publikacje.py::test_reuse_slug_po_soft_delete -x
  uv run python src/manage.py makemigrations --check --dry-run bpp
  ```
  Oczekiwane: PASS + `No changes detected`.
- [ ] **Krok 3.6 — commit:**
  ```bash
  git add src/bpp/models/wydawnictwo_ciagle.py src/bpp/models/wydawnictwo_zwarte.py src/bpp/models/patent.py src/bpp/models/praca_doktorska.py src/bpp/models/praca_habilitacyjna.py src/bpp/migrations/0491_publikacje_slug_warunkowy_unique.py
  git commit -m "feat(soft-delete): slug -> warunkowy UniqueConstraint (reuse po soft-delete)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

</details>

---

## Task 2b: Widoki + gałąź kasująca + bramka `WHEN` dla 5 tabel publikacji (LUKA)

> 🔄 **Dodane 2026-08-06.** Poprzednia wersja planu zakładała, że fazа 01
> „dodała filtr `deleted_at` w widokach `bpp_rekord`/`bpp_*_autorzy`" i że
> ta faza nie musi ruszać DDL-a. **To nieprawda:** faza 01 dotyka wyłącznie
> ścieżki autorstwa (3 tabele `*_autor`). Dla 5 tabel publikacji ten sam
> trójskładnikowy wzorzec trzeba powtórzyć TUTAJ — inaczej soft-delete
> publikacji nie usunie jej z `bpp_rekord_mat`.

Powtórz wzorzec z fazy 01, Task 3 (tam jest pełny opis mechanizmu i pułapek),
dla `REKORD_SITES` z `0432_cache_trigger_plpgsql.py`:

1. filtr `deleted_at IS NULL` w 5 widokach `bpp_<typ>_view` **oraz w 2 widokach
   `bpp_praca_doktorska_autorzy` / `bpp_praca_habilitacyjna_autorzy`** — te
   ostatnie selektują z tabeli PUBLIKACJI (autor leży na jej wierszu), więc
   filtr jest tam „po własnej kolumnie" i klucz `object_id_raw` = id
   publikacji jest POPRAWNY. Bez nich `bpp_autorzy` przecieka autorów
   skasowanego doktoratu (faza 01 ich nie dotyka — przypis 3 tamtego planu),
2. gałąź kasująca w 5 funkcjach `bpp_refresh_rekord_<model>()`,
3. regeneracja bramki `WHEN` na 5 triggerach `<tabela>_cache_upd`.

⚠️ **Klucz filtra zależy od rodzaju widoku.** W `bpp_<typ>_view` i w
`bpp_praca_{doktorska,habilitacyjna}_autorzy` `object_id_raw` to id
publikacji — filtruj po nim. W widokach `bpp_*_autorzy` trzech typów
z through-modelem (faza 01) `object_id_raw` to też id publikacji, ale
filtrowaliśmy tam po pk wiersza through (`(id)[2]`). Nie kopiuj klucza
między fazami bez sprawdzenia, co dana kolumna znaczy.

**Files:**
- Create: `src/bpp/migrations/0493_soft_delete_rekord_views.py`
- Test: `src/bpp/tests/test_soft_delete/test_views_sql_publikacje.py`
- Test (modify): `src/bpp/tests/test_cache/test_soft_delete_preconditions.py` —
  **zdejmij `xfail`** z oryginalnych kanarków i odwróć ich asercje (operują na
  `bpp_wydawnictwo_ciagle`, więc dopiero ta faza je zazieleni).

⚠️ **Różnica wobec fazy 01 — doktorat i habilitacja dotykają OBU tabel `_mat`.**
`_create_rekord_function` z `0432` generuje dla nich (`autor_na_wierszu=True`)
dodatkowy blok na `bpp_autorzy_mat`, bo autor leży na wierszu publikacji.
Gałąź kasująca musi wyczyścić **obie**:

```sql
IF NEW.deleted_at IS NOT NULL THEN
    DELETE FROM bpp_rekord_mat  WHERE id        = ARRAY[ct, NEW.id]::integer[];
    DELETE FROM bpp_autorzy_mat WHERE rekord_id = ARRAY[ct, NEW.id]::integer[];
    RETURN NULL;
END IF;
```

(dla `wydawnictwo_ciagle`/`wydawnictwo_zwarte`/`patent` — tylko `bpp_rekord_mat`;
ich autorstwa czyści kaskada na `*_Autor` z Task 1 + gałąź z fazy 01).

⚠️ **Zwróć uwagę na klucz:** w `bpp_rekord_mat` kolumna nazywa się `id`,
w `bpp_autorzy_mat` — `rekord_id` (patrz `_create_rekord_function`
i `_create_delete_rekord_function` w `0432`).

- [ ] Testy kontraktu DDL (wzorzec z fazy 01, Task 3) dla 5 widoków, 5 funkcji,
      5 triggerów — oczekiwany FAIL przed migracją.
- [ ] Migracja `RunPython` w kolejności widoki → funkcje → bramka.
- [ ] Odwrócone kanarki `test_soft_delete_preconditions.py` — PASS.
- [ ] `makemigrations --check --dry-run` — brak driftu.

---

## Task 2c: Bramka denorm dla 5 modeli publikacji (DRUGI system triggerów)

> 🔴 **Dodane 2026-08-06** po recenzji fazy 01 Task 2. Analogia do Taska 3b
> fazy 01 — tam dla `*_Autor`, tu dla samych publikacji.

`django-denorm` ma własną bramkę `WHEN` budowaną z list `only=` w
`@depend_on_related` (`denorm/db/triggers.py:102-118`, `denorm/db/base.py:136`).
Jest to system NIEZALEŻNY od naszych triggerów `<tabela>_cache_upd` z `0432`/`0433`.

Dla publikacji dochodzi drugi wariant zależności — `@depend_on_related("self",
"wydawnictwo_nadrzedne")` (rozdziały → książka-matka, `wydawnictwo_zwarte.py`).
Soft-delete książki-matki musi unieważnić denorm-cache rozdziałów.

**Steps:**

- [ ] Wypisz WSZYSTKIE `@depend_on_related` celujące w 5 modeli publikacji
      (także `"self"`) i sprawdź, które mają `only=`, a które nie:
      ```bash
      grep -rn --include='*.py' -A5 "depend_on_related" src/ | grep -B2 -A5 "self\|Wydawnictwo_\|Patent\|Praca_"
      ```
      ⚠️ Zależność **bez** `only=` + `denorm_always_only` = ZAWĘŻENIE do samego
      `deleted_at` (patrz ostrzeżenie w fazie 01 Task 3b). Jeśli choć jedna taka
      jest — dopisz `"deleted_at"` do list `only=` ręcznie zamiast używać
      `denorm_always_only`.
- [ ] Test end-to-end: soft-delete książki-matki → denorm-cache rozdziału
      (`opis_bibliograficzny_cache` zawierający tytuł nadrzędny) przestaje być
      aktualny? Rozstrzygnij, czy to w ogóle pożądane — guard PROTECT z fazy 04
      i tak zablokuje soft-delete książki z rozdziałami, więc być może ten
      przypadek jest nieosiągalny. **Jeśli nieosiągalny — zapisz to i pomiń**,
      nie dokładaj martwego kodu.
- [ ] Przeinstaluj triggery denorm i zweryfikuj DDL (`pg_get_triggerdef`).

---

## ~~Task 3b: `unique_together` na `*_Autor`~~ → PRZENIESIONE DO FAZY 01 (Task 3c)

> 🔀 **Przeniesione 2026-08-06.** Umieszczenie tego w fazie 02 było błędem
> kolejności: `*_Autor` staje się soft-delete już w fazie 01 (Task 2), więc
> `unique_together` blokuje re-insert od tamtej fazy. Regresja wyszła realnie
> (`import_sqlite/handlers/patent.py:192` → `UniqueViolation`) i jest naprawiana
> w fazie 01, Task 3c. **W tej fazie NIE rób nic z `*_Autor` unique** —
> poniższa treść zostaje wyłącznie jako kontekst historyczny.

<details><summary>oryginalna treść tasku (nieaktualna)</summary>


> Dodane 2026-08-06 (spec §2.2b). Ten sam problem co ze slugiem, przeoczony
> w pierwszej wersji planu.

Soft-deletowany wiersz `*_Autor` **nadal zajmuje slot w unique**, będąc
niewidocznym dla operatora. Od Task 1 tej fazy kaskada soft-deletuje wiersze
`*_Autor` masowo, więc kolizja przestaje być teoretyczna: `deduplikator_autorow`
przenosi autorstwa z duplikatu na autora głównego
(`src/deduplikator_autorow/utils/merge.py:191,284,354`) i trafia w
soft-deletowany wiersz o tej samej trójce → `IntegrityError` o rekord,
którego nie widać.

**Files:**
- Modify: `src/bpp/models/wydawnictwo_ciagle.py:73-77` (`Wydawnictwo_Ciagle_Autor.Meta`)
- Modify: `src/bpp/models/wydawnictwo_zwarte.py` (`Wydawnictwo_Zwarte_Autor.Meta`)
- Modify: `src/bpp/models/patent.py` (`Patent_Autor.Meta`)
- Create: `src/bpp/migrations/0492_autor_warunkowy_unique.py`
- Test: `src/bpp/tests/test_soft_delete/test_autor_unique.py`

- [ ] **Krok 3b.1 — padający test: re-add autorstwa po soft-delete.**
  ```python
  @pytest.mark.django_db
  def test_readd_autorstwa_po_soft_delete(wydawnictwo_ciagle_z_autorem, autor_jan_kowalski):
      """Po soft-delete autorstwa da się dodać to samo powiązanie ponownie."""
      wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
      rekord, autor, typ, kolejnosc = (
          wca.rekord, wca.autor, wca.typ_odpowiedzialnosci, wca.kolejnosc,
      )
      wca.delete()

      # bez warunkowego constraintu: IntegrityError na (rekord, autor, typ)
      Wydawnictwo_Ciagle_Autor.objects.create(
          rekord=rekord, autor=autor, jednostka=wca.jednostka,
          typ_odpowiedzialnosci=typ, kolejnosc=kolejnosc,
      )
      assert Wydawnictwo_Ciagle_Autor.objects.filter(rekord=rekord).count() == 1
      assert Wydawnictwo_Ciagle_Autor.global_objects.filter(rekord=rekord).count() == 2
  ```

- [ ] **Krok 3b.2 — zamiana w `Meta` 3 modeli.** Usuń `unique_together`, dodaj:
  ```python
  constraints = [
      models.UniqueConstraint(
          fields=["rekord", "autor", "typ_odpowiedzialnosci"],
          condition=Q(deleted_at__isnull=True),
          name="wc_autor_uniq_rekord_autor_typ",
      ),
      models.UniqueConstraint(
          fields=["rekord", "autor", "kolejnosc"],
          condition=Q(deleted_at__isnull=True),
          name="wc_autor_uniq_rekord_autor_kolejnosc",
      ),
  ]
  ```
  Nazwy per model (`wc_`/`wz_`/`pat_`) — muszą być unikalne w całej bazie.

- [ ] **Krok 3b.3 — ⚠️ zweryfikuj admin.** Komentarz przy drugiej krotce
  („Tu musi być autor, inaczej admin nie pozwoli wyedytować") sugeruje, że ten
  constraint istnieje **ze względu na walidację formularzy**.
  `Model.validate_unique()` honoruje `unique_together`, ale **`UniqueConstraint`
  z `condition` pomija** (Django waliduje tylko constrainty bezwarunkowe).
  Ryzyko: zamiast czytelnego błędu formularza operator dostanie `IntegrityError`
  (HTTP 500). Test:
  ```bash
  uv run pytest src/bpp/tests/test_admin/ -k "autor and (inline or duplikat)" -v
  ```
  Jeśli admin regresuje — dodaj jawną walidację w formularzu inline
  (`clean()` sprawdzający kolizję przez `objects`), NIE wracaj do
  `unique_together` (nie da się go pogodzić z soft-delete).

- [ ] **Krok 3b.4 — migracja + brak driftu:**
  ```bash
  DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations bpp
  DJANGO_BPP_SKIP_DOTENV=1 uv run python src/manage.py makemigrations --check --dry-run
  uv run pytest src/bpp/tests/test_soft_delete/test_autor_unique.py -q
  ```

---

</details>

## Task 4: Przeplecenie menedżerów `Wydawnictwo_*_Manager` z filtrem soft-delete (wspólny QuerySet/MRO)

**Files:**
- Modify: `src/bpp/models/wydawnictwo_ciagle.py:87` (`Wydawnictwo_Ciagle_Manager`)
- Modify: `src/bpp/models/wydawnictwo_zwarte.py:167` (`Wydawnictwo_Zwarte_Manager` + metoda `wydawnictwa_nadrzedne_dla_innych`)
- Modify: `src/bpp/models/wydawnictwo_ciagle.py:185`, `wydawnictwo_zwarte.py:197` (przypisanie `objects`/`global_objects`/`deleted_objects`)
- Test path: `src/bpp/tests/test_soft_delete_publikacje.py`

Po wpięciu mixinu `Wydawnictwo_Ciagle`/`Wydawnictwo_Zwarte` dostają z `SoftDeleteModel` menedżery `objects`/`global_objects`/`deleted_objects` — ALE one nadpisują/kolidują z istniejącym `objects = Wydawnictwo_*_Manager()` (mixin opłat). Trzeba **przepleść**: menedżer publikacji ma równocześnie (a) filtrować `deleted_at__isnull=True`, (b) zachować `rekordy_z_oplata()`/`wydawnictwa_nadrzedne_dla_innych()`. Robimy to przez wspólny `BppSoftDeleteQuerySet` + MRO (mixin opłat operuje na queryset, więc działa nad każdym QS), **bez** nadpisywania metod fees.

> **Klucz:** `ManagerModeliZOplataZaPublikacjeMixin` to mixin metod menedżera (`self.exclude(...)`), niezależny od źródła QS. `BppSoftDeleteManager` z fazy 01 już zwraca `BppSoftDeleteQuerySet(...).filter(deleted_at__isnull=True)`. Składamy: `class Wydawnictwo_Ciagle_Manager(ManagerModeliZOplataZaPublikacjeMixin, BppSoftDeleteManager)`. `rekordy_z_oplata()` woła `self.exclude(...)` → działa na już-przefiltrowanym (żywym) QS. Zero nadpisywania fees.

- [ ] **Krok 4.1 — padający test: `objects` ukrywa skasowane, `rekordy_z_oplata` też, `global_objects` widzi wszystko.** Dopisz:
  ```python
  @pytest.mark.django_db
  def test_menedzery_publikacji_filtruja_soft_delete():
      wc_zywy = baker.make(Wydawnictwo_Ciagle, opl_pub_cost_free=True)
      wc_kosz = baker.make(Wydawnictwo_Ciagle, opl_pub_cost_free=True)
      wc_kosz.delete()

      ids = set(Wydawnictwo_Ciagle.objects.values_list("pk", flat=True))
      assert wc_zywy.pk in ids
      assert wc_kosz.pk not in ids, "objects nie ukrywa skasowanych"

      # metoda fees nadal działa i też pomija kosz:
      oplata_ids = set(
          Wydawnictwo_Ciagle.objects.rekordy_z_oplata().values_list(
              "pk", flat=True
          )
      )
      assert wc_zywy.pk in oplata_ids
      assert wc_kosz.pk not in oplata_ids

      all_ids = set(
          Wydawnictwo_Ciagle.global_objects.values_list("pk", flat=True)
      )
      assert wc_kosz.pk in all_ids, "global_objects nie widzi skasowanych"
  ```
- [ ] **Krok 4.2 — uruchom, oczekiwany FAIL.** Przed implementacją `objects` to wciąż stary `Wydawnictwo_Ciagle_Manager(... models.Manager)` (NIE filtruje `deleted_at`) → `wc_kosz.pk` jest w `ids`:
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete_publikacje.py::test_menedzery_publikacji_filtruja_soft_delete -x
  ```
  Oczekiwane: `AssertionError: objects nie ukrywa skasowanych` (albo `AttributeError: global_objects` jeśli mixin opłat przesłonił menedżery SoftDeleteModel).
- [ ] **Krok 4.3 — implementacja: przeplecione menedżery.** Import w obu plikach:
  ```python
  from bpp.models.soft_delete import BppGlobalManager, BppSoftDeleteManager
  ```
  W `wydawnictwo_ciagle.py` zamień definicję menedżera:
  ```python
  class Wydawnictwo_Ciagle_Manager(
      ManagerModeliZOplataZaPublikacjeMixin, BppSoftDeleteManager
  ):
      pass
  ```
  i w ciele `Wydawnictwo_Ciagle` (przy `objects = ...`):
  ```python
  objects = Wydawnictwo_Ciagle_Manager()
  global_objects = BppGlobalManager()
  deleted_objects = DeletedManager()  # import: from django_softdelete.managers import DeletedManager
  ```
  W `wydawnictwo_zwarte.py`:
  ```python
  class Wydawnictwo_Zwarte_Manager(
      ManagerModeliZOplataZaPublikacjeMixin, BppSoftDeleteManager
  ):
      def wydawnictwa_nadrzedne_dla_innych(self):
          return (
              self.exclude(wydawnictwo_nadrzedne_id=None)
              .values_list("wydawnictwo_nadrzedne_id", flat=True)
              .distinct()
          )
  ```
  i w ciele `Wydawnictwo_Zwarte`:
  ```python
  objects = Wydawnictwo_Zwarte_Manager()
  global_objects = BppGlobalManager()
  deleted_objects = DeletedManager()
  ```
  > `Patent`/`Praca_Doktorska`/`Praca_Habilitacyjna` NIE mają mixinu opłat — dostają `objects`/`global_objects`/`deleted_objects` wprost z `SoftDeleteModel` (przez `BppPublikacjaSoftDeleteMixin`). NIC tu nie zmieniamy dla nich. Ale upewnij się, że ich `objects` to `BppSoftDeleteManager` — jeśli mixin dziedziczy gołe `SoftDeleteModel`, menedżer to package-owy `SoftDeleteManager` (też filtruje `deleted_at`, ale bez gate na `.update()`). **Decyzja:** w `BppPublikacjaSoftDeleteMixin` ustaw jawnie `objects = BppSoftDeleteManager()`, `global_objects = BppGlobalManager()`, `deleted_objects = DeletedManager()` w ciele mixinu — wtedy 3 proste modele dostają gate'owany QuerySet z fazy 01 za darmo, a `Wydawnictwo_*` nadpisują `objects` własnym (przeplecionym) menedżerem.
- [ ] **Krok 4.4 — dopisz menedżery do mixinu (Task 1).** W `BppPublikacjaSoftDeleteMixin` (ciało, przed `Meta`):
  ```python
  from django_softdelete.managers import DeletedManager

  objects = BppSoftDeleteManager()
  global_objects = BppGlobalManager()
  deleted_objects = DeletedManager()
  ```
  (importy `BppSoftDeleteManager`/`BppGlobalManager` są już w `soft_delete.py`).
- [ ] **Krok 4.5 — uruchom test (PASS) + sprawdź, że nie powstała migracja menedżera.** Menedżery nie tworzą migracji schematu (chyba że `use_in_migrations`):
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete_publikacje.py::test_menedzery_publikacji_filtruja_soft_delete -x
  uv run python src/manage.py makemigrations --check --dry-run bpp
  ```
  Oczekiwane: PASS + `No changes detected` (jeśli Django chce migrację `default_manager` — wygeneruj ją: `--name publikacje_menedzery` i dołącz do commitu).
- [ ] **Krok 4.6 — commit:**
  ```bash
  git add -A
  git commit -m "feat(soft-delete): przeplecenie menedzerow Wydawnictwo_* z filtrem soft-delete

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 5: Testy integracyjne — znika z Rekord/Autorzy, restore, post_soft_delete, *_Streszczenie nietknięte, gate bulk-update

**Files:**
- Modify: `src/bpp/tests/test_soft_delete_publikacje.py`
- Test path: ten sam

> Te testy zależą od fazy 01 (trigger/widoki muszą usuwać z `bpp_rekord_mat`/`bpp_autorzy_mat` na podstawie `deleted_at`). Jeśli któryś z testów Rekord/Autorzy padnie z powodu cache, to regresja fazy 01 — zgłoś, NIE łataj tu.

- [ ] **Krok 5.1 — test: publikacja znika z `Rekord` i `Autorzy`, restore wraca.** Dopisz:
  ```python
  from bpp.models import Autorzy, Rekord


  @pytest.mark.django_db
  def test_soft_delete_znika_z_rekord_i_autorzy_restore_wraca(denorms):
      wc = baker.make(Wydawnictwo_Ciagle)
      baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc)
      wc.refresh_from_db()
      from django.contrib.contenttypes.models import ContentType

      # UWAGA: content_type NIE istnieje na modelach publikacji -- to
      # property na RekordBase (rekord.py:288). Bierzemy z ContentType.
      ct_pk = ContentType.objects.get_for_model(type(wc)).pk

      assert Rekord.objects.filter(
          id=(ct_pk, wc.pk)
      ).exists() or Rekord.objects.filter(tytul_oryginalny=wc.tytul_oryginalny).exists()

      wc.delete()
      assert not Rekord.objects.filter(
          tytul_oryginalny=wc.tytul_oryginalny
      ).exists(), "skasowany rekord wciąż w Rekord"
      assert not Autorzy.objects.filter(rekord_id=(ct_pk, wc.pk)).exists()

      wc.restore()
      assert Rekord.objects.filter(
          tytul_oryginalny=wc.tytul_oryginalny
      ).exists(), "po restore rekord nie wrócił do Rekord"
      assert Autorzy.objects.filter(rekord_id=(ct_pk, wc.pk)).exists()
  ```
  > `Rekord.id` to tuple `(content_type_id, object_id)`. ⚠️ `content_type_id` bierz z `ContentType.objects.get_for_model(...)` — modele publikacji tego atrybutu NIE mają. Jeśli `Rekord`/`Autorzy` API różni się — dostosuj filtr po realnym kontrakcie `src/bpp/models/cache/`. Fixture `denorms` (z `src/conftest.py`) odpala denorm flush — sprawdź czy istnieje; jeśli nie, użyj właściwej fixtury cache z repo (`flush_denorm`/`denorm_rebuild`).
- [ ] **Krok 5.2 — test: restore przywraca `*_Autor` po tym samym transaction_id.**
  ```python
  @pytest.mark.django_db
  def test_restore_przywraca_autorow():
      wc = baker.make(Wydawnictwo_Ciagle)
      a1 = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc)
      wc.delete()
      assert Wydawnictwo_Ciagle_Autor.objects.filter(pk=a1.pk).count() == 0

      wc.restore()
      row = Wydawnictwo_Ciagle_Autor.objects.get(pk=a1.pk)
      assert row.deleted_at is None
      assert row.transaction_id is None
  ```
- [ ] **Krok 5.3 — test: `post_soft_delete` emitowany.**
  ```python
  from django_softdelete.signals import post_soft_delete


  @pytest.mark.django_db
  def test_post_soft_delete_emitowany():
      odebrane = []

      def receiver(sender, instance, **kwargs):
          odebrane.append(instance)

      post_soft_delete.connect(receiver, sender=Wydawnictwo_Ciagle)
      try:
          wc = baker.make(Wydawnictwo_Ciagle)
          wc.delete()
      finally:
          post_soft_delete.disconnect(receiver, sender=Wydawnictwo_Ciagle)

      assert len(odebrane) == 1
      assert odebrane[0].pk == wc.pk
  ```
- [ ] **Krok 5.4 — test: `*_Streszczenie` NIE jest ruszane przez kaskadę.** Znajdź realny model streszczeń (`grep -rn "class Streszczenie\|Wydawnictwo_Ciagle_Streszczenie" src/bpp/models/` — prawdopodobnie `Wydawnictwo_Ciagle_Streszczenie` z FK `rekord`). Dopisz:
  ```python
  from bpp.models import Wydawnictwo_Ciagle_Streszczenie  # zweryfikuj nazwę/import


  @pytest.mark.django_db
  def test_kaskada_nie_rusza_streszczenia():
      wc = baker.make(Wydawnictwo_Ciagle)
      strz = baker.make(Wydawnictwo_Ciagle_Streszczenie, rekord=wc)
      wc.delete()  # NIE może rzucić SoftDeleteException
      # streszczenie fizycznie istnieje, nietknięte (nie jest SoftDeleteModel)
      assert Wydawnictwo_Ciagle_Streszczenie.objects.filter(pk=strz.pk).exists()
  ```
  > Jeśli `Wydawnictwo_Ciagle_Streszczenie` ma inną nazwę pola FK niż `rekord` — sprawdź modelem. Kluczowy asercja: `wc.delete()` NIE rzuca `SoftDeleteException` (dowód, że nie używamy refleksyjnej kaskady pakietu) i streszczenie zostaje.
- [ ] **Krok 5.5 — test: gate `BppSoftDeleteQuerySet.update(deleted_at=...)` rzuca (kontrakt reversion).**
  ```python
  @pytest.mark.django_db
  def test_bulk_update_deleted_at_zabroniony():
      baker.make(Wydawnictwo_Ciagle)
      with pytest.raises(RuntimeError):
          Wydawnictwo_Ciagle.objects.update(deleted_at="2026-01-01")
  ```
- [ ] **Krok 5.6 — uruchom cały plik:**
  ```bash
  uv run pytest src/bpp/tests/test_soft_delete_publikacje.py -x
  ```
  Oczekiwane: wszystkie testy PASS. Jeśli test Rekord/Autorzy (5.1) padnie na cache — to regresja fazy 01, zgłoś.
- [ ] **Krok 5.7 — lint:**
  ```bash
  ruff format src/bpp/tests/test_soft_delete_publikacje.py src/bpp/models/soft_delete.py src/bpp/models/wydawnictwo_ciagle.py src/bpp/models/wydawnictwo_zwarte.py src/bpp/models/patent.py src/bpp/models/praca_doktorska.py src/bpp/models/praca_habilitacyjna.py
  ruff check src/bpp/models/soft_delete.py src/bpp/tests/test_soft_delete_publikacje.py
  ```
  Oczekiwane: czysto (linia ≤88). Napraw każdy zgłoszony problem ręcznie (Edit), NIE `--fix`.
- [ ] **Krok 5.8 — commit:**
  ```bash
  git add src/bpp/tests/test_soft_delete_publikacje.py
  git commit -m "test(soft-delete): integracja publikacji - Rekord/Autorzy/restore/sygnaly/streszczenie/gate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Task 6: Weryfikacja końcowa fazy

**Files:** —

- [ ] **Krok 6.1 — pełny check migracji + testy soft-delete + sąsiednie regresje publikacji:**
  ```bash
  uv run python src/manage.py makemigrations --check --dry-run bpp
  uv run pytest src/bpp/tests/test_soft_delete_publikacje.py
  uv run pytest src/bpp/tests/ -k "wydawnictwo or patent or doktor or habilit" -q
  ```
  Oczekiwane: `No changes detected` + zielone testy. Jeśli istniejące testy publikacji padają, bo zakładały hard-delete — przejrzyj: prawdziwa regresja vs. test do aktualizacji (hard-delete → `.hard_delete()`). Aktualizuj tylko testy jawnie testujące kasowanie; NIE maskuj realnych regresji.
- [ ] **Krok 6.2 — `pre-commit` na zmienionych plikach (bez argumentów-akcji):**
  ```bash
  pre-commit run --files src/bpp/models/soft_delete.py src/bpp/models/wydawnictwo_ciagle.py src/bpp/models/wydawnictwo_zwarte.py src/bpp/models/patent.py src/bpp/models/praca_doktorska.py src/bpp/models/praca_habilitacyjna.py src/bpp/tests/test_soft_delete_publikacje.py
  ```
  Napraw issues ręcznie, NIE batch-fix.
- [ ] **Krok 6.3 — finalny commit (jeśli zostały zmiany po lintach):**
  ```bash
  git add -A
  git commit -m "chore(soft-delete): finalizacja fazy 02 publikacje (lint + regresje)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
  ```

---

## Definition of Done (faza 02)

- [ ] 5 modeli publikacji to `SoftDeleteModel` (przez `BppPublikacjaSoftDeleteMixin`); migracje `deleted_at`/`restored_at`/`transaction_id` + indeks per model (`0490_`).
- [ ] `delete(self, *args, user=None, reason="", **kwargs)` / `restore(self, *args, user=None, **kwargs)` — per-instancja `save()`, wąska kaskada na `autorzy_set` pod wspólnym `transaction_id`, BEZ refleksyjnej kaskady pakietu, BEZ bulk `update(deleted_at=)`.
- [ ] `*_Streszczenie` (i pozostałe nie-soft dzieci) nietknięte; `delete()` nie rzuca `SoftDeleteException`.
- [x] ~~`slug` → warunkowy `UniqueConstraint`~~ — **świadomie NIEwykonane.** `slug` zostaje `unique=True`; slug zawiera `pk`, więc kolizja jest konstrukcyjnie niemożliwa i warunkowanie tylko osłabiłoby gwarancję. Uzasadnienie w boxie przy Tasku 3.
- [ ] `Wydawnictwo_*_Manager` przeplecione: `objects` filtruje `deleted_at` ORAZ ma `rekordy_z_oplata()`/`wydawnictwa_nadrzedne_dla_innych()`; `global_objects`/`deleted_objects` dostępne na wszystkich 5 modelach.
- [ ] Testy: kaskada wspólny txid, znika z Rekord/Autorzy + restore, restore `*_Autor`, `post_soft_delete`, `*_Streszczenie` nietknięte, gate bulk-update — zielone.
- [ ] `makemigrations --check --dry-run bpp` → `No changes detected`. Istniejące migracje NIE modyfikowane.

---

## Podsumowanie (3 punkty)

1. **Co robi faza:** wpina `SoftDeleteModel` w 5 modeli publikacji przez nowy mixin `BppPublikacjaSoftDeleteMixin` (w `src/bpp/models/soft_delete.py`), który nadpisuje `delete()`/`restore()` na **jawną wąską kaskadę** soft-delete na `autorzy_set` (`*_Autor`) pod wspólnym `transaction_id` — z pominięciem refleksyjnej kaskady pakietu (żeby nie ruszać `*_Streszczenie` i innych nie-soft dzieci). Dokłada migracje pól+indeksów (`0421`), warunkowy `UniqueConstraint` na `slug` (`0422`, reuse po soft-delete) i przeplata menedżery `Wydawnictwo_*_Manager` (mixin opłat × `BppSoftDeleteManager`) tak, by `objects` filtrowały `deleted_at`, zachowując `rekordy_z_oplata()`/`wydawnictwa_nadrzedne_dla_innych()`.

2. **Krytyczne kontrakty utrzymane:** (a) zawsze per-instancja `save()`/`.delete()` — NIGDY bulk `update(deleted_at=)` (szew pod reversion, egzekwowany gate'em fazy 01); (b) sygnatury `delete(... user=None, reason="")` / `restore(... user=None)` (konsumuje je faza 06/07, tu tylko obecne); (c) wspólny `transaction_id` rodzic↔`*_Autor` (restore po nim); (d) emisja `post_soft_delete`/`post_restore`.

3. **Założenia między-fazowe (zweryfikowane):** zależy od **fazy 01** (moduł `soft_delete.py` z `BppSoftDeleteQuerySet`/`BppSoftDeleteManager`/`BppGlobalManager`, `*_Autor` już SoftDeleteModel, filtr `deleted_at` w widokach `bpp_rekord`/`bpp_*_autorzy`). Testy Rekord/Autorzy (Task 5) walidują integrację z fazą 01 — ich porażka = regresja 01, NIE łatać tu. Świadomie **NIE** ruszamy: FK flips `CASCADE→PROTECT` i guardy (autor, `wydawnictwo_nadrzedne`) → **faza 04**; audyt `global_objects` w imporcie/dedup/PBN → **faza 03**; PBN-wycofanie → **faza 05**; `SoftDeleteLog`+receivery (konsumują `user`/`reason`) → **faza 06**; admin (kosz/przywróć/usuń-trwale, hook usera) → **faza 07**. **Wrinkle do pilnowania:** `slug` jest polem `@denormalized` (`django-denorm-iplweb`) z `unique=True` jako kwargiem — zdejmujemy `unique`, dodajemy `UniqueConstraint` w `Meta` każdej konkretnej klasy (dla `Praca_Doktorska`/`Praca_Habilitacyjna` slug pochodzi ze wspólnego abstraktu `Praca_Doktorska_Baza`, ale constraint per konkretny model).
