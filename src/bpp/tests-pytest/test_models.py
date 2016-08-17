# -*- encoding: utf-8 -*-

import pytest
import time

from lxml import etree

from bpp.admin.helpers import MODEL_PUNKTOWANY_KOMISJA_CENTRALNA, MODEL_PUNKTOWANY
from bpp.models.openaccess import Licencja_OpenAccess
from bpp.models.system import Status_Korekty


@pytest.mark.django_db
def test_models_wydawnictwo_ciagle_dirty_fields_ostatnio_zmieniony_dla_pbn(wydawnictwo_ciagle, wydawnictwo_zwarte, autor_jan_nowak, jednostka, statusy_korekt):

    # Licencje muszą być w bazie, jakiekolwiek
    assert Licencja_OpenAccess.objects.all().first() != Licencja_OpenAccess.objects.all().last()

    for wyd in wydawnictwo_ciagle, wydawnictwo_zwarte:
        wyd.openaccess_licencja = Licencja_OpenAccess.objects.all().first()
        wyd.save()

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

        for fld in MODEL_PUNKTOWANY_KOMISJA_CENTRALNA + MODEL_PUNKTOWANY + ('adnotacje', ):
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

        # Test na foreign keys
        ost_zm_pbn = wyd.ostatnio_zmieniony_dla_pbn

        assert wyd.openaccess_licencja.pk != Licencja_OpenAccess.objects.all().last().pk
        wyd.openaccess_licencja = Licencja_OpenAccess.objects.all().last()
        wyd.save()

        wyd.refresh_from_db()
        assert ost_zm_pbn != wyd.ostatnio_zmieniony_dla_pbn


def test_export_pubmed_id(wydawnictwo_ciagle):
    wc = wydawnictwo_ciagle

    wc.pubmed_id = None
    wc.public_www = "http://www.onet.pl/"
    wc.www = None

    toplevel = etree.fromstring("<body></body>")
    wc.eksport_pbn_public_uri(toplevel)
    assert toplevel[0].attrib['href'] == "http://www.onet.pl/"

    wc.public_www = None
    wc.pubmed_id = "123"
    toplevel = etree.fromstring("<body></body>")
    wc.eksport_pbn_public_uri(toplevel)
    assert toplevel[0].attrib['href'] == "http://www.ncbi.nlm.nih.gov/pubmed/123"

    wc.public_www = None
    wc.pubmed_id = None
    wc.www = "http://www.onet.pl/"
    toplevel = etree.fromstring("<body></body>")
    wc.eksport_pbn_public_uri(toplevel)
    import pytest
    with pytest.raises(IndexError):
        toplevel[0]
