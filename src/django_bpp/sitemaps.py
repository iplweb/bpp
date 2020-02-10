# -*- encoding: utf-8 -*-


from django.contrib.sitemaps import Sitemap

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from bpp.models import Jednostka
from bpp.models.autor import Autor
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.struktura import Uczelnia, Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


class BppSitemap(Sitemap):
    url_obj_field = "pk"

    def items(self):
        return self.klass.objects.all()

    def lastmod(self, obj):
        return obj.ostatnio_zmieniony

    def location(self, obj):
        return reverse(self.url, args=(getattr(obj, self.url_obj_field),))


class JednostkaSitemap(BppSitemap):
    changefreq = "yearly"
    klass = Jednostka
    url = "bpp:browse_jednostka"
    url_obj_field = "slug"


class UczelniaSitemap(BppSitemap):
    changefreq = "yearly"
    klass = Uczelnia
    url = "bpp:browse_uczelnia"
    url_obj_field = "slug"

    def items(self):
        # Funkcja musi zwrócić posortowane wyniki, w przeciwnym wypadku będzie ostrzeżenie
        return super().items().order_by("slug")


class WydzialSitemap(BppSitemap):
    changefreq = "yearly"
    klass = Wydzial
    url = "bpp:browse_wydzial"
    url_obj_field = "slug"

    def items(self):
        return self.klass.objects.filter(widoczny=True)


class AlphabeticBppSitemap(BppSitemap):
    changefreq = "weekly"
    url = "bpp:browse_praca"
    title_field = "tytul_oryginalny"
    litera = None

    def __init__(self, litera=""):
        super(AlphabeticBppSitemap, self).__init__()
        if litera:
            self.litera = litera

    def items(self):
        if not self.litera:
            return list(super(AlphabeticBppSitemap, self).items())
        kw = {self.title_field + "__istartswith": self.litera}
        return list(super(AlphabeticBppSitemap, self).items().filter(**kw))


class AutorSitemap(AlphabeticBppSitemap):
    changefreq = "weekly"
    klass = Autor
    url = "bpp:browse_autor"
    url_obj_field = "slug"
    title_field = "nazwisko"


class PracaBppSitemap(AlphabeticBppSitemap):
    def location(self, obj):
        return reverse(self.url, args=(str(self.klass.__name__).lower(), obj.pk))


class Wydawnictwo_CiagleSitemap(PracaBppSitemap):
    klass = Wydawnictwo_Ciagle


class Wydawnictwo_ZwarteSitemap(PracaBppSitemap):
    klass = Wydawnictwo_Zwarte


class Praca_DoktorskaSitemap(PracaBppSitemap):
    klass = Praca_Doktorska


class Praca_HabilitacyjnaSitemap(PracaBppSitemap):
    klass = Praca_Habilitacyjna


class PatentSitemap(PracaBppSitemap):
    klass = Patent


django_bpp_sitemaps = {
    "jednostka": JednostkaSitemap,
    "uczelnia": UczelniaSitemap,
    "wydzial": WydzialSitemap,
}

for litera in "aąbcćdefghijklłmnńoópqrsśtuvwxyzźż":
    for label, klasa in [
        ("wydawnictwo-zwarte", Wydawnictwo_ZwarteSitemap),
        ("wydawnictwo-ciagle", Wydawnictwo_CiagleSitemap),
        ("praca-doktorska", Praca_DoktorskaSitemap),
        ("praca-habilitacyjna", Praca_HabilitacyjnaSitemap),
        ("autor", AutorSitemap),
        ("patent", PatentSitemap),
    ]:
        django_bpp_sitemaps[label + "-" + litera] = klasa(litera)
