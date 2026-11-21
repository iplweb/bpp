# Integracja z PBN API — dla administratora

Zwięzła lista kroków. Opis formularza pole po polu, ze zrzutami ekranu,
znajdziesz na stronie [Konfiguracja integracji z serwisami PBN](konfiguracja-pbn.md).

1.  Celem uzyskania dostępu do PBN API, należy po stronie PBN z użytkownika mającego
    rolę "Menadżer aplikacji" utworzyć aplikację o danym identyfikatorze (np. "BPP") oraz
    token dla tej aplikacji. W serwisie testowym po zalogowaniu można te dane podejrzeć
    pod adresem <https://pbn-micro-alpha.opi.org.pl/auth/pbn/api/manager/applications/0>

2.  Adres zwrotny ("callback") dla aplikacji należy ustawić jako <https://nazwa.serwera.bpp/pbn_api/callback>

3.  Identyfikator i token aplikacji należy wpisać do ustawień obiektu Uczelnia w module
    redagowania (**Struktura** → **Uczelnia** → sekcja **„PBN API”**, widoczna tylko
    dla superużytkownika)

4.  Podczas edycji powyższych ustawień należy zwrócić uwagę na adres PBN API,
    dla serwisu testowego w momencie tworzenia niniejszej dokumentacji jest to
    domyślnie <https://pbn-micro-alpha.opi.org.pl/> . Jeżeli korzystamy z wersji
    produkcyjnej to należy ten adres zaktualizować.

5.  Integrację z PBN API kontrolują dwa ustawienia obiektu "Uczelnia".

    - „Czy używać integracji z PBN?”: gdy zaznaczone, system będzie cyklicznie pobierał
      informacje z PBNu do bazy BPP; dane te można obejrzeć w module redagowania
      oraz użyć ich do ręcznego ustawiania odpowiedników PBN dla rekordów z BPP.
      Na stronie głównej pojawia się też menu **PBN**
    - „Włącz opcjonalną aktualizację przy edycji”: na stronach edycji wydawnictw
      pojawiają się przyciski „Zapisz i wyślij do PBN”. Rekord trafia do PBN
      wtedy, gdy redaktor kliknie taki przycisk. W przypadku niepowodzenia
      użytkownik dostaje adekwatny komunikat, a brak dostępności serwerów PBN
      czy prowadzone na nich prace serwisowe nie mają wpływu na edycję bazy BPP

6.  Dla integracji z PBN warto podać również konto użytkownika BPP które będzie używane
    do celów wgrywania danych na serwer - pod warunkiem, że ów użytkownik wcześniej
    zaloguje się do BPP i dokona autoryzacji swojego konta w PBN API
    (menu **PBN** → **autoryzuj PBN API** na stronie głównej).

7.  Rekordy publikacji aby były dodane do PBN muszą spełniać następujące warunki:

    - określony DOI lub strona WWW,
    - charakter formalny musi mieć określony rodzaj dla PBN,
    - język musi mieć określony odpowiednik dla PBN,
    - jednostki muszą mieć określony odpowiednik dla PBN,
    - źródło musi mieć określony odpowiednik dla PBN,
    - wydawca musi mieć określony odpowiednik dla PBN,
    - autorzy mogą lecz nie muszą mieć określony odpowiednik dla PBN,
    - autorzy powinni mieć uzupełnione numery ORCID,
    - autorzy muszą mieć przypisaną dyscyplinę naukową (w przypadku wysyłania prac z oświadczeniami).

8.  System umożliwia także wysyłanie prac **bez oświadczeń** do PBN. Takie prace są wysyłane
    do repozytorium PBN i nie zawierają informacji o dyscyplinach naukowych autorów.
    Prace bez oświadczeń wysyła się identycznie jak prace z oświadczeniami - z poziomu
    panelu Redagowania systemu BPP. Użytkownik otrzymuje informację o tym, że praca została
    wysłana bez oświadczeń.

    Możliwość wysyłki prac bez oświadczeń zależy od **konfiguracji systemu** - należy
    ją włączyć w module redagowania: **Struktura** → **Uczelnia**, sekcja **PBN API**,
    pole „Wysyłaj prace bez oświadczeń”.

## Wgrywanie wyłącznie opłat do PBN przez API

Pojedyncze rekordy:

``` shell
bpp-manage.py pbn_client upload_publication_fee pub:wydawnictwo_ciagle:{id rekordu}
```

Wszystkie rekordy:

``` shell
bpp-manage.py pbn_upload_fees
```

!!! note

    Procedura `pbn_upload_fees` w przypadku wgrywania informacji o płatnościach
    dla publikacji która nigdy nie była wcześniej wgrywana do PBN (nie posiada numeru
    PBN UID czyli "odpowiednika PBN") wgra taką pracę na serwer.


## Kody błędów

Podczas synchronizacji z PBN mogą wystąpić m.in. następujące wyjątki:

- PraceSerwisoweException: po stronie PBN trwają prace serwisowe - zamiast odpowiedzi API
  w formacie JSON, serwer PBN zwraca stronę błędu z pszczółkami,
