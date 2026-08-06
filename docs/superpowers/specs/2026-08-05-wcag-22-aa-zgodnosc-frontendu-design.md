# Zgodność części publicznej BPP z WCAG 2.2 AA

Data: 2026-08-05
Gałąź: `feat/wcag-22-aa-audyt`

## Cel

Doprowadzić publiczną (anonimową) część serwisu BPP do zgodności z WCAG 2.2
na poziomie AA oraz wytworzyć **wersjonowany raport zgodności** jako artefakt
produktu — dokument, na którym uczelnia opiera własną deklarację dostępności.

Motor prac jest prawny. Uczelnie są podmiotami publicznymi w rozumieniu
ustawy z 4 kwietnia 2019 r. o dostępności cyfrowej stron internetowych
i aplikacji mobilnych podmiotów publicznych. Załącznik do ustawy wskazuje
WCAG 2.1 AA; celujemy wyżej, w WCAG 2.2 AA, ponieważ:

1. WCAG 2.2 zawiera w sobie 2.1 (jedyna różnica in minus to usunięcie
   kryterium 4.1.1 Parsing), więc wymóg ustawowy jest spełniony automatycznie.
2. Norma EN 301 549, do której odsyła prawodawstwo unijne, jest w rewizji
   pod mandatem M/587, a kierunkiem tej rewizji jest WCAG 2.2. Badanie 2.2
   teraz oszczędza powtórny audyt po nowelizacji.

   **Zastrzeżenie:** status publikacji zrewidowanej normy w Dzienniku
   Urzędowym UE nie został zweryfikowany na etapie pisania tej
   specyfikacji. Zdanie w raporcie zgodności musi albo podawać źródło
   z datą, albo mówić o rewizji w toku — dokument o funkcji prawnej nie
   może stwierdzać faktu, którego nie sprawdziliśmy. Decyzji o celu 2.2
   to nie zmienia: uzasadnia ją już punkt 1.

Zakres liczbowy: **55 kryteriów sukcesu poziomu A i AA** (38 z WCAG 2.0,
12 dodanych w 2.1, 6 dodanych w 2.2, minus wycofane 4.1.1).

## Zakres

**W zakresie:** część publiczna, dostępna bez logowania — strona główna,
widoki `browse/*` (autor, jednostka, uczelnia, praca, listy i indeksy),
wyszukiwarka multiseek wraz z wynikami, kreator „Zgłoś publikację", widok
grafu powiązań autorów, deklaracja dostępności, strona logowania, strony
błędów.

**Poza zakresem tego projektu:** panel zalogowanego użytkownika (importer,
raport slotów, ewaluacja, kolejki PBN) oraz Django admin (Grappelli). To
osobne, większe przedsięwzięcia. Poza zakresem także konfigurowalność
widgetu UserWay per uczelnia — kwestia konfiguracji produktu, nie kryterium
WCAG; odnotowana w raporcie jako obserwacja poboczna.

## Punkt wyjścia

BPP nie startuje od zera. Zweryfikowane elementy już obecne:

- `<html lang="pl">` — `bare.html:4`
- skip-link „Przejdź do głównej zawartości" — `bare.html:148`, styl w
  `_utilities.scss:73` (widoczny dopiero przy focusie)
- landmark `<main id="main-content" role="main">` — `base.html:260`
- 61 użyć `aria-label` w śledzonych szablonach
- 3 elementy `<img>` bez atrybutu `alt`, z czego **dwa w zakresie**:
  `src/bpp/templates/504.html:12` (strony błędów są w zakresie) oraz
  `src/bpp/templates/user_navigation_autocomplete.html:7` (modal
  globalnego wyszukiwania); trzeci — `src/maint-site/index.html:19` —
  jest poza zakresem
- `Uczelnia.deklaracja_dostepnosci_*` — `uczelnia.py:669,709,714`
- gotowa infrastruktura Playwright (`src/integration_tests/`, fixture
  `channels_live_server`, marker `playwright` w `pytest.ini:73`)

## Metodyka

WCAG-EM (*Website Accessibility Conformance Evaluation Methodology*, W3C):
określenie zakresu → poznanie serwisu → dobór reprezentatywnej próbki →
badanie próbki → dokumentacja wyniku. Jest to metodyka rozpoznawana przez
polskich audytorów i organ nadzoru.

Dwie zasady WCAG kształtujące dobór próbki:

- **§5.2.2 Full pages** — zgodność deklaruje się dla całej strony. Nie wolno
  wyłączyć z oceny pojedynczego komponentu.
- **§5.2.3 Complete processes** — jeśli strona należy do procesu, wszystkie
  strony procesu muszą być zgodne, by którakolwiek mogła być tak
  zadeklarowana. Stąd w próbce **pary**: multiseek formularz + wyniki,
  kreator zgłoszenia w komplecie kroków.

## Inwentaryzacja i próbka

### Źródło listy URL-i

Powierzchnia publiczna ma dwie warstwy o skrajnie różnej liczności:

**Strony obiektowe** — pokrywa je `src/django_bpp/sitemaps.py:104-118`:
`browse_autor`, `browse_jednostka`, `browse_uczelnia` oraz `browse_praca`
dla pięciu typów (Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Praca_Doktorska,
Praca_Habilitacyjna, Patent). Liczność: dziesiątki–setki tysięcy. Wzorców
szablonowych: trzy.

**Strony nawigacyjne i procesowe** — sitemap ich nie zna: strona główna,
`autorzy`/`jednostki`/`zrodla`/`typy`/`lata`/`literki`/`rok`/`w_latach`,
multiseek, kreator zgłoszenia, graf powiązań, deklaracja dostępności,
logowanie, 404/500, `brak_uczelni`. Liczność ~20, ale **każda ma własny
układ** — tu leży większość ryzyka.

### Skan szeroki (poprzedza dobór próbki)

Uruchamiany przed audytem, żeby próbka wynikała z danych, a nie z domysłu.
Obejmuje wszystkie strony nawigacyjne oraz warstwowaną próbę ~30 URL-i na
każdy z 8 typów obiektowych, dobraną pod skrajności: praca z jednym autorem
i z sześćdziesięcioma, autor ze zdjęciem i bez, jednostka z podjednostkami
i bez, rekord z abstraktem i bez.

Wynik skanu to **mapa cieplna**, nie raport. Odpowiada na pytanie: czy dane
naruszenie siedzi w szablonie współdzielonym (naprawa jedna), czy w
konkretnym widoku (naprawa lokalna). Naruszenie występujące na 100% stron
wskazuje na `base.html`/`top_bar.html`.

### Próbka WCAG-EM

Około 20 stron badanych także ręcznie. Liczba jest wyższa niż liczba
pozycji na liście poniżej, bo „kreator zgłoszenia — wszystkie kroki" to
jedna pozycja, ale kilka stron: §5.2.3 wymaga zbadania **każdej** strony
procesu, nie procesu jako całości.

strona główna · lista autorów (paginacja + indeks literowy) · autor ·
jednostka · praca ciągła (rekord najbogatszy) · patent (rekord najuboższy) ·
multiseek — formularz · multiseek — wyniki (własna tabela i paginator
pakietu `multiseek`) · kreator „Zgłoś publikację" — wszystkie kroki · graf
powiązań autorów · strona logowania · deklaracja dostępności · 404 · oraz
2–3 widoki wskazane przez skan jako odstające.

Lista finalna zapada po skanie i trafia do raportu wraz z uzasadnieniem.

## Warstwa automatyczna

### Narzędzie

`axe-core` z npm, wstrzykiwany do strony w teście Playwrighta:

```python
page.add_script_tag(path=str(KORZEN_REPO / "node_modules/axe-core/axe.min.js"))
wynik = page.evaluate(
    """() => axe.run(document, {
        runOnly: {type: 'tag', values: [
            'wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'
        ]}
    })"""
)
```

