# Specyfikacja: motywy (THEMES) + streszczenia dla `create_demo_data`

**Data:** 2026-06-01
**Status:** draft — do akceptacji
**Autor:** Michał Pasternak + sesja brainstormingowa Claude'a
**Rozszerza:** [`2026-05-13-create-demo-data-design.md`](2026-05-13-create-demo-data-design.md)

## 1. Cel

Rozszerzyć istniejący generator danych demo (`bpp.demo_data`, komendy
`create_demo_data` / `cleanup_demo_data`) o:

1. **System motywów (THEMES)** — wymienialne „paczki treści", z których
   czerpią wszystkie generatory nazw: postacie→autorzy, nazwa uczelni,
   wydziały, jednostki, źródła (czasopisma), wydawcy, tytuły prac i
   streszczenia.
2. **Generator streszczeń** — tekstowe streszczenia (`Wydawnictwo_*_Streszczenie`)
   nasycone motywem, dla konfigurowalnego odsetka prac.
3. **Realistyczne nazewnictwo** — koniec z `Demo — Jednostka 1-1`,
   `Demo — Czasopismo 1`, `Demo — Wydawca 1`. Nazwy składane z
   realistycznych polskich wzorców akademickich × treść motywu.

**Motywacja:** obecny generator daje realistyczne nazwiska autorów, ale
jednostki/źródła/wydawcy mają nudne numerowane nazwy (`Demo — X N`). Dane
mają „wyglądać prawdopodobnie", a przy okazji — z przymrużeniem oka —
pozwalać na tematyczne uniwersa (Lem, Wiedźmin, Harry Potter, Disney).

**Zachowane bez zmian:** architektura batch-create + manifest, podwójne
potwierdzenie, preflight słowników, manifest-DB consistency check,
determinizm po `--seed`, cleanup po PK z manifestu.

## 2. Decyzje produktowe (z sesji)

| Pytanie | Decyzja |
|---|---|
| Co dostarcza motyw? | **Wszystko**: postacie (autorzy), uczelnia, wydziały, jednostki, źródła, wydawcy, tytuły, streszczenia |
| Motywy w v1 | `realistyczny` (domyślny), `lem`, `wiedzmin`, `harry-potter`, `disney` |
| Jeden motyw na uruchomienie? | Tak — `--motyw <key>`, bez mieszania |
| Streszczenia | „Zawsze tematyczne" → każdy motyw ma własne szablony; `realistyczny` = generyczny akademicki tekst |
| Język streszczeń | Polski (FK `jezyk_streszczenia` → polski, fallback `None`) |
| Pokrycie streszczeń | ~70% prac, flaga `--procent-ze-streszczeniem` |
| Marker „Demo —" | **Domyślnie WŁĄCZONY**; flaga `--bez-prefiksu` wyłącza dla pełnego realizmu |
| Lata prac | Domyślnie **2020–2026** (flagi `--od-roku/--do-roku` zostają) |

## 3. CLI — nowe flagi

```bash
uv run python src/manage.py create_demo_data \
    [--motyw realistyczny|lem|wiedzmin|harry-potter|disney]   # NOWE, default realistyczny
    [--procent-ze-streszczeniem 70]                           # NOWE
    [--bez-prefiksu]                                          # NOWE (flaga)
    [--od-roku 2020] [--do-roku 2026]                         # zmienione defaulty
    [... wszystkie dotychczasowe flagi bez zmian ...]
```

- `--motyw` — `choices=` z kluczy registry; nieznany klucz → błąd argparse.
- `--bez-prefiksu` — gdy podane, `prefix=""`; inaczej `prefix="Demo — "`.
- `cleanup_demo_data` — CLI i logika `run_cleanup` **bez zmian** (działa po
  PK z manifestu); jedynie stała `CLEANUP_ORDER` zyskuje 2 wpisy na
  streszczenia (§6.1), więc czyści je automatycznie.

## 4. Architektura — pakiet `themes/`

```
src/bpp/demo_data/
  themes/                          ← NOWY podpakiet
    __init__.py
    base.py                        ← @dataclass(frozen=True) Theme + SHARED_* stałe
    compose.py                     ← compose_jednostka/zrodlo/autor/tytul/streszczenie
    registry.py                    ← THEMES dict + get_theme(key) + ALL_KEYS
    realistyczny.py                ← wchłania obecne names.py (PL realistyczny)
    lem.py
    wiedzmin.py
    harry_potter.py
    disney.py
  names.py                         ← USUNIĘTE (treść → themes/realistyczny.py)
  generators/                      ← każdy generator dostaje param `theme` + `prefix`
    streszczenia.py                ← NOWY generator
```

