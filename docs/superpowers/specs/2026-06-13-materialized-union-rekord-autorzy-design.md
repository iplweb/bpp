# Notatka projektowa: `MaterializedUnion` — deklaratywny `bpp_rekord_mat` / `bpp_autorzy_mat` (czerwiec 2026)

> **Status: ROZWAŻONE I ŚWIADOMIE ODŁOŻONE.** Nie budujemy tego teraz.
> Ten dokument zapisuje cały design + uzasadnienie „czemu nie", żeby przyszłe
> JA nie przechodziło tej analizy od zera i miało gotowy seed, gdyby decyzja
> się odwróciła.
>
> Data: 2026-06-13 · Kontekst: po PR #363 (port `bpp_refresh_cache`
> PL/Python → PL/pgSQL + bramka WHEN). · Tryb: brainstorming (bez implementacji).

---

## TL;DR (decyzja)

Rozważaliśmy zbudowanie deklaratywnej abstrakcji Django (`MaterializedUnion`),
która z jednej deklaracji generowałaby: 5 widoków per-typ + tabelę
zmaterializowaną + triggery + bramkę + kanarka — zamiast dzisiejszego ręcznego
SQL-a rozsianego po dziesiątkach migracji.

**Werdykt: nie budować.** Wszystkie trzy dźwignie ROI są słabe:

1. widoki zmieniają się **rzadko** (kilka razy w roku — migracje 0071…0428
   rozsiane po setkach numerów) → ergonomia nie zwraca tygodni pracy;
2. ręczny churn **nie blokuje** zespołu (jest brzydki, nie bolesny);
3. wątek OSS **kuszący, ale niepewny popyt** → „zbuduję i się okaże" topi
   tygodnie w infrastrukturze.

Do tego **trudną połowę i tak już zrobiliśmy tanio** w PR #363: migracje
`0432`/`0433` introspektują kolumny i wypiekają DDL triggerów + bramkę + mają
kanarka. Zostaje głównie ergonomia *zmiany kolumn widoku* — czyli ta rzadka
operacja.

