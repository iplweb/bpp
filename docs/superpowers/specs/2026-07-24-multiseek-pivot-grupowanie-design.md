# Grupowanie wyników jako tabela krzyżowa (pivot) — multiseek

**Data:** 2026-07-24
**Gałąź:** `feat/multiseek-pivot-grupowanie`
**Status:** projekt zaakceptowany, do spisania planu implementacji

## 1. Cel

Dodać do wyszukiwarki możliwość **grupowania wyników w tabelę krzyżową
(pivot)** — zbiorcze podsumowanie zamiast płaskiej listy rekordów. User
wybiera wymiar wierszy, wymiar kolumn i metrykę w komórce (model pivota
z Excela: *Rows × Columns × Values*), dostaje krzyżówkę z sumami
brzegowymi i wierszem/kolumną „RAZEM".

Motywacja użytkownika: szybko zobaczyć np. „ile prac i ile punktów PK
w danym roku wg charakteru", „prace autora wg kliniki i rodzaju",
„rozkład prac wg koszyka punktów PK".

## 2. Kluczowe ustalenie architektoniczne

**„Prace autora" renderują się przez ten sam silnik co „Szukaj →
Multiseek".** Strona autora (`AutorView`, `src/bpp/views/browse.py:235`)
to tylko formularz; `BuildSearch` (`src/bpp/views/browse.py:781`) składa
zapytanie multiseek do sesji i przekierowuje na wyniki multiseek. Dlatego
**pivot zaimplementowany w multiseek pokrywa jednocześnie „Szukaj →
Multiseek" i „prace autora"** — bez dodatkowego kodu w widoku autora.

Wyszukiwarka „Szukaj → Zapytaniem" (DjangoQL, `ZapytanieView`,
`src/bpp/views/zapytanie.py`) to **osobny silnik** (dostępny tylko dla
redaktorów/superuserów). Jest poza zakresem fazy 1.

## 3. Decyzje projektowe (podjęte)

