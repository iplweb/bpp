from datetime import date

from django.contrib.postgres.fields import JSONField
from django.db import models, transaction, IntegrityError
from django.db.models import Q, Count
from django.urls import reverse
from django_fsm import FSMField, transition, GET_STATE
from model_utils.models import TimeStampedModel

from bpp.fields import YearField
from bpp.models import Autor, Jednostka, Wydzial, Dyscyplina_Naukowa, Autor_Dyscyplina
from django_bpp.settings.base import AUTH_USER_MODEL
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

    task_id = models.CharField(max_length=36, blank=True, null=True)
    task_id.__doc__ = "celery.uuid() z identyfikatorem zadania"

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

    def wiersze(self):
        return Import_Dyscyplin_Row.objects.filter(parent=self)

    def poprawne_wiersze_do_integracji(self):
        return self.wiersze() \
            .exclude(autor_id=None) \
            .exclude(dyscyplina_naukowa=None, subdyscyplina_naukowa=None) \
            .exclude(stan=Import_Dyscyplin_Row.STAN.BLEDNY) \
            .exclude(stan=Import_Dyscyplin_Row.STAN.ZINTEGROWANY)

    def niepoprawne_wiersze(self):
        return self.wiersze().filter(
            Q(autor_id=None) |
            Q(stan=Import_Dyscyplin_Row.STAN.BLEDNY) |
            Q(dyscyplina_naukowa=None, subdyscyplina_naukowa=None)
        )

    def distinct_info_dla_qs(self, qs):
        return qs.order_by("info") \
            .values("info") \
            .annotate(icount=Count('info')) \
            .distinct()

    def niepoprawne_wiersze_przyczyny(self):
        return self.distinct_info_dla_qs(self.niepoprawne_wiersze())

    def zintegrowane_wiersze_przyczyny(self):
        return self.distinct_info_dla_qs(self.zintegrowane_wiersze())

    def zintegrowane_wiersze(self):
        return self.wiersze().filter(
            stan=Import_Dyscyplin_Row.STAN.ZINTEGROWANY
        )

    def integruj_dyscypliny(self):
        # order_by jest w poniższym zapytaniu potrzebny, żeby pozbyć się
        # problemu z domyślnym porządkiem sortowania, wywołanym przez
        # Import_Dyscyplin_Row.Meta - wówczas distinct powinien zawierać
        # również kolumny po których sortujemy, a to jest nam zbędne, więc:
        for elem in self.wiersze().order_by("dyscyplina").values(
                "dyscyplina",
                "kod_dyscypliny",
                "subdyscyplina",
                "kod_subdyscypliny").distinct():

            if not elem['dyscyplina'] or not elem['kod_dyscypliny']:
                continue

            try:
                d, _c = Dyscyplina_Naukowa.objects.get_or_create(
                    nazwa=elem['dyscyplina'],
                    kod=elem['kod_dyscypliny'],
                    dyscyplina_nadrzedna=None
                )
            except IntegrityError:
                for r in self.wiersze().filter(
                        dyscyplina=elem['dyscyplina'],
                        kod_dyscypliny=elem['kod_dyscypliny']):
                    r.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                    r.info = "Nie można zintegrować nazwy i kodu dyscypliny. W bazie danych istnieje " \
                             "już rekord o takiej nazwie i innym kodzie lub o takim kodzie ale o innej " \
                             "nazwie."
                    r.save()

                continue

            for r in self.wiersze().filter(
                    dyscyplina=elem['dyscyplina'],
                    kod_dyscypliny=elem['kod_dyscypliny']):
                r.dyscyplina_naukowa = d
                r.save()

            if not elem['subdyscyplina'] or not elem['kod_subdyscypliny']:
                continue

            try:
                sd, _c = Dyscyplina_Naukowa.objects.get_or_create(
                    nazwa=elem['subdyscyplina'],
                    kod=elem['kod_subdyscypliny'],
                    dyscyplina_nadrzedna=d
                )
            except IntegrityError:
                for r in self.wiersze().filter(
                        subdyscyplina=elem['subdyscyplina'],
                        kod_subdyscypliny=elem['kod_subdyscypliny']
                ):
                    r.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                    r.info = "Nie można zintegrować nazwy i kodu subdyscypliny. W bazie danych istnieje " \
                             "już rekord o takiej nazwie i innym kodzie lub o takim kodzie ale o innej " \
                             "nazwie."
                    r.save()
                continue

            for r in self.wiersze().filter(
                    subdyscyplina=elem['subdyscyplina'],
                    kod_subdyscypliny=elem['kod_subdyscypliny']
            ):
                r.subdyscyplina_naukowa = sd
                r.save()

        for r in self.wiersze():
            r.dyscyplina_ostateczna = r.subdyscyplina_naukowa or r.dyscyplina_naukowa
            r.save()

    def sprawdz_czy_konieczne(self):
        """Sprawdza wszystkie wiersze, po przeanalizowaniu oraz po
        integracji dyscyplin, czy wprowadzanie ich jest konieczne do bazy. To znaczy,
        jeżeli istnieją już takie przypisania do autora i dyscypliny, to oznacz
        takie rekordy adekwatnie.
        """
        for elem in self.poprawne_wiersze_do_integracji().select_related():
            try:
                Autor_Dyscyplina.objects.get(
                    autor=elem.autor,
                    rok=self.rok,
                    dyscyplina=elem.subdyscyplina_naukowa or elem.dyscyplina_naukowa
                )
                elem.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                elem.info = "Już istnieje takie przypisanie"
                elem.save()
            except Autor_Dyscyplina.DoesNotExist:
                pass

    def id_zdublowanych_autorow(self):
        return self.poprawne_wiersze_do_integracji() \
            .values_list("autor_id", flat=True) \
            .order_by("autor_id") \
            .annotate(acount=Count("autor_id")) \
            .filter(acount__gt=1).distinct()

    def sprawdz_czy_poprawne(self):
        """Sprawdza, czy są wiersze z podwójnym (tym samym) autorem w imporcie"""
        for elem in self.id_zdublowanych_autorow():
            for r in self.poprawne_wiersze_do_integracji().filter(autor_id=elem):
                r.stan = Import_Dyscyplin_Row.STAN.BLEDNY
                r.info = "Więcej, niż jeden wiersz z pliku XLS został dopasowany do tego autora w systemie."
                r.save()

    @transition(field=stan,
                source=STAN.PRZEANALIZOWANY,
                target=GET_STATE(
                    lambda self: "błędny" if self.bledny else "zintegrowany",
                    states=[STAN.BLEDNY, STAN.ZINTEGROWANY]),
                on_error=STAN.BLEDNY)
    def integruj_wiersze(self):
        return self._integruj_wiersze()

    def _integruj_wiersze(self):
        for elem in self.poprawne_wiersze_do_integracji().select_related():
            res = elem.subdyscyplina_naukowa or elem.dyscyplina_naukowa

            try:
                ad = Autor_Dyscyplina.objects.get(
                    autor=elem.autor,
                    rok=self.rok
                )

                if ad.dyscyplina != res:
                    elem.info = "istniejące dla roku %i zmieniono z %s na %s" % (
                        self.rok,
                        ad.dyscyplina,
                        res)

                    ad.dyscyplina = res
                    ad.save()

                else:
                    elem.info = "przypisanie %s dla roku %s już istniało" % (
                        ad.dyscyplina,
                        self.rok
                    )

            except Autor_Dyscyplina.DoesNotExist:
                Autor_Dyscyplina.objects.create(
                    autor=elem.autor,
                    rok=self.rok,
                    dyscyplina=res
                )
                elem.info = "nowe przypisanie dla %i: %s" % (self.rok, res)

            elem.stan = Import_Dyscyplin_Row.STAN.ZINTEGROWANY
            elem.save()

        Autor_Dyscyplina.objects.ukryj_nieuzywane()

    def delete(self, *args, **kw):
        transaction.on_commit(
            lambda instance=self: instance.plik.delete(False)
        )
        return super(Import_Dyscyplin, self).delete(*args, **kw)

    class Meta:
        ordering = ('-modified',)


