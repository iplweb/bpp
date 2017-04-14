# -*- encoding: utf-8 -*-


from django.contrib.sitemaps import Sitemap
from django.core.urlresolvers import reverse

from bpp.models import Jednostka
from bpp.models.autor import Autor
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.struktura import Uczelnia, Wydzial
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


class BppSitemap(Sitemap):
    priority = 0.5

    def items(self):
        return self.klass.objects.all()

    def lastmod(self, obj):
        return obj.ostatnio_zmieniony

    def location(self, obj):
        return reverse(self.url, args=(obj.pk,))


class JednostkaSitemap(BppSitemap):
    changefreq = "yearly"
    klass = Jednostka
    url = "bpp:browse_jednostka"


class UczelniaSitemap(BppSitemap):
    changefreq = "yearly"
    klass = Uczelnia
    url = "bpp:browse_uczelnia"

class WydzialSitemap(BppSitemap):
    changefreq = "yearly"
    klass = Wydzial
    url = "bpp:browse_wydzial"


class AutorSitemap(BppSitemap):
    changefreq = "weekly"
    klass = Autor
    url = "bpp:browse_autor"


class PracaBppSitemap(BppSitemap):
    changefreq = "weekly"
    url = "bpp:browse_praca"

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
    'jednostka': JednostkaSitemap,
    'autor': AutorSitemap,
    'uczelnia': UczelniaSitemap,
    'wydzial': WydzialSitemap,
    'wydawnictwo-ciagle': Wydawnictwo_CiagleSitemap,
    'wydawnictwo-zwarte': Wydawnictwo_ZwarteSitemap,
    'praca-doktorska': Praca_DoktorskaSitemap,
    'praca-habilitacyjna': Praca_HabilitacyjnaSitemap,
    'patent': PatentSitemap
}
