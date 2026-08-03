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
- nagrobki dla skasowanych rekordów; `Identify` deklaruje
  `deletedRecord=no`;
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
    const.py              namespace 1.2, nazwy setów, metadataPrefix, epoka
    identyfikatory.py     oai:{namespace}:{Typ}/{slug}-{pk} ↔ (model, pk)
    kontekst.py           KontekstSerializacji, Kursor
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
    migrations/ tests/ tests/xsd/
```

Nazewnictwo jest celowo mieszane: `providers/` po polsku (dotyka domeny BPP),
`cerif/` po angielsku (moduły odwzorowują 1:1 encje specyfikacji, więc droga
od komunikatu walidatora do pliku jest bezpośrednia).

### Kontrakty warstw

| Komponent | Odpowiedzialność | Czego nie wolno mu znać |
|---|---|---|
| `providers/` | strony obiektów ORM, scope do uczelni, pełny `prefetch_related`, wyliczenie zbiorów widoczności | XML, OAI, HTTP |
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

- `Jezyk.kod_bcp47` — z `skrot_crossref` (`en`/`es`/`pl`); gdzie puste,
  z `skrot` jeśli pasuje do `^[a-z]{2,3}$`.
- `Licencja_OpenAccess.uri` — patrz reguły niżej.

### Reguły migracji `Licencja_OpenAccess.uri`

Skróty w bazie są **wielkimi literami** (np. `CC-BY-ND`), a ścieżka
Creative Commons jest małymi. Reguły:

- `skrot == "OTHER"` → pozostaje `""`;
- `skrot in ("CC0", "CC-0")` → `https://creativecommons.org/publicdomain/zero/1.0/`
  (CC0 ma inny schemat URL niż pozostałe licencje);
- `skrot` pasujący do `^CC-([A-Z-]+)$` →
  `https://creativecommons.org/licenses/{grupa.lower()}/4.0/`;
- pozostałe → `""`.

**Wersja `4.0` jest świadomym przybliżeniem** — skrót nie niesie wersji
licencji. Wartości wymagają ręcznego przeglądu przez redakcję; komenda
`cerif_raport_mapowan` listuje je jako wymagające potwierdzenia.

### Zmiany opisów w `Ukryj_Status_Korekty`

Pole `api` ma dziś `help_text` „Dotyczy ukrywania prac w API JSON-REST
**oraz OAI-PMH**" (`src/bpp/models/uczelnia.py:958`). Nowy endpoint CERIF też
jest OAI-PMH, więc bez korekty admin pokaże dwie sprzeczne etykiety. Wymagane:

- `api.help_text` → „Dotyczy ukrywania prac w API JSON-REST oraz OAI-PMH
  dla Primo";
- `cerif.help_text` → „Dotyczy ukrywania prac w eksporcie CERIF/OpenAIRE";
- `Ukryj_Status_Korekty.__str__` — dopisać `api` i `cerif` (dziś pomija
  nawet `api`);
- docstring `Uczelnia.ukryte_statusy` — uzupełnić listę kanałów.

Wszystkie nowe pola trafiają do odpowiednich klas w `src/bpp/admin/`.
`Rodzaj_Prawa_Patentowego` dziedziczy `ModelZNazwa` i **nie ma `skrot`** —
admin i raport mapowań identyfikują wiersze po `nazwa`. Jeśli model nie jest
zarejestrowany w adminie, należy go zarejestrować.

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
MODELE_WG_SLUGU: dict[str, type[models.Model]]     # odwrotność SLUGI

class BlednyIdentyfikator(ValueError): ...

def zbuduj(namespace: str, obj) -> str: ...
def rozbierz(oai_id: str) -> tuple[str, type[models.Model], int]: ...
    # (namespace, model, pk); podnosi BlednyIdentyfikator
