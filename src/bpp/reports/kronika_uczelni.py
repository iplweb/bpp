# -*- encoding: utf-8 -*-
from tempfile import mkstemp
from celeryui.registry import ReportAdapter
from django.core.files.base import ContentFile
from django.template.loader import render_to_string
from bpp.models import Jednostka, Zrodlo, Wydzial
from bpp.models.kronika_view import Kronika_View
from bpp.reports import slugify, addToRegistry

class Kronika_Uczelni(ReportAdapter):
    slug = "kronika-uczelni"

    def _get_title(self):
        return "Kronika Uczelni dla roku %s" % self.original.arguments['rok']
    title = property(_get_title)

    def readable_arguments(self):
        return "rok = %s" % self.original.arguments['rok']

    def perform(self):
        report = self.original
        rok = report.arguments['rok']

        fd, nazwa = mkstemp()

        prace_do_kroniki = Kronika_View.objects.filter(rok=rok)

        dct = {}
        dct['rok'] = rok

        numerek = 1
        numerki = {}
        for praca in prace_do_kroniki:
            if praca.kolejnosc == 1:
                praca.numerek = numerek
                numerki[(praca.object, praca.object_pk)] = numerek
                numerek += 1

        for praca in prace_do_kroniki:
            if praca.kolejnosc != 1:
                praca.numerek = numerki.get((praca.object, praca.object_pk))

        old_autor = None
        cnt = 1
        for no, elem in enumerate(prace_do_kroniki):
            if elem.autor_id == old_autor:
                cnt += 1
            else:
                cnt = 1

            elem.cnt = cnt
            old_autor = elem.autor_id

        dct['prace_dla_roku'] = prace_do_kroniki
        dct['zrodla'] = Zrodlo.objects.filter(
            pk__in=prace_do_kroniki.values_list('zrodlo_id').distinct())
        dct['jednostki'] = Jednostka.objects.filter(
            pk__in=prace_do_kroniki.values_list('jednostka_id').distinct())
        dct['wydzialy'] = Wydzial.objects.filter(
            id__in=dct['jednostki'].values_list('wydzial_id').distinct())

        for jednostka in dct['jednostki']:
            jednostka.numery_prac = set()

        jednostka_lookup = dict([
            (jednostka.pk, jednostka) for jednostka in dct['jednostki']
        ])

        for praca in prace_do_kroniki:
            if praca.kolejnosc == 1:
                jednostka_lookup[praca.jednostka_id].numery_prac.add(praca.numerek)

        for wydzial in dct['wydzialy']:
            wydzial.jednostki_do_kroniki = list(Jednostka.objects.filter(
                wydzial=wydzial, pk__in=[x.pk for x in dct['jednostki']]))
            for jednostka in wydzial.jednostki_do_kroniki:
                jednostka.numery_prac = jednostka_lookup[jednostka.pk].numery_prac

        myfile = ContentFile(render_to_string("raporty/kronika_uczelni.html", dct))
        report.file.save(str(self.original.uid) + ".html", myfile)

addToRegistry(Kronika_Uczelni)
