# Specyfikacja: konsolidacja Wydział → Jednostka (jedno drzewo struktury)

**Data:** 2026-07-02
**Status:** design zaakceptowany (Sekcja 1 + 2), do przeglądu przed planem wdrożenia
**Analiza wykonalności:** `docs/superpowers/specs/2026-07-02-konsolidacja-wydzial-jednostka-analiza.md`

## Cel

Zlikwidować podział na dwa osobne modele `Wydzial` i `Jednostka`. Docelowo
jedna drzewiasta struktura oparta na istniejącym drzewie MPTT `Jednostka`:
na górze `Uczelnia`, poniżej jednostki dowolnie zagnieżdżone. Wydział staje
się jednostką o określonym *rodzaju*, która „pełni rolę wydziału" (jest
poziomem raportowym).

**Nie jest to destrukcyjne usunięcie `Wydzial`**, lecz **konwersja**: każdy
wiersz `Wydzial` staje się wierszem `Jednostka`, a wszystkie pola wskazujące
dotąd na `Wydzial` zostają przepięte na odpowiadającą `Jednostka`. Dane
przeżywają migrację w całości. Model `Wydzial` jest usuwany dopiero na końcu,
gdy nic już go nie referuje.

## Zasady niepodważalne (ustalone z użytkownikiem)

1. **Historia temporalna zostaje w całości.** Jednostki historyczne,
   przypisania `od`/`do`, brak nakładania zakresów — wszystko zachowane.
2. **Rola „wydziału" NIE zależy od pozycji w drzewie.** Uczelnia może mieć
   np. 2 instytuty bezpośrednio pod sobą (nie-wydziały) ORAZ jeden wydział
   skupiający 5 jednostek — wszystkie na tym samym poziomie drzewa. Rola
   wydziału to jawna właściwość rodzaju, nie poziom MPTT.
3. **Trigger bazodanowy znika.** Jego zadania (derywacja bieżącego wskaźnika
   z historii) przejmuje kod w Pythonie, który dodatkowo utrzymuje
   księgowość nested-set MPTT (czego trigger nie robił).

---

## Sekcja 1 — Model danych

### Nowy słownik `RodzajJednostki`

Edytowalny w adminie (per-tenant — różne uczelnie różne nazewnictwo).

```
RodzajJednostki
  nazwa                : CharField          # "Wydział", "Instytut", "Klinika",
                                            #  "Katedra", "Koło naukowe"…
  skrot                : CharField (opc.)
  pelni_role_wydzialu  : BooleanField       # czy ten rodzaj jest poziomem
                                            #  raportowym „wydziałowym"
  kolejnosc            : PositiveIntegerField
```

- Seed migracyjny: dzisiejsze wartości `Jednostka.rodzaj_jednostki`
  (`normalna`, `kolo_naukowe`) stają się dwoma pierwszymi wierszami słownika.
  `Wydział` dochodzi jako trzeci (z `pelni_role_wydzialu=True`).
- `kolo_naukowe` zachowuje swoją dotychczasową specjalną obsługę (metody
  `kola_naukowe()` itp.) — zmienia się tylko nośnik: string → FK.

### Zmiany w `Jednostka`

- `rodzaj` → **FK do `RodzajJednostki`** (zastępuje `rodzaj_jednostki`
  CharField). Migracja mapuje istniejące stringi na wiersze słownika.
- `parent` (MPTT `TreeForeignKey`) → **jedyny nośnik struktury**.
  Dotychczasowe grupowanie „wydziałowe" również realizowane przez drzewo.
