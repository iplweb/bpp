# WCAG faza 3 — naprawa naruszeń wykrywalnych automatem i bramka axe-core

Gałąź odbita od `fix-wcag-2140-2570` (faza 2, PR #763), która sama jest
podciągnięta do `dev`.

Poprzednie fazy zamykały pojedyncze kryteria wskazane lekturą kodu. Ta faza
zmienia rodzaj zabezpieczenia: zamiast kolejnego kryterium wprowadza
**automat, który pilnuje wszystkich naraz** — na stronach objętych testami.

## Dlaczego akurat to

Wszystko, co naprawiły fazy 1 i 2, chronią wyłącznie testy, które ktoś
pomyślał, żeby napisać. Sama faza 2 dostarczyła trzech dowodów, że to za
mało: asercja przybliżania grafu przechodziła, bo `cy.fit()` dobijał do
`maxZoom`; guardy `uczelnia.html` sprawdzały regexem obecność zamiast
semantyki, więc przepuszczały odwróconą logikę; stub `localStorage`
w testach JS nie działał, bo `Storage` w jsdom to legacy platform object.
Każdy z tych przypadków wyszedł dopiero przy próbie zepsucia kodu.

Skaner łapie klasę problemów, których nie trzeba przewidzieć. Nie zastąpi
audytu ręcznego — wyłapuje rzędu jednej trzeciej naruszeń WCAG — ale ta
jedna trzecia przestaje wymagać czujności człowieka.

## Stan zmierzony (2026-08-16, axe-core 4.13, motyw `green`)

Pomiar na trzech stronach, tagi `wcag2a`, `wcag2aa`, `wcag21a`, `wcag21aa`,
`wcag22a`, `wcag22aa`. Na stronie autora axe ocenił 66 reguł: 2
z naruszeniami, 30 zaliczonych, 1 niejednoznaczna, 33 niedotyczące.

| strona | reguła | elementów | szczegóły |
|---|---|---|---|
| autora | `color-contrast` | 6 | patrz niżej |
| autora | `label` | 1 | **critical** |
| uczelni | `color-contrast` | 4 | opisy kafelków |
| graf powiązań | `color-contrast` | 3 | breadcrumbs + szarości |

Razem **14 elementów** w dwóch regułach.

Naruszenia kontrastu rozkładają się na trzy kolory:

| kolor | tło | zmierzony | wymagany | charakter |
|---|---|---|---|---|
| `#7f8c8d` | `#ffffff` / `#fefefe` | 3.44–3.47 | 4.5 | szarość pomocnicza |
| `#6c757d` | `#f8f9fa` | 4.44 | 4.5 | opisy kafelków |
| `#008000` | `#efefef` | 4.46 | 4.5 | zieleń `app-green` |

**Wszystkie trzy kolory naprawiamy sami, bez pytania klientów.** Dwa
pierwsze to zwykłe szarości wspólne dla motywów. Trzeci to
`.breadcrumbs a{color:green}` z `app-green` — a `app-green` jest motywem
**produktowym i domyślnym**, nie klienckim. Ustalenie z 08-05 o tym, że
poprawa kontrastu zmienia branding i nie jest decyzją zespołu, dotyczy
wyłącznie `vizja`, `mwsl` i `uafm` („motywy konkretnych klientów, nie
warianty produktu", 08-05 wiersz 985). Wcześniejsza wersja tej
specyfikacji rozciągała to ustalenie na `app-green` — błędnie.

**Warunki pomiaru.** Dane z fikstur `model_bakery`, nie z dumpu: pojedynczy
`Autor` (`pokazuj=True`), pojedyncza `Uczelnia`, dla grafu dodatkowo
`AuthorConnection` do drugiego autora. To ma znaczenie przy progu zero:
`color-contrast` nie zgłosi elementu, którego na stronie nie ma, więc ubogi
fixture daje bramkę przechodzącą pusto. Patrz „Dane testowe" niżej.

**Hipoteza o 2.5.8 nie potwierdza się na tych stronach.** Reguła
`target-size` wykonała się i wylądowała w `passes` — sprawdzone wprost, bo
brak reguły w wyniku mógłby znaczyć „nie uruchomiła się". Audyt 08-05
przewidywał tu największy zbiór naruszeń; na zmierzonych stronach go nie ma.
Nie skanowano paginatora multiseek ani gęstych tabel bibliograficznych,
które hipoteza wymienia — werdykt dotyczy wyłącznie trzech stron.

## Zakres

1. **Etykieta dla widocznych pól `suggested-title`** — nie tylko na stronie
   autora. Ten sam nieopisany `input[type="text"][name="suggested-title"]`
   jest w czterech szablonach: `browse/autor.html:349`,
   `browse/jednostka.html:524`, `browse/zrodlo.html:118` oraz
   `browse/tytul_raportu.html:5`. Bramka widzi tylko pierwszy, ale
   naruszenie critical jest w każdym. Warianty `type="hidden"` tego samego
   pola (m.in. w `uczelnia.html`) są poprawne i zostają bez zmian —
   ukryte pola nie wymagają etykiety.

   `browse/tytul_raportu.html` nie jest nigdzie includowany; przed naprawą
   ustalić, czy to martwy szablon (faza 1 usunęła już jeden taki), i wtedy
   go skasować zamiast poprawiać.

2. **Przyciemnienie dwóch szarości** — `#7f8c8d` i `#6c757d` — do co
   najmniej 4.5:1. Zakres zawężony do **deklaracji `color:` w części
   publicznej**: `_autor-bem.scss`, `browse.scss`, `browse_autorzy.scss`,
   `browse_jednostki.scss`, `uczelnia.scss`, `_autor-legacy.scss`.
   `_autor-bem.scss` jest tu najważniejszy — ma cztery wystąpienia
   `#7f8c8d` i to on stoi za czterema z sześciu naruszeń kontrastu na
   stronie autora (`__id-value`, `__search-subtitle`, `__title-hint`,
   `__embed-link`). Pominięcie go zostawia próg zero nieosiągalnym. Oba
   kolory występują też w aplikacjach za logowaniem
   (`ewaluacja_optymalizuj_publikacje`, `pbn_downloader_app`,
   `pbn_export_queue`), gdzie `#6c757d` bywa `background-color` — tam
   „przyciemnienie do 4.5:1 na swoim tle" nie ma sensu i tych wystąpień nie
   ruszamy. Docelowo jeden token SCSS zamiast kolejnego literału.

3. **Zieleń breadcrumbs** — przyciemnić `#008000` do progu 4.5:1.
   **Punkt obowiązkowy, nie warunkowy:** breadcrumbs są na wszystkich
   trzech stronach bramki, więc bez tej naprawy próg zero jest
   nieosiągalny i punkt 6 nie może przejść.

4. **Pomiar wszystkich sześciu motywów** — wartości to `app-blue`,
   `app-green`, `app-orange`, `app-vizja`, `app-mwsl`, `app-uafm`
   (`settings/base.py`), a context processor skleja je wprost do
   `scss/<wartość>.css`. Uwaga na kontrakt: motyw bierze się z
   `request._uczelnia`, czyli z mapowania host → `Site` → `Uczelnia`, a nie
   z oglądanego obiektu. Sześć rekordów `Uczelnia` na jednym hoście
   zmierzyłoby sześć razy to samo. Pomiar wymaga **jednej** uczelni
   powiązanej z `Site`, przestawianej per przebieg, plus asercji, że
   faktycznie załadował się właściwy `app-X.css` ze statusem 200. Wynik ma
   charakter rozpoznania — naprawy w motywach **klienckich** nie wchodzą do
   tej fazy, tylko do wykazu i do rozmowy z uczelnią.

5. **Dane testowe bramki i sanity** — jawnie zdefiniowany fixture per
   strona. Sama asercja „axe ocenił niezerową liczbę węzłów" nie
   wystarcza: wspólny `base.html` spełnia ją nawet na stronie 404. Bramka
   ma więc sprawdzać status odpowiedzi 200, obecność sentinela właściwego
   widoku (element unikalny dla tej strony) i liczność kluczowych bloków,
   a dopiero potem uruchamiać axe. Do tego **wyłączony rerun**: fixture
   `page` dokłada automatyczny powtórny przebieg (`src/fixtures/conftest.py`),
   więc chwiejna bramka „czerwona, potem zielona" zostałaby zaliczona.

6. **Bramka axe-core** w istniejącym harnessie Playwright, progiem na zero
   naruszeń. **Wymaga ukończenia punktów 1–3 i 5.**

## Bramka — kształt

**Zero, nie baseline.** Przy czternastu naruszeniach plik baseline to więcej
maszynerii niż same naprawy: trzeba obsłużyć dryf selektorów przy
przebudowie szablonu i wybrać granulację (per selektor jest precyzyjny, ale
kruchy; per liczba jest stabilny, ale przepuszcza podmianę naruszenia na
inne w tej samej regule). Naprawiamy czternaście rzeczy raz i mamy próg,
który nie wymaga pielęgnacji.

**Zasięg: strony odwiedzane przez testy.** To nie jest skan całej
aplikacji. Nowa strona bez testu jest dla bramki niewidzialna — ograniczenie
świadome, nie przeoczone. Startowy zestaw to trzy zmierzone strony: autora,
uczelni i grafu powiązań.

**Reguła dołączania kolejnych stron.** Próg zero znaczy, że strony nie da
się dołączyć „na próbę": albo najpierw naprawiamy jej naruszenia, albo jej
nie dołączamy i wpisujemy powód do wykazu w
`2026-08-13-wcag-stan-i-pozostale-prace.md`. Bez tej reguły zestaw zamarza
na trzech stronach, bo dołączenie czwartej zawsze będzie „na później".

**Polityka dla `incomplete`.** axe zwraca trzecią kategorię — reguły, które
nie umiały rozstrzygnąć (na stronie autora był jeden taki przypadek;
`color-contrast` ląduje tam regularnie przy półprzezroczystych tłach, a
wrapper breadcrumbs ma `rgba(240,240,240,.85)` i `backdrop-filter`).
Bramka **nie blokuje** na `incomplete`, ale musi je **utrwalać**. Samo
`print` nie wystarczy: CI uruchamia pytest z domyślnym przechwytywaniem
wyjścia, więc tekst z przechodzącego testu nigdzie się nie pokaże i
migracja `violation → incomplete` zniknie dokładnie tak, jak ten zapis miał
temu zapobiec. Zapis idzie do artefaktu przebiegu albo do Step Summary.

**Kształt techniczny.** Moduł testowy wstrzykuje `axe.min.js` przez
`page.add_script_tag` (projekt nie ma CSP), woła `axe.run()` z tagami WCAG
2.2 A i AA, asertuje pustą listę naruszeń.

**Skąd `axe.min.js` w CI — warunek konieczny.** Obraz, w którym biegną
testy na CI, to target `test-runner` (`.github/workflows/tests.yml:257`),
a ten **nie zawiera `node_modules`**: stage `test-assets-builder` kompiluje
CSS/JS osobno i do finalnego obrazu trafiają „tylko gotowe pliki z /src/src
— bez Node, Yarn, Grunta i node_modules" (`docker/bpp_base/Dockerfile`,
komentarz nad stage'em). Wstrzykiwanie prosto z `node_modules` przejdzie
lokalnie i **padnie na CI**. Plan musi więc dołożyć jawny `COPY` samego
`axe.min.js` z `test-assets-builder` do `test-runner` i wskazywać ścieżkę
docelową, a nie hostowy `node_modules`. Weryfikacja tego punktu wymaga
zbudowania targetu `test-runner` i uruchomienia bramki w nim — lokalna
suita niczego tu nie dowodzi.
Komunikat błędu wypisuje regułę, selektor i fragment HTML-a, żeby diagnoza
nie wymagała powtarzania pomiaru. `axe-core` dochodzi jako devDependency
przez yarn; wersja jest przypięta w `yarn.lock`, a jej podbicie to świadoma
zmiana, która może zapalić bramkę nowymi regułami — do wykonania osobno,
z ponownym pomiarem.

**Czego bramka nie robi:** nie mierzy motywów innych niż ten, w którym
biegną testy; nie zastępuje audytu ręcznego; nie ma zdania o kryteriach
niewykrywalnych automatem (2.5.7, 3.3.7, 3.3.8 i pozostałe z listy w
`2026-08-13-wcag-stan-i-pozostale-prace.md`).

## Stosunek do architektury bramki z 08-05

Audyt 08-05 projektował inną bramkę: baseline-zapadkę (krok 5 wymagał 4,
a 4 — próbki zamrożonej skanem szerokim), stronę wzorników do kontrastu
w sześciu motywach, dwa przebiegi (blokujący plus `best-practice`
informacyjny) i podwójne markery `playwright` + `a11y`. Ta faza świadomie
się z tego wyłamuje:

- **unieważnia** baseline dla stron objętych progiem zero — przy czternastu
  naruszeniach zapadka jest droższa niż naprawa,
- **odracza** stronę wzorników, drugi przebieg `best-practice` i pomiar
  ×6 motywów w CI,
- **zachowuje** rozdzielenie markerów, bo bramka wchodzi do istniejącego
  zestawu Playwright.

Po wdrożeniu zaktualizować mapę dokumentów w
`2026-08-13-wcag-stan-i-pozostale-prace.md`, żeby kroki 4 i 5 planu z 08-05
nie wyglądały na nietknięte.

## Odrzucone propozycje z recenzji

Zapisane, żeby nie wracały jako „przeoczenie".

**Hybryda: zero dla trzech czystych stron + ratchet baseline dla nowych.**
Kusząca i technicznie słuszna — zdejmuje zarzut, że próg zero premiuje
trzymanie brudnej strony poza CI. Odrzucona na teraz, bo wprowadza dokładnie
tę maszynerię, której ta faza unika, zanim istnieje choć jedna strona
z długiem nie do spłacenia. **Warunek powrotu:** pierwszy widok, którego
naruszeń nie da się naprawić w ramach jednego PR-a. Wtedy ratchet z 08-05
(wiersze 269–328) jest gotowym projektem do przejęcia.

**Właściciel bramki, cadence aktualizacji axe, SLA triage'u, zakaz `xfail`
bez numeru sprawy.** Rozsądne w większym zespole. Tutaj byłby to proces
pisany dla samego procesu — reguły, których nikt nie egzekwuje, psują
dokument bardziej niż ich brak. Ryzyko degeneracji jest za to nazwane
w „Ryzykach", a przypięta wersja axe znaczy, że bramka nie zmieni zdania
sama z siebie.

**Meta-test pilnujący, że nikt nie dopisał `skip`, `exclude` ani
`disableRules`.** Odłożone: przy trzech przypadkach i jednym helperze
przegląd kodu wystarcza. Wraca razem z ratchetem, gdy bramka urośnie.

## Poza zakresem

- Skan szeroki na dumpie produkcyjnym (krok 2 planu z 08-05).
- Audyt ręczny WCAG-EM i raport zgodności (kroki 6 i 7).
- Skrót `/` w panelu administracyjnym — osobne zadanie, poza zadeklarowanym
  zakresem audytu.
- 3.1.2 dla tytułu przełożonego — wymaga migracji schematu.
- Naprawy kontrastu w motywach klienckich (`vizja`, `mwsl`, `uafm`), gdyby
  pomiar z punktu 4 je wykazał.

## Ryzyka

**Pomiar sześciu motywów może dorzucić pracy poza tę fazę.** Jeśli motywy
klienckie mają gorszy kontrast, wynik idzie do wykazu i do rozmowy
z uczelnią, a nie do tego wdrożenia. Sama bramka biegnie w `app-green`
i tej zależności nie ma.

**Przyciemnienie szarości dotyka wielu widoków naraz.** Oba kolory są
używane szerzej niż na zmierzonych stronach — zmiana jest mała liczbowo,
ale globalna w części publicznej. Weryfikacja zrzutami przed i po.

**Bramka biegnie w jednym motywie.** Rozszerzenie na sześć to
sześciokrotny czas przebiegu; świadomie poza fazą. Pomiar z punktu 4 powie,
czy to pilne.

**Token zamiast literału rozszerza promień zmiany.** Wprowadzenie jednego
tokenu SCSS w miejsce dwóch literałów brzmi porządkowo, ale `common.scss`
importuje kilkanaście arkuszy — zmiana tokenu dotknie selektorów spoza
pięciu wymienionych plików. Zrzuty tylko strony autora i uczelni nie pokryją
takiego promienia. Jeśli token ma wejść, to z osobnym przeglądem widoków.

**DOM testowy różni się od produkcyjnego.** Widget UserWay jest całkowicie
wyłączony pod `TESTING` (`base.html`), więc bramka mierzy stronę bez niego.
To świadome ograniczenie zakresu, nie przeoczenie — ale znaczy, że zielona
bramka nie mówi nic o dostępności tego widgetu na produkcji.

**Próg zero jest bezlitosny dla nowych stron.** To jego zaleta i wada
naraz: nie da się dołączyć strony bez naprawy, więc pokrycie rośnie wolno.
Reguła dołączania wyżej ma zapobiec temu, żeby „wolno" zmieniło się
w „nigdy".

## Weryfikacja

- Każda naprawa potwierdzona ponownym pomiarem axe na tej samej stronie:
  z naruszenia ma zrobić się `pass`.
- **Bramka uruchomiona w zbudowanym targecie `test-runner`**, nie tylko
  lokalnie. Bez tego nie wiadomo, czy `axe.min.js` w ogóle jest w obrazie.
- Bramka sprawdzona w obie strony, dla **obu** egzekwowanych rodzin reguł:
  usunięcie etykiety musi zapalić `label`, a rozjaśnienie koloru —
  `color-contrast`. Mutacja tylko pierwszej dowodzi połowy. Bez tego kroku
  nie wiadomo, czy bramka cokolwiek pilnuje — trzy razy w fazie 2 test
  przechodził z niewłaściwego powodu.
- Asercja sanity na niepustość: bramka ma widzieć elementy, nie pustą
  stronę.
- Zrzuty ekranu przed i po zmianie szarości, na stronie autora i uczelni.
- Naprawy w trzech szablonach spoza zasięgu bramki (`jednostka`, `zrodlo`,
  `tytul_raportu`) potwierdzone **semantycznie na wyrenderowanym DOM** —
  sprawdzeniem dostępnej nazwy pola, nie obecnością znacznika `<label>`
  w źródle. `<label>` z błędnym `for` istnieje i niczego nie wiąże; to
  dokładnie ten rodzaj pozornej zieleni, który faza 2 złapała trzy razy.
- Pełna suita lokalnie na świeżych kontenerach; `PYTEST_TESTCONTAINERS_REUSE`
  unieważnia wynik przy testach zależnych od stanu bazy.
