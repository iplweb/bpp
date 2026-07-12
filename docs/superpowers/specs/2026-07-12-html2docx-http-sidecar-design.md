# html2docx jako sidecar HTTP — usunięcie docker.sock z appservera

**Data:** 2026-07-12
**Status:** design zatwierdzony, do spisania planu
**Zakres:** `mpasternak/html2docx` (.NET — usługa HTTP) + `iplweb/bpp` (klient).
`iplweb/bpp-deploy` — **downstream, robi user sam**, tu tylko udokumentowany
kontrakt.

## Problem

Produkcyjny appserver ma zamontowany `/var/run/docker.sock`
(`bpp-deploy/docker-compose.application.yml:95`, `:ro`) i zawiera Docker CLI
(`docker/appserver/Dockerfile`). Wykorzystuje to do konwersji HTML→DOCX:
`src/nowe_raporty/docx_export.py` odpala `docker run --rm -i iplweb/html2docx -`
jako **fallback**, gdy `pypandoc` zawiedzie.

Sufiks `:ro` nie czyni API Dockera read-only — proces nadal może tworzyć
kontenery, montować katalogi hosta i wykonywać procesy. Każde przyszłe RCE
w appserverze (jedynej z tych usług, która parsuje niezaufany input z sieci)
oznacza natychmiastowe przejęcie hosta i wszystkich kontenerów. Fallback
odpalany rzadko — a socket wisi 24/7.

### Dlaczego fallback musi zostać

Obraz `iplweb/html2docx` istnieje, bo **pandoc robi core dump na hostach
VMWare ESX** (opis repo `mpasternak/html2docx`). To realna produkcyjna siatka
bezpieczeństwa pod crashującym primary converterem, nie kaprys — nie wolno go
po prostu usunąć.

### Fakty ustalone empirycznie (2026-07-12)

- `iplweb/html2docx` to **.NET 8** (nie Mono): `dotnet HtmlToDocx.dll`,
  `DOTNET_VERSION=8.0.20`. Framework-dependent; sama apka ~11 KB, runtime
  .NET ~106 MB. Obraz ~90 MB (arm64).