Ścieżka **absolutna**, wyliczana od korzenia repo — `add_script_tag(path=…)`
rozwiązuje ścieżki względne wobec bieżącego katalogu roboczego procesu
pytest, a ten nie jest gwarantowany.

Bez nowej zależności Pythona. `make assets` jest warunkiem wstępnym testów
Playwrighta, więc `node_modules/` jest obecne, gdy te testy biegną. Owijka
Pythonowa dokładałaby zależność i własny cykl wydawniczy dla dwóch linijek.

`axe-core` trafia do `devDependencies` w `package.json`.

### Tagi reguł — dwa przebiegi, nie jeden

**Przebieg blokujący:** `runOnly` ograniczone do `wcag2a`, `wcag2aa`,
`wcag21a`, `wcag21aa`, `wcag22a`, `wcag22aa` (jak w snippecie powyżej).

**Przebieg informacyjny:** osobne wywołanie `axe.run` z `runOnly` na
`best-practice`, którego wynik trafia do artefaktu testu, ale nie do
asercji. To zalecenia Deque, nie kryteria ustawowe — mieszanie ich z WCAG
psuje wiarygodność raportu.

Rozdzielenie na dwa wywołania jest konieczne: `runOnly` **ogranicza** zbiór
uruchamianych reguł, więc przy konfiguracji z przebiegu blokującego reguły
`best-practice` w ogóle by nie wystartowały i nie byłoby czego raportować.

**Do sprawdzenia przed implementacją:** kryterium 4.1.1 Parsing zostało
w WCAG 2.2 wycofane, a realizujące je reguły `duplicate-id` oraz
`duplicate-id-active` zostały — wedle rozeznania — usunięte z axe-core
w okolicach wersji 4.10. Jeśli tak, nie ma czego wyciszać; pozostaje
`duplicate-id-aria`, która mapuje się na **4.1.2 Name, Role, Value**,
czyli kryterium obowiązujące i blokujące. Wersję axe-core i aktualną listę
reguł należy zweryfikować przy pisaniu testu, zamiast przenosić to
założenie z niniejszej specyfikacji.

### Trzy artefakty

**(a) `src/integration_tests/test_a11y_probka.py`** — parametryzowany po
widokach próbki.

Dwa wymagania, bez których test jest bezwartościowy albo niestabilny:

- **Fixture'y deterministyczne i jawnie zdefiniowane.** Osobny moduł
  fixture ze specyfikacją danych per widok (ile autorów, które pola
  wypełnione, jaki charakter formalny), z **wartościami stałymi**.
  `baker.make` bez jawnych wartości losuje, a baseline liczy wystąpienia
  per reguła — dane niedeterministyczne dałyby niedeterministyczne
  liczniki, czyli flakującą bramkę. „Fixture'y celowo bogate" to za mało:
  potrzebna jest lista.
- **Zdefiniowany moment pomiaru.** Kryteria z bloku 6 (4.1.3 przede
  wszystkim) dotyczą treści pojawiającej się **po** interakcji. Test
  mierzący stronę w spoczynku nie zobaczy nic z tego, co uznaliśmy za
  najgroźniejsze. Widoki z treścią dynamiczną wymagają scenariusza:
  `networkidle` → interakcja (otwarcie modala, doładowanie wyników,
  dodanie wiersza warunku) → ponowny `axe.run`. Wyniki obu pomiarów
  księgowane osobno w baseline (klucz `<widok>` i `<widok>:po-interakcji`).

**(b) `src/integration_tests/test_a11y_kontrast.py`** — **syntetyczna strona
wzorników** (nowy widok renderujący komplet komponentów: nagłówki,
przyciski, callouty wszystkich poziomów, badge punktacji, tabela
bibliograficzna, paginator multiseek, pola formularza w stanie normalnym
i błędu, breadcrumbs, top-bar), iterowana po wszystkich wartościach
`theme_name`. **Źródłem prawdy dla listy motywów jest
`settings.BPP_THEMES`** (`settings/base.py:632`), nie `Gruntfile.js` —
pole `Uczelnia.theme_name` (`uczelnia.py:233`) nie ma `choices` i jest
walidowane wobec tej listy. Test iteruje po `BPP_THEMES` i dodatkowo
asertuje, że każdy motyw ma odpowiadający wpis w `Gruntfile.js` — dwa
źródła listy motywów mogą się rozjechać, a cicha rozbieżność oznaczałaby
motyw nigdy niezbadany.

Reguły: `color-contrast`. **Tylko ona** — kryterium 1.4.11 Non-text
Contrast (ramki pól, wskaźnik focusa, ikony) nie ma odpowiednika
automatycznego w axe-core; Deque klasyfikuje je jako wymagające oceny
ręcznej. Strona wzorników nadal służy 1.4.11, ale jako **materiał do
oględzin** we wszystkich sześciu motywach, nie jako wejście do asercji.

Strona wzorników, a nie „jedna strona referencyjna z serwisu": komponent
nieobecny na wybranej stronie byłby zmierzony tylko w tym motywie, w którym
akurat biegnie test (a), a w pozostałych pięciu pozostałby niezbadany.
Parametryzowanie realnych stron × 6 motywów rozwiązałoby to samo za cenę
ponad stu przebiegów przeglądarki, w większości redundantnych — strona
wzorników daje pełne pokrycie komponentów przy sześciu.

**Umiejscowienie:** widok rejestrowany wyłącznie w konfiguracji testowej
(`settings.TESTING`), nie w produkcyjnym URLconf. Inaczej sam wszedłby do
publicznej powierzchni serwisu, a więc i do zakresu audytu — strona
narzędziowa musiałaby wtedy spełniać kryteria, które ma tylko pomagać
mierzyć.

**Ryzyko dryfu, przyjęte świadomie:** komponent dodany do serwisu, ale
nieodwzorowany we wzornikach, jest po cichu niemierzony w pięciu z sześciu
motywów — czyli dokładnie ta luka, którą wzorniki miały zamknąć.
Mitygacja: komentarz-kontrakt w szablonie wzorników („dodajesz komponent
do serwisu → dodaj go tutaj") oraz odnotowanie ograniczenia w raporcie.
Rozwiązania szczelnego nie ma bez testów regresji wizualnej, których
projekt nie ma.

**(c) `manage.py audyt_dostepnosci`** — komenda uruchamiana ręcznie, **poza
CI**. Czyta URL-e ze sitemapy plus listy stron nawigacyjnych, zrzuca
JSON/CSV z rozkładem naruszeń. Poza CI, bo tysiąc URL-i × przeglądarka to
dziesiątki minut. Uruchamiana lokalnie na **dumpie produkcyjnym** — i to
jest jej główna wartość, bo świeża baza testowa ma puste tabele, a puste
tabele nie mają problemów z dostępnością.

Źródło serwera HTTP dla Playwrighta: komenda **nie stawia własnego** —
przyjmuje obowiązkowy argument `--base-url` i odpytuje instancję już
działającą. Docelowy scenariusz to `run-site run --from-dump <dump>`
w jednym terminalu i `manage.py audyt_dostepnosci --base-url
http://localhost:$(cat .dev_helpers_port)` w drugim. Powód: stawianie
serwera wewnątrz komendy zarządzającej dubluje logikę `run-site`,
a wskazanie URL-a pozwala puścić skan również na środowisku testowym
uczelni. Skan chodzi wyłącznie po zasobach anonimowych — komenda nie
uwierzytelnia się i nie używa `.dev_helpers_token`.

**Listę URL-i komenda pobiera po HTTP z `<base-url>/sitemap.xml`, nie
przez ORM.** Gdyby czytała z bazy, czytałaby bazę wskazaną przez `.env`
procesu `manage.py` — a `--base-url` wskazuje instancję `run-site`
z własnym testcontainerowym PostgreSQL załadowanym dumpem. To dwie różne
bazy; wygenerowane z jednej URL-e mogłyby nie istnieć na drugiej. Pobranie
sitemapy po HTTP czyni komendę bezstanową i pozwala jej działać przeciwko
dowolnej instancji.

### Baseline jako zapadka

Bez tego nie da się wmergować testu, który wywala się na istniejącym długu,
zanim ten dług zostanie spłacony.

**Lokalizacja:** `src/integration_tests/a11y-baseline.json`, obok testów.

**Ziarnistość: para (widok, identyfikator reguły) wraz z liczbą
wystąpień** — nie pojedynczy węzeł. Selektor axe to tablica ścieżek CSS
generowanych z drzewa dokumentu; przy dynamicznych identyfikatorach
i zmianie kolejności elementów jest niestabilny, więc baseline oparty na
selektorach szumiałby przy każdej kosmetycznej zmianie szablonu.
Przechowujemy licznik, bo to on niesie informację o kierunku:

```json
{
  "browse_autor": {"color-contrast": 3, "link-name": 1},
  "multiseek_wyniki": {"target-size": 12}
}
```

Selektory trafiają do artefaktu testu (do diagnostyki), ale **nie** do
asercji.

**Zapadka działa w jedną stronę:**

- reguła niewystępująca w baseline dla danego widoku → test czerwony,
- liczba wystąpień **większa** niż w baseline → test czerwony,
- liczba wystąpień **mniejsza** → test czerwony z komunikatem „napraw
  zaksięgowana, zaktualizuj baseline" (obniżenie licznika jest ręczne
  i świadome — automatyczne obniżanie zamieniłoby zapadkę w mechanizm
  cichego przepisywania historii).

