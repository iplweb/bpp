# Import pracowników — synchronizacja dat zatrudnienia (`data_od` / `data_do`)

**Data:** 2026-07-13
**Moduł:** `src/import_pracownikow/`
**Bazuje na:** `origin/dev` po scaleniu PR #559 (dwuwierszowa karta rekordu +
rejestr `POLA_ROZNIC` / `stany_pol_snapshot`).
**Review:** przeszedł review Fable (2026-07-13) — poprawki naniesione (analyze.py,
N+1, sygnał świeżego AJ, `MultipleObjectsReturned`, czerwone testy).

---

## 1. Kontekst i cel

Plik importu pracowników niesie dwie kolumny dat zatrudnienia:

| Kolumna w pliku | Klucz znormalizowany | Pole `Autor_Jednostka` | Znaczenie |
|---|---|---|---|
| „Data zatrudnienia" | `data_zatrudnienia` | `rozpoczal_prace` | data **od** |
| „Data końca zatrudnienia" | `data_końca_zatrudnienia` | `zakonczyl_prace` | data **do** |

Daty **już** się synchronizują w integracji (`_integruj_daty_aj`), ale:

1. **są niewidoczne** — porównywarka „plik vs baza" (karta rekordu, §9)
   pokazuje e-mail / tytuł / stopień / funkcję / stanowisko, ale **nie daty**;
2. **różnica daty od jest cicho ignorowana** — `_check_autor_jednostka_needs_update`
   reaguje na „data od" tylko gdy baza ma `NULL`; gdy plik niesie **inną** datę
   od niż baza, operator tego **nie widzi**;
3. **brak semantyki okresu** — różna data od to (wg `unique_together`) inny
   rekord zatrudnienia, ale import traktuje `(autor, jednostka)` jako jeden AJ.

**Cel:** uwidocznić obie daty w porównywarce i domknąć logikę synchronizacji
wokół pojęcia **okresu zatrudnienia identyfikowanego przez „data od"**, wraz z
tworzeniem **nowego okresu** (nowy `Autor_Jednostka`), gdy plik niesie inną
datę od niż baza.

---

## 2. Model semantyczny — „data od" = tożsamość okresu

`Autor_Jednostka` ma `unique_together = (autor, jednostka, rozpoczal_prace)`.
Zatem **okres zatrudnienia** jest jednoznacznie identyfikowany trójką
`(autor, jednostka, rozpoczal_prace)`. Wartość „data od" z pliku wybiera, o
**który okres** chodzi:

- ta sama „data od" → ten sam okres → synchronizujemy do niego „data do";
- inna „data od" → inny (nowy) okres → tworzymy nowy `Autor_Jednostka`.

To spłaca istniejący dług: dwie ścieżki wyboru AJ zakładają **jeden** AJ na parę
`(autor, jednostka)`:

- `pewnosc.odtworz_autor_jednostka` — `AJ.filter(autor, jednostka).first()`
  (naiwny `.first()`);
- `analyze._wybierz_autor_jednostka` — już **deterministyczny** (aktywny →
  najświeższy `rozpoczal`, #508 F6), ale nadal ignoruje `plik_od`.

Po zmianie obie ścieżki idą przez **jeden resolver** (§7), który przy „data od"
z wartością rozstrzyga po **pełnym** kluczu unikalności, a przy pustej „data od"
zachowuje deterministyczny wybór aktywny→najświeższy (absorbuje semantykę
`_wybierz_autor_jednostka`).

**Uwaga o `rozpoczal_prace = NULL`:** Postgres traktuje `NULL`-e jako **różne** w
unikalnym indeksie, a Django pomija walidację `unique_together`, gdy któraś
wartość jest `None`. Dwa AJ `(A, J, NULL)` mogą więc legalnie istnieć (dane z
admina / legacy). Dlatego **nie** twierdzimy „pełny klucz nie trafi na >1
wiersz" dla `None` — lookup po `rozpoczal_prace=None` używa
`order_by("pk").first()` zamiast `get_or_create` (§8.3), a przy tworzeniu
nowego AJ z pustym `plik_od` od razu stemplujemy fallback (konkretna data,
nie `NULL`), więc `None` w kluczu tworzonego rekordu nie występuje.

---

## 3. Tabela decyzyjna — „data od"

Dla wiersza: autor **A**, jednostka **J**, `plik_od` (wartość / puste),
`plik_do` (wartość / puste). „Puste `plik_od`" = kolumny nie ma w pliku **lub**
komórka w tym wierszu jest pusta (rozróżnienie nieistotne — patrz §5).

| Stan bazy dla (A, J) | `plik_od` | Akcja na „data od" | Cel |
|---|---|---|---|
| brak AJ | wartość | utwórz AJ z `rozpoczal = plik_od` | **NOWY** |
| brak AJ | puste | utwórz AJ z `rozpoczal =` (fallback: data zmian → dziś) | **NOWY** |
| AJ istnieje, `rozpoczal = plik_od` | wartość | bez zmian (ten sam okres) | istniejący |
| AJ istnieje, `rozpoczal = NULL` | wartość | **wypełnij** `plik_od` (to samo, niedatowane) | istniejący |
| AJ istnieje, `rozpoczal ≠ plik_od` | wartość | pokaż różnicę + **utwórz NOWY okres** | **NOWY** |
| AJ istnieje | puste | **NIC NIE ZMIENIAJ** (`rozpoczal` zostaje jak jest, nawet `NULL`) | istniejący |

### „data do" (`zakonczyl_prace`)

Zawsze w obrębie **docelowego** okresu (wybranego wyżej):

- `plik_do` ma wartość, `cel.zakonczyl` **puste** → **wstaw** `plik_do`;
- `plik_do` ma wartość, `cel.zakonczyl` ma wartość → **NIE nadpisuj**; różnicę
  **pokaż** w porównywarce;
- `plik_do` puste → nic nie zmieniaj.

To zmiana względem obecnego zachowania (dziś „data do" = *nadpisz-gdy-różna*;
docelowo *wstaw-tylko-gdy-pusta*).

---

## 4. Precedencja daty przy STEMPLOWANIU pustej „data od"

Gdy stemplujemy pustą datę od (nowy AJ, albo istniejący AJ z `NULL` gdy
`plik_od` ma wartość):

```
rozpoczal = plik_od  →  parent.data_zmian_personalnych  →  timezone.localdate()  (dziś)
```

**Bez zmian** względem obecnego kodu. „Data od" z pliku zawsze wygrywa; globalna
„data zmian personalnych" jest tylko fallbackiem, gdy wiersz nie niesie własnej
daty; dziś to ostateczność.

---

## 5. Reguła „pustej kolumny / pustej komórki"

Kluczowe doprecyzowanie: **istniejącego AJ nie ruszamy, gdy `plik_od` jest
puste.** Nie ma znaczenia, czy kolumny „Data zatrudnienia" w pliku nie ma w
ogóle, czy jest, ale komórka pusta — oba przypadki znaczą „brak informacji o
dacie od dla tego wiersza" i oba dają **no-op** na istniejącym AJ (nie
stemplujemy `data zmian`/dziś na istniejącej dacie od, nie tworzymy nowego
okresu).

