"""Brak wydawcy w PBN nie może wywalać importu wydawnictwa zwartego.

Geneza (Rollbar, batch apoz.edu.pl 2026-06-29):
- #352 ``KeyError: 'publisher'`` (1789x) — książki (w tym EDITED_BOOK) bez
  wydawcy; parser robił ``pbn_json.pop("publisher")["id"]`` wprost,
- #417 ``KeyError: 'publisher'`` (4x) — to samo dla rozdziałów.

``wydawca`` jest polem NULLABLE (redagowane/self-published legalnie bywają bez
wydawcy — patrz decyzja projektowa: braki OPCJONALNE degradują, rekord wchodzi).
Ten test pilnuje, że książka bez ``publisher`` importuje się z ``wydawca=None``,
a nie wywala całego rekordu.

Test jedzie end-to-end przez ``importuj_publikacje_po_pbn_uid_id`` (dispatch +
``importuj_ksiazke``) na SYNTETYCZNYM payloadzie odwzorowującym #352 — dzięki
temu chroni jednocześnie łagodną degradację wydawcy ORAZ happy-path bramki
minimum-viable-record dla poprawnej książki.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Zwarte
from pbn_api.models import Publication
from pbn_integrator import importer


@pytest.mark.django_db
def test_importuj_edited_book_bez_publisher_wchodzi_bez_wydawcy():
    """EDITED_BOOK bez ``publisher`` (payload #352) → rekord z ``wydawca=None``."""
    baker.make(
        Publication,
        mongoId="b352",
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {
                    "type": "EDITED_BOOK",
                    "title": "Książka redagowana bez wydawcy",
                    "year": 2019,
                    "mainLanguage": "pol",
                },
            }
        ],
    )

    # client=None jest bezpieczne: bez autorów i bez publisher żadna ścieżka
    # nie sięga do klienta PBN.
    ret = importer.importuj_publikacje_po_pbn_uid_id(
        "b352", client=None, default_jednostka=None
    )

    assert ret is not None
    assert isinstance(ret, Wydawnictwo_Zwarte)
    assert ret.wydawca is None
    assert ret.tytul_oryginalny == "Książka redagowana bez wydawcy"
    assert ret.rok == 2019
    assert Wydawnictwo_Zwarte.objects.filter(pbn_uid_id="b352").count() == 1
