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
   `deleted_at`; rekord znika z widoku publicznego / ewaluacji / API / PBN.
   Powiązania `*_Autor` są soft-deletowane razem z rekordem (wąska kaskada,
   §2.2) — zachowane i odwracalne, nie tracone jak przy hard-delete.
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
| Through-modele `*_Autor` | `SoftDeleteModel`, **wąska kaskada** z rodzica | nie kaskadują od autora |
| Doktorat / habilitacja | Soft-delete (są publikacjami) | FK do autora → `PROTECT` |

**Konsekwencja kluczowa (autor):** soft-delete **autora** to operacja-liść na
pustych rekordach — autor z jakimkolwiek autorstwem/doktoratem/habilitacją jest
`PROTECT` (§3), więc usunięcie autora nigdy nie dotyka materializowanych
widoków, ewaluacji ani PBN. Soft-delete autora **nie kaskaduje** do `*_Autor`.

**Konsekwencja kluczowa (publikacja):** through-modele `Wydawnictwo_*_Autor`
i `Patent_Autor` **stają się `SoftDeleteModel`** — ale wyłącznie jako cel
**wąskiej kaskady** z soft-delete publikacji (§2.2), NIE pełnego refleksyjnego
Projektu B. Pozostałe dzieci (`*_Streszczenie`, `*_Zewnetrzna_Baza_Danych`,
`Publikacja_Habilitacyjna`, `Opi_2012_Tytul_Cache`) zostają nie-soft —
kaskada zatrzymuje się na `*_Autor` i **nie jest wirusowa**. Powód: 90
bezpośrednich zapytań `*_Autor.objects` w kodzie (większość w
`ewaluacja_optymalizacja` — najwrażliwszy korekcyjnie podsystem) — domyślny
menedżer `objects` po wpięciu `SoftDeleteModel` czyni je poprawnymi
automatycznie, eliminując 90-punktowe ryzyko „silent leak" do ewaluacji.

**Dlaczego nie kaskada autor→prace ani „guard z 50 publikacjami":**
realny przypadek użycia kasowania autora jest wąski — to wyłącznie puste /
błędne / duplikowane rekordy (literówki, dane testowe, husk po scaleniu).
Nikt nie kasuje autora z 50 pracami („Kowalski zniknął, usuńmy go" się nie
zdarza). Kaskada soft-delete autor+publikacje byłaby ogromną, rzadką operacją
i kasowałaby publikacje współautorów; „guard" wymuszający ręczną edycję 50
publikacji przed usunięciem czyni kasowanie bezużytecznym. Wąska semantyka
„bez prac = soft-delete, z pracami = PROTECT" pokrywa 100% realnej potrzeby.

---

## 2. Publikacje — fundament (Projekt A + wąska kaskada na `*_Autor`)

5 modeli: `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte`, `Praca_Doktorska`,
`Praca_Habilitacyjna`, `Patent` ← `SoftDeleteModel`. Dodatkowo 3 through-modele
`Wydawnictwo_Ciagle_Autor`, `Wydawnictwo_Zwarte_Autor`, `Patent_Autor` ←
`SoftDeleteModel` (cel wąskiej kaskady z rodzica, §2.2).

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
> jeśli `TD['new']['deleted_at'] IS NOT NULL` → zachowaj się jak `DELETE`
> (usuń z `_mat`, **nie** re-insertuj).
> `deleted_at: <data>→NULL` (restore) → normalny re-insert.

**Jednolitość dzięki wąskiej kaskadzie na `*_Autor` (§2.2).** Ponieważ
through-modele też stają się `SoftDeleteModel`, **każda z 8 tabel pod
triggerem ma własną kolumnę `deleted_at`** (5 publikacji + 3 `*_autor`).
Trigger czyta `deleted_at` z **własnego** wiersza (`TD['new']`) — reguła
działa identycznie niezależnie od tego, czy zadziałała tabela publikacji czy
tabela autorska. **Nie ma potrzeby JOIN-a/lookupu do rekordu nadrzędnego.**

