# -*- encoding: utf-8 -*-

import pytest
import time

from bpp.admin.helpers import MODEL_PUNKTOWANY_KOMISJA_CENTRALNA, MODEL_PUNKTOWANY
from bpp.models.system import Status_Korekty


@pytest.mark.django_db
def test_models_wydawnictwo_ciagle_dirty_fields_ostatnio_zmieniony_dla_pbn(wydawnictwo_ciagle, wydawnictwo_zwarte, autor_jan_nowak, jednostka, statusy_korekt):
    for wyd in wydawnictwo_ciagle, wydawnictwo_zwarte:
        ost_zm_pbn = wyd.ostatnio_zmieniony_dla_pbn

        time.sleep(0.5)

        wyd.status = Status_Korekty.objects.get(nazwa="w trakcie korekty")
        wyd.save()
        assert ost_zm_pbn == wyd.ostatnio_zmieniony_dla_pbn

        time.sleep(0.5)

        wyd.status = Status_Korekty.objects.get(nazwa="po korekcie")
        wyd.save()
        assert ost_zm_pbn == wyd.ostatnio_zmieniony_dla_pbn

        time.sleep(0.5)

        for fld in MODEL_PUNKTOWANY_KOMISJA_CENTRALNA + MODEL_PUNKTOWANY:
            setattr(wyd, fld, 123)
            wyd.save()
            assert ost_zm_pbn == wyd.ostatnio_zmieniony_dla_pbn
            time.sleep(0.5)

        wyd.tytul_oryginalny = "1234 test zmian"
        wyd.save()

        try:
            assert ost_zm_pbn != wyd.ostatnio_zmieniony_dla_pbn
        except TypeError:
            pass # TypeError: can't compare offset-naive and offset-aware datetimes

        time.sleep(0.5)

        ost_zm_pbn = wyd.ostatnio_zmieniony_dla_pbn

        aj = wyd.dodaj_autora(autor_jan_nowak, jednostka)
        wyd.refresh_from_db()
        assert ost_zm_pbn != wyd.ostatnio_zmieniony_dla_pbn

        ost_zm_pbn = wyd.ostatnio_zmieniony_dla_pbn

        aj.delete()
        wyd.refresh_from_db()
        assert ost_zm_pbn != wyd.ostatnio_zmieniony_dla_pbn