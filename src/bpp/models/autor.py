# -*- encoding: utf-8 -*-

"""
Autorzy
"""
from datetime import date, timedelta
from datetime import datetime

from autoslug import AutoSlugField
from django.contrib.postgres.search import SearchVectorField as VectorField
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models, IntegrityError
from django.db.models import Sum
from django.urls.base import reverse
from django.utils import six
from lxml.etree import Element, SubElement

from bpp.models import ModelZAdnotacjami, NazwaISkrot
from bpp.models.abstract import ModelZPBN_ID
from bpp.util import FulltextSearchMixin


class Tytul(NazwaISkrot):
    class Meta:
        verbose_name = 'tytuł'
        verbose_name_plural = 'tytuły'
        app_label = 'bpp'
        ordering = ('skrot',)


class Plec(NazwaISkrot):
    class Meta:
        verbose_name = "płeć"
        verbose_name_plural = "płcie"
        app_label = 'bpp'


class AutorManager(FulltextSearchMixin, models.Manager):
    pass

@six.python_2_unicode_compatible
class Autor(ModelZAdnotacjami, ModelZPBN_ID):
    imiona = models.CharField(max_length=512, db_index=True)
    nazwisko = models.CharField(max_length=256, db_index=True)
    tytul = models.ForeignKey(Tytul, blank=True, null=True)

    aktualny = models.BooleanField("Aktualny?", default=False, help_text="""Jeżeli zaznaczone, pole to oznacza,
    że autor jest aktualnie - na dziś dzień - przypisany do jakiejś jednostki w bazie danych i jego przypisanie
    do tej jednostki nie zostało zakończone wraz z konkretną datą w 
    przeszłości.""", db_index=True)

    aktualna_jednostka = models.ForeignKey('Jednostka', blank=True, null=True, related_name='aktualna_jednostka')
    aktualna_funkcja = models.ForeignKey('Funkcja_Autora', blank=True, null=True, related_name='aktualna_funkcja')

    pokazuj = models.BooleanField(
        default=True,
        help_text="Pokazuj autora na stronach jednostek oraz w rankingu. ")

    email = models.EmailField("E-mail", max_length=128, blank=True, null=True)
    www = models.URLField("WWW", max_length=1024, blank=True, null=True)

    plec = models.ForeignKey(Plec, null=True, blank=True)

    urodzony = models.DateField(blank=True, null=True)
    zmarl = models.DateField(blank=True, null=True)
    poprzednie_nazwiska = models.CharField(
        max_length=1024, blank=True, null=True, help_text="""Jeżeli ten
        autor(-ka) posiada nazwisko panieńskie, pod którym ukazywały
        się publikacje lub zmieniał nazwisko z innych powodów, wpisz tutaj
        wszystkie poprzednie nazwiska, oddzielając je przecinkami.""",
        db_index=True)

    pesel_md5 = models.CharField(verbose_name="PESEL MD5",
                                 max_length=32, db_index=True, blank=True, null=True,
                                 help_text="Hash MD5 numeru PESEL")

    orcid = models.CharField(
        "Identyfikator ORCID",
        max_length=19,
        blank=True, null=True,
        help_text="Open Researcher and Contributor ID, "
                  "vide http://www.orcid.org",
        validators=[
            RegexValidator(
                regex='^\d\d\d\d-\d\d\d\d-\d\d\d\d-\d\d\d(\d|X)$',
                message='Identyfikator ORCID to 4 grupy po 4 cyfry w każdej, '
                        'oddzielone myślnikami',
                code='orcid_invalid_format'
            ),
        ]
    )

    search = VectorField()

    objects = AutorManager()

    slug = AutoSlugField(
        populate_from='get_full_name',
        unique=True,
        max_length=1024)

    sort = models.TextField()

    jednostki = models.ManyToManyField('bpp.Jednostka', through='Autor_Jednostka')

    def get_absolute_url(self):
        return reverse("bpp:browse_autor", args=(self.slug,))

    class Meta:
        verbose_name = 'autor'
        verbose_name_plural = 'autorzy'
        ordering = ['sort']
        app_label = 'bpp'

    def __str__(self):
        buf = "%s %s" % (self.nazwisko, self.imiona)

        if self.poprzednie_nazwiska:
            buf += " (%s)" % self.poprzednie_nazwiska

        if self.tytul is not None:
            buf += ", " + six.text_type(self.tytul.skrot)
        return buf

    def dodaj_jednostke(self, jednostka, rok=None, funkcja=None):
        if rok is None:
            rok = datetime.now().date().year - 1

        start_pracy = date(rok, 1, 1)
        koniec_pracy = date(rok, 12, 31)

        if Autor_Jednostka.objects.filter(
                autor=self,
                jednostka=jednostka,
                rozpoczal_prace__lte=start_pracy,
                zakonczyl_prace__gte=koniec_pracy):
            # Ten czas jest już pokryty
            return

        try:
            Autor_Jednostka.objects.create(
                autor=self, rozpoczal_prace=start_pracy,
                jednostka=jednostka, funkcja=funkcja,
                zakonczyl_prace=koniec_pracy)
        except IntegrityError:
            return
        self.defragmentuj_jednostke(jednostka)

    def defragmentuj_jednostke(self, jednostka):
        Autor_Jednostka.objects.defragmentuj(autor=self, jednostka=jednostka)

    def save(self, *args, **kw):
        self.sort = (self.nazwisko.lower().replace("von ", "") + self.imiona).lower()
        ret = super(Autor, self).save(*args, **kw)

        for jednostka in self.jednostki.all():
            self.defragmentuj_jednostke(jednostka)

        return ret

    def afiliacja_na_rok(self, rok, wydzial, rozszerzona=False):
        """
        Czy autor w danym roku był w danym wydziale?

        :param rok:
        :param wydzial:
        :return: True gdy w danym roku był w danym wydziale
        """
        start_pracy = date(rok, 1, 1)
        koniec_pracy = date(rok, 12, 31)

        if Autor_Jednostka.objects.filter(
                autor=self,
                rozpoczal_prace__lte=start_pracy,
                zakonczyl_prace__gte=koniec_pracy,
                jednostka__wydzial=wydzial
        ):
            return True

        # A może ma wpisaną tylko datę początku pracy? W takiej sytuacji
        # stwierdzamy, że autor NADAL tam pracuje, bo nie ma końca, więc:
        if Autor_Jednostka.objects.filter(
                autor=self,
                rozpoczal_prace__lte=start_pracy,
                zakonczyl_prace=None,
                jednostka__wydzial=wydzial
        ):
            return True

        # Jeżeli nie ma takiego rekordu z dopasowaniem z datami, to może jest
        # rekord z dopasowaniem JAKIMKOLWIEK innym?
        # XXX po telefonie p. Małgorzaty Zając dnia 2013-03-25 o godzinie 11:55
        # dostałem informację, że NIE interesują nas tacy autorzy, zatem:

        if not rozszerzona:
            return

        # ... aczkolwiek, sprawdzanie afiliacji do wydziału dla niektórych autorów może
        # być przydatne np przy importowaniu imion i innych rzeczy, więc sprawdźmy w sytuacj
        # gdy jest rozszerzona afiliacja:

        if Autor_Jednostka.objects.filter(
            autor=self, jednostka__wydzial=wydzial):
            return True

    def get_full_name(self):
        buf = "%s %s" % (self.imiona, self.nazwisko)
        if self.poprzednie_nazwiska:
            buf += " (%s)" % self.poprzednie_nazwiska
        return buf

    def get_full_name_surname_first(self):
        buf = "%s" % self.nazwisko
        if self.poprzednie_nazwiska:
            buf += " (%s)" % self.poprzednie_nazwiska
        buf += " %s" % self.imiona
        return buf

    def prace_w_latach(self):
        """Zwraca lata, w których ten autor opracowywał jakiekolwiek prace."""
        from bpp.models.cache import Rekord
        return Rekord.objects.prace_autora(self).values_list(
            'rok', flat=True).distinct().order_by('rok')

    def eksport_pbn_serializuj(self, tagname='author', affiliated=True, employed=True):
        author = Element(tagname)

        imiona = self.imiona.replace(".", " ")
        if self.pbn_id:
            imiona = imiona.replace("*", "")

        given_names = SubElement(author, 'given-names')
        given_names.text = imiona

        nazwisko = self.nazwisko
        if self.pbn_id:
            nazwisko = nazwisko.replace("*", "")

        family_name = SubElement(author, 'family-name')
        family_name.text = nazwisko

        system_identifier = SubElement(author, 'system-identifier', system="BPP-ID")
        system_identifier.text = str(self.pk)

        if self.pbn_id:
            pbn_id_system_identifier = SubElement(author, 'system-identifier', system="PBN-ID")
            pbn_id_system_identifier.text = str(self.pbn_id)

        affiliated_to_unit = SubElement(author, 'affiliated-to-unit')
        if affiliated:
            affiliated_to_unit.text = 'true'
        else:
            affiliated_to_unit.text = 'false'

        employed_in_unit = SubElement(author, 'employed-in-unit')
        if employed:
            employed_in_unit.text = 'true'
        else:
            employed_in_unit.text = 'false'

        return author

    def liczba_cytowan(self):
        """Zwraca liczbę cytowań prac danego autora
        """
        from bpp.models.cache import Rekord
        return Rekord.objects.prace_autora(self)\
            .distinct()\
            .aggregate(s=Sum('liczba_cytowan'))['s']

    def liczba_cytowan_afiliowane(self):
        """Zwraca liczbę cytowań prac danego autora tam,
        gdzie została podana afiliacja na jednostkę uczelni"""
        from bpp.models.cache import Rekord
        return Rekord.objects.prace_autora_z_afiliowanych_jednostek(self)\
            .distinct()\
            .aggregate(s=Sum('liczba_cytowan'))['s']


