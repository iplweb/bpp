# Import pracowników — dopasowanie do rekordu głównego (dedup) + wzbogacenie widoków

- **Data:** 2026-07-12
- **Branch:** `feat/import-pracownikow-dedup-ui`
- **Autor specyfikacji:** brainstorming z użytkownikiem (mpasternak)

## Cel

Batch usprawnień w przepływie `import_pracownikow`: (1) jedna zmiana logiki
dopasowania autora (dopasowanie zdublowanych autorów do **rekordu głównego**
przez logikę deduplikatora) oraz (2) dziewięć zmian UI na trzech podstronach
(`/rezultaty/`, `/odpiecia/`, `/audyt/`) — wzbogacenie o ORCID, linki, wskaźnik
PBN-instytucjonalny, spójny wygląd tabel, aktywne wyszukiwanie i akcję zbiorczą.

## Zakres (10 pozycji)

| # | Podstrona / obszar | Pozycja |
|---|---|---|
| 1 | `/odpiecia/` | Przycisk zbiorczy „zaznacz do odpięcia" dla wierszy z bieżącego filtra tabeli (+ odznacz) |
| 2 | `/odpiecia/` | Kolumny ORCID + link do autora BPP (BEZ kolumny „linia XLSX") |
| 3 | `/odpiecia/` | Wspólny wygląd tabeli z `/rezultaty/` |
| 4 | `/rezultaty/` | Kolumna ORCID |
| 5 | `/rezultaty/` | Wskaźnik: autor pochodzi z API instytucjonalnego PBN (`OsobaZInstytucji`) |
| 6 | `/rezultaty/` | Przekolorowanie plakietek statusów (patrz „Schemat plakietek") |
| 7 | logika | Zdublowany autor → dopasowanie do rekordu głównego (deduplikator, **opcja B**), tylko `import_pracownikow` |
| 8 | `/audyt/` | Pełne nazwy jednostek na plakietkach |
| 9 | `/audyt/` | Dane autora: ORCID, link do strony autora BPP, link do adminu |
| 10 | `/audyt/` | Aktywne wyszukiwanie + stronicowanie (DataTables) |

## Punkty integracji (stan istniejący)

- **Dopasowanie autora:** `import_pracownikow/pipeline/analyze.py::_dopasuj_autora_i_status`
  — ścieżka ID (`matchuj_autora`), a poza ID: `znajdz_kandydatow_autora`
  (`import_common/core/autor.py`) → `oblicz_status_pewnosci` →
  `wybierz_autora_z_kandydatow` (`import_pracownikow/pewnosc.py`).
- **Status/plakietki:** `import_pracownikow/pewnosc.py` (`STATUS_*`,
  `STATUS_DISPLAY`, `oblicz_status_pewnosci`, `wybierz_autora_z_kandydatow`),
  render przez `ImportPracownikowRow.confidence_badge` (`models.py:564`).
- **Deduplikator:** `deduplikator_autorow/utils/analysis.py`
  (`analiza_duplikatow(osoba_z_instytucji)`, `_ustal_glownego_autora`),
  `finders.py::_osoba_z_instytucji_autora(autor)` (`autor.pbn_uid.osobazinstytucji`),
  próg wyświetlania `MIN_PEWNOSC_DO_WYSWIETLENIA = 50` (pewność 0–100).
- **„Autorzy zaimportowani z jednostki":** `pbn_api.models.OsobaZInstytucji`
  (`.personId` → `Scientist` → `.rekord_w_bpp` = główny autor BPP).
- **Widoki:** `OdpieciaView`, `ImportPracownikowResultsView`, `LogZmianView`
  (`views.py`); szablony `odpiecia.html`, `importpracownikowrow_list.html`,
  `audyt.html` + partiale `_wiersz_preview_kom.html`, `_odpiecie_row*.html`.
- **URL autora:** `bpp:browse_autor` (pk), admin `admin:bpp_autor_change`.
- **SCSS:** `import_pracownikow` nie ma własnego SCSS; wspólny
  `src/bpp/static/scss/common.scss` jest `@import`-owany przez każdy theme
  `app-*.scss` → tam trafia nowy kolor plakietki.

---

## Pozycja 7 — dopasowanie do rekordu głównego (opcja B)

### Zasada

Gdy dopasowanie po nazwisku daje **≥2 kandydatów na najwyższym tierze pewności**
(dziś zawsze `STATUS_WIELU` → wybór ręczny), spróbuj rozstrzygnąć automatycznie
przez logikę deduplikatora, ale **tylko gdy sygnał jest jednoznaczny**. Ryzyko:
`STATUS_WIELU` powstaje też dla dwóch **różnych** osób o tym samym nazwisku —
auto-wybór w tym przypadku byłby korupcją danych. Dlatego bramka jest
konserwatywna.

### Algorytm `_rozstrzygnij_do_rekordu_glownego(kandydaci)`

Wywoływany w `_dopasuj_autora_i_status` **tylko** gdy wyliczony `status ==
STATUS_WIELU`.

1. **Top-tier:** `top = [k for k in kandydaci if k.pewnosc == kandydaci[0].pewnosc]`.
2. **PBN-backed:** dla każdego `k` w `top` ustal `OsobaZInstytucji`
   (`k.autor.pbn_uid.osobazinstytucji`, wzorzec `_osoba_z_instytucji_autora`,
   z obsługą `RelatedObjectDoesNotExist` i braku `pbn_uid`).
3. Jeśli **dokładnie jeden** kandydat z `top` jest PBN-backed → `osoba` = jego
   `OsobaZInstytucji`, `glowny = _ustal_glownego_autora(osoba)`.
   W przeciwnym razie (0 lub ≥2 PBN-backed, albo `glowny is None`) → **zwróć
   `(None, STATUS_WIELU)`** (wybór ręczny).
4. `analiza = analiza_duplikatow(osoba)`; zbuduj mapę
   `{a["autor"].pk: a["pewnosc"] for a in analiza["analiza"]}` (pewność 0–100).
5. **Bramka potwierdzenia:** każdy kandydat z `top` **inny niż `glowny`** musi
   być w mapie z `pewnosc >= PROG_AUTO_DEDUP`. Jeśli tak (wszystkie pozostałe to
   potwierdzone duplikaty rekordu głównego) → **zwróć `(glowny, STATUS_DEDUP)`**.
   Jeśli którykolwiek pozostały kandydat nie jest potwierdzonym duplikatem →
   **zwróć `(None, STATUS_WIELU)`** (bezpieczeństwo > automatyzacja).
6. `glowny` może NIE być wśród `top` (name-match go nie znalazł, np. inne
   nazwisko) — to poprawne: sedno pozycji to dopasowanie do rekordu głównego,
   nie do żadnego z name-kandydatów. Bramka z pkt. 5 dalej działa (wszystkie
   `top` to wtedy duplikaty).

### Parametr do zatwierdzenia

- `PROG_AUTO_DEDUP` — próg pewności deduplikatora do **automatycznego** scalenia.
  Musi być **wyższy** niż próg wyświetlania (`50`). Proponowany **domyślny: 80**
  (0–100). Wartość wydzielona jako nazwana stała w `import_pracownikow`
  (nie w deduplikatorze), do rewizji w planie/PR.

### Wydajność

- `analiza_duplikatow` (+ `szukaj_kopii` + zgadywanie płci + 8 ocen) uruchamiane
  wyłącznie dla wierszy `STATUS_WIELU` z **dokładnie jednym** PBN-backed
  kandydatem — mniejszość wierszy.
- **Memoizacja per `osoba.pk`** w obrębie jednego przebiegu analizy (ta sama
  osoba instytucjonalna bywa kandydatem dla wielu wierszy o tym samym nazwisku).

### Transparentność / audyt

- Nowy status `STATUS_DEDUP = "dedup"` (autom. dopasowanie do rekordu głównego).
- Przy rozstrzygnięciu zapis do `log_zmian`/diff wiersza: „auto-dopasowano do
  rekordu głównego #<pk> (deduplikator, pewność N%)".
- `STATUS_DEDUP` traktowany jak status **rozstrzygnięty**:
  - dołączyć do `confidence__in=[STATUS_TWARDY, STATUS_RECZNY]` w
    `ImportPracownikowResultsView.get_queryset` (`_prio` → na dół listy),
  - dodać do `CONFIDENCE_CHOICES` + `STATUS_DISPLAY`,
  - migracja stanu Django dla `choices` pola `confidence` (no-op DB;
    **nowa** migracja `002x`, nie modyfikacja istniejących).

### Zależność między pozycjami

Pozycja 5 (wskaźnik PBN-instytucjonalny) i pozycja 7 dzielą to samo zapytanie
`autor.pbn_uid.osobazinstytucji` — wspólny helper
`autor_ma_osobe_z_instytucji(autor)` w `import_common` lub `import_pracownikow`,
z prefetch/adnotacją w widokach, by uniknąć N+1.

---

## Schemat plakietek statusów (pozycja 6 + 7)

Zmiana w `import_pracownikow/pewnosc.py::STATUS_DISPLAY`. Kolory Foundation
dostępne (skompilowane): `success`, `warning`, `primary`, `secondary`, `alert`.
`info`/`debug` **nie istnieją** w zbudowanym CSS.

| status | kolor (było → jest) | ikona | etykieta |
|---|---|---|---|
| twardy | success (bez zmian) | fi-check | twardy match |
| **dedup** (nowy) | **primary** (zwolniony przez wielu→alert) | fi-torsos | rekord główny |
| zgadywanie | warning (bez zmian) | fi-flag | zgadywanie |
| **wielu** | primary → **alert** | fi-page-multiple | wielu kandydatów |
| brak | secondary (bez zmian) | fi-minus-circle | brak dopasowania |
| **reczny** | success → **kolor custom** | fi-pencil | wybór użytkownika |

- **reczny** dostaje **własny kolor** (custom): nowa reguła
  `.label.import-reczny { background-color: <fiolet, np. #7b3fa0>; color: #fefefe; }`
  w `src/bpp/static/scss/common.scss` (po komponencie label Foundation), potem
  `grunt build`. `confidence_badge` zwraca wtedy klasę `import-reczny` zamiast
  klasy Foundation dla statusu ręcznego (render: `class="label {{ klasa }}"`).
- Wszystkie sześć stanów pozostaje rozróżnialnych parą (kolor, ikona).

---

## Zmiany UI

### `/rezultaty/` (poz. 4, 5)

- Kolumna „Autor" (`_wiersz_preview_kom.html`): pod linkiem do autora dołożyć
  ORCID (link `https://orcid.org/<orcid>` gdy niepusty) oraz — gdy autor ma
  `OsobaZInstytucji` — małą plakietkę „PBN" (np. `label secondary` + tooltip
  „z API instytucjonalnego PBN").
- `ImportPracownikowResultsView`: prefetch/adnotacja „ma OsobaZInstytucji" po
  `autor.pbn_uid` (bez N+1). `orcid`/`tytul` już na `Autor`.

### `/odpiecia/` (poz. 1, 2, 3)

- **Kolumny** (`_odpiecie_row_kom.html`): „Autor" jako **link** do
  `bpp:browse_autor` + ORCID (jak w rezultaty); nowa kolumna „ORCID" lub ORCID
  inline pod nazwiskiem — spójnie z rezultaty. **Bez** kolumny „linia XLSX".
- `OdpieciaView.get_queryset` już `select_related` autora/tytuł/jednostkę;
  dołożyć `autor_jednostka__autor__pbn_uid` jeśli pokazujemy wskaźnik PBN
  (opcjonalnie, spójnie z rezultaty).
- **Przycisk zbiorczy (poz. 1):** przycisk „Zaznacz do odpięcia zaznaczone w
  tabeli" + „Odznacz wszystkie z bieżącego wyboru". Działanie **po stronie
  klienta**: JS czyta wiersze przechodzące bieżący filtr DataTables
  (`dt.rows({search:'applied'})`), zbiera ich `odp.pk`, wysyła **POST** do
  nowego endpointu zbiorczego.
  - Nowy widok `ZaznaczOdpieciaView` (wzorzec `ZaznaczWszystkiePrzepieciaView`):
    owner/superuser-scope + bramka `edytowalny_podglad`; przyjmuje listę
    `odp_pk[]` + flagę `zaznacz` (true/false); `update(zaznaczone=...)`
    filtrowane po `parent` i `pk__in`; zwraca JSON lub redirect z komunikatem.
  - Nowy URL `<uuid:pk>/odpiecia/zaznacz/`.
  - Puste wyszukiwanie → filtr obejmuje wszystkie wiersze (naturalne „zaznacz
    wszystkie").
- **Wspólny wygląd (poz. 3):** ten sam init DataTables i te same kolumny/
  klasy co `/rezultaty/`.

### `/audyt/` (poz. 8, 9, 10)

- **Poz. 8:** plakietka jednostki → `jednostka.nazwa` (pełna) zamiast
  `jednostka.skrot`; `skrot` do `title=` (tooltip).
- **Poz. 9:** w sekcji „Zmiany per wiersz" dane autora: ORCID (link),
  link do `bpp:browse_autor`, link do `admin:bpp_autor_change`.
- **Poz. 10:** sekcję „Zmiany per wiersz" przebudować na **tabelę DataTables**
  (kolumny: Autor / Jednostka / Zmiany) z aktywnym wyszukiwaniem i
  **stronicowaniem** (tu paging **włączony** — widok read-only po integracji,
  brak per-wierszowego HTMX do zachowania). Usunąć serwerowe `is_paginated`
  (Django Paginator) z `LogZmianView` / szablonu — DataTables przejmuje paging
  i search po stronie klienta. Kolumna „Zmiany" = `<ul>` z `log_zmian_lista`.
  - `LogZmianView`: ładować wszystkie wiersze ze zmianami (bez serwerowej
    paginacji); prefetch autora + `pbn_uid` + jednostki (bez N+1).

---

## Testy

- **Poz. 7 (priorytet):**
  - Dwa różne rekordy tego samego autora (główny z `OsobaZInstytucji`+ORCID+tytuł,
    duplikat bez) o identycznej pewności nazwiskowej → `STATUS_DEDUP`, autor =
    główny.
  - Dwie **różne** osoby o tym samym nazwisku (obie bez lub obie z PBN, brak
    potwierdzenia duplikatu) → pozostaje `STATUS_WIELU` (brak auto-wyboru).
  - Duplikat poniżej `PROG_AUTO_DEDUP` → `STATUS_WIELU`.
  - Główny spoza top-tier (name-match nie znalazł głównego) → auto-wybór
    głównego, gdy wszystkie top-tier to potwierdzone duplikaty.
  - Memoizacja: `analiza_duplikatow` liczone raz per `osoba` w przebiegu.
- **UI:** render kolumn ORCID/linków (rezultaty, odpiecia, audyt); klasa
  plakietki per status (rozszerzyć `test_confidence_badge_*`); endpoint zbiorczy
  odpięć (owner-scope, bramka podglądu, filtrowanie `pk__in`, toggle
  zaznacz/odznacz); pełna nazwa jednostki w audycie.
- Konwencje: pytest (bez klas), `@pytest.mark.django_db`, `model_bakery.baker`.

## Poza zakresem / ryzyka

- Brak zmian w `import_common` widocznych dla innych importerów (poz. 7 lokalna).
- Brak pełnego UI scalania duplikatów — używamy tylko *odczytu* analizy
  deduplikatora do wyboru rekordu głównego (bez `scal_autora`).
- `PROG_AUTO_DEDUP` = decyzja jakościowa; domyślnie konserwatywnie (80),
  do rewizji.
- DataTables w audycie ładuje wszystkie wiersze do DOM — dla bardzo dużych
  importów rozważyć limit; obecnie spójne z pozostałymi tabelami przepływu.
- Newsfragment (`src/bpp/newsfragments/`, `.feature.rst`) po implementacji.
- Baseline: nowa migracja `choices` — odświeżyć baseline dopiero przy scalaniu.
