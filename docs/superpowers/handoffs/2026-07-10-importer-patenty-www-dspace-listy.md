# Handoff — importer publikacji: patenty + wykrywanie list (WWW/DSpace/PPM)

**Data:** 2026-07-10
**Autor kontekstu:** sesja po zbudowaniu `MultipleWorksImport` (PR #511)
**Worktree:** `~/Programowanie/bpp-bibtex-import-wiele-prac`
**Gałąź bazowa:** `feat-bibtex-import-wiele-prac` (PR #511 → `dev`, **jeszcze niezmergowany**)

## 0. TL;DR — o co chodzi

Trzy powiązane pomysły, wszystkie stoją na **tej samej dźwigni** zbudowanej w PR #511:

> `FetchView.post` woła `provider.split_input(normalized)`; jeśli zwróci ≥2
> `SplitRecord`, powstaje paczka `MultipleWorksImport` + N dzieci i multi-import
> „dzieje się sam". Domyślne `split_input` zwraca 1 rekord; tylko `BibTeXProvider`
> je nadpisuje. **Każdy provider, który nadpisze `split_input`, dostaje
> multi-import za darmo.** `SplitRecord.raw` = wartość, którą *ten sam* provider
> `fetch()` już umie rozwiązać.

Trzy tracki, wg rosnącej trudności:

| Track | Co | Trudność | Zależność od PR #511 |
|---|---|---|---|
| **A. DSpace-lista** | wklejasz URL kolekcji/browse DSpace → multi-import | **łatwe** | tak (split_input/batch) |
| **B. Patenty w BibTeX** | wklejasz `@patent{...}` → tworzy `bpp.Patent` | **średnie/trudne** | nie (osobny wątek, ale ten sam moduł) |
| **C. PPM-lista** | wklejasz URL `globalResultList.seam` → multi-import | **trudne / ryzyko** | tak |

**Uwaga o zależności:** tracki A i C stoją na `split_input`+batch z PR #511.
Dopóki #511 nie jest w `dev`, nową pracę rób **na gałęzi off
`feat-bibtex-import-wiele-prac`** (albo poczekaj na merge). Track B (patenty)
technicznie nie zależy od batcha, ale dotyka tych samych plików — najczyściej
też off tej gałęzi lub po jej merge.

**Wspólny wzorzec (precedens w kodzie):** `WWWProvider.fetch()` już sniffuje URL
po kształcie i skacze do dedykowanej ścieżki (Omega-PSIR:
`providers/www/omega_psir.py`, dispatch w `providers/www/provider.py:129-136`).
To dokładnie kształt, jaki przyjmie „wykryj stronę-listę" — tyle że w
`split_input`, nie `fetch`.

---

## Track A — DSpace: wykrycie listy → multi-import (NAJŁATWIEJSZE)

### Stan dziś (fakty)
- `providers/dspace.py` — klient **pojedynczego itemu** przez REST: DSpace 7
  (`/items/{uuid}` → `/server/api/core/items/{uuid}`, `_fetch_dspace7`
  `:155-202`) lub DSpace 6 (`/handle/{prefix}/{suffix}` →
  `/rest/handle/{h}?expand=metadata`, `_fetch_dspace6` `:205-279`).
- `validate_identifier` (`:313-320` → `_parse_dspace_url` `:136-152`)
  **twardo odrzuca** URL-e nie-itemowe (kolekcja/browse/discover). To jest
  bramka PRZED `split_input` (`views/wizard.py:177-187`), więc **musi być
  poluzowana**, inaczej `split_input` się nie odpali.
- Cel `dspace.piwet.pulawy.pl` = **DSpace 6 XMLUI** (server-rendered, nie SPA).
  URL-e prac `/handle/123456789/N` **już działają dziś** w pojedynczym imporcie.
- `split_input` nienadpisane (dziedziczy default 1-rekord).
- **Latentny bug (osobny):** `_parse_handle_url` regex `r"/handle/(\d+/\d+)"`
  (`:127`) nie odróżnia handle *itemu* od *kolekcji/community* — dziś
  wrzucenie handle kolekcji do `fetch()` po cichu potraktuje ją jak item.

### Co zrobić
1. Poluzuj `validate_identifier`, żeby akceptował URL-e listowe
   (kolekcja/community/browse/discover) — inaczej batch nigdy nie ruszy.
2. Nadpisz `DSpaceProvider.split_input(url)`:
   - jeśli URL to lista → uderz **REST** (`GET /rest/collections/{uuid}/items`
     dla DSpace 6, albo `/server/api/discover/search/objects` dla 7), albo
     **OAI-PMH** (`/oai/request?verb=ListRecords&set=...`) — DUŻO pewniejsze niż
     scraping HTML (paginacja przez `offset`/`limit` lub `resumptionToken`),
   - zwróć `SplitRecord(raw=<item_handle_or_uuid_url>)` per item.
   - inaczej → `return [SplitRecord(raw=url)]` (dzisiejsze zachowanie).
3. `fetch()` **bez zmian** — już rozwiązuje item-handle jeden po drugim.

### Otwarte pytania
- Czy `piwet` ma włączony OAI-PMH (`/oai/request`)? (standard w DSpace 6, ale
  zweryfikować na żywo). Jeśli tak — najczystsza droga.
- Jak user wskaże „którą kolekcję/zapytanie" — wkleja URL kolekcji? browse?
  całe repo? Zdecydować zakres (kolekcja vs cały serwer).
- Przy okazji naprawić latentny bug item-vs-collection handle.

### Werdykt
Najłatwiejszy z trzech. REST/OAI omija JS i kruchość scrapingu; `fetch()` gotowy.

---

## Track B — Patenty w BibTeX (`@patent` → `bpp.Patent`) (ŚREDNIE/TRUDNE)

### Stan dziś (fakty) — patentów NIE da się zaimportować
- `BIBTEX_TYPE_MAP` (`providers/bibtex.py:20-34`) **nie ma** klucza `patent`.
  `@patent` to typ biblatexowy; standardowy BibTeX go nie ma (ludzie fudge’ują
  `@misc`/`@techreport`). `bibtexparser` v2 parsuje dowolne `@xxx{}` generycznie,
  więc `@patent{}` wchodzi jako zwykły `Entry` z `entry_type=="patent"`.
- `fetch()` (`:117-181`): `publication_type = BIBTEX_TYPE_MAP.get("patent")` →
  **`None`** (cicho, bez wyjątku). Dalej `_get_crossref_mapper(None)`
  (`views/helpers.py:122-128`) zwraca `None` → brak auto-podpowiedzi. **Nic się
  nie wywala** — operator ląduje na Verify z pustym `charakter_formalny`.
- Ścieżka tworzenia = **twardy binarny switch** (`views/publikacja.py:266-269`)
  na `session.jest_wydawnictwem_zwartym` → `Wydawnictwo_Ciagle`/`Zwarte`.
  **Brak trzeciej gałęzi. `Patent` nigdzie nie jest importowany.**

### Pułapka / bug (warto naprawić NIEZALEŻNIE od feature’a)
- W Verify `charakter_formalny` jest filtrowany tylko `ukryty=False`
  (`forms.py:98`), a wiersz **"Patent"** ma `publikacja=false`, `ukryty` default
  `False` → **jest widoczny i wybieralny** (`fixtures/charakter_formalny.json`).
- Model-level guard `ZapobiegajNiewlasciwymCharakterom.clean_fields()`
  (`bpp/models/util.py:278-308`) blokuje `skrot in ["D","H","PAT"]` na
  `Wydawnictwo_*` — ale odpala się tylko w `full_clean()` (admin ModelForm),
  a importer woła `.objects.create()` → **guard omijany**. Efekt: operator może
  dziś stworzyć zmieszany `Wydawnictwo_Ciagle/Zwarte` otagowany „Patent",
  który potem **utknie** (edycja w adminie rzuci błąd „kliknij tutaj").
- **Fix niezależny:** w `VerifyForm` wyklucz `skrot__in=["D","H","PAT"]` z
  queryseta `charakter_formalny` dla ścieżki ciagle/zwarte (mirror guardu).

### Model `Patent` (`bpp/models/patent.py`) — impedancja
- `tytul_oryginalny` (pojedynczy tytuł, NIE `DwaTytuly`), `data_zgloszenia`,
  `numer_zgloszenia`, `data_decyzji`, `numer_prawa_wylacznego`,
  `rodzaj_prawa` (FK `Rodzaj_Prawa_Patentowego`), `wdrozenie` (bool),
  `wydzial` (FK `Jednostka`, NIE „applicant/holder" — takiego pola brak).
- **NIE ma `typ_kbn`** (brak `ModelTypowany`) i **`charakter_formalny` NIE jest
  settable** (hardcoded `@cached_property` → `Charakter_Formalny(skrot="PAT")`,
  `:127-129`; brak `ModelZCharakterem`).
  → `_create_publication` buduje `common_fields` z `typ_kbn` i
  `charakter_formalny` (`publikacja.py:237-254`); przekazanie ich do
  `Patent.objects.create(**common_fields)` **rzuci TypeError**. Nowy
  `_create_patent()` MUSI je odfiltrować.
- **Autorzy: gotowe.** `Patent_Autor` dzieli `BazaModeluOdpowiedzialnosciAutorow`
  z `Wydawnictwo_*_Autor`; `Patent.dodaj_autora()` (via `DodajAutoraMixin`,
  `autor_rekordu_klass=Patent_Autor`) jest wołalne przez
  `_add_authors_to_record()` (`publikacja.py:111-154`) **bez zmian**.
- `ImportSession.created_record` to już `GenericForeignKey` — schema sesji jest
  polimorficzna, trzeci typ modelu nie wymaga zmiany tego pola.

### Luka mapowania pól (biblatex `@patent` → `Patent`)
biblatex `@patent`: `number`(zgłoszenie), `holder`(uprawniony), `date`,
`location`(kraj), `type`(patent/wzór). `fetch()` **nic z tego nie czyta**
patentowo dziś (`number`→`issue`). BPP własny **eksport** patentu
(`bpp/export/bibtex.py:279-311`) emituje `@misc` z polami wrzuconymi w
free-text `note` („Numer zgłoszenia: X…") — więc nawet round-trip własnego
eksportu jest **stratny**; nie ma w repo strukturalnej konwencji do importu.

### Co zrobić
- (a) `BIBTEX_TYPE_MAP += {"patent": ...}` + mechanizm routingu (uwaga:
  „patent" nie jest typem CrossRef, a `Crossref_Mapper` jest CrossRef-flavored —
  rozważyć osobny tor, nie wciskać w mapper).
- (b) `FetchedPublication` + pola patentowe (`patent_number`, `patent_holder`,
  `filing_date`, `grant_date`, `patent_type`/`jurisdiction`); `fetch()` czyta je
  z biblatex gdy `bibtex_type=="patent"`.
- (c) `_create_patent(session, common_fields, normalized_data)` w
  `publikacja.py` — **odfiltruj `typ_kbn` i `charakter_formalny`**, wypełnij
  `numer_zgloszenia`/`data_zgloszenia`/`numer_prawa_wylacznego`/`data_decyzji`/
  `rodzaj_prawa`/`tytul_oryginalny`/`rok`. Dispatch (`:266-269`) potrzebuje
  trzeciej gałęzi → `ImportSession` potrzebuje realnego pola „rodzaj rekordu"
  (dziś tylko boolean `jest_wydawnictwem_zwartym`).
- (d) Wizard: nowe pole typu na `ImportSession` + pola patentowe w `VerifyForm`
  / warunkowe w `step_verify.html` (albo osobny pod-krok patentowy).
- (e) Autorzy: bez zmian.

### Werdykt
Parsowanie łatwe; **cała praca to plumbing wizarda/tworzenia**: nowe pole typu
na sesji, trzecia gałąź dispatchu, pola patentowe w formularzu/UI, `_create_patent`
z odfiltrowaniem `typ_kbn`/`charakter_formalny`. Model `Patent` odstaje
(brak typ_kbn/charakter, daty/numery, brak pola holder). Rozważyć: czy w ogóle
mapować z biblatex `@patent`, czy raczej dać operatorowi pola ręcznie (bo źródeł
BibTeX brak/stratne).

---

## Track C — PPM `globalResultList` → multi-import (NAJTRUDNIEJSZE / RYZYKO)

### Stan dziś (fakty)
- `providers/www/provider.py` — generyczny scraper meta-tagów (citation_*,
  Schema.org JSON-LD, Dublin Core, OpenGraph) + jeden adapter site’owy
  (Omega-PSIR). `input_mode=IDENTIFIER` (URL). `validate_identifier` akceptuje
  **dowolny** poprawny URL (`network.py:31-51`) — więc URL listy przejdzie
  walidację, ale `fetch()` zwróci 0/1 rekord (brak pojęcia „lista").
- `https://ppm.umlub.pl/globalResultList.seam?...` = **JBoss Seam/JSF**. Pobrany
  HTML dla tego URL pokazuje tylko zakładki z licznikami, **brak linków do
  pojedynczych prac** — grid wyników renderowany prawdopodobnie AJAX-em
  (JSF/RichFaces) na bazie server-side `javax.faces.ViewState`, którego
  `requests.get` (bezstanowy, jak wszędzie w kodzie) **nie odtworzy**.
- Brak PPM-owego kodu w repo; nieznany kształt URL-a strony-detalu.

### Co zrobić / ryzyka
- `split_input` musiałby albo (i) sparsować grid Seam — ale jest AJAX/ViewState,
  `requests.get` nie wystarczy; albo (ii) znaleźć pod-endpoint JSON/REST grida
  (nieodkryty — wymaga devtools na żywej sesji).
- `fetch()` na stronie-detalu PPM **niezweryfikowany** (zadziała, jeśli detal ma
  citation_*/DC/Schema.org — wtedy fallback WWW „po prostu działa").
- **Zalecenie:** najpierw prototyp na żywej sesji przeglądarki (Chrome DevTools
  MCP / Playwright) — znaleźć (a) kształt URL-a detalu, (b) czy grid ma
  underlying JSON endpoint, (c) czy `requests.get` w ogóle coś zwróci —
  ZANIM zaczniesz pisać `split_input`.

### Werdykt
Materialnie ryzykowniejsze niż DSpace przez statefulność Seam/ViewState.
Nie commitować się w scraping HTML bez wcześniejszego reverse-engineeringu.

---

## Rekomendowana kolejność

1. **Track A (DSpace)** — najszybszy ROI, REST/OAI, `fetch()` gotowy. Dobry
   pierwszy „prawdziwy" dowód, że `split_input` skaluje się poza BibTeX.
2. **Bug niezależny (charakter_formalny trap)** — tani fix, realne dane-ryzyko
   (mislabeled/utknięte rekordy). Można zrobić przy okazji Track B albo od razu.
3. **Track B (patenty)** — większy plumbing; wart osobnego spec/planu. Zdecydować
   najpierw *product*: mapować z biblatex `@patent` czy pola ręczne w wizardzie.
4. **Track C (PPM)** — dopiero po prototypie przeglądarkowym; może się okazać
   niewykonalne bez headless browsera w imporcie (duża zmiana architektury).

## Pierwszy krok w nowej sesji
- Wejść w worktree `~/Programowanie/bpp-bibtex-import-wiele-prac`, gałąź off
  `feat-bibtex-import-wiele-prac` (lub po merge #511 — off `dev`).
- Odpalić **brainstorming** dla wybranego tracku (to nowy feature → design przed
  kodem). Dla Track A pierwsze pytania: OAI-PMH vs REST discovery? zakres
  (kolekcja vs zapytanie vs całe repo)? jak operator wskazuje listę?
- Ten worktree ma zbudowany `MultipleWorksImport`/`split_input` — nowe providery
  tylko nadpisują `split_input`, reszta batcha działa.

## Pliki-klucze
**Batch/dźwignia:** `providers/__init__.py` (`split_input`, `SplitRecord`),
`providers/bibtex.py` (jedyny override — wzorzec), `views/wizard.py:114-226`
(`_create_batch`, `FetchView.post` — bramka `validate_identifier`/`split_input`),
`tests/test_split_input.py` (kontrakt testów).
**DSpace:** `providers/dspace.py`, `providers/dspace_common.py`.
**WWW/PPM:** `providers/www/provider.py`, `providers/www/network.py`,
`providers/www/omega_psir.py` (precedens URL-sniff).
**Patenty:** `providers/bibtex.py`, `providers/__init__.py`,
`views/publikacja.py` (`_create_*`, dispatch `:266-269`), `views/steps.py`
(`_verify_context`), `forms.py` (`VerifyForm`), `models.py` (ImportSession),
`bpp/models/patent.py`, `bpp/models/abstract/authors.py`,
`bpp/models/abstract/metadata.py` (`ModelZCharakterem`),
`bpp/models/util.py` (`ZapobiegajNiewlasciwymCharakterom`),
`bpp/models/system/crossref_mapper.py`, `bpp/admin/patent.py` (referencja pól
formularza), `bpp/export/bibtex.py` (stratny round-trip), `forms.py:98`
(trap charakter_formalny), `fixtures/charakter_formalny.json` (wiersz PAT).
