# Opis bibliograficzny: wydawnictwo nadrzędne z PBN + synchronizacja dbtemplate

Data: 2026-06-21
Ticket: Freshdesk #329 ("wyd. zwarte - problem")

## Kontekst

Zgłoszenie #329 (Biblioteka Naukowa IHiT): dodano rozdział książki, którego
**wydawnictwo nadrzędne pobrano z PBN**, ale nie wyświetla się ono jako
wydawnictwo nadrzędne w opisie bibliograficznym BPP.

## Diagnoza

Splatają się tu **dwa niezależne problemy** wokół jednego objawu.

### Trzy warstwy "starości" opisu bibliograficznego

1. **dbtemplate** `opis_bibliograficzny.html` — wiersz w tabeli
   `django_template` (django-dbtemplates). Loader `dbtemplates.loader.Loader`
   stoi w łańcuchu **przed** loaderem dyskowym
   (`src/django_bpp/settings/base.py:257`), więc wiersz w bazie **zasłania**
   plik z dysku. Wiersz jest jednorazowo zasiewany migracją
   `src/bpp/migrations/0295_instaluj_szablony.py`; późniejsze zmiany pliku na
   dysku **nie propagują się** do istniejących instalacji.
2. **`opis_bibliograficzny_cache`** — pole `@denormalized` (per rekord),
   przechowujące wyrenderowany HTML
   (`src/bpp/models/wydawnictwo_zwarte.py:309` itd.). Nawet po naprawie
   szablonu trzeba je przerenderować.
3. **`cache.Rekord.opis_bibliograficzny_cache`** — zmaterializowana kopia
   stringa (`src/bpp/models/cache/rekord.py:245`). Przepisuje gotowy string ze
   źródła; nie renderuje samodzielnie — naprawia się automatycznie, gdy model
   źródłowy przerenderuje.

> Uwaga nazewnicza: **nie istnieje** plik `opis_bibliograficzny_cache.html`.
> To skrót myślowy łączący dbtemplate `opis_bibliograficzny.html` z polem
> `opis_bibliograficzny_cache`.

### Problem A — renderowanie rodzica z PBN

Szablon `src/bpp/templates/opis_bibliograficzny.html:33-37` renderuje "W:"
tylko dla dwóch źródeł rodzica, **tytułem**:

```django
{% if praca.wydawnictwo_nadrzedne.tytul_oryginalny %}
    W: {{ praca.wydawnictwo_nadrzedne.tytul_oryginalny }}.
{% elif praca.wydawnictwo_nadrzedne_w_pbn.title %}
    W: {{ praca.wydawnictwo_nadrzedne_w_pbn.title }}.
{% endif %}
```

- `wydawnictwo_nadrzedne` — FK self (rodzic w BPP).
- `wydawnictwo_nadrzedne_w_pbn` — kurowany FK do `pbn_api.Publication`
  (`wydawnictwo_zwarte.py:221`), ustawiany ręcznie (autocomplete) lub w
  kreatorze importera (`importer_publikacji/views/wizard.py:266`).

Brakuje **trzeciego źródła**: gdy rozdział zaimportowano z PBN, jego własny
`pbn_uid` wskazuje publikację PBN, a rodzic siedzi w surowym JSON-ie tej
publikacji pod `object.book` — i **nic** tego nie renderuje ani nie wystawia
jako property. To najpewniejszy scenariusz dla #329 ("pobrane z PBN" = import,
`pbn_uid` ustawiony, kurowany FK **nie**).

Ograniczenie techniczne: szablon Django nie umie wywołać
`value_or_none("object", "book", "title")` (brak argumentów w wywołaniach
szablonowych). Dlatego to **jedyne** źródło wymaga drobnej warstwy Pythona,
żeby było osiągalne z szablonu.

### Problem B — dystrybucja poprawek dbtemplate

Nawet gdy plik na dysku jest poprawny, instalacje mają **stary wiersz w
bazie**. Istnieje read-only `compare_dbtemplates`
(`src/bpp/management/commands/compare_dbtemplates.py`, diff DB↔dysk), ale
**brak** mechanizmu, który wepchnąłby poprawkę z dysku do bazy. Ustalono, że
praktycznie **żadna instalacja nie kastomizuje** dbtemplates (poza
marginalnymi szablonami do druku).

## Decyzje (zatwierdzone)

