# Eksport CERIF-XML / OpenAIRE Guidelines for CRIS Managers 1.2.0

Data: 2026-08-03
Gałąź: `feat/cerif-export`
Audyt źródłowy: `AUDYT-EUROCRIS-2026-08-03.md`

## Cel

Wystawić z BPP endpoint OAI-PMH zgodny z **OpenAIRE Guidelines for CRIS
Managers 1.2.0**, przechodzący `openaire-cris-validator`, umożliwiający
rejestrację instalacji w DRIS i OpenAIRE Provide.

## Zakres — wariant A („minimum przechodzące walidator")

W zakresie:

- serializacja CERIF-XML encji `Publication`, `Person`, `OrgUnit`, `Patent`,
  `Event`, `Service`;
- warstwa OAI-PMH: sześć czasowników, dziewięć setów, resumption tokeny;
- mapowania słowników kontrolowanych (COAR, SPDX/CC, BCP 47);
- pola `ror_id` na `Jednostka` i `Uczelnia`;
- przełączniki włączania/wyłączania `/api/v1/` oraz eksportu CERIF na
  `Uczelnia`.

Poza zakresem (świadomie, do osobnych specyfikacji):

- rozbudowa `Grant` do pełnej encji `Project` — set `openaire_cris_projects`
  pozostaje pusty;
- encja `Funding` — set `openaire_cris_funding` pozostaje pusty;
- encje `Product` i `Equipment` — sety puste;
- nagrobki dla skasowanych rekordów (`deletedRecord=no`);
- modyfikacje `src/bpp/views/oai.py` i feedu `oai_dc` do Primo.

Puste sety są zgodne z profilem — wytyczne wymagają, by dziewięć setów
istniało, nie by były zapełnione.

## Zależność: `fix/oai-identyfikator-repozytorium`

Ta gałąź naprawia zaszytą domenę `bpp.umlub.pl` w `src/bpp/views/oai.py`
(feed do Primo) i wprowadza na `Uczelnia`:

```python
oai_identyfikator_repozytorium = models.CharField(
    "Identyfikator repozytorium OAI-PMH",
    max_length=255, blank=True, default="",
)

def oai_repository_identifier(self):
    return self.oai_identyfikator_repozytorium.strip() or self.site.domain
```

Eksport CERIF **konsumuje** `oai_repository_identifier()` i nie definiuje
własnego mechanizmu. Ponieważ tamta gałąź zawiera na razie sam dokument,
niniejsza implementuje pole i metodę **verbatim wg jej specyfikacji**. Przy
scaleniu obu gałęzi konflikt sprowadza się do usunięcia duplikatu.

Podział własności: `fix/oai-identyfikator-repozytorium` → `views/oai.py`
i Primo. `feat/cerif-export` → nowy endpoint CERIF.

## Architektura

Nowa aplikacja `src/cerif_export/`, rejestrowana w `INSTALLED_APPS` obok
`crossref_bpp` / `dspace_api`.

```
src/cerif_export/
    const.py              namespace 1.2, nazwy setów, metadataPrefix
    identyfikatory.py     oai:{namespace}:{Typ}/{slug}-{pk} ↔ (model, pk)
    providers/
        base.py           ProviderEncji
        publikacje.py osoby.py jednostki.py patenty.py konferencje.py puste.py
    cerif/
        wspolne.py        string wielojęzyczny, DisplayName, identyfikatory
        publication.py person.py orgunit.py patent.py event.py service.py
    slowniki/
        coar.py dostep.py licencje.py jezyki.py
    oai/
        czasowniki.py tokeny.py bledy.py
    views.py urls.py
    management/commands/cerif_raport_mapowan.py
    migrations/ tests/
```

Nazewnictwo jest celowo mieszane: `providers/` po polsku (dotyka domeny BPP),
`cerif/` po angielsku (moduły odwzorowują 1:1 encje specyfikacji, więc droga
od komunikatu walidatora do pliku jest bezpośrednia).

### Kontrakty warstw

| Komponent | Odpowiedzialność | Czego nie wolno mu znać |
|---|---|---|
| `providers/` | strony obiektów ORM, scope do uczelni, pełny `prefetch_related`, predykat bramkowania | XML, OAI, HTTP |
| `cerif/` | obiekt → `lxml.etree.Element`; funkcje czyste | baza (żaden lazy-load), request |
| `slowniki/` | mapowania na słowniki kontrolowane | wszystko inne |
| `oai/` | czasowniki, sety, tokeny, błędy protokołu | semantyka CERIF |
| `views.py` | adapter HTTP, rozstrzygnięcie tenanta | reszta |

