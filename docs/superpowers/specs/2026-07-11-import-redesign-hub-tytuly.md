# Import pracowników — hub z kafelkami, dopasowanie autora, reconciler tytułów

**Data:** 2026-07-11
**Gałąź:** `feat/import-pracownikow-tworzenie-jednostek` (kontynuacja)
**Status:** design zatwierdzony przez użytkownika, do przejrzenia przed planem

## Cel

Przeprojektować ekran szczegółów importu pracowników w trzech spójnych krokach:

1. **Dopasowanie autora** — kolumna „Akcje / zmiany" przestaje pozwalać na
   edycję danych wejściowych z XLS-a; zamiast tego pozwala *dopasować wiersz do
   istniejącego autora BPP* (albo utworzyć nowego).
2. **Hub z kafelkami** — jedna długa strona szczegółów rozbita na landing z
   2–4 kafelkami (Jednostki / Ludzie z XLS / Ludzie spoza XLS / Tytuły) i
   skupione podstrony. Te same widoki, inaczej rozłożone.
3. **Reconciler tytułów** — tytuły naukowe matchowane/tworzone przy imporcie
   analogicznie do jednostek (klasyfikacja → ekran decyzji → tworzenie).

Zero utraty funkcjonalności — wszystkie dzisiejsze akcje zostają, przesunięte
lub przebudowane. Bez zmian w modelu domenowym BPP (`bpp.Autor`, `bpp.Tytul`,
`bpp.Jednostka` bez migracji); nowe pola tylko w modelach `import_pracownikow`.

## Architektura (skrót)

Import ma pipeline dwufazowy: **analiza** (`pipeline/analyze.py`, dry-run,
klasyfikuje i odracza niedopasowania) i **integracja** (`pipeline/integrate.py`,
commit). Wzorzec „reconcilera" już istnieje dla jednostek:

- klasyfikacja: `import_common/core/jednostka.py::sklasyfikuj_jednostke`
  (twardy / zgadywanie / brak, trigram),
- decyzja per unikalna nazwa: model `ImportPracownikowJednostka`
  (dedup iexact, pola liczone przez analizę + wybory usera),
- odświeżanie decyzji przez (re)analizę: `analyze.py::_ReconcilerJednostek`,
- rozstrzygnięcie w commit: `integrate.py::_rozstrzygnij_jednostki`
  (FAZA 0, przed snapshotem i fazą autorów; idempotentne przez guard
  `utworzona`), + `_podlacz_wiersze_do_jednostek`.

Część 3 (tytuły) **wiernie kopiuje ten wzorzec**. Części 1–2 to warstwa
widoków/szablonów + nowe endpointy htmx.

## Tech stack

Django, Foundation CSS (ikony Foundation-Icons w publicznym froncie), htmx 2
(już używane w podglądzie), django-autocomplete-light (Select2) dla wyszukiwarki
autorów, django-liveops (strona live), PostgreSQL `pg_trgm` (TrigramSimilarity).

## Ograniczenia globalne (dotyczą każdego zadania planu)

- **Max długość linii: 88 znaków** (ruff).
- **`uv run` przed każdym poleceniem Pythona**; testy `pytest` z `-n auto`
  (patrz reguły projektu), output do pliku + grep, nie dwukrotnie.
- **Nie modyfikować WYDANYCH migracji.** Migracja `0016` (tworzenie jednostek)
  jest na tej gałęzi, NIEwydana — ale i tak dokładamy **nową migrację `0017`**
  (nie dotykamy 0016), bo 0016 jest już zacommitowana i na niej stoją inne
  zmiany. Baseline (`make baseline-update`) odświeżyć **raz, przy scaleniu**
  gałęzi (obejmie 0016 + 0017) — NIE w tej pracy.
- **Komentarze Django `{# #}` jedno-liniowe** (każda linia własne `{# … #}`),
  albo `{% comment %}…{% endcomment %}`.
- **Ikony:** publiczny front → Foundation-Icons (`<span class="fi-…">`).
- **Testy:** pytest-style (funkcje, `@pytest.mark.django_db`, `baker.make`),
  fixtures z `src/conftest.py`. Select2/AJAX testy: symulować pisanie
  (`select_select2_autocomplete`), nie wstrzykiwać PK.
- **Bez `except: pass`** — logować / re-raise / sensowny błąd.

## Stan obecny (co przebudowujemy)

