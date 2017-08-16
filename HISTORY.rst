==============
Historia zmian
==============

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
