# html2docx HTTP sidecar — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zamienić docker.sock-owy fallback html2docx (`docker run` per request) na długożyjącą usługę HTTP, tak że appserver traci Docker CLI i wołania dockera, a konwerter .NET staje się izolowanym sidecarem z wąskim API.

**Architecture:** Dwa deliverables przez dwa repo. (A) `mpasternak/html2docx` (.NET 8): apka konsolowa zyskuje tryb serwera ASP.NET (`POST /convert`, `GET /health`) obok istniejącego trybu CLI stdin→stdout. (B) `iplweb/bpp`: fallback w `docx_export.py` woła usługę przez `requests.post` pod konfigurowalnym URL-em (`DJANGO_BPP_HTML2DOCX_URL`, default `None` → miękka degradacja), a obraz appservera traci Docker CLI. Wiring produkcyjnego compose robi user osobno (poza planem).

**Tech Stack:** .NET 8 / ASP.NET minimal API, HtmlToOpenXml.dll 3.2.7, DocumentFormat.OpenXml 3.1.0; Python 3.10+/Django, `requests`, pytest + monkeypatch; Docker.

**Spec:** `docs/superpowers/specs/2026-07-12-html2docx-http-sidecar-design.md`

## Global Constraints

- **Port konwertera:** default **3030**, nadpisywalny env `HTML2DOCX_PORT`. Bind `http://0.0.0.0:${HTML2DOCX_PORT:-3030}`.
- **Kontrakt HTTP:** `POST /convert` — request body = surowy HTML (`text/html; charset=utf-8`), response 200 = bajty `.docx` (`Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document`); błąd konwersji → 4xx/5xx + tekst. `GET /health` → 200. `MaxRequestBodySize = 104857600` (100 MB).
- **Config po stronie bpp:** `HTML2DOCX_URL = env("DJANGO_BPP_HTML2DOCX_URL", default=None)`. Nigdy hardcodowany. `None`/pusty → fallback pominięty (warning + `DocxConversionError`), zero twardego crasha.
- **Timeouty klienta:** `requests.post(..., timeout=(5, 30))` (connect 5 s, read 30 s).
- **Tryb CLI w apce .NET zostaje** (arg `-`/plik → stdin→stdout, bez zmian zachowania).
- **Python:** ZAWSZE `uv run` przed pythonem/pytest. Max linia 88 znaków (ruff).
- **Bez `except: pass`** — każdy except loguje/re-raise/zwraca sensowny błąd.
- **Newsfragment** dla zmiany bugfix w `src/bpp/newsfragments/`.
- **Repo .NET:** klon jako katalog-rodzeństwo `~/Programowanie/html2docx` (nie w /tmp, nie w drzewie bpp).

---

## Faza A — usługa HTTP w `mpasternak/html2docx` (.NET)

