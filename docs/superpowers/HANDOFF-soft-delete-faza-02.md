# Handoff: soft-delete, start fazy 02

> Dokument przekazania po zamknięciu **fazy 01**. Napisany 2026-08-07, po
> sesji, która wykonała całą fazę 01 (41 commitów, 9 migracji, PR #312, CI 23/23).
>
> **Czytaj to zamiast odtwarzania historii z gita.** Zawiera rzeczy, których
> nie widać w diffie, a które w fazie 01 kosztowały rundy poprawek.

---

## 1. Gdzie jesteśmy

| | |
|---|---|
| Gałąź | `feat/soft-delete`, worktree `~/Programowanie/bpp-soft-delete` |
| PR | #312, **CI 23/23 SUCCESS** |
| Commity fazy 01 | 41 (od `7119a766f`) |
| Migracje | `bpp/0488`…`0496`, `rozbieznosci_dyscyplin/0022` |
| Testy | 9409 passed (+157 Playwright), 0 failed |

**Faza 01 objęła TYLKO autorstwa** — 3 through-modele `Wydawnictwo_Ciagle_Autor`,
`Wydawnictwo_Zwarte_Autor`, `Patent_Autor`. Publikacje to faza 02.

Dokumenty:
- spec: `docs/superpowers/specs/2026-06-04-soft-delete-publikacje-i-autorzy-design.md`
- plan fazy 02: `docs/superpowers/plans/2026-06-04-soft-delete-02-publikacje.md`
- **runbook wdrożeniowy**: `docs/deweloper/runbook-soft-delete-faza-01.md`
- ledger fazy 01 (gitignored, tylko lokalnie):
  `.superpowers/sdd/2026-06-04-soft-delete-01-autor-trigger-widoki/progress.md`

---

## 2. Najważniejsza lekcja fazy 01

**Soft-delete nie jest „dodaniem kolumny".** To zmiana kontraktu `delete()`
z „wiersz przestaje istnieć" na „wiersz istnieje, ale się nie liczy". Każdy
mechanizm, który polegał na pierwszym znaczeniu, trzeba znaleźć i przekonfigurować.

W fazie 01 takich mechanizmów było **siedem**, odkrywanych pojedynczo, przez awarie:

| # | Mechanizm | Jak się objawiał |
|---|---|---|
| 1 | bramka `WHEN` triggerów cache (`0433`) | `save(update_fields=[…])` nie ruszał bramkowanej kolumny → trigger się nie odpalał |
| 2 | funkcje refresh (`0432`) | czysty upsert bez `DELETE` → odfiltrowanie z widoku było no-opem |
| 3 | bramka `django-denorm` | **drugi, niezależny** system triggerów z własną bramką z list `only=` |
| 4 | `unique_together` | blokował „skasuj i wstaw od nowa" (`UniqueViolation` w re-imporcie) |
| 5 | legacy raw-SQL `UNIQUE … DEFERRABLE` z `0132` (2018) | **niewidoczny dla ORM**; wybuchał dopiero przy `COMMIT` |
| 6 | `restore(strict=True)` | pakiet sprawdza `strict` dla *każdej* relacji → gołe `.restore()` rzucało wyjątek |
| 7 | widoki pochodne | `liczba_autorow`, ranking, raport rozbieżności czytały surową tabelę |

**Faza 02 dostaje dwa strażniki, żeby nie powtarzać tego odkrywania:**

- `src/bpp/tests/test_soft_delete/test_kanarek_katalogowy.py` — pyta `pg_depend`
  o zależność na poziomie **kolumny** i pada, gdy widok czyta tabelę soft-delete
  bez filtra po jej `deleted_at`;
- `src/bpp/tests/test_soft_delete/test_kanarek_orm.py` — AST, wykrywa zapytania
  ORM z JOIN-em po relacji bez predykatu `deleted_at`.

> ⚠️ **Rozszerz `TABELE_SOFT_DELETE` w kanarku katalogowym NA STARCIE fazy 02,
> a nie na końcu.** To jest cała jego wartość: dostajesz listę winowajców
> w pierwszej godzinie, zamiast odkrywać ich po jednym przez trzy tygodnie.
> Faza 01 zrobiła to odwrotnie i kosztowało to trzy dodatkowe zadania oraz
> werdykt „NIE SCALAĆ" na finalnej recenzji.

---

## 3. Zakres fazy 02 — co MUSI się w niej znaleźć

Plan (`…-02-publikacje.md`) ma jawną tabelę kolejności wykonania — taski
dopisywane po rewizjach wylądowały poza numeracją, więc **czytaj tabelę,
nie numery nagłówków**.

Poza pierwotnym zakresem doszły cztery rzeczy:

### 3.1 Nagrobki (decyzja właściciela, obowiązkowa)

`ostatnio_zmieniony` **MUSI** być bumpowany przy kasowaniu — to już jest
w kontrakcie PINNED (faza 01, `BppAutorstwoSoftDeleteMixin.save()`), więc
publikacje dostaną to „z urodzenia". Ale trzeba dołożyć **widoczność usunięć
na zewnątrz**:

- **OAI-PMH**: `<header status="deleted">` w `src/cerif_export` (serwuje
  `ListRecords`/`ListIdentifiers`/`resumptionToken`; **nie ma dziś żadnej
  obsługi `deleted`**), respektujące `from`/`until`;
- **CERIF**: odpowiednik nagrobka w formacie rekordu;
- **API `/api/v1/`**: sposób odkrycia usuniętych (endpoint „usunięte od…"
  albo parametr).

Dzięki bumpowi lista nagrobków to po prostu
`Model.deleted_objects.filter(ostatnio_zmieniony__gte=X)` — bez potrzeby
`SoftDeleteLog` z fazy 06.

**Traktuj to jako bramkę wydania**: faza 02 nie idzie na produkcję bez tego.

### 3.2 Agregaty przez `FILTER`, nie przez `WHERE`/`JOIN`

To jest pułapka, która **niszczy dane**, a nie tylko przecieka:

```sql
-- ŹLE: warunek na prawej stronie LEFT JOIN degeneruje go do INNER JOIN
--      → publikacja, której WSZYSCY autorzy są w koszu, ZNIKA z bpp_rekord_mat
LEFT JOIN bpp_..._autor ON … WHERE bpp_..._autor.deleted_at IS NULL

-- DOBRZE: liczy zero, ale zachowuje wiersz
count(bpp_..._autor.autor_id) FILTER (WHERE bpp_..._autor.deleted_at IS NULL)
```

Sprawdź **wszystkie** agregaty po tabelach objętych soft-delete
(`count`/`min`/`max`/`array_agg`/`string_agg`/`sum`/`bool_*`), nie tylko `count`.

### 3.3 Sprzątanie `bpp_kronika_*` — siedem widoków, jedną migracją

Cała rodzina jest martwa (zero konsumentów w kodzie, szablonach, `Meta.db_table`,
`flexible_reports`, surowym SQL-u). Nie da się skasować trzech osobno — zależą
od nich dwa widoki nadrzędne. Graf zależności i kolejność `DROP` są w planie 02.
Po zrobieniu: usuń wpisy z `WYJATKI` w kanarku katalogowym.

### 3.4 Rozszerzenie obu kanarków

`TABELE_SOFT_DELETE` += 5 tabel publikacji. Po tym kanarek złapie też
`bpp_kronika_praca_{doktorska,habilitacyjna}_view` — ich żywotności **nikt
jeszcze nie zweryfikował**.

---

## 4. Fakty o kodzie, które w fazie 01 były źródłem błędów

Wszystkie zweryfikowane empirycznie. Nie zakładaj, że któryś jest inny —
ale przy okazji fazy 02 warto potwierdzić, bo `dev` żyje.

- **`.filter()` resolwuje nazwy pól NATYCHMIAST** (`Query.build_filter`), nie
  przy iteracji. `FieldError` leci od razu na modelu bez kolumny.
- **`content_type_id` NIE istnieje** na modelach publikacji — to property na
  `RekordBase` (`rekord.py:288`). Używaj `ContentType.objects.get_for_model()`.
- **`transactional_db` NIE jest potrzebny** — triggery działają w transakcji
  testowej. Zwykły `django_db` wystarcza.
- **Fixtury `wydawnictwo_ciagle_z_dwoma_autorami` i `wydawnictwo_ciagle_z_autorem`
  to TEN SAM obiekt** (`conftest_publications.py:193-215`, pierwsza zwraca drugą).
- **`Rekord` czyta tabelę `bpp_rekord_mat`**, nie widok `bpp_rekord`
  (`rekord.py:382-386`); widok obsługuje marginalna klasa `RekordView`.
- **`full_refresh()` to `denorm.rebuildall`**, NIE re-projekcja `_mat`
  (`rekord.py:121-127`). Nie nadaje się do weryfikacji spójności soft-delete.
- **`_upsert_sql` z `0432` mapuje kolumny POZYCYJNIE.** Zmiana definicji widoku,
  która przestawi kolumny, wpisze dane do złych pól i nic nie krzyknie.
- **`Uczelnia.objects.get_default()` NIE ISTNIEJE** — usunięte, pilnowane
  `src/bpp/tests/test_multihosted_get_default_guard.py`.
- **`SentData` jest scope'owane po uczelni** — `get_for_rec(rec, uczelnia=None)`;
  przy ≥2 wierszach lookup bez uczelni rzuca `MultipleObjectsReturned`.
- **Klient PBN to pakiet zewnętrzny** (`pbn_client`), nie `src/pbn_api/client/mixins/`.
- **`DENORM_DISABLE_AUTOTIME_DURING_FLUSH = True`** (`settings/base.py:1222`) —
  zapisy denorma nie bumpują `ostatnio_zmieniony`. Skutek: zmiana składu autorów
  nie podnosi znacznika publikacji. **Zachowanie prekursorskie** (hard-delete
  działa tak samo), opisane w runbooku jako obserwacja.

---

## 5. Jak pracować (proces, który się sprawdził — i gdzie zawiódł)

### Co działało

- **SDD** (`superpowers:subagent-driven-development`): implementer → recenzja →
  runda poprawek → re-recenzja. Recenzje znalazły rzeczy, których nie znalazł
  ani self-review planów, ani implementer.
- **Mutation testy.** W fazie 01 **cztery** testy okazały się przechodzić
  niezależnie od implementacji (tautologie, oparcie o efekt uboczny hard-delete,
  fixtury będące tym samym obiektem, sprawdzanie substringu w DDL). Pytaj
  o każdy nowy test: *co muszę zepsuć, żeby spadł na czerwono* — i sprawdź to.
- **Inwentaryzacja przed naprawą.** Przy wycieku ORM dała 15 znalezionych /
  11 naprawionych / 4 świadomie zostawione, plus listę kategorii z **zerem**
  trafień — żeby nikt nie szukał drugi raz.

### Czego NIE powtarzać

- ⚠️ **Nie uruchamiaj równoległych agentów w jednym worktree.** Rozdzielenie
  plików nie wystarcza: `reset`, `stash`, `amend` widzą całą gałąź. W tej sesji
  doszło do trzech kolizji (plik roboczy w cudzym commicie, `git stash pop`
  zjadający cudzy stash, `git reset --soft` omal nie kasujący cudzego commitu).
  Równoległość → **osobne worktree**.
- ⚠️ **`PYTEST_TESTCONTAINERS_REUSE=1` daje fałszywe alarmy** — reużywany
  kontener dryfuje (w jednym przebiegu zniknęła `Instytucja_Finansujaca`).
  Przy dziwnych, niepowtarzalnych awariach: świeży kontener.
- ⚠️ **`make clean-testcontainers` na tym hoście ubija CUDZE kontenery.**
  Celuj po nazwie/ID.
- ⚠️ **Pusty wynik ≠ potwierdzenie.** Pathspec `'src/*/migrations/'` w cudzysłowie
  zwraca pustkę; `xfail` bez `strict=True` chowa `XPASS`; `git stash push` na
  czystym drzewie nic nie tworzy, ale `pop` i tak coś zdejmie. Zanim uznasz brak
  wyniku za dowód — sprawdź, czy narzędzie w ogóle potrafi coś pokazać.

---

## 6. Otwarte decyzje

| Sprawa | Stan |
|---|---|
| **Strategia wydania** | Rekomendacja: scalać fazami do `dev`, **wydać dopiero po 04**. Faza 01 sama nie daje wartości użytkownikowi (kosz bez UI — admin to faza 07), a kosztuje okno serwisowe i narzut GiST. Faza 03 jest obowiązkowa razem z 02 (bez niej re-import tworzy duplikaty). |
| Ręczne GET-y changelistu admina (`?autorzy_set__…=`) | `lookup_allowed` przepuszcza surowy lookup; decyzja produktowa |
| Pomiar `0492` na kopii produkcyjnej | **przed wdrożeniem**, patrz runbook §1 |
| Pomiar narzutu GiST | nikt nie zmierzył; testy tego nie wykryją |
| A2 — zmiana składu autorów nie podnosi znacznika publikacji | prekursorskie, w runbooku |

## 7. Długi pozostałych faz (spłacić przy starcie danej fazy)

- **03**: decyzja #14 („pomiń + zaraportuj" przy trafieniu w kosz) niewpięta
  w taski 2-5; test ma literalny placeholder; `deduplikator_autorow/utils/merge.py`
  zrefaktoryzowany (cytowane linie nieaktualne).
- **04**: nikt nie przeplata `AutorManager` (husk autora zostanie widoczny);
  `Autor.restore()` **musi** nadpisać `strict=False`.
- **05**: ✅ spłacony 2026-08-07.
- **06**: `MetrykaAutora` trzyma listy ID prac w JSON-ach — zostanie stale;
  Task 5 (shim `zakolejkuj_*`) jest **martwy** po ustaleniach fazy 05 — usunąć.
