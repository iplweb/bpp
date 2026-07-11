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
  - `wdrozenie` — `BooleanField`
  - `wydzial` — `ModelChoiceField(Jednostka.objects.all(),
    widget=autocomplete.ModelSelect2(url="bpp:jednostka-autocomplete"))`
    (autocomplete jak w istniejących formularzach)
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
- Pokazywanie/chowanie grup **JS-em** po zmianie radia (bez round-tripu). Pola
  ukrytej grupy mają `required=False`, więc nie generują fałszywych błędów
  walidacji.

## Przepływ — rozgałęzienia patent-aware

Przejścia są rozproszone po `post()` handlerach (brak centralnego routera).
Patent-awareness wchodzi w **trzy** punkty:

1. **`VerifyView.post`** — po zapisaniu:
   - `session.rodzaj_rekordu = form.cleaned_data["rodzaj_rekordu"]`;
   - `session.jest_wydawnictwem_zwartym = (rodzaj == ZWARTE)` (back-compat:
     downstream — dispatch, punktacja — nadal czyta boolean);
   - gdy PATENT: `charakter_formalny=None`, `typ_kbn=None`, `jezyk=None`
     (Patent i tak je hardkoduje); zapisz edytowane pola patentowe do
     `normalized_data` (patrz „Kontrakt normalized_data"); `return
     _render_authors_step(...)` — **pomija Source**;
   - inaczej: dotychczasowe zapisy + `return _render_source_step(...)`.
2. **`PunktacjaView.post`** — po zapisie `punkty_kbn`:
   - gdy PATENT: `return _render_review_step(...)` — **pomija PBN**;
   - inaczej: dotychczasowa logika (`provider == "PBN"` → Review, else PBN).
3. **`steps.py::_review_context`** — gdy PATENT: `back_step = "punktacja"`
   (pomija PBN wstecz) i **nie** ustawiaj `show_save_and_pbn` (patent nie idzie
   do PBN).

Krok **Source i PBN** dla patentu nigdy nie są odwiedzane; ich widoki
pozostają bez zmian (dostępne tylko dla nie-patentów).

## Punktacja dla patentu

`steps.py::_oblicz_sugestie` dostaje gałąź patentową na początku: gdy
`session.rodzaj_rekordu == PATENT` → zwróć `(SugestiaPunktacji(None,
rodzaj_braku=..., powod_braku="Patent nie ma źródła — brak sugestii
punktacji"), None)`. Formularz `PunktacjaForm` (jedno pole `punkty_kbn`) i
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
| `wdrozenie` (bool)         | `wdrozenie`            | `wdrozenie`               |
| `wydzial_id`               | `wydzial`              | `wydzial` (FK)            |
| `patent_holder`            | `uprawniony`           | `informacje` (prefiks „Uprawniony: ") |
| `year`                     | `rok`                  | `rok`                     |

Daty zapisywane jako string ISO `YYYY-MM-DD` (JSON-owalne); `_create_patent`
parsuje je przez istniejące `_parse_iso_date`.

## Zmiany w `_create_patent`

Rozszerzyć o odczyt **jawnych** wartości operatora (mają pierwszeństwo nad
best-effort z fundamentu):

- `rodzaj_prawa`: gdy `normalized_data.get("rodzaj_prawa_id")` ustawione →
  `Rodzaj_Prawa_Patentowego.objects.filter(pk=...).first()`; inaczej fallback
  do dotychczasowego `_resolve_rodzaj_prawa(patent_type)` (po nazwie).
- `wdrozenie`: `normalized_data.get("wdrozenie")` (bool | None).
- `wydzial`: gdy `normalized_data.get("wydzial_id")` → `Jednostka.objects
  .filter(pk=...).first()`.

Uprawniony (`informacje`) — logika bez zmian (fundament już wrzuca „Uprawniony:
X"); wartość pochodzi teraz z edytowalnego pola, nie tylko z BibTeX.

## Prefill kroku Verify (patent)

`steps.py::_verify_context`: gdy `form is None` i `rodzaj_rekordu == PATENT`,
initial buduj z `normalized_data`: `numer_zgloszenia=patent_number`,
`data_zgloszenia=filing_date`, `numer_prawa_wylacznego=patent_grant_number`,
`data_decyzji=grant_date`, `uprawniony=patent_holder`, `rodzaj_prawa` =
best-effort `_resolve_rodzaj_prawa(patent_type)` (po nazwie), `rok=year`,
`rodzaj_rekordu=PATENT`. `wdrozenie`/`wydzial` bez prefillu (BibTeX ich nie ma).

Dla nie-patentu initial jak dziś, plus `rodzaj_rekordu` = `ZWARTE` gdy
`jest_wydawnictwem_zwartym` (z sesji lub z mappera CrossRef), inaczej `CIAGLE`.

## Detekcja przy fetchu

`tasks.py`: po `_store_normalized_data` / w `_auto_match_type_and_language` —
gdy `result.publication_type == "patent"`: `session.rodzaj_rekordu =
ImportSession.RodzajRekordu.PATENT`. Jedyny auto-set; wszystko inne pozostaje
`CIAGLE` (default). `_get_crossref_mapper("patent")` zwraca `None` (patent nie
jest typem CrossRef), więc `charakter_formalny`/`jest_wydawnictwem_zwartym` nie
są auto-ustawiane — operator zobaczy patentowy Verify.

## Create — PBN

Bez zmian. `_create_publication` woła `_link_pbn_uid`, który jest naturalnym
no-op gdy `matched_data["pbn_mongo_id"]` puste — a dla patentu (krok PBN
pominięty) nigdy nie zostanie ustawione. Żadnego jawnego guardu nie trzeba.

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

## Pliki (do zmiany)

- `src/importer_publikacji/forms.py` — `VerifyForm` (radio + pola patentowe +
  warunkowa walidacja).
- `src/importer_publikacji/views/wizard.py` — `VerifyView.post`,
  `PunktacjaView.post` (rozgałęzienia patent).
- `src/importer_publikacji/views/steps.py` — `_verify_context` (prefill),
  `_review_context` (PBN suppression), `_oblicz_sugestie` (gałąź patent).
- `src/importer_publikacji/views/publikacja.py` — `_create_patent`
  (rodzaj_prawa_id/wdrozenie/wydzial_id).
- `src/importer_publikacji/tasks.py` — auto-set `rodzaj_rekordu=PATENT`.
- `src/importer_publikacji/templates/.../partials/step_verify.html` — radio +
  grupy pól + JS show/hide.
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
