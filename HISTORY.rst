==============
Historia zmian
==============

.. towncrier release notes start

Bpp 202411.1144 (2024-11-18)
============================

Usprawnienie
------------

- import list ministerialnych, kolory dla dyscyplin (#1411)
- przeszukiwanie po polu "Status korekty" w multiwyszukiwarce (#1437)
- możliwość wydruku oświadczeń dot. dyscyplin z poziomu widoku publikacji dla osób zalogowanych, z uprawnieniem do dodawania
  rekordów (#1438)
- dodaj punktację do źródła / uzupełnij punktację ze źródła obsługuje również kwartyle (#1460)
- usunięto odwołania do pól dla Komisji Centralnej z kodu (#1462)
- wyświetlaj kwartyl WoS/SCOPUS w raportach (#1464)


Bpp 202410.1142 (2024-10-14)
============================

Naprawione
----------

- nie pokazuj dyscyplin z nie-aktualnego roku (#1314)


Usprawnienie
------------

- obsługa dyscyplin źródeł dla kolejnych lat; możliwość odfiltrowania autorów nie będących pracownikami w rozbieżności
  dyscyplin źródeł, możliwość filtrowania po roku, ograniczenie wyświetlanych prac do prac
  z roku 2017 i wyższych;


  możliwość eksportowania rozbiezności dyscyplin źródeł/rekordów do formatu XLS, (#1411)
- dodaj ID systemu kadrowego do raportu slotów zerowego i raportu slotów ewaluacja upoważnienia (#1458)
- dodaj PBN UID do raportu slotów - ewaluacja (#1459)
- wyświetlaj kwartyl źródła (WoS i SCOPUS) w raporcie slotów - ewaluacja (#1464)


Bpp 202410.1141 (2024-10-08)
============================

Naprawione
----------

- parametryzacja czasu otwarcia połączeń + domyślne wyłączenie persistent connections na produkcji (do momentu Django 5,
  gdzie można będzie użyć psycopg-pool)


Bpp 202410.1140 (2024-10-07)
============================

Naprawione
----------

- usuń błąd który nie wyświetlał nie-obcych autorów w sytuacji gdy byli przypisani do obcej jednostki + błędnej jednostki (ale mieli dodatkowe przypisania, właściwe dla uczelni) w sytuacji wyłączonej opcji "pokazuj obcych autorów w przeglądaniu danych" (#1445)
- podpowiadaj dyscyplinę dla wpisywania autorów przez "zakładkę" (powyżej 25 autorów)
- szybsze generowanie XLSa w raport slotów - ewaluacja


Usprawnienie
------------

- maksymalny rok dla PBN ustawiony na 2025 (#1409)
- wyswietlaj ID systemu kadrowego w raport slotów - uczelnia (#1412)


Bpp 202410.1138 (2024-10-02)
============================

Naprawione
----------

- celery aktualizacja do 5.4.0 (lepsza współpraca z Python 3.11)
- obsługuj "puste" email backends (dummy, console, memory) na produkcji (w przypadku nie działającego e-maila mogą się przydać)


Bpp 202410.1137 (2024-10-02)
============================

Naprawione
----------

- celery aktualizacja do 5.4.0 (lepsza współpraca z Python 3.11)


Bpp 202409.1136 (2024-09-26)
============================

Naprawione
----------

- poprawka błędu uniemożliwiającego zaznaczenie wydziałów w rankingu autorów


Bpp 202407.1135 (2024-07-27)
============================

Naprawione
----------

- popraw błąd wyświetlania niektórych prac doktorskich (#1440)


Usprawnienie
------------

- nie pokazuj obcych autorów na stronach przeglądania danych (opcja obiektu 'Uczelnia')

- opcjonalnie nie wyświetlaj autorów bez publikacji na stronach przeglądania danych (opcja obiektu 'Uczelnia') (#1439)


Bpp 202407.1134 (2024-07-26)
============================

Naprawione
----------

- przeniesiono ustawienia "ranking autorów bez kół naukowych" do obiektu uczelnia,
- poprawki kodu: usunięcie kodu raportów jednostek i autorów, w tym tzw. "raport jednostek / autorów 2012",
- poprawki kodu: usunięcie celeryui oraz raportów zależnych (j/w); przesunięcie rankingu autorów do oddzielnego modułu (#1395)


Bpp 202407.1133 (2024-07-25)
============================

Usprawnienie
------------

- ranking autorów bez kół naukowych (#1395)


Bpp 202407.1132 (2024-07-21)
============================

Naprawione
----------

- importuj plik dyscyplin bazując na formacie POLON (fix #1434)


Bpp 202407.1131 (2024-07-20)
============================

Naprawione
----------

- nie wyświetlaj nieaktualnych kół naukowych w polu "aktualne jednostki", przesuń do "jednostki historyczne"


Bpp 202407.1130 (2024-07-20)
============================

Naprawione
----------

- poprawiono dodawanie autorów przez "zakładkę Autorzy" - problem z komunikatem "wpisz rok" w polu dyscypliny
  dla wydawnictw ciągłych i zwartych


Bpp 202406.1129 (2024-06-24)
============================

Naprawione
----------

- eksport do PBN dopasowany do nowego API (błąd ValueError("Field 'id' expected a number but got '**UID**'.")) (#1410)
- poprawnie wyświetlaj w raportach aktualną jednostkę, gdy wybrano również autorów "zerowych"


Bpp 202405.1128 (2024-05-23)
============================

Usprawnienie
------------

- umożliwiaj dodawanie książek / rozdziałów przez CrossRef API (#1371)


Bpp 202405.1126 (2024-05-22)
============================

Naprawione
----------

- poprawne edytowanie autorów wydawnictwa zwartego przez "zakładkę"


Usprawnienie
------------

- dodano deklarację dostępności z opcją skonfigurowania jej w ramach serwisu
  lub na zewnątrz (#1398)
- dodaj flagi HttpOnly oraz Secure do ciasteczek sessionId oraz csrftoken,
  dodaj nagłówek X-Frame-Options (#1406)


Bpp 202405.1125 (2024-05-13)
============================

Usprawnienie
------------

- dodano kolumnę "impact factor" do raportu uczelnia - ewaluacja (new-1)
- dodano kolumnę "Aktualna jednostka" dla raportu slotów - uczelnia bez podziału na jednostki i wydziały (new-2)


Bpp 202312.1123 (2023-12-11)
============================

Naprawione
----------

- korekta literówek w nazwach pól w wyszukiwarce + migracja zapisanych formularzy wyszukiwania (new-1)


Bpp 202312.1122 (2023-12-10)
============================

Naprawione
----------

- napraw edycję dyscyplin dla prac przy większej ilości autorów -- przez
  zakładkę "Autorzy" dla wydawnictw ciągłych i zwartych (#1194)
- umożliwiaj edycję rekordów z dużą ilością autorów (wcześniej: błąd timeout) (#1207)
- porównuj prawidłowo autorów po ORCID w module dodawania z CrossRef (#1356)


Usprawnienie
------------

- opis w HTML również dla wydziału (new-1)
- wyświetlaj aktualną dyscyplinę/subdyscyplinę autora (#1314)
- więcej opcji edytora HTML - opis autora i jednostki (#1341)
- lepsza lista aktualnych pracowników na stronie jednostki (#1342)
- sortuj jednostki alfabetycznie (fix #1344) (#1344)
- Zmiana nazw kolumn/etykiet:
  - PK na MNiSW/MEiN
  - Typ KBN/MNiSW na Typ MNiSW/MEiN (#1351)
- opcjonalnie wysyłaj do PBN prace bez oświadczeń (#1358)
- nie ustawiaj domyślnie ISSN bazując na e-issn dla prac pobieranych z
  CrossRef (#1361)
- wyłącz django-password-policies gdy aktywne logowanie przez Microsoft (#1364)


Bpp 202311.1121 (2023-11-12)
============================

Usprawnienie
------------

- kompatybilność z nowym API PBN w zakresie wysyłania dyscyplin ze słowników aktualnych i nieaktualnych (odpowiedniki-pbn)


Bpp 202310.1118 (2023-10-19)
============================

Usprawnienie
------------

- umożliwiaj importowanie punktów i dyscyplin źródeł z informacji z PBN,
  umożliwiaj weryfikację źródeł po stronie PBN (ten sam ISSN, różne MNISWID,
  brak informacji o dyscyplinach) (#1354)


Bpp 202310.1116 (2023-10-01)
============================

Usprawnienie
------------

- autoryzacja za pomocą Office 365 (office365)
- możliwość instalowania backendów autoryzacyjnych jako warianty podstawowego pakietu (warianty)


Bpp 202309.1115 (2023-09-25)
============================

Usprawnienie
------------

- licz sloty dla roku 2024, przy pomocy dotychczasowego algorytmu (rok-2024)


Bpp 202309.1114 (2023-09-14)
============================

Naprawione
----------

- napraw pobieranie journali przez ich PBN UID (pobieranie-journala-przez-pbn-id)
- ponownie włacz widoczność przycisków "Eksport" oraz "Dodaj z CrossRef API" (regresja-eksport-api)


Usprawnienie
------------

- import list ministerialnych 2023 (import-list-2023)


Bpp 202309.1113 (2023-09-10)
============================

Usprawnienie
------------

- obsługa API v2 dla dyscyplin PBN (nowe-dyscypliny-pbn)


Bpp 202308.1112 (2023-08-31)
============================

Naprawione
----------

- poprawka dotycząca parametru 'minimalne PK' dla raportu zerowego (ignoruj
  prace z wynikiem PK mniejszym, niż zadany parametr; poprzednio - mniejszym
  lub równym) (raport-zerowy-1)


Bpp 202308.1111 (2023-08-29)
============================

Naprawione
----------

- poprawiono wyświetlanie bannera dot. cookies; kod trackera Google pojawia się w tej sytuacji opcjonalnie (bug1-cookie)


Usprawnienie
------------

- konfigurowalny raport zerowy (raport-zerowy-1)


Bpp 202307.1110 (2023-07-25)
============================

Naprawione
----------

- poprawka błędu pojawiającego się przy wyświetlaniu wielu stron w multiwyszukiwarce (bug1)


Bpp 202307.1107 (2023-07-21)
============================

Usprawnienie
------------

- Django 4.2 (new)


Bpp 202307.1106 (2023-07-09)
============================

Naprawione
----------

- napraw błąd związany z przetwarzaniem zmiennych przez bibliotekę formularzy ``django-crispy-forms`` (template1)


Usprawnienie
------------

- Nie loguj "anonimowych" zdarzeń związanych ze zmianą rekordu przez easyaudit (new)


Bpp 202307.1105 (2023-07-09)
============================

Usprawnienie
------------

- Moduł import_dbf przesunięty do oddzielnego modułu -- plugina (new-2)


Bpp 202307.1104 (2023-07-04)
============================

Naprawione
----------

- poprawne wyszukiwanie po wydziale pierwszego zgłaszającego autora w module "Zgłoś publikację" (new-2)


Usprawnienie
------------

- modułowość oprogramowania -- możliwość instalowania pakietów w namespace ``bpp_plugins``, które to
  kolejno zostaną automatycznie wykryte i dodane do INSTALLED_APPS (new-1)
- pole 'Opis' również dla autorów (new-2)


Bpp 202305.1102 (2023-05-22)
============================

Usprawnienie
------------

- nowy styl prezentacji jednostek na stronie wydziału (#1344)


Bpp 202304.1101 (2023-04-17)
============================

No significant changes.


Bpp 202304.1100 (2023-04-17)
============================

Usprawnienie
------------

- poprawna obsługa punktacji dyscyplin z dziedzin humanistycznych, społecznych i teologicznych (1331-dyscypliny)
- opis jednostki może zawierać tagi HTML (#1341)


Bpp 202302.1099 (2023-02-21)
============================

Usprawnienie
------------

- umożliwiaj pobieranie raportu slotów - uczelnia przez API w formacie JSON (#1332)


Bpp 202302.1098 (2023-02-06)
============================

Naprawione
----------

- poprawna obsługa parametrów początkowych dla formularzy inline z autorami w przypadku dodawania rekordu
  przy pomocy CrossRef API (#1310)


Usprawnienie
------------

- Możliwość dodawania i wyszukiwania oświadczeń Komisji Ewaluacji Nauki
  (Uniwersytet Medyczny w Lublinie) (#1318)
- dodanie kolumny z jednostką afiliowaną do raportu ewaluacja - upoważnienia (#1330)


Bpp 202301.1097 (2023-01-01)
============================

Usprawnienie
------------

- możliwość wysyłania wyłącznie informacji o płatnościach do PBNu (bez_numeru2)


Bpp 202212.1096 (2022-12-27)
============================

Usprawnienie
------------

- * mapowanie kół naukowych do powiązania autora i jednostki do rekordu --
    dla jednostek przypisz koło naukowe, do którego przypisany jest autor. (bez_numeru)


Bpp 202211.1095 (2022-11-30)
============================

Naprawione
----------

- naprawiono generowanie raportu slotów uczelnia w formacie XLSX (#1316)


Usprawnienie
------------

- umożliwiaj import opłat za publikację z plików XLSX generowanych przez system (bez_numeru)


Bpp 202211.1094 (2022-11-22)
============================

Naprawione
----------

- popraw literówkę (bez_numeru)


Usprawnienie
------------

- możliwość wyszukiwania po rodzaju jednostki (jednostka / koło naukowe) (bn1)
- możliwość wyszukiwania po kierunkach studiów (bn2)


Bpp 202210.1092 (2022-11-20)
============================

Naprawione
----------

- popraw literówkę (bez_numeru)


Usprawnienie
------------

- użyj standardowego polecenia env() zamiast django_getenv() do konfigurowania serwisu (bez_numeru)


Bpp 202210.1091 (2022-10-16)
============================

Naprawione
----------

- popraw literówkę w nazwie kolumny modułu redagowania (bez_numeru)


Bpp 202210.1090 (2022-10-16)
============================

Naprawione
----------

- załącz prawidłowo pliki tłumaczeń w pakiecie WHL (bez_numeru)


Bpp 202209.1089 (2022-10-16)
============================

Naprawione
----------

- prawidłowe łączenie do kanałów ASGI w sytuacji, gdy nazwa użytkownika zawiera znaki nie-alfanumeryczne lub akcenty (bez_numeru-01)
- prawidłowe wysyłanie listów e-mail w sytuacji gdy tytuł pracy zawiera nowe linie (moduł ``zglos_publikacje``) (bez_numeru-02)
- prawidłowo obsługuj pliki dodawane w formularzu zgłoszenia pracy (bez_numeru-03)
- zmiana w powiadamianiu zgłaszających publikację: użyj nie jednostki pierwszego autora do określenia wydziału (a przez to
  osoby do powiadomienia), ale użyj pierwszej nie-obcej jednostki, jeżeli taka występuje, do określenia wydziału (a przez
  to osoby do powiadomienia) (bez_numeru-04)
- poprawne komunikaty przy braku ID autora w autocomplete dla dyscypliny (bez_numeru-05)


Dokumentacja
------------

- użycie ``towncrier`` do generowania list zmian (bez_numeru-01)


Usprawnienie
------------

- pokazuj aktualną funkcję autora po nazwisku w wyszukiwaniu globalnym (bez_numeru-01)
- umożliwiaj większy wybór kolumn przy wyświetlaniu tabelki autorów w module redagowania (bez_numeru-02)
- możliwość szybkiego dodawania zgłoszeń prac użytkowników jako
  wydawnictwo zwarte lub wydawnictwo ciągłe (b/n),
- możliwość porównywania danych prac z CrossRef API po DOI (b/n),
- możliwość importu rekordów z CrossRef API - do nowego rekordu wydawnictwa
  ciągłego (b/n),
- możliwość eksportowania danych z tabeli autora do formatu XLS (b/n),
- popraw błąd wyszukiwarki objawiający się problemami z sortowaniem po polu
  źródło/wydawnictwo nadrzędne (b/n),
- poprawiono błąd wysyłania rekordu do PBN w sytuacji, gdy lokalnie nie istnieje
  instytucja lub osoba (b/n),
- poprawki aplikacji do uruchamiania procesów w tle (b/n),
- nie wyświetlaj przycisku "pokaż w PBN" gdy autor nie ma określonego odpowiednika w PBN (b/n),
- szybsze wyświetlanie listy nazwisk dla odpowiedników PBN dla autora (b/n),
- możliwość wyboru widocznych kolumn w module redagowania (b/n),
- synchronizacja danych z istniejącymi rekordami z CrossRef API (b/n),
- możliwość oznaczenia jednostki jako "koło naukowe" (b/n),
- możliwość oznaczenia afiliacji autora do kierunku studiów (b/n),
- możliwość wymuszenia wysyłania publikacji afiliujących na uczelnię w sytuacji, gdy jednostka
  nie ma odpowiednika PBN UID a jest poprawną, zatrudniającą autorów jednostką uczelni (b/n),
- popraw wyszukiwanie autorów w sytuacji, gdy autor o nazwisku o tym samym początku
  posiada więcej prac naukowych, niż autor o krótszym nazwisku (b/n),
- użyj funkcji do pełnotekstowego wyszukiwania z Django (porzuć .extra) (b/n),
- pozbądź się wyszukiwania wg podobieństwa z modułu redagowania dla wydawców (b/n),

Zmiany w poprzednich wersjach
=============================

Poniżej znajduje się lista zmian w formacie sprzed używania narzędzia ``towncrier``.


202209.1088
-----------

* usunięto moduł generowania drukowanej "Kroniki Uczelni" (b/n),
* obsługa Python 3.10, Django 3.2 (#1115),
* użycie model_bakery zamiast model_mommy (b/n),
* aktualizuj listę charakterów w multiwyszukiwarce na bieżąco (#647),
* obsługa PostgreSQL 14 (#1243),
* aktualizacja biblioteki Celery do 5.2.2 (b/n),
* podgląd edycji schematu opisu bibliograficznego (#898),
* możliwość dopisywania własnych publikacji do bazy danych przez pracowników uczelni (#1237),
* możliwość edycji zgłoszeń publikacji + powiadomienia przez e-mail (#1255),
* nowa grupa użytkowników "zgłoszenia publikacji" - redaktorzy zajmujący się zgłoszeniami
  publikacji (b/n),
* w przypadku pustej grupy użytkowników "zgłoszenia publikacji", wysyłaj informację mailową
  do grupy użytkowników "wprowadzanie danych"
* możliwość wyłączenia wymagania informacji o opłatach w formularzu zgłaszania prac (b/n),
* wyświetlaj "flash messages" dla użytkownika niezalogowanego (b/n),
* włącz język zapytań dla modułu redagowania: autorzy, źródła, jednostki, itp.
  (b/n),
* możliwość eksportu danych wydawnictw ciągłych i zwartych do formatu XLSX (b/n),
* możliwość autoryzacji użytkowników za pomocą protokołu LDAP / ActiveDirectory (b/n),
* wstępna konfiguracja za pomocą django-environ (b/n),
* wszyscy zalogowani użytkownicy którzy chcą uzyskać dostęp do raportów muszą być dodani
  do grupy "generowanie raportów" (b/n),
* formularz zgłaszania publikacji opcjonalnie wymaga zalogowania (b/n),
* możliwość konfiguracji e-mail za pomoca pliku .env (b/n)
* możliwość konfiguracji kont administratora za pomocą pliku .env (b/n),
* usunięty błąd wyszukiwania wydawców w module redagowania po PBN ID (b/n),
* możliwość obliczania slotów za 2023 (b/n),
* zgłaszanie publikacji: mozna dopisywac redaktorow do grupy "zgłoszenia publikacji" aby
  tylko do nich docierały zgłoszenia publikacji, można też dodać ich jako osoby obsługujące
  zgłoszenia dla wydziału (Redagowanie -> Administracja) aby dostawały e-maile wg wydziału
  pierwszej jednostki autora ze zgłoszenia publikacji (b/n),
* użycie backendu django-celery-email dla wysyłania e-maili out-of-band (b/n),
* logowanie dostępu do serwisu BPP za pomocą django-easy-audit (b/n),

202207.1087
-----------

* aktualizacja biblioteki do generowania PDF z systemu do wersji WeasyPrint 55.0, dodatkowe
  "uodpornienie" systemu drukującego na przestarzałe certyfikaty SSL na serwerze bpp (#1223),
* wyświetlaj aktualną jednostkę w raporcie slotów - ewaluacja (#1036)
* filtry wracają do raportu slotów - uczelnia (#985)
* możliwość edycji nagłówka strony dla wyświetlania i wydruków po stronie
  użytkownika (#1226)
* możliwość edycji stopki z poziou bazy danych (b/n),
* w sytuacji, gdy kolejność jednostek ustalana jest ręcznie, nie dziel strony
  Struktura -> Jednostki w module redagowania na podstrony (#1211)
* umożliwiaj wygenerowanie kodu JSON wysyłanego do PBN API z linii
  poleceń -- polecenie ``pbn_show_json`` (b/n),
* poprawnie wysyłaj strony do PBN API (#1176),
* informacja o aktualnej jednostce w raportach "zerowych" (#1224),
* możliwość pobierania/uruchamiania systemu BPP za pomoca polecenia pipx (#1231),
* przed wyszukiwaniem pełnotekstowym usuń tagi HTML z zapytania (#1222),
* pokazuj w pierwszej kolejności odpowiedniki PBN dla wydawców, które posiadają
  ID ministerialne w module redagowania (#1174)
* pole bazodanowe "aktualny" znika z modelu Autor (b/n),
* pola "aktualna jednostka" oraz "aktualna funkcja" dla modelu Autor mogą mieć
  wartość pustą (null) (b/n),
* poprawiony skrypt odpinający miejsca pracy podczas importu danych
  kadrowych (#1229),
* polecenie przebudowania pola 'aktualna jednostka' dla powiązań autor+jednostka (b/n),
* możliwość wpisywania i eksportowania do PBN danych o kosztach publikacji (#1235),
* możliwość wyszukiwania publikacji w multiwyszukiwarce po aktualnej jednostce autora (#1236),
* ostrzegaj przed zdublowanym PBN UID przy zapisie prac w module redagowania (#1152),
* wyświetlaj opis jednostki na podstronie jednostki (#1217),
* lepsza prezentacja autorów na stronie jednostki przy wykorzystaniu pola "podstawowe miejsce pracy"
  oraz importu danych kadrowych (#1215)

202205.1086
-----------

* import pracowników: autorzy będą mieli aktualizowane tytuły naukowe przy imporcie,
  pod warunkiem, że tytuł o takiej samej nazwie lub skrócie jak w pliku XLS istnieje również
  po stronie BPP; w sytuacji, gdyby w pliku aktualizacji był
  podany pusty tytuł lub tytuł nie istniejący w systemie BPP, zmiana
  tytułu naukowego autora nie zostanie przeprowadzona (#1033)
* aktualna jednostka: w sytuacji, gdyby autor miał dwa lub więcej przypisań do jednostek
  w tym samym okresie czasu lub w sytuacji gdy daty rozpoczęcia lub zakończenia
  pracy są puste, system w pierwszej kolejności jako aktualną jednostkę
  ustali tą, gdzie autor rozpoczął pracę najwcześniej, zakończył najpóźniej,
  zaś w sytuacji braku jednej lub obydwu tych dat -- ustali jednostkę
  aktualną na tą, która została najpóźniej przypisana, wg numeru ID
  przypisania, zwiększającego się z każdym kolejnym przypisaniem (#1177),
* w REST-API przy eksporcie danych pojawiają się streszczenia z bazy danych,
  wraz z polem języka (#1208),
* poprawiono błąd związany z niepoprawnym wyliczaniem punktów dla prac
  w roku 2022 (#1209),
* raport slotów - ewaluacja pozwala na tworzenie raportów później niż dla
  2021 roku (#1210),
* definiowalna ilość wyświetlanych jednostek na stronę (#1211),
* możliwość ukrycia jednostek podrzędnych na stronie prezentacji danych (#1212),
* możliwość wyszukiwania w multiwyszukiwarce po pierwszej jednostce i po pierwszym
  wydziale (b/n),
* tylko jedno "podstawowe miejsce pracy" dla połączenia autor+jednostka (b/n),
* poprawna obsługa pola importowanego z Excela "podstawowe miejsce pracy" (#1213),
* pokazuj rekordy, którym należy skorygować pole "podstawowe miejsce pracy" oraz
  umożliwiaj jego wyłączenie (b/n),
* ustawiaj 'Aktualne miejsce pracy' autora na podstawie pola 'Podstawowe miejsce pracy' (b/n),
* szybsze i skuteczniejsze dopasowania źródeł przy integracji danych z PBN (b/n),
* polecenie ``check_email`` znika, korzystamy ze standardowego ``sendtestemail`` (b/n),
* pokazuj 'Aktualne miejsce pracy' na podstronie przeglądania autora oraz
  w module redagowania (b/n),
* nie pokazuj 'Aktualnego miejsca pracy' na podstronie autora jezeli jest to obca jednostka (b/n),
* import pracowników: umożliwiaj automatyczne przypisywanie obcej jednostki osobom,
  których nie ma w wykazie pracowników (b/n),
* przeglądanie/autor: umożliwiaj wyszukiwanie wyłącznie w jednostkach, w których
  autor ma publikacje (b/n),

202202.1085
-----------

* pola "kwartyl w SCOPUS" oraz "kwartyl w WoS" dla wydawnictwa ciągłego (częściowa
  implementacja #1204),
* pola "kwartyl w SCOPUS" oraz "kwartyl w WoS" dla punktacji źródła na dany rok
  (częściowa implementacja #1203),
* poprawne wykrywanie serwera testowego (#1191),
* ustawiaj nagłówek X-Forwarded-Proto i korzystaj z jego zawartości - celem poprawnego
  generowania linków m.in. w REST API (https zamiast http) (#1180),

202201.1083
-----------

* licz punktacje dla rozdziałów i monografii z roku 2022 wg reguł dla roku
  2021 (#1200),
* w przypadku uruchomienia na serwerze z nazwą "test" w domenie, ustaw tło na
  zawierające napis "serwer testowy" (#1191),
* wielowątkowy raport genetyczny (#1202),
* edycja tytułu raportu multiwyszukiwarki - teraz może zawierać on dodatkowe linie (#1201).

202201.1082
-----------

* nie używaj tagów HTML w generowanych raportach 3N (b/n),
* zawężaj raporty 3N do zakresu lat 2017-2021 (b/n),

202201.1081
-----------
* poprawka błędu związanego z uruchamianiem procedur na serwerze przez django_tee (#1171)
* potencjalna poprawka błędu związanego z jednoczesnym działaniem wielu wątków generujących raporty,
  przebudowujących dane itp. a powstawaniem deadlocks przy przebudowie bazy (#1185),
* wliczaj monografie do limitu 2.2N dla uczelni dla algorytmów liczących 3N (#1198),
* do algorytmu genetycznego wprowadzone zostały epoki - kolejne pokolenia osobników, korzystające z populacji
  rozwiązań obliczonych przez algorytm z poprzednimi ustawieniami (b/n),
* napraw stronę administracyjną django_tee (b/n).

202111.1081-rc7
---------------

* automatycznie odpinanie publikacji dla raportu genetycznego 3N (#965),

202110.1081-rc6
---------------

* raporty 3N plecakowy i genetyczny (#965),

202110.1081-rc1
---------------

* poprawka błędu związanego z importem maksymalnych slotów autora (b/n),
* możliwość złapania logów z poleceń uruchamianych w nocy do bazy danych (#1136),
* raport ewaluacja - upoważnienia (#1083),
* sprawdzanie i ostrzeganie użytkownika przy zapisie rekordów w sytuacji, gdy dane DOI lub WWW
  już istnieją w bazie danych (#1059),
* raport rozbieżności autor-źródło (#1023),
* z kodu usunięto funkcjonalność importu dyscyplin źródeł (#1122),
* możliwość importu streszczeń z rekordów PBN (#1146),
* dołączaj liczbę PK dla raportów wyjściowych 3N (#1159),
* nie bierz pod uwagę autorów bez okreslonych maksymalnych udziałów jednostkowych do raportów 3N (#1158),

202110.1081-rc0
---------------

* liczba N dla autora staje się ilością udziałów oraz ilością udziałów monografii (#1153),
* możliwość importu udziałów dla autorów z plików XLSX (#1144),
* raport 3N pobiera dane z bazy danych (#1157),
* możliwość dodawania streszczeń do rekordów (#1155),
* możliwość eksportu streszczeń do PBN (#1155),
* możliwość eksportu słów kluczowych do PBN (#1155),
* możliwość pobierania danych autora po PBN UID z modułu redagowania (#1154),
* usuń błąd polegający na nie wysyłaniu rekordu do PBN w sytuacji istniejących już identycznych danych
  w tabeli "Przesłane dane" po wycofaniu jego oświadczeń (#1149),
* usuń błąd polegający na nieprawidłowym importowaniu oświadczeń z PBN po eksporcie rekordu zawierającego
  oświadczenia z datą (pole statedTimestamp) (#1147),

202110.1081-beta2
-----------------

* drobna korekta opisu bibliograficznego - wraca pole "uwagi" (b/n),
* drobna korekta funkcji ``strip_html`` - w przypadku pustego ciągu znaków, nie podnoś wyjątku (b/n)
* aktualizajca django-denorm-iplweb_ do wersji 0.5.3 -- korekta błędu z deadlockami (b/n),

202110.1081-beta1
-----------------

* poprawiono błąd występujący przy wysyłaniu publikacji do PBN przez panel redagowania, w sytuacji, gdy
  wydawnictwo nadrzędne nie miało odpowiednika PBN UID, a użytkownik nie był autoryzowany (b/n),
* poprawiono bład występujący przy wysyłaniu publikacji do PBN i włączonym kasowaniu oświadczeń,
  w sytuacji, gdy serwer PBN odpowiada statusem 200 ale dokument nie zawiera tresci (b/n),
* usunięto kod odpowiadający za eliminowanie ciągu znaków [kropka][przecinek] z opisów bibliograficznych (b/n),

202110.1081-beta0
------------------

* zmiana określenia z formularza raportu "tylko prace z jednostek uczelni" -> "tylko prace z afiliacją uczelni"
  (#1094),
* okreslanie liczby N dla autora dla każdej z dyscyplin (#1143),
* poprawne przebudowywanie rekordów przy zmianie szablonu przy pomocy django-denorm-iplweb_ (#1107, #1135),
* opcja "tylko prace afiliowane" dla raportów: uczelni, wydziału, jednostki i autora (#1092).

202110.1081-alpha
-----------------

* pełnotekstowe wyszukiwanie dla indeksu wydawców, wydawców PBN, wydawnictw zwartych (#1102)
* caching-framework przy użyciu django-denorm-iplweb_ (#1099)
* raport optymalizujący 3N (#1131),
* liczba N dla uczelni dla każdej z dyscyplin (#1131),
* oznaczaj alias wydawcy w nazwie (#1097),
* pozwalaj odszukać aliasy wydawcy w adminie (#1097),

.. _django-denorm-iplweb: https://github.com/mpasternak/django-denorm-iplweb/

202109.1080-beta1
-----------------

* kasowanie oświadczen dla rekordów z PK=0 z linii poleceń (#1121),
* błąd przy zapytaniu kasowania wszystkich dyscyplin przed wysłaniem do PBN nie zaburza
  dalszej wysyłki rekordu (#1130),
* poprawna obsługa parametru "nie wysyłaj prac z PK=0" dla integratora uruchamianego
  z linii poleceń (#1108),
* poprawne wyświetlanie komunikatu w przypadku próby eksportu pracy z PK=0 (#1108),


202109.1080-beta0
------------------

* możliwość nadpisywania dyscyplin podczas importu -- wystarczy podać imie i nazwisko istniejacego
  w systemie autora w pliku XLS (#884)
* możliwość zmiany opisu bibliograficznego przez użytkownika (#898),
* możliwośc zmiany tabelki z widokiem publikacji przez użytkownika (b/n),

202109.1080-alpha
-----------------

* przypisywanie dyscyplin za pomocą opcji "rozbieżności dyscyplin" (#909),
* sortowanie opcji multiwyszukiwarki (opcja "Szukaj") (#895),
* polecenie ``reset_multiseek_ordering`` do resetowania kolejności sortowania do domyślnej (#895),

202109.1079
-----------

* akcja grupowego wysyłania do PBN w module Redagowania dostepna dla wydawnictwo zwartych (b/n),
* usunięto regresję związaną z polami WWW/DOI/publiczny WWW, polegającą na nie pojawianiu się ich
  wartości w formularzu w module redagowania i nie zapisywaniu się ich (b/n),
* pobieranie po DOI/ISBN zawsze pobiera rekordy z bazy danych PBNu (które to mogły się zmienić w
  tak zwanym międzyczasie w stosunku do lokalnego cache) (b/n),
* normalizuj ISBN zapisywany dla lokalnego cache publikacji PBNu (b/n),
* eksperymentalne wyszukiwanie za pomocą DjangoQL dla wydawnictw zwartych (b/n),
* wyświetlanie linku do wysłanych danych przy komunikacie błędu (b/n),
* łatwe przechodzenie z aliasu do wydawcy nadrzędnego (b/n),
* usunięto błąd który pojawiał się gdy tworzono wydawcę będącym aliasem z przypisaniem poziomów (b/n),
* możliwość wyszukania po konkretnym wydawcy indeksowanym z poziomu rekordu wydawcy w module Redagowania (b/n),
* poprawione tłumaczenie drobnych elementów w panelu Redagowania ("Add" -> "Dodaj", "Filter" -> "Filtruj) (b/n),
* poszerzone pole wyszukiwania tekstowego/języka DjangoQL w module redagowania (b/n),
* włącz DjangoQL dla wydawnictw ciągłych (b/n),
* usunięto błąd pojawiający sie w module Redagowania przy wysyłaniu do PBN, gdy wystąpił inny błąd,
  niż autoryzacji lub związany z wysłanymi już danymi (b/n),
* zmiana nomenklatury: publikacja w PBN API -> publikacja z PBN API (b/n),
* możliwość pobierania prac z PBN API po identyfikatorze PBN UID z Redagowanie -> PBN API -> Publikacje -> Dodaj (b/n),
* możliwość pobierania prac z PBN API po numerze MongoID z pola "Odpowiednik w PBN" (b/n),
* konfigurowalne w obiekcie uczelnia: kasowanie oświadczeń rekordu przed wysłaniem danych do PBN (b/n),
  konfigurowalne nie wysyłanie z automatu prac z PK=0 (b/n),
* liczenie slotów dla roku 2022 (wg algorytmu 2021) (b/n),
* wyłaczono opcje "Dodaj" dla widoczności pól w wyszukiwarce (b/n),
* polecenie 'pbn_importuj_wydawcow', pozwalające pobrać nowe dane z PBN do lokalnego indeksu wydawców (b/n),
* możliwość pobrania źródła przez PBN UID (b/n),

202108.1078
-----------

* pobieranie pracy z PBNu za pomocą ISBN uwzględnia E-ISBN w sytuacji, gdy ISBN nie jest wypełniony (b/n),
* w przypadku wielu prac z tym samym ISBN, wcisnienie przycisku "pobierz po ISBN" wyświetla je wszystkie (b/n),
* przy wysyłaniu do PBN, w przypadku braku wartości w polu ISBN, weź wartość z pola E-ISBN, jezeli istnieje (b/n),
* przy wysyłaniu do PBN, w przypadku trybu udostępnienia "po publikacji", gdy ilośc miesięcy jest pusta,
  wstawiaj tam cyfrę zero (b/n),
* przy wysyłaniu do PBN "z automatu", w przypadku gdyby po stronie PBN istniał już rekord o takim DOI lub
  ISBN, spróbuj automatycznie pobrać ten rekord i dopasować do wysyłanego (b/n),
* przy eksporcie do PBN, użyj strony WWW wydawnictwa nadrzędnego dla rozdziałów, w sytuacji, gdyby nie miały
  określonej strony WWW (b/n),
* nie pokazuj "publikacje instytucji" w module redagowania w menu (b/n),
* nie wysyłaj artykułów bez zadeklarowanych oświadczeń do PBN (b/n),
* kasowanie oswiadczen kasuje rowniez historie wysłanych danych (b/n),
* narzedzie command-line do PBN: możliwość wysłania wyłącznie błędnych rekordów ponownie, możliwość wymuszonego
  wysłania wszystkich rekordów (b/n),
* kasowanie obiektów SentData przy usuwaniu oświadczeń (b/n),
* poprawka błędu przy wysyaniu rekordów przy odpowiedzi serwera PBN 400 i istniejącym DOI/ISBN (b/n),
* opcja dla narzędzia command-line umożliwiająca wysyłąnie do PBN wyłącznie nowych rekordów (bez
  informacji w tabeli SentData) (b/n),
* nie wysyłaj do PBN, jeżeli rozdział nie ma oświadczeń (b/n),
* rozszerzono zakres wysyłanych prac do PBN przez automatyczne narzędzie zgodnie z w/wym poprawkami (b/n)
* umożliwiaj "odpinanie" dyscyplin (b/n),
* przycisk "pobierz po DOI" pobierający prace z PBNu po adresie DOI,
* lepsze komunikaty błędów w przypadku braku autoryzacji w PBN i kliknięciu przycisku "pobierz po DOI"
  lub "pobierz po ISBN" (b/n),
* nie pozwalaj na wpisanie adresu WWW w pole DOI (b/n),
* nie pozwalaj na wpisanie odnośnika do doi.org w pole WWW (b/n),
* lepsze komunikaty błędu w przypadku braku tokena autoryzacyjnego przy eksporcie do PBN (b/n),
* PBN wysłane dane otrzymują typ rekordu i możliwosć filtrowania/sortowania po nim (b/n),
* poprawki kodu przycisku "Wyślij ponownie" z wyslanych danych PBN (b/n)

202108.1077
-----------

* widoki PBN API umożliwiają łatwiejsze odnajdywanie rekordów na stronie PBN oraz w serwisie BPP (b/n),
* zwiększ ilosć widocznych prac w multiwyszukiwarce do 25000,
* aktualizuj lokalną kopię oświadczeń przy wysyłce rekordu (b/n),
* wycofywanie oświadczeń instytucji z poziomu modułu "Redagowanie" (b/n),
* przyciski umożliwiające szybkie przechodzenie między modułami PBN API a edycją prac w module "Redagowanie" (b/n)
* możliwość filtrowania rekordów wydanwnictwa zwartego wg posiadania lub nie wydawnicwa nadrzędnego oraz
  wg kryterium bycia lub nie wydawnictwem nadrzędnym dla innego rekordu (b/n),
* przycisk "Pobierz wg ISBN" w module redagowania, do pobierania odpowiedników z PBN po ISBN - interaktywnie
  (b/n),
* matchuj prace po ISBN - wyłącznie rekordy nadrzędne (b/n),
* użyj bardziej efektywnej metody pobierania danych do generowania PDF do raportu autorów (b/n),
* bardziej wydajne pobieranie PBN UID po ISBN (b/n),
* usuwanie wszystkich oświadczeń instytucji z linii poleceń (b/n),

202108.1075
-----------

* szybsze przeglądanie zawartości bazy w opcji PBN API w module redagowania (b/n),

202108.73
---------

* poprawki importu i synchronizacji danych z PBN (b/n),
* możliwość konfiguracji wyświetlanych opcji w multiwyszukiwarce (#896),

202108.72
---------

* poprawki matchowania rekordów przy wpisywaniu odpowiedników PBN w module redagowania: szybsze wyszukiwanie
  autorów, instytycji i publikacji, czytelniejsze rekordy instytucji i autorów, możliwość wyszukiwania publikacji
  po PBN ID, DOI, źródeł po PBN ID, ISSN, E-ISSN, książek po ISBN i inne
* pole "język oryginalny" dla tłumaczeń + eksport do PBN,
* jeżeli autor ma identyfikator PBN to nie wysyłaj ORCIDu (błąd o braku po stronie PBN),

202107.71
---------

* usunięto pole "data ostatniej aktualizacji dla PBN" (#1061),
* szybsze pobieranie publikacji z profilu instytycji PBN, dokładniejsze matchowanie, pobieranie
  oświadczeń z profilu instytucji PBN, wydajniejsze importowanie do bazy danych danych z PBN (#1088),
* szukaj po tytule w danych wysłanych do PBN (#1086),
* nie wysyłaj ORCID gdy autor nie posiada dyscypliny (#1085),
* wysyłanie wydawnictwo zwartych do PBN (#1044),

202106.71
---------

* w przypadku braku daty udostępnienia OpenAccess, wysyłaj rok + pierwszy miesiąc (b/n),

202106.70
---------

* szybsze globalne wyszukiwanie (#1067),
* wyszukiwanie jednostek po PBN UID w module redagowania (#1071),
* wyświetlaj płaską listę jednostek przy wyszukiwaniu lub filtrowaniu w module redagowania (#1082),
* eksport PBN: wysyłaj nie-puste oświadczenia, nawet gdy jednostka nie ma ustawionego odpowiednika w PBN (#1070,
* wyświetlaj kolumne "Profil ORCID" dla raportu slotów - ewaluacja (#1075),
* usuń zbędny tekst "jest nadrzędną jednostką dla" (#1074)
* powiązania autorów z dyscyplinami z modułu redagowania:
   - wyświetlają PBN UID i umożliwiają filtrowanie po nim (#1072),
   - eksportują poprawnie wartość ORCID i PBN UID do formatu XLS/CSV (#1072),
* eksport PBN: nie wysyłaj pola 'months' w przypadku trybów opublikowania innych, niż 'po publikacji'
  (#1081)
* eksport PBN: próbuj wysyłać wszystkie ORCIDy, niezależnie czy są po stronie PBN czy nie (wyłącz
  "ciche" wysyłanie autorów z brakującym po stronie PBNu ORCIDem) (#1078),
* eksport PBN: matchuj publikacje również po źródle (#1080),
* eksport PBN: pobieraj wszystkich autorow (#1077) i wszystkie publikacje z PBNu (b/n)

202105.67
---------

* usunięcie błędu polegającego na niemożliwości zapisania rekordu gdy w momencie
  tworzenia go dodany był autor z dyscypliną (b/n)
* hierarchia jednostek (#1018),
* raport uczelni (#1028)

202105.66
---------

* w przypadku synchronizacji prac z PBN i podwójnego DOI, wyswietlaj komunikat,
* wyłącz raportowanie Sentry dla procesów interaktywncyh (#1064),


202105.65
---------

* eksportuj naturalId w danych z PBN (#1063),
* lepsze matchowanie źródeł z PBN (#1064),
* weryfikuj obecnośc ORCID w PBN dla niezmatchowanych autorów (#1054),
* pobieraj wszystkie osoby z PBNu (b/n),
* pole dla wpisania wartości, czy praca występuje w profilu ORCID autora (#1054),
* nie eksportuj oświadczeń dla autorów bez afiliacji (#1055),

202105.64
---------

* eksport danych dot. OpenAccess do PBN (#1045),
* możliwosć wyswietlania raportów tylko dla członków zespołu (#1047),
* nie dodawaj automatycznie linków w tytułach prac (#976),
* możliwość ponownej synchronizacji rekordów niepoprawnie wyslanych
  (#1052),
* możliwość wysłania wielu rekordów do PBN z poziomu listy rekordów w module
  redagowania (b/n),
* synchronizacja wysyłania do PBN opcjonalna przy edycji rekordu (#1051),
* edycja autorów może odbywać się niezależnie od edycji "głównego" rekordu
  (#1049),
* ograniczenie maksymalnej liczby autorów edytowanej razem z
  formularzem rekordu do 25,
* lepszy komponent dla określania uprawnień w module administratora (#1048),
* wyszukiwanie po DOI w multiwyszukiwarce, module redagowania, globalnym
  wyszukiwaniu (b/n),
* ostrzeganie o zdublowanych DOI w module administratora (b/n),
* możliwość wyszukiwania po PBN UID w globalnym wyszukiwaniu w module redagowania
  oraz w interfejsie użytkownika (b/n),

202104.62
---------

* nie sprawdzaj obecnosci tabel rozbieżnosci dyscyplin przy starcie serwera (b/n),

202104.61
---------

* tagi Google Scholar na podstronach publikacji (#993),
* wymiana danych z PBN przez API (#949),

202103.60
---------

* pole "Afiliuje" w wyszukiwaniu traci operator "różne od" (#988),
* czasopismom (źródłom) można określać listę dyscyplin naukowych (#863),
* ulepszone linki tekstowe dla rekordów w bazie danych (#1001),
* raport slotów - autor może być eksportowany do PDF bezpośrednio z poziomu
  BPP (b/n),
* korygowanie "starych" linków tekstowych przy założeniu, że ID pracy na końcu
  linku nie uległo zmianie (#1015),
* umożliwiaj filtrowanie rekordów w module redagowania po osobie, która ostatnia
  zmieniała rekord oraz po osobie, która utworzyła rekord (#957),
* raport wyświetlający rozbieżności punktacji IF pomiędzy źródłem a rekordem
  (#1002),
* poprawne wyszukiwanie po słowach kluczowych (#1027),
* konfigurowalne numerki baz danych REDIS (#1026),
* walidacja pola 'Kod' przy edycji dyscyplin naukowych w module redagowania (#1030),

202103.59
---------

* poprawnie generuj raporty slotów - uczelnia dla eksportu wszystkich prac (#1010),

202103.58
---------

* poprawny link do przykladowego pliku do importu list IF (#1008),
* opis tekstowy artykułów na miniblogu w UI redagowania (#706),
* sortowanie powiązań Autor+Jednostka po dacie zatrudnienia, nie po nazwie (#1006),
* możliwośc wyświetlania wybranych stanowisk autorów dla aktualnych jednostek za nazwiskiem autora
  na stronie prezentacji danych autora (#1005),
* naprawiono błąd związany z przebudowaniem cache po wyłączeniu transakcji (b/n)
* nie licz punktów dla dyscypliny w sytuacji, gdy nie ma żadnych autorów w tej dyscypline
  (k=0) nawet dla progu 1 (#1006),
* prawidłowo formatuj tekstowe opisy obiektu "Poziom wydawcy" w module redagowania (#999),
* pola "od roku", "do roku" i "upoważnienie PBN" oraz kolumna "upoważnienie PBN" w
  raport slotów uczelnia - ewaluacja (#995)

202103.57
---------

* limit slotów w raporcie slotów-uczelnia, możliwość wygenerowania wszystkich prac (#997),
* import list IF (#868),
* poprawka importu pól daty z plików XLSX (b/n),
* licz poprawnie punktację w przypadku k=0 (#986),
* rozbij źródło/wydawnictwo nadrzędne i szczegóły na dwie kolumny w raporcie slotów - ewaluacja (#939),

202103.56
---------

* wyeliminowano błędy związane z niepoprawnie sformułowanymi zapytaniami w multiwyszukiwarce (b/n),
* wyeliminowano błędy związane z przeszukiwaniem po datach w przypadku operatorów mniejszy/większy/
  mniejszy lub równy/wiekszy lub równy (#982),
* wyeliminowano drobny bład podczas importu dyscyplin (#962),
* raport uczelnia-ewaluacja: jeżeli autor ma punktowane prace w danym roku w danej dyscyplinie, ale w innym
  roku będącym w zakresie raportu autor jest "zerowy", to nie pokazuj go jako zerowego (#984),
* wyeliminowano błąd przebudowy cache poprzez usuniecie 'globalnej' transakcji (#989),
* prawdziwe, indeksowane słowa kluczowe dla wszystkich rekordów, z możliwością edycji oraz przeszukiwania (#883),
* [API] słowa kluczowe eksportowane są teraz jako lista, nie jako ciąg znaków (b/n),
* [raporty] poprawka błędu uniemożliwiającego wygenerowanie raportu w formacie XLSX podczas gdy
  jeden z nagłówków elementów raporty zawierał w sobie znak "/" (slash) (b/n),
* poprawka błędu związanego z resetowaniem hasła,
* usunięto identyfikator pesel_md5 z systemu,
* import danych kadrowych z plików XLS (#983),
* [ASGI] raporty opracowywane w tle powinny przestać gubić komunikaty powiadomień,
* popraw błędy z wyświetlaniem stron z podwójnym znakiem "-" w polu "slug" (#980),
* popraw błędy przy imporcie dyscyplin w sytuacji gdy nie określono pola tytuł naukowy (#885),
* popraw błędy przy wyszukiwaniu jednostek bez wydziału (#964),
* możliwość indywidualnego określenia wliczania do rankingu dla każdego charakteru formalnego
  oraz typu KBN (#973)

202102.55
---------

* ograniczenie ilości zapytań przy generowaniu rekordów do API (#981),
* poprawne sortowanie po źródle/wydawnictwie nadrzędnym (#938),
* ORCID i PBN ID w raporcie zerowym (#940),
* umozliwiaj grupową zmianę statusu korekty w module redagowania (#948),
* umożliwiaj tworzenie raportu z wymierną liczbą slotów dla autora (#966),
* opcjonalnie pokazuj autorów zerowych w raporcie slotów-uczelnia (#941),
* pokazuj ORCID w module redagowania przy powiązaniach autor-jednostka (#970),
* optymalizacja algorytmu liczącego dla zadania dużej ilości slotów w sytuacji,
  gdy pracownik jej nie osiąga (b/n),
* poprawne ukrywanie prac w wyszukiwaniu globalnym oraz po wpisanu URL (#950).

202101.54
---------
* poprawne wyświetlanie charakteru formalnego dla doktoratów i habilitacji
  w widoku prac (b/n),
* możliwość wyszukania prac z ustawioną strona WWW [errata] (#865),
* aktualizacja pakietu django-password-policies-iplweb do wersji 0.8.0 (b/n),
* aktualizacja pakietu django-multiseek do wersji 0.9.43 (b/n),
* lepsze wyszukiwanie wg daty utworzenia rekordu dla zakresu dat (#932),
* wyświetlaj link do PubMedCentral dla prac z PMC ID (#959),
* poprawki pobierania PubMed ID (#958),
* poprawne zawężanie do zakresu punktów PK (#967),
* katalog cache ma nazwę z numerem wersji (#961),
* raport slotów uczelnia wg algorytmu plecakowego (#923),
* ustawienie ukrywania publikacji na podglądzie i w wyszukiwaniu globalnym (#950),
* w multiwyszukiwarce w polu "Wydawnictwo nadrzędne" pokazuj wyłącznie rekordy
  będące już wydawnictwami nadrzędnymi dla rekordów (#953).

202101.53
---------
* poprawne opisy powiązań autora z dyscypliną w module redagowania (#686)
* zezwalaj na więcej, niż jedną pracę doktorską dla autora (#873)
* pełne BPP ID na stronie pracy (#951)
* możliwość wyszukania prac z ustawionym DOI (#864)
* możliwość wyszukania prac z ustawioną strona WWW (#865)
* opcjonalnie traktuj jako slot zerowy prace z PK=5 (#877)
* wygodny podgląd powiązań autora z dyscypliną w module redagowania (b/n)
* możliwość eksportu danych dyscyplin autorów w formacie XLS (#893)
* wyświetlanie rekordów powiązanych dla wydawnictw zwartych (#897)
* wyszukiwanie rekordów powiązanych dla wydawnictw zwartych (#897)

202101.52
---------
* raport slotów - autor umożliwia zbieranie "do N slotów" dla autora (b/n),
* konfigurowane wartości domyślne dla daty w formularzach (#947)
* wyszukiwanie pełnotekstowe uwzględnia myślniki (#851)
* poprawne wyszukiwanie po polu "Licencja OpenAccess ustawiona" (#934)
* możliwość wyszukiwania po polu "charakter formalny ogólny" (#933)
* poprawne wyszukiwanie w polach numerycznych (#913)
* możliwość powiązania zewnętrznej bazy danych również dla wydawnictwo zwartych (#935)
* poprawne działanie funkcjo restartującej hasło na produkcji (#936)

202012.51
---------
* zbieranie slotów dla autora za pomocą algorytmu plecakowego (b/n),
* ukrywanie statusów korekt w multiwyszukiwarce (#942),
* ukrywanie statusów korekt przy obliczaniu slotów -
  liczenie punktów za sloty w zależności od ustawienia statusu korekty (#945),
* ukrywanie wybranych statusów korekt w rankingach (#946),
* ukrywanie wybranych statusów korekt w raortach (#943),
* ukrywanie wybranych statusów korekt w API (#946),

202011.50
---------
* prawidłowe obliczanie punktów dla tłumaczeń (#931)

202011.49
---------
* podczas obliczania slotów dla liczby autorów z dyscypliny nie uwzględniaj autorów
  z odznaczonym polem "afiliuje" (#927)
* pole "pseudonim" dla autora (#921)
* wyświetlanie wewnętrznego ID autora na podstronie autora (b/n),
* możliwość otwarcia strony autora po ID za pomocą linku /bpp/autor/{ID}/ (b/n),
* prawidłowe obliczanie punktów dla referatów (#930)

202009.48
---------
* umożliwiaj konfigurację domyślnych wartości parametrów dla
  wybranych formularzy oraz wyświetlanie dowolnego tekstu HTML przed i
  po formularzach (#922)
* zamiast zbierać prace na minimalny slot, zbieraj prace do osiągnięcia maksymalnego
  slotu: usunięta zostaje opcja "minimalny slot" oraz "wyświetlaj prace poniżej minimalnego
  slotu", dodana zostaje opcja "maksymalny slot" (#917)
* licz sloty dla roku 2021 jak dla roku 2020 (#925)
* poprawka błędu edycji wydawców (#925)

202008.47
---------

* ograniczaj wyświetlanie do 20 tys rekordów przy braku zapytania w wyszukiwarce (b/n),

202008.46
---------

* możliwość przypisywania grantów rekordom (b/n),
* możliwość przypisywania elementów repozytoryjnych (plików) rekordom (b/n),

202008.45
---------

* backend cache zmieniony na django-redis-cache (wcześniej: pylibmc) (b/n),

202008.43
---------

* lepszy silnik notyfikacji dynamicznych (channels+ASGI+uvicorn) (b/n),
* import danych o dyscyplinach autorów z plików DBF (b/n),
* dodatkowe pola "rodzaj autora" oraz "wymiar etatu" (b/n),
* import danych grantów, nr odbitek i liczne drobne poprawki importu DBF (b/n),

202007.41
---------

* poprawione regenerowanie opisów bibliograficznych (#875)
* prawidłowe renumerowanie kolejności z poziomu polecenia nawet w sytuacji gdy afiliacja
  autora przypisana jest niepoprawnie (afiliuj="tak" przy obcej jednostce) (b/d)
* prawidłowe wyszukiwanie wydawnictw nadrzędnych w module redagowania (#882)

202006.40
---------

* poprawne importowanie niektórych akcentowanych znaków z plików DBF (n/d),
* zamień pola "szczegóły" i "informacje" przy imporcie (#857)
* opcjonalna walidacja pola "Afiliowana" przy przypisaniu autora do rekordu
  za pomocą zmiennych środowiskowych (n/d),
* dodatkowe pole "nie eksportuj do API" dla rekordów wydawnictw zwartych, ciągłych,
  patentów, prac doktorskich i habilitacyjnych.

202006.39
---------

* prace habilitacyjne i patenty w API (#859)
* nie importuj pola źródła 200C w przypadku importu DBF dla prac z redaktorami (#797)
* przy imporcie z plików DBF ustawiaj to samo ID jednostki co po stronie DBF (n/d)
* przy imporcie plików DBF poprawnie importuj wartości niepoprawnie zapisane w DBF (#876)
* upoważnienie PBN - pole (#840)

202006.38
---------

* procedura serwerowa do wycinania wartości pola ISBN z pola "Uwagi" (#796)
* poprawione wycinanie numerów i suplementów (#845)
* lepszy opis dla rekordów z wydawnictwem nadrzędnym - oznaczenie wydania dla rozdziałów (#843)
* charakter formalny dostaje nowe pole - charakter ogólny (książka/rozdział/artykuł) (wynika z #843)
* wyświetlaj informacje o czasie udostępnienia OpenAccess w API (#861)

202005.37
---------

* eksport promotora w pracach doktorskich w API (b/n),
* pole "oznaczenie wydania" (#843),
* poprawnie importuj ilość stron dla monografii dla plików DBF (#847),
* lepsze przypisywanie grup punktowych w imporcie DBF (b/n),

202005.36
---------

* poprawki importu rekordów z plików DBF oraz procedur wycinających
  dane na temat numeru i tomu (#845)
* import z plików DBF zachowuje oryginalne numery ID (b/n),
* eksport prac doktorskich w API (b/n),

202004.35
---------

* filtrowanie po roku publikacji w API (#844)

202004.34
---------

* zmiany nazw kolumn raportu ewaluacji (#830)
* dodatkowe pola metryczki rekordu oraz sumowanie w XLS w raportach slotów
  (#829),
* rozszerzanie listy źródeł przy imporcie plików DBF (b/n),
* nie wymagaj wydziału przy eksporcie do PBN - eksportuj całą uczelnię (#828)
* wygodniejsze sortowanie wydziałów w module redagowania oraz możliwość
  ręcznego sortowania jednostek (#802)

202004.33
---------

* eksport pola public-uri do PBNu eksportuje w pierwszej kolejnosci adres publiczny,
  w drugiej - płatny, adresy generowane na podstawie PubMedID nie są już wysyłane (#834)
* eksportowane jest pole book-with-chapters do PBN (#824)
* nie usuwaj spacji przed kropką przy imporcie publikacji (b/n),

202004.32
---------

* filtrowanie po charakterze formalnym w API (b/n)

202004.31
---------

* filtrowanie po dacie w REST API dla obiektów Autor,
  Wydawnictwo_Ciagle, Wydawnictwo_Zwarte, Zrodlo (b/n),
* dodatkowe pola ISSN / EISSN w REST API (b/n),
* eksportuj identyfikator ORCID autora do PBN, datę modyfikacji rekordu
  dla wydawnictw, datę dostępu dla OpenAccess (#824)

202003.29
---------

* Django 3.0 (b/n),
* REST API (b/n),
* narzędzie do dzielenia "podwójnych" wydawców po imporcie (b/n)

202003.27
---------

* napraw błąd importu pliku dyscyplin uniemożliwiający zmianę zaimportowanych już
  dyscyplin (b/n),
* drobne poprawki zachowania admina (nie wyświetlaj listy tabel z importem danych z
  pliku DBF jeżeli nie są zaimportowane, nie pozwalaj na usuwanie własnego konta,
  nie pozwalaj na usunięcie ostatniego konta superużytkownika, nie wyświetlaj
  komunikatu błędu gdy próbujemy dopisać rekord z powiązaniem autora do rekordu
  w sytuacji gdy nie podano jednostki) (b/n),

202003.26
---------

* wyświetlaj również wydawnictwa zwarte w raporcie slotów - ewaluacja (b/n),
* skracaj listę autorów gdy powyżej 100 znaków dla widoku HTML w raporcie slotów - ewaluacja (b/n),
* umożliwiaj filtrowanie raportu slotów - ewaluacja (b/n),

202003.25
---------

* wyświetlaj kolumnę z ilością wszystkich autorów w raporcie slotów - autor (#807)
* wyświetlaj mniejsze czcionki w raporcie slotów - autor
* raport slotów - ewaluacja (#809)

202003.23
---------

* wyświetlaj dodatkowe kolumny w raporcie slotów - autor (#807)

202003.22
---------

* regresja: błędy raportu slotów (#811)

202003.21
---------

* regresja: wyszukuj po polu "Dostęp dnia (wolny dostęp)" (#815)
* regresja: wyszukuj prawidłowo prace w obcych jednostkach (#816) + poprawki
  wydajności,
* ustalaj obcą jednostkę w uczelni przy imporcie (b/d),
* nie pozwalaj na ustalenie nie-obcej jednostki jako obcej dla uczelni (b/d),
* regresja: wyszukuj prawidłowo prace w obcych jednostkach (#816)
* poprawnie wyszukuj przypisania autora do dyscypliny w multiwyszukiwarce (b/d),
* mniejsza ilość zapytań o grupy użytkownika w redagowaniu (b/d),

202003.20
---------

* ORCID i PBN ID w raport slotów - uczelnia (#808),
* wyświetlanie numeru PBN ID na stronie autora (b/n),
* licz sloty tylko dla autorów afiliowanych (#810)
* w przypadku zaznaczenia opcji 'afiliuje' przy obcej jednostce, zgłaszaj błąd (b/n),
* operatory do multiwyszukiwarki: afiliuje TAK/NIE, dyscyplina ustawiona TAK/NIE,
  obca jednostka TAK/NIE (umożliwia zapytania z #816, #817, #814, #815)

202003.19
---------

* import pliku DBF nie dzieli tytułu po znaku równości na oryginalny i pozostały (b/n),
* autorom przypisanym do rekordów patentów można przypisywać dyscypliny naukowe (b/n),
* aktualizacja pakietów zależnych z przyczyn bezpieczeństwa (bleach3) (b/n),
* eksport PBN: eksportuj prace z PK większym, niż 5 (poprzedni warunek: większe lub równe) (b/n),
* aliasy wydawców (b/n),
* tworzenie źródła wprost z formularza dodawania wydawnictwa ciągłego w module redagowania (#800),
  tak utworzone źródło dostanie zawsze rodzaj źródła równy: periodyk,
* wyświetlanie PubMed ID, PMC ID oraz ISBN i ISSN w opisie bibliograficznym (#801, #799),

202002.18
---------

* wyświetlaj lata dla raportu zerowego w jednej kolumnie (#812)
* nie uwzględniaj wpisów dyscyplin bez punktacji w raporcie zerowym (#785)
* umożliwiaj oddzielne zarządzanie widocznością raportu slotów zerowych (#785)
* nie dodawaj pola 103 do konferencji przy imporcie DBF (#794)
* akceptuj podwójnych autorów przy imporcie DBF (#792)
* poprawnie rozpoznawaj formę główną autora (#806)
* poprawnie importuj z plików DBF numery stron i pola szczegółów (#795, #796)

202002.17
---------

* umożliwiaj poprawne wylogowanie użytkownika z systemu, bez wyświetlania strony błędu (#714)
* nie zgłaszaj awarii dla eksportu XLS pustych skoroszytów dla raportu slotów - autor (#782)
* umożliwiaj poprawne resetowanie hasła użytkownika (#675)
* napraw błąd w wyszukiwaniu pełnotekstowym (#683)

v202002.16
----------

* raport slotów "zerowy", pokazujący autorów z zadeklarowaną dyscypliną, ale bez prac w tej
  dyscyplinie (#785)

v202002.15
----------

* rezygnacja z Pipfile na rzecz pip-tools
* rezygnacja z Raven na rzecz sentry-sdk
* zmiany eksportu do PBN:

  * wyrzucono pole eksport-pbn-size,
  * wyrzucono pole employed-in-unit dla autorów/redaktorów,
  * wykasowano pola "other-contributors", generują się wszyscy autorzy (również obcy)
  * dla książek pod redakcją generują się wszyscy redaktorzy oraz nie generują się autorzy rozdziałów
  * dla książek i rozdziałów generują się tylko publikacje z punktacją PK>5

v202001.14
----------

* poprawiony błąd związany z obliczaniem punktów dla dyscyplin z dziedziny nauk humanistycznych, etc.
  (sentry:BPP-UP-8Q)

v202001.12
----------

* poprawne obliczanie punktacji dla dyscyplin z dziedziny nauk humanistycznych, społecznych i teologicznych (#775)
* mniejszy rozmiar pliku wynikowego (whl)
* usunięto minimalną ilośc slotów dla raportu slotów - uczelnia (#781)
* rozbijanie raportu slotów - uczelnia na jednostki i wydziały (#784)

v201911.9
---------

* import baz danych z systemów zewnętrznych
* równolegle działające polecenie rebuild_cache, przyspieszające czas nocnej przebudowy cache bazy

v201910.7
---------

* niezwykle eleganckie tabele w XLS wraz z opisem (#766)
* bardziej widoczny indeks wydawców w module redagowania (#771)
* uwzględniaj prace posiadające 100 punktów PK dla "Monografia – wydawnictwo poziom I" (#770)
* klikalny tytuł pracy w raporcie slotów (#772)
* raport slotów z możliwością podania parametru poszukiwanej ilości slotów i opcjonalnym
  wyświetlaniem autorów poniżej zadanego slotu (#765)
* nie licz slotów dla prac wieloośrodkowych (typ MNiSW/MEiN=PW) (#761)
* zmiana nazwy kolumny "PKdAut" na "punkty dla autora" (#754)
* wyświetlaj punkty PK w raporcie autora (#769)
* nie kopiuj linku do płatnego dostępu w opcji "tamże" (#722)
* konfigurowalne "Rozbij punktację na jednostki" dla rankingu autorów (#750)

v201910.6
---------

* możliwość niezależnego ustalenia opcji widoku raportów "raport slotów - uczelnia" i "raport slotów - autor"
* poprawne kasowanie wcześniej zapisanej informacji o slotach i punktach
* poprawki pobierania arkuszy XLS dla raportu slotow - poprawnie eksportowane liczby, szerokośc kolumn

v201910.5a0
-----------

* raport slotów - uczelnia: eksport do XLS bez tagów HTML, możliwość filtrowania
* usunięto zdublowaną tabelę dla raportu slotów autorów

v201910.1a0
-----------

* tabelki z możliwością eksportu XLS - punkty i sloty dla autorów i uczelni

v201909.0001-alpha
------------------

* przełączenie na system wersji numerowanych od kalendarza (calver, #746)

* opcje wyświetlania raportu slotów i tabelki z punktacją slotów na podstronie pracy -- dla wszystkich,
  tylko dla zalogowanych lub dla nikogo.

* nie licz slotów dla punkty PK = 0 dla wydawnictw ciągłych

* możliwość umieszczenia dowolnego tekstu przed i po liście autorów w opisie bibliograficznym

1.0.31
------

* drobne poprawki zmiany nazwy raportu slotów

1.0.31-dev3
-------------

* w przypadku braku wpisanej wartości w pole "liczba znakow wydawniczych", do paczek dla PBN
  wrzucaj wartosc 0 (zero). Pole wg Bibliotekarzy nie jest już wymagane przez Ministerstwo,
  zas oprogramowanie PBN na ten moment jeszcze tego pola wymaga.

* kolumna z PK dla raportu slotów

* poprawiono matchowanie autorów dla importu dyscyplin w sytuacji szukania autora po tytule
  naukowym (#742)

1.0.31-dev2
-------------

* polecenie do automatycznego przypisywania dyscyplin - dla autorów, którzy mają przypisaną tylko
  jedną dyscyplinę dla danego roku, można za pomocą polecenia command-line przypisać z automatu
  tą dyscyplinę do wszystkich ich prac, które nie mają przypisanej dyscypliny

* raport slotów

1.0.31-dev1
-------------

* nie wymagaj ilości znaków wydawniczych od rozdziałów i monografii przy eksporcie dla PBN

* połącz 3 pola obiektu Charakter Formalny: "Artykuł w PBN", "Rozdział w PBN", "Ksiażka w PBN" w jedno
  pole "Rodzaj dla PBN", które to może przyjąć jedną z 3 powyższych wartości; wcześniejszy model umożliwiał
  eksportowanie jednego charkateru formalnego jako rozdział bądź książka, jednakże po usunięciu
  warunku dotyczącego liczby znaków wydawniczych, niektóre rekordy mogłyby w takiej sytuacji być
  eksportowane więcej, niż jeden raz.

* konfigurowalne podpowiadanie dyscypliny autora (w sytuacji gdy ma tylko jedną na dany rok) podczas
  przypisywania autora do rekordu publikacji; zmiana konfiguracji za pomoca obiektu 'Uczelnia' (#728),

* poprawka błędu gdzie dla autorow z dwoma dyscyplinami była podpowiedź dyscypliny a nie powinno jej byc
  (#729)

* rozbicie pliku test_admin.py na klika mniejszych celem usprawnienia efektywności testow uruchamianych
  za pomocą pytest-xdist (na wielu procesorach)


1.0.31-dev0
-------------

* liczenie punktów i slotów dla wydawnictw zwartych

* "charakter dla slotów" dla charakteru formalnego

* informacja o możliwości (lub niemożliwości) policzenia punktów dyscyplin dla rekordu w panelu administracyjnym

1.0.30-dev3
-------------

* "rozbieżności dyscyplin" - moduł umożliwiający podejrzenie różnic pomiędzy dyscyplinami
  przypisanymi na dany rok dla autora a dyscyplinami przypisanymi do rekordów

* lepsza obsługa kolejki cache

1.0.30-dev2
-------------

* poprawki drobnych błędów

1.0.30-dev1
-------------

* drobne poprawki

1.0.30-dev0
-------------

* poprawki

1.0.29-dev3
-------------

* wyświetlanie informacji o punktacji dla dyscyplin i slotach

1.0.29-dev2
-----------

* powiązanie rekordu publikacji z autorem pozwala również wprowadzić informację
  na temat dyscypliny

1.0.29-dev1
-----------

* umożliwiaj konfigurację opcji "pokazuj liczbę cytowań na stronie autora",

* poprawione kasowanie patentów

* poprawne wyszukiwanie po dyscyplinach

* procent odpowiedzialności za powstanie pracy wyświetla się na podstronie pracy


1.0.28
------

* poprawki importu dyscyplin: lepsze dopasowywanie autora z jednostką z pliku wejściowego
  do danych w systemie

* poprawiony błąd importu dyscyplin utrudniający poprawne wprowadzenie pliku do bazy

* możliwość wyszukiwania przez ORCID w multiwyszukiwarce oraz w globalnym wyszukiwaniu

* numer ORCID staje się unikalny dla autora


1.0.27
------

* dyscyplina główna i subdyscyplina wraz z procentowym udziałem

* możliwość identyfikowania autorów po ORCID przy imporcie dyscyplin

* nowy plik z przykładowymi informacjami dla importu dyscyplin,

* możliwość przypisywania rodzaju kolumny przy imporcie dyscyplin,

* możliwosć wprowadzania procentowego udziału odpowiedzialności autora w powstaniu
  publikacji

* Django 2.1

1.0.26
------

* wyszukiwanie zaawansowane: gdy podane jest imię i nazwisko ORAZ np jednostka lub
  typ autora, wyniki będą poprawne tzn związane ze sobą (autor + afiliacja), a nie
  tak jak do tej pory pochodzące z dowolnych powiązań autora do rekordu,

* nowy operator dla pól autor, jednostka, wydział, typ odpowiedzialności "równy+wspólny",
  który zachowuje się tak, jak do tej pory zachowywał się operator "równy". Gdy chcemy
  znaleźć rekordy wspólne opublikowane przez dwóch lub więcej autorów/jednostki/wydziały,
  gdy chcemy znaleźć rekordy, które np. mają typ autora "redaktor" i "tłumacz" - korzystamy
  z tego operatora; gdy chcemy znaleźć prace autora afiliowane na konkretną jednostkę,
  korzystamy z operatora "równy"

* kosmetyka wyświetlania szczegółów rekordu: pole "Zewnętrzna baza danych", justowanie
  nagłówków do prawej strony.

* wyszukiwanie: prawidłowo obsługuj zapytania o rekordy zarejestrowane
  w kilku zewnętrznych bazach danych

1.0.27-alpha
------------------------------

* obsługa punktacji SNIP

1.0.25
------

* mniejsza wielkość tytułu na wydruku z opcji "Wyszukiwanie" (#632)

* tytuł naukowy autora nie wchodzi do elementu opisu bibliograficznego rekordu
  (#633)

* możliwość określania drzewiastej struktury dla charakterów formalnych - określanie
  charakterów nadrzędnych, wraz z możliwością wyszukiwania z uwwzględnieniem
  tej struktury (#630)

* możliwość określenia dla rankingu autorów, aby wybierane były jedynie prace
  afiliowane na jednostkę uczelni (= czyli taką, która ma zaznaczone "skupia
  pracowników" w module Redagowanie - Struktura) (#584)

1.0.23
------

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

* możliwość podglądania do 100 rekordów wydawnictw zwartych i ciągłych powiązanych
  do konferencji

* możliwość jednoczasowej edycji do 100 rekordów powiązań autora i jednostki w module
  redagowanie, przy edycji obiektu Jednostka

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
