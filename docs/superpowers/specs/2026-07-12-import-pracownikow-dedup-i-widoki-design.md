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
| 7 | logika | Zdublowany autor → operacje zatrudnienia (przypisanie do jednostki, zmiana miejsca pracy, przepięcia) kierowane na rekord **oryginalny/główny** (ORCID + tytuł + PBN instytucjonalny), **BEZ scalania rekordów**, tylko `import_pracownikow` |
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

## Pozycja 7 — operacje zatrudnienia kierowane na rekord ORYGINALNY

### Zasada (DOPRECYZOWANE przez użytkownika)

**NIE scalamy rekordów autorów podczas importu.** Zmiana dotyczy wyłącznie tego,
do **którego rekordu autora** import podpina operacje zatrudnienia
(`Autor_Jednostka`: przypisanie do jednostki, zmiana miejsca pracy, przepięcia
dorobku). Gdy dopasowanie po nazwisku trafia na **rekord-duplikat**, import ma
podpiąć zatrudnienie do **rekordu oryginalnego/głównego** — tego z ORCID,
tytułem i odpowiednikiem w API instytucjonalnym PBN (`OsobaZInstytucji`). Żaden
rekord nie jest usuwany ani łączony (`scal_autora` **nie** jest wołane).

### Mechanizm — persystowany `DuplicateCandidate` (nie live analiza)

Deduplikator zapisuje wyniki skanu w `deduplikator_autorow.models.DuplicateCandidate`:
`duplicate_autor` (duplikat) → `main_autor` (oryginał, z `OsobaZInstytucji`/
`pbn_uid`), z `confidence_percent` (0.0–1.0), `confidence_score` (surowy) i
`status` (`pending`/`merged`/`not_duplicate`). To gotowa, przeglądalna przez
operatora, **odwrotna** mapa duplikat→oryginał — dużo tańsza niż uruchamianie
`analiza_duplikatow` per wiersz. („Opcja B" = logika deduplikatora; używamy jej
**zmaterializowanej** formy zamiast liczyć na żywo.)

### Helper `kanoniczny_autor(autor) -> Autor`

Czysty helper (w `import_pracownikow`, np. `dedup.py`):

1. Jeśli istnieje `NotADuplicate` dla `autor` → zwróć `autor` (operator
   zawetował — nie przekierowuj).
2. Znajdź najlepszy `DuplicateCandidate` gdzie `duplicate_autor == autor`,
   `status != NOT_DUPLICATE`, `confidence_percent >= PROG_KANONICZNY`,
   sort po `-confidence_percent` (bierz `main_autor` najpewniejszego).
   - Uszanuj też `main_osoba_z_instytucji`/`main_autor` jako „oryginał"
     (ma pochodzić z PBN instytucjonalnego — to gwarantuje konstrukcja skanu).
3. Jeśli znaleziono → zwróć `main_autor`; inaczej zwróć `autor` (no-op).

Idempotentny: dla rekordu, który sam jest `main_autor` (nie występuje jako
`duplicate_autor`), zwraca wejściowy autor.

### Punkt wpięcia

W `_dopasuj_autora_i_status` (`analyze.py`), **po** ustaleniu `(autor, status,
kandydaci)` i **tylko** gdy `autor is not None` (twardy/zgadywanie/ID):

```
autor_kanoniczny = kanoniczny_autor(autor)
if autor_kanoniczny != autor:
    # przekierowanie zatrudnienia na oryginał; zapamiętaj do audytu/badge
    status = STATUS_DEDUP
    autor = autor_kanoniczny
```

- Dla `STATUS_WIELU`/`STATUS_BRAK` (brak auto-autora) nie przekierowujemy —
  wybór należy do operatora. Po ręcznym wyborze (`DopasujAutoraView`/
  `WybierzKandydataView`) można opcjonalnie zaproponować oryginał, ale to
  **poza zakresem** tej iteracji (patrz Ryzyka).
- Dla dopasowania po `pbn_uid` (ID-path) rekord i tak jest zwykle oryginałem
  (duplikaty nie mają `pbn_uid`) → helper jest no-opem. Poprawne.

### Parametr do zatwierdzenia

- `PROG_KANONICZNY` — minimalny `confidence_percent` z `DuplicateCandidate`, przy
  którym ufamy relacji duplikat→oryginał na tyle, by przekierować zatrudnienie.
  Musi być **wyższy** niż próg wyświetlania deduplikatora
  (`MIN_PEWNOSC_DO_WYSWIETLENIA = 50` na skali 0–100 ≈ `0.5`). Proponowany
  **domyślny: 0.80**. Stała w `import_pracownikow`, do rewizji w PR.

