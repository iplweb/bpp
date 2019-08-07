# -*- encoding: utf-8 -*-

from django.core.management import BaseCommand
from django.db import transaction

from bpp.models import Wydawca, Wydawnictwo_Zwarte, Praca_Doktorska, Praca_Habilitacyjna


class Command(BaseCommand):
    help = 'Znajduje wydawców indeksowanych'

    @transaction.atomic
    def handle(self, *args, **options):
        for wydawca in Wydawca.objects.all():
            for klass in Wydawnictwo_Zwarte, Praca_Doktorska, Praca_Habilitacyjna:
                for model in klass.objects.filter(wydawca=None, rok__gte=2017).filter(wydawca_opis__istartswith=wydawca.nazwa):
                    if model.wydawca_opis == 'Wydawnictwo naukowe PWN SA':
                        model.wydawca_opis = 'Wydawnictwo Naukowe PWN SA'
                        model.save()

                    stare_wydawnictwo = model.wydawnictwo
                    model.wydawca = wydawca
                    model.wydawca_opis = model.wydawca_opis[len(wydawca.nazwa):].strip()
                    if stare_wydawnictwo.strip() != model.wydawnictwo:
                        print("Nie zgadza mi sie: stare wydawnictwo z nowym: %r != %r, nie zapisuje" % (
                        stare_wydawnictwo, model.wydawnictwo))
                    else:
                        if stare_wydawnictwo != wydawca.nazwa:
                            print("Ciąg znaków %r przypisuję do indeksowanego wydawcy ID %i nazwa %r (%r ID %s)" % (
                                stare_wydawnictwo, wydawca.pk, wydawca.nazwa,
                                model.pk, model.tytul_oryginalny))
                        model.save()