Skutki:
- **Mechanizm #1 — filtr `deleted_at IS NULL` w widokach źródłowych** (po
  **własnej** kolumnie tabeli, bez JOIN): `bpp_*_autorzy` (selektują
  `FROM bpp_*_autor`, `src/bpp/migrations/0001_widoki_autorzy.sql`) i każda
  gałąź UNION-u `bpp_rekord`. **To jest nadrzędny mechanizm**, bo pokrywa
  WSZYSTKIE ścieżki: re-insert triggera, bezpośredni odczyt z widoku `bpp_rekord`
  (`Rekord` czyta `bpp_rekord`, `src/bpp/models/cache/rekord.py:357`), oraz
  pełną re-projekcję/weryfikację cache.
- **Mechanizm #2 (optymalizacja) — trigger-skip:** w gałęzi `UPDATE/INSERT`
  `if TD['new'].get('deleted_at') is not None: <pomiń re-insert>`. Oszczędza
  no-op SELECT/INSERT, ale **sam nie wystarcza** (nie pokrywa odczytu z widoku
  ani `verify_cache`). Filtr widoku (#1) jest obowiązkowy; trigger-skip
  opcjonalny.
- **`verify_cache` (`src/bpp/management/commands/verify_cache.py`)** porównuje
  `bpp_rekord_mat` ze źródłem — MUSI respektować `deleted_at` (przez filtr #1),
  inaczej zgłosi fałszywy rozjazd dla skasowanych i spróbuje je wskrzesić.
- **Przypadek brzegowy znika strukturalnie:** edycja wiersza autorstwa
  skasowanej publikacji nie wskrzesi go w `bpp_autorzy_mat`, bo widok
  źródłowy go odfiltruje (ma własne `deleted_at` ustawione kaskadą).
- **Koszt:** soft-delete publikacji z N autorami odpala N dodatkowych (no-op)
  triggerów through. Pomijalne.

Testy spójności mat-view obowiązkowe (soft-delete → znika z `Rekord` i
`Autorzy`; restore → wraca; `verify_cache` czysty po soft-delete; brak
rozjazdu `Cache_Punktacja_*`).

### 2.2 Override `delete()` — wąska, kontrolowana kaskada na `*_Autor`

`SoftDeleteModel.delete()` domyślnie kaskaduje **refleksyjnie** po wszystkich
odwrotnych relacjach. W `strict=True` (domyślny) rzuci `SoftDeleteException`
na nie-soft dzieciach (`*_Streszczenie`, `*_Zewnetrzna_Baza_Danych`,
`Publikacja_Habilitacyjna`, `Opi_2012_Tytul_Cache`), a `strict=False` twardo
skasuje je przez CASCADE. **Oba złe.** Dlatego na 5 modelach nadpisujemy
`delete()` tak, by **NIE** używał refleksyjnej kaskady pakietu, lecz:

1. ustawił własne `deleted_at` i zapisał,
2. **jawnie soft-deletował własne wiersze `*_Autor`** (`Wydawnictwo_Ciagle_Autor`
   / `Wydawnictwo_Zwarte_Autor` / `Patent_Autor`) pod **wspólnym
   `transaction_id`** — kaskada wąska, kontrolowana, zatrzymana na `*_Autor`.

Pozostałe dzieci (`*_Streszczenie`, `*_Zewnetrzna_Baza_Danych`,
`Publikacja_Habilitacyjna`, `Opi_2012_Tytul_Cache`) **nie są ruszane** (nie są
`SoftDeleteModel`, czyta się je przez rodzica). `restore()` analogicznie:
przywraca rodzica i jego `*_Autor` po `transaction_id`. Trigger (§2.1) usuwa
wszystko z `_mat` na podstawie własnych `deleted_at`; przy restore
re-projektuje ze źródła.

Po co jawna kaskada na `*_Autor`, skoro trigger i tak czyści `bpp_autorzy_mat`?
Bo **90 miejsc w kodzie czyta `*_Autor.objects` bezpośrednio** (z pominięciem
cache), głównie w `ewaluacja_optymalizacja`. Domyślny menedżer `objects`
`SoftDeleteModel` ukrywa skasowane → te 90 miejsc staje się poprawne
automatycznie, bez ręcznych filtrów `wydawnictwo_ciagle__deleted_at__isnull`
(których pominięcie = po cichu zliczona skasowana praca w ewaluacji).

Zweryfikować, że nadpisany `delete()`/`restore()` nadal emituje sygnały
`post_soft_delete`/`post_restore` (patrz §5), oraz że ścieżka queryset
(`.delete()` na QS) również kaskaduje na `*_Autor`.

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

**Through-modele `*_Autor` (90 miejsc).** Po wpięciu `SoftDeleteModel`
90 bezpośrednich zapytań `*_Autor.objects` (głównie `ewaluacja_optymalizacja`:
`reset_pins`, `reset_disciplines`, `unpin_all_sensible`, `optimization`,
`author_works`, `evaluation_browser`, `verification`; oraz `api_v1`,
`przemapuj_prace_autora`, `ewaluacja_dwudyscyplinowcy`) **staje się poprawne
domyślnie** (pomijają skasowane). Audyt sprawdza wyjątki kat. B: czy
któreś z nich *musi* widzieć skasowane autorstwa (mało prawdopodobne w
ewaluacji — tam „pomiń skasowane" jest poprawnym defaultem) → wtedy
`global_objects`. Domyślny default „pomijaj" jest tu znacznie bezpieczniejszy
niż przeciwny.

### 2.6 Self-referencja `Wydawnictwo_Zwarte` + GenericForeignKey

**Self-FK `wydawnictwo_nadrzedne`** (`src/bpp/models/wydawnictwo_zwarte.py:202`,
rozdziały → książka-matka; denorm `@depend_on_related("self",
"wydawnictwo_nadrzedne")`). Wąska kaskada (§2.2) zatrzymuje się na `*_Autor` —
**nie kaskaduje na rozdziały**. Soft-delete książki-matki zostawia rozdziały
widoczne, wskazujące na skasowaną książkę.

> **DECYZJA (proponowana, do potwierdzenia):** soft-delete książki-matki
> **NIE** kaskaduje automatycznie na rozdziały (są niezależnymi publikacjami,
> często z osobnym dorobkiem autorów); admin pokazuje **ostrzeżenie** „ta
> książka ma N rozdziałów — zostaną widoczne". Alternatywa: kaskada na
> rozdziały (jak na `*_Autor`). Powiązane: zweryfikować, że denorm
> `depend_on_related("self", ...)` nie wywala się przy ustawianiu `deleted_at`
> rodzica.

**GenericForeignKey** (`Nagroda`, `Publikacja_Habilitacyjna` → rekord przez
`content_type`+`object_id`): przy soft-delete obiekt **fizycznie istnieje**,
więc GFK rozwiązuje się poprawnie — soft-delete jest tu *bezpieczniejszy* niż
hard-delete (mniej sierot). Do rozważenia tylko, czy `nagrody` skasowanego
rekordu mają być nadal pokazywane (domyślnie: skoro rekord w koszu, jego
podstrona i tak znika — kwestia bez realnego skutku).

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

> **Interakcja z kaskadą §2.2 (krytyczne!):** `*_Autor` są teraz
> `SoftDeleteModel`, a soft-delete publikacji kaskadowo soft-deletuje ich
> wiersze. Domyślny `*_Autor.objects` **ukrywa** te skasowane autorstwa.
> Gdyby guard użył `objects`, autor, którego wszystkie prace są w koszu,
> wyglądałby na „pustego" i przeszedłby przez guard — łamiąc decyzję „licz
> wszystko, też kosz". **Guard musi liczyć przez `*_Autor.global_objects`**
> (i analogicznie doktorat/habilitację przez `global_objects`), żeby widzieć
> również kaskadowo-skasowane autorstwa. To samo dotyczy FK `PROTECT`:
> chroni przed hard-delete niezależnie od `deleted_at` (constraint DB widzi
> wiersz fizyczny).

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
PBN per-rekord. **Po udanym wycofaniu:** ustawiamy `submitted_successfully =
False` (rekord nie jest już „wystawiony" w PBN) i dodajemy znacznik wycofania
(np. `withdrawn_at` — nowe pole, lub `api_response_status`); **wiersza
`SentData` NIE kasujemy** — zostaje dla audytu i re-matchingu przy restore.
Restore (`WYSYLKA`) → ponowne `mark_as_successful` po udanej wysyłce.

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

1. **`*_Autor` + trigger + widoki** — kolejność wewnątrz fazy: (a) migracja
   `SoftDeleteModel` na 3 through-modelach (`deleted_at`+indeks) — **musi być
   PRZED** (b), bo trigger/widok czytają tę kolumnę; (b) filtr `deleted_at IS
   NULL` w widokach źródłowych `bpp_rekord`/`bpp_*_autorzy` (mechanizm #1, po
   własnej kolumnie); (c) funkcja `bpp_refresh_cache()` z regułą
   `deleted_at IS NOT NULL → pomiń re-insert` (opcjonalna optymalizacja).
   Testy spójności mat-view + `verify_cache`. **Najwrażliwsze, pierwsze.**
2. **Publikacje** — `SoftDeleteModel` na 5 modelach, override
   `delete()`/`restore()` z **wąską kaskadą na `*_Autor`** (wspólny
   `transaction_id`, bez refleksyjnej kaskady pakietu), migracje
   (`deleted_at`+indeks, ew. `CONCURRENTLY`), `slug` `UniqueConstraint`,
   przeplecenie menedżerów.
3. **Audyt kat. B** — przełączenie import/dedup/PBN-matching na
   `global_objects`; audyt 90 miejsc `*_Autor.objects` (default „pomijaj"
   poprawny, wyjątki → `global_objects`). Testy: re-import nie tworzy
   duplikatów; ewaluacja pomija prace w koszu.
4. **Autor** — flip FK `CASCADE→PROTECT` (`*_Autor`, doktorat), guard w soft
   `delete()` **liczący przez `global_objects`** (widzi kaskadowo-skasowane
   autorstwa), soft-delete husku; weryfikacja merge.
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
  8 tabelach (5 publikacji + 3 `*_autor`) + ścieżce UPDATE + widokach
  źródłowych. Najgroźniejsze, wydajnościowo wrażliwe. Mitygacja: testy
  spójności jako pierwsze.
- **Guard autora przez `objects` zamiast `global_objects`** — autor z pracami
  tylko-w-koszu przeszedłby przez guard (autorstwa kaskadowo skasowane są
  ukryte). MUSI być `global_objects` (§3.2).
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

1. **Autor:** z pracami → `PROTECT`; bez prac → soft-delete (husk). Guard
   liczy przez `global_objects`. Soft-delete autora **nie** kaskaduje do
   `*_Autor`. Doktorat/habilitacja: FK do autora → `PROTECT`.
2. **Publikacje:** Projekt A z **wąską kaskadą na `*_Autor`** — 5 modeli +
   3 through-modele `*_Autor` stają się `SoftDeleteModel`; override `delete()`
   soft-deletuje rodzica i jego `*_Autor` (wspólny `transaction_id`), bez
   refleksyjnej kaskady na pozostałe dzieci. Trigger jako choke-point,
   jednolity dzięki własnym `deleted_at` na wszystkich 8 tabelach (bez JOIN
   do rodzica). Powód kaskady: 90 miejsc `*_Autor.objects` w ewaluacji.
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
9. **Cache — mechanizm nadrzędny:** filtr `deleted_at IS NULL` w widokach
   źródłowych (pokrywa trigger, odczyt z `bpp_rekord`, `verify_cache`);
   trigger-skip to opcjonalna optymalizacja.
10. **SentData przy wycofaniu:** `submitted_successfully=False` + znacznik
    wycofania, wiersza nie kasujemy.

**Oczekuje potwierdzenia:**
- **Self-FK `Wydawnictwo_Zwarte` (rozdziały):** propozycja — soft-delete
  książki-matki NIE kaskaduje na rozdziały, admin ostrzega (§2.6).

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
