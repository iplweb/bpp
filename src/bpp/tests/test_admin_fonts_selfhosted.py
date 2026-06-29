"""Strażnik: fonty panelu admina muszą być self-hostowane.

Panel admina nie może odpytywać `fonts.googleapis.com` /
`fonts.gstatic.com` przy każdym wyświetleniu strony — to wyciek
informacji do Google, zależność od działającego DNS/sieci (awaria DNS
potrafiła wieszać testy Playwright na ładowaniu fontów) i spowolnienie.

Reguły `@font-face` żyją w `scss/themes/_font-faces.scss` i wskazują
lokalne pliki `.woff2` w `static/bpp/fonts/` (generowane przez
`fonts/fetch-fonts.py`).
"""

import re
from pathlib import Path

# Lokalizujemy pliki względem TEGO pliku testowego (src/bpp/tests/...), a
# nie przez `import bpp` — przy editable-install `bpp.__file__` wskazałby
# główny checkout, nie ten worktree. Tu test zawsze sprawdza checkout, w
# którym sam leży: parents[1] == src/bpp.
STATIC = Path(__file__).resolve().parents[1] / "static" / "bpp"
THEMES_DIR = STATIC / "scss" / "themes"
FONTS_DIR = STATIC / "fonts"
FONT_FACES = THEMES_DIR / "_font-faces.scss"

# Skanujemy treść SCSS regexem (nie `"host" in text`), bo substringowe
# sprawdzanie literału-hosta odpala fałszywy alarm CodeQL
# `py/incomplete-url-substring-sanitization` — heurystyka traktuje
# `"fonts.googleapis.com" in x` jak (obejście-podatne) sanityzowanie URL-a,
# choć tutaj tylko przeszukujemy tekst pliku. Jeden regex łapie oba hosty.
_GOOGLE_FONTS_HOST_RE = re.compile(r"fonts\.(?:googleapis|gstatic)\.com", re.IGNORECASE)
_EXTERNAL_IMPORT_RE = re.compile(r"@import\s+url\(\s*['\"]?https?:", re.IGNORECASE)
_LOCAL_SRC_RE = re.compile(r"""url\(\s*['"]?(\.\./fonts/[^)'"]+\.woff2)""")
# Komentarze blokowe /* ... */ usuwamy przed skanem, żeby benignowa
# wzmianka o haście w komentarzu nie była fałszywym alarmem. NIE tniemy
# komentarzy linijkowych `//` — zjadłyby `https://` w realnym @imporcie.
_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)


def test_admin_theme_scss_does_not_reference_external_fonts():
    """Żaden SCSS motywów nie odwołuje się do hostów Google ani nie robi
    `@import url(http...)` (poza komentarzami)."""
    offenders = []
    for scss in sorted(THEMES_DIR.glob("*.scss")):
        text = _BLOCK_COMMENT_RE.sub("", scss.read_text(encoding="utf-8"))
        if _GOOGLE_FONTS_HOST_RE.search(text):
            offenders.append(f"{scss.name}: host Google")
        if _EXTERNAL_IMPORT_RE.search(text):
            offenders.append(f"{scss.name}: @import url(http...)")
    assert not offenders, "Zewnętrzne fonty w SCSS motywów: " + ", ".join(offenders)


def test_font_faces_partial_is_local_and_files_exist():
    """`_font-faces.scss` ma reguły @font-face wskazujące wyłącznie lokalne
    pliki .woff2, a każdy wskazany plik istnieje na dysku i jest niepusty."""
    assert FONT_FACES.is_file(), f"Brak {FONT_FACES}"
    text = FONT_FACES.read_text(encoding="utf-8")

    assert "@font-face" in text, "Brak reguł @font-face"
    assert "http://" not in text and "https://" not in text, (
        "Wygenerowany partial zawiera URL zewnętrzny"
    )

    srcs = _LOCAL_SRC_RE.findall(text)
    assert srcs, "Brak lokalnych odwołań ../fonts/*.woff2"

    missing = []
    for rel in srcs:
        # rel jest względne do skompilowanego css/ ("../fonts/..."), więc
        # na dysku: static/bpp/fonts/<reszta>.
        disk = FONTS_DIR / rel[len("../fonts/") :]
        if not disk.is_file() or disk.stat().st_size == 0:
            missing.append(rel)
    assert not missing, f"Brakujące/puste pliki woff2: {missing}"


def test_every_woff2_on_disk_is_referenced():
    """Brak osieroconych plików .woff2 — każdy ściągnięty plik jest użyty
    w `_font-faces.scss` (inaczej to martwy ciężar w repo)."""
    text = FONT_FACES.read_text(encoding="utf-8")
    referenced = {Path(rel).name for rel in _LOCAL_SRC_RE.findall(text)}
    on_disk = {p.name for p in FONTS_DIR.rglob("*.woff2")}
    orphaned = on_disk - referenced
    assert not orphaned, f"Pliki .woff2 nieużyte w _font-faces.scss: {sorted(orphaned)}"
