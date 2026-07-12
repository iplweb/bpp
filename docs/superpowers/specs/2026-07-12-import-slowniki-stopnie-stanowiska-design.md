# Import pracowników — nowe słowniki (stopień służbowy, stanowisko dydaktyczne), e-mail, parser komórki, niepełna nazwa jednostki, profil ostatnio użyty

**Data:** 2026-07-12
**Branch:** `feat/import-pracownikow-slowniki-stopnie-stanowiska` (od `dev`)
**Plik wejściowy (próbka):** `~/Downloads/struktura.xlsx` (dane APOŻ, 142 wiersze)

## 1. Cel i kontekst

Nowy plik importu pracowników (APOŻ) ma kolumny:

```
lp | nazwisko imię | email | stopień | tytuł | funkcja | stanowisko_dydakt | komórka
```

Wymagania użytkownika (dosłownie):

- **`nazwisko imię`** → rozbić na nazwisko + imię (bez tytułu). Format jest
  deterministyczny: nazwisko-first.
- **`email`** → autorzy mają pole e-mail. Nowym zapisujemy; istniejących **nie
  nadpisujemy**, ale pokazujemy plik-vs-baza w porównywarce.
- **`stopień`** → to **stopień służbowy pożarniczy** (kpt., bryg., mł. bryg.,
  st. kpt., …), NIE tytuł naukowy. „DODAJ do autora stopień służbowy i tyle,
  słownik, to samo co z tytułami" → nowy słownik na `Autor`, pełny ekran
  weryfikacji jak tytuły.
- **`tytuł`** → tytuł/stopień naukowy → istniejące pole `tytuł_stopień`.
- **`funkcja`** → funkcja w jednostce (`Funkcja_Autora`) — dziś cel mapowania
  nazywa się mylnie „stanowisko"; relabel.
- **`stanowisko_dydakt`** → **stanowisko dydaktyczne**. „A DODAJ do jednostki
  stanowisko_dydaktyczne i tyle" → nowy słownik na `Autor_Jednostka`, **pełny
  ekran weryfikacji** (jak tytuły/jednostki). Model: `StanowiskoDydaktyczne`.
- **`komórka`** → złożona nazwa jednostki, np.
  `RW-1/1 Zakład Kierowania Działaniami Ratowniczymi … WIBiOL taktyka`, gdzie
  `RW-1/1` = skrót, `WIBiOL` = oddział, `taktyka` = znacznik (śmieć). Parsować.

Dwa dodatkowe wymagania (runda 2):

- **„niepełna nazwa jednostki"** — nowy *rodzaj pola* mapowania. Inny import ma
  kolumnę `wydział` = „Medyczny" (jedno słowo, nie „Wydział Medyczny").
  Obecny `matchuj_wydzial` robi tylko `nazwa__iexact` → nie trafia. Zamiast
  grzebać w wydziale: opt-in cel mapowania z dopasowaniem `icontains`/trigram.
- **profil ostatnio użyty** — jeśli zapiszemy schemat importowania pod nazwą, to
  przy kolejnym imporcie proponuj ostatnio użyty schemat.

**Zasada nadrzędna:** wszystko jest **opt-in przez ekran mapowania kolumn**.
Żaden istniejący format (IHIT, standard BPP) nie zmienia zachowania — nowe cele
mapowania aktywują się tylko, gdy użytkownik zmapuje na nie kolumnę. To realizuje
wymóg „kompatybilne z innymi formatami importu".

## 2. Stan obecny (fakty z kodu)

- **Model domenowy** (`src/bpp/models/autor.py`):
  - `Autor` ma `email` (`EmailField`, blank, default="") oraz `tytul` FK →
    `Tytul`.
  - `Autor_Jednostka` ma FK: `funkcja` (→ `Funkcja_Autora`),
    `grupa_pracownicza`, `wymiar_etatu`, plus `podstawowe_miejsce_pracy`,
    `rozpoczal_prace`, `zakonczyl_prace`. **Nie ma** pola „stanowisko".
  - Słowniki dziedziczą po `NazwaISkrot` (`src/bpp/models/abstract/naming.py`),
    np. `Tytul`, `Funkcja_Autora`.
