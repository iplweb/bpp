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

Około 16 widoków badanych także ręcznie:

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
widokach próbki. Fixture'y muszą być celowo bogate (patrz Ryzyka).

**(b) `src/integration_tests/test_a11y_kontrast.py`** — **syntetyczna strona
wzorników** (nowy widok testowy renderujący komplet komponentów: nagłówki,
przyciski, callouty wszystkich poziomów, badge punktacji, tabela
bibliograficzna, paginator multiseek, pola formularza w stanie normalnym
i błędu, breadcrumbs, top-bar), iterowana po wszystkich wartościach
`Uczelnia.theme_name` (`uczelnia.py:233`; motywy blue, green, orange,
vizja, mwsl, uafm wg `Gruntfile.js`). Reguły: `color-contrast` **oraz**
`non-text-contrast` (kryterium 1.4.11 — ramki pól, wskaźnik focusa, ikony;
sam `color-contrast` bada wyłącznie tekst).

Strona wzorników, a nie „jedna strona referencyjna z serwisu": komponent
nieobecny na wybranej stronie byłby zmierzony tylko w tym motywie, w którym
akurat biegnie test (a), a w pozostałych pięciu pozostałby niezbadany.
Parametryzowanie 16 realnych stron × 6 motywów rozwiązałoby to samo za cenę
96 przebiegów przeglądarki, w większości redundantnych — strona wzorników
daje pełne pokrycie komponentów przy sześciu przebiegach.

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

**Wykrywanie martwych wpisów** wymaga widoku całości, a test jest
parametryzowany per widok — asercja o wpisie dla widoku X nie ma
naturalnego miejsca w przebiegu widoku Y. Rozwiązanie: każdy przebieg
zapisuje swój wynik do wspólnego słownika w `pytest` cache, a **osobny
test zbiorczy**, uruchamiany po nich (`@pytest.mark.order` albo fixture
sesyjna z asercją w teardownie), porównuje sumę z baseline i zgłasza wpisy,
które się nie zmaterializowały. Test zbiorczy musi **rozpoznać niepełny
przebieg** (uruchomienie pojedynczego widoku, shard xdist) i wtedy się
pominąć — inaczej `pytest -k browse_autor` wywalałby się na wszystkich
pozostałych widokach jako „martwych".

Ten sam mechanizm obsługuje test motywów (b): widokiem jest tam
`wzorniki:<motyw>`.

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
wskaźnika focusa i ikon niosących znaczenie. Pokryty częściowo automatem
przez `non-text-contrast` w teście (b), ale wskaźnik focusa wymaga oceny
ręcznej, bo axe nie renderuje stanu `:focus-visible`.

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
wyszukiwania oraz podmian htmx. W całym `src/` jest 12 wystąpień
`aria-live`/`role="status"`/`role="alert"`, w większości w adminie —
czyli na ścieżce publicznej praktycznie zero.

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

**Wektor 2 — `opis_bibliograficzny_cache` (kosztowny).** Opis
bibliograficzny jest generowany serwerowo i cache'owany jako gotowy HTML,
a używany w 31 miejscach w szablonach — listy `browse`, wyniki multiseek,
wydawnictwa powiązane. Tytuł obcojęzyczny siedzi **wewnątrz tego
zcache'owanego HTML-u**, więc poprawka na poziomie szablonu go nie
obejmuje. Domknięcie 3.1.2 dla list i wyników wyszukiwania wymaga zmiany
w generatorze opisu (`src/bpp/models/util.py`) oraz **przebudowy
cache'u**, czyli migracji danych na produkcji.

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
   Jego obecność w konfiguracji jest nieszkodliwa, ale w raporcie mogłaby
   sugerować pokrycie, którego nie ma.

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

**Testy muszą nosić oba markery** — `playwright` i `a11y`. `Makefile:517`
selekcjonuje `-m "playwright"`, a `tests-without-playwright` selekcjonuje
`-m "not playwright"`; test oznaczony wyłącznie `a11y` wypadłby z obu
przebiegów i nigdy by się nie wykonał. Marker `a11y` służy do
selektywnego uruchamiania podczas prac (`-m "a11y"`), nie do włączania go
do przebiegu.

Blokuje **wyłącznie warstwa automatyczna**: naruszenia axe spoza baseline'u
na widokach próbki oraz kontrast w sześciu motywach. Warstwa ręczna z natury
nie może być bramką — jest procesem, nie asercją.

Funkcja bramki jest węższa, niż się wydaje: **nie chroni użytkownika, tylko
chroni raport.** Wartość dla użytkownika daje naprawa. Bramka chroni przed
scenariuszem, w którym audyt wykazuje trzy niezgodności, dwadzieścia
release'ów później jest ich trzydzieści, a deklaracja wciąż mówi o trzech —
co jest podaniem nieprawdy w dokumencie i realną podstawą skargi.

Zakres bramki jest celowo wąski — pilnuje tego podzbioru kryteriów, o którym
raport twierdzi, że został zweryfikowany maszynowo. Rozszerzanie jej na
rzeczy mierzone przez axe nierzetelnie dałoby ten sam rodzaj fałszywej
pewności co widget UserWay, tylko po naszej stronie.

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

## Poza zakresem

- panel zalogowanego użytkownika i Django admin (a wraz z nimi DataTables)
- konfigurowalność widgetu UserWay per uczelnia
- wymiana Select2 lub pakietu `multiseek` na inne komponenty
- zewnętrzny audyt certyfikowany (możliwy krok walidacyjny **po**
  wykonaniu niniejszego — wtedy tani, bo bez niespodzianek)
- poziom AAA
