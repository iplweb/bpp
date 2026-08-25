# WCAG faza 3 — bramka axe-core: plan wdrożenia

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Naprawić 14 naruszeń WCAG wykrytych przez axe-core na trzech
publicznych stronach BPP i postawić bramkę, która nie przepuści kolejnych.

**Architecture:** Bramka to moduł testowy Playwright w istniejącym harnessie
(`src/integration_tests/`). `axe.min.js` trafia do statyków przez zadanie
grunta — tym samym wzorcem, którym repo kopiuje już Rollbara — więc jest
dostępny i lokalnie, i w obrazie CI `test-runner`, który nie ma
`node_modules`. Próg: zero naruszeń, bez pliku baseline.

**Tech Stack:** axe-core 4.13 (devDependency przez yarn), Playwright
(pytest-playwright), Grunt, SCSS/Dart Sass, Django templates.

Spec: `docs/superpowers/specs/2026-08-17-wcag-faza3-bramka-axe-design.md`

## Global Constraints

- Python: max 88 znaków w linii (ruff).
- Testy: wyłącznie konwencja pytest — funkcje, nie klasy `unittest.TestCase`.
- Komentarze w szablonach Django: `{# ... #}` **jednoliniowe**, każda linia
  z własnym otwarciem i zamknięciem.
- Nigdy `npm install` — projekt używa Yarn.
- Nigdy `pre-commit --all-files` ani `ruff check --fix`.
- Nigdy `make clean-testcontainers` — na hoście biegają cudze kontenery.
- Po zmianie SCSS: `make assets` (nie `npx grunt build` — choć od #772 grunt
  też stempluje sentinel, `make assets` jest kanoniczne).
- Do werdyktu „zielono" NIE używać `PYTEST_TESTCONTAINERS_REUSE=1` —
  współdzielona baza daje fałszywe wyniki w testach zależnych od stanu.
- Host bywa obciążony: `-n 4`, nie `-n auto`.
- Każdy commit kończy się stopką `Co-Authored-By: Claude Opus 5 (1M context)
  <noreply@anthropic.com>`.

## Kolory — wartości docelowe (policzone, nie oszacowane)

| było | będzie | kontrast po zmianie |
|---|---|---|
| `#7f8c8d` | `#68706f` | 5.08 na `#ffffff`, 5.03 na `#fefefe`, 4.82 na `#f8f9fa` |
| `#6c757d` | `#636b73` | 5.41 na `#ffffff`, 5.13 na `#f8f9fa` |
| `green` (`#008000`) | `#006e00` | 5.65 na `#efefef` |

Wszystkie z zapasem ponad próg 4.5, żeby drobna zmiana tła nie wywróciła
bramki.

## Struktura plików

| plik | odpowiedzialność |
|---|---|
| `Gruntfile.js` | nowe zadanie `shell:copyAxe` w liście `build` |
| `.gitignore` | `src/bpp/static/axe/` jako artefakt builda |
| `package.json`, `yarn.lock` | `axe-core` jako devDependency |
| `src/integration_tests/axe_helper.py` | jedyne miejsce z konfiguracją axe: tagi, wstrzyknięcie, formatowanie raportu |
| `src/integration_tests/test_wcag_bramka_axe.py` | bramka: trzy strony, próg zero, sanity |
| `src/bpp/templates/browse/{autor,jednostka,zrodlo,tytul_raportu}.html` | etykiety pól `suggested-title` |
| `src/bpp/tests/test_wcag/test_etykiety_pol.py` | semantyczne testy dostępnej nazwy |
| `src/bpp/static/scss/*.scss` | podmiana dwóch szarości |
| `src/bpp/static/scss/app-green.scss` | punktowy override zieleni breadcrumbs |

---

### Task 1: axe-core dostępny lokalnie i w obrazie CI

