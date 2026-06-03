import pytest
from model_bakery import baker


@pytest.mark.django_db
@pytest.mark.parametrize(
    "model,expected_type",
    [
        ("bpp.Wydawnictwo_Ciagle", "article"),
        ("bpp.Wydawnictwo_Zwarte", "book"),
        ("bpp.Patent", "patent"),
        ("bpp.Praca_Doktorska", "doctoralThesis"),
        ("bpp.Praca_Habilitacyjna", "Thesis"),
    ],
)
def test_adapter_for(model, expected_type):
    from dspace_api.adapters import adapter_for

    rec = baker.make(model, tytul_oryginalny="X", rok=2024)
    adapter = adapter_for(rec)
    assert adapter.dc_type == expected_type


@pytest.mark.django_db
def test_adapter_for_nieobslugiwany():
    from dspace_api.adapters import adapter_for

    rec = baker.make("bpp.Autor")
    with pytest.raises(ValueError):
        adapter_for(rec)
