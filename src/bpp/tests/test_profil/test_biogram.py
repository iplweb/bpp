"""Testy renderowania biogramu autora (Markdown/HTML → bezpieczny HTML).

Biogram używa własnego, bogatszego zestawu dozwolonych tagów niż globalny
``safe_html`` (który jest celowo wąski) — autor potrzebuje akapitów, nagłówków,
list i linków.
"""

from bpp.util.biogram import renderuj_biogram


def test_markdown_pogrubienie():
    assert "<strong>ala</strong>" in renderuj_biogram("**ala**", "md")


def test_markdown_naglowek_i_lista():
    out = renderuj_biogram("## Tytul\n\n- raz\n- dwa", "md")
    assert "<h2>" in out
    assert "<li>raz</li>" in out


def test_html_przepuszcza_dozwolone_tagi():
    out = renderuj_biogram("<p>tekst <b>pogrubiony</b></p>", "html")
    assert "<p>tekst <b>pogrubiony</b></p>" in out


def test_html_usuwa_skrypt_wraz_z_trescia():
    out = renderuj_biogram("<script>alert(1)</script><p>ok</p>", "html")
    assert "script" not in out
    assert "alert(1)" not in out
    assert "<p>ok</p>" in out


def test_markdown_usuwa_wstrzykniety_html():
    out = renderuj_biogram("**a** <script>alert(1)</script>", "md")
    assert "script" not in out
    assert "alert(1)" not in out
    assert "<strong>a</strong>" in out


def test_link_dostaje_rel_nofollow():
    out = renderuj_biogram('<a href="http://example.com">x</a>', "html")
    assert 'href="http://example.com"' in out
    assert "nofollow" in out
    assert "noopener" in out


def test_link_javascript_wycina_schemat():
    out = renderuj_biogram('<a href="javascript:alert(1)">x</a>', "html")
    assert "javascript:" not in out


def test_pusty_biogram_daje_pusty_string():
    assert renderuj_biogram("", "md") == ""
    assert renderuj_biogram(None, "html") == ""


def test_nieznany_format_traktowany_jak_html():
    # Bezpieczny fallback: nieznany format nie renderuje Markdowna,
    # tylko sanityzuje wejście jako HTML.
    out = renderuj_biogram("**x** <script>bad</script>", "cokolwiek")
    assert "script" not in out
    assert "**x**" in out
