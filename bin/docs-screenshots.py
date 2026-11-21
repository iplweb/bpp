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
import os
import sys
from pathlib import Path
from urllib.parse import quote

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
# A made-up staff file in the layout of the template
# (src/import_pracownikow/static/import_pracownikow/import_pracownikow_przyklad.xlsx)
# for docs/administrator/import-pracownikow.md. bin/docs-demo-admin-import-pracownikow.py
# leaves "Zarządzaj automatycznie" on "Klinika Mutacji" only, so the two people
# of that unit missing here (Eskel z Cintry, Cahir z Vengerbergu) are the whole
# "odpięcia" proposal. Ciri has a namesake, so she is matched by "BPP ID"; Leo
# Merigold has a namesake too and no ID ("wielu kandydatów"); Vilgefortz is not
# in BPP and his unit does not exist yet.
IMPORT_PRAC_NAGLOWEK = [
    "Numer",
    "Nazwisko",
    "Imię",
    "ORCID",
    "Tytuł/Stopień",
    "Stanowisko",
    "Grupa pracownicza",
    "Nazwa jednostki",
    "Wydział",
    "Data zatrudnienia",
    "Data końca zatrudnienia",
    "Podstawowe miejsce pracy",
    "PBN UUID",
    "BPP ID",
    "Wymiar etatu",
]
IMPORT_PRAC_WIERSZE = [
    # numer, nazwisko, imię, tytuł, jednostka, wydział, od, BPP ID
    (1001, "Merigold", "Margarita", "dr hab.", "Klinika Mutacji", "2019-10-01", None),
    (1002, "van der Eretein", "Ciri", "dr", "Klinika Mutacji", "2021-03-01", 209),
    (1003, "z Rivii", "Renfri", "mgr", "Klinika Mutacji", "2023-10-01", None),
    (
        1004,
        "z Roggeveen",
        "Eredin",
        "dr n. med.",
        "Klinika Mutacji",
        "2018-02-01",
        None,
    ),
    (1005, "ze Stygga", "Renfri", "dr", "Klinika Mutacji", "2020-10-01", None),
    (1006, "Merigold", "Leo", "dr", "Klinika Eliksirologii", "2017-10-01", None),
    (
        1007,
        "z Roggeveen",
        "Vilgefortz",
        "dr",
        "Pracownia Eliksirów Bojowych",
        "2026-10-01",
        None,
    ),
]
IMPORT_PRAC_WYDZIAL = "Wydział Magii i Eliksirów"
# Demo author with three workplaces (bin/docs-demo-panel-uczelnia.py).
AUTOR_MIEJSCA_PRACY = 187  # Margarita Merigold
# Demo article with three authors, for reordering them.
REKORD_TRZECH_AUTOROW = 1130
UCZELNIA_ZMIANA = "/admin/bpp/uczelnia/"
# Demo work by an author with two disciplines in 2023 (bin/docs-demo-oswiadczenia.py).
OSW_REKORD = 1130
OSW_REKORD_SLUG = (
    "Modelowanie-eliksirow-wiedzminskich-z-wykorzystaniem-tolerancje-eliksirow"
    "-nr-530-Folia-Kaedwenica-z-Roggeveen-T-z-Cintry-R-var-Emreis-C-6-1130"
)
LISTA_ROZBIEZNOSCI = "/admin/rozbieznosci_dyscyplin/rozbieznosciview/"
# A made-up ministerial journal list ("wykaz czasopism") in the layout the
# import reads: two header rows (discipline NAMES in the first, codes in the
# second), columns Lp. / identifier / "Tytuł 1" issn e-issn / "Tytuł 2" issn
# e-issn / points, then one column per discipline with "x". Run
# bin/docs-demo-import-list-ministerialnych.py first (seeds what it compares to).
WYKAZ_DEMO_ROK = 2025
WYKAZ_DEMO_DYSCYPLINY = [
    ("101", "archeologia"),
    ("103", "filozofia"),
    ("104", "historia"),
    ("602", "biotechnologia"),
    ("605", "nauki biologiczne"),
    ("606", "nauki chemiczne"),
    ("702", "nauki teologiczne"),
]
WYKAZ_DEMO_WIERSZE = [
    (201001, "Acta Wiedźmińska", "6746-8071", 100, "filozofia, nauki teologiczne"),
    (
        201002,
        "Annales Aretuzańska",
        "9770-3482",
        140,
        "biotechnologia, nauki chemiczne",
    ),
    (201003, "Folia Temerska", "7109-3248", 40, "archeologia, historia"),
    (
        201004,
        "Studia Aretuzańska",
        "4990-913X",
        70,
        "biotechnologia, nauki biologiczne",
    ),
    (201005, "Acta Oxenfurcka", "4936-183X", 20, "filozofia"),
    (201006, "Przegląd Temerska", "9938-6774", 100, "historia"),
    (
        201007,
        "Zoologia Brokilońska",
        "1111-2228",
        70,
        "nauki biologiczne",
    ),  # not in BPP
    (201001, "Acta Wiedźmińska", "6746-8071", 100, "filozofia, nauki teologiczne"),
]
DEMO_USER_REDAKTOR = "vesemir"  # demo editor: is_staff + "wprowadzanie danych"
DEMO_USER_ADMIN = "regis"  # demo superuser for administrator pages
# The fake POL-on export of the demo university (docs/deweloper/dane-demo.md,
# "Plik POL-on do importu"); generate it with
# `manage.py generuj_plik_polon_demo --out <dir>` and point this at it.
PLIK_POLON = os.environ.get("BPP_DOCS_PLIK_POLON", "")
# Demo submissions created for this page (docs/redaktor/obsluga-zgloszen.md):
# an article with a DOI, a book with a PDF and no link, one closed by the importer.
ZGL_ARTYKUL = "Wpływ fazy księżyca na skuteczność eliksiru Jaskółka"
ZGL_KSIAZKA = "Bestiariusz porównawczy potworów Velen i Temerii"
ZGL_ZAIMPORTOWANE = "Perspektywy rozwoju bestii w lochach Novigradu (nr 10)"
AUTORZY_ZGL = "#zgloszenie_publikacji_autor_set-group"  # authors inline
# A made-up journal list in the layout of a JCR export (header row with
# "Journal name", "<year> JIF", "JIF Quartile"), for the demo journals. One
# journal is listed under two categories (the import keeps the better
# quartile), one has "N/A" and one does not exist in BPP.
JCR_DEMO_ROK = 2024
JCR_DEMO_WIERSZE = [
    ("Acta Wiedźmińska", "6746-8071", "MULTIDISCIPLINARY SCIENCES", "2.417", "Q2"),
    ("Annales Aretuzańska", "9770-3482", "CHEMISTRY, APPLIED", "4.105", "Q1"),
    ("Folia Temerska", "7109-3248", "HISTORY", "1.032", "Q3"),
    ("Folia Temerska", "7109-3248", "AREA STUDIES", "1.032", "Q2"),
    ("Studia Aretuzańska", "4990-913X", "ZOOLOGY", "3.250", "Q1"),
    ("Przegląd Novigradzka", "7444-3135", "HUMANITIES", "N/A", "N/A"),
    ("Journal of Applied Monsterology", "2049-3630", "ZOOLOGY", "0.874", "Q4"),
]
# Demo data for the "nowy rok" page (docs/redaktor/nowy-rok.md): an author
# with disciplines for 2020-2026, a source with points/disciplines up to 2026
# and a 2027 article - i.e. "January, the new year has no data yet".
AUTOR_NOWY_ROK = 210  # Yennefer Merigold
ZRODLO_NOWY_ROK = 40  # Folia Temerska
REKORD_2027 = 1201
# Demo article whose type is sent to PBN (bin/docs-demo-pbn.py maps it).
PBN_REKORD = 1097
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


def import_polon_liczba_n(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/import-polon-liczba-n.md: POL-on import (preview, save) and the N number.

    Needs BPP_DOCS_PLIK_POLON (the generated .xlsx) and a freshly restored demo
    dump: the scenario saves the import for 2022-2025, so a second run on the
    same DB shows no differences.
    """
    if not PLIK_POLON:
        raise SystemExit("Set BPP_DOCS_PLIK_POLON to the demo POL-on .xlsx file.")
    red = new_session(page, base, DEMO_USER_REDAKTOR)

    def czekaj_na_koniec() -> None:
        red.wait_for_selector("#op-result .callout", state="visible", timeout=180_000)
        red.wait_for_timeout(500)

    def importuj(rok: str, zapisz: bool, ukryj: bool = True) -> None:
        red.goto(f"{base}/import_polon/dane/nowy/")
        red.wait_for_load_state("networkidle")
        red.fill("#id_rok", rok)
        red.set_checked("#id_ukryj_niezmatchowanych_autorow", ukryj)
        red.set_checked("#id_zapisz_zmiany_do_bazy", zapisz)
        red.set_input_files("#id_plik", PLIK_POLON)

    # 1. operacje -> import z POLON
    red.goto(f"{base}/")
    red.wait_for_load_state("networkidle")
    li = open_top_menu(red, "fi-wrench")
    mark(
        red,
        [
            {
                "sel": f"{li} a[href*='/import_polon/dane/']",
                "arrow": "right",
                "label": "import z POLON",
                "dx": 60,
            }
        ],
    )
    menu = page_box(red, f"{li} > .menu-columns-wrapper")
    shot(red, out / "01-menu-operacje.png", 0, menu["y"] + menu["height"] + 40)

    # 2. the form: year, unmatched authors shown, "save" left unchecked
    importuj("2025", zapisz=False, ukryj=False)
    red.mouse.move(5, 5)
    mark(
        red,
        [
            {
                "sel": "#id_rok",
                "arrow": "above",
                "label": "1. rok",
                "dx": 100,
                "dy": 0,
            },
            {
                "sel": "label[for=id_ukryj_niezmatchowanych_autorow]",
                "arrow": "right",
                "label": "2. odznacz, by widzieć błędy",
                "dx": 300,
                "dy": -40,
            },
            {
                "sel": "label[for=id_zapisz_zmiany_do_bazy]",
                "arrow": "right",
                "label": "3. puste = tylko podgląd",
                "dx": 300,
                "dy": -40,
            },
            {
                "sel": "#id_plik",
                "arrow": "below",
                "label": "4. plik .xlsx z POL-on",
                "dx": 200,
                "dy": -60,
            },
            {
                "sel": "#id_submit",
                "arrow": "right",
                "label": "5. Utwórz import",
                "dx": 20,
                "dy": -20,
            },
        ],
    )
    shot(red, out / "02-formularz.png", 0, bottom_of(red, "#id_submit", 60))

    # 3. progress page -> finished panel
    red.click("#id_submit")
    czekaj_na_koniec()
    mark(
        red,
        [
            {
                "sel": "#op-result a",
                "text": "Zobacz wyniki",
                "arrow": "below",
                "label": "najpierw przejrzyj wyniki",
                "dx": 0,
                "dy": -20,
            },
        ],
    )
    shot(red, out / "03-import-zakonczony.png", 0, bottom_of(red, "#op-result", 160))
    wyniki = red.locator("#op-result a", has_text="Zobacz wyniki").get_attribute("href")
    wyniki = base + wyniki
    zapisz_url = red.locator(
        "#op-result a", has_text="Zapisz ten import"
    ).get_attribute("href")

    # 4. results: preview warning, people missing from the file, filters
    red.goto(wyniki)
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": ".callout.warning h2"},
            {
                "sel": "#toggle-unmatched",
                "arrow": "right",
                "label": "osoby spoza pliku",
                "dx": 40,
                "dy": -20,
            },
            {"sel": ".filter-checkbox-label"},
        ],
    )
    shot(red, out / "04-wyniki-podglad.png", 0, bottom_of(red, "#filter-form", 30))

    # The results table is wider than 1280 px: shoot it in a wider window,
    # clipped to the full page width.
    tabela_sel = "a[name=pager] ~ table.compact-table"
    red.set_viewport_size({"width": 1600, "height": 800})

    def szeroki(path: Path, box: dict, height: float) -> None:
        """Slice of the page as wide as the results table."""
        red.evaluate("window.scrollTo(0, 0)")
        red.screenshot(
            path=path,
            full_page=True,
            clip={
                "x": max(0, box["x"] - 16),
                "y": max(0, box["y"] - 20),
                "width": box["width"] + 32,
                "height": height,
            },
        )

    # 5. only the differences
    red.check("input[name=pokaz_tylko_roznice]")
    red.wait_for_load_state("networkidle")
    red.wait_for_selector(f"{tabela_sel} tbody tr")
    mark(red, [{"sel": "th", "text": "Rezultat importu"}])
    tabela = page_box(red, tabela_sel)
    szeroki(out / "05-tylko-roznice.png", tabela, 700)

    # 6. the four broken rows of the demo file. The "nie" search narrows the
    # list to one page; rows without an error are hidden only to keep the
    # picture short - every row shown is real.
    red.goto(f"{wyniki}?autor_wiersz=nie")
    red.wait_for_load_state("networkidle")
    red.evaluate(
        """(sel) => {
        const bledy = /REKORD ZIGNOROWANY|Nie udało|nie może być puste/;
        for (const tr of document.querySelectorAll(sel + ' tbody tr'))
          if (!bledy.test(tr.lastElementChild.textContent)) tr.style.display = 'none';
        }""",
        tabela_sel,
    )
    mark(red, [{"sel": "th", "text": "Rezultat importu"}])
    tabela = page_box(red, tabela_sel)
    szeroki(out / "06-wiersze-z-bledami.png", tabela, tabela["height"] + 40)
    red.set_viewport_size(VIEWPORT)

    # 7. authors with a discipline in BPP who are not in the file
    red.goto(wyniki)
    red.wait_for_load_state("networkidle")
    red.click("#toggle-unmatched")
    red.wait_for_timeout(300)
    panel = page_box(red, ".callout.secondary", "nie byli w pliku Excel")
    shot(red, out / "07-osoby-spoza-pliku.png", panel["y"] - 10, 520)

    # 8. confirm saving
    red.goto(base + zapisz_url)
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "#id_submit",
                "arrow": "below",
                "label": "zapis do bazy",
                "dx": 100,
                "dy": -40,
            }
        ],
    )
    shot(red, out / "08-potwierdzenie-zapisu.png", 0, bottom_of(red, "#id_submit", 150))
    red.click("#id_submit")
    czekaj_na_koniec()

    # the remaining years, saved straight away
    for rok in ("2022", "2023", "2024"):
        importuj(rok, zapisz=True)
        red.click("#id_submit")
        czekaj_na_koniec()

    # 9. list of imports with their statistics
    red.goto(f"{base}/import_polon/dane/")
    red.wait_for_load_state("networkidle")
    mark(red, [{"sel": ".importy-table"}])
    shot(red, out / "09-lista-importow.png", 0, bottom_of(red, ".importy-legenda", 20))

    # 10. ewaluacja -> liczba N
    red.goto(f"{base}/")
    red.wait_for_load_state("networkidle")
    li = open_top_menu(red, "fi-graph-bar")
    mark(
        red,
        [
            {
                "sel": f"{li} a[href*='ewaluacja_liczba_n']",
                "arrow": "right",
                "label": "liczba N",
                "dx": 60,
            }
        ],
    )
    menu = page_box(red, f"{li} > .menu-columns-wrapper")
    shot(red, out / "10-menu-ewaluacja.png", 0, menu["y"] + menu["height"] + 40)

    # 11. compute and look at the result
    red.goto(f"{base}/ewaluacja_liczba_n/")
    red.wait_for_load_state("networkidle")
    red.click("#obliczLiczbeNButton")
    red.wait_for_load_state("networkidle")
    red.wait_for_selector("#sankcjeForm")
    mark(
        red,
        [
            {
                "sel": "#obliczLiczbeNButton",
                "arrow": "right",
                "label": "1. Oblicz liczbę N",
                "dx": 40,
                "dy": -20,
            },
            {
                "sel": "a",
                "text": "Weryfikuj poprawność bazy",
                "arrow": "left",
                "label": "kontrola danych",
                "dx": 0,
                "dy": 0,
            },
        ],
    )
    shot(
        red,
        out / "11-liczba-n-gora.png",
        0,
        bottom_of(red, ".ewaluacja-liczba-n__actions-callout", 60),
    )

    mark(
        red,
        [
            {"sel": "#sankcjeForm table"},
            {"sel": ".callout.alert"},
        ],
    )
    h = page_box(red, "h3", "Liczba N dla poszczególnych dyscyplin")
    nier = page_box(red, ".callout.alert")
    shot(
        red,
        out / "12-liczba-n-tabela.png",
        h["y"] - 20,
        nier["y"] + nier["height"] + 30 - (h["y"] - 20),
    )
    red.context.close()


def obsluga_zgloszen(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/obsluga-zgloszen.md: handling submissions (editor in "zgłoszenia publikacji")."""
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    lista = f"{base}/admin/zglos_publikacje/zgloszenie_publikacji/"
    w = VIEWPORT["width"]

    def otworz(tytul: str) -> None:
        red.goto(lista + "?stan_obslugi=wszystkie")
        red.wait_for_load_state("networkidle")
        red.locator("#result_list a", has_text=tytul).first.click()
        red.wait_for_load_state("networkidle")

    # 1. top bar: "redagowanie" -> "Zgłoszenia publikacji"
    li = open_top_menu(red, "fi-pencil")
    mark(
        red,
        [
            {
                "sel": f"{li} > ul a",
                "text": "Zgłoszenia publikacji",
                "arrow": "left",
                "label": "Zgłoszenia publikacji",
                "dy": -60,
            },
        ],
    )
    red.screenshot(
        path=out / "01-menu-redagowanie.png",
        clip={"x": 0, "y": 0, "width": w, "height": 560},
    )

    # 2. the list ("Do obsługi" by default)
    red.mouse.move(5, 700)
    red.goto(lista)
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "#result_list a",
                "text": ZGL_ARTYKUL,
                "arrow": "below",
                "label": "kliknij tytuł",
                "dx": 40,
                "dy": 50,
            },
            {
                "sel": "th.column-status",
                "arrow": "below",
                "label": "status",
                "dx": 40,
                "dy": 85,
            },
            {
                "sel": "#filter-panel-toggle",
                "arrow": "left",
                "label": "filtry",
                "dy": -85,
            },
        ],
    )
    shot(red, out / "02-lista.png", 0, 500)

    # 3. filter panel, "stan obsługi" expanded
    red.click("#filter-panel-toggle")
    red.wait_for_timeout(800)
    red.locator(".filter-title", has_text="stan obsługi").click()
    red.wait_for_timeout(800)
    mark(
        red,
        [
            {
                "sel": ".filter-group",
                "text": "stan obsługi",
                "arrow": "left",
                "label": "Do obsługi / Załatwione / Wszystkie",
                "dy": 60,
            },
        ],
    )
    red.screenshot(
        path=out / "03-filtry.png", clip={"x": 0, "y": 0, "width": w, "height": 480}
    )

    # Tall viewport for the submission page: the fixed "Usuń" footer bar
    # would otherwise cut through the middle of the form.
    red.set_viewport_size({"width": w, "height": 1600})

    # 4. an article with a DOI: the buttons above the form
    otworz(ZGL_ARTYKUL)
    tools = "ul.grp-object-tools a"
    mark(
        red,
        [
            {
                "sel": tools,
                "text": "Użyj importera",
                "arrow": "below",
                "label": "importer",
                "dx": -100,
            },
            {
                "sel": tools,
                "text": "Zwróć do autora",
                "arrow": "below",
                "label": "zwrot",
                "dx": -20,
            },
            {
                "sel": tools,
                "text": "Dodaj wyd. ciągłe",
                "arrow": "below",
                "label": "ręcznie",
                "dx": 20,
            },
        ],
    )
    shot(red, out / "04-zgloszenie-przyciski.png", 0, 400)

    # 5. a book without a link: the PDF attachment, no importer button.
    # The attachment is far below the buttons - top + torn edge + that part.
    otworz(ZGL_KSIAZKA)
    mark(
        red,
        [
            {
                "sel": "div.forma_dostepu .grp-readonly",
                "arrow": "right",
                "label": "dostęp ograniczony",
                "dx": 60,
                "dy": -30,
            },
            {
                "sel": tools,
                "text": "Dodaj wyd. zwarte",
                "arrow": "below",
                "label": "książka: wyd. zwarte",
                "dx": -160,
                "dy": -20,
            },
            {"sel": "div.strona_www .grp-readonly"},
            {
                "sel": "div.pliki_do_pobrania a",
                "arrow": "right",
                "label": "pobierz plik",
                "dx": 60,
                "dy": -40,
            },
            {
                "sel": AUTORZY_ZGL + " > h2",
                "arrow": "below",
                "label": "autorzy, jednostki, dyscypliny",
                "dx": 150,
                "dy": -40,
            },
        ],
    )
    top = shot(red, None, 0, bottom_of(red, "div.forma_dostepu", 10))
    box = page_box(red, "div.strona_www")
    dol = shot(
        red,
        None,
        box["y"] - 10,
        bottom_of(red, "div.pliki_do_pobrania", 10) - box["y"] + 10,
    )
    box = page_box(red, AUTORZY_ZGL)
    autorzy = shot(red, None, box["y"] - 10, box["height"] + 20)
    stitch(
        red,
        [top, dol, autorzy],
        out / "05-zgloszenie-plik.png",
        "niżej w formularzu",
    )

    # 6. return to the author: the reason form (not submitted - keeps the demo DB reusable)
    red.set_viewport_size(VIEWPORT)
    otworz(ZGL_ARTYKUL)
    red.locator(tools, has_text="Zwróć do autora").click()
    red.wait_for_load_state("networkidle")
    red.fill(
        "textarea[name=przyczyna_zwrotu]",
        "Proszę uzupełnić drugiego autora z Aretuzy i dyscyplinę.",
    )
    mark(
        red,
        [
            {
                "sel": "textarea[name=przyczyna_zwrotu]",
                "arrow": "below",
                "label": "1. powód zwrotu",
                "dx": 100,
                "dy": 30,
            },
            {
                "sel": "footer.grp-fixed-footer input[type=submit]",
                "arrow": "above",
                "label": "2. zapisz",
                "dx": -260,
                "dy": 20,
            },
        ],
    )
    red.screenshot(path=out / "06-zwrot.png")

    # 7. importer, first step, opened from the submission
    otworz(ZGL_ARTYKUL)
    red.locator(tools, has_text="Użyj importera").click()
    red.wait_for_load_state("networkidle")
    close_cookie_banner(red)
    mark(
        red,
        [
            {
                "sel": "input[name=identifier]",
                "arrow": "below",
                "label": "DOI ze zgłoszenia",
                "dx": 40,
                "dy": -10,
            },
            {
                "sel": "button[type=submit], input[type=submit]",
                "arrow": "below",
                "label": "dalej",
                "dx": 20,
                "dy": -10,
            },
        ],
    )
    red.screenshot(
        path=out / "07-importer.png", clip={"x": 0, "y": 0, "width": w, "height": 440}
    )

    # 8. a submission closed by the importer
    otworz(ZGL_ZAIMPORTOWANE)
    mark(
        red,
        [
            {
                "sel": "#panel-zgloszenie-zaimportowane",
                "arrow": "below",
                "label": "kto, kiedy, który rekord",
                "dx": 100,
                "dy": 10,
            },
        ],
    )
    shot(red, out / "08-zaimportowane.png", 0, 330)
    red.context.close()


