import pytest
from django.contrib.contenttypes.models import ContentType
from django.template.loader import render_to_string
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.templatetags.bezpieczny_url import bezpieczny_url
from bpp.util.bezpieczny_url import czy_bezpieczny_link, oczysc_url_do_zapisu

ZLY_URL = "javascript:alert(1)"


@pytest.mark.parametrize(
    "url,oczekiwany",
    [
        ("https://example.com/", True),
        ("HTTP://example.com/", True),
        ("  https://example.com/", True),
        (ZLY_URL, False),
        (" JaVa\tScRiPt:alert(1)", False),
        ("\x01javascript:alert(1)", False),
        ("data:text/html,x", False),
        ("www.example.com", False),
        ("", False),
        (None, False),
    ],
)
def test_czy_bezpieczny_link(url, oczekiwany):
    assert czy_bezpieczny_link(url) is oczekiwany
    assert bool(bezpieczny_url(url)) is oczekiwany


@pytest.mark.parametrize(
    "url,oczekiwany",
    [
        ("https://example.com/", "https://example.com/"),
        ("ftp://example.com/plik", "ftp://example.com/plik"),
        ("www.example.com", "www.example.com"),
        ("www.example.com:8080/x", "www.example.com:8080/x"),
        (ZLY_URL, ""),
        ("java\nscript:alert(1)", ""),
        ("vbscript:x", ""),
        ("data:text/html,x", ""),
        ("", ""),
    ],
)
def test_oczysc_url_do_zapisu(url, oczekiwany):
    assert oczysc_url_do_zapisu(url) == oczekiwany


@pytest.mark.django_db
def test_objects_create_czysci_www(wydawnictwo_ciagle):
    """Ścieżka importerów: ``objects.create()`` bez ``full_clean()``."""
    nowy = Wydawnictwo_Ciagle.objects.create(
        tytul_oryginalny="Import",
        rok=2020,
        jezyk=wydawnictwo_ciagle.jezyk,
        charakter_formalny=wydawnictwo_ciagle.charakter_formalny,
        typ_kbn=wydawnictwo_ciagle.typ_kbn,
        status_korekty=wydawnictwo_ciagle.status_korekty,
        www=ZLY_URL,
        public_www=" javascript:alert(2)",
    )
    nowy.refresh_from_db()
    assert nowy.www == ""
    assert nowy.public_www == ""


@pytest.mark.django_db
def test_save_zachowuje_poprawne_www(wydawnictwo_ciagle):
    wydawnictwo_ciagle.www = "https://example.com/a"
    wydawnictwo_ciagle.public_www = "www.example.com"
    wydawnictwo_ciagle.save()
    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.www == "https://example.com/a"
    assert wydawnictwo_ciagle.public_www == "www.example.com"


@pytest.mark.django_db
@pytest.mark.parametrize("pole", ["www", "public_www"])
def test_strona_rekordu_nie_linkuje_zlego_www(client, wydawnictwo_ciagle, pole):
    from denorm import denorms

    baker.make("bpp.Uczelnia")
    Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).update(
        **{pole: ZLY_URL}
    )
    denorms.flush()

    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    res = client.get(
        reverse("bpp:browse_praca", args=(ct.pk, wydawnictwo_ciagle.pk)),
        follow=True,
    )
    assert res.status_code == 200
    body = res.content.decode()
    assert 'href="javascript:' not in body
    assert 'data-open-url="javascript:' not in body


@pytest.mark.django_db
def test_strona_rekordu_linkuje_poprawne_www(client, wydawnictwo_ciagle):
    from denorm import denorms

    baker.make("bpp.Uczelnia")
    Wydawnictwo_Ciagle.objects.filter(pk=wydawnictwo_ciagle.pk).update(
        www="https://example.com/praca"
    )
    denorms.flush()

    ct = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    res = client.get(
        reverse("bpp:browse_praca", args=(ct.pk, wydawnictwo_ciagle.pk)),
        follow=True,
    )
    assert res.status_code == 200
    assert "https://example.com/praca" in res.content.decode()


@pytest.mark.parametrize(
    "szablon,kontekst",
    [
        (
            "importer_publikacji/partials/step_review.html",
            lambda u: {
                "session": {"pk": 1},
                "data": {"title": "T", "url": u, "license_url": u},
            },
        ),
        (
            "importer_publikacji/partials/step_verify.html",
            lambda u: {
                "session": {
                    "pk": 1,
                    "normalized_data": {"url": u, "license_url": u},
                }
            },
        ),
    ],
)
def test_szablony_importera_nie_linkuja_zlego_url(szablon, kontekst):
    html = render_to_string(szablon, kontekst(ZLY_URL))
    assert 'href="javascript:' not in html

    html = render_to_string(szablon, kontekst("https://example.com/x"))
    assert 'href="https://example.com/x"' in html