**Wykrywanie martwych wpisów nie wymaga agregacji między przebiegami.**
Wpis martwy dla widoku obecnego w próbce łapie już asercja per-widok
(0 < N to spadek licznika, czyli czerwony test tego widoku). Jedyny
przypadek nieobjęty to **klucz baseline'u dla widoku, którego nie ma już
w parametryzacji** — a to porównanie czysto statyczne: zbiór kluczy
`a11y-baseline.json` wobec listy parametryzacji próbki (oraz
`wzorniki:<motyw>` wobec `BPP_THEMES`).

Realizuje to zwykły test bez przeglądarki i bez bazy — szybki, odporny na
`pytest-xdist` i na uruchamianie z `-k`.

**Świadomie odrzucone:** wariant z agregacją wyników wszystkich widoków
w `pytest` cache i osobnym testem zbiorczym. Nie działa w tym projekcie:
zapis do cache nie jest atomowy, więc pod `-n auto` równoległe
read-modify-write gubi wpisy; fixture sesyjna jest per-worker, więc widzi
wyłącznie podzbiór swojego workera; `xdist_group` nie pomaga, bo projekt
jeździ na `--dist=worksteal` (`pytest.ini:37`), gdzie ten marker nie
działa. Efekt byłby najgorszy z możliwych — warunek „rozpoznaj niepełny
przebieg i pomiń się" byłby spełniony **zawsze** na CI, czyli mechanizm
zdegenerowałby się do cichego skipa dokładnie tam, gdzie miał chronić.

**Aktualizacja baseline'u** odbywa się przez `pytest
--a11y-update-baseline` (własna opcja w `conftest.py`), która nadpisuje
plik wynikiem bieżącego przebiegu. Wymaga pełnego przebiegu `-m a11y` bez
`-k`; przy niepełnym odmawia zapisu. Zmiana pliku jest widoczna w diffie
PR-a i podlega review na równi z kodem — to jedyny mechanizm kontroli nad
obniżaniem liczników i musi być tak traktowany przez recenzentów.

## Warstwa ręczna

Automat pokrywa około 30–40% kryteriów. Reszta wymaga badania prowadzonego
przez człowieka. Lista kontrolna skrojona pod BPP:

### Blok 1 — obsługa klawiaturą (2.1.1, 2.1.2, 2.4.3, 2.4.7, 2.4.11)

Przejście całej próbki wyłącznie klawiaturą. Punkty zapalne:

- **Select2** — dostępność listy podpowiedzi strzałkami, zatwierdzanie
  Enterem, zamykanie Escape. Uwaga: `bare.html:159` podmienia motyw na
  `foundation`, czyli warstwę prezentacji.
- **Wyniki multiseek** — własna tabela i paginator pakietu `multiseek`
  (`src/django_bpp/templates/multiseek/results.html`, `live-results.html`,
  `paginator.html`). Fokusowalność i aktywowalność nagłówków sortujących
  (`<th>` z `onclick` bez `tabindex` to typowa pułapka), paginacja jako
  lista linków. **DataTables nie występuje w części publicznej** — jest
  wyłącznie w aplikacjach za logowaniem (`importer_publikacji`,
  `import_dyscyplin`, `import_pracownikow`, `rozbieznosci_dyscyplin`),
  czyli poza zakresem.
- **Formularz multiseek** — najbardziej złożony interaktywnie publiczny UI
  (dynamicznie dodawane wiersze warunków, wybór operatorów). Logika w JS
  pakietu `multiseek` z site-packages; nadpisane mamy tylko szablony.
- **foundation-datepicker / jQuery UI** (`bare.html:73,79`) — wybór daty
  z kalendarza jest klasycznym źródłem pułapek klawiaturowych.
- **Modal globalnego wyszukiwania** — wejście focusa do modala, uwięzienie
  focusa wewnątrz, zamykanie Escape i **powrót focusa na element
  wyzwalający**.
- **Widget UserWay** — jego przycisk jest w tabulacji na każdej stronie;
  sprawdzić, czy nie tworzy pułapki i nie przejmuje wirtualnego kursora
  czytnika ekranu.
- **2.4.11 Focus Not Obscured** — `base.html:52-71` wylicza w JS pozycję
  sticky breadcrumbs pod sticky top-barem. Taka konstrukcja zasłania
  fokusowany element tuż pod krawędzią.

### Blok 2 — struktura i semantyka (1.3.1, 1.3.2, 2.4.1, 2.4.6)

Hierarchia nagłówków (jeden `h1`, brak przeskoków), landmarki, tabele danych
z `<th scope>` i sensownym `<caption>`, zgodność kolejności DOM z kolejnością
wizualną. Szczególnej uwagi wymagają `praca_tabela.html` i
`praca_tabela_mono.html` — tabele bibliograficzne bywają układem, nie danymi.

### Blok 3 — treści nietekstowe (1.1.1)

1781 użyć ikon `fi-*` (font ikonowy Foundation) oraz wizualizacje:
`chart.js`, `plotly`, `cytoscape`, `sigma`, `3d-force-graph`. Wykres
prezentujący dane wymaga alternatywy przekazującej **równoważną
informację** (tabela), a nie podpisu „wykres publikacji".

Ikon jest zbyt wiele na ręczną edycję — rozwiązanie ma być systemowe
(tag szablonowy lub include wymuszający `aria-hidden="true"` plus tekst
alternatywny), nie 1781 poprawek.

### Blok 4 — formularze i procesy (3.3.1, 3.3.2, 3.3.3, 3.3.7, 3.3.8, 3.2.6)

Multiseek, kreator zgłoszenia, logowanie: etykiety powiązane programowo,
komunikaty błędów wskazujące **który** element i **co** poprawić.

**3.2.6 Consistent Help (A, nowe w 2.2)** — jeśli serwis udostępnia
mechanizm pomocy, musi on występować w tej samej względnej kolejności na
każdej stronie. Przycisk wsparcia Freshworks (`base.html:132`) jest
widoczny wyłącznie dla zalogowanych, więc na ścieżce anonimowej kryterium
prawdopodobnie nie ma zastosowania — ale wymaga to sprawdzenia, czy w
stopce lub top-barze nie ma innego punktu pomocy (kontakt, instrukcja),
który bywa umieszczany niekonsekwentnie. Werdykt „nie dotyczy" wymaga
uzasadnienia w raporcie na równi z pozostałymi.

### Blok 5 — adaptacja (1.4.4, 1.4.10, 1.4.12, 1.4.11, 2.5.7, 2.5.8, 2.2.2)

Powiększenie 200%, reflow przy 320 px bez przewijania poziomego, wymuszone
odstępy tekstu, rozmiar celów dotykowych, alternatywy dla przeciągania.

**1.4.11 Non-text Contrast (AA)** — kontrast ramek pól formularza,
wskaźnika focusa i ikon niosących znaczenie. **W całości ręcznie** — axe
nie ma reguły dla tego kryterium. Oględziny prowadzone na stronie
wzorników, w każdym z sześciu motywów, z osobnym przejściem dla stanu
`:focus-visible`.

**2.2.2 Pause, Stop, Hide (A)** — baner odliczania `django_countdown`
(`base.html:246`) jest obecny na stronach publicznych. Jeśli aktualizuje
się automatycznie (tykający licznik), kryterium wymaga mechanizmu
wstrzymania albo ukrycia. Do zbadania — implementacji pakietu nie
sprawdzano na etapie pisania specyfikacji.

### Blok 6 — treść dynamiczna i etykiety (4.1.3, 1.4.13, 2.5.3, 1.3.5)

Blok wydzielony, bo dotyczy kryteriów praktycznie niewykrywalnych
automatem, a w tym serwisie wysoce ryzykownych.

**4.1.3 Status Messages (AA)** — najpoważniejsza przewidywana luka po
2.5.8. Treść zmieniana bez przeładowania strony musi być ogłaszana
czytnikowi ekranu przez `aria-live` lub `role="status"`/`role="alert"`.
W BPP dotyczy to: doładowywanych wyników multiseek (`live-results.html`),
komunikatów wstrzykiwanych przez `channelsBroadcast` do
`#messagesPlaceholder` (`base.html:252`), wyników modala globalnego
wyszukiwania oraz podmian htmx. W całym `src/` jest kilkanaście wystąpień
`aria-live`/`role="status"`/`role="alert"`, w większości w adminie —
czyli na ścieżce publicznej praktycznie zero. Dokładny licznik należy
przeliczyć przy implementacji; rząd wielkości jest tu istotny, nie cyfra.

