# -*- encoding: utf-8 -*

"""
delete from bpp_autor_jednostka ;delete from bpp_autor;delete from bpp_bppuser_groups; delete from bpp_bppuser;delete from bpp_jednostka;

delete from bpp_zrodlo;

delete from bpp_wydawnictwo_zwarte_autor;delete from bpp_wydawnictwo_zwarte; delete from bpp_wydawnictwo_ciagle_autor; delete from bpp_wydawnictwo_ciagle; delete from bpp_patent_autor; delete from bpp_patent; delete from bpp_praca_doktorska; delete from bpp_praca_habilitacyjna;
"""

from optparse import make_option
import subprocess
import sys

from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Uruchamiam import_bpp na wielu CPU'

    def add_arguments(self, parser):
        parser.add_argument("--cpu", action="store", type=int, default=4)

    def handle(self, *args, **options):
        cpus = options['cpu']

        jednowatkowe = ['uzytkownicy', 'korekty', 'clusters']

        for option in ['publikacje']:
            # '['uzytkownicy', 'jednostki', 'autorzy',
            #                'powiazania', 'zrodla', 'korekty', 'publikacje', 'clusters']:
            proc = []
            if option in jednowatkowe:
                ret = subprocess.check_call(
                    [sys.executable, sys.argv[1], 'import_bpp',
                     '--' + option,
                     '--traceback'])
                continue

            else:
                for n in range(cpus):
                    ret = subprocess.Popen(
                        [sys.executable, sys.argv[0], 'import_bpp',
                         '--' + option,
                         '--initial-offset=%s' % n,
                         '--skip=%s' % (cpus-1),
                         '--traceback'])
                    proc.append(ret)

                for elem in proc:
                    elem.wait()

        proc = []
        for n in range(cpus):
            ret = subprocess.Popen(
                [sys.executable, sys.argv[0], 'rebuild_cache',
                 '--initial-offset=%s' % n,
                 '--skip=%s' % (cpus-1),
                 '--traceback'])
            proc.append(ret)

        for elem in proc:
            elem.wait()
