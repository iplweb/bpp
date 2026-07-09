# Elastyczny import pracowników — design

**Data:** 2026-07-09
**Autor:** Michał Pasternak + Claude (brainstorming) + subagent Fable (review)
**Status:** wstępnie zaakceptowany, po 3 iteracjach self-review
**Zgłoszenie źródłowe:** mail od `michal.dtz@gmail.com` (w chwili pisania NIE dotarł
jeszcze do Freshdeska — patrz §13 „Dane wejściowe / chaos").

---

## 1. Cel i motywacja

Funkcja „import pracowników" (`src/import_pracownikow/`) przypisuje pracowników
do jednostek na podstawie pliku XLSX. Dziś zakłada plik ściśle zgodny z wzorcem
BPP. Realność: uczelnie wrzucają **różnorodne, niezgodne z wzorcem pliki** —
brakuje kolumn, kolumny są różnie nazwane, dane w komórkach mają różny format
(tytuł/imię/nazwisko rozbite albo sklejone w różnej kolejności), jednostki podane
raz nazwą, raz skrótem, raz „nazwa (SKRÓT)".

Cel: przerobić import tak, by:

1. **łykał różnorodne, „brudne" pliki** XLSX **oraz CSV** (odporność na brak /
   różne nazwy kolumn, różne formaty komórek, różny zapis jednostek);
2. był domyślnie **dry-run** (nie zapisuje do bazy) z osobnym, świadomym
   **zapisem później**;
3. pozwalał opcjonalnie **przepiąć prace naukowe** autora na jednostkę z pliku;
4. pokazywał **pewność dopasowania** każdego wiersza (twardy match / zgadywanie /
   wielu kandydatów / brak);
5. siedział na **`django-liveops`** zamiast wewnętrznego `long_running`.

Wzorzec referencyjny w repo: **`src/import_punktacji_zrodel/`** — już na
`django-liveops`, już ma dry-run (flaga zapisu) + osobny commit przez
`RestartView`. Ten design świadomie go naśladuje i rozszerza tam, gdzie import
pracowników jest bardziej złożony (interaktywne mapowanie, decyzje per-wiersz).

