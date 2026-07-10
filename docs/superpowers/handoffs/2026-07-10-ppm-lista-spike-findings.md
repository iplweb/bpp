# Spike — Track C: PPM `globalResultList` → multi-import

**Data:** 2026-07-10
**Worktree:** `~/Programowanie/bpp-ppm-lista`, gałąź `feat-ppm-lista-import`
**Gałąź bazowa:** `feat-bibtex-import-wiele-prac` (PR #511, jeszcze niezmergowany)
**Poprzedni handoff:** [`2026-07-10-importer-patenty-www-dspace-listy.md`](2026-07-10-importer-patenty-www-dspace-listy.md)
— sekcja "Track C" z rekomendacją: zrobić prototyp na żywej sesji ZANIM
zacznie się pisać `split_input`. Ten dokument jest wynikiem tego prototypu.

## TL;DR — werdykt

**DOWORKS_WITH_CAVEAT.** Literalny URL z zadania
(`globalResultList.seam?r=projectmain&tab=PROJECT` — zakładka **projektów**)
pozostaje **BLOCKED**: to JSF/Seam AJAX grid ze statefulnym
`javax.faces.ViewState`, którego `requests.get` nie odtworzy, i nie ma dla
niego żadnego odkrytego publicznego REST/OAI/eksportu.

Ale w trakcie reconu znalazłem **realny, stateless, działający** endpoint
listy — tyle że dla zakładki **publikacji** (`PUBLICATION`), czyli
dokładnie tego, czym BPP się zajmuje (Bibliografia Publikacji Pracowników):
SEO-sitemapa `articles-xml.seam?year=YYYY`, wpisana w `robots.txt` instancji
Omega-PSIR. To zaimplementowałem (TDD, mocki, zero live-network w testach).

| Widok PPM | Endpoint listy | Stan |
|---|---|---|
| Publikacje (`tab=PUBLICATION`) | `articles-xml.seam?year=YYYY` | **DZIAŁA** — zaimplementowane |
| Projekty (`tab=PROJECT`, z zadania) | brak odkrytego | **BLOCKED** |
| Patenty, doktoraty, dane badawcze, ... | brak odkrytego | **BLOCKED** (nie sprawdzane głębiej — poza zakresem BPP) |
| `globalResultList.seam` (dowolna zakładka, filtrowane wyszukiwanie) | brak — JS/ViewState grid | **BLOCKED** |

## 1. Czy PPM to Omega-PSIR? TAK, potwierdzone

- Nagłówek `Set-Cookie: JSESSIONID=...omegaprod` (cookie *domain suffix*
  `omegaprod`).
- Motyw PrimeFaces: `primefaces-omega`.
- Stopka strony: „© 2026 Obsługiwany przez Omega-PSIR”.
- Strona `/api.seam` (link w menu): „Ta platforma posiada API. Aby otrzymać
  dokumentację oraz klucz do API prosimy wysłać zapytanie na
  **api@omegapsir.io**” — a więc **istnieje** REST API, ale jest **gated**
  (trzeba pisać maila, dostać klucz) — nie nadaje się do stateless
  auto-detekcji bez interakcji człowieka z administracją PPM.

To znaczy: repo już ma adapter Omega-PSIR (`providers/www/omega_psir.py`,
regex `OMEGA_ARTICLE_RE = r"/info/article/([A-Za-z]{2,5}[0-9a-f]{32})"`) i
**on faktycznie pasuje** do kształtu URL-i PPM (`/info/article/UML<32hex>/`)
— potwierdzone na żywej stronie szczegółów (patrz sekcja 3). Test
`test_fetch_omega_psir_url` w repo już to pokrywał (z fikcyjnym hostem
`ppm.edu.pl`) — teraz mamy **potwierdzenie na prawdziwej instancji**.

## 2. `globalResultList.seam` — potwierdzone BLOCKED

Pobrane na żywo (`curl`, `2026-07-10`):

```
GET https://ppm.umlub.pl/globalResultList.seam?r=projectmain&tab=PROJECT&lang=pl
→ HTTP 200, Content-Type: text/html;charset=UTF-8, 69183 znaków
```

Fakty z body:

- **5 osobnych `javax.faces.ViewState` hidden-inputów** (jeden per `<form>`
  na stronie) — jednoznaczny odcisk palca statefulnego JSF/Seam. Bez
  poprawnego ViewState token-a serwer odrzuci/ zignoruje próbę
  „kolejnej strony”/AJAX-owego dociągnięcia wyników.
- **Zero** linków `/info/article/...` (ani żadnego innego per-wpis linku)
  w server-rendered HTML — tylko zakładki z licznikami
  (`Publikacje (N)`, `Projekty (N)`, `Patenty (N)`, ...) prowadzące do
  innych `globalResultList.seam?r=...&tab=...` (czyli tego samego problemu
  dla każdej zakładki).
- Próby oczywistych REST/JSON pod-endpointów (`/oai/request?verb=Identify`,
  `/seam/resource/rest/accesspoint/rdf/jsonld/<fake-id>`) → **404** (OAI-PMH
  nie jest wystawiony; REST JSON-LD istnieje, ale tylko per-artykuł, nie
  jako lista/wyszukiwarka).
- `sitemap.xml` (zgadywany, standardowa lokalizacja) → 404.

Żadna próba nie próbowała odtworzyć ViewState-owego round-tripu (to
wymagałoby prawdziwej przeglądarki — w tym środowisku **nie było dostępnego
Chrome/Chromium** ani dla `chrome-devtools-mcp`, ani dla `playwright`, więc
nie dało się nawet zweryfikować, czy sam grid faktycznie renderuje się AJAX-em
zamiast np. zwykłym re-postem formularza — ale zbiór dowodów [statefulny
ViewState + zero linków w HTML + brak endpointu REST/OAI dla wyszukiwania]
jest wystarczający, żeby ocenić stateless `requests.get` jako niewykonalny
dla tego widoku bez dużo większej inwestycji).

**Wniosek:** żeby zrobić `split_input` dla `globalResultList.seam` trzeba by
albo (a) headless przeglądarki wewnątrz importera (spory skok architektury —
Celery worker odpalający Playwright per-request), albo (b) uzyskania klucza
do gated API PPM (wymaga maila do `api@omegapsir.io` + prawdopodobnie umowy/
zgody instytucjonalnej — nie coś, co da się zdobyć w spike'u), albo (c)
współpracy z administratorem PPM o inny eksport. Żadne z tych nie jest
"cichym" fixem kodu — to decyzja produktowa/organizacyjna.

## 3. Odkrycie: `articles-xml.seam?year=YYYY` — DZIAŁA, stateless

`robots.txt` PPM zawiera:

```
User-agent: *
Disallow: /
Crawl-delay: 10

User-agent: googlebot
Allow: /
Disallow: /stats/
Disallow: /SearchExpert.seam*
Disallow: /SearchGlobal.seam*

Sitemap: https://ppm.umlub.pl/years-xml.seam
```

`years-xml.seam` to `<sitemapindex>` (standard sitemaps.org) z jednym
`<sitemap><loc>` per rok (potwierdzone 2007–2026), każdy wskazujący na
`articles-xml.seam?year=YYYY`. Ten z kolei to zwykły `<urlset>` z **1467
`<loc>`** dla roku 2026 — każdy `<loc>` to URL strony szczegółowej artykułu w
kształcie `https://ppm.umlub.pl/info/article/UML<32hex>/` — **dokładnie**
kształt, który `omega_psir.py` już rozpoznaje.

Sprawdzone na żywo, że strona szczegółowa faktycznie niesie dane do
sparsowania (bez potrzeby REST JSON-LD nawet — `citation_*` meta tagi
wystarczają):

```
GET https://ppm.umlub.pl/info/article/UML001085ec4f064177b924ac8a993e7701/
→ 200, <meta name="citation_title" content="Zakażenie HPV u kobiety a
  zdrowie noworodka - edukacyjna rola położnej">
  <meta name="citation_author" content="Siemieńczuk, Julia">
  <meta name="citation_author" content="Winiarczyk, Weronika">
  <meta name="citation_publication_date" content="2026">
  ...
```

`WWWProvider.fetch()` już to sparsuje bez żadnych zmian (fallback-chain
citation_meta → schema_jsonld → dublin_core → opengraph, plus Omega-PSIR
REST JSON-LD jeśli URL pasuje regexowi — tu wystarczy sam citation_meta).

**Ograniczenia tego, co odkryte:**

- Sitemapa jest per **rok kalendarzowy**, nie per zapytanie/filtr — wklejenie
  jej daje **wszystkie** artykuły z danego roku w PPM, nie przefiltrowany
  wynik wyszukiwania. To jest świadomy kompromis: dokładny i kompletny (nic
  nie ginie, nic nie jest zgadywane), ale operator nie może np. dociągnąć
  "tylko prac z mojej jednostki" tą drogą.
- Sprawdzone tylko dla zakładki **PUBLICATION** (`articles-xml.seam`).
  Próby analogicznych nazw dla innych zakładek (`projects-xml`,
  `projectmain-xml`, `patents-xml`, `patent-xml`, `phd-xml`,
  `doctorates-xml`, `publications-xml`, `theses-xml`) → wszystkie 404. Może
  istnieć inna nazwa dla innych typów, ale nie została odkryta w tym
  spike'u (i patenty/projekty/doktoraty to i tak drugorzędne w BPP wobec
  publikacji).
- Rozmiar: rok 2026 to już 1467 wpisów **w połowie roku** — starsze,
  pełne lata będą prawdopodobnie większe. `split_input` dziś **nie ogranicza**
  liczby zwracanych rekordów (spójne z `BibTeXProvider`, który też nie ma
  cappa) — ale w przeciwieństwie do BibTeX-a (parsowanie w pamięci, brak
  sieci) to jest **synchroniczny fetch sieciowy w request/response cyklu
  widoku** (`FetchView.post` woła `split_input` przed enqueue Celery). Dla
  bardzo dużych lat to może być zauważalne opóźnienie odpowiedzi HTTP —
  **nie zmierzone tu na żywo** (żeby nie obciążać cudzej produkcyjnej
  instancji powtarzalnymi testami wydajnościowymi). Realna implementacja
  produkcyjna powinna rozważyć: cap + ostrzeżenie, albo przesunięcie fetchu
  sitemapy do Celery zamiast do widoku.

## 4. Co zaimplementowano (ten branch)

- `providers/www/omega_psir_sitemap.py` — nowy moduł:
  `_detect_omega_articles_sitemap(url)` (rozpoznanie po kształcie URL:
  ścieżka `/articles-xml.seam` + parametr `year=YYYY`, bez allow-listy
  hostów — ten sam styl co `OMEGA_ARTICLE_RE` w `omega_psir.py`) oraz
  `_fetch_omega_articles_sitemap(url)` (GET + parsowanie XML przez
  `defusedxml.ElementTree` — **nie** stdlib `xml.etree`, bo XML z
  zewnętrznego serwera to potencjalny wektor XXE/billion-laughs).
- `WWWProvider.split_input()` (nadpisane, wcześniej dziedziczyło default
  1-rekordowy): jeśli URL pasuje do kształtu sitemapy → fetch + N
  `SplitRecord(raw=<article_url>)`; w każdym innym przypadku (w tym
  `globalResultList.seam`) → **niezmieniony fallback do 1 rekordu**,
  identyczny jak default `DataProvider.split_input`. Świadomie NIE robimy
  nic "sprytnego" dla `globalResultList.seam` (np. zgadywania roku z query
  stringa i cichego przełączenia na sitemapę) — to dawałoby operatorowi
  wynik niezgodny z tym, co faktycznie wkleił (przefiltrowane wyszukiwanie
  vs. cały rok), czyli dokładnie ten rodzaj "fake" feature'u, którego zadanie
  zabraniało.
- Testy (`tests/test_www_provider_ppm_split_input.py`, wszystkie z mockami,
  zero live-network):
  - sitemapa → 3 `SplitRecord` (happy path + weryfikacja że fetch poszedł
    dokładnie na URL sitemapy),
  - błąd HTTP / malformed XML → bezpieczny fallback do 1 rekordu,
  - URL spoza kształtu → **zero requestów sieciowych** (sprawdzone
    `mock_get.assert_not_called()`),
  - `globalResultList.seam` (fixture zbudowany na bazie realnej odpowiedzi:
    ViewState + zakładki + zero per-wpis linków) → dokumentuje dzisiejszy
    bezpieczny fallback (1 rekord, zero requestów),
  - `xfail(strict=True)` dokumentujący **docelowe** zachowanie dla
    `globalResultList.seam` (≥2 rekordy) — celowo czerwony dziś, żeby ktoś w
    przyszłości, kto to naprawi, dostał przypomnienie usunąć xfail.
- `pyproject.toml`: dodano `defusedxml>=0.7.1` (bezpieczny parser XML).

## 5. Rekomendacja na przyszłość

1. Jeśli operator PPM/BPP chce importować **publikacje** z PPM hurtowo:
   wkleja URL eksportu roku (`articles-xml.seam?year=2026`) — działa dziś.
   Warto rozważyć UX: `input_help_text` `WWWProvider` mogłoby wspomnieć o tym
   sposobie dla Omega-PSIR (na razie nie dodane w tym spike'u — do decyzji
   produktowej, czy eksponować to wprost w UI, czy zostawić jako "ukrytą"
   zdolność techniczną odkrywaną przez dokumentację/support).
2. `globalResultList.seam` (przefiltrowane wyszukiwanie, dowolna zakładka)
   pozostaje niewykonalne bez (a) headless browsera w pipeline importu, albo
   (b) gated API PPM (`api@omegapsir.io`), albo (c) współpracy z
   administratorem PPM o dedykowany eksport. To decyzja **poza zakresem
   inżynierskim** tego repo — ktoś (product/management) musi zdecydować,
   czy inwestycja w headless browser lub pozyskanie klucza API jest warta
   ROI, zanim ruszy dalsza praca.
3. Warto sprawdzić (osobny, krótki spike), czy inne instytucje z Omega-PSIR
   (są ich dziesiątki w Polsce — POL-on, wiele uczelni medycznych) mają ten
   sam `articles-xml.seam` — jeśli tak, obecna implementacja "za darmo"
   obsługuje je wszystkie (URL-sniff nie jest hostname-gated).
