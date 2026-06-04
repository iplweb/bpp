"""Testy poprawności wielouczelnianej (multi-hosted) dla BppPBNClient.

Dowodzą, że orchestracja czyta konfigurację z ``self.uczelnia`` (uczelni,
z której zbudowano klienta), a NIE z ``Uczelnia.objects.get_default()``
(pierwszej-z-brzegu). Te testy failowałyby przed Fazą 3B.

Patrz: docs/superpowers/specs/2026-06-02-pbn-client-split-design.md
"""

from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_api.client import BppPBNClient
from pbn_api.tests.utils import MockTransport


@pytest.mark.django_db
def test_pre_upload_clear_uzywa_flagi_z_wlasnej_uczelni_nie_get_default():
    """``_pre_upload_clear`` wybiera batch/selective wg ``self.uczelnia``.

    uczelnia_a (pierwsza, ``get_default()``) ma ``selektywnie=True``;
    uczelnia_b (ta, z której zbudowano klienta) ma ``selektywnie=False``.
    Klient MUSI wybrać batch DELETE (wg b), nie selective (wg a).
    """
    uczelnia_a = baker.make(Uczelnia, pbn_kasuj_dyscypliny_selektywnie=True)
    uczelnia_b = baker.make(Uczelnia, pbn_kasuj_dyscypliny_selektywnie=False)

    # Multi-hosted: są DWIE uczelnie, więc NIE ma „jedynej" do zgadnięcia —
    # klient MUSI użyć swojej (uczelnia_b), nie pierwszej-z-brzegu.
    assert Uczelnia.objects.get_single_uczelnia_or_none() is None
    assert uczelnia_a != uczelnia_b

    client = BppPBNClient(MockTransport(), uczelnia=uczelnia_b)
    client.get_institution_statements_of_single_publication = MagicMock(
        return_value=[
            {"id": "x", "personId": "p1", "area": "301", "type": "AUTHOR"}
        ]
    )
    client._delete_statements_selective = MagicMock()
    client._delete_statements_batch = MagicMock()

    rec = MagicMock(pbn_uid_id="PBN-UID-123", pk=42)
    client._pre_upload_clear_pbn_statements_if_any(rec)

    # uczelnia_b: selektywnie=False -> BATCH. Gdyby kod używał get_default()
    # (=uczelnia_a, True) -> SELECTIVE. To jest sedno multi-hosted.
    client._delete_statements_batch.assert_called_once()
    client._delete_statements_selective.assert_not_called()


@pytest.mark.django_db
def test_dwoch_klientow_czyta_wlasne_flagi_niezaleznie():
    """Dwa klienty związane z różnymi uczelniami czytają swoje flagi."""
    uczelnia_selektywna = baker.make(
        Uczelnia, pbn_kasuj_dyscypliny_selektywnie=True
    )
    uczelnia_batch = baker.make(Uczelnia, pbn_kasuj_dyscypliny_selektywnie=False)

    statements = [{"id": "x", "personId": "p1", "area": "301", "type": "AUTHOR"}]

    for uczelnia, expect_batch in (
        (uczelnia_selektywna, False),
        (uczelnia_batch, True),
    ):
        client = BppPBNClient(MockTransport(), uczelnia=uczelnia)
        client.get_institution_statements_of_single_publication = MagicMock(
            return_value=list(statements)
        )
        client._delete_statements_selective = MagicMock()
        client._delete_statements_batch = MagicMock()

        client._pre_upload_clear_pbn_statements_if_any(
            MagicMock(pbn_uid_id="PBN-UID-1", pk=1)
        )

        assert client._delete_statements_batch.called is expect_batch
        assert client._delete_statements_selective.called is not expect_batch
