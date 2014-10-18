# -*- encoding: utf-8 -*-

"""
Klasy abstrakcyjne
"""
from datetime import datetime
from decimal import Decimal
from django.db import models
from django.db.models.fields import TextField
from djorm_pgarray.fields import TextArrayField
from djorm_pgfulltext.fields import VectorField
from bpp.fields import YearField
from bpp.models.util import ModelZOpisemBibliograficznym


class ModelZAdnotacjami(models.Model):
    """Zawiera adnotację  dla danego obiektu, czyli informacje, które
    użytkownik może sobie dowolnie uzupełnić.
    """
    ostatnio_zmieniony = models.DateTimeField(
        auto_now=True, auto_now_add=True, null=True, db_index=True)
    adnotacje = models.TextField(help_text="""Pole do użytku wewnętrznego -
    wpisane tu informacje nie są wyświetlane na stronach WWW dostępnych
    dla użytkowników końcowych.""", null=True, blank=True, db_index=True)

    class Meta:
        abstract = True


class ModelZNazwa(models.Model):
    """Nazwany model."""
    nazwa = models.CharField(max_length=512, unique=True)

    def __unicode__(self):
        return self.nazwa

    class Meta:
        abstract = True
        ordering = ['nazwa']


class NazwaISkrot(ModelZNazwa):
    """Model z nazwą i ze skrótem"""
    skrot = models.CharField(max_length=128, unique=True)

    class Meta:
        abstract = True


class NazwaWDopelniaczu(models.Model):
    nazwa_dopelniacz_field = models.CharField(
        u"Nazwa w dopełniaczu", max_length=512, null=True, blank=True)

    class Meta:
        abstract = True

    def nazwa_dopelniacz(self):
        if not hasattr(self, 'nazwa'):
            return self.nazwa_dopelniacz_field
        if self.nazwa_dopelniacz_field is None \
            or self.nazwa_dopelniacz_field == '':
            return self.nazwa
        return self.nazwa_dopelniacz_field


class ModelZISSN(models.Model):
    """Model z numerem ISSN oraz E-ISSN"""
    issn = models.CharField("ISSN", max_length=32, blank=True, null=True)
    e_issn = models.CharField("e-ISSN", max_length=32, blank=True, null=True)

    class Meta:
        abstract = True


class ModelZISBN(models.Model):
    """Model z numerem ISBN oraz E-ISBN"""
    isbn = models.CharField("ISBN", max_length=64, blank=True, null=True)
    e_isbn = models.CharField("E-ISBN", max_length=64, blank=True, null=True)

    class Meta:
        abstract = True


class ModelZInformacjaZ(models.Model):
    """Model zawierający pole 'Informacja z' - czyli od kogo została
    dostarczona informacja o publikacji (np. od autora, od redakcji)."""
    informacja_z = models.ForeignKey('Zrodlo_Informacji', null=True, blank=True)

    class Meta:
        abstract = True


class DwaTytuly(models.Model):
    """Model zawierający dwa tytuły: tytuł oryginalny pracy oraz tytuł
    przetłumaczony."""
    tytul_oryginalny = models.TextField("Tytuł oryginalny", db_index=True)
    tytul = models.TextField("Tytuł", null=True, blank=True, db_index=True)

    class Meta:
        abstract = True


class ModelZeStatusem(models.Model):
    """Model zawierający pole statusu korekty, oraz informację, czy
    punktacja została zweryfikowana."""
    status_korekty = models.ForeignKey('Status_Korekty', default=1)

    class Meta:
        abstract = True


class ModelZRokiem(models.Model):
    """Model zawierający pole "Rok" """
    rok = YearField(
        help_text="""Rok uwzględniany przy wyszukiwaniu i raportach
        KBN/MNiSW)""", db_index=True)

    class Meta:
        abstract = True


class ModelZWWW(models.Model):
    """Model zawierający adres strony WWW"""
    www = models.URLField("Adres WWW", max_length=1024, blank=True, null=True)

    class Meta:
        abstract = True


class ModelAfiliowanyRecenzowany(models.Model):
    """Model zawierający informacje o afiliowaniu/recenzowaniu pracy."""
    afiliowana = models.BooleanField(default=False)
    recenzowana = models.BooleanField(default=False)

    class Meta:
        abstract = True