```

`rozbierz` **nie używa `assert`** — pod `python -O` asserty znikają.
Niepoprawny identyfikator daje `BlednyIdentyfikator`, mapowany przez warstwę
OAI na `idDoesNotExist`.

## Sety, providery, porządek keyset

### Providery NIE używają `Rekord`

Enumeracja idzie po **pięciu konkretnych modelach**, nie po widoku
`bpp_rekord`. Dwa powody:

1. `Rekord` zeruje `tom`, `nr_zeszytu` i `strony`
   (`src/bpp/models/cache/rekord.py:258-260`), a to są `Volume`, `Issue`
   i `StartPage`/`EndPage` w CERIF.
2. Widok `bpp_rekord` unionuje także `bpp_patent_view`
   (`src/bpp/migrations/0001_widoki_rekord.sql:320`) — patenty są w CERIF
   osobną encją w osobnym secie, więc użycie `Rekord` wymagałoby ich
   wykluczania.

Widok jest tu wyłącznie kontekstem wyjaśniającym, dlaczego go nie używamy.

### Interfejs providera

```python
@dataclass(frozen=True)
class Kursor:
    slug: str        # który model w obrębie setu
    ts: str          # ISO 8601 UTC
    pk: int


class ProviderEncji:
    set_spec: str
    typ_cerif: str
    modele: list[type[models.Model]]   # w porządku wyczerpywania

    def queryset(self, uczelnia, model): ...
    def strona(self, uczelnia, od=None, do=None, kursor=None, rozmiar=100)
        -> tuple[list, Kursor | None]: ...
    def pojedynczy(self, uczelnia, model, pk): ...
    def najstarszy_datestamp(self, uczelnia) -> str: ...
    def zbiory_widocznosci(self, uczelnia, obiekty) -> ZbioryWidocznosci: ...
