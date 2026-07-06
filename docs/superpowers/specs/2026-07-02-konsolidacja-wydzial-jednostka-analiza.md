# Analiza: konsolidacja Wydział → Jednostka (jedno drzewo struktury)

**Data:** 2026-07-02
**Status:** analiza wykonalności (NIE plan wdrożenia — decyzje otwarte)

## Pomysł użytkownika

Zlikwidować podział na osobne tabele `Wydzial` i `Jednostka`. Zamiast tego
jedna drzewiasta struktura: na górze uczelnia (lub federacja), niżej
jednostki. Kto używa wydziałów — dostaje drzewo `Uczelnia → Wydział →
Jednostka`. Kto nie — płaskie `Uczelnia → Jednostka`. Praktycznie: wpiąć
zawartość tabeli `Wydzial` jako najwyższy poziom drzewa `Jednostka`.

---

## TL;DR — werdykt

**Wykonalne i mniej ryzykowne niż wygląda — bo połowa infrastruktury już
istnieje.** `Jednostka` jest już modelem drzewiastym (MPTT, pole `parent`),
a to drzewo jest realnie używane w wyszukiwarce i cache raportów. Wydział ma
zaskakująco mało twardych zależności schematu (8 bezpośrednich FK), a w
raportach jest w większości **derywowany joinem** `jednostka__wydzial`, a nie
zdenormalizowany w ciężkich tabelach cache.

- **Trudność:** ŚREDNIA, a po korekcie sekcji B — bliżej ŚREDNIO-NISKIEJ.
  Nie ma zabójcy. „Trudny" pod-problem historii temporalnej okazał się TANI:
  maszyneria (tabela historii `od/do` + trigger derywujący bieżącą wartość +
  constraint GiST na nienakładanie) już istnieje i uogólnia się przez repoint
  `wydzial → parent`. Dominującym kosztem jest mechaniczne przepisanie
  konsumentów-raportów.
- **Szybkość:** przy podejściu fazowym (rekomendowane) ~4–6 tygodni pracy
  rozłożonej bezpiecznie; „na hurra" ~2–3 tygodnie kodu + tygodnie
  stabilizacji na produkcji.
- **Bezpieczeństwo:** akceptowalne PRZY podejściu fazowym (strangler).
  Big-bang jest niebezpieczny ze względu na multi-tenant i nieodwracalność.

---

## Co już jest (punkt wyjścia)

1. **`Jednostka` to już drzewo.** `class Jednostka(... MPTTModel)`,
   `parent = TreeForeignKey("self", ...)` (`src/bpp/models/jednostka.py:80-88`).
   Drzewo jest AKTYWNIE używane:
   - `djangoql_schema.py:120,134` — filtr `get_family()`
   - `multiseek_registry/fields/unit_fields.py:58,138,176` — filtry po rodzinie
   - `cache/rekord.py:81,89` — `prace_jednostki` przez
     `get_descendants(include_self=True)`
   - admin to już `DraggableMPTTAdmin` (`admin/jednostka.py:47`)

2. **Wydział słabo wpięty w schemat.** Tylko 8 bezpośrednich FK:
   | Model | on_delete | uwaga |
   |---|---|---|
   | `Jednostka.wydzial` | CASCADE, null | centralny, ale nullable |
   | `Jednostka_Wydzial.wydzial` | CASCADE | model temporalny (od/do) |
   | `Kierunek_Studiow.wydzial` | **PROTECT** | blokuje kasowanie wydziału |
   | `Patent.wydzial` | SET_NULL | |
   | `opi_2012` | CASCADE | legacy eksport |
   | `Nowe_Sumy_View.wydzial` | DO_NOTHING | VIEW, managed=False |
   | `Zgloszenie.wydzial` | CASCADE | zglos_publikacje |
   | `import_dyscyplin` | SET_NULL | |

3. **Cache nie trzyma zdenormalizowanego wydziału (poza jednym VIEW).**
   `Rekord` sięga wydziału wyłącznie joinem `autorzy__jednostka__wydzial`
   (`cache/rekord.py:98,101,271`). Jedyna twarda denormalizacja to
   `Nowe_Sumy_View.wydzial` — ale to VIEW (`managed=False`), więc „migruje
   się" go zmianą definicji SQL, nie migracją danych. Plus miękka zależność
   cachetools `@depend_on_related(..., "wydzial_id")` w
   `praca_doktorska.py:76`.

