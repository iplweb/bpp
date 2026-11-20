#!/usr/bin/env python
"""Annotated screenshots for the documentation and the Freshdesk knowledge base.

Rules and the full how-to: docs/deweloper/zrzuty-ekranu.md

Usage (with a run-site stack on the Witcher demo data running):

    uv run python bin/docs-screenshots.py --base http://localhost:PORT moj-profil-autora
    uv run python bin/docs-screenshots.py --list

Each scenario writes PNGs to docs/images/<section>/<scenario>/. Highlights and
arrows are drawn as an SVG overlay *inside the page*, anchored to real DOM
elements, so re-running after a UI change re-places them automatically.
"""

from __future__ import annotations

import argparse
import base64
import sys
from pathlib import Path

from playwright.sync_api import Page, sync_playwright
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

REPO = Path(__file__).resolve().parent.parent
IMAGES = REPO / "docs" / "images"

# Demo account created per docs/deweloper/zrzuty-ekranu.md — an ordinary
# author (no staff/superuser), so screenshots show what a typical user sees.
DEMO_USER = "yennefer"
# Local throwaway demo DB only; password == username keeps secret scanners quiet.
DEMO_PASSWORD = DEMO_USER
# Second demo account with NO linked author, for "Brak powiązania z autorem".
DEMO_USER_BEZ_AUTORA = "jaskier"
# Third demo account in the group "generowanie raportów" (reports, slots).
DEMO_USER_RAPORTY = "filippa"
DEMO_USER_REDAKTOR = "vesemir"  # demo editor: is_staff + "wprowadzanie danych"

VIEWPORT = {"width": 1280, "height": 800}

# The Freshdesk "Pomoc" launcher floats over whatever we're explaining.
HIDE_HELP_LAUNCHER = (
    "document.addEventListener('DOMContentLoaded', () => {"
    " const s = document.createElement('style');"
    " s.textContent = '#freshworks-container, #launcher-frame, #bppSupportButton"
    " { display: none !important }';"
    " document.head.appendChild(s); });"
)

# One shared look for every screenshot: red (#e8173c) 4px highlight box,
# 5px curved arrow, bold label in a white rounded pill, drop shadow on both
# arrow and pill so labels stay readable on any background.
OVERLAY_JS = r"""
([marks]) => {
  document.getElementById('kb-overlay')?.remove();
  const W = document.documentElement.scrollWidth, H = document.documentElement.scrollHeight;
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.id = 'kb-overlay';
  svg.setAttribute('width', W); svg.setAttribute('height', H);
  svg.style.cssText = 'position:absolute;left:0;top:0;pointer-events:none;z-index:2147483647';
  // userSpaceOnUse: with the default objectBoundingBox units a perfectly
  // straight (zero-height) arrow gets a zero-height filter region and vanishes.
  svg.innerHTML = `<defs><marker id="kbh" viewBox="0 0 10 10" refX="8" refY="5"
      markerWidth="5" markerHeight="5" orient="auto-start-reverse">
      <path d="M0,0 L10,5 L0,10 z" fill="#e8173c"/></marker>
      <filter id="kbs" filterUnits="userSpaceOnUse" x="0" y="0" width="${W}" height="${H}">
        <feDropShadow dx="0" dy="3" stdDeviation="3.5" flood-color="#000" flood-opacity="0.45"/>
      </filter></defs>`;
  document.body.appendChild(svg);  // must be in the DOM before getBBox()
  const set = (el, attrs) => Object.entries(attrs).forEach(([k, v]) => el.setAttribute(k, v));
  for (const m of marks) {
    // m.text: pick the first m.sel element whose text contains it (for
    // sections that only differ by their heading).
    const el = m.text
      ? [...document.querySelectorAll(m.sel)].find(e => e.textContent.includes(m.text))
      : document.querySelector(m.sel);
    if (!el) throw new Error('no element: ' + m.sel + (m.text ? ' / ' + m.text : ''));
    const r = el.getBoundingClientRect();
    const x = r.left + scrollX - 6, y = r.top + scrollY - 6, w = r.width + 12, h = r.height + 12;
    const rect = document.createElementNS(ns, 'rect');
    set(rect, {x, y, width: w, height: h, rx: 8, fill: 'none', stroke: '#e8173c', 'stroke-width': 4});
    svg.appendChild(rect);
    if (!m.arrow) continue;
    // m.arrow = side the arrow comes FROM; m.dx/m.dy move the label start
    // point to steer it into empty space.
    const cx = x + w / 2, cy = y + h / 2, d = 110, ox = m.dx || 0, oy = m.dy || 0;
    const [sx, sy, ex, ey] = {
      left:  [x - d + ox, cy + 40 + oy, x - 8, cy],
      right: [x + w + d + ox, cy + 40 + oy, x + w + 8, cy],
      below: [cx + 60 + ox, y + h + d + oy, cx, y + h + 8],
      above: [cx + 60 + ox, y - d + oy, cx, y - 8],
    }[m.arrow];
    const p = document.createElementNS(ns, 'path');
    set(p, {d: `M${sx},${sy} Q${(sx + ex) / 2},${sy} ${ex},${ey}`, fill: 'none',
            stroke: '#e8173c', 'stroke-width': 5, 'stroke-linecap': 'round',
            'marker-end': 'url(#kbh)', filter: 'url(#kbs)'});
    svg.appendChild(p);
    if (!m.label) continue;
    const t = document.createElementNS(ns, 'text');
    set(t, {x: m.arrow === 'left' ? sx - 6 : sx + 6, y: sy + 8,
            'text-anchor': m.arrow === 'left' ? 'end' : 'start'});
    t.style.cssText = 'font:700 22px system-ui,sans-serif;fill:#e8173c';
    t.textContent = m.label;
    svg.appendChild(t);
    const b = t.getBBox(), pad = 8;
    const bg = document.createElementNS(ns, 'rect');
    set(bg, {x: b.x - pad, y: b.y - pad / 2, width: b.width + 2 * pad, height: b.height + pad,
             rx: 10, fill: '#fff', stroke: '#e8173c', 'stroke-width': 3, filter: 'url(#kbs)'});
    svg.insertBefore(bg, t);
  }
}
"""


def mark(page: Page, marks: list[dict]) -> None:
    """Draw highlight boxes/arrows/labels. Each mark: sel, text?, arrow?, label?, dx?, dy?"""
    page.evaluate(OVERLAY_JS, [marks])


def login(page: Page, base: str, user: str = DEMO_USER) -> None:
    page.goto(f"{base}/accounts/login/")
    page.fill("input[name=username]", user)
    page.fill("input[name=password]", user)  # demo accounts: password == login
    page.locator("form [type=submit]").first.click()
    page.wait_for_load_state("networkidle")
    if "/accounts/login/" in page.url:
        raise SystemExit(
            f"Login as {user!r} failed - create the demo account first "
            "(docs/deweloper/zrzuty-ekranu.md)."
        )
    close_cookie_banner(page)


def close_cookie_banner(page: Page) -> None:
    """The cookie banner would cover the lower part of every full-page shot."""
    agree = page.get_by_role("button", name="Zgadzam się")
    if agree.count():
        agree.first.click()


# --------------------------------------------------------------------------
# Scenarios: one function per documentation page / KB article.
# --------------------------------------------------------------------------


