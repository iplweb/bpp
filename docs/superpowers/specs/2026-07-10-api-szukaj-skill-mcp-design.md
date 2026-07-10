# API BPP: rozszerzenie o wyszukiwanie + skill + serwer MCP

**Data:** 2026-07-10
**Autor:** Michał Pasternak (+ Claude)
**Status:** design zaakceptowany, przed pisaniem planów implementacji

## Cel

Umożliwić wygodną, programistyczną i agentową pracę z danymi BPP przez API
`/api/v1/`, poprzez trzy współzależne dostawy:

- **Faza 0** — dołożyć do API BPP wyszukiwanie (publikacje + autorzy), oparte na
  istniejącym silniku pełnotekstowym. Bez tego API nie da się sensownie
  „odkrywać" danych (patrz niżej).
- **Faza 1** — skill Claude Code (`../bpp-skills/`): wiedza o API jako markdown.
- **Faza 2** — serwer MCP (`../bpp-mcp/`, FastMCP/Python): ta sama wiedza jako
  typowane, kuratorowane narzędzia dla Claude Desktop i innych agentów.

Konsument docelowy: **skill + MCP** — czyli zarówno Claude Code (przez skill),
jak i inne agenty/klienty MCP (przez serwer).

## Kontekst: rzeczywistość obecnego API (ustalona z kodu `src/api_v1/`)

- **Read-only, anonimowe.** Prawie wszystko to `ReadOnlyModelViewSet` z
  `DjangoModelPermissionsOrAnonReadOnly` — publiczne dane bez tokenu. Wyjątek:
  `raport_slotow_uczelnia*` (BasicAuth + grupa `GR_RAPORTY_WYSWIETLANIE`).
- **Paginacja:** `LimitOffsetPagination`, `PAGE_SIZE=10` → `?limit=N&offset=M`.
- **Format:** trzeba wymuszać `?format=json` (inaczej HTML browsable API).
- **Brak throttlingu.**
- **Serializery są hyperlinked** — relacje to URL-e, nie zagnieżdżone obiekty.
  Przejście publikacja → autorzy → jednostka to *chodzenie po linkach* (N+1
  pobrań). To główny „haczyk" dla agenta i główna wartość, którą MCP ukrywa.
- **~30 endpointów** w 5 kategoriach: publikacje (`wydawnictwo_ciagle`,
  `wydawnictwo_zwarte`, `patent`, `praca_doktorska`, `praca_habilitacyjna`),
  autorzy/jednostki (`autor`, `autor_jednostka`, `funkcja_autora`, `tytul`,
  `jednostka`, `wydzial`, `uczelnia`), źródła/wydawcy (`zrodlo`,
  `rodzaj_zrodla`, `wydawca`, `poziom_wydawcy`), słowniki
  (`charakter_formalny`, `typ_kbn`, `jezyk`, `dyscyplina_naukowa`,
  `konferencja`, `seria_wydawnicza`, `czas_udostepnienia_openaccess`,
  `nagroda`), raporty.
- **Endpointy embedu** (poza standardowym routerem, `AllowAny`):
  `recent_author_publications/<id-lub-slug>/` i
  `recent_unit_publications/<id-lub-slug>/` — zwracają **zagnieżdżoną** listę
  publikacji (`opis_bibliograficzny`, `rok`, `url`), parametry
  `limit`/`rok_od`/`rok_do`. To jedyna wygodna ścieżka „encja → jej prace".
- **Filtry są wąskie i per-endpoint** (`DjangoFilterBackend`):
  - publikacje (ciągłe/zwarte): `rok` (RangeFilter → `rok_min`/`rok_max`),
    `charakter_formalny`, `ostatnio_zmieniony` (DateTimeFromToRange →
    `ostatnio_zmieniony_after`/`ostatnio_zmieniony_before`);
  - patenty / prace dr / hab: `rok`, `ostatnio_zmieniony`;
  - `autor`, `zrodlo`: tylko `ostatnio_zmieniony`.
- **Ukrywanie rekordów:** `nie_eksportuj_przez_api=True` oraz ukryte statusy
  korekty są odfiltrowane — API ≠ 1:1 baza.