class Import_Dyscyplin_Row(models.Model):
    class STAN:
        NOWY = "nowy"
        BLEDNY = "błędny"
        ZINTEGROWANY = "zintegrowany"

    STANY = (STAN.NOWY, STAN.BLEDNY, STAN.ZINTEGROWANY)

    parent = models.ForeignKey(Import_Dyscyplin)

    stan = models.CharField(
        max_length=50,
        choices=zip(STANY, STANY),
        default=STAN.NOWY,
        db_index=True)
    info = models.TextField(blank=True, null=True)

    row_no = models.IntegerField()
    original = JSONField()

    nazwisko = models.CharField(max_length=200)
    imiona = models.CharField(max_length=200)

    autor = models.ForeignKey(
        Autor,
        null=True,
        on_delete=models.SET_NULL)

    nazwa_jednostki = models.CharField(
        max_length=512, blank=True, null=True)
    jednostka = models.ForeignKey(
        Jednostka,
        null=True,
        on_delete=models.SET_NULL)

    nazwa_wydzialu = models.CharField(
        max_length=512, blank=True, null=True)
    wydzial = models.ForeignKey(
        Wydzial,
        null=True,
        on_delete=models.SET_NULL)

    dyscyplina = models.CharField(max_length=200, db_index=True)
    kod_dyscypliny = models.CharField(max_length=20, db_index=True)
    dyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'

    )

    subdyscyplina = models.CharField(max_length=200, null=True, blank=True, db_index=True)
    kod_subdyscypliny = models.CharField(max_length=20, null=True, blank=True, db_index=True)
    subdyscyplina_naukowa = models.ForeignKey(
        Dyscyplina_Naukowa,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )

    dyscyplina_ostateczna = models.ForeignKey(
        Dyscyplina_Naukowa,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )

    def serialize_dict(self):
        ret = {
            "nazwisko": self.nazwisko,
            "imiona": self.imiona,
            "jednostka": self.original['nazwa jednostki'],
            "wydzial": self.original['wydział'],

            "info": self.info,

            "dyscyplina": f"{ self.dyscyplina } ({ self.kod_dyscypliny })",
            "subdyscyplina": f"{ self.subdyscyplina } ({ self.kod_subdyscypliny })",

            "dopasowanie_autora": "-",
            "dyscyplina_ostateczna": "-"
        }

        for elem in "dyscyplina", "subdyscyplina":
            if ret[elem] == " ()":
                ret[elem] = ""

        if self.autor is not None:
            ret["autor_slug"] = self.autor.slug
            ret["dopasowanie_autora"] = "<a target=_blank href='%s'>%s %s</a>" % (
                reverse("bpp:browse_autor", args=(self.autor.slug,)),
                self.autor.nazwisko, self.autor.imiona)

        dyscyplina_ostateczna = self.dyscyplina_ostateczna
        if dyscyplina_ostateczna is not None:
            ret["dyscyplina_ostateczna"] = str(dyscyplina_ostateczna)

        return ret

    class Meta:
        ordering = ('nazwisko', 'imiona')
