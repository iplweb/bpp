#!/usr/bin/env python3
"""Pobierz i zself-hostuj fonty Google używane przez motywy admina.

Zastępuje `@import url(https://fonts.googleapis.com/...)` z
`themes/_fonts.scss` lokalnymi plikami `.woff2`, żeby panel admina nie
łączył się z `fonts.googleapis.com` / `fonts.gstatic.com` przy każdym
wyświetleniu strony (prywatność, brak zależności od sieci/DNS, szybsze
ładowanie).

Skrypt:
  1. Dla każdej rodziny pobiera arkusz css2 z Google (z nowoczesnym
     User-Agentem, żeby dostać `woff2` zamiast `ttf`).
  2. Zostawia TYLKO podzbiory `latin` i `latin-ext` — `latin-ext`
     pokrywa polskie znaki diakrytyczne (ą ć ę ł ń ś ź ż), `latin`
     resztę ASCII + typowe symbole.
  3. Ściąga pliki `.woff2` z `fonts.gstatic.com` do `<rodzina>/`.
  4. Generuje `../scss/themes/_font-faces.scss` z lokalnymi regułami
     `@font-face` (zachowuje `font-display: swap` i `unicode-range`).

Uruchomienie (z korzenia repo):

    uv run python src/bpp/static/bpp/fonts/fetch-fonts.py

Po regeneracji przebuduj CSS: `grunt build` (lub `grunt sass:adminthemes`).

Pliki `.woff2` oraz wygenerowany `_font-faces.scss` są commitowane do
repo — ten skrypt jest tylko narzędziem do ich (re)generacji.
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

# Nowoczesny UA — bez niego Google zwraca formaty ttf/eot zamiast woff2.
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Tylko te podzbiory hostujemy lokalnie. latin-ext = polskie ogonki.
WANTED_SUBSETS = ("latin", "latin-ext")

# (nazwa font-family w CSS, slug katalogu/pliku, wagi, [opcjonalna nazwa
#  rodziny w Google jeśli różni się od font-family — np. deprecjacje]).
FAMILIES = [
    ("Inter", "inter", [300, 400, 500, 600, 700], None),
    ("Open Sans", "open-sans", [300, 400, 500, 600, 700], None),
    ("Roboto", "roboto", [300, 400, 500, 700], None),
    ("Lato", "lato", [300, 400, 700], None),
    # "Source Sans Pro" zostało na Google Fonts przemianowane na
    # "Source Sans 3". Pliki bierzemy z nowej rodziny, ale font-family w
    # CSS zostawiamy jako 'Source Sans Pro' — tak nazywają ją reguły w
    # _fonts.scss i tego oczekuje przełącznik motywu.
    ("Source Sans Pro", "source-sans-pro", [300, 400, 600, 700], "Source Sans 3"),
]

HERE = Path(__file__).resolve().parent
SCSS_OUT = HERE.parent / "scss" / "themes" / "_font-faces.scss"

# Blok: poprzedzający komentarz /* subset */ + reguła @font-face {...}.
BLOCK_RE = re.compile(
    r"/\*\s*(?P<subset>[\w-]+)\s*\*/\s*@font-face\s*\{(?P<body>[^}]*)\}",
    re.DOTALL,
)
FIELD_RE = {
    "weight": re.compile(r"font-weight:\s*([^;]+);"),
    "style": re.compile(r"font-style:\s*([^;]+);"),
    "src": re.compile(r"src:\s*url\((https://[^)]+\.woff2)\)"),
    "range": re.compile(r"unicode-range:\s*([^;]+);"),
}


def http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 (trusted host)
        return resp.read()


def build_css_url(google_family: str, weights: list[int]) -> str:
    fam = google_family.replace(" ", "+")
    axis = ";".join(str(w) for w in sorted(weights))
    return f"https://fonts.googleapis.com/css2?family={fam}:wght@{axis}&display=swap"


def main() -> int:
    faces: list[str] = []
    faces.append(
        "/* ----------------------------------------------------------------- */"
    )
    faces.append(
        "/* GENEROWANE AUTOMATYCZNIE przez fonts/fetch-fonts.py — NIE EDYTUJ. */"
    )
    faces.append(
        "/* Self-hostowane fonty Google (podzbiory latin + latin-ext).        */"
    )
    faces.append(
        "/* Regeneracja: uv run python src/bpp/static/bpp/fonts/fetch-fonts.py */"
    )
    faces.append(
        "/* ----------------------------------------------------------------- */"
    )
    faces.append("")

    total_files = 0
    for css_family, slug, weights, google_override in FAMILIES:
        google_family = google_override or css_family
        url = build_css_url(google_family, weights)
        print(f"[{css_family}] {url}")
        css = http_get(url).decode("utf-8")

        out_dir = HERE / slug
        out_dir.mkdir(parents=True, exist_ok=True)

        kept = 0
        for m in BLOCK_RE.finditer(css):
            subset = m.group("subset")
            if subset not in WANTED_SUBSETS:
                continue
            body = m.group("body")
            weight = FIELD_RE["weight"].search(body).group(1).strip()
            style = FIELD_RE["style"].search(body).group(1).strip()
            src_url = FIELD_RE["src"].search(body).group(1).strip()
            urange_m = FIELD_RE["range"].search(body)
            urange = urange_m.group(1).strip() if urange_m else None

            fname = f"{slug}-{weight}-{subset}.woff2"
            (out_dir / fname).write_bytes(http_get(src_url))
            total_files += 1
            kept += 1

            rel = f"../fonts/{slug}/{fname}"
            face = [
                f"/* {css_family} {weight} — {subset} */",
                "@font-face {",
                f"    font-family: '{css_family}';",
                f"    font-style: {style};",
                f"    font-weight: {weight};",
                "    font-display: swap;",
                f"    src: url('{rel}') format('woff2');",
            ]
            if urange:
                face.append(f"    unicode-range: {urange};")
            face.append("}")
            faces.append("\n".join(face))
            faces.append("")

        if kept == 0:
            print(f"  !! UWAGA: 0 bloków @font-face dla {css_family} ({url})")
            return 1
        print(f"  -> {kept} plików (latin/latin-ext)")

    # rstrip — bez tego trailing pusty wiersz, który end-of-file-fixer
    # (pre-commit) i tak by przyciął przy każdej regeneracji.
    SCSS_OUT.write_text("\n".join(faces).rstrip("\n") + "\n", encoding="utf-8")
    print(f"\nZapisano {total_files} plików .woff2 + {SCSS_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
