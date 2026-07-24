"""Strażnik: żaden asset (JS/CSS/font) nie może być ładowany z zewnętrznego CDN-a.

Skrypt z CDN-a wstawiony w ``<body>`` blokuje parser: w sieci bez dostępu do
tego hosta (VPN, firewall uczelniany) przeglądarka wstrzymuje renderowanie do
timeoutu DNS/TCP — dziesiątki sekund białej strony. Tak właśnie zachowywała się
lista wyników importu pracowników, ładująca htmx z ``unpkg.com``. Dochodzi do
tego wyciek informacji o ruchu do operatora CDN-a i zależność dostępności BPP od
cudzej infrastruktury.

Reguła: biblioteki wchodzą do ``package.json`` (zbiera je ``YarnFinder``) albo
przyjeżdżają z pakietu pythonowego, a szablony sięgają po nie przez
``{% static %}``.

Skanujemy DWOMA wzorcami, bo asset można wpiąć na dwa sposoby:

- w szablonie — jako tag ``<script src>`` / ``<link href>``;
- w Pythonie — jako goły string w ``class Media`` (tag renderuje dopiero
  Django). Wzorzec tagowy by tego NIE złapał, a dokładnie tak wyglądał
  ``przemapuj_zrodlo/admin.py`` przed tą zmianą.

POZA ZASIĘGIEM tego testu (świadomie — zielony wynik NIE oznacza zera
zewnętrznych requestów):

- ``cdn.userway.org`` (widget dostępności WCAG) — wstrzykiwany inline'owym JS-em
  przez ``s.setAttribute("src", ...)`` w ``base.html``, więc żaden skan tagów go
  nie zobaczy;
- ``src/bpp/static/kbw-keypad/dist/index.html`` — strona demo vendorowanego
  pluginu, nigdy nierenderowana przez aplikację (nie jest szablonem Django).
"""

import re
from pathlib import Path

# Ścieżki liczymy względem TEGO pliku (src/django_bpp/tests/...), a nie przez
# `import django_bpp` — przy editable-install `__file__` pakietu wskazuje główny
# checkout, a nie worktree, w którym test faktycznie leży. Test ma sprawdzać
# checkout, w którym się znajduje. parents[2] == src/.
SRC = Path(__file__).resolve().parents[2]

# Hosty usług SaaS, których NIE da się self-hostować (to zdalne API, nie pliki).
# Oba są `async`, więc nie blokują parsera. Dopisanie czegokolwiek tutaj wymaga
# uzasadnienia w komentarzu — to jest wyjątek od reguły, nie wygodna furtka.
DOZWOLONE_HOSTY = (
    # Widget zgłoszeń Freshworks — base.html, admin/base_site.html
    "euc-widget.freshworks.com",
    # Google Analytics (gtag) — google_analytics.html, tylko gdy skonfigurowane
    "www.googletagmanager.com",
)

# Tag ładujący asset z bezwzględnego URL-a. Nie używamy `"host" in text`, bo
# substringowe sprawdzanie literału-hosta odpala fałszywy alarm CodeQL
# `py/incomplete-url-substring-sanitization` (heurystyka bierze je za
# obejściopodatną sanityzację URL-a) — patrz test_admin_fonts_selfhosted.py.
_TAG_RE = re.compile(
    r"""<(?:script|link)\b[^>]*?\b(?:src|href)\s*=\s*["']?(https?://[^"'\s>]+)""",
    re.IGNORECASE,
)

# Literał URL-a wskazujący na plik-asset — wzorzec dla plików .py (`class Media`).
# Zawężenie do rozszerzeń assetów odsiewa linki dokumentacyjne w docstringach
# i adresy stron zewnętrznych, które z ładowaniem zasobów nie mają nic wspólnego.
_LITERAL_ASSET_RE = re.compile(
    r"""["'](https?://[^"'\s]+\.(?:js|css|woff2?|ttf|eot|svg|png|gif|jpe?g))["']""",
    re.IGNORECASE,
)

# Komentarze blokowe Django `{# ... #}` wycinamy przed skanem szablonów, żeby
# wzmianka o CDN-ie w komentarzu (np. „wcześniej był tu unpkg") nie była
# fałszywym alarmem.
_KOMENTARZ_DJANGO_RE = re.compile(r"\{#.*?#\}", re.DOTALL)


def _dozwolony(url: str) -> bool:
    return any(host in url for host in DOZWOLONE_HOSTY)


def _szablony():
    """Wszystkie szablony Django w src/ (katalogi `templates/`)."""
    return sorted(SRC.glob("*/templates/**/*.html"))


def _moduly_python():
    """Wszystkie moduły Pythona w src/, poza migracjami i staticroot.

    Skanujemy nie tylko `admin.py` — `class Media` bywa też w `forms.py`
    i `widgets.py`.
    """
    return sorted(
        p
        for p in SRC.glob("*/**/*.py")
        if "/migrations/" not in str(p) and "/staticroot/" not in str(p)
    )


def test_szablony_nie_laduja_assetow_z_cdn():
    """Żaden szablon nie ma `<script src>` ani `<link href>` z bezwzględnym URL-em
    spoza allow-listy."""
    winowajcy = []
    for szablon in _szablony():
        tresc = _KOMENTARZ_DJANGO_RE.sub("", szablon.read_text(encoding="utf-8"))
        for url in _TAG_RE.findall(tresc):
            if not _dozwolony(url):
                winowajcy.append(f"{szablon.relative_to(SRC)}: {url}")

    assert not winowajcy, (
        "Assety ładowane z zewnętrznego CDN-a w szablonach:\n  "
        + "\n  ".join(winowajcy)
        + "\n\nZvendoruj bibliotekę (dodaj do package.json, zbierze ją YarnFinder) "
        "i użyj {% static '...' %}, albo — jeśli to usługa SaaS, której nie da "
        "się self-hostować — dopisz host do DOZWOLONE_HOSTY z uzasadnieniem."
    )


def test_klasy_media_nie_laduja_assetow_z_cdn():
    """Żaden moduł Pythona (m.in. `class Media` w adminie) nie wskazuje na plik
    assetu pod bezwzględnym URL-em spoza allow-listy."""
    winowajcy = []
    for modul in _moduly_python():
        if modul.resolve() == Path(__file__).resolve():
            continue  # ten plik z definicji zawiera wzorce URL-i
        for url in _LITERAL_ASSET_RE.findall(modul.read_text(encoding="utf-8")):
            if not _dozwolony(url):
                winowajcy.append(f"{modul.relative_to(SRC)}: {url}")

    assert not winowajcy, (
        "Assety ładowane z zewnętrznego CDN-a w kodzie Pythona:\n  "
        + "\n  ".join(winowajcy)
        + "\n\nW `class Media` podaj ścieżkę WZGLĘDNĄ do statików "
        "(np. 'foundation-datepicker/foundation/fonts/foundation-icons.css'), "
        "a bibliotekę zvendoruj przez package.json."
    )
