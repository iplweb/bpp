# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models.patent import Patent, Patent_Autor
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, \
    Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte, \
    Wydawnictwo_Zwarte_Autor


def znajdz_i_napraw_podwojnych(model, autor_model):
    rekord_pk = None
    poprzednia_kolejnosc = None

    for obj in autor_model.objects.all().order_by('rekord', 'kolejnosc'):
        # print autor_model, obj.rekord_id, obj.pk, obj.kolejnosc

        if obj.rekord_id != rekord_pk:
            rekord_pk = obj.rekord_id
            poprzednia_kolejnosc = None
            autorzy = []

            if obj.kolejnosc != 1:
                print("XX Dla rekordu %r %r autorzy zaczynaja sie od kolejnosci %i" % (
                    autor_model, obj.pk, obj.kolejnosc))

        if poprzednia_kolejnosc == obj.kolejnosc:
            print("XX Wykryto zdublowana kolejnosc %i dla wpisu %s %s" % (
                poprzednia_kolejnosc, autor_model, obj.pk))

        if poprzednia_kolejnosc is not None:
            delta = obj.kolejnosc - poprzednia_kolejnosc
            if delta != 1:
                print("XX roznica w kolejnosci wynosi %i dla rekordu %s %s" % (
                    delta, autor_model, obj.pk
                ))

        poprzednia_kolejnosc = obj.kolejnosc

        if obj.autor_id in autorzy:
            print("XX zdublowany autor %i dla rekordu %s %s (rekord_id %s)" % (
                obj.autor_id, autor_model, obj.pk, obj.rekord_id
            ))

            autorzy.append(obj.autor_id)



class Command(BaseCommand):
    help = 'Naprawia indeks autorow - szuka wpisów o tej samej kolejności'

    @transaction.atomic
    def handle(self, *args, **options):

        for model, autor_model in [
            (Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor),
            (Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor),
            (Patent, Patent_Autor)]:
            znajdz_i_napraw_podwojnych(model, autor_model)