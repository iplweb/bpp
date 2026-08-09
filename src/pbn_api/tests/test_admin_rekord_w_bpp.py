"""Kolumna „rekord w BPP" na changeliście publikacji PBN.

Ta metoda admina nie miała ŻADNEGO pokrycia, a woła `.original` — atrybut
istniejący wyłącznie na `Rekord` (`bpp/models/cache/rekord.py`). Pierwsza
wersja fazy 03 zmieniła `rekord_w_bpp` tak, że zwracał model konkretny,
i wywalała `AttributeError` na CAŁEJ changeliście (~20 tys. rekordów).
Wyszło dopiero w recenzji.
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_changelist_publikacji_dziala_gdy_jest_powiazanie_z_bpp(admin_client):
    """Changelista nie może się wywalić, gdy publikacja PBN ma odpowiednik.

    To jest test na TYP zwracany przez `rekord_w_bpp`: admin buduje z niego
    link przez `.original`, więc każda zmiana typu musi tu zapalić czerwone.
    """
    from pbn_api.models import Publication

    publication = baker.make(Publication)
    baker.make(Wydawnictwo_Ciagle, pbn_uid=publication, rok=2020)

    res = admin_client.get("/admin/pbn_api/publication/")

    assert res.status_code == 200


@pytest.mark.django_db
def test_changelist_publikacji_dziala_gdy_odpowiednik_w_koszu(admin_client):
    """Po soft-delete odpowiednika changelista dalej działa.

    Rekordu wtedy NIE MA (`Rekord` jest odfiltrowany po `deleted_at`), więc
    kolumna ma pokazać link do importu zamiast linku do rekordu — a nie
    wywalić stronę.
    """
    from pbn_api.models import Publication

    publication = baker.make(Publication)
    wc = baker.make(Wydawnictwo_Ciagle, pbn_uid=publication, rok=2020)
    wc.delete()

    res = admin_client.get("/admin/pbn_api/publication/")

    assert res.status_code == 200
