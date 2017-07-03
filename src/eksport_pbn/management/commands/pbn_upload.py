# -*- encoding: utf-8 -*-
import time
from splinter import Browser
import os
from optparse import make_option

from django.core.management import BaseCommand, call_command
import ssl
from bpp.models.struktura import Wydzial


class Command(BaseCommand):
    help = 'Wrzuca dane do PBN'

    option_list = BaseCommand.option_list + (
        make_option("--login", action="store", type="str", default="elzbieta.drozdz@bg.umlub.pl"),
        make_option("--wydzial", action="store", type="str", default="1WL"),
        make_option("--password", action="store", type="str", default=""),
        make_option("--fix", action="store", type="int", default="1"),
        make_option('--file', action='store', type=str)

    )

    def handle(self, *args, **options):
        ssl._create_default_https_context = ssl._create_unverified_context

        wydzial_pbn = Wydzial.objects.get(skrot=options['wydzial']).pbn_id

        browser = Browser()

        def id_importu():
            browser.visit("https://pbn.ici-test.org/workImport/lastDoneImport")
            return browser.html

        try:
            browser.visit("https://pbn.ici-test.org/login")
            browser.fill('j_username', options['login'])
            browser.fill('j_password', options['password'])
            button = browser.find_by_name("log")
            button.click()
            browser.is_text_present('Moje publikacje', wait_time=10)

            id_ostatniego_importu = id_importu()

            browser.visit("https://pbn.ici-test.org/workImport")
            browser.is_text_present("Import prac", wait_time=10)
            browser.is_element_present_by_name("files[]", wait_time=10)

            browser.attach_file("files[]", options["file"])
            browser.select("institution", str(wydzial_pbn))

            basename = os.path.basename(options['file'])
            browser.is_text_present(basename, wait_time=600)

            browser.find_by_id("importButton").click()

            while id_importu() == id_ostatniego_importu:
                time.sleep(3)

            browser.visit("https://pbn.ici-test.org/workImport")
            browser.is_text_present("Import prac", wait_time=10)

            s1 = browser.html[browser.html.find("wgranych")+len("wgranych"):]
            s2 = s1[s1.find("wgranych:</span>\n\t\t\t\t\t\t\t\t")+len("wgranych:</span>\n\t\t\t\t\t\t\t\t"):]
            wgranych = s2.split("<", 2)[0]

            s1 = browser.html[browser.html.find("wszystkich")+len("wszystkich"):]
            s2 = s1[s1.find("wszystkich:</span> ")+len("wszystkich:</span> "):]
            wszystkich = s2.split("<", 2)[0]

            if wgranych != wszystkich and options['fix'] == 1:
                ktora = int(wgranych)+1
                call_command('pbn_extract', file=options['file'], ktora=ktora)
                from .pbn_extract import new_filename

                import ipdb; ipdb.set_trace()

                call_command('pbn_upload',
                             file=new_filename(options['file'], ktora),
                             login=options['login'],
                             wydzial=options['wydzial'],
                             password=options['password'],
                             fix='0')

        finally:
            browser.quit()