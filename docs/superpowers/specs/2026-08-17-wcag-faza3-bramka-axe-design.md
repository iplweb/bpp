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
   publicznej**: `browse.scss`, `browse_autorzy.scss`,
   `browse_jednostki.scss`, `uczelnia.scss`, `_autor-legacy.scss`. Oba
   kolory występują też w aplikacjach za logowaniem
   (`ewaluacja_optymalizuj_publikacje`, `pbn_downloader_app`,
   `pbn_export_queue`), gdzie `#6c757d` bywa `background-color` — tam
   „przyciemnienie do 4.5:1 na swoim tle" nie ma sensu i tych wystąpień nie
   ruszamy. Docelowo jeden token SCSS zamiast kolejnego literału.

3. **Zieleń breadcrumbs** — przyciemnić `#008000` do progu 4.5:1.
   **Punkt obowiązkowy, nie warunkowy:** breadcrumbs są na wszystkich
   trzech stronach bramki, więc bez tej naprawy próg zero jest
   nieosiągalny i punkt 6 nie może przejść.

4. **Pomiar wszystkich sześciu motywów** (`blue`, `green`, `orange`,
   `vizja`, `mwsl`, `uafm`). Tani: context processor czyta
   `Uczelnia.theme_name`, więc wystarczy seed per motyw, bez restartu
   settings. Wynik ma charakter rozpoznania — naprawy w motywach
   **klienckich** nie wchodzą do tej fazy, tylko do wykazu i do rozmowy
   z uczelnią.

5. **Dane testowe bramki** — jawnie zdefiniowany fixture per strona plus
   asercja sanity, że badane elementy w ogóle istnieją (np. że axe ocenił
   niezerową liczbę węzłów w `color-contrast`). Bez tego próg zero można
   spełnić pustą stroną.

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
Bramka **nie blokuje** na `incomplete`, ale **wypisuje je w komunikacie**.
Powód: naruszenie może zmigrować z `violations` do `incomplete` po zmianie
tła i cicho zniknąć z pola widzenia.

**Kształt techniczny.** Moduł testowy wstrzykuje `axe.min.js`
z `node_modules` przez `page.add_script_tag` (projekt nie ma CSP, a obraz
testowy zachowuje `node_modules` — `docker/bpp_base/Dockerfile:499`), woła
`axe.run()` z tagami WCAG 2.2 A i AA, asertuje pustą listę naruszeń.
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

**Próg zero jest bezlitosny dla nowych stron.** To jego zaleta i wada
naraz: nie da się dołączyć strony bez naprawy, więc pokrycie rośnie wolno.
Reguła dołączania wyżej ma zapobiec temu, żeby „wolno" zmieniło się
w „nigdy".

## Weryfikacja

- Każda naprawa potwierdzona ponownym pomiarem axe na tej samej stronie:
  z naruszenia ma zrobić się `pass`.
- Bramka sprawdzona w obie strony: celowe wprowadzenie naruszenia (np.
  usunięcie etykiety) musi ją zapalić. Bez tego kroku nie wiadomo, czy
  bramka cokolwiek pilnuje — trzy razy w fazie 2 test przechodził
  z niewłaściwego powodu.
- Asercja sanity na niepustość: bramka ma widzieć elementy, nie pustą
  stronę.
- Zrzuty ekranu przed i po zmianie szarości, na stronie autora i uczelni.
- Naprawy w trzech szablonach spoza zasięgu bramki (`jednostka`, `zrodlo`,
  `tytul_raportu`) potwierdzone testem szablonowym albo doraźnym pomiarem —
  bramka ich nie obejmie.
- Pełna suita lokalnie na świeżych kontenerach; `PYTEST_TESTCONTAINERS_REUSE`
  unieważnia wynik przy testach zależnych od stanu bazy.