def plik_jcr_demo(path: Path) -> Path:
    """Write the made-up JCR-style XLSX used by the import-punktacji scenario."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append([f"Journal Data Filtered By: Selected JCR Year: {JCR_DEMO_ROK}"])
    ws.append([])
    ws.append(
        [
            "Journal name",
            "ISSN",
            "eISSN",
            "Category",
            f"{JCR_DEMO_ROK} JIF",
            "JIF Quartile",
        ]
    )
    for nazwa, issn, kategoria, jif, kwartyl in JCR_DEMO_WIERSZE:
        ws.append([nazwa, issn, "N/A", kategoria, jif, kwartyl])
    wb.save(path)
    return path


def impact_factor_i_punktacja(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/impact-factor-i-punktacja.md: ISSN export, JCR import, IF/quartile to records (fresh demo DB: imports and sets values)."""
    import tempfile

    red = new_session(page, base, DEMO_USER_REDAKTOR)
    rok = JCR_DEMO_ROK

    # 1. "operacje" menu: the three entries used on this page
    li = open_top_menu(red, "fi-wrench")
    kol = f"{li} .column-2"
    mark(
        red,
        [
            {
                "sel": f"{kol} a",
                "text": "eksport ISSNów",
                "arrow": "left",
                "label": "1. eksport ISSNów",
                "dx": -10,
                "dy": -7,
            },
            {
                "sel": f"{kol} a",
                "text": "import punktacji źródeł",
                "arrow": "left",
                "label": "2. import punktacji źródeł",
                "dx": -10,
                "dy": -13,
            },
            {
                "sel": f"{kol} a",
                "text": "rozbieżności punktacji/kwartyli",
                "arrow": "left",
                "label": "3. rozbieżności punktacji/kwartyli",
                "dx": -10,
                "dy": -50,
            },
        ],
    )
    menu = page_box(red, f"{li} .menu-columns-wrapper")
    shot(red, out / "01-menu-operacje.png", 0, menu["y"] + menu["height"] + 30)

    # 2. list of imports -> "Nowy import"
    red.goto(f"{base}/import_punktacji_zrodel/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "a.button",
                "text": "Nowy import",
                "arrow": "right",
                "label": "Nowy import",
                "dx": 20,
            }
        ],
    )
    shot(red, out / "02-nowy-import.png", 0, bottom_of(red, "table", 60))

    # 3. the form: file, preview first (save unchecked)
    red.goto(f"{base}/import_punktacji_zrodel/new/")
    red.wait_for_load_state("networkidle")
    plik = plik_jcr_demo(Path(tempfile.mkdtemp()) / f"jcr-{rok}-demo.xlsx")
    red.set_input_files("input[name=plik]", str(plik))
    mark(
        red,
        [
            {
                "sel": "label[for=id_zapisz_zmiany_do_bazy]",
                "arrow": "right",
                "label": "1. bez zaznaczenia = tylko podgląd",
                "dx": 300,
                "dy": -40,
            },
            {
                "sel": "input[name=plik]",
                "arrow": "below",
                "label": "2. plik z JCR",
                "dx": 200,
            },
            {
                "sel": "#id_submit",
                "arrow": "right",
                "label": "3. Wczytaj i pokaż podgląd",
                "dx": 20,
                "dy": -40,
            },
        ],
    )
    form = page_box(red, "form:has(#id_submit)")
    shot(
        red,
        out / "03-formularz-importu.png",
        form["y"] - 80,
        form["height"] + 220,
    )

    # 4. live page: preview finished
    red.click("#id_submit")
    red.wait_for_selector("text=Podgląd gotowy", timeout=60000)
    red.wait_for_timeout(500)
    mark(
        red,
        [
            {
                "sel": "a.button",
                "text": "Zobacz pełne wyniki importu",
                "arrow": "right",
                "label": "pełne wyniki",
                "dx": 20,
            }
        ],
    )
    wynik = page_box(red, ".panel.callout")
    shot(red, out / "04-podglad-gotowy.png", 0, wynik["y"] + wynik["height"] + 30)

    # 5. full preview results + "Zatwierdź i zapisz do bazy"
    red.click("text=Zobacz pełne wyniki importu")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "button",
                "text": "Zatwierdź i zapisz do bazy",
                "arrow": "right",
                "label": "zapisz, gdy podgląd się zgadza",
                "dx": 20,
            },
            {"sel": "tbody tr", "text": "Folia Temerska"},
        ],
    )
    shot(red, out / "05-wyniki-podgladu.png", 0, bottom_of(red, "table", 30))

    # 6. after saving: links to the discrepancy pages
    red.click("button:has-text('Zatwierdź i zapisz do bazy')")
    red.wait_for_selector("text=Import zakończony", timeout=60000)
    red.click("text=Zobacz pełne wyniki importu")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": ".callout.success a.button",
                "text": "IF",
                "arrow": "below",
                "label": "przenieś IF na prace",
                "dx": 40,
                "dy": -20,
            },
            {
                "sel": ".callout.success a.button",
                "text": "kwartyla",
                "arrow": "right",
                "label": "przenieś kwartyle",
                "dx": 30,
                "dy": -40,
            },
        ],
    )
    box = page_box(red, ".callout.success")
    shot(red, out / "06-import-zapisany.png", 0, box["y"] + box["height"] + 140)

    # 7. where the values live: the source's "punktacja źródła" rows
    red.goto(f"{base}/admin/bpp/zrodlo/37/change/")
    red.wait_for_load_state("networkidle")
    top = shot(red, None, 0, 300)
    sekcja = "#punktacja_zrodla_set-group"
    mark(
        red,
        [
            {"sel": "#id_punktacja_zrodla_set-0-rok"},
            {"sel": "#id_punktacja_zrodla_set-0-impact_factor"},
            {"sel": "#id_punktacja_zrodla_set-0-kwartyl_w_wos"},
        ],
    )
    box = page_box(red, sekcja)
    dol = shot(red, None, box["y"] - 20, box["height"] + 300)
    stitch(
        red,
        [top, dol],
        out / "07-zrodlo-punktacja.png",
        "przewiń do „punktacja źródła”",
    )

    # 8. one record: "Uzupełnij punktację" on the publication form
    red.goto(f"{base}/admin/bpp/wydawnictwo_ciagle/731/change/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "#id_wypelnij_pola_punktacji_button",
                "arrow": "below",
                "label": "kopiuje punktację źródła za rok pracy",
                "dx": 250,
            },
            {
                "sel": "#id_dodaj_punktacje_do_zrodla_button",
                "arrow": "above",
                "label": "odwrotnie: zapisuje do źródła",
                "dx": 40,
            },
        ],
    )
    box = page_box(red, "fieldset", "Punktacja")
    top = shot(red, None, 0, 260)
    dol = shot(red, None, box["y"] - 140, box["height"] + 300)
    stitch(
        red,
        [top, dol],
        out / "08-rekord-uzupelnij.png",
        "przewiń do sekcji „Punktacja”",
    )

    # 9. all records at once: rozbieżności IF for the year
    red.goto(f"{base}/rozbieznosci/if/?rok_od={rok}&rok_do={rok}")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": ".tabs"},
            {"sel": "td button", "text": "ustaw wg źródła"},
            {
                "sel": "button",
                "text": "Ustaw wszystkie wg źródła",
                "arrow": "left",
                "label": "wszystkie z listy",
                "dx": -10,
                "dy": -40,
            },
        ],
    )
    shot(red, out / "09-rozbieznosci-if.png", 0, bottom_of(red, "tbody tr", 20))

    # 10. confirmation page
    red.click("button:has-text('Ustaw wszystkie wg źródła')")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "form button",
                "text": "Tak, przejdź",
                "arrow": "below",
                "label": "potwierdź",
                "dx": 60,
                "dy": -30,
            }
        ],
    )
    shot(red, out / "10-ustaw-wszystkie.png", 0, bottom_of(red, "form button", 120))

    # 11. result message
    red.click("form button:has-text('Tak, przejdź')")
    red.wait_for_load_state("networkidle")
    red.wait_for_selector("#messagesPlaceholder >> text=Zaktualizowano")
    red.wait_for_timeout(800)
    mark(red, [{"sel": "#messagesPlaceholder"}])
    msg = page_box(red, "#messagesPlaceholder")
    shot(red, out / "11-ustawiono.png", 0, msg["y"] + msg["height"] + 260)

    # 12. ministerial lists: the form
    red.goto(f"{base}/import_list_ministerialnych/nowy/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "label[for=id_zapisz_zmiany_do_bazy]",
                "arrow": "right",
                "label": "bez zaznaczenia = tylko podgląd",
                "dx": 20,
            },
        ],
    )
    shot(red, out / "12-listy-ministerialne.png", 0, bottom_of(red, "#id_submit", 30))
    red.context.close()


def nowy_rok(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/nowy-rok.md: per-year data (author/source disciplines, source points) for a new year."""
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    rekord = f"{base}/admin/bpp/wydawnictwo_ciagle/{REKORD_2027}/change/"

    # 1. a 2027 record saved: the "rok poza zakresem" warning
    red.goto(rekord)
    red.wait_for_load_state("networkidle")
    red.click("input[name=_continue]")
    red.wait_for_load_state("networkidle")
    mark(red, [{"sel": ".grp-messagelist li", "text": "rok poza zakresem"}])
    shot(
        red,
        out / "01-rekord-rok-poza-zakresem.png",
        0,
        bottom_of(red, ".grp-messagelist", 30),
    )

    # 2. the discipline list of an author in a 2027 record
    sel = "select[name=autorzy_set-0-dyscyplina_naukowa]"
    red.locator(f"{sel} + .select2 .select2-selection").scroll_into_view_if_needed()
    red.locator(f"{sel} + .select2 .select2-selection").click()
    red.wait_for_selector(".select2-results__option", state="visible")
    red.wait_for_timeout(800)
    mark(
        red,
        [
            {
                "sel": ".select2-results__option",
                "arrow": "right",
                "label": "brak dyscypliny na 2027",
                "dx": -40,
            }
        ],
    )
    box = page_box(red, ".select2-container--open .select2-dropdown")
    red.screenshot(
        path=out / "02-rekord-brak-przypisania.png",
        clip={
            "x": 0,
            "y": max(0, box["y"] - 250),
            "width": VIEWPORT["width"],
            "height": 400,
        },
        full_page=True,
    )
    red.keyboard.press("Escape")

    # 3. author: disciplines per year, new row for 2027
    red.goto(f"{base}/admin/bpp/autor/{AUTOR_NOWY_ROK}/change/")
    red.wait_for_load_state("networkidle")
    grp = "#autor_dyscyplina_set-group"
    n = int(red.input_value("#id_autor_dyscyplina_set-TOTAL_FORMS")) - 1
    row = f"autor_dyscyplina_set-{n}"  # field names; the row <div> id has no dash
    red.fill(f"[name={row}-rok]", "2027")
    red.select_option(
        f"[name={row}-rodzaj_autora]", label="N - pracownik naukowy w liczbie N"
    )
    red.fill(f"[name={row}-wymiar_etatu]", "1")
    select2(red, f"select[name={row}-dyscyplina_naukowa]", "filozofia")
    red.fill(f"[name={row}-procent_dyscypliny]", "100")
    red.mouse.move(5, 5)
    mark(
        red,
        [
            {"sel": f"{grp} > h2"},
            {
                "sel": f"#autor_dyscyplina_set{n}",
                "arrow": "below",
                "label": "nowy wiersz: rok 2027",
                "dy": -10,
            },
        ],
    )
    top = shot(red, None, 0, 300)
    g = page_box(red, grp)
    bottom = shot(red, None, g["y"] - 20, g["height"] + 160)
    stitch(
        red,
        [top, bottom],
        out / "03-autor-dyscypliny.png",
        "przewiń do „Powiązania autor-dyscyplina”",
    )

    # 4. all authors' disciplines, filtered by year
    red.goto(f"{base}/admin/bpp/autor_dyscyplina/?rok=2026")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": "#result_list th", "text": "Rok"},
            {
                "sel": "a",
                "text": "Eksport",
                "arrow": "left",
                "label": "eksport do Excela",
                "dx": -60,
                "dy": -95,
            },
        ],
    )
    shot(red, out / "04-lista-autor-dyscyplina.png", 0, 520)

    # 5. operacje menu: the imports and the discrepancy reports
    red.goto(f"{base}/")
    red.wait_for_load_state("networkidle")
    li = open_top_menu(red, "fi-wrench")
    mark(
        red,
        [
            {"sel": f"{li} li:has(> a[href*='import_polon/dane'])"},
            {"sel": f"{li} li:has(> a[href*='import_list_ministerialnych'])"},
            {"sel": f"{li} li:has(> a[href*='import_dyscyplin'])"},
            {"sel": f"{li} li:has(> a[href*='rozbieznosciview'])"},
        ],
    )
    menu = page_box(red, f"{li} > .menu-columns-wrapper")
    shot(red, out / "05-menu-operacje.png", 0, menu["y"] + menu["height"] + 30)

    # 6. import dyscyplin: the file and the year
    red.goto(f"{base}/import_dyscyplin/create/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "[name=rok]",
                "arrow": "below",
                "label": "rok, którego dotyczy plik",
                "dx": 40,
                "dy": -30,
            }
        ],
    )
    shot(red, out / "06-import-dyscyplin.png", 0, bottom_of(red, "[name=rok]", 190))

    # 7. source: points per year, a new row for 2027
    red.goto(f"{base}/admin/bpp/zrodlo/{ZRODLO_NOWY_ROK}/change/")
    red.wait_for_load_state("networkidle")
    red.add_style_tag(content=".grp-fixed-footer{display:none!important}")
    grp = "#punktacja_zrodla_set-group"
    n = int(red.input_value("#id_punktacja_zrodla_set-TOTAL_FORMS")) - 1
    red.fill(f"[name=punktacja_zrodla_set-{n}-rok]", "2027")
    red.fill(f"[name=punktacja_zrodla_set-{n}-punkty_kbn]", "140")
    red.mouse.move(5, 5)
    mark(
        red,
        [
            {"sel": f"{grp} > h2"},
            {
                "sel": f"#punktacja_zrodla_set{n}",
                "arrow": "below",
                "label": "nowy wiersz: rok 2027",
                "dx": -100,
                "dy": -85,
            },
        ],
    )
    top = shot(red, None, 0, 260)
    g = page_box(red, grp)
    bottom = shot(red, None, g["y"] - 20, g["height"] + 50)
    stitch(
        red,
        [top, bottom],
        out / "07-zrodlo-punktacja.png",
        "przewiń do „Punktacja źródła”",
    )

    # 8. source: disciplines per year (a collapsed section - open it)
    grp = "#dyscyplina_zrodla_set-group"
    red.click(f"{grp} > h2")
    red.wait_for_timeout(600)
    mark(red, [{"sel": f"{grp} > h2"}])
    g = page_box(red, grp)
    shot(red, out / "08-zrodlo-dyscypliny.png", g["y"] - 20, g["height"] + 40)

    # 9. import list ministerialnych
    red.goto(f"{base}/import_list_ministerialnych/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "[name=rok]",
                "arrow": "below",
                "label": "rok listy",
                "dx": 300,
                "dy": -40,
            },
            {
                "sel": "label[for=id_zapisz_zmiany_do_bazy]",
                "arrow": "right",
                "label": "bez tego tylko podgląd",
                "dx": 40,
            },
        ],
    )
    shot(
        red,
        out / "09-import-list-ministerialnych.png",
        0,
        bottom_of(red, "#id_submit", 30),
    )

    # 10. a record: copy the source's points for the record's year
    red.goto(rekord)
    red.wait_for_load_state("networkidle")
    red.add_style_tag(content=".grp-fixed-footer{display:none!important}")
    btn = "#id_wypelnij_pola_punktacji_button"
    red.locator(btn).scroll_into_view_if_needed()
    mark(
        red,
        [
            {
                "sel": btn,
                "arrow": "below",
                "label": "punkty ze źródła za rok rekordu",
                "dx": 300,
                "dy": -80,
            },
            {"sel": "#id_dodaj_punktacje_do_zrodla_button"},
        ],
    )
    b = page_box(red, btn)
    shot(red, out / "10-rekord-uzupelnij-punktacje.png", b["y"] - 400, 500)

    red.context.close()


def pbn_wysylka_i_synchronizacja(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/pbn-wysylka-i-synchronizacja.md: PBN menu, sending, export queue, import, comparators.

    Needs the PBN demo state: uv run python src/manage.py shell < bin/docs-demo-pbn.py
    (re-run it before every run: step 5 adds a queue entry). No PBN behind it.
    """
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    w = VIEWPORT["width"]

    # 1. the PBN menu: authorise, import/download, queue, comparators
    li = open_top_menu(red, "fi-link")
    col1 = f"{li} .column-1 a"
    mark(
        red,
        [
            {
                "sel": col1,
                "text": "autoryzuj PBN API",
                "arrow": "left",
                "label": "1. autoryzacja",
            },
            {
                "sel": col1,
                "text": "kolejka eksportu",
                "arrow": "left",
                "label": "stan wysyłek",
            },
            {
                "sel": f"{li} .column-2",
                "arrow": "below",
                "label": "porównanie BPP z PBN",
                "dx": -330,
                "dy": -20,
            },
        ],
    )
    menu = page_box(red, f"{li} > .menu-columns-wrapper")
    shot(red, out / "01-menu-pbn.png", 0, menu["y"] + menu["height"] + 135)

    # 2. typed/bookmarked address: the page before leaving for PBN
    red.goto(f"{base}/pbn_api/authorize?next=/")
    red.wait_for_load_state("networkidle")
    btn = "form[action*='authorize'] button[type=submit]"
    mark(red, [{"sel": btn, "arrow": "below", "label": "2. logowanie w PBN"}])
    shot(red, out / "02-autoryzacja.png", 0, bottom_of(red, btn, 170))

    # 3. record form: the two PBN buttons in the bottom bar
    rekord = f"{base}/admin/bpp/wydawnictwo_ciagle/{PBN_REKORD}/change/"
    red.goto(rekord)
    red.wait_for_load_state("networkidle")
    teraz = "input[name=_continue_and_pbn]"
    w_tle = "input[name=_continue_and_pbn_later]"
    mark(
        red,
        [
            {"sel": teraz, "arrow": "above", "label": "od razu", "dx": 0},
            {"sel": w_tle, "arrow": "above", "label": "w tle", "dx": -140},
        ],
    )
    red.screenshot(
        path=out / "03-przyciski-wyslij.png",
        clip={"x": 0, "y": 590, "width": w, "height": 210},
    )

    # 4. "Zapisz i wyślij do PBN": the messages come back at the top.
    # Messages span the full width - boxes only, the text explains them.
    red.click(teraz)
    red.wait_for_load_state("networkidle")
    msgs = "ul.grp-messagelist"
    li_msg = f"{msgs} li"
    mark(
        red,
        [
            {"sel": li_msg, "text": "nie posiada odpowiednika"},
            {"sel": li_msg, "text": "nie zostanie wysłany"},
            {"sel": li_msg, "text": "W kolejce na wysłanie"},
        ],
    )
    shot(red, out / "04-komunikaty-wysylki.png", 0, bottom_of(red, msgs, 20))

    # 5. "... w tle": only a queue entry is created
    red.click(w_tle)
    red.wait_for_load_state("networkidle")
    mark(red, [{"sel": f"{li_msg} a", "text": "śledzić stan"}])
    shot(red, out / "05-wyslij-w-tle.png", 0, bottom_of(red, msgs, 20))

    # 6. many records at once: admin action at the bottom of the list
    red.goto(f"{base}/admin/bpp/wydawnictwo_ciagle/?rok=2024")
    red.wait_for_load_state("networkidle")
    for box in red.locator("input.action-select").all()[:3]:
        box.check()
    red.select_option("select[name=action]", label="Wyślij do PBN w tle")
    marks = [
        {"sel": f"#result_list tbody tr:nth-child({n}) input.action-select"}
        for n in (1, 2, 3)
    ]
    marks += [
        {
            "sel": "select[name=action]",
            "arrow": "above",
            "label": "akcja",
            "dx": 40,
            "dy": 20,
        },
        {
            "sel": ".grp-changelist-actions button, button[name=index]",
            "arrow": "above",
            "label": "Wykonaj",
            "dx": 60,
            "dy": 20,
        },
    ]
    mark(red, marks)
    red.screenshot(path=out / "06-akcja-zbiorcza.png")

    # 7. the export queue: counters, filters, bulk retry buttons
    red.goto(f"{base}/pbn_export_queue/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": ".pbn-export-queue__page-actions"},
            {"sel": ".pbn-export-queue__filter-buttons"},
        ],
    )
    shot(
        red,
        out / "07-kolejka-lista.png",
        0,
        bottom_of(red, ".pbn-export-queue__send-section", 10),
    )

    # 8. error rows under the list entries
    red.goto(f"{base}/pbn_export_queue/?zakonczono_pomyslnie=false")
    red.wait_for_load_state("networkidle")
    mark(red, [{"sel": "#export-queue-table tbody tr", "text": "Wpływ szlaku"}])
    tab = page_box(red, "#export-queue-table")
    shot(red, out / "08-kolejka-bledy.png", tab["y"] - 10, tab["height"] + 20)

    # 9. details of one failed send
    # (queue ids change with every seed run - open it from the list)
    red.locator("#export-queue-table tr", has_text="Wpływ szlaku").locator(
        "a.button"
    ).click()
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": ".pbn-export-queue__error-section",
                "arrow": "left",
                "label": "1. powód",
                "dx": 20,
                "dy": -150,
            },
            {
                "sel": "a.button",
                "text": "Edytuj w admin",
                "arrow": "right",
                "label": "2. popraw rekord",
            },
            {
                "sel": ".pbn-export-queue__header form",
                "text": "Wyslij do PBN",
                "arrow": "below",
                "label": "3. wyślij ponownie",
                "dx": -110,
                "dy": -20,
            },
        ],
    )
    shot(
        red,
        out / "09-kolejka-szczegoly.png",
        0,
        bottom_of(red, ".pbn-export-queue__error-section", 30),
    )

    # 10. Import z PBN: one-off import, needs an active PBN session
    red.goto(f"{base}/pbn_import/")
    red.wait_for_load_state("networkidle")
    red.wait_for_function("document.body.innerText.includes('Aktualizacja')")
    mark(red, [{"sel": "a.button", "text": "Zaloguj się do PBN"}])
    hist = page_box(red, "h2", "Historia importów")
    shot(red, out / "10-import-z-pbn.png", 0, hist["y"] - 40)

    # 11. Pobieranie danych z PBN: refreshes the local copy
    red.goto(f"{base}/pbn_downloader_app/")
    red.wait_for_load_state("networkidle")
    mark(red, [{"sel": "#download-btn"}])
    shot(red, out / "11-pobieranie-danych.png", 0, bottom_of(red, "#download-btn", 150))

    # 12. Komparator PBN: what is missing on either side
    red.goto(f"{base}/komparator_pbn/")
    red.wait_for_load_state("networkidle")
    sekcja = "h3"
    roz = page_box(red, sekcja, "rozbieżności między PBN a BPP")
    mark(
        red,
        [
            {"sel": "h4", "text": "Publikacje PBN nieistniejące w BPP"},
            {"sel": "h4", "text": "Publikacje skasowane w PBN"},
        ],
    )
    top = shot(red, None, 0, 470)
    dol = shot(red, None, roz["y"] - 20, 420)
    stitch(
        red,
        [top, dol],
        out / "12-komparator-pbn.png",
        "przewiń do „Publikacje - rozbieżności między PBN a BPP”",
    )
    red.context.close()


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


