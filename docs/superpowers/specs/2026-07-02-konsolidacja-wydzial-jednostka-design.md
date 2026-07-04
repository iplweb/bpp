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

> ## ⚠ Aktualizacja 2026-07-04 — po recenzji adwersaryjnej (fable 5)
>
> Czysty subagent zweryfikował spec w kodzie i znalazł błędy, które wywaliłyby
> migrację na produkcji. Wszystkie potwierdzone `grep`-em/lekturą. Rozstrzygnięte
> decyzje projektowe (patrz sekcja „Decyzje z recenzji 2026-07-04" niżej):
> - **Triggery są TRZY, nie jeden** — poza `ustaw_wydzial_aktualna` istnieją
>   `bpp_jednostka_sprawdz_uczelnia_id` (ON `bpp_jednostka`, czyta `wydzial_id`)
>   i `bpp_jednostka_wydzial_sprawdz_uczelnia_id`. Drop kolumny/tabeli bez
>   wcześniejszego DROP-u ich wywala każdy zapis.
> - **`parent` NIE jest martwy** — konwersja ustawia `parent=węzeł` tylko gdy
>   `parent IS NULL` (inaczej demoluje katedra→zakład). `rebuild()` od razu.
> - **Domyślny manager robi `select_related("wydzial")`** — drop kolumny i kod
>   muszą iść w JEDNYM release (strangler „krok osobno" był fikcją).
> - **`aktualna`** dla rootów/instalacji płaskiej = **True** (inaczej znikają
>   z `publiczne()` → formularz zgłoszeń, publiczny autocomplete).
> - **Mapowanie `wydzial_id→jednostka_id` musi być TRWAŁE** (kolumna
>   `Jednostka.legacy_wydzial_id`) — dict nie przeżyje granicy migracji ani
>   idempotencji; zapisane multiseek trzymają PK wydziałów.
> - **Pola per-węzeł z `Wydzial`** (`zezwalaj_na_ranking_autorow`,
>   `otwarcie`/`zamkniecie`) → na `Jednostka` / w historię (flaga rodzaju ich
>   NIE zastępuje).

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
3. **Triggery bazodanowe znikają (jest ich TRZY).** `0056` instaluje, `0440`
   przepisuje na plpgsql trzy obiekty dotykające `wydzial`:
   - `bpp_jednostka_ustaw_wydzial_aktualna` (ON `bpp_jednostka_wydzial`) —
     derywacja `aktualna` (+ dawniej `wydzial`). Zastąpiony Pythonem.
   - `bpp_jednostka_sprawdz_uczelnia_id` (**ON `bpp_jednostka`**, czyta
     `NEW.wydzial_id` i `bpp_wydzial`) — walidacja „uczelnia jednostki ==
     uczelnia jej wydziału". Zastąpiony constraintem/walidacją na
     `Jednostka_Rodzic` (uczelnia rodzica == uczelnia dziecka).
   - `bpp_jednostka_wydzial_sprawdz_uczelnia_id` (ON `bpp_jednostka_wydzial`,
     czyta `bpp_wydzial`) — j.w. na tabeli historii.
   Kod Pythona dodatkowo utrzymuje księgowość nested-set MPTT (czego triggery
   nie robiły). **Każdy trigger ma jawny DROP w planie migracji** — inaczej
   drop kolumny `wydzial_id` / tabeli `bpp_wydzial` wywala każdy zapis.

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
  zapytania po poddrzewie (Sekcja 2). **Uwaga:** kolumny `wydzial_id` nie da
  się usunąć samą migracją schematu — czyta ją `JednostkaManager.get_queryset()`
  przez `select_related("wydzial")` (`jednostka.py:56`), `__str__`, admin,
  cache. Drop kolumny = część atomowego release'u kod+schemat (patrz plan).
- `aktualna` (dziś derywowana triggerem) → utrzymywana w Pythonie.
  **DECYZJA (recenzja 2026-07-04):** dla węzła bez wpisów historii
  (`Jednostka_Rodzic`) — root/były-wydział, jednostka wprost pod uczelnią,
  instalacja płaska — `aktualna = True`. Inaczej `publiczne()` (filtr
  `aktualna=True`) usunąłby je z formularza zgłoszeń (`zglos_publikacje/
  forms.py`) i publicznego autocomplete (`views/autocomplete/units.py`).
  „Brak historii" = „węzeł żyje bezterminowo", nie „węzeł nieaktualny".
- **`tmp` kolumna `legacy_wydzial_id`** (nullable, indeks) — TRWAŁE mapowanie
  `Wydzial.id → Jednostka.id` dla węzłów powstałych z konwersji. Nośnik
  idempotencji i migracji wartości (multiseek, FK). Kasowana w kroku „drop
  Wydzial".
- **Pola przeniesione per-węzeł z `Wydzial`** (flaga rodzaju ich NIE zastępuje):
  - `zezwalaj_na_ranking_autorow` (BooleanField, default True) — **per-węzeł**,
    filtruje listę wydziałów w rankingu (`ranking_autorow/forms.py:250`,
    `views.py:293`). Semantycznie różne od per-rodzaj `wyklucz_z_rankingu_autorow`
    (tamto wyklucza autorów z jednostek danego rodzaju; to wyłącza konkretny
    węzeł z listy sekcji rankingu). **Oba istnieją, nie mylić.**
  - `poprzednie_nazwy` (CharField), `skrot_nazwy` (CharField 250, unique) —
    brak dziś odpowiednika w `Jednostka`; dochodzą jako pola.
  - `otwarcie` / `zamkniecie` (daty życia) — patrz `Jednostka_Rodzic` niżej
    (lądują w temporalnej historii od/do, nie jako luźne pola).
- Pozostałe pola bez zmian (`uczelnia`, `pbn_uid`, `search`, `slug`, …).

### Historia temporalna — `Jednostka_Rodzic`

Uogólnienie istniejącego `Jednostka_Wydzial`:

```
Jednostka_Rodzic  (dawniej Jednostka_Wydzial)
  jednostka : FK(Jednostka, CASCADE)
  parent    : FK(Jednostka, CASCADE, null=True, blank=True)  # dawniej: wydzial
  od        : DateField (null, blank)
  do        : DateField (null, blank)
```

- **`parent` nullable (DECYZJA recenzja 2026-07-04).** Pozwala zapisać
  temporalny okres „jednostka wisiała bezpośrednio pod uczelnią (bez rodzica)
  od–do". Dawny `Jednostka_Wydzial.wydzial` był NOT NULL — po uogólnieniu na
  „rodzica" brak rodzica jest legalnym stanem historycznym.
- Manager rozcinający zakresy dat (`Jednostka_Wydzial_Manager`) przenosi się
  1:1 — logika interwałów jest generyczna. Check `uczelnia_id` staje się
  „uczelnia rodzica == uczelnia dziecka" (o ile `parent` nie-NULL).
- Constraint GiST `unikalny_zakres_dat_dla_jednostki` (btree_gist +
  `daterange … EXCLUDE`) — **zostaje**. Plus `bez_dat_do_w_przyszlosci`.
- **Daty życia węzła** (dawne `Wydzial.otwarcie`/`zamkniecie`, a dla jednostek
  historia obecności) mieszczą się w `od`/`do` wpisów — zasada niepodważalna #1.
- **Inwariant osi historia ↔ drzewo (ROZSTRZYGNIĘTY: TAK).** Bieżący wpis
  (`do IS NULL`) MUSI spełniać `Jednostka_Rodzic.parent == Jednostka.parent`
  (żywy MPTT). Historia dotyczy **krawędzi bezpośredniej** (zakład↔katedra),
  nie zakład↔wydział; przynależność wydziałowa w dacie D wyprowadza się przez
  wspinanie po drzewie i złożenie historii krawędzi. Szczegóły konwersji —
  patrz „Decyzje z recenzji", pkt 4.
- **Triggery — usuwane (patrz Zasady niepodważalne #3, trzy sztuki).**

### Utrzymanie spójności (zamiast triggera)

**KLUCZOWE (recenzja 2026-07-04): hook wisi na modelu HISTORII, nie na
Jednostce.** Dawny trigger odpalał się na SQL INSERT/UPDATE/DELETE tabeli
`bpp_jednostka_wydzial` — łapał wszystkie ścieżki. Zamiennik: sygnały
`post_save`/`post_delete` na **`Jednostka_Rodzic`** (nie save-hook Jednostki),
które derywują `aktualna` dziecka z bieżącego wpisu historii. Realne ścieżki
zapisu historii, które MUSZĄ przejść przez ten mechanizm:
- `pbn_import/utils/institution_import.py:126,149` (`get_or_create`),
- `import_jednostki_ipis.py:47,58`,
- `Jednostka_WydzialInline` w `admin/jednostka.py:21` (formset → save/delete),
- `Jednostka_Wydzial_Manager.wyczysc_przypisania`.

Zmiana `parent` (żywy MPTT) idzie Pythonowym API mptt (`move_to`/`save`).

**Cichy drift — jawnie zaadresowany:** `QuerySet.update()`, `bulk_create()`,
`loaddata` (`raw=True`) OMIJAJĄ sygnały. Egzekwowanie:
- management command `przelicz_aktualna` (idempotentny recompute całości) —
  wołany po importach masowych i w CI jako test spójności,
- test inwariantu „`aktualna` == derywacja z historii" na całej bazie,
- konwencja code-review: zakaz `update()`/`bulk_*` na `Jednostka.aktualna`
  i `Jednostka_Rodzic` bez następczego recompute.

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
węzła".** Raport tworzy sekcję per **bezpośrednie dziecko**, a każda sekcja
agreguje swoje poddrzewo (`child.get_descendants(include_self=True)`):

- klient z wydziałami: rozbicie na wydziały (jak dotąd),
- klient płaski: rozbicie na jednostki,
- dowolny węzeł: „rozbij `Wydział Lekarski` na jego katedry".

**DWA pęknięcia wyłapane w recenzji 2026-07-04 (wymagają jawnej obsługi):**

1. **`Uczelnia` NIE jest węzłem drzewa MPTT** — drzewo to wyłącznie
   `Jednostka`. Nie istnieje `Uczelnia.get_children()`. Domyślny (najczęstszy)
   przypadek „rozbij całą uczelnię" = **rooty danej uczelni**
   (`Jednostka.objects.filter(uczelnia=U, parent__isnull=True)`), nie
   `node.get_children()`. Kod raportu ma dwa tryby: `node=None` → rooty
   uczelni; `node=<Jednostka>` → `node.get_children()`.
2. **Jednostki-sieroty stają się sekcjami.** Dziś jednostka z `wydzial=NULL`
   (obce jednostki, „Jednostka domyślna" itp.) nie trafia do żadnej sekcji
   „per wydział". Po migracji jest rootem → naiwne „sekcja per root" wygeneruje
   sekcję per każda taka sierota → wynik ≠ dotychczasowy (łamie kryterium #4).
   Potrzebna jawna reguła filtrowania rootów raportowanych (np. tylko rooty
   rodzaju „Wydział", albo tylko `widoczna=True` / `wchodzi_do_raportow=True`) —
   do ustalenia per raport, tak by odtworzyć dotychczasowy zbiór sekcji.

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

**Zapisane wyszukiwania (persystencja) — migracja WARTOŚCI, nie tylko nazw
(recenzja 2026-07-04):** formularze multiseek są zapisywane
(`BppMultiseekVisibility`, saved searchform — por. migracja 0346). Zawierają
nie tylko `field_name="wydzial"`, ale też **konkretne PK wydziałów** — a te po
konwersji NIE ISTNIEJĄ (nowy węzeł ma NOWY PK). Sam alias nazwy pola nie
uratuje zapytania wskazującego `Wydzial.pk=5`. Wymagane: **migracja danych
zapisanych formularzy** przez trwałe mapowanie `legacy_wydzial_id` (PK
wydziału → PK węzła-jednostki) + przełączenie operatora na „+ podrzędne".
Analogicznie wartości `RodzajJednostkiQueryObject` (`normalna`/`kolo_naukowe`)
→ PK/kod wiersza `RodzajJednostki`. **Nie wolno po cichu usunąć QueryObjectu**
ani zostawić starych PK — zapisane wyszukiwania przestałyby się deserializować
lub wskazywałyby w próżnię. To kolejny powód, dla którego mapowanie musi być
trwałe (kolumna `legacy_wydzial_id`).

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

### Flaga „używaj wydziałów" — USUWANA CAŁKOWICIE (decyzja 2026-07-04)

To były DWA nośniki, **oba usuwane**:
- **`Uczelnia.uzywaj_wydzialow`** — pole BooleanField MODELU
  (`models/uczelnia.py:504`) → `RemoveField` (Faza C, po przepięciu call-site'ów).
- env `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW` → usuwana z settings/kodu.

**Nowa reguła: nawigacja/browse/menu ZAWSZE renderują drzewo jak jest.** Brak
bramkowania „czy istnieją wydziały" — instalacja płaska (`Uczelnia → Jednostka`)
po prostu ma płytkie drzewo i renderuje się naturalnie. Wszystkie rozproszone
warunki `if uczelnia.uzywaj_wydzialow` (menu `django_bpp/menu.py`, browse,
ranking, ewaluacja, pbn_import) → **usuwane** (gałąź „z wydziałami" staje się
bezwarunkowa; gałąź „bez" znika).

- **`bpp_setup_wizard/forms.py:82-99`** — pole/krok „używaj wydziałów" wypada
  z wizarda; setup zawsze zakłada drzewo.
- **`Jednostka.__str__`** — dziś dokleja skrót wydziału, bramkowany przez
  `uzywaj_wydzialow` I `DJANGO_BPP_SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI`. Po
  usunięciu pierwszego zostaje sam `SKROT_WYDZIALU_W_NAZWIE` (osobny,
  kosmetyczny przełącznik formatowania) → dokleja **skrót bezpośredniego
  rodzica** zamiast wydziału. Ten env-flag ZOSTAJE (to formatowanie nazwy, nie
  struktura).

---

## Plan migracji danych (konwersja, idempotentna, multi-tenant)

**UWAGA o granicach release'ów (recenzja 2026-07-04):** to NIE jest czysty
strangler „każdy krok osobno wdrażalny". `select_related("wydzial")` w
domyślnym managerze + triggery na `bpp_jednostka` sprawiają, że **usunięcie
`wydzial_id` i zmiany kodu MUSZĄ jechać w jednym release**. Plan dzieli się na
trzy fazy o różnej wdrażalności:

### Faza A — addytywna (wdrażalna przy STARYM kodzie, `Wydzial` żyje)

A1. **`RodzajJednostki` + seed** (Standard, Koło naukowe z flagami, Wydział).
   Dodać `Jednostka.rodzaj` FK **obok** `rodzaj_jednostki` (jeszcze nie
   usuwać stringa), backfill z mapowania stringów. Dodać per-węzeł pola
   przeniesione z `Wydzial` (`zezwalaj_na_ranking_autorow`, `poprzednie_nazwy`,
   `skrot_nazwy`) jako nullable/default. Dodać `Jednostka.legacy_wydzial_id`
   (nullable, indeks). `Wydzial` nietknięty.
A2. **Walidacja przed konwersją (read-only skan):** kolizje globalnie-unikalnych
   `nazwa` / `skrot` / **`slug`** / `skrot_nazwy` między wydziałami a
   jednostkami. Slug krytyczny dla redirectów 301 (`browse_wydzial` po slugu) —
   AutoSlug po cichu dokłada sufiks → stary URL trafiłby w 404/inną jednostkę.
   Rozwiązać ręcznie/z sufiksem PRZED konwersją.
A3. **Konwersja `Wydzial` → `Jednostka`** (jedna migracja, idempotentna po
   `legacy_wydzial_id`): dla każdego `Wydzial` utwórz `Jednostka`
   (rodzaj=Wydział, `uczelnia`, `parent=NULL` (root), `legacy_wydzial_id=W.id`,
   kopiując `nazwa`/`skrot`/`skrot_nazwy`/`opis`/`kolejnosc`/`widoczny`/
   `poprzednie_nazwy`/`pbn_id`/`zezwalaj_na_ranking_autorow`). Daty
   `otwarcie`/`zamkniecie` → wpis `Jednostka_Rodzic` (od/do) jednostek dzieci
   lub metadana węzła. Re-run rozpoznaje istniejące po `legacy_wydzial_id`.
A4. **Przepięcie struktury (parent) — TYLKO gdy `parent IS NULL`:** dla każdej
   `Jednostka` z `wydzial=W` i `parent IS NULL` ustaw `parent =
   węzeł(legacy=W)`. **Nie ruszaj** jednostek już mających `parent` (katedra→
   zakład zostaje). Reguła konfliktu (jednostka ma `parent` w INNYM wydziale
   niż `wydzial` — na multi-tenant wystąpi): zalogować + zostawić żywy `parent`,
   raport niespójności do ręcznego przeglądu. Skonwertować historię
   `Jednostka_Wydzial` → `Jednostka_Rodzic` wg mapowania (dla bezpośrednich
   dzieci wydziału 1:1; sub-jednostki — patrz „Decyzje z recenzji").
A5. **`MPTT rebuild()` OD RAZU** — kroki raportowe i denormalizacje polegają na
   poprawnych lft/rght; nie odkładać do końca.
A6. **Backfill `aktualna`** wg nowej semantyki (root/brak historii → True).

### Faza B — atomowy release kod+schemat (jeden deploy, NIE rozdzielać)

B1. **Przepięcie FK konsumentów** (8 FK) na `węzeł(legacy_wydzial_id)`:
   `Kierunek_Studiow` (PROTECT — przepiąć PRZED czymkolwiek), `Patent`,
   `opi_2012`, `zglos Zgloszenie`, `Obslugujacy_Zgloszenia_Wydzialow`,
   `import_dyscyplin`. Zmiana targetu FK na `Jednostka`.
B2. **DROP trzech triggerów** (`ustaw_wydzial_aktualna`,
   `bpp_jednostka_sprawdz_uczelnia_id`, `bpp_jednostka_wydzial_sprawdz_uczelnia_id`)
   + założenie zamienników (walidacja uczelni na `Jednostka_Rodzic`, sygnały
   `aktualna`). **Przed** dropem kolumny.
B3. **`RemoveField Jednostka.wydzial`** + usunięcie `rodzaj_jednostki`
   (CharField) — RAZEM z kodem, który przestaje je czytać (`select_related`,
   `__str__`, admin, cache, raporty, multiseek). To sedno atomowości fazy B.
B4. **`Nowe_Sumy_View`** — nowa definicja SQL (agregacja po poddrzewie/rodzicu,
   bez `wydzial`).
B5. **Migracja wartości zapisanych multiseek** (PK wydziału → PK węzła po
   `legacy_wydzial_id`; operator „+ podrzędne").
B6. **Kod konsumentów** (Sekcja 2): raporty (`get_descendants` + „rozbij na
   dzieci"/rooty uczelni + filtr sierot), admin (filtr `parent`), browse (301),
   API (deprecation), importy, `system.py` (grupy uprawnień bez `Wydzial`).
B7. **Usunięcie bramkowania `uzywaj_wydzialow`** — wszystkie `if
   uczelnia.uzywaj_wydzialow` (menu, browse, ranking, ewaluacja, pbn_import,
   setup wizard) → drzewo renderowane bezwarunkowo; `__str__` dokleja skrót
   rodzica gated tylko `SKROT_WYDZIALU_W_NAZWIE`. env
   `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW` usuwana.

### Faza C — sprzątanie (po weryfikacji fazy B na danych)

C1. **Drop `Wydzial`** — gdy nic go nie referuje. Wyczyścić osierocone
   `ContentType`/`Permission` po `Wydzial`/`Jednostka_Wydzial`/
   `Obslugujacy_Zgloszenia_Wydzialow` (przypisane do grup w `system.py`!).
C2. **Drop `Jednostka.legacy_wydzial_id`** (mapowanie już niepotrzebne) +
   **`RemoveField Uczelnia.uzywaj_wydzialow`** (po usunięciu bramkowania w B7).
C3. **Rebuild cache** (`Rekord`/`Autorzy`/`punktacja`) + `rebuild_jednostka` +
   ostateczny MPTT `rebuild()`.
C4. **Baseline** — `make baseline-update` RAZ, przy scalaniu (nie w
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
| Twarde FK → `Wydzial` | 8 |

**8 FK do obsłużenia** (`on_delete` → los):

- `Kierunek_Studiow.wydzial` **PROTECT** → Jednostka (przepiąć PRZED kasowaniem).
- `Patent.wydzial` SET_NULL → Jednostka.
- `opi_2012.wydzial` CASCADE → Jednostka.
- `zglos_publikacje Zgloszenie.wydzial` CASCADE → Jednostka.
- `Obslugujacy_Zgloszenia_Wydzialow.wydzial` CASCADE → Jednostka
  (`zglos_publikacje/models.py:380`; pominięty w poprzedniej tabeli).
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

**Powierzchnie DOKŁADANE po recenzji 2026-07-04** (spec ich wcześniej nie
wymieniał, a realnie zależą od `Wydzial`):
- `bpp/system.py:62,102,154,156,199` — słownik grup uprawnień z `Wydzial`,
  `Jednostka_Wydzial`, `Obslugujacy_Zgloszenia_Wydzialow` → po dropie zostają
  **osierocone `ContentType`/`Permission` przypisane do grup w produkcji**;
  wymaga jawnego sprzątania (Faza C1).
- `bpp/export/bibtex.py:172-179` — `wydzial.nazwa` jako `school` (zewnętrzny
  kontrakt eksportu, jak API — przełożyć na węzeł-rodzic).
- `bpp/models/autor.py:312-353` — `Autor.afiliacja_na_rok(rok, wydzial)`
  (`jednostka__wydzial=`), wołane z `imports/egeria_2012.py:281`.
- `bpp/models/praca_doktorska.py:76` — `@depend_on_related("bpp.Jednostka",
  only=(…, "wydzial_id"))` — zależność cache denorm; po usunięciu kolumny
  zmienić na ścieżkę drzewa/parent.
- `bpp/views/autocomplete/search_services.py:69` — global search
  `only("wydzial__skrot").select_related("wydzial")`.
- `bpp/management/commands/prace_do_rozliczenia.py:44` — `Wydzial.objects.all()`.
- `api_v1/serializers/raport_slotow_uczelnia.py:50` — pole
  `dziel_na_jednostki_i_wydzialy` (kontrakt API — deprecation obejmuje też to,
  nie tylko `/api/v1/wydzial/`).
- `django_bpp/dashboard.py:46` — moduł `bpp.models.wydzial` w dashboardzie.
- `JednostkaManager.create()` (kompat kwarg `wydzial=`) + **duplikat**
  `JednostkaCreateManager` (`models/wydzial.py:152-164`) — używane przez
  importy i dziesiątki testów; zdecydować o zachowaniu kompat-kwargu.
- `Uczelnia.uzywaj_wydzialow` (pole modelu) + `bpp_setup_wizard/forms.py:82-99`.

Reszta ze ~100 plików to raporty (`ranking_autorow`, `raport_slotow`,
`nowe_raporty`, `ewaluacja_metryki`), importy (`pbn_import`, `egeria_2012`,
`import_dyscyplin`, `mapuj_kierunki_studiow`), demo-data (`generators/wydzialy.py`,
`orchestrator.py`) oraz ~48 plików testowych i ~15 szablonów.

## Decyzje z recenzji adwersaryjnej 2026-07-04 (rozstrzygnięte z użytkownikiem)

1. **Konwersja struktury zachowuje istniejące `parent`.** Węzeł-wydział zostaje
   rodzicem TYLKO jednostek z `parent IS NULL`; zagnieżdżenia katedra→zakład
   nietknięte. `rebuild()` MPTT od razu po przepięciu.
2. **`aktualna` = True dla węzła bez historii** (root/były-wydział, jednostka
   pod uczelnią, instalacja płaska). Chroni widoczność w `publiczne()`.
   `Jednostka_Rodzic.parent` nullable (temporalny okres „pod uczelnią").
3. **Pola per-węzeł z `Wydzial` lądują na `Jednostka`:**
   `zezwalaj_na_ranking_autorow` (per-węzeł, ≠ per-rodzaj flaga),
   `poprzednie_nazwy`, `skrot_nazwy`; `otwarcie`/`zamkniecie` → historia od/do.
4. **Flaga `uczelnia.uzywaj_wydzialow` USUWANA całkowicie** (pole modelu + env).
   Nawigacja/browse/menu zawsze renderują drzewo jak jest; bramkowanie znika.
   `__str__` dokleja skrót rodzica gated tylko `SKROT_WYDZIALU_W_NAZWIE`.

4. **Historia sub-jednostek = per bezpośrednia krawędź w `Jednostka_Rodzic`**
   (decyzja 2026-07-04). Historia trzymana jest dla **faktycznego rodzica**
   (zakład↔katedra, katedra↔wydział), nie dla zdublowanej krawędzi
   zakład↔wydział. Przynależność wydziałowa w dowolnej dacie D **wyprowadza się**
   przez wspinanie po drzewie i złożenie historii krawędzi po drodze.
   - **Inwariant (rozstrzygnięty: TAK):** bieżący wpis `Jednostka_Rodzic(do=NULL)`
     dla węzła ma `parent == żywy MPTT parent`. Jeden nośnik prawdy o „gdzie
     węzeł wisi teraz".
   - **Konwersja (Faza A4):** dla jednostek, które staną się bezpośrednimi
     dziećmi wydziału (`parent` był NULL) — `Jednostka_Wydzial → Jednostka_Rodzic`
     1:1 (`parent=węzeł-wydział`). Dla sub-jednostek (miały już `parent=katedra`)
     — zostaje krawędź do faktycznego rodzica; stara `wydzial`-historia jest
     redundantna z historią przodka i **nie** jest przepisywana na zakład↔wydział.
     Jeśli sub-jednostka miała `wydzial` niezgodny z łańcuchem przodków (dane
     patologiczne) → zalogować do ręcznego przeglądu, nie zgadywać.
   - W typowej (płaskiej) instalacji sprawa nie występuje — większość jednostek
     to bezpośrednie dzieci wydziału.

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
10. **Trzy triggery** zdjęte z jawnymi DROP-ami; walidacja uczelni przeniesiona;
    `aktualna` utrzymywana sygnałami na `Jednostka_Rodzic`; command
    `przelicz_aktualna` + test spójności łapią drift z `bulk_*`/`loaddata`.
11. **Byłe wydziały (rooty) widoczne** w `publiczne()`, formularzu zgłoszeń i
    publicznym autocomplete (`aktualna=True`); instalacja płaska bez regresji.
12. **`zezwalaj_na_ranking_autorow` per-węzeł zachowany** — ranking wyłącza te
    same węzły co dotąd (osobno od per-rodzaj `wyklucz_z_rankingu_autorow`).
13. **Brak osieroconych `ContentType`/`Permission`** po `Wydzial`/
    `Jednostka_Wydzial`/`Obslugujacy_Zgloszenia_Wydzialow` (grupy uprawnień OK).
14. Redirecty 301 działają — brak kolizji `slug` wydział↔jednostka.
15. **Flaga `uzywaj_wydzialow` usunięta** (pole + env); nawigacja zawsze
    renderuje drzewo; brak martwych gałęzi `if uzywaj_wydzialow`.
16. Cała suita testów zielona; baseline odświeżony.
17. Migracja idempotentna (trwałe `legacy_wydzial_id`) i przetestowana na ≥1
    realnym dumpie multi-tenant.

## Świadomie odłożone (YAGNI)

- Zmiana nazwy modelu `Jednostka` → `JednostkaOrganizacyjna` (kosmetyka).
- Twarde usunięcie API `/wydzial/` (dopiero po okresie deprecation).
- Wariant raportu „suma bez double-count przy zagnieżdżeniu" — przy braku
  pojęcia wydziału i agregacji po jawnie wybranym węźle problem znika
  (użytkownik wybiera konkretny węzeł; nie ma automatycznej enumeracji).
- Odmiana `RodzajJednostki.nazwa` — spina się z gałęzią odmiany później
  (ta gałąź tylko przygotowuje pole `nazwa`).
