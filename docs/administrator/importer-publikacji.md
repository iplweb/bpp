# Importer publikacji

## Wprowadzenie

Moduł **Importer publikacji** umożliwia import rekordów publikacji do systemu BPP
na podstawie danych pobranych z zewnętrznych źródeł. Import odbywa się w formie
wielokrokowego kreatora (wizarda), który prowadzi użytkownika przez kolejne etapy:
od pobrania danych, przez dopasowanie typu publikacji, źródła i autorów, aż po
utworzenie rekordu w bazie danych.

Moduł dostępny jest z menu **redagowanie**, w pozycji **Import publikacji**. Strona
główna importera to kafelki z dostępnymi źródłami danych oraz odnośnik
**„Importy w toku / ostatnie”**.

## Wymagane uprawnienia

Aby korzystać z importera, użytkownik musi spełniać jeden z warunków:

- posiadać status **pracownika** (`is_staff = True`), lub
- należeć do grupy **"wprowadzanie danych"**.

## Dostawcy danych (providerzy)

System obsługuje import z wielu źródeł danych. Każde źródło nazywane jest
**dostawcą** (providerem). Obecnie dostępni są:

| Dostawca | Dane wejściowe |
|---|---|
| [CrossRef](#crossref) | DOI |
| [PBN](#pbn) | PBN UID albo adres pracy w repozytorium PBN |
| [BibTeX](#bibtex) | wklejony kod BibTeX — jedna praca lub wiele naraz |
| [DSpace](#dspace) | adres strony pracy w repozytorium DSpace |
| [Pozostałe strony WWW](#pozostałe-strony-www) | adres strony publikacji |

### CrossRef

Dostawca **CrossRef** umożliwia import publikacji na podstawie identyfikatora DOI.

- **Dane wejściowe:** DOI publikacji (np. `10.1234/example.2024`)
- **Sposób działania:** System pobiera metadane publikacji z API CrossRef.
  Odpowiedź jest buforowana w tabeli `CrossrefAPICache` — ponowny import tego
  samego DOI (także po wcześniejszym wyszukiwaniu w komparatorze) nie odpytuje
  CrossRef drugi raz.
- **Automatycznie rozpoznawane dane:**
  - tytuł, rok, DOI, tom, numer, strony
  - autorzy (imię, nazwisko, ORCID)
  - nazwa czasopisma lub wydawcy
  - ISSN, E-ISSN, ISBN, E-ISBN
  - typ publikacji (np. `journal-article`, `book`, `book-chapter`)
  - język, abstrakt, słowa kluczowe, URL, licencja

### PBN

Dostawca **PBN** pobiera publikację z Polskiej Bibliografii Naukowej.

- **Dane wejściowe:** PBN UID (24 znaki szesnastkowe) albo adres pracy
  w repozytorium PBN (`…/publication/view/<UID>`).
- **Sposób działania:** System odpytuje API PBN (tylko do odczytu) danymi
  aplikacji skonfigurowanymi w rekordzie uczelni. Typy PBN (`ARTICLE`, `BOOK`,
  `EDITED_BOOK`, `CHAPTER`) są mapowane na typy CrossRef, licencje Open Access
  na adresy Creative Commons.
- Odpowiednik w PBN jest wtedy znany z góry, więc krok
  [„Sprawdź w PBN”](#krok-6-sprawdź-w-pbn) jest pomijany.

### BibTeX

Dostawca **BibTeX** umożliwia import publikacji na podstawie wklejonego kodu BibTeX.

- **Dane wejściowe:** Kod BibTeX wklejony w pole tekstowe, np.:

  ``` bibtex
  @article{klucz2024,
    title = {Tytuł publikacji},
    author = {Kowalski, Jan and Nowak, Anna},
    year = {2024},
    journal = {Nazwa Czasopisma},
    doi = {10.1234/example}
  }
  ```

- **Sposób działania:** System parsuje kod BibTeX i wyodrębnia metadane.
  Obsługiwane są formaty autorów `Nazwisko, Imię` oraz `Imię Nazwisko`.
- **Wiele wpisów naraz:** po wklejeniu kilku wpisów importer tworzy listę
  **„Import wielu prac”** — każdy wpis jest osobną pozycją, którą importuje się
  (przyciskiem „Importuj”, tym samym kreatorem) albo pomija. Lista pokazuje
  postęp („Zaimportowano X z Y”) i można do niej wrócić z „Importy w toku /
  ostatnie”.

- **Mapowanie typów BibTeX na typy CrossRef:**

  - `article` → `journal-article`
  - `book` → `book`
  - `inbook`, `incollection` → `book-chapter`
  - `inproceedings`, `conference` → `proceedings-article`
  - `phdthesis`, `mastersthesis` → `dissertation`
  - `proceedings` → `proceedings`

### DSpace

Dostawca **DSpace** pobiera metadane pracy z repozytorium DSpace.

- **Dane wejściowe:** adres strony pracy w repozytorium.
- **Sposób działania:** wersja DSpace jest rozpoznawana po adresie:
  `…/items/<uuid>` → REST API DSpace 7+, `…/handle/<prefiks>/<sufiks>` →
  REST API DSpace 6. Metadane Dublin Core są mapowane na typy i pola BPP.

### Pozostałe strony WWW

Dostawca **Pozostałe strony WWW** wyciąga dane ze strony publikacji pod
podanym adresem — przydatny dla wydawców i repozytoriów, dla których nie ma
osobnego dostawcy.

- **Dane wejściowe:** adres strony publikacji.
- **Sposób działania:** system czyta metadane zapisane na stronie i łączy
  je w jeden wynik: tagi `citation_*` (Google Scholar / Highwire), Dublin
  Core, Schema.org (JSON-LD), OpenGraph oraz abstrakty z treści strony.
  Strony systemu **Omega-PSIR** są rozpoznawane automatycznie i czytane
  przez ich własny opis JSON-LD.

## Kroki importu

### Krok 1: Pobranie danych

Po wybraniu dostawcy i wpisaniu identyfikatora (DOI) lub wklejeniu kodu BibTeX
użytkownik klika przycisk "Pobierz". System:

1.  Waliduje dane wejściowe zgodnie z regułami wybranego dostawcy.
2.  Pobiera i normalizuje metadane publikacji.
3.  Tworzy **sesję importu** z pobranymi danymi.
4.  Automatycznie dopasowuje język publikacji.
5.  Automatycznie dopasowuje typ publikacji (charakter formalny) na podstawie
    mapowania CrossRef (patrz: konfiguracja Crossref Mapper w instrukcji
    administratora).
6.  Automatycznie dopasowuje autorów do istniejących rekordów w BPP.
7.  Uzupełnia brakujące dyscypliny z danych zgłoszeń publikacji (jeśli istnieje
    pasujące zgłoszenie).

Dostawcy pobierający dane z adresu podanego przez użytkownika (strony WWW,
repozytoria DSpace, Omega-PSIR) łączą się **wyłącznie przez HTTPS na
standardowym porcie 443** — także przy przekierowaniach. Adres zaczynający
się od `http://` (bez numeru portu) jest automatycznie zamieniany na
`https://`; adres z innym portem (np. `:8080`, `:8443`) zostanie odrzucony.

Na stronie głównej importera widoczna jest także lista ostatnich sesji importu
danego użytkownika, umożliwiając kontynuację przerwanych importów.

### Krok 2: Weryfikacja typu publikacji

W tym kroku użytkownik weryfikuje i ewentualnie koryguje:

- **Charakter formalny** -- typ publikacji w systemie BPP (np. artykuł
  w czasopiśmie, książka, rozdział). Jeśli dostępne jest mapowanie CrossRef,
  pole jest wstępnie wypełnione.
- **Typ MNiSW** -- klasyfikacja ministerialna (dawniej „typ KBN”).
- **Język** -- język publikacji.
- **Rodzaj rekordu** -- czy jest to wydawnictwo zwarte (książka/rozdział),
  ciągłe (artykuł w czasopiśmie) czy patent. Podpowiadany z typu publikacji
  według pola „Jest wydawnictwem zwartym” w mapowaniu typów CrossRef na BPP
  -- także wtedy, gdy typ nie ma tam przypisanego charakteru formalnego
  (wtedy charakter formalny wybiera redaktor).

System automatycznie wykrywa **duplikaty** -- szuka istniejących rekordów
po DOI (z normalizacją) oraz po tytule (dokładne porównanie). Jeśli znaleziono
potencjalne duplikaty, wyświetlane jest ostrzeżenie. Użytkownik może kontynuować
import mimo wykrycia duplikatów.

### Krok 3: Dopasowanie źródła

W zależności od typu wydawnictwa:

**Wydawnictwo ciągłe** (artykuł w czasopiśmie):

- Wymagane jest wskazanie **źródła** (czasopisma) z bazy BPP.
- System próbuje automatycznie dopasować źródło na podstawie nazwy
  czasopisma z danych dostawcy.

**Wydawnictwo zwarte** (książka, rozdział):

- Wymagane jest wskazanie **wydawcy** z bazy BPP lub wpisanie opisu wydawcy.
- System próbuje automatycznie dopasować wydawcę na podstawie nazwy
  z danych dostawcy.

### Krok 4: Dopasowanie autorów

Najważniejszy krok importu. System wyświetla listę autorów z danych dostawcy
wraz z informacją o statusie dopasowania:

- **Dokładne** (zielony) -- automatyczne dokładne dopasowanie do autora w BPP.
- **Luźne** (żółty) -- automatyczne częściowe dopasowanie (np. skrócone imię).
- **Ręczne** (niebieski) -- dopasowanie wykonane ręcznie przez użytkownika.
- **Niedopasowany** (czerwony) -- brak dopasowania; wymaga interwencji.

Dla każdego autora wyświetlane są:

- Imię i nazwisko z danych dostawcy
- ORCID (jeśli dostępny)
- Dopasowany autor, jednostka i dyscyplina w BPP
- Źródło dyscypliny (skąd pochodzi automatycznie wypełniona wartość)

**Edycja dopasowania autora**

Kliknięcie ikony ołówka przy autorze rozwija formularz edycji z polami:

- **Autor w BPP** -- wyszukiwanie autora (autouzupełnianie).
- **Jednostka** -- wyszukiwanie jednostki (autouzupełnianie).
- **Dyscyplina** -- lista rozwijana z dyscyplinami przypisanymi autorowi
  na dany rok.

Po wybraniu autora system automatycznie podpowiada jednostkę i dyscyplinę
na podstawie aktualnych danych w BPP.

**Źródło dyscypliny**

Przy automatycznie wypełnionej dyscyplinie system wyświetla informację
o jej pochodzeniu:

- *(Jedyna dyscyplina autora)* -- autor ma dokładnie jedną dyscyplinę
  na rok publikacji w tabeli `Autor_Dyscyplina`.
- *(Z aplikacji zgłoszeń publikacji)* -- dyscyplina pochodzi z pasującego
  zgłoszenia publikacji (moduł "Zgłoś publikację").
- *(Wybór użytkownika)* -- dyscyplina została wybrana ręcznie.

**Tworzenie autorów dla niedopasowanych**

Jeśli istnieją niedopasowani autorzy, dostępny jest przycisk
"Utwórz autorów dla niedopasowanych". System:

1.  Sprawdza, czy autor ma ORCID -- jeśli tak i istnieje autor z takim ORCID
    w BPP, dopasowuje go.
2.  W przeciwnym razie tworzy nowy rekord autora w BPP.
3.  Przypisuje wszystkich nowych/dopasowanych autorów do **obcej jednostki**
    skonfigurowanej w ustawieniach uczelni.

!!! note

    Operacja wymaga skonfigurowanej "obcej jednostki" w rekordzie uczelni.
    W przypadku jej braku wyświetlany jest komunikat o błędzie.


**Ustawianie ORCID**

Jeśli dostawca dostarczył identyfikator ORCID dla autora, a dopasowany autor
w BPP nie ma jeszcze ORCID, system umożliwia jego ustawienie -- pojedynczo
(przycisk przy autorze) lub grupowo (przycisk "Ustaw ORCIDy").

Warunki ustawienia ORCID:

- Autor importowany ma ORCID od dostawcy.
- Jest dopasowany do autora w BPP.
- Autor w BPP nie ma przypisanego ORCID.
- Ten sam autor BPP nie jest dopasowany wielokrotnie w danej sesji.

### Krok 5: Punktacja

System proponuje punktację MNiSW na podstawie danych źródła (punkty
czasopisma za rok publikacji) albo poziomu wydawcy z wykazu (dla wydawnictw
zwartych) i pokazuje podstawę wyliczenia. Wartość można zmienić albo
zostawić pustą. Gdy wśród autorów są osoby z dyscyplin HST, system
przypomina, że właściwy próg może być wyższy (np. 300 punktów dla
monografii).

### Krok 6: Sprawdź w PBN

Krok opcjonalny, dla wszystkich dostawców **poza PBN**. System szuka
importowanej pracy w PBN po DOI, tytule i adresie WWW, żeby od razu
wskazać jej odpowiednik i nie utworzyć w PBN duplikatu. Wybrany
odpowiednik można otworzyć w PBN albo wyczyścić. Krok wymaga zalogowania
do PBN; bez tego można go pominąć.

### Krok 7: Przegląd końcowy

Podsumowanie wszystkich danych przed utworzeniem rekordu:

- Metadane publikacji (tytuł, rok, DOI, tom, numer, strony itp.)
- Dopasowane źródło lub wydawca
- Lista autorów z jednostkami i dyscyplinami

Użytkownik potwierdza dane i przechodzi do utworzenia rekordu.

### Krok 8: Utworzenie rekordu

System tworzy rekord publikacji w BPP:

- **Wydawnictwo ciągłe** -- z przypisanym źródłem (czasopismem).
- **Wydawnictwo zwarte** -- z przypisanym wydawcą i danymi ISBN.

Do rekordu dodawani są wszyscy dopasowani autorzy z odpowiednimi jednostkami,
dyscyplinami i typem odpowiedzialności "autor". Autorzy przypisani do obcej
jednostki oznaczani są jako nieafiliowani.

Automatycznie uzupełniana jest punktacja na podstawie danych źródła
dla danego roku (jeśli dostępne).

Rekord otrzymuje adnotację `Dodano przez importer publikacji (nazwa dostawcy)`.

Na tym etapie oprócz zwykłego zapisu dostępny jest wariant **„Zapisz i wyślij
do PBN”** (nie dla patentów, które do PBN nie trafiają).

Po utworzeniu wyświetlana jest strona potwierdzenia z linkiem do edycji
rekordu w module redagowania.

!!! note "Patenty"

    Dla patentów importer pomija kroki *Dopasowanie źródła* i *Sprawdź w PBN*.

## Powiązanie ze zgłoszeniami publikacji

Importer współpracuje z modułem [Zgłaszanie publikacji](zglaszanie-publikacji.md):

- w zgłoszeniu z DOI lub adresem strony przycisk **„Użyj importera”**
  otwiera importer z danymi zgłoszenia,
- sesja importu jest wiązana ze zgłoszeniem **wyłącznie po DOI** (nigdy po
  tytule); DOI zgłoszenia jest czytany także z pola „strona WWW”, bo
  publiczny formularz zgłoszenia nie ma osobnego pola DOI,
- dyscypliny wpisane przez zgłaszającego są używane w kroku dopasowania
  autorów,
- po utworzeniu rekordu zgłoszenie dostaje automatycznie status
  **„zaimportowany przez importer prac”**; zgłoszenia odesłane autorowi do
  poprawek („wymaga zmian”) nie są wiązane.

## Anulowanie importu

Na każdym etapie importu dostępny jest przycisk "Anuluj", który po potwierdzeniu
oznacza sesję jako anulowaną. Anulowane sesje nie są domyślnie wyświetlane
na liście ostatnich importów — można je pokazać filtrem **„Status”** →
„Anulowano” (opis filtrów listy: [instrukcja redaktora](../redaktor/importer-publikacji.md#lista-sesje-importu-filtry-i-zapamiętany-widok)).

## Kontynuacja przerwanego importu

Jeśli użytkownik przerwie import (np. zamknie przeglądarkę), może go
kontynuować z listy **„Importy w toku / ostatnie”** na stronie głównej
importera. Ta sama lista zawiera rozpoczęte importy wielu prac z BibTeX.
Sesja zostanie wznowiona od ostatniego zapisanego kroku.