class Funkcja_Autora(NazwaISkrot):
    """Funkcja autora w jednostce"""

    class Meta:
        verbose_name = 'funkcja w jednostce'
        verbose_name_plural = 'funkcje w jednostkach'
        ordering = ['nazwa']
        app_label = 'bpp'


class Autor_Jednostka_Manager(models.Manager):
    def defragmentuj(self, autor, jednostka):
        poprzedni_rekord = None
        usun = []
        for rec in Autor_Jednostka.objects.filter(
                autor=autor, jednostka=jednostka).order_by('rozpoczal_prace'):

            if poprzedni_rekord is None:
                poprzedni_rekord = rec
                continue

            if rec.rozpoczal_prace is None and rec.zakonczyl_prace is None:
                # Nic nie wnosi tutaj taki rekord ORAZ nie jest to 'poprzedni'
                # rekord, więc:
                usun.append(rec)
                continue

            # Przy imporcie danych z XLS na dane ze starego systemu - obydwa pola są None
            if poprzedni_rekord.zakonczyl_prace is None and poprzedni_rekord.rozpoczal_prace is None:
                usun.append(poprzedni_rekord)
                poprzedni_rekord = rec
                continue

            # Nowy system - przy imporcie danych z XLS do nowego systemu jest sytuacja, gdy autor
            # zaczął kiedyśtam prace ALE jej nie zakończył:
            if poprzedni_rekord.zakonczyl_prace is None:
                if rec.rozpoczal_prace is None and poprzedni_rekord.rozpoczal_prace is not None:
                    if rec.zakonczyl_prace == poprzedni_rekord.rozpoczal_prace:
                        usun.append(rec)
                        poprzedni_rekord.rozpoczal_prace=rec.rozpoczal_prace
                        poprzedni_rekord.save()
                        continue

                if rec.rozpoczal_prace >= poprzedni_rekord.rozpoczal_prace:
                    usun.append(rec)
                    poprzedni_rekord.zakonczyl_prace = rec.zakonczyl_prace
                    poprzedni_rekord.save()
                    continue

            if rec.rozpoczal_prace == poprzedni_rekord.zakonczyl_prace + timedelta(days=1):
                usun.append(rec)
                poprzedni_rekord.zakonczyl_prace = rec.zakonczyl_prace
                poprzedni_rekord.save()
            else:
                poprzedni_rekord = rec

        for aj in usun:
            aj.delete()