### Zależność od skanu (WAŻNE)

Przekierowanie działa **tylko dla par duplikat→oryginał obecnych w
`DuplicateCandidate`**, tj. gdy skan deduplikatora został uruchomiony i pokrył
danego autora. Brak wpisu → brak przekierowania (bezpieczny no-op, import działa
jak dziś). Live `analiza_duplikatow` jako fallback dla nieprzeskanowanych
autorów — **poza zakresem** (droższe per-wiersz; do rozważenia osobno).

### Transparentność / audyt

- Nowy status `STATUS_DEDUP = "dedup"` — etykieta „rekord główny"
  (NIE „scalono"): wiersz dopasowano do rekordu oryginalnego.
- Zapis do `log_zmian`/diff wiersza: „zatrudnienie przypisane do rekordu
  głównego #<main_pk> (zamiast duplikatu #<dup_pk>, deduplikator, pewność N%)".
- `STATUS_DEDUP` traktowany jak status **rozstrzygnięty**:
  - dołączyć do `confidence__in=[STATUS_TWARDY, STATUS_RECZNY]` w
    `ImportPracownikowResultsView.get_queryset` (`_prio` → na dół listy),
  - dodać do `CONFIDENCE_CHOICES` + `STATUS_DISPLAY`,
  - migracja stanu Django dla `choices` pola `confidence` (no-op DB;
    **nowa** migracja `002x`, nie modyfikacja istniejących).

### Zależność między pozycjami

Pozycja 5 (wskaźnik PBN-instytucjonalny) dzieli sygnał „autor ma
`OsobaZInstytucji`" (`autor.pbn_uid.osobazinstytucji`) — wspólny helper
`autor_ma_osobe_z_instytucji(autor)` z prefetch/adnotacją w widokach (bez N+1).

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
  - Name-match trafia na duplikat; istnieje `DuplicateCandidate`
    duplikat→oryginał z `confidence_percent >= PROG_KANONICZNY` i
    `status != not_duplicate` → `row.autor == main_autor`, `STATUS_DEDUP`;
    `Autor_Jednostka` powstaje dla **oryginału**, duplikat nietknięty.
  - `DuplicateCandidate` poniżej `PROG_KANONICZNY` → brak przekierowania
    (autor = trafiony rekord, status bez zmian).
  - `NotADuplicate` dla trafionego autora → brak przekierowania (weto operatora).
  - Brak jakiegokolwiek `DuplicateCandidate` dla autora → no-op (autor bez zmian).
  - Dopasowanie po `pbn_uid` do oryginału → `kanoniczny_autor` no-op
    (oryginał nie występuje jako `duplicate_autor`).
  - Idempotencja: `kanoniczny_autor(main_autor) == main_autor`.
  - `STATUS_WIELU`/`STATUS_BRAK` (brak auto-autora) → przekierowanie się nie
    odpala.
  - Audyt: log zawiera `main_pk` i `dup_pk`.
- **UI:** render kolumn ORCID/linków (rezultaty, odpiecia, audyt); klasa
  plakietki per status (rozszerzyć `test_confidence_badge_*`); endpoint zbiorczy
  odpięć (owner-scope, bramka podglądu, filtrowanie `pk__in`, toggle
  zaznacz/odznacz); pełna nazwa jednostki w audycie.
- Konwencje: pytest (bez klas), `@pytest.mark.django_db`, `model_bakery.baker`.

## Poza zakresem / ryzyka

- Brak zmian w `import_common` widocznych dla innych importerów (poz. 7 lokalna).
- **Nie scalamy rekordów** — tylko *odczyt* `DuplicateCandidate` do wyboru
  rekordu, do którego trafia zatrudnienie (`scal_autora` NIE jest wołane).
- **Zależność od skanu:** przekierowanie działa tylko dla par obecnych w
  `DuplicateCandidate` (deduplikator musiał przeskanować autora). Brak wpisu →
  no-op. Live `analiza_duplikatow` jako fallback — poza zakresem.
- **Ręczny wybór** operatora (`STATUS_WIELU`) nie jest auto-przekierowywany —
  poza zakresem tej iteracji.
- `PROG_KANONICZNY` = decyzja jakościowa; domyślnie konserwatywnie (0.80),
  do rewizji.
- DataTables w audycie ładuje wszystkie wiersze do DOM — dla bardzo dużych
  importów rozważyć limit; obecnie spójne z pozostałymi tabelami przepływu.
- Newsfragment (`src/bpp/newsfragments/`, `.feature.rst`) po implementacji.
- Baseline: nowa migracja `choices` — odświeżyć baseline dopiero przy scalaniu.
