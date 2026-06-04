import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_adapter_ciagle_metadata():
    from dspace_api.adapters.wydawnictwo_ciagle import WydawnictwoCiagleDSpaceAdapter

    jezyk = baker.make("bpp.Jezyk", skrot="pl")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="Tytuł pracy",
        rok=2024,
        jezyk=jezyk,
    )
    baker.make(
        "bpp.Wydawnictwo_Ciagle_Streszczenie",
        rekord=rec,
        streszczenie="Streszczenie pracy",
    )
    d = WydawnictwoCiagleDSpaceAdapter(rec).to_dspace_dict()

    assert d["dc.title"][0]["value"] == "Tytuł pracy"
    assert d["dc.date.issued"][0]["value"] == "2024"
    assert d["dc.description.abstract"][0]["value"] == "Streszczenie pracy"
    assert d["dc.language.iso"][0]["value"] == "pl"
    assert d["dc.type"][0]["value"] == "article"


@pytest.mark.django_db
def test_adapter_ciagle_authors():
    from dspace_api.adapters.wydawnictwo_ciagle import WydawnictwoCiagleDSpaceAdapter

    rec = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="X", rok=2024)
    autor = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, autor=autor, kolejnosc=0)

    d = WydawnictwoCiagleDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.contributor.author"][0]["value"] == "Kowalski, Jan"