4. **Wydziały są już opcjonalne na poziomie prezentacji.** Flaga
   `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW` + `Uczelnia.uzywaj_wydzialow`
   (16+ użyć: menu, browse, multiseek, ranking, ewaluacja). Uczelnie mogą
   już dziś działać „bez wydziałów" wizualnie.

---

## Sedno problemu — trzy realne decyzje projektowe

### A. Jak odróżnić „ta jednostka JEST wydziałem"?
`rodzaj_jednostki` ma dziś `normalna` / `kolo_naukowe`. Opcje:
- dodać `WYDZIAL` do `rodzaj_jednostki`, albo
- wnioskować z poziomu MPTT (`level == 0`/`1` pod uczelnią).

Rekomendacja: jawny typ (`rodzaj_jednostki=WYDZIAL`) — poziom MPTT jest
kruchy przy federacjach i zmianach głębokości.

### B. Co z historią temporalną? (KOREKTA — mniejszy problem niż sądzono)

**Uwaga usera (trafna):** samo drzewo MPTT może przecież nieść historię
przypisań do jednostki-wyższego-szczebla `od`/`do`. I dokładnie tak jest —
kod DOWODZI, że ta maszyneria już istnieje i jest gotowa do uogólnienia.

Dziś architektura wygląda tak:
- **Tabela historii** `Jednostka_Wydzial(jednostka, wydzial, od, do)` = źródło
  prawdy o przypisaniu w czasie (manager rozcinający zakresy —
  `jednostka.py:320-491`, suita `test_jednostka_wydzial_jednostka.py`).
- **Zdenormalizowany wskaźnik „bieżący"** `Jednostka.wydzial` +
  `Jednostka.aktualna` — wypełniany **triggerem bazodanowym**
  `bpp_jednostka_ustaw_wydzial_aktualna` (`migrations/0056_*.sql`), który po
  każdym INSERT/UPDATE/DELETE wiersza historii wybiera rekord o najpóźniejszym
  `od` i przepisuje bieżący wydział + flagę `aktualna`.
- **Constraint GiST** `unikalny_zakres_dat_dla_jednostki` (btree_gist +
  `daterange ... EXCLUDE`) — baza gwarantuje brak nakładających się zakresów
  per jednostka. Plus `bez_dat_do_w_przyszlosci`.

Czyli wzorzec „tabela historii `od/do` + trigger derywujący bieżącą wartość +
constraint na nienakładanie" **jest już w produkcji**. Uogólnienie do drzewa
to **repoint**, nie przepisanie: `Jednostka_Wydzial.wydzial` (FK→Wydzial)
staje się `Jednostka_Rodzic.parent` (FK→Jednostka self). Manager, testy,
trigger i constraint przenoszą się niemal 1:1 (logika interwałów dat jest
generyczna, nie ma nic wydział-specyficznego poza nazwą pola i checkiem
`uczelnia_id`, który naturalnie staje się „uczelnia rodzica == uczelnia
dziecka").

Zostają więc już tylko dwie drogi, obie tanie:
- **B1:** porzucić historię — `parent` zastępuje `wydzial`, tabela historii
  znika. Regres funkcji, ale prosto.
- **B2 (teraz TANIE):** uogólnić istniejącą tabelę historii do self-parent.
  Zachowuje pełną zdolność point-in-time, reużywa gotowy trigger+constraint.

**Jedyny realny haczyk B2 — księgowość nested-set MPTT.** Dziś trigger
pisze `wydzial_id` jako zwykły FK (tanio, bez struktur pobocznych). Ale MPTT
utrzymuje dodatkowo kolumny `lft`/`rght`/`tree_id`/`level`, które kodują całe
drzewo — i robi to **django-mptt w Pythonie na `.save()`/`.move_to()`, NIE w
SQL**. Gdyby trigger przestawiał `parent_id` „za plecami" MPTT,
`get_descendants()`/`get_family()` (na których stoją raporty!) zwracałyby
błędne wyniki do czasu `Jednostka.objects.rebuild()`. Stąd wybór:
- **(i)** `parent` (bieżący, MPTT) utrzymywany po stronie Pythona jak dziś;
  tabela `Jednostka_Rodzic(od, do)` służy WYŁĄCZNIE do zapytań point-in-time
  (`wydzial_dnia` → chodzenie po wierszach historii). To najbliższe dzisiejszej
  semantyce i omija problem MPTT w całości. **Rekomendowane.**
- **(ii)** trzymać „bieżący parent" w MPTT derywowany z historii — wtedy każdy
  flip temporalny musi iść przez MPTT-aware `move_to()`/`rebuild()`, a nie
  surowy SQL UPDATE.

**Subtelność projektowa (nie blokująca):** dziś „który wydział" i „która
jednostka nadrzędna" to DWIE ORTOGONALNE osie (`wydzial` FK vs `parent` MPTT
— sub-jednostki katedra→zakład). Twój pomysł SCALA je w jedną: wydział to po
prostu „przodek najwyższego poziomu". Wtedy point-in-time „w jakim wydziale
była ta jednostka dnia X" przy dowolnej głębokości drzewa = rekurencyjne
wejście po łańcuchu temporalnych rodziców do węzła typu WYDZIAL — trochę
więcej kodu w zapytaniu niż dzisiejszy jednopoziomowy `wydzial_dnia`, ale
**składowanie danych jest rozwiązane**.