**Serializer nie dotyka bazy.** Naruszenie tej reguły zamienia pełny harvest
w N+1 przy setkach tysięcy rekordów. Komplet danych zapewnia provider i to on
jest testowany na liczbę zapytań.

### Przepływ

```
request → views → oai/czasowniki → provider (strona keyset)
        → cerif/* (per obiekt) → lxml → HttpResponse
```

## Model danych — zmiany

Wszystkie addytywne. Migracje w aplikacji `bpp` (pola na istniejących
modelach) — po ich dodaniu wymagany `make baseline-update`.

| Model | Pole | Typ | Default | Źródło wartości |
|---|---|---|---|---|
| `Charakter_Formalny` | `coar_type` | `CharField(200, blank)` | `""` | ręczne mapowanie |
| `Rodzaj_Prawa_Patentowego` | `coar_type` | `CharField(200, blank)` | `""` | ręczne mapowanie |
| `Jezyk` | `kod_bcp47` | `CharField(35, blank)` | `""` | migracja danych + ręczne |
| `Licencja_OpenAccess` | `uri` | `URLField(blank)` | `""` | migracja danych (CC) + ręczne |
| `Tryb_OpenAccess_Wydawnictwo_Ciagle` | `coar_access_right` | `CharField(200, blank)` | `""` | ręczne (4 wartości) |
| `Tryb_OpenAccess_Wydawnictwo_Zwarte` | `coar_access_right` | `CharField(200, blank)` | `""` | ręczne (4 wartości) |
| `Jednostka` | `ror_id` | `CharField(64, blank)` | `""` | ręcznie |
| `Uczelnia` | `ror_id` | `CharField(64, blank)` | `""` | ręcznie |
| `Uczelnia` | `oai_identyfikator_repozytorium` | `CharField(255, blank)` | `""` | patrz zależność wyżej |
| `Uczelnia` | `api_v1_wlaczone` | `BooleanField` | **`True`** | — |
| `Uczelnia` | `eksport_cerif_wlaczony` | `BooleanField` | **`True`** | — |
| `Ukryj_Status_Korekty` | `cerif` | `BooleanField` | `True` | — |

Migracje danych:

- `Jezyk.kod_bcp47` — z `skrot_crossref` (`en`/`es`/`pl`), gdzie puste,
  z `skrot` jeśli pasuje do `^[a-z]{2,3}$`.
- `Licencja_OpenAccess.uri` — dla `skrot` zaczynającego się od `CC-`
  złożyć `https://creativecommons.org/licenses/{reszta}/4.0/`; reszta pusta.

Wszystkie pola trafiają do odpowiednich klas admina.

## Identyfikatory

Format: `oai:{namespace}:{Typ}/{slug}-{pk}`, gdzie `namespace` pochodzi
z `Uczelnia.oai_repository_identifier()`.

| Set | Model źródłowy | Slug | Przykład |
|---|---|---|---|
| `openaire_cris_publications` | `Wydawnictwo_Ciagle` | `wc` | `Publications/wc-1234` |
| | `Wydawnictwo_Zwarte` | `wz` | |
| | `Praca_Doktorska` | `pd` | |
| | `Praca_Habilitacyjna` | `ph` | |
| | `Zrodlo` (kanał wydawniczy) | `zr` | |
| `openaire_cris_persons` | `Autor` | `au` | `Persons/au-1234` |
| `openaire_cris_orgunits` | `Jednostka` | `je` | `OrgUnits/je-1234` |
| | `Uczelnia` | `uc` | |
| `openaire_cris_patents` | `Patent` | `pt` | `Patents/pt-1234` |
| `openaire_cris_events` | `Konferencja` | `kf` | `Events/kf-1234` |

**Rejestr slugów, nie `content_type_id`.** `ContentType.pk` jest nadawany
przez bazę i różni się między instalacjami; wpuszczony do trwałego,
publicznego identyfikatora spowodowałby, że po odtworzeniu bazy z baseline'u
OpenAIRE zobaczy duplikat całego korpusu jako „nowe" rekordy.

`identyfikatory.py` eksportuje:

```python
SLUGI: dict[type[models.Model], tuple[str, str]]   # model → (typ_cerif, slug)

def zbuduj(namespace: str, obj) -> str
def rozbierz(oai_id: str) -> tuple[str, type[models.Model], int]
    # zwraca (namespace, model, pk); podnosi BledneIdentyfikatory
```

`rozbierz` **nie używa `assert`** — pod `python -O` asserty znikają.
Niepoprawny identyfikator daje wyjątek mapowany na `idDoesNotExist`.

## Sety i providery

`providers/base.py`:

```python
class ProviderEncji:
    set_spec: str
    typ_cerif: str

    def queryset(self, uczelnia) -> QuerySet: ...
    def strona(self, uczelnia, od=None, do=None, kursor=None, rozmiar=100)
        -> tuple[list, Kursor | None]: ...
    def pojedynczy(self, uczelnia, pk): ...
    def najstarszy_datestamp(self, uczelnia): ...
    def widoczny(self, uczelnia, obj) -> bool: ...
```

**`widoczny()` jest jedynym źródłem prawdy o bramkowaniu.** Serializery
i sprawdzanie integralności referencyjnej wołają tę samą metodę. Kopiowanie
predykatu jest zabronione — rozjazd między providerem a serializerem
produkuje dokładnie te błędy walidatora, których nie widać w testach
jednostkowych.

Provider publikacji **musi wykluczyć patenty**. Widok `bpp_rekord`
(`src/bpp/migrations/0001_widoki_rekord.sql:320`) unionuje
`wydawnictwo_ciagle`, `wydawnictwo_zwarte`, **`patent`**, `praca_doktorska`
i `praca_habilitacyjna`. Bez wykluczenia ten sam obiekt trafiłby do dwóch
setów pod dwoma identyfikatorami.

Sortowanie keyset po `(COALESCE(ostatnio_zmieniony, epoka), pk)`.
`ostatnio_zmieniony` jest `null=True` (`ModelZAdnotacjami`), więc bez
`COALESCE` rekordy z NULL-em wypadłyby z paginacji i nie trafiły do harvestu.

`providers/puste.py` dostarcza providera zwracającego zawsze zero rekordów —
obsługuje sety `products`, `equipment`, `projects`, `funding`.

## Serializery CERIF

Sygnatura jednolita:

```python
def serializuj(obj, ctx: KontekstSerializacji) -> lxml.etree.Element
```

`KontekstSerializacji` niesie `namespace`, `uczelnia` i callback
`czy_widoczny(obj) -> bool`. Nic poza tym — w szczególności nie request.

### Publication

Pola wg profilu; `Type` jest **obowiązkowe**. Mapowanie z audytu:
`tytul_oryginalny` + `Wydawnictwo_*_Tytul` → `Title` (wielojęzyczny),
`wydawnictwo_nadrzedne` → `PartOf`, `zrodlo` → `PublishedIn`,
`rok` → `PublicationDate`, `doi`/`pmc_id`/`issn`/`isbn`/`www` →
odpowiednie `FederatedIdentifier`, `BazaModeluOdpowiedzialnosciAutorow` →
`Authors/Author` + `Affiliation` (kolejność wg `kolejnosc`),
`typ_odpowiedzialnosci.typ_ogolny == TO_REDAKTOR` → `Editors/Editor`,
`slowa_kluczowe` → `Keyword`, `streszczenia` → `Abstract`,
`konferencja` → `PresentedAt`, `Element_Repozytorium` → `FileLocations`.

`Volume`, `Issue`, `StartPage`/`EndPage`: **`Rekord` zeruje `tom`,
`nr_zeszytu` i `strony`** (`src/bpp/models/cache/rekord.py:258-260`),
więc provider musi dostarczyć obiekt konkretny, nie wiersz cache'u.
`strony` to jedno pole tekstowe — rozbicie na `StartPage`/`EndPage`
przez wyrażenie `^\s*(\d+)\s*[-–]\s*(\d+)\s*$`; gdy nie pasuje, oba
elementy są pomijane (nie zgadujemy).

`Zrodlo` serializowane jako `Publication` typu *journal*
(`http://purl.org/coar/resource_type/c_0640`) — to jest kanał wydawniczy
wskazywany przez `PublishedIn`.

### Person

`nazwisko`/`imiona` → `PersonName`, `plec` → `Gender` (`m`/`f`),
`orcid` → `ORCID`, `pbn_uid` → `Identifier`, `email`/`www` →
`ElectronicAddress`, `Autor_Jednostka` → `Affiliation`.