def duplikaty(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/duplikaty.md: merging duplicate authors and sources (editor).

    Needs the duplicates from bin/docs-demo-duplikaty.py and a Celery worker
    (both scans run in the background). Merges and remaps for real, so run it
    on a fresh copy of the demo DB."""
    d = new_session(page, base, DEMO_USER_REDAKTOR)
    d.on("dialog", lambda dialog: dialog.accept())  # "Czy na pewno…?" prompts
    dedup = f"{base}/deduplikator_autorow/duplicate-authors/"

    def card(autor: str) -> str:
        return f"[data-author-name='{autor}']"

    # 1. "operacje" menu: author and source deduplicators
    li = open_top_menu(d, "fi-wrench")
    links = f"{li} .menu-columns-wrapper a"
    mark(
        d,
        [
            {
                "sel": links,
                "text": "deduplikator autorów",
                "arrow": "right",
                "label": "autorzy",
                "dx": 60,
                "dy": -40,
            },
            {
                "sel": links,
                "text": "deduplikator źródeł",
                "arrow": "right",
                "label": "źródła",
                "dx": 60,
                "dy": 0,
            },
        ],
    )
    shot(
        d, out / "01-menu-operacje.png", 0, bottom_of(d, f"{li} .menu-columns-wrapper")
    )

    # 2. First visit: no scan yet -> start one (runs in the background)
    d.goto(dedup)
    d.wait_for_load_state("networkidle")
    start = d.get_by_role("button", name="Uruchom skanowanie duplikatów")
    if start.count():
        d.mouse.move(5, 5)
        mark(
            d,
            [
                {
                    "sel": ".deduplikator-autorow__callout-centered button",
                    "arrow": "below",
                    "label": "uruchom skanowanie",
                    "dx": 120,
                    "dy": -30,
                }
            ],
        )
        shot(
            d,
            out / "02-uruchom-skanowanie.png",
            0,
            bottom_of(d, ".deduplikator-autorow__callout-centered", 90),
        )
        start.click()
        d.wait_for_load_state("networkidle")
        for _ in range(100):
            d.wait_for_timeout(3000)
            d.goto(dedup)
            d.wait_for_load_state("networkidle")
            if not d.locator("#scan-progress-container").count():
                break

    # 3. Search by surname, "Następny" to the next main author
    d.fill("#search_lastname", "Rivii")
    d.locator(".deduplikator-autorow__top-search button[type=submit]").click()
    d.wait_for_load_state("networkidle")
    d.mouse.move(5, 5)
    mark(
        d,
        [
            {
                "sel": ".deduplikator-autorow__top-search-group",
                "arrow": "above",
                "label": "1. nazwisko",
                "dx": -60,
                "dy": 45,
            },
            {
                "sel": ".deduplikator-autorow__header .button-group",
                "arrow": "left",
                "label": "2. kolejny autor",
                "dx": 0,
                "dy": -60,
            },
        ],
    )
    shot(
        d,
        out / "03-wyszukiwanie.png",
        0,
        bottom_of(d, ".deduplikator-autorow__header", 30),
    )
    d.locator("a.button", has_text="Następny").click()
    d.wait_for_load_state("networkidle")

    # 4. Main record (kept) — top of the blue card
    main = page_box(d, ".callout.primary", "Główny rekord autora")
    mark(
        d,
        [{"sel": ".deduplikator-autorow__main-record-title > span"}],
    )
    table = page_box(d, ".callout.primary table")
    shot(
        d,
        out / "04-glowny-rekord.png",
        main["y"] - 20,
        table["y"] + table["height"] - main["y"] + 40,
    )

    # 5. One candidate card: confidence, reasons, decision, merge buttons
    g = card("z Rivii G.")
    box = page_box(d, g)
    d.evaluate("document.getElementById('kb-overlay')?.remove()")
    mark(
        d,
        [
            {
                "sel": f"{g} .label",
                "arrow": "right",
                "label": "pewność",
                "dx": 80,
                "dy": -70,
            },
            {
                "sel": f"{g} .deduplikator-autorow__reasons-section",
                "arrow": "below",
                "label": "powody",
                "dx": -380,
                "dy": -50,
            },
            {
                "sel": f"{g} .deduplikator-autorow__action-group",
                "text": "Decyzja",
                "arrow": "left",
                "label": "to inna osoba",
                "dx": -10,
                "dy": -185,
            },
            {
                "sel": f"{g} .deduplikator-autorow__action-group",
                "text": "Scalanie",
                "arrow": "left",
                "label": "to ta sama osoba",
                "dx": -10,
                "dy": 40,
            },
        ],
    )
    reasons = page_box(d, f"{g} .deduplikator-autorow__action-group", "Scalanie")
    shot(
        d,
        out / "05-karta-duplikatu.png",
        box["y"] - 20,
        reasons["y"] + reasons["height"] - box["y"] + 50,
    )

    # 6. "Scal wszystkie…" for the whole group
    d.evaluate("document.getElementById('kb-overlay')?.remove()")
    head = page_box(d, ".deduplikator-autorow__duplicates-title")
    mark(
        d,
        [
            {
                "sel": "#merge-all-btn",
                "arrow": "below",
                "label": "wszystkie naraz",
                "dx": -260,
                "dy": -60,
            },
            {"sel": "#merge-all-no-pbn-btn"},
        ],
    )
    shot(d, out / "06-scal-wszystkie.png", head["y"] - 60, 210)

    # 7. Merge one candidate ("Scal, nie wysyłaj do PBN"): card disappears
    d.evaluate("document.getElementById('kb-overlay')?.remove()")
    d.locator(f"{g} [data-merge-action=no-pbn]").click()
    d.wait_for_selector(g, state="detached", timeout=60000)
    d.wait_for_timeout(1500)
    msg = d.locator(".callout.success", has_text="pomyślnie scaleni")
    if msg.count():
        mark(d, [{"sel": ".callout.success", "text": "pomyślnie scaleni"}])
        mbox = page_box(d, ".callout.success", "pomyślnie scaleni")
        shot(d, out / "07-scalono.png", 0, mbox["y"] + mbox["height"] + 30)

    # 8. Sidebar: recent merges (history)
    d.goto(f"{dedup}?search_lastname=Rivii&mode=both&skip_count=1")
    d.wait_for_load_state("networkidle")
    # The sidebar is position:fixed - a full-page shot would cut it at the
    # viewport height, so let it scroll with the page.
    d.add_style_tag(
        content=".left-menu-sidebar{position:absolute!important;"
        "height:auto!important;overflow:visible!important}"
    )
    d.locator(".accordion-title", has_text="Ostatnie scalenia").click()
    d.wait_for_timeout(2000)
    d.mouse.move(5, 5)
    mark(
        d,
        [
            {
                "sel": ".deduplikator-autorow__merge-list",
                "arrow": "right",
                "label": "co i kiedy",
                "dx": -10,
                "dy": -40,
            },
            {
                "sel": ".accordion-content a.button",
                "text": "Zobacz wszystkie",
                "arrow": "right",
                "label": "pełna historia",
                "dx": -10,
                "dy": -20,
            },
        ],
    )
    top = page_box(d, ".accordion-title", "Ostatnie scalenia")
    d.evaluate("window.scrollTo(0, 0)")
    d.screenshot(
        path=out / "08-ostatnie-scalenia.png",
        full_page=True,
        clip={
            "x": 0,
            "y": top["y"] - 20,
            "width": 700,
            "height": bottom_of(d, ".accordion-content a.button[href*=logscalania]", 30)
            - top["y"]
            + 20,
        },
    )

    # 9. "Nie jest duplikatem" on another pair -> "Nie-duplikaty" panel
    d.goto(f"{dedup}?search_lastname=Rivii&mode=both")
    d.wait_for_load_state("networkidle")
    d.locator("[data-mark-not-duplicate]").first.click()
    d.wait_for_timeout(2500)
    d.goto(dedup)
    d.wait_for_load_state("networkidle")
    d.add_style_tag(
        content=".left-menu-sidebar{position:absolute!important;"
        "height:auto!important;overflow:visible!important}"
    )
    d.mouse.move(5, 5)
    nd = ".accordion-item:has(#not-duplicate-count)"
    mark(
        d,
        [{"sel": f"{nd} a.button"}],
    )
    shot(d, out / "09-nie-duplikaty.png", 0, bottom_of(d, nd, 30))

    # 10. Author page: "Przemapuj prace" (works between units)
    d.goto(f"{base}/bpp/autor/166/")
    d.wait_for_load_state("networkidle")
    d.mouse.move(5, 5)
    mark(
        d,
        [
            {
                "sel": ".jednostka-remap-button",
                "arrow": "left",
                "label": "Przemapuj prace",
                "dx": 0,
                "dy": -60,
            }
        ],
    )
    shot(d, out / "10-strona-autora.png", 0, bottom_of(d, ".author-header", 90))

    # 11. Remap form: works sit in two units after the merge
    d.goto(f"{base}/przemapuj_prace_autora/autor/166/")
    d.wait_for_load_state("networkidle")
    zly = d.evaluate(
        """[...document.querySelectorAll('select[name=jednostka_z] option')]
        .find(o => o.textContent.includes('Pracownia')).value"""
    )
    d.select_option("select[name=jednostka_z]", zly)
    dobra = d.evaluate(
        """[...document.querySelectorAll('select[name=jednostka_do] option')]
        .find(o => o.textContent.startsWith('Zakład Bestiariuszu')).value"""
    )
    d.select_option("select[name=jednostka_do]", dobra)
    d.mouse.move(5, 5)
    mark(
        d,
        [
            {"sel": "table tbody tr", "text": "Pracownia"},
            {
                "sel": "select[name=jednostka_z]",
                "arrow": "below",
                "label": "1. skąd",
                "dx": 60,
                "dy": -30,
            },
            {
                "sel": "select[name=jednostka_do]",
                "arrow": "below",
                "label": "2. dokąd",
                "dx": -100,
                "dy": -30,
            },
            {
                "sel": "button[name=preview]",
                "arrow": "below",
                "label": "3. podgląd",
                "dx": -60,
                "dy": -40,
            },
        ],
    )
    shot(
        d, out / "11-przemapuj-prace.png", 0, bottom_of(d, "button[name=preview]", 110)
    )

    # 12. Preview -> confirm; 13. result with "Historia przemapowań" + "Cofnij"
    d.locator("button[name=preview]").click()
    d.wait_for_load_state("networkidle")
    d.locator("button[name=confirm]").click()
    d.wait_for_load_state("networkidle")
    d.mouse.move(5, 5)
    mark(
        d,
        [
            {"sel": ".callout.success"},
            {
                "sel": "form[action*=cofnij] button",
                "arrow": "below",
                "label": "cofnij",
                "dx": -200,
                "dy": -40,
            },
        ],
    )
    # Short page: message and history fit in one shot.
    hist = page_box(d, "h3", "Historia przemapowań")
    shot(d, out / "12-przemapowano-prace.png", 0, hist["y"] + 280)

    # 14. Source deduplicator: scan (django-liveops), then the list of pairs
    zr = f"{base}/deduplikator-zrodel/"
    d.goto(zr)
    d.wait_for_load_state("networkidle")
    skan = d.get_by_role("button", name="Skanuj bazę")
    if skan.count() and not d.locator("table tbody tr td a").count():
        skan.click()
        d.wait_for_load_state("networkidle")
        # Live progress page. When done it shows "Zobacz listę duplikatów"
        # (or liveops.js redirects to the list by itself).
        lista = d.get_by_role("link", name="Zobacz listę duplikatów")
        for _ in range(100):
            if "/live/" not in d.url or lista.count():
                break
            d.wait_for_timeout(3000)
        if lista.count():
            d.mouse.move(5, 5)
            mark(
                d,
                [
                    {
                        "sel": ".callout.success a.button",
                        "arrow": "right",
                        "label": "lista par",
                        "dx": 0,
                        "dy": -40,
                    }
                ],
            )
            shot(d, out / "13-skan-zrodel.png", 0, bottom_of(d, ".callout.success", 90))
            lista.click()
        d.wait_for_load_state("networkidle")
    para = "table tbody tr"
    przemapuj = "a.button[href*='/przemapuj-zrodlo/ACTA-OXENFURCKA/']"
    mark(
        d,
        [
            {"sel": para, "text": "ACTA OXENFURCKA"},
            {
                "sel": przemapuj,
                "arrow": "below",
                "label": "1. Przemapuj",
                "dx": -200,
                "dy": -20,
            },
            {
                "sel": "form[action*=skanuj] button",
                "arrow": "above",
                "label": "nowy skan",
                "dx": 300,
                "dy": 20,
            },
        ],
    )
    row = page_box(d, para, "ACTA OXENFURCKA")
    shot(d, out / "14-deduplikator-zrodel.png", 0, row["y"] + row["height"] + 140)

    # 15. "Przemapuj źródło" form, target prefilled from the pair
    d.locator(przemapuj).click()
    d.wait_for_load_state("networkidle")
    d.wait_for_timeout(1000)  # target panel is filled by fetch
    d.uncheck("input[name=wyslac_do_pbn]")
    d.check("input[name=potwierdzenie]")
    d.mouse.move(5, 5)
    mark(
        d,
        [
            {"sel": "#przemapuj-panels"},
            {"sel": "#id_zrodlo_docelowe + .select2"},
            {"sel": "#div_id_wyslac_do_pbn"},
            {"sel": "#div_id_potwierdzenie"},
            {"sel": "#przemapuj-form button[type=submit]"},
        ],
    )
    shot(
        d,
        out / "15-przemapuj-zrodlo.png",
        0,
        bottom_of(d, "#przemapuj-form .button-group", 30),
    )

    # 16. Submit -> target source page with the result message
    d.evaluate("document.getElementById('kb-overlay')?.remove()")
    d.locator("#przemapuj-form button[type=submit]").click()
    d.wait_for_load_state("networkidle")
    mark(d, [{"sel": ".callout.success", "text": "przemapowano"}])
    shot(d, out / "16-przemapowano-zrodlo.png", 0, bottom_of(d, ".callout.success", 30))

    # 17. History of source remaps with "Cofnij" (admin)
    d.goto(f"{base}/admin/przemapuj_zrodlo/przemapowazrodla/")
    d.wait_for_load_state("networkidle")
    mark(
        d,
        [
            {
                "sel": "#result_list a.admin-action-btn--warning",
                "arrow": "left",
                "label": "cofnij",
                "dx": -10,
                "dy": 40,
            }
        ],
    )
    shot(
        d,
        out / "17-historia-przemapowan-zrodel.png",
        0,
        bottom_of(d, "#result_list", 140),
    )

    # 18. Sources without publications: filter + bulk action (admin).
    # The filters sit behind "Filtruj"; the action bar is fixed at the bottom
    # of the window, so this one is a plain viewport screenshot.
    d.goto(f"{base}/admin/bpp/zrodlo/?ma_publikacje=nie")
    d.wait_for_load_state("networkidle")
    d.locator("#result_list tbody input.action-select").first.check()
    d.select_option("select[name=action]", "usun_zrodla_bez_publikacji_action")
    d.mouse.move(5, 5)
    mark(
        d,
        [
            {
                "sel": "#filter-panel-toggle",
                "arrow": "below",
                "label": "1. Filtruj: „nie ma publikacji”",
                "dx": -420,
                "dy": -20,
            },
            {
                "sel": "#result_list tbody input.action-select",
                "arrow": "below",
                "label": "2. zaznacz",
                "dx": 20,
                "dy": -20,
            },
            {
                "sel": "select[name=action]",
                "arrow": "above",
                "label": "3. akcja i „Wykonaj”",
                "dx": 0,
                "dy": 20,
            },
        ],
    )
    d.screenshot(path=out / "18-zrodla-bez-publikacji.png")
    d.context.close()


def metryki_ewaluacyjne(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/metryki-ewaluacyjne.md: evaluation metrics of authors (editor).

    Needs a Celery worker: "Uruchom generowanie" recomputes N and the metrics
    in the background. The scenario starts a real recompute."""
    m = new_session(page, base, DEMO_USER_REDAKTOR)
    lista = f"{base}/ewaluacja_metryki/"

    # 1. "ewaluacja" menu -> metryki ewaluacyjne
    li = open_top_menu(m, "fi-graph-bar")
    mark(
        m,
        [
            {
                "sel": f"{li} a[href$='/ewaluacja_metryki/']",
                "arrow": "right",
                "label": "metryki ewaluacyjne",
                "dx": 40,
                "dy": -20,
            }
        ],
    )
    shot(
        m,
        out / "01-menu-ewaluacja.png",
        0,
        bottom_of(m, f"{li} .menu-columns-wrapper"),
    )

    # 2. Disclaimer (shown until closed) + status box with "Uruchom generowanie"
    m.goto(lista)
    m.wait_for_load_state("networkidle")
    m.wait_for_timeout(500)  # disclaimer fades in
    if m.locator("#ewaluacja-disclaimer").is_visible():
        mark(
            m,
            [
                {
                    "sel": "#ewaluacja-disclaimer .close-button",
                    "arrow": "above",
                    "label": "zamknij (wróci po 14 dniach)",
                    "dx": -560,
                    "dy": -120,
                }
            ],
        )
        shot(
            m,
            out / "02-zastrzezenie.png",
            0,
            bottom_of(m, "#ewaluacja-disclaimer", 20),
        )
        m.locator("[data-action=close-disclaimer]").click()
        m.wait_for_timeout(600)
    m.mouse.move(5, 5)
    mark(
        m,
        [
            {
                "sel": "#status-box button[data-open=generowanie-modal]",
                "arrow": "left",
                "label": "uruchom generowanie",
                "dx": -60,
                "dy": -40,
            },
        ],
    )
    shot(m, out / "03-status-uruchom.png", 0, bottom_of(m, "#status-box", 20))

    # 3. The dialog: period, threshold, author types. Taller window, or the
    # dialog's heading hides under the top bar.
    m.evaluate("document.getElementById('kb-overlay')?.remove()")
    m.set_viewport_size({"width": VIEWPORT["width"], "height": 1060})
    m.click("#status-box button[data-open=generowanie-modal]")
    m.wait_for_selector("#generowanie-modal", state="visible")
    m.wait_for_timeout(800)  # reveal animation
    box = m.locator("#generowanie-modal").bounding_box()
    m.screenshot(
        path=out / "04-okno-generowania.png",
        clip={
            "x": box["x"] - 20,
            "y": max(0, box["y"] - 20),
            "width": box["width"] + 40,
            "height": box["height"] + 40,
        },
    )

    # 4. Submit, catch the progress box, wait until done
    m.click("#generowanie-form button[type=submit]")
    m.wait_for_selector("#status-box.warning", timeout=10000)
    m.wait_for_timeout(1000)
    m.set_viewport_size(VIEWPORT)
    m.mouse.move(5, 5)
    sb = page_box(m, "#status-box")
    shot(m, out / "05-postep.png", sb["y"] - 8, sb["height"] + 28)
    for _ in range(150):
        m.wait_for_timeout(2000)
        m.goto(lista)
        m.wait_for_load_state("networkidle")
        if m.locator("#status-box.success").count():
            break
    m.wait_for_timeout(1500)  # circular progress animates

    # 5. Filters, export and statistics buttons
    m.mouse.move(5, 5)
    mark(
        m,
        [
            {"sel": "#filter-form"},
            {
                "sel": "#filter-form a[href*='export-lista-xlsx']",
                "arrow": "above",
                "label": "Excel z filtrami",
                "dx": -420,
                "dy": 95,
            },
        ],
    )
    fb = page_box(m, "#status-box")
    shot(
        m,
        out / "06-filtry.png",
        fb["y"] - 10,
        bottom_of(m, "#filter-form", 20) - fb["y"],
    )

    # 6. Summary + the table
    m.evaluate("document.getElementById('kb-overlay')?.remove()")
    th = "table.hover thead th"
    mark(
        m,
        [
            {
                "sel": th,
                "text": "Średnia PKDaut/slot",
                "arrow": "above",
                "label": "punkty na slot",
                "dx": -420,
                "dy": 30,
            },
            {
                "sel": th,
                "text": "Wykorzystanie slotów",
                "arrow": "above",
                "label": "zebrane / dostępne sloty",
                "dx": -200,
                "dy": 30,
            },
            {"sel": "table.hover tbody tr:first-child td:last-child"},
        ],
    )
    st = page_box(m, ".callout.secondary")
    shot(
        m,
        out / "07-tabela.png",
        st["y"] - 10,
        bottom_of(m, "table.hover tbody tr:nth-child(3)") - st["y"],
    )

    # 7. Detail page of one author/discipline
    m.goto(f"{lista}?nazwisko=Yennefer")
    m.wait_for_load_state("networkidle")
    m.locator("table.hover tbody tr:first-child td:first-child a").click()
    m.wait_for_load_state("networkidle")
    m.wait_for_timeout(1500)  # charts and progress circle animate
    mark(
        m,
        [
            {
                "sel": "th",
                "text": "Slot maksymalny",
                "arrow": "above",
                "label": "limit slotów autora",
                "dx": -183,
                "dy": 90,
            }
        ],
    )
    h = page_box(m, "h4", "Informacje podstawowe")
    shot(m, out / "08-szczegoly.png", 0, h["y"] + 420)

    # 8. Collected works with the "Odepnij" button, far down the page
    m.evaluate("document.getElementById('kb-overlay')?.remove()")
    m.mouse.move(5, 5)
    top = shot(m, None, 0, 330)
    mark(
        m,
        [
            {"sel": "h4", "text": "Szczegóły prac nazbieranych"},
            {
                "sel": "button[title='Odepnij dyscyplinę']",
                "arrow": "left",
                "label": "odepnij",
                "dx": -260,
                "dy": 30,
            },
        ],
    )
    h = page_box(m, "h4", "Szczegóły prac nazbieranych")
    bottom = shot(m, None, h["y"] - 20, 330)
    stitch(
        m,
        [top, bottom],
        out / "09-prace-nazbierane.png",
        "przewiń do sekcji „Szczegóły prac nazbieranych”",
    )

    # 9. Statistics page
    m.goto(f"{base}/ewaluacja_metryki/statystyki/")
    m.wait_for_load_state("networkidle")
    m.wait_for_timeout(1000)
    mark(
        m,
        [
            {
                "sel": "a[href$='export-xlsx/top-autorzy/']",
                "arrow": "left",
                "label": "każda tabela do Excela",
                "dx": -60,
                "dy": -40,
            }
        ],
    )
    h = page_box(m, "h4", "Top 20 autorów PKDaut/slot")
    shot(m, out / "10-statystyki.png", 0, h["y"] + 330)
    m.context.close()


def liczba_n_faq(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/liczba-n-faq.md: where to check why BPP's N differs from SEDN/POL-on.

    Needs the demo state from bin/docs-demo-liczba-n-faq.py (part-time
    contracts, a two-discipline split, a doctoral student, missing data).
    """
    red = new_session(page, base, DEMO_USER_REDAKTOR)

    # 1. the N table: average vs end of 2025, non-reported disciplines
    red.goto(f"{base}/ewaluacja_liczba_n/")
    red.wait_for_load_state("networkidle")
    red.click("#obliczLiczbeNButton")
    red.wait_for_load_state("networkidle")
    red.wait_for_selector("#sankcjeForm")
    mark(
        red,
        [
            {
                "sel": "#sankcjeForm th",
                "text": "Liczba N - średnia",
                "arrow": "above",
                "label": "średnia z 4 lat",
                "dx": 40,
                "dy": 75,
            },
            {
                "sel": "#sankcjeForm th",
                "text": "Liczba N - koniec 2025",
                "arrow": "above",
                "label": "sam rok 2025",
                "dx": -300,
                "dy": 75,
            },
            {"sel": "h3", "text": "Dyscypliny nieraportowane"},
        ],
    )
    h = page_box(red, "h3", "Liczba N dla poszczególnych dyscyplin")
    nier = page_box(red, ".callout.alert")
    shot(
        red,
        out / "01-tabela-liczby-n.png",
        h["y"] - 20,
        nier["y"] + nier["height"] + 30 - (h["y"] - 20),
    )

    # 2. one year, one discipline, only "N": the number to compare with SEDN
    red.goto(f"{base}/ewaluacja_liczba_n/autorzy/")
    red.wait_for_load_state("networkidle")
    red.select_option("select[name=rok]", "2024")
    red.wait_for_load_state("networkidle")
    for name, text in (
        ("rodzaj_autora", "pracownik naukowy w liczbie N"),
        ("dyscyplina", "biotechnologia"),
    ):
        opt = red.locator(f"select[name={name}] option", has_text=text).first
        red.select_option(f"select[name={name}]", opt.get_attribute("value"))
        red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": "select[name=rok]"},
            {"sel": "select[name=rodzaj_autora]"},
            {"sel": "select[name=dyscyplina]"},
            {
                "sel": ".callout.primary .label.success",
                "arrow": "right",
                "label": "liczba N za 2024",
                "dx": 40,
                "dy": 10,
            },
        ],
    )
    tab = page_box(red, "#pager tbody tr:nth-child(4)")
    shot(red, out / "02-udzialy-za-rok.png", 0, tab["y"] + tab["height"] + 10)

    # 3. the author's disciplines: type, contract, percent
    red.goto(f"{base}/admin/bpp/autor/160/change/")
    red.wait_for_load_state("networkidle")
    grp = "#autor_dyscyplina_set-group"
    mark(
        red,
        [
            {
                "sel": f"{grp} .grp-th.rodzaj-autora",
                "arrow": "above",
                "label": "N, D, B, Z",
                "dx": -100,
                "dy": 20,
            },
            {
                "sel": f"{grp} .grp-th.wymiar-etatu",
                "arrow": "above",
                "label": "etat",
                "dx": 0,
                "dy": 20,
            },
            {
                "sel": f"{grp} .grp-th.procent-dyscypliny",
                "arrow": "above",
                "label": "75% przy jednej dyscyplinie",
                "dx": -330,
                "dy": 20,
            },
        ],
    )
    top = shot(red, None, 0, 300)
    g = page_box(red, grp)
    bottom = shot(red, None, g["y"] - 130, g["height"] + 150)
    stitch(
        red,
        [top, bottom],
        out / "03-dyscypliny-autora.png",
        "przewiń do „Powiązania autor-dyscyplina”",
    )

    # 4. a person with data only for 2024-2025
    # the search box takes one word (surname OR first name); the discipline
    # filter narrows it down to the one person
    red.goto(f"{base}/ewaluacja_liczba_n/autorzy/?search=Regis")
    red.wait_for_load_state("networkidle")
    opt = red.locator("select[name=dyscyplina] option", has_text="biotechnologia")
    red.select_option("select[name=dyscyplina]", opt.first.get_attribute("value"))
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": "input[name=search]"},
            {"sel": "select[name=dyscyplina]"},
            {"sel": "#pager tbody tr:nth-child(1) td:nth-child(2)"},
        ],
    )
    tab = page_box(red, "#pager")
    h1 = page_box(red, "h1")
    shot(
        red,
        out / "04-osoba-od-2024.png",
        h1["y"] - 20,
        tab["y"] + tab["height"] + 20 - (h1["y"] - 20),
    )

    # 5. "Weryfikuj poprawność bazy": author types, missing contract size
    red.goto(f"{base}/ewaluacja_liczba_n/weryfikuj-baze/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": "td", "text": "doktorant"},
            {"sel": "td", "text": "brak danych"},
            {
                "sel": "button",
                "text": "Ustaw wymiar etatu 1.0 wszystkim",
                "arrow": "left",
                "label": "uwaga: zawsze 1,0",
                "dx": -20,
                "dy": -10,
            },
        ],
    )
    h1 = page_box(red, "h1")
    s2 = page_box(red, "h3", "2. Autor_Dyscyplina bez informacji")
    shot(
        red, out / "05-weryfikuj-baze.png", h1["y"] - 20, s2["y"] + 230 - (h1["y"] - 20)
    )
    red.context.close()


def plik_wykazu_demo(path: Path) -> Path:
    """Write the made-up ministerial-list XLSX used by the import-list-ministerialnych scenario."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    naglowek = [
        "Lp.",
        "Unikatowy Identyfikator Czasopisma",
        "Tytuł 1",
        "issn",
        "e-issn",
    ]
    naglowek += ["Tytuł 2", "issn", "e-issn", "Punktacja"]
    ws.append(naglowek + [nazwa for _, nazwa in WYKAZ_DEMO_DYSCYPLINY])
    ws.append(naglowek + [kod for kod, _ in WYKAZ_DEMO_DYSCYPLINY])
    for lp, (ident, tytul, issn, punkty, dyscypliny) in enumerate(
        WYKAZ_DEMO_WIERSZE, 1
    ):
        x = [
            "x" if n in dyscypliny.split(", ") else None
            for _, n in WYKAZ_DEMO_DYSCYPLINY
        ]
        ws.append([lp, ident, tytul, issn, None, None, None, None, punkty] + x)
    wb.save(path)
    return path


def import_list_ministerialnych(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/import-list-ministerialnych.md: ministerial journal list import (preview, save, errors); run bin/docs-demo-import-list-ministerialnych.py first."""
    import tempfile

    red = new_session(page, base, DEMO_USER_REDAKTOR)
    rok = WYKAZ_DEMO_ROK
    tmp = Path(tempfile.mkdtemp())
    plik = plik_wykazu_demo(tmp / f"wykaz-czasopism-{rok}.xlsx")

    # 1. "operacje" menu
    li = open_top_menu(red, "fi-wrench")
    mark(
        red,
        [
            {"sel": f"{li} .column-1 a", "text": "import list"},
        ],
    )
    menu = page_box(red, f"{li} .menu-columns-wrapper")
    shot(red, out / "01-menu-operacje.png", 0, menu["y"] + menu["height"] + 30)

    # 2. the form: preview run, unmatched journals listed too
    def formularz(zapisz: bool, ignoruj: bool) -> None:
        red.goto(f"{base}/import_list_ministerialnych/nowy/")
        red.wait_for_load_state("networkidle")
        red.fill("input[name=rok]", str(rok))
        red.set_checked("#id_ignoruj_zrodla_bez_odpowiednika", ignoruj)
        red.set_checked("#id_zapisz_zmiany_do_bazy", zapisz)
        red.set_input_files("input[name=plik]", str(plik))

    formularz(zapisz=False, ignoruj=False)
    mark(
        red,
        [
            {
                "sel": "#id_rok",
                "arrow": "below",
                "label": "1. rok wykazu",
                "dx": 400,
                "dy": -80,
            },
            {
                "sel": "label[for=id_ignoruj_zrodla_bez_odpowiednika]",
                "arrow": "right",
                "label": "2. odznacz: pokaż też czasopisma spoza BPP",
                "dx": 60,
                "dy": -40,
            },
            {
                "sel": "label[for=id_zapisz_zmiany_do_bazy]",
                "arrow": "right",
                "label": "3. bez zaznaczenia = tylko podgląd",
                "dx": 60,
                "dy": -40,
            },
            {
                "sel": "input[name=plik]",
                "arrow": "below",
                "label": "4. plik XLSX z wykazem",
                "dx": 250,
                "dy": -60,
            },
            {
                "sel": "#id_submit",
                "arrow": "right",
                "label": "5. Przeprowadź import",
                "dx": 20,
            },
        ],
    )
    shot(
        red,
        out / "02-formularz-podglad.png",
        100,
        bottom_of(red, "#id_submit", 40) - 100,
    )

    # 3. live page: finished
    red.click("#id_submit")
    red.wait_for_selector("text=Import zakończony", timeout=60000)
    red.reload()  # drop the stale "Operacja w toku…" status line
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "#op-result a.button",
                "arrow": "right",
                "label": "pełne wyniki",
                "dx": 20,
            }
        ],
    )
    wynik = page_box(red, "#op-result")
    shot(red, out / "03-import-zakonczony.png", 0, wynik["y"] + wynik["height"] + 30)

    # 4. preview results: warning, statistics, filters, table
    red.click("#op-result a.button")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": ".panel.callout.warning"},
            {
                "sel": "#filter-form .button-group",
                "arrow": "below",
                "label": "filtry",
                "dx": 120,
                "dy": -50,
            },
            {"sel": "tbody tr", "text": "Brak takiego źródła"},
            {"sel": "tbody tr.duplicate-row"},
        ],
    )
    shot(red, out / "04-wyniki-podgladu.png", 0, bottom_of(red, "table", 30))

    # 5. one row in detail
    red.click("tbody tr >> nth=0 >> a")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": ".panel tr", "text": "Rezultat importu"},
        ],
    )
    box = page_box(red, ".panel", "Informacje o wierszu")
    shot(red, out / "05-szczegoly-wiersza.png", 0, box["y"] + box["height"] + 30)

    # 6. the real run: same file, "Zapisz zmiany do bazy" ticked
    formularz(zapisz=True, ignoruj=True)
    mark(
        red,
        [
            {
                "sel": "label[for=id_zapisz_zmiany_do_bazy]",
                "arrow": "right",
                "label": "teraz zaznacz: zapisz",
                "dx": 60,
                "dy": -10,
            },
        ],
    )
    red.click("#id_submit")
    red.wait_for_selector("text=Import zakończony", timeout=60000)
    red.click("#op-result a.button")
    red.wait_for_load_state("networkidle")
    mark(red, [{"sel": ".panel.callout.success"}])
    shot(red, out / "06-zapisano.png", 0, bottom_of(red, "table", 30))

    # 7. where the values live: the source's points and disciplines
    red.goto(f"{base}/admin/bpp/zrodlo/37/change/")  # Acta Wiedźmińska
    red.wait_for_load_state("networkidle")
    top = shot(red, None, 0, 300)
    mark(
        red,
        [
            {"sel": "#id_punktacja_zrodla_set-0-rok"},
            {"sel": "#id_punktacja_zrodla_set-0-punkty_kbn"},
        ],
    )
    box = page_box(red, "#punktacja_zrodla_set-group")
    srodek = shot(red, None, box["y"] - 20, box["height"] + 40)
    red.click("#dyscyplina_zrodla_set-group > h2")  # the inline starts collapsed
    red.wait_for_timeout(500)
    mark(
        red,
        [
            {"sel": "#dyscyplina_zrodla_set-group .grp-table"},
        ],
    )
    box = page_box(red, "#dyscyplina_zrodla_set-group")
    dol = shot(red, None, box["y"] - 20, box["height"] + 40)
    stitch(
        red,
        [top, srodek, dol],
        out / "07-zrodlo-punktacja-dyscypliny.png",
        "przewiń w dół",
    )

    # 8. points to records: rozbieżności, "Punkty MNiSW" tab
    red.goto(f"{base}/rozbieznosci/mnisw/?rok_od={rok}&rok_do={rok}")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": ".tabs .is-active, .tabs .active, .tabs li",
                "text": "Punkty MNiSW",
            },
            {
                "sel": "button",
                "text": "Ustaw wszystkie wg źródła",
                "arrow": "left",
                "label": "przenieś punkty na prace",
                "dx": -10,
                "dy": -40,
            },
        ],
    )
    shot(red, out / "08-rozbieznosci-mnisw.png", 0, bottom_of(red, "tbody tr", 20))

    # 9. wrong file type: form error
    red.goto(f"{base}/import_list_ministerialnych/nowy/")
    red.wait_for_load_state("networkidle")
    zly = tmp / f"wykaz-czasopism-{rok}.csv"
    zly.write_text("Lp.;Tytuł 1;issn\n1;Acta Wiedźmińska;6746-8071\n", encoding="utf-8")
    red.fill("input[name=rok]", str(rok))
    red.set_input_files("input[name=plik]", str(zly))
    red.click("#id_submit")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "#error_1_id_plik, .error, small.error",
                "text": "Niewłaściwy format",
            }
        ],
    )
    shot(red, out / "09-blad-formatu.png", 100, bottom_of(red, "#id_submit", 40) - 100)

    # 10. an Excel file with other columns (e.g. a JCR export): import fails
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(
        ["Journal name", "ISSN", "eISSN", "Category", f"{rok} JIF", "JIF Quartile"]
    )
    ws.append(["Acta Wiedźmińska", "6746-8071", "N/A", "ZOOLOGY", "2.417", "Q2"])
    ws.append(["Folia Temerska", "7109-3248", "N/A", "HISTORY", "1.032", "Q3"])
    jcr = tmp / f"jcr-{rok}.xlsx"
    wb.save(jcr)
    red.goto(f"{base}/import_list_ministerialnych/nowy/")
    red.wait_for_load_state("networkidle")
    red.fill("input[name=rok]", str(rok))
    red.set_input_files("input[name=plik]", str(jcr))
    red.click("#id_submit")
    red.wait_for_selector("text=Wystąpił błąd", timeout=60000)
    red.reload()  # the page as you find it later: "Ponów" instead of "Anuluj"
    red.wait_for_load_state("networkidle")
    mark(red, [{"sel": "#op-result .error"}])
    shot(red, out / "10-blad-importu.png", 0, 300)
    red.context.close()


def rozbieznosci_dyscyplin(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/rozbieznosci-dyscyplin.md: discipline discrepancies (authors, sources).

    Needs bin/docs-demo-rozbieznosci-dyscyplin.py (re-run it before each run:
    the scenario fixes three records and the script puts them back).
    """
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    lista = f"{base}{LISTA_ROZBIEZNOSCI}"

    # 1. operacje menu: both discrepancy reports
    red.goto(f"{base}/")
    red.wait_for_load_state("networkidle")
    li = open_top_menu(red, "fi-wrench")
    mark(
        red,
        [
            {"sel": f"{li} a[href*='rozbieznosciview'] i"},
            {"sel": f"{li} a[href*='rozbieznoscizrodelview'] i"},
        ],
    )
    menu = page_box(red, f"{li} > .menu-columns-wrapper")
    shot(red, out / "01-menu-operacje.png", 0, menu["y"] + menu["height"] + 30)

    # 2. the list as opened from the menu: columns and the ready-made query
    red.goto(f"{lista}?q-l=on&q=rok%3E%3D2022&pracuje_na_uczelni=tak")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "#result_list thead th.column-dyscyplina_rekordu",
                "arrow": "below",
                "label": "dyscyplina przy autorze w pracy",
                "dx": -560,
                "dy": 40,
            },
            {
                "sel": "#result_list thead th.column-dyscyplina_autora",
                "arrow": "below",
                "label": "dyscypliny autora w tym roku",
                "dx": -420,
                "dy": 150,
            },
            {"sel": "#result_list thead th.column-subdyscyplina_autora"},
            {"sel": "#grp-changelist-search-form"},
        ],
    )
    shot(red, out / "02-lista.png", 0, 520)

    # 3. the filter panel: "Dyscyplina rekordu ustawiona" opened
    red.goto(f"{lista}?rok=2024")
    red.wait_for_load_state("networkidle")
    red.click("#filter-panel-toggle")
    red.wait_for_timeout(800)
    tytul = ".filter-title"
    red.locator(tytul, has_text="Dyscyplina rekordu ustawiona").click()
    red.wait_for_timeout(800)
    mark(
        red,
        [
            {"sel": ".filter-group", "text": "Dyscyplina rekordu ustawiona"},
            {"sel": ".filter-group", "text": "Autor pracuje na uczelni"},
            {"sel": ".filter-group", "text": "rok"},
        ],
    )
    red.screenshot(path=out / "03-filtry.png")

    # 4. one discrepancy: buttons to the record and the author
    red.goto(f"{lista}?rok=2024&dyscyplina_rekordu_id=jest&q=Regis")
    red.wait_for_load_state("networkidle")
    red.locator("#result_list tbody tr a").first.click()
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": ".grp-object-tools",
                "arrow": "below",
                "label": "otwórz pracę lub autora",
                "dx": -330,
                "dy": 40,
            }
        ],
    )
    shot(red, out / "04-szczegoly.png", 0, 470)

    # 5. fix a few: tick the rows, pick the action, run
    red.goto(f"{lista}?rok=2024&dyscyplina_rekordu_id=jest&q=Regis")
    red.wait_for_load_state("networkidle")
    for box in red.locator("#result_list tbody input.action-select").all():
        box.check()
    red.select_option("select[name=action]", "ustaw_druga")
    red.mouse.move(5, 5)
    akcja = ".grp-changelist-actions button, button[name=index]"
    pierwszy = "#result_list tbody tr:first-child"
    mark(
        red,
        [
            {
                "sel": "#action-toggle",
                "arrow": "above",
                "label": "1. zaznacz (tu: wszystkie)",
                "dx": 180,
                "dy": 10,
            },
            {"sel": f"{pierwszy} td.field-dyscyplina_rekordu"},
            {"sel": f"{pierwszy} td.field-subdyscyplina_autora"},
            {
                "sel": "select[name=action]",
                "arrow": "above",
                "label": "2. akcja",
                "dx": 40,
                "dy": 20,
            },
            {
                "sel": akcja,
                "arrow": "above",
                "label": "3. Wykonaj",
                "dx": 60,
                "dy": 20,
            },
        ],
    )
    red.screenshot(path=out / "05-akcja.png")

    # 6. the result messages
    red.click(akcja)
    red.wait_for_load_state("networkidle")
    msgs = ".grp-messagelist"
    mark(red, [{"sel": msgs}])
    shot(red, out / "06-komunikaty.png", 0, bottom_of(red, msgs, 120))

    # 7. "second discipline" for an author who has only one: a warning
    red.goto(
        f"{lista}?rok=2024&dyscyplina_rekordu_id=brak&subdyscyplina_autora__isnull=True"
    )
    red.wait_for_load_state("networkidle")
    red.locator("#result_list tbody input.action-select").first.check()
    red.select_option("select[name=action]", "ustaw_druga")
    red.click(akcja)
    red.wait_for_load_state("networkidle")
    mark(red, [{"sel": f"{msgs} li", "text": "nie ustawiono"}])
    shot(red, out / "07-ostrzezenie.png", 0, bottom_of(red, msgs, 120))

    # 8. all rows of the filtered list: "Wybierz wszystkie..." (not run)
    red.goto(f"{lista}?rok=2024")
    red.wait_for_load_state("networkidle")
    red.locator("#action-toggle").check()
    red.wait_for_timeout(500)
    red.mouse.move(5, 5)
    mark(
        red,
        [
            {"sel": "#action-toggle"},
            {
                "sel": ".grp-question a",
                "arrow": "above",
                "label": "cała lista po filtrach",
                "dx": -40,
                "dy": 20,
            },
        ],
    )
    red.screenshot(path=out / "08-zaznacz-wszystkie.png")

    # 9. sources: work discipline outside the journal's disciplines
    red.goto(
        f"{base}/admin/rozbieznosci_dyscyplin/rozbieznoscizrodelview/"
        "?rok=2024&pracuje_na_uczelni=tak"
    )
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": "#result_list thead th.column-zrodlo"},
            {"sel": "#result_list thead th.column-dyscyplina_naukowa"},
        ],
    )
    shot(red, out / "09-zrodla.png", 0, 520)
    red.context.close()


