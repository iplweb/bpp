# euroCRIS / OpenAIRE — co jeszcze zostało do zrobienia

> **Śledzenie prac:** issue-parasol [#709](https://github.com/iplweb/bpp/issues/709).
> Ten dokument opisuje **dlaczego** jest jak jest; issues opisują **co i kto**.
> Konfigurację i uruchomienie eksportu na instancji opisuje
> [Eksport CERIF / OpenAIRE — dla administratora](../administrator/eksport-cerif.md).
> Otwarte sekcje mają odpowiadające im issues: A3 → #703, A4 → #704,
> B → #705 i #706, D → #707, F1 → #708. Zrobione: A1 → #701, A2 → #702
> (opisane w sekcji G).

Data: 2026-08-04. Aktualizacje: 2026-08-05 — sekcje A1 i A2 zrobione
(przeniesione do G); 2026-08-05 — poprawka pustego `PartOf` (#724).
Kontekst: po wdrożeniu aplikacji `cerif_export` (wariant A).

## Stan wyjściowy

Endpoint `/cerif-oai/` wystawia CERIF-XML zgodny z **OpenAIRE Guidelines for
CRIS Managers 1.2.0**. Zaimplementowane encje: `Publication` (wydawnictwa
ciągłe i zwarte, prace doktorskie i habilitacyjne, źródła jako kanały
wydawnicze), `Person`, `OrgUnit`, `Patent`, `Event`, `Service`, `Project`
i `Funding`.

**Zgodność formalna jest osiągnięta** — w tym sensie, że wszystkie wymagane
elementy profilu są zaimplementowane. Wszystko poniżej to różnica między
„przechodzi walidator" a „daje uczelni to, po co się w to wchodzi".

### Stan walidacji

| Data | Wynik `openaire-cris-validator` 2.1.1 |
|---|---|
| 2026-08-04 | `OK (13 tests)` na żywym endpoincie z bazą produkcyjną |
| 2026-08-05 | **2 błędy na 13** — `check500_CheckOrgUnits` i `check990` |
| po #724 | do potwierdzenia ponownym przebiegiem po wdrożeniu |

Błąd z 2026-08-05: jednostka, której jednostka nadrzędna jest wyłączona
z eksportu, dostawała pusty `<PartOf/>` — element niepoprawny wobec XSD.
Walidator **przerywa harvest setu na pierwszym złym rekordzie**, więc
kolejne jednostki nie trafiały do jego indeksu i ich referencje wyglądały
na wiszące. Stąd dwa błędy z jednej przyczyny (drugi był kaskadą).

Wniosek na przyszłość, ważniejszy niż sama poprawka: **zielony wynik
walidatora zależy od danych, nie tylko od kodu.** Przypadek wyszedł dopiero
na bazie, w której ktoś ukrył jednostkę nadrzędną — na danych testowych
i na bazie z 2026-08-04 nie występował. Po każdej zmianie w serializerach
i po większych zmianach w danych warto przepuścić endpoint przez
`make cerif-validate` (sekcja D, punkt 2), zamiast zakładać, że raz zielony
został zielony.

---

## A. Encje niezaimplementowane — największa realna wartość

Sety istnieją, ale bywają puste. Profil na to pozwala (wymaga istnienia setu,
nie jego zapełnienia), więc walidator przechodzi. Natomiast OpenAIRE nie
zobaczy przez to najważniejszego, co CRIS ma do pokazania: **powiązań
publikacja ↔ projekt ↔ finansowanie**.

Łańcuch publikacja ↔ projekt ↔ finansowanie jest już **zamknięty po stronie
kodu** (sekcja G) — otwarte zostają `Product` i `Equipment`. Uwaga: zamknięty
łańcuch nie znaczy wypełniony. Dopóki redakcja nie wprowadzi projektów
i nie podepnie do nich numerów grantów, sety `projects` i `funding` są puste
tak samo jak przed zmianą.

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
   Target wymaga JRE 17+ **albo** Dockera — nie wymaga już Mavena ani JDK,
   bo pobiera gotowego JAR-a z <https://github.com/iplweb/openaire-cris-validator>.
3. **Zarejestrować CRIS w DRIS** (euroCRIS): <https://dspacecris.eurocris.org/cris/explore/dris>.
4. **Zarejestrować endpoint w OpenAIRE Provide**:
   <https://provide.openaire.eu/>. Zespół agregacji OpenAIRE robi własną
   walidację; dopiero po niej dane zaczynają być zbierane.
5. **Decyzja RODO — do podjęcia PRZED punktem 4.** Set
   `openaire_cris_persons` jest domyślnie włączony i wystawia imię, nazwisko,
   ORCID, płeć oraz historię zatrudnienia do publicznego endpointu
   agregowanego przez OpenAIRE. Jedynym zabezpieczeniem jest `Autor.pokazuj`.
   Do rozstrzygnięcia przez uczelnię: czy taki zakres jest akceptowalny, czy
   wyłączyć set osób. `eksport_cerif_wlaczony=False` wyłącza całość, a
   `eksport_cerif_osoby=False` — sam set osób (autorzy zostają wtedy przy
   publikacjach jako samo imię i nazwisko, bez `@id`, ORCID-a i afiliacji).

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
| `OrgUnit/ISNI`, `GRID` | brak (ROR wystarcza, reszta opcjonalna) |
| `OrgUnit/FundRefID` | wychodzi dla instytucji finansujących (`Instytucja_Finansujaca.fundref_id`); dla jednostek i uczelni nadal brak — nie mają Crossref Funder ID |

---

## Sugerowana kolejność

1. **B (ROR + mapowania COAR)** — dni robocze redakcji, nie programisty,
   a bez tego eksport jest formalnie poprawny i merytorycznie ubogi.
2. **Wprowadzenie projektów przez redakcję** — kod z A1/A2 jest gotowy
   (sekcja G), ale bez danych sety `projects` i `funding` są puste tak samo
   jak przed zmianą. To jedyna pozycja z sekcji G, która jeszcze coś wymaga.
3. **D (rejestracja + decyzja RODO)** — odblokowuje jakikolwiek efekt.
4. **C (nagrobki)** — im wcześniej, tym mniej śmieci w indeksie.
5. **F1 (`FileLocations`)** — dziś eksport nie podaje lokalizacji pełnych
   tekstów, a to jest główna rzecz, po którą przychodzi OpenAIRE. Wysoko jak
   na „znane ograniczenie".
6. **A3, A4 (Product, Equipment)** — gdy uczelnia zacznie je rejestrować.
7. **E** — przy okazji, pojedynczo.

---

## F. Znane ograniczenia wdrożenia (z self-review PR #699)

Rzeczy świadomie zostawione, żeby nie były zaskoczeniem po wdrożeniu.

### F1. `FileLocations` nigdy nie powstaje — kod jest martwy

`wspolne.ATRYBUT_PLIKI` jest odczytywany, ale **nikt go nie ustawia**.
Powód: `Element_Repozytorium` wiąże się z publikacją przez
`GenericForeignKey` bez odwrotnej `GenericRelation`, więc provider nie ma
czego prefetchować, a serializerowi nie wolno odpytywać bazy.

Skutek: eksport **nie podaje lokalizacji pełnych tekstów** — a to jest
główna rzecz, po którą OpenAIRE przychodzi. Domknięcie wymaga dodania
`GenericRelation` w `src/bpp/models/`, czyli zmiany poza `cerif_export`.

### F2. Ukryty autor nie zostanie wycofany z OpenAIRE

`deletedRecord=no` (brak nagrobków, patrz sekcja C) znaczy, że gdy autor
poprosi o `pokazuj=False`, harvest przyrostowy po prostu przestanie go
widzieć — a agregator zachowa poprzedni rekord. W praktyce: **wpis
w OpenAIRE zostanie na zawsze**.

Przy zestawie danych obejmującym ORCID nie jest to neutralna decyzja
techniczna. Do rozważenia: `deletedRecord=persistent` przynajmniej dla setu
`persons`.

### F3. `PresentedAt/Event` dostaje identyfikator bezwarunkowo

Osadzone `Event` reużywa serializera rekordowego, który celowo pomija zbiory
widoczności. Dziś nieszkodliwe, bo widoczność konferencji jest pochodną
widoczności publikacji. Ale gdy `Konferencja` dostanie kiedyś opt-out
(analogicznie do `Jednostka.nie_eksportuj_przez_api`), zaczną powstawać
wiszące referencje i kontrola 5a walidatora zacznie padać — po cichu, bo
żaden dzisiejszy test tego nie pokrywa.

### F4. `adminEmail` w `Identify` pochodzi z globalnego `settings.ADMINS`

Czyli w każdej odpowiedzi `Identify` widnieje adres administratora
instalacji, a nie osoby odpowiedzialnej za CRIS w danej uczelni. Przy
wdrożeniu multi-hosted warto dodać pole na `Uczelnia` albo osobne
ustawienie.

### F5. Drobiazgi protokołu

- Powtórzony argument `verb` daje `badArgument` zamiast `badVerb`.
- Nieznany `setSpec` przekazany w resumption tokenie daje `noRecordsMatch`
  zamiast `badResumptionToken`.

Oba są odstępstwami od litery OAI-PMH, których walidator nie sprawdza.

---

## G. Zrobione — dla kontekstu, nie do roboty

Sekcje A1 i A2 były kiedyś największą pozycją tej listy. Zostają tutaj, bo
dokument opisuje **dlaczego jest jak jest**, a decyzje o świadomych
pominięciach nadal obowiązują i nadal bywa, że ktoś o nie pyta.

### A1. `Project` — set `openaire_cris_projects` (#701)

Model `Grant` (`src/bpp/models/grant.py`) pozostał tym, czym był: etykietą
numeru grantu przypinaną do publikacji. Obok niego stanął **`Projekt`**
(`src/bpp/models/projekt.py`) — pełna encja projektu badawczego, a `Grant`
dostał do niego FK. Dzięki temu istniejące numery grantów nie wymagają
migracji: redakcja podpina je do projektów stopniowo, a rekordy bez projektu
działają dalej po staremu.

Zaimplementowane:

- **model + admin** — `Projekt` (tytuł PL/EN, akronim, daty rozpoczęcia
  i zakończenia, status, abstrakt PL/EN, dyscypliny, słowa kluczowe,
  jednostka realizująca), `Projekt_Autor` (zespół: kierownik / wykonawca /
  współwykonawca);
- **eksport** — `src/cerif_export/cerif/project.py`,
  `src/cerif_export/providers/projekty.py`: `Acronym`, `Title` (PL i EN),
  `StartDate`, `EndDate`, `Consortium/Coordinator`, `Team/PrincipalInvestigator`
  i `Team/Member`, `Funded/By` + `Funded/As`, `Subject`, `Keyword`, `Abstract`,
  `Status`;
- **powiązanie z dorobkiem** — `Publication/OriginatesFrom`
  i `Patent/OriginatesFrom` osadzają pełny `<Project>`. To ogniwo, dla którego
  cała sekcja A w ogóle ma sens: bez niego agregator dostaje dwie rozłączne
  listy.

Świadomie pominięte:

| Element | Dlaczego |
|---|---|
| `Project/Type` | Profil oczekuje `cfGenericURIClassification__Type` ze schematem typologii projektów (badawczy / wdrożeniowy / infrastrukturalny). BPP takiej typologii nie prowadzi, a wpisanie wszystkim tej samej wartości byłoby twierdzeniem bez pokrycia w danych. |
| `Projekt.strona_www` | Sekwencja `Project` nie ma elementu na adres strony. Wciśnięcie URL-a do generycznego `Identifier` mówiłoby, że to identyfikator projektu — czym adres strony nie jest. |
| `Team/*/Affiliation` | `Projekt_Autor` nie niesie jednostki, a podstawienie `Projekt.jednostka` twierdziłoby, że każdy członek zespołu pracuje w jednostce realizującej. Bywa nieprawdą przy projektach międzyjednostkowych. |
| `Consortium/Partner`, `Consortium/Contractor` | Wymagają encji instytucji zewnętrznej (partner spoza uczelni), której BPP nie ma. `Jednostka` opisuje wyłącznie strukturę własnej uczelni. |
| Front publiczny i API dla projektów | Poza zakresem: zmiana miała domknąć eksport CERIF, a nie wprowadzić projekty do serwisu i do `/api/v1/`. |

Uwaga o schematach klasyfikacji: `Status` i `Subject` używają **własnych**
przestrzeni nazw (`const.SCHEMAT_STATUSU_PROJEKTU`, `const.SCHEMAT_DYSCYPLIN`),
bo profil nie dostarcza słownika ani dla statusu projektu, ani dla polskiej
klasyfikacji dyscyplin naukowych — a mapowanie dyscyplin na Fields of Science
jest osobną decyzją merytoryczną, nie techniczną. Własny schemat jawnie nazywa
pochodzenie wartości; to lepsze i od pominięcia danych, i od podszycia się pod
cudzy słownik.

### A2. `Funding` — set `openaire_cris_funding` (#702)

Zaimplementowane:

- **`Instytucja_Finansujaca`** — słownik grantodawców z `ror_id`
  i `fundref_id` (Crossref Funder ID), zaseedowany siedmioma pozycjami (NCN,
  NCBiR, MNiSW/MEiN, FNP, NAWA, NPRH, ABM);
- **`Finansowanie`** — typ (obowiązkowy, ze słownika OpenAIRE Funding Types),
  nazwa programu, numer umowy, `GrantDOI`, kwota + waluta, FK do projektu
  i do instytucji;
- **eksport** — `src/cerif_export/cerif/funding.py`,
  `src/cerif_export/providers/finansowanie.py`. `Funding/Funder` to
  **referencja** do `OrgUnit`; grantodawcy wychodzą w secie
  `openaire_cris_orgunits`, bo profil nie ma osobnej encji finansującego.
  Ta sama funkcja serializująca obsługuje rekord setu i element osadzony
  w `Project/Funded/As` — kontrola 5b walidatora (encja osadzona jest
  podzbiorem pełnego rekordu) jest wtedy spełniona trywialnie.

Świadomie pominięte:

| Element | Dlaczego |
|---|---|
| `Funding/Amount` domyślnie | Kwoty grantów bywają objęte klauzulą poufności, więc wychodzą dopiero po włączeniu `Uczelnia.eksport_cerif_kwoty` (domyślnie wyłączone). |
| `Funding/Acronym` | BPP nie ma osobnego pola na skrót finansowania, a wpisanie tam nazwy programu dublowałoby `Name`. |
| `Funding/PartOf`, `Duration`, `OAMandate` | Brak odpowiadających danych w modelu. |
| Numer umowy jako typowany identyfikator | Numer umowy grantowej nie ma w CERIF-ie własnego typu, a atrybut `type` jest obowiązkowy — stąd własny URI (`funding.TYP_ID_NUMER_UMOWY`), zamiast podszycia się pod cudzy słownik. |
| Front publiczny i API dla finansowania | Jak wyżej: zmiana domykała eksport, nie serwis. |

Integralność referencyjna całości (`Consortium/Coordinator`,
`Team/PrincipalInvestigator`, `Team/Member`, `Funded/By`, `Funding/Funder`)
jest pilnowana automatycznie —
`src/cerif_export/tests/test_integralnosc_projektow.py` harvestuje wszystkie
sety przez `ListRecords` i sprawdza, że każdy `@id` z encji osadzonej ma
rekord we właściwym secie, w obu stanach obu przełączników uczelni.
