# -*- encoding: utf-8 -*-
from tempfile import mkdtemp
from zipfile import ZipFile
import os
from optparse import make_option

from lxml import etree
from django.core.management import BaseCommand
from lxml.etree import tostring
from eksport_pbn.tasks import zipdir

def new_filename(current, number):
    return os.path.join(
            os.path.dirname(current),
            os.path.basename(current).replace(".zip", "-bledna-%i.zip" % number)
        )

class Command(BaseCommand):
    help = 'Ekstrahuje prace o zadanym numerze z pliku ZIP, tworzy nowy plik'

    option_list = BaseCommand.option_list + (
        make_option('--file', action='store', type=str),
        make_option("--ktora", action="store", type=int)
    )

    def handle(self, *args, **options):
        new_fn = new_filename(options['file'], options['ktora'])

        ktora = 0
        failed = None

        with ZipFile(options['file'], 'r') as myzip:
            for name in myzip.namelist():

                td = mkdtemp()
                myzip.extract(name, td)

                xml = etree.parse(os.path.join(td, name))
                root = xml.getroot()
                children = root.getchildren()

                try:
                    failed = children[ktora + options['ktora']]
                    break
                except IndexError:
                    ktora += len(children)
                    continue

        for child in root.getchildren():
            root.remove(child)
        root.append(failed)

        newtmpdir = mkdtemp()
        outfile = open(os.path.join(newtmpdir, '1.xml'), 'w')
        outfile.write(tostring(root))
        outfile.close()

        zipf = ZipFile(new_fn, 'w')
        zipdir(newtmpdir, zipf)
        zipf.close()

        pass