# Handoff: soft-delete, start fazy 08

> Po zamknięciu **fazy 07** (kosz w adminie: filtr, przywracanie, trwałe
> usuwanie, powód), 2026-08-25. Czytaj to zamiast odtwarzania historii z gita.

---

## 1. Gdzie jesteśmy

| | |
|---|---|
| Stan fazy 07 | gałąź `feat/soft-delete-06` (faza 07 dopisana na tej samej gałęzi) |
| Plan fazy 07 | [`plans/2026-06-04-soft-delete-07-admin.md`](plans/2026-06-04-soft-delete-07-admin.md) — wykonany, z odstępstwami z §3 |
| Migracje fazy 07 | **ŻADNE.** Mixin admina nie dotyka schematu |
| Następny plan | [`plans/2026-06-04-soft-delete-08-testy-regresji.md`](plans/2026-06-04-soft-delete-08-testy-regresji.md) — 11 tasków, faza czysto testowa |

### Stos PR-ów

```
#312  feat/soft-delete       -> dev
#745  feat/soft-delete-04    -> feat/soft-delete
#755  feat/soft-delete-05    -> feat/soft-delete-04
#767  feat/soft-delete-05b   -> feat/soft-delete-05
      feat/soft-delete-06    -> feat/soft-delete-05b   (fazy 06 ORAZ 07)
```

⚠️ Żaden PR ze stosu nie jest scalony. Bez zmian względem handoffu fazy 07.

⚠️ **Baseline (`baseline-sql/`) nadal NIEŚWIEŻY** — stoi na `bpp/0487`, ostatnia
migracja to `0503` (faza 06). Faza 07 nic tu nie zmieniła. Odświeżenie robi się
**raz, przy scalaniu** całego `feat/soft-delete` do `dev`.

⚠️ **CI NIE URUCHAMIA SIĘ na PR-ach do gałęzi `feat/soft-delete*`** — bez zmian.
Jedyną weryfikacją jest przebieg lokalny.

### Wynik weryfikacji fazy 07

| Przebieg | Wynik |
|---|---|
| `pytest src/bpp/tests/test_soft_delete/test_admin.py` (suita fazy) | **21 passed** |
| `pytest src/bpp/tests/test_soft_delete/` (cała rodzina soft-delete) | **197 passed, 1 xfailed** |
| `pytest src/bpp/tests/ -k admin` (regresja adminów, z Playwrightem) | **845 passed** |
| `make tests-without-playwright` (`-n auto`) | **9669 passed, 1 failed, 4 skipped, 2 xfailed** (5:32) |
| `ruff check` / `ruff format --check` na plikach fazy | czysto (9 plików) |
| `pre-commit` na plikach fazy + oba hooki szablonowe | Passed |

Jedyna porażka to `test_soft_delete/test_kronika_usunieta.py::test_0499_odwracalna`
— `Failed: Timeout (>90.0s)`, NIE asercja. **To nie jest regresja fazy 07:**

- serialnie ten test przechodzi w **32,98 s** (zmierzone po fazie 07); faza 06
  mierzyła 31,88 s na `05b` i 32,33 s na `06` — identycznie co do szumu,
- faza 07 **nie dokłada żadnej migracji**, a to jest test odwracalności migracji
  `0499`; nie wykonuje ani jednej operacji admina,
- to jeden z DWÓCH testów wskazanych już w handoffie fazy 07 §1 jako mające
  ~2× zapasu do limitu 90 s i przekraczające go pod `-n auto` (10 workerów) na
  współdzielonym hoście. Drugi (`pbn_api/…/test_migracja_dyscypliny_uuid_e2e`)
  tym razem przeszedł — co potwierdza, że rzecz jest w obciążeniu, nie w kodzie.

Kandydat do podniesienia `@pytest.mark.timeout` dla tych dwóch plików —
**wciąż poza zakresem**, teraz już drugą fazę z rzędu.

---

---

## 2. Co faza 07 dostarcza (kontrakt dla fazy 08)

Jedna klasa, `src/bpp/admin/helpers/mixins.py`:

```python
from bpp.admin.helpers.mixins import BppSoftDeleteAdminMixin, PokazSkasowaneFilter
```