> Repo bez frameworka testów jednostkowych (`test/` to fixture'y manualne).
> Weryfikacja = build obrazu + `curl`/stdin (integration-style). To świadomy
> wybór dopasowany do repo, nie pominięcie testów.

### Task A1: Klon repo + gałąź + baseline weryfikacji CLI

**Files:**
- Clone: `~/Programowanie/html2docx` (z `mpasternak/html2docx`)

**Interfaces:**
- Produces: lokalny klon na gałęzi `feat/http-server`, potwierdzony działający tryb CLI (baseline przed zmianami).

- [ ] **Step 1: Klon i gałąź**

```bash
cd ~/Programowanie
git clone git@github.com:mpasternak/html2docx.git
cd html2docx
git checkout -b feat/http-server
```

- [ ] **Step 2: Baseline — zbuduj obecny obraz i potwierdź tryb CLI**

```bash
cd ~/Programowanie/html2docx
docker build -t html2docx:baseline .
printf '<b>Ala</b> ma kota' | docker run --rm -i html2docx:baseline - > /tmp/baseline.docx
file /tmp/baseline.docx
```
Expected: `/tmp/baseline.docx: Microsoft Word 2007+` (tryb CLI działa przed zmianami).

- [ ] **Step 3: Commit (checkpoint gałęzi, bez zmian kodu)**

Brak zmian do commita — gałąź założona. Przejdź do A2.

---

### Task A2: Wydziel rdzeń konwersji do wspólnej funkcji

**Files:**
- Modify: `~/Programowanie/html2docx/src/Program.cs`

**Interfaces:**
- Produces: `static byte[] ConvertHtmlToDocxBytes(string html)` — synchroniczny wrapper wołający istniejący rdzeń (`HtmlConverter` / `ParseBody` / `Save`) i zwracający bajty `.docx`. Używany i przez CLI, i przez serwer (A3).

- [ ] **Step 1: Dodaj funkcję `ConvertHtmlToDocxBytes` i przełącz na nią ścieżkę CLI**

W `src/Program.cs` wydziel dotychczasowy blok konwersji (od `using var memoryStream = new MemoryStream();` do zapisu) do funkcji na końcu pliku:

```csharp
static byte[] ConvertHtmlToDocxBytes(string html)
{
    using var memoryStream = new MemoryStream();
    using (var doc = WordprocessingDocument.Create(
        memoryStream, DocumentFormat.OpenXml.WordprocessingDocumentType.Document))
    {
        var main = doc.AddMainDocumentPart();
        main.Document = new DocumentFormat.OpenXml.Wordprocessing.Document(
            new DocumentFormat.OpenXml.Wordprocessing.Body());
        var converter = new HtmlConverter(main);
        converter.ParseBody(html).GetAwaiter().GetResult();
        main.Document.Save();
    }
    return memoryStream.ToArray();
}
```

W ścieżce CLI (po ustaleniu `html`/`outputFile`) zastąp inline-konwersję wywołaniem:

```csharp
byte[] docx = ConvertHtmlToDocxBytes(html);
if (outputFile == null)
{
    using var stdout = Console.OpenStandardOutput();
    stdout.Write(docx, 0, docx.Length);
}
else
{
    File.WriteAllBytes(outputFile, docx);
}
```

Zachowaj istniejące bloki `catch (IOException …)` i `catch (Exception …)` z komunikatami + `Environment.Exit(1)`.

- [ ] **Step 2: Zbuduj i potwierdź, że CLI dalej działa (bez regresji)**

```bash
cd ~/Programowanie/html2docx
docker build -t html2docx:a2 .
printf '<b>Ala</b> ma kota' | docker run --rm -i html2docx:a2 - > /tmp/a2.docx
file /tmp/a2.docx
```
Expected: `Microsoft Word 2007+` (refaktor rdzenia nie zmienił zachowania CLI).

- [ ] **Step 3: Commit**

```bash
cd ~/Programowanie/html2docx
git add src/Program.cs
git commit -m "refactor: wydziel ConvertHtmlToDocxBytes wspolny dla CLI i serwera"
```

---

### Task A3: Tryb serwera ASP.NET (`POST /convert`, `GET /health`)

**Files:**
- Modify: `~/Programowanie/html2docx/src/HtmlToDocx.csproj`
- Modify: `~/Programowanie/html2docx/src/Program.cs`
- Modify: `~/Programowanie/html2docx/Dockerfile`

**Interfaces:**
- Consumes: `ConvertHtmlToDocxBytes(string html)` z A2.
- Produces: obraz, który **bez argów** serwuje HTTP na `0.0.0.0:${HTML2DOCX_PORT:-3030}` z `POST /convert` i `GET /health`; **z argiem `-`/plik** działa jak CLI.

- [ ] **Step 1: Przełącz SDK na Web**

W `src/HtmlToDocx.csproj` zmień:

```xml
<Project Sdk="Microsoft.NET.Sdk.Web">
```
(reszta `PropertyGroup`/`ItemGroup` bez zmian; `OutputType>Exe` zostaje).

- [ ] **Step 2: Dodaj rozgałęzienie CLI/serwer na początku `Program.cs`**

Na samej górze `Program.cs`, PRZED dotychczasową logiką parsowania argów, wstaw: gdy są argi (CLI) — leci stara ścieżka; gdy brak argów — serwer. Najprościej owinąć: jeśli `args.Length == 0` uruchom serwer i `return`, w przeciwnym razie kontynuuj dotychczasowy kod CLI.

```csharp
if (args.Length == 0)
{
    var port = Environment.GetEnvironmentVariable("HTML2DOCX_PORT");
    if (string.IsNullOrWhiteSpace(port)) port = "3030";

    var builder = WebApplication.CreateBuilder(args);
    builder.WebHost.UseUrls($"http://0.0.0.0:{port}");
    builder.WebHost.ConfigureKestrel(o => o.Limits.MaxRequestBodySize = 104857600);
    var app = builder.Build();

    app.MapGet("/health", () => Results.Ok("ok"));

    app.MapPost("/convert", async (HttpRequest request) =>
    {
        using var reader = new StreamReader(request.Body);
        var html = await reader.ReadToEndAsync();
        try
        {
            var docx = ConvertHtmlToDocxBytes(html);
            return Results.File(
                docx,
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
        }
        catch (Exception ex)
        {
            return Results.Problem(detail: ex.Message, statusCode: 500);
        }
    });

    app.Run();
    return;
}
```

> Uwaga: `WebApplication`/`Results` wymagają `Microsoft.NET.Sdk.Web` (Step 1). Nowy default (brak argów = serwer) zastępuje stary „brak argów = czytaj stdin"; tryb stdin nadal dostępny przez arg `-`.

- [ ] **Step 3: Dockerfile — port 3030**

W `~/Programowanie/html2docx/Dockerfile` dodaj przed `ENTRYPOINT` (entrypoint `dotnet HtmlToDocx.dll` zostaje):

```dockerfile
ENV HTML2DOCX_PORT=3030
EXPOSE 3030
```
(Odziedziczone `ASPNETCORE_HTTP_PORTS=8080` zignorowane — bind steruje `UseUrls`.)

- [ ] **Step 4: Zbuduj obraz**

```bash
cd ~/Programowanie/html2docx
docker build -t html2docx:a3 .
```
Expected: build OK.

- [ ] **Step 5: Zweryfikuj tryb serwera — /health i /convert**

```bash
CID=$(docker run -d -p 13030:3030 html2docx:a3)
sleep 4
curl -s -o /dev/null -w "health=%{http_code}\n" http://localhost:13030/health
printf '<table><tr><td><b>Ala</b></td></tr></table>' \
  | curl -s -X POST --data-binary @- \
    -H 'Content-Type: text/html; charset=utf-8' \
    http://localhost:13030/convert -o /tmp/a3.docx
file /tmp/a3.docx
docker rm -f "$CID"
```
Expected: `health=200` oraz `/tmp/a3.docx: Microsoft Word 2007+`.

- [ ] **Step 6: Zweryfikuj, że tryb CLI dalej działa (regresja)**

```bash
printf '<b>Ala</b> ma kota' | docker run --rm -i html2docx:a3 - > /tmp/a3-cli.docx
file /tmp/a3-cli.docx
```
Expected: `Microsoft Word 2007+`.

- [ ] **Step 7: Commit**

```bash
cd ~/Programowanie/html2docx
git add src/HtmlToDocx.csproj src/Program.cs Dockerfile
git commit -m "feat: tryb serwera HTTP (POST /convert, GET /health) na porcie 3030"
```

- [ ] **Step 8: Handoff publikacji**

Poinformuj usera: gałąź `feat/http-server` gotowa; obraz `iplweb/html2docx:<nowy-tag>` musi zostać **opublikowany** (workflow `.github/workflows/docker.yml` w repo html2docx), zanim deployment przełączy bpp na `DJANGO_BPP_HTML2DOCX_URL`. Push/merge/tag — decyzja usera.

---

## Faza B — klient w `iplweb/bpp`

> Wszystkie ścieżki względem korzenia repo bpp. Python zawsze przez `uv run`.

### Task B1: Setting `HTML2DOCX_URL` z env

**Files:**
- Modify: `src/django_bpp/settings/base.py`

**Interfaces:**
- Produces: `settings.HTML2DOCX_URL` (str albo `None`), czytany z `DJANGO_BPP_HTML2DOCX_URL`.

- [ ] **Step 1: Dodaj setting**

W `src/django_bpp/settings/base.py` (obok innych `env(...)`, np. przy `SITE_ID`) dodaj:

```python
# URL usługi html2docx (sidecar HTTP) używanej jako fallback DOCX,
# gdy pandoc zawiedzie. None => fallback wyłączony (miękka degradacja).
HTML2DOCX_URL = env("DJANGO_BPP_HTML2DOCX_URL", default=None)
```

- [ ] **Step 2: Sanity check importu settings**

Run: `DJANGO_BPP_SKIP_DOTENV=1 uv run python -c "from django.conf import settings; import django; django.setup(); print(repr(settings.HTML2DOCX_URL))"`
Expected: `None` (brak env → default None; brak wyjątku).

- [ ] **Step 3: Commit**

```bash
git add src/django_bpp/settings/base.py
git commit -m "feat(docx): setting HTML2DOCX_URL z env (default None)"
```

---

### Task B2: Klient HTTP fallbacku + miękki fail (TDD)

**Files:**
- Modify: `src/nowe_raporty/docx_export.py`
- Test: `src/nowe_raporty/tests/test_docx_export.py`

**Interfaces:**
- Consumes: `settings.HTML2DOCX_URL` (B1).
- Produces: `_convert_using_html2docx_service(html: str, output_path: str) -> None` — POST-uje HTML do usługi, zapisuje docx do `output_path`; przy braku URL/błędzie rzuca (propaguje do `DocxConversionError`). Zastępuje `_convert_using_docker_image` (usuwana). Oba miejsca wołające (`as_docx`, `html_to_docx`) używają nowej funkcji.

- [ ] **Step 1: Napisz failujące testy nowej funkcji**

W `src/nowe_raporty/tests/test_docx_export.py` dodaj (importy: `import requests`, `from django.test import override_settings`):

```python
def test_html2docx_service_success(monkeypatch, tmp_path):
    from nowe_raporty import docx_export

    output_path = tmp_path / "out.docx"

    class FakeResp:
        status_code = 200
        content = b"docx-bytes"

        def raise_for_status(self):
            pass

    captured = {}

    def fake_post(url, data, headers, timeout):
        captured["url"] = url
        captured["data"] = data
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)
    with override_settings(HTML2DOCX_URL="http://html2docx:3030/convert"):
        docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))

    assert output_path.read_bytes() == b"docx-bytes"
    assert captured["url"] == "http://html2docx:3030/convert"
    assert captured["data"] == "<b>x</b>".encode("utf-8")


def test_html2docx_service_soft_fail_when_url_none(tmp_path, caplog):
    from nowe_raporty import docx_export

    output_path = tmp_path / "out.docx"
    with override_settings(HTML2DOCX_URL=None):
        with pytest.raises(RuntimeError):
            docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))
    assert "html2docx" in caplog.text.lower()


def test_html2docx_service_raises_on_error_status(monkeypatch, tmp_path):
    from nowe_raporty import docx_export

    output_path = tmp_path / "out.docx"

    class FakeResp:
        status_code = 500

        def raise_for_status(self):
            raise requests.HTTPError("500")

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with override_settings(HTML2DOCX_URL="http://html2docx:3030/convert"):
        with pytest.raises(requests.HTTPError):
            docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))
```

- [ ] **Step 2: Uruchom — testy mają failować (brak funkcji)**

Run: `uv run pytest src/nowe_raporty/tests/test_docx_export.py -k html2docx_service -x`
Expected: FAIL — `AttributeError: module 'nowe_raporty.docx_export' has no attribute '_convert_using_html2docx_service'`.

- [ ] **Step 3: Zaimplementuj funkcję i usuń dockerową**

W `src/nowe_raporty/docx_export.py`: usuń `import subprocess`, dodaj `import requests` i `from django.conf import settings` (jeśli brak). Usuń stałe `_DOCKER_IMAGE`/`_DOCKER_COMMAND` oraz całą `_convert_using_docker_image`. Dodaj:

```python
def _convert_using_html2docx_service(html: str, output_path: str) -> None:
    url = getattr(settings, "HTML2DOCX_URL", None)
    if not url:
        LOGGER.warning(
            "html2docx fallback niedostępny: HTML2DOCX_URL nieustawiony"
        )
        raise RuntimeError("HTML2DOCX_URL not configured")

    response = requests.post(
        url,
        data=html.encode("utf-8"),
        headers={"Content-Type": "text/html; charset=utf-8"},
        timeout=(5, 30),
    )
    response.raise_for_status()

    with open(output_path, "wb") as output_file:
        output_file.write(response.content)

    output_file_path = Path(output_path)
    if not output_file_path.exists() or output_file_path.stat().st_size == 0:
        raise RuntimeError("html2docx service produced no output")
```

- [ ] **Step 4: Przełącz oba miejsca wołające na nową funkcję**

W `as_docx` (ok. linii 82) i `html_to_docx` (ok. linii 231) zmień wywołanie:

```python
_convert_using_html2docx_service(cleaned_html, output_file.name)
```
oraz analogicznie w `html_to_docx`:
```python
_convert_using_html2docx_service(html, output_path)
```
Komunikaty `DocxConversionError` („DOCX conversion failed using both pandoc and html2docx") zostają bez zmian.

- [ ] **Step 5: Uruchom nowe testy — mają przejść**

Run: `uv run pytest src/nowe_raporty/tests/test_docx_export.py -k html2docx_service -v`
Expected: 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add src/nowe_raporty/docx_export.py src/nowe_raporty/tests/test_docx_export.py
git commit -m "feat(docx): fallback html2docx przez HTTP zamiast docker run (miekki fail)"
```

---

### Task B3: Napraw istniejące testy pod nowy fallback

**Files:**
- Modify: `src/nowe_raporty/tests/test_docx_export.py`

**Interfaces:**
- Consumes: `_convert_using_html2docx_service` (B2).

- [ ] **Step 1: Uruchom cały plik — zobacz co pękło po usunięciu dockera**

Run: `uv run pytest src/nowe_raporty/tests/test_docx_export.py -v`
Expected: FAIL w testach odnoszących się do `_convert_using_docker_image` / `subprocess` / integration `docker run` (`test_as_docx_falls_back_to_docker`, `test_as_docx_raises_when_both_converters_fail`, `test_convert_using_docker_image_*`, integration).

- [ ] **Step 2: Przepnij testy fallbacku na nową funkcję**

W `test_as_docx_falls_back_to_docker` i `test_as_docx_raises_when_both_converters_fail` zmień:
```python
monkeypatch.setattr(docx_export, "_convert_using_docker_image", docker_fallback)
```
na:
```python
monkeypatch.setattr(docx_export, "_convert_using_html2docx_service", docker_fallback)
```
(nazwy lokalnych helperów `docker_fallback` możesz zostawić lub przemianować na `service_fallback` — bez znaczenia funkcjonalnego).

- [ ] **Step 3: Usuń martwe testy dockerowe**

Usuń testy operujące bezpośrednio na `subprocess`/`_convert_using_docker_image`
(`test_convert_using_docker_image_success`, `test_convert_using_docker_image_with_stderr`,
`test_convert_using_docker_image_*`, custom-image test na `HTML2DOCX_DOCKER_IMAGE`)
oraz integration-test wołający realny `docker run iplweb/html2docx`. Zastępuje je
`test_html2docx_service_*` z B2. Usuń nieużywany `import subprocess`.

- [ ] **Step 4: Uruchom cały plik — zielono**

Run: `uv run pytest src/nowe_raporty/tests/test_docx_export.py -v`
Expected: wszystkie PASS, brak referencji do dockera.

- [ ] **Step 5: Commit**

```bash
git add src/nowe_raporty/tests/test_docx_export.py
git commit -m "test(docx): przepnij testy fallbacku z docker na usluge HTTP"
```

---

### Task B4: Zdejmij Docker CLI z obrazu appservera

**Files:**
- Modify: `docker/appserver/Dockerfile`

**Interfaces:**
- (brak — zmiana obrazu)

- [ ] **Step 1: Usuń stage docker-cli i COPY**

W `docker/appserver/Dockerfile` usuń:
```dockerfile
ARG BPP_BASE_TAG=latest
FROM docker:cli AS docker-cli
```
(zostaw samą linię `ARG BPP_BASE_TAG=latest` — jest potrzebna dla `FROM iplweb/bpp_base:${BPP_BASE_TAG}`) oraz usuń:
```dockerfile
# Copy Docker CLI from official image (fast - ~5s vs ~70s apt install)
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
```
Wynik: brak `FROM docker:cli`, brak `COPY --from=docker-cli`. `ARG BPP_BASE_TAG=latest` pozostaje nad `FROM iplweb/bpp_base`.

- [ ] **Step 2: Zweryfikuj składnię Dockerfile (bez pełnego builda)**

Run: `docker build --check -f docker/appserver/Dockerfile .`
Expected: brak błędów składni (`--check` nie buduje, tylko waliduje). Jeśli `--check` niedostępny w wersji Dockera — pomiń, walidacja nastąpi w CI build test-runnera.

- [ ] **Step 3: Commit**

```bash
git add docker/appserver/Dockerfile
git commit -m "refactor(docker): usun Docker CLI z obrazu appservera (niepotrzebny po HTTP fallbacku)"
```

---

### Task B5: Dev compose (opcjonalnie) + newsfragment + docs

**Files:**
- Modify: `docker-compose.yml` (dev)
- Create: `src/bpp/newsfragments/<slug>.bugfix.rst`
- Modify: `docs/deweloper/` (krótka notka o kontrakcie)

**Interfaces:**
- (brak)

- [ ] **Step 1: Dodaj serwis html2docx do dev compose**

W `docker-compose.yml` dodaj serwis (obok innych) i env na `appserver`:

```yaml
  html2docx:
    image: iplweb/html2docx:latest
    restart: unless-stopped
    # brak published portu — tylko sieć wewnętrzna compose
```
oraz w bloku `appserver` (environment):
```yaml
      DJANGO_BPP_HTML2DOCX_URL: "http://html2docx:3030/convert"
```

- [ ] **Step 2: Zweryfikuj poprawność YAML**

Run: `uv run python -c "import yaml,sys; yaml.safe_load(open('docker-compose.yml')); print('yaml ok')"`
Expected: `yaml ok`.

- [ ] **Step 3: Newsfragment**

Utwórz `src/bpp/newsfragments/html2docx-http.bugfix.rst`:

```rst
Fallback konwersji DOCX (html2docx) działa teraz przez usługę HTTP zamiast
uruchamiania kontenera przez ``docker.sock``. Appserver nie potrzebuje już
dostępu do demona Dockera hosta ani Docker CLI w obrazie. Adres usługi podaje
zmienna środowiskowa ``DJANGO_BPP_HTML2DOCX_URL`` (brak = fallback wyłączony).
```

- [ ] **Step 4: Notka w docs o kontrakcie**

Dopisz krótką sekcję (np. w `docs/deweloper/polecenia.md` lub nowy plik `docs/deweloper/html2docx.md`) opisującą: usługę `iplweb/html2docx` w trybie serwera, port 3030 (`HTML2DOCX_PORT`), `POST /convert` (body=HTML, resp=docx), `GET /health`, oraz konfigurację `DJANGO_BPP_HTML2DOCX_URL` po stronie bpp.

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml src/bpp/newsfragments/html2docx-http.bugfix.rst docs/
git commit -m "docs+dev: serwis html2docx w dev compose, newsfragment, notka o kontrakcie"
```

---

### Task B6: Weryfikacja end-to-end (bpp ↔ realna usługa)

**Files:**
- (brak zmian — weryfikacja)

**Interfaces:**
- Consumes: obraz `html2docx:a3` (Faza A) + `_convert_using_html2docx_service` (B2).

- [ ] **Step 1: Uruchom usługę i wywołaj fallback z Pythona**

```bash
CID=$(docker run -d -p 13030:3030 html2docx:a3)
sleep 4
DJANGO_BPP_SKIP_DOTENV=1 DJANGO_BPP_HTML2DOCX_URL=http://localhost:13030/convert \
  uv run python -c "
import django; django.setup()
from nowe_raporty import docx_export
import tempfile, pathlib
p = tempfile.NamedTemporaryFile(suffix='.docx', delete=False).name
docx_export._convert_using_html2docx_service('<table><tr><td><b>Ala</b></td></tr></table>', p)
print('bytes', pathlib.Path(p).stat().st_size)
"
docker rm -f "$CID"
```
Expected: `bytes` > 0 (realny docx wygenerowany przez usługę przez ścieżkę Pythona).

- [ ] **Step 2: Pełna suita modułu**

Run: `uv run pytest src/nowe_raporty/tests/test_docx_export.py -v`
Expected: wszystkie PASS.

- [ ] **Step 3: ruff**

Run: `ruff check src/nowe_raporty/docx_export.py src/nowe_raporty/tests/test_docx_export.py src/django_bpp/settings/base.py`
Expected: brak naruszeń (m.in. brak nieużywanego `subprocess`).

---

## Kolejność i handoff

1. **Faza A** (repo html2docx) — dostarcz usługę, zbuduj/zweryfikuj obraz.
2. **Faza B** (repo bpp) — klient + testy + odchudzenie obrazu appservera.
3. **B6** — weryfikacja end-to-end bpp ↔ realna usługa.
4. **Handoff do usera:** publikacja obrazu `iplweb/html2docx:<tag>` **przed** przepięciem deploya; wiring `docker-compose.application.yml` (serwis + env + zdjęcie socketa) robi user sam (poza planem).

## Self-review (spec coverage)

- Kontrakt HTTP (POST /convert, GET /health, 100 MB, port 3030 + env) → A3, Global Constraints. ✓
- Tryb CLI zostaje → A2/A3 Step 6. ✓
- Config `HTML2DOCX_URL` z env default None → B1. ✓
- Miękki fail → B2 Step 1/3 (test + impl). ✓
- Timeouty 5/30 → B2 Step 3. ✓
- Oba call-sites przełączone → B2 Step 4. ✓
- Docker CLI usunięty z appservera → B4. ✓
- Testy przepięte, docker-testy usunięte → B3. ✓
- Newsfragment + docs → B5. ✓
- Deploy poza zakresem, handoff → Kolejność i handoff. ✓
