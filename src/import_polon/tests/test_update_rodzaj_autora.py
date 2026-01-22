"""
Tests for _update_rodzaj_autora function.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina
from import_polon.core.import_polon import _update_rodzaj_autora


@pytest.mark.django_db
def test_update_rodzaj_autora_none_with_jest_w_n(
    dyscyplina1, rodzaj_autora_n, rodzaj_autora_z, rodzaj_autora_b
):
    """Test that when rodzaj_autora is None and jest_w_n_xlsx=True, it is set to N."""
    autor = baker.make(Autor)
    ad = baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        rok=2023,
        rodzaj_autora=None,
    )

    ops, zmieniony = _update_rodzaj_autora(
        ad, jest_w_n_xlsx=True, jest_badawczy_xlsx=False
    )

    assert zmieniony is True
    assert ad.rodzaj_autora == rodzaj_autora_n
    assert len(ops) == 1
    assert "Ustawiam rodzaj autora" in ops[0]


@pytest.mark.django_db
def test_update_rodzaj_autora_none_with_jest_badawczy(
    dyscyplina1, rodzaj_autora_n, rodzaj_autora_z, rodzaj_autora_b
):
    """Test that when rodzaj_autora is None and jest_badawczy_xlsx=True, it is set to B."""
    autor = baker.make(Autor)
    ad = baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        rok=2023,
        rodzaj_autora=None,
    )

    ops, zmieniony = _update_rodzaj_autora(
        ad, jest_w_n_xlsx=False, jest_badawczy_xlsx=True
    )

    assert zmieniony is True
    assert ad.rodzaj_autora == rodzaj_autora_b
    assert len(ops) == 1
    assert "Ustawiam rodzaj autora" in ops[0]


@pytest.mark.django_db
def test_update_rodzaj_autora_none_without_flags(
    dyscyplina1, rodzaj_autora_n, rodzaj_autora_z, rodzaj_autora_b
):
    """Test that when rodzaj_autora is None and no flags set, it defaults to Z."""
    autor = baker.make(Autor)
    ad = baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        rok=2023,
        rodzaj_autora=None,
    )

    ops, zmieniony = _update_rodzaj_autora(
        ad, jest_w_n_xlsx=False, jest_badawczy_xlsx=False
    )

    assert zmieniony is True
    assert ad.rodzaj_autora == rodzaj_autora_z
    assert len(ops) == 1
    assert "Ustawiam rodzaj autora" in ops[0]


@pytest.mark.django_db
def test_update_rodzaj_autora_none_jest_w_n_takes_priority(
    dyscyplina1, rodzaj_autora_n, rodzaj_autora_z, rodzaj_autora_b
):
    """Test that jest_w_n_xlsx=True takes priority over jest_badawczy_xlsx=True."""
    autor = baker.make(Autor)
    ad = baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        rok=2023,
        rodzaj_autora=None,
    )

    ops, zmieniony = _update_rodzaj_autora(
        ad, jest_w_n_xlsx=True, jest_badawczy_xlsx=True
    )

    assert zmieniony is True
    assert ad.rodzaj_autora == rodzaj_autora_n
    assert len(ops) == 1
