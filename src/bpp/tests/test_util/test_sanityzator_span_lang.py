"""Allowlista sanityzatora opisu bibliograficznego po dopuszczeniu ``span``.

Opis powstaje z (niezaufanego) tytułu i jest renderowany ``|safe`` na
publicznych stronach, więc rozszerzenie allowlisty musi być wąskie:
``lang`` jest deklaratywny (nie wykonuje kodu, nie ładuje zasobów), ale
``style``/``class``/``on*`` na ``span`` nadal muszą wylatywać.
"""

from bpp.util import safe_opis_bibliograficzny_html


def test_span_z_lang_przechodzi():
    wynik = safe_opis_bibliograficzny_html('<span lang="en">Effects</span>')
    assert wynik == '<span lang="en">Effects</span>'


def test_span_z_kodem_regionalnym_przechodzi():
    wynik = safe_opis_bibliograficzny_html('<span lang="en-GB">Colour</span>')
    assert 'lang="en-GB"' in wynik


def test_span_zachowuje_zagniezdzona_kursywe():
    wynik = safe_opis_bibliograficzny_html(
        '<span lang="en">Role of <i>Candida</i></span>'
    )
    assert "<i>Candida</i>" in wynik
    assert 'lang="en"' in wynik


def test_span_traci_atrybut_style():
    wynik = safe_opis_bibliograficzny_html(
        '<span style="position:fixed;top:0">X</span>'
    )
    assert "style" not in wynik
    assert "<span>X</span>" in wynik


def test_span_traci_atrybut_class():
    wynik = safe_opis_bibliograficzny_html('<span class="evil">X</span>')
    assert "class" not in wynik


def test_span_traci_atrybut_zdarzenia():
    wynik = safe_opis_bibliograficzny_html(
        '<span onmouseover="alert(1)" lang="en">X</span>'
    )
    assert "onmouseover" not in wynik
    assert "alert" not in wynik
    assert 'lang="en"' in wynik


def test_script_nadal_usuwany_wraz_z_trescia():
    wynik = safe_opis_bibliograficzny_html(
        '<span lang="en">Tytuł</span><script>alert(1)</script>'
    )
    assert "<script" not in wynik
    assert "alert(1)" not in wynik


def test_link_autora_nadal_dziala():
    # Regresja: rozszerzenie allowlisty nie może zepsuć wariantu z linkami.
    wynik = safe_opis_bibliograficzny_html('<a href="/bpp/autor/1/">Kowalski Jan</a>')
    assert 'href="/bpp/autor/1/"' in wynik


def test_tag_spoza_allowlisty_nadal_usuwany():
    wynik = safe_opis_bibliograficzny_html("<div>blok</div>")
    assert "<div>" not in wynik
    assert "blok" in wynik