Wniosek: B2 nie jest już „trudnym pod-problemem". Największym kosztem projektu
staje się mechaniczne przepisanie konsumentów-raportów (sekcja niżej).

### C. Unikalność i URL-e
- `Jednostka.nazwa`/`skrot` są globalnie unique; `Wydzial.nazwa`/`skrot`
  też. Przed migracją trzeba zwalidować kolizje skrótów (np. wydział „WL"
  vs jakaś jednostka). Realne ryzyko na danych produkcyjnych.
- URL-e `browse_wydzial` vs `browse_jednostka` (osobne widoki, sitemap,
  autocomplete). Po scaleniu: albo nowy schemat URL, albo redirecty
  `browse_wydzial → browse_jednostka` (zalecane, bez utraty SEO).
- `Wydzial` ma legacy `pbn_id` (int); `Jednostka` ma `pbn_uid` FK →
  `Institution`. Po scaleniu wydziały zyskują pełne mapowanie PBN (nullable,
  bez regresu).

---

## Zakres pracy — inwentaryzacja warstwy aplikacyjnej

Bulk roboty to NIE schemat, tylko przepisanie konsumentów relacji
`jednostka__wydzial` na „przodek w drzewie":

### Raporty (największy blok, ~4 podsystemy)
- `nowe_raporty` — `POZIOM_WYDZIAL`, `prace_wydzialu`, seeding definicji
  (`poziomy.py:33-81`, `models.py:14`, `seeding/definicje.py`).
- `ranking_autorow` — `RankingAutorowJednostkaWydzialTable`,
  `rozbij_na_wydzialy`, `WydzialChoiceField` (`views.py:140-382`,
  `forms.py:39-312`).
- `raport_slotow` — `dziel_na_jednostki_i_wydzialy`, warianty tabel/filtrów
  (`models/uczelnia.py`, `filters.py`, `tables.py`, `views/uczelnia.py`).
- `ewaluacja_metryki` — filtr `jednostka__wydzial_id`, kolumna XLSX
  (`views/list.py:66-198`, `views/export.py:197-609`).

Każdy z nich zamienia `jednostka__wydzial=X` na
`jednostka__in=X.get_descendants(include_self=True)` — wzorzec już
sprawdzony w `prace_jednostki`. Mechaniczne, ale wymaga testów per raport.

### Admin
`WydzialAdmin`, `WydzialInline` w adminie Uczelni, kolumny/filtry
`wydzial` w adminach jednostki/patentu/kierunku/doktoratu/autora
(`admin/wydzial.py`, `admin/uczelnia.py`, `admin/jednostka.py`,
`admin/kierunek_studiow.py`, `admin/patent.py`), `WydzialResource` (XLSX).

### API
`WydzialViewSet` + `WydzialSerializer`, pola `wydzial` w serializerach
jednostki/patentu (`api_v1/viewsets/struktura.py`,
`api_v1/serializers/struktura.py:23-67`, `serializers/patent.py`).
Uwaga: zmiana kontraktu API — konsumenci zewnętrzni mogą polegać na
`/api/v1/wydzial/`. Trzeba deprecation, nie twarde usunięcie.

### Szablony / nawigacja
`browse/wydzial.html`, sekcja „Wybierz wydział" na stronie głównej
(`browse/uczelnia.html:391-472`), `WydzialView`, sitemap `WydzialSitemap`,
autocomplety `WydzialAutocomplete`/`PublicWydzialAutocomplete`.

