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
# 1. Lokalna instancja na backupie bazy + konfiguracja PBN i token z serwera.
#    HOST to alias SSH serwera (z bpp-deploy), LOGIN to Twoje konto w BPP.
uv run bin/run-site-z-backupu.py ~/Backups/<katalog>/<plik-backupu> \
    --get-pbn-token-from LOGIN@HOST

# 2. W drugim terminalu, w tym samym checkoucie:
uv run bin/pbn-zaloguj-lokalnie.py --user LOGIN
```

Krok 2 kończy się jednym zdaniem, np.:

```text
OK: token PBN użytkownika LOGIN działa dla uczelni XYZ — https://pbn.nauka.gov.pl
odpowiada (liczba publikacji w profilu instytucji: 12345).
```

Co się dzieje po drodze:

- `run-site-z-backupu.py` przyjmuje backup w dowolnym formacie
  ([szczegóły](#backup-w-formacie-katalogowym)) i uruchamia `run-site run`
  z resztą argumentów.
- `--get-pbn-token-from` pobiera z serwera po SSH adres API PBN, nazwę
  i token aplikacji **każdej uczelni** oraz token PBN użytkownika `LOGIN`
  ([dlaczego to potrzebne](#klucz-szyfrowania)).
- `pbn-zaloguj-lokalnie.py` najpierw sprawdza, czy zapisany token działa.
  Jeśli tak (token z serwera jest ważny) — **nie musisz się nigdzie logować**.
- Jeśli nie — otwiera okno przeglądarki ze stroną logowania aplikacji PBN
  i czeka, aż **sam zalogujesz się w PBN**. Hasła do PBN skrypt nie zna i nie
  wpisuje. Profil przeglądarki jest trwały (`~/.cache/bpp/pbn-profil`), więc
  dopóki sesja w PBN żyje, kolejne uruchomienia przechodzą bez logowania.

Lokalne konto `LOGIN` musi istnieć w odtworzonej bazie. `run-site` tworzy
konto `admin`; skrypt domyślnie zapisuje token właśnie jemu (`--user admin`).

!!! warning "Nie wyłączaj Celery"
    Pobieranie i import z PBN oraz wysyłka „w tle” idą przez workera Celery.
    `run-site` startuje go domyślnie — **nie dodawaj `--no-celery`**, bo
    w interfejsie nic się nie wydarzy. Worker jest bezpieczny: automaty
    wysyłki wstrzymuje [bezpiecznik](#bezpiecznik), także gdy dodasz
    `--with-celery-beat` (watchdog kolejki).

Pobieranie z serwera nie zatrzymuje startu `run-site`, a `run-site` pokazuje
wyjście hooków tylko przy ich awarii — o nieudanym pobraniu (brak VPN, zła
nazwa hosta) dowiesz się w kroku 2, który powie wprost, czego brakuje. To
samo można wtedy zrobić bez restartu:

```bash
uv run bin/pbn-zaloguj-lokalnie.py --user LOGIN --konfiguracja-z HOST
```

### Kilka uczelni w jednej bazie

W instalacji z kilkoma uczelniami każda ma własną aplikację w PBN. Wskaż,
przez którą ma iść logowanie:

```bash
uv run bin/pbn-zaloguj-lokalnie.py --user LOGIN --uczelnia SKROT
```

Bez `--uczelnia` skrypt wypisze listę uczelni do wyboru. Logowanie, wymiana
kodu i końcowe sprawdzenie idą przez aplikację wskazanej uczelni, a komunikat
końcowy mówi, dla której uczelni token sprawdzono. Konfiguracja z serwera
(`--get-pbn-token-from`, `--konfiguracja-z`) przenosi aplikacje wszystkich
uczelni naraz, parując je po skrócie.

### Backup w formacie katalogowym

Nocny backup z `bpp-deploy` to `db-backup-<TS>.tar.gz` z katalogiem
`pg_dump -Fd` w środku. `run-site --from-dump` ładuje takie archiwa klientem
PostgreSQL z hosta — gdy go nie ma, kończy się
`'psql' not found on PATH`, a rozpakowany katalog podany wprost daje
`IsADirectoryError`. `bin/run-site-z-backupu.py` zamienia backup na zwykły
plik SQL, uruchamiając `pg_restore` w kontenerze z obrazu bazy
z `runsite.toml` (na hoście wystarcza Docker), i dopiero ten plik podaje
`run-site`. Przyjmuje `.tar.gz` z katalogiem, sam rozpakowany katalog,
format custom (`.pg_dump`) i zwykły `.sql`/`.sql.gz` (bez konwersji).

Wynik trafia do `~/.cache/bpp/dumpy` i jest używany ponownie, dopóki plik
backupu się nie zmieni. Pliki bywają duże (kilkaset MB) — katalog można
bezpiecznie skasować. Sama konwersja, bez startu instancji:

```bash
uv run bin/run-site-z-backupu.py <backup> --tylko-konwersja
```

### `manage.py` obok działającego run-site

`run-site` stawia bazę i Redisa na losowych portach. `.run-site-env.sh`
eksportuje `DATABASE_URL` i `PG*`, ale ustawienia BPP czytają
`DJANGO_BPP_DB_*`, więc `source .run-site-env.sh && python src/manage.py …`
łączy się z `localhost:5432` i pada. Używaj launchera, który bierze
połączenia z `.run-site-config`:

```bash
uv run bin/run-site-manage.py shell
uv run bin/run-site-manage.py pbn_konfiguracja_z_serwera LOGIN@HOST
```

`bin/pbn-zaloguj-lokalnie.py` to skrót do
`bin/run-site-manage.py pbn_zaloguj_lokalnie`.

## Jak działa przechwycenie powrotu

Skrypt otwiera stronę logowania aplikacji PBN wskazanej uczelni
(`<adres API PBN>/auth/pbn/api/registration/user/token/<nazwa aplikacji>` —
ten sam adres, na który przekierowuje „autoryzuj PBN API”). PBN po
zalogowaniu odsyła przeglądarkę na adres zwrotny **zapisany przy aplikacji
w PBN**, czyli na serwer klienta:
`https://<serwer klienta>/pbn_api/callback?ott=<kod>`. To jedno żądanie jest
zatrzymywane, zanim wyjdzie z przeglądarki; serwer klienta niczego nie
dostaje (kod jest jednorazowy i serwer mógłby go zużyć). Przechwycony kod
skrypt wymienia na token tą samą ścieżką co widok `/pbn_api/callback`
(`pbn_api.autoryzacja.zapisz_token_z_ott`), jawnie dla wskazanej uczelni.

