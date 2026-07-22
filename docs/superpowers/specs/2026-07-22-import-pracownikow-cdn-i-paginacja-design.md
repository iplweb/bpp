# Self-hosting assetów + wydajność i paginacja widoku rezultatów importu pracowników

Data: 2026-07-22
Status: zaakceptowany do implementacji
Gałęzie: `fix/self-hosting-cdn-assets` (PR #1), `perf/import-pracownikow-paginacja-serwerowa` (PR #2)

## Problem

Wejście na `/import_pracownikow/<uuid>/rezultaty/` trwa dramatycznie długo. Diagnoza
wykazała **dwa niezależne** źródła, a nie jedno.

### Źródło 1 — blokujący skrypt z CDN-a (dominujące)

`src/import_pracownikow/templates/import_pracownikow/importpracownikowrow_list.html:53`
ładuje htmx z `https://unpkg.com/htmx.org@2.0.4`. Tag leży w `<body>` w linii 53,
a tabela zaczyna się w linii 144 — jest to więc **parser-blocking script**:
przeglądarka wstrzymuje parsowanie HTML-a i czeka na odpowiedź unpkg.com. Za
VPN-em lub firewallem, który tego hosta nie przepuszcza, oznacza to blokadę do
timeoutu DNS/TCP (typowo 20–75 s białej strony). Dodatkowo `unpkg.com/htmx.org@2.0.4`
odpowiada `301`, więc to dwa round-tripy zamiast jednego.

Objaw jest **niezależny od liczby wierszy** i nie odtwarza się w sieci, która CDN-a
widzi — stąd trudność w diagnozie.

htmx jest już w projekcie lokalnie i reszta aplikacji ładuje go poprawnie; trzy
szablony zostały pominięte przy przejściu na vendoring lokalny.

### Źródło 2 — koszt renderowania po stronie serwera (realny, niezależny)

Zmierzone benchmarkiem (render widoku przez `admin_client`, `CaptureQueriesContext`,
lokalny PostgreSQL w testcontainerze — czyli **bez** narzutu sieciowego; produkcja
będzie wolniejsza):

| N wierszy | czas odpowiedzi | zapytań SQL | rozmiar HTML |
|-----------|-----------------|-------------|--------------|
| 300       | 1,08 s          | 935         | 2,7 MB       |
| 1000      | 3,15 s          | 3035        | 9,1 MB       |

To **3 zapytania na każdy wiersz importu**, namierzone stack-trace'em:

1. **2× `bpp_uczelnia` na wiersz** — `Jednostka.__str__`
   (`src/bpp/models/jednostka.py:249`) czyta `self.uczelnia.uzywaj_wydzialow`.
   Szablon renderuje dwie różne jednostki na wiersz (`row.jednostka` oraz
   `row.autor.aktualna_jednostka`), a `select_related` tworzy **osobną instancję**
   `Jednostka` per wiersz, więc cache FK na instancji nic nie daje. W produkcji
   cacheops (`bpp.uczelnia` jest w `CACHEOPS`) zamienia to na trafienia do Redisa —
   tańsze, ale nadal 2×N round-tripów.
2. **1× `bpp_autor_jednostka` na wiersz** — `ImportPracownikowRow._aj_lista()`
   (`models.py:985`), wołane przez `porownaj_z_baza()` → `stany_pol()`.
   `bpp.autor_jednostka` **nie jest** w `CACHEOPS`, więc to prawdziwe uderzenie
   w PostgreSQL, N razy.

Do tego **9,1 KB HTML na wiersz**, z czego **3830 bajtów to identyczny blok
`<script>`** powtórzony w każdym wierszu (`partials/_wiersz_preview_kom.html:160-231`).
Ma guard `window.__bppImportAutorPicker`, więc wykonuje się raz — ale przesyła się
i parsuje N razy. Przy 1000 wierszy to 3,8 MB czystego duplikatu.

Wreszcie: widok **nie ma paginacji serwerowej**. `paginate_by` nie jest ustawione,
całość jedzie do DOM-u, a stronicowanie jest udawane w JS przez `hidden` na
`<tbody>`. Przy realnym imporcie uczelnianym (1500–3000 wierszy) daje to 15–27 MB
HTML-a niezależnie od tego, ile wierszy użytkownik ogląda.

### Zmierzony efekt poprawek (spike)

Spike (`select_related` na ścieżki `uczelnia`, hurtowy prefetch `Autor_Jednostka`,
wyniesienie `<script>`), N=1000:

| metryka          | przed  | po        | zysk |
|------------------|--------|-----------|------|
| czas odpowiedzi  | 3,15 s | **0,49 s**| 6,4× |
| czas w SQL       | 1,24 s | **0,08 s**| 15×  |
| liczba zapytań   | 3035   | **36**    | 84×  |
| rozmiar HTML     | 9,1 MB | **5,3 MB**| −42% |

Paginacja serwerowa dokłada się do tego ortogonalnie: sprowadza koszt renderu
z O(liczba wierszy importu) do O(rozmiar strony).

## Cele i nie-cele

**Cele.**

1. Żaden zasób ładowany przez BPP nie pochodzi z zewnętrznego CDN-a.
2. Widok rezultatów renderuje się w czasie niezależnym od rozmiaru importu.
3. Filtry działają na **całym** imporcie, nie na bieżącej stronie.
4. Regresja jest niemożliwa do wprowadzenia po cichu (testy pilnują obu rzeczy).

**Nie-cele.**

- Usuwanie widgetów SaaS (Freshworks, Google Analytics, UserWay). To zdalne
  **usługi**, nie pliki — nie da się ich self-hostować. Wszystkie są `async` lub
  wstrzykiwane dynamicznie, więc nie blokują parsera. Zostają bez zmian
  (świadoma decyzja, zapisana jako allow-lista w teście).
- Przepisywanie wykresów w `ewaluacja_optymalizacja` na inną bibliotekę.
  Chart.js zostaje, zmienia się wyłącznie źródło pliku.
- Zmiana logiki dopasowywania autorów, resolvera okresów ani czegokolwiek
  w potoku analizy/integracji.
- Refaktor `views.py` (1713 linii) poza tym, czego wymaga zadanie.

## PR #1 — self-hosting assetów

Gałąź `fix/self-hosting-cdn-assets`, baza `dev`. Mały, niskiego ryzyka,
mergowalny natychmiast — to on rozwiązuje realny ból użytkownika.

### Zmiany

| plik | dziś | po |
|------|------|-----|
| `import_pracownikow/templates/…/importpracownikowrow_list.html:53` | `https://unpkg.com/htmx.org@2.0.4` | `{% static 'liveops/vendor/htmx.min.js' %}` |
| `import_pracownikow/templates/…/odpiecia.html:25` | j.w. | j.w. |
| `importer_publikacji/templates/…/index.html:53` | j.w. | j.w. |
| `ewaluacja_optymalizacja/templates/…/run_detail.html:7` | `https://cdn.jsdelivr.net/npm/chart.js@4.4.0/…` | `{% static 'chart.js/dist/chart.umd.min.js' %}` |
| `przemapuj_zrodlo/admin.py:109` | `https://cdnjs.cloudflare.com/…/foundation-icons.min.css` | `foundation-datepicker/foundation/fonts/foundation-icons.css` |

Szczegóły, które zostały zweryfikowane w kodzie przed napisaniem specyfikacji:

- `liveops/vendor/htmx.min.js` pochodzi z zainstalowanego pakietu `liveops`
  (`site-packages/liveops/static/liveops/vendor/htmx.min.js`) i jest już używany
  przez `import_pracownikow/import_pracownikow.html:33` oraz
  `import_punktacji_zrodel/…:33`. Nie wymaga żadnej nowej zależności.
- `foundation-icons.css` jest już lokalnie, dostarczany przez pakiet npm
  `foundation-datepicker` pod ścieżką
  `foundation-datepicker/foundation/fonts/foundation-icons.css`, razem z fontami
  (`.woff`, `.ttf`, `.eot`, `.svg`). Używa go `bare.html:77` i dwa szablony
  admina. `przemapuj_zrodlo/admin.py` jest jedynym odstępstwem. Nie wymaga
  nowej zależności — to podmiana jednego stringa w `class Media`.
- **Chart.js jest jedyną pozycją wymagającą nowej zależności npm.** Do
  `package.json` (`dependencies`) trafia `"chart.js": "^4.4.0"`; `YarnFinder`
  zbierze `node_modules/chart.js/dist/chart.umd.min.js` do statików, analogicznie
  do `htmx.org/dist/htmx.js` używanego przez `admin/base_site.html:16`.
  Wymaga `yarn install` + `make assets` przy budowaniu obrazu — czyli nic nowego
  w pipeline, ale `yarn.lock` idzie do commita.

### Zejście htmx 2.0.4 → 1.9.12

Trzy szablony jadą dziś na htmx **2.0.4** z CDN-a, a cała reszta aplikacji na
**1.9.12** (`package.json`: `"htmx.org": "^1.9.12"`; `liveops/vendor/htmx.min.js`
raportuje `version:"1.9.12"`). Self-hosting oznacza więc **zejście o major**
w tych trzech miejscach — ujednolicenie wersji w całej aplikacji.

Ocena ryzyka: komentarze w `partials/_wiersz_preview_kom.html:83-87` wprost tłumaczą obejście
napisane **pod semantykę 1.x** (filtr zdarzenia `change[target.classList…]` zamiast
`from:`, bo „bare selektor w `from:` w htmx 1.x wiąże na CAŁYM dokumencie"). Kod był
więc projektowany pod 1.x i na 2.x działa przypadkiem. Użyte API to wyłącznie
`hx-post`, `hx-target`, `hx-swap="innerHTML"`, `hx-trigger` z filtrem zdarzenia oraz
zdarzenie `htmx:afterSettle` — wszystkie obecne i zgodne w 1.9.12.

**Warunek akceptacji:** samo przejście testów nie wystarcza. Trzy ekrany trzeba
przeklikać ręcznie (lista w „Testowanie" niżej).

### Test regresyjny — brak zewnętrznych assetów

Nowy test (`src/django_bpp/tests/test_brak_zewnetrznych_assetow.py`) skanuje
dwa rodzaje plików **dwoma różnymi wzorcami** — to jest istotne, bo naiwne
przeniesienie wzorca tagowego na `.py` przepuściłoby jedną z pięciu naprawianych
regresji:

- **szablony** (`src/**/templates/**`) — wzorzec tagowy: `<script src=…>` /
  `<link href=…>` wskazujące na `http://` lub `https://`;
- **pliki `*.py`** w `src/` — wzorzec **literału URL**, nie tagu. Klasa `Media`
  w `przemapuj_zrodlo/admin.py:109` nie zawiera żadnego tagu, tylko goły string
  `"https://cdnjs.cloudflare.com/…"` w tuplecie `css`; tag renderuje dopiero
  Django. Skanujemy więc literały `https?://` kończące się rozszerzeniem assetu
  (`.js`, `.css`, `.woff`, `.woff2`, `.svg`, `.png`) — to odsiewa linki
  dokumentacyjne w docstringach i `href`-y do stron zewnętrznych.

Skan `.py` obejmuje wszystkie moduły, nie tylko `admin.py` — klasy `Media` mogą
żyć też w `forms.py`/`widgets.py` (dziś ich tam nie ma, sprawdzone).

Test naśladuje istniejący precedens `src/bpp/tests/test_admin_fonts_selfhosted.py`
(strażnik self-hostowania fontów admina) — łącznie z dwiema jego nieoczywistymi
decyzjami, które trzeba powtórzyć:

1. **Dopasowanie regexem, nie `"host" in text`.** Substringowe sprawdzanie
   literału-hosta odpala fałszywy alarm CodeQL
   `py/incomplete-url-substring-sanitization` (heurystyka bierze je za
   obejściopodatną sanityzację URL-a).
2. **Lokalizowanie plików względem pliku testu** (`Path(__file__).resolve().parents[…]`),
   nie przez `import django_bpp`. Przy editable-install `__file__` pakietu
   wskazuje główny checkout, nie worktree — test sprawdzałby wtedy cudzy kod.
   Przy tej pracy (worktree obok repo) to nie jest teoretyczne.

Allow-lista (jawna, z uzasadnieniem w komentarzu) — usługi SaaS, których nie da
się self-hostować:

- `euc-widget.freshworks.com` — widget zgłoszeń; realny tag `<script src>`
  (`base.html:111`, `admin/base_site.html:157`), `async defer`
- `www.googletagmanager.com` — Google Analytics; realny tag (`google_analytics.html:1`), `async`

`cdn.userway.org` (widget dostępności WCAG) **nie trafia do allow-listy**, bo skan
tagów by go i tak nie zobaczył: jest wstrzykiwany inline'owym JS-em przez
`s.setAttribute("src", …)` (`base.html:368`). Wpis byłby martwy i mylący.
Zamiast tego docstring testu wymienia go jako znany, świadomie tolerowany
zewnętrzny zasób poza zasięgiem skanu — żeby nikt nie uznał zielonego testu za
dowód, że zewnętrznych requestów nie ma w ogóle.

Wszystko poza allow-listą to błąd testu. Komunikat błędu ma wprost mówić, co
zrobić: „zvendoruj do `package.json` i użyj `{% static %}`, albo dopisz do
allow-listy z uzasadnieniem".

Skanowanie ograniczamy do plików źródłowych — `src/django_bpp/staticroot/`
(artefakt `collectstatic`) i `node_modules/` są wyłączone. Świadomie **poza
zakresem** skanu zostaje `src/bpp/static/kbw-keypad/dist/index.html`, który ładuje
jQuery z `ajax.googleapis.com` — to strona demo vendorowanego pluginu, nigdy nie
renderowana przez aplikację. Test skanuje szablony Django, nie statyczny HTML
bibliotek, więc plik nie wpada w zakres i nie wymaga wyjątku.

## PR #2 — wydajność i paginacja serwerowa

Gałąź `perf/import-pracownikow-paginacja-serwerowa`, baza **`fix/self-hosting-cdn-assets`**
(nie `dev`) — oba PR-y dotykają `importpracownikowrow_list.html`, więc stackowanie
eliminuje konflikt i sprawia, że diff PR #2 pokazuje tylko jego własne zmiany.

### Zmiana 1 — N+1 „uczelnia"

W `ImportPracownikowResultsView.get_queryset()` dokładamy do istniejącego
`select_related` trzy ścieżki:

```python
.select_related(
    "jednostka__uczelnia",
    "autor__aktualna_jednostka__uczelnia",
    "autor__aktualna_jednostka__wydzial",
)
```

Dwie pierwsze zabijają zmierzone 2×N zapytań o `bpp_uczelnia`. Trzecia jest
**profilaktyczna**: `Jednostka.__str__` po sprawdzeniu `uzywaj_wydzialow` sięga do
`self.wydzial`. W benchmarku ta gałąź nie odpaliła (`uzywaj_wydzialow` było
`False`), ale na instancji z włączonymi wydziałami byłoby to trzecie N+1.
`jednostka__wydzial` jest już w `get_details_set()`; brakuje odpowiednika dla
`autor__aktualna_jednostka`.

### Zmiana 2 — N+1 `Autor_Jednostka`

Nowa funkcja modułowa w `views.py`, wołana z `get_context_data()`:

```python
def wstepnie_zaladuj_okresy(rows):
    """Zasila memo ``_aj_lista_cache`` wszystkich wierszy JEDNYM zapytaniem."""
```

Pobiera `Autor_Jednostka` dla zbioru par `(autor_id, jednostka_id)` widocznych
na stronie i przypisuje listy do `row._aj_lista_cache`. **Logika modelu pozostaje
nietknięta** — korzystamy z istniejącego kontraktu memo, ten sam, którego używa
`_okres()`. Wiersze bez pary dostają `[]`, żeby `hasattr` nie odpalił zapytania.

Wymóg jest jeden: funkcja musi dostać **tę samą listę instancji**, która pójdzie
do renderu (`rows = list(ctx["object_list"])`), inaczej memo trafi w inne obiekty
niż renderowane. Kolejność względem `oznacz_przepiecie_prac()` jest obojętna —
ta funkcja (`views.py:107-153`) nie dotyka `_aj_lista` ani `_okres`.

Zmiana pozostaje potrzebna **także po** Zmianie 4: szablon woła
`row.porownaj_z_baza` bezpośrednio, przy renderze bloku porównań
(`partials/_wiersz_preview_kom.html:263`), niezależnie od tego, skąd biorą się
`data-diff-*`. Materializacja stanów pól usuwa jedno wołanie, nie wszystkie.

### Zmiana 3 — zdublowany `<script>`

Blok `<script>` z `partials/_wiersz_preview_kom.html:160-231` przenosimy do
`importpracownikowrow_list.html` (raz na stronę). Kod jest już napisany jako
delegacja zdarzeń na `document` z guardem `window.__bppImportAutorPicker`, więc
przeniesienie jest czysto mechaniczne — nie wymaga zmian w samym JS.

Ważne: partial jest też wstrzykiwany przez HTMX przy swapie wiersza. Delegacja na
`document` + `htmx:afterSettle` (już w kodzie) obsługuje to poprawnie, bo listener
żyje na stronie, nie w wierszu. Po przeniesieniu guard `__bppImportAutorPicker`
przestaje być potrzebny, ale **zostaje** — chroni przed podwójną rejestracją,
gdyby ktoś kiedyś wstawił partial na inną stronę.

### Zmiana 4 — materializacja stanów pól

To jest warunek konieczny paginacji, więc opis zaczyna się od uzasadnienia.

**Dlaczego bez tego się nie da.** Pasek filtrów ma 8 filtrów stanu pola
(`POLA_ROZNIC`), dziś liczonych w Pythonie przez ekstraktory w `roznice.py`.
Sześć z nich (`jednostka`, `tytul`, `funkcja`, `email`, `stopien`, `stanowisko`)
to porównania FK/stringów, które dałoby się zapisać w SQL. Dwa pozostałe
(`data_od`, `data_do`) wołają `porownaj_z_baza()` → `_okres()` →
`rozwiaz_okres_zatrudnienia()`, czyli imperatywny resolver okresów zatrudnienia
operujący na liście `Autor_Jednostka`. **Tego nie da się wyrazić w SQL** bez
przepisania resolvera, co jest ryzykowną zmianą w logice biznesowej importu.

Zamiast tego materializujemy wynik.

**Model.** Pole `stany_pol_snapshot` (JSONField, `null=True`) już istnieje
(migracja `0024`). Rozszerzamy jego cykl życia na dwie fazy:

- **przed integracją** — żywy cache: liczony na koniec analizy i odświeżany po
  każdej mutacji **pól czytanych przez ekstraktory** (nie po każdej mutacji
  wiersza — patrz „Czego świadomie NIE odświeżamy");
- **przy integracji** — `integrate.py` zapisuje ostatnią wartość i przestaje
  odświeżać. Po integracji nic wiersza nie mutuje (wszystkie ścieżki mutujące są
  za bramką `edytowalny_podglad`), więc pole zamarza samo.

**Rozdzielenie „policz" od „przeczytaj" — warunek konieczny.** Obecna
`stany_pol()` (`models.py:1127-1142`) jest metodą **czytającą**: gdy snapshot jest
niepusty, **zwraca go** (`{**baza, **self.stany_pol_snapshot}`), a liczy tylko gdy
pole jest `None`. Po tej zmianie pole jest niepuste od końca analizy, więc każde
„przeliczenie" napisane jako `self.stany_pol_snapshot = self.stany_pol()` byłoby
**kopiowaniem pola w samo siebie** — cichym no-opem. Dotyczyłoby to wszystkich
punktów odświeżania naraz, czyli reaktywowałoby dokładnie ten błąd, któremu ta
sekcja ma zapobiegać.

Dlatego dokładamy metodę **liczącą**, bez gałęzi snapshotu:

```python
def stany_pol_live(self):
    """Stan każdego pola policzony ekstraktorami POLA_ROZNIC — ZAWSZE świeżo,
    z pominięciem ``stany_pol_snapshot``. Źródło prawdy dla materializacji."""
    from import_pracownikow.roznice import POLA_ROZNIC

    return {klucz: ekstraktor(self) for klucz, _et, ekstraktor in POLA_ROZNIC}
```

`stany_pol_live()` używają: `odswiez_stany_pol()`, backfill oraz zamrożenie
w `integrate.py`. `stany_pol()` — czytana przez szablon i przez kod spoza tej
zmiany — zachowuje dzisiejsze zachowanie; jej gałąź „policz na żywo" delegujemy
do `stany_pol_live()`, żeby nie było dwóch kopii tej samej pętli.

Świadomie **nie dodajemy** drugiej kolumny. Rozważona alternatywa (osobne
`stany_pol_cache` obok `stany_pol_snapshot`) daje czytelniejszy rozdział ról, ale
kosztem migracji, dodatkowego pola i dwóch miejsc, które mogą się rozjechać.
Ponieważ post-integracyjne zamrożenie wynika z bramki `edytowalny_podglad`
(a nie z osobnego pola), jedna kolumna wystarcza.

**Punkty odświeżania.** Metoda `ImportPracownikowRow.odswiez_stany_pol()`
przelicza i zapisuje pole (`update_fields=["stany_pol_snapshot"]`).

Ustalenie miejsc odświeżania wymagało prześledzenia, co **naprawdę** mutuje pola
czytane przez ekstraktory `POLA_ROZNIC`. Pierwsza wersja tej specyfikacji
wskazywała tu widoki `Weryfikacja{Jednostek,Tytulow,Stopni,Stanowisk}View` — **to
było błędne**. Te widoki zapisują wyłącznie obiekty decyzji
(`dec.save(update_fields=["decyzja", "wybrany_parent", "wybrana_jednostka"])`,
`views.py:1122`); wierszy nie dotykają. Faktyczne przypisanie pól wierszom dzieje
się w `pipeline/integrate.py` przy „Zapisz strukturę": `row.jednostka` (:543),
`row.tytul` (:735), `row.stopien` (:810), `row.stanowisko_dydaktyczne` (:876).

| miejsce | co mutuje |
|---------|-----------|
| koniec analizy (`pipeline/analyze.py`) | pierwsze wypełnienie, batch po całym imporcie |
| koniec integracji **strukturalnej** (`pipeline/integrate.py`) | `jednostka`, `tytul`, `stopien`, `stanowisko_dydaktyczne` — batch po całym imporcie |
| `WybierzKandydataView` | `autor` |
| `DopasujAutoraView` | `autor` |

**Dlaczego integracja strukturalna jest punktem krytycznym.** Kończy się ona
stanem `STAN_STRUKTURA_ZINTEGROWANA`, który **nadal jest** `edytowalny_podglad`
(`models.py:214-222`) — to jest Krok 2, faza osób, dokładnie ta, w której operator
pracuje na widoku rezultatów. Bez odświeżenia w tym miejscu filtr `jednostka`
pokazywałby stan sprzed przypisania jednostek — a razem z nim `data_od` i `data_do`
(ekstraktory bramkują po `jednostka_id`, `roznice.py:69,80`) oraz `funkcja`
i `stanowisko` (zależą od `autor_jednostka`, przeliczanego przy przypisaniu
jednostki). Zakres strukturalny bywa uruchamiany **drugi raz** z fazy osób
(dotworzenie słowników, `views.py:1480-1489`), więc odświeżenie musi być
idempotentne i wołane przy każdym przebiegu, nie tylko pierwszym.

**Dlaczego przebieg PEŁNY nie potrzebuje osobnego punktu.** Reconcilery
`_podlacz_wiersze_do_jednostek` / `_rozstrzygnij_{tytuly,stopnie,stanowiska}`
biegną w **każdym** zakresie, także pełnym (`integrate.py:908-931`), a
early-return dla zakresu strukturalnego (`:934-953`) w przebiegu pełnym się nie
wykonuje — więc formalnie mutują wiersze poza wymienionymi punktami. Nie tworzy
to dziury, bo: (a) widoki `Weryfikacja*` pozwalają edytować decyzje **tylko**
w stanie `przeanalizowany` (`views.py:970`, `:1137` i analogiczne), (b) przebieg
pełny wymaga wcześniejszego przebiegu strukturalnego, którego końcowy refresh
zobaczył te same decyzje, a (c) reconcilery są idempotentne, więc ponowne
przypisanie daje wartościowo tę samą jednostkę/tytuł/stopień/stanowisko. Wiersze
z worklisty i tak przechodzą przez zamrożenie w `integrate.py:193`. Zapisujemy ten
argument jawnie, żeby nie trzeba go było odtwarzać przy następnej zmianie w potoku.

**Czego świadomie NIE odświeżamy.** `PrzelaczUtworzNowegoView`,
`PrzepnijPraceView` i `ZaznaczWszystkiePrzepieciaView` mutują `utworz_nowego`
i `przepnij_prace`. Żaden ekstraktor `POLA_ROZNIC` ani `porownaj_z_baza()` tych
pól nie czyta (zweryfikowane gerepem po `roznice.py` i `models.py:1029-1125` —
zero trafień), więc odświeżanie byłoby no-opem. Filtr `?rodzaj=do-pominiecia`
czyta `utworz_nowego` **bezpośrednio w SQL** (`autor__isnull=True,
utworz_nowego=False`), a nie ze snapshotu, więc pozostaje świeży bez żadnych
zabiegów.

`RestartAnalizaView` kasuje wiersze i uruchamia analizę od nowa → pokrywa go punkt
„koniec analizy". `PrzelaczOdpiecieView` i `ZaznaczOdpieciaView` mutują
`Odpiecie.zaznaczone`, nie wiersze — bez wpływu.

**Zachowanie zamrożonego snapshotu audytu — bez zmian.** Dziś snapshot dla wiersza
„utwórz nowego" liczy się **po** tym, jak `_przygotuj_nowego_autora` (`integrate.py:983`,
przed pętlą worklisty w :986) ustawił świeżo utworzonego autora, a **przed**
`_materializuj_diff` — zamrożone stany porównują więc plik z nowym autorem, ale
z jeszcze niezmaterializowanym `Autor_Jednostka` (odroczone AJ = `None` →
`funkcja` = „brak"). Tak mówi komentarz w `integrate.py:189-192` i to jest wartość,
którą trzeba odtworzyć co do joty.

Po tej zmianie pole jest już wypełnione przed integracją, więc guard
`if stany_pol_snapshot is None` w `integrate.py:193` nigdy by nie strzelił i audyt
pokazałby stan z końca analizy (`autor=None` → wszędzie „brak"). Dlatego **w tym
jednym miejscu** zamieniamy guard na bezwarunkowe przeliczenie:

```python
row.stany_pol_snapshot = row.stany_pol_live()   # integrate.py:193, było: if ... is None
```

**Drugi guard, w `models.py:1366` (`ImportPracownikowRow.integrate()`), zostaje
nietknięty.** To nie jest martwy kod, tylko aktywne zabezpieczenie: `integrate()`
ma dokładnie jednego wywołującego (`_integruj_wiersz`, `integrate.py:219`)
i wykonuje się **po** `_materializuj_diff`, czyli **po zmianie bazy**. Gdyby
zamienić i ten guard na bezwarunkowe przeliczenie, nadpisałby świeże zamrożenie
wartościami policzonymi względem już utworzonego AJ — dla każdego wiersza
z `diff_do_utworzenia` (w tym każdego „utwórz nowego") `funkcja`, `data_od`
i `data_do` wyszłyby inaczej niż dziś. To byłaby dokładnie ta korupcja audytu,
przed którą guard chroni.

Test niezmienności audytu musi asertować **konkretne dzisiejsze wartości**
(np. `funkcja == "brak"` dla wiersza z odroczonym AJ), a nie samo „policzone
względem nowego autora" — bo błędny wariant też spełniałby ten słabszy warunek.

**Backfill (samonaprawianie).** Importy sprzed tej zmiany mają `NULL` i filtr SQL
by ich nie znalazł. Zamiast migracji danych (musiałaby wykonać zapytania per wiersz
na całej historii) robimy **leniwy backfill**: w `get_queryset()`, gdy
`parent.importpracownikowrow_set.filter(stany_pol_snapshot__isnull=True).exists()`,
przeliczamy **wyłącznie wiersze z `NULL`** (z hurtowym prefetchem `Autor_Jednostka`,
jak w Zmianie 2) i zapisujemy przez `bulk_update`. Raz na import, przy pierwszym
wejściu na stronę po wdrożeniu.

Zawężenie do `isnull=True` jest **warunkiem poprawności, nie optymalizacją**.
Snapshot dostają dziś tylko wiersze przechodzące przez worklistę integracji
(`parent.zmiany_potrzebne_set.all()`, `integrate.py:986`) — wiersze bez zmian,
pominięte i bez autora mają `NULL` **także w importach zintegrowanych po migracji
`0024`**. Warunek wejścia backfillu będzie więc prawdziwy dla większości
historycznych zintegrowanych importów, a przeliczenie „całego importu" nadpisałoby
zamrożone wartości audytowe („zmienione") wartościami policzonymi po integracji
(„zgodne"). Backfill jest opakowany w `transaction.atomic()`.

**Ryzyko rezydualne: mutacje spoza importu.** Ekstraktory zależą od stanu `Autor`
i `Autor_Jednostka` w bazie. Edycja autora w adminie BPP albo integracja *innego*
importu między analizą a integracją tego importu unieważnia snapshot po cichu —
filtr będzie kłamał do najbliższej mutacji wiersza. Dziś, przy liczeniu na żywo,
tego problemu nie ma; to jest cena, którą płacimy za filtrowanie w SQL.
Akceptujemy ją świadomie: okno jest wąskie (jedna sesja pracy operatora nad
importem), skutek jest kosmetyczny (filtr, nie decyzja importu), a operator ma
przycisk „Restart analizy", który przelicza wszystko od nowa. Alternatywa —
inwalidacja snapshotów sygnałami z `Autor`/`Autor_Jednostka` — kosztowałaby
przy każdym zapisie autora w całym systemie, dla korzyści w jednym widoku.

**Kontrola ryzyka głównego.** Jeśli przegapimy ścieżkę mutującą, filtr skłamie po
cichu. Test parametryzowany po endpointach HTMX tej dziury by **nie** złapał
(dla widoków Weryfikacja* snapshot trywialnie równa się live, bo nic nie mutują).
Dlatego test musi obejmować **przebieg integracji strukturalnej**: uruchom
`integruj()` w zakresie struktury i asertuj, że dla każdego wiersza
`stany_pol_snapshot == stany_pol()` policzone na żywo. Do tego test per endpoint
mutujący `autor` (`wybierz-kandydata`, `dopasuj-autora`).

### Zmiana 5 — paginacja i filtry po stronie serwera

**Paginacja.** `paginate_by = 25`, rozmiar strony z `?per_page=` (dozwolone:
10, 25, 50, 100; wartość spoza listy degraduje do 25 — tak samo jak dziś
zachowuje się walidacja `?rodzaj=`). Opcja „wszystkie" **znika**: przy paginacji
serwerowej byłaby jednoklikowym powrotem do problemu, który naprawiamy.

**Filtry w querysecie:**

| filtr | parametr GET | realizacja |
|-------|--------------|------------|
| rodzaj dopasowania | `?rodzaj=` | `confidence=` lub predykat `do-pominiecia` (`autor__isnull=True, utworz_nowego=False`) |
| szukaj | `?q=` | suma `Q(...__icontains=…)` po sześciu polach (niżej) |
| stan pola (8×) | `?stan_<klucz>=` | `stany_pol_snapshot__<klucz>=` (JSONB), ze specjalnym traktowaniem `"brak"` (niżej) |

**Zakres `?q=`.** Musi pokryć to, co dziś pokrywa kliencki filtr tekstowy —
a ten przeszukuje wszystkie elementy `[data-szukaj]`, czyli **więcej** niż
oczywiste nazwisko z pliku. Z `partials/_wiersz_preview_kom.html:16-23,33-35,235-241`
wynika sześć pól:

```python
Q(dane_znormalizowane__nazwisko__icontains=q)
| Q(**{"dane_znormalizowane__imię__icontains": q})
| Q(**{"dane_znormalizowane__tytuł_stopień__icontains": q})
| Q(autor__nazwisko__icontains=q) | Q(autor__imiona__icontains=q)
| Q(autor__poprzednie_nazwiska__icontains=q) | Q(autor__orcid__icontains=q)
| Q(jednostka__nazwa__icontains=q)
| Q(autor__aktualna_jednostka__nazwa__icontains=q)
```

Klucze `imię` i `tytuł_stopień` mają polskie znaki; `imię` jest poprawnym
identyfikatorem Pythona, ale `tytuł_stopień` w zapisie `Q(a__tytuł_stopień=…)`
byłby kruchy — dlatego oba przekazujemy przez `Q(**{...})`, jednolicie.

`poprzednie_nazwiska` i `orcid` wchodzą, bo `span[data-szukaj]`
(`partials/_wiersz_preview_kom.html:33-35`) obejmuje **cały** include `_autor_dane.html`,
a ten renderuje ORCID oraz `Autor.__str__`, doklejający poprzednie nazwiska.
Operator wklejający ORCID w wyszukiwarkę to realny scenariusz.

**Zaakceptowane zawężenie** (świadome, żeby nie budować wyszukiwania po
wyrenderowanym tekście): serwerowe `?q=` nie dopasuje po skrócie wydziału
doklejanym przez `Jednostka.__str__` przy włączonych wydziałach ani po skrócie
tytułu z `Autor.__str__`. Oba są pochodnymi pól, po których i tak szukamy.

**Stan `"brak"` wymaga osobnego lookupu.** Istnieją zamrożone snapshoty **bez**
kluczy `data_od`/`data_do` — pochodzą sprzed dodania tych pól i dlatego
`stany_pol()` dopełnia je w Pythonie (`models.py:1133-1135`). Zapytanie
`stany_pol_snapshot__data_od="brak"` takich wierszy **nie znajdzie**, bo w JSONB
klucza po prostu nie ma. Filtr stanu `"brak"` realizujemy więc jako:

```python
Q(**{f"stany_pol_snapshot__{klucz}": "brak"})
| ~Q(**{"stany_pol_snapshot__has_key": klucz})
```

Pozostałe stany (`zmienione`, `zgodne`) to zwykła równość. Nie „naprawiamy" tych
snapshotów backfillem — są zamrożonym zapisem audytowym i backfill ich nie dotyka
(patrz Zmiana 4).

Uwaga na kolejność w `get_queryset()`: `~Q(has_key)` dopasowuje także wiersze
z `stany_pol_snapshot IS NULL` (Django generuje `NOT (snap ? 'k' AND snap IS NOT
NULL)`). Poprawność filtra `"brak"` zależy więc od tego, że **backfill biegnie
przed filtrowaniem** w tym samym `get_queryset()` — po nim NULL-i już nie ma.

`?rodzaj=` zachowuje dzisiejszą walidację i dzisiejszą semantykę deep-linku
`?rodzaj=do-pominiecia` z ostrzeżenia finalizacji — z tą różnicą, że teraz filtruje
w SQL, więc trafia w **cały** import, a nie w to, co akurat jest w DOM-ie.

Indeksowanie: queryset jest zawsze zawężony do jednego importu (`parent_id`,
indeks FK istnieje), więc filtrowanie JSONB działa na najwyżej kilku tysiącach
wierszy. Indeks GIN na `stany_pol_snapshot` jest zbędny i świadomie go **nie
dodajemy** — kosztowałby przy każdym zapisie wiersza, a nic realnego nie przyspiesza.

**Szablon.** Formularz filtrów przestaje być sterowany JS-em i staje się zwykłym
`<form method="get">` z `<button>` „Filtruj”. Znika ~140 linii JS
(`importpracownikowrow_list.html:174-316`): funkcje `filtruj()`, `stanPola()`,
`tekstRekordu()`, `okRodzaj()` i cała kliencka paginacja. Zostaje standardowy
pager Django, a linki pagera **zachowują aktywne filtry** w querystringu
(tag szablonowy budujący URL z podmienionym `page`).

Atrybuty `data-diff-*`, `data-confidence`, `data-do-pominiecia` i `data-szukaj`
w `_wiersz_preview_kom.html` **zostają**. Przestają zasilać filtr, ale są
asertowane przez istniejące testy (`test_filtr_rodzaj.py`, `test_stany_pol.py`)
i pozostają użyteczne jako czytelny stan w DOM-ie.

**Zmiana zachowania, świadoma:** po akcji HTMX wiersz, który przestał pasować do
aktywnego filtra, zostaje widoczny do przeładowania strony. Dziś JS chowałby go
natychmiast. Uznajemy to za akceptowalne — a nawet lepsze: wiersz nie znika
operatorowi spod kursora zaraz po tym, jak go zmienił.

## Testowanie

**Automatyczne.**

- Test braku zewnętrznych assetów (PR #1, opis wyżej).
- Test liczby zapytań: render widoku dla N wierszy wykonuje **stałą** liczbę
  zapytań, niezależną od N. Realizacja: `django_assert_num_queries` dla N=5 i N=25
  z tym samym oczekiwaniem. To jest właściwy test regresyjny na N+1 — łapie każde
  z trzech naprawianych N+1 i każde przyszłe.
- Test paginacji: przy N > `paginate_by` strona zawiera dokładnie `paginate_by`
  kart, a pager pokazuje właściwą liczbę stron.
- Testy filtrów: dla każdego z 8 stanów pola oraz dla `?rodzaj=`, `?q=` —
  filtr zawęża wynik na **całym** imporcie, także gdy pasujący wiersz leży poza
  pierwszą stroną (to jest istota zmiany, więc test musi to sprawdzać jawnie).
- Test zachowania filtrów w linkach pagera.
- Test świeżości snapshotu po **integracji strukturalnej**: po `integruj()`
  w zakresie struktury każdy wiersz ma `stany_pol_snapshot` równy świeżo
  policzonemu `stany_pol()`. To jest test, który łapie klasę błędu opisaną
  w Zmianie 4 — parametryzacja po endpointach HTMX by jej nie złapała.
- Test świeżości po endpointach mutujących `autor` (`wybierz-kandydata`,
  `dopasuj-autora`).
- Test leniwego backfillu, dwa warianty:
  (a) wiersz z `NULL` po wejściu na stronę ma pole wypełnione wartością zgodną
  z liczoną na żywo; (b) wiersz z **niepustym** snapshotem, w tym samym imporcie,
  pozostaje **nietknięty** — to zabezpiecza zamrożony zapis audytowy.
- Test niezmienności audytu: wiersz „utwórz nowego" po pełnej integracji ma
  snapshot policzony względem świeżo utworzonego autora (zachowanie identyczne
  jak przed zmianą).
- Test filtra stanu `"brak"` na snapshocie **bez** klucza `data_od`/`data_do`
  (symulacja starego zapisu) — wiersz musi zostać znaleziony.
- Test zakresu `?q=`: dopasowanie po `autor__imiona` oraz po nazwie aktualnej
  jednostki autora (pola, które kliencki filtr obejmował, a naiwna wersja
  serwerowa by pominęła).
- Pełne `make tests` lokalnie (nie tylko na CI), zgodnie z regułą projektu.

**Ręczne (warunek merge'a PR #1 — zejście htmx o major).**

Trzy ekrany, każdy z akcją HTMX:

1. `/import_pracownikow/<uuid>/rezultaty/` — „zmień autora" (Select2 →
   `dopasuj-autora`), dropdown kandydatów dla wiersza `wielu`, radia
   Pomiń/Utwórz/Dopasuj dla wiersza `brak`, checkbox przepięcia prac.
2. `/import_pracownikow/<uuid>/odpiecia/` — przełączanie odpięcia i akcja zbiorcza.
3. `/importer_publikacji/` — przejście kreatora przez kroki.

Szczególna uwaga na `hx-trigger="change[target.classList.contains('js-brak-radio-post')]"`
w wierszu `brak`: to jest miejsce, gdzie różnica 1.x/2.x w obsłudze filtrów zdarzeń
ujawniłaby się najpierw (objaw regresji: jeden klik POST-uje wiele wierszy).

**Weryfikacja pomiaru.** Benchmark z sekcji „Problem" powtarzamy po zmianach
i wynik trafia do opisu PR #2. Bez liczby „po" nie twierdzimy, że jest szybciej.

## Newsfragmenty

`src/bpp/newsfragments/` (kanoniczny katalog), po polsku:

- PR #1: `self-hosting-assetow.bugfix.rst` — biblioteki JS/CSS ładowane są
  z serwera uczelni zamiast z zewnętrznych CDN-ów; strony importu działają
  w sieciach bez dostępu do unpkg.com/jsdelivr.
- PR #2: `import-pracownikow-paginacja.feature.rst` — lista wyników importu
  pracowników jest stronicowana po stronie serwera, a filtry działają na całym
  imporcie.

## Kolejność wdrożenia

1. PR #1 — self-hosting. Merge po ręcznym przeklikaniu trzech ekranów.
2. PR #2 — stackowany na PR #1: zmiany 1–3 (N+1, skrypt) jako pierwszy commit,
   zmiana 4 (materializacja) jako drugi, zmiana 5 (paginacja i filtry) jako trzeci.
   Kolejność jest istotna: paginacja bez materializacji nie miałaby czym filtrować.
