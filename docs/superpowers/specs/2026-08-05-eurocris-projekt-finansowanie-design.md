# euroCRIS: encje Projekt i Finansowanie — projekt techniczny

Data: 2026-08-05
Issues: [#701](https://github.com/iplweb/bpp/issues/701) (Project),
[#702](https://github.com/iplweb/bpp/issues/702) (Funding),
parasol [#709](https://github.com/iplweb/bpp/issues/709)
Kontekst merytoryczny: `docs/deweloper/eurocris-co-jeszcze.md`, sekcje A1 i A2

## Problem

Eksport CERIF-XML (`/cerif-oai/`, app `src/cerif_export/`) przechodzi
`openaire-cris-validator` 2.1.1 w całości, ale sety `openaire_cris_projects`
i `openaire_cris_funding` są **puste** — obsługuje je `ProviderPusty`.
Profil OpenAIRE wymaga istnienia setów, nie ich zapełnienia, więc formalna
zgodność jest osiągnięta, a merytorycznie brakuje najważniejszego, co CRIS
ma do pokazania: łańcucha **publikacja ↔ projekt ↔ finansowanie**.

Przyczyna leży w modelu danych, nie w eksporcie. `bpp.models.grant.Grant`
ma cztery pola (`nazwa_projektu`, `zrodlo_finansowania` jako wolny tekst,
`numer_projektu`, `rok`) — to etykieta numeru grantu przypinana do
publikacji, nie encja projektu. Encja finansującego nie istnieje w ogóle.

## Zakres

**W zakresie:** modele danych w `bpp`, admin (wprowadzanie danych przez
redakcję), migracje ze seedem grantodawców, providery i serializery CERIF
dla setów Projects i Funding, rozszerzenie setu OrgUnits o instytucje
finansujące.

**Poza zakresem** (świadomie, do ewentualnej osobnej iteracji):

- widok publiczny projektów na froncie BPP (lista, podstrona projektu,
  projekty na stronie autora/jednostki),
- endpointy `/api/v1/` dla projektów i finansowania,
- instytucje zewnętrzne jako partnerzy/wykonawcy projektu (BPP nie ma dziś
  encji instytucji zewnętrznej; `Consortium/Coordinator` obsługujemy
  jednostką własną),
- encje `Product` (#703) i `Equipment` (#704) — inne sety, inne issues.

## Zależność od gałęzi

Warstwa eksportu siada na `feat/cerif-mapowania` (PR #700), która wnosi
`cerif_export`, walidację ROR w `bpp/util/ror.py` oraz przełącznik
`Uczelnia.eksport_cerif_osoby`. Gałąź robocza: `feat/eurocris-projekty`,
odbita od `feat/cerif-mapowania`.

## Źródło prawdy o formacie

**XSD profilu leży w repozytorium**:
`src/cerif_export/tests/xsd/openaire-cerif-profile.xsd` wraz z
`includes/` i `vocabularies/`. Wszystkie mapowania w tym dokumencie są
z nim skonfrontowane — przy wątpliwościach czytamy XSD, nie dokumentację
OpenAIRE z pamięci.

## Decyzje projektowe

| Decyzja | Wybór | Uzasadnienie |
|---|---|---|
| Los modelu `Grant` | Nowy model `Projekt`; `Grant` zostaje etykietą numeru grantu z FK do projektu | Nie rusza istniejących danych ani inline'ów w adminach publikacji |
| Zasięg UI | Admin + eksport CERIF | Minimalny zakres domykający #701/#702 |
| Słownik grantodawców | Nowy model + seed polskich instytucji z prawdziwymi identyfikatorami | Bez FundRef ID `Funding` jest w OpenAIRE prawie bezużyteczny |
| Osoby w projekcie | Jedna relacja `Projekt_Autor` z rolą | CERIF wyraża PI jako rolę w `Team/PrincipalInvestigator` vs `Team/Member` |
| Finansowanie | Osobny model 1:N od projektu | Obsługuje projekty współfinansowane; mapuje się 1:1 na `<Funding>` |
| Kwoty | Zapisywane zawsze, eksportowane warunkowo | Przełącznik `Uczelnia.eksport_cerif_kwoty` (domyślnie wyłączony), wzorem `eksport_cerif_osoby` |
| Instytucje w projekcie | Tylko jednostka wiodąca | YAGNI: partnerzy zewnętrzni wymagaliby nowej encji |
| Tenant projektu | Przez **wymagane** `Projekt.jednostka` | Scoping idzie `jednostka__uczelnia`, wzorem `providers/publikacje.py`; nullable pole po cichu wypychałoby projekty z eksportu |
| Eksport funderów | Tylko ci realnie finansujący projekty uczelni | Seed nie ma wypychać instytucji niezwiązanych z uczelnią |

## Ścieżka danych publikacja → projekt

```
Wydawnictwo_* / Patent → Grant_Rekordu (GenericFK) → Grant → Projekt → Finansowanie → Instytucja_Finansujaca
```

`Grant_Rekordu` **nie wymaga zmian po stronie modelu** — po dodaniu
`Grant.projekt` niesie już relację publikacja↔projekt. Publikacje, których
grant nie ma przypisanego projektu, nie wnoszą powiązania i nie łamią
eksportu.

Po stronie **eksportu** relacja wymaga jednak osobnej roboty, i to ona
decyduje o wartości całego przedsięwzięcia. Profil łączy publikację
z projektem elementem **`Publication/OriginatesFrom`** (XSD, linia 698);
analogiczny element ma `Patent` (linia 871). `OriginatesFrom` **osadza**
pełny element z grupy podstawień `ProjectFunding__SubstitutionGroupHead`
(czyli całe `<Project>` albo `<Funding>`), nie samą referencję;
`minOccurs="0"`, `maxOccurs="unbounded"`.

Dziś `cerif/publication.py` i `cerif/patent.py` nie wiedzą nic o grantach.
Bez dopisania `OriginatesFrom` sety projektów i finansowania byłyby pełne,
walidator zielony, a agregator dostałby **dwie rozłączne listy** — osobno
publikacje, osobno projekty. Czyli dokładnie brak tego, po co powstało
issue #709.

## Modele danych (`src/bpp/models/projekt.py`)

Nowy moduł musi zostać dopisany do `src/bpp/models/__init__.py`
(konwencja `from .projekt import *  # noqa`).

Wszystkie nowe modele eksportowane przez OAI-PMH dziedziczą po
`ModelZAdnotacjami` (`src/bpp/models/abstract/metadata.py:11`) — daje
`ostatnio_zmieniony` (auto_now, null=True, db_index) oraz `adnotacje`.
Na `ostatnio_zmieniony` `cerif_export/providers/base.py` buduje keysetowy
kursor przyrostowego harvestu (`z_datestampem()`); model bez tego pola nie
da się harvestować przyrostowo.

### `Projekt`

Dziedziczy `ModelZAdnotacjami` oraz `ModelZeSlowamiKluczowymi`
(`src/bpp/models/abstract/keywords.py`; taggit z domyślnym generic-through,
współdzielony już przez `Patent` i oba `Wydawnictwo_*` — nowy model nie
wymaga własnego through-modelu).

| Pole | Typ | Element CERIF |
|---|---|---|
| `tytul` | `TextField` | `Title` (pl) |
| `tytul_en` | `TextField(blank=True, default="")` | `Title` (en) |
| `akronim` | `CharField(max_length=50, blank=True, default="")` | `Acronym` |
| `data_rozpoczecia` | `DateField(null=True, blank=True)` | `StartDate` |
| `data_zakonczenia` | `DateField(null=True, blank=True)` | `EndDate` |
| `status` | `CharField` z `choices` | `Status` (z własnym `scheme`) |
| `abstrakt` | `TextField(blank=True, default="")` | `Abstract` (pl) |
| `abstrakt_en` | `TextField(blank=True, default="")` | `Abstract` (en) |
| `slowa_kluczowe`, `slowa_kluczowe_eng` | z miksina | `Keyword` |
| `dyscypliny` | `M2M(Dyscyplina_Naukowa, blank=True)` | `Subject` (z własnym `scheme`) |
| `jednostka` | `FK(Jednostka, PROTECT)` — **wymagane** | `Consortium/Coordinator` |
| `strona_www` | `URLField(blank=True, default="")` | — (brak elementu w profilu) |

Wartości `status`: planowany / w trakcie / zakończony / przerwany.

`jednostka` jest wymagana, bo jest jedynym nośnikiem przynależności
projektu do uczelni (tenanta). Bez niej provider nie ma po czym filtrować.

`strona_www` zostaje jako pole wewnętrzne — sekwencja `Project` w XSD
(linie 238–450) nie zawiera ani `URI`, ani `ElectronicAddress`.

### `Projekt_Autor`

| Pole | Typ |
|---|---|
| `projekt` | `FK(Projekt, CASCADE)` |
| `autor` | `FK(Autor, PROTECT)` |
| `rola` | `CharField` z `choices`: kierownik / wykonawca / współwykonawca |
| `od`, `do` | `DateField(null=True, blank=True)` |

`unique_together = [("projekt", "autor", "rola")]`.

Dodatkowo warunkowy `UniqueConstraint(fields=["projekt"],
condition=Q(rola="kierownik"), name="...")` — wymusza jednego kierownika
na poziomie bazy. Sam `clean()` tego nie złapie, bo przy dwóch nowych
wierszach w inline widzi tylko stan z bazy; walidacja formsetu w adminie
jest dodatkiem dla czytelnego komunikatu, nie zabezpieczeniem.

Mapowanie: rola `kierownik` → `Team/PrincipalInvestigator`, pozostałe →
`Team/Member`.

### `Instytucja_Finansujaca`

Dziedziczy `ModelZAdnotacjami` — jest eksportowana jako OrgUnit, więc
potrzebuje datestampu.

| Pole | Typ | Uwagi |
|---|---|---|
| `nazwa` | `TextField` | `Name` |
| `nazwa_en` | `TextField(blank=True, default="")` | `Name` (en) |
| `akronim` | `CharField(max_length=50, blank=True, default="")` | `Acronym` |
| `kraj` | `CharField(max_length=2, default="PL")` | pole wewnętrzne — profil nie ma `Country` w OrgUnit |
| `ror_id` | `CharField(blank=True, default="")` | → `RORID` |
| `fundref_id` | `CharField(blank=True, default="")` | → `FundRefID` |
| `strona_www` | `URLField(blank=True, default="")` | → `ElectronicAddress` |

`RORID` i `FundRefID` to **dedykowane elementy** w
`includes/orgunit-identifiers.xsd`, nie generyczne `Identifier`.
Walidacja `ror_id` — walidatorem z `bpp/util/ror.py`.

### `Finansowanie`

Dziedziczy `ModelZAdnotacjami`.

| Pole | Typ | Element CERIF |
|---|---|---|
| `projekt` | `FK(Projekt, CASCADE)` | patrz niżej |
| `typ` | `CharField` z `choices`, **wymagany** | `Funding/Type` |
| `instytucja` | `FK(Instytucja_Finansujaca, PROTECT)` | `Funding/Funder` → OrgUnit |
| `nazwa_programu` | `CharField(blank=True, default="")` | `Funding/Name` — np. „OPUS 24" |
| `numer_umowy` | `CharField(blank=True, default="")` | `Funding/Identifier` |
| `kwota` | `DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)` | `Funding/Amount` |
| `waluta` | `CharField(max_length=3, default="PLN")` | atrybut `currency` |
| `grant_doi` | `CharField(blank=True, default="")` | `GrantDOI` (dedykowany element) |

Wartości `typ` — słownik jest **lokalnie w repo**:
`src/cerif_export/tests/xsd/vocabularies/openaire_funding_types.xsd`,
osiem wartości: FundingProgramme, Call, Tender, Gift, InternalFunding,
Contract, Award, Grant.

### Zmiany w istniejących modelach

- `Grant.projekt = FK(Projekt, SET_NULL, null=True, blank=True)` —
  `SET_NULL`, bo skasowanie projektu nie może kasować historycznych numerów
  grantów przypiętych do publikacji.
- `Uczelnia.eksport_cerif_kwoty = BooleanField(default=False)`.

### Walidacja (`clean()` na modelu)

Na modelu, bo dane mogą wejść także importem lub skryptem:

- `data_zakonczenia >= data_rozpoczecia`,
- `kwota` wypełniona ⇒ `waluta` wymagana.

Jeden kierownik na projekt — przez `UniqueConstraint` (patrz wyżej).

## Uprawnienia

Mechanizm jest ustalony: `src/bpp/system.py`, dict pod kluczem
`GR_WPROWADZANIE_DANYCH` (linie 159 i 219), wywoływany przez
`odtworz_grupy()` podpięte pod `post_migrate` w `src/bpp/apps.py:17`
(plus komenda `odtworz_grupy`). `Grant` i `Grant_Rekordu` już tam są —
dopisać `Projekt`, `Projekt_Autor`, `Instytucja_Finansujaca`,
`Finansowanie`.

## Admin (`src/bpp/admin/projekt.py`)

Wpięcie przez jawny import w `src/bpp/admin/__init__.py`
(`from .projekt import ProjektAdmin  # noqa`).

- **`ProjektAdmin`** — `list_display`: tytuł, akronim, status, daty,
  jednostka, liczba finansowań. `list_filter`: status, jednostka,
  dyscypliny. `search_fields`: tytuł, akronim, abstrakt.
  `autocomplete_fields = ["jednostka"]`. Inline'y:
  - `Projekt_AutorInline` (`TabularInline`, `autocomplete_fields=["autor"]`,
    walidacja formsetu na jednego kierownika),
  - `FinansowanieInline` (`TabularInline`, `autocomplete_fields=["instytucja"]`).
- **`Instytucja_FinansujacaAdmin`** — słownik. `search_fields` jest
  **wymagane**, inaczej autocomplete w `FinansowanieInline` nie zadziała.
  Walidacja `ror_id` walidatorem z `bpp/util/ror.py`; walidacja formatu
  `fundref_id`.
- **`GrantAdmin`** — dołożyć `projekt` do `list_display`,
  `autocomplete_fields` oraz filtr `projekt__isnull` („granty bez projektu"
  to robocza lista redakcji przy uzupełnianiu danych historycznych).
- **`UczelniaAdmin`** — `eksport_cerif_kwoty` do fieldsetu, w którym siedzi
  `eksport_cerif_osoby` (`src/bpp/admin/uczelnia.py:174`).

## Warstwa eksportu (`src/cerif_export/`)

Architektura bez zmian: **provider** (dostęp do danych, nie wie nic o XML)
→ **serializer w `cerif/`** → **`slowniki/`** (mapowania na słowniki
kontrolowane).

### Nowe pliki

- `slowniki/typy_finansowania.py` — `Finansowanie.typ` → URI ze słownika
  OpenAIRE Funding Types (plik XSD w repo, patrz wyżej). Wzorzec:
  `slowniki/coar.py`.
- `cerif/project.py` — builder `<Project>` w kolejności z XSD: `Type`,
  `Acronym`, `Title`, `Identifier`, `StartDate`, `EndDate`, `Consortium`
  (→ `Coordinator` = OrgUnit jednostki), `Team` (→ `PrincipalInvestigator`
  / `Member`), `Funded` (→ `By` = OrgUnit findera, `As` = osadzone
  `<Funding>`), `Subject`, `Keyword`, `Abstract`, `Status`.
- `cerif/funding.py` — builder `<Funding>`: identyfikator, `Type`
  (obowiązkowy), `Name`/`Acronym`, `Amount` + `currency` (tylko gdy
  `Uczelnia.eksport_cerif_kwoty`), `GrantDOI`, `Funder` → OrgUnit.
  Builder musi być **wywoływalny w dwóch kontekstach**: jako samodzielny
  rekord setu `openaire_cris_funding` i jako element osadzony w
  `Project/Funded/As`.
- `providers/projekty.py`, `providers/finansowanie.py` — realne providery
  (`ProviderEncji`) zamiast `ProviderPusty`.

### Struktura `Funded` — źródło pomyłek

XSD (linie 348–372) definiuje `Project/Funded` jako parę:

- `Funded/By` → `cfLinkWithDisplayNameToPersonOrOrgUnit__Type`, czyli
  **referencja do OrgUnit-a findera** (rola Funder),
- `Funded/As` → **osadzony pełny element `<Funding>`** (`<xs:element
  ref="Funding"/>`), nie referencja.

Po stronie samej encji `Funding` finder wchodzi elementem **`Funder`**
(linia 482), nie `FundedBy`.

### Klasyfikacje z własnym schematem

`Status` i `Subject` mają typ `cfGenericURIClassification__Type`
(`cerif-commons.xsd:270`) — wymagają atrybutu `scheme` (anyURI) i wartości
będącej URI. Profil nie dostarcza słownika ani dla statusu projektu, ani
dla polskich dyscyplin naukowych, więc definiujemy **własne schematy**,
jako stałe w `const.py`:

- scheme statusu projektu + URI per wartość,
- scheme dyscyplin (klasyfikacja MNiSW) + URI budowane z kodu dyscypliny.

Agregator nieznanego schematu nie zinterpretuje, ale dane są jawnie
oznaczone swoim pochodzeniem — to lepsze niż ich pominięcie i lepsze niż
podszywanie się pod cudzy słownik.

### Zmiany w istniejących plikach

- `identyfikatory._REJESTR` — trzy wpisy z jawnymi slugami: `bpp.Projekt`
  → `pj`, `bpp.Finansowanie` → `fn`, `bpp.Instytucja_Finansujaca` → `if`
  (typ **OrgUnit**). Slugi wolne i pasują do wzorca `[a-z]{2}`.
- `const.py` — **nie ma** stałych `TYP_PROJECT`/`TYP_FUNDING`, trzeba
  dodać; plus stałe schematów klasyfikacji.
- `providers/jednostki.py` — `modele = [Jednostka, Uczelnia,
  Instytucja_Finansujaca]` plus gałąź w `queryset()`. Paginacja w
  `strona()` obsługuje N modeli bez zmian. Queryset funderów zawężony do
  tych, do których prowadzi `Finansowanie` projektu należącego do tej
  uczelni (przez `projekt__jednostka__uczelnia`).
- `cerif/orgunit.py` — gałąź serializująca findera: `Name`, `Acronym`,
  `RORID`, `FundRefID`, `ElectronicAddress`.
- `providers/puste.py` — zostają tylko `ProviderProduktow`
  i `ProviderAparatury`; docstring modułu wymaga poprawienia (dziś twierdzi,
  że BPP „nie prowadzi ewidencji projektów ani finansowania").
- `cerif/publication.py`, `cerif/patent.py` — element `OriginatesFrom`
  z osadzonym `<Project>` dla każdego grantu publikacji mającego projekt
  (z deduplikacją: dwa granty tego samego projektu na jednej publikacji
  dają jeden element).
- `providers/publikacje.py`, `providers/patenty.py` — prefetch generycznej
  relacji `Grant_Rekordu` wraz z `grant__projekt` i tym, czego wymaga
  serializer projektu. Osadzanie projektu w każdej publikacji to naturalny
  kandydat na N+1 — bez prefetcha liczba zapytań rośnie z liczbą publikacji
  na stronie harvestu.

## Znane odstępstwa od intencji euroCRIS

Świadome, odnotowane, możliwe do poprawienia później:

1. **`Subject` z własnym schematem zamiast Fields of Science.** OpenAIRE
   rozumie taksonomię FOS; dyscypliny MNiSW dałoby się na nią zmapować
   i byłoby to bliżej intencji profilu. Mapowanie to jednak osobna robota
   słownikowa, więc na razie eksportujemy własny schemat — dane są jawnie
   oznaczone pochodzeniem, ale agregator ich nie zinterpretuje.
2. **`Status` projektu bez słownika kontrolowanego.** Profil żadnego nie
   dostarcza; własny schemat jest tu jedyną uczciwą opcją poza pominięciem
   elementu.
3. **Brak `Partner`/`Contractor`.** Wymagałoby encji instytucji
   zewnętrznej, której BPP nie ma. Elementy są w profilu opcjonalne.
4. **`Project/Type` nie jest wypełniany.** `minOccurs="0"`, a BPP nie ma
   danych pozwalających odróżnić projekt badawczy od wdrożeniowego czy
   infrastrukturalnego. Zgadywanie byłoby wpisywaniem nieprawdy.

### Integralność referencyjna a przełącznik osób

`Uczelnia.eksport_cerif_osoby` (default `True`) działa przez
`widoczni_autorzy()` → przy wyłączeniu zwraca `Autor.objects.none()`, co
zeruje set osób oraz `@id`/ORCID/afiliacje osadzone w publikacjach. Jeśli
`<Project>` bezwarunkowo wyemituje `Team`, przy wyłączonym przełączniku
powstaną referencje do identyfikatorów nieobecnych w harveście.
**`Team` podlega temu samemu przełącznikowi**: przy
`eksport_cerif_osoby=False` projekt wychodzi bez `PrincipalInvestigator`
i `Member`.

Analogicznie finder referowany z `Funding/Funder` i `Funded/By` **musi**
być w secie `openaire_cris_orgunits` — stąd rozszerzenie
`ProviderJednostek`, a nie osobny set.

`Funded` ma `minOccurs="0"` — projekt bez finansowania jest wobec XSD
poprawny i **nie** musi być odsiewany przez provider.

## Migracje

1. **Schema:** `Projekt`, `Projekt_Autor`, `Instytucja_Finansujaca`,
   `Finansowanie`, `Grant.projekt`, `Uczelnia.eksport_cerif_kwoty`,
   `UniqueConstraint` na kierownika.
2. **Dane:** seed instytucji finansujących — idempotentny `get_or_create`
   po `fundref_id`, wzorem migracji `0483`. Zakres: NCN, NCBR, MNiSW/MEiN,
   FNP, NAWA, ABM, Komisja Europejska. **Identyfikatory FundRef i ROR
   weryfikowane w rejestrach Crossref i ROR przy pisaniu migracji** — nie
   zgadywane z pamięci. Instytucja bez potwierdzonego identyfikatora
   wchodzi bez niego, nie ze zmyślonym.
3. **Baseline:** `make baseline-update` **raz, przy scalaniu**, nie
   w trakcie prac w gałęzi.

Istniejących migracji nie wolno modyfikować.

## Testy

Konwencja pytest: funkcje bez klas, `@pytest.mark.django_db`,
`model_bakery.baker.make`.

**Model:**
- `clean()` odrzuca `data_zakonczenia < data_rozpoczecia`,
- `clean()` odrzuca kwotę bez waluty,
- `UniqueConstraint` odrzuca drugiego kierownika,
- `Grant.projekt` na `SET_NULL`: skasowanie projektu zostawia grant.

**Provider:**
- scoping do tenanta przez `jednostka__uczelnia` (projekty innej uczelni
  nie wychodzą),
- finder bez powiązanego `Finansowanie` **nie** trafia do setu OrgUnits;
  finder z powiązaniem — trafia,
- przyrostowy harvest: zmiana projektu podnosi `ostatnio_zmieniony`
  i rekord wraca w kolejnym `from`.

**Serializer:**
- `Funding/Type` obecny zawsze,
- `Amount` obecny wtedy i tylko wtedy, gdy `eksport_cerif_kwoty=True`,
- `Funded/As` zawiera **osadzone** `<Funding>`, a `Funded/By` referencję do
  OrgUnit-a,
- projekt bez finansowania serializuje się poprawnie (brak `Funded`),
- walidacja wyniku wobec XSD z `tests/xsd/` — wzorem istniejących testów
  eksportu.

**Integralność referencyjna** (najważniejszy test tej zmiany): dla
wyeksportowanego projektu każdy referowany identyfikator OrgUnit / Person /
Funding istnieje w swoim secie — sprawdzane w obu stanach
`eksport_cerif_osoby`.

**Krok akceptacyjny poza CI:** przebieg `openaire-cris-validator` 2.1.1 na
żywym endpoincie z dumpem produkcyjnym, jak przy #699.

## Podział prac

Etap 1 (sekwencyjny, fundament): modele + migracja schema + wpięcie do
`models/__init__.py` i `system.py`.

Etap 2 (równolegle, po etapie 1):
- admin + walidacja formsetów,
- migracja danych ze seedem grantodawców (z weryfikacją identyfikatorów),
- eksport: `const.py`, `identyfikatory.py`, słownik typów finansowania,
  buildery `cerif/project.py` i `cerif/funding.py`, providery,
  rozszerzenie `providers/jednostki.py` i `cerif/orgunit.py`.

Etap 3 (po etapie 2): `OriginatesFrom` w `cerif/publication.py`
i `cerif/patent.py` wraz z prefetchami w ich providerach — ogniwo, dla
którego całość ma sens.

Etap 4: testy integralności referencyjnej, pełny przebieg testów,
newsfragmenty `src/bpp/newsfragments/701.feature.rst`
i `702.feature.rst`.

Kolejność odwrotna nie ma sensu: eksport bez modelu nie ma czego
serializować.
