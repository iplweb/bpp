"""Sanityzacja tytułów publikacji (XSS) z zachowaniem formatowania inline."""

import pytest
from django.template import Context, Template
from model_bakery import baker

from bpp.util import safe_tytul_html


def test_safe_tytul_strips_script():
    out = safe_tytul_html("<script>alert(1)</script>Tytuł pracy")
    assert "<script>" not in out
    assert "alert(1)" not in out
    assert "Tytuł pracy" in out


def test_safe_tytul_keeps_italic_and_bold():
    out = safe_tytul_html("<i>Genus species</i> oraz <b>ważne</b>")
    assert "<i>Genus species</i>" in out
    assert "<b>ważne</b>" in out


def test_safe_tytul_keeps_sub_and_sup():
    out = safe_tytul_html("H<sub>2</sub>O oraz CD4<sup>+</sup>")
    assert "<sub>2</sub>" in out
    assert "<sup>+</sup>" in out


def test_safe_tytul_strips_attributes():
    # Nawet na dozwolonym tagu — zero atrybutów (kill onerror/class/style).
    out = safe_tytul_html('<i onmouseover="alert(1)" class="x">a</i>')
    assert "onmouseover" not in out
    assert "class" not in out
    assert "<i>a</i>" in out


def test_safe_tytul_strips_img_onerror():
    out = safe_tytul_html("<img src=x onerror=alert(document.cookie)>")
    assert "<img" not in out
    assert "onerror" not in out


def test_safe_tytul_strips_links():
    out = safe_tytul_html('<a href="javascript:alert(1)">klik</a>')
    assert "<a" not in out
    assert "javascript" not in out
    assert "klik" in out


def test_safe_tytul_escapes_bare_less_than():
    # Notacja matematyczna w tytule nie może pożreć układu strony.
    out = safe_tytul_html("Wartości <30 jednostek")
    assert "&lt;30" in out
    assert "<30" not in out


def test_safe_tytul_puste_bez_zmian():
    # Brak '<' → zwracamy wejście bez mutacji (None/'' bez zmian, '&' nietknięty).
    assert safe_tytul_html(None) is None
    assert safe_tytul_html("") == ""
    assert safe_tytul_html("Rak & terapia (100%)") == "Rak & terapia (100%)"


def test_safe_tytul_filter_in_template_blocks_xss():
    tpl = Template("{% load prace %}{{ t|safe_tytul }}")
    rendered = tpl.render(Context({"t": "<script>alert(1)</script><i>ok</i>"}))
    assert "<script>" not in rendered
    assert "alert(1)" not in rendered
    assert "<i>ok</i>" in rendered


def test_safe_tytul_konwertuje_pseudotagi_greckie():
    assert safe_tytul_html("17<beta>-estradiol") == "17β-estradiol"
    # Wielka litera → majuskuła grecka.
    assert "Δ" in safe_tytul_html("<Delta><sup>2</sup>-triazoline")
    # Kombinacja: greka + XSS + kursywa.
    out = safe_tytul_html("<alfa> <script>x</script><i>ok</i>")
    assert out.startswith("α")
    assert "<script>" not in out
    assert "<i>ok</i>" in out


def test_safe_opis_zachowuje_linki_autorow_i_tnie_xss():
    from bpp.util import safe_opis_bibliograficzny_html

    out = safe_opis_bibliograficzny_html(
        '<a href="/autor/x">Kowalski J</a> <i>Nature</i> <script>alert(1)</script>'
    )
    assert '<a href="/autor/x">Kowalski J</a>' in out
    assert "<i>Nature</i>" in out
    assert "<script>" not in out
    assert "alert(1)" not in out


@pytest.mark.django_db
def test_zapis_tytulu_sanityzuje_u_zrodla(wydawnictwo_ciagle):
    """save() (a więc też objects.create()/import) czyści tytuł u źródła."""
    wydawnictwo_ciagle.tytul_oryginalny = (
        "<script>alert(1)</script><i>Genus</i> 17<beta>-estradiol"
    )
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.refresh_from_db()
    t = wydawnictwo_ciagle.tytul_oryginalny
    assert "<script>" not in t
    assert "alert(1)" not in t
    assert "<i>Genus</i>" in t
    assert "β" in t


@pytest.mark.django_db
def test_browse_praca_page_sanitizes_title_xss(client, wydawnictwo_ciagle):
    """End-to-end na PUBLICZNEJ stronie rekordu: złośliwy tytuł nie może
    wyrenderować aktywnego ``<script>``, a legalna kursywa ma przetrwać."""
    from denorm import denorms
    from django.contrib.contenttypes.models import ContentType
    from django.urls import reverse

    baker.make("bpp.Uczelnia")
    wydawnictwo_ciagle.tytul_oryginalny = (
        "<script>alert(1)</script><i>Genus species</i>"
    )
    wydawnictwo_ciagle.save()
    denorms.flush()

    ct = ContentType.objects.get(app_label="bpp", model="wydawnictwo_ciagle")
    res = client.get(
        reverse("bpp:browse_praca", args=(ct.pk, wydawnictwo_ciagle.pk)),
        follow=True,
    )
    assert res.status_code == 200
    body = res.content.decode()
    # Żaden aktywny <script> z tytułu — ani bezpośrednio, ani przez
    # zdenormalizowany opis_bibliograficzny_cache.
    assert "<script>alert(1)" not in body
    assert "<script>alert(1)</script>" not in body
    # Legalna kursywa (nazwa gatunku) przetrwała.
    assert "<i>Genus species</i>" in body