Design jest sensowny i elegancki (zasada „źródło → unie → trigger"), ale
**elegancja to nie ROI**. Gdyby któraś z 3 dźwigni się zmieniła (patrz
[Kiedy wrócić](#kiedy-wrócić-do-tematu)) — wchodzimy, zaczynając od PoC
`Rekord` + `Autorzy`.

---

## 1. Problem

`bpp_rekord_mat` (i `bpp_autorzy_mat`) to zmaterializowane unie 5 typów
publikacji (`ciagle`, `zwarte`, `patent`, `praca_doktorska`,
`praca_habilitacyjna`) z compound-id `[content_type_id, pk]` (bo `pg_ivm` nie
obsługuje `UNION`, więc IVM-dla-unii robimy ręcznie triggerami).

Każda zmiana kolumny dziś wymaga ręcznej edycji **5 widoków** per-typ +
`ALTER TABLE bpp_rekord_mat` + ewentualnie funkcji triggera — w osobnych,
ręcznie pisanych plikach SQL. Brak walidacji: literówka w nazwie kolumny
przechodzi cicho aż do błędu SQL (albo cichego staleness).

## 2. Architektura obecna (as-is)

- **5 widoków per-typ** `bpp_*_view` — ręczne `CREATE VIEW`, każdy wylicza
  dokładnie kolumny `bpp_rekord_mat` + `object_id_raw`. To **kontrakt kolumn**.
- **`bpp_rekord`** — widok `UNION ALL` po 5 typach (model `RekordView`,
  `managed=False`). **Niemal szczątkowy** — odpytywany tylko przez jedną
  relację FK + komentarz (`rozbieznosci_dyscyplin/admin.py`). Do weryfikacji,
  czy w ogóle potrzebny.
- **`bpp_rekord_mat`** — prawdziwa TABELA (zmaterializowana unia), model
  `Rekord` `managed=False`. **To jest publiczne API** — cały kod żyje na niej.
- **`bpp_autorzy_mat`** — analogiczna tabela z widoków `*_autorzy` (model
  `Autorzy`).
- **Triggery** na 5 tabelach bazowych (+3 through `*_autor`) → funkcja refresh
  (po PR #363: statyczny PL/pgSQL `bpp_refresh_rekord_*` / `bpp_refresh_autor_*`
  + `bpp_delete_*`, z bramką WHEN na UPDATE).

**Ustalony fakt (grep):** per-typ widoki `bpp_*_view` **nie są odpytywane przez
kod aplikacji — tylko przez testy**. Istnieją wyłącznie jako źródło SELECT-a
triggera. Wniosek: w ewentualnym frameworku stają się **wewnętrznym detalem
generowanym**, nie częścią API. Użytkownik widzi tylko `bpp_rekord_mat`.

## 3. Pomysł: abstrakcja `MaterializedUnion`

Rdzeń: **N `MaterializedUnion`, każda z listą źródeł; tabela bazowa może
zasilać kilka unii; jej trigger odświeża wszystkie unie, które zasila.**
`bpp_rekord_mat` i `bpp_autorzy_mat` to dwie instancje tego samego mechanizmu.

### Nazewnictwo (zdecydowane)

- **worek (klasa bazowa): `MaterializedUnion`** — szczere, greppable, wprost
  nazywa to, czego pg_ivm nie umie (UNION). Wygrało z metaforami
  (`Confluence`/`Manifold`/`Amalgam`) i z `PolymorphicMaterializedView`.
- **wkład typu: `Source`** (neutralne; alternatywy `Member`/`Variant`).
- Domenowy `Rekord` jest *instancją* tego worka:
  `class Rekord(MaterializedUnion)`.

### Składnia (wersja finalna z dyskusji)

Zasady:

- **`common_fields`** — pola passthrough na każdym źródle (w tym pola
  *zadeklarowane na unii*, których nie ma na obiektach, np.
  `liczba_autorow = count("autorzy")`).
- **globalne override** pól (dla wszystkich typów), np.
  `doi = lower("doi")`.
- **per-typ podklasy** `class Wydawnictwo_Ciagle(Overrides): ...`.
- **Reguła domyślna (sedno prostoty):** kolumna nie wymieniona → jeśli tabela
  bazowa ma pole o tej nazwie, `base.<kol>`; inaczej `NULL::<typ>`. **Typ
  wnioskowany z pola modelu** (`_meta`) — znika osobny słownik typów. Pokrywa
  ~40% kolumn (zrodlo_id, kwartyl_*, openaccess_*, konferencja_id, wydawca_id,
  tytul…) za darmo.
- **Walidacja nazw przez `Model._meta.get_field()`** w `manage.py check`
  (system check) → literówka = głośny błąd w CI/pre-commit. To **jedyna rzecz
  dająca realną przewagę nad plikiem SQL**: weryfikowalność.
- Helpery na nieregularny ogon: `lookup(Model, skrot=...)` (stała-podzapytanie),
  `strip(field, *chars)` (normalizacja stringa), `sql("...")` (escape hatch),
  `inner(rel)` (JOIN dla źródła publikacji w `Autorzy`).
- **Topologia FROM/JOIN/GROUP BY nie deklarowana** — wynika z obecności
  agregatu (`count("autorzy")` ⇒ `LEFT JOIN through + GROUP BY base.id`).

## 4. Specyfikacja `Rekord` (odtwarza wszystkie 5 `bpp_*_view`)

```python
class Rekord(MaterializedUnion):
    key = ["content_type_id", "id"]                 # ARRAY[ct, base.id] — auto
    sources = [Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Patent,
               Praca_Doktorska, Praca_Habilitacyjna]

    # passthrough tam gdzie pole ISTNIEJE (typ z modelu), inaczej NULL::typ.
    # nazwy walidowane przez Model._meta → literówka = błąd `manage.py check`.
    common_fields = [
        "tytul", "tytul_oryginalny", "search_index", "rok",
        "jezyk_id", "typ_kbn_id", "charakter_formalny_id",
        "zrodlo_id", "wydawnictwo_nadrzedne_id", "konferencja_id",
        "informacje", "szczegoly", "uwagi", "adnotacje",
        "impact_factor", "punkty_kbn", "index_copernicus",
        "punktacja_wewnetrzna", "punktacja_snip", "kwartyl_w_wos", "kwartyl_w_scopus",
        "utworzono", "ostatnio_zmieniony", "tytul_oryginalny_sort",
        "opis_bibliograficzny_cache", "opis_bibliograficzny_autorzy_cache",
        "opis_bibliograficzny_zapisani_autorzy_cache",
        "slug", "recenzowana", "liczba_znakow_wydawniczych",
        "www", "dostep_dnia", "public_www", "public_dostep_dnia",
        "openaccess_czas_publikacji_id", "openaccess_licencja_id",
        "openaccess_tryb_dostepu_id", "openaccess_wersja_tekstu_id",
        "openaccess_ilosc_miesiecy", "openaccess_data_opublikowania",
        "liczba_cytowan", "status_korekty_id", "pbn_uid_id",
        "slowa_kluczowe_eng", "wydawca_id",
    ]

    # globalne (wszędzie gdzie pole źródłowe istnieje; reszta → NULL):
    doi            = lower("doi")                    # lower(doi)
    wydawnictwo    = field("wydawca_opis")           # rename; ciagle/patent NULL auto
    liczba_autorow = count("autorzy")                # auto LEFT JOIN through + GROUP BY
    isbn           = strip("isbn",  "-", " ", ".")   # replace-chain
    e_isbn         = strip("e_isbn","-", " ", ".")

    class Patent(Overrides):
        jezyk_id              = lookup(Jezyk, skrot="pol.")     # (SELECT id … WHERE skrot=…)
        typ_kbn_id            = lookup(Typ_KBN, skrot="PO")
        charakter_formalny_id = lookup(Charakter_Formalny, skrot="PAT")
        liczba_znakow_wydawniczych = 0

    class Praca_Doktorska(Overrides):
        charakter_formalny_id = lookup(Charakter_Formalny, skrot="D")
        liczba_autorow        = 1                    # autor na wierszu, brak through
        liczba_znakow_wydawniczych = 0

    class Praca_Habilitacyjna(Overrides):
        charakter_formalny_id = lookup(Charakter_Formalny, skrot="H")
        liczba_autorow        = 1
        liczba_znakow_wydawniczych = 0
```

## 5. Specyfikacja `Autorzy` (druga unia) + zasada „źródło → unie → trigger"

**Kluczowe odkrycie w trakcie:** `bpp_autorzy_mat` to **osobna materializacja**,
więc ma własną deklarację — NIE flagę `autor_na_wierszu` w `Rekord` (to był
przeciek). „Autor na wierszu publikacji" (doktorat/habilitacja) **wynika** z
tego, że `Praca_Doktorska`/`Praca_Habilitacyjna` są źródłem DWÓCH unii naraz.

```python
class Autorzy(MaterializedUnion):
    key = ["content_type_id", "id"]              # id = ARRAY[ct, pk-wiersza-źródła]
    rekord = fk(Rekord)                           # rekord_id = ARRAY[ct, pk-publikacji]

    sources = [Wydawnictwo_Ciagle_Autor,          # through-table → tylko Autorzy
               Wydawnictwo_Zwarte_Autor,
               Patent_Autor,
               Praca_Doktorska,                    # ← źródło OBU unii (autor na wierszu)
               Praca_Habilitacyjna]               # ← INNER JOIN do bpp_autor

    common_fields = ["autor_id", "jednostka_id", "kolejnosc",
                     "typ_odpowiedzialnosci_id", "zapisany_jako", "zatrudniony",
                     "afiliuje", "dyscyplina_naukowa_id", "upowaznienie_pbn",
                     "profil_orcid", "kierunek_studiow_id", "oswiadczenie_ken",
                     "przypieta", "data_oswiadczenia"]

    class Praca_Doktorska(Overrides):
        join                     = inner("autor")   # FROM publikacja JOIN bpp_autor
        kolejnosc                = 1
        typ_odpowiedzialnosci_id = lookup(Typ_Odpowiedzialnosci, skrot="aut.")
        zapisany_jako            = sql("autor.nazwisko || ' ' || autor.imiona")
        zatrudniony = afiliuje = przypieta = True
        upowaznienie_pbn = profil_orcid = False
        # dyscyplina_naukowa_id, kierunek_studiow_id, oswiadczenie_ken,
        # data_oswiadczenia → NULL auto
    # Praca_Habilitacyjna: analogicznie
```

**Zasada (kasuje flagę):** *trigger tabeli bazowej odświeża każdą unię, której
tabela jest źródłem.* Stąd automatycznie:

- `bpp_praca_doktorska` zasila `Rekord` **i** `Autorzy` → trigger robi upsert do
  `rekord_mat` **i** DELETE+INSERT do `autorzy_mat` (dokładnie semantyka v3
  `AUTOR_NA_WIERSZU_PUBLIKACJI`, ale wyprowadzona, nie zadeklarowana);
- `bpp_wydawnictwo_ciagle_autor` (through) zasila tylko `Autorzy` → rusza tylko
  `autorzy_mat`;
- `bpp_wydawnictwo_ciagle` zasila tylko `Rekord` → rusza tylko `rekord_mat`.

## 6. Audyt wykonalności (czy DA SIĘ wyrazić wszystkie 5 widoków)

**Tak, da się — z dwoma escape-hatchami.** Przeszliśmy realny SQL wszystkich 5
`bpp_*_view` linia po linii:

| Konstrukcja SQL | Przykład (widok) | Składnia | Werdykt |
|---|---|---|---|
| compound id | `ARRAY[(SELECT ct…), id]` | `key=[…]` | ✅ auto |
| passthrough | `base.rok` | `common_fields` | ✅ |
| brak → `NULL::typ` | `NULL::integer AS zrodlo_id` | reguła „pole nieobecne → NULL" (`_meta`) | ✅ auto |
| rename | `wydawca_opis AS wydawnictwo` | `field("wydawca_opis")` | ✅ |
| transform | `lower(doi)` | `lower("doi")` | ✅ |
| agregat z joinu | `count(autor) AS liczba_autorow` | `count("autorzy")` (+auto JOIN/GROUP BY) | ✅ |
| const skalar | `0 AS …`, `1 AS liczba_autorow` | override `= 0` / `= 1` | ✅ |
| const-lookup subquery | `(SELECT id FROM bpp_jezyk WHERE skrot='pol.')` | `lookup(Jezyk, skrot="pol.")` | ✅ helper |
| normalizacja stringa | `TRIM(replace(replace(replace(isbn…))))` | `strip("isbn","-"," ",".")` | ⚠️ helper/escape |
| FROM/JOIN/GROUP BY | `LEFT JOIN through GROUP BY` | wynika z obecności `count()` | ✅ auto |

**Granice „związania z Django" (uczciwie):**

1. `lookup()`/`strip()`/`sql()` to **escape-hatche** — w środku surowy SQL;
   walidowana tylko nazwa pola/modelu, reszta „na słowo". Nieuchronny ogon
   ~10% kolumn (dokładnie te, które spec nazywał „stała-podzapytanie" i
   „computed string"). Reszta (90%) w pełni związana i sprawdzana.
2. **Framework ODSŁANIA niespójność, którą ręczny SQL ukrywał:** `isbn` na
   `zwarte` ma `TRIM(BOTH FROM replace(...))`, a na `doktorat`/`habilitacja`
   `replace(...)` **bez** `TRIM`. Pięć osobnych plików to przykryło; jedno
   `strip("isbn")` wymusza decyzję: ujednolicić (pewnie pożądane) czy świadomie
   różnicować per-typ. Zaleta (spójność), ale *zmiana zachowania* do
   świadomego podjęcia.

## 7. Model migracji (jak Django miałby tym zarządzać)

Dziś `Rekord` jest `managed = False` → `makemigrations` **nigdy** nic dla niego
nie generuje. **To jest dosłownie powód, dla którego wszystko jest ręcznym
SQL-em.** Framework musiałby dołożyć WŁASNĄ integrację z migracjami:

| Model | Jak | Plus | Minus |
|---|---|---|---|
| (a) Autodetektor | hook w `makemigrations` → auto-operacja `AlterMaterializedUnion` | czuje się natywnie | najwięcej kodu; walka z model-centrycznym autodetektorem (robi tak `django-pgtrigger`) |
| **(b) Własna komenda** ⭐ | `manage.py make_rekord_migration` diffuje deklarację vs snapshot i pisze **samodzielną** migrację z DDL-em | realne, odwracalne, self-contained; `system check` pilnuje driftu | osobna komenda |
| (c) `sync()` idempotentny | migracja `RunPython(Rekord.sync)` robi `CREATE OR REPLACE` do stanu z kodu | trywialne | historia migracji „rozmyta", słaba odwracalność |

**Rekomendacja: (b).** To generalizacja tego, co `0432`/`0433` robią ręcznie
(introspekcja stanu → wypiekanie samodzielnego DDL). Jedna zmiana deklaracji
dotyka tabeli + 5 widoków + 16 funkcji + 8 triggerów + bramki naraz — dlatego
to nie może być zwykły model; framework liczy cały delta-DDL z deklaracji.
Prior art: `django-pgtrigger` (triggery+migracje), `django-pgviews-redux`
(widoki+migracje) — łączymy oba dla unii.

## 8. Decyzja i uzasadnienie „czemu nie"

Odpowiedzi użytkownika na 3 pytania decydujące:

- zmiany **rzadkie**,
- churn **nie blokuje**,
- OSS **kuszące, ale niepewny popyt**.

Wszystkie 3 na „nie"/„nie wiem" → **nie budować**. Dodatkowo:

- **koszt i ryzyko skoncentrowane w najgorszym miejscu** — generator siadałby
  pod `bpp_rekord_mat`/`bpp_autorzy_mat`, najczęściej odpytywanymi tabelami;
  bug = cicha korupcja cache'a. Obecny SQL jest brzydki, ale wyklepany i
  zamrożony;
- **najtrudniejsza część (tooling migracji) daje najmniej splendoru i najwięcej
  okazji do subtelnych pomyłek** (odwracalność, baseline, drift);
- **większość wartości triggerowej już wyciągnięta tanio** w PR #363;
- **YAGNI** — realny ból to „cicha literówka" (10% kosztu frameworka), nie cała
  abstrakcja.

> Uwaga o biasie: autor designu (Claude) ma naturalny bias, żeby chcieć go
> zbudować. Świadomie ciągnięto w drugą stronę. Elegancja „źródło → unie →
> trigger" jest prawdziwa, ale to nie ROI.

## 9. Droga środka (gdyby ból kiedyś doskwierał, ~10% kosztu)

1. **Test / `system check` walidujący, że widoki zgadzają się z modelami** —
   każda kolumna `base.x` w widoku istnieje na modelu, typy się zgadzają.
   Zabija „cichą literówkę" (główny ból) bez frameworka. (~kilka godzin.)
   *Robić tylko jeśli drift widok↔model kiedyś realnie wywołał błąd — inaczej
   rozwiązuje problem, którego nie ma.*
2. **Mały helper do regeneracji 5 widoków z jednej listy kolumn**, używany
   *gdy* zmieniasz widok; generujesz SQL, wklejasz do normalnej migracji.
   Bez autodetektora, bez komendy-migracji. (~dzień.)
3. Zostaw standardowe migracje SQL — czytelne dla każdego znającego Postgresa.

## 10. Wstępny plan „GDYBYM kiedyś chciał to mieć" (pełny framework)

Kolejność, gdyby któraś dźwignia z §11 się odwróciła:

1. **PoC bez migracji-toolingu** — klasa `MaterializedUnion` + `Overrides` +
   `_meta`-driven NULL/typ + helpery (`field`/`lower`/`count`/`lookup`/`strip`/
   `sql`/`inner`). Metoda `.sync()` (CREATE OR REPLACE wszystkiego). Generuje
   `Rekord` i `Autorzy`. **Test złoty: wygenerowany DDL == obecny baseline**
   (widoki + tabele + triggery identyczne md5/diff). To dowodzi, że abstrakcja
   pokrywa realny stan, zanim dołożymy tooling.
2. **System check** — walidacja nazw pól (`_meta`) + spójność typów. To samo
   gardło, co łapie literówkę.
3. **Generacja triggerów + bramki + kanarka z deklaracji** — przenieś logikę z
   `0432`/`0433` tak, by brała rodzaje kolumn (passthrough/agg/derived/const)
   z deklaracji zamiast z `pg_depend`. Zasada „źródło → unie → trigger".
4. **Tooling migracji (opcja b)** — `manage.py make_<union>_migration`:
   diff deklaracji vs snapshot → samodzielna, odwracalna migracja
   (ALTER TABLE + CREATE OR REPLACE VIEW/FUNCTION + (re)CREATE TRIGGER + bramka).
   `system check` ostrzega o driftcie „deklaracja zmieniona, brak migracji".
5. **Decyzja o `bpp_rekord` UNION-view** — usunąć (jeśli szczątkowy) albo
   generować jako `UNION ALL` źródeł.
6. **(jeśli OSS)** wydzielić pakiet (`django-materialized-union`?), matrix
   testów (Python × Django × PG), README z niszą „IVM dla UNION-a, którego
   pg_ivm nie daje". **Najpierw zmierzyć popyt, potem dorabiać tooling.**

## 11. Kiedy wrócić do tematu

Zmienić decyzję, gdyby zaszło którekolwiek:

- **(a)** widoki zaczynają się zmieniać **często** (np. co sprint dokładasz
  kolumny) → ergonomia wygrywa;
- **(b)** pojawia się **realny sygnał popytu OSS** (ludzie pytają o
  „materialized UNION w Django / IVM dla unii") → koszt liczony jak produkt;
- **(c)** ręczny churn SQL **realnie blokuje** (traci czas / wprowadza bugi co
  sprint), nie tylko „jest brzydki".

## 12. Co już jest zrobione (żeby przyszłe-JA wiedziało)

PR **#363** (`feat/refresh-cache-plpgsql`, merge do dev) dostarczył **połowę
triggerową** tej wizji, niezależnie od frameworka:

- `0432_cache_trigger_plpgsql.py` — generator: 16 funkcji PL/pgSQL (8 refresh +
  8 delete, 5 rekord + 3 through) z introspekcji kolumn, semantyka v3 dokładna;
- `0433_cache_trigger_when_gate.py` — bramka WHEN z `pg_depend`;
- `test_cache_plpgsql_port.py` — kanarek staleności (`mat == widok`, pułapka
  rename `wydawca_opis`) + skip bramki (przez `ctid`, nie `xmin`!);
- `test_cache_plpgsql_benchmark.py` — VC vs V0: ~2,2–2,7× szybciej, md5
  identyczny.

Czyli mechanizm generowania triggerów/bramki/kanarka z introspekcji **istnieje i
jest przetestowany** — framework musiałby go tylko *sparametryzować deklaracją*
zamiast `pg_depend`. To istotnie obniża koszt kroku 3 z planu (§10).

## Otwarte kwestie do weryfikacji (gdyby wejść)

- Czy `bpp_rekord` (UNION-view) / `RekordView` da się usunąć — wygląda na
  wymarły (jedna relacja FK + komentarz), ale wymaga sprawdzenia.
- Decyzja o `isbn` `TRIM`: ujednolicić zwarte vs doktorat/habilitacja czy
  świadomie różnicować (patrz §6.2).
- Składnia źródła through-table vs publikacji (`join = inner("autor")`) —
  doprecyzować, jak framework rozpoznaje „autor na wierszu" z `sources`.