Ekran szczegółów to dziś **jedna strona** `importpracownikowrow_list.html`
(widok `ImportPracownikowResultsView`, URL `importpracownikow-results`):

- callout „N jednostek wymaga weryfikacji" + link do `jednostki`,
- akcja zbiorcza „zaznacz przepięcia",
- tabela wierszy (partial `_wiersz_preview.html`) z kolumną **Akcje / zmiany**,
- **na dole** sekcja „odpięcia" (powiązania spoza pliku).

Kolumna „Akcje / zmiany" w stanie `przeanalizowany` renderuje dziś (partial
`_wiersz_preview.html`):

- `wielu`: `<select name="wybrany_kandydat">` → `WybierzKandydataView`
  (`wybierz-kandydata`) — wybór spośród policzonych kandydatów;
- **zawsze**: formularz free-text `imiona`/`nazwisko`/`tytuł` + „popraw" →
  `EdytujWierszView` (`edytuj-wiersz`) → `_rematch_wiersz` — **to jest
  „edycja XLS-a", którą usuwamy**;
- `brak`: checkbox „utwórz nowego autora" → `PrzelaczUtworzNowegoView`
  (`utworz-nowego`).

Ekran `jednostki` (`WeryfikacjaJednostekView` + `weryfikacja_jednostek.html`)
już istnieje i jest wzorcem dla ekranu tytułów.

Statusy dopasowania autora (`import_pracownikow/pewnosc.py`, `STATUS_*`) — są
**cztery**: `twardy` (dokładny, badge success), `zgadywanie` (auto-match
trigramowy, pojedynczy kandydat — badge warning), `wielu` (remis kandydatów —
badge primary), `brak` (badge secondary). Wiersze `twardy`/`zgadywanie` mają już
auto-wybrany `row.autor` (`wybierz_autora_z_kandydatow`); `wielu`/`brak` mają
`row.autor=None` (decyzję podejmuje user).

---

## Część 1 — Dopasowanie autora (kolumna „Akcje / zmiany")

### Decyzje (zatwierdzone)

- Wyszukiwarka autora dla `brak` → **dedykowany, nowy autocomplete**
  `import-autor-autocomplete`. **KOREKTA PO REVIEW (ważne): NIE istniejący
  `autor-z-uczelni-autocomplete`** — ten filtruje `aktualnie_zatrudnieni`
  (`aktualna_jednostka__uczelnia=…, skupia_pracownikow=True`), a wiersze `brak`
  to typowo osoby OBECNE w BPP **bez aktualnego etatu** (import PBN, Obca
  jednostka, dopiero zatrudniani) — tych picker by nie pokazał, wymuszając
  „utwórz nowego" → duplikaty. Nowy widok: autorzy **kiedykolwiek związani z tą
  uczelnią** (dowolne `Autor_Jednostka` do jednostki uczelni, aktualne LUB
  historyczne; wzorzec scope’u jak `PublicAutorAutocomplete`), **bez
  `create_field`** (odziedziczony `create_field="nonzero"` pokazałby opcję
  „utwórz «…»", która tworzy `bpp.Autor` natychmiast — łamie dry-run i przy
  ręcznym ajaxie zwraca tekst zamiast pk → 400). To spełnia intencję „tej
  uczelni" (mniej szumu niż cała baza), nie tracąc niezatrudnionych.
- Tytuł nowego autora → **auto z kolumny Excela** (rozstrzygany przez reconciler
  tytułów, Część 3); **bez** ręcznego pola tytułu w tej kolumnie.
- Wiersz `twardy`/`zgadywanie` → **mały „zmień autora"** (ten sam autocomplete,
  leniwie inicjowany).

### Docelowe zachowanie per stan wiersza (partial `_wiersz_preview.html`)

Kolumny podglądu **Imiona / Nazwisko / Tytuł** zostają **read-only** — pokazują,
co przyszło z XLS-a, ale nie są edytowalne.

| Stan (`confidence`) | „Akcje / zmiany" po zmianie |
|---|---|
| `twardy` | badge „twardy" + auto-`row.autor` w kol. Autor + dyskretny **„zmień autora"** rozwijający autocomplete (`autor-z-uczelni`) → `dopasuj-autora` |
| `zgadywanie` | jak `twardy`, ale badge warning „zgadywanie" (miękkie „potwierdź") + **„zmień autora"** → `dopasuj-autora` |
| `wielu` | `<select>` kandydatów (`wybierz-kandydata`, bez zmian) **+** „inny autor…" autocomplete → `dopasuj-autora` |
| `brak` | autocomplete **„Dopasuj do istniejącego autora"** (`import-autor-autocomplete`) → `dopasuj-autora` **+** checkbox **„utwórz nowego autora"** (`utworz-nowego`, bez zmian) |

