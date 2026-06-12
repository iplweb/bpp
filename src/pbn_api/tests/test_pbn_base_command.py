"""Testy rozwiązywania uczelni/credentiali PBN w PBNBaseCommand (CLI).

Reguła multi-hosted dla komend CLI:
- ``--uczelnia-id`` zawsze honorowane,
- przy DOKŁADNIE jednej uczelni w systemie używamy jej automatycznie
  (get_default() jest OK tylko w tym jednym przypadku),
- przy wielu uczelniach brak ``--uczelnia-id`` to błąd (CommandError) —
  bez cichego wyboru pierwszej-z-brzegu.
"""

import pytest
from django.core.management import CommandError

from bpp.models import Uczelnia
from pbn_api.management.commands.util import PBNBaseCommand


def _second_uczelnia(**kwargs):
    from django.contrib.sites.models import Site

    site, _ = Site.objects.get_or_create(
        domain="druga.example.com", defaults={"name": "druga"}
    )
    return Uczelnia.objects.create(skrot="DR", nazwa="Druga", site=site, **kwargs)


def _blank_options(**over):
    opts = {
        "uczelnia_id": None,
        "app_id": None,
        "app_token": None,
        "base_url": None,
        "user_token": None,
    }
    opts.update(over)
    return opts


@pytest.mark.django_db
def test_single_uczelnia_used_without_flag(uczelnia):
    uczelnia.pbn_app_name = "APP-A"
    uczelnia.pbn_app_token = "TOK-A"
    uczelnia.pbn_api_root = "https://a.example/"
    uczelnia.save()

    options = _blank_options()
    PBNBaseCommand()._fill_pbn_credentials(options)

    assert options["app_id"] == "APP-A"
    assert options["app_token"] == "TOK-A"
    assert options["base_url"] == "https://a.example/"


@pytest.mark.django_db
def test_multiple_uczelnie_without_flag_raises(uczelnia):
    _second_uczelnia()

    with pytest.raises(CommandError):
        PBNBaseCommand()._fill_pbn_credentials(_blank_options())


@pytest.mark.django_db
def test_explicit_uczelnia_id_selects_it(uczelnia):
    uczelnia.pbn_app_name = "APP-A"
    uczelnia.pbn_app_token = "TOK-A"
    uczelnia.save()
    u2 = _second_uczelnia(
        pbn_app_name="APP-B",
        pbn_app_token="TOK-B",
        pbn_api_root="https://b.example/",
    )

    options = _blank_options(uczelnia_id=u2.pk)
    PBNBaseCommand()._fill_pbn_credentials(options)

    assert options["app_id"] == "APP-B"
    assert options["app_token"] == "TOK-B"
    assert options["base_url"] == "https://b.example/"


@pytest.mark.django_db
def test_unknown_uczelnia_id_raises(uczelnia):
    with pytest.raises(CommandError):
        PBNBaseCommand()._fill_pbn_credentials(_blank_options(uczelnia_id=999999))
