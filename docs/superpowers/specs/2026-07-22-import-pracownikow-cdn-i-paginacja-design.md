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
   (`models.py:995`), wołane przez `porownaj_z_baza()` → `stany_pol()`.
   `bpp.autor_jednostka` **nie jest** w `CACHEOPS`, więc to prawdziwe uderzenie
   w PostgreSQL, N razy.

Do tego **9,1 KB HTML na wiersz**, z czego **3830 bajtów to identyczny blok
`<script>`** powtórzony w każdym wierszu (`_wiersz_preview_kom.html:160-231`).
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

Ocena ryzyka: komentarze w `_wiersz_preview_kom.html:83-87` wprost tłumaczą obejście
napisane **pod semantykę 1.x** (filtr zdarzenia `change[target.classList…]` zamiast
`from:`, bo „bare selektor w `from:` w htmx 1.x wiąże na CAŁYM dokumencie"). Kod był
więc projektowany pod 1.x i na 2.x działa przypadkiem. Użyte API to wyłącznie
`hx-post`, `hx-target`, `hx-swap="innerHTML"`, `hx-trigger` z filtrem zdarzenia oraz
zdarzenie `htmx:afterSettle` — wszystkie obecne i zgodne w 1.9.12.

**Warunek akceptacji:** samo przejście testów nie wystarcza. Trzy ekrany trzeba
przeklikać ręcznie (lista w „Testowanie" niżej).

### Test regresyjny — brak zewnętrznych assetów

Nowy test (`src/django_bpp/tests/test_brak_zewnetrznych_assetow.py`) skanuje
wszystkie szablony w `src/**/templates/**` oraz wszystkie klasy `Media` w plikach
`admin.py` i szuka `<script src>` / `<link href>` wskazujących na `http://`
lub `https://`.

Allow-lista (jawna, z uzasadnieniem w komentarzu):

- `euc-widget.freshworks.com` — widget zgłoszeń, usługa SaaS, `async defer`
- `www.googletagmanager.com` — Google Analytics, usługa SaaS, `async`
- `cdn.userway.org` — widget dostępności WCAG, wstrzykiwany dynamicznie

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

Uwaga na kolejność: funkcja musi być wołana **przed** `oznacz_przepiecie_prac()`
i przed renderem, na tej samej liście instancji (`list(ctx["object_list"])`),
inaczej memo trafi w inne obiekty niż te renderowane.

### Zmiana 3 — zdublowany `<script>`

Blok `<script>` z `_wiersz_preview_kom.html:160-231` przenosimy do
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
  każdej mutacji wiersza;
- **przy integracji** — `integrate.py` zapisuje ostatnią wartość i przestaje
  odświeżać. Po integracji nic wiersza nie mutuje (wszystkie ścieżki mutujące są
  za bramką `edytowalny_podglad`), więc pole zamarza samo.

`stany_pol()` upraszcza się do: zwróć `stany_pol_snapshot` (dopełniony neutralnym
`"brak"` dla kluczy dodanych po zapisaniu snapshotu), a gdy `None` — policz na
żywo (ścieżka awaryjna, patrz backfill).

Świadomie **nie dodajemy** drugiej kolumny. Rozważona alternatywa (osobne
`stany_pol_cache` obok `stany_pol_snapshot`) daje czytelniejszy rozdział ról, ale
kosztem migracji, dodatkowego pola i dwóch miejsc, które mogą się rozjechać.
Ponieważ post-integracyjne zamrożenie wynika z bramki `edytowalny_podglad`
(a nie z osobnego pola), jedna kolumna wystarcza.

**Punkty odświeżania.** Metoda `ImportPracownikowRow.odswiez_stany_pol()`
przelicza i zapisuje pole (`update_fields=["stany_pol_snapshot"]`). Wołana z:

| miejsce | dlaczego |
|---------|----------|
| koniec analizy (`pipeline/analyze.py`) | pierwsze wypełnienie, batch |
| `WybierzKandydataView` | zmienia `autor` |
| `DopasujAutoraView` | zmienia `autor` |
| `PrzelaczUtworzNowegoView` | zmienia `utworz_nowego` (wpływa na `do_pominiecia`) |
| `PrzepnijPraceView` | zmienia `przepnij_prace` |
| `ZaznaczWszystkiePrzepieciaView` | akcja zbiorcza, batch |
| `WeryfikacjaJednostekView` | przypisuje `jednostka` wierszom |
| `WeryfikacjaTytulowView` | przypisuje `tytul` |
| `WeryfikacjaStopniView` | przypisuje `stopien` |
| `WeryfikacjaStanowiskView` | przypisuje `stanowisko_dydaktyczne` |

`RestartAnalizaView` czyści wiersze i uruchamia analizę od nowa, więc pokrywa go
punkt „koniec analizy". `PrzelaczOdpiecieView` i `ZaznaczOdpieciaView` mutują
`Odpiecie`, nie wiersze — bez wpływu.

**Backfill (samonaprawianie).** Importy sprzed tej zmiany mają `NULL` i filtr
SQL by ich nie znalazł. Zamiast migracji danych (która musiałaby wykonać zapytania
per wiersz na całej historii) robimy **leniwy backfill**: w `get_queryset()`, gdy
`parent.importpracownikowrow_set.filter(stany_pol_snapshot__isnull=True).exists()`,
przeliczamy cały import jednym batchem (z hurtowym prefetchem `Autor_Jednostka`,
jak w Zmianie 2) i zapisujemy przez `bulk_update`. Dzieje się to **raz na import**,
przy pierwszym wejściu na stronę po wdrożeniu.

Backfill jest opakowany w `transaction.atomic()` i **nie zmienia stanu importu** —
to czysta materializacja tego, co i tak liczyło się na żywo. Dla importu już
zintegrowanego backfill też jest bezpieczny: `integrate.py` zapisuje snapshot
przy integracji, więc importy zintegrowane po migracji `0024` mają go wypełnione;
starsze dostaną wartość policzoną na żywo, czyli dokładnie to, co widok pokazuje
dziś (`stany_pol()` z gałęzią live).

**Ryzyko i jego kontrola.** Jeśli przegapimy ścieżkę mutującą, filtr skłamie po
cichu. Kontrola: test parametryzowany po wszystkich endpointach mutujących, który
dla każdego wykonuje akcję zmieniającą stan pola i asertuje, że
`row.refresh_from_db().stany_pol_snapshot` odpowiada świeżo policzonemu
`stany_pol()`. Nowy endpoint mutujący bez odświeżenia = czerwony test.

### Zmiana 5 — paginacja i filtry po stronie serwera

**Paginacja.** `paginate_by = 25`, rozmiar strony z `?per_page=` (dozwolone:
10, 25, 50, 100; wartość spoza listy degraduje do 25 — tak samo jak dziś
zachowuje się walidacja `?rodzaj=`). Opcja „wszystkie" **znika**: przy paginacji
serwerowej byłaby jednoklikowym powrotem do problemu, który naprawiamy.

**Filtry w querysecie:**

| filtr | parametr GET | realizacja |
|-------|--------------|------------|
| rodzaj dopasowania | `?rodzaj=` | `confidence=` lub predykat `do-pominiecia` (`autor__isnull=True, utworz_nowego=False`) |
| szukaj | `?q=` | `Q(dane_znormalizowane__nazwisko__icontains=…) \| Q(dane_znormalizowane__imię__icontains=…) \| Q(autor__nazwisko__icontains=…) \| Q(jednostka__nazwa__icontains=…)` |
| stan pola (8×) | `?stan_<klucz>=` | `stany_pol_snapshot__<klucz>=` (JSONB) |

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
- Test świeżości snapshotu, parametryzowany po endpointach mutujących (opis wyżej).
- Test leniwego backfillu: import z `NULL` w `stany_pol_snapshot` po wejściu na
  stronę ma pole wypełnione, a wartości zgadzają się z liczonymi na żywo.
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