def oswiadczenia(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/oswiadczenia.md: statements on a record, printing them, sending them to PBN.

    Needs the demo state: uv run python src/manage.py shell < bin/docs-demo-oswiadczenia.py
    and a Celery worker (step 6 generates a file in the background). No PBN behind it.
    """
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    w = VIEWPORT["width"]

    # 1. the record form: discipline, "przypięta", statement date
    red.goto(f"{base}/admin/bpp/wydawnictwo_ciagle/{OSW_REKORD}/change/")
    red.wait_for_load_state("networkidle")
    f = "#id_autorzy_set-1-"
    mark(
        red,
        [
            {
                "sel": f"{f}dyscyplina_naukowa + .select2",
                "arrow": "right",
                "label": "1. dyscyplina",
                "dx": 40,
                "dy": -40,
            },
            {
                "sel": f"label[for={f[1:]}przypieta]",
                "arrow": "right",
                "label": "2. przypięta",
                "dx": 560,
                "dy": -40,
            },
            {
                "sel": f"{f}data_oswiadczenia",
                "arrow": "right",
                "label": "3. data oświadczenia",
                "dx": 60,
                "dy": -40,
            },
        ],
    )
    top = page_box(red, f"{f}autor + .select2")["y"] - 52
    shot(
        red,
        out / "01-formularz-autora.png",
        top,
        bottom_of(red, f"{f}data_oswiadczenia", 60) - top,
    )

    # 2. the record page: print icons next to "Punkty i sloty autorów"
    red.goto(f"{base}/bpp/rekord/{OSW_REKORD_SLUG}/")
    red.wait_for_load_state("networkidle")
    wiele = "a[href*='/oswiadczenia/wiele/']"
    alt = "a[href*='/oswiadczenia/pojedyncze-alternatywna/']"
    jedno = "a[href*='/oswiadczenia/pojedyncze/'][href*='/149/']"
    mark(
        red,
        [
            {
                "sel": wiele,
                "arrow": "above",
                "label": "wszystkie naraz",
                "dx": -330,
                "dy": 50,
            },
            {
                "sel": jedno,
                "arrow": "left",
                "label": "jedno oświadczenie",
                "dx": -400,
                "dy": 0,
            },
            {
                "sel": alt,
                "arrow": "below",
                "label": "druga dyscyplina",
                "dx": -100,
                "dy": -20,
            },
        ],
    )
    head = shot(red, None, 0, 260)
    y = page_box(red, wiele)["y"] - 90
    tabela = shot(red, None, y, bottom_of(red, alt, 170) - y)
    stitch(red, [head, tabela], out / "02-strona-rekordu.png", "przewiń na dół strony")

    # 3. one statement, ready to print
    href = red.get_attribute(jedno, "href")
    druk = red.context.new_page()
    druk.goto(f"{base}{href}")
    druk.wait_for_load_state("load")
    druk.wait_for_timeout(500)
    druk.screenshot(
        path=out / "03-oswiadczenie.png",
        clip={"x": 0, "y": 0, "width": w, "height": 560},
    )
    druk.close()

    # 4. menu "ewaluacja" -> "wydruk oświadczeń 2022-25"
    red.goto(f"{base}/")
    red.wait_for_load_state("networkidle")
    li = open_top_menu(red, "fi-graph-bar")
    mark(
        red,
        [
            {
                "sel": f"{li} .column-1 a",
                "text": "wydruk oświadczeń",
                "arrow": "right",
                "label": "wydruk oświadczeń",
                "dx": 0,
                "dy": -20,
            }
        ],
    )
    menu = page_box(red, f"{li} > .menu-columns-wrapper")
    shot(red, out / "04-menu-wydruk.png", 0, menu["y"] + menu["height"] + 40)

    # 5. the list: filter, then download or print
    red.goto(f"{base}/oswiadczenia/wydruk-2022-25/")
    red.wait_for_load_state("networkidle")
    red.fill("input[name=rok_od]", "2023")
    red.fill("input[name=rok_do]", "2023")
    red.fill("input[name=szukaj_autor]", "Cintry")
    red.select_option("select[name=dyscyplina]", label="nauki teologiczne (7.2)")
    red.click("button:has-text('Filtruj')")
    red.wait_for_load_state("networkidle")
    # three rows are enough to show the columns; the label goes below them
    red.evaluate(
        "document.querySelectorAll('table tbody tr:nth-child(n+4)')"
        ".forEach(r => r.remove())"
    )
    druk_alt = "tr:nth-child(3) a.button.warning[href*='pojedyncze-alternatywna']"
    mark(
        red,
        [
            {"sel": "form.callout"},
            {
                "sel": "form.callout button[type=submit]",
                "arrow": "left",
                "label": "1. zawęź listę",
                "dx": -100,
                "dy": -10,
            },
            {
                "sel": "fieldset",
                "text": "Jeden plik",
                "arrow": "above",
                "label": "2. pobierz wszystkie",
                "dx": -600,
                "dy": 40,
            },
            {
                "sel": druk_alt,
                "arrow": "below",
                "label": "albo wydrukuj jedno",
                "dx": -380,
                "dy": -20,
            },
        ],
    )
    tabela = page_box(red, "table")
    shot(
        red, out / "05-wydruk-lista.png", 80, tabela["y"] + tabela["height"] + 140 - 80
    )

    # 6. "Jeden plik" -> PDF: generated in the background
    with red.expect_download(timeout=120_000):
        red.click("fieldset:has-text('Jeden plik') button:has-text('PDF')")
        red.wait_for_selector("#download-link", timeout=120_000)
    mark(
        red,
        [
            {
                "sel": "#download-link",
                "arrow": "right",
                "label": "jeśli nie pobrało się samo",
                "dx": 20,
                "dy": -40,
            }
        ],
    )
    shot(red, out / "06-generowanie.png", 80, bottom_of(red, "#download-link", 90) - 80)

    # 7. menu "PBN" -> "wysylka oswiadczen do PBN"
    red.goto(f"{base}/")
    red.wait_for_load_state("networkidle")
    li = open_top_menu(red, "fi-link")
    mark(
        red,
        [
            {
                "sel": f"{li} .column-1 a",
                "text": "wysylka oswiadczen",
                "arrow": "left",
                "label": "wysyłka oświadczeń",
                "dx": 0,
                "dy": 0,
            },
            {
                "sel": f"{li} .column-1 a",
                "text": "autoryzuj PBN API",
                "arrow": "left",
                "label": "najpierw: logowanie w PBN",
                "dx": 0,
                "dy": -30,
            },
        ],
    )
    menu = page_box(red, f"{li} > .menu-columns-wrapper")
    shot(red, out / "07-menu-pbn.png", 0, menu["y"] + menu["height"] + 60)

    # 8. the sending page: range, counts, last task
    red.goto(f"{base}/pbn-wysylka-oswiadczen/")
    red.wait_for_load_state("networkidle")
    start = "#start-fresh-btn"
    mark(
        red,
        [
            {"sel": "#filter-form"},
            {
                "sel": "#rok_od",
                "arrow": "above",
                "label": "1. zakres",
                "dx": 160,
                "dy": 40,
            },
            {
                "sel": start,
                "arrow": "below",
                "label": "2. wyślij",
                "dx": 300,
                "dy": -40,
            },
            {
                "sel": "#task-status-panel",
                "arrow": "below",
                "label": "ostatnie zadanie",
                "dx": 0,
                "dy": -40,
            },
        ],
    )
    shot(red, out / "08-wysylka.png", 80, bottom_of(red, start, 120) - 80)

    # 9. without a PBN login the task does not start
    red.evaluate("document.getElementById('kb-overlay')?.remove()")
    red.click(start)
    red.wait_for_selector("#start-error", state="visible")
    mark(
        red,
        [
            {
                "sel": "#start-error",
                "arrow": "right",
                "label": "brak logowania w PBN",
                "dx": 0,
                "dy": -40,
            }
        ],
    )
    y = page_box(red, "#start-error")["y"] - 260
    shot(red, out / "09-brak-logowania-pbn.png", y, bottom_of(red, start, 120) - y)

    # 10. "Tylko odpięte": the preview with the unpinned work
    red.check("input[name=tylko_odpiete]")
    red.click("#filter-form button[type=submit]")
    red.wait_for_load_state("networkidle")
    red.wait_for_selector("#publication-list table")
    mark(
        red,
        [
            {
                "sel": "#filter-form label:has(input[name=tylko_odpiete])",
                "arrow": "below",
                "label": "1. tylko odpięte",
                "dx": 50,
                "dy": -50,
            },
            {
                "sel": "#publication-list tbody tr td:nth-child(7)",
                "arrow": "below",
                "label": "2. 0 przypiętych",
                "dx": -330,
                "dy": -30,
            },
        ],
    )
    y = page_box(red, "#filter-form")["y"] - 60
    shot(
        red,
        out / "10-tylko-odpiete.png",
        y,
        bottom_of(red, "#publication-list table", 120) - y,
    )

    # 11. the log of the last task: errors only
    red.goto(f"{base}/pbn-wysylka-oswiadczen/")
    red.wait_for_load_state("networkidle")
    red.click("a:has-text('Zobacz błędy')")
    red.wait_for_load_state("networkidle")
    szczeg = "a:has-text('Szczegoly')"
    mark(
        red,
        [
            {"sel": "form.inline-form"},
            {
                "sel": "table.stack tbody tr:last-child a.button",
                "arrow": "below",
                "label": "co poszło nie tak",
                "dx": -400,
                "dy": -20,
            },
        ],
    )
    shot(red, out / "11-logi.png", 80, bottom_of(red, "table.stack", 110) - 80)

    # 12. one log entry: error, what was sent, what PBN answered
    red.locator(szczeg).first.click()
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": ".panel.callout.alert",
                "arrow": "below",
                "label": "komunikat błędu",
                "dx": 40,
                "dy": -20,
            },
            {
                "sel": ".panel pre",
                "text": "'message'",
                "arrow": "above",
                "label": "odpowiedź PBN",
                "dx": 300,
                "dy": 80,
            },
        ],
    )
    odp = page_box(red, ".panel", "Odpowiedz z PBN")
    shot(red, out / "12-log-szczegoly.png", 80, odp["y"] + odp["height"] - 40)
    red.context.close()


def optymalizacja_ewaluacji(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/optymalizacja-ewaluacji.md: choosing works for the evaluation slots.

    Needs run-site WITH celery, the "vesemir" editor, and liczba N plus author
    metrics computed on the demo DB (`manage.py oblicz_metryki`). The scenario
    really runs "Policz całą ewaluację" and "Optymalizuj, odpinając sloty";
    the latter unpins works, so restore the dump before running it again.
    """
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    red.on("dialog", lambda d: d.accept())  # the buttons' "Czy na pewno…?" prompts
    idx = f"{base}/ewaluacja_optymalizacja/"

    def czekaj_na_przyciski() -> None:
        # buttons unlock once the "points recalculation" poll reports 0 dirty records
        red.wait_for_selector("#bulk-optimization-btn:not([disabled])", timeout=120_000)
        red.wait_for_timeout(500)

    # 1. ewaluacja menu -> optymalizacja ewaluacji
    red.goto(f"{base}/")
    red.wait_for_load_state("networkidle")
    li = open_top_menu(red, "fi-graph-bar")
    mark(
        red,
        [
            {
                "sel": f"{li} a[href$='/ewaluacja_optymalizacja/']",
                "arrow": "right",
                "label": "optymalizacja ewaluacji",
                "dx": 40,
            }
        ],
    )
    menu = page_box(red, f"{li} > .menu-columns-wrapper")
    shot(red, out / "01-menu-ewaluacja.png", 0, menu["y"] + menu["height"] + 40)

    # 2. main page: N-number check, solver mode, the start button
    red.goto(idx)
    red.wait_for_load_state("networkidle")
    czekaj_na_przyciski()
    mark(
        red,
        [
            {"sel": ".callout h4", "text": "Gotowe do optymalizacji"},
            {
                "sel": "label[for=algo-two-phase]",
                "arrow": "right",
                "label": "1. zostaw „Dwufazowy”",
                "dx": 120,
                "dy": 10,
            },
            {
                "sel": "#bulk-optimization-btn",
                "arrow": "below",
                "label": "2. Policz całą ewaluację",
                "dx": 40,
                "dy": -50,
            },
        ],
    )
    shot(
        red,
        out / "02-strona-glowna.png",
        0,
        bottom_of(red, "#bulk-optimization-form", 30),
    )

    # 3. the status page while the background task runs
    red.click("#bulk-optimization-btn")
    red.wait_for_url("**/bulk/status/**")
    red.wait_for_load_state("domcontentloaded")
    mark(
        red,
        [
            {
                "sel": "button",
                "text": "Anuluj zadanie",
                "arrow": "below",
                "label": "przerwanie obliczeń",
                "dx": 60,
                "dy": -40,
            }
        ],
    )
    shot(
        red,
        out / "03-status.png",
        0,
        bottom_of(red, "button.alert, .button.alert", 110),
    )

    # 4. back on the main page: one row per discipline
    red.wait_for_url(idx, timeout=600_000)
    red.wait_for_load_state("networkidle")
    czekaj_na_przyciski()
    tabela = page_box(red, "table")
    mark(
        red,
        [
            {"sel": "th", "text": "3N ost."},
            {"sel": "th", "text": "Sloty %"},
            {
                "sel": "tbody tr",
                "text": "filozofia",
            },
        ],
    )
    top = shot(red, None, 0, 200)
    bottom = shot(red, None, tabela["y"] - 60, tabela["height"] + 150)
    stitch(
        red,
        [top, bottom],
        out / "04-wyniki-lista.png",
        "przewiń do „Ostatnie kalkulacje”",
    )

    # 5. one discipline: totals, then the per-author table
    red.locator("tbody tr", has_text="filozofia").get_by_text(
        "Zobacz szczegóły"
    ).click()
    red.wait_for_load_state("networkidle")
    red.wait_for_timeout(1500)  # charts animate in
    top = shot(red, None, 0, 560)
    h = page_box(red, "h2", "Wyniki autorów")
    wiersz = page_box(red, "tbody tr:nth-child(5)")
    mark(
        red,
        [
            {"sel": "th:nth-child(4)"},
            {"sel": "th:nth-child(5)"},
            {"sel": "th:nth-child(6)"},
            {
                "sel": "a",
                "text": "Pobierz archiwum ZIP",
                "arrow": "right",
                "label": "Excel dla wszystkich autorów",
                "dx": 280,
                "dy": -70,
            },
        ],
    )
    bottom = shot(red, None, h["y"] - 20, wiersz["y"] + wiersz["height"] - h["y"] + 40)
    stitch(
        red,
        [top, bottom],
        out / "05-wyniki-dyscypliny.png",
        "przewiń do „Wyniki autorów”",
    )

    # 6. one author: works chosen and not chosen
    red.locator("tbody tr", has_text="Merigold Yennefer").locator("a").first.click()
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": ".callout", "text": "Prace nazbierane"},
            {"sel": ".callout", "text": "Sloty nazbierane"},
        ],
    )
    h = page_box(red, "h2", "Prace nazbierane")
    shot(red, out / "06-prace-autora.png", 0, h["y"] + 330)

    # 7. exports on the main page
    red.goto(idx)
    red.wait_for_load_state("networkidle")
    czekaj_na_przyciski()
    mark(
        red,
        [
            {"sel": "a", "text": "Pobierz wszystkie XLS (ZIP)"},
            {"sel": "a", "text": "Raport SEDN #1"},
            {
                "sel": "a",
                "text": "Raport SEDN #2",
                "arrow": "right",
                "label": "eksport do Excela",
                "dx": 0,
                "dy": 30,
            },
            {
                "sel": "#optimize-unpin-btn",
                "arrow": "below",
                "label": "zastosuj wynik",
                "dx": 0,
                "dy": -20,
            },
        ],
    )
    shot(red, out / "07-eksporty.png", 0, bottom_of(red, "#bulk-optimization-form", 30))

    # 8. one record: pin / unpin a discipline by hand
    red.goto(f"{base}/bpp/rekord/{REKORD_ZE_SLOTAMI}/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": ".praca-mono__optimize-button",
                "arrow": "left",
                "label": "Optymalizuj",
                "dy": -40,
            }
        ],
    )
    h = page_box(red, "h3", "Punkty i sloty autorów")
    top = shot(red, None, 0, 380)
    bottom = shot(red, None, h["y"] - 20, 360)
    stitch(
        red,
        [top, bottom],
        out / "08-rekord-optymalizuj.png",
        "przewiń do „Punkty i sloty autorów”",
    )

    red.locator(".praca-mono__optimize-button").click()
    red.wait_for_load_state("networkidle")
    red.wait_for_timeout(800)
    karta = page_box(red, ".author-card")
    mark(
        red,
        [
            {"sel": "#summary-section"},
            {
                "sel": ".ewaluacja-optymalizuj__unpin-button",
                "arrow": "right",
                "label": "odepnij / przypnij",
                "dx": 40,
                "dy": -40,
            },
        ],
    )
    shot(red, out / "09-optymalizuj-rekord.png", 0, karta["y"] + karta["height"] + 30)

    # 9. apply: unpin works that did not make it into the evaluation
    red.goto(idx)
    red.wait_for_load_state("networkidle")
    czekaj_na_przyciski()
    red.click("#optimize-unpin-btn")
    red.wait_for_url("**/optimize-unpin-status/**")
    red.wait_for_load_state("domcontentloaded")
    shot(
        red,
        out / "10-odpinanie-status.png",
        0,
        bottom_of(red, "#progress-container", 10),
    )

    # when done, back on the main page: the message and the "Odpięte" column
    red.wait_for_url(idx, timeout=600_000)
    red.wait_for_load_state("networkidle")
    czekaj_na_przyciski()
    mark(
        red,
        [
            {"sel": ".callout", "text": "Odpiętych publikacji"},
            {"sel": "th", "text": "Odpięte"},
        ],
    )
    tabela = page_box(red, "table")
    top = shot(red, None, 0, 200)
    bottom = shot(red, None, tabela["y"] - 60, tabela["height"] + 80)
    stitch(
        red,
        [top, bottom],
        out / "11-odpinanie-wynik.png",
        "przewiń do „Ostatnie kalkulacje”",
    )

    # 10. snapshots: the way back
    red.goto(f"{base}/snapshot_odpiec/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "a[href*='/aplikuj/']",
                "arrow": "below",
                "label": "przywróć stan sprzed odpinania",
                "dx": 200,
                "dy": -30,
            }
        ],
    )
    shot(red, out / "12-snapshoty.png", 0, bottom_of(red, "table", 110))
    red.context.close()


