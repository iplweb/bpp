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
- **(4) Baseline freeze** — dopiero po naprawach i po zamrożeniu próbki.
  Kolejność jest istotna: baseline zakładany przed naprawami zaksięgowałby
  dług, który zaraz znika.
- **(5) Bramka CI z axe-core** — wymaga (4). Od tego momentu regresje
  dostępności są blokowane automatycznie.
- **(6) Audyt ręczny WCAG-EM, bloki 1–6** — wymaga próbki z (2).
- **(7) Raport zgodności** — wymaga (6) i wyników (5). Dziś nie istnieje,
  dlatego wykazy niezgodności mieszkają tymczasowo w specyfikacjach.

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
