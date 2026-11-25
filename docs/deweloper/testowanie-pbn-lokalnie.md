# Testowanie PBN lokalnie

Jak na własnej maszynie, na kopii bazy klienta, dostać działający token PBN
i przetestować pobieranie albo wysyłkę na prawdziwym PBN — bez ręcznego
przeklejania kodów.

!!! danger "To jest prawdziwy PBN"
    Token, który tu uzyskujesz, działa na **produkcyjnym** profilu instytucji
    w PBN. Wysłana praca naprawdę tam trafi, a wycofane oświadczenia naprawdę
    znikną. Narzędzia z tej strony wstrzymują automaty (patrz
    [Bezpiecznik](#bezpiecznik)), ale ręczne „Zapisz i wyślij do PBN” robi
    dokładnie to, co mówi.

## Najkrótsza ścieżka

```bash
# 1. Lokalna instancja na kopii bazy + konfiguracja PBN i token z serwera.
#    HOST to alias SSH serwera (z bpp-deploy), LOGIN to Twoje konto w BPP.
uv run run-site run --from-dump ~/Backups/<katalog>/<plik-backupu> \
    --get-pbn-token-from LOGIN@HOST

# 2. W drugim terminalu, w tym samym checkoucie:
uv run bin/pbn-zaloguj-lokalnie.py --user LOGIN
```

Krok 2 kończy się jednym zdaniem, np.:

```text
OK: token PBN użytkownika LOGIN działa — https://pbn.nauka.gov.pl odpowiada
(liczba publikacji w profilu instytucji: 12345).
```

Co się dzieje po drodze:

- `--get-pbn-token-from` pobiera z serwera po SSH adres API PBN, nazwę
  i token aplikacji oraz token PBN użytkownika `LOGIN`
  ([dlaczego to potrzebne](#klucz-szyfrowania)).
- `pbn-zaloguj-lokalnie.py` najpierw sprawdza, czy zapisany token działa.
  Jeśli tak (token z serwera jest ważny) — **nie musisz się nigdzie logować**.
- Jeśli nie — otwiera okno przeglądarki, przechodzi przez „autoryzuj PBN API”
  i czeka, aż **sam zalogujesz się w PBN**. Hasła do PBN skrypt nie zna i nie
  wpisuje. Profil przeglądarki jest trwały (`~/.cache/bpp/pbn-profil`), więc
  dopóki sesja w PBN żyje, kolejne uruchomienia przechodzą bez logowania.

Lokalne konto `LOGIN` musi istnieć w odtworzonej bazie. `run-site` tworzy
konto `admin`; skrypt domyślnie loguje właśnie jego (`--user admin`) i wtedy
token PBN zostaje zapisany adminowi.

Pobieranie z serwera nie zatrzymuje startu `run-site`, a `run-site` pokazuje
wyjście hooków tylko przy ich awarii — o nieudanym pobraniu (brak VPN, zła
nazwa hosta) dowiesz się w kroku 2, który powie wprost, czego brakuje. To
samo można wtedy zrobić bez restartu:

```bash
uv run bin/pbn-zaloguj-lokalnie.py --user LOGIN --konfiguracja-z HOST
```

## Jak działa przechwycenie powrotu

PBN po zalogowaniu odsyła przeglądarkę na adres zwrotny **zapisany przy
aplikacji w PBN**, czyli na serwer klienta:
`https://<serwer klienta>/pbn_api/callback?ott=<kod>`. Skrypt zatrzymuje to
jedno żądanie, zanim wyjdzie z przeglądarki, i zastępuje je przekierowaniem
na ten sam adres lokalnej instancji (`http://localhost:<port>/pbn_api/callback?ott=…`).
Autoryzację kończy lokalny BPP swoim zwykłym widokiem. Serwer klienta
niczego nie dostaje — kod jest jednorazowy i serwer mógłby go zużyć.

Obsługiwane są też aliasy callbacku (literówki w rodzaju `kalbak`), powrót
formularzem POST oraz powrót z `ott` na zupełnie inny adres; w tym ostatnim
przypadku kod jest wymieniany bezpośrednio, jak w trybie `--ott`.

Przechwycenie używa protokołu CDP przeglądarki Chromium, a nie
`route()` Playwrighta — `route()` nie widzi kolejnych skoków przekierowania,
a powrót z PBN jest właśnie przekierowaniem. Szczegóły i ostrzeżenie:
`src/pbn_api/logowanie_lokalne.py`.

Przeglądarkę instalujesz raz: `make playwright-install`.

## Klucz szyfrowania

`Uczelnia.pbn_app_token` i `BppUser.pbn_token` są szyfrowane kluczem
`DJANGO_BPP_FIELD_ENCRYPTION_KEY`. W kopii bazy z serwera leżą szyfrogramy
zrobione kluczem serwera; lokalny klucz jest inny, więc oba pola **czytają
się jako puste** (bez wyjątku — w logu pojawia się ostrzeżenie
„Nie udało się odszyfrować EncryptedTextField”, a `manage.py check` zgłasza
`bpp.W103`). Bez tokenu aplikacji nie da się wymienić kodu z PBN na token.

Dwa wyjścia:

1. **Przenieś wartości, nie klucz** (zalecane) — `--get-pbn-token-from` albo
   `--konfiguracja-z`. Serwer odszyfrowuje je u siebie i podaje potokiem SSH,
   lokalny zapis szyfruje je lokalnym kluczem. Działa z serwerem na dowolnej
   wydanej wersji BPP (po stronie serwera to zwykłe `manage.py shell -c`).
   Sekrety nie trafiają na ekran, do logów ani do plików.

    Ręcznie, gdy do serwera wchodzisz inaczej niż `ssh HOST`:

    ```bash
    uv run python src/manage.py pbn_konfiguracja_z_serwera \
        --user LOGIN --wypisz-zdalne-polecenie
    # wypisane polecenie uruchom na serwerze, a jego wyjście podaj potokiem do:
    uv run python src/manage.py pbn_konfiguracja_z_serwera --stdin
    ```

2. **Uruchom lokalną instancję z kluczem serwera** — jeżeli go masz:

    ```bash
    export DJANGO_BPP_FIELD_ENCRYPTION_KEY='<klucz z .env serwera>'
    uv run run-site run --from-dump …
    ```

    Zmienna musi być ustawiona także w terminalu, w którym uruchamiasz
    `bin/pbn-zaloguj-lokalnie.py`. Klucza nie zapisuj w repozytorium.

## Bezpiecznik

Kopia bazy klienta przynosi ze sobą **kolejkę eksportu do PBN**, a kod ma
automaty, które wysyłają bez pytania. Z prawdziwym tokenem oznaczałoby to
prawdziwą wysyłkę z Twojej maszyny. Chronią przed tym dwie warstwy.

**1. Przełącznik `DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY`** — w
`settings/local.py` domyślnie `1` (każda lokalna instancja: run-site,
`runserver`, dev-owy docker compose); na produkcji i w testach wyłączony.
Wstrzymuje:

| Automat | Co robi normalnie |
|---|---|
| ponowienie po zalogowaniu (`kolejka_ponow_wysylke_prac_po_zalogowaniu`) | po zapisaniu tokenu wysyła prace czekające na autoryzację |
| watchdog kolejki (`queue_watchdog`) | co 10 minut budzi wpisy, które utknęły |
| łańcuch „następny z kolejki” (`check_and_send_next_in_queue`) | po każdej udanej wysyłce bierze kolejne wpisy |
| kosz i przywrócenie (`zakolejkuj_wycofanie`, `zakolejkuj_wysylke`) | przeniesienie pracy do kosza wycofuje jej oświadczenia w PBN |

**2. Komenda `pbn_bezpiecznik_lokalnej_kopii`** — zamyka wszystkie
niezakończone wpisy kolejki (zostają w historii z adnotacją). Uruchamia się
sama: przy każdym starcie `run-site`, przed pobraniem konfiguracji z serwera
i przed logowaniem. Ręcznie:

```bash
uv run python src/manage.py pbn_bezpiecznik_lokalnej_kopii \
    --tak-to-jest-lokalna-kopia
```

Komenda **odmawia**, gdy instancja nie wygląda na lokalną: wymaga
`DEBUG = True` oraz bazy na tej samej maszynie (`localhost` albo gniazdo
uniksowe). Flaga potwierdzenia tych warunków nie obchodzi. Gdy baza stoi
w dev-owym docker compose pod nazwą serwisu, dodaj `--lokalny-host-bazy db`.

Bezpiecznik blokuje automaty, nie funkcję. **Nadal działa** wszystko, co
klikasz świadomie: „Zapisz i wyślij do PBN” w formularzu rekordu, „wyślij
ponownie” w kolejce eksportu (także dla wpisu zamkniętego przez bezpiecznik),
komendy `manage.py pbn_*`. Narzędzia masowe (scalanie autorów, przemapowanie
źródeł) dopisują wpisy do kolejki, ale nic ich stamtąd samo nie zabierze.

Żeby lokalnie testować same automaty kolejki, uruchom instancję z
`DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY=0` — na bazie, w której nie ma
prawdziwego tokenu.

## Wariant awaryjny: ręczny kod OTT

Gdy przeglądarka z Playwrighta nie wchodzi w grę, kod można zdobyć ręcznie:

1. Otwórz **okno prywatne**, w którym **nie** jesteś zalogowany do BPP
   klienta.
2. Wejdź na adres logowania aplikacji w PBN:
   `<adres API PBN>/auth/pbn/api/registration/user/token/<nazwa aplikacji>`
   (oba człony są w adminie uczelni) i zaloguj się w PBN.
3. PBN przekieruje na serwer klienta, a ten — ponieważ nie jesteś
   zalogowany — na swoją stronę logowania. Kod zostaje w pasku adresu,
   w parametrze `next`: `…/login/?next=/pbn_api/callback%3Fott%3D<kod>`.
   Skopiuj `<kod>`.
4. Lokalnie:

    ```bash
    uv run bin/pbn-zaloguj-lokalnie.py --user LOGIN --ott <kod>
    ```

!!! warning "Nie loguj się i nie klikaj „autoryzuj” na serwerze klienta"
    Kod jest jednorazowy. Jeżeli w tej samej przeglądarce jesteś zalogowany
    do BPP klienta i w ciągu ostatnich 10 minut kliknąłeś tam „autoryzuj PBN
    API”, serwer klienta przyjmie powrót i **zużyje kod** — token trafi na
    produkcję, a nie do Ciebie. Stąd okno prywatne.

`--ott` robi to samo co `manage.py pbn_ott_na_token`, a dodatkowo uruchamia
bezpiecznik i sprawdza, czy token działa.

## Pozostałe opcje

```bash
uv run bin/pbn-zaloguj-lokalnie.py --tylko-sprawdz   # czy zapisany token działa
uv run bin/pbn-zaloguj-lokalnie.py --wymus           # loguj mimo działającego tokenu
uv run bin/pbn-zaloguj-lokalnie.py --help
```

Skrypt bierze adres strony i połączenie z bazą z pliku `.run-site-config`
działającego `run-site`, więc uruchamiaj go w tym samym checkoucie. Odmawia
pracy z adresem innym niż `localhost` / `127.0.0.1`.

Końcowe sprawdzenie to jedno zapytanie tylko-do-odczytu (pierwsza strona
publikacji profilu instytucji). Token nie jest nigdzie wypisywany.

## Gdzie to jest w kodzie

| Co | Gdzie |
|---|---|
| logowanie z przechwyceniem powrotu | `src/pbn_api/logowanie_lokalne.py`, komenda `pbn_zaloguj_lokalnie`, `bin/pbn-zaloguj-lokalnie.py` |
| przeniesienie konfiguracji z serwera | `src/pbn_api/konfiguracja_z_serwera.py`, komenda `pbn_konfiguracja_z_serwera` |
| bezpiecznik | `src/pbn_export_queue/bezpiecznik.py`, komenda `pbn_bezpiecznik_lokalnej_kopii` |
| hooki run-site | `src/django_bpp/runsite_hooks.py`, `runsite.toml` |
| test e2e na atrapie PBN | `src/pbn_api/tests/test_playwright/test_logowanie_lokalne_e2e.py` |

Mechanizm autoryzacji po stronie BPP (sesja, „oczekująca autoryzacja”)
opisuje [Pakiety klienckie PBN](pakiety-pbn.md#autoryzacja-pbn-api-na-lokalnej-instancji-przeniesienie-ott).
