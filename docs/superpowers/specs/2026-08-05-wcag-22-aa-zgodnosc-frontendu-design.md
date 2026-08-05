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
2. Norma EN 301 549, do której odsyła prawodawstwo unijne, w wydaniu z 2025 r.
   przeszła na WCAG 2.2 — kierunek nowelizacji jest znany. Badanie 2.2 teraz
   oszczędza powtórny audyt później.

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
- 153 użycia `aria-label`, 18 z 19 elementów `<img>` ma atrybut `alt`
- `Uczelnia.deklaracja_dostepnosci_*` — `uczelnia.py:669,709,714`
- gotowa infrastruktura Playwright (`src/integration_tests/`, fixture
  `channels_live_server`, marker `playwright` w `pytest.ini:73`)

## Metodyka

WCAG-EM (*Website Accessibility Conformance Evaluation Methodology*, W3C):
określenie zakresu → poznanie serwisu → dobór reprezentatywnej próbki →
badanie próbki → dokumentacja wyniku. Jest to metodyka rozpoznawana przez
polskich audytorów i organ nadzoru.

Dwie zasady WCAG kształtujące dobór próbki:

- **§5.2 Full pages** — zgodność deklaruje się dla całej strony. Nie wolno
  wyłączyć z oceny pojedynczego komponentu.
- **§5.3 Complete processes** — jeśli strona należy do procesu, wszystkie
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
multiseek — formularz · multiseek — wyniki (DataTables) · kreator „Zgłoś
publikację" — wszystkie kroki · graf powiązań autorów · strona logowania ·
deklaracja dostępności · 404 · oraz 2–3 widoki wskazane przez skan jako
odstające.

Lista finalna zapada po skanie i trafia do raportu wraz z uzasadnieniem.

## Warstwa automatyczna

### Narzędzie

`axe-core` z npm, wstrzykiwany do strony w teście Playwrighta:

```python
page.add_script_tag(path="node_modules/axe-core/axe.min.js")
wynik = page.evaluate(
    """() => axe.run(document, {
        runOnly: {type: 'tag', values: [
            'wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22a', 'wcag22aa'
        ]}
    })"""
)
```

Bez nowej zależności Pythona. `make assets` jest warunkiem wstępnym testów
Playwrighta, więc `node_modules/` jest obecne, gdy te testy biegną. Owijka
Pythonowa dokładałaby zależność i własny cykl wydawniczy dla dwóch linijek.

`axe-core` trafia do `devDependencies` w `package.json`.

### Tagi reguł

Egzekwowane: `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`, `wcag22a`,
`wcag22aa`.

Raportowane, **nieblokujące**: zestaw `best-practice` (to zalecenia Deque,
nie kryteria ustawowe — mieszanie ich z WCAG psuje wiarygodność raportu)
oraz reguły `duplicate-id` i `duplicate-id-active`, ponieważ realizują
kryterium 4.1.1 Parsing **wycofane w WCAG 2.2**.

### Trzy artefakty

**(a) `src/integration_tests/test_a11y_probka.py`** — parametryzowany po
widokach próbki. Fixture'y muszą być celowo bogate (patrz Ryzyka).

**(b) `src/integration_tests/test_a11y_kontrast.py`** — jedna strona
referencyjna, iterowana po wszystkich wartościach `Uczelnia.theme_name`
(`uczelnia.py:233`; motywy blue, green, orange, vizja, mwsl, uafm wg
`Gruntfile.js`), reguły ograniczone do `color-contrast`. Oś testowana
osobno, bo zmienną jest motyw, nie strona — parametryzowanie 16 stron × 6
motywów dałoby 96 przebiegów przeglądarki mierzących tę samą paletę.

**(c) `manage.py audyt_dostepnosci`** — komenda uruchamiana ręcznie, **poza
CI**. Czyta URL-e ze sitemapy plus listy stron nawigacyjnych, zrzuca
JSON/CSV z rozkładem naruszeń. Poza CI, bo tysiąc URL-i × przeglądarka to
dziesiątki minut. Uruchamiana lokalnie na **dumpie produkcyjnym** — i to
jest jej główna wartość, bo świeża baza testowa ma puste tabele, a puste
tabele nie mają problemów z dostępnością.

### Baseline jako zapadka

`a11y-baseline.json` zawiera znane, zaakceptowane naruszenia (identyfikator
reguły + selektor + widok). Bez tego nie da się wmergować testu, który
wywala się na istniejącym długu, zanim ten dług zostanie spłacony.

Zapadka działa w jedną stronę:

- naruszenie spoza baseline'u → test czerwony,
- wpis w baseline, który już nie występuje → **osobna asercja żąda jego
  usunięcia**. Bez tej drugiej asercji baseline po roku staje się listą
  nieprawd.

## Warstwa ręczna

Automat pokrywa około 30–40% kryteriów. Reszta wymaga badania prowadzonego
przez człowieka. Lista kontrolna skrojona pod BPP:

### Blok 1 — obsługa klawiaturą (2.1.1, 2.1.2, 2.4.3, 2.4.7, 2.4.11)

