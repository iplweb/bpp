"""Audyt bezpieczeństwa: stored XSS w publicznym rankingu autorów.

``render_autor`` wstawiał nazwę autora do ``<a>`` i oznaczał całość jako
bezpieczny HTML. Nazwisko autora (potencjalnie z importu bez sanityzacji)
zawierające markup trafiało wtedy nieescapowane na PUBLICZNĄ, anonimową
stronę rankingu.
"""

from types import SimpleNamespace

import pytest
from model_bakery import baker

from ranking_autorow.views import RankingAutorowTable


@pytest.mark.django_db
def test_render_autor_escapuje_html_w_nazwisku():
    autor = baker.make(
        "bpp.Autor",
        nazwisko="<img src=x onerror=alert(1)>",
        imiona="Jan",
    )
    html = str(RankingAutorowTable([]).render_autor(SimpleNamespace(autor=autor)))

    # Payload zescapowany, a nie wstrzyknięty jako żywy tag.
    assert "<img" not in html
    assert "&lt;img" in html
    # Link (href z reverse()) nadal jest prawdziwym markupem.
    assert html.startswith("<a ")