### Krytyczne ograniczenie, które motywuje Fazę 0

**Obecne API nie ma wyszukiwania pełnotekstowego ani po nazwisku/tytule.**
Zero `SearchFilter`, zero `search_fields` (zweryfikowane w całym `api_v1`).
Odkrywanie danych jest wyłącznie po **ID / slugu / roku / dacie modyfikacji**.
Nie da się przez API: znaleźć autora po nazwisku, znaleźć pracy po tytule.

### Dlaczego Faza 0 jest tania

Silnik wyszukiwania **już istnieje** w BPP — trzeba go tylko wystawić:

- `Rekord.objects.fulltext_filter("zapytanie")` (`bpp.util.orm.FulltextSearchMixin`,
  `RekordManager.fts_field = "search_index"`) daje **rankowane** FTS po
  **wszystkich** publikacjach naraz (`Rekord` to zmaterializowany cache
  spinający ciągłe+zwarte+patenty+prace). Wspiera składnię websearch
  (cudzysłowy, minus).
- `Autor`, `Zrodlo`, `Jednostka` mają własne pola `search_index` (tsvector,
  `ModelPrzeszukiwalny`) — gotowe do podpięcia.

Rozszerzenie to podpięcie istniejącego silnika w warstwie DRF: **brak nowej
logiki wyszukiwania, brak migracji**.

## Wspólny rdzeń wiedzy (dzielony przez Fazę 1 i 2)

Jedno źródło prawdy (ten spec) → dwie ręcznie utrzymywane reprezentacje
(tabela markdown w skillu; `dict`/`dataclass` w MCP). Świadomie **bez**
generatora z jednego YAML (YAGNI na tym etapie). Rdzeń obejmuje:

- mapę ~30 endpointów + kategorie,
- konwencje filtrów (`rok_min`/`rok_max`, `ostatnio_zmieniony_after`/`_before`),
- strategię hyperlinków (kiedy podążać za URL, kiedy nie),
- konfigurowalny `base_url` (wielo-instancyjność: umlub + inne wdrożenia BPP),
- pułapki: `nie_eksportuj_przez_api`, ukryte statusy, `?format=json`,
  LimitOffset,
- ścieżki odkrywania (po Fazie 0: `/szukaj/` + `autor?nazwisko=`).

---

## Faza 0 — rozszerzenie API BPP o wyszukiwanie

**Repo:** `bpp`. **Gałąź:** `feat-api-szukaj-skill-mcp`. Read-only, anonimowe,
stronicowane (`LimitOffsetPagination`).

### 0.1 Endpoint wyszukiwania publikacji — `GET /api/v1/szukaj/`

- Parametry: `q` (wymagany, tekst zapytania websearch), opcjonalnie
  `rok_od`/`rok_do`, `limit`/`offset`.
- Backend: `Rekord.objects.fulltext_filter(q)`; zawężenie po `rok__gte/lte`;
  wykluczenie ukrytych statusów korekty (kontekst `"api"`, jak w
  `recent_publications_common._ukryte_statusy`) i rekordów
  `nie_eksportuj_przez_api`.
- Sortowanie: rank malejąco (dostarcza `fulltext_filter`).
- Pozycja wyniku (płaska, bez chodzenia po linkach):
  - `id` — string `"<contenttype_id>-<pk>"` (klucz `Rekord`),
  - `tytul_oryginalny`, `rok`,
  - `opis_bibliograficzny` (z `opis_bibliograficzny_cache`),
  - `rekord_url` — hyperlink do typowanego detalu
    (`wydawnictwo_ciagle-detail` / `wydawnictwo_zwarte-detail` / … wybrany po
    content-type trafienia),
  - `absolute_url` — publiczny URL rekordu na stronie WWW.
- **Uwaga projektowa:** `Rekord` PK to `TupleField (content_type_id, pk)`.
  Endpoint musi zmapować content-type trafienia na właściwy typowany
  `*-detail` URL. Mapę contenttype→viewname trzymamy jawnie (mały, czytelny
  słownik), z bezpiecznym fallbackiem (gdy typ spoza mapy → `rekord_url = null`,
  ale pozycja nadal zwracana z `absolute_url`).

