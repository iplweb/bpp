# WCAG w BPP — stan prac i co zostało (2026-08-13)

Dokument-rozdzielacz: jedno miejsce, z którego widać, co w temacie WCAG jest
zrobione, co czeka i gdzie leżą szczegóły. Powstał, bo dotychczasowa wiedza
o pozostałych pracach żyła w `.superpowers/` — katalogu **wykluczonym przez
`.gitignore`** (linia 229), a więc znikającym razem z worktree. Ten plik jest
w repozytorium.

`docs/superpowers/` jest wykluczone z budowania mkdocs (`exclude_docs`
w `mkdocs.yml`), więc dokument nie trafia na stronę dokumentacji i nie
podlega gejtowi `mkdocs build --strict`.

## Mapa dokumentów

| dokument | o czym |
|---|---|
| `2026-08-05-wcag-22-aa-zgodnosc-frontendu-design.md` | audyt całościowy: tabela 55 kryteriów, kolejność prac, hipotezy, wykaz odroczonych |
| `2026-08-06-wcag-naprawy-stwierdzone-design.md` | faza 1 — 1.1.1, 3.1.1, 3.1.2 |
| `2026-08-07-wcag-skrot-i-graf-design.md` | faza 2 — 2.1.4, 2.5.7, 2.1.1 |
| `docs/superpowers/plans/2026-08-07-wcag-skrot-i-graf.md` | plan wdrożenia fazy 2 (8 zadań) |
| `2026-08-17-wcag-faza3-bramka-axe-design.md` | faza 3 — 14 naruszeń wykrywalnych automatem (kontrast, etykieta) + bramka axe-core progiem zero na trzech publicznych stronach |
| `docs/superpowers/plans/2026-08-25-wcag-faza3-bramka-axe.md` | plan wdrożenia fazy 3 (7 zadań) |

