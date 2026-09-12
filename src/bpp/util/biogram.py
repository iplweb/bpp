"""Renderowanie biogramu autora do bezpiecznego HTML.

Autor podaje biogram w jednym z dwóch formatów: Markdown (``md``) albo HTML
(``html``). Niezależnie od formatu wynik przechodzi przez ``safe_html`` (nh3),
więc istnieje dokładnie jeden punkt sanityzacji — niemożliwe jest wyrenderowanie
niezaufanego HTML-a z pominięciem czyszczenia.
"""

import markdown as _markdown

from bpp.util.text import safe_biogram_html

FORMAT_MARKDOWN = "md"
FORMAT_HTML = "html"

FORMATY_BIOGRAMU = (
    (FORMAT_MARKDOWN, "Markdown"),
    (FORMAT_HTML, "HTML"),
)


def renderuj_biogram(tekst, format):
    """Zwróć bezpieczny HTML biogramu.

    Dla ``md`` najpierw renderuje Markdown do HTML, następnie sanityzuje. Dla
    każdego innego formatu (w tym ``html``) sanityzuje wejście wprost — to
    bezpieczny domyślny wybór, bo nigdy nie przepuszcza surowego HTML-a bez
    czyszczenia.
    """
    if not tekst:
        return ""

    if format == FORMAT_MARKDOWN:
        tekst = _markdown.markdown(tekst)

    return safe_biogram_html(tekst)
