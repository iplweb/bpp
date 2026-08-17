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
`wcag22aa`. Na stronie autora axe ocenił 66 reguł: 2 z naruszeniami,
30 zaliczonych, 1 niejednoznaczna, 33 niedotyczące.

| strona | reguła | elementów | szczegóły |
|---|---|---|---|
| autora | `color-contrast` | 6 | patrz niżej |
| autora | `label` | 1 | **critical** |
| uczelni | `color-contrast` | 4 | opisy kafelków |
| graf powiązań | `color-contrast` | 3 | — |

Naruszenia kontrastu rozkładają się na trzy kolory:

| kolor | tło | zmierzony | wymagany | charakter |
|---|---|---|---|---|
| `#7f8c8d` | `#ffffff` / `#fefefe` | 3.44–3.47 | 4.5 | szarość pomocnicza |
| `#6c757d` | `#f8f9fa` | 4.44 | 4.5 | opisy kafelków |
| `#008000` | `#efefef` | 4.46 | 4.5 | **zieleń motywu** |

Dwa pierwsze to zwykłe szarości, wspólne dla motywów — ich przyciemnienie
nie dotyka brandingu. Trzeci to kolor motywu, a specyfikacja 08-05 stawia
sprawę jasno: poprawa kontrastu w motywach uczelnianych zmienia branding
klienta i nie jest decyzją zespołu. Brakuje tu 0,04 punktu.

**Hipoteza o 2.5.8 nie potwierdza się na tych stronach.** Reguła
`target-size` wykonała się i wylądowała w `passes` — sprawdzone wprost, bo
brak reguły w wyniku mógłby znaczyć „nie uruchomiła się". Audyt 08-05
przewidywał tu największy zbiór naruszeń; na zmierzonych stronach go nie ma.
Nie skanowano paginatora multiseek ani gęstych tabel bibliograficznych,
które hipoteza wymienia — werdykt dotyczy wyłącznie trzech stron.

## Zakres

1. **Etykieta dla `input[name="suggested-title"]`** (strona autora,
   `label`, critical). Pole ma widoczny tekst obok, ale nie jest z nim
   powiązane programowo.

2. **Przyciemnienie dwóch szarości** — `#7f8c8d` i `#6c757d` — do co
   najmniej 4.5:1 na swoich tłach. Zmiana w SCSS, bez ruszania palety
   motywów.

3. **Pomiar wszystkich sześciu motywów** (`blue`, `green`, `orange`,
   `vizja`, `mwsl`, `uafm`). Dotąd zmierzono tylko `green`. To punkt, który
   może zmienić zakres: jeśli motywy klienckie mają gorszy kontrast, wpadamy
   w decyzje brandingowe.

4. **Zieleń breadcrumbs** — decyzja po punkcie 3, nie przed. Rekomendacja:
   przyciemnić o włos, różnica 0,04 jest niewidoczna gołym okiem. Jeśli
   pomiar pokaże, że problem dotyczy wielu motywów naraz, temat wraca do
   uczelni jako osobna rozmowa.

5. **Bramka axe-core** w istniejącym harnessie Playwright, progiem na zero
   naruszeń.

## Bramka — kształt

**Zero, nie baseline.** Przy trzynastu naruszeniach plik baseline to więcej
maszynerii niż same naprawy: trzeba obsłużyć dryf selektorów przy
przebudowie szablonu, wybrać granulację (per selektor jest precyzyjny, ale
kruchy; per liczba jest stabilny, ale przepuszcza podmianę naruszenia na
inne w tej samej regule) i utrzymywać go dla sześciu motywów. Naprawiamy
trzynaście rzeczy raz i mamy próg, który nie wymaga pielęgnacji.

**Zasięg: strony odwiedzane przez testy.** To nie jest skan całej
aplikacji. Nowa strona bez testu jest dla bramki niewidzialna — ograniczenie
świadome, nie przeoczone. Startowy zestaw to trzy zmierzone strony: autora,
uczelni i grafu powiązań.

**Kształt techniczny.** Moduł testowy wstrzykuje `axe.min.js`
z `node_modules` przez `page.add_script_tag`, woła `axe.run()` z tagami WCAG
2.2 A i AA, asertuje pustą listę naruszeń. Komunikat błędu wypisuje regułę,
selektor i fragment HTML-a, żeby diagnoza nie wymagała powtarzania pomiaru.
`axe-core` dochodzi jako devDependency przez yarn.

**Czego bramka nie robi:** nie mierzy motywów innych niż ten, w którym
biegną testy; nie zastępuje audytu ręcznego; nie ma zdania o kryteriach
niewykrywalnych automatem (2.5.7, 3.3.7, 3.3.8 i pozostałe z listy w
`2026-08-13-wcag-stan-i-pozostale-prace.md`).

## Poza zakresem

- Skan szeroki na dumpie produkcyjnym (krok 2 planu z 08-05).
- Audyt ręczny WCAG-EM i raport zgodności (kroki 6 i 7).
- Skrót `/` w panelu administracyjnym — osobne zadanie, poza zadeklarowanym
  zakresem audytu.
- 3.1.2 dla tytułu przełożonego — wymaga migracji schematu.

## Ryzyka

**Punkt 3 może wywrócić szacunki.** Pomiar sześciu motywów jest tani, ale
jego wynik nie jest znany. Dlatego punkt 4 jest decyzją PO pomiarze, a nie
zadaniem do wykonania.

**Kontrast zależy od motywu, bramka biegnie w jednym.** Testy Playwright
używają domyślnej konfiguracji, więc bramka pilnuje jednego motywu.
Rozszerzenie na sześć to sześciokrotny czas przebiegu — świadomie nie
wchodzi w tę fazę, ale pomiar z punktu 3 powie, czy to pilne.

**Przyciemnienie szarości dotyka wielu widoków naraz.** `#7f8c8d`
i `#6c757d` są używane szerzej niż na zmierzonych stronach. Zmiana jest
mała liczbowo, ale globalna — weryfikacja wizualna zrzutami przed i po.

## Weryfikacja

- Każda naprawa potwierdzona ponownym pomiarem axe na tej samej stronie:
  z naruszenia ma zrobić się `pass`.
- Bramka sprawdzona w obie strony: celowe wprowadzenie naruszenia (np.
  usunięcie etykiety) musi ją zapalić. Bez tego kroku nie wiadomo, czy
  bramka cokolwiek pilnuje — trzy razy w fazie 2 test przechodził
  z niewłaściwego powodu.
- Zrzuty ekranu przed i po zmianie szarości, na stronie autora i uczelni.
- Pełna suita lokalnie na świeżych kontenerach; `PYTEST_TESTCONTAINERS_REUSE`
  unieważnia wynik przy testach zależnych od stanu bazy.