**1.4.13 Content on Hover or Focus (AA)** — tooltipy Foundation, m.in.
`src/bpp/templates/browse/autor.html:151` (`data-tooltip`). Kryterium
wymaga, by treść dało się odrzucić bez przesuwania wskaźnika (Escape),
by dało się na nią najechać, i by nie znikała samoczynnie. Domyślna
implementacja Foundation nie spełnia wymogu „dismissable".

**2.5.3 Label in Name (A)** — przy 61 ręcznie pisanych `aria-label`
ryzyko rozjazdu etykiety dostępnej z widocznym tekstem jest
systematyczne. Kryterium wymaga, by etykieta dostępna **zawierała** tekst
widoczny — inaczej sterowanie głosem („kliknij Szukaj") nie trafia
w przycisk. Wymaga przejrzenia wszystkich 61 wystąpień pod kątem par
tekst widoczny / `aria-label`.

**1.3.5 Identify Input Purpose (AA)** — pola zbierające dane o
użytkowniku wymagają atrybutu `autocomplete` z odpowiednią wartością.
Dotyczy pola e-mail w kreatorze zgłoszenia
(`src/zglos_publikacje/forms.py:212`) oraz pól logowania. W obu miejscach
atrybutów `autocomplete` brak.

## Przypisanie 55 kryteriów do źródeł werdyktu

Raport wymaga werdyktu dla **każdego** z 55 kryteriów A + AA. Poniższa
tabela mówi, skąd ten werdykt weźmie — bez niej tabela raportu powstaje
metodą „jakoś się uzupełni", a to dokładnie ten rodzaj luki, który obala
audyt przy kontroli.

Oznaczenia źródeł: **axe** — asercja automatyczna; **B1**–**B6** — blok
badania ręcznego; **N-D** — analiza pod kątem „nie dotyczy", wymagająca
udokumentowanego uzasadnienia, nie samego stwierdzenia.

### Postrzegalność

| Kryterium | Poz. | Źródło werdyktu |
|---|---|---|
| 1.1.1 Non-text Content | A | B3 + axe (`image-alt`) |
| 1.2.1–1.2.5 media | A/AA | **N-D** — przegląd treści publicznych i pól `HTMLField` pod kątem osadzonych audio/wideo |
| 1.3.1 Info and Relationships | A | B2 + axe |
| 1.3.2 Meaningful Sequence | A | B2 |
| 1.3.3 Sensory Characteristics | A | B2 |
| 1.3.4 Orientation | AA | B5 |
| 1.3.5 Identify Input Purpose | AA | B6 |
| 1.4.1 Use of Color | A | **B2** — linki w opisach bibliograficznych i wskaźniki sortowania odróżnialne wyłącznie kolorem to typowe naruszenie w tej klasie serwisów |
| 1.4.2 Audio Control | A | **N-D** |
| 1.4.3 Contrast (Minimum) | AA | axe, test (b) |
| 1.4.4 Resize Text | AA | B5 |
| 1.4.5 Images of Text | AA | B3 |
| 1.4.10 Reflow | AA | B5 |
| 1.4.11 Non-text Contrast | AA | B5 (w całości ręcznie) |
| 1.4.12 Text Spacing | AA | B5 |
| 1.4.13 Content on Hover or Focus | AA | B6 |

### Funkcjonalność

| Kryterium | Poz. | Źródło werdyktu |
|---|---|---|
| 2.1.1 Keyboard | A | B1 |
| 2.1.2 No Keyboard Trap | A | B1 |
| 2.1.4 Character Key Shortcuts | A | naprawa stwierdzona → B1 (weryfikacja po naprawie) |
| 2.2.1 Timing Adjustable | A | B5 (baner countdown) |
| 2.2.2 Pause, Stop, Hide | A | B5 |
| 2.3.1 Three Flashes | A | **N-D** |
| 2.4.1 Bypass Blocks | A | B2 (skip-link istnieje — zweryfikować działanie) |
| 2.4.2 Page Titled | A | **B2** — axe bada wyłącznie istnienie `<title>`, nie jego opisowość; przy stronach obiektowych opisowość jest istotą kryterium |
| 2.4.3 Focus Order | A | B1 |
| 2.4.4 Link Purpose (In Context) | A | **B2** — setki linków-ikon i linków „więcej" w tabelach |
| 2.4.5 Multiple Ways | AA | **B2** |
| 2.4.6 Headings and Labels | AA | B2 |
| 2.4.7 Focus Visible | AA | B1 |
| 2.4.11 Focus Not Obscured | AA | B1 |
| 2.5.1 Pointer Gestures | A | **B5** — graf powiązań obsługuje gesty wielopunktowe i ścieżkowe; to kryterium odrębne od 2.5.7 |
| 2.5.2 Pointer Cancellation | A | **B5** |
| 2.5.3 Label in Name | A | B6 |
| 2.5.4 Motion Actuation | A | **N-D** |
| 2.5.7 Dragging Movements | AA | naprawa stwierdzona → B5 |
| 2.5.8 Target Size (Minimum) | AA | B5 + axe (`target-size`, częściowo) |

### Zrozumiałość

| Kryterium | Poz. | Źródło werdyktu |
|---|---|---|
| 3.1.1 Language of Page | A | axe (`html-has-lang`) |
| 3.1.2 Language of Parts | AA | naprawa stwierdzona → B2 |
| 3.2.1 On Focus | A | **B6** |
| 3.2.2 On Input | A | **B6** — multiseek zmienia formularz przy zmianie operatora/pola |
| 3.2.3 Consistent Navigation | AA | **B2** |
| 3.2.4 Consistent Identification | AA | **B2** |
| 3.2.6 Consistent Help | A | B4 |
| 3.3.1 Error Identification | A | B4 |
| 3.3.2 Labels or Instructions | A | B4 |
| 3.3.3 Error Suggestion | AA | B4 |
| 3.3.4 Error Prevention | AA | **B4** — kreator zgłoszenia wysyła dane; prawdopodobnie N-D, ale werdykt wymaga uzasadnienia |
| 3.3.7 Redundant Entry | A | B4 (hipoteza) |
| 3.3.8 Accessible Authentication | AA | B4 (hipoteza) |

### Solidność

| Kryterium | Poz. | Źródło werdyktu |
|---|---|---|
| 4.1.2 Name, Role, Value | A | axe (częściowo) + **B1/B6** — werdykt dla komponentów własnych (Select2, dynamiczne wiersze multiseek, modal wyszukiwania) wymaga oceny ręcznej |
| 4.1.3 Status Messages | AA | B6 |

**Kryteria pogrubione** zostały dopisane po drugiej recenzji — pierwotna
wersja specyfikacji ich nie przypisywała. Bloki badania ręcznego
rozszerzają się o nie odpowiednio: B2 o 1.4.1, 2.4.2, 2.4.4, 2.4.5, 3.2.3,
3.2.4; B5 o 2.5.1, 2.5.2; B6 o 3.2.1, 3.2.2; B4 o 3.3.4.

Kryteria oznaczone **N-D** wymagają jednorazowej analizy z zapisem
uzasadnienia — nie są „darmowe", choć są tanie.

## Naruszenia stwierdzone na etapie projektowania

Poniższe zostały **potwierdzone lekturą kodu** i wchodzą do zakresu napraw
bez czekania na audyt. Zadanie brzmi „napraw".

### 2.1.4 Character Key Shortcuts (A) — skrót `/`

`base.html:39-49` wiąże jednoznakowy skrót `/` na poziomie `document`.
Kryterium wymaga spełnienia co najmniej jednego z trzech warunków: skrót
daje się wyłączyć, daje się przemapować, albo jest aktywny wyłącznie gdy
focus spoczywa na konkretnym komponencie. Obecny kod nie spełnia żadnego —
wykluczenie `input, textarea, select` to nie to samo co „aktywny tylko przy
focusie".

Dotyczy w szczególności użytkowników oprogramowania do rozpoznawania mowy,
którzy dyktując tekst wysyłają pojedyncze znaki w stronę dokumentu.

Wymaga decyzji produktowej: skrót wyłączalny w profilu użytkownika czy
przeniesiony w zasięg focusa pola wyszukiwania.

### 3.1.2 Language of Parts (AA) — tytuły obcojęzyczne

W bazie bibliograficznej większość tytułów jest angielska, na stronie
zadeklarowanej jako `lang="pl"`. Czytnik ekranu odczyta angielski tytuł
polską fonetyką.

Dane są już w modelu: `Jezyk.kod_bcp47`
(`src/bpp/models/system/__init__.py:81`) trzyma dokładnie notację wymaganą
przez atrybut `lang` (BCP 47 / RFC 5646). Pole dodano dla eksportu
CERIF/OpenAIRE.

**Naprawa ma dwa wektory o bardzo różnym koszcie.**

**Wektor 1 — szablony (tani).** Widoczny tytuł renderują
`browse/praca_tabela_mono.html:17-21`, `browse/praca_tabela.html:7-10`
oraz breadcrumb `browse/praca.html:49`. Owinięcie w
`<span lang="…">`, z obsługą pustego pola (`blank=True` — pusty `lang=""`
jest gorszy niż brak atrybutu, więc atrybut ma się nie pojawiać wcale).

Uwaga na dwa różne języki w jednym miejscu: szablony renderują obok siebie
`tytul_oryginalny` (język z `rekord.jezyk`) i `tytul` — tytuł przełożony,
zwykle polski. Wymagają **osobnych** znaczników `lang`, a nie jednego
wspólnego na całym bloku.

**Korekta (2026-08-06):** `browse/praca_tabela.html` nie jest stroną —
mimo katalogu `browse/` jest to WARIANT generatora opisu bibliograficznego
(instalowany przez migrację `0295_instaluj_szablony.py:25` obok
`opis_bibliograficzny.html`). Strona szczegółów włącza wyłącznie
`praca_tabela_mono.html` (`browse/praca.html:54`).

**Wektor 2 — `opis_bibliograficzny_cache` (kosztowny).** Opis
bibliograficzny jest generowany serwerowo i cache'owany jako gotowy HTML,
a używany w 31 miejscach w szablonach — listy `browse`, wyniki multiseek,
wydawnictwa powiązane. Tytuł obcojęzyczny siedzi **wewnątrz tego
zcache'owanego HTML-u**, więc poprawka na poziomie szablonu go nie
obejmuje. Domknięcie 3.1.2 dla list i wyników wyszukiwania wymaga zmiany
w generatorze opisu (`src/bpp/models/util.py`) oraz **przebudowy
cache'u**, czyli migracji danych na produkcji.

**Korekta (2026-08-06):** to ustalenie jest nieprawdziwe. Przeliczenie
całej bazy dzieje się co noc niezależnie od tej zmiany —
`denorm_rebuild --no-flush` o 22:00 z harmonogramu Ofelii
(`bpp-deploy/docker-compose.application.yml:117-118`) brudzi wszystkie
wiersze, kolejka `denorm` je przelicza, a trigger `bpp_refresh_cache`
propaguje wynik do `bpp_rekord_mat`. Rzeczywistym warunkiem koniecznym
wektora 2 jest rozszerzenie allowlisty nh3 o `span`/`lang`
(`src/bpp/util/text.py:306-313`), którego ten dokument nie wymieniał.
Wektor 2 został wykonany 2026-08-06.

Ten wektor jest zasadniczą częścią kosztu 3.1.2 i to on decyduje, czy
kryterium da się domknąć w tej iteracji, czy trafi do wykazu niezgodności
jako zaplanowane.

**Zastrzeżenie:** `kod_bcp47` jest opcjonalne i w istniejących instalacjach
bywa niewypełnione. Poprawka kodu nie wystarcza — uzupełnienie słownika
języków jest zadaniem uczelni i trafia do raportu jako warunek, nie jako
fakt dokonany.

### 1.1.1 Non-text Content (A) — obrazy bez `alt`

Dwa elementy `<img>` w zakresie nie mają atrybutu `alt`:
`src/bpp/templates/504.html:12` oraz
`src/bpp/templates/user_navigation_autocomplete.html:7`. Naprawa
trywialna; wymaga jedynie rozstrzygnięcia, czy obraz niesie treść
(`alt="…"`), czy jest dekoracją (`alt=""`).

**Korekta (2026-08-06):** `user_navigation_autocomplete.html` jest martwy —
żaden widok go nie renderuje. Widok `bpp:navigation-autocomplete` zwraca
JSON (`Select2QuerySetSequenceView`), a listę rysuje Select2 po stronie
klienta. Szablon usunięto zamiast dopisywać `alt`. W zakresie zostaje jeden
obraz, nie dwa.

### 2.5.7 Dragging Movements (AA) — graf powiązań

`src/powiazania_autorow/templates/powiazania_autorow/graf.html` to widok
publiczny (bramkowany per uczelnia przez `czy_pokazywac_siec_powiazan` —
`bpp/views/browse.py:245`). Nawigacja po grafie opiera się na przeciąganiu.
Kryterium wymaga alternatywy realizowanej pojedynczym wskaźnikiem:
przycisków przesuwania i zoomu albo obsługi klawiaturą.

## Hipotezy do zbadania w audycie

Poniższe **nie są stwierdzonymi naruszeniami**. To miejsca, w których
zidentyfikowaliśmy podwyższone ryzyko i które muszą dostać werdykt
w tabeli kryteriów. Zadanie brzmi „zbadaj", a nie „napraw" — naprawa
wchodzi do zakresu dopiero, jeśli badanie potwierdzi naruszenie.

Rozdzielenie jest celowe: wpis „napraw" bez stwierdzonego naruszenia nie
daje się zaimplementować, bo nie wiadomo, co miałoby ulec zmianie.

### 3.3.7 Redundant Entry (A) — kreator zgłoszenia

`src/zglos_publikacje/views.py` używa `formtools` (`render_done`), czyli
jest kreatorem wieloetapowym — to konstrukcja, do której kryterium zostało
napisane. Zbadać, czy któryś krok wymaga ponownego podania informacji
podanej wcześniej. Jeśli nie wymaga — werdykt „spełnione".

### 3.3.8 Accessible Authentication (AA) — logowanie

Publiczny formularz logowania (`HTMXAwareLoginView`, importowany
w `src/django_bpp/urls.py:40`, rejestrowany w liniach 472, 497, 522).
Standardowy formularz hasła z działającym wklejaniem i obsługą menedżera
haseł **spełnia** to kryterium. Zbadać należy, czy na ścieżce logowania nie
pojawia się test funkcji poznawczych (captcha, zagadka) — np. po serii
nieudanych prób, bo w projekcie działa `django-axes`.

### 1.1.1 Non-text Content (A) — CAPTCHA w kreatorze zgłoszenia

Kryterium wymaga alternatywy w innej modalności percepcyjnej. Altcha jest
mechanizmem proof-of-work, więc niewizualnym — co rokuje dobrze, ale wymaga
potwierdzenia badaniem, nie założeniem.

### 2.5.8 Target Size Minimum (AA) — przewidywana kategoria najliczniejsza

24 × 24 px CSS. Przy 1781 ikonach `fi-*`, paginatorze multiseek,
breadcrumbs i gęstych tabelach bibliograficznych to prawdopodobnie
największy zbiór naruszeń w całym audycie — ale skala jest hipotezą do
zmierzenia skanem szerokim, nie faktem ustalonym.

## Kod zewnętrzny

### Widget UserWay — zostaje, zmienia status

Widget (`base.html:316-373`) **pozostaje** jako udogodnienie użytkowe
(powiększanie tekstu, tryb wysokiego kontrastu, font dla dyslektyków,
powiększony kursor). Usunięcie go, dopóki serwis pod spodem jest
nienaprawiony, odebrałoby częściową mitygację bez zysku.

Zmienia się natomiast jego status w dokumentacji. Komentarz „Widget
dostępności UserWay (WCAG)" (`base.html:317`) utrwala przekonanie, że
widget realizuje zgodność — nie realizuje: nie doda etykiety do pola, nie
naprawi kolejności focusa, nie zmieni kontrastu zapisanego w SCSS.

**W raporcie i w deklaracji dostępności widget nie może figurować jako
środek zapewnienia zgodności.** Może figurować wyłącznie jako udogodnienie
dodatkowe. Komentarz w kodzie zostaje przeredagowany.

Guard `{% if not TESTING %}` (`base.html:316`) powoduje, że axe mierzy DOM
**bez nakładki** — czyli w stanie ocenianym przez audytora. Wymaga
komentarza wyjaśniającego, że ma to znaczenie semantyczne, nie tylko
wydajnościowe, żeby nikt go nie „naprawił". Gdyby widget się ładował,
fałszowałby pomiar w obie strony: podmienia atrybuty ARIA (fałszywa zieleń)
i wstrzykuje własny przycisk (fałszywa czerwień).

**Obserwacja poboczna, poza zakresem:** `data-account="u5BrWIqGkK"` jest
zaszyty na sztywno, więc wszystkie instancje wielo-uczelniane raportują się
do jednego konta UserWay. Do rozważenia jako pole w `Uczelnia`, z opcją
wyłączenia widgetu per uczelnia.

### Foundation 6.9 — nadpisujemy, nie czekamy

Foundation jest w trybie maintenance (odnotowuje to `Gruntfile.js:14-16`
przy okazji wyciszania deprecacji Sassa). Poprawka z upstreamu nie
nadejdzie. Naruszenia w komponentach Foundation naprawiamy u siebie:
nadpisaniem szablonu, dodatkowym atrybutem albo warstwą SCSS.

### Pakiet `multiseek` — komponent o największym znaczeniu

Wyszukiwarka to najbardziej złożony interaktywnie element części
publicznej, a jej logika (dynamiczne wiersze warunków, operatory,
doładowywanie wyników, paginator) pochodzi z pakietu `multiseek`
w site-packages. Nadpisane mamy **wyłącznie szablony**
(`src/django_bpp/templates/multiseek/`), nie JavaScript.

Konsekwencja: naprawy dotyczące struktury HTML są w naszym zasięgu przez
nadpisanie szablonu, natomiast naprawy dotyczące zachowania (focus,
`aria-live` przy doładowaniu wyników, obsługa klawiaturą dodawania
warunków) mogą wymagać zmiany w samym pakiecie. Ponieważ `multiseek` jest
pakietem rozwijanym w tej samej organizacji, ścieżka „poprawka
w upstreamie" jest realna — inaczej niż przy Foundation.

### Select2 — najpierw pomiar

Select2 deklaruje własne wsparcie ARIA. Pytanie brzmi, czy nasza
konfiguracja go nie psuje — `bare.html:159` podmienia motyw na
`foundation`, czyli całą warstwę prezentacji. Kolejność działań przy
stwierdzonym naruszeniu: konfiguracja komponentu → nasza nakładka →
dopiero w ostateczności wymiana.

### foundation-datepicker / jQuery UI

Ładowane w `bare.html:73,79`. Kalendarze wyboru daty są typowym źródłem
pułapek klawiaturowych; do zbadania w bloku 1.

**DataTables nie jest komponentem części publicznej** — występuje
wyłącznie w aplikacjach za logowaniem. Wcześniejsza wersja tej
specyfikacji błędnie umieszczała go w zakresie.

## Raport zgodności

Lokalizacja: `docs/dostepnosc/raport-zgodnosci-wcag22aa.md`, po polsku,
wersjonowany w gicie razem z kodem.

### Rozgraniczenie odpowiedzialności

Pierwszy akapit raportu musi stwierdzać wprost, że dotyczy on **silnika
BPP**, a nie wdrożenia konkretnej uczelni. Bez tego uczelnia wklei go do
deklaracji jako całość i zadeklaruje zgodność rzeczy niezbadanych.

### Struktura

1. **Metadane badania** — data, wersja BPP (`django_bpp/version.py`),
   zakres, poziom docelowy, narzędzia i przeglądarki, metodyka (WCAG-EM).
2. **Próbka** — lista zbadanych widoków z uzasadnieniem doboru. Bez niej
   raport jest nieweryfikowalny.
3. **Wynik zbiorczy** — *zgodna* / *częściowo zgodna* / *niezgodna*.
   Realistycznie na starcie „częściowo zgodna"; uczciwe „częściowo" wraz
   z wykazem niezgodności jest bezpieczniejsze prawnie niż „w pełni".
4. **Tabela 55 kryteriów A + AA WCAG 2.2** — każde z werdyktem
   *spełnione* / *niespełnione* / *nie dotyczy* i jednozdaniowym
   uzasadnieniem. „Nie dotyczy" również wymaga uzasadnienia. To jądro
   raportu i to odróżnia go od zrzutu z narzędzia.
5. **Wykaz niezgodności** — każda z odniesieniem do kryterium, opisem
   wpływu na użytkownika, lokalizacją w kodzie i statusem (naprawione /
   zaplanowane / zaakceptowane z uzasadnieniem).
6. **Sekcja „co musi zrobić uczelnia"** — jawna lista tego, czego raport
   nie obejmuje: własne treści i aktualności, załączniki PDF/DOCX, branding
   wgrany po wdrożeniu, dane kontaktowe i procedura odwoławcza w
   deklaracji, uzupełnienie `kod_bcp47` w słowniku języków.
7. **Ograniczenia weryfikacji automatycznej** — zapisane wprost przy
   każdym kryterium, którego bramka CI nie pokrywa:
   - **niewykrywalne automatem:** 2.5.7, 3.3.7, 3.3.8, 3.2.6, 2.5.3,
     1.4.13, 4.1.3 (axe wykryje brak `aria-live` tylko w wąskich
     przypadkach, nie stwierdzi, że komunikat *powinien* być ogłoszony),
     2.1.4, 2.4.11;
   - **wykrywane częściowo:** 2.5.8 (reguła `target-size` nie rozstrzyga
     wyjątków: odstępów, tekstu w zdaniu, kontrolki systemowej), 1.4.11
     (bez stanu `:focus-visible`), 3.1.2 (axe sprawdzi poprawność
     wartości `lang`, ale nie jej brak tam, gdzie język się zmienia).

   Odnotować też, że tag `wcag22a` w axe-core nie obejmuje żadnych reguł
   (oba kryteria 2.2 poziomu A — 3.2.6 i 3.3.7 — są nieautomatyzowalne).
   W konfiguracji zostaje **celowo**, jako zabezpieczenie na wypadek
   dodania reguł w przyszłych wersjach axe-core; w raporcie nie może być
   wymieniany jako dowód pokrycia.

8. **Zastrzeżenie o warunkach pomiaru** — badanie prowadzono na DOM-ie
   **bez nakładki UserWay** (patrz sekcja o kodzie zewnętrznym). Na
   produkcji nakładka jest aktywna i modyfikuje atrybuty ARIA oraz dokłada
   własny element interfejsu. Werdykty raportu opisują zatem serwis, a nie
   serwis-z-nakładką, i mogą nie odtworzyć się co do joty przy badaniu
   żywej strony. Zastrzeżenie musi paść **wprost**: kontroler, któremu
   werdykt nie odtworzy się na produkcji, ma podstawy zakwestionować cały
   dokument. Jest to zarazem argument za rozważeniem wyłączenia nakładki
   po zakończeniu napraw.

### Relacja do WCAG 2.1

Raport prowadzony jest wobec WCAG 2.2. Ponieważ 2.2 zawiera w sobie 2.1,
zgodność z wymogiem ustawowym wynika z niego wprost — należy to stwierdzić
jednym zdaniem, z odnotowaniem, że kryterium 4.1.1 Parsing zostało w 2.2
wycofane.

### Cykl życia

Raport jest ważny dla wersji, przy której powstał. Warstwę automatyczną
utrzymuje w prawdzie bramka CI. **Istotna zmiana funkcjonalna w części
publicznej wymaga ponownego badania ręcznego** kryteriów niepokrytych
automatem — reguła zapisana w raporcie, inaczej po dwóch latach opisuje on
serwis, którego już nie ma.

## Bramka CI

Nowy marker `a11y` w `pytest.ini`, testy w `src/integration_tests/`,
wykonywane w ramach istniejącego `tests-only-playwright`. Nie osobny
pipeline — BPP ma już 12 shardów, trzynasty kanał to koszt bez zysku.

**Testy muszą nosić oba markery** — `playwright` i `a11y`.
`tests-only-playwright` (`Makefile:518`)
selekcjonuje `-m "playwright"`, a `tests-without-playwright` selekcjonuje
`-m "not playwright"`; test oznaczony wyłącznie `a11y` wypadłby z obu
przebiegów i nigdy by się nie wykonał. Marker `a11y` służy do
selektywnego uruchamiania podczas prac (`-m "a11y"`), nie do włączania go
do przebiegu.

Blokuje **wyłącznie warstwa automatyczna**: rozjazd wyniku axe z baseline'em
(w **obie** strony — patrz zapadka) na widokach próbki oraz kontrast
w sześciu motywach. Warstwa ręczna z natury nie może być bramką — jest
procesem, nie asercją.

Zbiór kryteriów, o których bramka cokolwiek orzeka, jest wyliczony
w tabeli „Przypisanie 55 kryteriów do źródeł werdyktu" — to wiersze
oznaczone **axe**. Pozostałe bramka pomija i raport musi to mówić wprost.

Funkcja bramki jest węższa, niż się wydaje: **nie chroni użytkownika, tylko
chroni raport.** Wartość dla użytkownika daje naprawa. Bramka chroni przed
scenariuszem, w którym audyt wykazuje trzy niezgodności, dwadzieścia
release'ów później jest ich trzydzieści, a deklaracja wciąż mówi o trzech —
co jest podaniem nieprawdy w dokumencie i realną podstawą skargi.

Zakres bramki jest celowo wąski — pilnuje tego podzbioru kryteriów, o którym
raport twierdzi, że został zweryfikowany maszynowo. Rozszerzanie jej na
rzeczy mierzone przez axe nierzetelnie dałoby ten sam rodzaj fałszywej
pewności co widget UserWay, tylko po naszej stronie.

## Kolejność prac i zależności

Specyfikacja nie jest planem, ale rozstrzyga zależności, bez których planu
nie da się ułożyć:

1. **Infrastruktura testowa + strona wzorników.** Niezależna od
   wszystkiego; może startować od razu.
2. **Skan szeroki na dumpie.** Wymaga (1). Jego wynik **zamraża próbkę** —
   dopóki nie ma skanu, lista widoków jest wstępna.
3. **Naprawy stwierdzone** (2.1.4, 3.1.2 wektor 1, 1.1.1-alt, 2.5.7).
   Niezależne od skanu — wynikają z lektury kodu. Mogą iść równolegle z (2).
4. **Baseline freeze.** Dopiero **po** (3) i po zamrożeniu próbki. Kolejność
   jest istotna: baseline zakładany przed naprawami zaksięgowałby dług,
   który zaraz znika, i wymuszałby natychmiastową aktualizację pliku.
   Baseline zakładany po naprawach jest mniejszy i uczciwszy.
5. **Bramka CI.** Wymaga (4). Od tego momentu regresje są blokowane.
6. **Audyt ręczny, bloki 1–6.** Wymaga zamrożonej próbki z (2). Może iść
   równolegle z (5) — bramka i audyt nie kolidują.
7. **Raport.** Wymaga (6) i wyników (5).

Wąskim gardłem jest krok (2): wszystko poza naprawami stwierdzonymi na
niego czeka.

## Otwarte decyzje

Rzeczy, które specyfikacja świadomie zostawia do rozstrzygnięcia przed
planem — wypisane, żeby nie wypłynęły w trakcie wdrożenia:

**Skrót `/` (2.1.4).** Z trzech dopuszczonych przez kryterium wyjść —
wyłączenie, przemapowanie, zawężenie do focusa — dwa pierwsze wymagają
interfejsu ustawień, a ten nie istnieje dla użytkownika **anonimowego**,
czyli dokładnie dla audytowanego zakresu. **Rekomendacja: zawężenie skrótu
do sytuacji, gdy focus spoczywa na polu wyszukiwania w top-barze.** Jest to
jedyna opcja wykonalna bez budowania profilu preferencji dla anonima.
Decyzja produktowa — skrót przestanie działać globalnie.

**Motywy uczelniane w raporcie silnika.** `vizja`, `mwsl`, `uafm` to
motywy konkretnych klientów, nie warianty produktu. Jeśli test (b) wykaże
w nich zły kontrast, naprawa **zmienia branding uczelni** — decyzja nie
jest po stronie zespołu. Do rozstrzygnięcia: czy raport silnika obejmuje
wszystkie sześć motywów (i wtedy wymaga uzgodnień z klientami), czy trzy
motywy produktowe, a uczelniane trafiają do sekcji „co musi zrobić
uczelnia".

**Zakres 3.1.2.** Rekomendacja: wektor 2 (`opis_bibliograficzny_cache`)
**domyślnie poza tą iteracją**, ze statusem *zaplanowane* w wykazie
niezgodności. Przebudowa cache'u to operacja liveops na każdym wdrożeniu
z osobna, godziny przeliczania na dużych bazach.

**Alternatywy tekstowe dla wizualizacji (B3).** Pięć bibliotek, wymóg
„równoważnej informacji". Do rozstrzygnięcia, czy w tej iteracji, czy jako
osobne zadanie — akapit w bloku 3 ukrywa potencjalnie tygodnie pracy.

**Poprawki w pakiecie `multiseek`.** 4.1.3 przy doładowywaniu wyników
i obsługa klawiaturą dodawania warunków siedzą w JS pakietu. Czy ta
iteracja obejmuje wydanie nowej wersji `multiseek` i podbicie zależności
w BPP? To osobny cykl wydawniczy.

## Ryzyka

**Dane testowe są częścią mierzonego artefaktu.** Reguła `color-contrast`
nie analizuje CSS — renderuje piksele i porównuje rzeczywisty kolor tekstu
z rzeczywistym tłem. Element nieobecny na pustej bazie ma kontrast
niemierzalny, więc *nie zgłosi naruszenia*. Test na `baker.make(...)`
z jednym autorem przejdzie, a produkcyjna strona z sześćdziesięcioma
autorami, przypisami i badge'ami punktacji — niekoniecznie. Stąd wymóg
celowo bogatych fixture'ów dla (a) i uruchamiania (c) na dumpie
produkcyjnym.

**Źle dobrana próbka unieważnia raport.** Mitygacja: próbka jest doborem
opartym na skanie szerokim, jest zapisana w raporcie wraz z uzasadnieniem
i podlega akceptacji przed rozpoczęciem badania ręcznego.

**Skan szeroki mierzy jedno wdrożenie, nie silnik.** Dump produkcyjny to
jedna uczelnia: jeden motyw, jedna konfiguracja `Uczelnia` (graf powiązań
może być wyłączony, kreator zgłoszeń może być wyłączony, część widoków
ukryta). Mapa cieplna z takiego dumpa jest mapą **tego** wdrożenia.
Mitygacja: skan uzupełniony przebiegiem na bazie testowej z włączonymi
wszystkimi opcjonalnymi funkcjami — z jawnym odnotowaniem w raporcie,
które widoki zbadano na danych syntetycznych.

Dodatkowo: dumpy istnieją tylko na maszynie dewelopera. Dla każdego innego
wykonawcy skan ma niewycenione warunki wstępne (pozyskanie danych, a wraz
z nimi obowiązki RODO — dumpy zawierają dane osobowe autorów).

**2.5.8 może okazać się kosztowniejsze niż reszta razem wzięta.** Przy 1781
ikonach zmiana rozmiaru celów dotykowych to ingerencja w gęstość układu
całego serwisu, z ryzykiem regresji wizualnej we wszystkich sześciu
motywach. Jeśli nakład przekroczy oczekiwania, dopuszczalne jest zamknięcie
części przypadków jako niezgodności zaakceptowanych z uzasadnieniem —
z jawnym wpisem w wykazie, nie przez przemilczenie.

**`kod_bcp47` bywa niewypełnione.** Poprawka 3.1.2 jest częściowo poza naszą
kontrolą; raport musi to rozgraniczać.

**3.1.2 może nie zamknąć się w tej iteracji.** Wektor
`opis_bibliograficzny_cache` wymaga zmiany w generatorze opisu plus
przebudowy cache'u na produkcji. Jeśli okaże się zbyt kosztowny, kryterium
trafia do wykazu jako *zaplanowane*, z opisem stanu częściowego (strony
szczegółowe oznaczone, listy i wyniki wyszukiwania nie) — nie jako
spełnione.

## Znaleziska poboczne

Rzeczy zauważone przy analizie, niezwiązane bezpośrednio z WCAG,
odnotowane żeby nie zginęły:

- **Błąd w szablonie:** `src/django_bpp/templates/bare.html:50` ma
  nadmiarowy nawias klamrowy —
  `content="{% url "bpp:browse_deklaracja_dostepnosci" %}}"` wyrenderuje
  URL deklaracji dostępności z doklejonym `}`. Ironicznie dotyczy to
  metadanej wskazującej deklarację dostępności. Poprawka jednoznakowa,
  ale wymaga osobnego commita — nie jest częścią audytu.

## Odroczone niezgodności

Decyzje podjęte 2026-08-06 przy wykonywaniu kroku 3 („Naprawy stwierdzone").
Zapisane tutaj, bo raport zgodności — właściwe miejsce takich wpisów —
jeszcze nie istnieje. Szczegóły i uzasadnienia:
`2026-08-06-wcag-naprawy-stwierdzone-design.md`.

**2.1.4 Character Key Shortcuts (A) — skrót `/`.**
Handler w `src/django_bpp/templates/base.html:39-49` wiąże `/` na
`document`, wykluczając jedynie `input`/`textarea`/`select`. Nie spełnia
żadnego z trzech warunków kryterium (wyłączalny, przemapowywalny, aktywny
tylko przy focusie). Stan: **niezgodne, świadomie odroczone**. Powód: brak
nacisku regulacyjnego i brak odbiorcy raportu; wszystkie trzy dopuszczone
wyjścia mają koszt produktowy (utrata skrótu globalnego albo zbudowanie
interfejsu preferencji dla użytkownika anonimowego).

**2.5.7 Dragging Movements (AA) — graf powiązań.**
`src/powiazania_autorow/templates/powiazania_autorow/graf.html`, widok
publiczny bramkowany per uczelnia (`czy_pokazywac_siec_powiazan`,
`src/bpp/views/browse.py:245`). Nawigacja wyłącznie przez przeciąganie.
Stan: **niezgodne, świadomie odroczone**. Powód: koszt nieproporcjonalny do
pozostałych napraw w tej iteracji, a funkcja jest opcjonalna i w części
wdrożeń wyłączona.

**3.1.2 — tytuł przełożony (`tytul`).**
Stan: **spełnione częściowo**. Oznaczamy tytuł oryginalny; przekład zostaje
bez atrybutu i dziedziczy `lang="pl"`. Dla rekordów, w których przekład jest
obcojęzyczny, kryterium pozostaje niespełnione. Powód: **model nie zawiera
danych o języku przekładu** — `jezyk_alt` to odwzorowanie atrybutu z API PBN
oznaczające drugi język pracy, nie język tytułu przełożonego. Domknięcie
wymaga nowego pola (migracja schematu + uzupełnienie danych przez uczelnie),
więc jest osobnym zadaniem, nie doszlifowaniem tego.

**3.1.2 — instalacje z niewypełnionym `kod_bcp47`.**
Stan: **spełnione warunkowo**. Pole jest `blank=True`; poprawka oznacza
tytuł tylko tam, gdzie słownik języków ma wypełniony kod BCP 47.
Uzupełnienie słownika jest zadaniem uczelni. Dodatkowo: `@depend_on_related`
przy `opis_bibliograficzny_cache`
(`src/bpp/models/wydawnictwo_ciagle.py:218-226`) **nie obejmuje**
`bpp.Jezyk`, więc uzupełnienie kodu w słowniku nie zabrudzi cache'ów —
opisy złapią nowy kod dopiero po najbliższym nocnym rebuildzie (do 24 h).

**3.1.2 — instalacje z własnym szablonem opisu.**
Stan: **spełnione warunkowo**. Edytujemy dwa szablony z repozytorium; jeśli
`SzablonDlaOpisuBibliograficznego.nazwa_szablonu` wskazuje na inny plik,
opisy nie dostaną znaczników mimo poprawnej allowlisty.

**3.1.2 — instalacje z własnym `OPIS_BIBLIOGRAFICZNY_ALLOWED_TAGS`.**
Stan: **spełnione warunkowo**. Override w settings zastępuje domyślną
allowlistę; wdrożenie, które go ustawiło przed tą zmianą, straci znaczniki
w opisie do czasu dopisania `span`/`lang`.

## Poza zakresem

- panel zalogowanego użytkownika i Django admin (a wraz z nimi DataTables)
- konfigurowalność widgetu UserWay per uczelnia
- wymiana Select2 lub pakietu `multiseek` na inne komponenty
- zewnętrzny audyt certyfikowany (możliwy krok walidacyjny **po**
  wykonaniu niniejszego — wtedy tani, bo bez niespodzianek)
- poziom AAA