Fallback `data zmian → dziś` obowiązuje **wyłącznie** przy **tworzeniu nowego
AJ** (dopisanie autora do jednostki) — to udokumentowany sens pola „data zmian
personalnych". Dla istniejącego AJ pusty `plik_od` = zostaw `rozpoczal` bez
zmian (nawet gdy `NULL`).

**Decyzja P1 (POTWIERDZONA):** dla **nowego** AJ przy pustym `plik_od`
stosujemy fallback `data zmian → dziś` (nowe zatrudnienie potrzebuje daty
startu). Reguła „nic nie zmieniaj" dotyczy tylko *istniejących* AJ.

**Realizacja bez dwuznaczności (poprawka Fable):** rozróżnienie „świeży AJ" vs
„istniejący AJ z NULL" NIE opiera się na sygnale przekazywanym do
`_integruj_daty_aj` — zamiast tego **fallback stemplujemy w momencie
materializacji nowego AJ** (`_materializuj_diff`, §8.3). Dzięki temu:

- nowy AJ powstaje **od razu** z konkretną `rozpoczal_prace` (fallback albo
  `plik_od`), więc `_integruj_daty_aj` widzi już nie-`NULL` i no-opuje na dacie od;
- `_integruj_daty_aj` obsługuje na „data od" **wyłącznie** przypadek
  „istniejący AJ, `rozpoczal = NULL`, `plik_od` ma wartość → wypełnij"; brak
  gałęzi stemplującej fallback na istniejącym AJ (czyli reguła §5 wynika ze
  struktury kodu, nie z warunku);
- znika krucha zależność „fallback zadziała tylko, gdy recheck po materializacji
  odpali `integrate()`".

---

## 6. Dwie decyzje domyślne (POTWIERDZONE)

- **P2 (POTWIERDZONA) — stary okres NIE jest domykany automatycznie.** Gdy
  powstaje nowy okres (inna data od), stary `Autor_Jednostka` **zostaje otwarty**
  (bez `zakonczyl_prace`). Auto-domknięcie starego okresu
  (`zakonczyl = plik_od − 1`) to ryzyko korupcji historii afiliacji — poza
  zakresem (§14).
- **P3 (POTWIERDZONA) — nowy okres dziedziczy** funkcję / stanowisko / grupę
  pracowniczą / wymiar etatu z wiersza i (domyślnie, jak każdy zaimportowany
  wiersz) staje się **podstawowym miejscem pracy** — realizowane nie przez
  `defaults` `get_or_create`, tylko przez istniejącą ścieżkę
  recheck → `_integrate_autor_jednostka` (świeży AJ ma `podstawowe = None`, co
  wyzwala recheck; ta ścieżka ustawia P3-pola i primary). Bez dublowania logiki.

---

## 7. Resolver okresu — jedno źródło prawdy (+ wydajność)

Nowa funkcja (proponowana lokalizacja: `pewnosc.py`, obok
`odtworz_autor_jednostka`, albo nowy `okresy.py`):

```
rozwiaz_okres_zatrudnienia(autor, jednostka, plik_od, *, aj_lista=None) ->
    ("istniejacy", aj)               # dopasowany / niedatowany do wypełnienia
    | ("nowy", rozpoczal_prace|None) # utwórz nowy AJ z tą datą od (lub fallback)
```