- **Mapowanie** (`src/import_pracownikow/mapping.py`): synonimy nagłówek→cel,
  fallback podłańcuchowy, walidacja (wymaga nazwisko+imię lub osoba_sklejona +
  `nazwa_jednostki`), `remapuj_wiersz`, `dopasuj_profil` (pokrycie ≥90%
  nagłówków). Cel „stanowisko" faktycznie zasila `Funkcja_Autora`.
- **Profil** (`ProfilMapowania`): `nazwa` (unique), `mapowanie` (JSON),
  `ostatnio_uzyty` (DateTime, **dziś nieustawiany**), `utworzony_przez`. Widok
  `MapowanieView` proponuje profil przez `dopasuj_profil`; zapis przez
  `update_or_create` gdy zaznaczono `zapisz_profil`.
- **Dopasowanie jednostki** (`src/import_common/core/jednostka.py`):
  `matchuj_jednostke` matchuje `Q(nazwa__iexact) | Q(skrot__iexact)`, rozumie
  konwencję `Nazwa (SKRÓT)` (próbuje `skrot=`), oraz `istartswith` z
  ujednoznacznieniem po wydziale. `sklasyfikuj_jednostke` → (obj, status
  `twardy|zgadywanie|brak`, similarity), trigram ≥0.7 dla „zgadywanie" z puli
  afiliacyjnej (wyklucza lustra/wydziały).
- **Dopasowanie wydziału** (`src/import_common/core/tytul_funkcja.py`):
  `matchuj_wydzial` = `Wydzial.objects.get(nazwa__iexact=...)` — tylko dokładne.
- **Podsystem tytułów (WZORZEC do zduplikowania ×2):**
  - `import_common/core/tytul.py`: `sklasyfikuj_tytul`, `matchuj_tytul`,
    `zaproponuj_skrot_tytulu`, statusy `STATUS_TYTUL_{TWARDY,ZGADYWANIE,BRAK}`.
  - `import_pracownikow/models.py`: `ImportPracownikowTytul` (model decyzji),
    `ImportPracownikow.tworz_brakujace_tytuly`, `ImportPracownikowRow.{tytul,
    tytul_status, zrodlo_tytulu}`.
  - `pipeline/analyze.py`: `_ReconcilerTytulow`, `_klasyfikuj_tytul_wiersza`,
    `_STATUS_NA_TRYB_TYTUL`.
  - `pipeline/integrate.py`: `_rozstrzygnij_tytuly`,
    `_rozstrzygnij_jeden_tytul`, `_podlacz_wiersze_do_tytulow`,
    `unikalny_skrot_tytulu`; rozstrzyganie gated `zakres != ZAKRES_JEDNOSTKI`.
  - `views.py` + `templates/.../weryfikacja_tytulow.html` + `urls.py`.
- **Przepływ dwustopniowy:** Krok 1 (struktura) rozstrzyga i tworzy jednostki +
  tytuły → stan `STRUKTURA_ZINTEGROWANA`; Krok 2 (osoby) dopina do autorów.
  `zakres`: `JEDNOSTKI` (tylko jednostki), `STRUKTURA` (jednostki+tytuły),
  `PELNY`.
- **Admin/menu:** słowniki rejestrowane w `src/bpp/admin/__init__.py`
  (`NazwaISkrotAdmin` / `RestrictDeletionToAdministracjaGroupAdmin`); menu
  „Dane systemowe" w `src/django_bpp/menu.py` (`SYSTEM_MENU` + `SYSTEM_MENU_2`);
  test `src/django_bpp/tests/test_menu.py`.

## 3. Decyzje projektowe (zatwierdzone)

1. **Dwa nowe słowniki jako pełne modele** (`NazwaISkrot`):
   `Stopien_Sluzbowy` (na `Autor`) i `StanowiskoDydaktyczne` (na
   `Autor_Jednostka`).
2. **Oba dostają pełny ekran weryfikacji** (Approach C) — symetrycznie do
   tytułów/jednostek: klasyfikacja twardy/zgadywanie/brak, toggle „twórz
   brakujące", edytowalna nazwa+skrót przed utworzeniem, reconciler, dedup po
   nazwie case-insensitive.
