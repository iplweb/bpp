# html2docx — usługa konwersji HTML → DOCX (sidecar HTTP)

BPP eksportuje niektóre raporty do DOCX. Podstawowym konwerterem jest
`pypandoc` (in-process). Gdy pandoc zawiedzie — np. robi **core dump na
hostach VMWare ESX** — używany jest fallback: usługa **html2docx**.

Historycznie fallback uruchamiał kontener przez `docker run` (co wymagało
montowania `/var/run/docker.sock` do appservera — pełna kontrola nad demonem
Dockera hosta). Od teraz html2docx działa jako **długożyjąca usługa HTTP**
(sidecar), a appserver tylko POST-uje do niej HTML. Appserver nie ma już ani
socketa, ani Docker CLI.

## Obraz i tryby

Obraz `iplweb/html2docx` (źródło: https://github.com/mpasternak/html2docx,
apka .NET 8 oparta o HtmlToOpenXml) obsługuje **dwa tryby**, wybierane liczbą
argumentów:

- **bez argumentów → serwer HTTP** (domyślny tryb kontenera),
- **z argumentem `-`/ścieżką pliku → filtr CLI** stdin→stdout (kompatybilność
  wstecz, standalone).

## Kontrakt HTTP

- `POST /convert`
  - request: ciało = surowy HTML, `Content-Type: text/html; charset=utf-8`,
  - response 200: bajty `.docx`
    (`Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`),
  - błąd konwersji: `500` + tekst błędu.
  - limit ciała żądania: 100 MB.
- `GET /health` → `200` (healthcheck).

## Port

Domyślnie **3030**, nadpisywalny zmienną środowiskową `HTML2DOCX_PORT`
(port 8080 bywa zajęty na stackach dockera). Serwer binduje
`http://0.0.0.0:${HTML2DOCX_PORT:-3030}`.

## Konfiguracja po stronie BPP

Adres usługi podaje zmienna środowiskowa `DJANGO_BPP_HTML2DOCX_URL`
(setting `HTML2DOCX_URL`), np.:

```
DJANGO_BPP_HTML2DOCX_URL=http://html2docx:3030/convert
```

- **Brak/pusta wartość** → fallback wyłączony: `nowe_raporty.docx_export`
  loguje ostrzeżenie i podnosi `DocxConversionError` (degradacja **miękka**,
  bez twardego crasha — dokładnie jak dawniej przy braku Dockera).
- Timeouty klienta: connect 5 s, read 30 s.

## Deployment

Wiring produkcyjnego compose (serwis + env + brak published portu) robi
`bpp-deploy`. W dev `docker-compose.yml` serwis `html2docx` jest dodany, a
`DJANGO_BPP_HTML2DOCX_URL` siedzi w `.env.docker` (współdzielone przez
appserver i workery — celery task oświadczeń również generuje DOCX, więc
worker też musi widzieć usługę).
