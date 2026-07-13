import re

import lxml.html
import nh3
from django.conf import settings
from django.utils.html import strip_tags
from unidecode import unidecode

non_url = re.compile(r"[^\w-]+")

strip_nonalpha_regex = re.compile(r"\W+")
strip_extra_spaces_regex = re.compile(r"\s\s+")


def strip_nonalphanumeric(s):
    """Usuń nie-alfanumeryczne znaki z ciągu znaków"""
    if s is None:
        return

    return strip_nonalpha_regex.sub(" ", s)


def strip_extra_spaces(s):
    if s is None:
        return

    return strip_extra_spaces_regex.sub("", s).strip()


def fulltext_tokenize(s):
    if s is None:
        return

    return [
        elem
        for elem in strip_extra_spaces(strip_nonalphanumeric(strip_tags(s))).split(" ")
        if elem
    ]


def strip_html(s):
    if not s:
        return s

    return lxml.html.fromstring(str(s)).text_content()


def slugify_function(s):
    s = unidecode(strip_html(s)).replace(" ", "-")
    while s.find("--") >= 0:
        s = s.replace("--", "-")
    return non_url.sub("", s)


def zrob_cache(t):
    zle_znaki = [
        " ",
        ":",
        ";",
        "-",
        ",",
        "-",
        ".",
        "(",
        ")",
        "?",
        "!",
        "ę",
        "ą",
        "ł",
        "ń",
        "ó",
        "ź",
        "ż",
    ]
    for znak in zle_znaki:
        t = t.replace(znak, "")
    return t.lower()


isbn_regex = re.compile(
    r"^isbn\s*[0-9]*[-| ][0-9]*[-| ][0-9]*[-| ][0-9]*[-| ][0-9]*X?",
    flags=re.IGNORECASE,
)


def wytnij_isbn_z_uwag(uwagi):
    if uwagi is None:
        return

    if uwagi == "":
        return

    if uwagi.lower().find("isbn-10") >= 0 or uwagi.lower().find("isbn-13") >= 0:
        return None

    res = isbn_regex.search(uwagi)
    if res:
        res = res.group()
        isbn = res.replace("ISBN", "").replace("isbn", "").strip()
        reszta = uwagi.replace(res, "").strip()

        while (
            reszta.startswith(".") or reszta.startswith(";") or reszta.startswith(",")
        ):
            reszta = reszta[1:].strip()

        return isbn, reszta


class safe_html_defaults:
    ALLOWED_TAGS = (
        "a",
        "abbr",
        "acronym",
        "b",
        "blockquote",
        "code",
        "em",
        "i",
        "li",
        "ol",
        "strong",
        "ul",
        "font",
        "div",
        "span",
        "br",
        "strike",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "p",
        "table",
        "tr",
        "td",
        "th",
        "thead",
        "tbody",
        "dl",
        "dd",
        "u",
    )

    ALLOWED_ATTRIBUTES = {
        "*": ["class"],
        "a": ["href", "title", "rel"],
        "abbr": ["title"],
        "acronym": ["title"],
        "font": [
            "face",
            "size",
        ],
        "div": [
            "style",
        ],
        "span": [
            "style",
        ],
        "ul": [
            "style",
        ],
    }


def safe_html(html):
    html = html or ""

    ALLOWED_TAGS = getattr(settings, "ALLOWED_TAGS", safe_html_defaults.ALLOWED_TAGS)
    ALLOWED_ATTRIBUTES = getattr(
        settings, "ALLOWED_ATTRIBUTES", safe_html_defaults.ALLOWED_ATTRIBUTES
    )
    return nh3.clean(
        html,
        tags=set(ALLOWED_TAGS),
        attributes={k: set(v) for k, v in ALLOWED_ATTRIBUTES.items()},
        clean_content_tags=set(),
        link_rel=None,
    )


# Litery greckie wpisywane przez autorów jako pseudo-znaczniki (``<beta>``,
# ``<Delta>``, ``<alfa>``) — to NIE jest HTML, tylko nazwa litery w nawiasach
# ostrokątnych. Bez konwersji sanitizer (nh3) wyrzuciłby je jako nieznany tag,
# gubiąc literę. Zamieniamy je na właściwy znak Unicode ZANIM zadziała nh3.
# Nazwa z wielkiej litery (``<Delta>``) → majuskuła (Δ) tam, gdzie majuskuła
# różni się wizualnie od łacińskiej; inaczej minuskuła.
_GREEK_LOWER = {
    "alfa": "α",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "epsilon": "ε",
    "zeta": "ζ",
    "eta": "η",
    "theta": "θ",
    "iota": "ι",
    "kappa": "κ",
    "lambda": "λ",
    "my": "μ",
    "mu": "μ",
    "ny": "ν",
    "nu": "ν",
    "ksi": "ξ",
    "xi": "ξ",
    "omikron": "ο",
    "omicron": "ο",
    "pi": "π",
    "rho": "ρ",
    "ro": "ρ",
    "sigma": "σ",
    "tau": "τ",
    "ypsilon": "υ",
    "upsilon": "υ",
    "ipsilon": "υ",
    "fi": "φ",
    "phi": "φ",
    "chi": "χ",
    "khi": "χ",
    "psi": "ψ",
    "omega": "ω",
}
_GREEK_UPPER = {
    # tylko majuskuły wizualnie różne od łacińskich
    "gamma": "Γ",
    "delta": "Δ",
    "theta": "Θ",
    "lambda": "Λ",
    "ksi": "Ξ",
    "xi": "Ξ",
    "pi": "Π",
    "sigma": "Σ",
    "fi": "Φ",
    "phi": "Φ",
    "psi": "Ψ",
    "omega": "Ω",
}
_PSEUDO_GREEK_RE = re.compile(
    r"<(" + "|".join(sorted(_GREEK_LOWER, key=len, reverse=True)) + r")>",
    re.IGNORECASE,
)


