# Konsolidacja Wydział → Jednostka — Faza B (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Skonsolidować `Wydzial` w jedno drzewo MPTT `Jednostka`. `Jednostka.wydzial`
NIE jest usuwane — staje się **zdenormalizowanym self-FK do KORZENIA drzewa** (NULL
dla top-level), utrzymywanym przez `django-denorm-iplweb`.

**Architecture:** Jedno drzewo MPTT `Jednostka` (Uczelnia → Jednostka*). „Wydział" =
jednostka top-level (root, `parent IS NULL`). `Jednostka.wydzial` = denorm self-FK do
`get_root()` (NULL dla rootów) → odczyty i zapytania ORM działają jak dawniej
(`filter(jednostka__wydzial=root)`, `select_related("wydzial")`). Design-rationale:
patrz spec `docs/superpowers/specs/2026-07-02-konsolidacja-wydzial-jednostka-design.md`.

**Tech Stack:** Django 5, PostgreSQL, django-mptt 0.18, django-denorm-iplweb,
multiseek, DjangoQL, pytest + model_bakery + testcontainers.

## Global Constraints

- **`uv run` przed KAŻDYM Pythonem.** Nigdy goły `python`/`pytest`.
- **Max line length: 88** (ruff). `ruff format` + `ruff check` czysto na zmienionych.
- **NIE modyfikuj istniejących migracji.** Nowe od `0454` (liść = `0453_zrodlo_trigram_indexes`). Przed
  KAŻDYM pushem `git fetch origin dev` → nowy liść → renumeracja.
- **Zielony suite per task** = zielono PO każdym commicie (pytest stosuje WSZYSTKIE
  migracje). **Task = jeden commit.** Uwaga: `filter(...=<zła instancja modelu>)` w
  Django **NIE rzuca** — po cichu porównuje `.pk` → ciche złe wyniki. Dlatego zmiana
  targetu FK (`wydzial`, 5 FK) i jej konsumenci MUSZĄ być w jednym commicie.
- **Federacja (Zasada #4):** brak constraintu równości uczelni (trigger + CHECK +
  `Jednostka_Wydzial.clean()` uczelniany — usuwane bez zamiennika).
- **Idempotencja:** `legacy_wydzial_id` = trwały klucz. Każdy RunPython re-runnable.
- **Migracje = historical models** (`apps.get_model`), NIE real models/komendy.
- **⚠ RELEASE-ATOMOWOŚĆ (fable II-1 F2):** CAŁA Faza B (II-1..IV-1, migracje 0458–0463)
  MUSI iść JEDNYM deployem. Po retargecie (II-1) węzły-wydziały są `widoczna=False`
  aż do odkrycia w IV-1 — więc release samego II-1 (bez IV-1) dałby PUSTE pickery
  wydziału, pustą listę „tylko nadrzędne" w browse i 404 w `JednostkaSerializer.wydzial`.
  Nigdy nie wypuszczać II-1 osobno.
- **Baseline:** `make baseline-update` RAZ, przy scalaniu.

---

## Decyzje projektowe (finalne — pełne uzasadnienie w specu)

1. **`Jednostka.wydzial` = denorm self-FK do korzenia** (NULL dla top-level):
   `@denormalized(models.ForeignKey,"self",null=True,SET_NULL,related_name="+")` +
   `@depend_on_related("self","parent",only=("wydzial_id",))`; func: `parent_id is
   None → None; else parent.wydzial or parent`. Kaskada tranzytywna utrzymuje korzeń.
2. **„Wydział" = jednostka top-level.** Picker/„rozbij" = rooty uczelni;
   „szukaj po wydziale" = `filter(jednostka__wydzial=root)` (dołóż `| Q(jednostka=root)`
   dla prac samego korzenia).
3. **`wchodzi_do_raportow` → RenameField `wchodzi_do_rankingu_autorow`** (pole sum
   rankingu); widoki filtrują je, bez JOIN `bpp_wydzial`.