Oba dokumenty audytowe używają konwencji `**Korekta (data):**` — poprawki
dopisywane pod oryginalnym tekstem, bez kasowania. Ustalenia bywały
odwracane (2.1.4 i 2.5.7 przeszły drogę „napraw" → „odroczone" →
„naprawione"), więc historia decyzji jest tam czytelna.

## Co jest zrobione

**Faza 1** — PR [#732](https://github.com/iplweb/bpp/pull/732), gałąź
`fix-wcag-naprawy-stwierdzone`. Kryteria 1.1.1 (`alt=""` na 504), 3.1.1
(`lang="pl"` na 504), 3.1.2 (atrybut `lang` na tytułach, oba wektory).
Poza tym: allowlista nh3 o `span[lang]`, migracja `0488`, naprawa
podświetlania w wyszukiwarce rekordów powiązanych.

**Faza 2** — gałąź `fix-wcag-2140-2570`, worktree
`/Volumes/SSD/Programowanie/bpp-wcag-faza2`, PR jeszcze nie wystawiony.
Kryteria 2.1.4 (skrót `/` wyłączalny: `localStorage` + przełącznik
w stopce), 2.5.7 i 2.1.1 (siedem przycisków nawigacji po grafie + obsługa
klawiaturą, bez pułapki klawiaturowej 2.1.2 i bez przechwytywania zoomu
przeglądarki 1.4.4). Wszystkie 8 zadań planu domknięte.

**Faza 3** — gałąź `fix-wcag-faza3-bramka-axe`, ten sam worktree, PR
jeszcze nie wystawiony. Naprawiono 14 naruszeń wykrytych przez axe-core
(kontrast — dwie szarości + zieleń breadcrumbs w `app-green`, etykieta
pola `suggested-title`) i postawiono bramkę axe-core progiem zero w
`src/integration_tests/test_wcag_bramka_axe.py`. **Bramka NIE jest tym
samym co krok (5) planu 08-05** — patrz „Program WCAG poza tą gałęzią"
niżej za dokładny zasięg. Wszystkie 7 zadań planu domknięte.

## Ścieżka do scalenia

1. **#732** — odrzucić alerty CodeQL 155 i 156 (uzasadnienie:
   `codeql-155-156-report.md` w worktree `bpp-wcag-naprawy`), zmergować.
   Wszystkie realne gejty przechodzą; `UNSTABLE` bierze się wyłącznie
   z pomijanego „Deploy to GitHub Pages".
2. **Recenzja całej gałęzi fazy 2** na najmocniejszym modelu.
3. **Rebase.** `fix-wcag-naprawy-stwierdzone` został przebazowany po tym,
   jak odbiła się od niego faza 2: commity fazy 1 obecne w
   `fix-wcag-2140-2570` **nie są przodkami** base'a, który ma równoważne
   pod innymi SHA. `merge-base` obu gałęzi to dzisiaj czysty `dev`, więc
   PR stacked pokazałby zmiany fazy 1 jako część diffu fazy 2. Po merge'u
   #732:
   ```bash
   git rebase --onto origin/dev 6a0d66398 fix-wcag-2140-2570
   ```
   (`6a0d66398` to ostatni commit fazy 1 w historii fazy 2; rebase odtworzy
   wyłącznie commity fazy 2.)
4. **PR fazy 2** z bazą `dev` + recenzja PR-a.

## Triaż — otwarte decyzje projektowe

Nie usterki, tylko rzeczy wymagające czyjegoś zdania. Pozycje techniczne
z tej listy zostały już zamknięte (guardy `uczelnia.html` pod testem,
martwy `catch`, selektor BEM, test osi Y).

- **Układ siedmiu przycisków nawigacji.** Grid 3-kolumnowy układa je jako
  `↑ ← ⤢` / `→ ↓ +` / `−`, czyli w kolejności czytania, nie przestrzennie.
  Dla pomocy nawigacyjnej to słaby afordans: „w górę" sąsiaduje poziomo
  z „w lewo". Alternatywa to krzyż kierunkowy z zoomem obok.
- **Brak media query dla czterech narożnych overlayów grafu.** Przy 390 px
  legenda (`max-width: 260px`) zasłania większość obszaru rysowania,
  a przyciski nawigacji wypadają poniżej załamania.
- **Stopki `Co-Authored-By`.** Cztery z commitów fazy 2 ich nie mają
  (briefy 1–4 nie wymagały; dopisane od briefu 5). Rebase z punktu 3 jest
  naturalną okazją, żeby to poprawić — albo świadomie zostawić.

## Program WCAG poza tą gałęzią

Specyfikacja 08-05 rozpisuje siedem kroków. Wykonane są (1) infrastruktura
testowa częściowo i (3) naprawy stwierdzone. **Otwarte pozostają:**

- **(2) Skan szeroki na dumpie** — zamraża próbkę widoków. Wąskie gardło:
  wszystko poza naprawami stwierdzonymi na niego czeka.
- **(4) Baseline freeze** — **nieaktualne w kształcie z 08-05 dla stron
  objętych bramką fazy 3.** 08-05 projektował baseline-zapadkę zakładaną
  PRZED bramką CI (stąd zależność (5)→(4)). Faza 3 świadomie się z tego
  wyłamała: dla trzech stron (autor, uczelnia, graf powiązań) próg to
  ZERO naruszeń, bez pliku baseline — przy czternastu naruszeniach
  zapadka byłaby droższa niż sama naprawa (uzasadnienie:
  `2026-08-17-wcag-faza3-bramka-axe-design.md`, sekcja „Bramka —
  kształt"). Dla WSZYSTKICH POZOSTAŁYCH widoków serwisu krok (4) w
  kształcie z 08-05 nadal czeka na (2) — bramka fazy 3 ich nie dotyka.
- **(5) Bramka CI z axe-core** — **częściowo zrobione w fazie 3**, gałąź
  `fix-wcag-faza3-bramka-axe`, moduł
  `src/integration_tests/test_wcag_bramka_axe.py`. Różni się od (5)
  w 08-05 tym, że NIE wymagała (4) (patrz wyżej) i ma węższy zasięg niż
  „od tego momentu regresje są blokowane automatycznie" sugerowałoby:
  - **Zasięg bramki.** Tylko strony odwiedzane przez testy bramki — nie
    skan całej aplikacji. Startowy (i dziś jedyny) zestaw to trzy
    zmierzone strony: autora, uczelni i grafu powiązań. Bramka biegnie
    wyłącznie w motywie domyślnym `app-green`; pozostałych pięciu
    motywów NIE pilnuje (patrz „Kontrast w motywach" niżej). Nowa strona
    bez testu jest dla bramki niewidzialna — ograniczenie świadome, nie
    przeoczone.
  - **Reguła dołączania kolejnych stron.** Próg zero znaczy, że strony
    nie da się dołączyć „na próbę": albo najpierw naprawiamy jej
    naruszenia, albo jej nie dołączamy i wpisujemy powód do wykazu w
    tym dokumencie. Bez tej reguły zestaw zamarza na trzech stronach,
    bo dołączenie czwartej zawsze będzie „na później".
- **(6) Audyt ręczny WCAG-EM, bloki 1–6** — wymaga próbki z (2).
- **(7) Raport zgodności** — wymaga (6) i wyników (5). Dziś nie istnieje,
  dlatego wykazy niezgodności mieszkają tymczasowo w specyfikacjach.

**Znalezione przy recenzji fazy 2 (2026-08-16), nierozwiązane:**

- **2.1.4 w panelu administracyjnym.**
  `src/django_bpp/templates/admin/base_site.html:127` wiąże skrót `/` na
  `$(document)` i robi `preventDefault()` — dokładnie ten sam wzorzec, który
  faza 2 naprawiła po stronie publicznej, tylko nietknięty. Poza
  zadeklarowanym zakresem audytu (część publiczna dla anonima), ale
  kryterium obowiązuje per strona, więc raport zgodności obejmujący panel
  administracyjny to wykaże. Naprawa nie jest jednolinijkowa: admin nie
  dziedziczy po `base.html`, więc nie ładuje `skroty-klawiszowe.js` —
  potrzebny jest i skrypt, i guard. Osobne zadanie.

**Hipotezy do zbadania** (nie są stwierdzonymi naruszeniami — zadanie brzmi
„zbadaj", nie „napraw"):

- **3.3.7 Redundant Entry** — kreator zgłoszenia na `formtools`; czy któryś
  krok wymaga ponownego podania tej samej informacji.
- **3.3.8 Accessible Authentication** — czy na ścieżce logowania pojawia się
  test funkcji poznawczych, np. po serii nieudanych prób (`django-axes`).
- **1.1.1 dla CAPTCHA** — Altcha jest proof-of-work, więc niewizualna, co
  rokuje dobrze, ale wymaga potwierdzenia.
- **2.5.8 Target Size** — przewidywana najliczniejsza kategoria naruszeń
  (1781 ikon `fi-*`, paginator multiseek, gęste tabele). Skala jest
  hipotezą do zmierzenia skanem, nie faktem.

**Niezgodności odroczone i zgodności warunkowe** (pełne wpisy w sekcji
„Odroczone niezgodności" w 08-05):

- **3.1.2 dla tytułu przełożonego** — model nie ma pola z językiem
  przekładu; `jezyk_alt` to co innego. Domknięcie wymaga migracji schematu
  i uzupełnienia danych przez uczelnie.
- **3.1.2 na instalacjach z własnym szablonem opisu, z override'em
  `opis_bibliograficzny.html` w dbtemplates albo z własnym
  `OPIS_BIBLIOGRAFICZNY_ALLOWED_TAGS`** — trzy warianty tego samego
  ryzyka: wdrożenie dostanie deploy bez znacznika `lang` i **bez żadnego
  sygnału o tym**. Sposób sprawdzenia per wdrożenie i dwa wyjścia opisane
  w 08-05.

## Kontrast w motywach (pomiar 2026-08-25)

Bramka axe (zadania 1–5) biegnie wyłącznie na motywie domyślnym
`app-green` — o pozostałych pięciu (`app-blue`, `app-orange`, `app-vizja`,
`app-mwsl`, `app-uafm`, patrz `Uczelnia.theme_name` w
`src/django_bpp/settings/base.py`) nie było żadnych danych. To zadanie
(6) jest **rozpoznaniem, nie naprawą**: naprawy w motywach klienckich
(`app-vizja`, `app-mwsl`, `app-uafm`) nie wchodzą do tej fazy — audyt nie
oddaje takich decyzji zespołowi bez udziału uczelni.

**Metoda.** Skrypt tymczasowy (`src/integration_tests/test_tmp_motywy.py`,
skasowany po pomiarze, nie wszedł do commita) parametryzowany po sześciu
motywach: dla każdego, w izolowanym `transaction=True` teście, tworzy
**jedną** `Uczelnia` z danym `theme_name`, otwiera stronę autora i skanuje
axe-core (`axe_helper.skanuj`, wersja **axe-core 4.13.0**, zbudowana przez
`make assets` tego samego dnia). Motyw bierze się z `request._uczelnia`,
czyli z mapowania host → `Site` → `Uczelnia`, **nie** z oglądanego obiektu —
gdyby test trzymał sześć rekordów `Uczelnia` naraz na jednym hoście,
zmierzyłby sześć razy ten sam (pierwszy dopasowany) motyw. Dlatego każdy
przebieg miał dokładnie jedną `Uczelnię` w bazie (test transakcyjny,
tabele czyszczone między przebiegami), a asercja po `page.goto`
sprawdzała, że w `document.styleSheets` faktycznie załadował się arkusz
zawierający nazwę zadanego motywu w nazwie pliku (`{% static THEME_NAME %}`
→ `scss/app-X.css`) — inaczej test padał, zamiast cicho zmierzyć nie ten
motyw.

Asercja o arkuszu **przeszła za każdym razem bez modyfikacji seeda** —
kontrakt zadziałał zgodnie z założeniem briefu: `Site.objects.get(domain=…)`
nie znajduje dopasowania dla hosta testowego live-servera, `SITE_ID` też nie
wskazuje powiązanej `Uczelni`, więc `uczelnia_dla_site` spada na fallback
„jedyna uczelnia w systemie" (`get_single_uczelnia_or_none`) — a w
izolowanym teście transakcyjnym jest dokładnie jedna. Asercja została
zostawiona w skrypcie jako dowód, że pomiar mierzył to, co miał mierzyć —
nie usunięto jej mimo że nie zapaliła się ani razu. Skrypt tymczasowy
został skasowany po pomiarze (zgodnie z briefem), więc jej treść nie jest
nigdzie zacytowana w repozytorium — poniższa tabela i przyczyna źródłowa
są jedynym trwałym śladem tego pomiaru.

| motyw | naruszenia `color-contrast` (elementy) | wniosek |
|---|---|---|
| `app-green` (domyślny) | 0 | pokryty istniejącą bramką axe (zadania 1–5) |
| `app-blue` | 3 | naprawa w zakresie zespołu BPP — osobne zadanie |
| `app-orange` | 8 | naprawa w zakresie zespołu BPP — osobne zadanie |
| `app-vizja` | 8 | **motyw klienta** — naprawa wymaga decyzji uczelni |
| `app-mwsl` | 8 | **motyw klienta** — naprawa wymaga decyzji uczelni |
| `app-uafm` | 0 | brak naruszeń na zmierzonej stronie |

Naruszenia w `app-orange`, `app-vizja` i `app-mwsl` to (poza jednym
wspólnym z `app-blue`) ten sam zestaw ośmiu elementów: link „Autorzy" w
menu, link do widgetu publikacji, dwa linki w informacji
„przeglądarko-specyficznej", pasek cookie (tekst + oba przyciski) i stopka
(`bpp.iplweb.pl`, `iplweb.pl`). `app-blue` dzieli z nimi 2 z 3 pozycji
(link „Autorzy", stopka), ale nie ma naruszeń w pasku cookie ani w linkach
„przeglądarko-specyficznych" — nie jest identyczny.

**Przyczyna źródłowa (ustalona, nie hipoteza).** Wszystkie osiem elementów
w każdym motywie są linki `<a>`, a łącząca je usterka jest jedna: SCSS
motywów nie override'uje `$anchor-color` (domyślnie `:= $primary-color`)
na tle paska breadcrumbs `#efefef`. Zadanie 4 tej fazy naprawiło to
**wyłącznie dla `app-green`** (`.breadcrumbs a{color:green}` → `#006e00`,
patrz plan fazy 3); pozostałych pięciu motywów ta naprawa nie dotknęła —
nadal dziedziczą `$primary-color` motywu wprost. Policzone kontrasty linku
breadcrumbs na tle `#efefef` (próg WCAG 1.4.3: 4.5:1):

| motyw | kontrast | wynik |
|---|---|---|
| `app-vizja` | 1.83 | FAIL |
| `app-orange` | 2.73 | FAIL |
| `app-mwsl` | 3.17 | FAIL |
| `app-blue` | 4.08 | FAIL |
| `app-uafm` | 5.93 | PASS |

Naprawa jest tym samym jednolinijkowym override'em per motyw, co Zadanie 4
zastosowało dla `app-green`. `app-uafm` przechodzi próg mimo braku
tej naprawy — to wyjaśnia, dlaczego zmierzona strona autora wykazała dla
niego 0 naruszeń: to PASS akurat tego jednego koloru na tym jednym tle,
nie dowód, że cały motyw `app-uafm` jest wolny od problemów kontrastu.

`app-blue` i `app-orange` są motywami **produktowymi**, tak samo jak
`app-green` — naprawa tego koloru jest decyzją zespołu BPP, nie klienta
(ten sam status, jaki miała naprawa `app-green` w tej fazie). `app-vizja`
i `app-mwsl` są motywami **klienckimi** (ustalenie 08-05, wiersz 985:
„motywy konkretnych klientów, nie warianty produktu" — dotyczy `vizja`,
`mwsl` i `uafm`) — ich naprawa (zmiana koloru marki) wymaga zgody
uczelni, nie jest decyzją, którą audyt WCAG może podjąć sam.

**Zasięg pomiaru** — jak w istniejącej bramce (zadanie 5): tylko strona
autora, jedna strona na motyw. Nie jest to skan sześciu motywów × trzech
stron bramki; rozszerzenie zasięgu to osobna decyzja (koszt: 6× więcej
przebiegów Playwrighta na CI, gdyby miało wejść do bramki na stałe).

**Wniosek dla planowania:** `app-blue` i `app-orange` mają rzeczywiste,
naprawialne przez zespół BPP naruszenia kontrastu — kandydaci na kolejne
zadanie naprawcze w tym samym stylu co zadania 1–5 (dopasowanie koloru w
SCSS, bez zmiany layoutu). `app-vizja` i `app-mwsl` mają ten sam kształt
usterki, ale są motywami klienckimi — naprawa (zmiana koloru marki) nie
jest decyzją, którą audyt WCAG może podjąć sam; wymaga zgody właściciela
motywu. `app-uafm`, mimo że też klienckie, nie wykazał naruszeń na
zmierzonej stronie — nie znaczy to zgodności całego motywu, tylko że ta
jedna strona nie ujawniła problemu tym skanem.

### Drobiazgi odnotowane przy fazie 3 (nie blokują, do osobnych zadań)

**Te same dwie szarości żyją też poza zakresem naprawy.** Faza 3 przyciemniła
`#7f8c8d` i `#6c757d` w deklaracjach `color:` w `src/bpp/static/scss/*.scss`.
Oba kolory występują dodatkowo w arkuszach aplikacji **za logowaniem**
(`komparator_pbn.scss`, `ewaluacja_optymalizacja.scss`, `_multiseek-*.scss`,
`_pagination.scss`) oraz w innych aplikacjach (`pbn_import`,
`komparator_publikacji_pbn`, `ewaluacja_optymalizuj_publikacje`,
`src/bpp/static/bpp/scss/`). Były poza zadeklarowanym zakresem audytu (część
publiczna dla anonima), więc świadomie ich nie ruszano — ale jeśli zakres
kiedyś obejmie widoki za logowaniem, to jest gotowa lista miejsc.

**Martwe, śledzone w gicie arkusze CSS.** `src/bpp/static/scss/*.css` (m.in.
`browse.css`, `komparator_pbn.css`) są śledzone w repozytorium mimo wpisu
w `.gitignore`. Są przy tym **martwe**: grunt ich nie kompiluje (kompiluje
wyłącznie entrypointy `app-*.scss` i arkusze aplikacji), a żaden szablon ich
nie linkuje. `browse.css` to zastygły zrzut błędu kompilacji Sass sprzed lat.
Problem jest przedistniejący, niezwiązany z żadną fazą WCAG — wart osobnego
zgłoszenia i `git rm --cached`.

## Pułapki, które kosztowały czas

- **`grunt build` jest konieczny** po zmianie SCSS; szablony Django
  odświeżają się same, arkusze nie. Bundle JS jest **minifikowany**, więc
  grep po źródłowym formatowaniu daje fałszywy negatyw.
- **Nigdy `npm install`** — projekt używa Yarn.
- **Nigdy `pre-commit --all-files`** ani `ruff check --fix`. Uwaga: `pre-commit`
  bez argumentów przy czystym drzewie **nic nie sprawdza** („no files to
  check" na każdym hooku) — to przebieg pusty, nie zielony.
- **Nigdy `make clean-testcontainers`** na tym hoście — usuwa też cudze,
  działające kontenery. Zdarzyło się w trakcie prac: przy kilkunastu
  kontenerach na 8 GB świeży Postgres nie wstaje w 120 s. Obejście:
  `PYTEST_TESTCONTAINERS_REUSE=1`.
- **`run-site --from-dump` jest zepsuty** — `pg_restore: could not open
  input file "/tmp/dump": Brak dostępu`, mimo pliku 644, `/tmp` 1777
  w obrazie i `docker exec` jako root. Do zgłoszenia autorowi run-site.
  Obejście dla oględzin wizualnych: zrzuty ekranu z live servera
  Playwrighta.
- **Nazwa katalogu testów.** Założenie pakietu `tests/` obok istniejącego
  modułu `tests.py` przesłania ten drugi — pytest odmawia kolekcji, a testy
  po cichu przestają się wykonywać. Zdarzyło się w `powiazania_autorow`
  i kosztowało 18 niewykonywanych testów przez kilka commitów.
- **Ścieżki do plików w testach** kotwicz na katalogu pakietu
  (`Path(pakiet.__file__).parent`), nie na `parents[n]` od `__file__` —
  drugie łamie się przy każdym przeniesieniu pliku testowego.
