# Eksport CERIF / OpenAIRE — dla administratora

BPP wystawia dorobek uczelni w formacie **CERIF-XML** zgodnym z
[OpenAIRE Guidelines for CRIS Managers 1.2.0](https://openaire-guidelines-for-cris-managers.readthedocs.io/),
przez endpoint **OAI-PMH 2.0**. Dzięki temu publikacje, projekty
i finansowanie mogą zostać zebrane przez [OpenAIRE](https://explore.openaire.eu/)
i powiązane z profilem instytucji.

Eksport jest konfigurowany **per uczelnia** — w instalacji wielouczelnianej
każdy serwis ma własny przełącznik, własny ROR i własny zakres danych.

## Adres endpointu

```
https://<adres-instancji>/cerif-oai/
```

To pełnoprawny endpoint OAI-PMH, więc używa się go z czasownikami protokołu:

| Wywołanie | Co zwraca |
|---|---|
| `/cerif-oai/?verb=Identify` | metryczkę repozytorium (nazwa, adres, właściciel, granularność dat) |
| `/cerif-oai/?verb=ListSets` | dziewięć zestawów profilu OpenAIRE |
| `/cerif-oai/?verb=ListMetadataFormats` | jedyny obsługiwany format: `oai_cerif_openaire` |
| `/cerif-oai/?verb=ListRecords&metadataPrefix=oai_cerif_openaire&set=openaire_cris_publications` | rekordy wybranego zestawu |
| `/cerif-oai/?verb=GetRecord&metadataPrefix=oai_cerif_openaire&identifier=<id>` | pojedynczy rekord |

Szybki test po wdrożeniu:

```bash
curl -s "https://<adres-instancji>/cerif-oai/?verb=Identify"
```

!!! warning "To **nie jest** ten sam endpoint, co `/oai/`"
    BPP ma dwa niezależne endpointy OAI-PMH i **dwa osobne przełączniki**:

    - `/oai/` — format `oai_dc`, zbierany przez biblioteczne systemy typu
      Primo; przełącznik **„OAI-PMH aktywny"**;
    - `/cerif-oai/` — format CERIF/OpenAIRE, opisywany w tym rozdziale;
      przełącznik **„Włącz eksport CERIF/OpenAIRE"**.

    Wyłączenie jednego **nie** wyłącza drugiego. Gdy eksport CERIF jest
    wyłączony, `/cerif-oai/` odpowiada błędem **404**.

Zestawy (sety) wystawiane przez endpoint — profil wymaga, żeby istniały
wszystkie dziewięć, **nawet puste**:

`openaire_cris_publications`, `openaire_cris_products`,
`openaire_cris_patents`, `openaire_cris_persons`, `openaire_cris_orgunits`,
`openaire_cris_projects`, `openaire_cris_funding`, `openaire_cris_events`,
`openaire_cris_equipments`.

W BPP zapełnione są: publikacje, patenty, osoby, jednostki, projekty,
finansowanie i konferencje (`events`). `products` i `equipments` pozostają
puste — BPP nie prowadzi takich rejestrów.

## 1. Włączenie i konfiguracja na obiekcie Uczelnia

Przejdź do **Redagowanie → Struktura → Uczelnia**, otwórz obiekt uczelni
i rozwiń sekcję **„Eksport CERIF / OpenAIRE (/cerif-oai/)"**:

| Pole | Znaczenie |
|---|---|
| **Włącz eksport CERIF/OpenAIRE** | Główny przełącznik (domyślnie **włączony**). Odznaczenie sprawia, że `/cerif-oai/` przestaje odpowiadać (404). |
| **Eksportuj dane osób do CERIF/OpenAIRE** | Domyślnie włączone. Odznaczenie zeruje zestaw `openaire_cris_persons` **i** odbiera autorom osadzonym przy publikacjach identyfikatory, ORCID-y oraz afiliacje — zostają same imiona i nazwiska. |
| **Eksport CERIF: kwoty finansowania** | Domyślnie **wyłączone**. Włącz tylko, jeśli uczelnia świadomie chce upublicznić kwoty finansowania projektów. |
| **Identyfikator ROR** | Identyfikator uczelni w [Research Organization Registry](https://ror.org/), np. `https://ror.org/016f61126`. Patrz punkt 2. |

Dodatkowo eksport używa pola **„Identyfikator repozytorium OAI-PMH"**
(sekcja *OAI-PMH dla Primo*). Jest ono **wspólne dla obu endpointów** —
identyfikatory rekordów mają postać `oai:IDENTYFIKATOR:Publications/123`.
Puste pole oznacza użycie domeny serwisu.

!!! danger "Raz opublikowanego identyfikatora repozytorium nie wolno zmieniać"
    Harvestery (OpenAIRE, Primo, BASE) traktują go jako trwałą część klucza
    rekordu. Zmiana po starcie zbierania = wszystkie rekordy widziane jako
    nowe, a stare zostają w indeksie jako duplikaty.

## 2. Identyfikatory ROR

ROR jest tym, co pozwala OpenAIRE **skleić** wyeksportowane publikacje
z profilem instytucji. Bez niego eksport przechodzi walidację, ale dane
zawisają bez powiązania z uczelnią.

- **Uczelnia** — pole *Identyfikator ROR* w sekcji CERIF (patrz wyżej).
- **Jednostki** — analogiczne pole na każdej jednostce
  (**Redagowanie → Struktura → Jednostki**). Puste = jednostka wychodzi
  bez identyfikatora zewnętrznego, co jest dopuszczalne.

Pole ma walidację sumy kontrolnej (ISO 7064), więc literówka zostanie
odrzucona przy zapisie. Do przeglądu i ustawienia ROR-a uczelni z linii
poleceń służy komenda:

```bash
# przegląd stanu + kandydaci wyszukani po nazwie w publicznym API ROR
python src/manage.py cerif_ustaw_ror

# tylko walidacja tego, co już jest (bez odpytywania API ROR)
python src/manage.py cerif_ustaw_ror --offline

# zapis po walidacji
python src/manage.py cerif_ustaw_ror --uczelnia <skrót-lub-PK> --ustaw https://ror.org/016f61126
```

Komenda nigdy nie zapisuje niczego sama — zapis wymaga jawnego `--ustaw`.

!!! warning "ROR „na oko" jest gorszy niż brak ROR-a"
    Wpisany na chybił trafił identyfikator wygląda na uzupełniony,
    a wskazuje w próżnię albo na **cudzą instytucję**. Zawsze potwierdź
    identyfikator na [ror.org](https://ror.org/).

## 3. Co trafia do eksportu, a co nie

Eksport respektuje istniejące mechanizmy widoczności BPP — nie ma osobnej
„listy do wysłania".

| Encja | Wychodzi, gdy… |
|---|---|
| **Publikacje** (ciągłe, zwarte, doktorskie, habilitacyjne) | status korekty **nie** jest ukryty w kanale *Eksport CERIF*, rekord nie ma zaznaczonego **„Nie eksportuj przez API"**, a wśród autorów jest ktoś afiliowany do jednostki tej uczelni |
| **Patenty** | jak wyżej |
| **Jednostki** | jednostka jest **widoczna**, należy do tej uczelni i nie ma **„Nie eksportuj przez API"** |
| **Osoby** | przełącznik *Eksportuj dane osób* włączony, autor ma **„Pokazuj"** i kiedykolwiek był afiliowany do jednostki tej uczelni (także emerytowany) |
| **Projekty i finansowanie** | projekt ma przypisaną jednostkę tej uczelni; grantodawcy wychodzą tylko ci realnie finansujący jej projekty |
| **Źródła i konferencje** | tylko wtedy, gdy wskazuje na nie eksportowana publikacja tej uczelni |

Kanał **„Eksport CERIF"** ustawia się w formularzu uczelni, w sekcji
**„Ukryj status korekty"**: dla każdego statusu korekty (np. „przed
korektą") można osobno zdecydować,
czy prace o tym statusie mają wychodzić do eksportu CERIF. Jest to kanał
niezależny od kanału *API* (który dotyczy REST API i `/oai/`).

## 4. Uzupełnienie słowników przed startem

CERIF opiera się na słownikach kontrolowanych (COAR Resource Types, COAR
Access Rights, BCP 47, adresy licencji). Migracja wypełniła to, co dało się
wyprowadzić jednoznacznie; reszta jest decyzją merytoryczną redakcji.
Braki i wartości wymagające potwierdzenia pokazuje raport:

```bash
python src/manage.py cerif_raport_mapowan
```

Warto go uruchomić **przed** zgłoszeniem endpointu do OpenAIRE — nieuzupełnione
mapowania nie blokują walidatora, ale dają zubożony eksport (np. wszystkie
prace jako ogólny „text" zamiast „doctoral thesis").

## 5. Weryfikacja walidatorem euroCRIS

Zanim zgłosisz endpoint do rejestrów, sprawdź go oficjalnym walidatorem
euroCRIS — na **docelowym, publicznym adresie**, nie lokalnie (walidacja
lokalna nie sprawdzi HTTPS, przekierowań ani nagłówków proxy):

```bash
make cerif-validate URL=https://<adres-instancji>/cerif-oai/
```

Wymaga JRE 17+ **albo** Dockera. Poprawny wynik to `OK (13 tests)`.

## 6. Rejestracja endpointu

Sam działający endpoint niczego nie uruchamia — trzeba go zgłosić:

1. **DRIS** (Directory of Research Information Systems, euroCRIS) —
   <https://dspacecris.eurocris.org/cris/explore/dris>.
2. **OpenAIRE Provide** — <https://provide.openaire.eu/>. Zespół agregacji
   OpenAIRE przeprowadza własną walidację; dopiero po niej dane zaczynają
   być zbierane.

## 7. Decyzja RODO — podejmij ją PRZED rejestracją

Zestaw `openaire_cris_persons` jest domyślnie **włączony** i wystawia do
publicznego, agregowanego endpointu imię, nazwisko, ORCID, płeć oraz
historię zatrudnienia autorów. Jedynym filtrem po stronie redakcji jest
flaga **„Pokazuj"** na autorze.

Do rozstrzygnięcia przez uczelnię: czy taki zakres danych osobowych jest
akceptowalny. Jeśli nie — odznacz **„Eksportuj dane osób do CERIF/OpenAIRE"**.
Publikacje będą się nadal eksportować, a autorzy pojawią się w nich wyłącznie
jako imię i nazwisko, bez własnych rekordów i identyfikatorów.

## Znane ograniczenie: skasowane rekordy

Endpoint deklaruje `deletedRecord=no`. Oznacza to, że rekord usunięty z BPP
**zostaje w indeksie OpenAIRE** — harvester przyrostowy nie ma skąd wiedzieć,
że zniknął. Jedynym sposobem na usunięcie takiego rekordu z agregatora jest
dziś kontakt z OpenAIRE. Prace nad „nagrobkami" opisuje dokumentacja
deweloperska.

## Zobacz też

- [euroCRIS — co jeszcze zostało](../deweloper/eurocris-co-jeszcze.md) —
  stan implementacji, braki i plan rozwoju eksportu.
- [Konfiguracja ogólna](ogolna.md) — pozostałe ustawienia obiektu Uczelnia.