```

### Porządek keyset

Set `openaire_cris_publications` łączy pięć modeli, a `pk` między nimi
kolidują — para `(ts, pk)` nie jest unikalna. Dlatego:

- modele wyczerpywane są **sekwencyjnie**, w kolejności zadeklarowanej
  w `ProviderEncji.modele` (dla publikacji: `wc`, `wz`, `pd`, `ph`, `zr`);
- w obrębie modelu porządek to `(COALESCE(ostatnio_zmieniony, EPOKA), pk)`;
- `Kursor.slug` mówi, na którym modelu stanęliśmy; wyczerpanie modelu
  przesuwa kursor na kolejny slug z zerowym kursorem wewnętrznym.

`EPOKA = "1970-01-01T00:00:00Z"`. `ostatnio_zmieniony` jest `null=True`
(`ModelZAdnotacjami`, `src/bpp/models/abstract/metadata.py:16`), więc bez
`COALESCE` rekordy z NULL-em wypadłyby z paginacji i nie trafiły do harvestu.
Ta sama wartość idzie w `<datestamp>` nagłówka rekordu.

`providers/puste.py` dostarcza providera zwracającego zero rekordów —
obsługuje sety `products`, `equipment`, `projects`, `funding`.

## Widoczność i bramkowanie

### Przełączniki

| Warstwa | Mechanizm | Default |
|---|---|---|
| Endpoint CERIF | `Uczelnia.eksport_cerif_wlaczony` → 404 gdy `False` | włączony |
| Endpoint `/api/v1/` | `Uczelnia.api_v1_wlaczone` → 404 gdy `False` | włączony |
| Status korekty | `uczelnia.ukryte_statusy("cerif")` | — |

Oba przełączniki są **domyślnie włączone** — istniejące wdrożenia nie
zmieniają zachowania `/api/v1/`, a CERIF startuje aktywny.

### Widoczność per encja

`nie_eksportuj_przez_api` istnieje **tylko** na `Wydawnictwo_Ciagle`,
`Wydawnictwo_Zwarte`, `Patent` i `Jednostka`
(`ModelOpcjonalnieNieEksportowanyDoAPI`). Filtrowanie po nim na pozostałych
modelach dałoby `FieldError`. **Nie dokładamy tego pola do PD/PH** — to
osobna zmiana produktowa poza zakresem. Reguły są więc per encja:

| Encja | Warunek eksportu |
|---|---|
| `Wydawnictwo_Ciagle`, `Wydawnictwo_Zwarte` | status korekty niewykluczony kanałem `cerif`; `nie_eksportuj_przez_api=False`; w scope uczelni |
| `Praca_Doktorska`, `Praca_Habilitacyjna` | status korekty niewykluczony; w scope uczelni (brak pola opt-out) |
| `Patent` | jw. + `nie_eksportuj_przez_api=False` |
| `Autor` | `pokazuj=True` **oraz** istnieje `Autor_Jednostka` do `Jednostka` z `uczelnia=<ta uczelnia>` |
| `Jednostka` | `widoczna=True`, `uczelnia=<ta uczelnia>`, `nie_eksportuj_przez_api=False` |
| `Uczelnia` | zawsze (jedna, bieżąca) |
| `Zrodlo` | istnieje co najmniej jedna eksportowana publikacja tego tenanta wskazująca to źródło |
| `Konferencja` | jw. — istnieje eksportowana publikacja wskazująca tę konferencję |

`Zrodlo` i `Konferencja` nie mają FK do uczelni ani pola opt-out, więc bez
warunku „użyte przez widoczną publikację" każdy tenant wyeksportowałby cały
współdzielony słownik jako własny.

### Integralność referencyjna

Serializer emituje `id` osadzonej encji sąsiadującej **tylko wtedy, gdy ta
encja wyjdzie w swoim secie** — czyli gdy należy do prekomputowanego zbioru
widoczności w kontekście. W przeciwnym razie osadza ją bez `id`; profil
pozwala na to wprost („embedded entities without internal identifiers are
permitted").

Przypadek referencyjny: autor z `pokazuj=False` afiliowany przy publikacji —
publikacja wychodzi, ale `Person/@id` pojawić się nie może, bo wskazywałby na
nieistniejący rekord.

## Kontekst serializacji

Widoczność jest **prekomputowana przez provider** i wstrzykiwana do
serializera jako zbiory kluczy głównych. Serializer wykonuje wyłącznie
sprawdzenie przynależności do zbioru — żadnych zapytań.

```python
@dataclass(frozen=True)
class ZbioryWidocznosci:
    autorzy: frozenset[int]
    jednostki: frozenset[int]
    zrodla: frozenset[int]
    konferencje: frozenset[int]
    publikacje: frozenset[tuple[str, int]]   # (slug, pk)


@dataclass(frozen=True)
class KontekstSerializacji:
    namespace: str
    uczelnia: "Uczelnia"
    widoczne: ZbioryWidocznosci

    def id_dla(self, obj) -> str | None:
        """Identyfikator OAI albo None, gdy encja nie wychodzi w swoim
        secie. Czyste sprawdzenie przynależności do zbioru."""