Lokalne widoki `/pbn_api/authorize` i `/pbn_api/callback` nie biorą w tym
udziału: wybierają uczelnię po domenie żądania, więc pod `localhost`
w bazie z kilkoma uczelniami trafiałyby w pierwszą z brzegu.

Obsługiwane są też aliasy callbacku (literówki w rodzaju `kalbak`), powrót
formularzem POST oraz powrót z `ott` na zupełnie inny adres.

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
    uv run bin/run-site-manage.py pbn_konfiguracja_z_serwera \
        --user LOGIN --wypisz-zdalne-polecenie
    # wypisane polecenie uruchom na serwerze, a jego wyjście podaj potokiem do:
    uv run bin/run-site-manage.py pbn_konfiguracja_z_serwera --stdin
    ```

2. **Uruchom lokalną instancję z kluczem serwera** — jeżeli go masz:

    ```bash
    export DJANGO_BPP_FIELD_ENCRYPTION_KEY='<klucz z .env serwera>'
    uv run bin/run-site-z-backupu.py <backup>
    ```

    Zmienna musi być ustawiona także w terminalu, w którym uruchamiasz
    `bin/pbn-zaloguj-lokalnie.py`. Klucza nie zapisuj w repozytorium.

## Bezpiecznik

Kopia bazy klienta przynosi ze sobą **kolejkę eksportu do PBN**, a kod ma
automaty, które wysyłają bez pytania. Z prawdziwym tokenem oznaczałoby to
prawdziwą wysyłkę z Twojej maszyny. Dlatego lokalna instancja domyślnie
**niczego nie wysyła sama** — także z działającym workerem Celery.

Wstrzymywane automaty:

| Automat | Co robi normalnie |
|---|---|
| ponowienie po zalogowaniu (`kolejka_ponow_wysylke_prac_po_zalogowaniu`) | po zapisaniu tokenu wysyła prace czekające na autoryzację |
| watchdog kolejki (`queue_watchdog`) | co 10 minut budzi wpisy, które utknęły |
| łańcuch „następny z kolejki” (`check_and_send_next_in_queue`) | po każdej udanej wysyłce bierze kolejne wpisy |
| kosz i przywrócenie (`zakolejkuj_wycofanie`, `zakolejkuj_wysylke`) | przeniesienie pracy do kosza wycofuje jej oświadczenia w PBN |

**Nadal działa** wszystko, co klikasz świadomie: „Zapisz i wyślij do PBN”
w formularzu rekordu, „wyślij ponownie” w kolejce eksportu (także dla wpisu
zamkniętego przez bezpiecznik), komendy `manage.py pbn_*`. Narzędzia masowe
(scalanie autorów, przemapowanie źródeł) dopisują wpisy do kolejki, ale nic
ich stamtąd samo nie zabierze.

### Odblokowanie automatycznej wysyłki

Gdy chcesz przetestować właśnie automaty (kolejkę, watchdog, kosz):

- **w trakcie działania** — strona „Kolejka eksportu do PBN”
  (`/pbn_export_queue/`) pokazuje na górze stan („automatyczna wysyłka do
  PBN: wstrzymana / WŁĄCZONA”) i przycisk do przełączenia. Działa od razu
  dla strony i dla workera Celery,
- **od startu** — `uv run run-site run --pbn-automaty wlacz` (także przez
  `bin/run-site-z-backupu.py`).

Stan jest ustawiany przy każdym starcie `run-site`: bez flagi wraca do
„wstrzymana”, więc odblokowanie nie przeżywa restartu po cichu.

!!! danger "Odblokowane automaty = produkcyjne zachowanie na prawdziwym PBN"
    Po odblokowaniu każdy nowy wpis kolejki zostanie wysłany, a przeniesienie
    pracy do kosza wycofa jej oświadczenia w PBN. Wstrzymaj automaty, gdy
    skończysz.

Jak to jest zrobione: `settings/local.py` ustawia
`DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY=1` (produkcja i testy: wyłączone) i dodaje
klucz constance z decyzją o odblokowaniu — w bazie, bo czytają go osobne
procesy. Przełącznik istnieje wyłącznie na instancji lokalnej (`DEBUG = True`
i baza na tej samej maszynie); na produkcji klucza nie ma, adres przełącznika
odpowiada 404, a automaty działają normalnie bez czytania czegokolwiek.
W dev-owym docker compose (baza pod nazwą serwisu) widać stan, ale przycisku
nie ma — tam automaty włącza `DJANGO_BPP_PBN_WSTRZYMAJ_AUTOMATY=0`.

### Zamknięcie kolejki z kopii bazy

Komenda `pbn_bezpiecznik_lokalnej_kopii` zamyka wszystkie niezakończone
wpisy kolejki (zostają w historii z adnotacją). Uruchamia się sama: przy
każdym starcie `run-site`, przed pobraniem konfiguracji z serwera i przed
logowaniem. Ręcznie:

```bash
uv run bin/run-site-manage.py pbn_bezpiecznik_lokalnej_kopii \
    --tak-to-jest-lokalna-kopia
