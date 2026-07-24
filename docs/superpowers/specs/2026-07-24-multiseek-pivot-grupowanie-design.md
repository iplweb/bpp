# Grupowanie wyników jako tabela krzyżowa (pivot) — multiseek

**Data:** 2026-07-24
**Gałąź:** `feat/multiseek-pivot-grupowanie`
**Status:** projekt zaakceptowany, uzupełniony po self-review (Fable), do
spisania planu implementacji

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
zapytanie multiseek do sesji i przekierowuje na **`multiseek:index`**
(formularz z live-iframe `./live-results/`, `multiseek/index.html:402`) —
czyli user prac autora **ma na tej stronie selektor typu raportu**.
Kluczowe: to **ten sam silnik multiseek** renderuje listę prac, więc
pivot zaimplementowany w multiseek pokrywa jednocześnie „Szukaj →
Multiseek" i „prace autora" — bez dodatkowego kodu w widoku autora.

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
| „Wydział" jako wymiar | **Faza 2** (dziura NULL-korzenia, §6/§13) |

## 4. Punkt wpięcia — nowy `report_type` + parametry GET

Multiseek ma wybór typu raportu (lista / tabela / bibtex) sterujący
wyborem partiala w `src/django_bpp/templates/multiseek/common-results.html:103`.
Typy zdefiniowane w `src/bpp/multiseek_registry/reports.py:8`.

