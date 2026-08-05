"""Fixtures słownikowe.

Świeże bazy testowe ładują ``baseline-sql/baseline.sql``, który już zawiera
te słowniki (Typ_Odpowiedzialnosci ``aut.``, Charakter_Formalny ``PAT``,
Jezyk ``polski``, Status_Korekty ``przed korektą``). Dlatego ``get_or_create``,
nie ``baker.make`` — inaczej łamiemy unikalność (natural key już istnieje).
"""

import pytest


@pytest.fixture
def typ_odpowiedzialnosci_aut(db):
    from bpp.models import Typ_Odpowiedzialnosci

    obj, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="aut.", defaults={"nazwa": "autor"}
    )
    return obj


@pytest.fixture
def charakter_pat(db):
    from bpp.models import Charakter_Formalny

    obj, _ = Charakter_Formalny.objects.get_or_create(
        skrot="PAT", defaults={"nazwa": "Patent"}
    )
    return obj


@pytest.fixture
def jezyk_polski(db):
    from bpp.models import Jezyk

    obj, _ = Jezyk.objects.get_or_create(nazwa="polski", defaults={"skrot": "pol."})
    return obj


@pytest.fixture
def status_korekty(db):
    from bpp.models import Status_Korekty

    obj, _ = Status_Korekty.objects.get_or_create(nazwa="przed korektą")
    return obj
