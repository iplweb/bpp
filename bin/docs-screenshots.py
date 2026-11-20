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

REPO = Path(__file__).resolve().parent.parent
IMAGES = REPO / "docs" / "images"

# Demo account created per docs/deweloper/zrzuty-ekranu.md — an ordinary
# author (no staff/superuser), so screenshots show what a typical user sees.
DEMO_USER = "yennefer"
# Local throwaway demo DB only; password == username keeps secret scanners quiet.
DEMO_PASSWORD = DEMO_USER

VIEWPORT = {"width": 1280, "height": 800}

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


def login(page: Page, base: str) -> None:
    page.goto(f"{base}/accounts/login/")
    page.fill("input[name=username]", DEMO_USER)
    page.fill("input[name=password]", DEMO_PASSWORD)
    page.locator("form [type=submit]").first.click()
    page.wait_for_load_state("networkidle")
    if "/accounts/login/" in page.url:
        raise SystemExit(
            f"Login as {DEMO_USER!r} failed - create the demo account first "
            "(docs/deweloper/zrzuty-ekranu.md)."
        )
    # The cookie banner would cover the lower part of every full-page shot.
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
    page.wait_for_selector(f"{li} > ul", state="visible")
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


# name -> (docs/images subdirectory, function)
SCENARIOS = {
    "moj-profil-autora": ("uzytkownik/moj-profil-autora", moj_profil_autora),
    "widget-publikacji": ("uzytkownik/widget-publikacji", widget_publikacji),
    "wyszukiwanie": ("uzytkownik/wyszukiwanie", wyszukiwanie),
    "pobieranie-listy": ("uzytkownik/pobieranie-listy-publikacji", pobieranie_listy),
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
        # The Freshdesk "Pomoc" launcher floats over whatever we're explaining.
        ctx.add_init_script(
            "document.addEventListener('DOMContentLoaded', () => {"
            " const s = document.createElement('style');"
            " s.textContent = '#freshworks-container, #launcher-frame"
            " { display: none !important }';"
            " document.head.appendChild(s); });"
        )
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