```

Test liczby zapytań obejmuje **także serializację encji osadzonych** — to
jedyny sposób, żeby wyłapać przypadkowy lazy-load w `cerif/`.

## Serializery CERIF

Sygnatura jednolita:

```python
def serializuj(obj, ctx: KontekstSerializacji) -> lxml.etree.Element
```

### Publication — wydawnictwa ciągłe i zwarte

`tytul_oryginalny` + `Wydawnictwo_*_Tytul` → `Title` (wielojęzyczny),
`wydawnictwo_nadrzedne` → `PartOf`, `zrodlo` → `PublishedIn`,
`rok` → `PublicationDate`, `doi`/`pmc_id`/`issn`/`isbn`/`www` →
odpowiednie `FederatedIdentifier`, `BazaModeluOdpowiedzialnosciAutorow` →
`Authors/Author` + `Affiliation` (kolejność wg `kolejnosc`),
`typ_odpowiedzialnosci.typ_ogolny == TO_REDAKTOR` → `Editors/Editor`,
`slowa_kluczowe` → `Keyword`, `streszczenia` → `Abstract`,
`konferencja` → `PresentedAt`, `Element_Repozytorium` → `FileLocations`.

`strony` to jedno pole tekstowe — rozbicie na `StartPage`/`EndPage` przez
`^\s*(\d+)\s*[-–]\s*(\d+)\s*$`; gdy nie pasuje, oba elementy są pomijane
(nie zgadujemy).

### Publication — prace doktorskie i habilitacyjne

PD/PH mają **inną strukturę autorstwa**: pojedyncze FK `autor` i `promotor`
(`src/bpp/models/praca_doktorska.py:153-157`), nie
`BazaModeluOdpowiedzialnosciAutorow`. Mapowanie:

- `autor` → jedyny `Authors/Author`;
- `promotor` → **pomijany** (COAR/CERIF nie ma roli promotora, a wpisanie go
  jako współautora byłoby nieprawdą).

`charakter_formalny` na PD/PH to `cached_property` wołające
`Charakter_Formalny.objects.get(skrot="D")` przez singleton modułowy
(`praca_doktorska.py:141`). To jedno zapytanie na proces, nie N+1 — ale nadal
lazy DB hit wyzwalany z serializera i `DoesNotExist`, gdy słownik
przemianowano. Dlatego **typ dla PD/PH rozstrzyga provider**, nie serializer:
provider podaje gotowy URI COAR w kontekście, biorąc go z `coar_type` wiersza
o `skrot="D"`/`"H"`, a przy braku wiersza — ze stałej w `slowniki/coar.py`
(`doctoral thesis` dla PD, `thesis` dla PH).

### Zrodlo jako kanał wydawniczy

Serializowane jako `Publication` typu *journal*
(`http://purl.org/coar/resource_type/c_0640`) — to obiekt wskazywany przez
`PublishedIn`.

### Person

`nazwisko`/`imiona` → `PersonName`, `orcid` → `ORCID`, `pbn_uid` →
`Identifier`, `email`/`www` → `ElectronicAddress`, `Autor_Jednostka` →
`Affiliation`.

`Gender`: `Plec` to słownik ze `skrot`. Reguła: `"M"` → `m`, `"K"` → `f`,
każda inna wartość oraz `None` → element `Gender` pominięty.

### OrgUnit

`nazwa`/`skrot` → `Name`/`Acronym`, `ror_id` → `RORID`,
`Jednostka_Rodzic` → `PartOf`, `pbn_uid` → `Identifier`.

### Patent

`rodzaj_prawa.coar_type` → `Type` (obowiązkowe),
`tytul_oryginalny` → `Title`, `data_zgloszenia` → `RegistrationDate`,
`data_decyzji` → `ApprovalDate`, `numer_prawa_wylacznego` → `PatentNumber`,
`Patent_Autor` → `Inventors/Inventor`.

`Patent.rodzaj_prawa` jest `null=True` (`src/bpp/models/patent.py:108`) —
`None` traktowany jak niezmapowany, czyli fallback `c_15cd`.

### Event

`nazwa`/`skrocona_nazwa` → `Name`/`Acronym`, `miasto` → `Place`,
`panstwo` → `Country`, `rozpoczecie`/`zakonczenie` → `StartDate`/`EndDate`.

### Service

Jeden rekord opisujący CRIS, składany z `Uczelnia` i `Site`: `Acronym`,
`Name`, `WebsiteURL`, `OAIPMHBaseURL`, `Owner` (→ `OrgUnit` uczelni).
Zwracany w `<description>` odpowiedzi `Identify`.

## Słowniki

`slowniki/coar.py` — stałe URI dla poddrzewa COAR `text` oraz `patent`, plus
walidacja przynależności wartości `coar_type` do słownika. Interfejs
(ustalany w Fazie 0, bo koduje przeciw niemu agent serializerów):