### OrgUnit

`nazwa`/`skrot` → `Name`/`Acronym`, `ror_id` → `RORID`,
`Jednostka_Rodzic` → `PartOf`, `pbn_uid` → `Identifier`.

### Patent

`rodzaj_prawa.coar_type` → `Type` (obowiązkowe),
`tytul_oryginalny` → `Title`, `data_zgloszenia` → `RegistrationDate`,
`data_decyzji` → `ApprovalDate`, `numer_prawa_wylacznego` →
`PatentNumber`, `Patent_Autor` → `Inventors/Inventor`.

### Event

`nazwa`/`skrocona_nazwa` → `Name`/`Acronym`, `miasto` → `Place`,
`panstwo` → `Country`, `rozpoczecie`/`zakonczenie` → `StartDate`/`EndDate`.

### Service

Jeden rekord opisujący CRIS, składany z `Uczelnia` i `Site`:
`Acronym`, `Name`, `WebsiteURL`, `OAIPMHBaseURL`, `Owner` (→ `OrgUnit`
uczelni). Zwracany w `<description>` odpowiedzi `Identify`.

## Słowniki

`slowniki/coar.py` — stałe URI dla całego poddrzewa COAR `text` oraz
`patent`, plus walidacja, że wartość z `coar_type` należy do słownika.

**Fallback dla niezmapowanego typu:** korzeń hierarchii —
`http://purl.org/coar/resource_type/c_18cf` (`text`) dla publikacji,
`.../c_15cd` (`patent`) dla patentów. Oba są legalne, więc walidator
przechodzi, a rekord nie znika po cichu z eksportu. Alternatywa (pomijanie)
cicho gubiłaby publikacje z bibliografii.

**Praca habilitacyjna** → `thesis` (`c_46ec`). COAR nie zna habilitacji;
`doctoral thesis` byłoby bliższe praktyce, ale formalnie nieprawdziwe.

`slowniki/dostep.py` — cztery COAR Access Rights.
`slowniki/licencje.py` — odczyt `Licencja_OpenAccess.uri`.
`slowniki/jezyki.py` — odczyt `Jezyk.kod_bcp47`.

Komenda `cerif_raport_mapowan` listuje wartości słownikowe bez mapowania,
żeby redakcja miała co uzupełniać.

## Warstwa OAI-PMH

Sześć czasowników: `Identify` (z rekordem `Service`),
`ListMetadataFormats`, `ListSets`, `ListIdentifiers`, `ListRecords`,
`GetRecord`.

`metadataPrefix`: `oai_cerif_openaire`.
Namespace ładunku: `https://www.openaire.eu/cerif-profile/1.2/`.

Sety: `openaire_cris_publications`, `openaire_cris_products`,
`openaire_cris_patents`, `openaire_cris_persons`, `openaire_cris_orgunits`,
`openaire_cris_projects`, `openaire_cris_funding`, `openaire_cris_events`,
`openaire_cris_equipments`.

### Resumption tokeny

Keyset, nie offset. Ładunek podpisany `django.core.signing` z TTL:

```python
{"set": str, "prefix": str, "od": str|None, "do": str|None,
 "ts": str, "pk": int}
```

Podpis jest wymagany — bez niego token jest wektorem wstrzykiwania
parametrów zapytania. Keyset zamiast `[offset:offset+n]` daje stały koszt
strony i stabilność przy zapisach w trakcie harvestu; przy offsecie edycja
rekordu w połowie przebiegu przesuwa okno i gubi albo dubluje pozycje.

Rozmiar strony: 100. Token wygasły lub z niepoprawnym podpisem →
`badResumptionToken`.

### Integralność referencyjna

