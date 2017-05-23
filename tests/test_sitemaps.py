# -*- encoding: utf-8 -*-

import pytest
from model_mommy import mommy

from bpp.models.autor import Autor
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.struktura import Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_sitemaps(webtest_app):
    mommy.make(Wydzial)
    mommy.make(Autor, nazwisko="Alan")
    mommy.make(Wydawnictwo_Ciagle, tytul_oryginalny="A case of")
    mommy.make(Wydawnictwo_Zwarte, tytul_oryginalny="A case of")
    mommy.make(Praca_Doktorska, tytul_oryginalny="A case of")
    mommy.make(Praca_Habilitacyjna, tytul_oryginalny="A case of")
    mommy.make(Patent, tytul_oryginalny="A case of")

    for page in ['', '-jednostka', '-autor-a', '-uczelnia', '-wydawnictwo-ciagle-a', '-wydawnictwo-zwarte-a',
                 '-praca-doktorska-a', '-praca-habilitacyjna-a', '-patent-a', '-wydzial']:
        res = webtest_app.get("/sitemap%s.xml" % page)
        assert res.status_code == 200
        assert 'example.com' in res.content