**Jedno zapytanie (poprawka N+1 od Fable):** resolver pobiera listę okresów
`(A, J)` JEDNYM zapytaniem i rozstrzyga w Pythonie:

```
aj_lista = list(Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka))
```

Wołający, który już ma listę (albo prefetch z widoku), przekazuje ją przez
`aj_lista=` — resolver wtedy nie odpytuje bazy. Reguła (odpowiada tabeli §3):

```
jeśli plik_od ma wartość:
    exact = [aj for aj in aj_lista if aj.rozpoczal_prace == plik_od]  # ≤1 (unique)
    jeśli exact:                      -> ("istniejacy", exact[0])       # ten sam okres
    inaczej niedat = [aj for aj in aj_lista if aj.rozpoczal_prace is None]
        posortowane po pk            # determinizm przy >1 NULL (legacy)
        jeśli niedat:                 -> ("istniejacy", niedat[0])      # wypełnij plik_od
        inaczej:                      -> ("nowy", plik_od)              # NOWY okres
jeśli plik_od puste:
    aj = _wybierz_aktywny_najswiezszy(aj_lista)   # aktywny (zakonczyl IS NULL),
                                                  # remis → najświeższy rozpoczal
    jeśli aj:                         -> ("istniejacy", aj)             # NIE ruszaj daty od
    inaczej:                          -> ("nowy", None)                 # fallback data zmian → dziś
```

**Współdzielony wybór aktywny→najświeższy.** Gałąź „puste `plik_od`" absorbuje
semantykę `analyze._wybierz_autor_jednostka` (#508 F6). Wydzielamy **czystą**
funkcję `_wybierz_aktywny_najswiezszy(aj_lista)` (operuje na już pobranej
liście, zero zapytań); `_wybierz_autor_jednostka` **deleguje** do niej (albo
staje się cienką owijką pobierającą listę), więc jej testy
(`test_wybor_autor_jednostka.py`) zostają ważne bez migracji.

> **Klucz sortowania — parytet z SQL (poprawka N2).** Dziś
> `_wybierz_autor_jednostka` sortuje w SQL `order_by("-rozpoczal_prace")`, a
> Postgres przy `DESC` daje **NULLS FIRST** → AJ z `rozpoczal = NULL` jest
> traktowany jako „najświeższy". Czysta funkcja MUSI zachować ten parytet:
> naiwne `max`/`sorted(key=rozpoczal_prace)` rzuci `TypeError` przy `None`.
> Klucz: `key=lambda aj: (aj.zakonczyl_prace is None, aj.rozpoczal_prace is
> None, aj.rozpoczal_prace or date.min, aj.pk)` z `reverse` na odpowiednich
> osiach — tj. najpierw aktywny (`zakonczyl IS NULL`), potem `rozpoczal = NULL`
> jako największe, potem najświeższy `rozpoczal`, a na końcu **tie-break po
> `pk`** (SQL dziś go NIE gwarantuje → i tak wzmacniamy determinizm).

> **Kontrakt typu `plik_od` (poprawka N5).** Resolver przyjmuje **wyłącznie**
> `date | None`. Gdyby ścieżka podała ISO-string, `aj.rozpoczal_prace ==
> "2020-01-01"` jest zawsze `False` → **cichy fałszywy „nowy okres" + duplikat
> AJ**. Helper `_plik_od()` (patrz niżej) zwraca `date|None`, parsując przez
> `dane_bardziej_znormalizowane` (nie surowe `dane_znormalizowane`). W analizie
> (§8.1) — źródłem jest już sparsowany `date` z pipeline'u. Test §13: str na
> wejściu resolvera → asercja braku duplikatu.

**Memoizacja na wierszu (współdzielona podgląd↔integracja).** Wiersz cache'uje
wynik na instancji:

```
def _okres(self):
    if not hasattr(self, "_okres_cache"):
        self._okres_cache = rozwiaz_okres_zatrudnienia(
            self.autor, self.jednostka, self._plik_od(),
            aj_lista=self._aj_lista(),   # jednorazowe filter(autor, jednostka)
        )
    return self._okres_cache
```

gdzie `_plik_od()` zwraca `date|None` z `dane_bardziej_znormalizowane`
(kontrakt typu wyżej), a `_aj_lista()` robi jednorazowe
`list(AJ.filter(autor, jednostka))` na instancji.

Zarówno `porownaj_z_baza()` (§9.2), oba ekstraktory `_stan_data_od/_do` (§9.1),
jak i ścieżki analizy/`odtworz` czytają `_okres()` → **1 zapytanie o AJ /
wiersz** (zamiast ~6). Opcjonalnie (jeśli profil pokaże, że i to za dużo)
batch-prefetch w widoku: jedno zapytanie o AJ wszystkich (autor, jednostka)
strony → mapa wstrzyknięta do wierszy przez `aj_lista=`.

> **Inwalidacja memo przy zmianie autora/jednostki (poprawka N3).** Memo jest
> spójne dziś tylko dzięki niejawnemu niezmiennikowi „mutacja → `odtworz` →
> render". Punkty mutacji: `_zwiaz_autora_z_wierszem` (`row.autor = autor`,
> views.py) i `_podlacz_wiersze_do_jednostek` (`row.jednostka = jed`,
> integrate.py). Żeby niezmiennik był jawny: te dwa miejsca (oraz gałąź
> `jednostka_id is None`) **czyszczą `_okres_cache`** przez dedykowany helper
> (`_zapomnij_okres()`, nie goły `del`), zanim nastąpi ponowny odczyt. Test
> §13: odczyt `stany_pol()` przed i po zmianie autora daje różną decyzję.