Serializer emituje `id` osadzonej encji sąsiadującej **tylko wtedy, gdy ta
encja wyjdzie w swoim secie przy tej samej konfiguracji bramek** — czyli gdy
`ctx.czy_widoczny(obj)` zwraca prawdę. W przeciwnym razie osadza ją bez `id`;
profil pozwala na to wprost („embedded entities without internal identifiers
are permitted").

Przypadek referencyjny: autor z `pokazuj=False` afiliowany przy publikacji —
publikacja wychodzi, ale `Person/@id` pojawić się nie może, bo wskazywałby na
nieistniejący rekord.

## Bramkowanie i przełączniki

| Warstwa | Mechanizm | Default |
|---|---|---|
| Endpoint CERIF | `Uczelnia.eksport_cerif_wlaczony` → 404 gdy `False` | włączony |
| Endpoint `/api/v1/` | `Uczelnia.api_v1_wlaczone` → 404 gdy `False` | włączony |
| Status korekty | `uczelnia.ukryte_statusy("cerif")` — kanał niezależny od `api` | — |
| Per rekord | `nie_eksportuj_przez_api` | respektowany |
| Osoby | `Autor.pokazuj` | respektowany |
| Tenant | `scope_rekord_do_uczelni` | — |

Oba przełączniki są **domyślnie włączone** — istniejące wdrożenia nie zmieniają
zachowania `/api/v1/`, a CERIF startuje aktywny.

Ponieważ set `openaire_cris_persons` jest domyślnie aktywny, jedynym
zabezpieczeniem danych osobowych pozostaje `Autor.pokazuj`. Ten predykat musi
działać bezbłędnie i ma dedykowany test wycieku (patrz niżej).

Respektowanie `nie_eksportuj_przez_api` jest interpretacją: jego `help_text`
mówi o „JSON REST API", ale intencja czytana jest jako „ten rekord nie
wychodzi na zewnątrz".

Wyłączenie `/api/v1/` realizowane jest w `api_v1` przez klasę uprawnień
sprawdzającą flagę na `Uczelnia` rozstrzygniętej z requestu, spójnie
z istniejącym `src/api_v1/permissions.py`.

## Obsługa błędów

Błędy protokołu (`badVerb`, `badArgument`, `cannotDisseminateFormat`,
`idDoesNotExist`, `noRecordsMatch`, `badResumptionToken`) zwracane jako XML
z HTTP 200 — tak wymaga OAI-PMH.

Wyjątek przy serializacji pojedynczego rekordu: `rollbar.report_exc_info()`,
rekord pominięty, licznik pominięć w logu. Nigdy `except: pass`, nigdy
wywalenie całego harvestu przez jeden zepsuty wiersz. W testach ten sam kod
ma podnosić wyjątek — przełącznik przez ustawienie
`CERIF_EXPORT_PRZERYWAJ_NA_BLEDZIE`, domyślnie `False`, w testach `True`.

## Testy

| Poziom | Zakres |
|---|---|
| Serializery | snapshoty XML per encja; walidacja względem XSD profilu 1.2 |
| Providery | `django_assert_max_num_queries` (wzorzec z `test_oai.py`) |
| Identyfikatory | round-trip `zbuduj`/`rozbierz`; błędne wejścia → wyjątek, nie `assert` |
| Tokeny | round-trip, wygaśnięcie, zerwany podpis |
| Bramkowanie | test per warstwa |
| **Wyciek osób** | autor z `pokazuj=False` nie pojawia się w secie persons **ani** jako `Person/@id` w publikacji |
| Integralność | harvest wszystkich setów → zebrać `id` z powiązań → każde musi mieć rekord |
| Regresja Primo | `/oai/` z `oai_dc` odpowiada identycznie jak przed zmianą |
| E2E | `openaire-cris-validator` jako `make cerif-validate`, poza domyślną suitą (wymaga JVM) |

Konwencja pytest wg `CLAUDE.md`: funkcje bez klas, `@pytest.mark.django_db`,
`model_bakery.baker.make`.

## Podział na równoległe zadania

Faza 0 (szeregowo): scaffold aplikacji, `const.py`, `identyfikatory.py`,
`providers/base.py` (sygnatury), migracje modeli. Ustala kontrakty, przeciw
którym kodują pozostali.

Faza 1 (równolegle, rozłączne katalogi):

| Agent | Katalog | Zależy od |
|---|---|---|
| A | `slowniki/` + `management/commands/` | const |
| B | `providers/` | base, identyfikatory |
| C | `cerif/` | const, słowniki (interfejs) |
| D | `oai/` | const, providers (interfejs) |
| E | przełączniki `/api/v1/` + `Uczelnia` (aplikacja `api_v1`) | migracje |

Faza 2 (szeregowo): `views.py`/`urls.py`, testy integracyjne,
`make baseline-update`, newsfragment towncriera.

## Newsfragment

`src/bpp/newsfragments/cerif-export.feature.rst` — eksport CERIF-XML zgodny
z OpenAIRE Guidelines for CRIS Managers 1.2.0 oraz przełączniki włączania
API i eksportu CERIF na obiekcie Uczelnia.
