# -*- encoding: utf-8 -*-
import os
from tempfile import mkstemp
import sys
import webbrowser

from django.test import TestCase

from bpp.reports.kronika_uczelni import Kronika_Uczelni
from bpp.tests.tests_legacy.test_reports.util import USUAL_FIXTURES, stworz_obiekty_dla_raportow
from bpp.tests.util import any_autor, any_jednostka, any_ciagle, any_zwarte, CURRENT_YEAR, any_uczelnia, any_wydzial


class TestKronikaUczelni(TestCase):
    # fixtures = USUAL_FIXTURES

    def setUp(self):
        stworz_obiekty_dla_raportow()

        u = any_uczelnia()
        w = any_wydzial()

        j1 = any_jednostka(nazwa='Jednostka 1', wchodzi_do_raportow=True)
        j2 = any_jednostka(nazwa='Jednostka 2', wchodzi_do_raportow=True)

        a1 = any_autor()
        j1.dodaj_autora(a1)

        a2 = any_autor(nazwisko="Óńwak", imiona="Jań")
        j2.dodaj_autora(a2)

        a3 = any_autor(nazwisko="Budnik", imiona="Piotr")
        j2.dodaj_autora(a3)

        for a in range(3):
            c = any_ciagle(tytul="Ciagle-%s" % a)
            c.dodaj_autora(a1, j1)
            z = any_zwarte(tytul="Zwarte-%s" % a)
            z.dodaj_autora(a1, j1)

        c.dodaj_autora(a2, j2)
        c.dodaj_autora(a3, j2)
        z.dodaj_autora(a2, j2)
        z.dodaj_autora(a3, j2)

        for a in range(5):
            z = any_zwarte(tytul="Zwarte-2-%s" % a)
            z.dodaj_autora(a2, j2)
            c = any_ciagle(tytul="Ciagle-2-%s" % a)
            c.dodaj_autora(a2, j2)

        c.dodaj_autora(a1, j1)
        c.dodaj_autora(a3, j2)
        z.dodaj_autora(a1, j1)
        z.dodaj_autora(a3, j2)

    def test_kronika_uczelni(self):
        assertIn = self.assertIn

        class raport:
            arguments = dict(rok=CURRENT_YEAR)
            uid = 'test_procedure'

            class _file:
                def save(self, name, fobj):
                    fobj.seek(0)
                    buf = fobj.read()
                    assertIn('Kowalski', buf)
                    assertIn('[1]', buf)

                    # Test 'wizualny' przy ręcznym uruchomieniu:
                    if sys.platform == 'win32':
                        fd, name = mkstemp(suffix=".html")
                        os.write(fd, buf)
                        os.close(fd)

                        webbrowser.open("file:///" + name)

            file = _file()

        ku = Kronika_Uczelni(raport())
        ku.perform()
