import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_adapter_doktorska():
    from dspace_api.adapters.prace import PracaDoktorskaDSpaceAdapter

    autor = baker.make("bpp.Autor", nazwisko="Nowak", imiona="Anna")
    rec = baker.make(
        "bpp.Praca_Doktorska", tytul_oryginalny="Rozprawa", rok=2021, autor=autor
    )
    d = PracaDoktorskaDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.title"][0]["value"] == "Rozprawa"
    assert d["dc.type"][0]["value"] == "doctoralThesis"
    assert d["dc.contributor.author"][0]["value"] == "Nowak, Anna"


@pytest.mark.django_db
def test_adapter_habilitacyjna():
    from dspace_api.adapters.prace import PracaHabilitacyjnaDSpaceAdapter

    autor = baker.make("bpp.Autor", nazwisko="Lis", imiona="Ewa")
    rec = baker.make(
        "bpp.Praca_Habilitacyjna",
        tytul_oryginalny="Habilitacja",
        rok=2020,
        autor=autor,
    )
    d = PracaHabilitacyjnaDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.type"][0]["value"] == "Thesis"
    assert d["dc.contributor.author"][0]["value"] == "Lis, Ewa"