### 0.2 Wyszukiwanie autora po nazwisku — `autor?nazwisko=`

- Rozszerzyć `AutorFilterSet` o filtr `nazwisko`
  (`django_filters.CharFilter(lookup_expr="icontains")`) — proste, przewidywalne
  „nazwisko → lista kandydatów z ID/slug/jednostką". (Alternatywa: FTS na
  `Autor.search_index` — odrzucona w v1 jako mniej przewidywalna dla krótkich
  zapytań po nazwisku; można dołożyć później jako osobny param `szukaj=`.)
- Zachować istniejący filtr `ostatnio_zmieniony`.

### 0.3 Rejestracja i widoczność

- Zarejestrować `SzukajViewSet` (lub `APIView` + router `basename="szukaj"`) w
  `api_v1/urls.py`; dodać do kategoryzacji w `CustomAPIRootView` (nowa pozycja,
  np. w sekcji „publications" lub własna „search").
- Endpoint musi respektować multi-uczelnia (`Uczelnia.get_for_request`) tak jak
  reszta — zawężenie ukrytych statusów per bieżąca uczelnia.

### Kryteria akceptacji Fazy 0

- `GET /api/v1/szukaj/?q=<fraza>&format=json` zwraca rankowaną, stronicowaną
  listę trafień ze wszystkich typów publikacji, z `rekord_url` wskazującym
  właściwy typowany detal.
- `q` puste/niepoprawne → pusta lista (nie 500), zgodnie z
  `fulltext_filter`/`fulltext_empty`.
- `rok_od`/`rok_do` zawężają wyniki; `limit`/`offset` stronicują.
- Rekordy `nie_eksportuj_przez_api` oraz ukryte statusy **nie** pojawiają się.
- `GET /api/v1/autor/?nazwisko=kowalski&format=json` zwraca autorów, których
  nazwisko zawiera frazę (case-insensitive), z ich `id`, `slug`,
  `aktualna_jednostka`.
- Testy pytest (`src/api_v1/tests/`): trafienie/brak trafienia, filtr roku,
  wykluczenie ukrytych/`nie_eksportuj`, mapowanie contenttype→detal, filtr
  nazwiska. `model_bakery.baker` do fixtur.
- Newsfragment towncrier.
- Baseline bazy: Faza 0 **nie zmienia schematu** (tylko warstwa API) → brak
  odświeżania baseline.

---

## Faza 1 — skill `../bpp-skills/`

**Repo:** nowe, `~/Programowanie/bpp-skills/`. Skill Claude Code (format
`skill-creator`): `SKILL.md` + `references/`.

### Struktura

- `SKILL.md` — nazwa, opis (trigger: „praca z API BPP / bpp.umlub.pl/api /
  pobieranie publikacji/autorów z BPP"), sekcje:
  - jak wołać (`?format=json`, `curl`/WebFetch, host konfigurowalny),
  - paginacja LimitOffset,
  - **strategia hyperlinków** (kiedy podążać za URL, kiedy poprzestać na
    liście; że relacje to URL-e),
  - wyszukiwanie (`/szukaj/?q=`, `autor?nazwisko=`) — po Fazie 0,
  - „prace autora/jednostki" przez `recent_*_publications`,
  - uczciwa sekcja „czego API nie umie" (brak searcha po tytule poza
    `/szukaj/`, brak filtrów fasetowych, ukrywanie rekordów).
- `references/endpoints.md` — pełna tabela endpointów: ścieżka, opis, dostępne
  filtry, kształt zwracanych pól, powiązania (hyperlinki).
- `references/przyklady.md` — gotowe przepisy curl (szukaj → pobierz detal →
  rozwiń autorów; przyrostowy harvest po `ostatnio_zmieniony`).

### Kryteria akceptacji Fazy 1

- Skill przechodzi walidację `skill-creator` (poprawny front-matter, opis
  wyzwalający).
- `references/endpoints.md` pokrywa wszystkie endpointy z `api_v1/urls.py`
  (w tym `/szukaj/` z Fazy 0) z poprawnymi nazwami filtrów.
