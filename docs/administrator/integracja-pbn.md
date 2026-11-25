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


## Dopasowanie autorów do osób z PBN { #dopasowanie-autorow-do-osob-z-pbn }

Autor w BPP, który nie ma **odpowiednika w PBN** (puste pole „PBN UID”)
ani numeru ORCID, trafia do PBN tylko jako imię i nazwisko, a jego
oświadczenia nie są wysyłane. Tacy autorzy powstawali m.in. w importerze
publikacji (od tej wersji importer sam szuka odpowiednika — patrz
[Importer publikacji](../redaktor/importer-publikacji.md)). Dla autorów,
którzy już są w bazie, służy komenda `dopasuj_autorow_do_pbn`.

Komenda pracuje wyłącznie na **lokalnej kopii danych PBN** (nie łączy się
z PBN), więc najpierw pobierz aktualne dane osób i publikacji z PBN.

### Podgląd (niczego nie zmienia)

``` shell
bpp-manage.py dopasuj_autorow_do_pbn --raport /tmp/autorzy-pbn.xlsx
```

To tryb domyślny — to samo robi jawne `--dry-run`. Komenda bada wszystkich
autorów bez odpowiednika, wypisuje podsumowanie i zapisuje raport. Bez
`--raport` plik `dopasowanie_autorow_pbn_<data>.xlsx` powstaje w bieżącym
katalogu; rozszerzenie `.csv` daje plik CSV (średnik, UTF-8).

### Zapis

``` shell
bpp-manage.py dopasuj_autorow_do_pbn --zapisz --uzytkownik jkowalski --raport /tmp/autorzy-pbn-zapis.xlsx
```

Zapisywane są **tylko** wskazania o poziomie „pewne”. Każdy zapis zostawia
wpis w historii autora (*„Powiązano z naukowcem PBN … (dopasowanie autorów
bez odpowiednika w PBN: …)”*) i wersję, do której można wrócić przyciskiem
„Historia” na stronie autora. `--uzytkownik` wskazuje, komu przypisać
zmiany; bez niego trafiają na konto systemowe. Istniejący odpowiednik
nigdy nie jest nadpisywany — autorzy, którzy go mają, w ogóle nie są badani.

### Skąd komenda wie, kto jest kim

Dwa niezależne źródła:

1. **Po autorach** — numer ORCID autora wśród osób z PBN oraz imię
   i nazwisko wśród osób zatrudnionych w uczelni. Uwzględniane są poprzednie
   nazwiska autora, człony nazwisk dwuczłonowych, drugie imiona i brak
   polskich znaków.
2. **Po publikacjach** — dla prac autora, które mają odpowiednik w PBN,
   komenda bierze listę autorów z kopii publikacji PBN (z identyfikatorami
   osób) i znajduje na niej tego autora po nazwisku i imieniu (także
   inicjale); gdy pasuje kilka osób, rozstrzyga kolejność na liście autorów.

| Poziom pewności | Kiedy | Zapis przy `--zapisz` |
|---|---|---|
| **pewne** | ORCID wskazuje jedną osobę **albo** imię i nazwisko oraz publikacje wskazują tę samą osobę | tak |
| **prawdopodobne** | tylko jedno źródło: samo imię i nazwisko albo same publikacje | nie |
| **sprzeczne** | źródła (albo różne prace) wskazują różne osoby | nie |
| **możliwy duplikat autora** | wskazana osoba PBN jest już przypisana do innego autora BPP albo wskazuje ją kilku autorów bez odpowiednika | nie |
| **brak** | żadne źródło niczego nie wskazało | nie |

Wskazanie nie jest „pewne” także wtedy, gdy ORCID autora nosi w PBN kilka
osób, osoba jest w PBN oznaczona jako usunięta albo nie ma jej w lokalnej
kopii danych PBN (uwaga w raporcie mówi, żeby pobrać dane osób i uruchomić
komendę ponownie).

### Raport

Jeden wiersz na autora, posortowane od „pewne” do „brak”. Kolumny:
„ID autora”, „Nazwisko”, „Imiona”, „ORCID”, „Aktualna jednostka”,
„Poziom pewności”, „Proponowany PBN UID”, „Osoba w PBN”, „Źródła dowodu”
(np. `ORCID: 5e70…; publikacje: 5e70… (zgodnie w 4 pracach)`), „Liczba
zgodnych prac”, „Uwagi” (powód, dla którego nie ma pewności: inni
kandydaci, autor, do którego osoba jest już przypisana) i „Zapisano”
(tak/nie).

Wiersze „prawdopodobne” i „sprzeczne” rozstrzyga się ręcznie: w module
redagowania otwórz autora o podanym ID i wybierz osobę w polu „PBN UID”.
„Możliwy duplikat autora” to sprawa dla
[scalania duplikatów autorów](../redaktor/duplikaty.md) — po scaleniu
zostaje jeden autor z odpowiednikiem.

### Zawężanie

| Opcja | Znaczenie |
|---|---|
| `--uczelnia ID` | w instalacji z wieloma uczelniami (wymagane): tylko autorzy z zatrudnieniem w jednostkach tej uczelni; po imieniu i nazwisku szuka wśród osób z jej instytucji PBN |
| `--rok-od R`, `--rok-do R` | tylko autorzy, którzy mają prace z podanych lat |
| `--limit N` | najwyżej N autorów (alfabetycznie) — do próby |
| `--pewne-od-prac N` | uznaj za „pewne” także wskazanie z samych publikacji, jeśli ta sama osoba wynika zgodnie z co najmniej N prac (domyślnie wyłączone) |

### Bezpieczna kolejność

1. Zrób kopię bazy danych.
2. Pobierz aktualne dane osób i publikacji z PBN.
3. Uruchom podgląd i przejrzyj raport — zwłaszcza wiersze „pewne”.
4. Uruchom z `--zapisz` (z tymi samymi opcjami zawężenia).
5. Rozstrzygnij ręcznie resztę raportu, a prace autorów, którzy dostali
   odpowiednik, wyślij do PBN ponownie.


## Kody błędów

Podczas synchronizacji z PBN mogą wystąpić m.in. następujące wyjątki:

- PraceSerwisoweException: po stronie PBN trwają prace serwisowe - zamiast odpowiedzi API
  w formacie JSON, serwer PBN zwraca stronę błędu z pszczółkami,
