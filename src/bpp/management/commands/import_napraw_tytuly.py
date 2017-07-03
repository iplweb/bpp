# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models.cache import Rekord
from bpp.models import cache


FIXME = [
    ('<alpha>', 'α'),
    ('<alfa>', 'α'),
    ('<afa>', 'α'),

    ('<beta>', 'β'),
    ('<gamma>', 'γ'),
    ('<delta>', 'δ'),
    ('<d>', 'δ'),
    ('<epsilon>', 'ε'),
    ('<pi>', 'π'),

    ('<mi>', 'μ'),
    ('<omega>', 'ω'),

    ('<zeta>', 'ζ'),
    ('<tau>', 'τ'),
    ('<kappa>', 'κ'),

    ('<sub)', '<sub>'),

    ('<dn>', '<sub>'),
    ('</dn>', '</sub>'),

    ('<up>', '<sup>'),
    ('</up>', '</sup>'),

    ('<Heraclem sibiricum', '<i>Heraclem sibiricum</i>'),
    ('<foramen jugulare>', '<i>foramen jugulare</i>'),

]

class Command(BaseCommand):
    help = 'Naprawia tytuły prac po imporcie'

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

        for elem in Rekord.objects.raw("""select * from bpp_rekord_mat where
tytul_oryginalny like '%%<%%' and
lower(tytul_oryginalny) not like '%%<b>%%'  and
lower(tytul_oryginalny) not like '%%<i>%%'  and
lower(tytul_oryginalny) not like '%%<sub>%%'  and
lower(tytul_oryginalny) not like '%%<sup>%%'  and
lower(tytul_oryginalny) not like '%%<beta>%%' and
lower(tytul_oryginalny) not like '%%<alfa>%%' and
lower(tytul_oryginalny) not like '%%<pi>%%'  and
lower(tytul_oryginalny) not like '%%<gamma>%%' and
lower(tytul_oryginalny) not like '%%<up>%%' and
lower(tytul_oryginalny) not like '%%<dn>%%' and
lower(tytul_oryginalny) not like '%%<mi>%%' and
lower(tytul_oryginalny) not like '%%<i/>%%' and
lower(tytul_oryginalny) not like '%%<alfa>%%' and
lower(tytul_oryginalny) not like '%%<afa>%%' and
lower(tytul_oryginalny) not like '%%<delta>%%'  and
lower(tytul_oryginalny) not like '%%<zeta>%%'  and
lower(tytul_oryginalny) not like '%%<tau>%%'  and
lower(tytul_oryginalny) not like '%%<kappa>%%'  and
lower(tytul_oryginalny) not like '%%<sub)%%'  and
lower(tytul_oryginalny) not like '%%<alpha>%%';
"""):
            print("%r" % elem.tytul_oryginalny)