def moj_profil_autora(page: Page, base: str, out: Path) -> None:
    """docs/uzytkownik/moj-profil-autora.md + KB 'Jak samodzielnie edytować swoją stronę autora'."""
    # 1. top bar: open the "konto" menu
    page.goto(f"{base}/")
    page.wait_for_load_state("networkidle")
    page.hover("#konto-menu-item > a")
    page.wait_for_selector("#konto-submenu a[href*='profil']", state="visible")
    page.wait_for_timeout(800)  # let the dropdown finish its fade-in
    mark(
        page,
        [
            {
                "sel": "#konto-menu-item > a",
                "arrow": "right",
                "label": "1. konto",
                "dy": -40,
            },
            {
                "sel": "#konto-submenu a[href*='profil']",
                "arrow": "right",
                "label": "2. mój profil",
            },
        ],
    )
    page.screenshot(
        path=out / "01-menu-konto.png",
        clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": 300},
    )

    # 2. profile page: "Edytuj swoją stronę"
    page.mouse.move(5, 700)
    page.click("#konto-submenu a[href*='profil']", force=True)
    page.wait_for_load_state("networkidle")
    edit = "a.button[href*='edycja']"
    page.locator(edit).first.scroll_into_view_if_needed()
    mark(page, [{"sel": edit, "arrow": "left", "label": "kliknij"}])
    box = page.locator("div.callout.success").first.bounding_box()
    page.screenshot(
        path=out / "02-profil-edytuj.png",
        full_page=True,
        clip={
            "x": 0,
            "y": max(0, box["y"] - 30),
            "width": VIEWPORT["width"],
            "height": box["height"] + 150,
        },
    )

    # 3. the edit form
    page.click(edit)
    page.wait_for_load_state("networkidle")
    mark(
        page,
        [
            {
                "sel": "fieldset:nth-of-type(1) legend",
                "arrow": "right",
                "label": "zdjęcie",
            },
            {
                "sel": "fieldset:nth-of-type(2) legend",
                "arrow": "right",
                "label": "biogram",
            },
            {
                "sel": "fieldset:nth-of-type(3) legend",
                "arrow": "right",
                "label": "profile w innych serwisach",
            },
            {
                "sel": "button.button.primary.large[type=submit]",
                "arrow": "above",
                "label": "na koniec zapisz",
                "dx": 260,
                "dy": 75,
            },
        ],
    )
    page.screenshot(path=out / "03-formularz-edycji.png", full_page=True)


# A made-up department page standing in for "your own website" in the widget
# screenshots. Served by page.route() under a fake https:// origin, so the
# widget really runs cross-origin, exactly as on a customer site.
EXAMPLE_SITE = "https://katedra.example"
# What readers should see as "your university's BPP" in URLs and code snippets.
# Requests to it are proxied to the local stack (see proxy_public_bpp).
PUBLIC_BPP = "https://bpp.twoja-uczelnia.pl"
EXAMPLE_PAGE = """<!doctype html><html lang="pl"><head><meta charset="utf-8">
<title>dr Yennefer z Vengerbergu — Katedra Magii Stosowanej</title>
<style>
 body{margin:0;font:16px/1.5 Georgia,serif;color:#2b2233;background:#f6f3ee}
 header{background:#3b1f4a;color:#fff;padding:18px 40px}
 header b{font-size:22px} header span{opacity:.75;margin-left:14px}
 nav{background:#5a3570;padding:8px 40px} nav a{color:#fff;margin-right:22px;
   text-decoration:none;font:14px system-ui,sans-serif}
 main{display:flex;gap:40px;padding:30px 40px 170px;max-width:1100px}
 aside{flex:0 0 220px} .foto{width:200px;height:200px;border-radius:8px;
   background:linear-gradient(135deg,#7b4b94,#2b1638)}
 article{flex:1} h1{margin:0 0 4px} .rola{color:#6d5a78;margin:0 0 18px}
 h2{border-bottom:2px solid #c9b8d4;padding-bottom:4px}
</style></head><body>
<header><b>Aretuza — Akademia Magii</b><span>Katedra Magii Stosowanej</span></header>
<nav><a href="#">Aktualności</a><a href="#">Pracownicy</a><a href="#">Dydaktyka</a>
<a href="#">Badania</a><a href="#">Kontakt</a></nav>
<main><aside><div class="foto"></div><p>pok. 12, Wieża Wschodnia<br>
dyżur: wtorek 10–12</p></aside>
<article><h1>dr Yennefer z Vengerbergu</h1><p class="rola">adiunkt</p>
<p>Zajmuje się teorią i praktyką magii stosowanej, w szczególności
zaklęciami ochronnymi i teleportacją.</p>
<h2>Najnowsze publikacje</h2>
<script src="__BASE__/static/embed/bpp-publikacje.js"
        data-autor="__AUTOR__" data-limit="5" async></script>
</article></main></body></html>"""


def page_box(page: Page, sel: str, text: str | None = None) -> dict:
    """Element box in *page* coordinates (bounding_box() is viewport-relative,
    which is wrong for full_page clips once the page has scrolled)."""
    return page.evaluate(
        """([sel, text]) => {
        const el = text ? [...document.querySelectorAll(sel)].find(e => e.textContent.includes(text))
                        : document.querySelector(sel);
        const r = el.getBoundingClientRect();
        return {x: r.left + scrollX, y: r.top + scrollY, width: r.width, height: r.height}; }""",
        [sel, text],
    )


# A demo record by Yennefer with points and slots (after the slot fix-up of
# the demo DB, docs/deweloper/zrzuty-ekranu.md).
REKORD_ZE_SLOTAMI = "szlaku-wiedzminskiego-studium-przypadku-sile-znakow-nr-271-Acta-Oxenfurcka-Merigold-Y-6-871"


