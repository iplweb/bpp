"""
Smoke test dla anonimowego użytkownika.

Crawluje serwis jako użytkownik niezalogowany, sprawdzając:
- błędy HTTP (404, 500, itp.)
- błędy JavaScript w konsoli przeglądarki
"""

from urllib.parse import urljoin, urlparse

import pytest
from playwright.sync_api import Page

# Wzorce błędów konsoli do ignorowania
CONSOLE_IGNORE_PATTERNS = [
    "favicon.ico",
    "FontAwesome",
    "Failed to load resource",
    "net::ERR_",
    "WebSocket",  # WebSocket nie działa w live_server (tylko HTTP)
    "DAL function",  # django-autocomplete-light warning about double registration
    "select2",  # select2 library warnings
]

# Wzorce URL do pomijania
URL_SKIP_PATTERNS = [
    # "/admin/",
    # "/logout/",
    # "/login/",
    ".pdf",
    ".xlsx",
    ".xls",
    ".docx",
    ".doc",
    ".zip",
    ".rar",
    # "/api/",
    "/media/",
    "javascript:",
    "mailto:",
    "#",
    "{{",  # unrendered JS/Vue templates
    "}}",
    "/nowe_raporty/",  # requires uczelnia settings + authentication
]


@pytest.fixture
def console_errors(page: Page):
    """
    Zbiera błędy JS z konsoli przeglądarki.

    Niektóre błędy są ignorowane (np. błędy związane z FontAwesome,
    zewnętrznymi zasobami).
    """
    errors = []

    def handle_console(msg):
        if msg.type == "error":
            text = msg.text
            if any(pattern in text for pattern in CONSOLE_IGNORE_PATTERNS):
                return
            errors.append(
                {
                    "text": text,
                    "url": page.url,
                }
            )

    page.on("console", handle_console)
    return errors


@pytest.fixture
def test_data(
    uczelnia,
    wydzial,
    jednostka,
    autor_jan_nowak,
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
):
    """Fixture łączący wszystkie dane testowe."""
    return {
        "uczelnia": uczelnia,
        "wydzial": wydzial,
        "jednostka": jednostka,
        "autor": autor_jan_nowak,
        "ciagle": wydawnictwo_ciagle,
        "zwarte": wydawnictwo_zwarte,
    }


def _should_visit(url, visited, base_url):
    """Sprawdza czy URL powinien być odwiedzony."""
    if not url or _url_without_query(url) in visited:
        return False

    parsed = urlparse(url)
    base_parsed = urlparse(base_url)

    if parsed.netloc and parsed.netloc != base_parsed.netloc:
        return False

    if any(skip in url for skip in URL_SKIP_PATTERNS):
        return False

    return True


def _normalize_url(href, current_url):
    """Normalizuje URL względem aktualnej strony."""
    if not href:
        return None

    if href.startswith("#") or href.startswith("javascript:"):
        return None

    if href.startswith("http://") or href.startswith("https://"):
        return href

    return urljoin(current_url, href)


def _url_without_query(url):
    """Returns URL path without query parameters for deduplication."""
    parsed = urlparse(url)
    # Keep scheme, netloc, and path; drop query and fragment
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _collect_links(page, current_url, base_url):
    """Zbiera wszystkie linki ze strony."""
    hrefs = []
    try:
        # Wait for JS to remove fouc-hidden class (page uses this pattern)
        page.wait_for_function(
            "document.querySelector('body') && "
            "!document.body.classList.contains('fouc-hidden')",
            timeout=5000,
        )
    except Exception:
        # Continue even if fouc doesn't clear (might not be present)
        pass

    try:
        # Use JavaScript to get all links for better reliability
        hrefs_raw = page.evaluate("""
            () => Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.getAttribute('href'))
                .filter(h => h)
        """)

        for href in hrefs_raw:
            normalized = _normalize_url(href, current_url)
            if normalized:
                hrefs.append(normalized)
    except Exception as e:
        print(f"  Error collecting links from {current_url}: {e}")
    return hrefs


def _visit_page(page, url, visited, http_errors, base_url):
    """Odwiedza stronę i zwraca listę linków."""
    visited.add(_url_without_query(url))

    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)

        if response and response.status >= 400:
            http_errors.append({"url": url, "status": response.status})
            return []

        # Wait for page to stabilize
        try:
            page.wait_for_load_state("networkidle", timeout=10000)
        except Exception:
            # networkidle may timeout due to long-polling, continue anyway
            pass

        # Accept cookies if banner exists
        try:
            page.evaluate("if(window.Cookielaw) Cookielaw.accept()")
        except Exception:
            pass

        return _collect_links(page, url, base_url)

    except Exception as e:
        http_errors.append({"url": url, "error": str(e)})
        return []


def _crawl_recursive(page, url, depth, max_depth, visited, http_errors, base_url):
    """Rekursywnie crawluje stronę."""
    if depth > max_depth or not _should_visit(url, visited, base_url):
        return

    hrefs = _visit_page(page, url, visited, http_errors, base_url)

    for href in hrefs:
        if _should_visit(href, visited, base_url):
            _crawl_recursive(
                page, href, depth + 1, max_depth, visited, http_errors, base_url
            )


def _print_report(visited, http_errors, console_errors):
    """Drukuje raport z crawlingu."""
    print("\n=== Smoke Test Report ===")
    print(f"Odwiedzono stron: {len(visited)}")
    print(f"Błędy HTTP: {len(http_errors)}")
    print(f"Błędy JS: {len(console_errors)}")

    if visited:
        print("\nOdwiedzone strony:")
        for url in sorted(visited):
            print(f"  - {url}")

    if http_errors:
        print("\nBłędy HTTP:")
        for err in http_errors:
            if "status" in err:
                print(f"  - [{err['status']}] {err['url']}")
            else:
                print(f"  - [ERROR] {err['url']}: {err.get('error', 'unknown')}")

    if console_errors:
        print("\nBłędy JavaScript:")
        for err in console_errors:
            print(f"  - {err['url']}: {err['text'][:100]}")


@pytest.mark.django_db(transaction=True)
def test_anonymous_smoke_crawl(
    page: Page,
    live_server,
    test_data,
    console_errors,
):
    """
    Smoke test: crawluje stronę jako anonimowy użytkownik.

    - Zaczyna od strony głównej
    - Zbiera wszystkie linki i odwiedza je rekursywnie (do max_depth)
    - Sprawdza kody HTTP >= 400
    - Zbiera błędy JavaScript z konsoli
    """
    visited = set()
    http_errors = []
    base_url = live_server.url

    _crawl_recursive(page, base_url + "/", 0, 3, visited, http_errors, base_url)

    _print_report(visited, http_errors, console_errors)

    assert len(http_errors) == 0, f"HTTP errors found: {http_errors}"
    assert len(console_errors) == 0, f"JS console errors: {console_errors}"