Przejście całej próbki wyłącznie klawiaturą. Punkty zapalne:

- **Select2** — dostępność listy podpowiedzi strzałkami, zatwierdzanie
  Enterem, zamykanie Escape. Uwaga: `bare.html:159` podmienia motyw na
  `foundation`, czyli warstwę prezentacji.
- **DataTables** — fokusowalność i aktywowalność nagłówków sortujących
  (`<th>` z `onclick` bez `tabindex` to typowa pułapka), paginacja jako
  lista linków.
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

### Blok 5 — adaptacja (1.4.4, 1.4.10, 1.4.12, 2.5.7, 2.5.8)

Powiększenie 200%, reflow przy 320 px bez przewijania poziomego, wymuszone
odstępy tekstu, rozmiar celów dotykowych, alternatywy dla przeciągania.

## Naruszenia rozpoznane na etapie projektowania

Poniższe wynikają z lektury kodu i wchodzą do zakresu napraw bez czekania
na audyt.

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

`browse/praca.html:5` renderuje `tytul_oryginalny` bez oznaczenia języka.
W bazie bibliograficznej większość tytułów jest angielska, na stronie
zadeklarowanej jako `lang="pl"`. Czytnik ekranu odczyta angielski tytuł
polską fonetyką.

Dane są już w modelu: `Jezyk.kod_bcp47`
(`src/bpp/models/system/__init__.py:85`) trzyma dokładnie notację wymaganą
przez atrybut `lang` (BCP 47 / RFC 5646). Pole dodano dla eksportu
CERIF/OpenAIRE.

Naprawa: owinięcie tytułu w `<span lang="{{ rekord.jezyk.kod_bcp47 }}">`
w szablonach opisu pracy, z obsługą przypadku pustego pola (`blank=True` —
pusty `lang=""` jest gorszy niż brak atrybutu, więc atrybut ma się nie
pojawiać wcale).

**Zastrzeżenie:** pole jest opcjonalne i w istniejących instalacjach bywa
niewypełnione. Poprawka szablonu nie wystarcza — uzupełnienie słownika
języków jest zadaniem uczelni i trafia do raportu jako warunek, nie jako
fakt dokonany.

### 2.5.7 Dragging Movements (AA) — graf powiązań

`src/powiazania_autorow/templates/powiazania_autorow/graf.html` to widok
publiczny (bramkowany per uczelnia przez `czy_pokazywac_siec_powiazan` —
`bpp/views/browse.py:245`). Nawigacja po grafie opiera się na przeciąganiu.
Kryterium wymaga alternatywy realizowanej pojedynczym wskaźnikiem:
przycisków przesuwania i zoomu albo obsługi klawiaturą.

### 3.3.7 Redundant Entry (A) — kreator zgłoszenia

`src/zglos_publikacje/views.py` używa `formtools` (`render_done`), czyli
jest kreatorem wieloetapowym. Informacja podana w kroku wcześniejszym nie
może być wymagana ponownie w kroku późniejszym.

### 3.3.8 Accessible Authentication (AA) — logowanie

Publiczny formularz logowania (`HTMXAwareLoginView`,
`src/django_bpp/urls.py:40`). Kryterium zakazuje wymagania testu funkcji
poznawczych bez alternatywy.

### 1.1.1 — CAPTCHA w kreatorze zgłoszenia

Kryterium wymaga alternatywy w innej modalności percepcyjnej. Altcha jest
mechanizmem proof-of-work, więc niewizualnym — co rokuje dobrze, ale wymaga
potwierdzenia badaniem, nie założeniem.

### 2.5.8 Target Size Minimum (AA) — przewidywana kategoria najliczniejsza

24 × 24 px CSS. Przy 1781 ikonach `fi-*`, paginacji DataTables, breadcrumbs
i gęstych tabelach bibliograficznych to prawdopodobnie największy zbiór
naruszeń w całym audycie.

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

### Select2 i DataTables — najpierw pomiar

Oba deklarują własne wsparcie ARIA. Pytanie brzmi, czy nasza konfiguracja
go nie psuje. Kolejność działań przy stwierdzonym naruszeniu: konfiguracja
komponentu → nasza nakładka → dopiero w ostateczności wymiana komponentu.
Wymiana DataTables to osobny projekt, nie podzadanie audytu.

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
7. **Ograniczenia weryfikacji automatycznej** — przy kryteriach 2.5.7,
   3.3.7 i 3.3.8 zapisane wprost, że automat ich nie wykrywa; przy 2.5.8,
   że wykrywa częściowo (reguła `target-size` nie rozstrzyga wyjątków:
   odstępów, tekstu w zdaniu, kontrolki systemowej).

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

## Poza zakresem

- panel zalogowanego użytkownika i Django admin
- konfigurowalność widgetu UserWay per uczelnia
- wymiana DataTables lub Select2 na inne komponenty
- zewnętrzny audyt certyfikowany (możliwy krok walidacyjny **po**
  wykonaniu niniejszego — wtedy tani, bo bez niespodzianek)
- poziom AAA