---

## 8. Zmiany per plik/funkcja

### 8.1 `pipeline/analyze.py` — `_przetworz_wiersz` + `_wybierz_autor_jednostka` (GŁÓWNA ścieżka)

To jest **główna** ścieżka przypisania AJ (twardo dopasowana jednostka):
`_przetworz_wiersz` woła `_wybierz_autor_jednostka` i odkłada
`diff["autor_jednostka"]` dla nowych powiązań. Pominięcie jej = „nowy okres"
nigdy nie powstałby w standardowym flow (rozjazd z podglądem — anty-cel).

Zmiana: `_przetworz_wiersz` woła **resolver** zamiast bezpośrednio
`_wybierz_autor_jednostka`:

- `("istniejacy", aj)` → `row.autor_jednostka = aj` (jak dziś);
- `("nowy", rozpoczal)` → `row.autor_jednostka = None`, odkłada
  `diff["autor_jednostka"] = {"autor": …, "jednostka": …,
  "rozpoczal_prace": rozpoczal_iso_or_None, "nowy_okres": bool}` i ustawia
  `zmiany_potrzebne = True` (istniejąca gałąź `else` już to robi dla nowych
  powiązań — rozszerzamy o `rozpoczal_prace` + `nowy_okres`).

`"nowy_okres": True` **tylko** gdy istnieje jakiś AJ dla (A, J) (czyli tworzymy
DODATKOWY okres obok istniejącego); dla „pierwszego powiązania" (brak
jakiegokolwiek AJ) → `False` — potrzebne do licznika/opisu (§10).

### 8.2 `pewnosc.py` — `odtworz_autor_jednostka(row, autor)`

Ścieżka poboczna (zmiana autora w podglądzie / nowy autor / odroczona jednostka).
Zamiast `AJ.filter(autor, jednostka).first()`:

- woła resolver (`plik_od` z `row.dane_bardziej_znormalizowane`);
- `("istniejacy", aj)` → `row.autor_jednostka = aj`; przelicza `zmiany_potrzebne`
  jak dziś (`bool(diff) or _check_autor_jednostka_needs_update()`);
- `("nowy", rozpoczal)` → `row.autor_jednostka = None`, odkłada
  `diff_do_utworzenia["autor_jednostka"]` (ten sam kształt co §8.1, z
  `nowy_okres`), `zmiany_potrzebne = True`.

**Guard odroczonej jednostki:** gdy `row.jednostka_id is None` (jednostka
odroczona/brak) — resolver się NIE woła; zachowanie jak dziś (brak podpięcia AJ).

`rozpoczal_prace` w diffie serializujemy jako ISO-string (JSON-safe) lub `None`.

### 8.3 `integrate.py` — `_materializuj_diff(row) -> created: bool`

Tworzenie AJ po **pełnym** kluczu, z fallbackiem dat i zwrotem `created`:

```
d = diff["autor_jednostka"]
rozpoczal = date.fromisoformat(d["rozpoczal_prace"]) if d.get("rozpoczal_prace") else None
if rozpoczal is None:
    # nowy AJ, pusty plik_od → fallback (P1): data zmian → dziś
    rozpoczal = row.parent.data_zmian_personalnych or timezone.localdate()
# rozpoczal ZAWSZE ma wartość dla nowego AJ (plik_od albo fallback) → brak None w kluczu
aj = (Autor_Jednostka.objects
      .filter(autor_id=d["autor"], jednostka_id=d["jednostka"], rozpoczal_prace=rozpoczal)
      .order_by("pk").first())
created = aj is None
if created:
    aj = Autor_Jednostka.objects.create(
        autor_id=d["autor"], jednostka_id=d["jednostka"], rozpoczal_prace=rozpoczal,
        funkcja=row.funkcja_autora, stanowisko=row.stanowisko_dydaktyczne,
    )
row.autor_jednostka = aj
return created
```

- **Nie** używamy `get_or_create` — `order_by("pk").first()` + jawny `create`
  jest deterministyczny i eliminuje `MultipleObjectsReturned` (choć przy
  konkretnej dacie `unique_together` i tak daje ≤1, to jednolita ścieżka).
- Stemplowanie fallbacku **tu** (nie w `_integruj_daty_aj`) realizuje P1 bez
  sygnału „świeży AJ" i bez zależności od recheck→integrate (§5).
- Weryfikacja przy implementacji: ścieżka `row.parent.data_zmian_personalnych`
  (analogicznie jak dziś `self.parent…` w `_integruj_daty_aj`).
- **Przewód `created` (poprawka N1):** `_materializuj_diff` zwraca `created`,
  ale dziś jego jedyny wołający `_integruj_wiersz` zwraca `None`, a pętla
  `integruj` zwrot ignoruje. Trzeba **przeprowadzić** sygnał: `_integruj_wiersz`
  zwraca `created` (i `nowy_okres` — patrz §10), a pętla `integruj` je sumuje.
  Wczesny return na guardzie `log_zmian is not None` (restart) zwraca `False` —
  licznik liczy tylko pracę bieżącego przebiegu.

