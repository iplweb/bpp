# -*- encoding: utf-8 -*-

from django.test import TestCase
from model_mommy import mommy

from bpp.models import Autor
from bpp.util import get_copy_from_db, has_changed, slugify_function


class TestUtil(TestCase):
    def test_slugify_function(self):
        test = "Waldemar A. Łącki,,()*':;\r\n[]"
        result = "Waldemar-A-Lacki"
        self.assertEqual(slugify_function(test), result)

    def test_slugify_function_double_dash(self):
        test = "Andrzej   Wróbel"
        result = "Andrzej-Wrobel"
        self.assertEqual(slugify_function(test), result)

    def test_get_copy_from_db(self):
        a = mommy.make(Autor)
        b = get_copy_from_db(a)
        self.assertEqual(a.pk, b.pk)

    def test_has_changed(self):
        a = mommy.make(Autor)
        self.assertEqual(has_changed(a, "nazwisko"), False)

        a.nazwisko = "Foo"
        self.assertEqual(has_changed(a, "nazwisko"), True)

        a.save()
        self.assertEqual(has_changed(a, ["nazwisko", "imiona"]), False)

        a.imiona = "Bar"
        self.assertEqual(has_changed(a, ["nazwisko", "imiona"]), True)
