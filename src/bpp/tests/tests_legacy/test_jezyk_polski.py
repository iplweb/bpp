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
            ['Jan Maria Rokita-Potocki',       'Jan Maria Rokita',        'Jan Maria Potocki',
             'J[an] M[aria] Rokita-Potocki',   'J[an] M[aria] Rokita',    'J[an] M[aria] Potocki',
             'J. M. Rokita-Potocki',           'J. M. Rokita',            'J. M. Potocki',
             
             'Jan Rokita-Potocki',             'Jan Rokita',              'Jan Potocki',
             'J[an] Rokita-Potocki',           'J[an] Rokita',            'J[an] Potocki',
             'J. Rokita-Potocki',              'J. Rokita',               'J. Potocki',


             'Maria Rokita-Potocki',             'Maria Rokita',              'Maria Potocki',
             'M[aria] Rokita-Potocki',           'M[aria] Rokita',            'M[aria] Potocki',
             'M. Rokita-Potocki',              'M. Rokita',               'M. Potocki',
             ])

        self.assertEqual(
            list(wzn('Stanisław J.', 'Czuczwar', None)),
            ['Stanisław J. Czuczwar',      'S[tanisław] J. Czuczwar',         'S. J. Czuczwar',
             'Stanisław Czuczwar',         'S[tanisław] Czuczwar',            'S. Czuczwar',
             'J. Czuczwar',                'J. Czuczwar',                     'J. Czuczwar'])

        self.assertEqual(
            list(wzn('Zbigniew F.', 'Zagórski', None)),
            ['Zbigniew F. Zagórski',   'Z[bigniew] F. Zagórski',      'Z. F. Zagórski',
             'Zbigniew Zagórski',      'Z[bigniew] Zagórski',         'Z. Zagórski',
             'F. Zagórski',            'F. Zagórski',                 'F. Zagórski'])

        self.assertEqual(
            list(wzn('Jan', 'Kowalski', 'Nowak')),
            ['Jan Kowalski',        'J[an] Kowalski',       'J. Kowalski',
             'Jan Nowak',            'J[an] Nowak',          'J. Nowak'])
