"""
Smoke testy integralnosci HTML po przejsciu przez BppMinifyHtmlMiddleware.

Cel: zlapac regresje typu "footer wskakuje pod tabele" zanim trafia na
prod. minify-html (Rust engine pod django-minify-html) na pelnym
dokumencie restrukturyzuje DOM gdy w treningowym HTML-u sa puste/
niezamkniete tagi (np. <li class="ellipsis"></li>, <p/>, <span/>).
Plus: HTMX swap-uje fragmenty - dla nich minifier ma byc bypassowany.
"""

from html.parser import HTMLParser

from django.http import HttpResponse
from django.test import RequestFactory

from django_bpp.settings.production import BppMinifyHtmlMiddleware

VOID_HTML5 = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "source",
    "track",
    "wbr",
}

NESTING_FORBIDDEN_FOR_FOOTER = {
    "table",
    "tbody",
    "thead",
    "tfoot",
    "tr",
    "td",
    "th",
    "form",
    "ul",
    "ol",
    "li",
    "p",
    "span",
    "main",
    "nav",
}


class _StackParser(HTMLParser):
    """Sledzi stack tagow + zapamietuje rodzicow wybranych elementow."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.footer_parents: list[list[str]] = []
        self.main_parents: list[list[str]] = []

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "") or ""
        if tag == "footer" or "footer-container" in classes.split():
            self.footer_parents.append(list(self.stack))
        if tag == "main":
            self.main_parents.append(list(self.stack))
        if tag not in VOID_HTML5:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_HTML5:
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.stack.pop()
            if self.stack:
                self.stack.pop()


def _assert_footer_not_nested(html: str) -> None:
    parser = _StackParser()
    parser.feed(html)
    assert parser.footer_parents, "Test setup blad: brak <footer> w HTML"
    for parents in parser.footer_parents:
        bad = NESTING_FORBIDDEN_FOR_FOOTER.intersection(parents)
        assert not bad, (
            f"Footer zagniezdzony w {bad}; pelna sciezka rodzicow: {parents}\n"
            f"Snippet HTML: {html[:500]}..."
        )


def _run_through_middleware(content: str, *, request=None) -> str:
    response = HttpResponse(content, content_type="text/html; charset=utf-8")
    if request is None:
        request = RequestFactory().get("/")
    middleware = BppMinifyHtmlMiddleware(get_response=lambda r: response)
    middleware.maybe_minify(request, response)
    return response.content.decode(response.charset)


# ---------------------------------------------------------------------------
# Canary: kazdy z trzech ostatnich incydentow odtworzony minimalnym HTML-em.
# Asercja: po minify struktura sie nie rozjezdza.
# ---------------------------------------------------------------------------

CANARY_PAGINATION_EMPTY_LI = """<!DOCTYPE html>
<html><head><title>x</title></head><body>
<header><h1>H</h1></header>
<main>
  <table><tr><td>row</td></tr></table>
  <ul class="pagination">
    <li class="current"><span>1</span></li>
    <li class="ellipsis" aria-hidden="true"><span>&hellip;</span></li>
    <li><a href="?p=5">5</a></li>
  </ul>
</main>
<footer>Stopka</footer>
</body></html>
"""

CANARY_SELF_CLOSING_P = """<!DOCTYPE html>
<html><head><title>x</title></head><body>
<main>
  <div class="cell"><p/>
    <div id="messagesPlaceholder"></div>
  </div>
</main>
<footer>Stopka</footer>
</body></html>
"""

CANARY_SELF_CLOSING_SPAN = """<!DOCTYPE html>
<html><head><title>x</title></head><body>
<main>
  <button>
    <span class="fi-alert"/> Wyslij
  </button>
</main>
<footer>Stopka</footer>
</body></html>
"""


def test_pagination_with_ellipsis_li_survives_minification():
    """
    Pusty <li class="ellipsis"></li> w paginacji byl bombem zegarowym -
    minifier moglby uznac za redundantny element i usunac, rozbijajac
    nesting <ul>. Po fix-ie: pusty li MA zawartosc <span>&hellip;</span>.
    """
    out = _run_through_middleware(CANARY_PAGINATION_EMPTY_LI)
    _assert_footer_not_nested(out)


def test_self_closing_p_does_not_swallow_following_block():
    """
    <p/> w base.html linie 240/266 byl placeholderem - browser to lata
    automatycznie, ale minifier mogl go potraktowac roznie. Po fix-ie:
    placeholder usuniety calkowicie.
    """
    out = _run_through_middleware(CANARY_SELF_CLOSING_P)
    _assert_footer_not_nested(out)


def test_self_closing_span_corrupts_dom_after_minification():
    """
    NEGATIVE sentinel: dokumentuje, ze ``minify-html`` DALEJ rozjezdza
    DOM gdy templat zawiera self-closing tag na non-void elemencie
    (np. ``<span class="fi-alert"/>`` wewnatrz ``<button>``). To wlasnie
    chroni djlint H020/H025 + ten plik testowy.

    Jesli kiedys ``minify-html`` naprawi to zachowanie (lub zmienisz
    silnik), ten test failnie i bedzie sygnal, ze mozna poluzowac
    restrykcje wokol self-closing non-void.
    """
    out = _run_through_middleware(CANARY_SELF_CLOSING_SPAN)
    parser = _StackParser()
    parser.feed(out)
    assert parser.footer_parents, "Test setup blad: brak <footer> w out"
    nested_in_bad_parent = any(
        NESTING_FORBIDDEN_FOR_FOOTER.intersection(parents)
        for parents in parser.footer_parents
    )
    assert nested_in_bad_parent, (
        "Niespodzianka: minify-html nie psuje juz DOM przy self-closing "
        "<span/> wewnatrz <button>. Mozesz poluzowac djlint H025 i "
        "ten test usunac/zaktualizowac."
    )


# ---------------------------------------------------------------------------
# HTMX skip: BppMinifyHtmlMiddleware ma omijac minifikacje gdy header
# HX-Request: true (fragmenty z hx-swap=innerHTML, nie pelne dokumenty).
# ---------------------------------------------------------------------------

HTMX_FRAGMENT = (
    "<table>\n  <tr><td>row 1</td></tr>\n  <tr><td>row 2</td></tr>\n</table>\n"
)


def test_htmx_request_bypasses_minifier():
    """
    Fragment HTMX powinien przejsc przez middleware bez minifikacji
    (zachowane whitespace/newlines = nie zostal zmieniony).
    """
    request = RequestFactory().get("/", HTTP_HX_REQUEST="true")
    out = _run_through_middleware(HTMX_FRAGMENT, request=request)
    assert out == HTMX_FRAGMENT, (
        f"HTMX fragment zostal jednak zminifikowany; oryginal:\n"
        f"{HTMX_FRAGMENT!r}\nout:\n{out!r}"
    )


def test_non_htmx_request_still_gets_minified():
    """
    Sanity check: zwykly request DALEJ przechodzi przez minifier
    (whitespace zostaje zredukowany wewnatrz tagow).
    """
    request = RequestFactory().get("/")
    out = _run_through_middleware(HTMX_FRAGMENT, request=request)
    # fragment 'text/html' bez <html> tag - minifier i tak moze go
    # skrocic; sprawdzamy ze co najmniej jakis whitespace zostal usuniety.
    assert out != HTMX_FRAGMENT, (
        "Non-HTMX request nie zostal zminifikowany - minifier nie dziala?"
    )
