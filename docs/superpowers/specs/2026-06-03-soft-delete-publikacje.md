# Spec: Soft-delete dla rekordów publikacji (Wydawnictwo_Ciagle/Zwarte, Doktorat, Habilitacja, Patent)

> ⛔ **STATUS: ODŁOŻONE — na razie (2026-06-03).**
> Ten dokument to spec/analiza wykonalności, a **NIE** zlecenie do
> implementacji. Decyzja: świadomie wstrzymujemy realizację. Spec
> spisany, żeby nie tracić rozpoznania; gdy wrócimy do tematu, startujemy
> stąd. Patrz sekcja [„Dlaczego odkładamy"](#dlaczego-odkładamy).

**Cel:** Umożliwić „miękkie" kasowanie 5 typów rekordów publikacji —
zamiast fizycznego `DELETE` ustawiamy znacznik `deleted_at`, dzięki czemu
rekord znika z
widoku publicznego/ewaluacji/API, ale dane (w tym powiązania autor↔rekord)
zostają i można je przywrócić.

**Architektura (jednozdaniowo):** Wykorzystujemy istniejący w repo pakiet
`django-soft-delete` (`SoftDeleteModel`) na 5 modelach źródłowych, a
spójność z resztą systemu osiągamy w JEDNYM punkcie — w triggerze
PostgreSQL zasilającym materializowany cache `bpp_rekord_mat`, który uczymy
traktować „skasowany" jak zdarzenie DELETE.

**Stack:** Django, PostgreSQL (triggery `plpython3u`), `django-soft-delete`
(już w `pyproject.toml`), `django-denorm-iplweb`.

---

## 1. Motywacja

Dziś `Wydawnictwo_Ciagle/Zwarte`, `Praca_Doktorska`, `Praca_Habilitacyjna`,
`Patent` kasuje się fizycznie (`DELETE`). To pociąga kaskadowo:
- usunięcie wierszy przez-modeli `*_Autor` (powiązania autorów),
- usunięcie wpisów w `bpp_rekord_mat` / `bpp_autorzy_mat` (przez trigger),
- utratę danych bez możliwości cofnięcia.

Soft-delete daje: odzyskiwalność, ślad audytowy, oraz — co podkreślił
użytkownik — **zachowanie powiązań `*_Autor`** nawet gdy rekord nadrzędny
„znika" z widoków.

## 2. Modele w zakresie

| Model | Plik | Menedżer własny? | Through-model autorów |
|---|---|---|---|
| `Wydawnictwo_Ciagle` | `src/bpp/models/wydawnictwo_ciagle.py` | TAK (`Wydawnictwo_Ciagle_Manager`) | `Wydawnictwo_Ciagle_Autor` |
| `Wydawnictwo_Zwarte` | `src/bpp/models/wydawnictwo_zwarte.py` | TAK (`Wydawnictwo_Zwarte_Manager`) | `Wydawnictwo_Zwarte_Autor` |
| `Praca_Doktorska` | `src/bpp/models/praca_doktorska.py` | NIE | (brak; `autor` FK) |
| `Praca_Habilitacyjna` | `src/bpp/models/praca_habilitacyjna.py` | NIE | (brak; `autor` O2O) |
| `Patent` | `src/bpp/models/patent.py` | NIE | `Patent_Autor` |

Żaden z 5 modeli **nie ma** dziś własnego `delete()` ani sygnałów
`pre/post_delete` po stronie Pythona — cała logika kasowania siedzi w
triggerach DB. To upraszcza warstwę ORM.

## 3. Kluczowa decyzja architektoniczna — „choke-point" w triggerze

`Rekord` to UNION-view (`bpp_rekord`) nad materializowaną tabelą
`bpp_rekord_mat`, zasilaną triggerem `bpp_refresh_cache()`
(`src/bpp/migrations/107_cache_functions.sql`). Z tej tabeli czyta
**większość systemu**: publiczny frontend (`browse.py`), `multiseek`,
global search (`search_index`), ewaluacja (`Cache_Punktacja_*`),
raporty.

**Fakt z kodu** (`107_cache_functions.sql:81-86`): na `DELETE` trigger
usuwa wiersze z `bpp_rekord_mat`/`bpp_autorzy_mat`; na `UPDATE/INSERT`
re-insertuje. Ponieważ soft-delete to technicznie `UPDATE`, **bez zmiany
triggera skasowany rekord wróciłby do mat-view** i był widoczny wszędzie.

**Rozwiązanie:** trigger uczymy reguły (kolumna w DB to `deleted_at`,
nie boolean):
> jeśli `NEW.deleted_at IS NOT NULL` → zachowaj się jak `DELETE`
> (usuń wiersze z `bpp_rekord_mat` + `bpp_autorzy_mat`, **nie** re-insertuj).
> Przywrócenie (`deleted_at: <data>→NULL`) to zwykły UPDATE → normalny
> re-insert.

Skutek: **wszystko, co czyta przez `Rekord`/`Autorzy`/`Cache_*`, czyści
się jednym ruchem, bez dotykania kodu konsumentów.**

## 4. Odwrócenie zakresu dzięki `django-soft-delete`

`SoftDeleteModel` (zweryfikowane w
`.venv/.../django_softdelete/models.py`) udostępnia:
- pola DB: `deleted_at`, `restored_at`, `transaction_id` (DateTime/UUID;
  **nie ma** boolowskiego pola — `is_deleted` to *property* nad
  `deleted_at`, filtr w ORM to `deleted_at__isnull`),
- `objects` (`SoftDeleteManager`) — **domyślnie wyklucza** skasowane,
- `global_objects` (`GlobalManager`) — wszystkie (z usuniętymi),
- `deleted_objects` (`DeletedManager`) — tylko usunięte,
- `.delete()` → soft, `.hard_delete()` → fizyczne, `.restore()` →
  przywrócenie.

Konsekwencja dla naszej wcześniejszej analizy „223 miejsc / 47 przecieków":

- **Kategoria A („leak" — wyświetlanie/eksport/liczenie):** ich kod używa
  `Model.objects` → po wpięciu `SoftDeleteModel` **stają się czyste
  automatycznie**. Zero zmian w tych plikach. Dotyczy m.in.:
  `api_v1` (viewsety/serializery), `admin_dashboard` (statystyki,
  time-series), `bpp/views/autocomplete/*`, `bpp/views/browse.py`
  (strona Źródła), `bpp/admin_site.py` (liczniki), `komparator_pbn`,
  `ewaluacja_optymalizacja/utils.py`, `verification.py`,
  `ranking_autorow/forms.py`.
- **Kategoria B („wants-deleted" — MUSI widzieć usunięte):** te miejsca
  trzeba **świadomie przełączyć** z `objects` na `global_objects`,
  inaczej powstaną duplikaty / niespójny sync. To jest realny zakres
  pracy. Dotyczy:
  - `import_common/core/publikacja.py`, `importer_publikacji` — matching
    przy imporcie (inaczej re-import odtworzy skasowaną publikację),
  - `crossref_bpp/core.py:178,182` — dedup,
  - `deduplikator_publikacji/tasks.py` — dedup,
  - `pbn_integrator/utils/synchronization.py:42,69`,
    `pbn_integrator/importer/chapters.py:64`, `pbn_api/management/*` —
    sync z PBN (decyzja: skasowanie powinno raczej polecieć do PBN jako
    wycofanie; matching musi widzieć usunięte po `pbn_uid`).

> **Pułapka nadrzędna:** to właśnie kat. B jest groźna. Gdyby domyślny
> menedżer ukrywał usunięte, a importer go użył — soft-delete zamienia się
> w generator duplikatów. Audyt kat. B jest obowiązkowy.

## 5. Punkty wymagające osobnej uwagi

### 5.1 Własne menedżery `Wydawnictwo_*_Manager`
Dziedziczą po `ManagerModeliZOplataZaPublikacjeMixin`
(`src/bpp/models/abstract/fees.py`). Po wpięciu `SoftDeleteModel` muszą
**złączyć** zachowanie soft-delete (filtr `deleted_at__isnull=True`) z
istniejącą metodą `.rekordy_z_oplata()` / `.wydawnictwa_nadrzedne_dla_innych()`.
Nie wolno ich nadpisać — trzeba przepleść (MRO / wspólny `QuerySet`).

### 5.2 Unikalny `slug`
Wszystkie 5 modeli ma denormalizowany `slug` z `unique=True`. Skasowany
rekord trzyma slug zajęty → konflikt przy ponownym utworzeniu.
Rozwiązanie: warunkowy constraint
`UniqueConstraint(fields=["slug"], condition=Q(deleted_at__isnull=True))`
zamiast `unique=True`. Wymaga migracji (nie modyfikować istniejących!).

### 5.3 Through-modele `*_Autor` i dane pochodne (Cache_Punktacja_*)
Kluczowa obserwacja: `bpp_autorzy_mat`, `Cache_Punktacja_Autora`,
`Cache_Punktacja_Dyscypliny` są **pochodne** — zasila/czyści je trigger.
Gdy rodzic znika z `bpp_rekord_mat`, znikają i one (trigger + FK cascade
`bpp_autorzy_mat`→`bpp_rekord_mat`, `0001_cache_init.sql:19`). Przy
`restore` trigger re-projektuje je ze źródła. **To dzieje się automatycznie
niezależnie od tego, czy `*_Autor` są soft-delete czy nie** — bo cache
jest pochodny.

Pozostaje pytanie o same wiersze **źródłowe** `*_Autor`: zostawić nietknięte
(Projekt A) czy też je soft-deletować kaskadą (Projekt B). Pełna analiza i
rekomendacja — sekcja [5.5](#55-kaskada-delete--auto-undelete--co-naprawdę-robi-pakiet).
(Uwaga: trzeba zweryfikować, czy `Cache_Punktacja_*` faktycznie czyści ten
sam trigger, czy osobny mechanizm przeliczania — jeśli osobny, restore może
wymagać re-przeliczenia.)

### 5.4 GenericForeignKey — sieroty
`Publikacja_Habilitacyjna` i `Nagroda` wskazują na te modele przez
`content_type`+`object_id`. GFK nie kaskaduje. Przy soft-delete obiekt
fizycznie istnieje, więc GFK dalej rozwiązuje się poprawnie — to akurat
**plus** soft-delete (mniej sierot niż przy hard-delete). Trzeba tylko
zdecydować, czy `nagrody`/`publikacje_habilitacyjne` skasowanego rekordu
mają być nadal pokazywane.

### 5.5 Kaskada delete / auto-undelete — co NAPRAWDĘ robi pakiet
**Zweryfikowane w kodzie** (`django_softdelete/models.py`, `delete()` +
`restore()`):

- `SoftDeleteModel.delete()` **domyślnie kaskaduje refleksją** po
  odwrotnych relacjach (`one_to_one`, `one_to_many` = reverse FK),
  pomijając `GenericRelation`. Każdemu skasowanemu obiektowi nadaje wspólny
  `transaction_id`.
- `restore()` używa `transaction_id`, żeby **automatycznie odtworzyć
  dokładnie tę samą grupę** → „un-delete z automatu" działa.
- **ALE** w trybie `strict=True` (domyślny) jeśli powiązany model **nie
  jest** `SoftDeleteModel` → `SoftDeleteException`. A `strict=False` →
  dzieci z `on_delete=CASCADE` zostają **fizycznie skasowane** (czyli
  `*_Autor` przepadają, restore ich nie wskrzesi).

**Problem dla nas:** 5 modeli ma liczne nie-soft dzieci: `*_Autor`,
`*_Streszczenie`, `*_Zewnetrzna_Baza_Danych`, `Publikacja_Habilitacyjna`,
`Opi_2012_Tytul_Cache`. Goła kaskada pakietu **albo rzuci wyjątek
(strict), albo twardo skasuje dzieci (non-strict)** — oba złe.

**Dwa spójne projekty** (rozstrzygnąć w [otwartych decyzjach](#7-otwarte-decyzje),
pkt 1):

- **Projekt A — „cache sam to robi" (rekomendowany).**
  Override `delete()` na 5 modelach tak, by **NIE** robił refleksyjnej
  kaskady — tylko ustawia `deleted_at` i zapisuje. Dzieci `*_Autor`
  zostają **nietknięte** w tabeli źródłowej. Trigger usuwa rodzica z
  `bpp_rekord_mat` → `bpp_autorzy_mat` i `Cache_Punktacja_*` znikają
  automatycznie (są pochodne). `restore()` = `deleted_at→NULL` → trigger
  **re-projektuje** wszystko ze źródła (bo `*_Autor` nigdy nie zniknęły).
  - Plusy: minimalny blast radius, brak wirusowego soft-delete, restore
    automatyczny przez warstwę cache.
  - Minus: bezpośrednie zapytania `Wydawnictwo_*_Autor.objects` (z
    pominięciem rodzica) nadal widzą autorstwa skasowanych rekordów →
    trzeba dodać `.filter(rekord__deleted_at__isnull=True)` w kilku
    miejscach (ewaluacja `verification.py`, `komparator_pbn`).

- **Projekt B — pełna kaskada soft-delete.**
  `*_Autor` (i pozostałe dzieci, które chcemy móc przywrócić) stają się
  `SoftDeleteModel`. Kaskada + `transaction_id` + auto-restore działają
  „z pudełka", a bezpośrednie `*_Autor.objects` czyszczą się same.
  - Plusy: spójne z grain pakietu, brak ręcznych filtrów na through-modelach.
  - Minusy: efekt **wirusowy** — `*_Streszczenie`, `*_Zewnetrzna_Baza`,
    `Publikacja_Habilitacyjna`, `Opi_2012_Tytul_Cache` też muszą stać się
    soft-delete (albo zaakceptować ich twardy CASCADE). Dużo więcej
    migracji i pól; trzeba zweryfikować, że kaskada nie koliduje z
    triggerem (podwójne odświeżanie).

> **Rekomendacja:** Projekt A. Warstwa cache (`Rekord`/trigger) już
> realizuje „pochodne dane znikają i wracają", więc kaskada pakietu jest
> redundantna i tylko mnoży blast radius. Override `delete()` + kilka
> filtrów na through-modelach.

### 5.6 Self-referencja `Wydawnictwo_Zwarte → Wydawnictwo_Zwarte`
Rozdziały wskazują na książkę-matkę (`wydawnictwo_nadrzedne`, CASCADE).
Niezależnie od projektu z 5.5 trzeba zdecydować, czy soft-delete
książki-matki pociąga soft-delete rozdziałów (patrz
[otwarte pytania](#7-otwarte-decyzje), pkt 1).

## 6. Szkic zakresu prac (gdy wrócimy)

Kolejność (nie pełny TDD — to spec; szczegółowy plan TDD powstanie przy
realizacji):

1. **Trigger** `bpp_refresh_cache()` — nowa migracja SQL: obsługa
   `NEW.deleted_at IS NOT NULL` jako DELETE. + testy spójności mat-view (soft-delete →
   znika z `Rekord`; restore → wraca). **Najwrażliwszy, najpierw.**
2. **Modele** — wpięcie `SoftDeleteModel` w 5 modeli; migracja dodająca
   pola pakietu (`deleted_at`, `restored_at`, `transaction_id`) + indeks na
   `deleted_at`. `is_deleted` to property — **nie** tworzyć osobnego pola.
   Nie modyfikować istniejących migracji.
   - Przy **Projekcie A** (rekomendacja, sekcja 5.5): override `delete()`
     tak, by **nie** robił refleksyjnej kaskady pakietu (ustaw `deleted_at`
     i `save()`), inaczej `strict=True` rzuci wyjątkiem na nie-soft
     dzieciach. Zweryfikować też `restore()` (analogicznie bez kaskady).
3. **Menedżery** — przeplecenie soft-delete z `Wydawnictwo_*_Manager`.
4. **`slug`** — warunkowy `UniqueConstraint` (migracja).
5. **Audyt kat. B** — przełączenie import/dedup/PBN na `global_objects`.
6. **Admin** — akcja „przenieś do kosza" (zamiast hard-delete), filtr
   „pokaż skasowane", akcja „przywróć". Admin świadomie używa
   `global_objects`/`deleted_objects`.
7. **Testy regresji** — PBN sync (duplikaty!), dashboard, import,
   ewaluacja, API. Pełna suita (do ~10 min).

## 7. Otwarte decyzje

Do rozstrzygnięcia **zanim** ruszymy implementację:

1. **Projekt kaskady (A vs B) — patrz [5.5](#55-kaskada-delete--auto-undelete--co-naprawdę-robi-pakiet).**
   Rekomendacja: **Projekt A** (override `delete()`, dzieci nietknięte,
   cache/trigger robi resztę). Do potwierdzenia. Powiązane: czy soft-delete
   książki-matki `Wydawnictwo_Zwarte` pociąga rozdziały
   (`wydawnictwo_nadrzedne`)? (Propozycja: NIE automatycznie; ostrzeżenie
   w adminie.)
2. **PBN przy skasowaniu:** czy skasowana publikacja leci do PBN jako
   wycofanie/oświadczenie usuwające, czy tylko przestaje się
   synchronizować?
3. **Kto może kasować/przywracać** i czy potrzebny osobny perm
   (`can_soft_delete` / `can_restore`).
4. **Retencja / hard-delete:** czy po N dniach „kosz" czyści się fizycznie
   (zadanie celery), czy zostaje na zawsze.
5. **Widoczność `nagrody`/`publikacje_habilitacyjne`** skasowanego rekordu.
6. Czy soft-delete dotyczy też przez-modeli `*_Autor` osobno (np. usunięcie
   pojedynczego współautorstwa), czy tylko rekordów nadrzędnych.

## 8. Szacunek nakładu

Przy tej architekturze (trigger jako choke-point + istniejący
`django-soft-delete`):

| Obszar | Nakład |
|---|---|
| Trigger + 5 widoków + testy spójności cache | 2–3 dni |
| Modele + menedżery + migracje (`deleted_at`, `slug` constraint) | 1–2 dni |
| Audyt kat. B (`global_objects`) | 2–3 dni |
| Admin (kosz/filtr/przywracanie) | 2–3 dni |
| Testy regresji (PBN, dashboard, import, ewaluacja) | 3–5 dni |

**Razem realnie ~2–3 tygodnie.** Najwięcej ryzyka: (1) trigger/cache,
(2) duplikaty z importu/PBN przy źle zrobionym kat. B.

## 9. Ryzyka

- **Cache rozjedzie się**, jeśli trigger nie obsłuży `deleted_at IS NOT
  NULL` we wszystkich 5 tabelach + ścieżce UPDATE. Najgroźniejszy,
  wydajnościowo wrażliwy fragment.
- **Duplikaty** z importu/PBN/dedup, jeśli kat. B nie przejdzie na
  `global_objects`.
- **Denorm** (`django-denorm-iplweb`) działa na `pre_save` — soft-delete
  go bezpośrednio nie psuje, ale warto zweryfikować `cached_punkty_dyscyplin`
  po przywróceniu rekordu.
- Migracje dotykają 5 dużych tabel produkcyjnych — `deleted_at` domyślnie
  `NULL` (brak backfillu), indeks na `deleted_at` zakładać `CONCURRENTLY`
  jeśli rozmiar tego wymaga.

## 10. Precedens w repo

- `django-soft-delete>=1.0.23` — `pyproject.toml:122`.
- `src/zglos_publikacje/models.py:10,61` — `Zgłoszenie_Publikacji` już
  dziedziczy po `SoftDeleteModel`. Wzorzec do naśladowania (menedżery,
  migracja, admin).

---

## Dlaczego odkładamy

Świadoma decyzja z **2026-06-03**: temat jest dobrze rozpoznany i
wykonalny (~2–3 tyg.), ale **nie wchodzi teraz w realizację**. Powody:
inne priorytety (m.in. integracja DSpace, prace nad powiązaniami autorów).
Spec spisany, żeby rozpoznanie nie wyparowało. Gdy wrócimy:

1. rozstrzygnąć [otwarte decyzje](#7-otwarte-decyzje),
2. zacząć od triggera (sekcja 6, krok 1) jako najwrażliwszego,
3. dopiero potem reszta.

> Niniejszy dokument NIE jest planem TDD do wykonania. Przy starcie
> realizacji należy wygenerować szczegółowy plan implementacyjny
> (skill `superpowers:writing-plans`) na bazie tego speca.