| Decyzja | Wybór |
|---|---|
| Sens „grupowania" | **Pivot / zwinięte podsumowanie** (nie sekcje z pełną listą) |
| Kształt | **Tabela krzyżowa** (Wiersze × Kolumny × Wartość) |
| Zawartość komórki | **Wybierana metryka** (pole „Wartości" jak w Excelu) |
| Zasięg | **Multiseek najpierw** (pokrywa Multiseek + prace autora); zapytanie/DjangoQL = faza 2 |
| Eksport pivota | **W fazie 1** (XLSX/CSV od razu) |
| Drill-down (klik w komórkę → rekordy grupy) | **Faza 2** |
| Wymiary z tabeli `Autorzy` (Jednostka/Dyscyplina/Autor) | **W fazie 1**, z widoczną adnotacją o dublowaniu |

## 4. Punkt wpięcia — nowy `report_type`

Multiseek już ma wybór typu raportu (lista / tabela / bibtex) sterujący
wyborem partiala w `src/django_bpp/templates/multiseek/common-results.html:103`.
Typy zdefiniowane w `src/bpp/multiseek_registry/reports.py:8`.

**Dodajemy nowy typ raportu `"pivot"`** („Tabela krzyżowa").

- **Filtr (zapytanie)** zostaje bez zmian — w sesji pod
  `MULTISEEK_SESSION_KEY`, budowany dziś przez
  `registry.get_query_for_model(...)`.
- **Konfiguracja pivota** (wiersze / kolumny / metryka) czytana z
  **parametrów GET** na URL wyników:

  ```
  /multiseek/results/?pivot_row=rok&pivot_col=charakter_ogolny&pivot_val=liczba
  ```

  Zalety takiego rozdziału:
  - przestawienie pivota nie przebudowuje zapytania (tylko zmiana GET);
  - pivot jest **linkowalny / bookmarkowalny / współdzielony URL-em**;
  - działa identycznie dla prac autora (ten sam widok wyników).

Odrzucona alternatywa: osobny widok `/multiseek/pivot/` — dublowałby glue
„sesja → queryset" i wypychał usera z ekranu wyników.

## 5. Interfejs

Gdy typ raportu = „Tabela krzyżowa", nad wynikami pojawia się pasek z
trzema selektorami; zmiana któregokolwiek przeładowuje wyniki (GET):

```
Typ raportu: [ Tabela krzyżowa ▾ ]
Wiersze:[ Rok ▾ ]   Kolumny:[ Charakter ogólny ▾ | (brak) ]   W komórce:[ Liczba prac ▾ ]

              Artykuł  Rozdział  Monografia │ RAZEM
   2024          9        4          2      │  15
   2023          7        3          2      │  12
  ────────────────────────────────────────────────
   RAZEM        16        7          4      │  27
```

- **Kolumny = (brak)** → zwykła płaska tabela zbiorcza (degeneracja
  cross-tabu; user dostaje i pivot 2D, i proste podsumowanie 1D).
- Szeroka krzyżówka → poziomy scroll w kontenerze `overflow-x:auto`
  (body strony się nie rozjeżdża — wzorzec jak w tabelach importu).
- Komórki puste (brak rekordów na przecięciu) → puste albo `–`
  (do ustalenia w implementacji; domyślnie puste dla czytelności).
- Wiersz i kolumna **RAZEM** = sumy brzegowe; przecięcie = suma całkowita.
- Sortowanie wierszy: wg wartości wymiaru (rok malejąco jak dziś dla
  Rok; alfabetycznie dla słowników). Kolumny analogicznie.
- **Adnotacja o dublowaniu** (gdy wybrany wymiar z tabeli `Autorzy` —
  Jednostka/Dyscyplina/Autor) renderowana **bezpośrednio pod tabelą
  krzyżową** (pod pivotem, nie nad nim), stonowana wizualnie (mały,
  szary tekst / `<figcaption>`-style), by nie odciągała od danych.

## 6. Menu wymiarów i metryk

### Wymiary — jako **wiersze** (wszystkie):
Rok · Charakter formalny · Charakter ogólny (rodzaj: artykuł / rozdział /
monografia / …) · Typ MNiSW/MEiN (`typ_kbn`) · Koszyk punktów PK · Język ·
**Jednostka** · Wydział · Dyscyplina naukowa · Źródło · Autor

### Wymiary — jako **kolumny** (tylko o małej liczności):
Rok · Charakter formalny · Charakter ogólny · Typ MNiSW/MEiN · Koszyk PK ·
Język · Dyscyplina

> Jednostka / Wydział / Źródło / Autor **nie są dostępne jako kolumny** —
> zbyt duża liczność rozsadziłaby szerokość tabeli. Tylko jako wiersze.

### Metryki — „w komórce":
Liczba prac *(domyślna)* · Σ punkty PK (`punkty_kbn`) · Σ Impact Factor ·
Σ liczba cytowań · Σ punktacja wewnętrzna

### Mapowanie wymiarów na wyrażenia ORM
| Wymiar | Wyrażenie | Uwaga |
|---|---|---|
| Rok | `rok` | pole rekordu |
| Charakter formalny | `charakter_formalny__nazwa` (+ id do sortowania) | FK |
| Charakter ogólny | `charakter_formalny__charakter_ogolny` | `charakter_formalny.py:104` |
| Typ MNiSW/MEiN | `typ_kbn__nazwa` | FK |
| Koszyk punktów PK | `punkty_kbn` | wartość dyskretna; 0/NULL → „brak" |
| Język | `jezyk__nazwa` | FK |
| Jednostka | `autorzy__jednostka__nazwa` | **JOIN do `Autorzy`** — patrz §7 |
| Wydział | `autorzy__jednostka__wydzial__nazwa` | JOIN do `Autorzy` |
| Dyscyplina | `autorzy__dyscyplina_naukowa__nazwa` | JOIN do `Autorzy` |
| Źródło | `zrodlo__nazwa` | FK |
| Autor | `autorzy__autor` (str) | JOIN do `Autorzy` |

## 7. Subtelność semantyczna — wymiary z tabeli `Autorzy`

Pola **na rekordzie** (rok, charakter, typ, punkty, język, źródło):
grupowanie czyste — każdy rekord liczony raz, sumy się zgadzają.

Pola **na powiązaniu `Autorzy`** (Jednostka, Dyscyplina, Autor) —
`src/bpp/models/cache/autorzy.py:24`: rekord ma wielu autorów z różnych
jednostek/dyscyplin. Grupując po nich:
- „liczba prac" = liczba **powiązań** rekord–jednostka (praca z 2 klinik
  policzy się w obu),
- Σ PK **dubluje** punkty rekordu w każdej jednostce.

Zachowanie v1:
- **Wspieramy** te wymiary od razu (user wprost chce „po klinice").
- Przy ich wyborze pokazujemy **widoczną adnotację bezpośrednio pod
  tabelą krzyżową** (pod pivotem), np.:
  *„Grupowanie po jednostce/dyscyplinie/autorze liczy powiązania, nie
  unikatowe prace — praca powiązana z wieloma jednostkami liczona jest
  w każdej z nich; sumy mogą przewyższać wartości całkowite."*
- Dla **prac autora** dublowanie jest naturalne i pożądane (jeden autor,
  jego afiliacje) — adnotacja i tak nie szkodzi.
- „Uczciwe" punkty per-dyscyplina ze slotów (`Cache_Punktacja_Dyscypliny`,
  `src/bpp/models/cache/punktacja.py:18`, pola `pkd`/`slot`) → **faza 2**.

Implementacyjnie: gdy wymiar wiersza lub kolumny wymaga JOIN-u do
`autorzy`, queryset dostaje `.filter()`/`values()` po tej relacji i
**świadomie NIE** stosujemy `distinct()` na poziomie rekordu w agregacji
(dublowanie jest zamierzone i zakomunikowane).

## 8. Backend

Na **tym samym przefiltrowanym** queryzecie co lista wyników
(`MyMultiseekResults.get_queryset`, `src/bpp/views/mymultiseek.py:90`):

```python
qs = (
    filtered_qs
    .values(row_expr, col_expr)          # col_expr pominięty, gdy kolumny=(brak)
    .annotate(val=<agregat metryki>)     # Count("id") lub Sum("punkty_kbn") itd.
    .order_by(row_expr, col_expr)
)
```

Płaska lista trójek `(wiersz, kolumna, wartość)` składana w Pythonie w
strukturę macierzy:
- zbiór unikatowych wierszy (posortowany),
- zbiór unikatowych kolumn (posortowany) — pusty, gdy kolumny=(brak),
- słownik `{(wiersz, kolumna): wartość}`,
- sumy per-wiersz, sumy per-kolumna, suma całkowita.

Nowy helper (np. `src/bpp/multiseek_registry/pivot.py`) zawiera:
- rejestr dostępnych wymiarów (klucz GET → etykieta + wyrażenie ORM +
  flaga „dozwolony jako kolumna" + flaga „wymaga JOIN do autorzy"),
- rejestr metryk (klucz GET → etykieta + wyrażenie agregatu),
- funkcję `zbuduj_pivot(qs, row_key, col_key, val_key) -> PivotResult`
  zwracającą wiersze/kolumny/macierz/sumy,
- walidację parametrów GET (nieznany klucz → wartość domyślna / błąd
  komunikatem, nie 500).

Wydajność: jedno `GROUP BY` po stronie bazy; koszt porównywalny z
istniejącym liczeniem sum w stopce (`mymultiseek.py:181`). Twardy limit
25000 rekordów z listy (`common-results.html:10`) dla pivota **nie
obowiązuje** — pivot agreguje, nie renderuje pojedynczych rekordów; można
policzyć bezpiecznie dużo większy zbiór. (Do potwierdzenia: czy nakładać
osobny, znacznie wyższy limit czy żaden.)

## 9. Eksport (faza 1)

Multiseek ma eksport w `MyMultiseekExport` (`src/bpp/views/mymultiseek.py:239`)
i formatach w `src/bpp/views/multiseek_export.py` (CSV / XLSX / HTML /
DOCX / BibTeX). Dla pivota:
- eksport respektuje te same parametry GET pivota (row/col/val),
- generuje **XLSX i CSV** z macierzą krzyżową (wiersze × kolumny + sumy
  brzegowe). DOCX/HTML — opcjonalnie, jeśli tanie; BibTeX nie dotyczy
  pivota (pomijamy).
- Nowy builder eksportu pivota (np. w `multiseek_export.py`) korzysta z
  tej samej struktury `PivotResult` co widok — jedno źródło prawdy.

## 10. Pliki do zmiany (orientacyjnie)

- `src/bpp/multiseek_registry/reports.py` — nowy typ raportu `pivot`.
- `src/bpp/multiseek_registry/pivot.py` — **nowy**: rejestr wymiarów/metryk
  + `zbuduj_pivot()` + `PivotResult`.
- `src/bpp/views/mymultiseek.py` — w `MyMultiseekResults.get_context_data`
  (ok. `:181`): gdy `report_type == "pivot"`, policz `PivotResult` z GET;
  w `MyMultiseekExport` (`:239`) — gałąź eksportu pivota.
- `src/django_bpp/templates/multiseek/common-results.html` (`:103`) —
  gałąź partiala dla `pivot`.
- `src/django_bpp/templates/multiseek/report-body-pivot.html` — **nowy**:
  pasek selektorów + tabela krzyżowa + adnotacja o dublowaniu.
- `src/bpp/views/multiseek_export.py` — builder XLSX/CSV pivota.
- SCSS: ewentualny komponent stylu tabeli krzyżowej (sticky nagłówki
  wierszy/kolumn, scroll) — bez nadpisywania siatki Foundation.
- Testy: `src/bpp/tests/` (jednostkowe `zbuduj_pivot`) + test widoku +
  ewentualnie Playwright dla przełączania selektorów.
- Newsfragment: `src/bpp/newsfragments/<slug>.feature.rst`.

**Bez migracji, bez zmian w modelach.** Wszystko na istniejących polach
`Rekord` / `Autorzy` (materializowane widoki `bpp_rekord_mat` /
`bpp_autorzy_mat`).

## 11. Testy

- **Jednostkowe** `zbuduj_pivot()`: znane dane wejściowe → oczekiwana
  macierz + sumy brzegowe (w tym degeneracja kolumny=(brak),
  puste komórki, „koszyk PK" z 0/NULL → „brak").
- **Semantyka `Autorzy`**: rekord z autorami w 2 jednostkach → liczy się
  w obu; suma brzegowa > liczba unikatowych rekordów (test dokumentujący
  zamierzone dublowanie).
- **Widok**: GET z parametrami pivota → poprawny kontekst i status 200;
  nieznany klucz wymiaru/metryki → wartość domyślna / czytelny błąd,
  nie 500.
- **Eksport**: XLSX/CSV pivota zawiera te same liczby co widok.
- Konwencje pytest projektu: funkcje, `@pytest.mark.django_db`,
  `model_bakery.baker.make`, `-n auto`.

## 12. Poza zakresem v1 (faza 2 i dalej)

- **Szukaj → Zapytaniem (DjangoQL)** — ten sam pivot w `ZapytanieView`.
  Punkt wpięcia: `render_results` w `src/bpp/views/zapytanie.py:366`
  (przed `Paginator`). Osobny przepływ (GET zamiast sesji), ale wspólny
  komponent `zbuduj_pivot()` da się przenieść.
- **Drill-down** — klik w komórkę/wiersz → lista rekordów tej grupy
  (dodaje warunek do zapytania i pokazuje listę).
- **„Uczciwe" punkty per-dyscyplina** ze slotów
  (`Cache_Punktacja_Dyscypliny.pkd`/`slot`) zamiast dublowanych
  `punkty_kbn` przy grupowaniu po dyscyplinie/jednostce.
- Trzeci wymiar / zagnieżdżanie wielopoziomowe, wykresy z pivota.

## 13. Ryzyka i otwarte kwestie (do rozstrzygnięcia w planie)

1. **report_type z GET czy z sesji?** Dziś report_type bywa częścią
   formularza (sesja). Aby pasek pivota działał bez przebudowy zapytania,
   widok wyników powinien czytać `report_type` (i pivot_*) z GET z
   fallbackiem do sesji. Do potwierdzenia w implementacji.
2. **Limit rekordów dla pivota** — znieść twardy limit 25000 (pivot
   agreguje) czy nałożyć osobny, wyższy? Rekomendacja: znieść dla pivota,
   ewentualnie miękkie ostrzeżenie przy bardzo dużych zbiorach.
3. **Etykiety słowników z i18n / per-uczelnia** — nazwy charakterów/typów
   pobierać spójnie z istniejącymi (nie hardkodować).
4. **Puste komórki**: puste vs `–` vs `0` — ustalić w partialu.
5. **Widoczność wymiarów per-uczelnia** — czy respektować
   `BppMultiseekVisibility` (widoczność pól) także dla menu pivota, czy
   pivot ma własny, stały zestaw wymiarów. Rekomendacja: stały zestaw
   pivota niezależny od widoczności pól filtrowania (inne przeznaczenie).

## 14. Podsumowanie nakładu

Faza 1 (multiseek: widok pivota + eksport XLSX/CSV, pełne menu wymiarów
w tym Jednostka/Dyscyplina/Autor z adnotacją): **średni** — 1 nowy helper,
1 nowy partial, nowy report_type, gałąź eksportu, kilka parametrów GET.
Zero migracji, zero zmian modeli. Faza 2 (DjangoQL + drill-down +
slot-based punkty) — osobno.
