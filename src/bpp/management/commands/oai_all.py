# -*- encoding: utf-8 -*-
from datetime import datetime

from django.core.management import BaseCommand
from django.db import transaction
import sys
from bpp.models import cache


class Command(BaseCommand):
    help = 'Odbudowuje cache'

    def handle(self, *args, **options):
        from xml.etree import ElementTree
        import requests

        url = "http://bpp.umlub.pl:9080/bpp/oai/oai-pmh-repository.xml"
        params = {
            'verb': "ListRecords",
            'metadataPrefix': "oai_dc",
            'from': "2000-01-01T00:00:00Z",
            'until': "2020-01-01T00:00:00Z"
        }

        start = datetime.now()

        res = requests.get(url, params=params)
        print(res.content)
        
        while True:

            try:
                r = ElementTree.XML(res.content)
            except Exception as e:
                print(res.content)
                raise e

            try:
                resumptionToken = r.getchildren()[2].getchildren()[-1].text
            except IndexError:
                break

            delta = datetime.now() - start
            seconds = float(delta.seconds + delta.microseconds/1000000.0)

            print('\r', resumptionToken[:20], "response len: ", len(res.content), "response time: ", delta, "b/s: ", ("%.2f" % (len(res.content)/seconds)), end=' ')
            sys.stdout.flush()
            #print "%r" %  r.getchildren()[2].getchildren()[0][1].getchildren()[0].getchildren()[0].text[:78]

            newParams= {
                'verb': "ListRecords",
                "resumptionToken": resumptionToken
            }
            params['resumptionToken'] = resumptionToken

            start = datetime.now()
            res = requests.get(url, params=newParams)
