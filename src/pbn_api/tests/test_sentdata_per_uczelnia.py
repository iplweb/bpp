"""Testy izolacji SentData per-uczelnia (Track 4 audytu multi-hosted).

Klucz wysyłki do PBN to ``(object_id, content_type, uczelnia)`` — dwie uczelnie
wysyłające ten sam rekord BPP do swoich profili PBN dostają DWA niezależnie
tagowane wiersze SentData, bez współdzielenia stanu wysyłki.
"""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from pbn_api.models import SentData


@pytest.fixture
def uczelnia2(db):
    """Druga uczelnia (multi-hosted) — niezależna od fixture ``uczelnia``."""
    return baker.make(Uczelnia, skrot="U2", nazwa="Druga uczelnia")


@pytest.mark.django_db
def test_get_for_rec_per_uczelnia(uczelnia, uczelnia2, wydawnictwo_ciagle):
    rec = wydawnictwo_ciagle
    d1 = {"type": "ARTICLE", "title": "dla U1"}
    d2 = {"type": "ARTICLE", "title": "dla U2"}

    SentData.objects.create_or_update_before_upload(rec, d1, uczelnia=uczelnia)
    SentData.objects.create_or_update_before_upload(rec, d2, uczelnia=uczelnia2)

    assert SentData.objects.count() == 2
    assert SentData.objects.get_for_rec(rec, uczelnia).data_sent == d1
    assert SentData.objects.get_for_rec(rec, uczelnia2).data_sent == d2


@pytest.mark.django_db
def test_mark_successful_izolacja(uczelnia, uczelnia2, wydawnictwo_ciagle):
    rec = wydawnictwo_ciagle
    d = {"type": "ARTICLE", "title": "x"}

    SentData.objects.create_or_update_before_upload(rec, d, uczelnia=uczelnia)
    SentData.objects.create_or_update_before_upload(rec, d, uczelnia=uczelnia2)

    SentData.objects.mark_as_successful(rec, uczelnia=uczelnia)

    assert SentData.objects.get_for_rec(rec, uczelnia).uploaded_okay is True
    # Wysyłka U1 NIE może zmienić stanu U2 (brak współdzielenia wiersza).
    assert SentData.objects.get_for_rec(rec, uczelnia2).uploaded_okay is False


@pytest.mark.django_db
def test_check_if_upload_needed_per_uczelnia(uczelnia, uczelnia2, wydawnictwo_ciagle):
    rec = wydawnictwo_ciagle
    d = {"type": "ARTICLE", "title": "x"}

    SentData.objects.create_or_update_before_upload(rec, d, uczelnia=uczelnia)
    SentData.objects.mark_as_successful(rec, uczelnia=uczelnia)

    # U1 ma identyczne dane wysłane pomyślnie → nie trzeba ponawiać.
    assert SentData.objects.check_if_upload_needed(rec, d, uczelnia=uczelnia) is False
    # U2 jeszcze NIC nie wysłała → trzeba wysłać (mimo że U1 już wysłała te dane).
    assert SentData.objects.check_if_upload_needed(rec, d, uczelnia=uczelnia2) is True


@pytest.mark.django_db
def test_bad_uploads_per_uczelnia(uczelnia, uczelnia2, wydawnictwo_ciagle):
    from bpp.models import Wydawnictwo_Ciagle

    rec = wydawnictwo_ciagle
    d = {"type": "ARTICLE", "title": "x"}

    # U1: wysyłka OK; U2: wysyłka nieudana.
    SentData.objects.create_or_update_before_upload(rec, d, uczelnia=uczelnia)
    SentData.objects.mark_as_successful(rec, uczelnia=uczelnia)

    SentData.objects.create_or_update_before_upload(rec, d, uczelnia=uczelnia2)
    SentData.objects.mark_as_failed(rec, exception="boom", uczelnia=uczelnia2)

    bad_u1 = list(SentData.objects.bad_uploads(Wydawnictwo_Ciagle, uczelnia=uczelnia))
    bad_u2 = list(SentData.objects.bad_uploads(Wydawnictwo_Ciagle, uczelnia=uczelnia2))

    # Bad upload U2 nie może pojawić się w bad_uploads dla U1.
    assert rec.pk not in bad_u1
    assert rec.pk in bad_u2


@pytest.mark.django_db
def test_single_install_global_lookup_bez_uczelni(uczelnia, wydawnictwo_ciagle):
    """Single-install: jeden wiersz, lookup bez uczelni (legacy) działa."""
    rec = wydawnictwo_ciagle
    d = {"type": "ARTICLE", "title": "x"}

    SentData.objects.create_or_update_before_upload(rec, d, uczelnia=uczelnia)
    # Lookup bez uczelni zwraca jedyny wiersz (zachowanie globalne dla 1 wiersza).
    assert SentData.objects.get_for_rec(rec).data_sent == d
    # Lookup z uczelnią zwraca ten sam wiersz.
    assert SentData.objects.get_for_rec(rec, uczelnia).data_sent == d


@pytest.mark.django_db
def test_backfill_logic_single_install(uczelnia, wydawnictwo_ciagle):
    """Single-install: NULL-owy wiersz dostaje jedyną uczelnię (jak w 0072).

    Lustro logiki migracji ``0072_backfill_sentdata_uczelnia`` — jeśli
    zachowanie migracji się zmieni, ten test musi się zmienić razem z nią.
    """
    rec = wydawnictwo_ciagle
    # Wiersz wprost z uczelnia=None (legacy/untagged).
    SentData.objects.create_or_update_before_upload(
        rec, {"type": "ARTICLE"}, uczelnia=None
    )
    assert SentData.objects.filter(uczelnia__isnull=True).count() == 1

    # Symulacja backfillu z migracji (1 uczelnia → update NULL → tę uczelnię).
    assert Uczelnia.objects.count() == 1
    jedyna = Uczelnia.objects.get()
    SentData.objects.filter(uczelnia__isnull=True).update(uczelnia=jedyna)

    assert SentData.objects.filter(uczelnia__isnull=True).count() == 0
    assert SentData.objects.get_for_rec(rec, jedyna).uczelnia_id == jedyna.pk


@pytest.mark.django_db
def test_backfill_logic_multi_install_leaves_null(
    uczelnia, uczelnia2, wydawnictwo_ciagle
):
    """Multi-install (≥2 uczelnie): backfill NIE rusza NULL-owych wierszy.

    Lustro logiki migracji ``0072_backfill_sentdata_uczelnia`` — jeśli
    zachowanie migracji się zmieni, ten test musi się zmienić razem z nią.
    """
    rec = wydawnictwo_ciagle
    SentData.objects.create_or_update_before_upload(
        rec, {"type": "ARTICLE"}, uczelnia=None
    )

    # Warunek migracji: count != 1 → brak update. Przy ≥2 uczelniach migracja
    # świadomie zostawia NULL-owe wiersze (self-healing przy następnej wysyłce).
    assert Uczelnia.objects.count() == 2

    # NULL-owy wiersz pozostaje nietknięty.
    assert SentData.objects.filter(uczelnia__isnull=True).count() == 1