def admin_zglaszanie_publikacji(page: Page, base: str, out: Path) -> None:
    """docs/administrator/zglaszanie-publikacji.md: form visibility, login and fee options, per-faculty notifications (superuser); run bin/docs-demo-admin-zglaszanie-publikacji.py first."""
    adm = new_session(page, base, DEMO_USER_ADMIN)

    # 1. university settings, "Strona wizualna": who sees the button
    adm.goto(f"{base}/admin/bpp/uczelnia/")
    adm.wait_for_load_state("networkidle")
    adm.locator("#result_list tbody a").first.click()
    adm.wait_for_load_state("networkidle")
    wiersz = ".form-row.pokazuj_formularz_zglaszania_publikacji"
    mark(
        adm,
        [
            {
                "sel": "#id_pokazuj_formularz_zglaszania_publikacji",
                "arrow": "right",
                "label": "zawsze / tylko dla zalogowanych / nigdy",
                "dy": -40,
            }
        ],
    )
    sekcja = page_box(adm, "fieldset.grp-module > h2", "Strona wizualna")
    row = page_box(adm, wiersz)
    stitch(
        adm,
        [
            shot(adm, None, 0, 135),
            shot(adm, None, sekcja["y"] - 8, sekcja["height"] + 16),
            # a few neighbouring visibility options above, for context
            shot(adm, None, row["y"] - 470, row["height"] + 510),
        ],
        out / "01-widocznosc-przycisku.png",
        "przewiń w dół",
    )

    # 2. "Zgłaszanie publikacji": login required, fee questions per type
    mark(
        adm,
        [
            {
                "sel": "label[for=id_wymagaj_logowania_zglos_publikacje]",
                "arrow": "right",
                "label": "1. tylko zalogowani",
                "dx": 320,
                "dy": -45,
            },
            *(
                {"sel": f"label[for=id_wymagaj_oplatach_{rodzaj}]"}
                for rodzaj in ("artykul", "monografia", "rozdzial", "inne")
            ),
            {
                "sel": "label[for=id_wymagaj_oplatach_monografia]",
                "arrow": "right",
                "label": "2. pytaj o opłaty dla tych rodzajów",
                "dx": 300,
                "dy": -40,
            },
        ],
    )
    fs = page_box(adm, "fieldset.grp-module", "Wymagaj informacji o opłatach")
    shot(adm, out / "02-zglaszanie-publikacji.png", fs["y"] - 10, fs["height"] + 20)

    # 3. Administracja -> "Obsługa zgłoszeń prac - wydziały" -> add
    adm.goto(f"{base}/admin/zglos_publikacje/obslugujacy_zgloszenia_wydzialow/add/")
    adm.wait_for_load_state("networkidle")
    opcja = adm.locator("#id_user option", has_text=f"({DEMO_USER_REDAKTOR})")
    adm.select_option("#id_user", value=opcja.get_attribute("value"))
    adm.select_option("#id_wydzial", label="Wydział Magii i Eliksirów")
    mark(
        adm,
        [
            {
                "sel": "#id_user",
                "arrow": "right",
                "label": "1. kto dostaje powiadomienia",
                "dy": -40,
            },
            {
                "sel": "#id_wydzial",
                "arrow": "right",
                "label": "2. wydział razem z jednostkami podrzędnymi",
                "dx": 80,
                "dy": 0,
            },
        ],
    )
    shot(adm, out / "03-obsluga-zgloszen-wydzialy.png", 0, 290)
    adm.context.close()