### Importy / PBN
`matchuj_wydzial` (`import_common`), `wydzial_domyslny` w pbn_import
(`institution_import.py:22-153`, `pbn_import.py:31-77`), `import_pracownikow`,
`import_jednostki_ipis`, `mapuj_kierunki_studiow`.

### Osobny obszar
`Obslugujacy_Zgloszenia_Wydzialow` (`zglos_publikacje/models.py:354-388`) —
routing powiadomień e-mail per wydział. Trzeba przemyśleć osobno.

---

## Dwie strategie

### Strategia 1 — Big bang (NIE rekomendowana)
Jeden release: nowy kształt modelu + migracja danych + przepisanie
wszystkich konsumentów + drop `Wydzial`.
- ➕ szybko „gotowe" na papierze (~2–3 tyg. kodu)
- ➖ ogromny blast radius, jeden monstrualny PR, wielki churn baseline
- ➖ **nieodwracalne** bez backupu (drop tabeli)
- ➖ multi-tenant: migracja musi być odporna na WSZYSTKIE konfiguracje
  uczelni (bez wydziałów / z historią temporalną / z kolizjami skrótów)
- ➖ trudno przetestować wszystkie permutacje raportów naraz

### Strategia 2 — Strangler / fasada (REKOMENDOWANA)
Fazowo, każdy krok osobno testowalny i odwracalny:

1. **Model** — dodać `rodzaj_jednostki=WYDZIAL`, pozwolić by `parent`
   jednostki wskazywał na jednostkę-wydział. `Wydzial` zostaje.
2. **Backfill + sync** — migracja tworząca jednostki-wydziały jako lustro
   istniejących `Wydzial`, utrzymywana w spójności (sygnały) lub `Wydzial`
   staje się proxy/VIEW na drzewo. Walidacja kolizji skrótów TU.
3. **Migracja konsumentów** — raport po raporcie / obszar po obszarze
   przełączać `jednostka__wydzial` → przodek w drzewie. Każdy z testami
   i weryfikacją na danych.
4. **Drop** — gdy wszyscy konsumenci przeniesieni i zweryfikowani, usunąć
   `Wydzial` + lustro. Dopiero teraz nieodwracalny krok, ale na czystym polu.

- ➕ każdy krok mały, testowalny, odwracalny
- ➕ produkcja nie dostaje wielkiego skoku
- ➖ dłużej kalendarzowo (~4–6 tyg.), więcej „podwójnego utrzymania" w trakcie

---

## Ryzyka specyficzne dla BPP

1. **Multi-tenant.** Wdrożone na wielu uczelniach z różnymi danymi.
   Migracja danych musi być idempotentna i odporna na braki wydziałów,
   historię temporalną i kolizje nazw/skrótów. To główne źródło ryzyka.
2. **Baseline.** Zmiany schematu wymagają `make baseline-update` (patrz
   CLAUDE.md). Duża migracja = duży churn; rób baseline RAZ przy scalaniu,
   nie w równoległych branchach.
3. **Rebuild cache.** Po migracji trzeba przebudować `Rekord`/`Autorzy`/
   `punktacja` (`rebuild_jednostka`, cache mat-views).
4. **Historyczne migracje.** ~68 migracji referuje `wydzial`, ~80
   `jednostka` — nie tykamy ich, ale model musi pozostać importowalny do
   końca (dopiero drop na końcu).
5. **Kontrakt API.** `/api/v1/wydzial/` — deprecation, nie twarde usunięcie.
6. **PROTECT na `Kierunek_Studiow.wydzial`** — przepiąć zanim cokolwiek
   kasujemy, inaczej migracja się wywali.

---

## Rekomendacja

Zrobić to — **ale strategią fasadową (2)**, i **najpierw rozstrzygnąć
decyzję B (historia temporalna)**. To jedyna decyzja, która zmienia zakres
z „mechanicznego" na „przepisanie logiki". Reszta to dużo drobnej,
przewidywalnej pracy, którą można pokryć testami krok po kroku.

Kolejność pierwszego kroku (niskie ryzyko, dużo wartości):
1. Ustalić z userem: czy tracimy historię `Jednostka_Wydzial` (B1) czy
   uogólniamy ją do temporalnego drzewa (B2).
2. Skan danych produkcyjnych pod kątem kolizji skrótów wydział/jednostka
   (jednorazowy management command, read-only).
3. Dodać `rodzaj_jednostki=WYDZIAL` + pozwolić `parent` na jednostkę-wydział
   (mała, wsteczna migracja, `Wydzial` nietknięty).

Dopiero potem faza migracji konsumentów.
