"""Ekstrakcja streszczeń (abstract / streszczenie) z body HTML."""

from bs4 import BeautifulSoup

ABSTRACT_LABELS = {
    "abstract": "en",
    "streszczenie": "pl",
    "streszczenie w języku polskim": "pl",
    "streszczenie w języku angielskim": "en",
    "summary": "en",
}

MIN_ABSTRACT_LENGTH = 20


def _extract_body_abstracts(
    soup: BeautifulSoup,
) -> list[dict]:
    """Wyciągnij streszczenia z body HTML.

    Szuka nagłówków (h1-h6, dt, strong, b, label, th)
    pasujących do ABSTRACT_LABELS i pobiera tekst
    z następnego elementu rodzeństwa.
    """
    heading_tags = {"h1", "h2", "h3", "h4", "h5", "h6"}
    label_tags = {"strong", "b", "label"}
    all_tags = heading_tags | label_tags | {"dt", "th"}

    results = []
    seen_texts = set()

    for tag in soup.find_all(all_tags):
        text = tag.get_text(strip=True).lower()
        # Usuń dwukropek i białe znaki z końca
        text = text.rstrip(": \t")
        if text not in ABSTRACT_LABELS:
            continue

        language = ABSTRACT_LABELS[text]
        content = _get_abstract_content(tag)

        if not content or len(content) < MIN_ABSTRACT_LENGTH:
            continue

        # Deduplikacja po treści
        if content in seen_texts:
            continue
        seen_texts.add(content)

        results.append({"text": content, "language": language})

    return results


def _get_abstract_content(tag) -> str | None:
    """Pobierz tekst streszczenia z elementu."""
    tag_name = tag.name

    if tag_name == "dt":
        dd = tag.find_next_sibling("dd")
        if dd:
            return dd.get_text(strip=True)
        return None

    if tag_name == "th":
        return _get_th_content(tag)

    # h1-h6, strong, b, label
    sibling = tag.find_next_sibling()
    if sibling:
        return sibling.get_text(strip=True)

    # strong/b wewnatrz akapitu -- tekst po tagu
    if tag_name in {"strong", "b"}:
        return _get_inline_tag_trailing_text(tag)

    return None


def _get_th_content(tag) -> str | None:
    """Pobierz tekst z td obok th."""
    td = tag.find_next_sibling("td")
    if not td:
        # Sprobuj w tym samym wierszu
        tr = tag.parent
        if tr and tr.name == "tr":
            td = tr.find("td")
    if td:
        return td.get_text(strip=True)
    return None


def _get_inline_tag_trailing_text(tag) -> str | None:
    """Pobierz tekst po tagu strong/b w rodzicu."""
    parent = tag.parent
    if not parent:
        return None
    remaining = ""
    found_tag = False
    for child in parent.children:
        if child is tag:
            found_tag = True
            continue
        if found_tag:
            if hasattr(child, "get_text"):
                remaining += child.get_text(strip=True)
            else:
                remaining += str(child).strip()
    if remaining.strip():
        return remaining.strip()
    return None
