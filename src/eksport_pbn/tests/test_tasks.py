# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

from datetime import datetime, timedelta

from django.core.urlresolvers import reverse
from model_mommy import mommy

from eksport_pbn.models import PlikEksportuPBN, DATE_CREATED_ON
from eksport_pbn.tasks import eksport_pbn, id_zwartych, id_ciaglych, remove_old_eksport_pbn_files


def test_eksport_pbn(normal_django_user, jednostka, autor_jan_kowalski, wydawnictwo_ciagle, wydawnictwo_zwarte, rok):
    assert PlikEksportuPBN.objects.all().count() == 0

    autor_jan_kowalski.dodaj_jednostke(jednostka=jednostka)

    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    assert wydawnictwo_zwarte.charakter_formalny != wydawnictwo_ciagle.charakter_formalny

    cf = wydawnictwo_ciagle.charakter_formalny
    cf.artykul_pbn = True
    cf.ksiazka_pbn = cf.rozdzial_pbn = False
    cf.save()

    cf = wydawnictwo_zwarte.charakter_formalny
    cf.artykul_pbn = cf.rozdzial_pbn = False
    cf.ksiazka_pbn = True
    cf.save()

    obj = PlikEksportuPBN.objects.create(
            owner=normal_django_user,
            wydzial=jednostka.wydzial,
            od_roku=rok, do_roku=rok
    )

    eksport_pbn(obj.pk)

    assert PlikEksportuPBN.objects.all().count() == 1


def test_remove_old_eksport_files(db):
    mommy.make(PlikEksportuPBN, created_on=datetime.now())
    e2 = mommy.make(PlikEksportuPBN)
    e2.created_on = datetime.now() - timedelta(days=15)
    e2.save()

    assert PlikEksportuPBN.objects.all().count() == 2

    remove_old_eksport_pbn_files()

    assert PlikEksportuPBN.objects.all().count() == 1