# "Torn paper" gap between two parts of one long page, so a single image can
# show both where you are (top) and what to click (far below).
STITCH_HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
 body{margin:0;background:#fff;width:__W__px}
 img{display:block;width:__W__px}
 .cut{position:relative;height:64px;background:#e9e9ee;
   display:flex;align-items:center;justify-content:center;
   font:600 18px system-ui,sans-serif;color:#555}
 .cut svg{position:absolute;left:0;width:100%;height:14px}
 .cut .t{top:0} .cut .b{bottom:0;transform:scaleY(-1)}
</style></head><body>__PARTS__</body></html>"""
CUT = (
    '<div class="cut">'
    + "".join(
        f'<svg class="{c}" viewBox="0 0 100 14" preserveAspectRatio="none">'
        '<polygon fill="#fff" points="0,0 100,0 '
        + " ".join(f"{100 - i},{10 if i % 4 else 2}" for i in range(0, 101, 2))
        + '"/></svg>'
        for c in ("t", "b")
    )
    + "✂&nbsp; __LABEL__ &nbsp;✂</div>"
)


def stitch(page: Page, parts: list[bytes], path: Path, label: str) -> None:
    """Save parts (PNG bytes, top to bottom) as one image joined by torn-edge gaps."""
    imgs = [
        f'<img src="data:image/png;base64,{base64.b64encode(b).decode()}">'
        for b in parts
    ]
    html = STITCH_HTML.replace("__W__", str(VIEWPORT["width"])).replace(
        "__PARTS__", CUT.replace("__LABEL__", label).join(imgs)
    )
    tmp = page.context.new_page()
    tmp.set_content(html)
    tmp.screenshot(path=path, full_page=True)
    tmp.close()


def proxy_public_bpp(page: Page, base: str) -> None:
    """Answer PUBLIC_BPP requests from the local stack, so screenshots show a
    realistic address instead of http://localhost:PORT. It also keeps every
    request same-scheme (https page -> https "server"), so Chromium's
    mixed-content and local-network checks never trigger."""

    def handle(route):
        local = base + route.request.url[len(PUBLIC_BPP) :]
        resp = route.fetch(url=local)
        body = resp.body().replace(base.encode(), PUBLIC_BPP.encode())
        route.fulfill(response=resp, body=body)

    page.route(PUBLIC_BPP + "/**", handle)


def serve_docs_locally(page: Page) -> None:
    """Serve the GitHub Pages docs from a local `mkdocs build` (REPO/site).

    The author page links to the code generator on iplweb.github.io. That page
    is HTTPS and our local BPP is plain http, so the browser would block the
    live preview as mixed content — hence the local copy, at the same URL.
    """
    site = REPO / "site"
    if not (site / "index.html").exists():
        raise SystemExit("Build the docs first: mkdocs build  (writes ./site)")
    prefix = "https://iplweb.github.io/bpp/"

    def handle(route):
        rel = route.request.url.split("?")[0].split("#")[0][len(prefix) :]
        path = site / rel
        if path.is_dir():
            path = path / "index.html"
        if path.is_file():
            route.fulfill(path=str(path))
        else:
            route.fulfill(status=404, body="not found")

    page.route(prefix + "**", handle)


def widget_publikacji(page: Page, base: str, out: Path) -> None:
    """docs/uzytkownik/widget-publikacji.md + KB 'Jak wstawić listę swoich publikacji na stronę WWW'."""
    # 1. author page: the "Osadź publikacje…" link at the bottom
    page.goto(f"{base}/bpp/profil/")
    page.wait_for_load_state("networkidle")
    page.click("a[href*='/bpp/autor/']")  # "Powiązany autor" -> own author page
    page.wait_for_load_state("networkidle")
    link = ".autor-page__embed-link a"
    w = VIEWPORT["width"]
    top = page.screenshot(clip={"x": 0, "y": 0, "width": w, "height": 420})
    page.locator(link).scroll_into_view_if_needed()
    mark(
        page, [{"sel": link, "arrow": "above", "label": "kliknij", "dx": 40, "dy": 40}]
    )
    box = page_box(page, ".autor-page__embed-link")
    bottom = page.screenshot(
        full_page=True,
        clip={"x": 0, "y": box["y"] - 170, "width": w, "height": box["height"] + 190},
    )
    stitch(
        page,
        [top, bottom],
        out / "01-strona-autora-osadz.png",
        "przewiń na sam dół strony",
    )
    href = page.locator(link).get_attribute("href")

    # 2. the code generator, pre-filled from the link
    serve_docs_locally(page)
    proxy_public_bpp(page, base)
    page.goto(href.replace(base, PUBLIC_BPP))
    page.wait_for_load_state("networkidle")
    page.fill("#g-limit", "5")
    # the preview re-renders 600 ms after input; wait for the 5-item version
    page.wait_for_function(
        "document.querySelectorAll('#bpp-podglad .bpp-publikacje__item').length === 5"
    )
    page.wait_for_timeout(500)
    mark(
        page,
        [
            {
                "sel": "#bpp-gen p:has(#g-limit)",
                "arrow": "right",
                "label": "1. opcje",
                "dy": 10,
            },
            {"sel": "#g-copy", "arrow": "right", "label": "2. Kopiuj kod"},
            {"sel": "#bpp-podglad", "arrow": "right", "label": "podgląd", "dy": -60},
        ],
    )
    top = page_box(page, "h2#generator-kodu")
    end = page_box(page, "#bpp-podglad")
    page.screenshot(
        path=out / "02-generator-kodu.png",
        full_page=True,
        clip={
            "x": 0,
            "y": top["y"] - 20,
            "width": VIEWPORT["width"],
            "height": end["y"] + end["height"] - top["y"] + 28,
        },
    )

    # 3. the result on "your" website
    autor = href.split("autor=")[1].split("&")[0]
    html = EXAMPLE_PAGE.replace("__BASE__", PUBLIC_BPP).replace("__AUTOR__", autor)
    page.route(
        EXAMPLE_SITE + "/**",
        lambda route: route.fulfill(body=html, content_type="text/html; charset=utf-8"),
    )
    page.goto(EXAMPLE_SITE + "/pracownicy/yennefer/")
    page.wait_for_selector(".bpp-publikacje__item")
    page.wait_for_timeout(300)
    mark(
        page,
        [
            {
                "sel": ".bpp-publikacje",
                "arrow": "below",
                "label": "lista z BPP — aktualizuje się sama",
                "dy": -20,
            }
        ],
    )
    page.screenshot(path=out / "03-na-stronie-www.png", full_page=True)


TOP_MENU = "li:has(> a > .{icon})"  # top-bar dropdown by its icon class


def open_top_menu(page: Page, icon: str) -> str:
    """Hover a top-bar dropdown ("szukaj" = fi-magnifying-glass, ...) and
    wait for its fade-in. Returns the selector of the menu's <li>."""
    li = TOP_MENU.format(icon=icon)
    page.hover(f"{li} > a")
    # plain dropdowns are a <ul>; "ewaluacja" is a two-column wrapper
    page.wait_for_selector(f"{li} > ul, {li} > .menu-columns-wrapper", state="visible")
    page.wait_for_timeout(800)
    return li


def shot(page: Page, path: Path | None, y: float, height: float) -> bytes:
    """Full-width slice of the page, in page coordinates."""
    # Scroll home first: a sticky top bar is painted where the viewport is,
    # so after a click lower down it would show up in the middle of the slice.
    page.evaluate("window.scrollTo(0, 0)")
    return page.screenshot(
        path=path,
        full_page=True,
        clip={"x": 0, "y": max(0, y), "width": VIEWPORT["width"], "height": height},
    )


def wyszukiwanie(page: Page, base: str, out: Path) -> None:
    """docs/uzytkownik/przegladanie-i-wyszukiwanie.md: menus, quick search, author and record pages."""
    page.goto(f"{base}/")
    page.wait_for_load_state("networkidle")

    # 1. "szukaj" menu: two ways of searching
    li = open_top_menu(page, "fi-magnifying-glass")
    mark(
        page,
        [
            {
                "sel": f"{li} a[data-action=open-global-search]",
                "arrow": "right",
                "label": "szybko — tytuł, nazwisko, DOI",
                "dy": -30,
            },
            {
                "sel": f"{li} a[href$='/multiseek/']",
                "arrow": "right",
                "label": "precyzyjnie — wiele warunków",
                "dy": 20,
            },
        ],
    )
    shot(page, out / "01-menu-szukaj.png", 0, 300)

    # 2. quick search window (key "/")
    page.mouse.move(640, 700)
    page.goto(f"{base}/")
    page.wait_for_load_state("networkidle")
    page.keyboard.press("/")
    page.wait_for_selector("#globalSearchInput", state="visible")
    page.click("#globalSearchInput")
    page.keyboard.type("eliksir", delay=60)
    page.get_by_text("Wydział Magii i").first.wait_for()
    page.wait_for_timeout(800)
    mark(
        page,
        [
            {
                "sel": "#globalSearchInput",
                "arrow": "above",
                "label": "tytuł, nazwisko, jednostka, DOI…",
                "dx": -100,
                "dy": 60,
            }
        ],
    )
    page.screenshot(
        path=out / "02-szukaj-szybko.png",
        clip={"x": 0, "y": 0, "width": VIEWPORT["width"], "height": 670},
    )
    page.keyboard.press("Escape")

    # 3. "przeglądaj" menu
    page.goto(f"{base}/")
    page.wait_for_load_state("networkidle")
    li = open_top_menu(page, "fi-list")
    mark(
        page,
        [
            {
                "sel": f"{li} > ul",
                "arrow": "right",
                "label": "lista jednostek, autorów, czasopism…",
                "dy": -60,
            }
        ],
    )
    menu = page_box(page, f"{li} > ul")
    shot(page, out / "03-menu-przegladaj.png", 0, menu["y"] + menu["height"] + 30)

    # 4. author page at a glance: top, search form, export (stitched)
    page.mouse.move(640, 700)
    page.goto(f"{base}/bpp/autor/Yennefer-Merigold/")
    page.wait_for_load_state("networkidle")
    sekcja = ".autor-page__pas-cela"
    mark(
        page,
        [
            {
                "sel": "a.autor-page__show-all-btn",
                "arrow": "right",
                "label": "wszystkie prace autora",
                "dx": 60,
                "dy": -20,
            },
            {"sel": sekcja, "text": "Podsumowanie dorobku"},
        ],
    )
    top = shot(page, None, 0, 700)
    mark(page, [{"sel": sekcja, "text": "Wyszukaj publikacje autora"}])
    box = page_box(page, sekcja, "Wyszukaj publikacje autora")
    middle = shot(page, None, box["y"] - 12, box["height"] + 24)
    mark(
        page,
        [
            {
                "sel": sekcja,
                "text": "Eksport publikacji",
                "arrow": "left",
                "label": "pobierz plik",
                "dx": 60,
                "dy": -100,
            }
        ],
    )
    box = page_box(page, sekcja, "Eksport publikacji")
    bottom = shot(page, None, box["y"] - 20, box["height"] + 40)
    stitch(
        page,
        [top, middle, bottom],
        out / "04-strona-autora.png",
        "dalej na tej samej stronie",
    )

    # 5. record (publication) page
    # pick the first listed publication that has a DOI (the "Otwórz" button)
    hrefs = page.eval_on_selector_all(
        "a[href*='/bpp/rekord/']", "els => [...new Set(els.map(e => e.href))]"
    )
    for href in hrefs:
        page.goto(href)
        page.wait_for_load_state("networkidle")
        if page.locator("button[title='Otwórz stronę DOI']").count():
            break
    mark(
        page,
        [
            {
                "sel": "button[title='Otwórz stronę DOI']",
                "arrow": "above",
                "label": "pełny tekst (DOI)",
                "dx": -200,
                "dy": -110,
            },
            {
                "sel": ".praca-mono__card",
                "text": "Metryki",
                "arrow": "left",
                "label": "punkty",
                "dy": 200,
            },
            {
                "sel": "#bibtex-toggle-btn",
                "arrow": "left",
                "label": "do Zotero / Mendeley",
            },
        ],
    )
    page.screenshot(path=out / "05-strona-publikacji.png", full_page=True)


def pobieranie_listy(page: Page, base: str, out: Path) -> None:
    """docs/uzytkownik/pobieranie-listy-publikacji.md: export one's own publication list."""
    page.goto(f"{base}/bpp/autor/Yennefer-Merigold/")
    page.wait_for_load_state("networkidle")
    sekcja = ".autor-page__pas-cela"
    w = "Wyszukaj publikacje autora"

    # 1. author page search form: tick the years, then "Szukaj publikacji"
    top = shot(page, None, 0, 420)
    for rok in ("2024", "2025"):
        page.locator(f"label.autor-page__chip:has(input[value='{rok}'])").click()
    page.mouse.move(5, 5)  # no hover highlight on the last clicked chip
    mark(
        page,
        [
            {
                "sel": "label.autor-page__chip:has(input[value='2025'])",
                "arrow": "above",
                "label": "1. zaznacz lata",
                "dx": 300,
                "dy": 30,
            },
            {
                "sel": "button.autor-page__search-btn",
                "arrow": "above",
                "label": "2. Szukaj publikacji",
                "dx": -300,
                "dy": 30,
            },
        ],
    )
    box = page_box(page, sekcja, w)
    bottom = shot(page, None, box["y"] - 20, box["height"] + 40)
    stitch(
        page,
        [top, bottom],
        out / "01-strona-autora-szukaj.png",
        "przewiń do sekcji „Wyszukaj publikacje autora”",
    )

    # 2. results with the "Eksport" menu open
    page.click("button.autor-page__search-btn")
    page.wait_for_load_state("networkidle")
    page.click("#multiseek-szukaj")
    page.wait_for_load_state("networkidle")
    page.click("button.dropdown[data-toggle='multiseek-export-menu']")
    page.wait_for_selector("#multiseek-export-menu", state="visible")
    page.wait_for_timeout(500)
    mark(
        page,
        [
            {
                "sel": "button.dropdown[data-toggle='multiseek-export-menu']",
                "arrow": "left",
                "label": "3. Eksport",
                "dx": -20,
            },
            {
                "sel": "#multiseek-export-menu a",
                "text": "DOCX",
                "arrow": "right",
                "label": "4. Word",
                "dy": 10,
            },
            {
                "sel": "#multiseek-export-menu a",
                "text": "XLS: opis",
                "arrow": "right",
                "label": "albo Excel",
                "dy": -60,
            },
        ],
    )
    menu = page_box(page, "#multiseek-export-menu")
    shot(page, out / "02-wyniki-eksport.png", 0, menu["y"] + menu["height"] + 80)

    # 3. the ready-made export buttons on the author page
    page.goto(f"{base}/bpp/autor/Yennefer-Merigold/")
    page.wait_for_load_state("networkidle")
    mark(
        page,
        [
            {
                "sel": "a[href*='/eksport/xlsx']",
                "arrow": "below",
                "label": "wszystkie prace z punktacją (Excel)",
                "dx": -250,
                "dy": -60,
            },
        ],
    )
    box = page_box(page, sekcja, "Eksport publikacji")
    shot(page, out / "03-strona-autora-eksport.png", box["y"] - 20, box["height"] + 110)


def new_session(page: Page, base: str, user: str | None = None) -> Page:
    """A separate browser session: anonymous (user=None) or logged in as user."""
    ctx = page.context.browser.new_context(
        viewport=VIEWPORT, device_scale_factor=2, locale="pl-PL"
    )
    ctx.add_init_script(HIDE_HELP_LAUNCHER)
    other = ctx.new_page()
    if user:
        login(other, base, user)
    else:
        other.goto(f"{base}/")
        other.wait_for_load_state("networkidle")
        close_cookie_banner(other)
    return other


def bottom_of(page: Page, sel: str, margin: float = 20) -> float:
    box = page_box(page, sel)
    return box["y"] + box["height"] + margin


def select2(page: Page, select: str, szukaj: str, wybierz: str | None = None) -> None:
    """Pick an option in a select2 autocomplete next to the given <select>."""
    page.locator(f"{select} + .select2 .select2-selection").click()
    # Fill the search box only once it exists - typing right after the click
    # loses the first letters.
    page.locator(".select2-container--open .select2-search__field").fill(szukaj)
    page.locator(".select2-results__option", has_text=wybierz or szukaj).first.click()
    page.wait_for_timeout(500)


def punkty_i_sloty(page: Page, base: str, out: Path) -> None:
    """docs/uzytkownik/punkty-i-sloty.md: points and slots on the author and record pages, author slot report."""
    rap = new_session(page, base, DEMO_USER_RAPORTY)

    # 1. author page: the points chart is a few screens down
    rap.goto(f"{base}/bpp/autor/Yennefer-Merigold/")
    rap.wait_for_load_state("networkidle")
    rap.wait_for_timeout(1500)  # charts animate in
    top = shot(rap, None, 0, 420)
    mark(rap, [{"sel": "h3", "text": "Punkty MNiSW w latach"}])
    h = page_box(rap, "h3", "Punkty MNiSW w latach")
    bottom = shot(rap, None, h["y"] - 20, 420)
    stitch(
        rap,
        [top, bottom],
        out / "01-strona-autora-punkty.png",
        "przewiń do sekcji „Punkty MNiSW w latach”",
    )

    # 2. record page: who got how many points and slots, per discipline
    rap.goto(f"{base}/bpp/rekord/{REKORD_ZE_SLOTAMI}/")
    rap.wait_for_load_state("networkidle")
    mark(rap, [{"sel": "h3", "text": "Punkty i sloty autorów"}])
    h = page_box(rap, "h3", "Punkty i sloty autorów")
    top = shot(rap, None, 0, 330)
    bottom = shot(rap, None, h["y"] - 20, 260)
    stitch(
        rap,
        [top, bottom],
        out / "02-strona-pracy-sloty.png",
        "przewiń do tabeli „Punkty i sloty autorów”",
    )

    # 3. ewaluacja menu -> raport slotów - autor
    rap.goto(f"{base}/")
    rap.wait_for_load_state("networkidle")
    li = open_top_menu(rap, "fi-graph-bar")
    mark(
        rap,
        [
            {
                "sel": f"{li} a[href*='raport-slotow-autor']",
                "arrow": "right",
                "label": "punkty i sloty jednej osoby",
                "dx": 40,
            }
        ],
    )
    menu = page_box(rap, f"{li} > .menu-columns-wrapper")
    shot(rap, out / "03-menu-ewaluacja.png", 0, menu["y"] + menu["height"] + 40)

    # 4. the form
    rap.goto(f"{base}/raport_slotow/raport-slotow-autor/")
    rap.wait_for_load_state("networkidle")
    select2(rap, "select[name=obiekt]", "Merigold Yennefer")
    rap.fill("[name=od_roku]", "2022")
    rap.fill("[name=do_roku]", "2025")
    rap.mouse.move(5, 5)
    mark(
        rap,
        [
            {
                "sel": "select[name=obiekt] + .select2",
                "arrow": "right",
                "label": "1. autor",
                "dx": 0,
                "dy": -40,
            },
            {
                "sel": "[name=do_roku]",
                "arrow": "right",
                "label": "2. lata",
                "dx": 0,
                "dy": -40,
            },
            {
                "sel": "input[type=submit][value='Pobierz raport']",
                "arrow": "right",
                "label": "3. Pobierz raport",
                "dx": 20,
                "dy": -40,
            },
        ],
    )
    shot(
        rap,
        out / "04-raport-slotow-autor-formularz.png",
        0,
        bottom_of(rap, "input[type=submit][value='Pobierz raport']", 40),
    )

    # 5. the result: one table per discipline
    rap.click("input[type=submit][value='Pobierz raport']")
    rap.wait_for_load_state("networkidle")
    mark(
        rap,
        [
            {"sel": "a", "text": "pobierz XLS"},
            {
                "sel": "a",
                "text": "pobierz PDF",
                "arrow": "right",
                "label": "Excel albo PDF",
                "dx": 40,
                "dy": -40,
            },
        ],
    )
    shot(rap, out / "05-raport-slotow-autor-wynik.png", 0, 760)
    rap.context.close()


def raporty(page: Page, base: str, out: Path) -> None:
    """docs/uzytkownik/raporty-krok-po-kroku.md: the report guide (account in "generowanie raportów")."""
    rap = new_session(page, base, DEMO_USER_RAPORTY)
    submit = "input[type=submit]"

    def lata(od: str = "2022", do: str = "2025") -> None:
        rap.fill("[name=od_roku]", od)
        rap.fill("[name=do_roku]", do)

    # 1. "raporty" menu
    li = open_top_menu(rap, "fi-graph-trend")
    mark(
        rap,
        [
            {
                "sel": f"{li} > ul a",
                "text": "Raport jednostek",
                "arrow": "right",
                "label": "listy prac: wydział, jednostka, autor",
                "dx": 40,
            },
            {
                "sel": f"{li} > ul a",
                "text": "ranking",
                "arrow": "right",
                "label": "ranking autorów",
                "dx": 40,
                "dy": 10,
            },
        ],
    )
    menu = page_box(rap, f"{li} > ul")
    shot(rap, out / "01-menu-raporty.png", 0, menu["y"] + menu["height"] + 40)

    # 2. Raport jednostek: unit + years
    rap.goto(f"{base}/nowe_raporty/raport-jednostek/")
    rap.wait_for_load_state("networkidle")
    select2(rap, "select[name=obiekt]", "Klinika Szermierki")
    lata()
    rap.mouse.move(5, 5)
    mark(
        rap,
        [
            {
                "sel": "select[name=obiekt] + .select2",
                "arrow": "right",
                "label": "1. jednostka",
                "dx": 0,
                "dy": -40,
            },
            {
                "sel": "[name=do_roku]",
                "arrow": "right",
                "label": "2. lata",
                "dx": 0,
                "dy": -40,
            },
            {
                "sel": "select[name=_export]",
                "arrow": "below",
                "label": "ekran, Word albo Excel",
                "dx": 100,
                "dy": -50,
            },
            {
                "sel": f"{submit}[value='Pobierz raport']",
                "arrow": "right",
                "label": "3. Pobierz raport",
                "dx": 20,
                "dy": -40,
            },
        ],
    )
    shot(
        rap,
        out / "02-raport-jednostek-formularz.png",
        0,
        bottom_of(rap, f"{submit}[value='Pobierz raport']", 40),
    )

    # 3. its result, with Word/Excel downloads
    rap.click(f"{submit}[value='Pobierz raport']")
    rap.wait_for_load_state("networkidle")
    mark(
        rap,
        [
            {
                "sel": "a",
                "text": "pobierz jako MS Word",
                "arrow": "left",
                "label": "pobierz plik",
                "dx": 0,
                "dy": -40,
            },
            {"sel": "a", "text": "pobierz jako XLSX"},
        ],
    )
    shot(rap, out / "03-raport-jednostek-wynik.png", 0, 700)

    # 4. Ranking autorów
    rap.goto(f"{base}/bpp/raporty/ranking-autorow/wybierz/")
    rap.wait_for_load_state("networkidle")
    lata()
    rap.mouse.move(5, 5)
    mark(
        rap,
        [
            {
                "sel": "[name=do_roku]",
                "arrow": "right",
                "label": "1. lata",
                "dx": 0,
                "dy": -40,
            },
            {
                "sel": f"{submit}[value='Otwórz']",
                "arrow": "right",
                "label": "2. Otwórz",
                "dx": 20,
                "dy": -40,
            },
        ],
    )
    box = page_box(rap, f"{submit}[value='Otwórz']")
    top = shot(rap, None, 0, 520)
    bottom = shot(rap, None, box["y"] - 200, 280)
    stitch(
        rap,
        [top, bottom],
        out / "04-ranking-formularz.png",
        "niżej: filtry (opcjonalne) — przewiń do przycisku „Otwórz”",
    )

    # 5. ranking result
    rap.click(f"{submit}[value='Otwórz']")
    rap.wait_for_load_state("networkidle")
    mark(
        rap,
        [
            {
                "sel": "a",
                "text": "Pobierz XLSX",
                "arrow": "left",
                "label": "do Excela",
                "dx": 0,
                "dy": -40,
            }
        ],
    )
    shot(rap, out / "05-ranking-wynik.png", 0, 700)

    # 6. Raport slotów - zerowy: who has a discipline but no slots
    rap.goto(f"{base}/raport_slotow/raport-slotow-zerowy/")
    rap.wait_for_load_state("networkidle")
    lata()
    rap.click(f"{submit}[value='Wyślij formularz']")
    rap.wait_for_load_state("networkidle")
    mark(
        rap,
        [
            {
                "sel": "input[value='Pobierz XLS']",
                "arrow": "above",
                "label": "do Excela",
                "dx": -200,
                "dy": 50,
            }
        ],
    )
    shot(rap, out / "06-raport-zerowy-wynik.png", 0, 700)

    # 7. Raport slotów - ewaluacja: every author x work x discipline
    rap.goto(f"{base}/raport_slotow/raport-slotow-ewaluacja/")
    rap.wait_for_load_state("networkidle")
    lata()
    rap.click(f"{submit}[value='Pobierz raport']")
    rap.wait_for_load_state("networkidle")
    mark(
        rap,
        [
            {
                "sel": "input[value='Pobierz XLS']",
                "arrow": "above",
                "label": "do Excela",
                "dx": -200,
                "dy": 50,
            }
        ],
    )
    shot(rap, out / "07-raport-ewaluacja-wynik.png", 0, 700)
    rap.context.close()


# A made-up Witcher article for the importer walkthrough: one author matched
# exactly, one with two namesakes (pick by unit), one not in BPP at all.
IMPORTER_BIBTEX = """@article{vesemir2025jaskolka,
  title    = {Stabilność eliksiru Jaskółka w warunkach górskich},
  author   = {Merigold, Yennefer and Merigold, Leo and Chivay, Zoltan},
  journal  = {Acta Wiedźmińska},
  year     = {2025},
  volume   = {12},
  number   = {3},
  pages    = {45--58},
  doi      = {10.99999/aw.2025.0312},
  language = {pl}
}"""


def importer_publikacji(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/importer-publikacji.md: importer walkthrough with a pasted BibTeX entry.

    Needs a FRESH demo DB (re-run = restore the dump) plus, in that DB: account
    vesemir (is_staff + "wprowadzanie danych"), Uczelnia.obca_jednostka set,
    Punktacja_Zrodla for "Acta Wiedźmińska" 2025 and the CrossRef mapper
    journal-article -> "Artykuł w czasopismie". No external service is called.
    """
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    red.on("dialog", lambda d: d.accept())  # hx-confirm prompts
    wizard = "#importer-wizard"

    def czekaj(ms: int = 1500) -> None:
        red.wait_for_load_state("networkidle")
        red.wait_for_timeout(ms)

    def wyrownaj_nakladke() -> None:
        # An open Foundation reveal pins the page, so the overlay (absolute,
        # page coordinates) drifts by the scroll offset - shift it back.
        red.evaluate(
            """() => { const ov = document.getElementById('kb-overlay');
            const o = ov.getBoundingClientRect();
            ov.style.top = (-scrollY - o.top) + 'px'; }"""
        )

    def dalej(text: str) -> None:
        red.locator(f"{wizard} button", has_text=text).last.click()
        czekaj()
        # htmx swaps the step in place: drop the previous step's marks
        red.evaluate("document.getElementById('kb-overlay')?.remove()")

    # 1. top bar "redagowanie" -> "Import publikacji"
    li = open_top_menu(red, "fi-pencil")
    mark(
        red,
        [
            {
                "sel": f"{li} > ul a",
                "text": "Import publikacji",
            }
        ],
    )
    menu = page_box(red, f"{li} > ul")
    shot(red, out / "01-menu-redagowanie.png", 0, menu["y"] + menu["height"] + 30)

    # 2. the same from the admin: "Wprowadzanie danych" -> "Importer publikacji"
    red.goto(f"{base}/admin/")
    czekaj(500)
    red.locator("li.menu-icon-edit > a").hover()
    red.wait_for_timeout(800)
    mark(
        red,
        [
            {
                "sel": "li.menu-icon-edit li a",
                "text": "Importer publikacji",
                "arrow": "right",
                "label": "Importer publikacji",
                "dx": 40,
            }
        ],
    )
    menu = page_box(red, "li.menu-icon-edit > ul")
    shot(red, out / "02-menu-admin.png", 0, menu["y"] + menu["height"] + 90)

    # 3. provider tiles
    red.goto(f"{base}/importer_publikacji/")
    czekaj(500)
    mark(
        red,
        [
            {
                "sel": "a.tile-card[data-provider=BibTeX]",
                "arrow": "above",
                "label": "masz opis BibTeX",
                "dy": 40,
            },
            {
                "sel": "a.tile-card[data-provider=CrossRef]",
                "arrow": "above",
                "label": "masz DOI",
                "dy": 40,
            },
            {
                "sel": "a.tile-card[data-provider=PBN]",
                "arrow": "right",
                "label": "praca jest w PBN",
            },
        ],
    )
    shot(red, out / "03-zrodla-danych.png", 0, bottom_of(red, "#import-progress-bar"))

    # 4. CrossRef: the first (and only) screen we show - no call to CrossRef
    red.click("a.tile-card[data-provider=CrossRef]")
    czekaj(500)
    red.fill("#input-identifier input", "10.99999/aw.2025.0312")
    mark(
        red,
        [
            {
                "sel": "#input-identifier input",
                "arrow": "below",
                "label": "wklej DOI",
                "dx": 60,
                "dy": -20,
            },
            {
                "sel": "#input-identifier button",
                "arrow": "below",
                "label": "Pobierz dane",
                "dx": -40,
                "dy": -20,
            },
        ],
    )
    shot(red, out / "04-doi.png", 0, bottom_of(red, wizard, 150))

    # 5. PBN: first screen too
    red.goto(f"{base}/importer_publikacji/?provider=PBN")
    czekaj(500)
    mark(
        red,
        [
            {
                "sel": "#input-identifier input",
                "arrow": "below",
                "label": "PBN UID albo adres pracy w PBN",
                "dx": 60,
                "dy": -20,
            }
        ],
    )
    shot(red, out / "05-pbn.png", 0, bottom_of(red, wizard, 150))

    # 6. BibTeX: paste and "Importuj"
    red.goto(f"{base}/importer_publikacji/?provider=BibTeX")
    czekaj(500)
    red.fill("textarea", IMPORTER_BIBTEX)
    mark(
        red,
        [
            {
                "sel": "#input-text textarea",
                "arrow": "right",
                "label": "wklej wpis BibTeX",
                "dx": -330,
                "dy": -60,
            },
            {
                "sel": "#input-text button[type=submit]",
                "arrow": "right",
                "label": "Importuj",
                "dx": 0,
                "dy": -40,
            },
        ],
    )
    shot(red, out / "06-bibtex.png", 0, bottom_of(red, "#input-text"))
    red.click("#input-text button[type=submit]")
    red.wait_for_url("**/verify/", timeout=60000)
    czekaj()

    # 7. verify: data from BibTeX + record kind, type, language
    red.select_option("#id_typ_kbn", label="Praca Oryginalna")
    mark(
        red,
        [
            {
                "sel": f"{wizard} table",
                "arrow": "right",
                "label": "sprawdź dane",
                "dx": -330,
                "dy": -170,
            },
            {
                "sel": "#id_charakter_formalny",
                "arrow": "below",
                "label": "uzupełnij pola z gwiazdką",
                "dx": 420,
                "dy": -60,
            },
            {
                "sel": f"{wizard} button[type=submit]",
                "text": "Dalej",
                "arrow": "right",
                "label": "Dalej",
                "dx": 0,
                "dy": -40,
            },
        ],
    )
    btn = page_box(red, f"{wizard} button[type=submit]", "Dalej")
    shot(red, out / "07-weryfikacja.png", 0, btn["y"] + btn["height"] + 50)
    dalej("Dalej")

    # 8. source matched by the journal title
    mark(
        red,
        [
            {
                "sel": "#id_zrodlo + .select2",
                "arrow": "right",
                "label": "dopasowane po tytule czasopisma — sprawdź",
                "dx": 0,
            }
        ],
    )
    shot(red, out / "08-zrodlo.png", 0, bottom_of(red, wizard, 0))
    dalej("Dalej")

    # 9. authors: exact, loose (two namesakes), unmatched
    red.mouse.move(5, 5)
    mark(
        red,
        [
            {"sel": "#authors-table tbody tr:nth-child(1) td:nth-child(4) .label"},
            {"sel": "#authors-table tbody tr:nth-child(2) td:nth-child(4) .label"},
            {"sel": "#authors-table tbody tr:nth-child(3) td:nth-child(4) .label"},
            {"sel": "#authors-table tbody tr:nth-child(2) .btn-edit-author"},
        ],
    )
    shot(red, out / "09-autorzy.png", 0, bottom_of(red, "#unmatched-warning", 80))

    # 10. two namesakes: pick the one from the right unit
    # a tall viewport so the whole modal (with "Zapisz") fits on the shot
    red.set_viewport_size({"width": VIEWPORT["width"], "height": 1150})
    red.evaluate("window.scrollTo(0, 0)")
    red.locator("#authors-table tbody tr:nth-child(2) .btn-edit-author").click()
    red.wait_for_selector("#author-edit-modal .modal-candidate-button")
    red.wait_for_timeout(1500)
    red.locator(
        "#author-edit-modal .modal-candidate-button", has_text="Klinika Eliksirologii"
    ).click()
    red.wait_for_timeout(1500)
    red.evaluate("window.scrollTo(0, 0)")
    mark(
        red,
        [
            {
                "sel": "#author-edit-modal .modal-candidate-button",
                "text": "Klinika Eliksirologii",
                "arrow": "left",
                "label": "kliknij właściwą osobę",
                "dy": 60,
            },
            {
                "sel": "#modal-author-form button[type=submit]",
                "arrow": "below",
                "label": "Zapisz",
                "dx": -40,
                "dy": -50,
            },
        ],
    )
    wyrownaj_nakladke()
    red.screenshot(path=out / "10-kandydaci.png")
    red.locator("#modal-author-form button[type=submit]").click()
    czekaj()

    # 11. author not in BPP: create a new one
    red.evaluate("window.scrollTo(0, 0)")
    red.locator("#authors-table tbody tr:nth-child(3) .btn-edit-author").click()
    red.wait_for_selector("#modal-create-new-author", state="visible")
    red.wait_for_timeout(1500)
    mark(
        red,
        [
            {
                "sel": "#modal-create-new-author",
                "arrow": "left",
                "label": "nowy autor",
                "dx": 0,
                "dy": -40,
            }
        ],
    )
    wyrownaj_nakladke()
    red.screenshot(path=out / "11-nowy-autor.png")
    red.click("#modal-create-new-author")
    nowy = red.locator("#authors-table tbody tr", has_text="Obca jednostka")
    try:
        nowy.wait_for(timeout=8000)
    except PlaywrightTimeoutError:
        # the modal button occasionally fires before its handler is bound -
        # the bulk button above the table does the same thing
        red.keyboard.press("Escape")
        red.locator("button", has_text="Utwórz niedopasowanego autora").click()
        nowy.wait_for()
    czekaj()
    red.set_viewport_size(VIEWPORT)
    red.goto(red.url)  # fresh counters and an enabled "Potwierdź i przejdź dalej"
    czekaj()
    red.mouse.move(5, 5)
    mark(
        red,
        [
            {
                "sel": "#authors-table tbody tr:nth-child(2) td:nth-child(4) .label",
            },
            {
                "sel": f"{wizard} button[type=submit]",
                "text": "Potwierdź i przejdź dalej",
                "arrow": "right",
                "label": "Potwierdź i przejdź dalej",
                "dx": 0,
                "dy": -40,
            },
        ],
    )
    btn = page_box(red, f"{wizard} button[type=submit]", "Potwierdź i przejdź dalej")
    shot(red, out / "12-autorzy-gotowe.png", 0, btn["y"] + btn["height"] + 40)
    dalej("Potwierdź i przejdź dalej")

    # 12. points suggested from the journal
    mark(
        red,
        [
            {
                "sel": "input[name=punkty_kbn]",
            }
        ],
    )
    shot(red, out / "13-punktacja.png", 0, bottom_of(red, wizard, 0))
    dalej("Dalej")

    # 13. "Sprawdź w PBN" (optional; not logged in to PBN here)
    mark(
        red,
        [
            {
                "sel": f"{wizard} a, {wizard} button",
                "text": "Pomiń",
                "arrow": "right",
                "label": "krok opcjonalny — Pomiń",
                "dx": 0,
                "dy": -40,
            }
        ],
    )
    shot(red, out / "14-pbn-sprawdz.png", 0, bottom_of(red, wizard, 0))
    dalej("Dalej")

    # 14. review + "Utwórz publikację" far below
    top = shot(red, None, 0, 520)
    mark(
        red,
        [
            {
                "sel": f"{wizard} button[type=submit]",
                "text": "Utwórz publikację",
                "arrow": "right",
                "label": "Utwórz publikację",
                "dx": 0,
                "dy": -40,
            }
        ],
    )
    btn = page_box(red, f"{wizard} button[type=submit]", "Utwórz publikację")
    dol = shot(red, None, btn["y"] - 220, 300)
    stitch(red, [top, dol], out / "15-przeglad.png", "przewiń na dół strony")
    red.locator(f"{wizard} button[type=submit]", has_text="Utwórz publikację").click()
    red.wait_for_url("**/done/", timeout=60000)
    czekaj()

    # 15. done
    mark(
        red,
        [
            {
                "sel": f"{wizard} a",
                "text": "Edytuj w module redagowania",
                "arrow": "right",
                "label": "popraw szczegóły rekordu",
                "dx": 100,
                "dy": 0,
            }
        ],
    )
    shot(red, out / "16-gotowe.png", 0, bottom_of(red, wizard, 0))

    # 16. what can go wrong: the same entry again -> duplicate warning
    red.goto(f"{base}/importer_publikacji/?provider=BibTeX")
    czekaj(500)
    red.fill("textarea", IMPORTER_BIBTEX)
    red.click("#input-text button[type=submit]")
    red.wait_for_url("**/verify/", timeout=60000)
    czekaj()
    mark(red, [{"sel": f"{wizard} .callout.alert"}])
    shot(red, out / "17-duplikat.png", 0, bottom_of(red, f"{wizard} .callout.alert"))
    red.locator(f"{wizard} button", has_text="Anuluj import").click()
    czekaj()

    # 17. what can go wrong: a malformed PBN identifier (checked before any call)
    red.goto(f"{base}/importer_publikacji/?provider=PBN")
    czekaj(500)
    red.fill("#input-identifier input", "5e709189878c28a0")
    red.click("#input-identifier button")
    czekaj()
    mark(red, [{"sel": "#input-identifier .help-text[style]"}])
    shot(red, out / "18-zly-identyfikator.png", 0, bottom_of(red, wizard, 0))
    red.context.close()


def zgloszenie_publikacji(page: Page, base: str, out: Path) -> None:
    """docs/uzytkownik/zgloszenie-publikacji.md: the "Zgłoś publikację" wizard, end to end."""
    nastepny = ".wizard-nav button:not([name=wizard_goto_step])"

    # 1. the only entry point: the big button on the home page
    page.goto(f"{base}/")
    page.wait_for_load_state("networkidle")
    mark(
        page,
        [
            {
                "sel": "a.main-page-button-primary",
                "arrow": "below",
                "label": "zgłoś nową publikację",
                "dx": -200,
                "dy": -55,
            }
        ],
    )
    shot(page, out / "01-strona-glowna.png", 0, 560)

    # 2. step "Rodzaj": a click on a tile moves on by itself
    page.goto(f"{base}/zglos_publikacje/nowe_zgloszenie/")
    page.wait_for_load_state("networkidle")
    mark(
        page,
        [
            {
                "sel": "label.tile-card[data-value=ARTYKUL]",
                "arrow": "above",
                "label": "kliknij rodzaj",
                "dx": 300,
                "dy": 40,
            }
        ],
    )
    shot(page, out / "02-rodzaj.png", 0, bottom_of(page, "#form-container"))
    page.click("label.tile-card[data-value=ARTYKUL]")
    page.wait_for_load_state("networkidle")

    # 3. step "Dostęp"
    mark(
        page,
        [
            {
                "sel": "label.tile-card[data-value=OTWARTY]",
                "arrow": "right",
                "label": "jest w internecie — podasz link lub DOI",
                "dx": -560,
                "dy": -40,
            },
            {
                "sel": "label.tile-card[data-value=OGRANICZONY]",
                "arrow": "right",
                "label": "nie ma — dołączysz PDF",
                "dx": -400,
                "dy": -40,
            },
        ],
    )
    shot(page, out / "03-dostep.png", 0, bottom_of(page, "#form-container"))
    page.click("label.tile-card[data-value=OTWARTY]")
    page.wait_for_load_state("networkidle")

    # 4. step "Dane"
    page.fill(
        "[name='2-tytul_oryginalny']",
        "Wpływ fazy księżyca na skuteczność eliksiru Jaskółka",
    )
    page.fill("[name='2-rok']", "2024")
    page.fill("[name='2-strona_www']", "10.1234/aretuza.2024.017")
    mark(
        page,
        [
            {
                "sel": "[name='2-strona_www']",
                "arrow": "above",
                "label": "adres strony albo sam DOI",
                "dx": 250,
                "dy": 102,
            },
            {
                "sel": nastepny,
                "arrow": "left",
                "label": "dalej",
                "dx": 0,
                "dy": -30,
            },
        ],
    )
    shot(page, out / "04-dane.png", 0, bottom_of(page, ".wizard-nav"))
    page.click(nastepny)
    page.wait_for_load_state("networkidle")

    # 5. step "Autorzy": the unit fills itself in once the author is picked
    def wybierz(pole: str, szukaj: str) -> None:
        page.locator(f"select[name='3-0-{pole}'] + .select2 .select2-selection").click()
        # Type into the search box only once it exists - typing right after
        # the click loses the first letters ("Yennefer" -> "ennefer").
        page.locator(".select2-container--open .select2-search__field").fill(szukaj)
        page.locator(".select2-results__option", has_text=szukaj).first.click()
        page.wait_for_timeout(500)

    wybierz("autor", "Merigold Yennefer")
    # The list holds only the author's disciplines for that year; take the first.
    page.locator(
        "select[name='3-0-dyscyplina_naukowa'] + .select2 .select2-selection"
    ).click()
    page.locator(".select2-results__option:not(.loading-results)").first.click()
    page.wait_for_timeout(500)
    page.mouse.move(5, 5)
    mark(
        page,
        [
            {
                "sel": "select[name='3-0-autor'] + .select2",
                "arrow": "above",
                "label": "wpisz nazwisko i wybierz z listy",
                "dx": 120,
                "dy": 60,
            },
            {
                "sel": "#add-form",
                "arrow": "right",
                "label": "kolejni współautorzy z uczelni",
                "dx": 40,
            },
        ],
    )
    shot(page, out / "05-autorzy.png", 0, bottom_of(page, ".wizard-nav"))
    page.click(nastepny)
    page.wait_for_load_state("networkidle")

    # 6. step "Płatności" (only for some kinds): "Publikacja bezkosztowa" must be answered
    page.select_option("[name='4-opl_pub_cost_free']", label="Tak")
    mark(
        page,
        [
            {
                "sel": "[name='4-opl_pub_cost_free']",
                "arrow": "right",
                "label": "wymagane: Tak albo Nie",
                "dx": -330,
                "dy": -95,
            },
            {
                "sel": nastepny,
                "arrow": "above",
                "label": "Zakończ i wyślij",
                "dx": -200,
                "dy": 40,
            },
        ],
    )
    shot(page, out / "06-platnosci.png", 0, bottom_of(page, ".wizard-nav"))
    page.click(nastepny)
    page.wait_for_load_state("networkidle")
    page.wait_for_selector("text=Dziękujemy!")

    # 7. confirmation
    shot(page, out / "07-sukces.png", 0, bottom_of(page, "a.submit.button", 40))


def logowanie(page: Page, base: str, out: Path) -> None:
    """docs/uzytkownik/logowanie.md: logging in, password reset, lockout, account without an author."""
    anon = new_session(page, base)

    # 1. "zaloguj" menu (anonymous visitor)
    li = open_top_menu(anon, "fi-lock")
    mark(
        anon,
        [
            {
                "sel": f"{li} > ul a[href*='login']",
                "arrow": "right",
                "label": "konto w BPP",
                "dx": 60,
            },
        ],
    )
    menu = page_box(anon, f"{li} > ul")
    shot(anon, out / "01-menu-zaloguj.png", 0, menu["y"] + menu["height"] + 40)

    # 2. login form with the "forgot password" link
    anon.goto(f"{base}/accounts/login/")
    anon.wait_for_load_state("networkidle")
    mark(
        anon,
        [
            {
                "sel": "a[href*='password_reset']",
                "arrow": "right",
                "label": "nie pamiętam hasła",
                "dx": 40,
            },
        ],
    )
    shot(
        anon,
        out / "02-logowanie.png",
        0,
        bottom_of(anon, "a[href*='password_reset']", 60),
    )

    # 3. password reset form
    anon.click("a[href*='password_reset']")
    anon.wait_for_load_state("networkidle")
    mark(
        anon,
        [
            {
                "sel": "input[type=email]",
                "arrow": "left",
                "label": "adres e-mail z konta BPP",
                "dx": 40,
                "dy": 30,
            },
        ],
    )
    shot(anon, out / "03-reset-hasla.png", 150, 420)

    # 4. lockout after too many failed attempts. Axes locks the (login, IP)
    # pair, so a made-up login leaves the demo accounts usable.
    for _ in range(11):
        anon.goto(f"{base}/accounts/login/")
        anon.fill("input[name=username]", "geralt")
        anon.fill(
            "input[name=password]", "geralt"
        )  # wrong on purpose (no such account)
        anon.locator("form [type=submit]").first.click()
        anon.wait_for_load_state("networkidle")
        if anon.locator("text=Konto tymczasowo zablokowane").count():
            break
    anon.wait_for_selector("h1:has-text('Konto tymczasowo zablokowane')")
    shot(
        anon,
        out / "04-blokada.png",
        0,
        bottom_of(anon, "a.button.secondary[href='/']", 60),
    )
    anon.context.close()

    # 5. logged in, but the account is not linked to an author
    bez = new_session(page, base, DEMO_USER_BEZ_AUTORA)
    bez.goto(f"{base}/bpp/profil/")
    bez.wait_for_load_state("networkidle")
    mark(bez, [{"sel": ".callout.warning", "text": "Brak powiązania"}])
    shot(bez, out / "05-brak-powiazania.png", 0, bottom_of(bez, ".callout.warning", 16))
    bez.context.close()


# name -> (docs/images subdirectory, function)
SCENARIOS = {
    "moj-profil-autora": ("uzytkownik/moj-profil-autora", moj_profil_autora),
    "widget-publikacji": ("uzytkownik/widget-publikacji", widget_publikacji),
    "wyszukiwanie": ("uzytkownik/wyszukiwanie", wyszukiwanie),
    "pobieranie-listy": ("uzytkownik/pobieranie-listy-publikacji", pobieranie_listy),
    "zgloszenie-publikacji": (
        "uzytkownik/zgloszenie-publikacji",
        zgloszenie_publikacji,
    ),
    "logowanie": ("uzytkownik/logowanie", logowanie),
    "punkty-i-sloty": ("uzytkownik/punkty-i-sloty", punkty_i_sloty),
    "raporty": ("uzytkownik/raporty", raporty),
    "importer-publikacji": ("redaktor/importer-publikacji", importer_publikacji),
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("scenario", nargs="*", help="scenario name(s); default: all")
    ap.add_argument("--base", default="http://localhost:8000", help="BPP base URL")
    ap.add_argument("--list", action="store_true", help="list scenarios and exit")
    args = ap.parse_args()

    if args.list:
        for name, (subdir, fn) in SCENARIOS.items():
            print(f"{name:24} -> docs/images/{subdir}/  ({fn.__doc__})")
        return 0
    unknown = set(args.scenario) - set(SCENARIOS)
    if unknown:
        ap.error(f"unknown scenario(s): {', '.join(sorted(unknown))}")

    base = args.base.rstrip("/")
    with sync_playwright() as pw:
        # channel="chromium" = full Chromium (not the headless shell), which
        # honours --lang, so native widgets read "Wybierz plik", not "Choose File".
        browser = pw.chromium.launch(
            channel="chromium",
            args=["--lang=pl"],
        )
        ctx = browser.new_context(
            viewport=VIEWPORT, device_scale_factor=2, locale="pl-PL"
        )
        ctx.add_init_script(HIDE_HELP_LAUNCHER)
        page = ctx.new_page()
        login(page, base)
        for name in args.scenario or list(SCENARIOS):
            subdir, fn = SCENARIOS[name]
            out = IMAGES / subdir
            out.mkdir(parents=True, exist_ok=True)
            fn(page, base, out)
            print(f"{name}: {out.relative_to(REPO)}")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
