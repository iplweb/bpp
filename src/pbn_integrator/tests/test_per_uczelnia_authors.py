"""Tests for per-uczelnia affiliation comparison in _przetworz_afiliacje.

Verifies that _przetworz_afiliacje uses the explicitly-passed uczelnia
for affiliation matching instead of Uczelnia.objects.default.
"""

import pytest
from model_bakery import baker

from bpp.models import Jednostka, Typ_Odpowiedzialnosci, Uczelnia
from pbn_api.models import Institution


@pytest.fixture
def typ_autor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )[0]


@pytest.fixture
def typ_redaktor(db):
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="redaktor", defaults={"skrot": "red."}
    )[0]


def _make_uczelnia_with_pbn(db_marker):
    """Create a Uczelnia with a distinct Institution (pbn_uid) and obca_jednostka."""
    institution = baker.make(Institution)
    uczelnia = baker.make(Uczelnia, pbn_uid=institution)
    obca = baker.make(
        Jednostka,
        uczelnia=uczelnia,
        skupia_pracownikow=False,
    )
    uczelnia.obca_jednostka = obca
    uczelnia.save()
    return uczelnia


@pytest.fixture
def uczelnia1(db):
    return _make_uczelnia_with_pbn(db)


@pytest.fixture
def uczelnia2(db):
    return _make_uczelnia_with_pbn(db)


@pytest.fixture
def default_jednostka(uczelnia1):
    return baker.make(Jednostka, uczelnia=uczelnia1)


@pytest.mark.django_db
def test_afiliacja_matches_own_uczelnia(
    uczelnia1, uczelnia2, default_jednostka, typ_autor, typ_redaktor
):
    """Affiliation matching uczelnia1.pbn_uid_id → afiliuje=True, default_jednostka."""
    from pbn_integrator.importer.authors import _przetworz_afiliacje

    ta_afiliacja = [{"type": "AUTHOR", "institutionId": uczelnia1.pbn_uid_id}]

    jednostka, afiliuje, typ = _przetworz_afiliacje(
        ta_afiliacja=ta_afiliacja,
        default_jednostka=default_jednostka,
        typ_odpowiedzialnosci_autor=typ_autor,
        typ_odpowiedzialnosci_redaktor=typ_redaktor,
        uczelnia=uczelnia1,
    )

    assert afiliuje is True
    assert jednostka == default_jednostka
    assert typ == typ_autor


@pytest.mark.django_db
def test_afiliacja_foreign_when_different_uczelnia(
    uczelnia1, uczelnia2, default_jednostka, typ_autor, typ_redaktor
):
    """Same affiliation (uczelnia1 institutionId) processed with uczelnia2
    → afiliuje=False, returns uczelnia2.obca_jednostka."""
    from pbn_integrator.importer.authors import _przetworz_afiliacje

    ta_afiliacja = [{"type": "AUTHOR", "institutionId": uczelnia1.pbn_uid_id}]

    jednostka, afiliuje, typ = _przetworz_afiliacje(
        ta_afiliacja=ta_afiliacja,
        default_jednostka=default_jednostka,
        typ_odpowiedzialnosci_autor=typ_autor,
        typ_odpowiedzialnosci_redaktor=typ_redaktor,
        uczelnia=uczelnia2,
    )

    assert afiliuje is False
    assert jednostka == uczelnia2.obca_jednostka
    assert typ == typ_autor
