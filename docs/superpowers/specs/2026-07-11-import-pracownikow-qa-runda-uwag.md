# Import pracowników — runda uwag QA (2026-07-11, wieczór)

Zebrane uwagi z sesji przeglądu UI/UX importu pracowników i jednostek.
Bazuje na dwustopniowym flow (Krok 1 struktura → Krok 2 osoby) już obecnym
na `dev`. **Status: SPEC — jeszcze NIC nie zaimplementowane w tej rundzie.**

Branch roboczy (proponowany): `fix/import-pracownikow-qa-runda-uwag`.

Pliki, których dotyczy większość zmian:
- `src/import_pracownikow/templates/import_pracownikow/przeglad.html`
- `src/import_pracownikow/templates/import_pracownikow/import_pracownikow_result.html`
- `src/import_pracownikow/models.py`
- `src/import_pracownikow/views.py`
- `src/import_pracownikow/forms.py`
- `src/import_pracownikow/pewnosc.py` (nowy status)
- `src/import_pracownikow/pipeline/analyze.py` / `integrate.py`
- nowa migracja + odświeżenie baseline (przy merge, nie w gałęzi równoległej)

Decyzje projektowe rozstrzygnięte z użytkownikiem:
- **Item 3**: bramka tytułów = *wymuś rozstrzygnięcie* (mirror bramki jednostek).
- **Item 6**: log = *osobny ekran audytu*.
- **Item 7**: ręczny match = *nowy status `ręczny`* (confidence).

---

## Lista rzeczy do zrobienia

### 1. Kontrast przycisku „Zweryfikuj jednostki" — DO ZROBIENIA
Przycisk `button primary` siedzi na `callout primary` (ciemny na ciemnawym tle,
źle czytelny). Zmienić na czytelny wariant (np. `button success` albo jaśniejszy)
w OBU miejscach: górny callout Kroku 1 oraz kafelek „Jednostki" (audyt poza flow).
- Plik: `przeglad.html` (linie ~34, ~100). Sprawdzić analogiczne „Zweryfikuj tytuły".
- Bez migracji, czysto szablon/CSS.

### 2. „Zobacz tytuły" gdy tytuły są dopasowane — DO ZROBIENIA
Gdy wszystkie tytuły z pliku dopasowały się dokładnie, nie ma żadnego kafelka
tytułów, więc user nie widzi, co się stanie z tytułami. Chce podglądu „jakie
będą dodane".
- W Kroku 1 dodać linię tytułów analogiczną do jednostek (liczniki
  `do_utworzenia · do_sprawdzenia`) + przycisk **„Zobacz tytuły"** linkujący do
  ekranu weryfikacji tytułów.
- Rozważyć: ekran weryfikacji tytułów pokazuje TYLKO nierozstrzygnięte. Dla
  transparentności dodać sekcję „dopasowane dokładnie" (source → istniejący
  tytuł), żeby „Zobacz tytuły" miał zawsze co pokazać.
- Powiązane z Item 3 (bramka) — patrz niżej.

### 3. Bramka tytułów przed importem osób — DO ZROBIENIA
**Decyzja: wymuś rozstrzygnięcie.** Import osób (Krok 2, `zakres=pelny`)
zablokowany, dopóki są nierozstrzygnięte tytuły z pliku (`tytuly_do_decyzji`
z niedopasowaniem). Mirror istniejącej bramki jednostek.
- Konsekwencja: ścieżka „Zapisz tylko jednostki" zostawia tytuły
  nierozstrzygnięte → nie odblokowuje importu osób. W praktyce trzeba użyć
  „Zapisz jednostki + tytuły" (albo najpierw ręcznie rozstrzygnąć tytuły).
- Do przemyślenia w implementacji: obecnie OBA zakresy strukturalne ustawiają
  `STAN_STRUKTURA_ZINTEGROWANA` (odblokowuje Krok 2). Bramka musi dodatkowo
  sprawdzać „brak nierozstrzygniętych tytułów" — albo w `faza_osob`/hub, albo
  w `ZatwierdzImportView` dla `zakres=pelny`. Wybrać jedno spójne miejsce.
- UI: w Kroku 2 pokazać wyraźny komunikat „najpierw rozstrzygnij N tytułów"
  z linkiem, zamiast cichej blokady.