Terminologia (finding review): confident status to `STATUS_TWARDY` (nie ma
`STATUS_PEWNY`). „Miękkie «potwierdź»" przy `zgadywanie` to **tylko sygnał
wizualny** (badge warning) — NIE osobny endpoint ani flip na `twardy`. Akceptacja
= nic nie robić (auto-autor zostaje). Jedyna akcja to „zmień autora" (override
przez `dopasuj-autora`, które ustawia `STATUS_TWARDY`). Licznik „luźnych" liczy
niezmienione `zgadywanie`.

### Zmiany

**Nowy endpoint `dopasuj-autora`** — `DopasujAutoraView(_WierszImportuMixin)`,
URL `<uuid:pk>/wiersz/<int:row_pk>/dopasuj-autora/`. POST (htmx) przyjmuje
`autor` (pk z autocomplete; `get_object_or_404(Autor, pk=…)` — walidacja, bo
przy ręcznym ajaxie może przyjść tekst). Wiąże `row.autor` i **przelicza jak
`WybierzKandydataView`** przez wspólny helper `_zwiaz_autora_z_wierszem(row,
autor)`:

- ustaw `row.autor = autor` PRZED liczeniem (`odtworz_autor_jednostka` czyta
  `self.autor`);
- **guard `jednostka=None` (finding review): gdy `row.jednostka_id is None` NIE
  wołaj `odtworz_autor_jednostka`** — wpisałby diff `{"jednostka": None}` →
  `_materializuj_diff` `get_or_create(jednostka_id=None)` → `IntegrityError`
  wywalający task (mirror analyze.py:302: bez jednostki `autor_jednostka=None`,
  `diff.pop('autor_jednostka')`, `zmiany_potrzebne=False`). Ten sam guard
  dotyczy istniejącego `WybierzKandydataView` (dziś latentny bug — helper go
  naprawia dla obu);
- `confidence = STATUS_TWARDY` (ręczny wybór = jednoznaczny), `utworz_nowego=
  False`, `przepnij_prace=False`;
- **kompletne `update_fields` (finding review): `autor`, `confidence`,
  `autor_jednostka`, `diff_do_utworzenia`, `zmiany_potrzebne`, `utworz_nowego`,
  `przepnij_prace`** — bez tych trzech ostatnich zerowanie nie zapisze się.
  `wybrany_kandydat`: helper zeruje na None; `WybierzKandydataView` PO helperze
  nadpisuje `wybrany_kandydat=autor` i dokłada je do `update_fields`
  (provenance kandydata zachowana).

Zwraca partial wiersza (OOB swap). Owner-scoped, bramka stanu `przeanalizowany`.

**Usunięcie edycji XLS-a:** wywalić z UI formularz free-text oraz martwy kod:
`EdytujWierszView`, `_rematch_wiersz`, URL `edytuj-wiersz`, ich testy
(`test_views_wiersz.py`). Pole `ImportPracownikowRow.korekta_uzytkownika`
**zostaje** w DB (bez migracji drop — kolumna nieszkodliwa; ustawiał ją tylko
`_rematch_wiersz`, więc zawsze domyślna). `row.tytul` FK zostaje. **Osierocone
docstringi do aktualizacji (finding review):** G1 w `_wykonaj_odpiecia`
(integrate.py:178 — dopisać `DopasujAutoraView`), F5 guard pustego imienia
(integrate.py:327 — guard ZOSTAJE jako defensywa, docstring do przeredagowania),
`test_integrate_nowy_autor.py:60`. Asercja `korekta_uzytkownika == {}`
(test_kandydaci_model.py:19) nieszkodliwa — zostaje.

**Select2 + htmx (finding review):** użyć **manualnego wzorca** jak
`importer_publikacji/partials/step_authors.html:530` — goły `<select>` +
`select2({ajax:{url: data-url}})` na endpoint `import-autor-autocomplete`, BEZ
`form.media`/DAL-widget-auto-init (auto-init działa tylko na DOMContentLoaded, a
partial jest podmieniany OOB). `bundle.js` (globalnie w `bare.html:112`) już
wnosi jQuery+select2+DAL. **Init leniwie** — dopiero po kliknięciu „zmień
autora"/rozwinięciu (tabela `ImportPracownikowResultsView` BEZ `paginate_by`;
init Select2 per wiersz przy setkach wierszy = zamulenie). Re-init po
`htmx:afterSettle` na podmienionym wierszu. Test integracyjny symuluje pisanie
(`select_select2_autocomplete`), nie wstrzykuje PK.

