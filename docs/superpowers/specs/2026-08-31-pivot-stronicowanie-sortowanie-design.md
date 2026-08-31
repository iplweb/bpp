# Tabela krzyżowa: stronicowanie i sortowanie

Data: 2026-08-31
Branch: `feat-pivot-stronicowanie-sortowanie`

## Problem

Tabela krzyżowa (`postac=pivot` na `/zapytanie/`, `report_type=pivot`
w multiseeku) renderuje **wszystkie** wiersze macierzy naraz. Przy
`pivot_row=autor` to ~2000 wierszy na jednej stronie — nieużywalne.

Brakuje też jakiegokolwiek sterowania kolejnością: `_labels()` sortuje
alfabetycznie po etykiecie (albo malejąco po roku dla `rok`/`koszyk_pk`)
i to jedyna dostępna kolejność. Typowe pytanie użytkownika brzmi „kto ma
najwięcej prac" — dziś wymaga eksportu do XLSX i posortowania w Excelu.

## Zakres

1. Stronicowanie wierszy macierzy — **obie** ścieżki wejścia (multiseek
   „precyzyjne" i `/zapytanie/` DjangoQL), bo obie renderują ten sam
   partial `multiseek/report-body-pivot.html`.
2. Sortowanie wierszy: po etykiecie (dzisiejsze, domyślne) albo po sumie
   wiersza (RAZEM), oba kierunki.

Poza zakresem: sortowanie kolumn (kolumn jest z definicji mało — bramka
`PIVOT_MAX_CELLS` i tak by nie przepuściła szerokiej macierzy), sortowanie
po konkretnej kolumnie, stronicowanie kolumn.

## Rozważone podejścia

| | Opis | Werdykt |
|---|---|---|
| A | Sortuj + stronicuj **już zbudowaną** macierz w pamięci | **wybrane** |
| B | `LIMIT/OFFSET` na kluczach wierszy w SQL-u | odrzucone |
| C | Sortowanie/stronicowanie po stronie klienta (DataTables) | odrzucone |

**B** wymagałoby drugiego przebiegu po zbiorze, żeby policzyć sumy kolumn
i sumę całkowitą (te muszą obejmować cały dataset, nie widoczną stronę),
a przy wymiarze idącym przez `autorzy__` płaciłoby ten sam drogi JOIN
dwa razy. Bramka `PIVOT_MAX_PAIRS` i tak ogranicza rozmiar tego, co wchodzi
do RAM-u, więc oszczędność pamięci byłaby iluzoryczna.

**C** przeczy sednu zgłoszenia: 2000 wierszy nadal poleciałoby do
przeglądarki. Strona musi też działać bez JS (partial ma `<noscript>`).

## Projekt

### 1. `PivotWidok` (nowy, `bpp/pivot/core.py`)

Oddziela „co policzono" (`PivotResult`) od „jak pokazać" (`PivotWidok`):

```python
@dataclass(frozen=True)
class PivotWidok:
    sort: str = SORT_ETYKIETA        # "etykieta" | "suma"
    kierunek: str | None = None      # "asc" | "desc"; None = naturalny
    strona: int = 1
    na_stronie: int = DOMYSLNIE_NA_STRONIE   # 0 = bez stronicowania
```

`parse_widok(GET)` czyta `pivot_sort`, `pivot_dir`, `pivot_page`,
`pivot_per_page`. Mieszka w `core`, **nie** w rejestrach — dzięki temu
sygnatura `parse_params()` i jej pięć miejsc wywołania zostają nietknięte.

`na_stronie` jest walidowane względem `DOZWOLONE_NA_STRONIE = (25, 50,
100, 250)`. Bez tego `?pivot_per_page=999999` unieważnia całą zmianę.

`bez_stronicowania()` zwraca kopię z `na_stronie=0` — używa tego eksport.

### 2. Sortowanie — rozszerzenie `_labels()`

`_labels(keys, dim, widok=None, row_totals=None)`. Bez `widok` zachowuje
się **dokładnie** jak dziś (pełna kompatybilność wsteczna z istniejącymi
testami kolejności i z osią kolumn, która sortowania nie dostaje).

- `sort=etykieta` (domyślny): dzisiejsza kolejność. `kierunek=desc`
  odwraca ją.
- `sort=suma`: klucz `(-suma, etykieta.lower())`; `kierunek=asc` daje
  `(suma, etykieta.lower())`.

**Kolejność musi być porządkiem TOTALNYM, inaczej stronicowanie gubi
wiersze.** Bez tego wiersze nierozróżnialne przez kryterium główne mogą
wypaść w różnej kolejności między żądaniami — a wtedy wiersz na granicy
strony pokazuje się na dwóch stronach albo znika z obu.

Etykieta jako ostatni dyskryminator NIE wystarcza: etykiety nie są
unikatowe (dwóch autorów „Kowalski Jan" ma różne PK i ten sam `str()`).
Przy remisie decydowałaby wtedy kolejność wejścia, a ta pochodzi
z `set(row_keys)` wypełnianego wynikiem `GROUP BY` bez `ORDER BY` —
Postgres nie gwarantuje jej powtarzalności między wykonaniami
(HashAggregate, parallel workers). Ostatecznym dyskryminatorem jest więc
sam klucz wymiaru (`_klucz_rozstrzygajacy`, `str()` bo klucze bywają
mieszanych typów). To samo dotyczy `_labels` — dla `sort=etykieta` cała
totalność siedzi właśnie tam.

### 3. Stronicowanie — `as_table(widok=None)`

Wywołane bez argumentu zwraca dokładnie to co dziś (ważne:
`_pivot_export_rows()` woła je bezargumentowo).

Z `widok`: `Paginator` + `get_page()` (poza zakresem → ostatnia strona,
bez 404). Dokłada `page_obj`, `paginator`, `is_paginated`, `sort`,
`kierunek`, `na_stronie`, `wszystkich_wierszy`.

`col_totals` i `grand_total` **nie** są przeliczane per strona — pokazują
cały zbiór (semantyka Excela). Pod tabelą staje adnotacja, że tak jest;
inaczej redaktor zsumuje widoczną kolumnę i uzna, że liczby się nie zgadzają.

### 4. Szablon

W `multiseek/report-body-pivot.html`:

- nagłówek pierwszej kolumny i `RAZEM` stają się linkami sortującymi (▲/▼),
- nowy partial `multiseek/_pivot-pager.html` (parametr `pivot_page`),
- selektor „wierszy na stronie" w istniejącym pasku kontrolek,
- **ukryte pola `pivot_sort`/`pivot_dir` w formularzu kontrolek** — selecty
  auto-submitują, więc bez tego zmiana wymiaru gubiłaby wybrane sortowanie.
  `pivot_page` celowo NIE jest przenoszone: zmiana wymiaru wraca na stronę 1.

Linki sortujące budowane wbudowanym tagiem `{% querystring %}` (Django
5.1+; projekt jest na 5.2.17), który przenosi całe bieżące `request.GET`:

```django
{% querystring pivot_sort="suma" pivot_dir="desc" pivot_page=None print=None %}
```

`print=None` jest konieczne: `common-results.html` odpala
`if (queryDict.print == "1") window.print();`, więc bez wykasowania tego
klucza kliknięcie sortowania na wydruku otwierałoby okno drukowania.

### 5. Eksport

`_pivot_export_rows()` i oba `pivot_*_export_response()` dostają
opcjonalny `widok`; oba miejsca wywołania przekazują
`parse_widok(GET).bez_stronicowania()`. Sortowanie jest respektowane,
stronicowanie ignorowane — plik zawsze zawiera pełną macierz. To także
powód, dla którego UI nie ma opcji „pokaż wszystkie wiersze".

### 6. `PIVOT_MAX_CELLS`: 10 000 → 50 000

Limit chronił przed wyrenderowaniem gigantycznego HTML-a. Po
wprowadzeniu stronicowania renderowanie przestaje być wąskim gardłem —
do DOM-u trafia najwyżej `na_stronie` wierszy. `PIVOT_MAX_PAIRS`
(200 000) zostaje bez zmian: to prawdziwy bezpiecznik pamięci dla
strategii B i anonimowych użytkowników.

### 7. Testy + newsfragment

Sortowanie po sumie w obu kierunkach, rozstrzyganie remisów,
`widok=None` == dzisiejsze zachowanie, podział na strony, strona poza
zakresem, odrzucenie `pivot_per_page=999999`, globalność `col_totals` na
stronie ≠ 1, eksport ignoruje stronę ale respektuje sortowanie, oba widoki
(multiseek + `/zapytanie/` dla `model=rekord` i `model=autor`).

## Pliki

`src/bpp/pivot/core.py`, `src/bpp/pivot/__init__.py`,
`src/bpp/views/mymultiseek.py`, `src/bpp/views/zapytanie.py`,
`src/bpp/views/zapytanie_export.py`, `src/bpp/views/multiseek_export.py`,
`src/django_bpp/templates/multiseek/report-body-pivot.html`,
nowy `src/django_bpp/templates/multiseek/_pivot-pager.html`,
`src/bpp/static/scss/_multiseek-reports.scss` (+ `grunt build`),
testy, newsfragment.
