# Specyfikacja: konsolidacja Wydział → Jednostka (jedno drzewo struktury)

**Data:** 2026-07-02 (rewizja: 2026-07-04)
**Status:** design zrewidowany 2026-07-04 — do przeglądu przed planem wdrożenia
**Issue:** [#438](https://github.com/iplweb/bpp/issues/438)
**Analiza wykonalności:** `docs/superpowers/specs/2026-07-02-konsolidacja-wydzial-jednostka-analiza.md`

> ## ⚠ Rewizja 2026-07-04 — zabicie pojęcia „wydziału"
>
> Pierwotny design (2026-07-02) utrzymywał pojęcie „poziomu wydziałowego"
> przez flagę `pelni_role_wydzialu` na rodzaju oraz zdenormalizowane pole
> `Jednostka.wydzial` (najbliższy przodek-wydział). **Ta rewizja to usuwa.**
>
> Ustalenie z użytkownikiem: **nie ma żadnego markera wydziału.** Wielu
> klientów ma instalacje bez wydziałów (`Uczelnia → Jednostka → autorzy`) i
> „wydział" nie ma być bytem w kodzie. Struktura to po prostu drzewo; raport
> pozwala wybrać dowolny węzeł i automatycznie bierze jego potomków.
>
> Konsekwencje względem v1:
> - ❌ **znika `pelni_role_wydzialu`** — brak jakiegokolwiek markera roli.
> - ❌ **znika zdenormalizowane `Jednostka.wydzial` (self-FK)** — bez pojęcia
>   wydziału nie ma czego denormalizować; odpada backfill i przeliczanie
>   poddrzewa przy każdym przesunięciu.
> - ✅ **`RodzajJednostki` zostaje**, ale jako czysto opisowy, per-tenant
>   słownik z **behawioralnymi przełącznikami** (np. `wyklucz_z_rankingu_autorow`),
>   a nie z flagą wydziału. „Wydział" staje się zwykłą etykietą-wierszem.
> - ✅ **raporty** = wybór węzła → agregacja poddrzewa; „rozbicie" = sekcja
>   per bezpośrednie dziecko wybranego węzła.

## Cel

Zlikwidować podział na dwa osobne modele `Wydzial` i `Jednostka`. Docelowo
jedna drzewiasta struktura oparta na istniejącym drzewie MPTT `Jednostka`:
na górze `Uczelnia`, poniżej jednostki dowolnie zagnieżdżone. **Nie istnieje
osobne pojęcie „wydziału"** — wydział to była po prostu jednostka o jeden
poziom wyżej; po konsolidacji jest to zwykły węzeł drzewa (opcjonalnie
opatrzony opisową etykietą rodzaju „Wydział").

**Nie jest to destrukcyjne usunięcie `Wydzial`**, lecz **konwersja**: każdy
wiersz `Wydzial` staje się wierszem `Jednostka` (rodzicem swoich dotychczasowych
jednostek), a wszystkie pola wskazujące dotąd na `Wydzial` zostają przepięte na
odpowiadającą `Jednostka`. Dane przeżywają migrację w całości. Model `Wydzial`
jest usuwany dopiero na końcu, gdy nic już go nie referuje.

## Zasady niepodważalne (ustalone z użytkownikiem)

1. **Historia temporalna zostaje w całości.** Jednostki historyczne,
   przypisania `od`/`do`, brak nakładania zakresów — wszystko zachowane.
2. **Nie ma pojęcia „wydziału" w kodzie.** Instalacja bez wydziałów
   (`Uczelnia → Jednostka`) jest w pełni wspierana i niczym się nie różni od
   instalacji „z wydziałami", poza tym, że ta druga ma dodatkowy poziom
   węzłów w drzewie. Żaden marker, flaga ani zdenormalizowane pole nie
   wyróżnia „poziomu wydziałowego".
3. **Trigger bazodanowy znika.** Jego zadanie (derywacja bieżącego wskaźnika
   `aktualna` z historii) przejmuje kod w Pythonie, który dodatkowo utrzymuje
   księgowość nested-set MPTT (czego trigger nie robił).

---

## Sekcja 1 — Model danych

### Strategia scalenia i nazewnictwo (decyzja)

**Absorpcja-in-place, NIE nowa tabela.** Zachowujemy tożsamość dzisiejszego
modelu `Jednostka` (jego PK-e i wszystkie dziesiątki przychodzących FK-ów
zostają nietknięte na poziomie danych). Wiersze `Wydzial` **wmigrowujemy do
tabeli `Jednostka`** z nowymi PK-ami; repointowane są **tylko konsumenci
`Wydzial`** (~8 FK), nie konsumenci `Jednostka`.

Uzasadnienie: `Jednostka` jest referowana ekstremalnie mocno (Autor_Jednostka,
wszystkie *_Autor, cache Autorzy/punktacja, raport_slotow, ewaluacja…),
`Wydzial` słabo (~8). Fizycznie nowa tabela wymuszałaby repoint OBU stron
(przekluczowanie i migracja danych każdego FK) — droga najdroższą stroną.
Kolizja PK (`Wydzial.id=5` vs `Jednostka.id=5`) i tak wymusza jakieś
przekluczowanie; absorpcja-in-place ogranicza je do samych wierszy `Wydzial`.

**Nazwa modelu: zostaje `Jednostka`.** Zostawienie nazwy = zero zmian w setkach
miejsc (importy, API, multiseek, szablony, `Autor_Jednostka`…). Ewentualny
rename na ładniejszą nazwę (np. `JednostkaOrganizacyjna`) to czysto
kosmetyczny, opcjonalny krok na później — poza zakresem tej specyfikacji.

### Nowy słownik `RodzajJednostki`

Osobna tabela, edytowalna w adminie (per-tenant — różne uczelnie różne
nazewnictwo i różne reguły). **Zastępuje** dzisiejszy CharField
`Jednostka.rodzaj_jednostki` (`normalna` / `kolo_naukowe`).

```
RodzajJednostki
  nazwa                      : CharField          # "Standard", "Koło naukowe",
                                                  #  "Wydział", "Instytut", "Katedra"…
  skrot                      : CharField (opc.)
  kolejnosc                  : PositiveIntegerField
  # --- przełączniki behawioralne (rozszerzalne) ---
  wyklucz_z_rankingu_autorow : BooleanField (default False)
  pokazuj_jako_odrebna_sekcje: BooleanField (default False)
```

- **Behawior jest wyłącznie w flagach, nie w nazwie.** Rodzaj „Wydział" nie ma
  żadnego specjalnego kodu — to tylko etykieta. Cały dotychczasowy „specjalny"
  behawior koła naukowego wyraża się przez flagi:
  - `wyklucz_z_rankingu_autorow` — generalizacja dzisiejszego wykluczenia
    kół z rankingu autorów (`ranking_autorow/views.py:250`).
  - `pokazuj_jako_odrebna_sekcje` — generalizacja listowania kół osobną
    sekcją na podstronie przeglądania (`views/browse.py:124`,
    `Wydzial.kola_naukowe()` / `aktualne_jednostki()`).
  - Zbiór flag jest rozszerzalny — kolejne reguły domenowe dokłada się jako
    nowe pola boolowskie, bez migracji danych struktury.
- **Seed migracyjny:** dzisiejsze wartości `Jednostka.rodzaj_jednostki`
  stają się wierszami słownika:
  - `normalna` → **Standard** (wszystkie flagi False),
  - `kolo_naukowe` → **Koło naukowe** (`wyklucz_z_rankingu_autorow=True`,
    `pokazuj_jako_odrebna_sekcje=True`),
  - dochodzi **Wydział** (wszystkie flagi False — czysta etykieta), używany
    przy konwersji wierszy `Wydzial` na węzły.
- **Odmiana (przypadki gramatyczne):** gałąź `feat/odmiana-rodzaj-instytucji`
  **nie tworzy** `RodzajJednostki` (używa odchudzonego `Rzeczownik` z 3
  stałymi uid-ami). Docelowo — wg reconciliation w spec odmiany — źródłem
  lematu dla węzłów struktury stanie się `RodzajJednostki.nazwa` (per-węzeł).
  **Ten branch jest jedynym twórcą `RodzajJednostki`** — brak kolizji migracji.
  Pole `nazwa` projektujemy tak, by później dało się z niego czytać lemat.

### Zmiany w `Jednostka`

- `rodzaj_jednostki` (CharField) → **`rodzaj` FK do `RodzajJednostki`**.
  Migracja mapuje istniejące stringi na wiersze słownika (patrz seed).
  Metody typu `kola_naukowe()` przechodzą na `rodzaj__wyklucz_z_rankingu_autorow`
  / `rodzaj__pokazuj_jako_odrebna_sekcje` (zależnie od intencji miejsca).
- `parent` (self-FK, MPTT) → **jedyny nośnik struktury**. Dotychczasowe
  grupowanie „wydziałowe" realizowane teraz wyłącznie przez drzewo.
  - **DECYZJA: zostajemy przy django-mptt** (0.18.0, nested-set; używany też
    przez `Charakter_Formalny`). Powód: jedyny realny motyw do zmiany
    (konflikt trigger↔nested-set) znika wraz z usunięciem triggera;
    utrzymanie `parent` idzie Pythonowym API mptt (`move_to`/`save`).
  - **Ryzyko przyjęte świadomie:** mptt zwalnia (brak deklarowanego wsparcia
    Django 6.0). Ścieżka wyjścia: **django-treebeard (Materialized Path)**.
    Ten design jest **tree-lib-agnostyczny** (wymaga tylko: potomkowie,
    rodzina, draggable admin), więc późniejsza zmiana biblioteki go nie narusza.
- ❌ **`wydzial` (FK→`Wydzial`) — USUWANE, nie repointowane.** W v1 pole miało
  stać się zdenormalizowanym wskaźnikiem „najbliższego wydziału". Bez pojęcia
  wydziału pole nie ma sensu. Konsumenci (`jednostka__wydzial=X`) przechodzą na
  zapytania po poddrzewie (Sekcja 2).
- `aktualna` (dziś derywowana triggerem) → utrzymywana w Pythonie.
- Pozostałe pola bez zmian (`uczelnia`, `pbn_uid`, `search`, `slug`, …).

### Historia temporalna — `Jednostka_Rodzic`

Uogólnienie istniejącego `Jednostka_Wydzial`:

```
Jednostka_Rodzic  (dawniej Jednostka_Wydzial)
  jednostka : FK(Jednostka, CASCADE)
  parent    : FK(Jednostka, CASCADE)      # dawniej: wydzial → Wydzial
  od        : DateField (null, blank)
  do        : DateField (null, blank)
```

- Manager rozcinający zakresy dat (`Jednostka_Wydzial_Manager`) przenosi się
  1:1 — logika interwałów jest generyczna. Check `uczelnia_id` staje się
  „uczelnia rodzica == uczelnia dziecka".
- Constraint GiST `unikalny_zakres_dat_dla_jednostki` (btree_gist +
  `daterange … EXCLUDE`) — **zostaje**. Plus `bez_dat_do_w_przyszlosci`.
- **Trigger `bpp_jednostka_ustaw_wydzial_aktualna` — usuwany.** Jego robotę
  (już tylko `aktualna` — nie ma `wydzial` do liczenia) przejmuje Python.

### Utrzymanie spójności (zamiast triggera)

Jedna ścieżka w Pythonie (save-hook Jednostki / akcja admina / metoda
domenowa), wywoływana przy zmianie `parent` lub wpisu historii:

1. Utrzymuje żywą krawędź MPTT `parent` (django-mptt, `move_to`/`save`).
2. Ustawia `aktualna` na podstawie bieżącego wpisu historii.
3. Dopisuje/rozcina wiersze `Jednostka_Rodzic` (przez istniejący manager).

**Uproszczenie względem v1:** znika krok „przelicz zdenormalizowane `wydzial`
dla węzła i całego poddrzewa" — przesunięcie węzła nie pociąga już przeliczeń
poddrzewa (poza samą księgowością lft/rght MPTT).

### Usuwane / przepinane modele

- `Wydzial` — usuwany na końcu (po konwersji danych i przepięciu FK).
- FK dotąd → `Wydzial`, po migracji → `Jednostka`:
  `Kierunek_Studiow.wydzial` (PROTECT), `Patent.wydzial` (SET_NULL),
  `opi_2012`, `Zgloszenie.wydzial` (zglos_publikacje), `import_dyscyplin`,
  `Nowe_Sumy_View.wydzial` (VIEW, managed=False — zmiana definicji SQL),
  `Obslugujacy_Zgloszenia_Wydzialow.wydzial`.

---

## Sekcja 2 — Konsumenci: raporty / UI / API / importy

### Raporty (największy blok) — agregacja po poddrzewie

Bez zdenormalizowanego `Jednostka.wydzial` raporty przechodzą z filtra
`autorzy__jednostka__wydzial=X` na **zapytanie po poddrzewie węzła**:

```python
# było:   .filter(autorzy__jednostka__wydzial=wydzial)
# jest:   .filter(autorzy__jednostka__in=
#             node.get_descendants(include_self=True))
```

MPTT realizuje `get_descendants` jako zakres `lft/rght BETWEEN` — jedno
tanie zapytanie zakresowe, bez rekursji. To realny (ale mechaniczny i
jednorodny) refactor 4 podsystemów, nie zdenormalizowany trik z v1.

**Wzorzec „rozbij na wydziały" → „rozbij na bezpośrednie dzieci wybranego
węzła".** Użytkownik wybiera węzeł (domyślnie `Uczelnia`); raport tworzy
sekcję per **bezpośrednie dziecko** (`node.get_children()`), a każda sekcja
agreguje swoje poddrzewo (`child.get_descendants(include_self=True)`):

- klient z wydziałami: wybiera `Uczelnia` → sekcja per wydział (jak dotąd),
- klient płaski: wybiera `Uczelnia` → sekcja per jednostka,
- dowolny węzeł: „rozbij `Wydział Lekarski` na jego katedry".

Jedna mechanika obsługuje wszystkie instalacje bez pojęcia „wydziału".

Podsystemy do przejścia i weryfikacji testami:
- `nowe_raporty` — `POZIOM_WYDZIAL` → „poziom = bezpośrednie dzieci wybranego
  węzła"; `prace_wydzialu` → `prace_poddrzewa` (`poziomy.py`, `models.py:14`,
  `seeding/definicje.py`).
- `ranking_autorow` — `RankingAutorowJednostkaWydzialTable`,
  `rozbij_na_wydzialy` → `rozbij_na_dzieci`, `WydzialChoiceField` →
  picker węzła (`views.py`, `forms.py`). Wykluczenie kół:
  `rodzaj__wyklucz_z_rankingu_autorow=True`.
- `raport_slotow` — `dziel_na_jednostki_i_wydzialy` → dziel po poziomach
  drzewa (węzeł + jego dzieci), warianty tabel/filtrów.
- `ewaluacja_metryki` — filtr `jednostka__wydzial_id` → poddrzewo węzła,
  kolumna XLSX.
- Manager cache: `Rekord.prace_wydzialu` (`cache/rekord.py:96`) →
  `prace_poddrzewa(node)`.

**Kryterium zgodności wyników:** dla instalacji z wydziałami wynik agregacji
poddrzewa węzła-(byłego-wydziału) = ten sam zbiór jednostek co dawniej, więc
liczby są identyczne (kryterium sukcesu #3). Różni się tylko mechanizm
zapytania i to, że „lista wydziałów" to teraz „dzieci wybranego węzła".

### Multiseek / DjangoQL (osobny, nietrywialny blok)

`src/bpp/multiseek_registry/fields/unit_fields.py` — 6 QueryObject-ów.
**Kluczowa obserwacja: mechanika „węzeł + potomne" JUŻ ISTNIEJE** —
`JednostkaQueryObject` ma operator `EQUAL_PLUS_SUB_FEMALE` (=
`Q(autorzy__jednostka__in=value.get_family())`). „Szukaj po wydziale" to więc
po prostu „szukaj po `Jednostka=<węzeł-wydział>` + potomne". Zmiany:

- **`WydzialQueryObject` / `PierwszyWydzialQueryObject` → zwijają się do
  `JednostkaQueryObject`.** Dziś używają zdenormalizowanego
  `Q(autorzy__jednostka__wydzial=value)` (znika). Zamiast osobnego pola:
  wybór jednostki-węzła z operatorem „+ podrzędne". Jeśli nazwane pola
  `wydzial` / `pierwszy_wydzial` mają przetrwać jako **alias-kompat**, ich
  `real_query` przechodzi z równości na
  `Q(autorzy__jednostka__in=value.get_descendants(include_self=True))`,
  a `model`/`url` z `Wydzial`/`public-wydzial-autocomplete` na
  `Jednostka`/`jednostka-autocomplete`.
  - **Niuans `get_family()` vs `get_descendants(include_self=True)`:**
    istniejący „+ podrzędne" liczy `get_family()` (przodkowie + self +
    potomkowie). Dla semantyki „wydział i wszystko pod nim" chcemy
    `get_descendants(include_self=True)` (self + potomkowie, bez przodków).
    Do uzgodnienia przy implementacji — to różnica w wynikach, nie kosmetyka.
- **`RodzajJednostkiQueryObject`** — dziś statyczna 2-wartościowa lista
  (`Jednostka.RODZAJ_JEDNOSTKI.labels`, zahardkodowane NORMALNA/KOLO_NAUKOWE).
  Po zmianie `rodzaj` → FK: **lista dynamiczna** z tabeli `RodzajJednostki`
  (`RodzajJednostki.objects.all()`), zapytanie `autorzy__jednostka__rodzaj=<row>`.

**Kontrakt DjangoQL (osobny haczyk — zapisane/udokumentowane zapytania):**

- `WydzialQueryObject.djangoql_field_name = "autorzy__jednostka__wydzial"`
  oraz wirtualne pole `jednostka_z_podjednostkami__rel` (MPTT `get_family`) i
  `RodzajJednostkiQueryObject.to_djangoql` → `autorzy.jednostka.rodzaj_jednostki`.
- Usunięcie `Jednostka.wydzial` i zmiana `rodzaj_jednostki` (string) → `rodzaj`
  (FK) **łamie zapytania DjangoQL** referujące te nazwy. Wymagane:
  **mapowanie kompat** (wirtualne pole DjangoQL `wydzial` przełożone na
  poddrzewo węzła; `rodzaj_jednostki` → `rodzaj.nazwa`/kod) albo jawne
  zerwanie kontraktu z notką migracyjną. Decyzja: utrzymać alias przez okres
  przejściowy (spójnie z deprecacją API).

**Zapisane wyszukiwania (persystencja):** formularze multiseek są zapisywane
(`BppMultiseekVisibility`, saved searchform — por. migracja 0346). Wiersze z
`field_name="wydzial"`/`"pierwszy_wydzial"` nie znikają same — albo migracja
danych (przepisanie na `jednostka` + operator „+ podrzędne"), albo utrzymanie
aliasu-kompat. **Nie wolno po cichu usunąć QueryObjectu** — zapisane
wyszukiwania przestałyby się deserializować.

### Selektor struktury (UI)

Jeden **picker drzewa** zamiast osobnych autocomplete „wydział" i „jednostka":
użytkownik wybiera dowolny węzeł, a raport/filtr domyślnie obejmuje jego
potomków (mechanika jak w Multiseek wyżej).

### Admin

- `WydzialAdmin`, `WydzialInline` w adminie Uczelni → **usuwane**;
  zarządzanie węzłami idzie przez draggable-drzewo `JednostkaAdmin`
  (`DraggableMPTTAdmin`, już istnieje).
- **Filtrowanie po jednostce nadrzędnej (wymaganie usera):** w `JednostkaAdmin`
  dodać filtr po `parent` — **autocomplete-backed** (lista jednostek bywa
  duża; nie zwykły dropdown FK). Kolumna `parent_nazwa` już jest w
  `list_display`; `wydzial`-owe kolumny/filtry (`wydzial`, `wydzial_skrot`,
  `wydzial__nazwa` w `search_fields`, `list_select_related=["wydzial"]`) →
  usuwane / zastąpione `parent`.
- `rodzaj_jednostki` (CharField) w `list_display`/`list_filter`/`fieldsets`
  → `rodzaj` (FK), filtr po `RodzajJednostki`.
- `RodzajJednostki` → własny prosty admin słownikowy (nazwa, skrót,
  kolejność, flagi behawioralne).

### Browse / URL / sitemap

- `WydzialView` + `browse/wydzial.html` → **znika osobny „widok wydziału"**;
  przeglądanie dowolnego węzła (`JednostkaView`) pokazuje jego dzieci /
  poddrzewo. Sekcja „osobno listowane" (dawne koła) sterowana flagą
  `pokazuj_jako_odrebna_sekcje`.
- Stary URL `bpp:browse_wydzial` → **redirect 301** na `bpp:browse_jednostka`
  (SEO, brak martwych linków, sitemap zaktualizowany).
- `WydzialSitemap` → scalony z `JednostkaSitemap`.
- `WydzialAutocomplete`/`PublicWydzialAutocomplete` → wariant autocomplete
  jednostek (bez filtra po roli — nie ma roli; ewentualnie po rodzaju, jeśli
  konkretne miejsce tego potrzebuje).

### API (kontrakt — deprecation, nie usunięcie)

- `WydzialViewSet` (`/api/v1/wydzial/`) + `WydzialSerializer` → **deprecated**,
  utrzymywane przez okres przejściowy (mogą serwować węzły `Jednostka`
  rodzaju „Wydział", by nie zerwać konsumentów zewnętrznych).
- Pola `wydzial` w serializerach jednostki/patentu → wskazują zasób
  `Jednostka` (rodzic węzła) lub są oznaczone jako deprecated.

### Importy / PBN / management commands

- `matchuj_wydzial` (`import_common`), `wydzial_domyslny` w `pbn_import`
  (`institution_import.py`, `pbn_import.py`) → operują na `Jednostka`
  (węzeł-rodzic); tworzą wpisy `Jednostka_Rodzic`.
- `mapuj_kola_naukowe` → keyuje po `rodzaj` (RodzajJednostki z flagą), nie po
  stringu.
- `import_jednostki_ipis`, `import_pracownikow`, `mapuj_kierunki_studiow`,
  `rebuild_slugs`, `create_demo_data`, generatory demo (`wydzialy.py`,
  `jednostki.py`) → dostosowane (wydział = węzeł-rodzic).

### Flaga `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW`

Znaczenie zmienia się z „czy istnieją wydziały" na **„czy pokazywać dodatkowy
górny poziom drzewa w nawigacji/menu/browse"**. Instalacja płaska
(`Uczelnia → Jednostka`) po prostu nie ma pośrednich węzłów i flaga steruje
tylko prezentacją. Rozproszone użycia (menu, browse, ranking, ewaluacja,
pbn_import, `Jednostka.__str__` — `DJANGO_BPP_SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI`)
→ przemapowane na nowe znaczenie (skrót rodzica zamiast skrótu wydziału).

---

## Plan migracji danych (konwersja, idempotentna, multi-tenant)

Kolejność (każdy krok osobno testowalny; strangler):

1. **Dodać `RodzajJednostki` + seed** (Standard, Koło naukowe z flagami,
   Wydział). `Jednostka.rodzaj` FK, zmapować istniejące stringi. `Wydzial`
   nietknięty.
2. **Konwersja `Wydzial` → `Jednostka`:** dla każdego `Wydzial` utworzyć
   `Jednostka` (rodzaj=Wydział, `uczelnia`, `parent`=null-lub-root, kopiując
   `nazwa`/`skrot`/`opis`/`kolejnosc`/`widoczny`/`pbn_id`…). Zapamiętać
   mapowanie `wydzial_id → jednostka_id`.
   - **Walidacja przed konwersją:** kolizje globalnie-unikalnych `nazwa`/
     `skrot` między wydziałami a jednostkami (read-only skan; rozwiązać
     ręcznie/z sufiksem przed migracją).
3. **Przepięcie struktury:** dla każdej `Jednostka.wydzial=W` ustawić
   `parent = mapowanie[W]`. Skonwertować historię `Jednostka_Wydzial` →
   `Jednostka_Rodzic` (wydzial→jednostka wg mapowania).
4. **Przepięcie FK konsumentów** (`Kierunek_Studiow`, `Patent`, `opi_2012`,
   `Zgloszenie`, `import_dyscyplin`, `Obslugujacy_Zgloszenia_Wydzialow`) →
   każdy wiersz na `mapowanie[wydzial_id]`. Zmiana targetu FK na `Jednostka`.
5. **Usunięcie kolumny `Jednostka.wydzial`** (po przepięciu struktury —
   nikt jej już nie czyta). W v1 tu był backfill denormalizacji; teraz
   to zwykły `RemoveField`.
6. **Backfill `aktualna`** dla całego drzewa + **usunięcie triggera**,
   przełączenie utrzymania na Python.
7. **`Nowe_Sumy_View`** — nowa definicja SQL (VIEW) na bazie `Jednostka`
   (agregacja po poddrzewie / rodzicu, bez kolumny `wydzial`).
8. **Migracja konsumentów-raportów/UI/API** (Sekcja 2), po jednym obszarze,
   z testami i weryfikacją na danych (agregacja poddrzewa = te same liczby).
9. **Drop `Wydzial`** — dopiero gdy nic go nie referuje.
10. **Rebuild cache** (`Rekord`/`Autorzy`/`punktacja`) + `rebuild_jednostka` +
    MPTT `rebuild()`.
11. **Baseline** — `make baseline-update` RAZ, przy scalaniu (nie w
    równoległych branchach).

---

## Ryzyka i strategie

- **Multi-tenant:** migracja idempotentna, odporna na uczelnie bez wydziałów,
  z historią temporalną i kolizjami nazw/skrótów. Główne źródło ryzyka.
- **Refactor raportów jest szerszy niż w v1:** brak zdenormalizowanego
  `wydzial` = każdy raport przechodzi na `get_descendants`. Mechaniczne, ale
  dotyka 4 podsystemów + cache; każdy weryfikowany testem „te same liczby".
- **Wydajność agregacji poddrzewa:** `get_descendants` to zakres lft/rght —
  tani, ale przy dużych raportach zbiorczych warto sprawdzić plany zapytań
  (indeks na lft/rght MPTT ma domyślnie).
- **MPTT nested-set:** utrzymanie `parent` MUSI iść przez Python (mptt), nie
  surowy SQL — inaczej `get_descendants()`/`get_family()` (podstawa raportów)
  zwracają śmieci do `rebuild()`.
- **Kontrakt API:** deprecation zamiast twardego usunięcia `/api/v1/wydzial/`.
- **PROTECT na `Kierunek_Studiow.wydzial`:** przepiąć przed jakimkolwiek
  kasowaniem, inaczej migracja się wywali.
- **Baseline churn / cache rebuild:** duża migracja; robić baseline raz,
  przebudować cache po konwersji.
- **~68 historycznych migracji** referuje `Wydzial` — nietykane; model musi
  pozostać importowalny do kroku 9 (drop na końcu).

---

## Inwentaryzacja `Wydzial` w kodzie (grep 2026-07-04)

Skala przepięcia „`Wydzial` → `Jednostka`" (bez migracji — nietykalne):

| Kategoria | Liczba |
|---|---|
| Pliki produkcyjne `.py` z `Wydzial`/`wydzial` | ~100 |
| Pliki testowe `.py` | ~48 |
| Szablony `.html` z „wydział" | ~15 |
| Twarde FK → `Wydzial` | 7 |

**7 FK do obsłużenia** (`on_delete` → los):

- `Kierunek_Studiow.wydzial` **PROTECT** → Jednostka (przepiąć PRZED kasowaniem).
- `Patent.wydzial` SET_NULL → Jednostka.
- `opi_2012.wydzial` CASCADE → Jednostka.
- `zglos_publikacje…wydzial` CASCADE → Jednostka.
- `import_dyscyplin…wydzial` SET_NULL → Jednostka.
- `Nowe_Sumy_View.wydzial` DO_NOTHING (VIEW) → nowa definicja SQL.
- `Jednostka.wydzial` CASCADE → ❌ USUWANE (denormalizacja, nie repoint).

**Twarde zależności modelu `Wydzial`** (import / `model = Wydzial` /
`sender=Wydzial`) do przepięcia lub usunięcia: `api_v1/serializers/struktura.py`,
`bpp/admin/xlsx_export/resources.py`, `bpp/admin/uczelnia.py` (+ inline),
`bpp/admin/wydzial.py` (+ rejestracja w `admin/__init__.py`),
`bpp/views/browse.py` (`WydzialView`), `bpp/views/autocomplete/simple.py`,
`ranking_autorow/views.py`, `multiseek_registry/fields/unit_fields.py`,
`zglos_publikacje/admin/filters.py`, `models/uczelnia.py`,
`models/jednostka.py` (`__str__`, denorm), `models/wydzial.py`
(cały plik — metody `jednostki()`/`kola_naukowe()`/… przenoszą się na
`Jednostka` lub znikają), `django_bpp/menu.py`, `bpp/urls.py`,
`bpp/jezyk_polski.py`.

Reszta ze ~100 plików to raporty (`ranking_autorow`, `raport_slotow`,
`nowe_raporty`, `ewaluacja_metryki`), importy (`pbn_import`, `egeria_2012`,
`import_dyscyplin`, `mapuj_kierunki_studiow`), demo-data (`generators/wydzialy.py`,
`orchestrator.py`) oraz ~48 plików testowych i ~15 szablonów.

## Kryteria sukcesu

1. Jedno drzewo struktury: `Uczelnia → (Jednostka*)`. **Brak markera
   wydziału** — instalacja płaska i „z wydziałami" różnią się tylko liczbą
   poziomów węzłów.
2. Pełna historia temporalna zachowana i widoczna (jednostki historyczne).
3. Raporty (nowe_raporty, ranking_autorow, raport_slotow, ewaluacja_metryki)
   dają wyniki identyczne jak przed migracją na tych samych danych
   (agregacja poddrzewa węzła-(byłego-wydziału) = ten sam zbiór jednostek).
4. „Rozbij na wydziały" działa jako „rozbij na bezpośrednie dzieci wybranego
   węzła" — dla klienta z wydziałami wynik jak dotąd.
5. Admin jednostki: filtr po jednostce nadrzędnej (`parent`, autocomplete).
6. Stare URL-e wydziałów → 301 na jednostki (brak martwych linków).
7. `/api/v1/wydzial/` działa (deprecated) przez okres przejściowy.
8. **Multiseek/DjangoQL:** zapisane wyszukiwania i zapytania DjangoQL z
   `wydzial`/`pierwszy_wydzial`/`rodzaj_jednostki` działają (alias-kompat na
   poddrzewo/FK) albo są zmigrowane — nic się nie sypie przy deserializacji;
   „szukaj po wydziale" = „Jednostka=X + potomne".
9. `RodzajJednostki` edytowalny per-tenant; koło naukowe = rodzaj z flagą
   `wyklucz_z_rankingu_autorow` (te same wykluczenia z rankingu co dotąd).
10. Cała suita testów zielona; baseline odświeżony.
11. Migracja idempotentna i przetestowana na ≥1 realnym dumpie multi-tenant.

## Świadomie odłożone (YAGNI)

- Zmiana nazwy modelu `Jednostka` → `JednostkaOrganizacyjna` (kosmetyka).
- Twarde usunięcie API `/wydzial/` (dopiero po okresie deprecation).
- Wariant raportu „suma bez double-count przy zagnieżdżeniu" — przy braku
  pojęcia wydziału i agregacji po jawnie wybranym węźle problem znika
  (użytkownik wybiera konkretny węzeł; nie ma automatycznej enumeracji).
- Odmiana `RodzajJednostki.nazwa` — spina się z gałęzią odmiany później
  (ta gałąź tylko przygotowuje pole `nazwa`).