def api_session(page: Page, base: str, user: str | None = None) -> Page:
    """A browser session on the browsable API at PUBLIC_BPP.

    The slot-report endpoints accept HTTP Basic auth only (no session
    cookie), so a logged-in user is passed as an Authorization header."""
    headers = {}
    if user:
        token = base64.b64encode(f"{user}:{user}".encode()).decode()
        headers["Authorization"] = f"Basic {token}"
    ctx = page.context.browser.new_context(
        viewport=VIEWPORT,
        device_scale_factor=2,
        locale="pl-PL",
        extra_http_headers=headers,
    )
    ctx.add_init_script(HIDE_HELP_LAUNCHER)
    other = ctx.new_page()
    proxy_public_bpp(other, base)
    # The dev server's live-reload stream never ends; proxying it would leave
    # a route in flight and break closing the context.
    other.route(f"{PUBLIC_BPP}/__dev_reload__/**", lambda route: route.abort())
    return other


def close_api_session(other: Page) -> None:
    other.unroute_all(behavior="ignoreErrors")
    other.context.close()


def api_index(page: Page, base: str, out: Path) -> None:
    """docs/api/index.md: the browsable /api/v1/ root and the slot report over the API."""
    # 1. anonymous visitor: the API root, with the format menu open
    anon = api_session(page, base)
    anon.goto(f"{PUBLIC_BPP}/api/v1/")
    anon.wait_for_load_state("networkidle")
    # Bootstrap opens the format menu to the right, past the page edge
    anon.evaluate(
        "document.querySelector('.format-selection .dropdown-menu')"
        ".classList.add('dropdown-menu-right')"
    )
    anon.locator(".format-selection .dropdown-toggle").first.click()
    anon.wait_for_selector(".format-selection .dropdown-menu", state="visible")
    anon.mouse.move(5, 790)  # no tooltip over the open menu
    anon.wait_for_timeout(600)
    mark(
        anon,
        [
            {
                "sel": '.response-info a[href$="/api/v1/autor/"]',
                "arrow": "right",
                "label": "1. kliknij adres, aby obejrzeć dane",
                "dx": 100,
            },
            {
                "sel": ".format-selection .dropdown-menu a[href*='format=json']",
                "arrow": "left",
                "label": "2. te same dane jako JSON",
                "dy": 40,
            },
        ],
    )
    shot(
        anon,
        out / "01-strona-glowna-api.png",
        0,
        bottom_of(anon, '.response-info a[href$="/api/v1/uczelnia/"]', 40),
    )
    close_api_session(anon)

    # 2. slot report: the form at the bottom of the list (group "generowanie raportów")
    rap = api_session(page, base, DEMO_USER_RAPORTY)
    rap.goto(f"{PUBLIC_BPP}/api/v1/raport_slotow_uczelnia/")
    rap.wait_for_load_state("networkidle")
    form = "#post-object-form"
    rap.fill(f"{form} input[name=od_roku]", "2022")
    rap.fill(f"{form} input[name=do_roku]", "2025")
    rap.fill(f"{form} input[name=slot]", "1")
    mark(
        rap,
        [
            {
                "sel": f"{form} input[name=od_roku]",
                "arrow": "below",
                "label": "1. parametry raportu",
                "dx": 150,
                "dy": 20,
            },
            {
                "sel": f"{form} button",
                "arrow": "left",
                "label": "2. utwórz raport",
                "dy": -60,
            },
        ],
    )
    title = bottom_of(rap, ".page-header")
    top = shot(rap, None, 0, title + 10)
    box = page_box(rap, ".nav-tabs")
    bottom = shot(rap, None, box["y"] - 20, bottom_of(rap, form) - box["y"] + 40)
    stitch(
        rap,
        [top, bottom],
        out / "02-formularz-raportu-slotow.png",
        "przewiń na sam dół strony",
    )

    # 3. rows of the finished report (bin/docs-demo-api-index.py made one)
    resp = rap.context.request.get(
        f"{base}/api/v1/raport_slotow_uczelnia/",
        headers={"Accept": "application/json"},
    )
    url = resp.json()["results"][0]["id"]
    raport_id = url.split("/raport_slotow_uczelnia/")[1].split("/")[0]
    rap.goto(f"{PUBLIC_BPP}/api/v1/raport_slotow_uczelnia_wiersz/?parent={raport_id}")
    rap.wait_for_load_state("networkidle")
    mark(
        rap,
        [
            {
                "sel": ".pagination",
                "arrow": "left",
                "label": "kolejne strony wyników",
                "dx": -40,
                "dy": 40,
            },
        ],
    )
    shot(rap, out / "03-wiersze-raportu.png", 0, 900)
    close_api_session(rap)


def rest_api(page: Page, base: str, out: Path) -> None:
    """docs/administrator/rest-api.md: the six REST API switches and a switched-off group."""
    adm = new_session(page, base, DEMO_USER_ADMIN)
    adm.goto(f"{base}/admin/bpp/uczelnia/")
    adm.wait_for_load_state("networkidle")
    adm.locator("#result_list tbody th a, #result_list tbody td a").first.click()
    adm.wait_for_load_state("networkidle")
    form_url = adm.url
    sekcja = "fieldset.grp-module"
    tytul = "REST API (/api/v1/)"

    def otworz_sekcje() -> None:
        # grappelli collapses the fieldset; open it the way its handler does
        adm.evaluate(
            """(t) => { const h = [...document.querySelectorAll('h2.grp-collapse-handler')]
                .find(e => e.textContent.trim() === t);
              h.parentElement.classList.remove('grp-closed');
              h.parentElement.classList.add('grp-open'); }""",
            tytul,
        )
        adm.wait_for_timeout(300)

    # 1. the fieldset with the six switches, numbered as on the page
    otworz_sekcje()
    pola = [
        "api_v1_wlaczone",
        "api_v1_tylko_zalogowani",
        "api_v1_dane_bibliograficzne",
        "api_v1_wyszukiwanie",
        "api_v1_kafelki",
        "api_v1_narzedzia_redaktorskie",
    ]
    mark(
        adm,
        [
            {
                "sel": f"label[for=id_{pole}]",
                "arrow": "right",
                "label": str(n),
                "dy": -48,
            }
            for n, pole in enumerate(pola, 1)
        ],
    )
    box = page_box(adm, sekcja, tytul)
    shot(adm, out / "01-przelaczniki.png", box["y"] - 10, box["height"] + 20)

    # 2. switch "dane bibliograficzne" off, look at /api/v1/ anonymously,
    #    then switch it back on
    def ustaw(pole: str, wartosc: bool) -> None:
        adm.goto(form_url)
        adm.wait_for_load_state("networkidle")
        otworz_sekcje()
        adm.locator(f"#id_{pole}").set_checked(wartosc)
        adm.locator("input[name=_continue]").click()
        adm.wait_for_load_state("networkidle")
        if adm.locator(".errornote, .grp-errornote").count():
            raise SystemExit("Uczelnia form did not save - see the admin page.")

    ustaw("api_v1_dane_bibliograficzne", False)
    try:
        anon = api_session(page, base)
        anon.goto(f"{PUBLIC_BPP}/api/v1/")
        anon.wait_for_load_state("networkidle")
        mark(
            anon,
            [
                {"sel": ".response-info pre"},
            ],
        )
        req = page_box(anon, ".request-info")
        top = shot(
            anon, None, req["y"] - 8, bottom_of(anon, ".response-info") - req["y"] + 30
        )
        anon.goto(f"{PUBLIC_BPP}/api/v1/autor/")
        anon.wait_for_load_state("networkidle")
        mark(
            anon,
            [
                {"sel": ".response-info pre"},
                {
                    "sel": ".response-info pre span",
                    "text": "grupa_wylaczona",
                    "arrow": "right",
                    "label": "404 i powód: wyłączona grupa",
                    "dx": 320,
                    "dy": -40,
                },
            ],
        )
        req = page_box(anon, ".request-info")
        bottom = shot(
            anon, None, req["y"] - 8, bottom_of(anon, ".response-info") - req["y"] + 30
        )
        stitch(
            anon,
            [top, bottom],
            out / "02-wylaczona-grupa.png",
            "adres z wyłączonej grupy: /api/v1/autor/",
        )
        close_api_session(anon)
    finally:
        ustaw("api_v1_dane_bibliograficzne", True)
    adm.context.close()