- Pilnować, żeby nie zablokować importów bez żadnych tytułów w pliku.
- Testy: import z niedopasowanym tytułem po „tylko jednostki" → osoby
  zablokowane; po rozstrzygnięciu → odblokowane.

### 4. Auto-przejście po „struktura zapisana" — DO ZROBIENIA
Po integracji struktury `get_success_url` zwraca `None` → user zostaje na
panelu wyniku liveops (jest ręczny przycisk „Przejdź do importu osób").
User chce AUTO-redirect na hub (Krok 2) + flash message.
- `models.py get_success_url`: dla `STAN_STRUKTURA_ZINTEGROWANA` zwróć
  `reverse("import_pracownikow:przeglad", pk=...)` zamiast `None`.
- Flash message („Struktura zapisana — przejdź do importu osób") przez
  `messages` — uwaga: `get_success_url` woła się w `on_commit`, sprawdzić czy
  `request`/`messages` są dostępne; jeśli nie, flash ustawić w widoku wyniku
  albo na hubie na podstawie stanu.
- Panel wyniku zostaje jako fallback dla no-JS.
- Testy: liveops test na redirect (jak istniejący dla analizy).

### 5. Układ Kroku 2 (osoby) — DO ZROBIENIA
Obecnie przycisk „Zapisz osoby do bazy" jest od razu na górze Kroku 2. User chce:
- W callout „Krok 2" NIE dawać przycisku od razu.
- Wewnątrz Kroku 2 wyświetlić kafle „Ludzie z XLS" + „Ludzie spoza XLS"
  (obecnie renderowane niżej w `.row`) — przenieść je do środka.
- Przycisk „Zapisz osoby do bazy" NA SAMYM KOŃCU, z potwierdzeniem, że
  „to zmieni bazę danych — czy zapisać?" (inline checkbox „rozumiem…"
  odblokowujący przycisk, albo natywny `confirm()`; preferowany inline).
- Plik: `przeglad.html` — restrukturyzacja bloku `moze_importowac_osoby`
  i `pokaz_ludzi`.

### 6. Ekran audytu (log przepięć / przepisań / utworzeń) — DO ZROBIENIA
**Decyzja: osobny ekran audytu.** Integracja już zapisuje per-wiersz
`log_zmian` (`utworzono`, `przepiecie` {z→do, prace_ciągłe/zwarte},
`przepiecie_pominiete`) oraz `nowy_autor`, a `odpiecia` mają swój model.
Brakuje przeglądarki szczegółów.
- Nowa podstrona (np. `import_pracownikow:audyt` / „Log zmian") listująca
  per-wiersz: utworzono autora/jednostkę/tytuł, przepięto prace (z→do, liczba),
  odpięto, pominięto (nieaktualne / niedopasowane / bez jednostki).
- Źródła: `importpracownikowrow_set` (`log_zmian`, `diff_do_utworzenia`) +
  `parent.odpiecia`.
- Linki: z panelu wyniku integracji i z huba (kafelek / przycisk „Log zmian").
- Widoczne dopiero po integracji (`STAN_ZINTEGROWANY`).
- Testy: po integracji z przepięciem/odpięciem/nowym autorem ekran pokazuje
  właściwe wpisy.

### 7. Status „ręczny" vs „twardy match" — DO ZROBIENIA
**Decyzja: nowy status `ręczny`.** Ręczny wybór autora
(`_zwiaz_autora_z_wierszem` w `views.py`) ustawia `confidence=STATUS_TWARDY`
→ badge kłamie „twardy match". Dodać dedykowany status.
- `pewnosc.py`: `STATUS_RECZNY = "reczny"`; wpis w `STATUS_CHOICES` i
  `STATUS_DISPLAY` (własna ikona/etykieta, np. „wybór użytkownika",
  `fi-pencil`/`fi-torso`).
- `views.py _zwiaz_autora_z_wierszem`: ustaw `STATUS_RECZNY` zamiast
  `STATUS_TWARDY` (dotyczy `WybierzKandydataView` i `DopasujAutoraView`).
- `models.py`: `confidence` choices change → migracja (tylko choices, bez
  zmiany schematu — pole i tak `CharField`).
- Przejrzeć WSZYSTKICH konsumentów `STATUS_TWARDY`/statusów:
  - `liczniki_ludzi_z_xls` (kafelek „Ludzie z XLS") — dodać/rozliczyć „ręczny"
    (nie może wpaść w „brak" przez koalescencję).
  - `ludzie_do_akceptacji = wielu + brak` — ręczny to rozstrzygnięcie usera,
    NIE liczy się „do akceptacji" (OK, ale zweryfikować).
  - `PrzelaczUtworzNowegoView` gard `confidence != STATUS_BRAK` — bez zmian.
  - Filtry integracji (`confidence=STATUS_BRAK`, `confidence__in=[BRAK,WIELU]`)
    — ręczny ich nie dotyczy (autor ustawiony), zweryfikować.
- Testy: po ręcznym wyborze wiersz ma `confidence=reczny`, badge inny niż
  twardy; liczniki się zgadzają.

### 8. Data zmian personalnych na formularzu importu — DO ZROBIENIA
Na formularzu tworzenia importu pytać o **datę zmian personalnych** z XLSX,
z opisem, że zostanie użyta jako **data początku pracy** przy dopisywaniu
autora do jednostki.
- Nowe pole modelu: `data_zmian_personalnych` (DateField, `null=True, blank=True`).
- Formularz: dodać pole (patrz Item „gdzie" niżej) z help-textem.
- Użycie: w analizie/integracji jako domyślna data początku AJ, gdy wiersz nie
  ma własnej daty zatrudnienia. **UWAGA**: pogodzić z polityką „no-overwrite"
  z Issue #4 (data z wiersza wygrywa; globalna tylko wypełnia brak).
- Migracja + baseline.
- Do potwierdzenia w implementacji: czy globalna data NADPISUJE, czy tylko
  UZUPEŁNIA brak per-wiersz (założenie: uzupełnia brak).

### 9. Checkbox „zaznacz wszystkie prace do przepięcia" na formularzu — DO ZROBIENIA
Na formularzu tworzenia importu checkbox **„Zaznaczaj domyślnie WSZYSTKIE prace
do przepisania na nowe jednostki"** z help-textem:
- ZAZNACZONE gdy: świeża baza, import struktury autorów PO imporcie do PBN.
- NA PEWNO ODZNACZONE gdy: „dojrzała" baza produkcyjna.
- Nowe pole modelu: `przepnij_wszystkie_prace` (BooleanField, `default=False`).
- Efekt: podczas analizy ustawia per-wiersz `przepnij_prace=True` domyślnie
  (patrz `analyze.py`) — z zachowaniem istniejących guardów kwalifikacji
  przepięcia (F1/F2/F3 — nie przepinać par z pliku itd.).
- Migracja + baseline.

### Gdzie umieścić pola z Item 8 + 9 (do potwierdzenia)
User pisze „na początku formularza jak tworzysz import". Kandydaci:
- `NowyImportForm` (upload, `plik_xls`) — najbardziej dosłowne „na początku",
  ale parametry analizy (`tworz_brakujace_*`) są dziś na `MapowanieForm`.
- `MapowanieForm` (drugi ekran) — spójne z resztą parametrów analizy.
- **Rekomendacja**: `NowyImportForm` (zgodnie z „na początku"), pola zapisywane
  na modelu przy tworzeniu; analiza (późniejsza) je czyta. Potwierdzić z userem
  jeśli będzie tarcie.

---

## Uwagi wspólne / kolejność

- **Migracje**: Items 7, 8, 9 dodają pola/choices → jedna wspólna migracja na
  końcu gałęzi. Baseline odświeżyć DOPIERO przy merge (nie w równoległych
  branchach — konflikt na wielkim pliku).
- **Testy**: każdy item z logiką (3, 4, 6, 7, 8, 9) dostaje test pytest
  (konwencja projektu — model_bakery, `@pytest.mark.django_db`, bez klas).
- **Sugerowana kolejność** (od najtańszych/najbezpieczniejszych):
  1. Item 1 (kontrast) — trywialne.
  2. Item 4 (auto-redirect) — mały, izolowany.
  3. Item 5 (układ Kroku 2) — szablon.
  4. Item 7 (status ręczny) — model+migracja, dużo konsumentów do przejrzenia.
  5. Item 2 + 3 (tytuły: podgląd + bramka) — razem, spójne.
  6. Item 8 + 9 (pola formularza) — razem, jedna migracja.
  7. Item 6 (ekran audytu) — największy, na końcu.
  8. Migracja zbiorcza (7/8/9) + baseline przy merge.
