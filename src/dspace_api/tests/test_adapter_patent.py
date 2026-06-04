import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_adapter_patent():
    from dspace_api.adapters.patent import PatentDSpaceAdapter

    rec = baker.make(
        "bpp.Patent",
        tytul_oryginalny="Wynalazek",
        rok=2022,
        numer_prawa_wylacznego="PL12345",
    )
    d = PatentDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.title"][0]["value"] == "Wynalazek"
    assert d["dc.type"][0]["value"] == "patent"
    assert d["dc.identifier"][0]["value"] == "PL12345"