def zamien_pseudotagi_na_greke(text):
    """Zamień pseudo-znaczniki liter greckich (``<beta>`` → ``β``) na Unicode."""
    if not text or "<" not in text:
        return text or ""

    def _repl(m):
        name = m.group(1)
        low = name.lower()
        if name[:1].isupper() and low in _GREEK_UPPER:
            return _GREEK_UPPER[low]
        return _GREEK_LOWER.get(low, m.group(0))

    return _PSEUDO_GREEK_RE.sub(_repl, text)


class safe_tytul_defaults:
    # Tytuły publikacji: wyłącznie formatowanie inline typowe dla bibliografii —
    # kursywa (nazwy gatunków, obce zwroty), pogrubienie, indeks górny/dolny
    # (wzory: "H<sub>2</sub>O", "CD4<sup>+</sup>", "m<sup>2</sup>") i
    # podkreślenie. Bez linków, tabel, bloków i BEZ atrybutów — tytuł nie ma
    # powodu ich nieść, a ich brak dodatkowo domyka wektory (onerror, style).
    ALLOWED_TAGS = ("i", "em", "b", "strong", "sub", "sup", "u")


def safe_tytul_html(tytul):
    """Zwróć bezpieczny HTML tytułu publikacji.

    Zamiennik dla ``|safe`` przy tytułach (``tytul``/``tytul_oryginalny``),
    które bywają importowane z niezaufanych źródeł (WWW, zgłoszenia anonimowe)
    i renderowane w publicznych widokach. Escape'uje gołe operatory '<'/'>'
    (notacja matematyczna w tytule) i przepuszcza wynik przez nh3 z wąską
    allowlistą inline, usuwając ``<script>``, atrybuty zdarzeń i pozostały XSS.
    Pseudo-znaczniki liter greckich (``<beta>``) są wcześniej zamieniane na
    Unicode (β), a nie wyrzucane jak nieznany tag.

    Sanityzujemy WYŁĄCZNIE gdy tytuł zawiera ``<`` — inaczej zwracamy go bez
    zmian, żeby nh3 nie zakodował podwójnie ``&`` (korupcja danych w
    fulltext/eksporcie).
    """
    if not tytul or "<" not in tytul:
        return tytul

    html = zamien_pseudotagi_na_greke(tytul)
    html = _escape_bare_angle_brackets(html)

    ALLOWED_TAGS = getattr(
        settings, "TYTUL_ALLOWED_TAGS", safe_tytul_defaults.ALLOWED_TAGS
    )
    return nh3.clean(
        html,
        tags=set(ALLOWED_TAGS),
        attributes={},
        # Usuń także TREŚĆ tych tagów (nie tylko znaczniki), żeby w tytule nie
        # zostawał goły ``alert(1)`` po wyciętym ``<script>``.
        clean_content_tags={"script", "style"},
        link_rel=None,
    )


class safe_opis_bibliograficzny_defaults:
    # Opis bibliograficzny składa się z tytułu (sanityzowanego jak wyżej) oraz
    # inline'owego formatowania cytowania; w wariancie linkowanym niesie też
    # odnośniki autorów (``<a href>``). Dopuszczamy TE SAME tagi co tytuł plus
    # ``<a>`` z samym ``href``/``rel``/``title`` — bez tagów blokowych, bez
    # ``style``/``class`` i bez innych atrybutów.
    ALLOWED_TAGS = safe_tytul_defaults.ALLOWED_TAGS + ("a",)
    ALLOWED_ATTRIBUTES = {"a": ["href", "title", "rel"]}