**Kluczowa różnica względem `import_punktacji_zrodel`:** tam commit = „re-run z
flagą", bo user nic nie edytuje per-wiersz. Tu user **będzie** edytował wiersze
w preview (korekta rozbicia nazwiska, opt-in „utwórz nowego", opt-in „przepnij
prace", zaznaczenie odpięć), więc commit **nie może** kasować wierszy i liczyć
wszystkiego od nowa — decyzje usera muszą przeżyć. To wywraca `on_restart()`
(patrz §4).

---

## 2. Stan obecny (co dziedziczymy)

- **Model** `ImportPracownikow(ASGINotificationMixin, Operation)` z `long_running`:
  pola `plik_xls` (FileField), `performed`, `integrated` (booleany).
  `perform()` iteruje wiersze z `XLSImportFile`, dla każdego `_przetworz_wiersz`
  (matchuje jednostkę → waliduje autora `AutorForm` → matchuje funkcję/grupę/
  wymiar → matchuje autora → znajduje/tworzy `Autor_Jednostka` → tworzy
  `ImportPracownikowRow`). **Na końcu `perform()` AUTOMATYCZNIE woła `integrate()`**
  — czyli dziś NIE ma prawdziwego dry-run: match i zapis są sklejone.
- `integrate()`: dla wierszy `zmiany_potrzebne=True` woła `row.integrate()`
  (zapis do `Autor` i `Autor_Jednostka`, log do `log_zmian` JSONField).
- `autorzy_spoza_pliku_set()` / `odepnij_autorow_spoza_pliku()`: znajduje
  powiązania autor+jednostka których NIE ma w pliku (jednostki zarządzane
  automatycznie, nie-obce) i kończy im zatrudnienie (data końca = wczoraj,
  `podstawowe_miejsce_pracy=False`).
- **Walidacja kolumn jest sztywna** (`AutorForm`, `JednostkaForm` z twardymi
  polskimi kluczami). Słownik wiersza MUSI mieć dokładnie te klucze.
- **Parsowanie:** `import_common.util.XLSImportFile` — TYLKO openpyxl (XLSX). Ma
  już fuzzy-detekcję nagłówka: `find_similar_row(sheet, try_names, min_points)`
  skanuje wiersze i bierze pierwszy, w którym ≥`min_points` nazw z `try_names`
  pasuje po `normalize_cell_header`. `DEFAULT_BANNED_NAMES=['pesel',...]` wywalane.
  **Brak obsługi CSV.**
- **Matchowanie:** `import_common.core.matchuj_autora(...)`,
  `matchuj_jednostke(nazwa, wydzial)` (obsługuje już „Nazwa (SKRÓT)" przez
  `wytnij_skrot`, dopasowanie nazwa/skrot iexact, prefix istartswith, zawężenie
  wydziałem). `matchuj_funkcja_autora` / `matchuj_grupa_pracownicza` /
  `matchuj_wymiar_etatu` — **tworzą** obiekt słownikowy gdy brak (istotne dla
  dry-run, patrz §7).
- Istnieje osobna aplikacja `src/przemapuj_prace_autora/` (przepinanie prac
  autora na inną jednostkę) — do reużycia w feature §8.
- **Confidence-matchowanie** ma już wzorzec w `importer_publikacji`
  (pole `candidate`, migracja `0009_importedauthor_candidate`) — reużyć pattern.

---

## 3. Decyzje produktowe (zatwierdzone przez właściciela)

| # | Kwestia | Decyzja |
|---|---------|---------|
| D1 | Mapowanie kolumn | **Hybryda**: auto-detekcja + ekran korekty + zapisywalne profile |
| D2 | Nowi autorzy (brak dopasowania) | **Twórz, ale z potwierdzeniem w preview** (checkbox per-wiersz) |
| D3 | Odpięcia autorów spoza pliku | **Domyślnie ODZNACZONE, per-autor** (nie masowo) |
| D4 | Minimalna identyfikacja | Match po **nazwisko + jednostka + tytuł**; jeśli jest ID (numer kadrowy / ORCID / PBN / bpp_id) — matchuj też po ID. ID **nieobowiązkowe** |
| D5 | Wskaźnik pewności matcha | **Tak** — twardy match / zgadywanie / wielu kandydatów / brak (jak w `importer_publikacji`) |
| D6 | Przepięcie prac na jednostkę | **Tak, z cofaniem w UI** (log + przycisk „cofnij") |
| D7 | Zakres przepięcia prac | **Wszystkie prace autora afiliowane do starej jednostki** (niezależnie od roku) |
| D8 | Formaty plików | **XLSX + CSV** |
| D9 | Framework operacji | **`django-liveops`** (migracja z `long_running`) |
| D10 | Pliki-próbki | Użytkownik dostarczy realne pliki → fixtures + słownik synonimów |

Domyślne (moja propozycja, do potwierdzenia w razie sprzeciwu):

| # | Kwestia | Domyślne |
|---|---------|----------|
| DD1 | RODO / retencja | Blob `plik_xls` kasowany po 90 dniach (housekeeping); metadane wierszy zostają jako audyt. Konfigurowalne |
| DD2 | Współbieżność | Nie blokujemy twardo (single-tenant), ale **ostrzegamy** gdy istnieje niezatwierdzony import w stanie `przeanalizowany` |
| DD3 | 2 kolumny → 1 pole (np. osobno „stopień" i „tytuł") | **v2** — rzadkie; v1 = 1 kolumna → 1 pole + kompozyty z §6 |

---

## 4. Maszyna stanów i przepływ (sedno dry-run)

Pole `stan` (CharField z choices) na modelu, **obok** stanu operacyjnego liveops
(liveops mówi tylko „task biegnie / padł / skończył"; `stan` mówi „gdzie w
procesie importu jesteśmy").

```
utworzony
   │  (sync: sniff nagłówka + próbki ~10 wierszy → ekran mapowania)
   ▼
zmapowany
   │  (liveops task #1: PARSE + MATCH — ZERO zapisów do Autor/Autor_Jednostka)
   ▼
przeanalizowany  ⇄  user edytuje wiersze:
   │                  • korekta rozbicia nazwiska (inline, HTMX → re-match wiersza)
   │                  • wybór kandydata (gdy wielu)
   │                  • opt-in „utwórz nowego autora" (D2)
   │                  • opt-in „przepnij prace" (D6)
   │                  • zaznaczenie odpięć (D3)
   │  (jawny POST „Zapisz do bazy")
   ▼
zatwierdzony
   │  (liveops task #2: INTEGRACJA istniejących wierszy z decyzjami usera)
   ▼
zintegrowany
   └──(dowolny task) ──▶ błąd (traceback liveops)
```

Reguły krytyczne:

- **`run(self, p)` jest dyspozytorem po `stan`**: `zmapowany` → faza analizy;
  `zatwierdzony` → faza integracji.
- **`on_restart()` kasuje wiersze TYLKO przy cofnięciu do analizy** (`stan`
  wraca do `zmapowany`, np. user zmienił mapowanie i re-analizuje). Przy przejściu
  `przeanalizowany → zatwierdzony` wiersze (z decyzjami usera) **przeżywają**.
- **Faza integracji robi per-wiersz świeży re-check** (`check_if_integration_needed`)
  w osobnej `transaction.atomic` — baza mogła się zmienić od preview. Wiersz
  nieaktualny → oznacz `pominiety_bo_nieaktualny`, **nie** wywalaj całości.
- Sync (< 100 ms, bez liveops): upload, sniff nagłówka/próbki, edycje per-wiersz,
  re-match pojedynczego wiersza po korekcie.
- Liveops task #1 „analiza": pełny parse + match wszystkich wierszy → pisze
  **wyłącznie** `ImportPracownikowRow` (+ `dane_znormalizowane`, FK do dopasowanych
  obiektów, `zmiany_potrzebne`, proponowany diff w JSON, `confidence`). Postęp
  `p.track(rows)`, logi `p.log`, podsumowanie `p.result({...})`.
- Liveops task #2 „commit": iteruje istniejące wiersze → `row.integrate()` +
  odpięcia zaznaczonych (§9) + przepięcia zaznaczonych (§8).
- `stages = ["Parsowanie", "Matchowanie", "Integracja"]` → pasek postępu z liveops
  za darmo.

Wariant odrzucony (commit = pełny re-run z flagą, jak w `import_punktacji_zrodel`):
prostszy i odporny na drift bazy, ale **kasuje edycje usera per-wiersz** —
dyskwalifikacja przy D2/D5/D6. Drift łatamy re-checkiem per-wiersz przy integracji.

---

## 5. Warstwa źródeł — CSV + XLSX (D8)

Protokół `TabularSource` w `import_common/sources.py` (duck-typing / `typing.Protocol`):

```python
class TabularSource(Protocol):
    def headers_candidates(self) -> list[list[str]]: ...   # pierwsze N surowych wierszy (detekcja nagłówka)
    def rows(self, mapping) -> Iterator[dict]: ...          # wiersze danych po zmapowaniu
    def count(self) -> int: ...
```

- **`XLSXSource`** — opakowuje obecny `XLSImportFile` (openpyxl, bez zmian logiki
  parsowania). Wielo-arkuszowość zostaje.
- **`CSVSource`** — nowy:
  - **Detekcja formatu** po magic-bytes (XLSX = ZIP, zaczyna się `PK`), NIE po
    rozszerzeniu (ludzie nazywają `.xls` plik CSV i odwrotnie).
  - **Encoding**: próbuj kolejno `utf-8-sig` → `cp1250` → `iso-8859-2` (polski
    Excel na Windows zapisuje cp1250); kryterium: dekodowanie bez błędów + brak
    znaków zastępczych. Bez nowej zależności.
  - **Delimiter**: `csv.Sniffer` na pierwszych ~4 KB z fallbackiem „policz `;` vs
    `,` vs `\t` w pierwszych 5 liniach" (Sniffer bywa kruchy na jednokolumnowych).
    Polski Excel domyślnie zapisuje `;`.
- **Fuzzy-header format-agnostyczny**: wynieść rdzeń `find_similar_row` do
  `find_similar_row_in_rows(rows: list[list], try_names, min_points)` przyjmującej
  gołe listy; obie implementacje źródła podają swoje pierwsze N wierszy.
  `normalize_cell_header` bez zmian.
- **Normalizacja wartości** (`parsers/wartosci.py`) siedzi **nad** źródłem: CSV
  daje stringi tam, gdzie XLSX daje typy. Parsowanie dat (`YYYY-MM-DD`,
  `DD.MM.YYYY`), wymiaru etatu (`1`, `1,0`, `0.5`, `pełny etat`), booleanów
  (`TAK`/`NIE`/`tak`/`x`/`1`).

---

## 6. Mapowanie kolumn — hybryda + profile (D1)

Po uploadzie widok **synchronicznie** czyta nagłówek + ~10 wierszy próbki
(milisekundy, bez taska w tle) i proponuje mapowanie: dla każdej kolumny arkusza
→ pole systemowe (dropdown) albo „ignoruj".

- **Auto-propozycja**: `find_similar_row_in_rows` + **rozszerzony słownik
  synonimów** (stała w kodzie, wersjonowana z kodem — nie w DB): „nazwisko i imię",
  „imię i nazwisko", „stopień/tytuł", „etat", „jedn. org.", „komórka organizacyjna",
  „zakład", „klinika", „katedra" itd. (uzupełniany z realnych plików — §13).
- **Pola docelowe** obejmują nie tylko obecne twarde klucze, ale też **kompozyty**:
  - `osoba_sklejona` — 1 komórka „tytuł+imię+nazwisko" → uruchamia parser z §7;
  - `jednostka_nazwa_i_skrot` — „Nazwa (SKRÓT)" → już obsłużone przez `wytnij_skrot`.
- **Walidacja mapowania** przed przejściem dalej: pola obowiązkowe (identyfikacja
  osoby: `nazwisko`+`imię` LUB `osoba_sklejona`; oraz `jednostka`; oraz `tytuł`)
  muszą być zmapowane. `DEFAULT_BANNED_NAMES` (`pesel`) twardo odrzucane —
  kolumna nieoferowana.
- **Przechowywanie**:
  - **Per-import (snapshot)**: `mapowanie_kolumn` JSONField na modelu importu —
    niemutowalny zapis „czego użyto", audytowalny, odtwarzalny przy restarcie.
  - **Profile do reużycia**: model `ProfilMapowania(nazwa, mapowanie JSONField,
    ostatnio_uzyty, utworzony_przez)`. BPP jest single-tenant per instalacja →
    profile globalne dla instancji. Auto-propozycja: jeśli zbiór znormalizowanych
    nagłówków pliku pokrywa się ≥90% z profilem, prefill z profilu zamiast fuzzy.
    Checkbox „zapisz jako profil" na ekranie korekty. Realnie załatwia „ta sama
    uczelnia wrzuca co kwartał ten sam bałagan".

---

## 7. Parser sklejonej komórki „tytuł/imię/nazwisko" (D4)

Czysta funkcja `parsers/osoba.py` (testy tabelaryczne, bez ORM poza leksykonem).

Algorytm:

1. **Zdejmij tytuły**: tokenizuj, longest-match do słownika tytułów. Źródło
   słownika: model `bpp.Tytul` (skróty + nazwy, już używany przez
   `matchuj_autora(tytul_str=...)`) plus statyczna lista wariantów zapisu
   („dr hab. n. med.", „prof. ucz.", „mgr inż.", z kropkami / bez, różna
   wielkość liter). Tytuły mogą stać z przodu i z tyłu — zdejmuj z obu stron.
2. **Sygnały kolejności** (hierarchia pewności):
   - **przecinek**: „Kowalska-Nowak, Anna Maria" → nazwisko przed przecinkiem
     (pewne);
   - **WERSALIKI** wśród mixed-case: „KOWALSKI Jan" → nazwisko (pewne);
   - **match do bazy obu hipotez** (imię-pierwsze / nazwisko-pierwsze) przez
     `matchuj_autora`; jeśli dokładnie jedna daje jednoznaczny match — wygrała
     (najsilniejszy praktyczny sygnał: importujemy ludzi, którzy w większości JUŻ
     są w bazie);
   - **leksykon imion**: zbiór znanych imion z istniejącej tabeli `Autor`
     (`values_list` imion, splitowane) + mała statyczna lista popularnych imion;
   - token z dywizem → prawdopodobnie nazwisko dwuczłonowe.
3. **Składanie**: wiele imion = wszystkie tokeny-imiona po stronie „imię";
   fallback bez sygnału: ostatni token = nazwisko, `confidence=low`.
4. **Wynik**: `{tytul, imiona, nazwisko, confidence: high|medium|low, alternatywy: [...]}`
   → zapis w `dane_znormalizowane` wiersza.

**Niepewność nie jest chowana**: w preview kolumny „imiona/nazwisko/tytuł" zawsze
pokazane jako wynik rozbicia; wiersze `confidence != high` podświetlone i
sortowane na górę; edycja inline (HTMX POST na wiersz) zapisuje korektę w polu
`korekta_uzytkownika` (JSONField) i **od razu** ponawia matchowanie tego wiersza
synchronicznie. Bez ML/LLM — deterministyczna heurystyka + człowiek w pętli jest
tańsza, testowalna i wystarczająca przy plikach rzędu setek wierszy.

---

## 8. Matchowanie autora + wskaźnik pewności (D4, D5)

Match po **nazwisko + jednostka + tytuł**; jeśli plik ma ID (numer kadrowy /
ORCID / PBN / bpp_id) — dodatkowo po ID. ID **nieobowiązkowe**.

Każdy wiersz dostaje **status pewności** (reużycie patternu `candidate` z
`importer_publikacji`), zapisany na `ImportPracownikowRow`:

| Status | Znaczenie | UI |
|--------|-----------|-----|
| 🟢 `twardy` | ID jednoznaczne LUB jednoznaczne nazwisko+jednostka+tytuł | zielony |
| 🟡 `zgadywanie` | dopasowanie miękkie (np. sam prefix nazwiska, brak tytułu) | żółty, podświetlony |
| 🔵 `wielu` | kilku kandydatów | dropdown wyboru |
| ⚪ `brak` | brak w bazie | checkbox „utwórz nowego autora" (D2) |

- Konflikt `bpp_id` z pliku ≠ pk zmatchowanego autora → twardy błąd wiersza
  (jak dziś w `_matchuj_autora_z_walidacja`).
- **Dry-run musi naprawdę nic nie pisać**: `matchuj_funkcja_autora` /
  `matchuj_grupa_pracownicza` / `matchuj_wymiar_etatu` dziś **tworzą** obiekty
  słownikowe gdy brak. W fazie analizy dostają `create=False` i zapisują „do
  utworzenia przy commicie" w diffie wiersza (JSON). Tworzenie realne dopiero w
  fazie integracji.

---

## 9. Odpięcia autorów spoza pliku (D3)

`autorzy_spoza_pliku_set()` liczone w **fazie analizy** i pokazywane w preview
jako osobna zakładka z checkboxami **per-autor, domyślnie ODZNACZONYMI**.
Wykonanie (zakończenie zatrudnienia = wczoraj, `podstawowe_miejsce_pracy=False`)
**tylko w fazie commit**, dla zaznaczonych. Zachować istniejącą logikę
wykluczeń (jednostki `zarzadzaj_automatycznie=True`, nie-obce, aktywne).

---

## 10. Przepięcie prac na jednostkę (D6, D7)

- **Ekstrakcja logiki** z `przemapuj_prace_autora/views.py`
  (`_wykonaj_przemapowanie`, ok. linii 124) → `przemapuj_prace_autora/service.py`:
  `przemapuj(autor, jednostka_z, jednostka_do, user) -> PrzemapoaniePracAutora`
  (bez `request`, bez `messages`). Widok i import wołają to samo.
- **Zakres** (D7): tylko prace afiliowane do **starej** jednostki
  (`filter(autor=..., jednostka=jednostka_z).update(jednostka=jednostka_do)`) —
  wszystkie, niezależnie od roku. „Wszystkie prace autora" byłoby pułapką (drugi
  etat, historia).
- **UI**: w preview kolumna „przepnij prace: ☐ z ⟨stara⟩ do ⟨nowa⟩ (N prac)"
  tylko gdy jednostka z pliku ≠ dotychczasowa. Opt-in per-wiersz
  (`przepnij_prace` BooleanField na `ImportPracownikowRow`) + akcja zbiorcza
  „zaznacz wszystkie z różnicą jednostki". `N` liczone lazy (HTMX per wiersz albo
  jedno zapytanie agregujące przy budowie preview — do zmierzenia; przy setkach
  wierszy agregat OK).
- **Wykonanie** w fazie commit, po `row.integrate()`, w transakcji wiersza; wynik
  (pk przemapowania, liczby) do `log_zmian`.
- **Cofanie** (D6): model `PrzemapoaniePracAutora` (już ma JSON-ową listę
  przemapowanych prac) + nowe nullable FK `import_row` (powiązanie z importem) +
  **przycisk „cofnij"** przywracający starą jednostkę z logu.
- Autor z wieloma starymi jednostkami: v1 przepina tylko z jednostki, którą import
  faktycznie zmienia w tym wierszu; reszta = link do ręcznego widoku
  `przemapuj_prace_autora`.

---

## 11. Migracja `long_running` → `django-liveops` (D9)

**In-place** (schema migration tego samego modelu), bez migracji „żywych" operacji.

- `ImportPracownikow(LiveOperation)`. Pola bazowe niemal identyczne (UUID pk,
  `owner`, `created_on`, `started_on`, `finished_on`, `finished_successfully`,
  `traceback`). Migracja: usuń `last_updated_on`, dodaj pola liveops
  (`cancel_requested`, `cancelled`, `result_context`, `language`, `status_text`,
  `percent`, `log`, `log_seq`, `current_stage`, `stage_states`) z defaultami.
- Usunięte `performed`/`integrated` booleany → zastępuje `stan` (§4). Data
  migration: stare rekordy `performed AND integrated` → `stan="zintegrowany"`,
  reszta → `porzucony`. `log_zmian` wierszy nietykalny (audyt).
- **Nie** przenosić operacji „w trakcie" — okno deploya; nota w release notes.
- Mapowanie API:
  - `perform()` + `integrate()` → `run(self, p)` z dyspozytorem po `stan`.
  - `send_progress()` / `ASGINotificationMixin` → `p.track(iterable)` + `p.log(line)`;
    podsumowanie → `p.result(ctx)` renderowane fragmentem HTML.
  - `on_reset()` → `on_restart()` (warunek po `stan`, §4).
  - Widoki: `CreateLongRunningOperationView` → `CreateLiveOperationView`;
    `Details/Router` → znikają (centralny `liveops:live` przez
    `get_absolute_url`); `LongRunningResultsView` → własny `ListView` z
    owner-scopingiem (kopia `ResultsView` z `import_punktacji_zrodel`);
    `Restart` → liveops `RestartView`. Bramka:
    `braces.GroupRequiredMixin("wprowadzanie danych")` jak dotąd.
  - Testy: `liveops.testing.MockProgress` (wzorce w
    `src/import_punktacji_zrodel/tests/`).

---

## 12. Struktura plików (małe, testowalne moduły)

```
src/import_pracownikow/
  models.py            # ImportPracownikow(LiveOperation), ImportPracownikowRow,
                       #   ProfilMapowania — TYLKO pola, stan, cienkie metody
  forms.py             # upload, formularz mapowania (dynamiczny), zatwierdzenie
  views.py             # Create / Mapowanie / Preview(ListView) / edycja wiersza
                       #   (HTMX) / Zatwierdz(RestartView) / Lista
  urls.py
  mapping.py           # auto-propozycja mapowania, walidacja, dopasowanie profili
  parsers/
    osoba.py           # rozbicie sklejonej komórki (czysta funkcja)
    wartosci.py        # normalizacja dat / etatu / boolean (CSV + XLSX)
  pipeline/
    analyze.py         # faza 1: źródło → normalize → match → Row  (dostaje p)
    integrate.py       # faza 2: Row.integrate + odpięcia + przepięcia (dostaje p)
  tests/               # per moduł: test_parsers_osoba (tabelaryczne!),
                       #   test_mapping, test_sources_csv, test_pipeline_analyze,
                       #   test_pipeline_integrate, test_views, test_migracja_liveops
src/import_common/
  sources.py           # TabularSource, XLSXSource, CSVSource, detekcja formatu/encodingu
  util.py              # find_similar_row_in_rows (refaktor istniejącego)
src/przemapuj_prace_autora/
  service.py           # przemapuj(...) wyekstrahowane z views._wykonaj_przemapowanie
```

Zasada cięcia: `models.py` przestaje być 500-liniowym silnikiem — logika
przetwarzania w `pipeline/` jako funkcje `(import_obj, p)`; matchowanie zostaje
w `import_common.core` (bez zmian sygnatur poza `create=False` dla słowników).

---

## 13. Dane wejściowe / chaos do obsłużenia (§D10)

W chwili pisania **mail zgłoszeniowy od `michal.dtz@gmail.com` NIE dotarł** do
Freshdeska (brak kontaktu, brak ticketu). Tickety wskazanych osób (Anna Wołodko
[IHIT] #417/#420, Jan Bihalowicz #428/#422) dotyczą innych tematów (IF, CrossRef)
i **nie zawierają** Exceli personalnych. Firm „VIZJA"/„UAFM" nie ma w Freshdesku
pod tymi nazwami.

**Skutek dla planu:** realne pliki wzbogacają **słownik synonimów** (§6) i
**fixtures testowe** (§7, §5) — NIE zmieniają architektury. Implementacja startuje
na podstawie znanych wariantów (niżej); po dostarczeniu plików: dopisać synonimy
+ fixtures i ponowić testy tabelaryczne parsera.

### Katalog znanych wariantów „chaosu" (do rozszerzenia z realnych plików)

Wzorzec BPP (`src/import_pracownikow/tests/testdata.xlsx`):

- **Preambuła przed nagłówkiem**: wiersze 0–5 to objaśnienia
  („Numer.- to numer ID z systemu…", „BPP ID - to numer…"), nagłówek dopiero w
  wierszu 6, dane od 7. → fuzzy `find_similar_row` MUSI skanować, nie zakładać
  wiersza 1. (już działa)
- **Nazwa kolumny z wtrąconym `\n`**: „Podstawowe miejsce pracy \nTAK/NIE". →
  `normalize_cell_header` bierze `str(...).split("\n")[0]` (już działa).
- Kolumny wzorca: `Numer, Nazwisko, Imię, ORCID, Tytuł/Stopień, Stanowisko,
  Grupa pracownicza, Nazwa jednostki, Wydział, Data zatrudnienia, Data końca
  zatrudnienia, Podstawowe miejsce pracy, PBN UUID, BPP ID, Wymiar etatu`.

Warianty do pokrycia (z opisu właściciela + domeny):

- **Brakujące kolumny** (np. brak ORCID / PBN / dat) → mapowanie „ignoruj",
  matchowanie po tym, co jest.
- **Różne nazwy kolumn** → słownik synonimów + ekran korekty.
- **Sklejone „tytuł/imię/nazwisko"** w jednej komórce, kolejność zmienna (raz
  nazwisko pierwsze, raz imię, raz tytuł pierwszy) → parser §7.
- **Jednostki**: sama nazwa; sam skrót; „nazwa (SKRÓT)"; „klinika" / „katedra" /
  „zakład" jako różne poziomy → `matchuj_jednostke` + `wytnij_skrot`.
- **CSV** z polskim Excela: separator `;`, encoding cp1250.

---

## 14. Fazowanie implementacji

Duży zakres → plan w fazach, każda dowozalna i testowalna osobno:

- **Faza 0** — migracja `long_running → django-liveops` przy zachowaniu obecnego
  zachowania + rozdzielenie dry-run / commit (maszyna stanów §4). *Fundament.*
- **Faza 1** — warstwa źródeł CSV + XLSX (`TabularSource`) + refaktor fuzzy-header
  (§5).
- **Faza 2** — hybrydowe mapowanie kolumn + profile (§6).
- **Faza 3** — parser sklejonej osoby + wskaźnik pewności + edycja inline (§7, §8).
- **Faza 4** — „utwórz nowego autora" (D2) + odpięcia per-autor (§9).
- **Faza 5** — przepięcie prac + cofanie (§10).

Każda faza: TDD (test czerwony → implementacja → zielony), własne testy, brak
modyfikacji istniejących migracji, `ruff` czysto, po zmianie schematu
`make baseline-update`.

---

## 15. Ryzyka i pytania otwarte

1. **Match po samym nazwisku** (D4, ID opcjonalne): ryzyko dubli przy popularnych
   nazwiskach. Mitygacja: jednostka + tytuł jako dezambiguatory, status
   `zgadywanie`/`wielu` wymusza decyzję usera.
2. **Drift bazy między preview a commit**: mitygacja re-checkiem per-wiersz (§4).
3. **Wydajność liczenia „N prac do przepięcia"** przy dużych plikach — zmierzyć,
   ewentualnie agregat zamiast per-wiersz (§10).
4. **Realne pliki**: dopóki nie dotrą (§13), słownik synonimów i fixtures są
   oparte na wzorcu BPP + domenie — możliwe luki w nietypowych nagłówkach.
5. **DD1/DD2/DD3** — domyślne do potwierdzenia w razie sprzeciwu.
