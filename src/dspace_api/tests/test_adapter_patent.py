import pytest
from model_bakery import baker

from bpp.models.system import Jezyk


@pytest.mark.django_db
def test_adapter_patent():
    from dspace_api.adapters.patent import PatentDSpaceAdapter

    # Patent.jezyk to @cached_property: Jezyk.objects.get(nazwa__icontains="polski").
    # Test nie może polegać na danych referencyjnych baseline — inny test
    # transakcyjny potrafi je wyczyścić, co daje order-zależny flake przy
    # przetasowaniu shardów (pytest-split). Zapewnij dokładnie jeden "polski"
    # Jezyk: dotwórz TYLKO gdy brak (inaczej baseline + nowy => MultipleObjectsReturned).
    if not Jezyk.objects.filter(nazwa__icontains="polski").exists():
        baker.make(Jezyk, nazwa="polski")

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
