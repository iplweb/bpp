import pytest
from django.urls.base import reverse

from django.utils.http import urlencode

from bpp.models.autor import Autor


def test_search_field(autor_jan_kowalski):
    assert Autor.objects.all()[0].search is not None


@pytest.mark.django_db
def test_tokenizer_minus(wydawnictwo_zwarte, client):
    wydawnictwo_zwarte.tytul_oryginalny = "ewaluacja 2017-2020"
    wydawnictwo_zwarte.save()

    base_url = reverse("bpp:navigation-autocomplete")
    url = base_url + "?" + urlencode({"q": "2017-2020"})
    res = client.get(url)
    assert b"ewaluacja" in res.content

    url = base_url + "?" + urlencode({"q": "-2020"})
    res = client.get(url)
    assert b"ewaluacja" in res.content


def test_fulltext_search_mixin(autor_jan_kowalski):
    res = Autor.objects.fulltext_filter("kowalski jan")
    assert autor_jan_kowalski in res


@pytest.mark.django_db
def test_fulltext_search_removes_space_dash_space(wydawnictwo_zwarte, client):
    """Test that ' - ' (space-dash-space) is removed from search queries"""
    wydawnictwo_zwarte.tytul_oryginalny = "Uniwersytet Medyczny Lublin"
    wydawnictwo_zwarte.save()

    base_url = reverse("bpp:navigation-autocomplete")
    # Search with ' - ' should find the publication
    url = base_url + "?" + urlencode({"q": "Uniwersytet - Medyczny"})
    res = client.get(url)
    assert b"Uniwersytet Medyczny" in res.content

    # Should work the same as without ' - '
    url = base_url + "?" + urlencode({"q": "Uniwersytet Medyczny"})
    res2 = client.get(url)
    assert b"Uniwersytet Medyczny" in res2.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "s",
    [
        "śmierć",
        "śmierć",
        "pas ternak'",
        "paste rnak''",
        "past ernak\\",
        "pastern ak\\'",
        "past ernak'",
        "past ernak &",
        "pa sternak (",
        "!paster nak",
        "paste rnak)",
        "&",
        "& &",
        "()",
        "!!",
        "!",
        ")()()(\\\\!@!!@@!#!@",
        "   ()(*(*$(*#  oiad  9*(*903498985398)()(||| aosid  p p    ",
    ],
)
def test_global_nav_search(client, s):
    url = reverse("bpp:navigation-autocomplete")
    url += "?" + urlencode({"q": s})
    res = client.get(url)
    assert res.status_code == 200
