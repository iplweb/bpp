Integracja z PBN API
====================

#. Celem uzyskania dostępu do PBN API, należy po stronie PBN z użytkownika mającego
   rolę "Menadżer aplikacji" utworzyć aplikację o danym identyfikatorze (np. "BPP") oraz
   token dla tej aplikacji. W serwisie testowym po zalogowaniu można te dane podejrzeć
   pod adresem https://pbn-micro-alpha.opi.org.pl/auth/pbn/api/manager/applications/0

#. Adres zwrotny ("callback") dla aplikacji należy ustawić jako https://nazwa.serwera.bpp/pbn_api/callback

#. Identyfikator i token aplikacji należy wpisać do ustawień obiektu Uczelnia w module
   "Redagowanie" (Redagowanie -> Struktura -> Uczelnia -> zakładka "PBN API")

#. Podczas edycji powyższych ustawień należy zwrócić uwagę na adres PBN API,
   dla serwisu testowego w momencie tworzenia niniejszej dokumentacji jest to
   domyślnie https://pbn-micro-alpha.opi.org.pl/ . Jeżeli korzystamy z wersji
   produkcyjnej to należy ten adres zaktualizować.

#. Integrację z PBN API kontrolują dwa ustawienia obiektu "Uczelnia".

   - "integracja z PBN API": gdy zaznaczone, system będzie cyklicznie pobierał
     informacje z PBNu do bazy BPP; dane te można obejrzeć w module redagowania
     oraz użyć ich do ręcznego ustawiania odpowiedników PBN dla rekordów z BPP
   - "aktualizuj rekordy w PBN na bieżąco": to ustawienie sprawia, że po zapisywaniu
     rekordów w BPP są one na bieżąco wysyłane do PBN. W chwili tworzenia niniejszej
     dokumentacji ta opcja może nieco spowolnić zapisywanie rekordów w module redagowania,
     gdyż system każdorazowo wysyła dane do PBN i czeka na potwierdzenie. W przypadku
     niepowodzenia użytkownik dostaje adekwatny komunikat, ale brak dostępności serwerów
     PBN czy prowadzone na nich prace serwisowe nie powinien mieć wpływu na edycję bazy
     BPP

#. Dla integracji z PBN warto podać również konto użytkownika BPP które będzie używane
   do celów wgrywania danych na serwer - pod warunkiem, że ów użytkownik wcześniej
   zaloguje się do BPP i dokona autoryzacji swojego konta w PBN API.

#. Rekordy publikacji aby były dodane do PBN musza spełniać następujące warunki:

   - określony DOI lub strona WWW,
   - charakter formalny musi mieć określony rodzaj dla PBN,
   - język musi mieć określony odpowiednik dla PBN,
   - jednostki muszą mieć określony odpowiednik dla PBN,
   - zrodlo musi mieć okreslony odpowiednik dla PBN,
   - wydawca musi mieć określony odpowiednik dla PBN,
   - autorzy mogą lecz nie muszą mieć określony odpowiednik dla PBN,
   - autorzy powinni mieć uzupełnione numery ORCID.

Kody błędów
-----------

Podczas synchronizacji z PBN mogą wystąpić m.in. następujące wyjątki:

* PraceSerwisoweException: po stronie PBN trwają prace serwisowe - zamiast odpowiedzi API
  w formacie JSON, serwer PBN zwraca stronę błędu z pszczółkami,
