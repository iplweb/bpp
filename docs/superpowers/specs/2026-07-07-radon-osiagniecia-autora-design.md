# Osiągnięcia autora z RAD-on OpenData (client-side, po ORCID)

**Data:** 2026-07-07
**Gałąź:** `feat/radon-profil-autora` (na bazie `feature/profil-autora`, PR #385)
**Status:** spec zaakceptowany do implementacji

## Cel

Na podstronie autora (`/autor/<pk|slug>/`) dla naukowców posiadających ORCID
dodać sekcję z ich osiągnięciami naukowymi pobranymi **na żywo z RAD-on
OpenData** — **po stronie klienta** (fetch z przeglądarki), z podpisem drobnymi
literami „informacje pobrane z RAD-on".

Kod odpytujący RAD-on ma być **wydzielonym, przenośnym modułem JS** (bez
zależności od BPP), tak by dało się go wyjąć i użyć gdzie indziej.

## Ustalenia badawcze (przetestowane na żywo 2026-07-07)

Reverse-engineering + testy żywego API. Fakty, na których stoi ten projekt:

### Usługa `scientist` (dane zintegrowane) — TO JEST nasze źródło

- **Endpoint:** `POST https://radon.nauka.gov.pl/opendata/scientist/search`
- **Ciało żądania** (schemat `ScientistQueryParameters`):
  ```json
  {"resultNumbers": 10, "token": null, "body": {"firstName": "...", "lastName": "..."}}
  ```
  - `token` MUSI być `null` lub pominięty przy pierwszym żądaniu
    (`""` zwraca `400 Malformed token`).
  - `resultNumbers` ≤ 100; paginacja kursorem `pagination.token`.
  - `body` = `ScientistSearchCriteria`: `firstName`, `lastName`, `uid`,
    `employmentMarker`, `calculatedEduLevel`, `academicDegreeMarker`,
    `academicTitleMarker`, `dataSources`, `lastRefresh`.
    **Nie ma kryterium `orcid`** — po ORCID NIE da się filtrować.
- **CORS: OTWARTY** — preflight `OPTIONS` zwraca
  `Access-Control-Allow-Origin: <odbite Origin>`, `Allow-Methods: POST`,
  `Allow-Headers: content-type`. Fetch z przeglądarki działa.
- **Odpowiedź** (`ScientistResult`): `{results[], pagination{maxCount, token},
  version}`. Każdy `Scientist`:
  - `personalData`: **`orcid`**, `id` (uid POL-on, 40-hex), `firstName`,
    `middleName`, `lastName`, `lastNamePrefix`.
  - `academicDegrees[]`: `academicDegreeName` („Doktor" / „Doktor
    habilitowany"), `grantingYear`, `grantingInstitutionName`,
    `degreeClassification[]` (dziedzina/dyscyplina).
  - `academicTitles[]`: `academicTitleName` (profesura), `grantingYear`.
  - `professionalTitles[]`: `professionalTitleName` (Magister…),
    `graduationYear`, `institutionName`, `courseName`.
  - `employments[]`: `employingInstitutionName`, `startDate`,
    `basicPlaceOfWork`, `declaredDisciplines`.
  - `calculatedEduLevel` (np. „dr hab. inż."), `dataSources`.

**Kluczowe:** wynik zawiera `personalData.orcid`. Dzięki temu szukamy po
nazwisku, a właściwą osobę wybieramy porównując ORCID z wynikiem — homonimy
znikają w 100%.

Dowód (żywe API, „Kowalczewski"):
```
Jacek     Kowalczewski — ORCID 0000-0002-4977-3923 — prof. dr hab. — dr 1994, hab. 2004
Przemysław Kowalczewski — ORCID 0000-0002-0153-4624 — dr hab. inż. — dr 2016, hab. 2023
```

### Czego świadomie NIE używamy (i dlaczego)

- **Usługa `employees` (POL-on)** (`/opendata/polon/employees`): NIE zawiera
  ORCID i ignoruje parametr `?orcid=`. Odrzucona na rzecz `scientist`.
- **Ludzie Nauki** (`ludzie.nauka.gov.pl/api/profiles-api`): ma projekty /
  publikacje / patenty / osiągnięcia per-osobę, ale **CORS zamknięty**
  (brak nagłówków ACAO → przeglądarka blokuje) i wyszukiwarka za OAuth,
  a `profileId` nie da się wyprowadzić z ORCID. **Świadomie wykluczone** —
  wymagałoby proxy w BPP i ręcznego mostu. Poza zakresem.
- **Usługi zintegrowane `project` / `publication` / `product`**: kryteria
  wyszukiwania nie zawierają osoby/ORCID/uid (tylko tytuł/DOI/status) — nie
  da się dostać „projektów tej osoby". Poza zakresem.

Konsekwencja: sekcja pokazuje **stopnie / tytuły / wykształcenie /
zatrudnienie / dyscypliny**. Projektów/publikacji/patentów/osiągnięć-nagród
NIE — nie są dostępne per-osobę w sposób client-side z RAD-on.

## Zakres

### Wchodzi

1. **Przenośny moduł JS „odpytywacz RAD-on"** (`radon-client`), bez zależności
   od BPP, z czystym API:
   - `searchScientists({firstName, lastName, resultNumbers})` →
     `Promise<Scientist[]>` (POST + normalizacja odpowiedzi, obsługa
     paginacji tylko dla pierwszej strony — do dopasowania wystarczy).
   - `matchByOrcid(scientists, orcid)` → `Scientist | null` — normalizuje
     ORCID (usuwa `https://orcid.org/`, spacje, myślniki do porównania) i
     zwraca rekord o zgodnym ORCID; gdy brak zgodnego → `null`.
   - `extractAchievements(scientist)` → znormalizowany obiekt:
     `{stopnie: [{typ, rok, uczelnia, dyscyplina}], tytuly: [{nazwa, rok}],
     wyksztalcenie: [{tytul, rok, uczelnia, kierunek}],
     zatrudnienie: [{instytucja, od, podstawowe, dyscypliny}],
     poziom, zrodla}`.
   - Konfigurowalny `baseUrl` (domyślnie
     `https://radon.nauka.gov.pl/opendata`) — do wydzielenia/testów.
   - Zero zależności zewnętrznych; `fetch` natywny.
2. **Warstwa integracji BPP** (cienka, osobny plik JS) — spina moduł z DOM-em:
   czyta `data-*` (imię, nazwisko, orcid) z kontenera sekcji, woła
   `searchScientists` → `matchByOrcid` → `extractAchievements`, renderuje HTML,
   dokleja podpis „informacje pobrane z RAD-on".
3. **Sekcja w rejestrze profilu** (`bpp.profil_autora`): nowy klucz
   `KLUCZ_RADON = "radon_osiagniecia"`, `TypSekcji(..., template_only=True)`.
   Renderowana tylko gdy `autor.orcid` niepusty. Kolumna domyślna: LEWA
   (przy „Stopnie naukowe"/„Historia zatrudnienia"), do przestawienia jak
   każda sekcja.
4. **Partial szablonu** `autor_sekcje/radon_osiagniecia.html`: kontener z
   `data-orcid`, `data-imie`, `data-nazwisko`, stan „ładowanie…", miejsce na
   wynik, podpis. Reszta dzieje się w JS.
5. **Degradacja bez błędów:** brak sieci / 0 wyników / brak dopasowania po
   ORCID → sekcja chowa swój kontener (nie zostaje pusty nagłówek), brak
   wyjątków w konsoli poza jednym `console.debug`.

### Świadomie poza zakresem

- Ludzie Nauki (projekty/publikacje/patenty/osiągnięcia), proxy w BPP,
  pole `radon_profil_id`, OAuth — **nie robimy**.
- Cache po stronie serwera / zapisywanie pobranych danych w BPP — nie; dane
  są ulotne, pobierane na żywo w przeglądarce.
- Filtrowanie/rozstrzyganie homonimów inne niż po ORCID.

## Architektura i przepływ

```
Django (AutorView)                 Przeglądarka (client-side)
─────────────────                  ──────────────────────────
render sekcji radon_osiagniecia →  <div data-orcid data-imie data-nazwisko>
  (tylko gdy autor.orcid)            │
                                     ├─ integracja.js czyta data-*
                                     ├─ radon-client.searchScientists({imie,nazwisko})
                                     │     POST radon.nauka.gov.pl/opendata/scientist/search
                                     ├─ radon-client.matchByOrcid(wyniki, orcid_z_BPP)
                                     ├─ radon-client.extractAchievements(trafiony)
                                     └─ render HTML + „informacje pobrane z RAD-on"
```

Podział odpowiedzialności (granice modułów):

- `radon-client` — **czysta logika RAD-on**: HTTP + normalizacja. Testowalna
  w izolacji (mock `fetch`). Nie dotyka DOM-u, nie zna BPP. To jest
  „wydzielony odpytywacz".
- `integracja` — **klej DOM↔klient**: I/O na stronie, rendering, degradacja.
- Szablon/rejestr — **osadzenie**: gdzie i kiedy sekcja się pojawia.

## Model danych

**Brak zmian modelu, brak migracji.** Używamy istniejącego `Autor.orcid`
(+ imię/nazwisko). Nic nie zapisujemy.

## Dopasowanie po ORCID (algorytm)

1. Zapytanie: `searchScientists({firstName: autor.imiona, lastName:
   autor.nazwisko})`. (Imiona z BPP mogą zawierać drugie imię — do zapytania
   bierzemy pierwszy człon; RAD-on i tak filtruje po `firstName`/`lastName`.)
2. Normalizacja ORCID po obu stronach: do 16 cyfr/`X` (usuń URL, spacje,
   myślniki), porównanie case-insensitive.
3. `matchByOrcid`: zwróć rekord ze zgodnym `personalData.orcid`.
4. Gdy 0 zgodnych → sekcja się chowa (świadomie NIE pokazujemy „najlepszego
   zgadnięcia" — bez ORCID-matcha ryzyko pomyłki jest za duże).

## Bezpieczeństwo / prywatność

- Wywołanie idzie do publicznego, rządowego API RAD-on (dane jawne z POL-on).
- ORCID i imię/nazwisko autora są już publiczne na podstronie — nie wyciekają
  nowe dane wrażliwe.
- Brak sekretów, tokenów, kluczy w JS. Brak `credentials` w `fetch`
  (żądanie anonimowe, mimo że API odbija `Allow-Credentials`).
- Sekcja wyłącznie gdy `autor.orcid` — nie odpytujemy RAD-on masowo/bez
  potrzeby.
- Odporność na treść z API: renderujemy przez `textContent`/tworzenie węzłów,
  **nie** `innerHTML` z surowych pól — zero XSS z odpowiedzi RAD-on.

## Obsługa błędów (żadnych cichych połknięć)

- Błąd sieci / !ok / timeout → `console.debug("[radon] …", err)` + schowanie
  kontenera. Nie `throw` w górę (nie wywalamy strony), ale i nie „pass" —
  logujemy powód.
- Nieoczekiwany kształt odpowiedzi → traktowany jak brak wyniku (log + chowaj).

## Testy

**JS (jest/istniejący runner JS w repo):**
- `searchScientists`: buduje poprawne ciało (`token: null`, `body:{…}`),
  parsuje `results`, obsługuje pustą listę.
- `matchByOrcid`: trafia przy różnych formatach ORCID (URL, z myślnikami,
  bez), zwraca `null` bez dopasowania, rozróżnia 2 osoby o tym samym nazwisku.
- `extractAchievements`: mapuje stopnie/tytuły/zatrudnienie; odporny na
  brakujące/`null` pola.
- Degradacja: mock `fetch` odrzucony → brak wyjątku, kontener schowany.

**Python (pytest):**
- Render sekcji: gdy `autor.orcid` ustawiony → kontener z poprawnymi
  `data-orcid`/`data-imie`/`data-nazwisko` obecny; gdy pusty ORCID → sekcji
  nie ma.
- Sekcja obecna w `KATALOG_SEKCJI`, przechodzi `waliduj_uklad`/`rozwiaz_uklad`
  (forward-compat: dokleja się do istniejących układów bez migracji danych).

**Świadomie bez testu E2E odpytującego żywy RAD-on** (flaky, zależny od sieci
zewnętrznej). Logika klienta testowana na mockach; kontrakt API udokumentowany
w tym specu.

## Ryzyka

- RAD-on zmieni kształt API / kryteria / CORS → sekcja degraduje się do
  „schowana" (bez błędu). Kontrakt spisany tu; łatwo zaktualizować moduł.
- Autor bez rekordu w RAD-on (nie-naukowiec z ORCID, obcokrajowiec) → brak
  dopasowania → sekcja schowana. Oczekiwane.
- Nazwisko/imię w BPP odbiega od POL-on (warianty, znaki) → brak dopasowania.
  Akceptowalne; ORCID-match jest twardym warunkiem poprawności.