4. **`rodzaj_jednostki` (CharField) usuwane** → `rodzaj` FK; nowa flaga
   `RodzajJednostki.pokazuj_strukture_podjednostek` (dodawana w B, seed „Wydział"=True)
   steruje stylem strony browse.
5. **`uzywaj_wydzialow` konsolidowane na modelu `Uczelnia`** (per-uczelnia); env
   `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW` usuwane.
6. **`aktualna`** derywowana z historii + **ręczny override** (`aktualna_override`
   nullable: NULL=derywuj; ustawione=trzymaj).
7. **Multiseek** `WydzialQueryObject`/`PierwszyWydzialQueryObject` zostają osobne
   (picker top-level, `filter(jednostka__wydzial=root)`, operatory męskie).

---

## Mechanizm przejściowy: węzeł-lustro (wyłoniony w I-3, nie było w pierwotnym planie)

W Fazie B współistnieją stary `Wydzial` (drop w Fazie C) i drzewo `Jednostka`.
`Jednostka_Rodzic.parent` wskazuje Jednostkę, więc kod linkujący jednostkę do
wydziału potrzebuje **węzła-lustra** (ukryta Jednostka z `legacy_wydzial_id==Wydzial.id`).
Realizacja (I-3): `struktura_konwersja.py::znajdz_lub_utworz_wezel_wydzialu(wydzial)`
(get-or-create, collision-safe, MPTT root, `widoczna=False/aktualna=False`, rodzaj
„Wydział"), wołany **LAZY** — tylko w link-sites (`institution_import`,
`import_jednostki_ipis`), NIE eager na `post_save` Wydziału (eager zawyżałby
`Jednostka.objects.count()` suite-wide). `post_delete` Wydziału usuwa lustro-sierotę.
Znika w Fazie C. **⚠ I-4:** `post_delete` lustra CASCADE'uje na `Jednostka_Rodzic.parent`
— przy podpięciu realnych dzieci pod lustra pamiętać o tym.

## Kolejność (0454–0463)

- **B-I** (0454–0457): schemat/historia/drzewo. `wydzial` (stary FK→Wydzial) żyje,
  stary kod czyta go dalej → zielono.
- **B-II** (0458–0460): **atomowy retarget `wydzial`→denorm-korzeń + WSZYSCY jego
  konsumenci** (jeden commit II-1), potem repoint 5 FK (II-2).
- **B-III** (0461 + kod): usunięcie `rodzaj_jednostki` + czyste UI/admin/browse/cleanup.
- **B-IV** (0462–0463): recompute `aktualna`/`widoczna` + migracja wartości multiseek.

---

## Sub-plan B-I — Schemat, historia, drzewo (0454–0457)

### Task I-1 (0454): additive — flagi + rename pola rankingu + override aktualna
- `rodzaj_jednostki.py`: AddField `pokazuj_strukture_podjednostek` (Bool default=False);
  seed „Wydział"=True.
- `jednostka.py`: **RenameField** `wchodzi_do_raportow`→`wchodzi_do_rankingu_autorow`
  (verbose_name „Wlicza prace jednostki do rankingu autorów"); **AddField
  `aktualna_override`** (BooleanField null=True, „Ręczne nadpisanie «aktualna»").
- Refy `wchodzi_do_raportow` (same commit — RenameField): `ranking_autorow/forms.py:158,259`,
  `views.py:316`, **`ranking_autorow/tests.py:273,280,364,369,405,412`**, `admin/jednostka.py:88,100,133`,
  `admin/xlsx_export/resources.py:323`, `api_v1/serializers/struktura.py:65`,
  `pbn_api/admin/publication.py:252`, **`src/fixtures/conftest_models.py:152`**.
- Test `test_faza_b/test_i1.py`. **Uwaga:** RenameField renames kolumnę; zależne
  widoki `bpp_nowe_sumy_*` auto-śledzą po attnum. **Step 1–5.**

### Task I-2 (0455): DROP 3 triggery + konwersja re-run (historical) + sygnały aktualna
- `0455_...py`: RunSQL `DROP TRIGGER/FUNCTION IF EXISTS` × (3+3); RunPython konwersja
  re-run na `apps.get_model` (explicit `lft/rght/tree_id/level`, `rodzaj_jednostki="normalna"`,
  `widoczna=False/aktualna=False`, `legacy_wydzial_id`, idempotent, kolizje-sufiks).
- **Sygnały (kod, same commit):** `post_save`/`post_delete` na `Jednostka_Wydzial`
  derywują `aktualna` (respektują `aktualna_override`). **Ważne (BŁĄD #3):** stary
  trigger `bpp_jednostka_ustaw_wydzial_aktualna` utrzymywał TAKŻE `wydzial_id` — po
  jego zdjęciu edycja historii przestaje aktualizować `jednostka.wydzial` (do B-II,
  gdzie `wydzial` staje się denorm-em). **Decyzja:** sygnały do B-II utrzymują też
  interim `wydzial_id` (jak stary trigger), usuwane w II-1. Semantyka „brak wpisów":
  interim `False` (jak dziś) do IV-1, tam finalne `True`.
- **Testy same-commit (asertują trigger):** `test_struktura/test_jednostka_wydzial_jednostka.py:13-39`
  (`j.wydzial==w`, `aktualna` po delete), `:52-56` (cross-uczelnia raise — walidacja
  zdjęta → test do zmiany na „nie rzuca"), `:63+`, `:87+`. **Step 1–5.**

### Task I-3 (0456): RenameModel Jednostka_Wydzial→Jednostka_Rodzic + parent
- `0456_...py`: RenameModel; AddField `parent` FK(Jednostka,null); RunPython backfill
  `parent` z bieżącego wpisu (przez `legacy_wydzial_id`); RemoveField historia.`wydzial`.
- Modify (same commit, ~10 plików): rename klasy/managera, `przypisania`/`wydzial_dnia`/
  `wyczysc_przypisania`, **`clean()` — usuń check uczelni** (Zasada #4), Inline rename,
  `jednostka_wydzial_set`→`jednostka_rodzic_set`, `struktura.py`, `system.py`,
  `util/uczelnia_scope.py`, `pbn_import/utils/institution_import.py`, `import_jednostki_ipis`.
- **`wydzial.py` (BŁĄD #2 — brakowało):** `historyczne_jednostki()`/`kola_naukowe()`
  importują `Jednostka_Wydzial` + `filter(wydzial=self)` na historii → przepisz na
  `Jednostka_Rodzic.objects.filter(parent__legacy_wydzial_id=self.pk)`.
- **Testy same-commit:** `test_models/test_wydzial.py`, `test_struktura/test_jednostka_wydzial_jednostka.py`,
  `test_struktura/test_jednostka.py` (importują `Jednostka_Wydzial`). **Step 1–5.**

### Task I-4 (0457): re-parent + przepisanie historii + nested-set (czysty Python)
- `0457_...py` RunPython: (1) SNAPSHOT sub-jednostek (parent NOT NULL, wydzial_id NOT
  NULL) PRZED czymkolwiek; (2) `parent`=węzeł(legacy=wydzial_id) TYLKO gdy `parent IS
  NULL` i `wydzial_id NOT NULL`; (3) węzeł-wydział: własny wpis Jednostka_Rodzic
  (parent=NULL, od=otwarcie, do=CLAMP: NULL jeśli ≥dziś; od<do; idempotent guard);
  (4) sub_ids: przepisz wpisy na krawędź faktycznego rodzica (od/do), NIE ruszaj
  direct-children; (5) lft/rght/tree_id/level w czystym Pythonie. **Step 1–5.**

---

## Sub-plan B-II — Atomowy retarget `wydzial` + repoint 5 FK (0458–0460)

### Task II-1 (mig 0458+0459, JEDEN commit): retarget `wydzial`→denorm-korzeń + WSZYSCY konsumenci

**Dlaczego atomowo (BŁĄD #1):** retarget zmienia, na co wskazuje `wydzial` (Wydzial→
Jednostka-korzeń). W tym samym momencie każdy, kto podaje `Wydzial` do
`filter(jednostka__wydzial=…)` albo woła metody Wydziału na `jednostka.wydzial`, musi
flipnąć — bo `filter` nie rzuca, tylko cicho zwraca złe wyniki. Nowej formy
`wydzial=root` nie da się napisać przed retargetem. Więc jeden commit.

**Kolejność migracji w commicie:** (0458) widoki sum → (0459) retarget kolumny.

**(a) Widoki sum (0458, BŁĄD #6/#7):** `DROP VIEW bpp_nowe_sumy_view`→5 komponentów→
recreate: usuń JOIN `bpp_wydzial`, zachowaj `bpp_jednostka.wydzial_id AS wydzial_id`,
reguła = `WHERE wchodzi_do_rankingu_autorow=true`. Tylko `bpp_nowe_sumy_*` (kronika/
ewaluacja czyste). Bazuj na baseline (po `108_..bug.sql`). `Nowe_Sumy_View.wydzial`
→ FK→Jednostka (state). Zdjęcie JOIN-u bezpieczne, gdy `wydzial_id` wciąż = Wydzial.

**(b) Retarget `wydzial` (0459, three-step):** `AlterField→IntegerField` → RunPython
**oblicz korzeń wędrówką po `parent`** (drzewo gotowe po I-4; NIE ślepy remap starego
`wydzial_id`, bo dla zagnieżdżonych z driftem stary `wydzial_id` ≠ korzeń — BŁĄD #8;
rooty→NULL) → `AlterField→ForeignKey("self",null=True,SET_NULL)` + `@denormalized`/
`@depend_on_related`. **denorm okno (BŁĄD #5):** `denorm drop`+retarget+`denorm init`
w tym commicie (init instaluje TYLKO triggery — wartości daje remap wyżej). Test-inwariant
„po re-parencie potomek ma `wydzial==get_root()`" (deep tree).

**(c) Definicja + metody:** denorm-func w `jednostka.py` (Decyzja #1); metody `Wydzial`
(`jednostki`/`kola_naukowe`/`aktualne_jednostki`/`historyczne_jednostki`) → na
`Jednostka` (metody węzła po `get_children`/poddrzewie). Sygnały przestają utrzymywać
interim `wydzial_id`.

**(d) Konsumenci zapytań `wydzial` (same commit — inaczej ciche złe wyniki):**
- `cache/rekord.py:96 prace_wydzialu(node)` — parametr to teraz root Jednostka;
  `filter(autorzy__jednostka__wydzial=node) | Q(autorzy__jednostka=node)`.
- `ranking_autorow/views.py:231,300 get_dostepne_wydzialy` → rooty z
  `zezwalaj_na_ranking_autorow=True`; `forms.py:252-257` Subquery; kolo-exclusion
  `views.py:257`→ (uwaga: `rodzaj_jednostki` znika w III-1 — tu użyj FK `rodzaj`,
  bo pole CharField jeszcze jest do 0461; spójnie z III-1).
- `nowe_raporty/poziomy.py:34-37` → `prace_wydzialu(root)`; picker widget →
  `public-jednostka-toplevel-autocomplete` (tworzony niżej).
- `ewaluacja_metryki/views/list.py:205` (`Wydzial.objects.filter(jednostka__in=…)` —
  reverse-rel znika → FieldError) + `export.py` filtry/kolumna → rooty/`jednostka.wydzial`.
- **Autocomplete top-level:** nowy `public-jednostka-toplevel-autocomplete`
  (`parent__isnull=True`, UczelniaScoped, `.widoczne()`) + helper `jednostki_toplevel`.
- **Multiseek (BŁĄD #1 + #7):** `WydzialQueryObject`/`PierwszyWydzial` — model→Jednostka,
  url→top-level, `real_query`=`Q(autorzy__jednostka__wydzial=value)|Q(autorzy__jednostka=value)`,
  operatory męskie; PierwszyWydzial +`kolejnosc=0`. **Gate (wariant 1):** rejestruj
  `WydzialQueryObject` ZAWSZE w `fields/__init__.py` (usuń oba `if getattr(settings,
  …UZYWA_WYDZIALOW)`); widoczność per-uczelnia przez `BppMultiseekVisibility`
  (uczelnia bez wydziałów chowa pole). Picker i real_query flipują RAZEM.
- `api_v1/serializers/struktura.py:48 JednostkaSerializer.wydzial` (HyperlinkedRelatedField
  →wydzial-detail; `jednostka.wydzial` to teraz Jednostka) → wskaż zasób Jednostki-korzenia.
- `autor.py:363 afiliacja_na_rok(rok, node)` (`jednostka__wydzial=`) + caller
  `egeria_2012.py:281`; `import_pracownikow/models.py:92`.

**(e) Fabryki testów (BŁĄD #1/#9 — same commit):** `tests/util.py:85 any_jednostka`
→ tworzy jednostkę top-level (rola wydziału) + `parent` dziecka na nią (`wydzial`
derywuje się sam). Usuń kompat-kwarg `wydzial=` z `JednostkaManager.create()`.
**DWA fixture'y (BŁĄD #9):** nowy `jednostka_toplevel` dla nowego świata; fixture
`wydzial` ZOSTAJE Wydzial-typed (testy `/api/v1/wydzial/`, `WydzialAdmin`, `WydzialView`
żyjące do B-III/C potrzebują prawdziwych `Wydzial`). **Writery `wydzial=` (ValueError
po retargecie):** `demo_data/generators/jednostki.py:34`, `zaloz_jednostki_domyslne.py:141,154`,
`admin/jednostka_import.py:151-153` (importer pęka od II-1 — NIE zostawiać do III).
**Kolo-fixtury (seam C):** `ranking_autorow/tests.py:110`, `conftest_models.py:105`
ustawiają stary CharField `rodzaj_jednostki` — flipnij na FK `rodzaj` (inaczej
wykluczenie kół w II-1 ich nie łapie → test czerwony).

**(f) GREP-SWEEP (metoda, uzgodnione — hand-lista NIE jest wyczerpująca):** przed
zamknięciem commitu uruchom i obsłuż KAŻDE trafienie:
`grep -rn "\.wydzial\b\|jednostka__wydzial\|wydzial=\|Wydzial\.objects\|__wydzial__" src/ --include="*.py" | grep -v /migrations/`.
Rozdziel na: (i) odczyty `.nazwa`/`.skrot` (działają — root ma je), (ii) zapytania/
przypisania podające `Wydzial` (flipnij na root Jednostkę — TO są miejsca do zmiany),
(iii) traversale czysto-ORM bez instancji (`raport_slotow/tables.py:174`,
`upowaznienie_pbn.py:102`, `browse.py:417/424`, admin `select_related` — bez zmian).
Lista (a)–(e) to znany zbiór, nie kompletny. **Seam A (same commit):** stare metody
na `Wydzial` (`jednostki`/`kola_naukowe`/`aktualne_jednostki`/`historyczne_jednostki`)
+ `WydzialView` + `browse/wydzial.html` + `test_wydzial.py` — albo przepisz metody
Wydziału by delegowały przez `legacy_wydzial_id`-korzeń, albo wciągnij WydzialView tu
(nie zostawiaj do III-2, bo `filter(wydzial=self)` cicho zwraca śmieci). **Seam B:**
`zglos_publikacje/views.py:154` — między II-1 a II-2 `emaile_dla_wydzialu(jednostka.wydzial)`
cicho źle rutuje; albo most `root→Wydzial(legacy)` w II-1, albo II-1+II-2 lądują
back-to-back ze świadomym oknem. `cache/rekord.py:271` filter-map + `ewaluacja
list.py:70` — objęte sweepem. **Step 1–10.**

### Task II-2 (0460): repoint 5 FK konsumentów Wydzial→Jednostka + konsumenci
**Files:** `0460_...py`; FK-decls: `kierunek_studiow.py:7` (PROTECT), `patent.py:106`
(SET_NULL), `opi_2012.py:20` (CASCADE), `import_dyscyplin/models.py:546` (SET_NULL),
`zglos_publikacje/models.py:394` (CASCADE).
- Per FK: `AlterField→IntegerField` / remap (`legacy_wydzial_id`) / `AlterField→FK(Jednostka)`.
  Unmappable: PROTECT→fail loud; SET_NULL→NULL+log; CASCADE→NULL/skip+log.
- **Konsumenci same-commit:** routing `zglos_publikacje/views.py:154`
  (`emaile_dla_wydzialu(jednostka.wydzial)`→`emaile_dla_obslugujacego(jednostka.get_root())`),
  `models.py:368-402` (manager + FK→Jednostka, unique_together/ordering),
  `admin/filters.py:9-22` (miesza oba końce — `jednostka__wydzial` już zrobione w II-1,
  tu `Obslugujacy.wydzial`); testy/fixtures 5 FK (`create(wydzial=<Wydzial>)`→root Jednostka).
  **Step 1–5.**

---

## Sub-plan B-III — usunięcie `rodzaj_jednostki` + czyste UI/admin/cleanup (0461 + kod)

### Task III-1 (0461): re-backfill rodzaj + RemoveField `rodzaj_jednostki` + konsumenci
- `0461_...py`: RunPython rebackfill `rodzaj` WHERE NULL (`{"normalna":"Standard",
  "kolo_naukowe":"Koło naukowe"}`); RemoveField `rodzaj_jednostki`.
- **Konsumenci CharField/`RODZAJ_JEDNOSTKI` (same commit — BŁĄD #6, usunięcie klasy
  łamie importy):** `demo_data/generators/jednostki.py:37`, `management/commands/mapuj_kola_naukowe.py:35,45,68`
  (przepisz na FK `rodzaj`), `admin/xlsx_export/resources.py:320`, admin
  `list_display/filter/fieldsets`, testy: `test_multiseek_djangoql_fields_misc.py:16-23`,
  **`fixtures/conftest_models.py:105`, `ranking_autorow/tests.py:110`,
  `test_views/test_views_browse.py:121`, `test_multiseek/test_multiseek_organizations.py:162`,
  `test_models/test_jednostka_rodzaj_fk.py`** (asertuje CharField wprost — twardo pęka
  na 0461 RemoveField). Grep-sweep `rodzaj_jednostki`/`RODZAJ_JEDNOSTKI` jak w II-1(f).
- **`RodzajJednostkiQueryObject` CAŁY tutaj** (values→`RodzajJednostki.objects.all()`,
  `real_query` `autorzy__jednostka__rodzaj=<row>`, `to_djangoql` — refy w `unit_fields.py`,
  NIE w `djangoql_export.py`). **Step 1–5.**

### Task III-2: Browse — JednostkaView dual-style + 301 + sitemap + strona uczelni
- `browse.py`: usuń `WydzialView`; `JednostkaView` rozgałęzia wg
  `object.rodzaj.pokazuj_strukture_podjednostek` (struktura: metody węzła z II-1; prace:
  dotychczas). Template `browse/jednostka.html` `{% if …pokazuj_strukture… %}`.
- `urls.py:247` `browse_wydzial`→RedirectView 301 (lookup `Wydzial` po slug → `Jednostka(
  legacy_wydzial_id)` → jej slug). `sitemaps.py` `WydzialSitemap` usuń.
- **`templates/browse/uczelnia.html` + `Uczelnia.wydzialy()` (BŁĄD #5):** sekcja
  wydziałów iteruje `uczelnia.wydzialy` (tabela `bpp_wydzial`) + linkuje
  `admin:bpp_wydzial_changelist` (`:400,:436`) → **NoReverseMatch** po usunięciu
  `WydzialAdmin` (III-3). Przepnij sekcję na rooty uczelni; usuń link adminowy. **Step 1–6.**

### Task III-3: Admin (WydzialAdmin removal) + system.py
- `admin/jednostka.py`: filtr `parent` (autocomplete-backed); `wydzial_skrot` (czyta
  root — zostaje). Usuń `admin/wydzial.py` + `__init__.py:63` + `uczelnia.py WydzialInline`
  (zostaw `uzywaj_wydzialow` w fieldset). `xlsx_export/resources.py`: `WydzialResource` usuń.
- API: `Wydzial` żyje do Fazy C → `/api/v1/wydzial/` NIETKNIĘTE (pole serializera
  zrobione w II-1).
- `system.py`: usuń `Wydzial`/`Jednostka_Wydzial` z grup, DODAJ `Jednostka_Rodzic`;
  `Obslugujacy_Zgloszenia_Wydzialow` zostaje. (Czyszczenie ContentType → Faza C.)
- **`uzywaj_wydzialow` konsolidacja (Decyzja #5):** env `DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW`
  usuń (`settings/base.py:142,1510`); pozostałe czytniki env → `uczelnia.uzywaj_wydzialow`:
  `browse.py:709`, `menu.py:257`, `jednostka.py:207 __str__` (przez `self.uczelnia`);
  testy `@override_settings` → ustaw pole. (Czytnik multiseeka zrobiony w II-1 wariantem 1.)
  Adaptuj `Wydzial.objects`→rooty (menu/ranking/ewaluacja/pbn_import/wizard). **Step 1–5.**

---

## Sub-plan B-IV — Recompute + multiseek (0462–0463)

### Task IV-1 (0462): przelicz_aktualna (z override) + odkrycie widoczna + aktualna default
- `0462_...py` + `management/commands/przelicz_aktualna.py` (RunPython **duplikuje
  logikę**, NIE woła komendy): **`aktualna_override`≠NULL → użyj override, POMIŃ
  derywację**; inaczej brak wpisów→True, `do IS NULL`→True, wszystkie `do` w
  przeszłości→False. Odkrycie (`widoczna=True`) skonwertowanych węzłów z
  `bpp_wydzial.widoczny` po `legacy_wydzial_id`. AlterField `aktualna` default=True.
  Invalidate cache raz. Test-inwariant „aktualna==derywacja gdy override NULL". **Step 1–5.**

### Task IV-2 (0463): migracja WARTOŚCI zapisanych multiseek
- `0463_...py` RunPython: parse `multiseek_searchform.data` (JSON, NIE `replace()`);
  `field∈{"Wydział","Pierwszy wydział"}` → remap `value` (Wydzial pk → `Jednostka(
  legacy_wydzial_id=pk).pk`); `field=="Rodzaj jednostki"` → remap LABEL
  (`"zwyczajna jednostka (katedra, zakład, pracownia, itp.)"`→`"Standard"`,
  `"koło naukowe"`→`"Koło naukowe"`). BEZ relabel pola wydziału / operatorów. Brak
  mapowania→drop+log; idempotent guard. **Step 1–5.**

---

## Faza C (poza B)
Drop `Wydzial`, drop `legacy_wydzial_id`, czyszczenie ContentType/Permission,
konfigurowalny label poziomu top-level (audit; `uzywaj_wydzialow` ZOSTAJE), rename
`wydzial`→`jednostka_toplevel`, rebuild cache, `baseline-update`.

## Self-review (writing-plans)
- Wszystkie 9 findingów fable-review wchłonięte: #1 (atomowy II-1), #2 (wydzial.py w I-3),
  #3 (interim wydzial_id + testy w I-2), #4 (2 refy w I-1), #5 (uczelnia.html w III-2),
  #6 (konsumenci rodzaj_jednostki w III-1), #7 (wariant 1 multiseek w II-1), #8 (korzeń
  wędrówką po parent w II-1b), #9 (dwa fixture'y w II-1e).
- Decyzje 1–7 zmapowane. Design-rationale w specu.
- **Przed KAŻDYM taskiem migracyjnym:** `git fetch origin dev` + renumeracja.
