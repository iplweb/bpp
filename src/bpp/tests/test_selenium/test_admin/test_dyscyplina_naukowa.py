# -*- encoding: utf-8 -*-
import time

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from model_mommy import mommy

from bpp.models import Wydawnictwo_Ciagle, Uczelnia, Autor, Jednostka, Typ_Odpowiedzialnosci, TO_AUTOR
from bpp.models.patent import Patent
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from .helpers import *


@pytest.mark.parametrize(
    "url,klasa", [("wydawnictwo_ciagle", Wydawnictwo_Ciagle),
#                  ("wydawnictwo_zwarte", Wydawnictwo_Zwarte),
#                  ("patent", Patent)
                     ])
@pytest.mark.django_db(transaction=True)
def test_admin_dyscyplina_naukowa_w_przypisaniu_rekordu(
        preauth_admin_browser,
        nginx_live_server,
        url,
        klasa):

    try:
        uczelnia = mommy.make(Uczelnia)
        autor = mommy.make(Autor, nazwisko="Kowal", imiona="Ski")
        jednostka = mommy.make(Jednostka, nazwa="Lol", skrot="WT")
        wydawnictwo = mommy.make(klasa, tytul_oryginalny="test")
        Typ_Odpowiedzialnosci.objects.get_or_create(
            skrot="aut.", nazwa="autor", typ_ogolny=TO_AUTOR)
        wa = wydawnictwo.dodaj_autora(autor, jednostka, zapisany_jako="Wutlolski")
        wa.save()

        browser = preauth_admin_browser
        browser.visit(nginx_live_server.url + reverse(f"admin:bpp_{url}_change",
                                            args=(wydawnictwo.pk,)))

        browser.execute_script("""
        document.getElementsByClassName("grp-add-handler")[1].scrollIntoView()
        """)
        time.sleep(0.5)
        browser.find_by_css(".grp-add-handler")[1].click()
        time.sleep(0.5)
    finally:
        uczelnia.delete()
        Jednostka.objects.filter(skrot="WT").delete()
        Autor.objects.filter(nazwisko="Kowal").delete()
        klasa.objects.filter(tytul_oryginalny="test").delete()

    raise NotImplementedError