- **Problem A:** logika renderowania zostaje **w szablonie** (title-only,
  spójnie z dotychczasowym zachowaniem; szablon i tak ma masę warunków, a
  bibliotekarz może go samodzielnie poprawić). Jedyny Python to **drobny
  akcesor** `book_title` na `pbn_api.Publication`, wyłącznie po to, by szablon
  mógł sięgnąć do `object.book.title`.
- **Problem B:** wariant **Hybrid** — komenda zarządzająca **oraz** akcja w
  adminie, obie pokazujące diff DB↔dysk przed wykonaniem akcji **pull**
  (nadpisz wiersz z dysku) lub **reset** (skasuj wiersz → fallback na dysk).
  Model "DB jest źródłem prawdy" pozostaje; reużywamy istniejącą maszynerię
  przebudowy cache po zapisie szablonu.

## Część A — rendering wydawnictwa nadrzędnego z PBN

### A1. Akcesor `book_title` na `pbn_api.Publication`

Plik: `src/pbn_api/models/publication.py`. Wzorowany 1:1 na istniejącym
`journal` (`publication.py:39-41`):

```python
@cached_property
def book(self):
    return self.value_or_none("object", "book")

@cached_property
def book_title(self):
    book = self.book
    return book.get("title") if book else None
```

To czysta hydraulika (wystawienie wartości JSON), nie logika biznesowa.

### A2. Gałąź w szablonie

Plik: `src/bpp/templates/opis_bibliograficzny.html`, dopisana **trzecia**
gałąź `elif` (title-only, spójnie z istniejącymi):

```django
{% if praca.wydawnictwo_nadrzedne.tytul_oryginalny %}
    W: {{ praca.wydawnictwo_nadrzedne.tytul_oryginalny }}.
{% elif praca.wydawnictwo_nadrzedne_w_pbn.title %}
    W: {{ praca.wydawnictwo_nadrzedne_w_pbn.title }}.
{% elif praca.pbn_uid.book_title %}
    W: {{ praca.pbn_uid.book_title }}.
{% endif %}
```

`praca` to `Wydawnictwo_Zwarte` (dziedziczy `ModelZPBN_UID` →
`pbn_uid` jako OneToOne do `pbn_api.Publication`,
`src/bpp/models/abstract/pbn.py:133-135`), więc `praca.pbn_uid.book_title`
jest osiągalne w czasie renderowania.

### A3. Testy

- `src/pbn_api/tests/` — unit dla `Publication.book` / `book_title`
  (JSON z `object.book.title`, brak `object.book` → `None`).
- `src/bpp/tests/test_opis_bibliograficzny.py` — rozszerzyć: rozdział z
  `pbn_uid` mającym `object.book.title`, bez `wydawnictwo_nadrzedne` i bez
  `wydawnictwo_nadrzedne_w_pbn` → opis zawiera `W: <tytuł>.`. Plus test
  pierwszeństwa (gdy ustawiony FK BPP, wygrywa on nad PBN-em).

### A4. Znane ograniczenie (świadomie poza zakresem)

`opis_bibliograficzny_cache` (`@denormalized` + `@depend_on_related`) nie
przebuduje się automatycznie, gdy zmieni się **JSON** publikacji PBN
(`object.book`), bo zależność denorm tego nie obejmuje. To samo ograniczenie
dotyczy istniejącej gałęzi `wydawnictwo_nadrzedne_w_pbn`. Dla #329 wystarcza
jednorazowa przebudowa cache po wdrożeniu (patrz Część B / kolejność). Pełne
podpięcie pod denorm — osobny temat.

## Część B — synchronizacja dbtemplate (Hybrid)

### B1. Komenda `update_dbtemplates`

Nowy plik: `src/bpp/management/commands/update_dbtemplates.py`. Symetryczna do
`compare_dbtemplates`; reużywa jego logikę liczenia diffa (refaktor wspólnego
kodu do helpera albo import). Sygnatura:

```
manage.py update_dbtemplates [template_names...] [opcje]
  --diff              pokaż unified diff DB↔dysk i nie zmieniaj nic
  --dry-run           jak --diff: tylko raport, bez zapisu
  --pull              nadpisz content wiersza w bazie treścią z dysku
  --reset-to-disk     skasuj wiersz w bazie (get_template → fallback na dysk)
  --all               działaj na wszystkich wierszach dbtemplates
  -y / --yes          nie pytaj interaktywnie (dla deployu)
```

