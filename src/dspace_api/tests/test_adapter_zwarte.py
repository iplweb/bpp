import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_adapter_zwarte_book():
    from dspace_api.adapters.wydawnictwo_zwarte import WydawnictwoZwarteDSpaceAdapter

    rec = baker.make(
        "bpp.Wydawnictwo_Zwarte",
        tytul_oryginalny="Książka",
        rok=2023,
        isbn="978-83-000-0000-0",
    )
    d = WydawnictwoZwarteDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.title"][0]["value"] == "Książka"
    assert d["dc.identifier.isbn"][0]["value"] == "978-83-000-0000-0"
    assert d["dc.type"][0]["value"] == "book"