```

Komenda **odmawia**, gdy instancja nie wygląda na lokalną: wymaga
`DEBUG = True` oraz bazy na tej samej maszynie (`localhost` albo gniazdo
uniksowe). Flaga potwierdzenia tych warunków nie obchodzi. Gdy baza stoi
w dev-owym docker compose pod nazwą serwisu, dodaj `--lokalny-host-bazy db`.
Opcja `--automaty wstrzymaj|wlacz` ustawia przy okazji przełącznik automatów.

Uwaga: logowanie do PBN też zamyka niezakończone wpisy kolejki — jeśli
testujesz automaty i masz w kolejce własne wpisy, zaloguj się wcześniej.

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

Przy kilku uczelniach dodaj `--uczelnia SKROT` — tej, której aplikacji użyłeś
w kroku 2.

`--ott` robi to samo co `manage.py pbn_ott_na_token`, a dodatkowo uruchamia
bezpiecznik i sprawdza, czy token działa.

## Pozostałe opcje

```bash
uv run bin/pbn-zaloguj-lokalnie.py --tylko-sprawdz   # czy zapisany token działa
uv run bin/pbn-zaloguj-lokalnie.py --wymus           # loguj mimo działającego tokenu
uv run bin/pbn-zaloguj-lokalnie.py --help
```

Skrypt bierze połączenie z bazą z pliku `.run-site-config` działającego
`run-site`, więc uruchamiaj go w tym samym checkoucie.

Końcowe sprawdzenie to jedno zapytanie tylko-do-odczytu (pierwsza strona
publikacji profilu instytucji). Token nie jest nigdzie wypisywany.

## Gdzie to jest w kodzie

| Co | Gdzie |
|---|---|
| logowanie z przechwyceniem powrotu | `src/pbn_api/logowanie_lokalne.py`, komenda `pbn_zaloguj_lokalnie`, `bin/pbn-zaloguj-lokalnie.py` |
| backup → SQL dla run-site | `bin/run-site-z-backupu.py` |
| `manage.py` na bazie run-site | `bin/run-site-manage.py` |
| przeniesienie konfiguracji z serwera | `src/pbn_api/konfiguracja_z_serwera.py`, komenda `pbn_konfiguracja_z_serwera` |
| bezpiecznik i przełącznik automatów | `src/pbn_export_queue/bezpiecznik.py`, komenda `pbn_bezpiecznik_lokalnej_kopii`, widok `przelacz_automaty` |
| hooki run-site | `src/django_bpp/runsite_hooks.py`, `runsite.toml` |
| test e2e na atrapie PBN | `src/pbn_api/tests/test_playwright/test_logowanie_lokalne_e2e.py` |

Mechanizm autoryzacji po stronie BPP (sesja, „oczekująca autoryzacja”)
opisuje [Pakiety klienckie PBN](pakiety-pbn.md#autoryzacja-pbn-api-na-lokalnej-instancji-przeniesienie-ott).
