# Specyfikacja: prawdziwa odmiana instytucji (silnik SGJP) + odchudzenie Rzeczownika do lematu

**Data:** 2026-07-03 (rewizja 2026-07-04)
**Gałąź:** `feat/odmiana-rodzaj-instytucji`
**Status:** design — do przeglądu przed planem wdrożenia
**Powiązane:** `docs/superpowers/specs/2026-07-02-konsolidacja-wydzial-jednostka-design.md`

## Cel

Zastąpić ręcznie utrzymywaną, zakodowaną-na-sztywno tabelę odmiany
(`jezyk_polski.deklinacja`) **prawdziwą odmianą** przez przypadki (silnik SGJP,
`django-polish-inflection`), a model `Rzeczownik` **zachować jako per-install
źródło nazwy**, ale odchudzić do **jednego pola = mianownik l.poj. (lemat)**.
Wszystkie przypadki i liczbę mnogą generuje silnik z tego lematu.

Dzięki temu instalacja, która przemianowała `JEDNOSTKA` → „Dział" albo
`WYDZIAL` → „Klinika", **dalej ma poprawne etykiety** w całym UI, we wszystkich
przypadkach — mimo że w bazie trzymamy tylko mianownik.

## Zasada działania

```
Rzeczownik(uid="JEDNOSTKA").mianownik == "Dział"          # per-install, admin
{% odmien nazwa_jednostki "dopelniacz" liczba="mnoga" %}  # silnik → "Działów"
{% odmiana_liczebnikowa nazwa_jednostki 5 %}              # silnik → "Działów"
```

- **Źródło lematu:** wiersz `Rzeczownik` (edytowalny w adminie). Domyślnie
  zasiane: `UCZELNIA`→„uczelnia", `WYDZIAL`→„wydział", `JEDNOSTKA`→„jednostka".
- **Odmiana:** zawsze silnik — żadnych form trzymanych ręcznie.
- **Liczba:** parametr wywołania (`liczba="mnoga"`), nie osobny wiersz `_PL`.

## Zależności

Dodać do `pyproject.toml`:

```
django-polish-inflection>=0.1,<0.2
```

Ciągnie tranzytywnie: `polish-inflection>=0.7.0` (silnik dane-only, SGJP,
marisa-trie, mmap — bez kompilatora/Morfeusza/SWIG) oraz
`polish-inflection-data` (~50 MB indeksów SGJP, wheel binarny).

Do `INSTALLED_APPS` dodać `"django_polish_inflection"`.
W `settings/base.py`: `POLISH_INFLECTION_STRICT = False` (prod: słowo spoza SGJP
→ passthrough; strona się nie wywala). W konfiguracji testowej rozważyć `True`.

### Wpływ na obraz Docker

+~50 MB (dane SGJP) w warstwie zależności; wheele binarne (bez kompilacji),
import przez `mmap` (RSS ~1,5 MB). Do potwierdzenia na buildzie test-runnera.

---

## Sekcja 1 — Model `Rzeczownik` (odchudzenie)

`src/bpp/models/rzeczownik.py` — zostaje, ale tylko lemat:

```python
class Rzeczownik(models.Model):
    uid = models.CharField(max_length=20, primary_key=True)
    m = models.CharField(
        max_length=200,
        verbose_name="mianownik (lemat)",
        help_text="Mianownik liczby pojedynczej, np. „wydział" lub „dział". "
                  "Pozostałe przypadki i liczbę mnogą generuje automatycznie "
                  "polish-inflection.",
    )

    @property
    def mianownik(self):   # czytelny alias przy odczycie
        return self.m

    class Meta:
        verbose_name_plural = "rzeczowniki"

    def __str__(self):
        return f"Rzeczownik {self.uid} = {self.m}"
```

- **Kolumna `m` zostaje** (już znaczy mianownik) — bez ryzykownego renejmu.
  Alias `mianownik` tylko dla czytelnych call-site'ów.
- **Znikają kolumny** `d, c, b, n, ms, w`.

### Migracja `0445_rzeczownik_tylko_mianownik`

1. `RemoveField` × 6: `d, c, b, n, ms, w`.
2. `RunPython`: skasuj wiersze `_PL` (`uid__in=["UCZELNIA_PL", "WYDZIAL_PL",
   "JEDNOSTKA_PL"]`) — plural liczy silnik z singularnego lematu.
   Reverse: no-op (z notką; dane odtwarzalne z singulara).
3. `dependencies = [("bpp", "0444…")]`.
4. Migracje `0362`/`0364` **NIE modyfikowane** (append-only) — nowa migracja
   ściąga nadmiarowe kolumny/wiersze, `m` z poprawnym lematem zostaje.
