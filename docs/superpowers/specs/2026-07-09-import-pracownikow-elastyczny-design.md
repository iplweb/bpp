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
  pasuje po `normalize_cell_header`.
  `DEFAULT_BANNED_NAMES=['pesel', 'pesel_md5', 'peselmd5']` wywalane.
  **Brak obsługi CSV.**
- **Matchowanie:** `import_common.core.matchuj_autora(...)`,
  `matchuj_jednostke(nazwa, wydzial)` (obsługuje już „Nazwa (SKRÓT)" przez
  `wytnij_skrot`, dopasowanie nazwa/skrot iexact, prefix istartswith, zawężenie
  wydziałem). `matchuj_funkcja_autora` / `matchuj_grupa_pracownicza` /
  `matchuj_wymiar_etatu` (`core/tytul_funkcja.py:47-61`) — to **czyste `.get()`**
  rzucające `DoesNotExist`; **tworzenie** obiektu słownikowego siedzi w callerze
  (`ImportPracownikow._matchuj_funkcje_autora`, `_matchuj_grupe_i_wymiar` —
  `models.py:112-151`). Analogicznie `_znajdz_autor_jednostka` (`models.py:195-198`)
  robi `Autor_Jednostka.objects.create(...)` przy braku powiązania. **To są
  miejsca, które dry-run musi ominąć** (patrz §8) — a NIE sygnatury `matchuj_*`.
- Istnieje osobna aplikacja `src/przemapuj_prace_autora/` (przepinanie prac
  autora na inną jednostkę) — do reużycia w feature §8.
