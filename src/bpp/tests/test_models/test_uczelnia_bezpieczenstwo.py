from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from bpp.models import Uczelnia

POPRAWNY_SVG = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<svg xmlns="http://www.w3.org/2000/svg" '
    b'xmlns:xlink="http://www.w3.org/1999/xlink" width="10" height="10">'
    b'<defs><linearGradient id="g"/></defs>'
    b'<rect width="10" height="10" fill="url(#g)"/>'
    b'<use xlink:href="#g"/>'
    b'<a href="https://example.com/"><circle r="2"/></a>'
    b"</svg>"
)


def _svg(wnetrze, naglowek=b""):
    return (
        naglowek + b'<svg xmlns="http://www.w3.org/2000/svg" '
        b'xmlns:xlink="http://www.w3.org/1999/xlink">' + wnetrze + b"</svg>"
    )


NIEDOZWOLONE_SVG = [
    _svg(b"<script>alert(1)</script>"),
    _svg(b'<rect onload="alert(1)"/>'),
    _svg(b'<rect ONCLICK="alert(1)"/>'),
    _svg(b'<a href="javascript:alert(1)"><rect/></a>'),
    _svg(b'<a xlink:href=" javascript:alert(1)"><rect/></a>'),
    _svg(b"<foreignObject><div>x</div></foreignObject>"),
    _svg(b'<set attributeName="href" to="javascript:alert(1)"/>'),
    _svg(b"<rect/>", naglowek=b'<!DOCTYPE svg [<!ENTITY x "y">]>'),
    _svg(b"<rect/>", naglowek=b'<?xml-stylesheet href="x.xsl"?>'),
    _svg(b'<image href="data:image/svg+xml;base64,AAAA"/>'),
]


def _png(format="PNG"):
    buf = BytesIO()
    Image.new("RGB", (16, 16), "red").save(buf, format=format)
    return buf.getvalue()


@pytest.mark.django_db
def test_deklaracja_dostepnosci_url_z_niedozwolonym_schematem(uczelnia):
    uczelnia.pokazuj_deklaracje_dostepnosci = (
        Uczelnia.DeklaracjaDostepnosciChoices.ZEWNETRZNY_URL
    )
    uczelnia.deklaracja_dostepnosci_url = "javascript:alert(1)"
    with pytest.raises(ValidationError) as e:
        uczelnia.save()
    assert "deklaracja_dostepnosci_url" in e.value.message_dict


@pytest.mark.django_db
def test_deklaracja_dostepnosci_strona_nie_przekierowuje_na_zly_url(uczelnia, client):
    Uczelnia.objects.filter(pk=uczelnia.pk).update(
        pokazuj_deklaracje_dostepnosci=(
            Uczelnia.DeklaracjaDostepnosciChoices.ZEWNETRZNY_URL
        ),
        deklaracja_dostepnosci_url="javascript:alert(1)",
    )
    res = client.get(reverse("bpp:browse_deklaracja_dostepnosci"))
    body = res.content.decode()
    assert "location.href = 'javascript" not in body
    assert 'href="javascript:' not in body


@pytest.mark.django_db
def test_deklaracja_dostepnosci_url_escapejs(uczelnia, client):
    uczelnia.pokazuj_deklaracje_dostepnosci = (
        Uczelnia.DeklaracjaDostepnosciChoices.ZEWNETRZNY_URL
    )
    uczelnia.deklaracja_dostepnosci_url = "https://example.com/a'b"
    uczelnia.save()
    res = client.get(reverse("bpp:browse_deklaracja_dostepnosci"))
    body = res.content.decode()
    assert "location.href = 'https://example.com/a\\u0027b'" in body


@pytest.mark.django_db
def test_logo_svg_poprawne_przechodzi(uczelnia):
    uczelnia.logo_svg = SimpleUploadedFile("logo.svg", POPRAWNY_SVG)
    uczelnia.save()
    uczelnia.refresh_from_db()
    with uczelnia.logo_svg.open("rb") as f:
        assert f.read() == POPRAWNY_SVG


@pytest.mark.django_db
@pytest.mark.parametrize("tresc", NIEDOZWOLONE_SVG)
def test_logo_svg_z_aktywna_trescia_odrzucone(uczelnia, tresc):
    uczelnia.logo_svg = SimpleUploadedFile("logo.svg", tresc)
    with pytest.raises(ValidationError) as e:
        uczelnia.save()
    assert "logo_svg" in e.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize(
    "nazwa,tresc",
    [
        ("logo.html", POPRAWNY_SVG),
        ("logo.svg", b"to nie jest xml"),
        ("logo.svg", b'<html xmlns="http://www.w3.org/1999/xhtml"/>'),
    ],
)
def test_logo_svg_niepoprawny_plik_odrzucony(uczelnia, nazwa, tresc):
    uczelnia.logo_svg = SimpleUploadedFile(nazwa, tresc)
    with pytest.raises(ValidationError) as e:
        uczelnia.save()
    assert "logo_svg" in e.value.message_dict


@pytest.mark.django_db
@pytest.mark.parametrize(
    "nazwa,format", [("favicon.png", "PNG"), ("favicon.ico", "ICO")]
)
def test_favicon_poprawny_przechodzi(uczelnia, nazwa, format):
    uczelnia.favicon_ico = SimpleUploadedFile(nazwa, _png(format))
    uczelnia.save()
    uczelnia.refresh_from_db()
    assert uczelnia.favicon_ico.name


@pytest.mark.django_db
@pytest.mark.parametrize(
    "nazwa,tresc",
    [
        ("favicon.ico", b"<html><script>alert(1)</script></html>"),
        ("favicon.png", POPRAWNY_SVG),
        ("favicon.html", _png()),
        ("favicon.png", _png("GIF")),
    ],
)
def test_favicon_nie_obraz_odrzucony(uczelnia, nazwa, tresc):
    uczelnia.favicon_ico = SimpleUploadedFile(nazwa, tresc)
    with pytest.raises(ValidationError) as e:
        uczelnia.save()
    assert "favicon_ico" in e.value.message_dict


@pytest.mark.django_db
def test_zapis_bez_zmiany_plikow_nie_waliduje_ponownie(uczelnia):
    Uczelnia.objects.filter(pk=uczelnia.pk).update(logo_svg="logo_svg/stare.svg")
    uczelnia.refresh_from_db()
    uczelnia.nazwa = "Zmieniona"
    uczelnia.save()