- Przepisy w `przyklady.md` są wykonywalne wobec `bpp.umlub.pl` (host
  parametryzowany).
- README + LICENSE (skill jako repo OSS, spójnie z resztą pakietów iplweb).

---

## Faza 2 — serwer MCP `../bpp-mcp/`

**Repo:** nowe, `~/Programowanie/bpp-mcp/`. **Stack:** Python + FastMCP
(oficjalny SDK `mcp`), `httpx` do wołania API, `uv` do packagingu, `pytest`
do testów. **Granularność:** kuratorowane, zadaniowe narzędzia — MCP sam
rozwija paginację i hyperlinki.

### Konfiguracja

- `BPP_BASE_URL` (env, domyślnie `https://bpp.umlub.pl`) — wielo-instancyjność.
- Opcjonalnie `BPP_BASIC_AUTH` (user:pass) — tylko dla raportów slotów
  (poza v1 rdzeniem; patrz „poza zakresem").

### Narzędzia (nazwy polskie, pod domenę)

| Narzędzie | Endpoint(y) | Rola |
|---|---|---|
| `szukaj_publikacji(q, rok_od?, rok_do?, limit?)` | `/szukaj/` | rankowane FTS |
| `szukaj_autora(nazwisko)` | `autor?nazwisko=` | nazwisko → profil+ID |
| `publikacje_autora(id_lub_slug, rok_od?, rok_do?, limit?)` | `recent_author_publications` | prace autora |
| `publikacje_jednostki(id_lub_slug, …)` | `recent_unit_publications` | prace jednostki |
| `pobierz_rekord(typ, id)` | `wydawnictwo_*` + relacje | **rozwija hyperlinki** (autorzy, źródło, streszczenia inline) |
| `lista_publikacji(typ, rok_od?, rok_do?, charakter?, zmienione_po?, limit?, offset?)` | `wydawnictwo_*` | harvest/przyrost |
| `slownik(rodzaj)` | `charakter_formalny`/`jezyk`/`dyscyplina_naukowa`/… | tłumaczenie ID↔nazwa |

- `pobierz_rekord` to rdzeń wartości: pobiera detal, następnie równolegle
  rozwiązuje hyperlinki `autorzy_set`, `zrodlo`, `streszczenia`,
  `zewnetrzna_baza_danych` i zwraca **jeden** zagnieżdżony obiekt — agent nie
  chodzi po URL-ach.
- Wszystkie narzędzia zwracają dane już z `?format=json`, auto-follow
  paginacji LimitOffset do `limit`.

### Kryteria akceptacji Fazy 2

- `uv run` startuje serwer MCP; narzędzia widoczne przez `mcp` inspector.
- Testy pytest z zamockowanym httpx (respx/httpx MockTransport): każde
  narzędzie — happy path + błąd sieci + pusty wynik.
- `pobierz_rekord` udowodniony test-em: z hyperlinked detalu buduje
  zagnieżdżony obiekt (autorzy jako nazwy, nie URL-e).
- `szukaj_publikacji`/`szukaj_autora` działają wobec żywego umlub (test
  smoke, oznaczony/opcjonalny — nie w domyślnym CI offline).
- README (konfiguracja `BPP_BASE_URL`, instrukcja podpięcia do Claude
  Desktop/Code) + LICENSE + GitHub Actions (matryca pytest).

## Poza zakresem (v1, świadomie)

- Search po `zrodlo`/`jednostka` w API (dołożymy, gdy pojawi się potrzeba).
- Filtry fasetowe, konfigurowalne sortowania, agregacje.
- Zapis/modyfikacja przez API (pozostaje read-only).
- Narzędzia MCP dla raportów slotów (BasicAuth) — możliwy Faza 2.1.
- Generator wspólnego katalogu endpointów z jednego YAML.

## Kolejność realizacji

Faza 0 → Faza 1 → Faza 2. Faza 0 odblokowuje uczciwe `szukaj_*` w skillu i MCP.
Każda faza ma osobny plan implementacji i osobny cykl review.