- **Confidence-matchowanie** ma już infrastrukturę w `import_common.core.autor`:
  `znajdz_kandydatow_autora(...) -> list[KandydatAutora]` (`autor.py:439`) z progami
  `PEWNOSC_IEXACT=1.0`, `PEWNOSC_IEXACT_PIERWSZE_IMIE=0.95`,
  `PEWNOSC_POLISH_ENGLISH=0.85`, `PEWNOSC_INICJAL=0.5` oraz
  `PEWNOSC_MIN_AUTOMATYCZNA=0.85`. `matchuj_autora` (`autor.py:553`) zwraca
  kandydata tylko gdy `kandydaci[0].pewnosc >= PEWNOSC_MIN_AUTOMATYCZNA`. Dodatkowo
  `importer_publikacji` ma **model** `ImportedAuthor_Candidate` (migr. `0009`, nie
  „pole `candidate`") jako wzorzec UI wyboru kandydata. **Wskaźnik pewności §8 MUSI
  mapować się na te istniejące progi**, nie budować równoległej skali.

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
| DD1 | RODO / retencja | Blob `plik_xls` kasowany po `IMPORT_PRACOWNIKOW_RETENCJA_DNI` (default 90) przez **management command** `usun_stare_pliki_importu_pracownikow` odpalany z crona (nie celery-beat — spójne z resztą housekeepingu BPP); metadane wierszy zostają jako audyt |
| DD2 | Współbieżność | Nie blokujemy twardo (single-tenant), ale **ostrzegamy** gdy istnieje niezatwierdzony import w stanie `przeanalizowany` |
| DD3 | 2 kolumny → 1 pole (np. osobno „stopień" i „tytuł") | **v2** — rzadkie; v1 = 1 kolumna → 1 pole + kompozyty z §6 |

---

## 4. Maszyna stanów i przepływ (sedno dry-run)

Pole `stan` (CharField z choices) na modelu, **obok** stanu operacyjnego liveops
(liveops mówi tylko „task biegnie / padł / skończył"; `stan` mówi „gdzie w
procesie importu jesteśmy"). Zbiór stanów:
`utworzony`, `zmapowany`, `przeanalizowany`, `zatwierdzony`, `zintegrowany`,
`porzucony` (dla starych rekordów z migracji, §11).

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

- **NIE enqueue'ujemy po uploadzie.** `CreateLiveOperationView.form_valid`
  (`liveops/views.py:101-105`) domyślnie robi `form.save(); self.object.enqueue();
  redirect(get_absolute_url())` — to odpaliłoby `run()` natychmiast, w stanie
  `utworzony`, przed ekranem mapowania. Dlatego **własny `form_valid`**: zapis
  obiektu (`stan="utworzony"`) **bez `enqueue`**, redirect na ekran mapowania.
  `enqueue()` wołamy dopiero po zatwierdzeniu mapowania (przejście → `zmapowany`).
- **`run(self, p)` jest dyspozytorem po `stan`**: `zmapowany` → faza analizy
  (task #1); `zatwierdzony` → faza integracji (task #2). Dla **każdego innego
  stanu** (`utworzony`, `przeanalizowany`, `zintegrowany`, `porzucony`) `run()`
  jest **no-op z logiem ostrzegawczym** (`p.log("run() w nieoczekiwanym stanie …")`)
  — chroni przed gołym restartem z centralnej strony liveops.
- **`on_restart()` warunkowy po `stan`** — uwaga, liveops `RestartView.post()` woła
  `on_restart()` **bezwarunkowo jako pierwszy krok**, potem re-enqueue:
  - przejście do commitu: widok „Zatwierdź" ustawia i **zapisuje**
    `stan="zatwierdzony"` PRZED `super().post()` (wzorzec `ZatwierdzImportView`,
    `import_punktacji_zrodel/views.py:107-111`); `on_restart()` widzi `zatwierdzony`
    → **NIE kasuje wierszy** (decyzje usera przeżywają), tylko czyści flagi błędu.
  - restart analizy: user zmienił mapowanie → widok cofa `stan="zmapowany"` przed
    `super().post()`; `on_restart()` widzi `zmapowany` → **kasuje wiersze** i liczy
    od nowa.
  - goły restart z centralnej strony (`przeanalizowany`/`zintegrowany`):
    `on_restart()` nie kasuje, a `run()` trafia w gałąź no-op (wyżej) — bezpieczne.
- **`RestartView` twardo zeruje `result_context`, `log`, `stage_states`,
  `percent`** — po zatwierdzeniu podsumowanie fazy analizy znika ze strony live.
  Akceptujemy to; faza integracji **odtwarza** komplet podsumowania w swoim
  `p.result(...)` (liczby: zmienieni autorzy, odpięci, przepięte prace).
- **Faza integracji robi per-wiersz świeży re-check** (`check_if_integration_needed`)
  w osobnej `transaction.atomic` — baza mogła się zmienić od preview. Wiersz
  nieaktualny → oznacz `pominiety_bo_nieaktualny`, **nie** wywalaj całości.
- Sync (< 100 ms, bez liveops): upload, sniff nagłówka/próbki, edycje per-wiersz,
  re-match pojedynczego wiersza po korekcie.
- Liveops task #1 „analiza": pełny parse + match wszystkich wierszy → pisze
  **wyłącznie** `ImportPracownikowRow` (+ `dane_znormalizowane`, FK do dopasowanych
  obiektów gdy są, `zmiany_potrzebne`, `confidence`, oraz **diff-do-utworzenia**
  w JSON: funkcja/grupa/wymiar/`Autor_Jednostka` których jeszcze NIE ma —
  patrz §8, bo to są create'y odraczane z dry-run). Postęp `p.track(rows)`, logi
  `p.log`, podsumowanie `p.result({...})`.
- Liveops task #2 „commit": iteruje istniejące wiersze → materializuje odroczone
  create'y (słowniki + `Autor_Jednostka`) → `row.integrate()` + odpięcia
  zaznaczonych (§9) + przepięcia zaznaczonych (§10).
- `stages = ["Parsowanie", "Matchowanie", "Integracja"]` (statyczna lista klasowa).
  **Caveat:** task #1 wypełnia etapy 1–2, task #2 etap 3; po `RestartView`
  `stage_states={}`, więc w fazie commit etapy 1–2 pokażą się jako „niewykonane".
  Akceptujemy (etap „Integracja" jest jedynym istotnym w tej fazie); alternatywa
  (per-fazowe listy stages albo prefill `stage_states`) — odłożona, jeśli
  wizualnie przeszkadza.

Wariant odrzucony (commit = pełny re-run z flagą, jak w `import_punktacji_zrodel`):
prostszy i odporny na drift bazy, ale **kasuje edycje usera per-wiersz** —
dyskwalifikacja przy D2/D5/D6. Drift łatamy re-checkiem per-wiersz przy integracji.

---

## 5. Warstwa źródeł — CSV + XLSX (D8)

Protokół `TabularSource` w `import_common/sources.py` (duck-typing / `typing.Protocol`):

```python
class TabularSource(Protocol):
    # nagłówki-kandydaci PER ARKUSZ (XLSX ma N arkuszy; CSV = 1 „arkusz")
    def sheet_headers(self) -> list[list[list[str]]]: ...   # [arkusz][wiersz][komórka]
    def rows(self, mapping) -> Iterator[dict]: ...          # wiersze danych po zmapowaniu
    def count(self) -> int: ...
```

- **Wielo-arkuszowość (istotne!):** `XLSImportFile` wykrywa nagłówek **per arkusz**
  (`sheet_row_cache`), a mapowanie kolumn (§6) jest **jedno na cały import**.
  Kontrakt: nagłówki wszystkich arkuszy muszą się **zgadzać** (ten sam
  znormalizowany zbiór kolumn) — mapowanie stosujemy do wszystkich. Jeśli arkusze
  różnią się nagłówkami → **błąd walidacji przed analizą** z listą rozbieżności
  (v1 nie wspiera per-arkusz różnych mapowań). CSV = zawsze jeden „arkusz".
- **Kontrakt kluczy lokalizacyjnych:** `get_details_set()` sortuje po
  `__xls_loc_sheet__` / `__xls_loc_row__` (RawSQL na `dane_z_xls`). **Każde**
  źródło (także `CSVSource`) MUSI emitować te dwa klucze w każdym wierszu
  (`CSVSource`: `sheet=0`, `row=n`), inaczej sortowanie preview się wywali.
- **`XLSXSource`** — opakowuje obecny `XLSImportFile` (openpyxl, bez zmian logiki
  parsowania).
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
- **Walidacja mapowania** przed przejściem dalej: **jedyne pola obowiązkowe** to
  identyfikacja osoby (`nazwisko`+`imię` LUB `osoba_sklejona`) oraz `jednostka`.
  **Wszystkie pozostałe pola stają się opcjonalne** — w tym te dziś-`required` w
  `AutorForm`: `tytuł_stopień`, `stanowisko`, `grupa_pracownicza`,
  `data_zatrudnienia`, `wymiar_etatu` (to zmiana względem obecnej sztywnej
  walidacji — §13 obiecuje łykanie plików z brakami; §8 przewiduje „brak tytułu"
  jako miękki match). Skutki braku:
  - brak `tytuł` → tylko obniża `confidence` matcha (nie blokuje);
  - brak pola `Autor_Jednostka` (stanowisko/grupa/wymiar/daty) → w fazie integracji
    **nie nadpisujemy** tego pola (ustawiamy tylko to, co w pliku jest) — spójne z
    obecnym `_integrate_autor_jednostka`, które i tak sprawdza `is not None`.
  `DEFAULT_BANNED_NAMES` (`pesel`, `pesel_md5`, `peselmd5`) twardo odrzucane —
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

Dwuwarstwowo, żeby rdzeń był czysty i testowalny tabelarycznie:
- **rdzeń** `parsers/osoba.py` — czysta tokenizacja + reguły składania, **bez
  ORM**; sygnał bazodanowy (krok 2, tiret „match do bazy") przyjmuje jako
  **wstrzykiwaną zależność** (callable `probuj_match(imiona, nazwisko) -> bool`),
  a słowniki tytułów/imion jako argumenty. Testy tabelaryczne odpalają rdzeń z
  atrapami callable/słowników.
- **adapter** w pipeline wstrzykuje realny `matchuj_autora` i leksykony z bazy.

Algorytm rdzenia:

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

Każdy wiersz dostaje **status pewności** zapisany na `ImportPracownikowRow`,
**wyprowadzony z istniejących progów** `znajdz_kandydatow_autora()` (§2), nie z
nowej, równoległej skali:

| Status | Źródło (istniejące API) | UI |
|--------|-------------------------|-----|
| 🟢 `twardy` | jednoznaczny match po ID, LUB dokładnie 1 kandydat z `pewnosc >= PEWNOSC_IEXACT` (1.0) | zielony |
| 🟡 `zgadywanie` | dokładnie 1 kandydat z `PEWNOSC_MIN_AUTOMATYCZNA (0.85) <= pewnosc < 1.0` (np. `PIERWSZE_IMIE` 0.95, `POLISH_ENGLISH` 0.85) | żółty, podświetlony |
| 🔵 `wielu` | ≥2 kandydatów powyżej progu, LUB kandydaci `< PEWNOSC_MIN_AUTOMATYCZNA` (np. `INICJAL` 0.5) | dropdown wyboru |
| ⚪ `brak` | `znajdz_kandydatow_autora` zwraca pustą listę | checkbox „utwórz nowego autora" (D2) |

- Konflikt `bpp_id` z pliku ≠ pk zmatchowanego autora → twardy błąd wiersza
  (jak dziś w `_matchuj_autora_z_walidacja`).
- **Model kandydatów per-wiersz**: dla statusu `wielu` zapisujemy listę kandydatów
  (mały model `ImportPracownikowRowKandydat(row FK, autor FK, pewnosc, powod)` —
  wzorzec `ImportedAuthor_Candidate`) + pole wyboru usera. UI = dropdown.
- **Migracja NULLABLE FK (krytyczne!)**: dziś na `ImportPracownikowRow` pola
  `autor`, `jednostka`, `autor_jednostka`, `funkcja_autora`, `grupa_pracownicza`,
  `wymiar_etatu` są **NOT NULL** (`models.py:340-350`). Statusy `brak`/`wielu` oraz
  odroczone create'y (niżej) wymagają zapisu wiersza **bez** części tych FK →
  potrzebna migracja `null=True` na wszystkich sześciu (nowa migracja, bez ruszania
  istniejących). Przypisane do Fazy 0 (§14).
- **Dry-run musi naprawdę nic nie pisać** — sprostowanie względem błędnego założenia:
  `matchuj_funkcja_autora`/`matchuj_grupa_pracownicza`/`matchuj_wymiar_etatu` to
  czyste `.get()` (§2), **nie** tworzą — więc NIE zmieniamy ich sygnatur. Tworzenie
  siedzi w callerach (`_matchuj_funkcje_autora`, `_matchuj_grupe_i_wymiar`) oraz w
  `_znajdz_autor_jednostka` (`Autor_Jednostka.objects.create`). Faza analizy **nie
  woła tych fallbacków create** — zamiast tego zapisuje „do utworzenia przy
  commicie" w diffie JSON wiersza (`diff_do_utworzenia`: brakująca funkcja/grupa/
  wymiar/`Autor_Jednostka`). Realne `create()` dopiero w fazie integracji (§4,
  task #2), przed `row.integrate()`.

---

## 9. Odpięcia autorów spoza pliku (D3)

`autorzy_spoza_pliku_set()` liczone w **fazie analizy** i pokazywane w preview
jako osobna zakładka z checkboxami **per-autor, domyślnie ODZNACZONYMI**.
Wykonanie (zakończenie zatrudnienia = wczoraj, `podstawowe_miejsce_pracy=False`)
**tylko w fazie commit**, dla zaznaczonych. Zachować istniejącą logikę
wykluczeń (jednostki `zarzadzaj_automatycznie=True`, nie-obce, aktywne).

- **Persystencja decyzji (istotne!)**: `autorzy_spoza_pliku_set()` liczy się
  dynamicznie z bazy, a autorzy spoza pliku NIE są w `ImportPracownikowRow`.
  Zaznaczenia usera muszą przeżyć do fazy commit i drift bazy → materializujemy je
  w fazie analizy jako wiersze `ImportPracownikowOdpiecie(parent FK,
  autor_jednostka FK, zaznaczone BooleanField=False, wykonane BooleanField=False)`.
  Preview edytuje `zaznaczone`; commit iteruje `zaznaczone=True`, robi świeży
  re-check (powiązanie mogło już zostać zakończone ręcznie) i ustawia `wykonane`.

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
- **Cofanie** (D6) — z jawnymi ograniczeniami. Realny model
  `PrzemapoaniePracAutora` ma `jednostka_z`, `jednostka_do` (top-level) oraz DWA
  pola JSON: `prace_ciagle_historia`, `prace_zwarte_historia` — **listy ID+tytuł
  publikacji, BEZ pk wierszy `Wydawnictwo_*_Autor`**. Undo po samym ID publikacji
  jest niejednoznaczne (autor może występować w pracy wielokrotnie; praca mogła
  później zmienić afiliację). Dlatego:
  - **Rozszerzamy wpisy historii** (dla przemapowań robionych przez import) o
    `{rekord_id, autor_rekord_pk, jednostka_z_pk, tytul, rok}` (dodatek do JSON,
    bez migracji schematu) + nowe nullable FK `import` (powiązanie z importem).
  - **Algorytm undo**: dla każdego wpisu przywróć `autor_rekord_pk` →
    `jednostka_z_pk` **tylko gdy** jego bieżąca `jednostka == jednostka_do`
    (guard przed nadpisaniem późniejszych zmian); niepasujące → **pomiń i
    zaraportuj** (nie cofaj na ślepo). Undo w `transaction.atomic`.
  - **Przycisk „cofnij"** w UI wykonuje powyższe i pokazuje raport
    (cofnięto N, pominięto M z powodu późniejszych zmian).
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
                       #   ImportPracownikowRowKandydat, ImportPracownikowOdpiecie,
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
w `import_common.core` **bez zmian sygnatur** (`matchuj_*` to czyste `.get()`,
§2/§8 — dry-run po prostu nie woła fallbacków `create()` w pipeline).

Nowe migracje `import_pracownikow` (bez ruszania istniejących): (a) pola liveops
+ `stan` + usunięcie `performed/integrated` (Faza 0); (b) `null=True` na sześciu
FK `ImportPracownikowRow` (Faza 0); (c) modele `ImportPracownikowOdpiecie`,
`ImportPracownikowRowKandydat`, `ProfilMapowania` + pola `mapowanie_kolumn`,
`diff_do_utworzenia`, `confidence`, `przepnij_prace`, `korekta_uzytkownika` (fazy
2–5, dokładany schemat). Po każdej zmianie schematu: `make baseline-update`.

---

## 13. Dane wejściowe / chaos do obsłużenia (§D10)

W chwili pisania **mail zgłoszeniowy od `michal.dtz@gmail.com` NIE dotarł** do
Freshdeska (brak kontaktu, brak ticketu). Tickety wskazanych osób (Anna Wołodko
[IHIT] #417/#420, Jan Bihalowicz #428/#422) dotyczą innych tematów (IF, CrossRef)
i **nie zawierają** Exceli personalnych. Firm „VIZJA"/„UAFM" nie ma w Freshdesku
pod tymi nazwami. Właściciel wskazał dodatkowo pliki na Freshdesku: Kowalczewski
„Wydziały i ludzie z nich" oraz „przyporządkowanie do wydziałów - uniwersytet
vizja" — ale **Freshdesk MCP nie ma full-text search po temacie/treści ani
listowania załączników**, a te tematy nie występują wśród ~70 zwracanych ticketów
(367–434); prawdopodobnie zamknięte/zarchiwizowane. **Do pobrania ręcznego przy
implementacji** (numery ticketów albo przesłanie plików).

**Skutek dla planu:** realne pliki wzbogacają **słownik synonimów** (§6) i
**fixtures testowe** (§7, §5) — NIE zmieniają architektury. Implementacja startuje
na podstawie znanych wariantów (niżej); po dostarczeniu plików: dopisać synonimy
+ fixtures i ponowić testy tabelaryczne parsera. **Znane źródła danych do zebrania:**
Wołodko (kliniki), Bihałowicz (pracownicy), Kowalczewski (wydziały+ludzie),
uniwersytet Vizja (przyporządkowanie do wydziałów), UAFM, wzorzec BPP (mamy).

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

- **Faza 0** — migracja `long_running → django-liveops` + rozdzielenie dry-run /
  commit. *Fundament.* Faza 0 używa **zredukowanej maszyny stanów** (BEZ
  `zmapowany`, który wymaga ekranu mapowania z Fazy 2):
  `utworzony → przeanalizowany → zatwierdzony → zintegrowany`. Analiza używa
  dotychczasowego sztywnego `AutorForm`/`JednostkaForm` (jeszcze bez mapowania).
  **W tej fazie odraczamy create'y** (słowniki funkcja/grupa/wymiar +
  `Autor_Jednostka`) do fazy commit — to warunek prawdziwego dry-run (§8) — oraz
  robimy migrację `null=True` na sześciu FK `ImportPracownikowRow` (§8). Custom
  `form_valid` bez natychmiastowego `enqueue` (§4). To domyka „dry-run + zapis
  później" niezależnie od reszty faz.
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
