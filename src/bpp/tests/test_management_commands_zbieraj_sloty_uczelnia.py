"""Testy multi-hosted dla komendy ``zbieraj_sloty`` (audyt follow-up B2).

Kontrakt do zablokowania:
(a) ``Autor.zbieraj_sloty`` przekazuje ``uczelnia_id`` do funkcji
    ``bpp.core.zbieraj_sloty`` (scope per-uczelnia).
(b) Komenda CLI: gdy >1 uczelnia i brak ``--uczelnia`` -> ``CommandError``
    (bez cichego wyboru pierwszej-z-brzegu).
"""

from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker


@pytest.mark.django_db
def test_autor_zbieraj_sloty_przekazuje_uczelnia_id():
    autor = baker.make("bpp.Autor")
    with patch("bpp.models.autor.zbieraj_sloty") as m:
        m.return_value = (0, [])
        autor.zbieraj_sloty(4, 2017, 2020, uczelnia_id=123)
    assert m.call_args.kwargs["uczelnia_id"] == 123


@pytest.mark.django_db
def test_command_wiele_uczelni_bez_flagi_to_commanderror():
    autor = baker.make("bpp.Autor")
    baker.make("bpp.Uczelnia")
    baker.make("bpp.Uczelnia")

    with pytest.raises(CommandError):
        call_command("zbieraj_sloty", autor.pk)


@pytest.mark.django_db
def test_command_jedna_uczelnia_nie_wymaga_flagi():
    autor = baker.make("bpp.Autor")
    baker.make("bpp.Uczelnia")

    with patch("bpp.models.autor.zbieraj_sloty") as m:
        m.return_value = (0, [])
        # Komenda kończy się sys.exit(0) przy braku --xls; łapiemy SystemExit,
        # liczy się tylko że NIE poleciał CommandError "podaj --uczelnia".
        with pytest.raises(SystemExit):
            call_command("zbieraj_sloty", autor.pk)

    assert m.call_args.kwargs["uczelnia_id"] is not None