def safe_opis_bibliograficzny_html(html):
    """Zwróć bezpieczny HTML opisu bibliograficznego.

    Opis jest budowany z (potencjalnie niezaufanego) tytułu i renderowany
    ``|safe`` na publicznych stronach oraz cache'owany w
    ``opis_bibliograficzny_cache``. Sanityzujemy wynik złożenia, żeby żaden
    ``<script>`` z tytułu nie przeżył — zachowując kursywę, sub/sup oraz
    odnośniki autorów (``<a href>``). Pseudo-znaczniki liter greckich
    (``<beta>``) są wcześniej zamieniane na Unicode (β).
    """
    html = zamien_pseudotagi_na_greke(html or "")
    html = _escape_bare_angle_brackets(html)
    ALLOWED_TAGS = getattr(
        settings,
        "OPIS_BIBLIOGRAFICZNY_ALLOWED_TAGS",
        safe_opis_bibliograficzny_defaults.ALLOWED_TAGS,
    )
    ALLOWED_ATTRIBUTES = getattr(
        settings,
        "OPIS_BIBLIOGRAFICZNY_ALLOWED_ATTRIBUTES",
        safe_opis_bibliograficzny_defaults.ALLOWED_ATTRIBUTES,
    )
    return nh3.clean(
        html,
        tags=set(ALLOWED_TAGS),
        attributes={k: set(v) for k, v in ALLOWED_ATTRIBUTES.items()},
        clean_content_tags={"script", "style"},
        link_rel=None,
    )


def sanitize_multiseek_title(value):
    """Sanityzuj tytuł raportu multiseek zapisywany do sesji.

    Wartość jest renderowana ``|safe`` w szablonie tytułu, więc musi być
    oczyszczona z XSS. Wspólne dla AJAX-owego ``update_multiseek_title`` i
    formularza wyszukiwania (``suggested-title``) — obie ścieżki piszą do
    ``session['MULTISEEK_TITLE']`` i muszą sanityzować tak samo.
    """
    if not value:
        return ""
    return nh3.clean(
        value.replace("\r\n", "\n").replace("\n", "<br/>"),
        tags=set(getattr(settings, "ALLOWED_TAGS", [])) | {"hr", "p", "br"},
        clean_content_tags=set(),
        link_rel=None,
    )


# Streszczenia (abstrakty) bywają importowane z zewnętrznych źródeł (Crossref,
# PBN) i mieszają prawdziwy markup (JATS/HTML) z matematycznymi operatorami
# porównania wpisanymi wprost w tekst ("<30 IU/dL", "ct<or ≥15K", ">= 1%").
# Pojedynczy "goły" '<' bez zamykającego '>' (np. "<30IU/dL ...") sprawia, że
# parser HTML — a w produkcji minifikator django-minify-html — połyka wszystko
# aż do następnego '>', niszcząc układ strony (regresja: tekst streszczenia
# pożerał prawą kolumnę rekordu i całość zlewała się w jedną kolumnę). Dlatego
# najpierw escape'ujemy gołe nawiasy ostrokątne, a dopiero potem czyścimy resztę
# sanitizerem nh3.
#
# Znacznik uznajemy za poprawny tylko gdy ma nazwę i zamykający '>' bez '<' w
# środku oraz albo NIE ma atrybutów (``<sup>``, ``</sup>``, ``<br/>``), albo
# zawiera prawdziwy atrybut z '=' (``<jats:italic toggle="yes">``). Proza typu
# ``<b and c>`` tych warunków nie spełnia, więc jej '<' trafia do encji zamiast
# otwierać element (brak fałszywego pogrubienia i utraty tekstu).
_WELL_FORMED_TAG_RE = re.compile(r"</?[a-zA-Z][\w:-]*(?:\s+[^<>]*=[^<>]*)?\s*/?>")


def _escape_bare_angle_brackets(text):
    """Escape '<'/'>' które nie tworzą poprawnego, domkniętego znacznika."""
    out = []
    pos = 0
    for m in _WELL_FORMED_TAG_RE.finditer(text):
        start, end = m.span()
        out.append(text[pos:start].replace("<", "&lt;").replace(">", "&gt;"))
        out.append(text[start:end])
        pos = end
    out.append(text[pos:].replace("<", "&lt;").replace(">", "&gt;"))
    return "".join(out)


class safe_streszczenie_defaults:
    # Te same tagi co `safe_html`, plus sub/sup typowe dla notacji naukowej
    # (np. "CD4<sup>+</sup>", "H<sub>2</sub>O", "m<sup>2</sup>").
    ALLOWED_TAGS = safe_html_defaults.ALLOWED_TAGS + ("sub", "sup")


def safe_streszczenie_html(html):
    """Zwróć bezpieczny, zbalansowany HTML streszczenia.

    1. Escape'uje gołe operatory porównania '<'/'>' z treści streszczenia, aby
       nie były interpretowane jako początek znacznika (i nie psuły układu
       strony w minifikatorze).
    2. Przepuszcza wynik przez nh3: usuwa niedozwolone tagi (w tym JATS,
       zachowując ich tekst) oraz potencjalny XSS, oddając poprawny HTML.
    """
    html = _escape_bare_angle_brackets(html or "")

    ALLOWED_TAGS = getattr(
        settings,
        "STRESZCZENIE_ALLOWED_TAGS",
        safe_streszczenie_defaults.ALLOWED_TAGS,
    )
    ALLOWED_ATTRIBUTES = getattr(
        settings, "ALLOWED_ATTRIBUTES", safe_html_defaults.ALLOWED_ATTRIBUTES
    )
    return nh3.clean(
        html,
        tags=set(ALLOWED_TAGS),
        attributes={k: set(v) for k, v in ALLOWED_ATTRIBUTES.items()},
        clean_content_tags=set(),
        link_rel=None,
    )