5. **Baseline** (`make baseline-update`) odświeżamy **raz, przy scalaniu**
   (reguła z CLAUDE.md — nie w równoległym feature-branchu).

### Admin (`src/bpp/admin/__init__.py`)

`RzeczownikAdmin` zostaje, uproszczony do `list_display = ("uid", "m")`,
`readonly_fields = ("uid",)` (3 kanoniczne wiersze; bez add/delete).
Rozważyć `has_add_permission=False`/`has_delete_permission=False`.

---

## Sekcja 2 — Co znika

- `src/bpp/jezyk_polski.py` — `deklinacja` (lista), `znajdz_rzeczownik`,
  `lazy_rzeczownik_title`. **Zostają** `czasownik_byc` (używa `zrodlo.py`) i
  `warianty_zapisanego_nazwiska` (dopasowywanie autorów) — to nie odmiana.
- `src/bpp/templatetags/deklinacja.py` — **cały plik** (`{% rzeczownik %}`,
  dynamiczne `{% rzeczownik_* %}`). Zastąpione stockowymi tagami
  `django-polish-inflection` + lematami z kontekstu.

---

## Sekcja 3 — Dostarczanie lematów + odmiana

### Resolver (nowy `src/bpp/nazwy.py`)

```python
DOMYSLNE_LEMATY = {
    "UCZELNIA": "uczelnia", "WYDZIAL": "wydział", "JEDNOSTKA": "jednostka",
}

def lemat(uid):
    """Lemat (mianownik) dla uid: override z Rzeczownik albo default."""
    from bpp.models import Rzeczownik
    row = Rzeczownik.objects.filter(uid=uid).first()
    return row.m if row else DOMYSLNE_LEMATY[uid]
```

(Wiersze są zawsze zasiane przez `0362`, więc `DOMYSLNE_LEMATY` to tylko siatka
bezpieczeństwa — np. świeża baza przed migracją albo ręczne skasowanie wiersza.)

### Kontekst dla szablonów

Rozszerzyć **istniejący, cache'owany** context processor `uczelnia`
(`src/bpp/context_processors/uczelnia.py`) o trzy lematy (jedno zapytanie
`filter(uid__in=[...])`, cache 1h jak reszta):

```python
"nazwa_uczelni":   lemat("UCZELNIA"),
"nazwa_wydzialu":  lemat("WYDZIAL"),
"nazwa_jednostki": lemat("JEDNOSTKA"),
```

Szablony używają **stockowych** tagów `django-polish-inflection` na tych
zmiennych — brak BPP-owego tagu.

### Menu (Python)

`src/django_bpp/menu.py` — helper leniwy (menu jest budowane przy imporcie;
`lemat()` dotyka DB → odczyt dopiero przy renderze):

```python
from django.utils.functional import lazy
from django.template.defaultfilters import capfirst
from polish_inflection import odmien_lub_wyraz, MIANOWNIK, MNOGA
from bpp.nazwy import lemat

def _tytul(uid, liczba=None):
    return capfirst(odmien_lub_wyraz(lemat(uid), MIANOWNIK, liczba))
_tytul_lazy = lazy(_tytul, str)
```

---

## Sekcja 4 — Migracja konsumentów

### `menu.py` — `STRUKTURA_MENU`

| Było | Będzie |
|---|---|
| `lazy_rzeczownik_title("UCZELNIA")` | `_tytul_lazy("UCZELNIA")` → „Uczelnia" / „Instytut"… |
| `lazy_rzeczownik_title("WYDZIAL_PL")` | `_tytul_lazy("WYDZIAL", MNOGA)` → „Wydziały" / „Kliniki"… |
| `lazy_rzeczownik_title("JEDNOSTKA_PL")` | `_tytul_lazy("JEDNOSTKA", MNOGA)` → „Jednostki" / „Działy"… |

- Kształt listy bez zmian (3 krotki) — `_should_hide_wydzial` indeksuje
  `STRUKTURA_MENU[1][1]` (URL) i dalej działa.