| Element | Uwaga |
|---|---|
| `BppSoftDeleteAdminMixin` | wpięty w 6 adminów; **OSTATNI** na liście baz, patrz §3.3 |
| `PokazSkasowaneFilter` | `?is_deleted=true` = tylko kosz, `=all` = wszystko, brak = tylko żywe |
| `_soft_delete_user_context(request)` | JEDEN punkt wstrzyknięcia usera; deleguje do `soft_delete_context` |
| `_soft_delete_jeden(request, obj, powod)` | soft-delete jednej instancji z obsługą guarda fazy 04 |
| akcja `usun_do_kosza` | strona pośrednia z polem „powód" → `SoftDeleteLog.powod` |
| akcja `przywroc_zaznaczone` | restore przez ten sam hook |
| akcja `usun_trwale_zaznaczone` | superuser-only, **tylko rekordy z kosza** |
| `templates/admin/bpp/soft_delete_powod.html` | faktyczna ścieżka: `src/django_bpp/templates/…` |
| fixture `staff_user` / `staff_client` | `src/conftest.py`; staff z grupą „wprowadzanie danych" |

Objęte adminy: `Wydawnictwo_CiagleAdmin`, `Wydawnictwo_ZwarteAdmin`,
`Patent_Admin`, `Praca_DoktorskaAdmin`, `Praca_HabilitacyjnaAdmin`, `AutorAdmin`.

**Poza zakresem (świadomie):** `Zgloszenie_Publikacji` — szósty model
soft-delete znaleziony w fazie 06 (§4 tamtego handoffu). Nie ma admina kosza,
bo plan fazy 07 obejmował 5 publikacji + `Autor`. Operacje na nim i tak trafiają
do `SoftDeleteLog` (receivery są podpięte bez `sender=`).

---

## 3. ⚠️ Cztery miejsca, w których plan rozjechał się z kodem

Wszystkie wykryte PRZED napisaniem kodu, przez weryfikację „PINNED kontraktów"
planu wobec źródeł. Trzy to błędy rzeczowe w planie, jeden — luka bezpieczeństwa.

### 3.1 API atrybucji z planu nie istnieje (a overview mówił to wprost)

Plan §„Kontrakty z fazą 06 (PINNED — używaj VERBATIM)" pinuje
`set_soft_delete_user` / `get_soft_delete_user` / `clear_soft_delete_user`
w `bpp/models/soft_delete.py`. **Żadna z tych funkcji nie istnieje.** Faza 06
dostarczyła context manager `soft_delete_context(user=, reason=)` w
`bpp/models/soft_delete_context.py`.