@six.python_2_unicode_compatible
class Autor_Jednostka(models.Model):
    """Powiązanie autora z jednostką"""
    autor = models.ForeignKey(Autor)
    jednostka = models.ForeignKey('bpp.Jednostka')
    rozpoczal_prace = models.DateField("Rozpoczął pracę",
                                       blank=True, null=True, db_index=True)
    zakonczyl_prace = models.DateField(
        "Zakończył pracę", null=True, blank=True, db_index=True)
    funkcja = models.ForeignKey(Funkcja_Autora, null=True, blank=True)

    objects = Autor_Jednostka_Manager()

    def clean(self, exclude=None):
        if self.rozpoczal_prace is not None and self.zakonczyl_prace is not None:
            if self.rozpoczal_prace >= self.zakonczyl_prace:
                raise ValidationError("Początek pracy późniejszy lub równy, jak zakończenie")

        if self.zakonczyl_prace is not None:
            if self.zakonczyl_prace >= datetime.now().date():
                raise ValidationError(
                    "Czas zakończenia pracy w jednostce nie może być taki sam"
                    " lub większy, jak obecna data")

    def __str__(self):
        buf = "%s ↔ %s" % (self.autor, self.jednostka.skrot)
        if self.funkcja:
            buf = "%s ↔ %s, %s" % (
                self.autor,
                self.funkcja.nazwa,
                self.jednostka.skrot)
        return buf

    class Meta:
        verbose_name = "powiązanie autor-jednostka"
        verbose_name_plural = "powiązania autor-jednostka"
        ordering = ['autor__nazwisko', 'jednostka__nazwa', 'rozpoczal_prace']
        unique_together = [('autor', 'jednostka', 'rozpoczal_prace')]
        app_label = 'bpp'
