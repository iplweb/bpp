# Spec: Soft-delete publikacji + autorów (jedno opracowanie wdrożeniowe)

> ✅ **STATUS: DO REALIZACJI (2026-06-04; zrewidowany 2026-08-06).**
>
> 🔄 **Rewizja 2026-08-06.** Spec powstał przed PR #363 (port
> `bpp_refresh_cache` PL/Python → PL/pgSQL + bramka `WHEN`, migracje
> `0432`/`0433`). Weryfikacja na aktualnym `dev` obaliła **dwa nośne
> założenia** o warstwie cache — §2.1 przepisana od zera, decyzja #9
> unieważniona. Domknięto też 5 luk/decyzji (#12–#16): `Cache_Punktacja_*`,
> warunkowy unique na `*_Autor`, polityka importu wobec kosza, dwuwejściowe
> wycofanie z PBN, semantyka `full_refresh()`. Dowód empiryczny obalonych
> założeń: `src/bpp/tests/test_cache/test_soft_delete_preconditions.py`.
>
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
   instytucji: asynchronicznie przez kolejkę (`pbn_export_queue`) lub
   synchronicznie, gdy rekord szedł do PBN bez kolejki (§4.2).
4. **Audyt** — dedykowana tabela `SoftDeleteLog` (kto / kiedy / dlaczego /
   status PBN).
5. **Admin** (superuser-only) — „kosz" zamiast hard-delete, filtr „pokaż
   skasowane", akcja „przywróć", osobna jawna akcja „usuń trwale".

**Stack.** Django, PostgreSQL (triggery **PL/pgSQL** — po porcie z `plpython3u`,
PR #363), `django-soft-delete`
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
kaskada zatrzymuje się na `*_Autor` i **nie jest wirusowa**. Powód: 89
bezpośrednich, produkcyjnych zapytań `*_Autor.objects` w kodzie (większość w
`ewaluacja_optymalizacja` — najwrażliwszy korekcyjnie podsystem) — domyślny
menedżer `objects` po wpięciu `SoftDeleteModel` czyni je poprawnymi
automatycznie, eliminując 89-punktowe ryzyko „silent leak" do ewaluacji.

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

> 🔄 **Sekcja przepisana 2026-08-06** po weryfikacji na aktualnym `dev`.
> Poprzednia wersja opisywała funkcję `bpp_refresh_cache()` z migracji
> `0399_fix_refresh_cache_upsert.sql` (PL/Python). **Ta funkcja już nie
> istnieje** — PR #363 (migracje `0432`/`0433`) zastąpił ją 16 statycznymi
> funkcjami PL/pgSQL i bramką `WHEN` na triggerach UPDATE. Oba założenia,
> na których stała poprzednia wersja, są **fałszywe**; dowód w kanarkach
> `src/bpp/tests/test_cache/test_soft_delete_preconditions.py`.

`Rekord` to model nad **tabelą materializowaną `bpp_rekord_mat`**
(`src/bpp/models/cache/rekord.py:382-386` — `db_table = "bpp_rekord_mat"`;
widok `bpp_rekord` obsługuje osobna, marginalna klasa `RekordView`, `:394-396`).
Z `bpp_rekord_mat`/`bpp_autorzy_mat` czyta większość systemu (publiczny
frontend, multiseek, global search, raporty). **Tabele `_mat` utrzymywane są
WYŁĄCZNIE triggerami** — nie ma innej ścieżki zapisu.

**Stan faktyczny po PR #363** (`0432_cache_trigger_plpgsql.py`,
`0433_cache_trigger_when_gate.py`):

- 8 tabel bazowych (5 publikacji + 3 `*_autor`), każda z **trzema** triggerami:
  `_cache_ins` (AFTER INSERT, bezwarunkowy), `_cache_del` (AFTER DELETE,
  bezwarunkowy), `_cache_upd` (AFTER UPDATE, **bramkowany**);
- funkcja refresh dla publikacji to **czysty upsert, BEZ `DELETE`**:
  ```sql
  PERFORM pg_advisory_xact_lock(ct, NEW.id);
  INSERT INTO bpp_rekord_mat (...) SELECT ... FROM bpp_<typ>_view
    WHERE object_id_raw = NEW.id
    ON CONFLICT (id) DO UPDATE SET ...;
  ```
- bramka na UPDATE to `WHEN (OLD."kol" IS DISTINCT FROM NEW."kol" OR ...)`,
  gdzie lista kolumn jest **wyliczana z `pg_depend`** (kolumny bazowe, które
  widok faktycznie czyta) **w momencie migracji** i wklejona na sztywno
  w definicję triggera.

**Dwa fałszywe założenia poprzedniej wersji (potwierdzone testem):**

| Założenie | Rzeczywistość |
|---|---|
| „UPDATE ustawiający `deleted_at` doleci do triggera" | **Nie doleci.** `django-soft-delete` zapisuje przez `save(update_fields=['deleted_at','restored_at','transaction_id'])`. Żadna z tych kolumn nie jest w bramce (i być nie może — nie zasilają widoku), więc `WHEN` jest fałszywe. Efekt uboczny `update_fields`: `ostatnio_zmieniony` (`auto_now`) też **nie** jest bumpowany, więc nie ma przypadkowego ratunku. |
| „Filtr `deleted_at IS NULL` w widoku wystarczy, bo trigger robi bezwarunkowy `DELETE` przed upsertem" | **Nie robi.** `INSERT ... SELECT` z widoku, który odfiltrował wiersz, wybiera zero wierszy → **no-op** → stary wiersz przeżywa w `_mat`. Inwariant „delete-first" nie istnieje dla `bpp_rekord_mat`. |

**Wzorzec do naśladowania jest już w kodzie.** Gałąź doktorat/habilitacja
w `_create_rekord_function` robi dokładnie to, czego potrzebujemy — bo tam
wiersz **może wypaść ze źródła** (widok `*_autorzy` ma INNER JOIN do
`bpp_autor`):

```sql
DELETE FROM bpp_autorzy_mat WHERE rekord_id = ARRAY[ct, NEW.id]::integer[];
INSERT INTO bpp_autorzy_mat (...) SELECT ... ;
```

Soft-delete to uogólnienie tej samej sytuacji na wszystkie 8 tabel.

**Zmiana — CZTERY elementy, wszystkie OBOWIĄZKOWE** (żaden nie wystarcza sam;
> 🔄 **liczba poprawiona 2026-08-06** po finalnej recenzji fazy 01: pierwotna
> wersja tej sekcji zatrzymywała się na trzech i faza 01 dokładnie w to
> trafiła — widok źródłowy + gałąź kasująca + bramka `WHEN` przeszły bez
> problemu, ale finalna recenzja osobno znalazła TRZY widoki POCHODNE
> (`bpp_<typ>_view.liczba_autorow`, `bpp_nowe_sumy_*_view`,
> `rozbieznosci_dyscyplin_zrodel`), które czytały surową tabelę `*_autor`
> niezależnie od widoku źródłowego z punktu 3 i wymagały osobnych migracji
> `0494`/`0495`/`rozbieznosci_dyscyplin/0022`. Punkt 4 poniżej domyka ten
> wzorzec jako STAŁY element checklisty, nie jednorazową łatkę):

1. **Gałąź kasująca w 8 funkcjach refresh.** Prolog przed upsertem:
   ```sql
   IF NEW.deleted_at IS NOT NULL THEN
       DELETE FROM bpp_rekord_mat WHERE id = ARRAY[ct, NEW.id]::integer[];
       RETURN NULL;
   END IF;
   ```
   (dla `*_autor` analogicznie na `bpp_autorzy_mat`). Restore
   (`deleted_at: data→NULL`) przechodzi dalej do normalnego upsertu — symetria
   za darmo.
2. **Regeneracja bramki `WHEN`** — żeby UPDATE w ogóle doszedł do funkcji.
   Nie hardkodujemy `deleted_at`: bramka wylicza kolumny z `pg_depend` po
   definicji widoku, więc **gdy punkt 3 wstawi `deleted_at` do `WHERE` widoku,
   ponowne uruchomienie logiki `forward()` z `0433` samo ją wciągnie**. Nowa
   migracja = `RunPython` wołający tę samą funkcję (kolejność: najpierw widok,
   potem regeneracja bramki).
3. **Filtr `deleted_at IS NULL` w widokach źródłowych** — po **własnej**
   kolumnie tabeli, bez JOIN do rodzica (każda z 8 tabel ma własne
   `deleted_at`, patrz §2.2). Rola tego filtra jest **inna niż zakładano**:
   nie sprząta `_mat` (to robi punkt 1), tylko (a) karmi `pg_depend` dla
   punktu 2 i (b) gwarantuje, że pełne przebudowy i odczyty przez `bpp_rekord`
   nie wskrzeszą kosza.
4. **Widoki i agregaty POCHODNE** — każdy widok SQL poza `bpp_*_view`/
   `bpp_*_autorzy` (punkt 3), który JOIN-uje lub podzapytuje którąkolwiek z
   8 tabel objętych soft-delete, musi być znaleziony i naprawiony osobno —
   filtr w widoku źródłowym NIE propaguje się automatycznie do widoków,
   które czytają surową tabelę bazową zamiast widoku już przefiltrowanego.
   Znalezione (i naprawione) w fazie 01: `bpp_<typ>_view.liczba_autorow`
   (`count()` po surowej `*_autor`), `bpp_nowe_sumy_*_view` (ranking
   autorów), `rozbieznosci_dyscyplin_zrodel`. Dla `count()`/agregatów: użyj
   `FILTER (WHERE deleted_at IS NULL)`, NIE warunku w `JOIN`/`WHERE` — ten
   drugi zamienia `LEFT JOIN` w efektywny `INNER JOIN` i wywala z widoku
   całą publikację, której WSZYSTKIM autorom soft-deletowano wiersz
   (patrz `bpp/migrations/0494_liczba_autorow_bez_skasowanych.py`).
   **Źródłem prawdy o tym, co jeszcze nie jest naprawione, jest żywy
   `pg_views` — nie pliki migracji** (późniejsze migracje nadpisują
   wcześniejsze definicje widoków, a `baseline.sql` bywa snapshotem sprzed
   części migracji). Faza 01 dodała kanarka katalogowego
   (`src/bpp/tests/test_soft_delete/test_kanarek_katalogowy.py`), który
   odpytuje `pg_views` i pilnuje tego niezmiennika automatycznie dla całej
   listy tabel objętych soft-delete — faza 02 rozszerza jego stałą
   modułową o 5 tabel publikacji zamiast odkrywać te widoki ręcznie.

**Jednolitość dzięki wąskiej kaskadzie na `*_Autor` (§2.2).** Ponieważ
through-modele też stają się `SoftDeleteModel`, każda z 8 tabel pod triggerem
ma własną kolumnę `deleted_at`. Funkcja czyta `deleted_at` z **własnego**
wiersza (`NEW`) — reguła działa identycznie dla tabeli publikacji i autorskiej.
**Nie ma potrzeby JOIN-a/lookupu do rekordu nadrzędnego.**

**Przypadek brzegowy znika strukturalnie:** edycja wiersza autorstwa
skasowanej publikacji nie wskrzesi go w `bpp_autorzy_mat` — jego własne
`deleted_at` jest ustawione kaskadą, więc gałąź z punktu 1 zadziała.

**Koszt:** soft-delete publikacji z N autorami odpala N dodatkowych triggerów
through (każdy = jeden `DELETE` po indeksie). Pomijalne.

⚠️ **`full_refresh()` NIE jest re-projekcją `_mat`.**
`Rekord.objects.full_refresh()` (`src/bpp/models/cache/rekord.py:121-127`) to
`denorm.rebuildall(...)` — przebudowa pól denormalizowanych, nie odtworzenie
`_mat` z widoków. Nie nadaje się jako weryfikacja spójności soft-delete (nigdy
nic z `_mat` nie usuwa, więc test „po `full_refresh()` skasowane nie wracają"
przeszedłby z fałszywych powodów). Dodatkowo po wpięciu `SoftDeleteModel`
`rebuildall` iteruje po domyślnym managerze, więc **pominie rekordy
skasowane** — to jest pożądane, ale zapisujemy jako świadomą decyzję (#12),
nie odkrycie.

⚠️ `src/bpp/management/commands/verify_cache.py` to **martwy stub**
(`psycopg2.connect(database="b_med", host="linux-dev")` + `raise
NotImplementedError`) — nie da się go uruchomić; naprawa POZA zakresem.

**Weryfikacja spójności robimy wprost, surowym SQL-em** (wzorzec:
`src/bpp/tests/test_cache/test_cache_plpgsql_port.py`): soft-delete → wiersza
nie ma w `bpp_rekord_mat`/`bpp_autorzy_mat`; restore → wraca i zgadza się
kolumna-po-kolumnie ze świeżo policzonym widokiem; `ctid` do wykrywania
jałowych przepisań.

### 2.2 Override `delete()` — wąska, kontrolowana kaskada na `*_Autor`

`SoftDeleteModel.delete()` domyślnie kaskaduje **refleksyjnie** po wszystkich
odwrotnych relacjach.

⚠️ **Korekta 2026-08-06:** poprzednia wersja tej sekcji twierdziła, że
`strict=True` jest domyślne. W zainstalowanej wersji pakietu jest **odwrotnie**
(`django_softdelete/models.py`): `delete(self, strict: bool = False, ...)`,
ale `restore(self, strict: bool = True, ...)`. To czyni argument za własnym
override'em **mocniejszym**, nie słabszym: przy `strict=False` kaskada nie
krzyknie `SoftDeleteException` na nie-soft dzieciach — **po cichu przejedzie
po wszystkich odwrotnych relacjach**. Asymetria `delete`/`restore` to dodatkowy
powód, by nie polegać na domyślnym zachowaniu pakietu w żadną stronę.

Nie-soft dzieci (`*_Streszczenie`, `*_Zewnetrzna_Baza_Danych`,
`Publikacja_Habilitacyjna`, `Opi_2012_Tytul_Cache`) nie mają być ruszane
w żadnym trybie. Dlatego na 5 modelach nadpisujemy `delete()` tak, by **NIE**
używał refleksyjnej kaskady pakietu, lecz:

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
Bo **89 miejsc w kodzie produkcyjnym czyta `*_Autor.objects` bezpośrednio** (z pominięciem
cache), głównie w `ewaluacja_optymalizacja`. Domyślny menedżer `objects`
`SoftDeleteModel` ukrywa skasowane → te 89 miejsc staje się poprawnych
automatycznie, bez ręcznych filtrów `wydawnictwo_ciagle__deleted_at__isnull`
(których pominięcie = po cichu zliczona skasowana praca w ewaluacji).

Zweryfikować, że nadpisany `delete()`/`restore()` nadal emituje sygnały
`post_soft_delete`/`post_restore` (patrz §5), oraz że ścieżka queryset
(`.delete()` na QS) również kaskaduje na `*_Autor`.

### 2.2b `unique_together` na `*_Autor` — też warunkowy (decyzja #13)

Ten sam problem co ze slugiem (§2.3), przeoczony w pierwszej wersji specu.
`BazaModeluOdpowiedzialnosciAutorow` ma w konkretnych klasach (np.
`src/bpp/models/wydawnictwo_ciagle.py:73-77`):

```python
unique_together = [
    ("rekord", "autor", "typ_odpowiedzialnosci"),
    ("rekord", "autor", "kolejnosc"),
]
```

Soft-deletowany wiersz `*_Autor` **nadal zajmuje slot w unique**, będąc
niewidocznym dla operatora. Realny scenariusz kolizji: `deduplikator_autorow`
przenosi autorstwa z duplikatu na autora głównego
(`src/deduplikator_autorow/utils/merge.py:191,284,354`) i trafia w
soft-deletowany wiersz o tej samej trójce → `IntegrityError` o rekord, którego
nie widać.

**DECYZJA: zamienić na warunkowy `UniqueConstraint`** — spójnie ze slugiem:

```python
constraints = [
    models.UniqueConstraint(
        fields=["rekord", "autor", "typ_odpowiedzialnosci"],
        condition=Q(deleted_at__isnull=True),
        name="...",
    ),
    models.UniqueConstraint(
        fields=["rekord", "autor", "kolejnosc"],
        condition=Q(deleted_at__isnull=True),
        name="...",
    ),
]
```

⚠️ Uwaga wykonawcza: `unique_together` jest walidowane także przez
`Model.validate_unique()` (formularze adminu), a `UniqueConstraint` z
`condition` **nie jest** brane pod uwagę przez `validate_unique` w starszym
Django. Zweryfikować w fazie 02, czy admin inline'ów autorstwa nadal daje
czytelny komunikat zamiast `IntegrityError` — komentarz przy drugiej krotce
(„Tu musi być autor, inaczej admin nie pozwoli wyedytować") sugeruje, że ten
constraint istnieje właśnie ze względu na admina.

### 2.3 `slug` — warunkowy unique

⚠️ `slug` to **pole denormalizowane** (`@denormalized(models.SlugField, ...,
unique=True, ...)` z `django-denorm-iplweb`), zadeklarowane w 4 miejscach:
`wydawnictwo_ciagle.py:246`, `wydawnictwo_zwarte.py:325`, `patent.py:180`,
`Praca_Doktorska_Baza:105` (dzielone przez doktorat i habilitację). Skasowany
rekord trzyma slug → konflikt przy ponownym utworzeniu. Zmiana: **zdjąć
`unique=True` z kwargs denorm** i dodać w `Meta` każdej konkretnej klasy
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

**Co po dopasowaniu do rekordu w koszu (decyzja #14).** Samo przejście na
`global_objects` usuwa duplikaty, ale otwiera drugie pytanie: importer
dopasował po `pbn_uid`/DOI rekord, który operator świadomie skasował — i co
teraz? Bez rozstrzygnięcia domyślnie „zaktualizowałby go po cichu", czyli
import nadpisywałby zawartość kosza.

> **DECYZJA: POMIŃ + ZARAPORTUJ.** Rekord w koszu nie jest tykany; trafienie
> ląduje w raporcie importu jako osobna kategoria (nie „błąd", nie „utworzono").
> Uzasadnienie: soft-delete to jawna deklaracja operatora „tego tu nie ma";
> cichy update kosza ją podważa, a auto-restore pozwoliłby importowi wskrzeszać
> rzeczy skasowane celowo. Nowy rekord obok też odpada — odtwarzałby dokładnie
> ten problem duplikatów, przed którym broni `global_objects`.
>
> Wymaganie wykonawcze: **każda** ścieżka kat. B musi mieć gdzie ten fakt
> zaraportować. Tam, gdzie importer nie ma struktury raportu, wystarczy log
> + licznik; nie wolno pominąć milcząco.

### 2.5b `Cache_Punktacja_*` — praca w koszu nie może liczyć się do ewaluacji

⚠️ **Luka wykryta 2026-08-06** — nie pokrywa jej wąska kaskada na `*_Autor`.

`Cache_Punktacja_Autora` i `Cache_Punktacja_Dyscypliny`
(`src/bpp/models/cache/punktacja.py`) to **osobne tabele**, kluczowane tablicą
`rekord_id = [content_type_id, pk]`. Nie mają FK do publikacji, więc **żadna
kaskada Django ich nie ruszy**, a triggery cache ich nie dotyczą. Zapisywane
są z `src/bpp/models/sloty/core.py:401,439`.

Czytane bezpośrednio, z pominięciem `Rekord`, m.in. w:
- `src/ewaluacja_optymalizacja/utils.py:182`,
- `src/ewaluacja_optymalizacja/views/evaluation_browser/prefetch.py:41`,
- `src/oswiadczenia/views.py:353`.

Bez osobnego mechanizmu **soft-deletowana praca dalej wnosi sloty i punkty do
ewaluacji** — czyli dokładnie ten „silent leak", przed którym broni §2.2, tyle
że innym kanałem.

> **DECYZJA: kasować przy soft-delete, przeliczać przy restore (#15).**
> - `post_soft_delete` publikacji → usuń wiersze `Cache_Punktacja_Autora`
>   i `Cache_Punktacja_Dyscypliny` dla tego `rekord_id`;
> - `post_restore` → przelicz je z powrotem (maszyneria istnieje —
>   `src/bpp/models/sloty/core.py`).
>
> Wybrane zamiast „filtrować przy odczycie", bo nie wymaga tknięcia ~10 miejsc
> odczytu ani pilnowania każdego nowego. Koszt: restore staje się operacją
> liczącą (nie samym `UPDATE`), co trzeba uwzględnić w adminie (może trwać).

**Through-modele `*_Autor` (89 miejsc produkcyjnych).** Po wpięciu `SoftDeleteModel`
89 bezpośrednich, produkcyjnych zapytań `*_Autor.objects` (głównie `ewaluacja_optymalizacja`:
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
"wydawnictwo_nadrzedne")`).

> **DECYZJA: PROTECT — soft-delete książki-matki jest ZABLOKOWANY, jeśli ma
> rozdziały.** Ten sam dwuwarstwowy wzorzec co guard autora (§3):
> - **warstwa 1:** flip FK `wydawnictwo_nadrzedne` `CASCADE→PROTECT`
>   (obrona przed hard-delete; migracja state-only),
> - **warstwa 2:** guard w soft-`delete()` `Wydawnictwo_Zwarte` — jeśli rekord
>   ma rozdziały (dzieci `wydawnictwo_nadrzedne`), odmów z czytelnym
>   komunikatem; operator najpierw usuwa/przenosi rozdziały.
>
> Liczenie rozdziałów: przez `global_objects` (także soft-deletowane
> rozdziały blokują — spójnie z guardem autora §3.2). Dzięki PROTECT problem
> „rozdziały wskazujące na skasowaną książkę" w ogóle nie powstaje, a denorm
> `depend_on_related("self", ...)` nie jest wyzwalany kaskadą (rodzic nie
> może być skasowany, póki ma dzieci).

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

## 4. PBN — wycofanie oświadczeń (kolejka + ścieżka synchroniczna)

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

### 4.2 Mechanizm — jeden prymityw, DWA wejścia (decyzja #16)

⚠️ **Zmiana 2026-08-06.** Poprzednia wersja zakładała jedno wejście
(`pbn_export_queue`). Rekord może jednak trafić do PBN **synchronicznie, bez
kolejki** (`synchronizuj_publikacje`, `src/pbn_integrator/utils/synchronization.py:180`,
wołane m.in. z `pbn_uploader` / `pbn_integrator`), a od czasu pisania specu
doszła aplikacja `src/pbn_wysylka_oswiadczen/`, która już woła
`delete_all_publication_statements` (`tasks.py:68`) z dopracowaną obsługą
wyjątków PBN. Wycofanie musi więc działać w obu trybach.

**Architektura: wspólna funkcja-prymityw + dwa wywołujące ją wejścia.**

1. **Prymityw** (nowy, jedno miejsce prawdy) — np.
   `wycofaj_oswiadczenia(publikacja, client) -> wynik`:
   - gate na `pbn_uid` (brak → no-op, jawnie zaraportowany),
   - `client.delete_all_publication_statements(pbn_uid)`,
   - obsługa `CannotDeleteStatementsException` (brak oświadczeń = sukces,
     nie błąd), `PraceSerwisoweException`, `HttpException` — wzorzec
     do przejęcia z `pbn_wysylka_oswiadczen/tasks.py:54-76`,
   - aktualizacja `SentData` (§4.2b) — zawsze, niezależnie od wejścia.
2. **Wejście asynchroniczne** — `pbn_export_queue` rozszerzona o pole
   `operacja: TextChoices(WYSYLKA, WYCOFANIE)` (default `WYSYLKA` dla
   kompatybilności wstecznej). Gałąź w `send_to_pbn()`
   (`src/pbn_export_queue/models.py:456`): `WYCOFANIE` → prymityw. Status
   zapisywany jak dla wysyłki (`zakonczono_pomyslnie`, `komunikat`,
   `ilosc_prob`). To jest **ścieżka domyślna** dla soft-delete z admina —
   ma retry, locking i `UniqueConstraint` na jednym aktywnym wpisie na rekord.
3. **Wejście synchroniczne** — kod, który wysyła rekord bez kolejki, woła
   prymityw bezpośrednio. Nie kolejkuje, nie ma retry; odpowiada za obsługę
   wyniku na miejscu.

> **Niezmiennik:** żadne z wejść nie woła `delete_all_publication_statements`
> samodzielnie — wyłącznie przez prymityw. Inaczej aktualizacja `SentData`
> i wpis w `SoftDeleteLog` rozjadą się między ścieżkami.

⚠️ **`PBN_Export_Queue.zamowil` jest NOT NULL (`on_delete=CASCADE`).**
Zakolejkowanie z admina ma `request.user`. Ale zakolejkowanie inicjowane
sygnałem przy soft-delete bez usera (operacje programistyczne / celery) nie ma
kogo wpisać. Rozwiązanie (faza 05/06): **konto techniczne** (np.
`get_or_create` systemowego użytkownika) jako `zamowil` dla operacji
systemowych — NIE robić `zamowil` nullable (psułoby istniejące zał. kolejki).

### 4.2b `SentData` — stan PBN per-rekord

`SentData` (`src/pbn_api/models/sentdata.py`, GFK + `pbn_uid` +
`submitted_successfully` + `mark_as_successful`/`mark_as_failed`) trzyma stan
PBN per-rekord. **Po udanym wycofaniu:** ustawiamy `submitted_successfully =
False` (rekord nie jest już „wystawiony" w PBN) i dodajemy znacznik wycofania
(np. `withdrawn_at` — nowe pole, lub `api_response_status`); **wiersza
`SentData` NIE kasujemy** — zostaje dla audytu i re-matchingu przy restore.
Restore (`WYSYLKA`) → ponowne `mark_as_successful` po udanej wysyłce.

Aktualizację `SentData` robi **prymityw** (§4.2 pkt 1), nie wywołujący — dzięki
temu ścieżka asynchroniczna i synchroniczna zostawiają identyczny stan.

### 4.3 Restore → symetria

Restore publikacji → ponowna wysyłka oświadczeń (dyscypliny wracają do
profilu instytucji), tym samym dwuwejściowym wzorcem co wycofanie: domyślnie
wpis `WYSYLKA` w `pbn_export_queue`, a w kontekście synchronicznym —
bezpośrednio. Symetria delete↔restore.

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

1. **`*_Autor` + widoki + funkcje triggera + bramka** — kolejność wewnątrz
   fazy jest wymuszona zależnościami (§2.1):
   (a) migracja `SoftDeleteModel` na 3 through-modelach (`deleted_at`+indeks) —
   **musi być PRZED** (b), bo widok czyta tę kolumnę;
   (b) filtr `deleted_at IS NULL` w widokach źródłowych `bpp_*_autorzy`
   (po własnej kolumnie, bez JOIN);
   (c) **gałąź kasująca** w funkcjach refresh (`IF NEW.deleted_at IS NOT NULL
   THEN DELETE ... RETURN NULL`) — **obowiązkowa**, nie optymalizacja;
   (d) **regeneracja bramki `WHEN`** (logika `forward()` z `0433`) — musi być
   PO (b), żeby `pg_depend` już znało `deleted_at`.
   Weryfikacja: odwrócenie asercji w
   `src/bpp/tests/test_cache/test_soft_delete_preconditions.py` + testy
   spójności surowym SQL-em. **Najwrażliwsze, pierwsze.**
2. **Publikacje** — `SoftDeleteModel` na 5 modelach, override
   `delete()`/`restore()` z **wąską kaskadą na `*_Autor`** (wspólny
   `transaction_id`, bez refleksyjnej kaskady pakietu), migracje
   (`deleted_at`+indeks, ew. `CONCURRENTLY`), `slug` `UniqueConstraint`,
   warunkowe `UniqueConstraint` na `*_Autor` (§2.2b), przeplecenie menedżerów,
   powtórzenie kroków 1(b)–1(d) dla 5 widoków publikacji i ich funkcji.
3. **Audyt kat. B** — przełączenie import/dedup/PBN-matching na
   `global_objects`; audyt 89 miejsc produkcyjnych `*_Autor.objects` (146 wystąpień łącznie, 57 w testach) (default „pomijaj"
   poprawny, wyjątki → `global_objects`). Testy: re-import nie tworzy
   duplikatów; ewaluacja pomija prace w koszu.
4. **Guardy PROTECT** (ten sam wzorzec: flip FK + guard liczący przez
   `global_objects`):
   - **Autor** — flip FK `CASCADE→PROTECT` (`*_Autor`, doktorat), guard w soft
     `delete()` (widzi kaskadowo-skasowane autorstwa), soft-delete husku;
     weryfikacja merge.
   - **`Wydawnictwo_Zwarte` (rozdziały)** — flip FK `wydawnictwo_nadrzedne`
     `CASCADE→PROTECT`, guard w soft `delete()` blokujący gdy ma rozdziały
     (§2.6).
5. **PBN** — prymityw `wycofaj_oswiadczenia()` + dwa wejścia: `operacja
   WYCOFANIE` w `pbn_export_queue` (async) i wywołanie bezpośrednie
   (synchroniczne); restore→`WYSYLKA`; integracja `SentData` (§4.2).
6. **SoftDeleteLog** + receivery sygnałów (`post_soft_delete`/`post_restore`/
   `post_hard_delete`), wstrzykiwanie `user`, **kasowanie/przeliczanie
   `Cache_Punktacja_*`** (§2.5b).
7. **Admin** — kosz / filtr / przywróć / usuń-trwale / powód (5 modeli +
   `Autor`).
8. **Testy regresji** — pełna suita: PBN (duplikaty + wycofanie), dashboard,
   import, ewaluacja, merge autorów, API. Do ~10 min.

---

## 9. Ryzyka

- **Cache/trigger** — rozjazd, jeśli `deleted_at` nie obsłużone we wszystkich
  8 tabelach (5 publikacji + 3 `*_autor`) × trzech elementach (widok, gałąź
  kasująca, bramka `WHEN`). Najgroźniejsze, wydajnościowo wrażliwe.
  Mitygacja: kanarki `test_soft_delete_preconditions.py` odwrócone na
  docelowe asercje jako PIERWSZY krok fazy 01.
- **Bramka `WHEN` zapomniana przy kolejnej zmianie widoku** — bramka jest
  wypiekana w migracji z `pg_depend`, więc **każda przyszła zmiana definicji
  widoku źródłowego wymaga jej regeneracji**. Pominięcie = cichy staleness
  (rekord w koszu widoczny dalej). Mitygacja: kanarki + nota w
  `docs/deweloper/spec-bpp-refresh-cache-plpgsql-2026-06.md`.
- **`Cache_Punktacja_*` nietknięte przy soft-delete** — praca w koszu nadal
  liczy się do ewaluacji (§2.5b). Osobny kanał, którego kaskada `*_Autor`
  NIE zamyka.
- **Restore staje się operacją liczącą** — przeliczenie `Cache_Punktacja_*`
  (§2.5b) może trwać; admin musi to znieść (komunikat / zadanie w tle).
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
   do rodzica). Powód kaskady: 89 miejsc produkcyjnych `*_Autor.objects` w ewaluacji.
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
9. ~~**Cache — mechanizm nadrzędny:** filtr `deleted_at IS NULL` w widokach
   źródłowych; trigger-skip to opcjonalna optymalizacja.~~
   **UNIEWAŻNIONE 2026-08-06.** Zastąpione przez: **cztery elementy, wszystkie
   obowiązkowe** — (a) filtr w widoku źródłowym, (b) gałąź kasująca w
   funkcji refresh, (c) regeneracja bramki `WHEN`, (d) widoki i agregaty
   POCHODNE (dopisany po finalnej recenzji fazy 01 — patrz §2.1 punkt 4).
   Żaden nie wystarcza sam (§2.1).
10. **SentData przy wycofaniu:** `submitted_successfully=False` + znacznik
    wycofania, wiersza nie kasujemy.
11. **Self-FK `Wydawnictwo_Zwarte` (rozdziały):** **PROTECT** — soft-delete
    książki-matki zablokowany, jeśli ma rozdziały (flip FK `CASCADE→PROTECT`
    + guard liczący przez `global_objects`, §2.6). Wzorzec jak guard autora.

### Decyzje domknięte 2026-08-06 (po weryfikacji na `dev`)

12. **`full_refresh()` pomija skasowane** — `denorm.rebuildall` iteruje po
    domyślnym managerze. Świadomie akceptowane (przebudowa opisów
    bibliograficznych rekordu w koszu jest bez wartości). NIE używamy
    `full_refresh()` jako weryfikacji spójności soft-delete (§2.1).
13. **`unique_together` na `*_Autor` → warunkowy `UniqueConstraint`**
    z `condition=Q(deleted_at__isnull=True)`, spójnie ze slugiem (§2.2b).
14. **Import trafiający w kosz: POMIŃ + ZARAPORTUJ.** Nie tykamy rekordu
    w koszu; trafienie idzie do raportu importu jako osobna kategoria.
    Nie auto-restore, nie nowy rekord (§2.5).
15. **`Cache_Punktacja_*`: kasować przy soft-delete, przeliczać przy restore.**
    Zamiast filtrowania w ~10 miejscach odczytu (§2.5b).
16. **PBN: jeden prymityw, dwa wejścia** — asynchroniczne przez
    `pbn_export_queue` (`operacja=WYCOFANIE`, ścieżka domyślna) i
    synchroniczne wywołanie bezpośrednie, bo rekord bywa wysyłany bez kolejki.
    Żadne wejście nie woła `delete_all_publication_statements` samodzielnie
    (§4.2).

---

## 11. Precedensy w repo

- `django-soft-delete>=1.0.23` — `pyproject.toml`.
- `src/zglos_publikacje/models.py:60` — `Zgłoszenie_Publikacji` już
  `SoftDeleteModel` (wzorzec).
- `src/bpp/models/repozytorium.py:18` — `Element_Repozytorium` też jest
  `SoftDeleteModel` (drugi precedens, wykryty przy wykonaniu fazy 01).
  Model bez własnych managerów — przydatny w testach jako gotowy nośnik
  kolumn `deleted_at`/`restored_at`.
- ⚠️ `src/zglos_publikacje/models.py:315` — `Zgloszenie_Publikacji_Autor`
  dziedziczy po `BazaModeluOdpowiedzialnosciAutorow`, ale jest **POZA
  zakresem** soft-delete. Dlatego `SoftDeleteModel` wpinamy w 3 konkretne
  through-modele, NIE w abstrakt (§2.2).
- `src/pbn_export_queue/` — dojrzała kolejka PBN (model + Celery + admin +
  retry/lock), wzorzec dla operacji `WYCOFANIE` (wejście asynchroniczne).
- `src/pbn_wysylka_oswiadczen/tasks.py:54-76` — wzorcowa obsługa wyjątków PBN
  przy `delete_all_publication_statements` (`CannotDeleteStatementsException`
  = brak oświadczeń = sukces, nie błąd). Do przejęcia przez prymityw §4.2.
- `src/pbn_api/models/sentdata.py` — `SentData` (stan PBN per-rekord).
- `src/bpp/models/oplaty_log.py`, log w `deduplikator_autorow` — precedensy
  tabel-logów.
- `src/bpp/migrations/0432_cache_trigger_plpgsql.py` /
  `0433_cache_trigger_when_gate.py` — generatory funkcji triggera i bramki.
  **Faza 01 wprost korzysta z ich logiki**, nie pisze SQL-a od zera.
- `src/bpp/tests/test_cache/test_cache_plpgsql_port.py` — wzorzec testów
  spójności `_mat` surowym SQL-em (porównanie kolumna-po-kolumnie, `ctid`
  do wykrywania jałowych przepisań).
