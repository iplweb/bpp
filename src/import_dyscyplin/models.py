from datetime import date

from django.contrib.postgres.fields import JSONField
from django.db import models, transaction
# 1) formularz wrzucania pliku,
# 2) task analizujący, integrujący dane, informujący (mail + notyfikacja)
# 3) view wyświetlający live table z rekordami:
#    - zmatchowanymi
#   - niezmatchowanymi
#   - dający możliwość edycji poprawienia
# 4) opcja zatwierdzenia importu
# 5)
# 1) task usuwający importy po 24 godzinach
#
from django.dispatch import receiver
from django.urls import reverse
from django_fsm import FSMField, transition, GET_STATE, post_transition
from model_utils.models import TimeStampedModel

import notifications
from bpp.fields import YearField
from bpp.models import Autor, Jednostka, Wydzial
from django_bpp.settings.base import AUTH_USER_MODEL
# TODO:
# - napisac testy do create z wrzucaniem pliku
# - testy do details z pokazywaniem
# - przemyslec: diff ma byc liczony wobec:
from import_dyscyplin.exceptions import ImproperFileException, BadNoOfSheetsException, HeaderNotFoundException


def obecny_rok():
    return date.today().year


class Import_Dyscyplin(TimeStampedModel):
    class STAN:
        NOWY = 'nowy'
        BLEDNY = 'błędny'
        PRZEANALIZOWANY = 'przeanalizowany'

        ZINTEGROWANY = 'zintegrowany'

    STANY = (STAN.NOWY,
             STAN.PRZEANALIZOWANY,
             STAN.BLEDNY,
             STAN.ZINTEGROWANY)

    owner = models.ForeignKey(AUTH_USER_MODEL)
    web_page_uid = models.CharField(max_length=36, blank=True, null=True)
    web_page_uid.__doc__ = "UUID4 strony internetowej która może być używana do notyfikacji. "

    plik = models.FileField()
    rok = YearField(default=obecny_rok)
    stan = FSMField(
        default=STAN.NOWY,
        choices=zip(STANY, STANY),
        protected=True)

    bledny = models.BooleanField(default=False)
    info = models.TextField(blank=True, null=True)

    @transition(field=stan,
                source=STAN.NOWY,
                target=GET_STATE(
                    lambda self: "błędny" if self.bledny else "przeanalizowany",
                    states=[STAN.BLEDNY, STAN.PRZEANALIZOWANY]),
                on_error=STAN.BLEDNY)
    def przeanalizuj(self):
        from import_dyscyplin.core import przeanalizuj_plik_xls

        try:
            res = przeanalizuj_plik_xls(self.plik.path, parent=self)
        except ImproperFileException as e:
            self.bledny = True
            self.info = "niepoprawny plik - %s" % e
        except BadNoOfSheetsException as e:
            self.bledny = True
            self.info = "Plik musi zawierać tylko jeden arkusz"
        except HeaderNotFoundException:
            self.bledny = True
            self.info = "Nagłówek nie został znaleziony"

    def delete(self, *args, **kw):
        transaction.on_commit(
            lambda instance=self: instance.plik.delete(False)
        )
        return super(Import_Dyscyplin, self).delete(*args, **kw)


class Import_Dyscyplin_Row(models.Model):
    parent = models.ForeignKey(Import_Dyscyplin)

    row_no = models.IntegerField()
    original = JSONField()

    autor = models.ForeignKey(
        Autor,
        null=True,
        on_delete=models.SET_NULL)

    jednostka = models.ForeignKey(
        Jednostka,
        null=True,
        on_delete=models.SET_NULL)

    wydzial = models.ForeignKey(
        Wydzial,
        null=True,
        on_delete=models.SET_NULL)