### 8.4 `models.py` — `_integruj_daty_aj(aj, dane)`

- **„data od":** stempluj `aj.rozpoczal_prace` **tylko** gdy
  `aj.rozpoczal_prace is None` **oraz** wiersz niesie datę
  (`dane.get("data_zatrudnienia")`) — to przypadek „wypełnienie NULL" dla
  **istniejącego** AJ (§3 wiersz 4). Świeży AJ ma już `rozpoczal` (§8.3), więc
  ta gałąź go nie dotyczy. Istniejący AJ + pusty `plik_od` → **nie ruszaj**
  (brak gałęzi — reguła §5). Ten sam okres (`rozpoczal == plik_od`) → równe,
  brak zmiany.
- **„data do":** `if plik_do and aj.zakonczyl_prace is None: aj.zakonczyl_prace =
  plik_do` (wstaw-gdy-pusta). Usuwamy gałąź *nadpisz-gdy-różna*.
- **Walidacja** `rozpoczal < zakonczyl` (istniejąca w `_integrate_autor_jednostka`,
  → `BPPDatabaseError`) obejmuje nowe okresy i wstawioną „data do" — bez zmian.

### 8.5 `models.py` — `_check_autor_jednostka_needs_update(dane)`

- **„data od": bez zmian** — obecny warunek („`data_zatrudnienia` niepuste
  **oraz** `aj.rozpoczal_prace is None`" = wypełnienie NULL) zostaje. Przypadek
  „nowy okres" NIE potrzebuje tu obsługi: resolver zwraca wtedy `aj = None`
  (odroczony do utworzenia), a `zmiany_potrzebne` ustawia `bool(diff)` w §8.1/§8.2.
- **„data do": jedyna zmiana** — z „różni się" na „`plik_do` niepuste **oraz**
  `aj.zakonczyl_prace is None`" (wstawienie, nie nadpisanie).
- **Resolvera tu NIE wołamy** (poprawka Fable) — check jest w gorących miejscach
  (analyze/integrate), nie dokładamy mu zapytań.
- reszta pól (funkcja/stanowisko/grupa/wymiar/primary) bez zmian.

---

## 9. Warstwa widoczności (rejestr `POLA_ROZNIC` z #559)

### 9.1 `roznice.py` — dwa nowe wpisy

```
POLA_ROZNIC = [
    ("jednostka", "Jednostka", _stan_jednostka),
    ("email", "E-mail", _stan_email),
    ("tytul", "Tytuł naukowy", _stan_tytul),
    ("stopien", "Stopień służbowy", _stan_stopien),
    ("funkcja", "Funkcja w jednostce", _stan_funkcja),
    ("stanowisko", "Stanowisko dydaktyczne", _stan_stanowisko),
    ("data_od", "Data od", _stan_data_od),      # NOWE
    ("data_do", "Data do", _stan_data_do),      # NOWE
]
```

Ekstraktory (kontrakt `"zmienione" | "zgodne" | "brak"`); oba czytają
`row._okres()` (memo, §7) — bez własnych zapytań:

- `_stan_data_od(row)`:
  - `"brak"` gdy `plik_od` puste **lub** brak dopasowanego autora **lub**
    `row.jednostka_id is None`;
  - `"zmienione"` gdy `plik_od` ma wartość i decyzja resolvera to **nowy okres**
    (`("nowy", …)`) **lub** wypełnienie pustej daty od (`("istniejacy", aj)`,
    `aj.rozpoczal_prace is None`);
  - `"zgodne"` w pozostałych (ta sama data od).
- `_stan_data_do(row)`:
  - `"brak"` gdy `plik_do` puste **lub** brak autora **lub** `row.jednostka_id
    is None`;
  - `"zmienione"` gdy `plik_do` ma wartość i:
    - dla `("istniejacy", aj)` — różni się od `aj.zakonczyl_prace`
      (wstawienie pustej **lub** różnica pokazana bez nadpisania), **lub**
    - dla `("nowy", …)` — zawsze (nowy okres jeszcze nie ma końca → wstawimy);
  - `"zgodne"` gdy równe.

> Rozstrzygnięcie sprzeczności (Fable): „brak AJ docelowego" dla `_stan_data_do`
> znaczy **wyłącznie** brak autora/jednostki. Nowy okres z `plik_do` → „zmienione".

> **Świadoma konsekwencja (N4).** Dla wiersza „nowy okres" (`rozpoczal ≠ plik_od`)
> analiza ustawia `row.autor_jednostka = None`, więc `_stan_funkcja`/`_stan_stanowisko`
> i `porownaj_z_baza()["funkcja"]/["stanowisko"]` pokażą **„brak" / pustą bazę**
> (nie ma istniejącego AJ, z którym porównać). To poprawne semantycznie („nowy
> okres — nie ma z czym porównywać") — zapisane wprost, żeby implementujący NIE
> „naprawił" tego przypadkowo, podpinając stary AJ.

### 9.2 `models.py` — `porownaj_z_baza()` + `_porownaj_data`

Nowy statyczny helper (analogiczny do `_porownaj_email` / `_porownaj_fk`):

```
_porownaj_data(plik_date, baza_date, *, nowy_okres=False) ->
    {"plik": "YYYY-MM-DD"|"", "baza": "YYYY-MM-DD"|"", "rozne": bool, "nowy_okres": bool}