Co jest tu warte zapamiętania: **overview ostrzegał przed dokładnie tym błędem**
(`2026-06-04-soft-delete-00-overview.md:187` — „NIE wymyślać osobnego
`set/get/clear_soft_delete_user` — używać `soft_delete_context`"). Plan fazy 07
powstał wcześniej i nie został zsynchronizowany. Etykieta „PINNED — używaj
VERBATIM" była więc *silniejsza* niż jej pokrycie w kodzie — to ta sama lekcja,
co `Autor.pbn_uid` w fazie 06 §3.1 („zweryfikowane" ≠ zweryfikowane).

### 3.2 `hard_delete()` nie przyjmuje `user=` ani `reason=`

Plan (Task 4) wołał `obj.hard_delete(user=request.user, reason=powod)` →
`TypeError`. `BppPkPrzedHardDeleteMixin.hard_delete(*args, **kwargs)` przekazuje
argumenty prosto do pakietu, który o userze nie wie.

**Skutek projektowy, nie kosmetyczny:** to jest powód, dla którego
`_soft_delete_user_context` MUSI być context managerem, a nie „przekaż `user=`
do metody". Dla trwałego usuwania kontekst jest JEDYNYM kanałem atrybucji.

### 3.3 „Mixin PIERWSZY" otwierało lukę wielotenantową (blokujące)

Plan powtarza w Task 1 i Task 6: `BppSoftDeleteAdminMixin` ma być **PIERWSZY**
na liście baz, „żeby jego metody wygrywały".

`get_queryset` tego mixinu **nie może wołać `super()`** — musi podmienić manager
bazowy na `global_objects`, a `super()` zwraca już przefiltrowany `objects`.
Z pierwszej pozycji w MRO ucina więc CAŁY łańcuch. W `AutorAdmin` w tym łańcuchu
stoi `SiteFilteredAdminMixin.get_queryset`, zawężające widok nie-superusera do
jego uczelni (`kiedykolwiek_zwiazani`, FD#390). Wpięcie wg planu dałoby
personelowi uczelni A widok i kasowanie autorów uczelni B.

**Rozstrzygnięcie:** mixin wpinany jako **OSTATNI**, tuż przed terminalną bazą
(`admin.ModelAdmin` / `Wydawnictwo_ZwarteAdmin_Baza` /
`Praca_Doktorska_Habilitacyjna_Admin_Base`). Z tej pozycji jego `get_queryset`
jest PODSTAWĄ łańcucha — zwraca `global_objects`, a wszystkie mixiny wyżej
nakładają na to swoje filtry normalnie. Zweryfikowane: w tych 6 łańcuchach
jedynym innym `get_queryset(self, request)` jest ten z `SiteFilteredAdminMixin`
i woła `super()`; `get_actions` / `get_list_filter` w łańcuchu
(`AutorAdmin.get_actions`, `ExportActionsMixin.get_actions`) też wołają `super()`
i tylko DOKŁADAJĄ pozycje — więc z ostatniej pozycji działają tak samo.

Strażnikiem jest `test_admin.py::test_mixin_nie_znosi_zawezenia_do_uczelni_w_autoradmin`.
**Nie usuwaj go przy refaktorze MRO** — to jedyne miejsce, które zapala się,
gdy ktoś „posprząta" kolejność baz z powrotem do wersji z planu.

### 3.4 Plan odwracał semantykę parametru filtra na podstawie błędnego odczytu

Plan (Task 1, Step 5) twierdzi, że pakietowy `SoftDeleteFilter` ma mylącą
semantykę (`'true'` → „Deleted Softly" przez mapę `{'true': False}`) i każe
odwrócić ją tak, by `?is_deleted=false` znaczyło „pokaż kosz".

Pakiet czyta się jednak inaczej niż plan go przeczytał: `{'true': False}` trafia
do `filter(deleted_at__isnull=value)`, czyli `deleted_at IS NOT NULL` — a więc
`is_deleted=true` JUŻ znaczy „rekordy skasowane". Odwrócenie sprawiłoby, że
parametr w URL-u kłamie (bookmark `is_deleted=false` pokazywałby kosz).

**Rozstrzygnięcie:** zostaje semantyka pakietu. `PokazSkasowaneFilter` zmienia
wyłącznie zachowanie DOMYŚLNE (brak parametru = tylko żywe zamiast wszystkiego),
bo po poszerzeniu `get_queryset` do `global_objects` nie ma już nikogo innego,
kto by kosz schował.

---

## 4. Decyzje wykraczające poza plan (i ich uzasadnienia)

### 4.1 Trwałe usuwanie WYŁĄCZNIE z kosza

Plan nie ograniczał `usun_trwale_zaznaczone` do rekordów skasowanych. Ogranicza
je faza 07 — i nie jest to ostrożnościowy rytuał:

`Cache_Punktacja_*` nie ma FK do publikacji (klucz to tablica
`[content_type_id, pk]`), więc nie sprząta jej ani kolektor Django, ani triggery.
Kasuje ją dopiero receiver `post_soft_delete` (faza 06, `_skasuj_punktacje`).
Twarde skasowanie rekordu Z POMINIĘCIEM kosza zostawiłoby więc wiersze punktacji
wskazujące na nieistniejący rekord — **i wciąż liczące się do ewaluacji**.
Rekordy spoza kosza są pomijane z komunikatem.

To jest kandydat na test regresji w fazie 08 (Task 2/7 dotykają dokładnie tej
materii).

### 4.2 Akcje działają na querysecie changelisty, nigdy na `deleted_objects`

`przywroc_zaznaczone` można było zrobić „wygodniej": dociągnąć zaznaczone pk
z `Model.deleted_objects`, żeby akcja działała niezależnie od aktywnego filtra.
**Świadomie tego nie robimy** — dociąganie po pk omija każde zawężenie nałożone
przez łańcuch, w tym `SiteFilteredAdminMixin`. Personel jednej uczelni mógłby
przywrócić rekord drugiej, podając jego pk.

Koszt: przywracanie wymaga wcześniejszego ustawienia filtra „🗑️ Tylko
skasowane". Puste zaznaczenie tłumaczy komunikat, zamiast cicho zwrócić
„przywrócono: 0".

### 4.3 Strona pośrednia przenosi `select_across`, nie tylko pk-i

Django przy `select_across=1` IGNORUJE `_selected_action` i podaje akcji cały
przefiltrowany queryset. Gdyby strona z powodem re-postowała same zaznaczone
pk-i, „zaznacz wszystkie 40 000 pasujących" skurczyłoby się po cichu do 100
wierszy bieżącej strony — a operator byłby przekonany, że skasował całość.
Dlatego formularz niesie `select_across` i `index`.

Podgląd listy jest przycięty do `LIMIT_PODGLADU_KOSZA = 50`; licznik idzie
z `.count()`, więc liczba pozostaje prawdziwa przy skróconej liście.

### 4.4 Komunikat guarda bierzemy z wyjątku, nie piszemy własnego

`raise_if_has_protected_children` (faza 04) zna liczbę i rodzaj powiązań i już
je opisuje po polsku. Drugi tekst w adminie byłby kopią tej samej reguły —
rozjechałby się z oryginałem przy pierwszej zmianie listy relacji. Admin
pokazuje `e.args[0]`.

Łapanie jest **per instancja**: jeden zablokowany autor nie przewraca całego
zaznaczenia.

---

## 5. Bug znaleziony po drodze, NIE naprawiony (poza zakresem)

**Staff bez żadnej grupy dostaje 500 na każdej stronie admina.**

`src/django_bpp/menu.py:302` robi bezwarunkowe
`del menu.children[-1].children[-1]`, podczas gdy `flt(...)` kilka linii wyżej
dokłada submenu tylko członkom grupy. Użytkownik `is_staff=True` bez grup ma
`menu.children == []` → `IndexError: list assignment index out of range`.

Reprodukcja: dowolny staff bez grup, dowolna strona `/admin/…`.

Fixture `staff_user` obchodzi to, dopisując użytkownika do grupy
`GR_WPROWADZANIE_DANYCH` — co przy okazji modeluje realnego redaktora, więc nie
jest to obejście „na siłę". Ale **bug istnieje w produkcji** i wywróci się przy
pierwszym koncie staff założonym bez grupy. Naprawa jest jednolinijkowa
(warunek na niepustą listę), tylko nie należy do soft-delete.

---

## 6. Czego faza 07 NIE domyka (świadomie)

- **Brak admina dla samego `SoftDeleteLog`.** Log powstaje, ale nie ma widoku,
  w którym operator obejrzy „co, kto i dlaczego usunął". Plan fazy 07 tego nie
  obejmował (mimo że handoff fazy 06 §6 zapowiadał „UI dla logu — faza 07").
  **To jest realna luka w domknięciu fazy** — bez niej `powod` zapisywany przez
  `usun_do_kosza` jest widoczny wyłącznie przez ORM.
- **`Zgloszenie_Publikacji` bez kosza w adminie** — patrz §2.
- **Masowe operacje nadal synchroniczne.** Handoff fazy 06 §7 mierzył
  `restore()` z przeliczeniem punktacji na 46,7 ms/rekord; 100 rekordów ≈ 4,7 s
  w jednym żądaniu HTTP. `hard_delete()` na querysecie to N zapytań (faza 06,
  Task 8). Zadanie w tle nadal nie istnieje — przy zaznaczeniu „wszystkie
  pasujące" na dużej bazie akcja się wywali na timeoucie.
- **Rekord z `pbn_uid` — asymetria uprawnień.** `RestrictDeletionWhenPBNUIDSetMixin`
  nadal zwraca `has_delete_permission=False` dla rekordu z `pbn_uid`, więc
  przycisk „Usuń" na changeformie i `delete_selected` są dla niego niedostępne.
  Własna akcja `usun_do_kosza` **działa** (akcje w Django nie przechodzą przez
  `has_delete_permission`). Jest to zgodne z intencją planu („soft-delete rekordu
  z `pbn_uid` realizujemy mimo to" — faza 05 istnieje właśnie po to, żeby
  zakolejkować `WYCOFANIE`), ale dwie ścieżki do tej samej operacji mają różne
  reguły dostępu. Jeśli to ma być spójne, właściwym miejscem jest jawne
  `has_soft_delete_permission()` — plan je zapowiadał, ale nigdy nie zdefiniował.

---

## 7. Dług nadal otwarty (z faz 01–06)

Bez zmian względem handoffu fazy 07, z dwiema pozycjami zamkniętymi:

| Sprawa | Stan |
|---|---|
| **Brak UI dla `ProtectedError`** | **ZAMKNIĘTE w fazie 07** (§4.4) |
| **`Autor` nie ma kosza w adminie** | **ZAMKNIĘTE w fazie 07** |
| **Brak admina dla `SoftDeleteLog`** | **NOWE/otwarte** — patrz §6 |
| **Staff bez grupy = 500 w adminie** | **NOWE/otwarte** — patrz §5 |
| **Asymetria gate'u `.update(deleted_at=...)`** | `BppSoftDeleteQuerySet` blokuje, `BppDeletedQuerySet` **nie** |
| **Kaskada `Jednostka` → `Autor`** | `aktualna_jednostka`/`aktualna_funkcja` nadal `CASCADE` |
| **`Autor.slug` `unique=True` bezwarunkowo** | husk trzyma slug zarezerwowany |
| **Wycieki ORM (kanarek `xfail(strict=True)`)** | bez zmian |
| **PR upstream `django-easy-audit`** | [#348](https://github.com/soynatan/django-easy-audit/pull/348) |
| **`SoftDeleteLog` nie niesie `pbn_uid`** | dług z 05a §6 nadal otwarty |
| **`pbn_status=""` dwuznaczne** | bez zmian (faza 06 §6) |
| **`uczelnia_rekordu()` → `None` przy dwuznaczności** | bez zmian |
| **Reguła przynależności zduplikowana z `cerif_export`** | bez zmian |
| Słowniki (`Zrodlo`, `Konferencja`, `Projekt`, `Jednostka`) bez soft-delete | bez zmian |
| Pomiar `0492` i narzutu GiST | wciąż nikt nie zmierzył |
| **Strategia wydania** | bramka nadal otwarta |

---

## 8. Wskazówki wprost dla fazy 08 (suita regresji E2E)

- **Fixture `staff_user`/`staff_client` już są** (`src/conftest.py`). Staff ma
  uprawnienia modelowe do `wydawnictwo_ciagle` i `autor` oraz grupę
  „wprowadzanie danych". Jeśli faza 08 potrzebuje staffu dla innego modelu —
  poszerz `content_type__model__in`, nie twórz drugiego fixture'u.
- **`_log(model, pk, akcja)`** w `test_soft_delete/test_admin.py` filtruje
  `SoftDeleteLog` po `content_type` ORAZ `object_id`. Plan fazy 07 filtrował po
  samym `object_id` — to nie jest unikalne globalnie, a kaskada fazy 02 loguje
  przy okazji wiersze `*_Autor`, które łatwo trafiają na tę samą wartość `pk`.
  Skopiuj ten helper, nie wzorzec z planu.
- **Task 2 i Task 7 planu fazy 08** (`Cache_Punktacja_*`, ewaluacja) dotykają
  dokładnie tej materii, co decyzja §4.1. Test „hard-delete rekordu żywego
  zostawia osierocone wiersze punktacji" byłby dowodem, że ograniczenie jest
  potrzebne — dziś opiera się na lekturze kodu, nie na eksperymencie.
- **Task 4 planu fazy 08** (regresja `SoftDeleteLog`) częściowo pokrywa się
  z `test_soft_delete/test_admin.py` — sprawdź, zanim napiszesz duplikat.

---

## 9. Proces — co się sprawdziło w fazie 07

- **Weryfikacja „PINNED" kontraktów planu wobec źródeł zwróciła się natychmiast.**
  Cztery rozjazdy z §3, wszystkie wykryte przed napisaniem pierwszej linii kodu.
  Najgroźniejszy (§3.3, luka wielotenantowa) nie zapaliłby się w żadnym teście
  z planu — plan testował wyłącznie superuserem, a dla superusera
  `SiteFilteredAdminMixin` i tak jest no-opem. **Test na regresję MRO trzeba było
  dopisać, bo w planie go nie było.**
- **Overview był aktualniejszy niż plan fazy.** §3.1 to błąd, przed którym
  overview ostrzegał explicite. Przy rozjeździe plan-vs-overview zaufaj temu,
  co potwierdzasz w kodzie, a overview czytaj ZANIM zaczniesz task.
- **Pierwszy „padający test" bywa padający z niewłaściwego powodu.** Test akcji
  „Przywróć" padał nie dlatego, że akcji nie było, ale dlatego, że akcja
  dostawała puste zaznaczenie (domyślny filtr chowa kosz). Rozpoznanie tego
  ujawniło realną własność bezpieczeństwa (§4.2), której plan nie widział.
- **Pomiar „co faktycznie robi pakiet" bije cytat z planu.** §3.4 — plan
  streszczał zachowanie `SoftDeleteFilter` i streścił je odwrotnie. Trzy linie
  kodu pakietu rozstrzygnęły sprawę w minutę.
