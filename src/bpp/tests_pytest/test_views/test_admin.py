# -*- encoding: utf-8 -*-
import pytest
from bpp.models.cache import Rekord
from django.urls.base import reverse
from model_mommy import mommy

from bpp.models.patent import Patent, Patent_Autor
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, \
    Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, \
    Wydawnictwo_Zwarte_Autor


@pytest.mark.parametrize(
    "klass,autor_klass,form_name,url",
    [
        (Wydawnictwo_Ciagle,
         Wydawnictwo_Ciagle_Autor,
         "wydawnictwo_ciagle_form",
         "admin:bpp_wydawnictwo_ciagle_change"),

        (Wydawnictwo_Zwarte,
         Wydawnictwo_Zwarte_Autor,
         "wydawnictwo_zwarte_form",
         "admin:bpp_wydawnictwo_zwarte_change"),

        (Patent,
         Patent_Autor,
         "patent_form",
         "admin:bpp_patent_change"),
    ]
)


def test_zapisz_wydawnictwo_ciagle(klass, autor_klass, form_name,
                                   url, admin_app):
    Rekord.objects.all().delete()

    wc = mommy.make(klass)
    wca = mommy.make(autor_klass, rekord=wc)

    url = reverse(url, args=(wc.pk,))
    res = admin_app.get(url)

    res2 = res.forms[form_name].submit().maybe_follow()
    assert res2.status_code == 200

