# Osiągnięcia autora z RAD-on OpenData (client-side, po ORCID)

**Data:** 2026-07-07
**Gałąź:** `feat/radon-profil-autora` (na bazie `feature/profil-autora`, PR #385)
**Status:** spec zaakceptowany do implementacji

## Cel

Na podstronie autora (`/autor/<pk|slug>/`) dla naukowców posiadających ORCID
dodać sekcję z ich osiągnięciami pobranymi **na żywo z RAD-on OpenData** —
**po stronie klienta** (fetch z przeglądarki), z podpisem drobnymi literami
„informacje pobrane z RAD-on".

Pokazujemy to, czego BPP nie ma we własnej bazie: **stopnie/tytuły naukowe,
zatrudnienie, projekty naukowe (z kwotami), patenty i prawa ochronne,
osiągnięcia artystyczne (z nagrodami)**. **Publikacji NIE pobieramy** — BPP ma
je we własnej bazie.

Kod odpytujący RAD-on ma być **wydzielonym, przenośnym modułem JS** (bez
zależności od BPP), tak by dało się go wyjąć i użyć gdzie indziej.

## Ustalenia badawcze (przetestowane na żywo 2026-07-07)

Reverse-engineering + testy żywego API. **Cała rodzina `/opendata/*` ma CORS
otwarty** (preflight/GET/POST odbijają `Origin` → fetch z przeglądarki działa;
zweryfikowane na `scientist/search`, `polon/projects`, `polon/products`,
`polon/artisticAchievements`, `polon/publications`).

Wszystkie endpointy: baza `https://radon.nauka.gov.pl/opendata`, odpowiedź
`{results[], pagination{maxCount, token}, version}`, paginacja kursorem
`token` (`null`/pominięty na starcie).

### A. `scientist` (dane zintegrowane) — CV: stopnie/tytuły/zatrudnienie

- **`POST /opendata/scientist/search`**, ciało:
  ```json
  {"resultNumbers": 10, "token": null, "body": {"firstName": "...", "lastName": "..."}}
  ```
  `token` MUSI być `null`/pominięty na starcie (`""` → `400 Malformed token`).
  Kryteria (`body`): `firstName`, `lastName`, `uid`, markery. **Bez filtra
  `orcid`.**
- Rekord: `personalData{orcid, id(uid POL-on 40-hex), firstName, middleName,
  lastName}`, `academicDegrees[]` (Doktor/Doktor habilitowany + `grantingYear`
  + `grantingInstitutionName` + `degreeClassification`), `academicTitles[]`
  (profesura + rok), `professionalTitles[]` (magisterium + rok + uczelnia),
  `employments[]`, `calculatedEduLevel`, `dataSources`.
- **Wynik zawiera `personalData.orcid`** → dopasowanie po nazwisku, weryfikacja
  po ORCID.

### B. `polon/projects` — PROJEKTY NAUKOWE (filtr po kierowniku)

- **`GET /opendata/polon/projects`** z parametrami:
  `projectManagerFirstName`, `projectManagerLastName`, `disciplineName`,
  `disciplineCode`, `entityShowingAchievementsName`, `projectStartDate`,
  `projectEndDate`, `resultNumbers`, `token`.
- Rekord: `projectTitlePl`/`projectTitleEn`, `acronym`, `totalFunds`,
  `receivedFunds`, `nationalFunds`, `foreignFunds`, `projectStartDate`,
  `projectEndDate`, `projectGrantDate`, `projectClassification`,
  `financedCompetition`, `financingInstitutions[]`, `implementingInstitutions[]`,
  `disciplines[]`, `dataSource`, oraz **`projectManagers[]`** z polami
  `firstName`, `middleName`, `lastName`, **`ORCID`**, `kindManager`,
  `institutionName`, `startDate`, `endDate`.
- **Weryfikacja:** `projectManagers[].ORCID == autor.orcid` (potwierdzone na
  żywo: Kowalczewski → 3 projekty, manager ORCID = `0000-0002-0153-4624`,
  kwoty w `totalFunds`).

### C. `polon/products` — PATENTY I PRAWA OCHRONNE (filtr po wynalazcy)

- **`GET /opendata/polon/products`**:
  `inventorFirstName`, `inventorLastName`, `institutionName`,
  `productTitle`, `protectionTypeCode`, `publicationDateFrom/To`,
  `resultNumbers`, `token`.
- Rekord: `productTitles[]`, `protectionType`, `protectionTitle`,
  `publicationNumber`, `publicationDate`, `applicationDate`,
  `grantingInstitutionName`, `productDescription`, `applicants[]`, oraz
  **`inventors[]`** → `persons[]` z `firstName`, `lastName`,
  **`relatedOrcid`** (bywa `null`).
- **Weryfikacja:** `inventors[].persons[].relatedOrcid == autor.orcid`; gdy
  `relatedOrcid` puste — dopasowanie tylko po nazwisku (słabsze; oznaczamy jako
  „niezweryfikowane po ORCID" wewnętrznie, patrz reguła niżej).

### D. `polon/artisticAchievements` — OSIĄGNIĘCIA ARTYSTYCZNE (filtr po autorze)

- **`GET /opendata/polon/artisticAchievements`**:
  `authorFirstName`, `authorLastName`, `institutionName`, `title`,
  `achievementKindCode`, `implementationYearFrom/To`, `resultNumbers`, `token`.
- Rekord: `title`, `discipline`, `achievementKind`, `achievementType`,
  `implementationYear`, `firstPublicationYear`, `publisherName`,
  `achievementRange`, **`awards[]`** (`competitionName`, `awardYear`,
  `awardingInstitution`), oraz **`authors[]`** (`AuthorData`) z `firstName`,
  `lastName`, **`orcid`**.
- **Weryfikacja:** `authors[].orcid == autor.orcid`. (Domena akademii sztuk —
  dla większości autorów `maxCount=0`; sekcja typu chowa się pusta.)

### Czego świadomie NIE używamy

- **Publikacje** (`polon/publications`, filtr `orcidId` istnieje) — **BPP ma
  publikacje we własnej bazie**. Poza zakresem.
- **`polon/employees`** — brak ORCID, odrzucone na rzecz `scientist`.
- **Ludzie Nauki** (`ludzie.nauka.gov.pl`) — CORS zamknięty, OAuth,
  `profileId` nie z ORCID. Poza zakresem.
- **Usługi zintegrowane `project`/`publication`/`product`** — kryteria bez
  osoby; używamy per-osobowych usług POL-on (B/C/D powyżej).

## Zakres

### Wchodzi

1. **Przenośny moduł JS „odpytywacz RAD-on"** (`radon-client`), bez zależności
   od BPP, natywny `fetch`, konfigurowalny `baseUrl` (domyślnie
   `https://radon.nauka.gov.pl/opendata`), z metodami:
   - `searchScientist({firstName, lastName})` → `Scientist[]` (POST
     `scientist/search`).
   - `fetchProjects({firstName, lastName})` → `Project[]`
     (GET `polon/projects`).
   - `fetchPatents({firstName, lastName})` → `Patent[]`
     (GET `polon/products`).
   - `fetchArtisticAchievements({firstName, lastName})` → `Achievement[]`
     (GET `polon/artisticAchievements`).
   - Helper `orcidMatches(a, b)` — normalizuje (usuwa URL/spacje/myślniki,
     case-insensitive) i porównuje.
   - Selektory: `pickScientistByOrcid`, `filterProjectsByOrcid` (po
     `projectManagers[].ORCID`), `filterPatentsByOrcid` (po
     `inventors[].persons[].relatedOrcid`), `filterAchievementsByOrcid` (po
     `authors[].orcid`).
   - Normalizatory `extract*` → płaskie obiekty do renderu (patrz „Pola
     wyświetlane").
   - Zero zależności zewnętrznych; sprawdzone na NPM — gotowego klienta
     RAD-on/POL-on nie ma (repo OPI to notebooki R/Python).
2. **Warstwa integracji BPP** (cienki, osobny plik JS) — czyta `data-*`
   (imię, nazwisko, orcid) z kontenera sekcji, woła powyższe metody
   równolegle (`Promise.allSettled`), filtruje po ORCID, renderuje pod-bloki,
   dokleja podpis „informacje pobrane z RAD-on".
3. **Sekcja w rejestrze profilu** (`bpp.profil_autora`): nowy klucz
   `KLUCZ_RADON = "radon_osiagniecia"`, `TypSekcji(..., template_only=True)`,
   renderowana tylko gdy `autor.orcid`. Kolumna domyślna: LEWA.
4. **Partial** `autor_sekcje/radon_osiagniecia.html`: kontener z
   `data-orcid`/`data-imie`/`data-nazwisko`, stan „ładowanie…", cztery
   pod-kontenery (CV / projekty / patenty / osiągnięcia artystyczne), podpis.
5. **Degradacja bez błędów, per pod-blok:** każdy typ danych ładuje się
   niezależnie; brak sieci / 0 wyników / brak ORCID-matcha → dany pod-blok się
   chowa; gdy wszystkie puste → cała sekcja się chowa.

### Pola wyświetlane (per typ)

- **CV (scientist):** stopnie „Doktor 2016, UP Poznań", „Doktor habilitowany
  2023", tytuł profesorski (rok), zatrudnienie (instytucja + od), dyscypliny.
- **Projekty:** tytuł PL, program/konkurs (`financedCompetition`),
  kwota (`totalFunds`), lata (`projectStartDate`–`projectEndDate`),
  instytucja finansująca, rola (`projectManagers[].kindManager`).
- **Patenty:** tytuł (`productTitles`), typ ochrony (`protectionType`),
  nr i data publikacji, instytucja udzielająca.
- **Osiągnięcia artystyczne:** tytuł, rodzaj, rok, nagrody (`awards[]`:
  konkurs + rok).

### Świadomie poza zakresem

Publikacje; Ludzie Nauki; proxy/OAuth; pola/migracje na modelu; cache po
stronie serwera; rozstrzyganie homonimów inne niż po ORCID.

## Model danych

**Brak zmian modelu, brak migracji.** Używamy `Autor.orcid` + imię/nazwisko.
Nic nie zapisujemy — dane ulotne, pobierane na żywo w przeglądarce.

## Reguła dopasowania po ORCID

1. Normalizacja ORCID po obu stronach do 16 znaków (cyfry + `X`), porównanie
   case-insensitive.
2. **scientist / projekty / osiągnięcia artystyczne:** pokazujemy wyłącznie
   rekordy ze zgodnym ORCID (`personalData.orcid` / `projectManagers[].ORCID`
   / `authors[].orcid`). Brak zgodnego → pod-blok pusty → schowany.
3. **patenty:** rekord ze zgodnym `relatedOrcid` pokazujemy zawsze; rekord z
   `relatedOrcid == null` (dane POL-on niekompletne) pokazujemy tylko gdy
   nazwisko+imię są jednoznaczne dla tego autora — inaczej pomijamy. (Patenty
   bez ORCID to jedyny słabszy przypadek; świadomie ostrożni.)

## Bezpieczeństwo / prywatność

- Wywołania do publicznego, rządowego API RAD-on (dane jawne POL-on/PBN).
- ORCID + imię/nazwisko są już publiczne na podstronie — brak nowego wycieku.
- Brak sekretów/tokenów w JS. Brak `credentials` w `fetch`.
- Sekcja tylko gdy `autor.orcid` — nie odpytujemy RAD-on bez potrzeby.
- Render przez `textContent`/tworzenie węzłów, **nie** `innerHTML` z surowych
  pól API → zero XSS z odpowiedzi RAD-on.

## Obsługa błędów (żadnych cichych połknięć)

- Każde zapytanie w `Promise.allSettled`; odrzucone/`!ok`/timeout →
  `console.debug("[radon] <endpoint>", err)` + schowanie danego pod-bloku.
  Nie `throw` w górę (nie wywalamy strony), ale zawsze logujemy powód.
- Nieoczekiwany kształt odpowiedzi → traktowany jak brak wyniku (log + chowaj).

## Testy

**JS:**
- Każda metoda `fetch*`: buduje poprawny URL/ciało, parsuje `results`,
  obsługuje pustkę i błąd sieci (mock `fetch`).
- `orcidMatches`: różne formaty (URL, myślniki, spacje), case, `null`.
- Selektory `filter*ByOrcid`: rozróżniają dwie osoby o tym samym nazwisku po
  ORCID; projekty po `projectManagers[].ORCID`; patenty po
  `inventors[].persons[].relatedOrcid`; osiągnięcia po `authors[].orcid`.
- `extract*`: mapują pola do renderu; odporne na brakujące/`null`.
- Degradacja: część zapytań odrzucona → pozostałe pod-bloki renderują,
  odrzucone chowają się, brak wyjątku globalnego.

**Python (pytest):**
- Render sekcji: `autor.orcid` ustawiony → kontener z poprawnymi `data-*`;
  pusty ORCID → brak sekcji.
- Sekcja w `KATALOG_SEKCJI`, przechodzi `waliduj_uklad`/`rozwiaz_uklad`
  (forward-compat: dokleja się bez migracji danych).

**Bez E2E odpytującego żywy RAD-on** (flaky/sieć zewnętrzna). Kontrakt API
udokumentowany w tym specu; logika na mockach.

## Ryzyka

- RAD-on zmieni API/kryteria/CORS → dany pod-blok degraduje do „schowany".
  Kontrakt spisany tu.
- Autor bez rekordów w RAD-on → pod-bloki puste → schowane. Oczekiwane.
- Rozjazd imię/nazwisko BPP vs POL-on → brak dopasowania. Akceptowalne;
  ORCID-match jest twardym warunkiem poprawności (poza opisanym wyjątkiem
  patentów bez ORCID).
- Patenty bez `relatedOrcid` → ostrożna reguła nazwiskowa; ryzyko rzadkie.
