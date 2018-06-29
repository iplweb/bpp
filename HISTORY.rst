==============
Historia zmian
==============

dev
---

*

1.0.22-dev
-------------

* możliwość skonfigurowania, czy na wydrukach z "Wyszukiwania" ma pojawiać się logo
  i nazwa uczelni oraz parametry zapytania (#603)

* poprawki wydruków - mniejsza czcionka i marginesy (#619)

* ukryj liczbę cytowań dla użytkowników niezalogowanych w wyszukiwaniu; dodaj raporty
  z opcjonalnie widoczną liczbą cytowań (#626)

* pozwalaj na określanie szerokości logo na wydrukach przez edycję obiektu "Uczelnia"

* automatycznie dodawaj ciąg znaków "W: " dla opisu bibliograficznego wydawnictwa
  zwartego (#618)

* wyszukiwanie po liczbie autorów, możliwość wyszukiwania rekordów bez uzupełnionych
  autorów (#598)

* możliwość sortowania przy użyciu pól liczba autorów, liczba cytowań, data ostatniej
  zmiany, data utworzenia rekordu i innych (#589)

* kropka na końcu opisu bibliograficznego, prócz rekordów z DOI (#604)

* definiowana ilość rekordów przy której pojawia się opcja "drukuj" i "pokaż wszystkie"
  dla użytkowników zalogowanych i anonimowych, poprzez edycję obiektu Uczelnia (#610)

1.0.21
------

* możliwość ustalenia domyślnej wartości pola "Afiliuje" dla rekordów wiążących
  rekord pracy z rekordem autora

* możliwość wyszukiwania po liczbie cytowań; wyświetlanie liczby cytowań w tabelkach
  wyszukiwania

* możliwość pokazywania liczby cytowań w rankingu autorów z opcjonalnym ukrywaniem
  tego parametru za pomocą modułu redagowania (opcje obiektu Uczelnia)

* możliwość pokazywania liczby cytowań na podstronie autora z opcjonalnym ukrywaniem
  tego parametru za pomocą modułu redagowania (opcje obiektu Uczelnia)

* poprawiono błąd powodujący niewłaściwe generowanie eksportów PBN dla rekordów książek
  w których skład wchodziło powyżej 1 rozdziału (#623)

* poprawne wyświetlanie raportów jednostek i wydziałów, zgodne z ustawieniami
  obiektu "Uczelnia"

* poprawne eksportowanie do PBN konferencji indeksowanych w WOS/Scopus (#621)

* poprawione generowanie plików XLS w niektórych środowiskach (#601)

* możliwość określania rodzaju konferencji w module redagowanie: lokalna, krajowa,
  międzynarodowa oraz wyszukiwania po typach konferencji (#620)

1.0.20
------

* możliwość wyszukiwania nazwiska autora dla pozycji 1-3, 1-5 oraz dla ostatniej
  pozycji - dla użytkowników zalogowanych

1.0.19
------

* możliwość globalnej konfiguracji sposobu wprowadzania powiązań autorów z rekordami

1.0.18
-------

* obsługa API WOS-AMR od Clarivate Analytics

* lepsze wyświetlanie rekordu patentu w widoku rekordu

* poprawka formularza edycji autorów powiązanych z rekordem w module redagowania -
  obecnie edycja odbywa się za pomocą formularzy poziomych, co zwiększyło czytelnosć

* możliwość oznaczania i wyszukiwania rekordów indeksowanych w zewnętrznych bazach danych
  (np. WoS, Scopus) dla wydawnictw ciągłych

* nazwa konferencji zawiera etykietę "WoS" lub "Scopus" w przypadku, gdy konferencja
  jest indeksowana,

* eksport PBN działa poprawnie w przypadku podania tej samej daty w polu "od" i "do"

* ukrywanie pól w "wyszukiwaniu" oraz brak dostępu do raportów zgodnie z ustawieniami
  systemu dokonanymi w module "Redagowanie"

1.0.17
------

* import i wyszukiwanie dyscyplin naukowych

1.0.16 (2018-03-20)
-------------------

* błąd wyświetlania strony w przeglądarce Edge został naprawiony,

* data ostatniej modyfikacji dla PBN wyświetla się dla zalogowanych użytkowników

1.0.15 (2018-03-07)
-------------------

* dodatkowe pole dla typu odpowiedzialności, umożliwiające mapowanie charakterów
  formalnych autorów na charaktery formalne dla PBN

* nowe pola dla patentów: wydział, rodzaj prawa patentowego, data zgłoszenia,
  numer zgłoszenia, data decyzji, numer prawa wyłącznego, wdrożenie.

* impact factor dla Komisji Centralnej ma 3 pola po przecinku (poprzednio 2)

* zmiana sposobu nawigacji na menu na górze ekranu,

* wyszukiwanie zyskuje nową szatę graficzną i animacje.

1.0.4 (2018-02-13)
------------------

* poprawienie błędu wyszukiwania autorów w przypadku, gdy w wyszukiwanym
  ciągu znajdzie się spacja,

* zezwalaj na dowolną wartość zapisanego imienia i nazwiska w module
  redagowania,

* umożliwiaj wyszukiwanie po pierwszym nazwisku i imieniu (pierwszy autor,
  redaktor, etc)

1.0.1 (2018-01-01)
------------------

* wyświetlanie danych OpenAccess na widoku pracy,

* wyświetlanie DOI w opisach bibliograficznych, raportach oraz widoku pracy,

* poprawiony błąd budowania zapytania SQL na potrzeby wyszukiwania pełnotekstowego

0.11.112 (2017-12-09)
---------------------

* wyszukiwanie konferencji w globalnej nawigacji modułu redagowania

0.11.111 (2017-11-16)
---------------------

* poprawiony błąd związany z wyborem pola "tylko prace z afiliowanych jednostek"
  występujący w formularzu raportu autorów

* optymalizacja wyświetlania podstrony jednostki w przypadku, gdy zawiera
  ona więcej, niż 100 autorów.

0.11.109 (2017-11-14)
---------------------

* możliwość przejścia do panelu redagowania z każdej strony serwisu, gdzie
  tylko ma to sens (jednostki, autorzy, artykuły, wydziały),

* kosmetyczne poprawki wyświetla raportów,

* poprawiony błędny warunek dla funkcji raportu autorów "uwzględniaj tylko
  prace afiliowanych jednostek uczelni",


0.11.107 (2017-11-12)
---------------------

* opcja "Stwórz autora" tworzy domyślnie autora niewidocznego na stronach
  jednostek, kapitalizując nazwiska,

* poprawiono błąd powodujący niepoprawne działanie funkcji usuwania
  pojedynczych rekordów z wyników wyszukiwania.

0.11.106 (2017-11-10)
---------------------

* możliwość łatwego przechodzenia z formularza edycji w module redagowania do
  stron WWW dostepnych dla użytkownika końcowego

* [kod] generowanie opisu bibliograficznego autorów za pomocą systemu
  templatek Django; usunięcie kodu generowania opisu bibliograficznego
  autorów za pomocą własnych tagów,

* pole "Pokazuj na stronach jednostek" dla Autorów staje się polem "Pokazuj"
  i określa widoczność autora na stronie jednostki oraz w "Rankingu autorów"


0.11.104 (2017-11-08)
---------------------

* usunięto błąd uniemożliwiający edycję już zapisanego autora w rekordach
  wydawnictwa ciągłego i zwartego

0.11.103 (2017-11-06)
---------------------

* od tej wersji, dla wydawnictw zwartych, gdzie określone jest wydawnictwo nadrzędne,
  nie ma już potrzeby uzupełniania pola "Informacje", gdyż system w opisie
  bibliograficznym użyje tytułu wydawnictwa nadrzędnego,
  
* miniblog - możliwość umieszczenia aktualności na pierwszej stronie serwisu.

* obsługa przycisku "Uzupełnij rok" dla wydawnictwa zwartego (uzupełnia dane
  na podstawie pola "Szczegóły" bądź z "Wydawnictwo nadrzędne") oraz dla
  wydawnictwa ciągłego (uzupełnia dane na podstawie pola "Informacje").

0.11.101 (2017-11-03)
---------------------

* opcjonalne uwzględnianie prac spoza jednostek uczelni w raportach autorów,

* naprawiono działanie konektora OAI-PMH,

* "prawdziwa" funkcja "pozostałe prace" dla raportów,

* poprawione wyświetlanie rekordów (poprawna obsługa tagów "sup" i "sub"
  w opisach bibliograficznych).


0.11.90 (2017-09-23)
--------------------

* opcjonalne rozbicie na jednostki i wydziały w rankingu autorów

* możliwość ukrycia pola "Praca recenzowana"

* poprawki wyświetlania podstron autora i jednostki

0.11.77 (2017-09-19)
--------------------

* poprawiono liczenie punktacji sumarycznej w rankingu autorów

* poprawiono wyszukiwanie dla podanych jednocześnie par autor + jednostka

* poprawki wydajności wyszukiwania

0.11.55 (2017-08-30)
--------------------

* domyślne sortowanie rankingu autorów

* obsługa PostgreSQL 9.6

0.11.53 (2017-08-29)
--------------------

* poprawiony błąd eksportowania plików XLS i DOCX utrudniający ich otwieranie

* poprawiony błąd wyszukiwania dla pola "Źródło"

* opcjonalne ukrywanie elementów menu serwisu dla użytkowników zalogowanych
  i niezalogowanych


0.11.50 (2017-08-23)
--------------------

* poprawiony błąd uniemożliwiający sortowanie w rankingu autorów

* tabela rankingu autorów stylizowana podobnie jak inne tabele w systemie

* możliwość eksportowania rankingu autorów oraz raportów autorów, jednostek i
  wydziałów w różnych formatach wyjściowych (m.in. MS Excel, MS Word, CSV)


0.11.43 (2017-08-15)
--------------------

* możliwość zmiany wyglądu kolorystycznego systemu

* nowy framework raportów oparty o zapytania w języku DSL, obsługiwany
  w pełni przez użytkownika końcowego

* konfigurowalny czas długości trwania sesji - możliwość wybrania, jak długo
  system czeka na reakcję użytkownika przed automatycznym jego wylogowaniem

* autorzy przy wyszukiwaniu przez globalną nawigację oraz w module "Redagowanie"
  wyświetlani są zgodnie z ilością publikacji w bazie

* możliwość automatycznego utworzenia autora i serii wydawniczej
  podczas wpisywania rekordu - bez konieczności przechodzenia do innej częsci
  modułu redagowania

* opcja resetu hasła w przypadku jego zapomnienia

* konfigurowalny czas do przymusowej zmiany hasła, konfigurowalny moduł
  zapamiętujący ostatnio wpisane hasła oraz konfigurowalna ilość
  ostatnio zapamiętanych haseł

0.11.19 (2017-07-15)
--------------------

* do rekordu powiązania autora z wydawnictwem (zwartym, ciągłym lub patentem)
  dochodzi pole "afiliowany", domyślnie mające wartość 'PRAWDA'. Należy je
  odznaczyć w sytuacji, gdyby autor danej publikacji zgłosił powiązanie
  do jednostki będącej w strukturach uczelni w której jest zatrudniony jednakże
  jednoczasowo do tej publikacji zgłosił inną jednost

* do rekordu wydawnictwa zwartego, ciągłego, patentu, pracy doktorskiej i
  pracy habilitacyjnej dochodzą pola "strony", "tom" i "numer zeszytu":
  - w sytuacji, gdy są wypełnione, to ich wartości są używane do eksportu PBN,
  - w sytuacji, gdy są niewypełnione, system spróbuje wyekstrahować te dane z
    pól "szczegóły" i "informacje" analizując ciągi znaków, poszukując ciągów
    takich jak "vol.", "t.", "r.", "bd." dla tomu, "nr", "z.", "h." dla numeru
    zeszytu, "ss." lub "s." dla stron, "b. pag." dla braku paginacji,
  - podczas edycji rekordu w module "redagowanie" pola te zostaną uzupełnione
    przez system na podstawie pól "szczegóły" i "informacje" gdy użytkownik
    kliknie odpowiedni przycisk; w takiej sytuacji pola te, jeżeli zawierają
    jakieś informacje, zostaną nadpisane.

* konferencje - w module redagowania można dopisywać dane o konferencjach, które
  następnie mogą być przypisane do wydawnictwa ciągłego lub wydawnictwa
  zwartego

* struktura - w module redagowania za pomocą rekordu uczelni można ukryć
  wyświetlanie punktacji wewnętrznej oraz Index Copernicus

* autor - nowe pole "Open Researcher and Contributor ID"

* wygodna edycja kolejności wydziałów w module Redagowanie➡Struktura➡Uczelnia

* poprawiono błąd związany z obsługą pola dla rekordu Autor "Pokazuj na stronie
  jednostki". Autorzy którzy mają to pole odznaczone, nie będą prezentowani
  na stronach jednostek.

* dla typów KBN można określać odpowiadający im charakter PBN. Pole to zostanie
  użyte jako fallback w sytuacji, gdy rekord charakteru formalnego do którego
  przypisana jest dana praca nie ma określonego odpowiadającego mu charakteru
  PBN

* podgląd na znajdujące się w bazie charaktery PBN i przypisane im charaktery
  formalne i typy KBN w module "Redagowanie"

* w bloku "Adnotacje" w module "Redagowanie" wyświetla się ID oraz PBN ID

* pola "Seria wydawnicza" oraz "ISSN" dla wydawnictwa zwartego

* możliwość określania nagród oraz statusu wybitności pracy dla rekordów
  wydawnictw zwartych i wydawnictw ciągłych

* możliwość filtrowania po statusach openaccess w module "Wyszukiwanie" dla
  użytkowników niezalogowanych

0.11.0 (2017-07-05)
-------------------

* obsługa Python 3 + Django 1.10

0.10.96 (2017-04-02)
--------------------

* pierwsza publicznie dostępna wersja
