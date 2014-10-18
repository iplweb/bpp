# -*- encoding: utf-8 -*-

from django.test import TestCase
from django_dynamic_fixture import G
from bpp.models import Autor
from bpp.util import slugify_function, get_copy_from_db, has_changed


class TestUtil(TestCase):
    def test_slugify_function(self):
        test = u'Waldemar A. Łącki,,()*\':;\r\n[]'
        result = u'Waldemar-A-Lacki'
        self.assertEquals(slugify_function(test), result)

    def test_get_copy_from_db(self):
        a = G(Autor)
        b = get_copy_from_db(a)
        self.assertEquals(a.pk, b.pk)

    def test_has_changed(self):
        a = G(Autor)
        self.assertEquals(has_changed(a, 'nazwisko'), False)

        a.nazwisko = 'Foo'
        self.assertEquals(has_changed(a, 'nazwisko'), True)

        a.save()
        self.assertEquals(has_changed(a, ['nazwisko', 'imiona']), False)

        a.imiona = 'Bar'
        self.assertEquals(has_changed(a, ['nazwisko', 'imiona']), True)
