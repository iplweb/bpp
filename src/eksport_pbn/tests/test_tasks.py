# -*- encoding: utf-8 -*-



from datetime import timedelta

from django.utils import timezone
from model_mommy import mommy

from bpp.models.system import Charakter_Formalny, Typ_KBN
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from eksport_pbn.models import PlikEksportuPBN
from eksport_pbn.tasks import eksport_pbn, remove_old_eksport_pbn_files


def test_eksport_pbn(normal_django_user, jednostka, autor_jan_kowalski, rok,
                     typy_odpowiedzialnosci, nginx_live_server, settings):
    settings.NOTIFICATIONS_HOST = nginx_live_server.host
    settings.NOTIFICATIONS_PORT = nginx_live_server.port

    assert PlikEksportuPBN.objects.all().count() == 0

    autor_jan_kowalski.dodaj_jednostke(jednostka=jednostka)

    cf_ciagle = mommy.make(Charakter_Formalny,
                           artykul_pbn=True,
                           ksiazka_pbn=False,
                           rozdzial_pbn=False)
    cf_zwarte = mommy.make(Charakter_Formalny,
                           artykul_pbn=False,
                           ksiazka_pbn=True,
                           rozdzial_pbn=True)

    typ_ciagle = mommy.make(Typ_KBN,
                            artykul_pbn=True)

    typ_zwarte = mommy.make(Typ_KBN, artykul_pbn=False)

    for elem in range(50):
        wydawnictwo_ciagle = mommy.make(
            Wydawnictwo_Ciagle,
            charakter_formalny=cf_ciagle,
            typ_kbn=typ_ciagle,
            rok=rok)
        wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

        wydawnictwo_zwarte = mommy.make(
            Wydawnictwo_Zwarte,
            charakter_formalny=cf_zwarte,
            rok=rok,
            typ_kbn=typ_zwarte)
        wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    obj = PlikEksportuPBN.objects.create(
        owner=normal_django_user,
        wydzial=jednostka.wydzial,
        od_roku=rok, do_roku=rok
    )

    ret = eksport_pbn(obj.pk, max_file_size=1)

    assert PlikEksportuPBN.objects.all().count() == 1


def test_remove_old_eksport_files(db):
    mommy.make(PlikEksportuPBN, created_on=timezone.now())
    e2 = mommy.make(PlikEksportuPBN)
    e2.created_on = timezone.now() - timedelta(days=15)
    e2.save()

    assert PlikEksportuPBN.objects.all().count() == 2

    remove_old_eksport_pbn_files()

    assert PlikEksportuPBN.objects.all().count() == 1
