# -*- encoding: utf-8 -*-

from django.test import TestCase

from bpp.jezyk_polski import warianty_zapisanego_nazwiska

class TestWariantyZapisanegoNazwiska(TestCase):
    def test_wariantyZapisanegoNazwiska(self):
        wzn = warianty_zapisanego_nazwiska

        self.assertEqual(
            list(wzn("Jan Maria", "Rokita", None)),
            ["Jan Maria Rokita",    "J[an] M[aria] Rokita",     "J. M. Rokita",
             "Jan Rokita",          "J[an] Rokita",             "J. Rokita",
             "Maria Rokita",        "M[aria] Rokita",           "M. Rokita",
             ])

        self.assertEqual(
            list(wzn("Jan Maria", "Rokita-Potocki", None)),
            [u'Jan Maria Rokita-Potocki',       u'Jan Maria Rokita',        u'Jan Maria Potocki',
             u'J[an] M[aria] Rokita-Potocki',   u'J[an] M[aria] Rokita',    u'J[an] M[aria] Potocki',
             u'J. M. Rokita-Potocki',           u'J. M. Rokita',            u'J. M. Potocki',
             
             u'Jan Rokita-Potocki',             u'Jan Rokita',              u'Jan Potocki',
             u'J[an] Rokita-Potocki',           u'J[an] Rokita',            u'J[an] Potocki',
             u'J. Rokita-Potocki',              u'J. Rokita',               u'J. Potocki',


             u'Maria Rokita-Potocki',             u'Maria Rokita',              u'Maria Potocki',
             u'M[aria] Rokita-Potocki',           u'M[aria] Rokita',            u'M[aria] Potocki',
             u'M. Rokita-Potocki',              u'M. Rokita',               u'M. Potocki',
             ])

        self.assertEqual(
            list(wzn(u'Stanisław J.', u'Czuczwar', None)),
            [u'Stanisław J. Czuczwar',      u'S[tanisław] J. Czuczwar',         u'S. J. Czuczwar',
             u'Stanisław Czuczwar',         u'S[tanisław] Czuczwar',            u'S. Czuczwar',
             u'J. Czuczwar',                u'J. Czuczwar',                     u'J. Czuczwar'])

        self.assertEqual(
            list(wzn(u'Zbigniew F.', u'Zagórski', None)),
            [u'Zbigniew F. Zagórski',   u'Z[bigniew] F. Zagórski',      u'Z. F. Zagórski',
             u'Zbigniew Zagórski',      u'Z[bigniew] Zagórski',         u'Z. Zagórski',
             u'F. Zagórski',            u'F. Zagórski',                 u'F. Zagórski'])

        self.assertEqual(
            list(wzn(u'Jan', u'Kowalski', u'Nowak')),
            ['Jan Kowalski',        'J[an] Kowalski',       'J. Kowalski',
             'Jan Nowak',            'J[an] Nowak',          'J. Nowak'])