- To **console-filter**: stdin(HTML) → stdout(DOCX), jeden strzał, exit.
  **Nie serwuje HTTP** (mimo odziedziczonego `ASPNETCORE_HTTP_PORTS=8080`
  i runtime'u ASP.NET — apka ich nie używa). Zweryfikowane: uruchomienie
  bez arg produkuje DOCX i kończy proces.
- Rdzeń konwersji (`src/Program.cs`): `new HtmlConverter(main);
  await converter.ParseBody(html); main.Document.Save();` → MemoryStream →
  stdout. Biblioteka: **HtmlToOpenXml.dll 3.2.7** + DocumentFormat.OpenXml 3.1.0.
- Input do konwertera jest już **nh3-sanitizowany** (`docx_export.py:58`) —
  ten sam HTML, który pandoc przetwarza in-process. „Izolacja" kontenera nigdy
  nie była tu środkiem bezpieczeństwa; wynika z heterogeniczności runtime'ów
  (.NET vs Python).
- `requests>=2.34.2` jest zależnością bpp (klient HTTP gotowy).
- Fallback wołany z dwóch miejsc: `as_docx()` i `html_to_docx()`, oba przez
  wspólne `_convert_using_docker_image` w `docx_export.py`.

## Rozważone i odrzucone warianty

- **A — html2docx jako biblioteka pip in-process.** Niemożliwe: to binarka
  .NET, nie pakiet Python.
- **C — bake runtime .NET w obraz appservera + lokalny subprocess.** Działa
  (zweryfikowane: `dotnet /app/HtmlToDocx.dll -` daje poprawny docx), ale
  dokłada ~106 MB runtime .NET do bazowego obrazu appservera — **jawnie
  odrzucone przez usera** („absolutnie nie chcę dokładać niczego do
  podstawowego obrazu").
- **D — docker-socket-proxy.** Proxy przepuszczające `containers/create` i tak
  pozwala mountować hosta → nie zamyka dziury.

## Wybrany wariant: B — sidecar HTTP

html2docx staje się długożyjącym serwisem HTTP w osobnym kontenerze; appserver
woła go POST-em po sieci wewnętrznej. W zakresie tego speca appserver traci
**Docker CLI** i przestaje wołać dockera; sam mount `docker.sock` zdejmuje
downstream deployment. Konwerter zyskuje realną izolację: osobny kontener,
wąskie API, tylko sieć wewnętrzna, nie-root.

### Kontrakt HTTP (zatwierdzony)

- `POST /convert`
  - **Request:** ciało = surowy HTML, `Content-Type: text/html; charset=utf-8`.
  - **Response 200:** bajty `.docx`,
    `Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`.
  - **Błąd konwersji:** HTTP 4xx/5xx + tekst błędu w ciele (odpowiednik
    dzisiejszego stderr).
  - Limit ciała żądania Kestrela `MaxRequestBodySize = 100 MB` (104857600 B) —
    raporty bywają duże.
- `GET /health` → `200` (healthcheck compose/autoheal).

Odwzorowuje 1:1 dzisiejszy filtr stdin→stdout — minimum kodu po obu stronach,
brak parsowania multipart, brak narzutu base64.

## Zmiany po stronie .NET — `mpasternak/html2docx`

1. **`src/HtmlToDocx.csproj`**: `<Project Sdk="Microsoft.NET.Sdk">` →
   `Microsoft.NET.Sdk.Web`. Runtime ASP.NET jest już w obrazie bazowym.
2. **`src/Program.cs`** — rozgałęzienie na starcie:
   - **brak argów → tryb serwera** (nowy default): `WebApplication`
     nasłuchujący na `0.0.0.0:8080`, endpointy `POST /convert` i `GET /health`.
     Endpoint reużywa istniejący rdzeń konwersji (HtmlConverter/ParseBody/Save)
     — wydzielony do wspólnej funkcji `ConvertHtmlToDocxBytes(string html)`.
   - **arg `-`/nazwa pliku → tryb CLI** (bez zmian): stary filtr stdin→stdout
     zachowany dla kompatybilności i standalone-żności. Ta sama funkcja rdzenia.
   - Obsługa błędów: w trybie serwera wyjątek konwersji → odpowiedź 4xx/5xx
     z komunikatem; w trybie CLI → dotychczasowe `Console.Error` + `Exit(1)`.
   - Limit ciała żądania Kestrela (`MaxRequestBodySize`) podniesiony.
3. **`Dockerfile`**: entrypoint zostaje `dotnet HtmlToDocx.dll` (teraz domyślnie
   serwuje), `EXPOSE 8080`, user nie-root (uid 1654) bez zmian. Bez socketa.
   Rozważyć `HEALTHCHECK` w obrazie (lub zdać się na healthcheck compose).

## Zmiany po stronie BPP — `iplweb/bpp`

1. **`src/nowe_raporty/docx_export.py`**:
   - `_convert_using_docker_image` → `_convert_using_html2docx_service(html,
     output_path)`:
     `requests.post(settings.HTML2DOCX_URL, data=html.encode("utf-8"),
     headers={"Content-Type": "text/html; charset=utf-8"}, timeout=(5, 30))`.
     `200` → `response.content` (docx) do pliku; non-200/timeout/ConnectionError
     → `raise` (propaguje do `DocxConversionError` — logika fallbacku bez zmian).
   - **Endpoint z konfiguracji, nigdy hardcodowany.** Setting `HTML2DOCX_URL`
     czytany z env (np. `DJANGO_BPP_HTML2DOCX_URL`), **default `None`**.
     Zastępuje `HTML2DOCX_DOCKER_IMAGE` / `HTML2DOCX_DOCKER_COMMAND`. Znika
     import i wołanie dockera.
   - **Miękki fail:** gdy `HTML2DOCX_URL` jest `None`/pusty → fallback HTTP
     jest pominięty, logujemy `warning` („html2docx nie skonfigurowany") i
     rzucamy `DocxConversionError` — dokładnie tak, jak dziś, gdy dockera nie
     ma. Gdy ustawiony, ale serwis nieosiągalny → to samo (błąd propaguje do
     500). Appserver nigdy nie wywala się twardo.
   - Timeouty klienta: connect 5 s, read 30 s.
   - Host/port docelowego serwisu = wyłącznie sprawa konfiguracji (env), poza
     kodem — patrz sekcja Deployment.
2. **`docker/appserver/Dockerfile`**: usunąć stage `FROM docker:cli AS
   docker-cli` i `COPY --from=docker-cli … /usr/local/bin/docker` — appserver
   traci Docker CLI (chudszy obraz, mniejsza powierzchnia).
3. **`docker-compose.yml` (dev)** — opcjonalnie: dodać serwis `html2docx`
   (`image: iplweb/html2docx:...`, sieć wewnętrzna, bez published portu) oraz
   ustawić `DJANGO_BPP_HTML2DOCX_URL` na appserverze — żeby fallback dało się
   przetestować lokalnie. Bez tego (default `None`) dev jedzie na samym
   pandocu, co jest OK.
4. **`src/nowe_raporty/tests/test_docx_export.py`**: mock `requests.post`
   zamiast `subprocess.run`; przypadki 200 / non-200 / timeout /
   ConnectionError / `HTML2DOCX_URL is None` (miękki fallback). Rozważyć
   integration-test z realnym serwisem przez testcontainers (osobny punkt
   w planie — dziś istnieje integration-test wołający realny `docker run`,
   do zastąpienia).
5. **Newsfragment** (`src/bpp/newsfragments/*.bugfix.rst`) — po polsku, o
   przejściu fallbacku html2docx z `docker run` na usługę HTTP (+ usunięcie
   Docker CLI z obrazu appservera).
6. **Docs**: notka o kontrakcie HTTP obrazu html2docx (np. w
   `docs/deweloper/`), żeby kontrakt był udokumentowany.

## Deployment — `iplweb/bpp-deploy` (robi user sam, poza zakresem)

Cały wiring produkcyjnego compose robi **user we własnym zakresie** — **nie
jest** deliverable tego speca ani planu. Spec tylko **dokumentuje kontrakt**,
który deployment musi spełnić po wdrożeniu obrazu z trybem serwera i klienta
w bpp:

- serwis `html2docx` (`image: iplweb/html2docx:<tag>`, sieć wewnętrzna, **bez
  published portu**, restart + healthcheck wg uznania), pin **po tagu**;
- na appserverze env `DJANGO_BPP_HTML2DOCX_URL=http://<host>:<port>/convert`;
- zdjęcie mountu `docker.sock` z appservera.

`depends_on`, healthcheck, restart policy, sieć — decyzje deploymentu, nie
tego planu.

## Efekt bezpieczeństwa

- Appserver: **zero Docker CLI** w obrazie (zmiana w bpp) i kod nie woła już
  dockera; **zero `docker.sock`** po zdjęciu mountu przez bpp-deploy. RCE
  w appserverze nie ma już czym sięgnąć do demona Dockera hosta.
- Konwerter: osobny kontener, **wąskie API HTTP** (`/convert`, `/health`),
  tylko sieć wewnętrzna (bez published portu), nie-root, parsuje wyłącznie
  nh3-sanitizowany HTML.
- Fallback nadal dostępny (wymóg ESX/core-dump spełniony); nowa zależność =
  zdrowie kontenera html2docx, mitygowane po stronie deploymentu (restart +
  healthcheck + autoheal), a po stronie bpp degradacją miękką.

## Ryzyka i punkty do rozstrzygnięcia w planie

- **Reliability fallbacku:** B dokłada zależność od drugiego kontenera będącego
  up. Mitygacja **po stronie deploymentu** (restart + healthcheck + autoheal).
  Zaakceptowane świadomie (user wybrał B ponad C mimo tego). Po stronie bpp
  degradacja jest miękka (patrz niżej), więc niedostępny serwis = brak eksportu
  DOCX, nie crash.
- **Dev/test bez serwisu:** gdy `HTML2DOCX_URL` jest `None` lub html2docx nie
  biegnie (np. czysty `pytest`), fallback rzuci `DocxConversionError` — tak jak
  dziś rzucał, gdy brak dockera. Testy jednostkowe mockują `requests.post`,
  więc nie wymagają serwisu.
- **Kolejność deliverables:** obraz html2docx z trybem serwera musi być
  opublikowany i dostępny **zanim** user przełączy deployment na
  `DJANGO_BPP_HTML2DOCX_URL` i zdejmie socket. Plan dostarcza (a) usługę .NET
  i (b) klienta bpp; sam moment przepięcia deploya to handoff do usera.
- **CI integration-test:** zastąpić dzisiejszy `docker run`-owy test wariantem
  z testcontainers stawiającym serwis, albo oznaczyć jako opt-in.