- `wydzial` (FK→`Wydzial`) → **repoint na FK→`Jednostka`** i zmiana znaczenia:
  to **zdenormalizowany wskaźnik „wydziału raportowego"** = najbliższego
  przodka w drzewie, którego `rodzaj.pelni_role_wydzialu = True`. Utrzymywany
  w Pythonie (patrz „Utrzymanie spójności"). Pole zachowuje nazwę `wydzial`,
  by zminimalizować zmiany w konsumentach — zmienia się tylko model docelowy.
  (Nazwę pola można później zmienić na `wydzial_raportowy`; na teraz zostaje
  `wydzial` dla mniejszego diffa.)
  - **Semantyka `include_self`:** dla węzła, który SAM pełni rolę wydziału,
    zdenormalizowane `wydzial` wskazuje **na siebie** (żeby raporty grupujące
    „po wydziale" zaliczyły prace afiliowane wprost na węzeł-wydział).
    Dla jednostki bez żadnego wydziałowego przodka (np. instytut wprost pod
    uczelnią) `wydzial = NULL` (jak dziś dla jednostek bez wydziału).
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
  przejmuje Python (niżej).

### Utrzymanie spójności (zamiast triggera)

Jedna ścieżka w Pythonie (save-hook Jednostki / akcja admina / metoda
domenowa), wywoływana przy zmianie `parent` lub wpisu historii:

1. Utrzymuje żywą krawędź MPTT `parent` (django-mptt, `move_to`/`save`).
2. Przelicza zdenormalizowane `wydzial` (najbliższy przodek z
   `pelni_role_wydzialu=True`) **dla węzła i całego jego poddrzewa**.
3. Ustawia `aktualna` na podstawie bieżącego wpisu historii.
4. Dopisuje/rozcina wiersze `Jednostka_Rodzic` (przez istniejący manager).

Decyzja projektowa: **flaga `pelni_role_wydzialu` żyje na TYPIE
(`RodzajJednostki`), nie na pojedynczym węźle.** Override per-węzeł to
świadomie odłożone rozszerzenie (YAGNI).

### Usuwane / przepinane modele

- `Wydzial` — usuwany na końcu (po konwersji danych i przepięciu FK).
- FK dotąd → `Wydzial`, po migracji → `Jednostka`:
  `Kierunek_Studiow.wydzial` (PROTECT), `Patent.wydzial` (SET_NULL),
  `opi_2012`, `Zgloszenie.wydzial` (zglos_publikacje), `import_dyscyplin`,
  `Nowe_Sumy_View.wydzial` (VIEW, managed=False — zmiana definicji SQL),
  `Obslugujacy_Zgloszenia_Wydzialow.wydzial`.

---

## Sekcja 2 — Konsumenci: raporty / UI / API / importy

### Raporty (największy blok) — trik denormalizacji

Dzięki zachowaniu zdenormalizowanego pola `Jednostka.wydzial` (teraz
FK→Jednostka) raporty zmieniają się **niemal mechanicznie**: wyrażenia
`autorzy__jednostka__wydzial=X` / `jednostka__wydzial__…` zostają, zmienia
się tylko to, że `X` jest teraz `Jednostka` (węzeł-wydział), nie `Wydzial`.

Podsystemy do przejścia i weryfikacji testami:
- `nowe_raporty` — `POZIOM_WYDZIAL`, `prace_wydzialu`, seeding definicji
  (`poziomy.py`, `models.py:14`, `seeding/definicje.py`).
- `ranking_autorow` — `RankingAutorowJednostkaWydzialTable`,
  `rozbij_na_wydzialy`, `WydzialChoiceField` (`views.py`, `forms.py`).
- `raport_slotow` — `dziel_na_jednostki_i_wydzialy`, warianty tabel/filtrów.
- `ewaluacja_metryki` — filtr `jednostka__wydzial_id`, kolumna XLSX.
- Manager cache: `Rekord.prace_wydzialu` (`cache/rekord.py:96`).

### Admin

- `WydzialAdmin`, `WydzialInline` w adminie Uczelni → zastąpione zarządzaniem
  jednostek-wydziałów w `DraggableMPTTAdmin` Jednostki (drzewo).
- Kolumny/filtry `wydzial` w adminach jednostki/patentu/kierunku/doktoratu/
  autora → wskazują `Jednostka`.
- `RodzajJednostki` → własny prosty admin słownikowy.
- Nowy admin słownika + inline zarządzania rodzajem na Jednostce.

### Browse / URL / sitemap

- `WydzialView` + `browse/wydzial.html` → węzeł z `pelni_role_wydzialu`
  renderuje „widok wydziałowy" (aktualne jednostki / koła / historyczne —
  logika zostaje, oparta na drzewie i `Jednostka_Rodzic`).
- Stary URL `bpp:browse_wydzial` → **redirect 301** na `bpp:browse_jednostka`
  (zachowanie SEO, brak martwych linków, sitemap zaktualizowany).
- `WydzialSitemap` → scalony z `JednostkaSitemap` (lub filtr po rodzaju).
- Autocomplety `WydzialAutocomplete`/`PublicWydzialAutocomplete` → wariant
  autocomplete jednostek filtrowany po `rodzaj.pelni_role_wydzialu`.

### API (kontrakt — deprecation, nie usunięcie)

- `WydzialViewSet` (`/api/v1/wydzial/`) + `WydzialSerializer` → oznaczone jako
  **deprecated**, utrzymywane przez okres przejściowy (mogą serwować jednostki
  z rodzajem-wydziałem, by nie zerwać konsumentów zewnętrznych).
- Pola `wydzial` w serializerach jednostki/patentu → wskazują zasób
  `Jednostka`.

### Multiseek / wyszukiwarka / djangoql

- `WydzialQueryObject`, `PierwszyWydzialQueryObject`
  (`multiseek_registry/fields/unit_fields.py`) → operują na `Jednostka`
  z rodzajem-wydziałem; filtry `get_family()` już działają na drzewie.
- `djangoql_schema` — bez zmian koncepcyjnych (już używa drzewa).

### Importy / PBN / management commands

- `matchuj_wydzial` (`import_common`), `wydzial_domyslny` w `pbn_import`
  (`institution_import.py`, `pbn_import.py`) → operują na `Jednostka`
  z rodzajem-wydziałem; tworzą wpisy `Jednostka_Rodzic`.
- `import_jednostki_ipis`, `import_pracownikow`, `mapuj_kierunki_studiow`,
  `rebuild_slugs`, `create_demo_data`, generatory demo (`wydzialy.py`,
  `jednostki.py`) → dostosowane.

### Flaga `uzywaj_wydzialow` / `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW`

Znaczenie zmienia się z „czy istnieją wydziały" na „czy drzewo ma węzły
pełniące rolę wydziału / czy pokazywać poziom wydziałowy". Rozproszone
użycia (menu, browse, ranking, ewaluacja, pbn_import, template uczelni) →
przemapowane na nowe znaczenie.

---

## Plan migracji danych (konwersja, idempotentna, multi-tenant)

Kolejność (każdy krok osobno testowalny; strangler):

1. **Dodać `RodzajJednostki` + seed** (`normalna`, `kolo_naukowe`, `Wydział`).
   `Jednostka.rodzaj` FK, zmapować istniejące stringi. `Wydzial` nietknięty.
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
5. **Przeliczenie denormalizacji** `Jednostka.wydzial` (self-FK) + `aktualna`
   dla całego drzewa (jednorazowy backfill Pythonem).
6. **Usunięcie triggera** i przełączenie utrzymania na Python.
7. **`Nowe_Sumy_View`** — nowa definicja SQL (VIEW) na bazie `Jednostka`.
8. **Migracja konsumentów-raportów/UI/API** (Sekcja 2), po jednym obszarze,
   z testami i weryfikacją na danych.
9. **Drop `Wydzial`** — dopiero gdy nic go nie referuje.
10. **Rebuild cache** (`Rekord`/`Autorzy`/`punktacja`) + `rebuild_jednostka` +
    MPTT `rebuild()`.
11. **Baseline** — `make baseline-update` RAZ, przy scalaniu (nie w
    równoległych branchach).

---

## Ryzyka i strategie

- **Multi-tenant:** migracja idempotentna, odporna na uczelnie bez wydziałów,
  z historią temporalną i kolizjami nazw/skrótów. Główne źródło ryzyka.
- **MPTT nested-set:** utrzymanie `parent` MUSI iść przez Python (mptt), nie
  surowy SQL — inaczej `get_descendants()`/`get_family()` (podstawa raportów)
  zwracają śmieci do `rebuild()`.
- **Denormalizacja `wydzial`:** przeliczana dla węzła i CAŁEGO poddrzewa przy
  każdym przesunięciu — koszt zapisu, ale trywialne raporty. Świadomy trade.
- **Kontrakt API:** deprecation zamiast twardego usunięcia
  `/api/v1/wydzial/`.
- **PROTECT na `Kierunek_Studiow.wydzial`:** przepiąć przed jakimkolwiek
  kasowaniem, inaczej migracja się wywali.
- **Baseline churn / cache rebuild:** duża migracja; robić baseline raz,
  przebudować cache po konwersji.
- **~68 historycznych migracji** referuje `Wydzial` — nietykane; model musi
  pozostać importowalny do kroku 9 (drop na końcu).

---

## Kryteria sukcesu

1. Jedno drzewo struktury: `Uczelnia → (Jednostka*)`, wydział to jednostka
   z rodzajem `pelni_role_wydzialu=True`, na dowolnym poziomie.
2. Pełna historia temporalna zachowana i widoczna (jednostki historyczne).
3. Raporty (nowe_raporty, ranking_autorow, raport_slotow, ewaluacja_metryki)
   dają wyniki identyczne jak przed migracją na tych samych danych.
4. Stare URL-e wydziałów → 301 na jednostki (brak martwych linków).
5. `/api/v1/wydzial/` działa (deprecated) przez okres przejściowy.
6. Cała suita testów zielona; baseline odświeżony.
7. Migracja idempotentna i przetestowana na ≥1 realnym dumpie multi-tenant.

## Świadomie odłożone (YAGNI)

- Override `pelni_role_wydzialu` per-węzeł (na teraz tylko per-rodzaj).
- Zmiana nazwy pola `Jednostka.wydzial` → `wydzial_raportowy` (osobny,
  kosmetyczny refaktor po ustabilizowaniu).
- Twarde usunięcie API `/wydzial/` (dopiero po okresie deprecation).
