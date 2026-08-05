# Statystyki importów na liście `/import_polon/dane/`

Data: 2026-08-03
Status: zaakceptowany projekt po self-review, gotowy do implementacji

## Problem

Strona `/import_polon/dane/` („Ostatnio importowane dane") renderuje listę
importów jako `<ul>` z jednym zdaniem na import
(`src/import_polon/templates/import_polon/importplikupolon_list.html:19-28`):

```
plik protected/import_polon/rozszerzone_zestawienie_pracownikow_podmiotu_na_dzien_wygenerowania_raportu_2026-01-15.xlsx:
import utworzono 15 stycznia 2026 09:12, ukończono 15 stycznia 2026 09:14, zakończono pomyślnie
```

Trzy wady:

1. Prefiks `protected/import_polon/` to szczegół implementacyjny `upload_to` —
   nie niesie informacji dla użytkownika, a zjada szerokość wiersza.
2. Nazwa pliku z POLON-u („rozszerzone zestawienie pracowników podmiotu na
   dzień wygenerowania raportu…") jest tak długa, że część odróżniająca
   kolejne importy — data na końcu — ginie z pola widzenia.
3. Nie widać nic o zawartości importu. Żeby dowiedzieć się, ilu autorów plik
   obejmował i ile zmian wprowadził, trzeba wejść w każdy import osobno. Nie
   widać też roku importu (`ImportPlikuPolon.rok`), który rozstrzyga, których
   wpisów `Autor_Dyscyplina` import dotyczy.

## Zakres

Wyłącznie lista importów POLON (`/import_polon/dane/`). Lista importów
absencji (`/import_polon/absencje/`) pozostaje bez zmian — świadoma decyzja,
nie przeoczenie.

## Cel

Zamienić listę na tabelę pokazującą per import: skróconą nazwę pliku, rok,
status i tryb, oraz sześć liczb opisujących zawartość i skutek importu.

## Kluczowe odkrycie: część liczb nie jest odtwarzalna z bazy

`WierszImportuPlikuPolon` nie jest wiernym odbiciem pliku. W
`src/import_polon/core/import_polon.py:548-549` jest:

```python
if autor is None and parent_model.ukryj_niezmatchowanych_autorow:
    continue
```

Przy domyślnym `ukryj_niezmatchowanych_autorow=True` wiersz z niedopasowanym
autorem nie trafia do bazy w ogóle. Zatem `get_details_set().count()` ≠ liczba
wierszy w pliku, a różnicy nie da się odzyskać po zakończeniu importu.

Wniosek: liczby muszą być zapamiętane w trakcie importu, nie liczone przy
wyświetlaniu listy. To zresztą korzystne wydajnościowo — metryka
`do_odpiecia` to `autorzy_niezmatchowani()`, czyli `Autor_Dyscyplina` ×
`kiedykolwiek_zatrudnieni()` × `annotate(Count(prace))`. Liczona na żywo dla
10 importów oznaczałaby 10 ciężkich zapytań przy każdym wejściu na stronę.

## Pułapka: dwa różne komunikaty „bez zmian"

Kuszące jest policzenie zmian zapytaniem
`exclude(rezultat__startswith="W BPP jest identycznie jak w XLSX")` — tak
działa filtr „pokaż tylko różnice" w
`src/import_polon/views/plik_polon.py:197-199`. Dla statystyk to nie wystarczy,
i to z dwóch niezależnych powodów.

**Powód pierwszy — ORCID doklejany po sentinelu.** `_sync_autor_dyscyplina`
dokłada sentinel w `core/import_polon.py:431`, ale główna pętla dokłada potem
operacje ORCID (`core/import_polon.py:597-598`):

```python
orcid_ops = _update_autor_orcid(autor, orcid, parent_model)
ops.extend(orcid_ops)
rezultat = ", ".join(ops)
```

Wiersz, który realnie ustawił autorowi ORCID, ma
`rezultat == "W BPP jest identycznie jak w XLSX, Ustawiam ORCID. "` — czyli
zaczyna się od sentinela, a mimo to jest zmianą.

**Powód drugi — sentinel ma wariant z sufiksem.** W `core/import_polon.py:253`
(gałąź „autor nie ma wpisu za ten rok, a plik nie niesie dyscyplin"):

```python
ops.append("W BPP jest identycznie jak w XLSX (brak danych o dyscyplinach).")
```

To również „bez zmian", ale tekst jest inny. Naiwne `op != SENTINEL`
policzyłoby taki wiersz jako zmianę i systematycznie zawyżało metrykę.

**Rozwiązanie.** Jawny zbiór komunikatów oznaczających brak zmian, sprawdzany
przez dokładne dopasowanie — nie przez `startswith`:

```python
KOMUNIKAT_BEZ_ZMIAN = "W BPP jest identycznie jak w XLSX"
KOMUNIKAT_BEZ_ZMIAN_BRAK_DYSCYPLIN = (
    f"{KOMUNIKAT_BEZ_ZMIAN} (brak danych o dyscyplinach)."
)
KOMUNIKATY_BEZ_ZMIAN = frozenset(
    {KOMUNIKAT_BEZ_ZMIAN, KOMUNIKAT_BEZ_ZMIAN_BRAK_DYSCYPLIN}
)

zmieniono = any(op not in KOMUNIKATY_BEZ_ZMIAN for op in ops)
```

`startswith` byłby tą samą krchą klasą rozwiązania, co pierwotny błąd:
działałby przypadkiem, dopóki ktoś nie doda trzeciego komunikatu zaczynającego
się tak samo, ale znaczącego zmianę. Zbiór dokładnych dopasowań **wymusza**
rejestrację każdego nowego komunikatu „bez zmian" — nowy tekst spoza zbioru
domyślnie liczy się jako zmiana, co jest bezpieczną stroną pomyłki.

## Architektura

### 1. Stałe komunikatów

Tekst sentinela żyje dziś w trzech miejscach niezależnie
(`core/import_polon.py:253`, `core/import_polon.py:431`,
`views/plik_polon.py:198`). Wyciągamy stałe do `core/import_polon.py`,
budując wariant z sufiksem z bazowego przez f-string, i importujemy
`KOMUNIKAT_BEZ_ZMIAN` w widoku (filtr `startswith` w widoku pozostaje
poprawny — oba komunikaty zaczynają się od bazowego).

To celowana poprawka w obrębie zmienianego obszaru, nie refaktor przy okazji:
bez niej statystyki dołożyłyby czwartą kopię tego samego napisu.

### 1a. Ujednolicenie filtru „pokaż tylko różnice" (wynik self-review PR-a)

Filtr w `views/plik_polon.py` wycinał wiersze przez
`exclude(rezultat__startswith=KOMUNIKAT_BEZ_ZMIAN)`. Po dołożeniu licznika
„zmian" obie strony zaczęłyby sobie przeczyć: wiersz ustawiający wyłącznie
ORCID jest liczony jako zmiana (bo `ops` zawiera operację ORCID), ale jego
`rezultat` zaczyna się od sentinela — więc filtr by go **ukrył**. Import
ustawiający ORCID trzem autorom pokazywałby na liście „zmian: 3", a po
wejściu w szczegóły i włączeniu filtru — zero wierszy.

Filtr przechodzi więc na dokładne dopasowanie
`exclude(rezultat__in=KOMUNIKATY_BEZ_ZMIAN)`, czyli tę samą semantykę, co
licznik. Skutek uboczny: to naprawia istniejącą wadę — zmiany samego ORCID-a
były dotąd niewidoczne w „pokaż tylko różnice". Filtr nie miał żadnego
pokrycia testowego; dostaje dwa testy (wiersz ORCID-owy widoczny, wiersz bez
zmian nadal ukryty).

### 2. Statystyki jako podział zupełny i rozłączny

`analyze_file_import_polon()` prowadzi licznik inkrementowany w tych samych
gałęziach, które już decydują o losie wiersza, i zwraca słownik (dziś funkcja
nie ma `return`, więc zwraca `None`).

Rdzeniem projektu jest **partycja**: każdy wiersz pliku wpada do dokładnie
jednego z sześciu koszyków, a ich suma równa się `wierszy_w_pliku`. To nie
jest kosmetyka — daje asercję możliwą do sprawdzenia w teście, która wychwyci
każdą przyszłą gałąź `continue` dodaną bez aktualizacji liczników.

| Koszyk | Kiedy | Miejsce w kodzie |
|---|---|---|
| `odrzuconych_zatrudnienie` | `ZATRUDNIENIE` nie zaczyna się od nazwy uczelni | `core/import_polon.py:497-509` |
| `odrzuconych_obca_uczelnia` | dopasowany autor należy do innej uczelni | `core/import_polon.py:530-545` |
| `ukrytych_niedopasowanych` | autor niedopasowany + `ukryj_niezmatchowanych_autorow` | `core/import_polon.py:548-549` |
| `z_bledem` | `bledy` niepuste → nic nie synchronizowano | `core/import_polon.py:578-579` |
| `ze_zmianami` | brak `bledy`, `ops` zawiera cokolwiek spoza `KOMUNIKATY_BEZ_ZMIAN` | `core/import_polon.py:580-600` |
| `bez_zmian` | brak `bledy`, wszystkie `ops` w `KOMUNIKATY_BEZ_ZMIAN` | jw. |

Partycja jest szczelna, bo w pętli istnieje dokładnie ta rozłączna kaskada:
trzy `continue`, a potem gałąź `if bledy: … else: …` — wiersz albo ma błędy
(i wtedy nic nie synchronizuje), albo produkuje `ops`.

Ponadto dwa liczniki **ortogonalne** do partycji (celowo przecinające
koszyki, więc nie sumujące się z nimi):

| Licznik | Znaczenie |
|---|---|
| `dopasowanych` | `matchuj_autora()` znalazł Autora — niezależnie od tego, czy wiersz skończył w `z_bledem`, `ze_zmianami` czy `bez_zmian` |
| `do_odpiecia` | `parent_model.autorzy_niezmatchowani().count()`, liczone raz po pętli |

### 3. Wartości pochodne i świadome ustalenia

- **`z_uczelni`** nie jest przechowywane — liczone jako
  `wierszy_w_pliku − odrzuconych_zatrudnienie` we właściwości
  `ImportPlikuPolon.statystyki` (nie w szablonie: szablon Django nie ma
  arytmetyki, a wartość pochodna utrwalona obok składników by się z nimi
  rozjechała).
- **Przy `ignoruj_miejsce_pracy=True`** `odrzuconych_zatrudnienie` wynosi
  `None`, a kolumna „z uczelni" pokazuje **„n/d"**. Walidacja `ZATRUDNIENIE`
  była wtedy wyłączona (`core/import_polon.py:492`), więc każda liczba w tej
  kolumnie byłaby zmyślona. Lepiej powiedzieć „nie wiem" niż podać
  `wierszy_w_pliku` udające pomiar.
- **`ze_zmianami` w trybie podglądu** (`zapisz_zmiany_do_bazy=False`) znaczy
  „ile zmian **zostałoby** wprowadzonych". Ta sama liczba, inne znaczenie —
  rozróżnienie niesie badge trybu w kolumnie statusu oraz `title=` na
  nagłówku kolumny.
- **Kolumny się nie sumują.** `dopasowanych` przecina `z_bledem`,
  `ze_zmianami` i `bez_zmian`; `w pliku` obejmuje wiersze, których w bazie nie
  ma. Każdy nagłówek liczbowy dostaje `title=` z jednozdaniową definicją —
  bez tego użytkownik będzie próbował te liczby dodawać.
- **`do_odpiecia` to migawka z chwili importu**, podczas gdy
  `ImportPolonResultsView` liczy `unmatched_count` na żywo
  (`views/plik_polon.py:231-234`). Po późniejszych zmianach w bazie lista i
  strona wyników mogą pokazać różne wartości. Akceptujemy to świadomie:
  liczenie na żywo dla 10 importów kosztuje 10 ciężkich zapytań na każde
  wejście na listę, a liczba na liście ma odpowiadać na pytanie „co ten
  import zastał", nie „jaki jest stan teraz".

### 4. Zapis do `result_context`

Bez migracji — `LiveOperation.result_context` to istniejące pole `JSONField`
(`liveops/models.py:47`), zapisywane przez `p.result()`. Zweryfikowane:
`p.result()` **nadpisuje** `result_context` w całości, więc musi dostać
komplet danych w jednym wywołaniu.

`_uruchom_import()` (`src/import_polon/models.py:53-73`) jest współdzielony z
importem absencji, którego rdzeń nadal nie zwraca nic — scalanie musi być
odporne na `None`:

```python
def _uruchom_import(parent, p, analyze):
    try:
        wynik = analyze(parent.plik.path, parent, p)
    except Exception:
        ...  # bez zmian
    p.result({"total": parent.get_details_set().count(), **(wynik or {})})
```

Kształt — statystyki **zagnieżdżone** pod jednym kluczem, żeby nie mieszały
się z polami wyniku liveops:

```python
{"total": 1156,
 "statystyki": {"wierszy_w_pliku": 1284,
                "odrzuconych_zatrudnienie": 94,
                "odrzuconych_obca_uczelnia": 0,
                "ukrytych_niedopasowanych": 0,
                "z_bledem": 34,
                "ze_zmianami": 87,
                "bez_zmian": 1069,
                "dopasowanych": 1156,
                "do_odpiecia": 12}}
```

(94 + 0 + 0 + 34 + 87 + 1069 = 1284 — partycja się domyka.)

`analyze_file_import_polon` zwraca `{"statystyki": {...}}`, `_uruchom_import`
tylko scala. Klucz `total` zostaje nietknięty.

### 5. Skracanie nazwy pliku

Czysta funkcja w `src/import_polon/utils.py`:

```python
def skroc_nazwe_pliku(sciezka, limit=36):
    """'protected/import_polon/rozszerzone_….xlsx' → 'rozszerzone_zestawie…_2026-01-15.xlsx'"""
```

- Katalog obcinany przez `os.path.basename`, nie przez usunięcie
  zahardkodowanego `protected/import_polon/` — działa dla dowolnego
  `upload_to` i nie psuje się przy jego zmianie.
- Wycinany jest **środek**, nie koniec: ogon nazwy zawiera datę i rozszerzenie,
  czyli jedyną część odróżniającą kolejne raporty POLON.
- Nazwa nie dłuższa niż `limit` wraca bez zmian (brak `…`).
- Pusta nazwa (`plik` niewypełniony) wraca jako pusty napis.
- Ogon składany jawnym warunkiem, nie ujemnym indeksem: `nazwa[-0:]` zwraca
  w Pythonie **cały** napis, więc przy bardzo małym limicie naiwna wersja
  oddawała wynik dłuższy od wejścia (złapane w self-review PR-a).
- Funkcja czysta, bez Django — testowalna bez bazy.

Model `ImportPlikuPolon` dostaje dwie właściwości:

- `nazwa_pliku_skrocona` → `skroc_nazwe_pliku(self.plik.name)`,
- `statystyki` → `(self.result_context or {}).get("statystyki")`, żeby szablon
  nie łańcuchował `result_context.statystyki` po polu, które bywa `None`.

### 6. Szablon

`importplikupolon_list.html`: `<ul>` → `<table class="compact-table">`.

Klasa `compact-table` jest już definiowana w tym appie inline
(`wierszimportuplikupolon_list.html:16-39`) — nowy szablon idzie tą samą
konwencją. Nie dotykamy SCSS-a, więc `grunt build` nie jest potrzebny.

```
                                    │        z pliku POLON         │  wynik
Plik                     Rok Status │  w pliku  z uczelni  dopasow.│ zmian  błędów  do odpięcia
────────────────────────────────────┼──────────────────────────────┼──────────────────────────
rozszerzone_zestaw…15.xlsx  2025  ✓ │   1 284      1 190     1 156 │    87      34          12
  utworzono 15.01 09:12               podgląd
```

- **Plik** — `nazwa_pliku_skrocona` jako link do `get_absolute_url`, `title` z
  pełną ścieżką (`object.plik.name`); badge uczelni gdy `object.uczelnia` (jak
  dziś, `importplikupolon_list.html:22`); pod spodem daty utworzenia i
  ukończenia mniejszym drukiem.
- **Rok** — `object.rok`; nowa informacja, dziś nigdzie na liście niewidoczna.
- **Status** — badge `w trakcie` / `✓ pomyślnie` / `✗ błąd` z `finished_on` +
  `finished_successfully`, pod nim badge trybu `podgląd` (secondary) /
  `zapisany do bazy` (success).
- Sześć kolumn liczbowych, każda z `title=` (patrz „kolumny się nie sumują").
- Ikony: Foundation-Icons (`fi-*`), zgodnie z regułą dla frontendu publicznego.
- Komentarze Django: każdy `{# … #}` w jednej linii.

**Trzy różne stany pustki**, rozróżniane jawnie:

| Stan | Warunek w szablonie | Wyświetlenie |
|---|---|---|
| brak statystyk (import stary, w trakcie, anulowany lub zakończony błędem) | `{% if object.statystyki %}` fałsz | `—` we wszystkich kolumnach |
| `odrzuconych_zatrudnienie is None` (walidacja wyłączona) | `\|default_if_none:"n/d"` | `n/d` w kolumnie „z uczelni" |
| liczba zerowa | — | `0` |

`default_if_none` jest tu istotny: zwykły `default` potraktowałby `0` jak brak
wartości i pokazał `n/d` zamiast prawdziwego zera.

Tabela w `<div style="overflow-x:auto">` — dziewięć kolumn nie zmieści się na
wąskim ekranie. Klas gridu Foundation (`medium-*`, `large-*`) nie ruszamy.

Zachowujemy istniejące przekierowanie na `./nowy`, gdy lista jest pusta
(`importplikupolon_list.html:30-34`).

## Zgodność wsteczna

- Brak migracji — wykorzystujemy istniejące `JSONField`.
- Stare importy renderują się z `—` w kolumnach liczbowych.
- Restart importu oraz akcja „zapisz do bazy" idą przez ten sam
  `analyze_file_import_polon`, więc przeliczają statystyki bez dodatkowej
  ścieżki kodu.
- Import absencji: `analyze_file_import_absencji` nadal zwraca `None`, więc
  jego `result_context` pozostaje dokładnie `{"total": n}`.

## Testy

Konwencja repo: pytest, funkcje bez klas, `model_bakery.baker.make`,
`@pytest.mark.django_db` tam, gdzie baza jest potrzebna.

**`src/import_polon/tests/test_liveops.py` — aktualizacja istniejącego testu.**
`test_run_finalizuje_polon` (linia 40) asertuje dziś
`imp.result_context == {"total": n}` — ścisła równość, którą ta zmiana łamie.
Zmieniamy na sprawdzenie `result_context["total"] == n` plus obecności i
kształtu `result_context["statystyki"]`. `test_run_finalizuje_absencji`
(linia 55) zostaje bez zmian — i to jest celowe: pilnuje, że import absencji
nie dostał statystyk przypadkiem.

**`src/import_polon/tests/test_utils.py` — rozszerzenie istniejącego pliku**
(zawiera już testy `read_excel_or_csv_dataframe_guess_encoding`). Bez bazy:
- nazwa krótsza niż limit wraca bez zmian, bez `…`,
- nazwa dokładnie na granicy limitu wraca bez zmian,
- nazwa dłuższa niż limit zachowuje rozszerzenie i ogon z datą oraz mieści się
  w limicie,
- ścieżka z katalogiem gubi katalog,
- pusty napis wraca jako pusty napis.

**`src/import_polon/tests/test_import_polon_core.py`:**
- partycja się domyka: suma sześciu koszyków `== wierszy_w_pliku`,
- **regresja na sentinel z sufiksem**: wiersz kończący się komunikatem
  `KOMUNIKAT_BEZ_ZMIAN_BRAK_DYSCYPLIN` liczy się do `bez_zmian`, nie do
  `ze_zmianami`,
- **regresja na pułapkę ORCID**: wiersz zmieniający wyłącznie ORCID liczy się
  do `ze_zmianami`, mimo że jego `rezultat` zaczyna się od
  `KOMUNIKAT_BEZ_ZMIAN`,
- `ignoruj_miejsce_pracy=True` → `odrzuconych_zatrudnienie is None`,
- wiersz odrzucony przez walidację `ZATRUDNIENIE` wchodzi do
  `odrzuconych_zatrudnienie`, a nie do `z_bledem`,
- `ukryj_niezmatchowanych_autorow=True`: `wierszy_w_pliku` > liczba
  `WierszImportuPlikuPolon`, a różnicę widać w `ukrytych_niedopasowanych`,
- nakładanie się liczników ortogonalnych: wiersz z dopasowanym autorem, ale
  błędem dyscypliny, wchodzi jednocześnie do `dopasowanych` i `z_bledem`,
- plik o zerowej liczbie wierszy danych: same zera, `do_odpiecia` policzone,
- plik o błędnym formacie: wyjątek przed pętlą, `p.result` się nie woła,
  `result_context` pozostaje `None` (statystyki nie powstają).

**Test widoku `PokazImporty`:**
- lista renderuje się dla importu bez `statystyki` (stary import) i pokazuje `—`,
- lista renderuje się dla importu ze `statystyki` i pokazuje liczby,
- `odrzuconych_zatrudnienie=None` → „n/d"; `0` → `0`, nie „n/d",
- skrócona nazwa pliku w treści, pełna ścieżka w `title`.

## Newsfragment

`src/bpp/newsfragments/import-polon-statystyki-listy.feature.rst` — lista
importów POLON pokazuje teraz tabelę ze statystykami i skróconą nazwą pliku.

## Poza zakresem

- Lista importów absencji — bez zmian.
- Sortowanie i filtrowanie tabeli importów — nie było o to prośby, a lista
  jest ograniczona do 10 pozycji (`PokazImporty.max_previous_ops`).
- Doliczanie statystyk dla starych importów wstecz — pokazują `—`.
- Rozbicie zmian na typy operacji (osobno dyscyplina / procent / ORCID /
  rodzaj autora) — odrzucone jako zbyt drobiazgowe na listę zbiorczą.
