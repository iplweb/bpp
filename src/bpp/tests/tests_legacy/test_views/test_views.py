try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from model_bakery import baker

from django.contrib.auth.models import Group

from bpp.models import Autor, Jednostka, Uczelnia, Wydzial
from bpp.models.cache import Rekord
from bpp.models.system import Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.tests.tests_legacy.testutil import SuperuserTestCase, UserTestCase
from bpp.tests.util import (
    any_autor,
    any_ciagle,
    any_doktorat,
    any_habilitacja,
    any_jednostka,
)
from bpp.util import rebuild_contenttypes
from bpp.views.browse import AutorView, AutorzyView


class TestRoot(UserTestCase):
    def setUp(self):
        Group.objects.get_or_create(name="wprowadzanie danych")

    def test_root(self):
        res = self.client.get("/")
        self.assertContains(res, "W systemie nie ma", status_code=200)

        Uczelnia.objects.create(nazwa="uczelnia", skrot="uu")
        res = self.client.get("/", follow=False)
        self.assertRedirects(
            res, reverse("bpp:browse_uczelnia", args=("uu",)), status_code=301
        )


class TestBrowse(UserTestCase):
    def setUp(self):
        Group.objects.get_or_create(name="wprowadzanie danych")

    def test_wydzial(self):
        u = Uczelnia.objects.create(nazwa="uczelnia", skrot="uu")
        Wydzial.objects.create(nazwa="wydzial", uczelnia=u)
        res = self.client.get(reverse("bpp:browse_uczelnia", args=("uu",)))
        self.assertContains(res, "Wybierz wydział", status_code=200)

    def test_jednostka(self):
        u = Uczelnia.objects.create(nazwa="uczelnia", skrot="uu")
        w = Wydzial.objects.create(nazwa="wydzial", uczelnia=u)
        j = Jednostka.objects.create(nazwa="jednostka", wydzial=w, uczelnia=u)

        res = self.client.get(reverse("bpp:browse_jednostka", args=(j.slug,)))
        self.assertContains(res, "jednostka", status_code=200)


class FakeUnauthenticatedUser:
    def is_authenticated(self):
        return False


class TestBrowseAutorzy(UserTestCase):
    def setUp(self):
        super().setUp()

        Group.objects.get_or_create(name="wprowadzanie danych")

        self.view = AutorzyView()

        class FakeRequest:
            GET = dict(search="Autor")

            def __init__(self):
                self.user = FakeUnauthenticatedUser()

        self.view.request = FakeRequest()
        self.autor = baker.make(Autor, nazwisko="Autor", imiona="Foo")
        self.view.kwargs = dict(literka="A")

    def test_get_queryset(self):
        q = self.view.get_queryset()
        self.assertEqual(list(q)[0], self.autor)

    def test_get_context_data(self):
        self.view.object_list = []
        d = self.view.get_context_data()
        self.assertEqual(d["wybrana"], "A")
        self.assertEqual(d["flt"], "Autor")


class TestBrowseAutor(UserTestCase):
    # fixtures = ['charakter_formalny.json', 'tytul.json',
    #             'typ_odpowiedzialnosci.json']

    def setUp(self):
        Group.objects.get_or_create(name="wprowadzanie danych")

        rebuild_contenttypes()

    def test_get_context_data(self):
        av = AutorView()
        av.object = baker.make(Autor)
        d = av.get_context_data()
        self.assertTrue("publikacje" in d["typy"])

    def test_habilitacyjna_doktorska(self):
        a = baker.make(Autor)
        kw = dict(autor=a, tytul_oryginalny="X", tytul="Y", uwagi="Z")
        any_doktorat(**kw)
        any_habilitacja(**kw)
        res = self.client.get(reverse("bpp:browse_autor", args=(a.slug,)))
        self.assertContains(res, "Praca doktorska")
        self.assertContains(res, "Praca habilitacyjna")

    def test_autor(self):
        a = baker.make(Autor)
        res = self.client.get(reverse("bpp:browse_autor", args=(a.slug,)))
        self.assertNotContains(res, "otwórz do edycji")


class TestBrowseAutorStaff(SuperuserTestCase):
    def setUp(self):
        super().setUp()
        Group.objects.get_or_create(name="wprowadzanie danych")

    def test_autor(self):
        a = baker.make(Autor)
        res = self.client.get(reverse("bpp:browse_autor", args=(a.slug,)))
        self.assertContains(res, "otwórz do edycji")


class TestOAI(UserTestCase):
    def setUp(self):
        super().setUp()

        rebuild_contenttypes()

        aut, ign = Typ_Odpowiedzialnosci.objects.get_or_create(
            skrot="aut.", nazwa="autor"
        )

        ch, ign = Charakter_Formalny.objects.get_or_create(
            skrot="AC", nazwa="Artykuł w czasopismie", nazwa_w_primo="Artykuł"
        )

        ch2, ign = Charakter_Formalny.objects.get_or_create(
            skrot="KOM", nazwa="Komentarz"
        )

        c = any_ciagle(tytul_oryginalny="Test foo bar", charakter_formalny=ch)

        c2 = any_ciagle(
            tytul_oryginalny="TEGO NIE BEDZIE bo nie ma nazwa_w_primo dla typu KOM",
            charakter_formalny=Charakter_Formalny.objects.get(skrot="KOM"),
        )

        a = any_autor()
        j = any_jednostka()

        for rekord in c, c2:
            Wydawnictwo_Ciagle_Autor.objects.create(
                rekord=rekord, autor=a, jednostka=j, typ_odpowiedzialnosci=aut
            )

        Rekord.objects.full_refresh()

        cnt = Rekord.objects.all().count()
        self.assertEqual(cnt, 2)

        self.c = c

    def test_get_record(self):
        url = reverse("bpp:oai")
        identifier = "oai:bpp.umlub.pl:Wydawnictwo_Ciagle/%s" % self.c.pk
        res = self.client.get(
            url,
            data={
                "verb": "GetRecord",
                "metadataPrefix": "oai_dc",
                "identifier": identifier,
            },
        )
        self.assertContains(res, "foo", status_code=200)

    def test_list_records(self):
        url = reverse("bpp:oai")

        res = self.client.get(
            url, data={"verb": "ListRecords", "metadataPrefix": "oai_dc"}
        )
        self.assertContains(res, "foo", status_code=200)
        self.assertNotContains(res, "TEGO NIE BEDZIE", status_code=200)