def redaktor_wyszukiwanie_redagowanie(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/wyszukiwanie-redagowanie.md: global search, list filters, DjangoQL.

    Needs bin/docs-demo-redaktor-wyszukiwanie-redagowanie.py (editor account).
    """
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    lista = f"{base}/admin/bpp/wydawnictwo_ciagle/"
    pole_ql = "#grp-changelist-search-form"

    # 1. the global search box in the editing module's top bar
    red.goto(f"{base}/admin/")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "#search-container .select2-selection",
                "arrow": "below",
                "label": "wyszukiwanie globalne",
                "dx": -500,
                "dy": -50,
            }
        ],
    )
    shot(red, out / "01-wyszukiwanie-globalne.png", 0, 200)

    # 2. results of the global search, grouped by record type
    red.goto(f"{base}/admin/")
    red.wait_for_load_state("networkidle")
    red.click("#search-container .select2-selection")
    red.locator(".select2-container--open .select2-search__field").fill("Brokilon")
    red.wait_for_selector(".select2-results__group")
    red.wait_for_timeout(1200)
    mark(
        red,
        [
            {"sel": ".select2-results__group", "text": "Wydawnictwo zwarte"},
            {"sel": ".select2-results__group", "text": "Wydawnictwo ciągłe"},
        ],
    )
    # only the drop-down: the dashboard behind it is noise here
    red.screenshot(
        path=out / "02-wyszukiwanie-globalne-wyniki.png",
        clip={"x": 360, "y": 0, "width": VIEWPORT["width"] - 360, "height": 560},
    )

    # 3. the text filter of one table
    red.goto(f"{lista}?q=Brokilon")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": pole_ql,
                "arrow": "left",
                "label": "filtr tekstowy",
                "dy": -88,
            },
            {"sel": ".grp-pagination li:first-child"},
        ],
    )
    shot(red, out / "03-filtr-tekstowy.png", 0, 470)

    # 4. the filter panel
    red.goto(lista)
    red.wait_for_load_state("networkidle")
    red.click("#filter-panel-toggle")
    red.wait_for_timeout(900)
    mark(red, [{"sel": ".filter-panel-content"}])
    red.screenshot(path=out / "04-filtry.png")

    # 5. one filter opened: "Język"
    red.locator(".filter-title-text", has_text="Język").click()
    red.wait_for_timeout(900)
    grupa = page_box(red, ".filter-group", "Język")
    mark(red, [{"sel": ".filter-group", "text": "Język"}])
    red.screenshot(
        path=out / "05-filtr-jezyk.png",
        clip={
            "x": grupa["x"] - 20,
            "y": grupa["y"] - 20,
            "width": grupa["width"] + 40,
            "height": grupa["height"] + 40,
        },
    )

    # 6. the DjangoQL switch in the search box
    red.goto(lista)
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "input.djangoql-toggle",
                "arrow": "left",
                "label": "włącz DjangoQL",
                "dy": -88,
            }
        ],
    )
    shot(red, out / "06-djangoql-przelacznik.png", 0, 330)

    def zapytanie(q: str) -> None:
        red.goto(lista)
        red.wait_for_load_state("networkidle")
        red.check("input.djangoql-toggle")
        red.fill("textarea[name=q]", q)
        red.press("textarea[name=q]", "Enter")
        red.wait_for_load_state("networkidle")
        red.mouse.move(5, 400)

    # 7. a simple query and its result
    zapytanie("rok = 2022 or rok = 2024")
    mark(
        red,
        [
            {"sel": pole_ql},
            {"sel": "#result_list thead th.column-rok"},
        ],
    )
    shot(red, out / "07-djangoql-wynik.png", 0, 520)

    # 8.-9. completion: field names, then the fields of a related object
    red.goto(lista)
    red.wait_for_load_state("networkidle")
    red.check("input.djangoql-toggle")
    red.click("textarea[name=q]")
    red.keyboard.type("(charakt", delay=60)
    red.wait_for_selector(".djangoql-completion li")
    red.wait_for_timeout(800)
    mark(red, [{"sel": ".djangoql-completion"}])
    shot(red, out / "08-djangoql-podpowiedzi.png", 0, 360)
    red.keyboard.type("er_formalny.", delay=60)
    red.wait_for_timeout(1200)
    mark(red, [{"sel": ".djangoql-completion"}])
    shot(red, out / "09-djangoql-podpowiedzi-pola.png", 0, 560)

    # 10. the finished, more complex query
    zapytanie(
        '(charakter_formalny.skrot = "KSP" or charakter_formalny.skrot = "AC")'
        " and punkty_kbn >= 100"
    )
    mark(
        red,
        [
            {"sel": pole_ql},
            {"sel": "#result_list thead th.column-charakter_formalny__skrot"},
            {"sel": ".grp-pagination li:first-child"},
        ],
    )
    shot(red, out / "10-djangoql-wynik-zlozony.png", 0, 520)

    # 11. a syntax error ("lub" instead of "or")
    zapytanie("rok = 2024 lub rok = 2025")
    mark(
        red,
        [
            {"sel": ".grp-messagelist, ul.messagelist"},
            {"sel": pole_ql},
        ],
    )
    shot(red, out / "11-djangoql-blad.png", 0, 300)

    # 12. the public "szukaj -> zapytaniem" menu entry
    red.goto(f"{base}/")
    red.wait_for_load_state("networkidle")
    li = open_top_menu(red, "fi-magnifying-glass")
    mark(
        red,
        [{"sel": f"{li} a[href*='zapytanie']"}],
    )
    menu = page_box(red, f"{li} > ul")
    shot(red, out / "12-menu-zapytaniem.png", 0, menu["y"] + menu["height"] + 40)

    # 13. the "Szukaj zapytaniem" page with a query and its result
    q = (
        '(charakter_formalny.skrot = "KSP" or charakter_formalny.skrot = "AC")'
        " and punkty_kbn >= 100"
    )
    red.goto(f"{base}/bpp/zapytanie/?model=rekord&query={quote(q)}")
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {"sel": ".zapytanie-model-group"},
            {"sel": "textarea[name=query]"},
            {"sel": "#id_postac"},
            {"sel": "h2, h3, h4", "text": "Wyniki ("},
        ],
    )
    wynik = page_box(red, "h2, h3, h4", "Wyniki (")
    shot(red, out / "13-szukaj-zapytaniem.png", 0, wynik["y"] + 330)


def otworz_uczelnie(page: Page, base: str) -> None:
    """The university change form (the demo DB has exactly one)."""
    page.goto(f"{base}{UCZELNIA_ZMIANA}")
    page.wait_for_load_state("networkidle")
    page.locator("#result_list a[href*='/change/']").first.click()
    page.wait_for_load_state("networkidle")


def fieldset_shot(page: Page, path: Path, legend: str, below: float = 20) -> None:
    """One collapsible fieldset of a Grappelli form, by its heading."""
    box = page.evaluate(
        """legend => {
        const fs = [...document.querySelectorAll('fieldset.grp-module')].find(
            f => f.querySelector(':scope > h2')?.textContent.trim() === legend);
        const r = fs.getBoundingClientRect();
        return {y: r.top + scrollY, height: r.height}; }""",
        legend,
    )
    shot(page, path, box["y"] - 16, box["height"] + 16 + below)


def konfiguracja_pbn(page: Page, base: str, out: Path) -> None:
    """docs/administrator/konfiguracja-pbn.md: the "PBN API" section of the university, menu "autoryzuj PBN API"."""
    adm = new_session(page, base, DEMO_USER_ADMIN)

    # 1. Uczelnia form, "PBN API" section (fake app name and token)
    otworz_uczelnie(adm, base)
    mark(
        adm,
        [
            {
                "sel": "label[for=id_pbn_integracja]",
                "arrow": "right",
                "label": "1. włącz integrację",
                "dx": 560,
                "dy": -40,
            },
            {
                "sel": "#id_pbn_app_name",
                "arrow": "right",
                "label": "2. nazwa i token",
                "dx": -70,
                "dy": 0,
            },
            {"sel": "#id_pbn_app_token"},
            {
                "sel": "#id_pbn_api_user",
                "arrow": "right",
                "label": "3. konto do pracy w tle",
                "dy": -50,
            },
        ],
    )
    fieldset_shot(adm, out / "01-sekcja-pbn-api.png", "PBN API")

    # 2. top bar on the main page: "PBN" -> "autoryzuj PBN API"
    adm.goto(f"{base}/")
    adm.wait_for_load_state("networkidle")
    li = open_top_menu(adm, "fi-link")
    mark(
        adm,
        [
            {"sel": f"{li} > a"},
            {
                "sel": f"{li} a[href*='authorize']",
                "arrow": "left",
                "label": "PBN → autoryzuj PBN API",
                "dx": -20,
                "dy": 190,
            },
        ],
    )
    shot(
        adm,
        out / "02-menu-autoryzuj.png",
        0,
        bottom_of(adm, f"{li} .column-1 li:last-child", 2),
    )
    adm.context.close()


def integracja_dspace(page: Page, base: str, out: Path) -> None:
    """docs/administrator/integracja-dspace.md: the "DSpace" section of the university, adding a collection mapping."""
    adm = new_session(page, base, DEMO_USER_ADMIN)

    # 1. Uczelnia form, "DSpace" section
    otworz_uczelnie(adm, base)
    mark(
        adm,
        [
            {
                "sel": "label[for=id_dspace_aktywny]",
                "arrow": "right",
                "label": "1. włącz eksport",
                "dx": 350,
                "dy": -40,
            },
            {
                "sel": "#id_dspace_api_endpoint",
                "arrow": "right",
                "label": "2. adres i konto API",
                "dx": -100,
            },
            {"sel": "#id_dspace_api_username"},
            {"sel": "#id_dspace_api_password"},
        ],
    )
    fieldset_shot(adm, out / "01-sekcja-dspace.png", "DSpace")

    # 2. "Dodaj mapowanie DSpace": no DSpace behind the demo, so the live
    # collection list fails and the field stays a plain UUID input.
    adm.goto(f"{base}/admin/dspace_api/mapowanie_dspace/add/")
    adm.wait_for_load_state("networkidle")
    status = ".dspace-collection-picker-status"
    adm.wait_for_function(
        "s => { const e = document.querySelector(s);"
        " return e && e.textContent && !e.textContent.startsWith('Pobieranie'); }",
        arg=status,
        timeout=30000,
    )
    select2(adm, "#id_charakter_formalny", "Artykuł w czasopismie")
    adm.fill("#id_collection_uuid", "8f0c1a2b-3c4d-4e5f-8a9b-0c1d2e3f4a5b")
    mark(
        adm,
        [
            {
                "sel": "#id_charakter_formalny + .select2",
                "arrow": "right",
                "label": "1. charakter formalny",
                "dx": -100,
            },
            {
                "sel": "#id_collection_uuid",
                "arrow": "below",
                "label": "2. UUID kolekcji — wpisany ręcznie",
                "dx": 120,
                "dy": -10,
            },
            {
                "sel": ".dspace-collection-picker-status",
            },
        ],
    )
    shot(adm, out / "02-mapowanie-dodaj.png", 0, bottom_of(adm, "form fieldset", 90))
    adm.context.close()


def eksport_cerif(page: Page, base: str, out: Path) -> None:
    """docs/administrator/eksport-cerif.md: the CERIF/OpenAIRE section of the university."""
    adm = new_session(page, base, DEMO_USER_ADMIN)
    otworz_uczelnie(adm, base)
    mark(
        adm,
        [
            {
                "sel": "label[for=id_eksport_cerif_wlaczony]",
                "arrow": "right",
                "label": "1. główny przełącznik",
                "dx": 410,
                "dy": -40,
            },
            {
                "sel": "label[for=id_eksport_cerif_osoby]",
                "arrow": "right",
                "label": "2. dane osób (RODO)",
                "dx": 420,
                "dy": -40,
            },
            {
                "sel": "#id_ror_id",
                "arrow": "right",
                "label": "3. ROR uczelni",
                "dx": -100,
                "dy": -40,
            },
        ],
    )
    fieldset_shot(
        adm, out / "01-sekcja-cerif.png", "Eksport CERIF / OpenAIRE (/cerif-oai/)"
    )
    adm.context.close()


def grupy_uprawnien(page: Page, base: str, out: Path) -> None:
    """docs/administrator/grupy-uprawnien.md: Administracja -> Użytkownicy, the group column and the "grupy" filter."""
    adm = new_session(page, base, DEMO_USER_ADMIN)
    adm.goto(f"{base}/admin/bpp/bppuser/")
    adm.wait_for_load_state("networkidle")
    w = VIEWPORT["width"]

    # 1. the list: "Lista grup" column (the table is wider than the window)
    mark(
        adm,
        [
            {"sel": "th.column-lista_grup"},
            {"sel": "th.column-is_superuser"},
            {
                "sel": "#result_list tbody tr:nth-child(5) td.field-lista_grup",
                "arrow": "below",
                "label": "grupy konta",
                "dx": -180,
                "dy": -20,
            },
            {
                "sel": "#result_list tbody tr:nth-child(4) td.field-is_superuser",
                "arrow": "below",
                "label": "superużytkownik",
                "dx": -170,
                "dy": 40,
            },
        ],
    )
    tabela = page_box(adm, "#result_list")
    adm.evaluate("window.scrollTo(0, 0)")
    szer = max(w, tabela["x"] + tabela["width"] + 40)
    adm.screenshot(
        path=out / "01-lista-uzytkownikow.png",
        full_page=True,
        clip={
            "x": szer - w,
            "y": 0,
            "width": w,
            "height": bottom_of(adm, "#result_list", 140),
        },
    )

    # 2. filter panel, "grupy" expanded
    adm.reload()
    adm.wait_for_load_state("networkidle")
    adm.click("#filter-panel-toggle")
    adm.wait_for_timeout(800)
    adm.locator(".filter-title", has_text="grupy").click()
    adm.wait_for_timeout(800)
    mark(
        adm,
        [
            {
                "sel": ".filter-group",
                "text": "grupy",
                "arrow": "left",
                "label": "członkowie wybranej grupy",
                "dy": -60,
            },
        ],
    )
    adm.screenshot(
        path=out / "02-filtr-grupy.png",
        clip={"x": 0, "y": 0, "width": w, "height": VIEWPORT["height"]},
    )
    adm.context.close()


def open_admin_menu(page: Page, icon: str) -> str:
    """Hover a top-bar dropdown of the editing module ("menu-icon-structure",
    ...) and wait for it. Returns the selector of the menu's <li>."""
    li = f"#grp-navigation li.{icon}"
    if not page.locator(li).count():
        li = f"li.menu-item.{icon}"
    page.hover(f"{li} > a")
    page.wait_for_selector(f"{li} > ul", state="visible")
    page.wait_for_timeout(600)
    return li


def open_fieldset(page: Page, nazwa: str) -> str:
    """Expand a collapsible admin fieldset by its heading and tag it with an
    id; returns a plain CSS selector (usable by mark/page_box too)."""
    fid = page.evaluate(
        """(nazwa) => {
        const h = [...document.querySelectorAll('fieldset.grp-module > h2')]
            .find(e => e.textContent.trim() === nazwa);
        const fs = h.parentElement;
        fs.id = fs.id || 'kb-fs-' + [...document.querySelectorAll('fieldset')].indexOf(fs);
        return fs.id; }""",
        nazwa,
    )
    sel = f"#{fid}"
    if "grp-closed" in (page.get_attribute(sel, "class") or ""):
        page.click(f"{sel} > h2")
        page.wait_for_timeout(500)
    return sel


def panel_uczelnia_ogolna(page: Page, base: str, out: Path) -> None:
    """docs/administrator/ogolna.md: author visibility, "Strona wizualna",
    the author page tile editor and the column picker.

    Needs bin/docs-demo-panel-uczelnia.py (accounts vesemir and regis).
    """
    w = VIEWPORT["width"]
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    adm = new_session(page, base, DEMO_USER_ADMIN)

    # 1. author form: "Pokazuj na stronie jednostki" in "Widoczność"
    red.goto(f"{base}/admin/bpp/autor/{AUTOR_MIEJSCA_PRACY}/change/")
    red.wait_for_load_state("networkidle")
    sekcja = open_fieldset(red, "Widoczność")
    mark(
        red,
        [
            {
                "sel": ".form-row.pokazuj_na_stronie_jednostki label",
                "arrow": "right",
                "label": "odznacz, by ukryć autora",
                "dx": 200,
                "dy": -40,
            }
        ],
    )
    box = page_box(red, sekcja)
    shot(
        red,
        out / "01-pokazuj-na-stronie-jednostki.png",
        box["y"] - 15,
        box["height"] + 30,
    )

    # 2. university form: "Strona wizualna" - who sees what
    uczelnia = f"{base}/admin/bpp/uczelnia/"
    adm.goto(uczelnia)
    adm.wait_for_load_state("networkidle")
    adm.locator("#result_list tbody a").first.click()
    adm.wait_for_load_state("networkidle")
    sekcja = open_fieldset(adm, "Strona wizualna")
    mark(
        adm,
        [
            {
                "sel": ".form-row.pokazuj_status_korekty select",
                "arrow": "right",
                "label": "zawsze / zalogowani / zespół / nigdy",
                "dx": 40,
                "dy": 10,
            },
            {"sel": ".form-row.pokazuj_ranking_autorow select"},
        ],
    )
    gora = page_box(adm, sekcja)
    od = page_box(adm, ".form-row.pokazuj_status_korekty")
    do = page_box(adm, ".form-row.pokazuj_formularz_zglaszania_publikacji")
    stitch(
        adm,
        [
            shot(adm, None, gora["y"] - 10, 140),
            shot(adm, None, od["y"] - 10, do["y"] + do["height"] - od["y"] + 20),
        ],
        out / "02-strona-wizualna.png",
        "niżej w tej samej sekcji",
    )

    # 3. "Profil autora (podstrona)": the tile editor
    sekcja = open_fieldset(adm, "Profil autora (podstrona)")
    kafelek = ".uklad-profilu-kafelek[data-klucz]"
    mark(
        adm,
        [
            {
                "sel": f"{kafelek}:nth-child(2) .uklad-uchwyt",
                "arrow": "left",
                "label": "1",
                "dx": 40,
                "dy": -40,
            },
            {
                "sel": f"{kafelek}:nth-child(3) .uklad-widoczna",
                "arrow": "left",
                "label": "2",
                "dx": 40,
                "dy": 30,
            },
            {
                "sel": f"{kafelek}:nth-child(4) .uklad-szerokosc-select",
                "arrow": "right",
                "label": "3",
                "dx": 260,
                "dy": -60,
            },
            {
                "sel": f"{kafelek}:nth-child(6) .uklad-limit-select",
                "arrow": "right",
                "label": "4",
                "dx": 120,
                "dy": 0,
            },
        ],
    )
    box = page_box(adm, sekcja)
    shot(adm, out / "03-profil-autora-kafelki.png", box["y"] - 10, box["height"] + 20)

    # 4. any list in the editing module: the "Kolumny" button
    lista = f"{base}/admin/bpp/wydawnictwo_ciagle/"
    adm.goto(lista)
    adm.wait_for_load_state("networkidle")
    mark(
        adm,
        [
            {
                "sel": "#dyncol-button",
                "arrow": "below",
                "label": "Kolumny",
                "dx": -220,
                "dy": 20,
            }
        ],
    )
    adm.screenshot(
        path=out / "04-przycisk-kolumny.png",
        clip={"x": 0, "y": 0, "width": w, "height": 420},
    )

    # 5. the column picker (superuser: also the global defaults)
    adm.click("#dyncol-button")
    adm.wait_for_selector(
        "#dyncol-modal:not([hidden]) #dyncol-list li", state="visible"
    )
    adm.wait_for_timeout(800)
    mark(
        adm,
        [
            {
                "sel": ".dyncol-scope",
                "arrow": "right",
                "label": "1. dla mnie / dla wszystkich",
                "dx": -170,
                "dy": -110,
            },
            {
                "sel": "#dyncol-list li:nth-child(3) .dyncol-handle, #dyncol-list li:nth-child(3) [class*=handle]",
                "arrow": "left",
                "label": "2. przeciągnij",
                "dx": -40,
                "dy": -20,
            },
            {
                "sel": "#dyncol-list li:nth-child(8) input[type=checkbox]",
                "arrow": "left",
                "label": "3. pokaż / ukryj",
                "dx": -40,
                "dy": 20,
            },
            {
                "sel": "#dyncol-save",
                "arrow": "right",
                "label": "4. Zapisz",
                "dx": 40,
                "dy": -60,
            },
        ],
    )
    adm.screenshot(path=out / "05-okno-kolumn.png")
    adm.keyboard.press("Escape")

    # 6. Administracja -> Kolumny w module redagowania: saved layouts
    adm.goto(f"{base}/admin/")
    adm.wait_for_load_state("networkidle")
    li = open_admin_menu(adm, "menu-icon-admin")
    mark(
        adm,
        [
            {
                "sel": f"{li} > ul a[href*='dynamic_admin_columns']",
                "arrow": "left",
                "label": "Kolumny w module redagowania",
                "dx": 0,
                "dy": -180,
            }
        ],
    )
    menu = page_box(adm, f"{li} > ul")
    adm.screenshot(
        path=out / "06-menu-kolumny.png",
        clip={"x": 0, "y": 0, "width": w, "height": menu["y"] + menu["height"] + 60},
    )


def panel_uczelnia_redaktor(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/uczelnia.md: opening the university settings, PBN section,
    "Obca jednostka". Needs bin/docs-demo-panel-uczelnia.py (superuser regis:
    the PBN section is shown to superusers only)."""
    w = VIEWPORT["width"]

    # 1. anonymous visitor: "zaloguj" in the top bar
    anon = new_session(page, base)
    zaloguj = TOP_MENU.format(icon="fi-lock")
    if anon.locator(f"{zaloguj} > ul").count():
        zaloguj = open_top_menu(anon, "fi-lock")
    mark(
        anon,
        [
            {
                "sel": f"{zaloguj} > a",
                "arrow": "right",
                "label": "1. zaloguj",
                "dx": 330,
                "dy": -40,
            },
            {
                "sel": f"{zaloguj} > ul a[href*='login']",
                "arrow": "right",
                "label": "2. logowanie",
                "dx": 60,
                "dy": -20,
            },
        ],
    )
    anon.screenshot(
        path=out / "01-zaloguj.png", clip={"x": 0, "y": 0, "width": w, "height": 330}
    )
    anon.context.close()

    # 2. logged in: "redagowanie" -> "redagowanie" opens the editing module
    adm = new_session(page, base, DEMO_USER_ADMIN)
    li = open_top_menu(adm, "fi-pencil")
    mark(
        adm,
        [
            {
                "sel": f"{li} > ul a[href='/admin/']",
                "arrow": "left",
                "label": "moduł redagowania",
                "dx": -30,
                "dy": 60,
            }
        ],
    )
    menu = page_box(adm, f"{li} > ul")
    shot(adm, out / "02-menu-redagowanie.png", 0, menu["y"] + menu["height"] + 30)

    # 3. editing module: Struktura -> Uczelnia
    adm.mouse.move(5, 700)
    adm.goto(f"{base}/admin/")
    adm.wait_for_load_state("networkidle")
    li = open_admin_menu(adm, "menu-icon-structure")
    mark(
        adm,
        [
            {"sel": f"{li} > a"},
            {
                "sel": f"{li} > ul a[href='/admin/bpp/uczelnia/']",
                "arrow": "right",
                "label": "Struktura ➡ Uczelnia",
                "dx": 40,
                "dy": 30,
            },
        ],
    )
    adm.screenshot(
        path=out / "03-menu-struktura.png",
        clip={"x": 0, "y": 0, "width": w, "height": 260},
    )

    # 4. the list has one university: click its name
    adm.mouse.move(5, 700)
    adm.goto(f"{base}/admin/bpp/uczelnia/")
    adm.wait_for_load_state("networkidle")
    mark(
        adm,
        [
            {
                "sel": "#result_list tbody tr:first-child th a, #result_list tbody tr:first-child td a",
                "arrow": "below",
                "label": "kliknij nazwę uczelni",
                "dx": 40,
                "dy": 0,
            }
        ],
    )
    adm.screenshot(
        path=out / "04-lista-uczelni.png",
        clip={"x": 0, "y": 0, "width": w, "height": 400},
    )

    # 5. the "PBN API" section
    adm.locator("#result_list tbody a").first.click()
    adm.wait_for_load_state("networkidle")
    sekcja = open_fieldset(adm, "PBN API")
    mark(
        adm,
        [
            {"sel": ".form-row.pbn_integracja"},
            {
                "sel": ".form-row.pbn_app_token input",
                "arrow": "right",
                "label": "token z PBN (nie jest wyświetlany)",
                "dx": 120,
                "dy": -40,
            },
        ],
    )
    box = page_box(adm, sekcja)
    shot(adm, out / "05-pbn-api.png", box["y"] - 10, box["height"] + 20)

    # 6. "Obca jednostka" at the top of the form
    adm.add_style_tag(content=".grp-fixed-footer{display:none!important}")
    mark(
        adm,
        [
            {
                "sel": ".form-row.obca_jednostka .select2-selection",
                "arrow": "above",
                "label": "Obca jednostka",
                "dx": 300,
                "dy": 50,
            }
        ],
    )
    box = page_box(adm, ".form-row.obca_jednostka")
    shot(adm, out / "06-obca-jednostka.png", 0, box["y"] + box["height"] + 15)


def panel_uczelnia_autorzy(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/autorzy.md: "Aktualna jednostka" and the author's workplaces.
    Needs bin/docs-demo-panel-uczelnia.py."""
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    red.goto(f"{base}/admin/bpp/autor/{AUTOR_MIEJSCA_PRACY}/change/")
    red.wait_for_load_state("networkidle")
    red.add_style_tag(content=".grp-fixed-footer{display:none!important}")

    # 1. read-only "Aktualna jednostka"
    mark(
        red,
        [
            {
                "sel": ".form-row.aktualna_jednostka .grp-readonly, .form-row.aktualna_jednostka a",
                "arrow": "right",
                "label": "wyliczane z miejsc pracy",
                "dx": 60,
                "dy": -30,
            }
        ],
    )
    box = page_box(red, ".form-row.aktualna_jednostka")
    shot(red, out / "01-aktualna-jednostka.png", box["y"] - 140, box["height"] + 200)

    # 2. the workplaces table - wider than the window, so widen it for this shot
    szer = 1720
    red.set_viewport_size({"width": szer, "height": VIEWPORT["height"]})
    red.wait_for_timeout(500)
    grupa = "#autor_jednostka_set-group"
    mark(
        red,
        [
            {
                "sel": "#autor_jednostka_set0 .grp-td.zakonczyl_prace input",
                "arrow": "below",
                "label": "praca zakończona",
                "dx": -330,
                "dy": 70,
            },
            {
                "sel": "#autor_jednostka_set1 .grp-td.podstawowe_miejsce_pracy select",
                "arrow": "left",
                "label": "podstawowe miejsce pracy",
                "dx": 0,
                "dy": 160,
            },
        ],
    )
    box = page_box(red, grupa)
    red.evaluate("window.scrollTo(0, 0)")
    red.screenshot(
        path=out / "02-miejsca-pracy.png",
        full_page=True,
        clip={"x": 0, "y": box["y"] - 10, "width": szer, "height": box["height"] + 100},
    )
    red.set_viewport_size(VIEWPORT)


def panel_uczelnia_wydawnictwa(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/wydawnictwa.md: adding authors and changing their order."""
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    red.goto(f"{base}/admin/bpp/wydawnictwo_ciagle/{REKORD_TRZECH_AUTOROW}/change/")
    red.wait_for_load_state("networkidle")
    grupa = "#autorzy_set-group"
    # collapsed authors are easier to reorder
    red.click(f"{grupa} > .grp-tools .grp-close-handler")
    red.wait_for_timeout(600)
    mark(
        red,
        [
            {
                "sel": "#autorzy_set1 .grp-drag-handler",
                "arrow": "left",
                "label": "chwyć i przeciągnij w górę lub w dół",
                "dx": -420,
                "dy": -210,
            },
            {
                "sel": f"{grupa} a.grp-add-handler:not(.grp-icon)",
                "arrow": "right",
                "label": "dodaj autora",
                "dx": 200,
                "dy": 0,
            },
        ],
    )
    box = page_box(red, grupa)
    shot(red, out / "01-kolejnosc-autorow.png", box["y"] - 110, box["height"] + 170)


def plik_pracownikow_demo(path: Path) -> Path:
    """Write the made-up staff XLSX used by the import-pracownikow scenario."""
    import openpyxl

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Pracownicy"
    ws.append(IMPORT_PRAC_NAGLOWEK)
    for numer, nazwisko, imie, tytul, jedn, od, bpp_id in IMPORT_PRAC_WIERSZE:
        ws.append(
            [numer, nazwisko, imie, None, tytul, None, None, jedn]
            + [IMPORT_PRAC_WYDZIAL, od, None, "TAK", None, bpp_id, "Pełny etat"]
        )
    wb.save(path)
    return path


def import_pracownikow(page: Page, base: str, out: Path) -> None:
    """docs/administrator/import-pracownikow.md: staff import end to end; run bin/docs-demo-admin-import-pracownikow.py first."""
    import tempfile

    red = new_session(page, base, DEMO_USER_REDAKTOR)
    plik = plik_pracownikow_demo(
        Path(tempfile.mkdtemp()) / "pracownicy-wydzial-magii.xlsx"
    )

    def przeglad(url: str) -> None:
        """Wait out the background run; liveops.js usually redirects by itself."""
        try:
            red.wait_for_url("**/przeglad/**", timeout=120_000)
        except PlaywrightTimeoutError:
            red.goto(url)  # the "finished" push did not arrive; go by hand
        red.wait_for_load_state("networkidle")
        red.goto(url)  # drop the one-off flash message, same view each run
        red.wait_for_load_state("networkidle")

    # 1. "operacje" menu
    li = open_top_menu(red, "fi-wrench")
    mark(red, [{"sel": f"{li} .column-1 a", "text": "import pracowników"}])
    menu = page_box(red, f"{li} .menu-columns-wrapper")
    shot(red, out / "01-menu-operacje.png", 0, menu["y"] + menu["height"] + 30)

    # 2. new import: template, file, date, advanced options
    red.goto(f"{base}/import_pracownikow/new/")
    red.wait_for_load_state("networkidle")
    red.set_input_files("input[name=plik_xls]", str(plik))
    mark(
        red,
        [
            {
                "sel": "#download-example-file",
                "arrow": "right",
                "label": "plik wzorcowy",
                "dx": 20,
                "dy": -40,
            },
            {
                "sel": "input[name=plik_xls]",
                "arrow": "above",
                "label": "1. plik XLSX",
                "dx": -300,
                "dy": 30,
            },
            {
                "sel": "details.callout summary",
                "arrow": "below",
                "label": "opcje zaawansowane (rzadko potrzebne)",
                "dx": -250,
                "dy": -70,
            },
            {
                "sel": "#id_submit",
                "arrow": "right",
                "label": "2. Utwórz import",
                "dx": 20,
            },
        ],
    )
    shot(red, out / "02-nowy-import.png", 100, bottom_of(red, "#id_submit", 40) - 100)

    # 3. column mapping: sample of the file + the field for every column
    red.click("#id_submit")
    red.wait_for_url("**/mapowanie/**")
    red.wait_for_load_state("networkidle")
    url = red.url.replace("/mapowanie/", "/")
    mark(red, [{"sel": "h2", "text": "Próbka danych"}])
    top = shot(red, None, 100, bottom_of(red, "table", 30) - 100)
    submit = "input[type=submit][value*='Zapisz mapowanie']"
    mark(
        red,
        [
            {
                "sel": submit,
                "arrow": "right",
                "label": "Zapisz mapowanie i analizuj",
                "dx": 20,
                "dy": -40,
            },
        ],
    )
    pola = page_box(red, "label[for=id_kol__wymiar_etatu]")
    dol = shot(red, None, pola["y"] - 20, bottom_of(red, submit, 30) - pola["y"] + 20)
    mark(
        red,
        [
            {"sel": "#id_kol__nazwisko"},
            {"sel": "label[for=id_tworz_brakujace_jednostki]"},
        ],
    )
    poczatek = page_box(red, "label[for=id_zapisz_profil]")["y"] - 30
    srodek = shot(
        red, None, poczatek, bottom_of(red, "#id_kol__nazwisko", 30) - poczatek
    )
    stitch(red, [top, srodek, dol], out / "03-mapowanie-kolumn.png", "przewiń w dół")

    # 4. analysis done: step 1, the structure (a unit to create)
    red.click(submit)
    przeglad(url + "przeglad/")
    mark(
        red,
        [
            {
                "sel": ".callout.primary a.button",
                "text": "Zweryfikuj jednostki",
                "arrow": "right",
                "label": "1. sprawdź nowe jednostki",
                "dx": 20,
            },
            {
                "sel": "button[name=zakres][value=jednostki]",
                "arrow": "right",
                "label": "2. zapisz strukturę",
                "dx": 20,
            },
            {"sel": ".callout.secondary h2", "text": "Krok 2"},
        ],
    )
    shot(
        red,
        out / "04-krok-1-struktura.png",
        100,
        bottom_of(red, ".callout.secondary", 30) - 100,
    )

    # 5. unit verification: create it under the right faculty
    red.goto(url + "jednostki/")
    red.wait_for_load_state("networkidle")
    red.locator("select.js-wydzial").first.select_option(label=IMPORT_PRAC_WYDZIAL)
    red.wait_for_timeout(300)
    mark(
        red,
        [
            {"sel": "select.js-decyzja"},
            {
                "sel": "select.js-wydzial",
                "arrow": "below",
                "label": "wydział nadrzędny",
                "dx": -150,
                "dy": -20,
            },
            {
                "sel": "button[type=submit]",
                "text": "Zapisz decyzje",
                "arrow": "below",
                "label": "Zapisz decyzje",
                "dx": 40,
                "dy": -50,
            },
        ],
    )
    shot(
        red,
        out / "05-weryfikacja-jednostek.png",
        100,
        bottom_of(red, "form button[type=submit]", 110) - 100,
    )
    red.locator("button[type=submit]", has_text="Zapisz decyzje").click()
    red.wait_for_load_state("networkidle")

    # 6. save the structure -> step 2, people
    red.goto(url + "przeglad/")
    red.wait_for_load_state("networkidle")
    red.click("button[name=zakres][value=jednostki]")
    przeglad(url + "przeglad/")
    mark(
        red,
        [
            {
                "sel": ".callout a.button",
                "text": "Zobacz wiersze",
                "arrow": "right",
                "label": "1. osoby z pliku",
                "dx": 20,
                "dy": -40,
            },
            {
                "sel": ".callout a.button",
                "text": "Zobacz powiązania",
                "arrow": "right",
                "label": "2. osoby spoza pliku",
                "dx": 20,
                "dy": -40,
            },
        ],
    )
    kafle = page_box(red, ".callout.primary .row")
    shot(red, out / "06-krok-2-osoby.png", 100, kafle["y"] + kafle["height"] + 20 - 100)

    # 7. rows of the file: confirm a namesake, create a new author
    red.goto(url + "rezultaty/")
    red.wait_for_load_state("networkidle")
    leo = red.locator("tbody[data-rekord]", has_text="Leo")
    vilgefortz = red.locator("tbody[data-rekord]", has_text="Vilgefortz")
    leo_id = leo.get_attribute("id")
    vil_id = vilgefortz.get_attribute("id")
    mark(
        red,
        [
            {"sel": f"#{leo_id} .label", "text": "wielu"},
            {
                "sel": f"#{leo_id} button",
                "text": "potwierdź",
                "arrow": "right",
                "label": "potwierdź wybór",
                "dx": 20,
                "dy": 40,
            },
            {"sel": f"#{vil_id} .label", "text": "brak"},
            {
                "sel": f"#{vil_id} label",
                "text": "Utwórz nowego",
                "arrow": "right",
                "label": "lub nowy autor",
                "dx": 20,
                "dy": 30,
            },
        ],
    )
    tabela = page_box(red, "#tabela-autorow")
    koniec = page_box(red, f"#{vil_id}")
    shot(
        red,
        out / "07-wiersze-importu.png",
        tabela["y"] - 20,
        koniec["y"] + koniec["height"] - tabela["y"] + 40,
    )
    leo.locator("button", has_text="potwierdź").click()
    red.wait_for_timeout(1000)
    red.locator(f"#{vil_id} input[name=wybor][value=utworz]").check()
    red.wait_for_timeout(1000)

    # 8. people missing from the file: proposed unlinking
    red.goto(url + "odpiecia/")
    red.wait_for_load_state("networkidle")
    cahir = red.locator("#tabela-odpiec tbody tr", has_text="Cahir")
    cahir.locator("input[type=checkbox]").check()
    red.wait_for_timeout(1000)
    mark(
        red,
        [
            {
                "sel": "#tabela-odpiec tbody tr:nth-child(2) td:last-child",
                "arrow": "below",
                "label": "zaznacz, kogo odpiąć",
                "dx": -500,
                "dy": -50,
            },
            {
                "sel": "#btn-zaznacz-filtr",
                "arrow": "below",
                "label": "albo wszystkich naraz",
                "dx": 300,
                "dy": -70,
            },
        ],
    )
    shot(red, out / "08-odpiecia.png", 100, bottom_of(red, "#tabela-odpiec", 110) - 100)

    # 9. save the people: confirmation at the bottom of the overview
    red.goto(url + "przeglad/")
    red.wait_for_load_state("networkidle")
    red.check("input[name=potwierdzenie_zapisu]")
    mark(
        red,
        [
            {
                "sel": "input[name=potwierdzenie_zapisu]",
                "arrow": "left",
                "label": "1. potwierdź",
                "dx": -20,
                "dy": -40,
            },
            {
                "sel": "button.alert[type=submit]",
                "arrow": "right",
                "label": "2. Zapisz osoby do bazy",
                "dx": 60,
            },
        ],
    )
    top = shot(red, None, 100, bottom_of(red, ".callout.primary h2", 60) - 100)
    ostrz = page_box(red, ".callout.warning")
    dol = shot(red, None, ostrz["y"] - 20, ostrz["height"] + 40)
    stitch(red, [top, dol], out / "09-zapis-osob.png", "przewiń na sam dół")

    # 10. result of the run
    red.click("button.alert[type=submit]")
    red.wait_for_selector("#op-result .callout", state="visible", timeout=180_000)
    red.reload()
    red.wait_for_load_state("networkidle")
    mark(
        red,
        [
            {
                "sel": "#op-result a.button",
                "text": "Log zmian",
                "arrow": "right",
                "label": "co dokładnie zmieniono",
                "dx": 30,
            }
        ],
    )
    shot(red, out / "10-import-zakonczony.png", 0, bottom_of(red, "#op-result", 30))

    # 11. change log
    red.goto(url + "audyt/")
    red.wait_for_load_state("networkidle")
    shot(
        red,
        out / "11-log-zmian.png",
        100,
        red.evaluate(
            "(() => { const t = [...document.querySelectorAll('table')].pop();"
            " const r = t.getBoundingClientRect(); return r.bottom + scrollY + 30; })()"
        )
        - 100,
    )
    red.context.close()


def duplikaty_publikacji(page: Page, base: str, out: Path) -> None:
    """docs/redaktor/duplikaty-publikacji.md: the publication deduplicator (editor).

    Needs bin/docs-demo-duplikaty-publikacji.py (re-run it before each run:
    it removes earlier scans) and a Celery worker (the scan runs in the
    background)."""
    red = new_session(page, base, DEMO_USER_REDAKTOR)
    red.on("dialog", lambda dialog: dialog.accept())  # data-confirm prompts
    dedup = f"{base}/deduplikator-publikacji/duplicate-publications/"

    # 1. "operacje" menu: deduplikator publikacji
    li = open_top_menu(red, "fi-wrench")
    mark(
        red,
        [
            {
                "sel": f"{li} .menu-columns-wrapper a",
                "text": "deduplikator publikacji",
                "arrow": "right",
                "label": "deduplikator publikacji",
                "dx": 60,
                "dy": -20,
            }
        ],
    )
    shot(
        red,
        out / "01-menu-operacje.png",
        0,
        bottom_of(red, f"{li} .menu-columns-wrapper"),
    )

    # 2. start screen: no scan yet, the scan form
    red.goto(dedup)
    red.wait_for_load_state("networkidle")
    red.mouse.move(5, 5)
    red.fill("#year_from", "2020")
    red.fill("#year_to", "2026")
    mark(
        red,
        [
            {
                "sel": "label[for=year_from]",
                "arrow": "below",
                "label": "1. zakres lat",
                "dx": 60,
                "dy": -75,
            },
            {"sel": "label[for=year_to]"},
            {
                "sel": ".deduplikator-publikacji__checkboxes-inline",
                "arrow": "above",
                "label": "2. czego nie porównywać (opcjonalnie)",
                "dx": 0,
                "dy": 50,
            },
            {
                "sel": "button[type=submit].primary",
                "arrow": "below",
                "label": "3. uruchom",
                "dx": -60,
                "dy": -20,
            },
        ],
    )
    shot(
        red,
        out / "02-ekran-startowy.png",
        0,
        bottom_of(red, ".callout.warning", 30),
    )

    # 3. start the scan and catch it in progress
    red.goto(dedup)
    red.wait_for_load_state("networkidle")
    red.fill("#year_from", "2020")
    red.fill("#year_to", "2026")
    red.click("button[type=submit].primary")
    red.wait_for_load_state("networkidle")
    for _ in range(20):
        if red.locator("#scan-progress-container").count():
            break
        red.wait_for_timeout(300)
        red.reload()
    if red.locator("#scan-progress-container").count():
        red.wait_for_function(
            "parseFloat(document.getElementById('scan-progress-bar').style.width) > 0",
            timeout=30000,
        )
        red.mouse.move(5, 5)
        mark(
            red,
            [
                {"sel": "#scan-progress-container"},
                {
                    "sel": "#scan-eta-content",
                    "arrow": "right",
                    "label": "postęp i czas do końca, odświeżają się same",
                    "dx": 40,
                    "dy": -10,
                },
            ],
        )
        shot(
            red,
            out / "03-skanowanie-w-toku.png",
            0,
            bottom_of(red, "#scan-progress-container", 10),
        )
    # the page reloads itself when the scan is done
    red.wait_for_selector("table.deduplikator-publikacji__table", timeout=120000)
    red.wait_for_load_state("networkidle")

    # 4. the results list
    red.goto(dedup)
    red.wait_for_load_state("networkidle")
    red.mouse.move(5, 5)
    mark(
        red,
        [
            {"sel": "thead th", "text": "Podobieństwo"},
            {"sel": "thead th", "text": "Powody"},
            {"sel": "tbody tr:first-child .deduplikator-publikacji__actions"},
        ],
    )
    ostatni = page_box(red, "tbody tr", "Novigradu (nr 10)")
    shot(red, out / "04-lista-wynikow.png", 0, ostatni["y"] + ostatni["height"] + 4)

    # 5. one pair compared: both records of the DOI pair, one above the other
    wiersz = red.locator("tbody tr", has_text="Wpływ mutacji").first
    linki = wiersz.locator(".deduplikator-publikacji__pub-info a")
    adresy = [linki.nth(i).get_attribute("href") for i in range(2)]
    czesci = []
    for adres, opis in zip(adresy, ("oryginał", "potencjalny duplikat"), strict=True):
        rec = red.context.new_page()
        rec.goto(f"{base}{adres}")
        rec.wait_for_load_state("networkidle")
        close_cookie_banner(rec)
        rec.mouse.move(5, 5)
        autorzy = rec.locator(".praca-mono__authors-section .author-name").count()
        mark(
            rec,
            [
                {
                    "sel": ".praca-mono__authors-section",
                    "arrow": "below",
                    "label": f"{opis}: autorzy ({autorzy})",
                    "dx": -420,
                    "dy": -30,
                },
                {"sel": ".praca-mono__column--right > *:first-child"},
            ],
        )
        czesci.append(shot(rec, None, 0, 560))
        rec.close()
    stitch(red, czesci, out / "05-porownanie-pary.png", "drugi rekord z tej pary")

    # 6. decision: confirm the DOI pair -> message, the row is gone
    wiersz.locator("button[title='Potwierdź jako duplikat']").click()
    red.wait_for_load_state("networkidle")
    red.wait_for_selector("#messagesPlaceholder >> text=Duplikat potwierdzony")
    red.mouse.move(5, 5)
    mark(
        red,
        [
            {
                "sel": "#messagesPlaceholder .callout",
                "text": "Duplikat potwierdzony",
                "arrow": "below",
                "label": "para znika z listy",
                "dx": 60,
                "dy": 40,
            }
        ],
    )
    shot(red, out / "06-potwierdzony-duplikat.png", 0, 420)


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
    "import-polon-liczba-n": ("redaktor/import-polon-liczba-n", import_polon_liczba_n),
    "obsluga-zgloszen": ("redaktor/obsluga-zgloszen", obsluga_zgloszen),
    "impact-factor-i-punktacja": (
        "redaktor/impact-factor-i-punktacja",
        impact_factor_i_punktacja,
    ),
    "nowy-rok": ("redaktor/nowy-rok", nowy_rok),
    "pbn-wysylka-i-synchronizacja": (
        "redaktor/pbn-wysylka-i-synchronizacja",
        pbn_wysylka_i_synchronizacja,
    ),
    "importer-publikacji": ("redaktor/importer-publikacji", importer_publikacji),
    "duplikaty": ("redaktor/duplikaty", duplikaty),
    "metryki-ewaluacyjne": ("redaktor/metryki-ewaluacyjne", metryki_ewaluacyjne),
    "liczba-n-faq": ("redaktor/liczba-n-faq", liczba_n_faq),
    "import-list-ministerialnych": (
        "redaktor/import-list-ministerialnych",
        import_list_ministerialnych,
    ),
    "rozbieznosci-dyscyplin": (
        "redaktor/rozbieznosci-dyscyplin",
        rozbieznosci_dyscyplin,
    ),
    "oswiadczenia": ("redaktor/oswiadczenia", oswiadczenia),
    "optymalizacja-ewaluacji": (
        "redaktor/optymalizacja-ewaluacji",
        optymalizacja_ewaluacji,
    ),
    "admin-zglaszanie-publikacji": (
        "administrator/zglaszanie-publikacji",
        admin_zglaszanie_publikacji,
    ),
    "api-index": ("api/index", api_index),
    "rest-api": ("administrator/rest-api", rest_api),
    "redaktor-wyszukiwanie-redagowanie": (
        "redaktor/wyszukiwanie-redagowanie",
        redaktor_wyszukiwanie_redagowanie,
    ),
    "konfiguracja-pbn": ("administrator/konfiguracja-pbn", konfiguracja_pbn),
    "integracja-dspace": ("administrator/integracja-dspace", integracja_dspace),
    "eksport-cerif": ("administrator/eksport-cerif", eksport_cerif),
    "grupy-uprawnien": ("administrator/grupy-uprawnien", grupy_uprawnien),
    "panel-uczelnia-ogolna": ("administrator/ogolna", panel_uczelnia_ogolna),
    "panel-uczelnia-redaktor": ("redaktor/uczelnia", panel_uczelnia_redaktor),
    "panel-uczelnia-autorzy": ("redaktor/autorzy", panel_uczelnia_autorzy),
    "panel-uczelnia-wydawnictwa": ("redaktor/wydawnictwa", panel_uczelnia_wydawnictwa),
    "import-pracownikow": ("administrator/import-pracownikow", import_pracownikow),
    "duplikaty-publikacji": ("redaktor/duplikaty-publikacji", duplikaty_publikacji),
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
