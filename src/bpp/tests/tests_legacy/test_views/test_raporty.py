# -*- encoding: utf-8 -*-

import os
import sys
import uuid

import pytest
from django.apps import apps
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from django.db import transaction
from django.http import Http404
from django.test.utils import override_settings
from django.utils import timezone
from model_mommy import mommy

from bpp.models import Typ_KBN, Jezyk, Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.tests.tests_legacy.testutil import UserTestCase, UserTransactionTestCase
from bpp.tests.util import any_jednostka, any_autor, any_ciagle
from bpp.util import rebuild_contenttypes
from bpp.views.raporty import RaportSelector, PodgladRaportu, KasowanieRaportu
from celeryui.models import Report


class TestRaportSelector(UserTestCase):
    def test_raportselector(self):
        p = RaportSelector()
        p.request = self.factory.get('/')
        p.get_context_data()

    def test_raportselector_with_reports(self):
        for x, kiedy_ukonczono in enumerate([timezone.now(), None]):
            mommy.make(
                Report, arguments={},
                file=None, finished_on=kiedy_ukonczono)

        self.client.get(reverse('bpp:raporty'))

    def test_tytuly_raportow_kronika_uczelni(self):
        any_ciagle(rok=2000)

        rep = Report.objects.create(
            ordered_by=self.user,
            function="kronika-uczelni",
            arguments={"rok": "2000"})

        res = self.client.get(reverse('bpp:raporty'))
        self.assertContains(
            res,
            "Kronika Uczelni dla roku 2000",
            status_code=200)

    def test_tytuly_raportow_raport_dla_komisji_centralnej(self):
        a = any_autor("Kowalski", "Jan")
        rep = Report.objects.create(
            ordered_by=self.user,
            function="raport-dla-komisji-centralnej",
            arguments={"autor": a.pk})

        res = self.client.get(reverse('bpp:raporty'))
        self.assertContains(
            res,
            "Raport dla Komisji Centralnej - %s" % str(a),
            status_code=200)


class RaportMixin:
    def zrob_raport(self):
        r = mommy.make(
            Report, file=None,
            function="kronika-uczelni",
            arguments='{"rok":"2013"}')
        return r


class TestPobranieRaportu(RaportMixin, UserTestCase):
    def setUp(self):
        UserTestCase.setUp(self)
        self.r = self.zrob_raport()
        error_class = OSError
        if sys.platform.startswith('win'):
            error_class = WindowsError

        try:
            os.unlink(
                os.path.join(settings.MEDIA_ROOT, 'raport', 'test_raport'))
        except error_class:
            pass
        self.r.file.save("test_raport", ContentFile("hej ho"))

    def test_pobranie_nginx(self):
        # Raport musi byc zakonczony, ineczej nie ma pobrania
        self.r.finished_on = timezone.now()
        self.r.save()

        with override_settings(SENDFILE_BACKEND='sendfile.backends.nginx'):
            url = reverse('bpp:pobranie-raportu', kwargs=dict(uid=self.r.uid))
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertIn('x-accel-redirect', resp._headers)


class TestPodgladRaportu(RaportMixin, UserTestCase):
    def setUp(self):
        UserTestCase.setUp(self)
        self.r = self.zrob_raport()

    def test_podgladraportu(self):
        p = PodgladRaportu()
        p.kwargs = {}
        p.kwargs['uid'] = self.r.uid

        self.assertEqual(p.get_object(), self.r)

        p.kwargs['uid'] = str(uuid.uuid4())
        self.assertRaises(Http404, p.get_object)

    def test_podgladraportu_client(self):
        url = reverse('bpp:podglad-raportu', kwargs=dict(uid=self.r.uid))
        resp = self.client.get(url)
        self.assertContains(resp, 'Kronika Uczelni', status_code=200)


class KasowanieRaportuMixin:
    def setUp(self):
        self.r = self.zrob_raport()
        self.r.ordered_by = self.user
        self.r.save()


class TestKasowanieRaportu(KasowanieRaportuMixin, RaportMixin, UserTestCase):
    def setUp(self):
        UserTestCase.setUp(self)
        KasowanieRaportuMixin.setUp(self)

    def test_kasowanieraportu(self):
        k = KasowanieRaportu()
        k.kwargs = dict(uid=self.r.uid)

        class FakeRequest:
            user = self.user

        k.request = FakeRequest()

        k.request.user = None
        self.assertRaises(Http404, k.get_object)

        k.request.user = self.user
        self.assertEqual(k.get_object(), self.r)

    def test_kasowanieraportu_client(self):
        self.assertEqual(Report.objects.count(), 1)
        url = reverse('bpp:kasowanie-raportu', kwargs=dict(uid=self.r.uid))
        resp = self.client.get(url)
        self.assertRedirects(resp, reverse("bpp:raporty"))
        self.assertEqual(Report.objects.count(), 0)


from django.conf import settings


class TestWidokiRaportJednostek2012(UserTestCase):
    # fixtures = ['charakter_formalny.json',
    #             'jezyk.json',
    #             'typ_kbn.json',
    #             'typ_odpowiedzialnosci.json']

    def setUp(self):
        UserTestCase.setUp(self)
        self.j = any_jednostka()
        Typ_KBN.objects.get_or_create(skrot="PW", nazwa="Praca wieloośrodkowa")
        Jezyk.objects.get_or_create(skrot='pol.', nazwa='polski')
        Charakter_Formalny.objects.get_or_create(skrot='KSZ', nazwa='Książka w języku obcym')
        Charakter_Formalny.objects.get_or_create(skrot='KSP', nazwa='Książka w języku polskim')
        Charakter_Formalny.objects.get_or_create(skrot='KS', nazwa='Książka')
        Charakter_Formalny.objects.get_or_create(skrot='ROZ', nazwa='Rozdział książki')
        Group.objects.get_or_create(name="wprowadzanie danych")

    def test_jeden_rok(self):
        url = reverse("bpp:raport-jednostek-rok-min-max",
                      args=(self.j.pk, 2010, 2013))
        res = self.client.get(url)

        self.assertContains(
            res,
            "Dane o publikacjach za okres 2010 - 2013",
            status_code=200)

    def test_zakres_lat(self):
        url = reverse("bpp:raport-jednostek", args=(self.j.pk, 2013))
        res = self.client.get(url)

        self.assertContains(
            res,
            "Dane o publikacjach za rok 2013",
            status_code=200)


class TestRankingAutorow(UserTestCase):
    def setUp(self):
        UserTestCase.setUp(self)

        rebuild_contenttypes()

        Typ_Odpowiedzialnosci.objects.get_or_create(skrot='aut.', nazwa='autor')
        Group.objects.get_or_create(name="wprowadzanie danych")

        j = any_jednostka()
        a = any_autor(nazwisko="Kowalski")
        c = any_ciagle(impact_factor=200, rok=2000)
        c.dodaj_autora(a, j)

    def test_renderowanie(self):
        url = reverse("bpp:ranking-autorow", args=(2000, 2000))
        res = self.client.get(url)
        self.assertContains(
            res, "Ranking autorów", status_code=200)
        self.assertContains(res, "Kowalski")

    def test_renderowanie_csv(self):
        url = reverse("bpp:ranking-autorow", args=(2000, 2000))
        res = self.client.get(url, data={"_export": "csv"})
        self.assertContains(
            res,
            '"Kowalski Jan Maria, dr",Jednostka')
