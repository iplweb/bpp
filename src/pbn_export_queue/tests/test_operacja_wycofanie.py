"""Faza 05 soft-delete: wycofanie oświadczeń dyscyplin z PBN.

Soft-delete publikacji, która poszła do PBN, musi wycofać jej oświadczenia
z profilu instytucji. Realizuje to nowa operacja ``WYCOFANIE`` w kolejce
eksportu, obok dotychczasowej ``WYSYLKA``.
"""

import pytest
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue


@pytest.mark.django_db
def test_operacja_default_wysylka(wydawnictwo_ciagle, admin_user):
    """Wpisy sprzed fazy 05 (i wszystkie tworzone bez jawnej operacji)
    muszą nadal znaczyć „wyślij" — inaczej migracja zamieniłaby zaległą
    kolejkę wysyłek w kolejkę wycofań."""
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
    )
    wpis.refresh_from_db()
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYSYLKA
    assert PBN_Export_Queue.Operacja.WYSYLKA == "wysylka"
    assert PBN_Export_Queue.Operacja.WYCOFANIE == "wycofanie"


@pytest.mark.django_db
def test_sentdata_mark_as_withdrawn(wydawnictwo_ciagle, uczelnia):
    """Wycofanie zostawia ślad, przywrócenie go kasuje.

    Wiersza SentData NIE kasujemy: zostaje dla re-matchingu przy restore
    i dla SoftDeleteLog fazy 06. Znacznik ``withdrawn_at`` odróżnia „nigdy
    nie wysłane" od „wysłane, potem wycofane" — sam
    ``submitted_successfully=False`` tych dwóch stanów nie rozróżnia.

    Izolację per-uczelnia sprawdza osobno
    ``pbn_api/tests/test_sentdata_per_uczelnia.py`` (tam mieszka fixture
    ``uczelnia2`` i reszta rodzeństwa tego zachowania).
    """
    from pbn_api.models.sentdata import SentData

    SentData.objects.create(
        object=wydawnictwo_ciagle,
        data_sent={},
        submitted_successfully=True,
        uploaded_okay=True,
        uczelnia=uczelnia,
    )

    SentData.objects.mark_as_withdrawn(wydawnictwo_ciagle, uczelnia=uczelnia)

    sd = SentData.objects.get_for_rec(wydawnictwo_ciagle, uczelnia)
    assert sd.submitted_successfully is False
    assert sd.withdrawn_at is not None

    # restore → ponowna wysyłka zeruje znacznik wycofania
    SentData.objects.mark_as_successful(wydawnictwo_ciagle, uczelnia=uczelnia)
    sd = SentData.objects.get_for_rec(wydawnictwo_ciagle, uczelnia)
    assert sd.submitted_successfully is True
    assert sd.withdrawn_at is None
