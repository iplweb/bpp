from unittest import mock

import pytest
from model_bakery import baker


@pytest.fixture
def fernet_key(settings):
    from cryptography.fernet import Fernet

    settings.DSPACE_CREDENTIALS_KEY = Fernet.generate_key().decode()


@pytest.mark.django_db
def test_wachlarz_jedna_skonfigurowana_druga_nie(fernet_key):
    from dspace_api.eksport import eksportuj_rekord
    from dspace_api.models import Mapowanie_DSpace

    u1 = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u1.dspace_api_endpoint = "https://repo1/server/api"
    u1.save()
    u2 = baker.make("bpp.Uczelnia", dspace_aktywny=False)  # nieaktywna

    j1 = baker.make("bpp.Jednostka", uczelnia=u1)
    j2 = baker.make("bpp.Jednostka", uczelnia=u2)
    charakter = baker.make("bpp.Charakter_Formalny")
    rec = baker.make(
        "bpp.Wydawnictwo_Ciagle",
        tytul_oryginalny="T",
        rok=2024,
        charakter_formalny=charakter,
    )
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j1, kolejnosc=0)
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j2, kolejnosc=1)

    Mapowanie_DSpace.objects.create(
        uczelnia=u1,
        charakter_formalny=charakter,
        collection_uuid="66666666-6666-6666-6666-666666666666",
    )

    with mock.patch("dspace_api.eksport.DSpaceClient") as ClientCls:
        client = ClientCls.return_value
        client.create_item.return_value = "77777777-7777-7777-7777-777777777777"

        wyniki = eksportuj_rekord(rec)

    by_uczelnia = {w["uczelnia"]: w for w in wyniki}
    assert by_uczelnia[u1]["status"] == "wyslano"
    assert by_uczelnia[u2]["status"] == "pominieto"


@pytest.mark.django_db
def test_brak_mapowania_pomija_z_powodem(fernet_key):
    from dspace_api.eksport import eksportuj_rekord

    u = baker.make("bpp.Uczelnia", dspace_aktywny=True)
    u.dspace_api_endpoint = "https://repo/server/api"
    u.save()
    j = baker.make("bpp.Jednostka", uczelnia=u)
    rec = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="T", rok=2024)
    baker.make("bpp.Wydawnictwo_Ciagle_Autor", rekord=rec, jednostka=j, kolejnosc=0)

    wyniki = eksportuj_rekord(rec)
    assert wyniki[0]["status"] == "pominieto"
    assert "mapowani" in wyniki[0]["powod"].lower()
