==============
Historia zmian
==============

0.11.103 (2017-11-06)
---------------------

* miniblog - możliwość umieszczenia aktualności na pierwszej stronie serwisu


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
