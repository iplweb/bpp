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


@pytest.mark.django_db
def test_adapter_patent_numer_i_data_zgloszenia():
    import datetime

    from dspace_api.adapters.patent import PatentDSpaceAdapter

    if not Jezyk.objects.filter(nazwa__icontains="polski").exists():
        baker.make(Jezyk, nazwa="polski")

    rec = baker.make(
        "bpp.Patent",
        tytul_oryginalny="Wynalazek",
        rok=2022,
        numer_zgloszenia="P.123",
        data_zgloszenia=datetime.date(2021, 3, 4),
        numer_prawa_wylacznego="PL12345",
    )
    d = PatentDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.identifier"][0]["value"] == "PL12345"
    assert d["dc.identifier.other"][0]["value"] == "P.123"
    assert d["dc.date.submitted"][0]["value"] == "2021-03-04"
    assert d["dc.date.issued"][0]["value"] == "2022"


@pytest.mark.django_db
def test_adapter_patent_tylko_zgloszenie_bez_dubla():
    from dspace_api.adapters.patent import PatentDSpaceAdapter

    if not Jezyk.objects.filter(nazwa__icontains="polski").exists():
        baker.make(Jezyk, nazwa="polski")

    rec = baker.make(
        "bpp.Patent",
        tytul_oryginalny="Wynalazek",
        numer_zgloszenia="P.123",
        numer_prawa_wylacznego="",
        data_zgloszenia=None,
    )
    d = PatentDSpaceAdapter(rec).to_dspace_dict()
    assert d["dc.identifier"][0]["value"] == "P.123"
    assert "dc.identifier.other" not in d
    assert "dc.date.submitted" not in d
