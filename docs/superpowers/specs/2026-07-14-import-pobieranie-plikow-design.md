# Import pracowników i jednostek — pobieranie plików (oryginał + „po imporcie")

Data: 2026-07-14
Moduł: `src/import_pracownikow/`

## Cel

Na stronie rezultatów importu pracowników udostępnić dwa pobierania:

1. **Pobierz oryginał** — dokładnie ten plik XLSX, który użytkownik wgrał.
   Plik jest chroniony (leży w `protected/`, NGINX nie serwuje go bezpośrednio),
   dostępny tylko dla zalogowanych z uprawnieniami do modułu.

2. **Pobierz plik „po imporcie"** — kanoniczny, **SKORYGOWANY** XLSX
   odzwierciedlający **to, co faktycznie trafiło do BPP**. „Skorygowany" =
   plik naprawia bałagan z wejścia: każda wartość jest **odczytana z
   autorytatywnego rekordu w bazie** (nie echem z pliku), więc błędne/niepełne
   nazwy jednostek, literówki w nazwiskach, skróty tytułów itd. wychodzą jako
   **poprawne wartości z BPP**. Ma być tak zbudowany, żeby ponowny import tego
   pliku przeszedł bezobsługowo („bardzo gładko"): kanoniczne nagłówki
   auto-rozpoznawane przez importer, kanoniczne wartości z bazy, kolumna
   `BPP ID` kotwicząca autora po identyfikatorze.

   **Semantyka „skorygowany" (kluczowa):** wartości NIE pochodzą z pliku ani z
   *proponowanych* przez analizę FK wiersza — pochodzą z **rzeczywistych
   rekordów** utworzonych/zaktualizowanych w bazie:
   - pola **autora** → z `row.autor` (`Autor`): `nazwisko`, `imiona`, `tytul`,
     `stopien_sluzbowy`, `orcid`, `pbn_uid`, `system_kadrowy_id`, `email`;
   - pola **zatrudnienia** → z `row.autor_jednostka` (`Autor_Jednostka`):
     `jednostka`, `wymiar_etatu`, `funkcja` (= „Funkcja w jednostce"),
     `stanowisko` (= `StanowiskoDydaktyczne`!), `grupa_pracownicza`,
     `rozpoczal_prace`/`zakonczyl_prace`, `podstawowe_miejsce_pracy`.

   Dzięki temu plik pokazuje **stan BAZY po korekcie**, nawet gdy import nie
   nadpisał jakiegoś pola (polityki no-overwrite) — wtedy w pliku jest wartość
   z bazy, a nie sprzeczna wartość z pliku wejściowego.

## Kontekst techniczny (stan istniejący)

- Wgrany plik: pole `ImportPracownikow.plik_xls`
  (`upload_to="protected/import_pracownikow/"`).
- Serwowanie chronionych plików: `django_sendfile`
  (`from django_sendfile import sendfile`) — backend nginx w produkcji, simple
  lokalnie. Wzorce: `src/oswiadczenia/views.py`, `src/bpp/views/__init__.py`,
  `src/zglos_publikacje/admin/`.
- Gating dostępu: `braces.views.GroupRequiredMixin`,
  `GROUP_REQUIRED = "wprowadzanie danych"` (cały moduł).
- Mapowanie kolumn: `ImportPracownikow.mapowanie_kolumn` = JSON
  `{nagłówek_pliku: pole_kanoniczne}`; wartość `"__pomin__"` (`mapping.POLE_POMIN`)
  = kolumna zignorowana. Zbiór pól kanonicznych + etykiety: `mapping.POLA_DOCELOWE`.
- Auto-rozpoznawanie nagłówków: `mapping._SYNONIMY` (znormalizowany nagłówek →
  pole) + `mapping.pole_dla_naglowka(...)`. Import **dopasowuje autora po
  `bpp_id`** (`pipeline/analyze.py`), więc kolumna `BPP ID` w pliku „po imporcie"
  = jednoznaczne trafienie w autora przy re-imporcie.
- Wiersze importu: `ImportPracownikowRow`; kolejność oryginalna z pliku dostępna
  przez `ImportPracownikow.get_details_set()` (annotacja `__xls_loc_row__`,
  `select_related` → bez N+1). Każdy wiersz trzyma FK do rozwiązanych obiektów
  BPP: `autor`, `jednostka`, `tytul`, `stopien`, `stanowisko_dydaktyczne`,
  `funkcja_autora`, `grupa_pracownicza`, `wymiar_etatu`, `autor_jednostka`,
  `podstawowe_miejsce_pracy`.
- Daty zatrudnienia, które trafiły do bazy: `Autor_Jednostka.rozpoczal_prace` /
  `zakonczyl_prace` (przez `row.autor_jednostka`).
- Stan zakończenia: `ImportPracownikow.stan == STAN_ZINTEGROWANY`
  (`"zintegrowany"` — osoby zaimportowane; `STAN_STRUKTURA_ZINTEGROWANA` to
  dopiero zapisana struktura, za wcześnie na plik „po imporcie").
- XLSX zapis: `openpyxl` (już w zależnościach).
- **Bez zmian w modelach → bez migracji.**

---

## Feature A — Pobierz oryginał

### URL
`src/import_pracownikow/urls.py`:
```
path("<uuid:pk>/pobierz-oryginal/", views.PobierzOryginalView.as_view(),
     name="pobierz-oryginal"),
```

### Widok
`PobierzOryginalView(GroupRequiredMixin, View)` w `views.py`:
- `group_required = GROUP_REQUIRED` (spójnie z modułem).
- `get(self, request, pk)`: pobiera `ImportPracownikow` (404 gdy brak).
- Gdy `not obj.plik_xls` lub plik nie istnieje na dysku → `Http404`
  z czytelnym komunikatem.
- Zwraca:
  ```python
  return sendfile(
      request,
      obj.plik_xls.path,
      attachment=True,
      attachment_filename=<nazwa oryginalna>,
  )
  ```
- **Nazwa pobieranego pliku**: `os.path.basename(obj.plik_xls.name)`
  (oryginalna nazwa wgranego pliku).

### Bezpieczeństwo
Plik już leży w `protected/import_pracownikow/`. `sendfile` (X-Accel-Redirect
w nginx) to jedyna droga wydania — bezpośredni URL `/media/protected/...` jest
zablokowany na poziomie nginx (jak dla `oswiadczenia`). Dostęp gejtowany grupą
`"wprowadzanie danych"`. Nie dodajemy pliku do żadnego publicznego katalogu.

---

## Feature B — Pobierz plik „po imporcie"

Kanoniczny, re-importowalny XLSX generowany w locie (openpyxl → `BytesIO`, **nie
zapisywany na dysk**), gejtowany tą samą grupą, dostępny **tylko po finalizacji**
(`stan == STAN_ZINTEGROWANY`).

### URL
```
path("<uuid:pk>/pobierz-po-imporcie/", views.PobierzPoImporcieView.as_view(),
     name="pobierz-po-imporcie"),
```

### Widok
`PobierzPoImporcieView(GroupRequiredMixin, View)`:
- `group_required = GROUP_REQUIRED`.
- 404 gdy import nie istnieje.
- Gdy `obj.stan != STAN_ZINTEGROWANY` → `Http404` (albo redirect na rezultaty
  z `messages.warning`) — plik „po imporcie" ma sens tylko po zapisie osób.
- Buduje bajty przez `eksport.zbuduj_plik_po_imporcie(obj)` i zwraca
  `HttpResponse(content, content_type=<xlsx>)` z nagłówkiem
  `Content-Disposition: attachment; filename="<stem>-po-imporcie.xlsx"`,
  gdzie `<stem>` = nazwa oryginału bez rozszerzenia.

### Builder — `src/import_pracownikow/eksport.py` (NOWY moduł)

Funkcja czysta, testowalna bez requestu:
`def zbuduj_plik_po_imporcie(import_obj) -> bytes`.

#### 1. Wybór wierszy
Iteruj `import_obj.get_details_set()` (oryginalna kolejność, `select_related`).
**Pomiń wiersze „pominięte"**: warunek `row.autor_id is None`
(tożsamy z `row.do_pominiecia` — wiersz nie utworzył/nie dopiął autora, nic nie
trafiło do BPP). Do pliku trafiają wyłącznie wiersze z ustawionym `autor`.

#### 2. Wybór kolumn
Zbiór użytych pól: `uzyte = set(import_obj.mapowanie_kolumn.values()) - {POLE_POMIN}`.

Kolumna wyjściowa jest emitowana, jeśli:
- jest **kotwicą tożsamości** (zawsze): `BPP ID`, `Nazwisko`, `Imię`,
  `Nazwa jednostki`; **lub**
- jest **wzbogaceniem tożsamości** (`ORCID`, `PBN UUID`, `Numer`): gdy target
  użyty **lub** ≥1 eksportowany wiersz ma niepustą wartość (unikamy pustej
  kolumny‑szumu); **lub**
- jest **atrybutem** i jej target należy do `uzyte`.

**Kolumny zignorowanego wejścia (np. „dyscypliny naukowe") NIE pojawiają się** —
bo ich target = `__pomin__`, więc nie ma ich w `uzyte`.

Kilka targetów wejściowych **kolapsuje** do jednej kolumny kanonicznej:
- warianty nazwy osoby (`osoba_sklejona`, `nazwisko_imię`) → zawsze i tak
  emitujemy kanoniczne `Nazwisko` + `Imię` z bazy (autor), niezależnie od formy
  w oryginale;
- warianty jednostki (`nazwa_jednostki`, `nazwa_jednostki_niepelna`,
  `komórka_złożona`, `wydział`) → jedna kolumna `Nazwa jednostki`
  = `AJ.jednostka.nazwa` (autorytatywna nazwa z zatrudnienia w bazie);
- warianty wymiaru (`wymiar_etatu_tekst`, `wymiar_etatu_ulamek`) → jedna kolumna
  `Wymiar etatu`.

#### 3. Rejestr kolumn kanonicznych (kolejność + nagłówek + wartość)

Kolejność w pliku: blok tożsamości, potem atrybuty zatrudnienia.

Kolumna „Wartość z BPP" = **autorytatywny rekord bazy** (`A` = `row.autor`,
`AJ` = `row.autor_jednostka`), NIE proponowane FK wiersza.

| # | Nagłówek (kanoniczny) | Target(y) włączające | Wartość z BPP (autorytatywna) | Emisja |
|---|---|---|---|---|
| 1 | `BPP ID` | — | `A.pk` (`row.autor_id`) | ZAWSZE |
| 2 | `Nazwisko` | `nazwisko`/`osoba_sklejona`/`nazwisko_imię` | `A.nazwisko` | ZAWSZE |
| 3 | `Imię` | `imię`/`osoba_sklejona`/`nazwisko_imię` | `A.imiona` | ZAWSZE |
| 4 | `ORCID` | `orcid` | `A.orcid` | użyty ∨ niepusty |
| 5 | `PBN UUID` | `pbn_uuid` | `A.pbn_uid_id` | użyty ∨ niepusty |
| 6 | `Numer` | `numer` | `A.system_kadrowy_id` | użyty ∨ niepusty |
| 7 | `E-mail` | `email` | `A.email` | użyty |
| 8 | `Nazwa jednostki` | warianty jednostki | `AJ.jednostka.nazwa` | ZAWSZE |
| 9 | `Tytuł` | `tytuł_stopień` | `str(A.tytul)` | użyty |
| 10 | `Stopień służbowy` | `stopień_służbowy` | `str(A.stopien_sluzbowy)` | użyty |
| 11 | `Funkcja w jednostce` | `stanowisko` | `str(AJ.funkcja)` | użyty |
| 12 | `Stanowisko dydaktyczne` | `stanowisko_dydaktyczne` | `str(AJ.stanowisko)` | użyty |
| 13 | `Grupa pracownicza` | `grupa_pracownicza` | `str(AJ.grupa_pracownicza)` | użyty |
| 14 | `Wymiar etatu` | warianty wymiaru | `str(AJ.wymiar_etatu)` | użyty |
| 15 | `Data zatrudnienia` | `data_zatrudnienia` | `AJ.rozpoczal_prace` | użyty |
| 16 | `Data końca zatrudnienia` | `data_końca_zatrudnienia` | `AJ.zakonczyl_prace` | użyty |
| 17 | `Podstawowe miejsce pracy` | `podstawowe_miejsce_pracy` | `T`/`N` z `AJ.podstawowe_miejsce_pracy` | użyty |

Uwagi:
- **PUŁAPKA nazewnictwa** (potwierdzona w modelu): target `stanowisko` =
  „Funkcja w jednostce" = `AJ.funkcja` (`Funkcja_Autora`); a `StanowiskoDydaktyczne`
  siedzi w `AJ.stanowisko`. Nie pomylić tych dwóch.
- **`stopien_sluzbowy` i `tytul` są na `Autor`** (nie na zatrudnieniu ani na
  wierszu) — czytać z `A`, bo tam jest autorytatywna, skorygowana wartość.
- **Gdy `row.autor_jednostka is None`** (autor wszedł, ale zatrudnienie odroczone/
  nie powstało) — kolumny z `AJ` (8, 11–17) zostają **puste**; wiersz i tak jest
  eksportowany (autor trafił do BPP). Kolumna `Nazwa jednostki` (ZAWSZE) też
  będzie wtedy pusta — to uczciwe odbicie stanu bazy.
- **Nagłówki muszą być rozpoznawane** przez `mapping.pole_dla_naglowka` — przy
  implementacji zweryfikować każdy nagłówek względem `_SYNONIMY`; jeśli któryś
  długi label z `POLA_DOCELOWE` nie normalizuje się do synonimu, użyć
  najkrótszej rozpoznawanej formy. Egzekwuje to test round‑trip (niżej).
- Puste wartości → pusta komórka (nie `"None"`). Daty → format ISO `YYYY-MM-DD`
  (openpyxl może też zapisać typ daty; ISO jest bezpieczny dla re-importu).
- Gdy `row.autor_jednostka is None` (autor trafił, ale zatrudnienie odroczone) —
  kolumny dat/podstawowego zostają puste; wiersz i tak jest eksportowany (autor
  wszedł do BPP).
- Wartości `str(FK)` używają nazw kanonicznych z bazy — dokładnie tych, po
  których importer dopasowuje (poprawiony błędny zapis z oryginału).

#### 4. Formatowanie XLSX
- Jeden arkusz (spójne z regułą „jeden arkusz = jeden import").
- Wiersz nagłówka **pogrubiony**; opcjonalnie `freeze_panes = "A2"`.
- **Bez kolumny „Wynik/status"** — wszystkie eksportowane wiersze są
  zaimportowane, a taka kolumna byłaby ignorowana przy re-imporcie.
- **Bez kolorowania** wierszy — plik ma być czysty i re-importowalny.

---

## UI — strona rezultatów `/rezultaty/`

`ImportPracownikowResultsView` (szablon strony wyników). Na górze strony blok z
przyciskami:
- **„Pobierz oryginał"** — zawsze (link do `pobierz-oryginal`).
- **„Pobierz plik po imporcie"** — tylko gdy `stan == STAN_ZINTEGROWANY`
  (warunek w szablonie + gate serwerowy w widoku). Gdy jeszcze nieaktywny —
  ukryty (lub disabled z tooltipem „dostępne po zakończeniu importu").

Ikony: front publiczny (Foundation CSS) → Foundation-Icons (`<span class="fi-..."/>`).

---

## Testy (TDD)

Nowe pliki: `tests/test_eksport.py`, `tests/test_views_pobieranie.py`.
Konwencja pytest: funkcje, `@pytest.mark.django_db`, `model_bakery.baker`.

### Feature A
- Członek grupy `"wprowadzanie danych"` pobiera → 200 + treść pliku
  (backend simple w testach), `Content-Disposition: attachment`.
- Użytkownik spoza grupy / niezalogowany → odmowa (403/redirect).
- Brak pliku na dysku → 404.

### Feature B — builder (`zbuduj_plik_po_imporcie`)
Odczyt wygenerowanego skoroszytu z powrotem przez `openpyxl.load_workbook`.
- **Wiersze**: pominięte (`autor_id is None`) **nie** trafiają do pliku;
  zaimportowane trafiają; kolejność = oryginalna (`__xls_loc_row__`).
- **Kolumny**: zignorowane kolumny wejścia (target `__pomin__`, np. „dyscyplina")
  **nie** występują; kanoniczne nagłówki obecne; kolejność wg rejestru.
- **BPP ID** wypełnione dla każdego wiersza (także dla autora nowo utworzonego
  w tym imporcie).
- **Wartości SKORYGOWANE (autorytatywne z bazy)**: nazwa jednostki =
  `AJ.jednostka.nazwa` (nawet gdy oryginał miał inną/niepełną/błędną formę);
  tytuł = `A.tytul`, stopień służbowy = `A.stopien_sluzbowy`, stanowisko
  dydakt. = `AJ.stanowisko`, funkcja = `AJ.funkcja`, wymiar = `AJ.wymiar_etatu`.
  **Test wprost**: podaj w pliku wejściowym błędną nazwę jednostki / literówkę w
  nazwisku, a w bazie poprawną — asertuj, że w wygenerowanym pliku jest wartość
  z bazy, NIE z pliku.
- `ORCID`/`PBN UUID`/`Numer` wypełnione gdy autor je ma; kolumna pomijana gdy
  wszędzie pusto i target nieużyty.
- Daty zatrudnienia = z `autor_jednostka` (ISO); puste gdy `autor_jednostka None`.
- `Podstawowe miejsce pracy` = `T`/`N`.

### Feature B — round-trip (gwarancja „gładkiego re-importu") — TEST KLUCZOWY
- Dla **każdego** nagłówka wygenerowanego pliku
  `mapping.pole_dla_naglowka(normalize(nagłówek)) != POLE_POMIN`
  (żaden nie jest ignorowany) **oraz** `waliduj_mapowanie` przechodzi
  (jest identyfikacja osoby + jednostka). To dowodzi, że plik auto-mapuje się
  w całości.
- (Opcjonalnie, cięższy e2e) pełny re-import wygenerowanego pliku na tej samej
  bazie → 0 wierszy „do utworzenia", wszyscy „zmatchowani".

### Feature B — widok
- `stan != STAN_ZINTEGROWANY` → 404/redirect (brak pliku przed finalizacją).
- `stan == STAN_ZINTEGROWANY` → 200, `Content-Disposition` z nazwą
  `<stem>-po-imporcie.xlsx`, poprawny content-type XLSX.
- Gating grupy jak w Feature A.

---

## Higiena / pliki

- Newsfragment: `src/bpp/newsfragments/<slug>.feature.rst` (PL, zwięźle) —
  „Na stronie wyników importu pracowników można pobrać oryginalny plik oraz
  kanoniczny plik »po imporcie« gotowy do ponownego, bezobsługowego wczytania."
- **Bez migracji.**
- `ruff format` / `ruff check` na zmienionych plikach; `djlint` na szablonie;
  wieloliniowe komentarze Django tylko per-linia `{# #}`.

### Lista zmian
| Plik | Zmiana |
|---|---|
| `src/import_pracownikow/urls.py` | +2 ścieżki (`pobierz-oryginal`, `pobierz-po-imporcie`) |
| `src/import_pracownikow/eksport.py` | **NOWY** — `zbuduj_plik_po_imporcie` + rejestr kolumn |
| `src/import_pracownikow/views.py` | +2 widoki (`PobierzOryginalView`, `PobierzPoImporcieView`) |
| szablon rezultatów | +blok 2 przycisków (drugi warunkowy) |
| `tests/test_eksport.py` | **NOWY** — builder + round-trip |
| `tests/test_views_pobieranie.py` | **NOWY** — auth, gate, sendfile |
| `src/bpp/newsfragments/*.feature.rst` | **NOWY** |

## Poza zakresem (YAGNI)
- Pobieranie z innych ekranów (live/audyt) — świadomie tylko `/rezultaty/`.
- Kolumna „ID jednostki" — importer nie dopasowuje jednostki po ID; jednostkę
  identyfikuje pełna `Nazwa jednostki`. Plik pozostaje w 100% re-importowalny.
- Kolumna „Wynik/status" — zbędna (wszystkie eksportowane wiersze zaimportowane).
- Format CSV — tylko XLSX (lustro formatu wejścia).