### Testy (Część 1)

- `dopasuj-autora` wiąże wybranego autora, ustawia confident, przelicza
  `autor_jednostka`/`zmiany_potrzebne`; owner-scoping; bramka stanu.
- Partial `brak` renderuje autocomplete + checkbox „utwórz nowego"; **nie**
  renderuje pól free-text.
- Partial `twardy` renderuje „zmień autora"; `wielu` renderuje dropdown +
  „inny autor…".
- Regres: `edytuj-wiersz` URL nie istnieje (NoReverseMatch), `_rematch_wiersz`
  usunięty.
- Integracyjny (Playwright, opcjonalnie): wpisanie nazwiska w autocomplete dla
  wiersza `brak` i wybór autora podmienia wiersz na „pewny".

---

## Część 2 — Hub z kafelkami

### Landing

**Nowy widok `PodgladImportuView`** (`GroupRequiredMixin, DetailView`/`View`),
URL `<uuid:pk>/przeglad/`, name `przeglad`, szablon
`import_pracownikow/przeglad.html`. Owner-scoped (`parent_object` jak w
`ImportPracownikowResultsView`). To **nowy główny punkt wejścia „szczegóły
importu"**:

- **DODAĆ** link „Przegląd" w `importpracownikow_list.html` (finding review:
  dziś nie ma tam linku „szczegóły"; `object.get_absolute_url` → strona live
  liveops, której **NIE wolno przepinać** — redirect po `enqueue()` w
  `CreateLiveOperationView` musi dalej prowadzić na live). Nowy link obok, nie
  zamiast;
- panel wyniku live (`import_pracownikow_result.html`) — „Zobacz szczegóły" →
  `przeglad` (to link, nie enqueue-redirect; przepięcie OK).

Hub pokazuje nazwę pliku, stan operacji i **2–4 kafelki**. Gdy stan =
`przeanalizowany`, hub eksponuje CTA **„Zapisz do bazy"** (reużywa `zatwierdz`)
— review-then-commit z jednego miejsca (przycisk na panelu live zostaje też).

### Kafelki

Każdy kafelek: ikona (Foundation-Icons), tytuł, liczniki, stan
(`do zrobienia` / `✓ gotowe` / neutralny), przycisk wejścia.

1. **🏢 Jednostki** — **warunkowy**: pokazywany tylko gdy
   `parent.jednostki_do_decyzji.exists()`. Liczniki: „N do utworzenia"
   (`tryb=brak`) · „M do sprawdzenia" (`tryb=zgadywanie`), licząc
   nierozstrzygnięte (`utworzona__isnull=True`). Link → `jednostki`.
2. **👤 Ludzie z XLS** — **zawsze**. Liczniki z `importpracownikowrow_set` po
   `confidence` (4 stany): „X pewnych" (`twardy`) · „Y luźnych" (`zgadywanie`)
   · „Z do akceptacji" (`wielu` + `brak`). Link → `importpracownikow-results`
   (tabela wierszy, Część 1). Stan: `✓ gotowe` gdy 0 do akceptacji
   (`wielu`+`brak`); luźne (`zgadywanie`) to miękkie „warto sprawdzić", nie
   blokuje.
3. **🔗 Ludzie spoza XLS** — **zawsze**. Licznik: `parent.odpiecia.count()` —
   **powiązań** autor+jednostka, NIE „osób" (finding review: autor w 2
   jednostkach = 2 powiązania). Etykieta „K powiązań spoza pliku (jednostki
   uczelni oprócz Obcej)". Link → nowy `odpiecia`. Stan neutralny. **Ostrzeżenie
   na kafelku gdy `pary_z_pliku()` puste a odpięć dużo** — znane ograniczenie
   (wszystkie jednostki odroczone → wszystkie aktywne AJ uczelni flagowane jako
   spoza pliku); hub wynosi ten szum na landing, więc trzeba go tam złagodzić
   komunikatem, nie tylko wymienić w „Poza zakresem".
