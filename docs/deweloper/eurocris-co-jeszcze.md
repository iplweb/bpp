# euroCRIS / OpenAIRE — co jeszcze zostało do zrobienia

Data: 2026-08-04
Kontekst: po wdrożeniu aplikacji `cerif_export` (wariant A).

## Stan wyjściowy

Endpoint `/cerif-oai/` wystawia CERIF-XML zgodny z **OpenAIRE Guidelines for
CRIS Managers 1.2.0**. `openaire-cris-validator` 2.1.1 przechodzi w całości
(`OK (13 tests)`) na żywym endpoincie z bazą produkcyjną.

Zaimplementowane encje: `Publication` (wydawnictwa ciągłe i zwarte, prace
doktorskie i habilitacyjne, źródła jako kanały wydawnicze), `Person`,
`OrgUnit`, `Patent`, `Event`, `Service`.

**Zgodność formalna jest osiągnięta.** Wszystko poniżej to różnica między
„przechodzi walidator" a „daje uczelni to, po co się w to wchodzi".

---

## A. Encje niezaimplementowane — największa realna wartość

Sety istnieją, ale są puste. Profil na to pozwala (wymaga istnienia setu, nie
jego zapełnienia), więc walidator przechodzi. Natomiast OpenAIRE nie zobaczy
przez to najważniejszego, co CRIS ma do pokazania: **powiązań publikacja ↔
projekt ↔ finansowanie**.

### A1. `Project` — set `openaire_cris_projects`

Model `Grant` (`src/bpp/models/grant.py`) ma cztery pola: `nazwa_projektu`,
`zrodlo_finansowania`, `numer_projektu`, `rok`. To w praktyce etykieta numeru
grantu przypinana do publikacji, nie encja projektu.

Do dodania: `StartDate`/`EndDate` (dziś tylko `rok`), `Acronym`,
`PrincipalInvestigator`, `Coordinator`/`Partner`/`Contractor`, `Team`/`Member`,
`Abstract`, `Subject`, `Keyword`, `Status`, `Funded/By/As`.

Zakres: model + admin + UI + migracja danych. **5–7 osobodni.**

To jest zmiana produktowa, nie tylko eksportowa — dotyka formularzy, którymi
redakcja wprowadza dane. Warto ją brać razem z A2.

### A2. `Funding` — set `openaire_cris_funding`

Nie istnieje. `Grant.zrodlo_finansowania` to `TextField`. Brak encji
finansującego (Funder = `OrgUnit` z `FundRefID`), brak kwot, brak `GrantDOI`.

`Funding/Type` jest w profilu **obowiązkowy**, ze słownika OpenAIRE Funding
Types (Funding Programme / Call / Tender / Gift / Internal Funding / Contract
/ Award / Grant).

Zakres: nowy model + Funder + powiązanie z `Project`. **4–6 osobodni.**

### A3. `Product` — set `openaire_cris_products`

Zbiory danych, oprogramowanie, inne produkty badawcze z własnym DOI. BPP nie
ma takiej encji — `Element_Repozytorium` to załącznik plikowy do rekordu, nie
samodzielny produkt.

**5–8 osobodni.** Sensowne dopiero, gdy uczelnia faktycznie rejestruje zbiory
danych.

### A4. `Equipment` — set `openaire_cris_equipments`

Aparatura badawcza. Nie istnieje. **2–3 osobodni.** Najniższy priorytet.

---

## B. Jakość danych — do zrobienia przez redakcję, nie przez programistę

Kod jest gotowy, brakuje wartości w słownikach. Komenda
`cerif_raport_mapowan` wypisuje wszystkie braki.

| Co | Stan | Skutek pozostawienia |
|---|---|---|
| `Charakter_Formalny.coar_type` | do zmapowania ~40–60 wartości | wszystko leci jako ogólne `text` — OpenAIRE nie odróżni artykułu od rozdziału |
| `Rodzaj_Prawa_Patentowego.coar_type` | do zmapowania | patenty jako ogólne `patent` |
| `Jezyk.kod_bcp47` | automat wypełnił tylko `pol.` → `pl` | brak `Language` przy ~8 językach |
| `Licencja_OpenAccess.uri` | wygenerowane automatycznie, **wersja 4.0 to zgadywanka** | błędna wersja licencji w metadanych |
| `Tryb_OpenAccess_*.coar_access_right` | do zmapowania (4 wartości) | brak informacji o otwartości |
| `Uczelnia.ror_id`, `Jednostka.ror_id` | puste | **patrz niżej — to jest ważne** |

