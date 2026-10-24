# Pakiety klienckie PBN

Kod integracji z PBN jest wydzielony do **dwóch samodzielnych pakietów**
publikowanych na PyPI (repozytoria pod `github.com/iplweb/`):

| Dystrybucja (PyPI) | Import Pythona | Repozytorium | Odpowiedzialność |
| --- | --- | --- | --- |
| `pbn-client` | `pbn_client` | [iplweb/pbn-client](https://github.com/iplweb/pbn-client) | HTTP, uwierzytelnianie i protokół API PBN (niezależne od Django) |
| `django-pbn-client` | `django_pbn_client` | [iplweb/django-pbn-client](https://github.com/iplweb/django-pbn-client) | abstrakcyjne modele Django i pobieranie/zapis stron PBN |

BPP zależy od obu dystrybucji jak od każdej innej zależności z PyPI
(`pyproject.toml`, sekcja `[project.dependencies]`). `django-pbn-client`
zależy dodatkowo od `pbn-client`. Istniejąca aplikacja `pbn_api`, jej etykieta
Django, konkretne modele i migracje pozostają w BPP. Moduł `pbn_api.models.base`
oraz część `pbn_api.exceptions`/`pbn_api.const` to cienkie warstwy zgodności
re-eksportujące klasy z nowych pakietów.

**W repozytorium BPP nie ma już katalogu `packages/` ani konfiguracji
`uv workspace`.** Zmiana kodu klienta = PR do właściwego repozytorium pakietu →
nowe wydanie na PyPI (przez GitHub Release + Trusted Publishing) → bump wersji
zależności w BPP.

## Podział odpowiedzialności

`pbn-client` jest warstwą protokołu i nie może zależeć od modeli BPP ani od
`pbn_api`. `django-pbn-client` udostępnia abstrakcyjne klasy bazowe oraz
generyczne usługi pobierania stron i zapisu (m.in. `download_to_model`,
`get_or_download`). **Nie** dostarcza konkretnych modeli lustrzanych — te,
ich relacje do BPP oraz historia migracji pozostają w `pbn_api`. Orkiestracja
importu, dopasowywanie rekordów, Celery i interfejs pobierania również
pozostają po stronie BPP.

Późniejsze wydzielenie konkretnych modeli wymagałoby zaprojektowania
konfigurowalnych relacji i osobnej strategii migracji; nie należy przenosić
istniejących migracji ani zmieniać etykiety aplikacji.

Pobieranie równoległe domyślnie używa wątków. Opcjonalny tryb
`method="processes"` korzysta z POSIX-owego `fork`, więc nie jest dostępny na
Windows.

## Aktualizacja wersji pakietu w BPP

```bash
# po wydaniu nowej wersji pakietu na PyPI:
uv add "pbn-client>=0.2,<0.3"           # lub edycja pyproject.toml
uv sync --refresh-package pbn-client    # --refresh gdy index uv jest zcache'owany
uv run python src/manage.py check
uv run python src/manage.py makemigrations --check --dry-run   # brak dryfu pbn
```

## Wydawanie nowej wersji pakietu

W repozytorium danego pakietu (nie w BPP):

1. Bump `version` w `pyproject.toml`, merge do `main`.
2. Utwórz GitHub Release z tagiem `vX.Y.Z` — workflow `release.yml` publikuje na
   PyPI przez **Trusted Publishing** (OIDC, bez tokena).
3. Zbump zależność w BPP (sekcja wyżej).

## Autoryzacja PBN API na lokalnej instancji (przeniesienie `ott`)

PBN po zalogowaniu przekierowuje na adres callbacku skonfigurowany dla
aplikacji, czyli zwykle na serwer produkcyjny, a nie na `localhost`.
Parametru `state` PBN nie odsyła. Callback (`/pbn_api/callback?ott=<uuid>`)
przyjmuje więc `ott` tylko wtedy, gdy w sesji tego samego użytkownika jest
„oczekująca autoryzacja”, zapisana przez `/pbn_api/authorize` i nie starsza
niż 10 minut (`PBN_PENDING_AUTH_MAX_AGE_SECONDS` w `src/pbn_api/views.py`).
Wpis jest jednorazowy. Callback bez takiego wpisu jest odrzucany, zanim
dojdzie do wymiany `ott` w PBN, więc `ott` pozostaje niewykorzystany.

Wejście na `/pbn_api/authorize` z linku w BPP (nagłówek
`Sec-Fetch-Site: same-origin` albo Referer z tego samego hosta) od razu
przekierowuje do PBN. W każdym innym przypadku, także dla adresu wpisanego
ręcznie, pojawia się strona pośrednia z przyciskiem (formularz POST
z tokenem CSRF).

Procedura testu lokalnego, wariant (a), przez przeglądarkę:

1. Na lokalnej instancji (`uv run run-site run`) kliknij „autoryzuj PBN API”.
   W sesji lokalnej powstaje oczekujący wpis.
2. Zaloguj się w PBN. PBN przekieruje na callback serwera skonfigurowanego
   w aplikacji PBN. Ten serwer nie ma w Twojej sesji oczekującego wpisu,
   więc odrzuci callback z komunikatem błędu i nie zużyje `ott`.
   Skopiuj wartość `ott` z paska adresu.
3. W ciągu ~10 minut od kroku 1 otwórz w tej samej przeglądarce
   `http://localhost:<port>/pbn_api/callback?ott=<ott>`.

Jeżeli na serwerze docelowym w ciągu ostatnich 10 minut też kliknięto
„autoryzuj PBN API” w tej samej przeglądarce, serwer ten przyjmie i zużyje
`ott`. Wtedy zacznij od kroku 1 jeszcze raz.

Wariant (b), bez przeglądarki i bez sesji. Wykonaj krok 2 (adres logowania
PBN otworzysz też ze strony pośredniej `/pbn_api/authorize` na dowolnej
instancji), skopiuj `ott` z paska adresu i na lokalnej instancji uruchom:

```bash
uv run python src/manage.py pbn_ott_na_token <ott> --user admin
```

Komenda wymienia `ott` na token tą samą ścieżką co callback
(`pbn_api.autoryzacja.zapisz_token_z_ott`) i nie sprawdza sesji, bo wymaga
dostępu do shella. Przy kilku uczelniach wskaż jedną przez
`--uczelnia <ID|skrót>`.

Przeniesienie tokenu z serwera na inną maszynę:

```bash
# na serwerze (token trafia na stdout, to SEKRET):
uv run python src/manage.py pbn_ott_na_token <ott> --user X --pokaz-token
# lokalnie, bez kontaktu z PBN:
uv run python src/manage.py pbn_ott_na_token --user admin --token <wartość>
```
