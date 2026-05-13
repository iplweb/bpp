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