- Domyślnie (bez `--pull`/`--reset-to-disk`) zachowuje się jak `--diff`
  (bezpieczny default: pokaż, nie ruszaj).
- Po `--pull`/`--reset-to-disk`: wywołaj istniejącą maszynerię odświeżenia
  cache, tę samą co admin (`src/bpp/admin/templates.py:52-90`,
  `template_updated` → `remove_cached_template`, czyszczenie `CachedLoader`,
  `rebuild_instances_of_models`). Wydzielić ją do funkcji wywoływalnej spoza
  ModelAdmin (np. `bpp/admin/templates.py` lub `bpp/templates_sync.py`), żeby
  komenda i admin korzystały z jednego źródła.
- Czytanie treści z dysku: **nie** przez `get_template()` (łapie wersję z DB
  przez loader dbtemplates), tylko bezpośrednio z loadera dyskowego /
  ścieżki origin. (To istniejący błąd w `compare_dbtemplates`
  `get_filesystem_template_content` — przy okazji naprawić w wspólnym
  helperze.)

### B2. Akcja w adminie "Zaciągnij z dysku"

Plik: `src/bpp/admin/templates.py` (`BppTemplateAdmin`) + szablon
`src/django_bpp/templates/admin/dbtemplates/template/change_form.html`
(już ma blok `object-tools-items` z podglądem dla `opis_bibliograficzny.html`).

- Dodać przycisk **"Zaciągnij z dysku"** (per szablon), który otwiera widok
  pokazujący **diff DB↔dysk** (reużycie helpera z B1) i daje dwa działania:
  **Pull** (nadpisz z dysku) oraz **Reset** (skasuj wiersz → fallback).
- Po wykonaniu: ta sama ścieżka odświeżenia cache co `template_updated`.
- Gdy DB == dysk: przycisk pokazuje "brak różnic" (nic do zrobienia).

### B3. Testy

- `src/bpp/tests/test_admin/test_templateadmin.py` — rozszerzyć: diff,
  pull (content zmieniony, cache przebudowany), reset (wiersz skasowany,
  render leci z dysku).
- Nowy test komendy `update_dbtemplates` (`--diff`, `--pull`,
  `--reset-to-disk`, `--all`, `-y`).

## Kolejność wdrożenia

1. **Część A** (akcesor + gałąź szablonu + testy) — to właściwa poprawka #329
   na poziomie kodu/dysku.
2. **Część B** (komenda + admin) — mechanizm dystrybucji.
3. **Wdrożenie na instalację IHiT:** `update_dbtemplates opis_bibliograficzny.html
   --pull` (albo `--reset-to-disk`, skoro nie kastomizują) → przebudowa cache →
   weryfikacja na realnym rekordzie
   (`bpp.ihit.waw.pl/.../Niedokrwistosc-u-ciezarnych-...`). Jeśli rekord
   okaże się scenariuszem (a) (ustawiony kurowany FK), sama Część B go naprawia;
   Część A zabezpiecza scenariusz (b) i przyszłe importy.

## Poza zakresem (świadomie)

- Wzbogacanie "W:" o redaktorów / pełny opis bibliograficzny rodzica
  ("(red.)" itp.) — BPP nigdy tego nie robił; osobna funkcja, nie część #329.
- Odwrócenie domyślnego źródła (dysk-authoritative, kasowanie wszystkich
  niezmienionych wierszy) — rozważane, odrzucone na rzecz Hybrid.
- Podpięcie `object.book` pod zależności denorm (auto-refresh cache przy
  zmianie JSON PBN) — osobny temat (patrz A4).

## Dotknięte pliki

- `src/pbn_api/models/publication.py` — akcesor `book`/`book_title`.
- `src/bpp/templates/opis_bibliograficzny.html` — trzecia gałąź "W:".
- `src/bpp/management/commands/update_dbtemplates.py` — nowa komenda.
- `src/bpp/management/commands/compare_dbtemplates.py` — refaktor wspólnego
  helpera diff/odczyt-z-dysku.
- `src/bpp/admin/templates.py` — akcja "Zaciągnij z dysku" + wydzielenie
  funkcji odświeżania cache.
- `src/django_bpp/templates/admin/dbtemplates/template/change_form.html` —
  przycisk akcji.
- Testy: `src/pbn_api/tests/...`, `src/bpp/tests/test_opis_bibliograficzny.py`,
  `src/bpp/tests/test_admin/test_templateadmin.py`, test nowej komendy.