**ROR wymaga osobnego akapitu.** Bez `RORID` na `Uczelnia` publikacje nie
skleją się z profilem instytucji w OpenAIRE Explore. Formalnie pole jest
opcjonalne i walidator go nie wymaga, ale w praktyce jest to podstawowy klucz
dopasowania instytucji po stronie agregatora. Identyfikator uczelni znajdziesz
w <https://ror.org/search>. To jedna wartość do wpisania w adminie i największy
zwrot z włożonej minuty w całej tej liście.

---

## C. Protokół — nagrobki dla skasowanych rekordów

`Identify` deklaruje `deletedRecord=no`, co jest legalne. Konsekwencja: rekord
usunięty z BPP **zostaje w indeksie OpenAIRE na zawsze**, bo harvester
przyrostowy nie ma skąd wiedzieć, że zniknął.

Rozwiązanie: tabela nagrobków (rekord znika ze źródła → wiersz zostaje
z flagą `deleted`), `deletedRecord=transient` i emisja nagłówków ze
`status="deleted"`. **2–3 osobodni.**

Priorytet rośnie z czasem — im dłużej eksport działa bez nagrobków, tym więcej
zombie w indeksie.

---

## D. Kroki organizacyjne, nie programistyczne

1. **Wypełnić `Uczelnia.ror_id`** (patrz B).
2. **Uruchomić walidator na docelowym, publicznym adresie**:
   `make cerif-validate URL=https://<instancja>/cerif-oai/`.
   Walidacja lokalna nie sprawdzi HTTPS, przekierowań ani nagłówków proxy.
3. **Zarejestrować CRIS w DRIS** (euroCRIS): <https://dspacecris.eurocris.org/cris/explore/dris>.
4. **Zarejestrować endpoint w OpenAIRE Provide**:
   <https://provide.openaire.eu/>. Zespół agregacji OpenAIRE robi własną
   walidację; dopiero po niej dane zaczynają być zbierane.
5. **Decyzja RODO — do podjęcia PRZED punktem 4.** Set
   `openaire_cris_persons` jest domyślnie włączony i wystawia imię, nazwisko,
   ORCID, płeć oraz historię zatrudnienia do publicznego endpointu
   agregowanego przez OpenAIRE. Jedynym zabezpieczeniem jest `Autor.pokazuj`.
   Do rozstrzygnięcia przez uczelnię: czy taki zakres jest akceptowalny, czy
   wyłączyć set osób (`eksport_cerif_wlaczony=False` wyłącza całość; węższe
   wyłączenie samego setu osób wymagałoby drobnej zmiany w kodzie).

---

## E. Drobiazgi z profilu — pola dziś pomijane

Żadne z nich nie blokuje walidatora; każde poprawia kompletność metadanych.

| Element | Czego brakuje |
|---|---|
| `Publication/StartPage`,`EndPage` | `strony` to jedno pole tekstowe; rozbijamy tylko wzorzec `123-456`, reszta jest pomijana |
| `Publication/ISI-Number`, `SCP-Number` | siedzą w `Zewnetrzna_Baza_Danych.info` jako wolny tekst |
| `Publication/Handle`, `URN`, `ZDB-ID` | BPP nie przechowuje |
| `Publication/Subject` | dziś brak; `Dyscyplina_Naukowa` używa kodów polskich, profil oczekuje np. OECD FOS |
| `Publication/FileLocations` | `Element_Repozytorium` to `GenericForeignKey` bez `GenericRelation` po stronie `bpp` — prefetch niemożliwy bez zmiany w `src/bpp/models/` |
| `Patent/CountryCode`, `Issuer` | BPP nie przechowuje (implicite UPRP) |
| `Event/Type`, `Organizer`, `Sponsor` | `Konferencja` nie ma tych pól; `panstwo` jest tekstem, nie ISO 3166 |
| `Person/ScopusAuthorID`, `ResearcherID`, `ISNI` | BPP przechowuje tylko ORCID i PBN UID |
| `OrgUnit/ISNI`, `GRID`, `FundRefID` | brak (ROR wystarcza, reszta opcjonalna) |

---

## Sugerowana kolejność

1. **B (ROR + mapowania COAR)** — dni robocze redakcji, nie programisty,
   a bez tego eksport jest formalnie poprawny i merytorycznie ubogi.
2. **D (rejestracja + decyzja RODO)** — odblokowuje jakikolwiek efekt.
3. **C (nagrobki)** — im wcześniej, tym mniej śmieci w indeksie.
4. **A1 + A2 (Project + Funding)** — największa wartość merytoryczna,
   ~10–13 osobodni, wymaga decyzji produktowej o rozbudowie modelu grantów.
5. **A3, A4 (Product, Equipment)** — gdy uczelnia zacznie je rejestrować.
6. **E** — przy okazji, pojedynczo.
