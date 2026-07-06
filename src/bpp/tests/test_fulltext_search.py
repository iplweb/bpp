import pytest
from django.urls.base import reverse
from django.utils.http import urlencode
from model_bakery import baker

from bpp.models import Rekord, Wydawnictwo_Ciagle
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
def test_publication_fulltext_search_uses_weighted_cached_fields(
    autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_autor
):
    # typ_odpowiedzialnosci_autor jest wymagany jawnie: dodaj_autora robi
    # Typ_Odpowiedzialnosci.objects.get(skrot="aut."). Te dane pochodzą z
    # baseline, ale testy transakcyjne (transaction=True) czyszczą tabele
    # referencyjne bez ich odtworzenia — przy nieszczęśliwej kolejności
    # shardowania ten test trafiał na pustą tabelę. Fixture czyni go
    # samowystarczalnym.
    publication = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Neurokognitywny atlas markerowy",
        tytul="Neurocognitive marker atlas",
        rok=2031,
        doi="10.1234/BPP.FULLTEXT-ATLAS",
        szczegoly="Opis zawiera fraze neurodetektor",
    )
    publication.dodaj_autora(
        autor_jan_kowalski,
        jednostka,
        zapisany_jako="Kowalski Jan",
    )

    Rekord.objects.full_refresh()
    record = Rekord.objects.get_for_model(publication)

    queries = [
        "Neurokognitywny",
        "Neurokognitywny Kowalski",
        "Neurokognitywny 2031",
        "10.1234/BPP.FULLTEXT-ATLAS",
        "101234BPPFULLTEXTATLAS",
        "neurodetektor",
    ]

    for query in queries:
        assert record in Rekord.objects.fulltext_filter(query)


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