```python
TEKST_ROOT = "http://purl.org/coar/resource_type/c_18cf"
PATENT_ROOT = "http://purl.org/coar/resource_type/c_15cd"
JOURNAL = "http://purl.org/coar/resource_type/c_0640"
DOCTORAL_THESIS = "http://purl.org/coar/resource_type/c_db06"
THESIS = "http://purl.org/coar/resource_type/c_46ec"

def typ_publikacji(coar_type: str | None) -> str: ...   # fallback TEKST_ROOT
def typ_patentu(coar_type: str | None) -> str: ...      # fallback PATENT_ROOT
def znany(uri: str) -> bool: ...
```

**Praca habilitacyjna** → `thesis` (`c_46ec`). COAR nie zna habilitacji;
`doctoral thesis` byłoby bliższe praktyce, ale formalnie nieprawdziwe.

`slowniki/dostep.py` — cztery COAR Access Rights; `slowniki/licencje.py` —
odczyt `Licencja_OpenAccess.uri`; `slowniki/jezyki.py` — odczyt
`Jezyk.kod_bcp47`. Wszystkie z sygnaturami `(obj) -> str | None`.

Komenda `cerif_raport_mapowan` listuje wartości słownikowe bez mapowania
oraz URI licencji wygenerowane automatycznie (wymagające potwierdzenia).

## Warstwa OAI-PMH

Sześć czasowników: `Identify` (z rekordem `Service`),
`ListMetadataFormats`, `ListSets`, `ListIdentifiers`, `ListRecords`,
`GetRecord`.

`metadataPrefix`: `oai_cerif_openaire`.
Namespace ładunku: `https://www.openaire.eu/cerif-profile/1.2/`.

`Identify` deklaruje `granularity=YYYY-MM-DDThh:mm:ssZ`, `deletedRecord=no`,
`earliestDatestamp` z najstarszego rekordu wszystkich setów. Wszystkie
datestampy są w **UTC**, w tym formacie.

Sety: `openaire_cris_publications`, `openaire_cris_products`,
`openaire_cris_patents`, `openaire_cris_persons`, `openaire_cris_orgunits`,
`openaire_cris_projects`, `openaire_cris_funding`, `openaire_cris_events`,
`openaire_cris_equipments`.

### Resumption tokeny

Keyset, nie offset. Ładunek podpisany `django.core.signing` z TTL:

```python
{"set": str, "prefix": str, "od": str | None, "do": str | None,
 "slug": str, "ts": str, "pk": int}
```

`slug` jest obowiązkowy — bez niego kursor w secie łączącym pięć modeli jest
wieloznaczny i produkuje duplikaty albo gubi rekordy.

Podpis jest wymagany — bez niego token jest wektorem wstrzykiwania parametrów
zapytania. Keyset zamiast `[offset:offset+n]` daje stały koszt strony
i stabilność przy zapisach w trakcie harvestu; przy offsecie edycja rekordu
w połowie przebiegu przesuwa okno i gubi albo dubluje pozycje.

Rozmiar strony: 100. Token wygasły lub z niepoprawnym podpisem →
`badResumptionToken`.

## Wyłączanie `/api/v1/`

Realizowane w aplikacji `api_v1`. **Nie przez zwrócenie `False` z klasy
uprawnień** — DRF zamienia to na 403/401, a wymagane jest 404 (endpoint ma
wyglądać na nieistniejący). Klasa uprawnień rozstrzyga tenanta przez
`Uczelnia.objects.get_for_request(request)` — wzorzec z
`src/api_v1/viewsets/common.py` i `src/api_v1/scoping.py`, nie z
`src/api_v1/permissions.py` (tamtejsze klasy są per-user i nie dotykają
tenanta) — i przy wyłączonej fladze podnosi
`rest_framework.exceptions.NotFound`.

Analogicznie endpoint CERIF przy `eksport_cerif_wlaczony=False` zwraca
`Http404`.

## Obsługa błędów

Błędy protokołu (`badVerb`, `badArgument`, `cannotDisseminateFormat`,
`idDoesNotExist`, `noRecordsMatch`, `badResumptionToken`) zwracane jako XML
z HTTP 200 — tak wymaga OAI-PMH.