3. **`email`**: nowi autorzy → zapis; istniejący → **nigdy nie nadpisuj**,
   pokaż plik-vs-baza w porównywarce.
4. **`komórka`**: parser opt-in (cel `komórka_złożona`); dopasowanie **po
   skrócie** (pewne); oddział jako **hint** (ustaw wydział tylko gdy istnieje
   Wydział/jednostka o tym skrócie), ogon-znacznik odrzucony.
5. **`nazwisko imię`**: deterministyczny split nazwisko-first (osobny cel niż
   `osoba_sklejona`, który zostaje dla komórek z tytułem).
6. **„niepełna nazwa jednostki"**: nowy cel mapowania, dopasowanie
   `icontains`/trigram, wpięte w istniejący ekran weryfikacji jednostek.
7. **Profil ostatnio użyty**: ustawiaj `ostatnio_uzyty` przy zastosowaniu/zapisie
   profilu; przy kolejnym imporcie proponuj (fallback po dopasowaniu nagłówków)
   ostatnio użyty.
8. **Nazewnictwo:** `StanowiskoDydaktyczne` (CamelCase, wprost od użytkownika),
   `Stopien_Sluzbowy` (podkreślnik, spójnie z `Funkcja_Autora`/`Tytul`-sąsiedztwem).
9. **Nowy branch** od `dev` (zrobione).
10. **Baseline** (`baseline-sql/`) — **NIE** odświeżamy w feature-branchu; refresh
    dopiero przy scalaniu (reguła projektu).

## 4. Zmiany domenowe (`bpp`)

### 4.1 Modele (`src/bpp/models/autor.py`)

```python
class Stopien_Sluzbowy(NazwaISkrot):
    class Meta:
        verbose_name = "stopień służbowy"
        verbose_name_plural = "stopnie służbowe"
        ordering = ["nazwa"]
        app_label = "bpp"

class StanowiskoDydaktyczne(NazwaISkrot):
    class Meta:
        verbose_name = "stanowisko dydaktyczne"
        verbose_name_plural = "stanowiska dydaktyczne"
        ordering = ["nazwa"]
        app_label = "bpp"
```

- `Autor.stopien_sluzbowy = models.ForeignKey("bpp.Stopien_Sluzbowy",
  models.SET_NULL, blank=True, null=True)` — obok `tytul`.
- `Autor_Jednostka.stanowisko = models.ForeignKey("bpp.StanowiskoDydaktyczne",
  models.SET_NULL, blank=True, null=True)` — obok `funkcja`.
- Eksport w `src/bpp/models/__init__.py`.

**Uwaga on_delete:** `Tytul`/`Funkcja_Autora` używają `CASCADE`, ale kasowanie
słownika nie powinno kasować autorów/zatrudnień → używamy `SET_NULL` (bezpiecznej
semantyki dla słownika opisowego). Do potwierdzenia w code-review.

### 4.2 Migracja `bpp`

Jedna migracja: 2 modele + 2 FK. Nazwa np.
`04XX_stopien_sluzbowy_stanowisko_dydaktyczne`. Zależność od najnowszej migracji
`bpp` na `dev` w chwili implementacji.

### 4.3 Admin (`src/bpp/admin/__init__.py`)

- Rejestracja `Stopien_Sluzbowy` i `StanowiskoDydaktyczne` przez
  `NazwaISkrotAdmin` (jak `Tytul`).
- `stopien_sluzbowy` w formularzu/adminie `Autor` (obok tytułu).
- `stanowisko` w inline `Autor_Jednostka` (obok funkcji).

### 4.4 Menu „Dane systemowe" (`src/django_bpp/menu.py`)

- `SYSTEM_MENU_2`: dodać alfabetycznie
  `("Stanowiska dydaktyczne", "/admin/bpp/stanowiskodydaktyczne/")` i
  `("Stopnie służbowe", "/admin/bpp/stopien_sluzbowy/")` (URL-e = lowercase
  model_name Django admina).
- Zaktualizować `src/django_bpp/tests/test_menu.py` (liczba/obecność pozycji).