class ModelPunktowanyBaza(models.Model):
    impact_factor = models.DecimalField(
        max_digits=6, decimal_places=3,
        default=Decimal("0.000"), db_index=True)
    punkty_kbn = models.DecimalField(
        "Punkty KBN", max_digits=6, decimal_places=2,
        default=Decimal("0.00"), db_index=True)
    index_copernicus = models.DecimalField(
        "Index Copernicus", max_digits=6, decimal_places=2,
        default=Decimal("0.00"), db_index=True)
    punktacja_wewnetrzna = models.DecimalField(
        "Punktacja wewnętrzna", max_digits=6, decimal_places=2,
        default=Decimal("0.00"), db_index=True)

    kc_impact_factor = models.DecimalField(
        "KC: Impact factor", max_digits=6, decimal_places=2,
        default=None, blank=True, null=True, help_text="""Jeżeli wpiszesz
        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji
        Centralnej w punkcie IXa tego raportu.""", db_index=True)
    kc_punkty_kbn = models.DecimalField(
        "KC: Punkty KBN", max_digits=6, decimal_places=2,
        default=None, blank=True, null=True, help_text="""Jeżeli wpiszesz
        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji
        Centralnej w punkcie IXa i IXb tego raportu.""", db_index=True)
    kc_index_copernicus = models.DecimalField(
        "KC: Index Copernicus", max_digits=6, decimal_places=2,
        default=None, blank=True, null=True, help_text="""Jeżeli wpiszesz
        wartość w to pole, to zostanie ona użyta w raporcie dla Komisji
        Centralnej w punkcie IXa i IXb tego raportu.""")

    class Meta:
        abstract = True


class ModelPunktowany(ModelPunktowanyBaza):
    """Model zawiereający informację o punktacji."""

    weryfikacja_punktacji = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def ma_punktacje(self):
        """Zwraca 'True', jeżeli ten rekord ma jakąkolwiek punktację,
        czyli jeżeli dowolne z jego pól ma wartość nie-zerową"""

        for pole in POLA_PUNKTACJI:
            f = getattr(self, pole)

            if f is None:
                continue

            if type(f) == Decimal:
                if not f.is_zero():
                    return True
            else:
                if f != 0:
                    return True

        return False


POLA_PUNKTACJI = [
    x.name for x in ModelPunktowany._meta.fields
    if x.name not in ['weryfikacja_punktacji', ]]

from bpp.models.system import Charakter_Formalny


class ModelTypowany(models.Model):
    """Model zawierający typ KBN oraz język."""
    typ_kbn = models.ForeignKey('Typ_KBN', verbose_name="Typ KBN")
    jezyk = models.ForeignKey('Jezyk', verbose_name="Język")

    class Meta:
        abstract = True


class BazaModeluOdpowiedzialnosciAutorow(models.Model):
    """Bazowa klasa dla odpowiedzialności autorów (czyli dla przypisania
    autora do czegokolwiek innego). Zawiera wszystkie informacje dla autora,
    czyli: powiązanie ForeignKey, jednostkę, rodzaj zapisu nazwiska, ale
    nie zawiera podstawowej informacji, czyli powiązania"""
    autor = models.ForeignKey('Autor')
    jednostka = models.ForeignKey('Jednostka')
    kolejnosc = models.IntegerField('Kolejność', default=0)
    typ_odpowiedzialnosci = models.ForeignKey('Typ_Odpowiedzialnosci',
                                              verbose_name="Typ odpowiedzialności")
    zapisany_jako = models.CharField(max_length=512)

    class Meta:
        abstract = True
        ordering = ('kolejnosc', 'typ_odpowiedzialnosci__skrot')

    def __unicode__(self):
        return unicode(self.autor) + u" - " + unicode(self.jednostka.skrot)

    # XXX TODO sprawdzanie, żęby nie było dwóch autorów o tej samej kolejności

    def save(self, *args, **kw):
        if self.autor.jednostki.filter(pk=self.jednostka.pk).count() == 0:
            self.jednostka.dodaj_autora(self.autor)
        return super(BazaModeluOdpowiedzialnosciAutorow, self).save(*args, **kw)



class ModelZeSzczegolami(models.Model):
    """Model zawierający pola: informacje, szczegóły, uwagi, słowa kluczowe."""
    informacje = models.TextField(
        "Informacje", null=True, blank=True)

    szczegoly = models.CharField(
        "Szczegóły", max_length=512, null=True, blank=True,
        help_text="Np. str. 23-45")

    uwagi = models.TextField(null=True, blank=True, db_index=True)

    slowa_kluczowe = models.TextField("Słowa kluczowe", null=True, blank=True)

    utworzono = models.DateTimeField(
        "Utworzono", auto_now_add=True, default=datetime(1970,1,1))

    class Meta:
        abstract = True


class ModelZCharakterem(models.Model):
    charakter_formalny = models.ForeignKey(
        Charakter_Formalny, verbose_name='Charakter formalny')

    class Meta:
        abstract = True

class ModelPrzeszukiwalny(models.Model):
    """Model zawierający pole pełnotekstowego przeszukiwania
    'search_index'"""

    search_index = VectorField()
    tytul_oryginalny_sort = models.TextField(db_index=True, default='')

    class Meta:
        abstract = True

class Wydawnictwo_Baza(ModelZOpisemBibliograficznym, ModelPrzeszukiwalny):
    def __unicode__(self):
        return self.tytul_oryginalny

    class Meta:
        abstract = True


class ModelHistoryczny(models.Model):
    rozpoczecie_funkcjonowania = models.DateField(
        "Rozpoczęcie funkcjonowania", blank=True, null=True)
    zakonczenie_funkcjonowania = models.DateField(
        "Zakończenie funkcjonowania", blank=True, null=True
    )

    class Meta:
        abstract = True
        