```

Musi tolerować `str` / `date` / pusty (`porownaj_z_baza` czyta surowe
`dane_znormalizowane`; §12 pkt 8).

`porownaj_z_baza()` dostaje klucze `"data_od"` i `"data_do"`, wszystko z jednej
decyzji `row._okres()` (§7):

- `data_od`: `plik = plik_od`; `nowy_okres`/`rozne` z **decyzji resolvera**.
  Strona `baza`:
  - `("istniejacy", aj)` → `baza = aj.rozpoczal_prace` (może być pusta, gdy
    wypełniamy `NULL`);
  - `("nowy", …)` → `baza` = `rozpoczal_prace` **okresu-referencyjnego**
    (`_wybierz_aktywny_najswiezszy(aj_lista)`, §7), żeby operator widział
    „stara → nowa"; gdy AJ (A, J) w ogóle brak → `baza` pusta;
- `data_do`: `plik = plik_do`; `baza` = `zakonczyl_prace` **docelowego** okresu
  (`("istniejacy", aj)` → `aj.zakonczyl_prace`; `("nowy", …)` → pusta, nowy
  okres nie ma jeszcze końca); `rozne` = obie niepuste i różne, **lub** baza
  pusta a plik niepusty (wstawienie), **lub** nowy okres z niepustym plik_do;
- **guard:** gdy brak autora lub `row.jednostka_id is None` → obie strony puste,
  `rozne=False`.

**Jedno źródło prawdy:** o „istniejący vs nowy okres" i o docelowy AJ decyduje
TEN SAM `row._okres()` co integracja — podgląd nie może „obiecać" innego okresu
niż utworzy commit. Data `baza` po stronie *wyświetlania* dla nowego okresu to
tylko kontekst („z jakiego okresu operator patrzy"), nie wpływa na decyzję.

### 9.3 `stany_pol()` — zgodność snapshotów

`stany_pol()` zwraca zamrożony `stany_pol_snapshot` (utrwalony przy integracji,
przed mutacją — `_integruj_wiersz` / `integrate()` z guardem `is None`).
Snapshoty rekordów sprzed tego feature'a **nie mają** kluczy `data_od`/`data_do`;
filtr po nowym polu (≠ „wszystkie") ukryłby taki rekord. Dopełniamy brakujące
klucze wartością domyślną (lazy import `POLA_ROZNIC` **przed** gałąź snapshotu):

```
from .roznice import POLA_ROZNIC          # przed if — używane w obu gałęziach
if self.stany_pol_snapshot is not None:
    baza = {k: "brak" for k, _e, _x in POLA_ROZNIC}
    return {**baza, **self.stany_pol_snapshot}
# ... ścieżka live (snapshot None, faza analizy) — bez zmian
```

Snapshot `None` (faza analizy) spada do ścieżki live bez zmian. Stare snapshoty
pod nowym filtrem dają neutralne „brak".

### 9.4 Szablon `_wiersz_preview_kom.html`

- `data-diff-*` na pierwszym `<tr>` generuje się **automatycznie**
  (pętla po `row.stany_pol.items`) — bez zmian kodu, dochodzą
  `data-diff-data_od` / `data-diff-data_do`.
- W bloku porównywarki (drugi `<tr>`) dwa nowe „item"-y, wzorem istniejących:

```
<div class="import-porownanie-item">
    <span class="import-porownanie-etykieta">Data od:</span>
    {% include "…/_porownanie_kom.html" with pole=porownanie.data_od %}
</div>
<div class="import-porownanie-item">
    <span class="import-porownanie-etykieta">Data do:</span>
    {% include "…/_porownanie_kom.html" with pole=porownanie.data_do %}
