# Faza 02 — inwentaryzacja widoków czytających tabele publikacji

> Wykonana **2026-08-07, na starcie fazy 02**, zanim powstała jakakolwiek
> migracja — dokładnie tak, jak nakazuje handoff (§2) i ostrzeżenie (a)
> w planie fazy 02. Faza 01 odkrywała takich winowajców pojedynczo, przez
> awarie; ten dokument jest wynikiem jednego przebiegu, trwającego 19 sekund.

## Metoda

Kanarek katalogowy fazy 01 (`src/bpp/tests/test_soft_delete/
test_kanarek_katalogowy.py`) eksportuje `znajdz_winowajcow(cur, tabele=...)`
przyjmujące **dowolną** listę tabel. Dzięki temu dało się uzyskać pełną listę
winowajców fazy 02 **bez** modyfikowania stałej `TABELE_SOFT_DELETE`, czyli bez
commitowania czerwonego testu na starcie gałęzi.

Wywołanie: `TABELE_SOFT_DELETE + _TABELE_PUBLIKACJI_FAZA_02` (8 tabel) na
żywym katalogu Postgresa (testcontainer: baseline + wszystkie migracje).

**Źródłem prawdy jest `pg_depend` na poziomie kolumny, nie tekst SQL-a.** To
istotne: analiza tekstowa `baseline.sql` przemilczałaby część widoków (baseline
jest snapshotem sprzed części migracji), a matcher substringowy dawał fałszywą
zieleń tam, gdzie widok dziedziczył słowo `deleted_at` z JOIN-a po *innej*
tabeli.

## Wynik: 15 par (widok, tabela), 15 unikalnych widoków

### Kategoria A — widoki rdzenia rekordu (5) → Task 2b

Bez filtra publikacja nie zniknie z `bpp_rekord_mat`, czyli z całego serwisu.

- `bpp_wydawnictwo_ciagle_view`
- `bpp_wydawnictwo_zwarte_view`
- `bpp_patent_view`
- `bpp_praca_doktorska_view`
- `bpp_praca_habilitacyjna_view`

### Kategoria B — widoki autorstw bez through-modelu (2) → Task 2b

Autor leży na wierszu publikacji, więc filtr jest tu „po własnej kolumnie".

- `bpp_praca_doktorska_autorzy`
- `bpp_praca_habilitacyjna_autorzy`

### Kategoria C — sumy (5) → **Task 2d (NOWY — brak w tabeli zadań planu)**

Plan miał dla nich wyłącznie ostrzeżenie (c) „sprawdź, czy wymagają poprawki".
Sprawdzone: **wymagają, wszystkie pięć.** Faza 01 poprawiła w tych widokach
wyłącznie wymiar *autora* (migracja `0495`); wymiar *publikacji* nadal
przecieka.

- `bpp_nowe_sumy_wydawnictwo_ciagle_view`
- `bpp_nowe_sumy_wydawnictwo_zwarte_view`
- `bpp_nowe_sumy_patent_view`
- `bpp_nowe_sumy_praca_doktorska_view`
- `bpp_nowe_sumy_praca_habilitacyjna_view`

⚠️ To są widoki **agregujące** — obowiązuje w nich pułapka z handoffu §3.2:
warunek `deleted_at IS NULL` w `WHERE`/`ON` degeneruje `LEFT JOIN` do `INNER
JOIN`. Właściwy wzorzec to `agregat(...) FILTER (WHERE ... deleted_at IS
NULL)`. Sprawdzić **każdy** agregat, nie tylko `count` (`sum`, `min`, `max`,
`array_agg`, `string_agg`, `bool_*`).

### Kategoria D — rozbieżności dyscyplin (1) → **Task 2d**

- `rozbieznosci_dyscyplin_rozbieznoscizrodelview`

Analogicznie do C: faza 01 poprawiła wymiar autora (`rozbieznosci_dyscyplin/
0022`), wymiar publikacji został.

### Kategoria E — kronika (2) → zadanie „Sprzątanie `bpp_kronika_*`"

- `bpp_kronika_praca_doktorska_view`
- `bpp_kronika_praca_habilitacyjna_view`

Dokładnie te dwa, których żywotności — jak zapowiadał handoff §3.4 — **nikt
jeszcze nie zweryfikował**. Pozostałe trzy z rodziny (`wydawnictwo_ciagle`,
`wydawnictwo_zwarte`, `patent`) nie pojawiają się na liście tylko dlatego, że
siedzą w `WYJATKI` jako zweryfikowanie martwe.

## Wynik negatywny, który też jest wynikiem

**Zero winowajców wśród trzech tabel `*_autor` fazy 01**
(`bpp_wydawnictwo_ciagle_autor`, `bpp_wydawnictwo_zwarte_autor`,
`bpp_patent_autor`) — suma par per tabela (2+4+4+3+2) wyczerpuje wszystkie 15,
więc dla tabel fazy 01 nie ma ani jednej. DDL fazy 01 trzyma się na żywym
katalogu.

## Wniosek dla planu

Tabela kolejności wykonania w planie fazy 02 dostaje **jedno zadanie więcej**:

| # | Task | Źródło |
|---|---|---|
| … | **Task 2d — sumy + rozbieżności (6 widoków)** | ta inwentaryzacja; w planie tylko jako ostrzeżenie (c), bez zadania |

Zakres Taska 2b jest potwierdzony jako dokładnie 7 widoków (5 rdzenia + 2
autorstw), a nie „5 plus może coś jeszcze".
