# Spec: Soft-delete publikacji + autorów (jedno opracowanie wdrożeniowe)

> ✅ **STATUS: DO REALIZACJI (2026-06-04).**
> Ten dokument jest projektem wdrożeniowym (design), zatwierdzonym przez
> użytkownika. Zastępuje feasibility-spec
> [`2026-06-03-soft-delete-publikacje.md`](2026-06-03-soft-delete-publikacje.md)
> (publikacje-only, „ODŁOŻONE") i rozszerza go o: soft-delete autora,
> wycofanie z PBN przez kolejkę, tabelę-log audytu oraz wsparcie w adminie.
> Szczegółowy plan TDD powstaje na bazie tego speca (skill
> `superpowers:writing-plans`).

**Cel.** Wprowadzić odwracalne („miękkie") kasowanie tam, gdzie ma to realny
sens, przy minimalnym blast-radiusie:

1. **Publikacje** (5 modeli) — pełny soft-delete: `DELETE` → znacznik
   `deleted_at`; rekord znika z widoku publicznego / ewaluacji / API / PBN,
   dane (w tym powiązania `*_Autor`) zostają i da się je przywrócić.
2. **Autor** — soft-delete **wyłącznie dla autora bez prac** (odwracalny
   „kosz" dla pustych/błędnych rekordów). Autor **z** pracami → `PROTECT`
   (zero kasowania, soft ani hard).
3. **PBN** — soft-delete publikacji wycofuje oświadczenia dyscyplin z profilu
   instytucji, asynchronicznie przez kolejkę (`pbn_export_queue`).
4. **Audyt** — dedykowana tabela `SoftDeleteLog` (kto / kiedy / dlaczego /
   status PBN).
5. **Admin** (superuser-only) — „kosz" zamiast hard-delete, filtr „pokaż
   skasowane", akcja „przywróć", osobna jawna akcja „usuń trwale".

**Stack.** Django, PostgreSQL (triggery `plpython3u`), `django-soft-delete`
(`SoftDeleteModel`, już w `pyproject.toml`), `django-denorm-iplweb`,
Celery + `pbn_export_queue`.

---

## 1. Decyzja architektoniczna nadrzędna — asymetria publikacja vs autor

Połączenie obu ficzerów (soft-delete publikacji ORAZ autora) prowadzi do
celowej **asymetrii**, która drastycznie ogranicza ryzyko:

| | **Publikacje** (5 modeli) | **Autor** |
|---|---|---|
| Mechanizm | Pełny `SoftDeleteModel` | Soft-delete **tylko gdy brak prac** |
| Autor/rekord z pracami | — | **PROTECT** (zero kasowania) |
| Autor/rekord bez prac | — | Soft-delete = odwracalny husk |
| Through-modele `*_Autor` | **Nietknięte** (Projekt A) | Nie stają się soft-delete |
| Doktorat / habilitacja | Soft-delete (są publikacjami) | FK do autora → `PROTECT` |

**Konsekwencja kluczowa:** `Wydawnictwo_*_Autor`, `Praca_Doktorska`,
`Praca_Habilitacyjna` **NIE** stają się `SoftDeleteModel` na potrzeby
soft-delete autora. Soft-delete autora to operacja-liść na pustych rekordach,
więc nie dotyka materializowanych widoków, ewaluacji ani PBN. Cała ryzykowna
robota zostaje skupiona na publikacjach.

**Dlaczego nie kaskada autor→prace ani „guard z 50 publikacjami":**
realny przypadek użycia kasowania autora jest wąski — to wyłącznie puste /
błędne / duplikowane rekordy (literówki, dane testowe, husk po scaleniu).
Nikt nie kasuje autora z 50 pracami („Kowalski zniknął, usuńmy go" się nie
zdarza). Kaskada soft-delete autor+publikacje byłaby ogromną, rzadką operacją
i kasowałaby publikacje współautorów; „guard" wymuszający ręczną edycję 50
publikacji przed usunięciem czyni kasowanie bezużytecznym. Wąska semantyka
„bez prac = soft-delete, z pracami = PROTECT" pokrywa 100% realnej potrzeby.

---

## 2. Publikacje — fundament (Projekt A)

5 modeli: `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`, `Praca_Doktorska`,
`Praca_Habilitacyjna`, `Patent` ← `SoftDeleteModel`.

### 2.1 Trigger jako choke-point (najwrażliwszy, robiony PIERWSZY)

`Rekord` to UNION-view nad materializowaną tabelą `bpp_rekord_mat`, zasilaną
triggerem `bpp_refresh_cache()`
(**baseline: `src/bpp/migrations/0001_cache_functions.sql`** — uwaga: stary
spec referował przed-squashowy `107_cache_functions.sql`). Z `bpp_rekord_mat`
/ `bpp_autorzy_mat` czyta większość systemu (publiczny frontend, multiseek,
global search, ewaluacja `Cache_Punktacja_*`, raporty).

**Fakt z kodu** (`0001_cache_functions.sql:78-87`): na `DELETE` trigger usuwa
wiersze z tabel `_mat`; na `UPDATE/INSERT` re-insertuje. Soft-delete to
technicznie `UPDATE` → **bez zmiany triggera skasowany rekord wróciłby do
mat-view**.

**Zmiana:** ścieżka `UPDATE/INSERT` triggera uczona reguły:
> jeśli `NEW.deleted_at IS NOT NULL` → zachowaj się jak `DELETE` (usuń z
> `bpp_rekord_mat` + `bpp_autorzy_mat`, **nie** re-insertuj).
> `deleted_at: <data>→NULL` (restore) → normalny re-insert.

Trzeba to obsłużyć dla **wszystkich 5 tabel źródłowych** oraz przemyśleć
ścieżkę przez tabele autorskie (`bpp_wydawnictwo_*_autor`, `bpp_patent_autor`)
— tam `deleted_at` siedzi na rekordzie nadrzędnym, nie na wierszu autorskim,
więc warunek czytamy z rekordu rodzica (lub polegamy na tym, że trigger
rodzica już wyczyścił `bpp_autorzy_mat`). Do rozstrzygnięcia w planie TDD;
testy spójności mat-view są obowiązkowe (soft-delete → znika z `Rekord`;
restore → wraca; brak rozjazdu `Cache_Punktacja_*`).

### 2.2 Override `delete()` — bez refleksyjnej kaskady pakietu

`SoftDeleteModel.delete()` domyślnie kaskaduje refleksyjnie po odwrotnych
relacjach. W trybie `strict=True` (domyślny) rzuci `SoftDeleteException` na
nie-soft dzieciach (`*_Autor`, `*_Streszczenie`, `*_Zewnetrzna_Baza_Danych`,
`Publikacja_Habilitacyjna`, `Opi_2012_Tytul_Cache`), a `strict=False` twardo
skasuje je przez CASCADE. **Oba złe.** Dlatego na 5 modelach nadpisujemy
`delete()` tak, by jedynie ustawił `deleted_at` i zapisał (bez kaskady) —
dzieci `*_Autor` zostają nietknięte, a trigger usuwa je z `bpp_autorzy_mat`
jako pochodne. `restore()` (analogicznie bez kaskady) → trigger re-projektuje
wszystko ze źródła. Zweryfikować, że nadpisany `delete()`/`restore()` nadal
emituje sygnały `post_soft_delete`/`post_restore` (patrz §5).

### 2.3 `slug` — warunkowy unique

Wszystkie 5 modeli ma denormalizowany `slug unique=True`. Skasowany rekord
trzyma slug → konflikt przy ponownym utworzeniu. Zamiana na
`UniqueConstraint(fields=["slug"], condition=Q(deleted_at__isnull=True))`.
Migracja (NIE modyfikować istniejących migracji).

### 2.4 Menedżery `Wydawnictwo_*_Manager`

Dziedziczą po `ManagerModeliZOplataZaPublikacjeMixin`
(`src/bpp/models/abstract/fees.py`). Po wpięciu `SoftDeleteModel` trzeba
**przepleść** filtr soft-delete (`deleted_at__isnull=True`) z istniejącymi
metodami (`rekordy_z_oplata()`, `wydawnictwa_nadrzedne_dla_innych()`) — przez
wspólny `QuerySet`/MRO, nie przez nadpisanie.

### 2.5 Audyt kategorii B — miejsca, które MUSZĄ widzieć usunięte

Domyślny menedżer `objects` ukrywa usunięte → kategoria A (wyświetlanie /
eksport / liczenie) staje się czysta automatycznie (zero zmian). Ale
**kategoria B** musi świadomie przejść na `global_objects`, inaczej powstaną
**duplikaty**:

- `import_common/core/publikacja.py`, `importer_publikacji` — matching importu,
- `crossref_bpp/core.py` — dedup,
- `deduplikator_publikacji/tasks.py` — dedup,
- `pbn_integrator/utils/synchronization.py`, `pbn_integrator/importer/chapters.py`,
  `pbn_api/management/*` — matching po `pbn_uid`.

> **Pułapka nadrzędna:** jeśli importer użyje domyślnego (ukrywającego)
> menedżera, soft-delete staje się generatorem duplikatów. Audyt kat. B jest
> obowiązkowy.

---

## 3. Autor — dwie warstwy ochrony + soft-delete husków

Obecne `on_delete` (potwierdzone w kodzie):

| Powiązanie | Plik | Dziś | Docelowo |
|---|---|---|---|
| `Wydawnictwo_*_Autor.autor` | `src/bpp/models/abstract/authors.py:22` (`CASCADE`) | hard-kasuje autorstwa | **PROTECT** |
| `Praca_Doktorska.autor` | `src/bpp/models/praca_doktorska.py:136` (`CASCADE`) | hard-kasuje doktorat | **PROTECT** |
| `Praca_Habilitacyjna.autor` | `src/bpp/models/praca_habilitacyjna.py:42` (`PROTECT`) | już blokuje | bez zmian |

### 3.1 Warstwa 1 — flip FK `CASCADE→PROTECT`

Migracja state-only (Django implementuje `on_delete` w ORM, nie jako
constraint DB → brak zmiany schematu). Broni przed przypadkowym hard-delete
i gołą kaskadą. Tabele atrybutów autora (jednostki, dyscypliny, funkcje,
`Cache_Punktacja_Autora`, profil) **zostają `CASCADE`** — to nie „prace",
mają znikać z autorem.

### 3.2 Warstwa 2 — guard w soft `Autor.delete()`

**Krytyczne:** `PROTECT` na FK łapie tylko hard-delete + kolektor kaskady
Django. Soft-delete to `UPDATE deleted_at=now()` — `on_delete` **nigdy się
nie odpala**. Dlatego `Autor.delete()` (soft) musi jawnie sprawdzić: jeśli
autor ma JAKIEKOLWIEK autorstwo (`Wydawnictwo_Ciagle_Autor`,
`Wydawnictwo_Zwarte_Autor`, `Patent_Autor`) / doktorat / habilitację →
odmowa (`ProtectedError`/`ValidationError` z czytelnym komunikatem).

**Definicja „bez prac":** liczą się WSZYSTKIE wiersze, także wskazujące na
*soft-deletowane* publikacje (najprościej i najbezpieczniej — autor jest
„husk" dopiero gdy naprawdę nic nie wskazuje). Autor `SoftDeleteModel`; jego
wiersze atrybutów zostają nietknięte (restore odtwarza całość).

### 3.3 Synergia z `deduplikator_autorow` (merge)

Merge najpierw przenosi wszystkie prace na autora głównego, potem woła
`autor.delete()` na pustym duplikacie (`src/deduplikator_autorow/views/merge.py:155`;
transfer through-rows w `src/deduplikator_autorow/utils/merge.py:191,284,354`).
Skutki:
- `PROTECT` **nie psuje** merge'a — duplikat jest już pusty w chwili `delete()`.
- Soft-delete sprawia, że husk po scaleniu staje się **odwracalny** (dziś
  znika bezpowrotnie) — błędne scalenie da się cofnąć. Darmowy bonus.
- **Do zweryfikowania w planie TDD:** czy merge przenosi WSZYSTKIE typy prac
  (ciągłe / zwarte / patent / doktorat / habilitacja) przed `delete()` —
  inaczej guard/PROTECT zablokuje usunięcie husku.

---

## 4. PBN — wycofanie oświadczeń przez kolejkę

### 4.1 Co i kiedy

Soft-delete publikacji **z `pbn_uid`** → wycofanie **oświadczeń dyscyplin z
profilu instytucji** (publikacja przestaje liczyć się do ewaluacji). Obiektu
publikacji w PBN **nie ruszamy** (jest współdzielony — pełny `DELETE` mógłby
się wywalić; wycofanie oświadczeń jest zawsze bezpieczne). Gate: jeśli rekord
nigdy nie poszedł do PBN (`pbn_uid is None`) — nic nie robimy.

Prymityw PBN istnieje:
`src/pbn_api/client/mixins/institutions.py:87` →
`delete_all_publication_statements(publicationId)` (+ selektywne
`delete_publication_statement` w `:135`, retry w
`pbn_api/client/publication_sync.py`).

### 4.2 Mechanizm — rozszerzenie istniejącej `pbn_export_queue`

Nie wprowadzamy nowego mechanizmu. Kolejka eksportu PBN żyje jako dedykowana
aplikacja **`src/pbn_export_queue/`** (model `PBN_Export_Queue`: GFK
content_type+object_id, `zamowil`, `ilosc_prob`, `zakonczono_pomyslnie`,
`rodzaj_bledu`, klasyfikacja błędów, locking, „ponowna wysyłka", admin,
`send_to_pbn()`).

Rozszerzenie:
- dodać pole `operacja: TextChoices(WYSYLKA, WYCOFANIE)` (default `WYSYLKA`
  dla kompatybilności wstecznej), migracja,
- gałąź w logice wysyłki: `WYCOFANIE` → `delete_all_publication_statements`,
- status zapisywany jak dla wysyłki (`zakonczono_pomyslnie`, `komunikat`,
  `ilosc_prob`) + odzwierciedlenie w `SentData` i `SoftDeleteLog`.

`SentData` (`src/pbn_api/models/sentdata.py`, GFK + `pbn_uid` +
`submitted_successfully` + `mark_as_successful`/`mark_as_failed`) trzyma stan
PBN per-rekord — po wycofaniu oznaczamy odpowiednio.

### 4.3 Restore → symetria

Restore publikacji → wpis `WYSYLKA` w `pbn_export_queue` (ponowna wysyłka
oświadczeń, dyscypliny wracają do profilu). Symetria delete↔restore.

---

## 5. SoftDeleteLog — dedykowany audyt (NASZ model)

`django-soft-delete` **nie ma** żadnej tabeli-logu — daje tylko pola
`deleted_at`/`restored_at`/`transaction_id` oraz **trzy sygnały**:
`post_soft_delete`, `post_hard_delete`, `post_restore`
(`django_softdelete/signals.py`). Audyt budujemy sami.

**Model `SoftDeleteLog`:** `content_type`, `object_id` (GFK), `akcja`
(`DELETE`/`RESTORE`/`HARD_DELETE`), `user` (kto), `timestamp`, `powod`
(tekst), FK/link do wpisu `pbn_export_queue` + jego status. Centralny dla
wszystkich soft-deletowalnych typów; zasila widok „Kosz"; jedno miejsce
prawdy „co / kto / dlaczego zniknęło i czy PBN przyjął".

**Zasilanie przez receivery sygnałów** (jeden punkt podpięcia dla wszystkich
modeli — odporne na pominięcie):
- `post_soft_delete` → `SoftDeleteLog(DELETE)` + (jeśli `pbn_uid`) wpis
  `WYCOFANIE` w `pbn_export_queue`,
- `post_restore` → `SoftDeleteLog(RESTORE)` + wpis `WYSYLKA`,
- `post_hard_delete` → `SoftDeleteLog(HARD_DELETE)`.

**Niuans „kto":** sygnał nie niesie użytkownika (`delete()` pakietu nie zna
requestu). `user` wstrzykujemy jawnie z warstwy admina (akcja superusera ma
`request.user` pod ręką — przekazujemy go do `delete(user=...)` / przez
kontekst). Operacje systemowe (np. merge, celery) logują `user=None` lub
konto techniczne.

---

## 6. Admin (superuser-only)

Dla 5 modeli publikacji + `Autor`:
- „Usuń" = **soft-delete** (kosz); „Usuń trwale" = osobna, jawnie oznaczona
  akcja superusera (`hard_delete`),
- filtr „Pokaż skasowane" (`deleted_objects`/`global_objects`) + akcja
  „Przywróć",
- pole „powód" przy kasowaniu (trafia do `SoftDeleteLog`),
- admin świadomie używa `global_objects`/`deleted_objects` (nie domyślnego
  ukrywającego menedżera),
- dla `Autor`: próba soft-delete autora z pracami → czytelny komunikat
  z guarda (§3.2).

Precedens: `src/zglos_publikacje/models.py` (`Zgłoszenie_Publikacji` już jest
`SoftDeleteModel` — wzorzec menedżerów/migracji/admina).

---

## 7. Retencja

Brak automatycznego czyszczenia kosza. Soft-deletowane rekordy trwają do
ręcznego „Usuń trwale" superusera. (Auto-hard-delete po N dniach — świadomie
odłożone, YAGNI; można dorobić jako zadanie `CELERYBEAT_SCHEDULE`,
`src/django_bpp/settings/base.py:670`, jeśli zajdzie potrzeba.)

---

## 8. Kolejność prac (fazy; szczegółowy TDD → writing-plans)

1. **Trigger** `bpp_refresh_cache()` — nowa migracja SQL: `deleted_at IS NOT
   NULL` jako DELETE dla 5 tabel + ścieżka tabel autorskich; testy spójności
   cache. **Najwrażliwsze, pierwsze.**
2. **Publikacje** — `SoftDeleteModel` na 5 modelach, override
   `delete()`/`restore()` (bez kaskady), migracje (`deleted_at`+indeks,
   ew. `CONCURRENTLY`), `slug` `UniqueConstraint`, przeplecenie menedżerów.
3. **Audyt kat. B** — przełączenie import/dedup/PBN-matching na
   `global_objects`. Testy: re-import nie tworzy duplikatów.
4. **Autor** — flip FK `CASCADE→PROTECT` (`*_Autor`, doktorat), guard w soft
   `delete()`, soft-delete husku; weryfikacja merge.
5. **PBN** — `operacja WYCOFANIE` w `pbn_export_queue` + restore→`WYSYLKA`;
   integracja `SentData`.
6. **SoftDeleteLog** + receivery sygnałów (`post_soft_delete`/`post_restore`/
   `post_hard_delete`), wstrzykiwanie `user`.
7. **Admin** — kosz / filtr / przywróć / usuń-trwale / powód (5 modeli +
   `Autor`).
8. **Testy regresji** — pełna suita: PBN (duplikaty + wycofanie), dashboard,
   import, ewaluacja, merge autorów, API. Do ~10 min.

---

## 9. Ryzyka

- **Cache/trigger** — rozjazd, jeśli `deleted_at` nie obsłużone we wszystkich
  5 tabelach + ścieżce UPDATE + tabelach autorskich. Najgroźniejsze,
  wydajnościowo wrażliwe. Mitygacja: testy spójności jako pierwsze.
- **Duplikaty** z importu/PBN/dedup, jeśli kat. B nie przejdzie na
  `global_objects`.
- **Merge autorów** — jeśli nie przenosi wszystkich typów prac przed
  `delete()`, PROTECT/guard zablokuje. Zweryfikować.
- **`user` w sygnałach** — łatwo zalogować `None`; zadbać o wstrzyknięcie
  z admina.
- **Denorm** (`django-denorm-iplweb`, `pre_save`) — soft-delete go wprost nie
  psuje, ale zweryfikować `cached_punkty_dyscyplin` po restore.
- **Migracje na dużych tabelach produkcyjnych** — `deleted_at` domyślnie
  `NULL` (bez backfillu), indeks `CONCURRENTLY` jeśli rozmiar wymaga.

---

## 10. Decyzje rozstrzygnięte (z brainstormingu 2026-06-04)

1. **Autor:** z pracami → `PROTECT`; bez prac → soft-delete (husk). Through-
   modele/doktorat/habilitacja **nie** stają się `SoftDeleteModel`.
2. **Publikacje:** Projekt A (override `delete()`, trigger jako choke-point;
   dzieci nietknięte).
3. **PBN przy soft-delete:** wycofanie oświadczeń instytucji
   (`delete_all_publication_statements`), gate na `pbn_uid`; obiektu
   publikacji nie kasujemy.
4. **PBN — mechanizm:** rozszerzenie `pbn_export_queue` o operację
   `WYCOFANIE` (async, retry, admin — istniejąca infra).
5. **Restore → PBN:** auto-zakolejkowanie `WYSYLKA`.
6. **Log:** dedykowany `SoftDeleteLog` zasilany sygnałami pakietu.
7. **Admin:** superuser-only; soft-delete zastępuje „usuń"; hard-delete jako
   osobna jawna akcja.
8. **Retencja:** brak auto-czyszczenia; tylko ręczny hard-delete.

---

## 11. Precedensy w repo

- `django-soft-delete>=1.0.23` — `pyproject.toml`.
- `src/zglos_publikacje/models.py` — `Zgłoszenie_Publikacji` już
  `SoftDeleteModel` (wzorzec).
- `src/pbn_export_queue/` — dojrzała kolejka PBN (model + Celery + admin +
  retry/lock), wzorzec dla operacji `WYCOFANIE`.
- `src/pbn_api/models/sentdata.py` — `SentData` (stan PBN per-rekord).
- `src/bpp/models/oplaty_log.py`, log w `deduplikator_autorow` — precedensy
  tabel-logów.