Wyjątek przy serializacji pojedynczego rekordu: `rollbar.report_exc_info()`,
rekord pominięty, licznik pominięć w logu. To **świadome odstępstwo** od
domyślnego wzorca z `CLAUDE.md` („report + raise") — harvest całego korpusu
nie może umierać na jednym zepsutym wierszu. Nigdy `except: pass`.
W testach ten sam kod ma podnosić wyjątek: ustawienie
`CERIF_EXPORT_PRZERYWAJ_NA_BLEDZIE`, domyślnie `False`, w testach `True`.

## Testy

Pliki testowe są przypisane do agentów, żeby równoległa praca nie kolidowała:

| Plik | Zakres | Agent |
|---|---|---|
| `tests/test_slowniki.py` | mapowania, fallbacki, raport mapowań | A |
| `tests/test_providery.py` | strony, keyset, `django_assert_max_num_queries` | B |
| `tests/test_widocznosc.py` | reguły per encja; **wyciek osób** | B |
| `tests/test_serializery.py` | snapshoty XML, walidacja XSD | C |
| `tests/test_identyfikatory.py` | round-trip, błędne wejścia → wyjątek, nie `assert` | Faza 0 |
| `tests/test_oai.py` | czasowniki, tokeny, błędy protokołu | D |
| `tests/test_przelaczniki.py` | `api_v1_wlaczone`, `eksport_cerif_wlaczony` | E |
| `tests/test_integralnosc.py` | harvest wszystkich setów → każde `id` ma rekord | Faza 2 |

Test wycieku osób jest obowiązkowy i ma dwie asercje: autor
z `pokazuj=False` nie pojawia się w secie `persons` **ani** jako
`Person/@id` w żadnej publikacji.

Regresja Primo: `/oai/` z `oai_dc` odpowiada identycznie jak przed zmianą.

### XSD

Schematy profilu 1.2 są **vendorowane** do `src/cerif_export/tests/xsd/`
wraz z zależnościami importowanymi przez `xsd:import` — testy muszą działać
offline. Źródło: repozytorium `EuroCRIS/openaire-cris-validator`
(katalog schematów). W `tests/xsd/README.md` zapisać URL i commit, z którego
pobrano pliki. lxml dostaje lokalny resolver, żeby nie sięgał po sieć.

E2E: `openaire-cris-validator` jako `make cerif-validate`, poza domyślną
suitą (wymaga JVM).

Konwencja pytest wg `CLAUDE.md`: funkcje bez klas, `@pytest.mark.django_db`,
`model_bakery.baker.make`.

## Podział na równoległe zadania

**Faza 0 (szeregowo)** — ustala wszystkie kontrakty, przeciw którym kodują
pozostali: scaffold aplikacji, `const.py`, `identyfikatory.py` (+ testy),
`kontekst.py` (`Kursor`, `ZbioryWidocznosci`, `KontekstSerializacji`),
`providers/base.py` (sygnatury), **sygnatury `slowniki/*`**, migracje modeli.

**Faza 1 (równolegle, rozłączne katalogi i pliki testowe):**

| Agent | Zakres | Zależy od |
|---|---|---|
| A | `slowniki/` + `management/commands/cerif_raport_mapowan.py` | const, sygnatury słowników |
| B | `providers/` | base, identyfikatory, kontekst |
| C | `cerif/` | const, kontekst, sygnatury słowników |
| D | `oai/` | const, sygnatury providerów |
| E | przełączniki `/api/v1/` + `Uczelnia`; **rejestracja wszystkich nowych pól w `src/bpp/admin/`** | migracje |

**Faza 2 (szeregowo):** `views.py`/`urls.py`, test integralności,
`make baseline-update`, newsfragment towncriera.

## Newsfragment

`src/bpp/newsfragments/cerif-export.feature.rst` — eksport CERIF-XML zgodny
z OpenAIRE Guidelines for CRIS Managers 1.2.0 oraz przełączniki włączania
API i eksportu CERIF na obiekcie Uczelnia.
