# Import patentów — UI kreatora (dokończenie #517) — design

> Status: zaakceptowany kierunek (brainstorming 2026-07-11). Ten dokument
> domyka Track B handoffu `2026-07-10-importer-patenty-www-dspace-listy.md`
> (punkt „(d) plumbing wizarda") — reszta Track B (fundament) już wylądowała
> na gałęzi `feat-patenty-bibtex-import`.

## Cel

Uczynić ścieżkę importu patentów (`bpp.Patent`) **osiągalną i użyteczną** z
poziomu kreatora `importer_publikacji`. Dziś fundament (mapowanie `@patent`,
`_create_patent`, trzecia gałąź dispatchu, pole `ImportSession.rodzaj_rekordu`,
migracja 0018, wykluczenie D/H/PAT z `VerifyForm`) jest na gałęzi, ale **nic
nigdy nie ustawia `rodzaj_rekordu = PATENT`**, więc `_create_patent` jest
martwym kodem, a krok Verify wymaga `charakter_formalny`/`typ_kbn` (bez sensu
dla patentu). Ten spec dokłada brakujące plumbing wizarda.

## Kontekst — stan „fundamentu" (już na gałęzi, NIE zmieniamy tego zakresu)

- `providers/bibtex.py`: `BIBTEX_TYPE_MAP["patent"] = "patent"`; `fetch()`
  czyta pola biblatex `@patent` (`number`→`patent_number`, `holder`→
  `patent_holder`, `date`→`filing_date`, `location`→`jurisdiction`,
  `type`→`patent_type`).
- `tasks.py::_store_normalized_data`: przepisuje pola patentowe do
  `session.normalized_data` (`patent_number`, `patent_grant_number`,
  `filing_date`, `grant_date`, `patent_type`, `patent_holder`, `jurisdiction`).
- `views/publikacja.py::_create_patent`: buduje `bpp.Patent`, odfiltrowuje
  `typ_kbn`/`charakter_formalny`/`jezyk`/`doi`/`issn`/`e_issn` z
  `common_fields`, wypełnia `numer_zgloszenia`/`data_zgloszenia`/
  `numer_prawa_wylacznego`/`data_decyzji`/`rodzaj_prawa` (best-effort po
  nazwie z `patent_type`), uprawnionego wrzuca do `informacje`.
- `views/publikacja.py::_create_publication`: dispatch trójstronny —
  `session.rodzaj_rekordu == PATENT` → `_create_patent`, inaczej binarnie po
  `jest_wydawnictwem_zwartym`.
- `forms.py::VerifyForm`: `charakter_formalny` queryset wyklucza
  `skrot__in=["D","H","PAT"]` (niezależny bugfix — patent nie może być wybrany
  jako charakter na ścieżce Wydawnictwo_*).

## Model `Patent` — impedancja (fakty)

`Patent` (`bpp/models/patent.py`) dziedziczy m.in. `ModelZRokiem`,
`ModelPunktowany`, `ModelZeStatusem`, `ModelZeSzczegolami`, `ModelZAdnotacjami`,
`ModelZInformacjaZ`, `DodajAutoraMixin`. Ma:

- `tytul_oryginalny` (pojedynczy tytuł), `rok`, `punkty_kbn`
  (z `ModelPunktowany`);
- `data_zgloszenia` (`DateField`, null/blank), `numer_zgloszenia`
  (`CharField`, null/blank), `data_decyzji` (`DateField`, null/blank),
  `numer_prawa_wylacznego` (`CharField`, null/blank);
- `rodzaj_prawa` (FK `Rodzaj_Prawa_Patentowego`, null/blank);
- `wdrozenie` (`BooleanField`, null/blank, default None);
- `wydzial` (FK `Jednostka`, SET_NULL, null/blank);
- `informacje` (z `ModelZInformacjaZ`) — tu ląduje „uprawniony".

**Nie ma:** `typ_kbn` (brak `ModelTypowany`), settable `charakter_formalny`
(zahardkodowany `@cached_property` → `Charakter_Formalny(skrot="PAT")`),
settable `jezyk` (zahardkodowany → „polski"), `zrodlo`, `wydawca`, pola
„holder/uprawniony". Autorzy: `dodaj_autora()` (przez `Patent_Autor`) działa
**bez zmian** — krok Authors nie wymaga modyfikacji.

## Decyzje produktowe (z brainstormingu)

1. **Detekcja patentu = auto z `@patent` + możliwość zmiany.** Auto-set
   `rodzaj_rekordu = PATENT` gdy `publication_type == "patent"`; operator może
   przełączyć typ w kroku Verify (trój-drożne radio).
2. **Ścieżka patentu:** `Fetch → Verify(patent) → Authors → Punktacja →
   Review → Create → Done`. Kroki **Source i PBN pominięte** (bezsensowne dla
   patentu — brak źródła/wydawcy; patentów nie wysyłamy do PBN).
3. **Punktacja:** krok zachowany, ale **bez sugestii ze źródła** (patent nie
   ma źródła) — operator wpisuje `punkty_kbn` ręcznie.
4. **Układ pól:** pola patentowe **warunkowo w kroku Verify** (jeden krok),
   pokazywane/chowane po wyborze typu rekordu (bez round-tripu serwera).
5. **PBN:** patentów **nie** wysyłamy do PBN — brak kroku PBN, brak opcji
   „Zapisz i wyślij do PBN" na Review, brak linkowania `pbn_uid` przy create.

## Architektura formularza — podejście A (wybrane)

Rozszerzamy istniejący `VerifyForm` (jeden formularz, warunkowa walidacja).
Odrzucone podejście B (osobny `PatentVerifyForm` + round-trip HTMX na przełącz)
— więcej plików i round-tripów, duplikacja pola `rok`.

### `VerifyForm` — zmiany

- **Nowe pole `rodzaj_rekordu`** — `ChoiceField(RadioSelect)` z opcjami
  `CIAGLE`/`ZWARTE`/`PATENT` (etykiety: „Wydawnictwo ciągłe" / „Wydawnictwo
  zwarte (książka/rozdział)" / „Patent"). **Zastępuje** dotychczasowy boolean
  `jest_wydawnictwem_zwartym` w UI (boolean pozostaje wyliczany z radia w
  widoku — patrz niżej, back-compat downstream).
- **`charakter_formalny` / `typ_kbn` / `jezyk`** — z `required=True` na
  `required=False`; wymagalność egzekwowana warunkowo w `clean()` (wymagane
  tylko gdy `rodzaj_rekordu != PATENT`).
- **Nowe pola patentowe (wszystkie `required=False`):**
  - `numer_zgloszenia` — `CharField(max_length=255)`
  - `data_zgloszenia` — `DateField(widget=DateInput(type="date"))`
  - `numer_prawa_wylacznego` — `CharField(max_length=255)`
  - `data_decyzji` — `DateField(widget=DateInput(type="date"))`
  - `rodzaj_prawa` — `ModelChoiceField(Rodzaj_Prawa_Patentowego.objects.all())`
    (zwykły dropdown — słownik jest mały)
  - `uprawniony` — `CharField(max_length=512)` (mapowane do
    `normalized_data["patent_holder"]` → `informacje`)
  - `wdrozenie` — `NullBooleanField(widget=NullBooleanSelect)` (model ma
    `BooleanField(null=True, default=None)` — „brak danych" ≠ „nie wdrożono";
    checkbox zgubiłby stan None, więc trój-stanowy select)
  - `wydzial` — `ModelChoiceField(Jednostka.objects.all(), required=False)`;
    **widget renderowany ręcznie w szablonie** jako goły `<select data-url=
    "bpp:jednostka-autocomplete">` + ręczna inicjalizacja select2 (NIE DAL-owy
    `ModelSelect2` — patrz uwaga o hidden-div w sekcji szablonu)
- **`rok`** — bez zmian (`required=True`, dotyczy wszystkich typów).

### `clean()` — walidacja warunkowa

- `rodzaj_rekordu == PATENT`: nie wymagaj `charakter_formalny`/`typ_kbn`/
  `jezyk`; `rok` wymagany (już). Pola patentowe pozostają opcjonalne — model
  `Patent` dopuszcza null we wszystkich poza `tytul_oryginalny`/`rok`.
- `rodzaj_rekordu != PATENT`: wymagaj `charakter_formalny`/`typ_kbn`/`jezyk`
  (dodaj `add_error` gdy puste) — zachowanie sprzed zmiany.

### Szablon `partials/step_verify.html`

- Radio `rodzaj_rekordu` na górze.
- Dwie grupy pól: **standardowa** (`charakter_formalny`, `typ_kbn`, `jezyk` +
  ewentualnie dotychczasowe podpowiedzi auto) i **patentowa** (8 pól). `rok`
  poza grupami (zawsze widoczny).
- Pokazywanie/chowanie grup **JS-em**. Toggle musi odpalić się **także na
  load** (nie tylko `onchange`) — po błędzie walidacji bound form z radiem
  PATENT musi od razu pokazać grupę patentową (WAŻNE r2). Pola ukrytej grupy
  mają `required=False`, więc nie generują fałszywych błędów walidacji.
- **`wydzial` (autocomplete) — uwaga na select2/HTMX/hidden-div (WAŻNE r2):**
  `step_verify.html` dziś **nie ma** `{{ form.media }}` (w odróżnieniu od
  `step_source.html`), a select2 inicjalizowany w `display:none` renderuje się
  z szerokością 0 i grozi podwojeniem widżetu przy swapach HTMX (znany problem
  projektu — patrz `helpers._is_htmx_partial`). Dlatego `wydzial` **nie**
  używa DAL-owego `ModelSelect2` w tym kroku, tylko in-projektowego wzorca
  ręcznej inicjalizacji gołego `<select data-url=...>` (jak `step_source.html`,
  sekcja ~171–203): render zwykłego `<select>` z `data-url` na
  `bpp:jednostka-autocomplete`, inicjalizacja select2 z `width:'100%'`
  **po pokazaniu grupy patentowej** (init-on-show), z guardem przeciw podwójnej
  inicjalizacji. (`ModelChoiceField` w Pythonie zostaje — chodzi tylko o widget
  po stronie szablonu.)

## Przepływ — rozgałęzienia patent-aware

Przejścia są rozproszone po `post()` handlerach ORAZ w `get_continue_url`
(wznowienie z listy/paczki) i w przyciskach „Wstecz" w szablonach. „Trzy
punkty" z pierwszej wersji specu były niewystarczające (review r1) — pełny
zestaw punktów patent-aware:

1. **`VerifyView.post`** — po zapisaniu:
   - `session.rodzaj_rekordu = form.cleaned_data["rodzaj_rekordu"]`;
   - `session.jest_wydawnictwem_zwartym = (rodzaj == ZWARTE)` (back-compat:
     downstream — dispatch, punktacja — nadal czyta boolean);
   - gdy PATENT: `charakter_formalny=None`, `typ_kbn=None`, `jezyk=None`
     (Patent i tak je hardkoduje); zapisz edytowane pola patentowe do
     `normalized_data`; **wyczyść stale pola nie-patentowe** (patrz „Toggle"
     niżej); `return _render_authors_step(...)` — **pomija Source**;
   - inaczej: dotychczasowe zapisy + `return _render_source_step(...)`.
2. **`PunktacjaView.post`** — po zapisie `punkty_kbn`:
   - gdy PATENT: `return _render_review_step(...)` — **pomija PBN**;
   - inaczej: dotychczasowa logika (`provider == "PBN"` → Review, else PBN).
3. **`ImportSession.get_continue_url`** (`models.py`) — **czwarty router**,
   używany przez listę sesji, widok paczki, idempotency w `FetchView.post`
   i `BatchEntryImportView`. Dziś mapuje `VERIFIED→source`, `PUNKTACJA→pbn`.
   Dodać gałąź patentową: gdy `rodzaj_rekordu == PATENT` → nadpisz
   `VERIFIED→"authors"` i `PUNKTACJA→"review"`. Bez tego każda przerwana i
   wznowiona sesja patentowa ląduje w Source/PBN. `models.py` **wchodzi do
   plików do zmiany.**
4. **`steps.py::_review_context`** — gdy PATENT: `back_step = "punktacja"`
   (pomija PBN wstecz) i **nie** ustawiaj `show_save_and_pbn`.
5. **`step_authors.html` — przycisk „Wstecz"** (linia ~206) hardkoduje
   `url 'importer_publikacji:source'`. Dla patentu Source jest pominięty —
   zrobić warunkowo: patent → `verify`, inaczej → `source`. Kontekst kroku
   Authors dostaje flagę `is_patent` (`_authors_context`).
6. **Guardy widoków Source/PBN** (defense-in-depth): gdy `session.rodzaj
   _rekordu == PATENT`, `get`/`post` **przekierowują** zamiast przetwarzać —
   jednoznacznie `return _hx_or_redirect(request, session.get_continue_url())`
   (helper już istnieje, `wizard.py:105`; `get_continue_url` po gałęzi
   patentowej zwraca właściwy krok — Authors/Review). Objąć **wszystkie**
   widoki tych kroków: `SourceView`, `PbnCheckView`, `PbnSelectView`,
   `PbnClearView` (stale karta mogłaby POST-nąć `PbnSelectView` i wpisać
   `pbn_mongo_id` po wyczyszczeniu — guard `_link_pbn_uid` i tak chroni create,
   ale domykamy deklarowane „guardy widoków PBN"). Bez guardu `SourceView.post`
   zapisałby `zrodlo`+`status=SOURCE_MATCHED` na sesji patentowej (korupcja).
   Guard jest warunkowany `rodzaj_rekordu` — **nie** blokuje cofnięcia dla
   nie-patentu.

## Toggle typu rekordu — czyszczenie stale stanu (KRYTYCZNE)

Scenariusz: Verify(CIAGLE) → Source (ustawia `zrodlo`/`wydawca`) → ewentualnie
PBN (ustawia `matched_data["pbn_mongo_id"]`) → powrót do Verify →
przełączenie na PATENT. Bez czyszczenia stale wartości powodują:

- `_create_publication` wywołałby `uzupelnij_punktacje_z_zrodla(patent,
  zrodlo, rok)` — punktacja czasopisma wlana do patentu;
- `_punktacja_context` pokazałby `punktacja_zrodla` (warunek `not zwarte and
  zrodlo`);
- **twardy błąd**: stale `pbn_mongo_id` → `_link_pbn_uid` wykona
  `record.pbn_uid = ...; record.save(...)`, a **`Patent` NIE MA pola
  `pbn_uid`** (tylko legacy `pbn_id` z `ModelZPBN_ID`; `ModelZPBN_UID` mają
  wyłącznie `Wydawnictwo_Ciagle/Zwarte`) → create task się wywali.

**Fix (dwa poziomy):**

- **W `VerifyView.post` gałąź PATENT:** wyczyść `session.zrodlo=None`,
  `wydawca=None`, `wydawnictwo_nadrzedne=None`,
  `wydawnictwo_nadrzedne_w_pbn=None`, oraz z `matched_data` popnij
  `pbn_mongo_id` i `wydawca_opis` (jedyne klucze zapisywane przez Source/PBN;
  `pbn_url` NIE jest zapisywany do `matched_data` — do wyczyszczenia zostaje
  tylko `pbn_mongo_id`).
- **W `_create_publication` (twardy guard, niezależny od toggle):** wołaj
  `_link_pbn_uid(session, record)` **tylko gdy `rodzaj_rekordu != PATENT`**.
  To robust fix na wypadek dowolnej ścieżki, nie tylko toggle. Analogicznie
  `uzupelnij_punktacje_z_zrodla` jest już strzeżone `if session.zrodlo` —
  z wyczyszczonym `zrodlo` nie odpali; guard pozostaje.

## Punktacja dla patentu

`steps.py::_oblicz_sugestie` dostaje gałąź patentową na początku: gdy
`session.rodzaj_rekordu == PATENT` → zwróć `(SugestiaPunktacji(None,
rodzaj_braku=RodzajBraku.BRAK_DANYCH_ZRODLA, powod_braku="Patent nie ma
źródła — brak sugestii punktacji"), None)`. `BRAK_DANYCH_ZRODLA` to
anomalia DANYCH (mapowana na skip+raport), a **nie**
`NIEOBSLUZONA_KOMBINACJA` (mapowana na twardy `NotImplementedError` w
komendzie współdzielącej ten moduł). Formularz `PunktacjaForm` (jedno pole
`punkty_kbn`) i
`PunktacjaView.post` (zapis do `matched_data["punkty_kbn"]`) — bez zmian, poza
rozgałęzieniem następnego kroku (patrz wyżej). Szablon kroku pokazuje pole
ręczne; blok „punktacja ze źródła" nie renderuje się, bo `punktacja_zrodla`
jest `None` dla patentu (brak `zrodlo`).

## Kontrakt `normalized_data` (patentowe klucze)

`VerifyView.post` (gałąź PATENT) zapisuje edycje operatora do
`session.normalized_data`, a `_create_patent` je odczytuje — jedno źródło
prawdy, spójne z resztą importera:

| klucz normalized_data      | pole formularza        | pole modelu `Patent`      |
|----------------------------|------------------------|---------------------------|
| `patent_number`            | `numer_zgloszenia`     | `numer_zgloszenia`        |
| `filing_date` (ISO str)    | `data_zgloszenia`      | `data_zgloszenia`         |
| `patent_grant_number`      | `numer_prawa_wylacznego`| `numer_prawa_wylacznego` |
| `grant_date` (ISO str)     | `data_decyzji`         | `data_decyzji`            |
| `rodzaj_prawa_id`          | `rodzaj_prawa`         | `rodzaj_prawa` (FK)       |
| `wdrozenie` (bool\|None)   | `wdrozenie`            | `wdrozenie`               |
| `wydzial_id`               | `wydzial`              | `wydzial` (FK)            |
| `patent_holder`            | `uprawniony`           | `informacje` (prefiks „Uprawniony: ") |
| `year`                     | `rok`                  | `rok`                     |

Daty zapisywane jako string ISO `YYYY-MM-DD` (JSON-owalne); `_create_patent`
parsuje je przez istniejące `_parse_iso_date`.

## Zmiany w `_create_patent`

`_create_patent` czyta **wyłącznie jawne** wartości z `normalized_data`
(ustawiane przez `VerifyView.post` — Verify jest zawsze wykonywany przed
create na ścieżce patentu). Best-effort dopasowanie po nazwie (`patent_type`)
przenosi się **do prefillu Verify**, NIE do create — inaczej operator, który
świadomie wyczyścił dropdown, dostałby wskrzeszoną wartość (WAŻNE r2):

- `rodzaj_prawa`: `normalized_data.get("rodzaj_prawa_id")` → `Rodzaj_Prawa
  _Patentowego.objects.filter(pk=...).first()` (None gdy klucz None/brak).
  **Bez** fallbacku do `patent_type` w create.
- `wdrozenie`: `normalized_data.get("wdrozenie")` (bool | None — `None` = nie
  ustawiaj; `NullBooleanField` zachowuje rozróżnienie None/False w JSON).
- `wydzial`: `normalized_data.get("wydzial_id")` → `Jednostka.objects
  .filter(pk=...).first()`.

Uprawniony (`informacje`) — fundament wrzuca „Uprawniony: X"; wartość pochodzi
teraz z edytowalnego pola. **Jurysdykcja** (`normalized_data["jurisdiction"]`,
z biblatex `location`) — fundament ją wyciąga, ale nikt nie zapisywał (cichy
data-drop, WAŻNE r2): dopisać do `informacje` analogicznie („Kraj: X") gdy
obecna, żeby dane ze źródła nie ginęły. `jurisdiction` nie dostaje osobnego
pola formularza (model nie ma takiego pola) — traktujemy jak uprawnionego.

Dodatkowo do listy odfiltrowywanych kluczy `common_fields` dopisać **`tytul`**:
`_create_publication` dokłada `common_fields["tytul"]` gdy istnieje
`original_title`, a `Patent` jest jedno-tytułowy (nie ma pola `tytul`) →
przekazanie rzuciłoby `TypeError`. Dziś martwe dla BibTeX (brak
`original_title`), ale filtr ma być kompletny na wypadek innych źródeł.

## Prefill kroku Verify (patent)

`steps.py::_verify_context`: gdy `form is None` i `rodzaj_rekordu == PATENT`,
initial buduj z `normalized_data`. Prefill musi czytać **najpierw jawne klucze
zapisane przez poprzedni submit**, z fallbackiem na wartości BibTeX — inaczej
powrót do Verify po pierwszym zapisie nadpisze wybory operatora pustymi (WAŻNE
r2):

- `numer_zgloszenia=patent_number`, `data_zgloszenia=filing_date`,
  `numer_prawa_wylacznego=patent_grant_number`, `data_decyzji=grant_date`,
  `uprawniony=patent_holder`, `rok=year`, `rodzaj_rekordu=PATENT` — te używają
  tych samych kluczy przy POST i prefillu, więc round-trip zachowuje wartość.
- `rodzaj_prawa`: `normalized_data.get("rodzaj_prawa_id")` gdy obecny (nawet
  `None` = operator wyczyścił → puste); **tylko gdy klucz nieobecny** (pierwsze
  wejście) fallback do best-effort `_resolve_rodzaj_prawa(patent_type)`.
- `wdrozenie`: `normalized_data.get("wdrozenie")` gdy klucz obecny; inaczej
  puste (BibTeX go nie ma).
- `wydzial`: `normalized_data.get("wydzial_id")` gdy obecny; inaczej puste.

Kluczowe rozróżnienie: „klucz nieobecny" (pierwszy raz — dozwolony best-effort)
vs „klucz obecny z `None`" (operator świadomie wyczyścił — uszanuj puste).

Dla nie-patentu initial jak dziś, plus `rodzaj_rekordu` = `ZWARTE` gdy
`jest_wydawnictwem_zwartym` (z sesji lub z mappera CrossRef), inaczej `CIAGLE`.

## Detekcja przy fetchu

`tasks.py`: po `_store_normalized_data` / w `_auto_match_type_and_language` —
gdy `result.publication_type == "patent"`: `session.rodzaj_rekordu =
ImportSession.RodzajRekordu.PATENT`. Jedyny auto-set; wszystko inne pozostaje
`CIAGLE` (default). `_get_crossref_mapper("patent")` zwraca `None` (patent nie
jest typem CrossRef), więc `charakter_formalny`/`jest_wydawnictwem_zwartym` nie
są auto-ustawiane — operator zobaczy patentowy Verify.

## Create — guardy modelowe (review r1 + r2)

`_create_publication` woła kilka helperów zakładających model `Wydawnictwo_*`.
Patent (`bpp.Patent`) odstaje — cztery miejsca wymagają guardu:

1. **`_link_pbn_uid`** (PBN): wołać **tylko gdy `rodzaj_rekordu != PATENT`**.
   `Patent` nie ma pola `pbn_uid` — bez guardu stale `pbn_mongo_id` (toggle)
   wywala create task. Nadrzędny, robust fix.
2. **`_create_streszczenia`** (BLOKER r2): wołać **tylko gdy `rodzaj_rekordu
   != PATENT`**. Funkcja robi `record.streszczenia.create(...)`, a related
   name `streszczenia` istnieje **wyłącznie** na `Wydawnictwo_Ciagle/Zwarte` —
   `Patent` go nie ma. BibTeX czyta `abstract` też dla `@patent` (typowy
   eksport Zotero), `_store_normalized_data` buduje `abstracts` → bez guardu
   `@patent` z abstraktem = `AttributeError` w create. (Streszczenia patentu są
   poza zakresem — model ich nie wspiera.)
3. **`CreateView.post` → `also_pbn`**: `also_pbn = "_create_and_pbn" in
   request.POST and session.rodzaj_rekordu != PATENT`. Chroni przed replayem
   POST ze starej karty / ręcznym POST.
4. **`step_review.html`**: przycisk „Zapisz i wyślij do PBN"
   (`name="_create_and_pbn"`) renderowany tylko gdy `show_save_and_pbn` —
   `_review_context` nie ustawia go dla patentu, więc przycisk znika.

`uzupelnij_punktacje_z_zrodla` jest już strzeżone `if session.zrodlo` — z
wyczyszczonym `zrodlo` (toggle) nie odpali; guard pozostaje.

## Review — render dla patentu (`step_review.html`)

Krok „Przegląd końcowy" dziś renderuje „Typ rekordu" binarnie z
`jest_wydawnictwem_zwartym` (patent pokazałby się jako „Wydawnictwo ciągłe")
i nie pokazuje żadnych pól patentowych — operator zatwierdzałby w ciemno.
Zmiany:

- „Typ rekordu": gdy `session.rodzaj_rekordu == PATENT` → „Patent".
- Dodać sekcję pól patentowych (widoczną tylko dla patentu): numer zgłoszenia,
  data zgłoszenia, numer prawa wyłącznego, data decyzji, rodzaj prawa,
  uprawniony, wdrożenie, wydział — czytane z `session.normalized_data` /
  rozwiązane FK. Bloki źródła/wydawcy/PBN nie renderują się dla patentu (brak
  `zrodlo`/`wydawca`/`show_save_and_pbn`).
- `step_review.html` **wchodzi do plików do zmiany.**

Kosmetyka (DROBNE r2): partiale mają zahardkodowane numery kroków w nagłówkach
(„Krok 2/3/4/5"). Ścieżka patentu pomija „Krok 3" (Source), więc numeracja się
rozjedzie (2 → 4). W dotykanych szablonach (`step_verify`, `step_authors`,
`step_review`) zneutralizować nagłówki do form bez numerów (jak krok Punktacja/
PBN, które już są bez-numerowe) zamiast łatać numerację warunkowo.

## Duplikaty — świadomość modelu `Patent`

`steps.py::_find_duplicates` przeszukuje dziś tylko `Wydawnictwo_Ciagle/Zwarte`.
Dołożyć `Patent` do wyszukiwania po tytule (patent nie ma DOI, więc tylko
`tytul_oryginalny__iexact`), żeby ponowny import tego samego `@patent`
ostrzegał o istniejącym rekordzie. Drobne, ale tanie i poprawne.

## Testy (TDD)

1. **Detekcja:** fetch `@patent` → `session.rodzaj_rekordu == PATENT`;
   fetch `@article` → `CIAGLE`.
2. **`VerifyForm`:** tryb PATENT waliduje **bez** `charakter_formalny`/
   `typ_kbn`/`jezyk`; tryb CIAGLE/ZWARTE nadal je **wymaga** (błąd gdy puste).
3. **`VerifyView.post` patent:** pomija Source → renderuje Authors; zapisuje
   pola patentowe do `normalized_data` (wg tabeli kontraktu); ustawia
   `rodzaj_rekordu=PATENT`, `jest_wydawnictwem_zwartym=False`.
4. **Toggle:** POST z `rodzaj_rekordu=CIAGLE` na sesji auto-wykrytej jako
   patent → wchodzi w ścieżkę Source (przełączenie działa) i odwrotnie.
5. **`PunktacjaView.post` patent:** → Review (pomija PBN).
6. **`_review_context` patent:** brak `show_save_and_pbn`, `back_step ==
   "punktacja"`.
7. **`_oblicz_sugestie` patent:** zwraca „brak sugestii" bez sięgania po
   `zrodlo`/`wydawca`.
8. **`_create_patent`:** czyta `rodzaj_prawa_id`/`wdrozenie`/`wydzial_id`;
   `rodzaj_prawa_id` ma pierwszeństwo nad `patent_type` po nazwie.
9. **Integracyjny (pełny flow):** BibTeX `@patent` → przejście Verify(patent)
   → Authors → Punktacja → Review → Create → powstaje `bpp.Patent` z
   ustawionymi polami, autorami, `punkty_kbn`, „Uprawniony: …" w `informacje`.
10. **Migracja istniejących testów Verify:** POST-y przechodzą z
    `jest_wydawnictwem_zwartym` na `rodzaj_rekordu` (blast radius podejścia A).
11. **`get_continue_url` patent:** sesja patentowa w `VERIFIED` → URL kroku
    `authors` (nie `source`); w `PUNKTACJA` → `review` (nie `pbn`).
12. **Guardy Source/PBN:** GET i POST na `SourceView`/`PbnCheckView` dla sesji
    patentowej → przekierowanie (nie zapis `zrodlo`/`SOURCE_MATCHED`).
13. **Toggle po Source:** sesja z ustawionym `zrodlo` + `pbn_mongo_id`
    przełączona na PATENT w Verify → `zrodlo`/`pbn_mongo_id` wyczyszczone;
    create **nie** woła `uzupelnij_punktacje_z_zrodla` ani `_link_pbn_uid`
    (patent powstaje bez błędu mimo braku pola `pbn_uid`).
14. **`_create_and_pbn` wymuszony w POST dla patentu:** `CreateView.post`
    ignoruje `also_pbn` (patent nie idzie do eksportu PBN).
15. **Render Review patentu:** kontekst/HTML pokazuje „Patent" jako typ i pola
    patentowe; brak przycisku „Zapisz i wyślij do PBN".
16. **`wdrozenie` trój-stan:** puste → `None`, „tak" → `True`, „nie" →
    `False` (nie gubi None jak checkbox).
17. **Duplikat patentu:** ponowny `@patent` o istniejącym `tytul_oryginalny`
    → `_find_duplicates` zwraca istniejący `Patent`.
18. **Patent z abstraktem (BLOKER r2):** `@patent` z polem `abstract` →
    create **nie** wywala się na `record.streszczenia` (guard); `Patent`
    powstaje, streszczenie pominięte.
19. **Round-trip prefill:** operator ustawia `rodzaj_prawa`/`wdrozenie`/
    `wydzial`, zapisuje (→ Authors), wraca do Verify → formularz pokazuje
    zapisane wartości (nie best-effort/puste); ponowny submit ich nie gubi.
20. **Wyczyszczenie `rodzaj_prawa`:** operator kasuje dropdown (był best-effort)
    → po zapisie `rodzaj_prawa_id=None`; create tworzy `Patent` z
    `rodzaj_prawa=None` (fallback po nazwie NIE wskrzesza wartości).
21. **Grupa patentowa po błędzie walidacji:** bound form z `rodzaj_rekordu=
    PATENT` i błędem → kontekst/HTML ma grupę patentową widoczną (toggle on
    load).
22. **Jurysdykcja:** `@patent` z `location` → `Patent.informacje` zawiera
    „Kraj: …" (dane nie giną).

## Maszyna statusów (patent)

Patent używa **tych samych** wartości `Status`, ale nigdy nie osiąga
`SOURCE_MATCHED` ani `PBN_CHECK`. Sekwencja: `FETCHED → VERIFIED
(VerifyView.post) → AUTHORS_MATCHED (AuthorsConfirmView) → PUNKTACJA
(PunktacjaView.post) → REVIEW/CREATING/COMPLETED`. `get_continue_url` routuje
wokół pominiętych statusów (patent: `VERIFIED→authors`, `PUNKTACJA→review`).
Filtrowanie listy sesji po statusie działa bez zmian (patent po prostu nie ma
sesji w `SOURCE_MATCHED`/`PBN_CHECK`).

## Pliki (do zmiany)

- `src/importer_publikacji/forms.py` — `VerifyForm` (radio + pola patentowe +
  warunkowa walidacja).
- `src/importer_publikacji/views/wizard.py` — `VerifyView.post` (rozgałęzienie
  + czyszczenie stale stanu), `PunktacjaView.post` (patent→review),
  `SourceView`/`PbnCheckView`/`PbnSelectView`/`PbnClearView` (guardy
  przekierowania `_hx_or_redirect(get_continue_url())` dla patentu),
  `CreateView.post` (guard `also_pbn`).
- `src/importer_publikacji/models.py` — `get_continue_url` (gałąź patentowa).
- `src/importer_publikacji/views/steps.py` — `_verify_context` (prefill
  round-trip-safe), `_authors_context` (flaga `is_patent`), `_review_context`
  (PBN suppression + back_step), `_oblicz_sugestie` (gałąź patent),
  `_find_duplicates` (Patent).
- `src/importer_publikacji/views/publikacja.py` — `_create_patent`
  (rodzaj_prawa_id/wdrozenie/wydzial_id + jurysdykcja→informacje + filtr
  `tytul`), `_create_publication` (guardy `_link_pbn_uid` i
  `_create_streszczenia` dla patentu).
- `src/importer_publikacji/tasks.py` — auto-set `rodzaj_rekordu=PATENT`.
- `src/importer_publikacji/templates/.../partials/step_verify.html` — radio +
  grupy pól + JS show/hide.
- `src/importer_publikacji/templates/.../partials/step_authors.html` — „Wstecz"
  patent-aware (verify vs source).
- `src/importer_publikacji/templates/.../partials/step_review.html` — typ
  „Patent" + sekcja pól patentowych.
- Testy: `tests/test_verify_form.py`, `tests/test_views_*` /
  `tests/test_create_patent.py`, plus nowy integracyjny.
- `src/bpp/newsfragments/*.feature.rst` — nota o UI patentów (fundament ma już
  fragment; uzupełnić lub dodać drugi).

## Nie-cele (YAGNI)

- Brak nowego pola „holder/uprawniony" na modelu `Patent` (kompromis
  `informacje` z fundamentu zostaje).
- Brak wysyłki patentów do PBN (żaden krok/opcja/link).
- Brak sugestii punktacji ze źródła dla patentu.
- Brak zmian w kroku Authors (`dodaj_autora` działa bez zmian).
- Brak importu patentów z innych źródeł niż BibTeX (DSpace/PPM/WWW mogą, ale
  poza zakresem — `publication_type=="patent"` włączy ścieżkę automatycznie,
  gdyby kiedyś któreś źródło je produkowało).
