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
  `ostatnio_uzyty` (DateTime — **JUŻ ustawiany przy ZAPISIE** profilu, commit
  `7be75739a`; brak stemplowania przy ZASTOSOWANIU), `utworzony_przez`. Widok
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
  - `import_common/core/tytul.py`: `sklasyfikuj_tytul`, `normalize_tytul`,
    `zaproponuj_skrot_tytulu`, statusy `STATUS_TYTUL_{TWARDY,ZGADYWANIE,BRAK}`.
    (UWAGA: `matchuj_tytul` jest w `tytul_funkcja.py`, NIE w `tytul.py`.)
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
   `StopienSluzbowy` (na `Autor`) i `StanowiskoDydaktyczne` (na
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
8. **Nazewnictwo:** oba w CamelCase — `StopienSluzbowy` i
   `StanowiskoDydaktyczne` (decyzja użytkownika). Świadome odejście od
   konwencji `Funkcja_Autora`/`Grupa_Pracownicza`/`Wymiar_Etatu` z
   podkreślnikiem. URL-e admina: `/admin/bpp/stopiensluzbowy/`,
   `/admin/bpp/stanowiskodydaktyczne/`.
9. **Nowy branch** od `dev` (zrobione).
10. **Baseline** (`baseline-sql/`) — **NIE** odświeżamy w feature-branchu; refresh
    dopiero przy scalaniu (reguła projektu).

## 4. Zmiany domenowe (`bpp`)

### 4.1 Modele (`src/bpp/models/autor.py`)

```python
class StopienSluzbowy(NazwaISkrot):
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

- `Autor.stopien_sluzbowy = models.ForeignKey("bpp.StopienSluzbowy",
  models.SET_NULL, blank=True, null=True)` — obok `tytul`.
- `Autor_Jednostka.stanowisko = models.ForeignKey("bpp.StanowiskoDydaktyczne",
  models.SET_NULL, blank=True, null=True)` — obok `funkcja`.
- Eksport w `src/bpp/models/__init__.py`.

**Nazewnictwo (kolizja):** pole domenowe to `Autor_Jednostka.stanowisko` (czyste,
bo model = `StanowiskoDydaktyczne`). ALE w warstwie importu klucz `stanowisko`
jest już zajęty przez string FUNKCJI (legacy: `AutorForm.stanowisko` →
`Funkcja_Autora`). Dlatego wszystkie NOWE identyfikatory stanowiska dydaktycznego
w warstwie importu (cel mapowania, pole `AutorForm`, FK i `zrodlo_` na
`ImportPracownikowRow`) noszą nazwę `stanowisko_dydaktyczne` — patrz §9/§10.

**on_delete = `SET_NULL` (POTWIERDZONE w review):** `Tytul`/`Funkcja_Autora`
używają `CASCADE`, ale `Autor_Jednostka.grupa_pracownicza`/`wymiar_etatu` już
używają `SET_NULL` — jest więc precedens na tym samym modelu. Kasowanie słownika
opisowego nie powinno kasować autorów/zatrudnień → `SET_NULL`. Nie łamie adminów
(rejestracja przez `NazwaISkrotAdmin`, inline AJ w `admin/autor.py`).

### 4.2 Migracja `bpp`

Jedna migracja: 2 modele + 2 FK. Nazwa np.
`04XX_stopien_sluzbowy_stanowisko_dydaktyczne`. Zależność od najnowszej migracji
`bpp` na `dev` w chwili implementacji.

### 4.3 Admin (`src/bpp/admin/__init__.py`)

- Rejestracja `StopienSluzbowy` i `StanowiskoDydaktyczne` przez
  `NazwaISkrotAdmin` (jak `Tytul`).
- `stopien_sluzbowy` w formularzu/adminie `Autor` (obok tytułu).
- `stanowisko` w inline `Autor_Jednostka` (obok funkcji).

### 4.4 Menu „Dane systemowe" (`src/django_bpp/menu.py`)

- `SYSTEM_MENU_2`: dodać alfabetycznie
  `("Stanowiska dydaktyczne", "/admin/bpp/stanowiskodydaktyczne/")` i
  `("Stopnie służbowe", "/admin/bpp/stopiensluzbowy/")` (URL-e = lowercase
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

**Matchowanie — mirror `tytul.py` (NIE `iexact`) — finding review #7:**
`sklasyfikuj_tytul` CELOWO nie używa SQL `iexact`, tylko porównuje po
`normalize_tytul` w Pythonie, bo kropki/spacje psują exact
(`"dr hab." == "Dr. Hab"`). To samo dotyczy stopni: wszystkie 9 wartości z próbki
ma kropki (`mł. bryg.`, `st. kpt.`, `st. str.`…), więc `iexact` NIE złapie
wariantów `st.kpt.`/`st kpt`. Mirrorujemy: `normalize_stopien` /
`normalize_stanowisko` (usuń kropki, zredukuj spacje, lower) + porównanie
znormalizowane; „zgadywanie" = trigram ≥ próg krótkich stringów
(jak `PROG_ZGADYWANIA_TYTULU`, ~0.85 — NIE 0.7 jak jednostki).

## 6. Rozszerzenie dopasowania jednostki — „niepełna nazwa jednostki"

### 6.1 Klasyfikator

`import_common/core/jednostka.py`: nowa funkcja
`sklasyfikuj_jednostke_niepelna(fragment, wydzial=None, *, prog=...)`:

1. Najpierw `sklasyfikuj_jednostke` (exact/skrót) — jeśli `twardy`, zwróć.
2. `icontains` — **UWAGA (finding review #6): NIE używaj `_pula_afiliacyjna`**
   do szukania kandydatów. Ta pula wyklucza `jest_lustrem=True` i
   `rodzaj.autor_moze_afiliowac=False`, a po „Fazie B" wydział („Wydział
   Medyczny") jest zwykle **lustrem** → `icontains("Medyczny")` NIC by nie
   znalazło. Dla „niepełnej" szukamy w SZERSZYM zbiorze: `Jednostka.objects`
   filtrowane `nazwa__icontains` (± `Wydzial`), bez wykluczeń puli afiliacyjnej:
   - dokładnie 1 trafienie → `(obj, "zgadywanie", None)` (operator weryfikuje);
   - >1 trafień → najlepsze trigramowo, `"zgadywanie"`;
   - 0 → trigram fallback → `"zgadywanie"|"brak"`.

„niepełna" nazwa **nigdy** nie daje `twardy` z gałęzi `icontains` (zawsze
wymaga weryfikacji) — wynik ZAWSZE przez ekran `weryfikacja_jednostek`.

**Ograniczenia (udokumentowane):** (a) `icontains` NIE łapie odmiany fleksyjnej
(„Medyczny" ≠ „Medycznego"); (b) trigram na jednym krótkim słowie bywa hałaśliwy
— dlatego wynik zawsze do weryfikacji, nigdy auto-twardy.

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

Reguły szczegółowe (algorytm ZWERYFIKOWANY w review na wszystkich 31 wartościach):

- Skrót = pierwszy token pasujący do wzorca (`RW-1/1`, `RN-2`, `RW-9`).
- **Oddział — skanuj od tokenu 1 (NIE 0), finding review:** heurystyka „akronim"
  (len≥3, ≥2 wielkie litery) łapie też sam skrót `RW-1/1`, więc szukania oddziału
  NIE wolno zaczynać od tokenu skrótu. Oddział = pierwszy taki token PO skrócie
  (`WIBiOL`). Dla `RN-*` brak → oddział = None.
- **Ogon-znacznik — reguła zależna od oddziału (finding review):**
  - oddział ZNALEZIONY → ogon = **wszystko za oddziałem** (bez patrzenia na
    wielkość liter — inaczej `WIBiOL medyczne RM` zostawiłoby wielkoliterowe
    „RM"); nazwa = tokeny między skrótem a oddziałem.
  - BRAK oddziału (`RN-*`) → ogon = końcowy ciąg tokenów **all-lowercase**
    (`instytut ib`, `instytut bw`); nazwa = reszta. Łączniki w środku (`i`, `w`,
    `Ppoż.`) są w ŚRODKU → nie wpadają do końcowego ciągu.
  - brak ogona (`RW-6/3 Zakład Nauk Społecznych WIBiOL`) → nazwa do oddziału.

Wyjście do wiersza (**KLUCZOWE — finding review #5: skrót z pliku MUSI trafić do
`Jednostka.skrot` przy tworzeniu**):

- **Nie** sklejaj `nazwa (SKRÓT)` — `zaproponuj_skrot` odrzuca token `(RW-1/1)`
  (zaczyna się od `(`) i utworzyłby jednostkę z akronimem „ZKDRDGiŁ" + nawiasami
  w nazwie, gubiąc skrót z pliku (główny scenariusz APOŻ = tworzenie struktury).
  Zamiast tego parser zasila decyzję JAWNIE: `nazwa` = czysta nazwa (bez
  nawiasów), `skrot_sugerowany` = **skrót z pliku** (`RW-1/1`). Wymaga nowego
  parametru `skrot_hint` w `_ReconcilerJednostek.reconciluj` (nadpisuje domyślny
  `zaproponuj_skrot`). Dopasowanie do ISTNIEJĄCEJ jednostki: najpierw po skrócie
  (`Jednostka.objects.filter(skrot=skrót)`), potem po nazwie.
- **Wydział (hint) — finding review #6:** `matchuj_wydzial` robi tylko
  `nazwa__iexact`, a `WIBiOL` to SKRÓT (`Wydzial.skrot` istnieje, ale ten tor go
  nie używa) → emitowanie `wydział="WIBiOL"` jest MARTWE. Parser rozwiązuje
  oddział przez `Wydzial.objects.filter(skrot=oddział).first()` i emituje jego
  **nazwę** (`wydział = w.nazwa`) — tylko gdy znaleziony; inaczej pomija.
  (Alternatywa: dodać branch `skrot` do `matchuj_wydzial` — do decyzji w planie.)

**Test akceptacyjny:** wszystkie 31 wartości → poprawny (skrót, nazwa, oddział),
test tabelaryczny. Szczególnie: `RW-7/1 … WIBiOL medyczne RM` (ogon za oddziałem
z „RM"), `RN-1 … instytut ib` (ogon lowercase bez oddziału),
`RW-6/3 … WIBiOL` (brak ogona).

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
| `stopień_służbowy` | Stopień służbowy | stopień_służbowy, stopien_sluzbowy, stopień_pożarniczy, stopien_pozarniczy (**NIE** gołe „stopień" — patrz niżej) |
| `stanowisko_dydaktyczne` | Stanowisko dydaktyczne | stanowisko_dydakt, stanowisko_dydaktyczne, stanowisko_dyd |
| `stanowisko` (KEY bez zmian — tylko relabel + synonim) | Funkcja w jednostce | funkcja, funkcja_w_jednostce, stanowisko |
| `nazwisko_imię` | Nazwisko i imię (jedna komórka, nazwisko-first) | nazwisko_imię, nazwisko_imie |
| `komórka_złożona` | Komórka (skrót + nazwa + oddział + znacznik) | komórka, komorka, komorka_zlozona |
| `niepełna_nazwa_jednostki` | Niepełna nazwa jednostki | (bez auto-synonimu domyślnie; wybierany ręcznie) |

**Decyzja (finding review #9): NIE przejmujemy gołego synonimu `stopień`.**
Dziś `stopień`/`stopien` → `tytuł_stopień`, bo na typowej uczelni „stopień" =
stopień NAUKOWY (dr, dr hab.). Zmiana exact-synonimu zepsułaby auto-propozycję
KAŻDEGO istniejącego pliku (stopnie naukowe wpadłyby do słownika stopni
służbowych). Dlatego `stopień` ZOSTAJE → `tytuł_stopień`; stopień służbowy ma
własne, jednoznaczne synonimy (bez gołego „stopień"). `funkcja` relabel zmienia
tylko ETYKIETĘ + dokłada synonim `funkcja` — **KEY celu zostaje `stanowisko`**
(inaczej trzeba by zmigrować `ProfilMapowania.mapowanie` i `AutorForm.stanowisko`
→ ryzyko cichej utraty funkcji). Dla APOŻ operator mapuje „stopień" ręcznie na
„Stopień służbowy" RAZ i zapisuje profil — kolejne importy proponują ostatni
profil (§13). Spójne z „wszystko opt-in" (§1).

**`waliduj_mapowanie` — DWA rozszerzenia (finding review #3, KRYTYCZNE):**

1. **Identyfikacja osoby:** dziś wymaga (`nazwisko`+`imię`) LUB `osoba_sklejona`.
   Dodać `nazwisko_imię` jako TRZECIĄ alternatywę — inaczej plik APOŻ (kolumna
   „nazwisko imię") NIE przejdzie walidacji („Brak identyfikacji osoby") i cały
   feature jest martwy.
2. **Jednostka wymagana:** dziś tylko `nazwa_jednostki`. Dodać
   `nazwa_jednostki_niepelna` (cel `niepełna_nazwa_jednostki`) i `komórka_złożona`
   jako alternatywy.

Zakaz duplikatów celów — bez zmian.

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
  - `stopien` FK → `StopienSluzbowy`, `stopien_status`, `zrodlo_stopnia` FK →
    `ImportPracownikowStopien` (mirror `tytul`/`tytul_status`/`zrodlo_tytulu`).
  - `stanowisko_dydaktyczne` FK → `StanowiskoDydaktyczne`,
    `stanowisko_dydaktyczne_status`, `zrodlo_stanowiska_dydaktycznego` FK →
    `ImportPracownikowStanowisko`. (NIE `stanowisko` — ten klucz w warstwie
    importu oznacza string FUNKCJI; patrz §4.1 „Nazewnictwo".)
- `AutorForm`: dodać pola `email`, `stopień_służbowy`, `stanowisko_dydaktyczne`
  (wszystkie `required=False`; wartości tekstowe z pliku, klasyfikacja/FK liczona
  później). **E-mail — łagodna walidacja (finding review):** `analyze` przy
  niepoprawnym formularzu rzuca `XLSParseError` bez per-wiersz recovery — jeden
  zepsuty adres w pliku kadrowym wywaliłby CAŁY run. `email` musi być
  tolerancyjny: niepoprawny adres → puste + ostrzeżenie w audycie, NIE wyjątek
  (`CharField` z miękką walidacją albo czyszczenie przed `full_clean`).

Migracja `import_pracownikow`: 2 modele decyzji + pola toggle + pola na Row.

## 11. Pipeline

### 11.0 Umiejscowienie w przepływie dwustopniowym (ROZSTRZYGNIĘTE)

**Zasada (potwierdzona z użytkownikiem):** weryfikujemy **wszystkie słowniki
PRZED wejściem w Krok 2 (osoby)**. Sekwencja weryfikacji Kroku 1:

```
Krok 1 (struktura / słowniki) — nie dotyka Autor/Autor_Jednostka:
    1. jednostki   → weryfikacja_jednostek
    2. tytuły      → weryfikacja_tytulow
    3. stopnie     → weryfikacja_stopni        (NOWE)
    4. stanowiska  → weryfikacja_stanowisk     (NOWE)
  → tworzone są REKORDY słowników; stan = STRUKTURA_ZINTEGROWANA

Krok 2 (osoby):
  → dla dopasowanego/utworzonego autora DOCZEPIAMY już-rozstrzygnięte FK:
    Autor.stopien_sluzbowy, Autor_Jednostka.stanowisko (+ tytuł, funkcja, email)
```

**Dlaczego to spójne (nie ma dziury):** `StopienSluzbowy` i
`StanowiskoDydaktyczne` to **słowniki** — dokładnie jak `Tytul`. Rekord słownika
(np. „kpt.", „adiunkt") powstaje w Kroku 1 (faza struktury). Samo *dopięcie* FK
wymaga istniejącego `Autor`/`Autor_Jednostka`, które powstają dopiero w Kroku 2 —
więc dopięcie ląduje w fazie osób. To lustro obecnego zachowania tytułów:
`_rozstrzygnij_tytuly` tworzy `Tytul` w fazie struktury, a `row.tytul` dopina się
do autora w fazie osób.

**Mechanika w `integruj` (`pipeline/integrate.py`):**

- Faza struktury jest gated `zakres != ZAKRES_JEDNOSTKI` i robi early-exit do
  `STAN_STRUKTURA_ZINTEGROWANA`. Rozstrzyganie stopni/stanowisk dokładamy
  **obok** `_rozstrzygnij_tytuly` w tej fazie (przed early-exitem) —
  `_rozstrzygnij_stopnie`, `_rozstrzygnij_stanowiska`.
- Dla `ZAKRES_STRUKTURA` (sama struktura): utworzą się rekordy słowników
  stopni/stanowisk, ale **żaden** `Autor`/`Autor_Jednostka` nie jest tknięty
  (early-exit). To jest zamierzone i zgodne z semantyką „Krok 1".
- Dla `ZAKRES_PELNY`: po fazie struktury (rozstrzygnięcie słowników) lecimy
  dalej w fazę osób, gdzie dopinamy `Autor.stopien_sluzbowy` (no-overwrite) i
  `Autor_Jednostka.stanowisko`.
- **Bramka Kroku 2:** wejście w import osób jest dozwolone dopiero, gdy
  wszystkie decyzje słownikowe są rozstrzygnięte (jednostki + tytuły + stopnie +
  stanowiska) — rozszerzyć istniejącą „bramkę tytułów" o stopnie i stanowiska
  (patrz `przeglad.html` i logika stanu). Tak jak dziś nie wchodzi się w osoby z
  nierozstrzygniętymi tytułami, tak samo z nierozstrzygniętymi stopniami/
  stanowiskami.

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
- **KRYTYCZNE (finding review #1) — auto-skip Krok 1→2:** dziś
  `struktura_bez_decyzji = not jednostki_do_decyzji.exists() and not
  tytuly_do_decyzji.exists()` skacze od razu do `STRUKTURA_ZINTEGROWANA`, a
  ekrany weryfikacji są edytowalne tylko w `PRZEANALIZOWANY`. Bez zmiany: plik z
  twardymi jednostkami/tytułami, ale z decyzjami stopni/stanowisk, wyląduje w
  Kroku 2 z decyzjami, których user NIE może już edytować. Rozszerzyć warunek o
  `stopnie_do_decyzji` i `stanowiska_do_decyzji` (i/lub odblokować edycję ekranów
  w `struktura_zintegrowana`).

### 11.2 `pipeline/integrate.py`

- FAZA słowników (obok tytułów, gated `zakres != ZAKRES_JEDNOSTKI`):
  `_rozstrzygnij_stopnie`, `_rozstrzygnij_stanowiska`
  (mirror `_rozstrzygnij_tytuly`; `unikalny_skrot_*` mirror
  `unikalny_skrot_tytulu`), `_podlacz_wiersze_do_{stopni,stanowisk}`.
- **KRYTYCZNE (finding review #4) — predykaty zmian.** `check_if_integration_
  needed` (`_check_autor_needs_update` / `_check_autor_jednostka_needs_update`)
  NIE zna nowych pól → wiersz, którego JEDYNĄ zmianą jest stopień/stanowisko,
  dostanie `zmiany_potrzebne=False` i nigdy nie wejdzie w `integrate()`
  (`_integruj_wiersz` iteruje `zmiany_potrzebne_set`). Trzeba:
  - `_check_autor_needs_update` += stopień (no-overwrite aware:
    `self.stopien_id is not None and autor.stopien_sluzbowy_id is None`);
  - `_check_autor_jednostka_needs_update` += stanowisko dydaktyczne (analogicznie
    na AJ);
  - MONOTONICZNY recompute `zmiany_potrzebne` w `_podlacz_wiersze_do_{stopni,
    stanowisk}` (mirror `_podlacz_wiersze_do_tytulow`).
- Krok 2 (osoby) — miejsca zapisu:
  - `Autor.stopien_sluzbowy` ← rozstrzygnięty stopień, **no-overwrite** (ustaw
    gdy puste u istniejącego; nowym zawsze). Dopiąć w `_integrate_autor` ORAZ
    `_przygotuj_nowego_autora` (`Autor.objects.create(...)` — tam TEŻ `email`).
  - `Autor_Jednostka.stanowisko` ← rozstrzygnięte stanowisko; dopiąć w
    `_integrate_autor_jednostka` / `_materializuj_diff` (mirror `funkcja`).
  - `email`: nowy autor → zapis w `Autor.objects.create`; istniejący → **bez
    zmian** (tylko porównywarka).
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
- **KRYTYCZNE (finding review #2) — bramka „wymagają rozstrzygnięcia".** Dziś
  `ZatwierdzImportView` (zakres PELNY) blokuje wejście w osoby tylko na
  `tytuly_wymagaja_rozstrzygniecia` (property w `models.py`). Bez mirrorów:
  ścieżka „Zapisz tylko jednostki" (ZAKRES_JEDNOSTKI) zostawia decyzje stopni/
  stanowisk nierozstrzygnięte, a `integruj` w PELNY wykona
  `_rozstrzygnij_stopnie/_stanowiska` z domyślną `decyzja=AKCEPTUJ` → CICHE
  tworzenie (to, co item 3 wyeliminował dla tytułów). Dodać
  `stopnie_wymagaja_rozstrzygniecia` / `stanowiska_wymagaja_rozstrzygniecia`
  (mirror property tytułów) i rozszerzyć warunek 400 w `ZatwierdzImportView`.
- `MapowanieForm`: dodać checkboxy `tworz_brakujace_stopnie` /
  `tworz_brakujace_stanowiska` + `update_fields` w `form_valid`.
- Teksty: opis `ZAKRES_STRUKTURA` (`models.py`: „jednostki + tytuły (bez osób)"
  → dodać stopnie/stanowiska) i przyciski w `przeglad.html`.

## 13. Profil ostatnio użyty (`views.py` + `mapping.py`)

- **Korekta (finding review #8):** `ostatnio_uzyty` JUŻ jest ustawiane przy
  ZAPISIE profilu (`views.py` `update_or_create(..., ostatnio_uzyty=now())`,
  commit `7be75739a`). Do zrobienia zostaje TYLKO:
  - stemplowanie przy ZASTOSOWANIU profilu — w `form_valid` (NIE w GET; zapis DB
    w GET psuje idempotencję refreshy/prefetchy), gdy mapowanie pochodziło z
    profilu;
  - fallback wyboru profilu (niżej).
- Sugestia w `MapowanieView.get_form_kwargs`/kontekście (`views.py` ~207-213 —
  tu wpiąć fallback PO `dopasuj_profil`):
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
- **E2E:** przejście `struktura.xlsx` (Krok 1 → słowniki → Krok 2 → osoby).
  **Uwaga (finding review):** testowy baseline (testcontainers) NIE zawiera
  struktur APOŻ (WIBiOL/RW-*), więc test musi sam przejść Krok 1 (utworzenie
  jednostek po skrócie + tytułów + stopni + stanowisk) albo zaseedować przez
  `baker`. Izolacja Playwright/asyncio jak w `conftest.py` (pamięć: wyciek pętli).

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
- **`on_delete` słowników** = `SET_NULL` — POTWIERDZONE (precedens
  `grupa_pracownicza`/`wymiar_etatu` na `Autor_Jednostka`).
- **E-mail wywala analizę:** walidacja `AutorForm` jest fail-fast
  (`XLSParseError` bez per-wiersz recovery) — e-mail musi być tolerancyjny (§10).
- **Kolejność migracji** vs równoległe branche na `dev` (denorm_init invariant —
  patrz pamięć). Nowe modele bez denorm, więc niskie ryzyko. Najnowsza migracja
  bpp na dev to 0467 → nowa 0468+.
- **Parser komórki** dostrojony do konwencji APOŻ; dla innych uczelni oddział/
  ogon mogą wyglądać inaczej — dlatego opt-in i dopasowanie głównie po skrócie.
- **`stopień` NIE przejęty** (§9) — APOŻ mapuje ręcznie + zapisuje profil.
```