4. **🎓 Tytuły** — **warunkowy** (Część 3): tylko gdy
   `parent.tytuly_do_decyzji.exists()`. Liczniki: „N do utworzenia" ·
   „M do sprawdzenia". Link → `tytuly`.

Zasada „2–4 kafelki": Ludzie z XLS + Ludzie spoza XLS zawsze; Jednostki i
Tytuły tylko gdy jest co rozstrzygać.

### Wydzielenie odpięć

**Nowy widok `OdpieciaView`** (`GroupRequiredMixin, ListView`/`View`), URL
`<uuid:pk>/odpiecia/`, name `odpiecia`, szablon
`import_pracownikow/odpiecia.html`. Przenosi z dołu `importpracownikowrow_list.html`
sekcję odpięć (tabela + partial `_odpiecie_row.html`, endpoint
`przelacz-odpiecie` bez zmian). Queryset = `parent.odpiecia.select_related(...)`
(przeniesiony z `ImportPracownikowResultsView.get_context_data`).

`ImportPracownikowResultsView` (strona „Ludzie z XLS") **traci** sekcję odpięć w
szablonie i `odpiecia` z kontekstu; reszta bez zmian.

### Nawigacja

Podstrony (`importpracownikow-results`, `odpiecia`, `jednostki`, `tytuly`)
dostają breadcrumb + przycisk **„← wróć do przeglądu"** → `przeglad`.

### Liczniki — implementacja

Property/metody na `ImportPracownikow` (jedno źródło prawdy, testowalne):
`liczniki_ludzi_z_xls()` → dict `{twardy, zgadywanie, wielu, brak}` (jeden
`values('confidence').annotate(Count)`). **Koaguluj `confidence=None` do `brak`
(finding review): `confidence` jest `null=True` — stare wiersze (sprzed migracji
0013) mają `None`; bez koagulacji suma kafelka ≠ liczba wierszy.**
`liczniki_jednostek()` / `liczniki_tytulow()` → dict `{do_utworzenia,
do_sprawdzenia}` (nierozstrzygnięte: `utworzona`/`utworzony` `__isnull=True`).
Hub czyta je z kontekstu.

### Testy (Część 2)

- Hub renderuje się w każdym stanie (`utworzony`…`zintegrowany`).
- Kafelek Jednostki ukryty gdy 0 decyzji, widoczny gdy >0; analogicznie Tytuły.
- Liczniki zgadzają się z danymi (twardy/zgadywanie/wielu/brak;
  do_utworzenia/sprawdzenia).
- `odpiecia` osiągalny, renderuje tabelę odpięć; `przelacz-odpiecie` działa.
- `importpracownikow-results` **nie** renderuje już sekcji odpięć.
- Wszystkie podstrony mają link „wróć do przeglądu".
- Entry-pointy (lista importów, panel wyniku) linkują do `przeglad`.

---

## Część 3 — Reconciler tytułów (analogia do jednostek)

### Klasyfikacja — `import_common/core/tytul.py` (NOWY)

Wzorzec: `core/jednostka.py`. `import_common` to warstwa niższa — stałe statusów
definiujemy lokalnie (bez importu w górę).

```
PROG_ZGADYWANIA_TYTULU = 0.85   # wyższy niż jednostki (krótkie stringi)
STATUS_TYTUL_TWARDY = "twardy"
STATUS_TYTUL_ZGADYWANIE = "zgadywanie"
STATUS_TYTUL_BRAK = "brak"

normalize_tytul(s) -> str
    # lower + strip + collapse spacji + usuń kropki; do PORÓWNANIA
    # ("dr hab." == "Dr. Hab" == "dr hab"). Nie zmienia zapisu.

sklasyfikuj_tytul(tytul_str) -> (Tytul|None, status, similarity|None)
    # "" / None                          -> (None, BRAK, None)  # bez decyzji!
    # norm-exact match Tytul.nazwa|skrot -> (t, TWARDY, None)
    # trigram(nazwa|skrot) >= prog        -> (best, ZGADYWANIE, sim)
    # wpp                                 -> (None, BRAK, None)
```

Uwaga krytyczna: **pusty tytuł to normalny przypadek** (wielu pracowników bez
tytułu) — MUSI dawać `(None, BRAK, None)` i **nie** tworzyć decyzji ani nie być
liczony na kafelku. Decyzja powstaje tylko dla NIEPUSTEGO stringa, który nie jest
`twardy`. Matchujemy po **wszystkich** `Tytul` (brak odpowiednika „puli
afiliacyjnej" — każdy tytuł to poprawny cel).

Skrót/nazwa nowego tytułu: Excel podaje zwykle jedną formę (skrót „dr hab.").
Domyślnie `skrot = nazwa = string z Excela` (przycięte do `max_length`
`NazwaISkrot`), **edytowalne na ekranie decyzji**. `Tytul.skrot` bywa unikalny →
guard unikalności przy tworzeniu (sufiks przy kolizji, jak `unikalny_skrot`).

### Model `ImportPracownikowTytul` (NOWY, migracja 0017)

Mirror `ImportPracownikowJednostka`, uproszczony (tytuł nie ma drzewa/parenta):

- `parent` FK `ImportPracownikow`, `related_name="tytuly_do_decyzji"`,
- `nazwa_zrodlowa` (string z Excela, `max_length=512`),
- `tryb` (`zgadywanie`/`brak`, `TRYB_CHOICES`),
- `auto_tytul` FK `bpp.Tytul` (auto-match dla `zgadywanie`, SET_NULL),
- `auto_similarity` FloatField null,
- `nazwa_do_utworzenia` / `skrot_do_utworzenia` (default = string, edytowalne),
- `decyzja` (`akceptuj`/`mapuj`/`pomin`, default `akceptuj`),
- `wybrany_tytul` FK `bpp.Tytul` (cel `mapuj`, SET_NULL),
- `utworzony` FK `bpp.Tytul` (guard idempotencji, jak `utworzona`),
- `unique_together = (("parent", "nazwa_zrodlowa"),)`.

Semantyka decyzji: `pomin` → **wiersz bez tytułu** — nowy autor powstaje bez
tytułu, ale istniejącemu autorowi tytuł **ZOSTAJE** (`_integrate_autor`
models.py:390 ustawia tytuł tylko przy `tytul_id is not None`, nigdy nie kasuje);
`mapuj` → `wybrany_tytul`; `akceptuj`: `zgadywanie` → `auto_tytul`, `brak` →
utwórz z `nazwa_do_utworzenia`/`skrot_do_utworzenia` (albo dołącz do istniejącego
po norm-exact — drift bazy).

### Pola na istniejących modelach (migracja 0017)

- `ImportPracownikowRow.tytul_status` (CharField choices, null) — mirror
  `jednostka_status`.
- `ImportPracownikowRow.zrodlo_tytulu` FK `ImportPracownikowTytul` SET_NULL,
  `related_name="wiersze_tytul"` — mirror `zrodlo_jednostki`.
- `ImportPracownikow.tworz_brakujace_tytuly` BooleanField default=True
  (help_text analog do `tworz_brakujace_jednostki`). **UI (finding review):
  checkbox w `MapowanieForm` + zapis w `MapowanieView.form_valid` (update_fields,
  jak `tworz_brakujace_jednostki` forms.py:58 / views.py:229) — inaczej flaga
  martwa (zawsze True).**

`row.tytul` FK już istnieje (rozstrzygnięty `Tytul`).

### Analiza — `analyze.py`

Zastąpić `_dopasuj_tytul` klasyfikacją + reconcilerem `_ReconcilerTytulow`
(mirror `_ReconcilerJednostek`: `reconciluj(nazwa, tryb, auto_tytul, sim)` z
get_or_create po `nazwa_zrodlowa__iexact`, odświeżanie pól liczonych, zachowanie
wyborów usera; `usun_stale`). W `_przetworz_wiersz`:

```
tytul, tyt_status, tyt_sim = sklasyfikuj_tytul(tytul_str)
if tytul_str empty:            row.tytul=None; tytul_status=None      # bez decyzji
elif TWARDY:                   row.tytul=tytul; tytul_status=TWARDY   # bez decyzji
elif ZGADYWANIE or (BRAK and tworz_brakujace_tytuly):
    dec = reconciler.reconciluj(...); row.zrodlo_tytulu=dec
    row.tytul=None (odroczony); tytul_status=tyt_status
else (BRAK and not tworz_brakujace_tytuly):
    row.tytul=None; tytul_status=BRAK                                 # bez decyzji
```

Odroczone (`zgadywanie`/`brak` z decyzją) rozstrzyga integracja — spójnie z
jednostkami. `_ReconcilerTytulow.usun_stale()` po pętli wierszy.

### Integracja — `integrate.py`

Nowy `_rozstrzygnij_tytuly(parent, p)` — mirror `_rozstrzygnij_jednostki`, jako
**FAZA 0.5** (po jednostkach, PRZED snapshotem i fazą autorów — tytuł jest
potrzebny przy tworzeniu/aktualizacji autora: `_integrate_autor` ustawia
`a.tytul_id`). Idempotentne (guard `utworzony`).

- `_rozstrzygnij_jeden_tytul(dec, zajete_nazwy, zajete_skroty, p)` →
  `(Tytul|None, czy_utworzono)`: guard `utworzony`; `pomin`→None;
  `mapuj`→`wybrany_tytul`; `akceptuj`+`zgadywanie`→`auto_tytul`;
  `akceptuj`+`brak`→ tworzenie. **UWAGA (finding review): `Tytul.nazwa` ORAZ
  `Tytul.skrot` są `unique=True`** (`NazwaISkrot`, naming.py: nazwa max_length
  512, skrot 128). `nazwa_do_utworzenia` jest edytowalna, więc przed create:
  `Tytul.objects.filter(nazwa__iexact=nazwa_do_utworzenia).first()` → jeśli
  istnieje, dołącz (nie twórz duplikatu); guard in-batch `zajete_nazwy`
  (dwie decyzje z tą samą edytowaną nazwą). Skrót: `unikalny_skrot_tytulu(
  skrot_do_utworzenia, zajete_skroty)` (sufiks przy kolizji, jak
  `unikalny_skrot`). `create(nazwa=…, skrot=…)`; dopisz do obu zbiorów.
- `_podlacz_wiersze_do_tytulow(parent)` — mirror `_podlacz_wiersze_do_jednostek`:
  dla wierszy z `zrodlo_tytulu` ustaw `row.tytul = zrodlo_tytulu.utworzony`
  (zawsze — faza nowych autorów czyta `row.tytul`). **BLOCKER-guard (finding
  review): przelicz `zmiany_potrzebne` TYLKO gdy `row.autor is not None and
  row.autor_jednostka is not None`** — `check_if_integration_needed()` woła
  `getattr(self.autor, …)` / `aj.…`, więc dla `autor`/`autor_jednostka=None`
  (wiersze `wielu`/`brak` z decyzją tytułu — przypadek codzienny) rzuciłby
  `AttributeError` i wywalił cały task liveops. Przeliczenie **monotoniczne**:
  `row.zmiany_potrzebne = bool(row.diff_do_utworzenia) or
  row.check_if_integration_needed() or row.zmiany_potrzebne` (nie cofać
  True→False). Wiersze bez autora tylko zapisują `row.tytul`.

`_rozstrzygnij_tytuly(parent, p)` trzyma `zajete_nazwy=set()` + `zajete_skroty=
set()`, iteruje `parent.tytuly_do_decyzji`, per decyzja `transaction.atomic` +
guard `utworzony` (jak jednostki), na końcu `_podlacz_wiersze_do_tytulow`.
`integruj()` woła je zaraz po `_rozstrzygnij_jednostki`.

**Zmiana istniejącego checku (finding review — usuwa szum, nie tworzy).**
Dziś `_check_autor_needs_update` (models.py:346) zwraca `self.tytul_id !=
a.tytul_id` **bezwarunkowo** — a `_integrate_autor` (models.py:390) ustawia
tytuł tylko przy `tytul_id is not None`. Skutek (już dziś): utytułowany autor z
niedopasowanym/pustym tytułem → `zmiany_potrzebne=True` + puste `integrate()`.
Odroczenie tytułu (`row.tytul=None` do FAZY 0.5) by to nasiliło. **Fix:
symetryzacja** — porównuj tytuł tylko gdy `self.tytul_id is not None` (import
USTAWIA tytuł, nigdy nie kasuje; spójne z `_integrate_autor`). Test regresji na
utytułowanego autora + pusty/niedopasowany tytuł → `zmiany_potrzebne` nie
zawyżone.

### Ekran `WeryfikacjaTytulowView`

Mirror `WeryfikacjaJednostekView`: URL `<uuid:pk>/tytuly/`, name `tytuly`,
szablon `weryfikacja_tytulow.html` (mirror `weryfikacja_jednostek.html`). GET:
sekcje „Dopasowane automatycznie" (`zgadywanie`, kolumny: nazwa z pliku · osób ·
auto-tytuł+similarity · decyzja · mapuj-na) i „Do utworzenia" (`brak`, kolumny:
nazwa z pliku · osób · decyzja · **nazwa** (edytowalna) · **skrót** (edytowalny) ·
mapuj-na). `mapuj_opcje = Tytul.objects.all()`. POST: zapis decyzji + edytowalne
`nazwa_do_utworzenia`/`skrot_do_utworzenia`, tylko w stanie `przeanalizowany`.
Breadcrumb + „← wróć do przeglądu".

### Testy (Część 3)

- `sklasyfikuj_tytul`: pusty→BRAK-bez-decyzji; „dr hab."/„Dr. Hab"/„dr hab"→
  ten sam TWARDY; bliski literowo→ZGADYWANIE≥0.85; śmieć→BRAK.
- Analiza: niepusty niedopasowany tytuł tworzy 1 decyzję na unikalny string
  (dedup iexact); pusty tytuł NIE tworzy decyzji; `usun_stale` czyści znikłe.
- Integracja: `akceptuj`+`brak` tworzy `Tytul` (nazwa/skrót z decyzji, skrót
  unikalny); `mapuj` używa istniejącego; `pomin`→autor bez tytułu; idempotencja
  (restart nie duplikuje); `zmiany_potrzebne` przeliczone.
- `tytuly` ekran: sekcje, edycja nazwa/skrót dla `brak`, bramka stanu.
- Kafelek Tytuły: liczniki, ukryty gdy 0 decyzji.

---

## URL-e (podsumowanie)

**Dodane:** `przeglad` (hub), `odpiecia`, `tytuly`, `dopasuj-autora`,
`import-autor-autocomplete` (nowy widok autocomplete; URL w `bpp/urls.py` obok
istniejących `autor-*-autocomplete`).
**Usunięte:** `edytuj-wiersz`.
**Bez zmian:** `jednostki`, `wybierz-kandydata`, `utworz-nowego`,
`przepnij-prace`, `zaznacz-przepiecia`, `przelacz-odpiecie`, `zatwierdz`,
`restart-analiza`, `importpracownikow-results`, `index`, `new`, `mapowanie`.

## Migracja i baseline

Jedna nowa migracja **`0017`**: model `ImportPracownikowTytul`, pola
`ImportPracownikowRow.tytul_status` + `zrodlo_tytulu`,
`ImportPracownikow.tworz_brakujace_tytuly`. Nie dotyka 0016. Baseline
(`make baseline-update`) — **przy scaleniu gałęzi**, nie w tej pracy.

## Kolejność implementacji (rekomendacja dla planu)

1. **Część 3 backend** — `core/tytul.py`, model, migracja 0017, analiza,
   integracja (fundament, testowalny bez UI).
2. **Część 1** — `dopasuj-autora` + usunięcie edycji XLS + override `pewny`.
3. **Część 2** — hub, liczniki, wydzielenie `odpiecia`, kafelek Tytuły,
   repointing entry-pointów i nawigacji. (Hub potrzebuje modelu tytułów z kroku 1
   dla kafelka 🎓.)

## Poza zakresem

- Ręczny picker profili mapowania nagłówków (osobny cykl).
- Higiena/skracanie długich nazw nagłówków.
- Zmiany w modelu domenowym BPP (`Tytul`/`Autor`/`Jednostka`).
- Refresh baseline (robiony raz przy scaleniu).
- Naprawa szumu odpięć gdy wszystkie jednostki odroczone (znane ograniczenie).

## Pytania otwarte

- **Odchylenie od dosłownego wyboru pickera (do potwierdzenia przez usera).**
  User wybrał „tylko autorzy tej uczelni". Review wykazał, że istniejący
  `autor-z-uczelni-autocomplete` znaczy „aktualnie ZATRUDNIENI", co gubi
  właśnie autorów-celów wierszy `brak` (istnieją w BPP bez aktualnego etatu).
  Spec zakłada więc **nowy** `import-autor-autocomplete` = „kiedykolwiek
  związani z tą uczelnią" (aktualni + historyczni, bez create). To honoruje
  intencję („tej uczelni", mniej szumu niż cała baza) i naprawia lukę. Jeśli
  user woli twardo „całą bazę BPP" albo „tylko aktualnie zatrudnieni" — łatwa
  zmiana scope’u.

Pozostałe decyzje rozstrzygnięte: tytuł nowego autora auto z Excela, override
`twardy`/`zgadywanie`, próg tytułów 0.85, `skrot=nazwa=string` edytowalne,
kafelki 2–4 z Jednostki/Tytuły warunkowymi.