</div>
```

- Sygnał „nowy okres": gdy `pole.nowy_okres`, dodatkowy `label` („nowy okres
  zatrudnienia") w komórce — drobne rozszerzenie `_porownanie_kom.html` albo
  inline w karcie. Pasek filtrów dostaje „Data od"/„Data do" **automatycznie**
  (`views.py` iteruje `POLA_ROZNIC` do `ctx["pola_roznic"]`).

---

## 10. Liczniki + audyt

- **Przewód licznika (N1):** `_materializuj_diff` zwraca `created` (§8.3) →
  `_integruj_wiersz` propaguje `created` (early-return na guardzie `log_zmian`
  → `False`) → pętla `integruj` **sumuje** i gdy `created` **oraz**
  `diff["autor_jednostka"].get("nowy_okres")` → inkrementuje
  `utworzono_nowych_okresow` w słowniku `p.result(...)`; podgląd wyniku pokaże
  „utworzono N nowych okresów zatrudnienia". Bez tego przewodu licznik nigdy
  nie zobaczy `created`.
- `_opisz_utworzone(diff, created)` — gdy `created` **oraz**
  `diff["autor_jednostka"]["nowy_okres"]`, opis „nowy okres zatrudnienia od
  `<data>`" (zamiast/obok „powiązanie autor-jednostka"). **Poprawka N6:**
  przekazujemy `created`, żeby drugi wiersz z tym samym `(A, J, data)`
  (`created=False`) NIE kłamał „nowy okres" w audycie.
- `log_zmian["autor_jednostka"]` — istniejące wpisy „data rozpoczęcia pracy na
  …" / „data końca zatrudnienia na …" zostają (już są).

---

## 11. Migracje

**Brak migracji schematu.** Nowe okresy to rekordy runtime; `stany_pol_snapshot`
istnieje od #559 (migracja 0024); `diff_do_utworzenia` dostaje dodatkowe klucze
JSON (`rozpoczal_prace`, `nowy_okres`). Po scaleniu należy jedynie **odświeżyć
baseline** (`make baseline-update`) zgodnie z regułą projektu — bez nowych
migracji delta będzie pusta (baseline odświeżamy RAZ przy scalaniu, nie w tym
branchu).

---

## 12. Przypadki brzegowe

1. **Multi-etat (wiele AJ dla (A, J)):** resolver po pełnym kluczu
   (`rozpoczal_prace`) rozstrzyga jednoznacznie; przy pustym `plik_od` wybór
   aktywnego/najświeższego (`_wybierz_aktywny_najswiezszy`).
2. **`plik_od` present, baza `rozpoczal = NULL`:** wypełnienie, **nie** nowy
   okres (§3 wiersz 4). Przy >1 AJ z `NULL` (legacy) — deterministyczny wybór
   po `order_by("pk")`.
3. **Odwrócony zakres (`plik_do < rozpoczal`):** istniejąca walidacja rzuca
   `BPPDatabaseError` — dotyczy też nowych okresów i wstawionej „data do".
4. **Idempotencja restartu integracji:** gwarantem NIE jest `get_or_create`
   (po stemplu fallbackiem lookup `None` już nie trafia w tworzony rekord) —
   gwarantują ją: guard `log_zmian is not None` (#508 F2) + per-wierszowy
   `transaction.atomic`. Drugi przebieg trafia w istniejący okres przez lookup
   po pełnym kluczu (`filter(...).order_by("pk").first()` → found → reuse).
5. **Drift bazy analiza→commit** (między analizą a commitem powstał AJ
   `(A, J, plik_od)` podczas „wypełniania NULL"): `aj.save()` mógłby rzucić
   `IntegrityError`. To ta sama klasa ryzyka co dziś (stemplowanie NULL→data);
   `_integrate_autor_jednostka` powinien być odporny (re-check przez lookup /
   złapanie i pominięcie duplikatu). Zaznaczone jako drobne wzmocnienie.
6. **Podgląd = integracja:** strona „baza" w porównywarce liczona TYM SAMYM
   `row._okres()` — podgląd nie może zapowiadać innego okresu niż utworzy commit.
7. **Odpięcia / przepięcia:** ortogonalne. Odpięcia dotyczą par „spoza pliku";
   nowy okres to ta sama jednostka (inna data), a przepięcia to **inna**
   jednostka — nie kolidują. Nowe AJ (aktywne, primary) aktualizuje
   `aktualna_jednostka` przez istniejący trigger — bez zmian.
8. **`data_zatrudnienia` jako `date` vs ISO-string:** `dane_bardziej_znormalizowane`
   parsuje oba pola do `date`; `porownaj_z_baza` czyta `dane_znormalizowane`
   (surowe) — helper `_porownaj_data` musi tolerować `str`/`date`/pusty.

---

## 13. Plan testów (TDD — najpierw testy)

Nowy plik `tests/test_pipeline/test_integrate_okresy_dat.py` + rozbudowa
`test_integrate_daty.py`, `test_porownywarka.py`, `test_stany_pol.py`,
`test_views_preview_render.py`, `test_wybor_autor_jednostka.py`.

**Resolver (`rozwiaz_okres_zatrudnienia`)** — po jednym teście na wiersz §3:
brak AJ + data / brak AJ + puste / ten sam okres / wypełnienie NULL / nowy
okres / istniejący + puste (no-op). + multi-etat wybór aktywnego. + `>1` AJ z
`rozpoczal=NULL` → deterministyczny wybór po pk. + `aj_lista=` nie odpala
zapytania. **+ (N5)** `plik_od` jako ISO-string → asercja braku fałszywego
„nowy okres"/duplikatu (kontrakt: resolver dostaje `date|None`).

**`_wybierz_aktywny_najswiezszy` (N2)** — parytet z dzisiejszym SQL
`order_by("-rozpoczal_prace")` (NULLS FIRST): przy mieszance AJ z `rozpoczal`
datowanym i `rozpoczal=NULL` funkcja wybiera **ten sam** rekord co dawny SQL
(NULL jako „najświeższy"); aktywny (`zakonczyl IS NULL`) ma priorytet;
tie-break po pk. Bez `TypeError` na `None`.

**Analiza (`_przetworz_wiersz`)** — wiersz z `plik_od ≠ baza` na twardo
dopasowanej jednostce odkłada `diff["autor_jednostka"]` z `rozpoczal_prace` +
`nowy_okres=True`; wiersz z `plik_od == baza` NIE odkłada nowego okresu; wiersz
z pustą jednostką → brak resolvera.

**Integracja:**
- nowy okres tworzy DRUGI `Autor_Jednostka` (stary zostaje otwarty — P2);
- „data do" wstaw-gdy-pusta; NIE nadpisuje istniejącej (assert wartość z bazy);
- istniejący AJ + pusty `plik_od` → `rozpoczal_prace` NIE zmienione (nawet gdy
  `NULL`) i NIE stemplowane dziś/data-zmian;
- nowy AJ + pusty `plik_od` → `rozpoczal = data zmian` (i → dziś gdy brak);
- odwrócony zakres → `BPPDatabaseError`;
- idempotencja: drugi `integruj` nie tworzy trzeciego okresu;
- `_materializuj_diff` zwraca `created`; licznik `utworzono_nowych_okresow`.

**Porównywarka / stany pól:**
- `porownaj_z_baza()["data_od"]/["data_do"]` — `plik`/`baza`/`rozne`/`nowy_okres`
  dla: zgodne / wypełnienie / nowy okres / brak / pusta jednostka;
- `stany_pol()` daje `data_od`/`data_do` ∈ {zmienione,zgodne,brak};
- stary snapshot bez kluczy dopełniony do „brak" (nie znika pod filtrem);
- render karty: dwa nowe „item"-y + `data-diff-data_od/-data_do` na `<tr>`;
- **(N3) inwalidacja memo:** `stany_pol()`/`porownaj_z_baza()` przed i po zmianie
  autora (`_zwiaz_autora_z_wierszem`) na tej samej instancji wiersza dają
  decyzję dla **nowego** autora (cache `_okres_cache` wyczyszczony).

**Wydajność (poprawka Fable):**
- `assertNumQueries` na renderze podglądu wiersza — liczba zapytań **nie rośnie
  liniowo** z dodaniem dat (resolver 1×/wiersz przez memo, nie ~6×).

**Testy WYMAGAJĄCE aktualizacji (zidentyfikowane przez Fable — czerwone bez
zmiany):**
- `test_integrate_daty.py::test_data_zmian_wypelnia_nowe_aj_bez_daty_w_pliku`
  (istniejący AJ `rozpoczal=None` + puste dane asertuje stempel `data_zmian`) —
  wg §5 to teraz **no-op**; przepisać na wariant „**świeży** AJ" (materializacja);
- `test_integrate_daty.py::test_brak_globalnej_daty_stempluje_date_importu` —
  jw., przepisać na „świeży AJ";
- `test_stany_pol.py::test_stany_pol_ma_wszystkie_klucze` — rozszerzyć oczekiwany
  zbiór o `data_od`/`data_do` (8 kluczy);
- `test_views_preview_render.py::test_podglad_wiersz_ma_atrybuty_data_diff`
  oraz `::test_podglad_ma_pasek_filtrow_radia` — pętle po kluczach `POLA_ROZNIC`
  → dołożyć `data_od`/`data_do`;
- `test_wybor_autor_jednostka.py` — pozostaje ważny, jeśli
  `_wybierz_autor_jednostka` deleguje do `_wybierz_aktywny_najswiezszy` (§7);
  gdyby zdecydować o usunięciu funkcji — zmigrować na resolver.

> Uwaga: dokładne nazwy testów/linie zweryfikować przy implementacji — Fable
> podał je z bieżącego stanu `origin/dev`; jeśli któraś nazwa się nie zgadza,
> znaleźć asercję po sensie (stempel daty / zbiór kluczy `POLA_ROZNIC`).

Po implementacji: pełna suita (`make tests`, ~10 min) — 0 regresji; moduł
`uv run pytest src/import_pracownikow/` zielony.

---

## 14. Poza zakresem (świadomie)

- Auto-domykanie starego okresu (P2) — dopiero na jawną prośbę (opt-in w podglądzie).
- Edycja/rozdzielanie okresów z poziomu podglądu (operator ręcznie).
- Wykrywanie „przeniesienia" (data od = koniec innego okresu) — to przepięcia,
  osobny mechanizm.
- Batch-prefetch AJ w widoku — tylko jeśli profil pokaże, że memo 1×/wiersz to
  za mało (resolver już przyjmuje `aj_lista=`).

---

## 15. Ryzyka

- **Rozjazd podgląd ↔ integracja** — mitygacja: jeden `row._okres()` dla obu
  (w tym GŁÓWNA ścieżka `analyze.py`, §8.1).
- **N+1 w renderze podglądu** — mitygacja: 1 zapytanie w resolverze + memo na
  wierszu; test `assertNumQueries`.
- **`MultipleObjectsReturned` / niedeterminizm na `(A, J, NULL)`** — mitygacja:
  `order_by("pk").first()` + create (nie `get_or_create`); fallback stempluje
  konkretną datę, więc tworzony rekord nie ma `NULL` w kluczu.
- **Snapshoty pre-feature** — mitygacja: dopełnianie kluczy w `stany_pol()`.
- **Drift bazy analiza→commit** — mitygacja: lookup po pełnym kluczu + odporność
  `_integrate_autor_jednostka` (§12 pkt 5).
- **Konflikt z równoległymi branchami importu** — baseline odświeżyć **raz przy
  scalaniu** (reguła projektu), nie w tym branchu.
