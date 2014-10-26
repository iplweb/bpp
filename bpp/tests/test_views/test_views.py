# -*- encoding: utf-8 -*-
from django.contrib import auth
from django.core.urlresolvers import reverse
from model_mommy import mommy
from ludibrio import Mock
from bpp.models import Autor, Zrodlo, Uczelnia, Wydzial, Jednostka, \
    Praca_Doktorska, Praca_Habilitacyjna
from bpp.models.cache import Rekord
from bpp.models.system import Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, \
    Wydawnictwo_Ciagle_Autor
from bpp.tests.util import any_doktorat, any_habilitacja, any_ciagle, any_autor, \
    any_jednostka

from bpp.tests.testutil import UserTestCase, SuperuserTestCase
from bpp.views import navigation_autocomplete, autorform_dependant_js
from bpp.views.browse import AutorzyView, AutorView
from bpp.views.utils import JsonResponse

class TestViews(UserTestCase):
    def test_navigation_autocomplete(self):
        req = self.factory.get('/', {'q': 'test'})
        navigation_autocomplete(req)

        # dla superusera dochodzi parę opcji w wyszukiwaniu
        # zakładamy, że poniższa linia znajdzie przyajmniej JEDNEGO usera, autora i zrodlo
        a = mommy.make(Autor, nazwisko='Test autor testowski')
        z = mommy.make(Zrodlo, nazwa='Zrodlo test testowe')
        auth.get_user_model().objects.create_user('Test test user X', 'foo',
                                                  'bar')
        req.user = auth.get_user_model().objects.create_superuser('Test user',
                                                                  'pass', 'ema')
        ret = navigation_autocomplete(req)

        self.assertContains(ret, 'Test autor')
        self.assertContains(ret, 'Zrodlo test')
        self.assertContains(ret, 'Test user')

    def test_autorform_dependant_js(self):
        autorform_dependant_js(self.factory.get('/'))


class TestUtils(UserTestCase):
    def test_jsonresponse(self):
        JsonResponse('foo')


class TestRoot(UserTestCase):
    def test_root(self):
        res = self.client.get("/")
        self.assertContains(res, "W systemie nie ma", status_code=200)

        Uczelnia.objects.create(nazwa="uczelnia", skrot="uu")
        res = self.client.get("/")
        self.assertRedirects(
            res,
            reverse("bpp:browse_uczelnia", args=('uu',)),
            status_code=302)


class TestBrowse(UserTestCase):
    def test_wydzial(self):
        u = Uczelnia.objects.create(nazwa="uczelnia", skrot="uu")
        w = Wydzial.objects.create(nazwa="wydzial", uczelnia=u)
        res = self.client.get(reverse("bpp:browse_uczelnia", args=('uu',)))
        self.assertContains(res, "Wybierz wydział", status_code=200)

    def test_jednostka(self):
        u = Uczelnia.objects.create(nazwa="uczelnia", skrot="uu")
        w = Wydzial.objects.create(nazwa="wydzial", uczelnia=u)
        j = Jednostka.objects.create(nazwa="jednostka", wydzial=w)

        res = self.client.get(reverse("bpp:browse_jednostka", args=(j.slug,)))
        self.assertContains(res, "jednostka", status_code=200)


class TestBrowseAutorzy(UserTestCase):
    def setUp(self):
        super(TestBrowseAutorzy, self).setUp()

        self.view = AutorzyView()

        class FakeRequest:
            GET = dict(search='Autor')
        self.view.request = FakeRequest()
        self.autor = mommy.make(Autor, nazwisko='Autor', imiona='Foo')
        self.view.kwargs = dict(literka='A')

    def test_get_queryset(self):
        q = self.view.get_queryset()
        self.assertEquals(list(q)[0], self.autor)

    def test_get_context_data(self):
        self.view.object_list = []
        d = self.view.get_context_data()
        self.assertEquals(d['wybrana'], 'A')
        self.assertEquals(d['flt'], 'Autor')


class TestBrowseAutor(UserTestCase):
    fixtures = ['charakter_formalny.json', 'tytul.json',
                'typ_odpowiedzialnosci.json']

    def test_get_context_data(self):
        av = AutorView()
        av.object = mommy.make(Autor)
        d = av.get_context_data()
        self.assert_('publikacje' in d['typy'])

    def test_habilitacyjna_doktorska(self):
        a = mommy.make(Autor)
        kw = dict(autor=a, tytul_oryginalny='X', tytul='Y', uwagi='Z')
        d = any_doktorat(**kw)
        h = any_habilitacja(**kw)
        res = self.client.get(reverse("bpp:browse_autor", args=(a.slug,)))
        self.assertContains(res, 'Praca doktorska')
        self.assertContains(res, 'Praca habilitacyjna')

    def test_autor(self):
        a = mommy.make(Autor)
        res = self.client.get(reverse("bpp:browse_autor", args=(a.slug,)))
        self.assertNotContains(res, 'otwórz do edycji')


class TestBrowseAutorStaff(SuperuserTestCase):
    def test_autor(self):
        a = mommy.make(Autor)
        res = self.client.get(reverse("bpp:browse_autor", args=(a.slug,)))
        self.assertContains(res, 'otwórz do edycji')


class TestOAI(UserTestCase):
    fixtures = ['charakter_formalny.json', 'tytul.json',
                'typ_odpowiedzialnosci.json', 'status_korekty.json']

    def setUp(self):
        c = any_ciagle(tytul_oryginalny="Test foo bar")
        a = any_autor()
        j = any_jednostka()
        Wydawnictwo_Ciagle_Autor.objects.create(
            rekord=c, autor=a, jednostka=j,
            typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.all()[0]
        )
        Rekord.objects.full_refresh()
        self.assertEquals(Rekord.objects.all().count(), 1)
        #Wydawnictwo_Ciagle.objects.raw("SELECT update_cache('bpp_wydawnictwo_ciagle', '%s')" % c.pk)
        self.c = c

    def test_get_record(self):
        url = reverse("bpp:oai")
        identifier = "oai:bpp.umlub.pl:Wydawnictwo_Ciagle/%s" % self.c.pk
        res = self.client.get(url, data={'verb': 'GetRecord',
                                         'metadataPrefix': 'oai_dc',
                                         'identifier': identifier})
        self.assertContains(res, "foo", status_code=200)


    def test_list_records(self):
        url = reverse("bpp:oai")

        res = self.client.get(url, data={'verb': 'ListRecords',
                                         'metadataPrefix': 'oai_dc'})
        self.assertContains(res, "foo", status_code=200)