## 5. Klasyfikatory (`import_common.core`)

Mirror `import_common/core/tytul.py` — dwa nowe moduły (lub jeden generyczny
helper `slownik.py` + dwa cienkie adaptery; do rozstrzygnięcia w planie,
preferencja: dwa moduły dla czytelności i spójności z `tytul.py`):

- `import_common/core/stopien.py`: `sklasyfikuj_stopien(s) -> (obj|None,
  status, sim|None)`, `matchuj_stopien(s)`, `zaproponuj_skrot_stopnia(s)`,
  `STATUS_STOPIEN_{TWARDY,ZGADYWANIE,BRAK}`.
- `import_common/core/stanowisko.py`: analogicznie dla
  `StanowiskoDydaktyczne`.

Matchowanie: `Q(nazwa__iexact) | Q(skrot__iexact)`; „zgadywanie" = trigram ≥
próg (jak tytuły). Normalizacja wartości (trim, spacje) przez istniejące helpery
`import_common.normalization` (dodać `normalize_stopien` / `normalize_stanowisko`
jeśli potrzebne — mogą być no-op/trim na start).

## 6. Rozszerzenie dopasowania jednostki — „niepełna nazwa jednostki"

### 6.1 Klasyfikator

`import_common/core/jednostka.py`: nowa funkcja
`sklasyfikuj_jednostke_niepelna(fragment, wydzial=None, *, prog=...)`:

1. Najpierw `sklasyfikuj_jednostke` (exact/skrót) — jeśli `twardy`, zwróć.
2. `icontains` w puli afiliacyjnej (`_pula_afiliacyjna`):
   - dokładnie 1 trafienie → `(obj, "zgadywanie", None)` (operator weryfikuje);
   - >1 trafień → wybierz najlepsze trigramowo, `"zgadywanie"` (do weryfikacji);
   - 0 → spadek do trigramu jak w `sklasyfikuj_jednostke` → `"zgadywanie"|"brak"`.

„niepełna" nazwa **nigdy** nie daje `twardy` z gałęzi `icontains` (zawsze
wymaga weryfikacji), bo fragment z definicji jest niejednoznaczny.

### 6.2 Wpięcie

- Nowy cel mapowania `niepełna_nazwa_jednostki` → remap do klucza
  `nazwa_jednostki_niepelna`.
- `analyze._przetworz_wiersz`: jeśli obecny `nazwa_jednostki_niepelna` (a brak
  `nazwa_jednostki`), użyj `sklasyfikuj_jednostke_niepelna`; dalej ten sam tor
  decyzji (`ImportPracownikowJednostka`, ekran `weryfikacja_jednostek`).
- `waliduj_mapowanie`: wymóg „jednostka" spełnia **którykolwiek** z:
  `nazwa_jednostki`, `nazwa_jednostki_niepelna`, `komórka_złożona`.

## 7. Parser komórki (`src/import_pracownikow/parsers/jednostka_zlozona.py`, nowy)

Czysty rdzeń (bez ORM), testowalny tabelarycznie. Uruchamiany jako preprocessing
wiersza (jak `sklej_drugie_imie`) **tylko** gdy kolumna zmapowana na
`komórka_złożona`.

Algorytm (zwaliduj na wszystkich 31 unikalnych wartościach z próbki):

```
tokeny = komorka.split()
skrót  = tokeny[0] jeśli re.match(r'^[A-ZŁŚŻĆŃÓ][A-ZŁŚŻĆŃÓ0-9]*-\d+(/\d+)?$', tokeny[0]) else None
# oddział = token „akronimowy” (len>=3, >=2 wielkie litery, np. WIBiOL), jeśli obecny
# nazwa = tokeny między skrótem a oddziałem, minus KOŃCOWY ciąg tokenów all-lowercase (ogon-znacznik)
```

Reguły szczegółowe (wynikają z danych):

- Skrót zawsze pierwszy token pasujący do wzorca (`RW-1/1`, `RN-2`, `RW-9`).
- Oddział = token mieszany-wielkoliterowy (`WIBiOL`). Dla `RN-*` brak takiego
  tokenu; wtedy oddział = None.