**Dodajemy nowy typ raportu `"pivot"`** („Tabela krzyżowa").

> **UWAGA (report_type to indeks pozycyjny, nie string!).** Formularz
> POST-uje `forloop.counter0` (`multiseek/index.html:44`); `get_report_type`
> indeksuje przefiltrowaną per-request listę (`multiseek/logic.py:721`).
> Sesje i zapisane `SearchForm` przechowują **indeks**. Dlatego nowy typ
> `pivot` **musi być dopisany na KOŃCU** `multiseek_report_types`
> (`reports.py:8`) i mieć **`public=True`** (anonim na stronie autora).
> Wstawienie w środek przesunęłoby zapisane formularze.

**Rozdział odpowiedzialności:**
- **report_type** (który to typ raportu, w tym „pivot") — mechanizmem
  istniejącym: **selektor w formularzu → sesja**. Bez GET-override
  (musiałby być honorowany spójnie w 3 miejscach — niepotrzebna
  komplikacja).
- **Konfiguracja pivota** (wiersze / kolumny / metryka) — **parametry GET**
  na URL wyników, czytane w widoku wyników:

  ```
  /multiseek/results/?pivot_row=rok&pivot_col=charakter_ogolny&pivot_val=liczba
  ```

  Zalety: przestawienie pivota nie przebudowuje zapytania (sama zmiana
  GET); pivot jest **linkowalny/bookmarkowalny**. Brak parametrów → sensowne
  domyślne (`pivot_row=rok`, `pivot_col=` brak, `pivot_val=liczba`).

> **Znane zachowanie (do udokumentowania, nie bug):** na stronie prac
> autora wyniki są w live-iframe; każda zmiana formularza robi POST do
> iframe i **resetuje** parametry `pivot_*` z GET. Świadome, akceptowalne
> w v1.

Odrzucona alternatywa: osobny widok `/multiseek/pivot/` — dublowałby glue
„sesja → queryset" i wypychał usera z ekranu wyników.

## 5. Interfejs

Gdy typ raportu = „Tabela krzyżowa", nad wynikami pojawia się pasek z
trzema selektorami (mini-formularz GET); zmiana któregokolwiek
przeładowuje wyniki:

```
Typ raportu: [ Tabela krzyżowa ▾ ]
Wiersze:[ Rok ▾ ]   Kolumny:[ Charakter ogólny ▾ | (brak) ]   W komórce:[ Liczba prac ▾ ]

              Artykuł  Rozdział  Monografia │ RAZEM
   2024          9        4          2      │  15
   2023          7        3          2      │  12
  ────────────────────────────────────────────────
   RAZEM        16        7          4      │  27

  ⓘ Grupowanie po jednostce/dyscyplinie/autorze liczy powiązania…  (adnotacja pod tabelą)
```

- **Kolumny = (brak)** → zwykła płaska tabela zbiorcza (degeneracja
  cross-tabu; user dostaje i pivot 2D, i proste podsumowanie 1D).
- Szeroka krzyżówka → poziomy scroll w kontenerze `overflow-x:auto`
  (body strony się nie rozjeżdża — wzorzec jak w tabelach importu).
- **Puste komórki** (brak rekordów na przecięciu) → puste (blank) dla
  czytelności; sumy brzegowe i tak liczone.
- Wiersz i kolumna **RAZEM** = sumy brzegowe; przecięcie = suma całkowita.
- Sortowanie wierszy: wg wartości wymiaru (rok malejąco; słowniki
  alfabetycznie). Kolumny analogicznie.
- **Adnotacja o dublowaniu** (gdy wybrany wymiar z tabeli `Autorzy` —
  Jednostka/Dyscyplina/Autor) renderowana **bezpośrednio pod tabelą
  krzyżową** (pod pivotem, nie nad nim), stonowana wizualnie (mały,
  szary tekst).

## 6. Menu wymiarów i metryk

### Wymiary — jako **wiersze**:
Rok · Charakter formalny · Charakter ogólny (rodzaj) · Typ MNiSW/MEiN
(`typ_kbn`) · Koszyk punktów PK · Język · Źródło · **Jednostka** ·
**Dyscyplina naukowa** · **Autor**

### Wymiary — jako **kolumny** (tylko o małej liczności):
Rok · Charakter formalny · Charakter ogólny · Typ MNiSW/MEiN · Koszyk PK ·
Język · Dyscyplina

> Jednostka / Źródło / Autor **nie są dostępne jako kolumny** — zbyt duża
> liczność rozsadziłaby szerokość tabeli. Tylko jako wiersze.
> **„Wydział" — faza 2** (patrz §13, dziura NULL-korzenia).

### Metryki — „w komórce":
Liczba prac *(domyślna)* · Σ punkty PK (`punkty_kbn`) · Σ Impact Factor ·
Σ liczba cytowań · Σ punktacja wewnętrzna

### Mapowanie wymiarów na wyrażenia ORM i etykiety
| Wymiar | Wyrażenie ORM (`values`) | Etykieta / uwaga |
|---|---|---|
| Rok | `rok` | wartość wprost |
| Charakter formalny | `charakter_formalny_id` | dociągnąć `nazwa` (mapa id→nazwa) |
| Charakter ogólny | `charakter_formalny__charakter_ogolny` | **surowe kody 3-zn.** → mapa `CHARAKTER_OGOLNY_CHOICES` (`charakter_formalny.py:80`) |
| Typ MNiSW/MEiN | `typ_kbn_id` | dociągnąć `nazwa` |
| Koszyk punktów PK | `punkty_kbn` | Decimal (default=0, NOT NULL); 0 → „brak (0)"; formatować etykiety |
| Język | `jezyk_id` | dociągnąć `nazwa` |
| Źródło | `zrodlo_id` | dociągnąć `nazwa`; NULL → „brak" |
| Jednostka | `autorzy__jednostka_id` | **JOIN do `Autorzy`** — §7; dociągnąć `nazwa`; NULL → „brak" |
| Dyscyplina | `autorzy__dyscyplina_naukowa_id` | JOIN do `Autorzy`; dociągnąć `nazwa`; NULL → „brak" |
| Autor | `autorzy__autor_id` | JOIN do `Autorzy`; **zwraca id, nie str** — hurtowo dociągnąć nazwiska, sortować w Pythonie |

> **Ujednolicenie NULL-kubłów:** dla każdego wymiaru dopuszczającego NULL
> (źródło, dyscyplina, autor, jednostka przy LEFT JOIN) wartość NULL →
> etykieta **„brak"** (spójnie z koszykiem PK).

## 7. Subtelność semantyczna — wymiary z tabeli `Autorzy`

Pola **na rekordzie** (rok, charakter, typ, punkty, język, źródło):
grupowanie czyste — każdy rekord liczony raz.

Pola **na powiązaniu `Autorzy`** (Jednostka, Dyscyplina, Autor) —
`src/bpp/models/cache/autorzy.py:24`: rekord ma wielu autorów z różnych
jednostek/dyscyplin. **Zdefiniowana semantyka v1: pary (rekord,
wartość-wymiaru).** Praca powiązana z 2 klinikami → liczy się **raz w
każdej klinice** (NIE N-krotnie wg liczby autorów z danej kliniki).

- „liczba prac" w grupie = liczba **unikatowych rekordów** powiązanych z
  daną jednostką (dedup po rekordzie w obrębie grupy),
- Σ metryki = suma po **unikatowych parach** (rekord, jednostka) — punkty
  rekordu wliczone raz do każdej jednostki, z którą powiązany.
- Dublowanie **między różnymi** jednostkami/dyscyplinami jest zamierzone
  i komunikowane adnotacją pod tabelą (§5).
- Dla **prac autora** (filtr `autorzy__autor=X`) join jest **reużywany**
  (zweryfikowany SQL) → grupujemy po jednostkach/dyscyplinach *tego*
  autora — dokładnie to, o co chodzi.
- „Uczciwe" punkty per-dyscyplina ze slotów (`Cache_Punktacja_Dyscypliny.pkd`/`slot`,
  `src/bpp/models/cache/punktacja.py:18`) → **faza 2**.

## 8. Backend — strategia agregacji (per typ wymiaru)

Punkt wyjścia: `base_qs` = przefiltrowany queryset (ten sam filtr co lista
wyników), ale **BEZ `.only()`, BEZ `.distinct()` i z WYCZYSZCZONYM
orderingiem** (`base_qs = filtered.order_by()`).

> **KRYTYCZNE (K3): jawny `order_by` wchodzi do GROUP BY.** Rejestr
> multiseek ZAWSZE aplikuje `.order_by(...)` (`default_ordering=["-rok"]`,
> `src/bpp/multiseek_registry/__init__.py:26`; `apply_ordering_to_queryset`,
> `multiseek/logic.py:744`). Bez `.order_by()` przed `values().annotate()`
> sort formularza (np. „źródło/wyd. nadrzędne" = `CASE WHEN…`) wchodzi do
> `GROUP BY` i **rozbija pivot na mikrogrupy**. Musi być jawnie wyczyszczony
> i pokryty testem (najgroźniejsza cicha regresja).

Filtry multiseek mogą **mnożyć wiersze** rekordu (JOIN do `bpp_autorzy_mat`
/ `bpp_zewnetrzne_bazy_view`). `.distinct()` z listy wyników **NIE
naprawia** GROUP BY (dedup następuje PO agregacji). Dlatego dwie ścieżki:

### A) Oba wymiary (wiersz i kolumna) są **rekordowe**
Agregujemy po **zdedupowanym zbiorze rekordów**, żeby filtr mnożący nie
zawyżał (K1):
```python
ids = base_qs.values("pk")
deduped = Rekord.objects.filter(pk__in=ids).order_by()   # świeży, czysty
matrix_rows = (deduped
    .values(row_expr, col_expr)          # col_expr pominięty, gdy kolumny=(brak)
    .annotate(licznik=Count("id"), suma=Sum(metric_field))
    .order_by(row_expr, col_expr))
```
Każdy rekord raz. `Count("id")` OK (`Rekord.id` = `TupleField`/`int[]`,
PG liczy). `Sum(metric_field)` — metryka raz per rekord.

### B) Wiersz **lub** kolumna to wymiar **autorski** (jednostka/dyscyplina/autor)
NIE używamy `pk__in`-subquery (zerwałby join-reuse → jednostki wszystkich
współautorów zamiast, dla prac autora, tylko tego autora). Operujemy na
`base_qs` (zachowuje kontekst filtra), pobieramy **unikatowe pary** i
agregujemy w Pythonie:
```python
pairs = (base_qs
    .values(row_expr, col_expr, "id", metric_field)  # id = rekord
    .distinct())
# w Pythonie, per (wiersz, kolumna):
#   licznik = liczba unikatowych rekordów (set po id)
#   suma    = Σ metric_field po unikatowych parach (wymiar, rekord)
```
Realizuje „raz per klinika" i punkty rekordu wliczone raz w każdą jednostkę
(§7). (Metryki v1 są zawsze **na poziomie rekordu**, więc `(wymiar, id)`
jednoznacznie wyznacza `metric_field`.)

### Składanie macierzy
Płaska lista trójek `(wiersz, kolumna, wartość)` → struktura:
- posortowany zbiór wierszy, posortowany zbiór kolumn (pusty gdy
  kolumny=(brak)), słownik `{(wiersz, kolumna): wartość}`, sumy per-wiersz,
  per-kolumna, suma całkowita.
- surowe klucze (id/kody) → etykiety wg map z §6 (hurtowe `in_bulk` dla
  FK, `dict(CHOICES)` dla kodów) — **jeden** dodatkowy query per słownik.

### Wydajność / liczności
- Dla pivota **nie** liczymy drogiego `qset.count()` (`mymultiseek.py:208`)
  ani sum ze stopki listy — pivot ma własne agregaty.
- Gate 25000 rekordów z listy (`common-results.html:10`) **nie obowiązuje**
  dla pivota (agreguje, nie renderuje rekordów). Ewentualne miękkie
  ostrzeżenie przy bardzo dużym zbiorze — patrz §13.
- **Cache:** w v1 **nie** cache'ujemy pivota (istniejący `_aggregate_cache_key`
  nie obejmuje `pivot_*` — cache'owanie bez poprawki klucza dałoby
  krzyżowe trafienia). Ewentualny cache z kluczem obejmującym GET — faza 2.

## 9. Eksport (faza 1)

Multiseek ma eksport `MyMultiseekExport` (`src/bpp/views/mymultiseek.py:239`),
formaty w `src/bpp/views/multiseek_export.py`. Kolizje z istniejącym
kontraktem (do rozwiązania):

1. **Twardy cap 5000 rekordów PRZED gałęzią** (`mymultiseek.py:252`) —
   dotyczy liczby rekordów źródłowych. Dla pivota **wynik to mała macierz**,
   nie per-rekord — cap na rozmiar wyjścia jest bezcelowy. Rozwiązanie:
   **dla `report_type==pivot` omijamy cap 5000** (budujemy z `PivotResult`,
   nie z listy rekordów).
2. **Kontrakt „csv/xlsx = stałe kolumny, niezależne od report_type"**
   (`mymultiseek.py:242`) — macierz pivota łamie to założenie. Rozwiązanie:
   **jawna gałąź `if report_type == pivot`** w `MyMultiseekExport.get`,
   budująca XLSX/CSV z tej samej struktury `PivotResult` co widok (jedno
   źródło prawdy). BibTeX nie dotyczy pivota — pomijamy; DOCX/HTML
   opcjonalnie, jeśli tanie.
3. **`LoginRequiredMixin`** na eksporcie — anonim ze strony autora
   **widzi** pivot na ekranie, ale **nie wyeksportuje**. W v1: przycisk
   eksportu pivota ukryty dla anonima; eksport pozostaje login-only.
   (Eksport dla anonima — faza 2, jeśli potrzebny.)

## 10. Pliki do zmiany (orientacyjnie)

- `src/bpp/multiseek_registry/reports.py` — nowy typ raportu `pivot`
  **na końcu** listy, `public=True`.
- `src/bpp/multiseek_registry/pivot.py` — **nowy**: rejestr wymiarów
  (klucz GET → etykieta + wyrażenie ORM + flaga „dozwolony jako kolumna"
  + flaga „wymaga JOIN do autorzy" + strategia etykiet) i metryk;
  `PivotResult` (macierz + sumy); `zbuduj_pivot(base_qs, row, col, val)`
  z rozgałęzieniem A/B (§8), czyszczeniem orderingu i mapowaniem etykiet;
  walidacja GET (nieznany klucz → default / czytelny komunikat, nie 500).
- `src/bpp/views/mymultiseek.py` — w `MyMultiseekResults.get_context_data`
  (`~:181`): gdy `report_type == pivot`, policz `PivotResult` z GET,
  **pomiń** count/sumy listy; w `MyMultiseekExport.get` (`~:239`) — gałąź
  eksportu pivota (omija cap 5000).
- `src/django_bpp/templates/multiseek/common-results.html` (`~:10`, `~:103`)
  — dla pivota **ominąć gate 25000, pominąć `autopaginate` i oba
  paginatory** (nie fetchować 20 rekordów na darmo), wybrać nowy partial.
  (Restrukturyzacja większa niż sam `if` przy :103.)
- `src/django_bpp/templates/multiseek/report-body-pivot.html` — **nowy**:
  pasek selektorów (GET) + tabela krzyżowa (sticky nagłówki, scroll) +
  adnotacja o dublowaniu pod tabelą.
- `src/bpp/views/multiseek_export.py` — builder XLSX/CSV pivota z
  `PivotResult`.
- SCSS: komponent stylu tabeli krzyżowej (sticky wiersz/kolumna nagłówków,
  `overflow-x`) — bez nadpisywania siatki Foundation.
- Testy: `src/bpp/tests/` (§11).
- Newsfragment: `src/bpp/newsfragments/<slug>.feature.rst`.

**Bez migracji, bez zmian w modelach.** Wszystko na istniejących polach
`Rekord` / `Autorzy` (materializowane widoki `bpp_rekord_mat` /
`bpp_autorzy_mat`).

## 11. Testy

Jednostkowe `zbuduj_pivot()` + widok + (opcjonalnie) Playwright. Zestaw z
review:
1. **Inflacja/K1**: filtr mnożący (szukanie po jednostce/typie
   odpowiedzialności) × wymiar rekordowy (rok × charakter) → liczby równe
   płaskiej liście z `distinct` (rekord raz).
2. **Ordering-leak/K3**: sort „tytuł oryginalny"/„źródło" ustawiony w
   formularzu → pivot nadal poprawny (ordering wyczyszczony).
3. **Semantyka autorska/K2**: rekord z 3 autorami z **jednej** kliniki →
   komórka = **1 praca** (nie 3), Σ punkty = punkty rekordu **raz**;
   rekord z autorami w 2 klinikach → liczy się po 1 w każdej.
4. **Stabilność indeksów `report_type`**: zapisany `SearchForm` sprzed
   dodania pivota działa po dopisaniu typu na końcu.
5. **Wydział/NULL-korzeń** (gdy trafi do v1) — pominięty, bo Wydział → faza 2.
6. **NULL-kubły**: źródło/dyscyplina/autor NULL → etykieta „brak".
7. **Degeneracja**: kolumny=(brak) → płaska tabela; puste komórki; koszyk
   PK z 0 → „brak (0)".
8. **Eksport**: XLSX/CSV pivota = te same liczby co widok; >5000 rekordów
   źródłowych nie blokuje eksportu pivota.
9. **Multi-hosted**: ukryte statusy (`ukryte_statusy`,
   `mymultiseek.py:100`) respektowane w pivocie dla anonima.
10. **Reset `pivot_*`** przy przełączeniu raportu w live-iframe
    (dokumentujący zamierzone zachowanie).

Konwencje pytest projektu: funkcje, `@pytest.mark.django_db`,
`model_bakery.baker.make`, `-n auto`.

## 12. Poza zakresem v1 (faza 2 i dalej)

- **Szukaj → Zapytaniem (DjangoQL)** — ten sam pivot w `ZapytanieView`
  (`src/bpp/views/zapytanie.py:366`, przed `Paginator`); wspólny
  `zbuduj_pivot()`.
- **Drill-down** — klik w komórkę/wiersz → lista rekordów tej grupy.
- **„Wydział"** jako wymiar (Coalesce/Case dla NULL-korzenia, §13/W4).
- **„Uczciwe" punkty per-dyscyplina** ze slotów
  (`Cache_Punktacja_Dyscypliny.pkd`/`slot`).
- Cache pivota z kluczem obejmującym `pivot_*`.
- Eksport pivota dla anonima; trzeci wymiar / zagnieżdżanie; wykresy.

## 13. Otwarte kwestie (do rozstrzygnięcia w planie)

Większość pierwotnych ryzyk rozstrzygnięta po review:
- ~~report_type z GET vs sesji~~ → **sesja** (selektor formularza), tylko
  `pivot_*` z GET (§4).
- ~~limit 25000~~ → **omijany** dla pivota (§8); eksport omija cap 5000 (§9).
- ~~etykiety~~ → mapowanie w §6/§8.
- ~~widoczność per-uczelnia~~ → pivot ma **własny, stały** zestaw wymiarów,
  niezależny od `BppMultiseekVisibility` (inne przeznaczenie niż filtry).

Pozostaje:
1. **Miękkie ostrzeżenie** przy bardzo dużym zbiorze źródłowym dla pivota
   (np. > N rekordów) — czy dodawać próg ostrzegawczy, czy liczyć zawsze.
   Rekomendacja: liczyć zawsze, bez progu (GROUP BY tani); dołożyć próg
   dopiero jeśli w praktyce zaboli.
2. **Puste komórki**: blank (rekomendacja) — potwierdzić w partialu.
3. **DOCX/HTML eksport pivota** — robić w v1 (jeśli tanie) czy tylko
   XLSX/CSV. Rekomendacja: XLSX+CSV w v1, reszta faza 2.

## 14. Podsumowanie nakładu

Po review: **średni-duży** (pierwotne „średni" zaniżone). Szkielet
(wymiary rekordowe + Count + partial) jest średni; ciężar dokłada:
(a) poprawna agregacja przy wymiarach autorskich i filtrach mnożących —
hybryda A/B (§8) zamiast „jednego GROUP BY"; (b) restrukturyzacja
`common-results.html` wokół gate'u 25000 i paginacji; (c) pogodzenie
eksportu z kontraktem DANE/DOKUMENT + cap 5000. Zero migracji, zero zmian
modeli. Faza 2 (DjangoQL + drill-down + Wydział + slot-based punkty) —
osobno.
