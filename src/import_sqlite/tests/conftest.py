import pytest
from model_bakery import baker


@pytest.fixture
def typ_odpowiedzialnosci_aut(db):
    return baker.make("bpp.Typ_Odpowiedzialnosci", skrot="aut.", nazwa="autor")


@pytest.fixture
def charakter_pat(db):
    return baker.make("bpp.Charakter_Formalny", skrot="PAT", nazwa="Patent")


@pytest.fixture
def jezyk_polski(db):
    return baker.make("bpp.Jezyk", nazwa="polski", skrot="pol.")


@pytest.fixture
def status_korekty(db):
    return baker.make("bpp.Status_Korekty", nazwa="przed korektą")
