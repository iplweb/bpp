# -*- encoding: utf-8 -*-

import pytest
from model_mommy import mommy

from bpp.models.autor import Autor
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_sitemaps(webtest_app):
    mommy.make(Autor)
    mommy.make(Wydawnictwo_Ciagle)
    mommy.make(Wydawnictwo_Zwarte)
    mommy.make(Praca_Doktorska)
    mommy.make(Praca_Habilitacyjna)
    mommy.make(Patent)

    for page in ['', '-jednostka', '-autor', '-uczelnia', '-wydawnictwo-ciagle', '-wydawnictwo-zwarte',
                 '-praca-doktorska', '-praca-habilitacyjna', '-patent']:
        res = webtest_app.get("/sitemap%s.xml" % page)
        assert res.status_code == 200
        assert 'example.com' in res.content