### 4.1. `Theme` (base.py)

`Theme` to **frozen dataclass — sama treść, zero logiki** (zgodnie z
obecnym podziałem „dane vs generatory"). Pola flavorowane są wymagane;
pola strukturalne (prefiksy jednostek, prefiksy źródeł, szablony tytułów)
mają **domyślne wartości = stałe `SHARED_*`**, więc motyw nadpisuje tylko
to, co ma być tematyczne.

**Uwaga implementacyjna:** dataclass jest `kw_only=True` (Python ≥3.10) —
dzięki temu pola z domyślną wartością (`jednostka_prefiksy`,
`zrodlo_prefiksy`, `tytul_templates`) mogą sąsiadować z polami bez
domyślnej bez łamania reguły „defaults last". Wszystkie `Theme(...)`
tworzymy z nazwanymi argumentami.

```python
@dataclass(frozen=True, kw_only=True)
class Theme:
    key: str                              # "wiedzmin"
    label: str                            # "Wiedźmin"
    # Uczelnia (singleton — bierzemy [0] deterministycznie):
    uczelnia_nazwy: tuple[str, ...]
    uczelnia_skrot: str
    # Wydział: "Wydział <dziedzina>"
    wydzial_dziedziny: tuple[str, ...]
    # Jednostka: "<prefiks> <dziedzina>"
    jednostka_dziedziny: tuple[str, ...]
    jednostka_prefiksy: tuple[str, ...] = SHARED_JEDNOSTKA_PREFIKSY
    # Autor: "<imiona> <nazwisko>"
    autor_imiona: tuple[str, ...]
    autor_nazwiska: tuple[str, ...]       # nazwiska LUB przydomki ("z Rivii")
    # Źródło: "<prefiks> <human>"
    zrodlo_human: tuple[str, ...]
    zrodlo_prefiksy: tuple[str, ...] = SHARED_ZRODLO_PREFIKSY
    # Wydawcy: pełne nazwy
    wydawcy: tuple[str, ...]
    # Tytuły:
    tytul_topics: tuple[str, ...]
    tytul_subjects: tuple[str, ...]
    tytul_contexts: tuple[str, ...]
    tytul_templates: tuple[str, ...] = SHARED_TYTUL_TEMPLATES
    # Streszczenia (każde {topic}/{subject}/{context} z pól tytułowych):
    streszczenie_templates: tuple[str, ...]
```

Stałe współdzielone (zawsze realistyczne — to one „uwiarygadniają"
nawet żartobliwą dziedzinę):

```python
SHARED_JEDNOSTKA_PREFIKSY = (
    "Katedra", "Zakład", "Klinika", "Katedra i Klinika",
    "Katedra i Zakład", "Instytut", "Pracownia",
)
SHARED_ZRODLO_PREFIKSY = (
    "Acta", "Annales", "Folia", "Roczniki", "Przegląd",
    "Zeszyty Naukowe", "Studia",
)
SHARED_TYTUL_TEMPLATES = (  # przeniesione z names.TYTULY_TEMPLATES
    "Analiza wpływu {topic} na {subject} w {context}",
    "Badania {topic} w kontekście {subject}",
    ...
)
```

### 4.2. Helpery kompozycyjne (compose.py)

Czyste funkcje `(theme, rng, ...) -> str`, deterministyczne przy danym
`rng`:

- `compose_jednostka_nazwa(theme, rng)` → `"Katedra Eliksirologii"`
- `compose_zrodlo_nazwa(theme, rng)` → `"Acta Kaedwenica"`
- `compose_wydzial_nazwa(theme, rng, i)` → `"Wydział Wiedźmiński"`
- `compose_autor(theme, rng)` → `("Geralt", "z Rivii")`
- `compose_tytul(theme, rng)` → tekst z `tytul_templates` × topics/subjects/contexts
- `compose_streszczenie(theme, rng)` → 3–5 zdań z `streszczenie_templates`
- `apply_prefix(nazwa, prefix)` → `f"{prefix}{nazwa}"` (prefix może być `""`)

**Reguła prefiksu:** marker dotyczy pól `nazwa` instytucji
(uczelnia, wydział, jednostka, źródło, wydawca) **oraz** `tytul_oryginalny`
prac. **NIE** dotyczy `imiona`/`nazwisko` autora — „Demo — Geralt"
wyglądałoby źle; demo-ność autora niesie slug (`...-demo-N`) + manifest,
tak jak dziś.

**Skróty** (`skrot`/`skrot_nazwy`) pozostają indeksowe i unikalne (np.
`DW{i}`, `DJ{i}-{j}`, `DC{i}`) — nie są celem realizmu, a unikalność jest
ważniejsza (część ma `unique=True`).

### 4.3. Registry (registry.py)

```python
THEMES: dict[str, Theme] = {t.key: t for t in (
    REALISTYCZNY, LEM, WIEDZMIN, HARRY_POTTER, DISNEY,
)}

def get_theme(key: str) -> Theme:
    try:
        return THEMES[key]
    except KeyError:
        raise ValueError(f"Nieznany motyw '{key}'. Dostępne: {sorted(THEMES)}")
```

Dodanie nowego motywu = 1 plik + 1 wpis. Test kompletności (§8) pilnuje,
że każdy motyw ma niepuste wszystkie pule.

## 5. Treść motywów (przykłady — pełne pule w modułach)

Poniżej **reprezentatywne** próbki; implementacja dostarcza pełniejsze
pule (≥10–20 pozycji na pole, by autorzy/jednostki nie powtarzali się
zbyt szybko). Powtórki nazwisk są dozwolone (realne bazy mają imienników;
slug i tak ma disambiguator).

### `realistyczny` (upgrade obecnego — domyślny)
- **uczelnia:** „Uniwersytet Przykładowy", „Akademia Nauk Stosowanych"
- **wydział dziedziny:** istniejące `KIERUNKI_POL` (Lekarski, Farmaceutyczny…)
- **jednostka dziedziny:** Kardiologii, Biochemii, Mikrobiologii Lekarskiej,
  Anatomii Prawidłowej, Genetyki Molekularnej, Chirurgii Ogólnej,
  Farmakologii, Patomorfologii, Neurologii, Pediatrii, Immunologii…
- **autor:** istniejące `IMIONA_POL` × `NAZWISKA_POL`
- **źródło human:** „Medica Polonica", „Biochemica", „Clinica",
  „Neurologica", „Chirurgica" → „Acta Medica Polonica", „Folia Biochemica"
- **wydawcy:** „Wydawnictwo Naukowe PWN", „Wydawnictwo Lekarskie PZWL",
  „Wydawnictwo Uniwersyteckie", „Oficyna Wydawnicza Scholar"
- **tytuł/streszczenie:** istniejące `TOPICS/SUBJECTS/CONTEXTS` + generyczne
  szablony akademickie

### `lem` (Stanisław Lem)
- **uczelnia:** „Instytut Badań Kosmicznych im. Ijona Tichego"
- **wydział dziedziny:** Kosmonautyki, Cybernetyki, Solarystyki, Robotyki,
  Futurologii, Sepulkologii
- **jednostka dziedziny:** Solarystyki, Robotyki Trurla, Sepulkologii,
  Bystrzochronu, Cyberiady Porównawczej, Kosmogonii Eksperymentalnej
- **autor imiona:** Ijon, Kris, Hal, Pirx, Trurl, Klapaucjusz, Snaut, Rohan
- **autor nazwiska:** Tichy, Kelvin, Bregg, Sartorius, Horpach
- **źródło human:** Solarystyczne, Cybernetyczne, Sepulkarne, Astronautyczne
- **wydawcy:** „Wydawnictwo Solaris", „Oficyna Kosmiczna Tichego",
  „Dom Wydawniczy Eden"
- **topics:** podróży międzygwiezdnych, sepulek, robotów Trurla, oceanu
  Solaris, cybernetyki

### `wiedzmin` (Wiedźmin)
- **uczelnia:** „Akademia Wiedźmińska w Kaer Morhen", „Uniwersytet w Oxenfurcie"
- **wydział dziedziny:** Wiedźmiński, Magii i Eliksirów, Bestiariuszu, Znaków
- **jednostka dziedziny:** Eliksirologii, Bestiariuszu Porównawczego,
  Znaków i Gestów, Szlaku Wiedźmińskiego, Mutacji, Zielarstwa Wiedźmińskiego
- **autor imiona:** Geralt, Yennefer, Ciri, Jaskier, Vesemir, Triss, Lambert,
  Eskel, Regis, Filippa, Cahir, Milva
- **autor nazwiska/przydomki:** z Rivii, z Vengerbergu, z Cintry, Merigold,
  z Kaer Morhen, z Oxenfurtu, z Aretuzy
- **źródło human:** Kaedwenica, Wiedźmińska, Novigradzka, Temerska, Aretuzańska
- **wydawcy:** „Wydawnictwo Kaer Morhen", „Oficyna Oxenfurcka",
  „Dom Wydawniczy Novigrad"
- **topics:** eliksirów wiedźmińskich, mutacji, bestii, znaków, szlaku

### `harry-potter`
- **uczelnia:** „Hogwart — Szkoła Magii i Czarodziejstwa"
- **wydział dziedziny:** Magii, Eliksirów, Transmutacji, Obrony przed Czarną
  Magią, Zielarstwa
- **jednostka dziedziny:** Eliksirów, Transmutacji, Obrony przed Czarną Magią,
  Zielarstwa, Numerologii, Zaklęć, Opieki nad Magicznymi Stworzeniami
- **autor imiona:** Harry, Hermiona, Ron, Albus, Severus, Minerwa, Rubeus,
  Draco, Luna, Neville, Ginny, Sybilla
- **autor nazwiska:** Potter, Granger, Weasley, Dumbledore, Snape, McGonagall,
  Hagrid, Malfoy, Lovegood, Longbottom
- **źródło human:** Hogvartensia, Magiczne, Czarodziejskie
- **wydawcy:** „Oficyna Hogwart Press", „Wydawnictwo Esy i Floresy",
  „Wydawnictwo Ministerstwa Magii"

### `disney`
- **uczelnia:** „Uniwersytet Disneya", „Akademia Magicznego Królestwa"
- **wydział dziedziny:** Animacji, Magii Królestwa, Przygód, Baśni
- **jednostka dziedziny:** Animacji Klasycznej, Magii Królestwa, Baśni
  Porównawczych, Przygód Morskich
- **autor imiona:** Miki, Donald, Sknerus, Goofy, Pluto, Daisy, Hyzio, Dyzio,
  Zyzio, Elsa, Anna, Ariel, Belle, Mulan, Simba, Aladyn
- **autor nazwiska:** Mysz, Kaczor, McKwacz, z Arendelle, Syrenka, Lew,
  z Krainy Lodu — **nigdy puste**: jednoimienne postacie (Elsa, Ariel,
  Simba) dostają tematyczny przydomek, by `nazwisko` autora było niepuste
- **źródło human:** Magicznego Królestwa, Disnejowskie, Animowane
- **wydawcy:** „Disney Academic Press", „Wydawnictwo Magicznego Królestwa"
- **uwaga:** marka silnie chroniona — OK dla wewnętrznego demo/dev/test
  (nazwy postaci jako placeholdery, brak dystrybucji jako produkt).

## 6. Generator streszczeń (`generators/streszczenia.py`)

```python
def create_streszczenia(
    *, prace_wc, prace_wz, theme, procent, manifest, rng,
    batch_size=500, disable_progress=False,
) -> None:
```

- Model: `Wydawnictwo_Ciagle_Streszczenie` (FK `rekord` → WC) i
  `Wydawnictwo_Zwarte_Streszczenie` (FK `rekord` → WZ); pola z
  `BazaModeluStreszczen`: `streszczenie` (TextField), `jezyk_streszczenia`
  (FK `bpp.Jezyk`, nullable).
- Dla każdej pracy: z prawd. `procent%` twórz 1 wiersz streszczenia,
  `streszczenie = compose_streszczenie(theme, rng)`,
  `jezyk_streszczenia = <polski>`.
- **Polski język:** `Jezyk.objects.filter(skrot__in=["pol.", "pol"]).first()`
  lub `filter(nazwa__icontains="polski").first()`; gdy brak → `None`
  (pole nullable). Implementacja weryfikuje dokładny `skrot` z fixtury
  `jezyk`.
- `bulk_create` w batchach + `manifest.append("bpp.Wydawnictwo_*_Streszczenie", pks)`.
- Brak pól `@denormalized` na tych modelach → bez `apply_denorm_pre_save_cache`.

### 6.1. Manifest — `CLEANUP_ORDER`

Dodać **przed** rekordami prac (FK `rekord` z `CASCADE`; usunięcie
najpierw streszczeń jest jawne i bezpieczne):

```python
CLEANUP_ORDER = (
    "bpp.Wydawnictwo_Ciagle_Autor",
    "bpp.Wydawnictwo_Zwarte_Autor",
    "bpp.Wydawnictwo_Ciagle_Streszczenie",   # NOWE
    "bpp.Wydawnictwo_Zwarte_Streszczenie",   # NOWE
    "bpp.Wydawnictwo_Ciagle",
    "bpp.Wydawnictwo_Zwarte",
    ... (reszta bez zmian) ...
)
```

## 7. Zmiany w istniejących generatorach i orchestratorze

- **orchestrator.py:** `CreateOptions` zyskuje `motyw: str`,
  `procent_ze_streszczeniem: int`, `bez_prefiksu: bool`. `run_create`:
  `theme = get_theme(opts.motyw)`; `prefix = "" if opts.bez_prefiksu else "Demo — "`.
  Przekazuje `theme` + `prefix` do generatorów; po `create_wc`/`create_wz`
  woła `create_streszczenia`. Defaulty `od_roku=2020`, `do_roku=2026` w
  `add_arguments`.
- **uczelnia.py:** `nazwa = apply_prefix(theme.uczelnia_nazwy[0], prefix)`,
  `skrot = theme.uczelnia_skrot`. Singleton — bez zmian w logice reuse.
- **wydzialy.py:** `nazwa = apply_prefix(compose_wydzial_nazwa(theme, rng, i), prefix)`.
- **jednostki.py:** `nazwa = apply_prefix(compose_jednostka_nazwa(theme, rng), prefix)`.
- **autorzy.py:** `imiona, nazwisko = compose_autor(theme, rng)` (bez prefiksu).
- **zrodla.py:** `nazwa = apply_prefix(compose_zrodlo_nazwa(theme, rng), prefix)`.
- **wydawcy.py:** `nazwa = apply_prefix(rng.choice(theme.wydawcy) + " <unik>", prefix)`
  — `nazwa` ma `unique=True`, więc do puli motywu dokładamy disambiguator
  indeksowy (np. sufiks `" (Oddział N)"`) gdy `n > len(pula)`.
- **_publikacje_common.py `make_tytul`:** `body = compose_tytul(theme, rng)`;
  wynik `apply_prefix(f"{body} (nr {idx})", prefix)`. (Sufiks `(nr idx)`
  zostaje — gwarantuje unikalność i pozwala namierzyć rekord; w trybie
  `--bez-prefiksu` tytuł nadal ma `(nr idx)` ale bez `Demo —`.)

Generatory publikacji (`create_wc`/`create_wz`) zyskują param `theme`
(przekazywany do `make_tytul`) i **zwracają listę stworzonych prac** (już
zwracają) — orchestrator przekazuje je do `create_streszczenia`.

## 8. Testy

Katalog `src/bpp/tests/test_demo_data/`. Zmiany + nowości:

**Aktualizacje (theme-aware):**
- `test_generator_autorzy`: `assert a.imiona in IMIONA_POL` →
  parametryzacja po motywie: `assert a.imiona in theme.autor_imiona`,
  `assert a.nazwisko in theme.autor_nazwiska`.
- `test_generator_zrodla_wydawcy`: `startswith("Demo —")` → przy
  `prefix="Demo — "` asercja prefiksu; przy `prefix=""` asercja **braku**
  prefiksu + obecności znanego `zrodlo_prefiks`/`zrodlo_human`.
- `test_generator_wydzialy_jednostki`: jednostka zawiera znany prefiks
  (`Katedra`/`Zakład`/…) **i** dziedzinę z motywu; już **nie** `Jednostka N`.
- `test_generator_uczelnia`: asercja na `theme.uczelnia_nazwy[0]` (+ prefix).

**Nowe:**
- `test_theme_registry` — każdy motyw w `THEMES`: wszystkie pule niepuste,
  `key`/`label` ustawione, `get_theme(zły)` → `ValueError`.
- `test_compose_determinizm` — ten sam `rng(seed)` → te same nazwy
  (per helper, per motyw).
- `test_generator_streszczenia` — dla `procent=100` każda praca ma 1
  streszczenie, `jezyk` ustawiony gdy fixtura `jezyk` obecna, manifest
  zawiera pks; dla `procent=0` — zero streszczeń.
- `test_bez_prefiksu` — `bez_prefiksu=True` → żadna `nazwa`/`tytul` nie
  zaczyna się od „Demo —"; nazwiska autorów nigdy nie mają prefiksu w
  żadnym trybie.
- `test_command_create` (rozszerzenie) — smoke per motyw (mały N), exit 0,
  manifest spójny, cleanup roundtrip czyści też streszczenia.

Wszystko zachowuje determinizm (RNG per-run, nie globalny) i wzorce z
oryginalnej specyfikacji §10.

## 9. Kolejność budowy (fazy)

1. **`themes/` szkielet:** `base.Theme` + `SHARED_*` + `compose` + `registry`
   + `realistyczny` (wchłonięcie `names.py`). Testy: registry, compose
   determinism. Usunięcie `names.py` + aktualizacja importów.
2. **Refactor generatorów** na `theme` + `prefix` (zachowując zachowanie
   `realistyczny`, ale z urealnionym nazewnictwem jednostek/źródeł/wydawców).
   Aktualizacja istniejących testów na theme-aware.
3. **4 motywy** (`lem`, `wiedzmin`, `harry_potter`, `disney`) + wpisy w
   registry + treść. Testy: każdy motyw składa sensowne nazwy.
4. **Streszczenia:** generator + `CLEANUP_ORDER` + wiring w orchestratorze
   + flagi (`--motyw`, `--procent-ze-streszczeniem`, `--bez-prefiksu`) +
   defaulty lat 2020–2026 + help text. Testy + e2e per motyw (mały N).
5. **Dokumentacja:** krótki howto w `docs/` (jak odpalić z motywem) +
   aktualizacja bannera stdout (wzmianka o motywie i streszczeniach).
6. **Domknięcie:** `ruff format`/`ruff check`, `pre-commit`, pełny przebieg
   `src/bpp/tests/test_demo_data/`, opcjonalny smoke przez `run-site`.

Każda faza = osobny commit; testy zielone po każdej.

## 10. Out of scope (v1)

- Nowe typy encji (konferencje, patenty, doktoraty, granty, nagrody) —
  jak w oryginale.
- Mieszanie wielu motywów w jednym przebiegu (1 motyw / run).
- Streszczenia wielojęzyczne (tylko PL; EN jako ewentualny follow-up).
- Tłumaczenie/odmiana gramatyczna nazw — pule podajemy w docelowej formie.
- Tematyczne słowniki (Charakter_Formalny itd. zostają standardowe).

## 11. Decyzje odrzucone (z trade-offami)

- **Faker / biblioteka z postaciami** — odrzucone (jak w oryginale): trzymamy
  samodzielne krotki danych, pełna kontrola + determinizm.
- **Dict-of-pools (jeden słownik)** — odrzucone: mniej typobezpieczne,
  słabsza różnorodność, łatwo o literówkę w kluczu.
- **Hierarchia klas z metodami** — odrzucone: więcej kodu, trudniej ogarnąć
  całą treść motywu naraz; `dataclass` + `compose` wystarcza.
- **Prefiks na nazwiskach autorów** — odrzucone: „Demo — Geralt" brzydkie;
  demo-ność niesie slug + manifest.
- **Cleanup streszczeń tylko przez CASCADE** — odrzucone: jawny wpis w
  manifeście + `CLEANUP_ORDER` (manifest pozostaje źródłem prawdy).
- **Prefiks domyślnie wyłączony** — odrzucone w pytaniu o marker: user
  wybrał marker domyślnie WŁĄCZONY (`--bez-prefiksu` dla realizmu).

## 12. Definicja sukcesu (acceptance)

- `create_demo_data --motyw <X> --yes-i-am-sure --confirm-db <NAME>` dla
  każdego z 5 motywów (mały N): exit 0, manifest spójny, nazwy złożone
  tematycznie/realistycznie (zero „Jednostka 1-1"/„Czasopismo 1").
- ~`--procent-ze-streszczeniem`% prac ma streszczenie nasycone motywem,
  z językiem polskim (gdy fixtura `jezyk` obecna).
- `--bez-prefiksu` → żadnego „Demo —" w nazwach/tytułach; nazwiska autorów
  zawsze czyste.
- Domyślne lata generowanych prac mieszczą się w 2020–2026.
- `cleanup_demo_data` czyści też streszczenia; świadkowie nietknięci;
  determinizm po `--seed` zachowany.
- `ruff format`/`ruff check`/`pre-commit` przechodzą; pełny
  `test_demo_data/` zielony.