- Ogon-znacznik = końcowy ciąg tokenów pisanych **w całości małą literą**
  (`taktyka`, `pożary`, `hydra hydromechanika`, `instytut ib`). Odrzucany.
  Uwaga: łączniki w środku nazwy (`i`, `w`, `Ppoż.`) są w ŚRODKU, więc nie
  wpadają do końcowego ciągu → nazwa zachowana poprawnie.

Wyjście do wiersza:

- `nazwa_jednostki = f"{nazwa} ({skrót})"` gdy jest skrót — `matchuj_jednostke`
  spróbuje najpierw `skrot=` (pewne dopasowanie); inaczej sama `nazwa`.
- `wydział = oddział` **tylko** gdy istnieje `Wydzial`/`Jednostka` o skrócie ==
  oddział; inaczej pomiń (hint best-effort).

**Test akceptacyjny:** dla wszystkich 31 wartości parser zwraca poprawny
(skrót, nazwa, oddział) — zapięte jako test tabelaryczny.

## 8. Parser „nazwisko imię" (deterministyczny)

Nowy cel `nazwisko_imię`. Preprocessing (w `parsers/wartosci.py` lub obok
`sklej_drugie_imie`): pierwszy token → `nazwisko`, reszta → `imię`. Obsługuje
`Ciuka-Witrylak Małgorzata` (łącznik = 1 token). **Ograniczenie:** dwuczłonowe
nazwiska bez łącznika nie są rozbijane (brak w próbce) — udokumentowane.
Różny od `osoba_sklejona` (parser z detekcją tytułu/kolejności — zostaje).

## 9. Mapowanie (`src/import_pracownikow/mapping.py`)

Nowe cele w `POLA_DOCELOWE` + synonimy w `_SYNONIMY`:

| Cel | Etykieta | Synonimy (znormalizowane) |
|---|---|---|
| `email` | E-mail | email, e_mail, mail, poczta, adres_email |
| `stopień_służbowy` | Stopień służbowy | stopień, stopien, stopień_służbowy, stopien_sluzbowy, stopień_wojskowy |
| `stanowisko_dydaktyczne` | Stanowisko dydaktyczne | stanowisko_dydakt, stanowisko_dydaktyczne, stanowisko_dyd |
| `funkcja` (relabel istn. „stanowisko") | Funkcja w jednostce | funkcja, funkcja_w_jednostce, stanowisko |
| `nazwisko_imię` | Nazwisko i imię (jedna komórka, nazwisko-first) | nazwisko_imię, nazwisko_imie |
| `komórka_złożona` | Komórka (skrót + nazwa + oddział + znacznik) | komórka, komorka, komorka_zlozona |
| `niepełna_nazwa_jednostki` | Niepełna nazwa jednostki | (bez auto-synonimu domyślnie; wybierany ręcznie) |

Uwaga: `stopień` → `stopień_służbowy` (przejęcie z dawnego
`stopień`→`tytuł_stopień`). `tytuł` nadal → `tytuł_stopień`. Dzięki temu tytuł
(naukowy) i stopień (służbowy) są rozdzielone — zgodnie z „jak jest tytuł to
tytuł".

`waliduj_mapowanie`: rozszerzyć regułę „jednostka wymagana" o
`nazwa_jednostki_niepelna` (cel `niepełna_nazwa_jednostki`) i `komórka_złożona`
jako alternatywy dla `nazwa_jednostki`. Zakaz duplikatów celów — bez zmian.

## 10. Model importu (`src/import_pracownikow/models.py`) — 1 migracja

Mirror wzorca tytułów, ×2:

- `ImportPracownikowStopien` (model decyzji, mirror `ImportPracownikowTytul`):
  `parent`, `nazwa_zrodlowa`, `tryb` (zgadywanie/brak), `auto_*`,
  `auto_similarity`, `decyzja` (akceptuj/mapuj/pomiń), `wybrany_stopien`,
  `nazwa_do_utworzenia`, `skrot_do_utworzenia`, `utworzony` (FK po commicie).
- `ImportPracownikowStanowisko` — analogicznie dla `StanowiskoDydaktyczne`.
- `ImportPracownikow`: `tworz_brakujace_stopnie`, `tworz_brakujace_stanowiska`
  (BooleanField, mirror `tworz_brakujace_tytuly`).
- `ImportPracownikowRow`:
  - `stopien` FK → `Stopien_Sluzbowy`, `stopien_status`, `zrodlo_stopnia` FK →
    `ImportPracownikowStopien` (mirror `tytul`/`tytul_status`/`zrodlo_tytulu`).
  - `stanowisko` FK → `StanowiskoDydaktyczne`, `stanowisko_status`,
    `zrodlo_stanowiska` FK → `ImportPracownikowStanowisko`.
- `AutorForm`: dodać pola `email` (EmailField, required=False),
  `stopień_służbowy` (CharField, required=False), `stanowisko_dydaktyczne`
  (CharField, required=False). (Wartości tekstowe z pliku; klasyfikacja/FK
  liczona później.)

Migracja `import_pracownikow`: 2 modele decyzji + pola toggle + pola na Row.

## 11. Pipeline

### 11.1 `pipeline/analyze.py`

- Preprocessing wiersza: `komórka_złożona` → parser komórki (§7);
  `nazwisko_imię` → split (§8) — przed `AutorForm`.
- Reconcilery: `_ReconcilerStopni`, `_ReconcilerStanowisk` (mirror
  `_ReconcilerTytulow`). Klasyfikacja przez `_klasyfikuj_stopien_wiersza`,
  `_klasyfikuj_stanowisko_wiersza` (mirror `_klasyfikuj_tytul_wiersza`), gated
  odpowiednimi toggle'ami `tworz_brakujace_*`.
- `email` z `AutorForm.cleaned_data` → zapis do `dane_znormalizowane`
  (do porównywarki i do zapisu przy tworzeniu autora).
- `niepełna_nazwa_jednostki` → `sklasyfikuj_jednostke_niepelna` (§6).
- `usun_stale` dla nowych reconcilerów.

### 11.2 `pipeline/integrate.py`

- FAZA słowników (obok tytułów, gated `zakres != ZAKRES_JEDNOSTKI`):
  `_rozstrzygnij_stopnie`, `_rozstrzygnij_stanowiska`
  (mirror `_rozstrzygnij_tytuly`; `unikalny_skrot_*` mirror
  `unikalny_skrot_tytulu`), `_podlacz_wiersze_do_{stopni,stanowisk}`.
- Krok 2 (osoby):
  - `Autor.stopien_sluzbowy` ← rozstrzygnięty stopień, **polityka
    no-overwrite** (ustaw tylko gdy puste na istniejącym autorze; nowym
    zawsze). Spójne z polityką dat.
  - `Autor_Jednostka.stanowisko` ← rozstrzygnięte stanowisko (materializacja jak
    `funkcja` w `_materializuj_diff`, ale ze źródła decyzji).
  - `email`: nowy autor → zapis; istniejący → **bez zmian** (tylko porównywarka).
- Liczniki wyniku: `utworzono_stopni`, `utworzono_stanowisk` (mirror
  `utworzono_tytulow`) w `p.result(...)`.

## 12. Widoki, URL-e, szablony

- `views.py`: `WeryfikacjaStopniView`, `WeryfikacjaStanowiskView` (mirror
  `weryfikacja_tytulow`; formset decyzji, akceptuj/mapuj/pomiń, edycja
  nazwy+skrótu, toggle „twórz brakujące").
- `urls.py`: 2 nowe trasy.
- `templates/import_pracownikow/weryfikacja_stopni.html`,
  `weryfikacja_stanowisk.html` (mirror `weryfikacja_tytulow.html`).
- Nawigacja Kroku 1 (bramki słowników): wpiąć ekrany stopni/stanowisk w
  sekwencję weryfikacji obok jednostek/tytułów (przegląd `przeglad.html`).
- **Porównywarka** (`przeglad.html`/`audyt.html`): kolumny e-mail
  (plik-vs-baza), stopień służbowy, stanowisko dydaktyczne — pokazać wartość z
  pliku i z bazy; e-mail różniący się podświetlić (bez nadpisania).

## 13. Profil ostatnio użyty (`views.py` + `mapping.py`)

- Ustawiaj `ProfilMapowania.ostatnio_uzyty = timezone.now()`:
  - przy zastosowaniu profilu (GET/POST, gdy profil zasilił mapowanie), oraz
  - przy zapisie profilu (`update_or_create` → dołożyć `ostatnio_uzyty`).
- Sugestia w `MapowanieView.get_form_kwargs`/kontekście:
  1. `dopasuj_profil(naglowki)` (pokrycie nagłówków) — priorytet;
  2. fallback: `ProfilMapowania.objects.filter(ostatnio_uzyty__isnull=False)
     .order_by("-ostatnio_uzyty").first()`.
- W szablonie `mapowanie.html`: pokaż, który profil zaproponowano („Zastosowano
  ostatnio użyty schemat: «…»") — informacyjnie.

## 14. Testy (`pytest`, `model_bakery`)

- **Parsery:** tabelaryczny test komórki na 31 wartościach; test split
  nazwisko-first (w tym łącznik).
- **Klasyfikatory:** `sklasyfikuj_stopien`/`sklasyfikuj_stanowisko`
  (twardy/zgadywanie/brak); `sklasyfikuj_jednostke_niepelna` („Medyczny" →
  „Wydział Medyczny" / jednostka; 0/1/wiele trafień).
- **Mapowanie:** synonimy nowych celów; przejęcie `stopień`; walidacja
  jednostki przez `niepełna_nazwa_jednostki`/`komórka_złożona`.
- **Analyze/Integrate:** rozstrzyganie + tworzenie stopni i stanowisk (mirror
  testów tytułów); polityka e-mail (nowy vs istniejący); dopięcie
  `Autor.stopien_sluzbowy` i `Autor_Jednostka.stanowisko`.
- **Profil:** `ostatnio_uzyty` ustawiany; fallback proponuje ostatni.
- **Widoki:** ekrany weryfikacji stopni/stanowisk (mirror
  `test_views_tytuly.py`).
- **Menu:** `test_menu.py` — nowe pozycje.
- **E2E:** przejście `struktura.xlsx` (Krok 1 → słowniki → Krok 2 → osoby) na
  bazie APOŻ (run-site baseline). Izolacja Playwright/asyncio jak w istniejącym
  `conftest.py` (patrz pamięć projektu o wycieku pętli).

## 15. Migracje i baseline

- 1 migracja `bpp` (modele + FK) + 1 migracja `import_pracownikow` (modele
  decyzji, toggle, pola Row).
- **Baseline NIE odświeżany** w tym branchu (reguła). Refresh (`make
  baseline-update`) przy scalaniu do `dev`.
- Newsfragmenty (towncrier) w `src/bpp/newsfragments/`: `feature` dla nowych
  słowników/kolumn, ewentualnie osobne dla profilu i niepełnej nazwy.

## 16. Poza zakresem (świadomie)

- Wyświetlanie stopnia służbowego na **publicznej** stronie autora (możliwe
  później; teraz admin + porównywarka importu).
- Import stopni **wojskowych** innych służb (model jest generyczny „stopień
  służbowy" — wartości dowolne ze słownika).
- Rozbijanie dwuczłonowych nazwisk bez łącznika w `nazwisko_imię`.
- Modelowanie `grupa_pracownicza`/`wymiar_etatu` z tego pliku (kolumn brak).

## 17. Ryzyka / uwagi

- **Duplikacja podsystemu tytułów ×2** — duży, powtarzalny diff. Rozważyć
  wspólny helper, ale nie kosztem czytelności (`tytul.py` jest wzorcem).
- **`on_delete` słowników** = `SET_NULL` (nie `CASCADE`) — do potwierdzenia w
  review.
- **Kolejność migracji** vs równoległe branche na `dev` (denorm_init invariant —
  patrz pamięć). Nowe modele bez denorm, więc niskie ryzyko.
- **Parser komórki** dostrojony do konwencji APOŻ; dla innych uczelni oddział/
  ogon mogą wyglądać inaczej — dlatego opt-in i dopasowanie głównie po skrócie.
```