Bez tego wszystko dalej jest bezużyteczne: obraz `test-runner`, w którym CI
uruchamia testy, **nie zawiera `node_modules`** (stage `test-assets-builder`
kompiluje assety osobno, a do finalnego obrazu trafiają „tylko gotowe pliki
z /src/src — bez Node, Yarn, Grunta i node_modules"). Wstrzykiwanie prosto
z `node_modules` przeszłoby lokalnie i padło na CI.

Rozwiązanie kopiuje wzorzec, który repo już stosuje dla Rollbara
(`Gruntfile.js`, zadanie `shell:copyRollbar`): grunt przenosi plik z
`node_modules` do katalogu statycznego pod `src/`, a ten katalog wchodzi do
obrazu razem z resztą źródeł.

**Files:**
- Modify: `package.json`, `yarn.lock` (przez `yarn add`)
- Modify: `Gruntfile.js` (zadanie `copyAxe` + wpis w `build`)
- Modify: `.gitignore`
- Create: `src/integration_tests/axe_helper.py`

**Interfaces:**
- Consumes: nic
- Produces: `axe_helper.skanuj(page) -> dict` — zwraca surowy wynik
  `axe.run()` (klucze `violations`, `passes`, `incomplete`, `inapplicable`);
  `axe_helper.opisz_naruszenia(wynik) -> str` — czytelny raport;
  `axe_helper.SCIEZKA_AXE: pathlib.Path`.

- [ ] **Step 1: Dodaj axe-core jako devDependency**

```bash
cd /Volumes/SSD/Programowanie/bpp-wcag-faza2
yarn add -D axe-core
```

Sprawdź, że `package.json` ma teraz `axe-core` w `devDependencies`, a
`yarn.lock` się zmienił.

- [ ] **Step 2: Dodaj zadanie kopiujące do Gruntfile**

W `Gruntfile.js`, w sekcji `shell:`, tuż po zadaniu `copyRollbar` (ok. linii
293) dopisz:

```js
            copyAxe: {
                // axe-core dla bramki dostepnosci. Kopiujemy do statykow tym
                // samym wzorcem co Rollbara, bo obraz CI `test-runner` NIE ma
                // node_modules — wstrzykiwanie prosto stamtad dziala lokalnie
                // i pada na CI.
                command: 'mkdir -p src/bpp/static/axe && ' +
                         'cp node_modules/axe-core/axe.min.js ' +
                         'src/bpp/static/axe/axe.min.js'
            },
```

- [ ] **Step 3: Wpisz zadanie do listy `build`**

W `grunt.registerTask('build', [...])` dopisz `'shell:copyAxe'` bezpośrednio
po `'shell:copyRollbar'`, a **przed** `'shell:collectstatic'` — inaczej plik
nie zdąży trafić do staticroot.

- [ ] **Step 4: Zignoruj katalog artefaktu**

W `.gitignore`, tuż pod wpisem `src/bpp/static/rollbar/` (ok. linii 227):

```
# axe-core kopiowany z node_modules przez grunt (build artifact, nie commitować)
src/bpp/static/axe/
```

- [ ] **Step 5: Zbuduj i sprawdź, że plik jest**

```bash
make assets
ls -la src/bpp/static/axe/axe.min.js
```

Oczekiwane: plik istnieje, ok. 580 KB.

- [ ] **Step 6: Napisz helper**

Utwórz `src/integration_tests/axe_helper.py`:

```python
"""Wspólna konfiguracja axe-core dla bramki dostępności (WCAG faza 3).

Jedno miejsce z tagami i wstrzykiwaniem, żeby dało się je zmienić raz,
a nie w trzech testach — i żeby przegląd kodu widział każdą zmianę
konfiguracji bramki w jednym pliku.

`axe.min.js` bierzemy ze statyków, nie z `node_modules`: obraz CI
`test-runner` nie zawiera zależności Node, więc ścieżka przez
`node_modules` działa lokalnie i pada na CI. Plik kopiuje tam zadanie
`shell:copyAxe` z `Gruntfile.js`.
"""

import json
from pathlib import Path

SCIEZKA_AXE = (
    Path(__file__).resolve().parents[1]
    / "bpp"
    / "static"
    / "axe"
    / "axe.min.js"
)

# Zakres audytu: WCAG 2.2, poziomy A i AA. `wcag22a` zostaje celowo, mimo
# że dziś nie niesie regul — jako zabezpieczenie na wypadek dodania ich
# w przyszlych wersjach axe (ustalenie ze specyfikacji 2026-08-05).
TAGI = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22a", "wcag22aa"]


def skanuj(page):
    """Wstrzykuje axe i zwraca surowy wynik `axe.run()`."""
    if not SCIEZKA_AXE.exists():
        raise AssertionError(
            f"Brak {SCIEZKA_AXE}. Uruchom `make assets` — plik kopiuje "
            "zadanie shell:copyAxe z Gruntfile.js."
        )
    page.add_script_tag(path=str(SCIEZKA_AXE))
    return page.evaluate(
        "async () => await axe.run(document, {runOnly: {type: 'tag', "
        "values: " + json.dumps(TAGI) + "}})"
    )


def opisz_naruszenia(wynik):
    """Czytelny raport: reguła, waga, selektor i fragment HTML-a.

    Diagnoza ma nie wymagać powtarzania pomiaru — komunikat z CI musi
    wystarczyć, żeby wiedzieć, co poprawić.
    """
    linie = []
    for v in wynik["violations"]:
        linie.append(f"\n{v['id']} [{v['impact']}] — {len(v['nodes'])} elem.")
        for n in v["nodes"]:
            selektor = n["target"][0] if n["target"] else "?"
            html = " ".join(n["html"].split())[:120]
            linie.append(f"  sel:  {selektor}")
            linie.append(f"  html: {html}")
    return "\n".join(linie)


def opisz_niejednoznaczne(wynik):
    """Raport `incomplete` — reguł, których axe nie umiał rozstrzygnąć.

    Nie blokują bramki, ale muszą być widoczne: naruszenie potrafi
    zmigrować z `violations` do `incomplete` (np. po zmianie tła na
    półprzezroczyste) i cicho zniknąć z pola widzenia.
    """
    if not wynik.get("incomplete"):
        return "incomplete: brak"
    czesci = [
        f"{v['id']}({len(v['nodes'])})" for v in wynik["incomplete"]
    ]
    return "incomplete: " + ", ".join(czesci)
```

- [ ] **Step 7: Napisz test, że helper w ogóle działa**

Utwórz `src/integration_tests/test_wcag_bramka_axe.py`:

```python
"""Bramka dostępności: axe-core na publicznych stronach BPP (WCAG faza 3).

Próg to ZERO naruszeń, bez pliku baseline — przy czternastu naprawianych
naruszeniach zapadka byłaby droższa niż sama naprawa.

WYMAGANIE WSTĘPNE: `make assets`. Bez niego nie ma `axe.min.js` w statykach
ani zbudowanego CSS, więc pomiar kontrastu byłby bez sensu.
"""

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Autor
from integration_tests import axe_helper


@pytest.mark.django_db(transaction=True)
def test_axe_daje_sie_uruchomic(channels_live_server, page: Page, transactional_db):
    """Sanity dla samego harnessu: axe się wstrzykuje i coś ocenia.

    Osobny test od bramki, bo odpowiada na inne pytanie. Bramka mówi „brak
    naruszeń"; ten mówi „pomiar w ogóle się odbył". Bez niego zielona bramka
    mogłaby znaczyć, że axe się nie załadował.
    """
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    page.goto(
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor', args=[autor.slug])}",
        wait_until="networkidle",
    )

    wynik = axe_helper.skanuj(page)

    ocenione = len(wynik["violations"]) + len(wynik["passes"])
    assert ocenione > 10, (
        f"axe ocenił tylko {ocenione} reguł — wygląda, jakby się nie "
        "uruchomił albo trafił na pustą stronę"
    )
```

- [ ] **Step 8: Uruchom test**

```bash
BPP_SKIP_ASSETS_BUILD=1 uv run pytest \
  src/integration_tests/test_wcag_bramka_axe.py -q
```

Oczekiwane: PASS.

- [ ] **Step 9: Sprawdź, że plik jest też w obrazie CI**

To jedyny sposób, żeby wiedzieć, że Task 1 zrobił, co obiecał — lokalna
suita niczego tu nie dowodzi, bo lokalnie `node_modules` istnieje.

```bash
docker build -f docker/bpp_base/Dockerfile --target test-runner -t bpp-test-runner-sprawdzenie .
docker run --rm bpp-test-runner-sprawdzenie ls -la /src/src/bpp/static/axe/axe.min.js
```

Oczekiwane: plik istnieje w obrazie. Jeśli nie — `shell:copyAxe` biegnie po
`collectstatic` albo w złym stage'u; popraw kolejność w `build`.

- [ ] **Step 10: Commit**

```bash
git add package.json yarn.lock Gruntfile.js .gitignore \
  src/integration_tests/axe_helper.py \
  src/integration_tests/test_wcag_bramka_axe.py
git commit -m "$(cat <<'MSG'
feat(wcag): axe-core dostepny lokalnie i w obrazie CI

Obraz `test-runner`, w ktorym CI uruchamia testy, NIE zawiera
node_modules — assety kompiluje osobny stage, a do finalnego obrazu trafiaja
tylko gotowe pliki. Wstrzykiwanie axe prosto z node_modules przeszloby
lokalnie i padlo na CI.

Grunt kopiuje wiec axe.min.js do statykow tym samym wzorcem, ktorym repo
kopiuje juz Rollbara (shell:copyRollbar). Katalog jest gitignorowany jako
artefakt builda.

Helper trzyma tagi i wstrzykiwanie w jednym miejscu, zeby zmiana
konfiguracji bramki byla widoczna w przegladzie kodu jako jeden plik.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 2: Etykiety dla widocznych pól `suggested-title`

axe zgłosił `label` (critical) na stronie autora. Ten sam nieopisany
`input[type="text"][name="suggested-title"]` jest w czterech szablonach —
bramka zobaczy tylko jeden, więc pozostałe trzy dostają test szablonowy.

Warianty `type="hidden"` tego samego pola (m.in. `uczelnia.html:187`) są
poprawne: ukryte pola nie wymagają etykiety. Nie ruszaj ich.

**Files:**
- Modify: `src/bpp/templates/browse/autor.html:349`
- Modify: `src/bpp/templates/browse/jednostka.html:524`
- Modify: `src/bpp/templates/browse/zrodlo.html:118`
- Modify: `src/bpp/templates/browse/tytul_raportu.html:5`
- Create: `src/bpp/tests/test_wcag/test_etykiety_pol.py`

**Interfaces:**
- Consumes: nic
- Produces: nic

- [ ] **Step 1: Ustal, czy `tytul_raportu.html` żyje**

```bash
grep -rn "tytul_raportu" src/ --include="*.py" --include="*.html" | grep -v "^src/bpp/templates/browse/tytul_raportu.html"
```

Jeśli wynik jest pusty, szablon nie jest nigdzie renderowany — wtedy zamiast
go poprawiać, **skasuj go** (`git rm`) i pomiń dalsze kroki jego dotyczące.
Faza 1 usunęła już jeden taki martwy szablon. Zapisz decyzję w komunikacie
commita.

- [ ] **Step 2: Napisz failujący test semantyczny**

Test sprawdza **dostępną nazwę** na wyrenderowanym DOM, nie obecność
znacznika w źródle. `<label>` z błędnym `for` istnieje i niczego nie wiąże —
to dokładnie ten rodzaj pozornej zieleni, który faza 2 złapała trzy razy.

Utwórz `src/bpp/tests/test_wcag/test_etykiety_pol.py`:

```python
"""WCAG 1.3.1/4.1.2 — pola formularzy mają dostępne nazwy.

axe zgłosił `label` (critical) dla widocznego pola „Tytuł raportu" na
stronie autora. To samo pole jest w kolejnych szablonach, których bramka
axe nie obejmuje — stąd te testy.

Sprawdzamy POWIĄZANIE, nie obecność znacznika: `<label for="zle-id">`
istnieje i nie wiąże niczego, a `aria-label` na ukrytym polu byłby
bezużyteczny.
"""

import re

import pytest
from django.template.loader import render_to_string

WZORZEC_POLA = re.compile(
    r'<input[^>]*name="suggested-title"[^>]*>', re.IGNORECASE
)


def _widoczne_pola(html):
    """Pola `suggested-title`, które NIE są ukryte."""
    return [
        znacznik
        for znacznik in WZORZEC_POLA.findall(html)
        if 'type="hidden"' not in znacznik.lower()
    ]


@pytest.mark.parametrize(
    "szablon",
    [
        "browse/jednostka.html",
        "browse/zrodlo.html",
    ],
)
@pytest.mark.django_db
def test_widoczne_pole_tytulu_ma_dostepna_nazwe(szablon):
    html = render_to_string(szablon, {})

    pola = _widoczne_pola(html)
    assert pola, f"{szablon}: nie znaleziono widocznego pola suggested-title"

    for pole in pola:
        ma_aria = "aria-label=" in pole.lower()
        ma_id = 'id="' in pole.lower()
        assert ma_aria or ma_id, (
            f"{szablon}: pole bez dostępnej nazwy — {pole}"
        )
        if ma_id and not ma_aria:
            identyfikator = re.search(r'id="([^"]+)"', pole).group(1)
            assert f'for="{identyfikator}"' in html, (
                f"{szablon}: jest id={identyfikator}, ale żaden <label> "
                "go nie wskazuje — etykieta nie wiąże się z polem"
            )
```

- [ ] **Step 3: Uruchom test i potwierdź czerwień**

```bash
BPP_SKIP_ASSETS_BUILD=1 uv run pytest \
  src/bpp/tests/test_wcag/test_etykiety_pol.py -q
```

Oczekiwane: FAIL — „pole bez dostępnej nazwy".

Jeśli któryś szablon nie da się wyrenderować z pustym kontekstem, dołóż do
`render_to_string` minimalny kontekst, jakiego wymaga (sprawdź `{{ }}`
w szablonie) — ale NIE osłabiaj asercji.

- [ ] **Step 4: Dodaj etykiety**

W każdym z szablonów zamień widoczne pole na wariant z powiązaną etykietą.
Wzorzec dla `browse/autor.html` (pole ok. linii 349, klasa
`autor-page__title-input`):

```django
{# WCAG 1.3.1: pole musi miec dostepna nazwe. Tekst obok jest podpowiedzia, #}
{# nie etykieta — bez `for`/`id` czytnik ekranu oglasza samo "edit text". #}
<label for="id_suggested_title" class="show-for-sr">Tytuł wyszukiwania</label>
<input type="text"
       id="id_suggested_title"
       name="suggested-title"
       value="{{ autor }}"
       class="autor-page__title-input">
```

`show-for-sr` to klasa Foundation ukrywająca wizualnie, ale zostawiająca
treść czytnikom — jest już używana w projekcie, więc nic nie dokładasz.

W `jednostka.html` i `zrodlo.html` użyj identyfikatorów unikalnych w obrębie
strony (`id_suggested_title` wystarczy, bo pole występuje raz na widok) oraz
wartości `value` takiej, jaka jest tam dzisiaj — nie zmieniaj jej.

- [ ] **Step 5: Uruchom test i potwierdź zieleń**

```bash
BPP_SKIP_ASSETS_BUILD=1 uv run pytest \
  src/bpp/tests/test_wcag/test_etykiety_pol.py -q
```

Oczekiwane: PASS.

- [ ] **Step 6: Sprawdź mutacją, że test ma zęby**

Zepsuj powiązanie w `jednostka.html` — zmień `for="id_suggested_title"` na
`for="nie-ma-takiego-id"` i uruchom test ponownie.

Oczekiwane: FAIL z komunikatem „żaden `<label>` go nie wskazuje". Przywróć
poprawną wartość.

- [ ] **Step 7: Commit**

```bash
git add src/bpp/templates/browse/ src/bpp/tests/test_wcag/test_etykiety_pol.py
git commit -m "$(cat <<'MSG'
fix(wcag): dostepne nazwy dla widocznych pol "suggested-title" (1.3.1)

axe zglosil `label` o wadze critical dla pola "Tytul raportu" na stronie
autora. To samo nieopisane pole jest w kolejnych szablonach, ktorych bramka
axe nie obejmuje — stad osobne testy szablonowe.

Testy sprawdzaja POWIAZANIE, nie obecnosc znacznika: `<label>` z blednym
`for` istnieje i niczego nie wiaze. Zweryfikowane mutacja — podmiana `for`
na nieistniejace id zapala test.

Warianty `type="hidden"` tego samego pola zostaja bez zmian; ukryte pola nie
wymagaja etykiety i axe slusznie je pomija.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 3: Przyciemnienie dwóch szarości

`#7f8c8d` ma 57 wystąpień, `#6c757d` — 33. Zmieniamy **wyłącznie
deklaracje `color:`**; wystąpienia jako `background`, `background-color`
i `border` zostają, bo tam próg kontrastu tekstu nie obowiązuje, a zmiana
byłaby czysto kosmetyczna i poza zakresem audytu.

**Files:**
- Modify: wszystkie `src/bpp/static/scss/*.scss` zawierające te kolory
  w deklaracji `color:`

**Interfaces:**
- Consumes: nic
- Produces: nic

- [ ] **Step 1: Zapisz stan przed zmianą**

```bash
grep -rn "color: *#7f8c8d" src/bpp/static/scss/*.scss | wc -l
grep -rn "color: *#6c757d" src/bpp/static/scss/*.scss | wc -l
```

Zapisz obie liczby — po podmianie muszą zejść do zera, a suma zmienionych
linii ma się zgadzać.

- [ ] **Step 2: Zrób zrzuty „przed"**

Uruchom dev stack i zrób zrzuty strony autora oraz strony uczelni:

```bash
BPP_SKIP_ASSETS_BUILD=1 uv run pytest \
  src/integration_tests/test_wcag_skrot_i_graf.py -q -k "waskim or szerokim"
```

(Test sam w sobie nie robi zrzutów — użyj go tylko jako potwierdzenia, że
harness działa. Zrzuty zrób ad hoc, `page.screenshot`, i odłóż poza repo.)

- [ ] **Step 3: Podmień kolory**

```bash
cd /Volumes/SSD/Programowanie/bpp-wcag-faza2
grep -rl "color: *#7f8c8d" src/bpp/static/scss/*.scss | \
  xargs sed -i '' 's/color: *#7f8c8d/color: #68706f/g'
grep -rl "color: *#6c757d" src/bpp/static/scss/*.scss | \
  xargs sed -i '' 's/color: *#6c757d/color: #636b73/g'
```

Uwaga: `sed -i ''` to składnia macOS. Na Linuksie `sed -i`.

- [ ] **Step 4: Sprawdź, że nie ruszyłeś teł ani ramek**

```bash
grep -rn "7f8c8d\|6c757d" src/bpp/static/scss/*.scss
```

Oczekiwane: zostają wyłącznie `background`, `background-color`, `border`
i `border-left`. Żadnej deklaracji `color:`.

- [ ] **Step 5: Przebuduj i zmierz**

```bash
make assets
BPP_SKIP_ASSETS_BUILD=1 uv run pytest \
  src/integration_tests/test_wcag_bramka_axe.py -q
```

Test z Taska 1 ma nadal przechodzić.

- [ ] **Step 6: Zrzuty „po" i porównanie**

Zrób te same dwa zrzuty i porównaj z „przed". Oczekiwane: różnica ledwo
dostrzegalna, żaden element nie znika i nie zmienia układu. Jeśli gdzieś
tekst zlewa się z tłem — to znak, że trafiłeś w deklarację na ciemnym tle;
przywróć ją punktowo i odnotuj w commicie.

- [ ] **Step 7: Commit**

```bash
git add src/bpp/static/scss/
git commit -m "$(cat <<'MSG'
fix(wcag): przyciemnienie dwoch szarosci do progu 4.5:1 (1.4.3)

axe zglosil `color-contrast` na trzech publicznych stronach. Zrodlem sa dwa
kolory: #7f8c8d (3.48 na bialym) i #6c757d (4.45 na #f8f9fa). Oba schodza
ponizej progu 4.5 wymaganego dla tekstu.

Nowe wartosci policzone, nie oszacowane, i z zapasem ponad prog, zeby drobna
zmiana tla nie wywrocila bramki:
  #7f8c8d -> #68706f  (5.08 na bialym, 4.82 na #f8f9fa)
  #6c757d -> #636b73  (5.41 na bialym, 5.13 na #f8f9fa)

Zmienione WYLACZNIE deklaracje `color:`. Wystapienia jako tlo i ramka
zostaja — tam prog kontrastu tekstu nie obowiazuje, a zmiana byla by czysto
kosmetyczna i poza zakresem audytu.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 4: Zieleń breadcrumbs w motywie `app-green`

Kolor bierze się z palety Foundation: `_settings_green.scss:76` ma
`primary: green`, czyli `#008000`. **Nie zmieniaj palety** — przemalowałaby
cały motyw (przyciski, linki, akcenty). Potrzebny jest override punktowy.

`app-green` jest motywem **produktowym i domyślnym**, nie klienckim, więc ta
zmiana nie wymaga rozmowy z uczelnią. Ustalenie z audytu 08-05 o brandingu
dotyczy wyłącznie `vizja`, `mwsl` i `uafm`.

**Files:**
- Modify: `src/bpp/static/scss/app-green.scss`

**Interfaces:**
- Consumes: nic
- Produces: nic

- [ ] **Step 1: Potwierdź stan wyjściowy**

```bash
grep -o "\.breadcrumbs a{color:[^}]*}" src/bpp/static/scss/app-green.css
```

Oczekiwane: `.breadcrumbs a{color:green}`.

- [ ] **Step 2: Dodaj override w motywie**

W `src/bpp/static/scss/app-green.scss`, w sekcji „Theme-specific overrides"
(ok. linii 26), dopisz:

```scss
// WCAG 1.4.3: `primary: green` z palety Foundation (#008000) daje na tle
// paska breadcrumbs (#efefef) kontrast 4.47 — ponizej progu 4.5 dla tekstu.
// Override jest punktowy CELOWO: zmiana palety przemalowala by caly motyw
// (przyciski, linki, akcenty), a chodzi o jeden element.
#breadcrumbs-wrapper .breadcrumbs a {
  color: #006e00; // 5.65 na #efefef
}
```

- [ ] **Step 3: Przebuduj i sprawdź skompilowany CSS**

```bash
make assets
grep -o "breadcrumbs-wrapper .breadcrumbs a{color:#006e00}" \
  src/bpp/static/scss/app-green.css
```

Oczekiwane: reguła jest obecna.

- [ ] **Step 4: Sprawdź, że nie ruszyłeś reszty motywu**

```bash
grep -c "color:green" src/bpp/static/scss/app-green.css
```

Oczekiwane: liczba niezerowa (inne elementy nadal używają zieleni z palety) —
zmiana miała być punktowa, nie globalna.

- [ ] **Step 5: Commit**

```bash
git add src/bpp/static/scss/app-green.scss
git commit -m "$(cat <<'MSG'
fix(wcag): kontrast linkow breadcrumbs w motywie app-green (1.4.3)

`primary: green` z palety Foundation (_settings_green.scss:76) to #008000,
co na tle paska breadcrumbs (#efefef) daje 4.47 — ponizej progu 4.5 dla
tekstu. Brakowalo 0,03.

Override jest punktowy CELOWO. Zmiana palety naprawila by kontrast, ale
przemalowala przy okazji caly motyw: przyciski, linki, akcenty. Chodzi
o jeden element, wiec zmieniamy jeden element.

app-green jest motywem produktowym i domyslnym, wiec to decyzja zespolu.
Ustalenie z audytu 08-05 o tym, ze poprawa kontrastu zmienia branding
klienta, dotyczy motywow vizja, mwsl i uafm — nie tego.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 5: Bramka na zero

Teraz, gdy naruszenia są naprawione, próg zero jest osiągalny.

**Files:**
- Modify: `src/integration_tests/test_wcag_bramka_axe.py`

**Interfaces:**
- Consumes: `axe_helper.skanuj`, `axe_helper.opisz_naruszenia`,
  `axe_helper.opisz_niejednoznaczne`
- Produces: nic

- [ ] **Step 1: Dopisz bramkę dla trzech stron**

Do `src/integration_tests/test_wcag_bramka_axe.py` dopisz:

```python
from bpp.models import Uczelnia
from powiazania_autorow.models import AuthorConnection


def _sprawdz_strone(page, url, sentinel, nazwa):
    """Otwiera stronę, sprawdza że to właściwa strona, skanuje, asertuje zero.

    Sentinel jest po to, żeby zielona bramka nie mogła znaczyć „trafiliśmy
    na 404". Wspólny `base.html` dziedziczy nawet strona błędu, więc sama
    obecność jakichkolwiek elementów niczego nie dowodzi.
    """
    odpowiedz = page.goto(url, wait_until="networkidle")

    assert odpowiedz is not None and odpowiedz.status == 200, (
        f"{nazwa}: status {odpowiedz.status if odpowiedz else '?'}, "
        "bramka mierzyłaby nie tę stronę"
    )
    assert page.locator(sentinel).count() > 0, (
        f"{nazwa}: brak sentinela {sentinel} — to nie jest ta strona"
    )

    wynik = axe_helper.skanuj(page)

    print(f"\n[{nazwa}] {axe_helper.opisz_niejednoznaczne(wynik)}")

    assert wynik["violations"] == [], (
        f"{nazwa}: axe znalazł naruszenia WCAG 2.2 AA"
        + axe_helper.opisz_naruszenia(wynik)
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_strona_autora(channels_live_server, page: Page, transactional_db):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor', args=[autor.slug])}",
        ".autor-page__title-input",
        "strona autora",
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_strona_uczelni(channels_live_server, page: Page, transactional_db):
    uczelnia = baker.make(Uczelnia, nazwa="Uczelnia Testowa", skrot="UT")
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_uczelnia', args=[uczelnia.slug])}",
        ".uczelnia__tile-description",
        "strona uczelni",
    )


@pytest.mark.django_db(transaction=True)
def test_bramka_graf_powiazan(channels_live_server, page: Page, transactional_db):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    wsp = baker.make(Autor, imiona="Anna", nazwisko="Nowak", pokazuj=True)
    baker.make(
        AuthorConnection,
        primary_author=autor,
        secondary_author=wsp,
        shared_publications_count=3,
    )
    _sprawdz_strone(
        page,
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor_powiazania', args=[autor.pk])}",
        "#graf-nawigacja",
        "graf powiązań",
    )
```

- [ ] **Step 2: Wyłącz automatyczny rerun dla bramki**

Fixture `page` dokłada testom jeden automatyczny powtórny przebieg
(`src/fixtures/conftest.py`). Dla bramki to trucizna: wynik „czerwony, potem
zielony" zostałby zaliczony, a właśnie chwiejność chcemy widzieć.

Na górze `src/integration_tests/test_wcag_bramka_axe.py`, pod importami,
dopisz:

```python
# Bramka NIE MOZE korzystac z automatycznego rerunu, ktory fixture `page`
# dokłada testom przegladarkowym. Naruszenie dostepnosci nie znika przy
# drugim podejsciu — jesli raz zapalilo, to jest realne. Rerun zamienilby
# je w migotanie i przepuscil.
pytestmark = pytest.mark.flaky(reruns=0)
```

Sprawdź w `src/fixtures/conftest.py`, czy jawny marker faktycznie ma
pierwszeństwo nad automatycznym (komentarz w okolicy linii 74 mówi, że
jawny `@pytest.mark.flaky(reruns=N)` nie jest nadpisywany). Jeśli
mechanizm działa inaczej, dostosuj — cel jest jeden: zero powtórek.

- [ ] **Step 3: Uruchom bramkę**

```bash
make assets
BPP_SKIP_ASSETS_BUILD=1 uv run pytest \
  src/integration_tests/test_wcag_bramka_axe.py -q -s
```

Oczekiwane: 4 PASS (sanity + trzy strony). Jeśli któraś pada — przeczytaj
raport z komunikatu, popraw i wróć tu. Nie osłabiaj asercji.

- [ ] **Step 4: Mutacja rodziny `label`**

W `src/bpp/templates/browse/autor.html` usuń `<label>` dodany w Tasku 2
i uruchom bramkę.

Oczekiwane: FAIL na stronie autora, w raporcie reguła `label`. Przywróć.

- [ ] **Step 5: Mutacja rodziny `color-contrast`**

W `src/bpp/static/scss/app-green.scss` zmień override na `color: #00a000`
(kontrast poniżej progu), `make assets`, uruchom bramkę.

Oczekiwane: FAIL, w raporcie `color-contrast` i selektor breadcrumbs.
Przywróć `#006e00` i przebuduj.

Obie mutacje są konieczne: jedna dowodzi połowy. Bramka egzekwuje dwie
rodziny reguł i obie muszą być sprawdzone.

- [ ] **Step 6: Commit**

```bash
git add src/integration_tests/test_wcag_bramka_axe.py
git commit -m "$(cat <<'MSG'
feat(wcag): bramka axe-core na trzech publicznych stronach, prog zero

Bramka sprawdza WCAG 2.2 A i AA na stronie autora, stronie uczelni
i w grafie powiazan. Prog to zero narusze, bez pliku baseline — przy
czternastu naprawionych rzeczach zapadka bylaby drozsza niz naprawa.

Zielona bramka NIE MOZE znaczyc "nie zmierzylismy". Stad trzy zabezpieczenia:
osobny test sanity (axe sie zaladowal i cos ocenil), asercja status 200
i sentinel wlasciwego widoku per strona. Wspolny base.html dziedziczy nawet
strona bledu, wiec sama obecnosc elementow niczego nie dowodzi.

Wyniki `incomplete` nie blokuja, ale sa wypisywane — naruszenie potrafi tam
zmigrowac (np. po zmianie tla na polprzezroczyste) i cicho zniknac.

Wartosc bramki sprawdzona mutacja OBU egzekwowanych rodzin regul: usuniecie
etykiety zapala `label`, rozjasnienie zieleni zapala `color-contrast`.
Mutacja tylko jednej dowodzila by polowy.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 6: Pomiar sześciu motywów

Rozpoznanie, nie naprawa. Wynik idzie do dokumentu stanu prac; naprawy
w motywach klienckich (`app-vizja`, `app-mwsl`, `app-uafm`) **nie wchodzą**
do tej fazy.

Uwaga na kontrakt: motyw bierze się z `request._uczelnia`, czyli z mapowania
host → `Site` → `Uczelnia`, a nie z oglądanego obiektu. Sześć rekordów
`Uczelnia` na jednym hoście zmierzyłoby sześć razy to samo.

**Files:**
- Create: tymczasowy skrypt pomiarowy (NIE commitować)
- Modify: `docs/superpowers/specs/2026-08-13-wcag-stan-i-pozostale-prace.md`

**Interfaces:**
- Consumes: `axe_helper.skanuj`
- Produces: nic

- [ ] **Step 1: Napisz tymczasowy pomiar**

Utwórz `src/integration_tests/test_tmp_motywy.py` (do skasowania po
pomiarze):

```python
"""Tymczasowy pomiar kontrastu w szesciu motywach — NIE commitować."""

import pytest
from django.urls import reverse
from model_bakery import baker
from playwright.sync_api import Page

from bpp.models import Autor, Uczelnia
from integration_tests import axe_helper

MOTYWY = [
    "app-green",
    "app-blue",
    "app-orange",
    "app-vizja",
    "app-mwsl",
    "app-uafm",
]


@pytest.mark.parametrize("motyw", MOTYWY)
@pytest.mark.django_db(transaction=True)
def test_pomiar_motywu(channels_live_server, page: Page, transactional_db, motyw):
    uczelnia = baker.make(Uczelnia, nazwa="Testowa", skrot="T")
    uczelnia.theme_name = motyw
    uczelnia.save()
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)

    page.goto(
        f"{channels_live_server.url}"
        f"{reverse('bpp:browse_autor', args=[autor.slug])}",
        wait_until="networkidle",
    )

    arkusze = page.evaluate(
        "Array.from(document.styleSheets).map(s => s.href).filter(Boolean)"
        ".map(h => h.split('/').pop())"
    )
    assert any(motyw in a for a in arkusze), (
        f"{motyw}: zaladowano {arkusze}, nie ten motyw — pomiar bylby fikcja"
    )

    wynik = axe_helper.skanuj(page)
    kontrast = [v for v in wynik["violations"] if v["id"] == "color-contrast"]
    ile = sum(len(v["nodes"]) for v in kontrast)
    print(f"\n### {motyw}: {ile} naruszen kontrastu")
    print(axe_helper.opisz_naruszenia(wynik))
```

- [ ] **Step 2: Uruchom pomiar**

```bash
make assets
BPP_SKIP_ASSETS_BUILD=1 uv run pytest \
  src/integration_tests/test_tmp_motywy.py -q -s -p no:randomly 2>&1 | grep -E "^###|sel:|passed|failed"
```

Jeśli asercja o arkuszu pada — kontrakt Site/host jest inny, niż zakładamy.
Wtedy ustal, jak `Uczelnia` wiąże się z `Site` w tym harnessie, i popraw
seed. **Nie usuwaj asercji** — bez niej pomiar byłby fikcją.

- [ ] **Step 3: Zapisz wyniki do dokumentu stanu prac**

W `docs/superpowers/specs/2026-08-13-wcag-stan-i-pozostale-prace.md`, w
sekcji o pozostałych pracach, dopisz podsekcję „Kontrast w motywach
(pomiar 2026-08-XX)" z tabelą: motyw, liczba naruszeń kontrastu, wniosek.
Dla motywów klienckich zaznacz, że naprawa wymaga decyzji uczelni.

- [ ] **Step 4: Skasuj tymczasowy plik**

```bash
rm src/integration_tests/test_tmp_motywy.py
git status --short
```

Oczekiwane: w statusie tylko zmieniony dokument.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-08-13-wcag-stan-i-pozostale-prace.md
git commit -m "$(cat <<'MSG'
docs(wcag): pomiar kontrastu w szesciu motywach

Rozpoznanie, nie naprawa. Bramka biegnie w motywie domyslnym `app-green`,
wiec o pozostalych pieciu nie wiedzielismy nic — a kontrast zalezy od
motywu.

Pomiar wymagal asercji, ze faktycznie zaladowal sie zadany arkusz: motyw
bierze sie z mapowania host -> Site -> Uczelnia, a nie z ogladanego obiektu,
wiec szesc rekordow Uczelnia na jednym hoscie zmierzyloby szesc razy to
samo.

Naprawy w motywach klienckich (vizja, mwsl, uafm) NIE wchodza do tej fazy —
audyt 08-05 nie oddaje takich decyzji zespolowi.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
```

---

### Task 7: Weryfikacja końcowa i newsfragment

**Files:**
- Create: `src/bpp/newsfragments/wcag-bramka-axe.feature.rst`

- [ ] **Step 1: Newsfragment**

```bash
cat > src/bpp/newsfragments/wcag-bramka-axe.feature.rst <<'EOF'
Publiczne strony BPP są teraz automatycznie sprawdzane pod kątem zgodności
z WCAG 2.2 AA przy każdym przebiegu testów. Przy okazji poprawiono kontrast
tekstu pomocniczego i opisów kafelków oraz dodano brakujące etykiety pól
formularza wyszukiwania.
EOF
```

- [ ] **Step 2: Pełna suita na świeżych kontenerach**

```bash
make assets
uv run pytest -n 4 -m "not playwright" -q
uv run pytest -n 4 -m "playwright" -q
make js-tests
```

Oczekiwane: wszystko zielone. **Nie** używaj `PYTEST_TESTCONTAINERS_REUSE=1`
— współdzielona baza daje fałszywe błędy w testach zależnych od stanu.

- [ ] **Step 3: Lint tylko zmienionych plików**

```bash
git diff --name-only origin/dev..HEAD | grep '\.py$' | \
  tr '\n' '\0' | xargs -0 uv run ruff check
git diff --name-only origin/dev..HEAD | grep '\.py$' | \
  tr '\n' '\0' | xargs -0 uv run ruff format --check
```

- [ ] **Step 4: Commit i PR**

```bash
git add src/bpp/newsfragments/wcag-bramka-axe.feature.rst
git commit -m "$(cat <<'MSG'
docs(wcag): newsfragment dla fazy 3

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
)"
git push -u origin fix-wcag-faza3-bramka-axe
```

PR z bazą `fix-wcag-2140-2570`, dopóki #763 nie jest zmergowany; po jego
scaleniu przepiąć na `dev`.