- **Naprawia live-bug:** dziś `WYDZIAL_PL` renderuje w nawigacji admina
  poprawnie tylko dzięki osobnemu wierszowi; nowa ścieżka liczy plural z lematu.
  (Uwaga: w obecnym `jezyk_polski.znajdz_rzeczownik` `WYDZIAL_PL` **nie ma**
  fallbacku i przy braku wiersza dawał „(brak deklinacji…" — silnik to eliminuje.)

### `top_bar.html`

- `{% rzeczownik_uczelnia %}` → `{% odmien nazwa_uczelni "mianownik" %}`
- `{% rzeczownik_jednostki_m %}` → `{% odmien nazwa_jednostki "mianownik" liczba="mnoga" %}`

### `browse/uczelnia.html`

- `{% rzeczownik_wydział %}` („Wybierz wydział") → `{% odmien nazwa_wydzialu "biernik" %}`
- `{% rzeczownik_jednostkę %}` („Wybierz jednostkę") → `{% odmien nazwa_jednostki "biernik" %}`

### `browse/jednostki.html` + `jednostki_modern_bordered.html`

- `{% rzeczownik_jednostki %}` → `{% odmien nazwa_jednostki "mianownik" liczba="mnoga" %}`
- `{% rzeczownik_jednostek_d %}` → `{% odmien nazwa_jednostki "dopelniacz" liczba="mnoga" %}`
- `{% rzeczownik_jednostki_w %}` → `{% odmien nazwa_jednostki "wolacz" liczba="mnoga" %}`
- `{% rzeczownik_jednostka %}` → `{% odmien nazwa_jednostki "mianownik" %}`
- Blok liczebnikowy
  `({{ count }} {% if count == 1 %}{% rzeczownik_jednostka %}{% elif count < 5 %}{% rzeczownik_jednostek_d %}{% else %}{% rzeczownik_jednostek_d %}{% endif %})`
  → `({{ paginator.count }} {% odmiana_liczebnikowa nazwa_jednostki paginator.count %})`
  **Naprawia live-bug:** dziś „2 jednostek" (błąd); będzie „2 jednostki".

Po migracji: usunąć `{% load deklinacja %}` z tych 4 szablonów, dodać
`{% load polish_inflection %}` gdzie potrzeba.

---

## Sekcja 5 — Testy

- **Przepisać** `test_models/test_rzeczownik.py` do nowego `__str__`
  (`"Rzeczownik JEDNOSTKA = jednostka"`) i pola `m`/`mianownik`.
- **Bez zmian:** `test_util/test_jezyk_polski.py` (tylko
  `warianty_zapisanego_nazwiska`).
- **Nowe:**
  - `nazwy.lemat`: override z `Rzeczownik` wygrywa; brak wiersza → default.
  - Render z przemianowaniem: `Rzeczownik(JEDNOSTKA).m="dział"` →
    menu „Działy", `{% odmien nazwa_jednostki "dopelniacz" liczba="mnoga" %}`
    → „działów", `{% odmiana_liczebnikowa nazwa_jednostki 5 %}` → „działów".
  - Domyślnie (bez przemianowania): „2 jednostki", „5 jednostek" (regresja
    live-buga).
- **Grep-guard w CI:** brak `{% rzeczownik_`, brak `{% load deklinacja %}`,
  brak `lazy_rzeczownik_title` / `znajdz_rzeczownik` / kolumn `d,c,b,n,ms,w`.

---

## Sekcja 6 — Zgodność z konsolidacją (reconciliation)

- Silnik jest podłączony; wzorzec ustalony: **typ/źródło niesie tylko lemat
  (mianownik)**, resztę liczy silnik. Spec konsolidacji prosił o „uzgodnienie
  kształtu pola, które niesie odmianę" — to jest odpowiedź: pojedynczy
  mianownik + silnik, nie zamrożone przypadki.
- Gdy struktura stanie się drzewem: źródłem lematu dla `WYDZIAL`/`JEDNOSTKA`
  staje się `RodzajJednostki.nazwa` (per-węzeł), a `UCZELNIA` — nazwa toplevel.
  Wtedy `Rzeczownik` można skasować, a `nazwy.lemat` przełączyć na nowe źródło.
  Do tego czasu `Rzeczownik` (3 wiersze) jest prostym, wystarczającym nośnikiem.

---

## Poza zakresem (→ przebudowa struktury / drzewo)

- Konfigurowalne nazwy poziomów jako „rodzaj" węzła drzewa (dowolna głębokość,
  `instytut → [nic] → dział`) — teraz mamy 3 stałe uid-y.
- Skasowanie modelu `Rzeczownik` (→ gdy `RodzajJednostki` przejmie źródło).
- Odmiana **własnej nazwy** uczelni (`Uczelnia.nazwa`) przez `{% odmien_fraze %}`.

## Ryzyka

- **Słowo spoza SGJP** w mianowniku (np. egzotyczny neologizm): silnik robi
  passthrough (`POLISH_INFLECTION_STRICT=False`) → forma nieodmieniona zamiast
  błędu. Akceptowalne; admin widzi efekt od razu.
- **Rozmiar obrazu** (+~50 MB) — do potwierdzenia na buildzie.
- **Numer migracji `0445`** — rebase przy równoległych gałęziach (standard).
- **`RemoveField` na kolumnach z baseline** — wymaga `baseline-update` przy
  scalaniu.
