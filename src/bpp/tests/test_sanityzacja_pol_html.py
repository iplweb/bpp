"""Sanityzacja pól HTML renderowanych na publicznych stronach.

Pola ``informacje``/``szczegoly``/``uwagi`` rekordów, ``Jednostka.opis``
oraz teksty ``Uczelnia`` muszą być czyszczone przy zapisie (także przez
``objects.create()``, z pominięciem ``full_clean()``) i przy renderze (dla
danych zapisanych wcześniej, np. przez ``QuerySet.update()``).
"""

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import Jednostka, Uczelnia, Wydawnictwo_Ciagle
from bpp.templatetags.prace import safe_opis, safe_szczegoly
from bpp.util import safe_opis_html, sanityzuj_jesli_html

NIEBEZPIECZNY = "<script>zly()</script><i>x</i>"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model_name",
    ["Wydawnictwo_Ciagle", "Wydawnictwo_Zwarte", "Patent"],
)
@pytest.mark.parametrize("field", ["informacje", "szczegoly", "uwagi"])
def test_pola_szczegolow_sanityzowane_przy_zapisie(model_name, field):
    from bpp import models as m

    obj = baker.make(getattr(m, model_name), **{field: NIEBEZPIECZNY})
    obj.refresh_from_db()

    value = getattr(obj, field)
    assert "<script" not in value
    assert "<i>x</i>" in value


@pytest.mark.django_db
def test_pola_szczegolow_objects_create(typy_odpowiedzialnosci):
    obj = baker.make(Wydawnictwo_Ciagle)
    nowy = Wydawnictwo_Ciagle.objects.create(
        tytul_oryginalny="Tytuł",
        rok=obj.rok,
        charakter_formalny=obj.charakter_formalny,
        jezyk=obj.jezyk,
        status_korekty=obj.status_korekty,
        typ_kbn=obj.typ_kbn,
        szczegoly=NIEBEZPIECZNY,
    )
    nowy.refresh_from_db()
    assert "<script" not in nowy.szczegoly
    assert "<i>x</i>" in nowy.szczegoly


@pytest.mark.django_db
def test_pola_szczegolow_bez_znacznikow_bez_zmian():
    obj = baker.make(Wydawnictwo_Ciagle, szczegoly="s. 1-2 & 3", informacje="")
    obj.refresh_from_db()
    assert obj.szczegoly == "s. 1-2 & 3"
    assert obj.informacje == ""


@pytest.mark.django_db
def test_jednostka_opis_sanityzowany_przy_zapisie():
    j = baker.make(
        Jednostka,
        opis='<p onclick="x()">Opis <a href="javascript:x()">l</a></p>'
        "<script>zly()</script><ul><li><strong>a</strong></li></ul>",
    )
    j.refresh_from_db()
    assert "<script" not in j.opis
    assert "zly()" not in j.opis
    assert "onclick" not in j.opis
    assert "javascript:" not in j.opis
    assert "<ul><li><strong>a</strong></li></ul>" in j.opis
    assert "<p>" in j.opis


@pytest.mark.django_db
def test_jednostka_opis_none_zostaje_none():
    j = baker.make(Jednostka, opis=None)
    j.refresh_from_db()
    assert j.opis is None


@pytest.mark.django_db
def test_jednostka_opis_sanityzowany_w_clean():
    j = baker.prepare(Jednostka, opis=NIEBEZPIECZNY)
    j.clean()
    assert "<script" not in j.opis
    assert "<i>x</i>" in j.opis


@pytest.mark.django_db
def test_uczelnia_teksty_sanityzowane_przy_zapisie(uczelnia):
    uczelnia.tytul_strony_glownej = "<b>Bibliografia</b><script>zly()</script>"
    uczelnia.deklaracja_dostepnosci_tekst = (
        '<h1>Deklaracja</h1><img src="x.png" onerror="zly()">'
    )
    uczelnia.save()
    uczelnia.refresh_from_db()
    assert "<script" not in uczelnia.tytul_strony_glownej
    assert "<b>Bibliografia</b>" in uczelnia.tytul_strony_glownej
    assert "onerror" not in uczelnia.deklaracja_dostepnosci_tekst
    assert "<h1>Deklaracja</h1>" in uczelnia.deklaracja_dostepnosci_tekst


def test_safe_opis_html_zachowuje_formatowanie_tinymce():
    wynik = safe_opis_html(
        '<p style="text-align: center; position: fixed">'
        '<a href="https://example.com/">l</a></p>'
    )
    assert "text-align:center" in wynik
    assert "position" not in wynik
    assert 'href="https://example.com/"' in wynik


def test_filtry_renderu():
    assert "<script" not in safe_szczegoly(NIEBEZPIECZNY)
    assert "<i>x</i>" in safe_szczegoly(NIEBEZPIECZNY)
    assert "<script" not in safe_opis(NIEBEZPIECZNY)
    assert safe_opis(None) == ""
    assert safe_szczegoly("a & b") == "a & b"
    assert sanityzuj_jesli_html(None) is None


@pytest.mark.django_db
def test_strona_rekordu_sanityzuje_stare_dane(client, wydawnictwo_ciagle):
    baker.make(Uczelnia)
    Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).update(
        szczegoly=NIEBEZPIECZNY, informacje=NIEBEZPIECZNY
    )
    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    res = client.get(
        reverse("bpp:browse_praca", args=(ct.pk, wydawnictwo_ciagle.pk)),
        follow=True,
    )
    assert res.status_code == 200
    assert b"<script>zly()" not in res.content
    assert b"<i>x</i>" in res.content


@pytest.mark.django_db
def test_strona_jednostki_sanityzuje_stare_dane(client, uczelnia, jednostka):
    Jednostka.objects.filter(pk=jednostka.pk).update(
        opis=NIEBEZPIECZNY, pokazuj_opis=True
    )
    res = client.get(reverse("bpp:browse_jednostka", args=(jednostka.slug,)))
    assert res.status_code == 200
    assert b"<script>zly()" not in res.content
    assert b"<i>x</i>" in res.content


@pytest.mark.django_db
def test_strony_uczelni_sanityzuja_stare_dane(client, uczelnia):
    Uczelnia.objects.filter(pk=uczelnia.pk).update(
        tytul_strony_glownej="<b>Tytul</b><script>zly()</script>",
        pokazuj_deklaracje_dostepnosci=Uczelnia.DeklaracjaDostepnosciChoices.TEKST,
        deklaracja_dostepnosci_tekst="<p>Dekl</p><script>zly()</script>",
    )
    res = client.get("/", follow=True)
    assert b"<script>zly()" not in res.content
    assert b"<b>Tytul</b>" in res.content

    res = client.get(reverse("bpp:browse_deklaracja_dostepnosci"))
    assert b"<script>zly()" not in res.content
    assert b"<p>Dekl</p>" in res.content
