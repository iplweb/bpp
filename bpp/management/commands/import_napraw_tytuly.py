# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models.cache import Rekord
from bpp.models import cache


FIXME = [
    ('<alpha>', u'α'),
    ('<alfa>', u'α'),
    ('<afa>', u'α'),

    ('<beta>', u'β'),
    ('<gamma>', u'γ'),
    ('<delta>', u'δ'),
    ('<d>', u'δ'),
    ('<epsilon>', u'ε'),
    ('<pi>', u'π'),

    ('<mi>', u'μ'),
    ('<omega>', u'ω'),

    ('<zeta>', u'ζ'),
    ('<tau>', u'τ'),
    ('<kappa>', u'κ'),

    ('<sub)', '<sub>'),

    ('<dn>', '<sub>'),
    ('</dn>', '</sub>'),

    ('<up>', '<sup>'),
    ('</up>', '</sup>'),

    ('<Heraclem sibiricum', '<i>Heraclem sibiricum</i>'),
    ('<foramen jugulare>', '<i>foramen jugulare</i>'),

]

class Command(BaseCommand):
    help = u'Naprawia tytuły prac po imporcie'

    @transaction.atomic
    def handle(self, *args, **options):
        cache.enable()

        for string, replacement in FIXME:
            for rekord in Rekord.objects.filter(tytul_oryginalny__contains=string):
                pre = (rekord.tytul_oryginalny, rekord.tytul)
                for pole in ['tytul', 'tytul_oryginalny']:
                    setattr(rekord, pole, getattr(rekord, pole).replace(string, replacement))
                post = (rekord.tytul_oryginalny, rekord.tytul)

                if pre != post:
                    # print pre, post
                    pass

                rekord.save()
