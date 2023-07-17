"""Funkcje pomocnicze dla klas w bpp.models"""
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from django.db import models
from django.db.models import Max
from django.template.loader import get_template

from django.utils import safestring


def dodaj_autora(
    klass,
    rekord,
    autor,
    jednostka,
    zapisany_jako=None,
    typ_odpowiedzialnosci_skrot="aut.",
    kolejnosc=None,
    dyscyplina_naukowa=None,
    afiliuje=True,
):
    """
    Utility function, dodająca autora do danego rodzaju klasy (Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte, Patent); funkcja używana przez te klasy, niejako
    wewnętrzna dla całego API; nie powinna być używana bezpośrednio nigdzie,
    jedynie API tych klas winno być używane.

    :param klass:
    :param rekord:
    :param autor:
    :param jednostka:
    :param zapisany_jako:
    :param typ_odpowiedzialnosci_skrot:
    :param kolejnosc:
    :return:
    """

    from bpp.models import Typ_Odpowiedzialnosci

    typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(
        skrot=typ_odpowiedzialnosci_skrot
    )

    if zapisany_jako is None:
        zapisany_jako = f"{autor.nazwisko} {autor.imiona}"

    if kolejnosc is None:
        kolejnosc = klass.objects.filter(rekord=rekord).aggregate(Max("kolejnosc"))[
            "kolejnosc__max"
        ]
        if kolejnosc is None:
            kolejnosc = 0
        else:
            kolejnosc += 1

    inst = klass(
        rekord=rekord,
        autor=autor,
        jednostka=jednostka,
        typ_odpowiedzialnosci=typ_odpowiedzialnosci,
        kolejnosc=kolejnosc,
        zapisany_jako=zapisany_jako,
        dyscyplina_naukowa=dyscyplina_naukowa,
        afiliuje=afiliuje,
    )
    inst.full_clean()
    inst.save()
    return inst


class ModelZOpisemBibliograficznym(models.Model):
    """Mixin, umożliwiający renderowanie opisu bibliograficznego dla danego
    obiektu przy pomocy template."""

    tekst_przed_pierwszym_autorem = models.TextField(blank=True, null=True)
    tekst_po_ostatnim_autorze = models.TextField(blank=True, null=True)

    def opis_bibliograficzny(self, links=None):
        """Renderuje opis bibliograficzny dla danej klasy, używając:
        * w pierwszej kolejności zadeklarowanej Template dla danego typu rekordu (lub ogólnego Template),
        * w trzeciej kolejności templatki z dysku "opis_bibliograficzny/opis_bibliograficzny.html"

        :param links: "normal" lub "admin" jeżeli chcemy, aby autorzy prowadzili gdzieś (do stron browse/
        lub do admina).
        """

        template_name = SzablonDlaOpisuBibliograficznego.objects.get_for_model(self)
        if template_name is None:
            template_name = "opis_bibliograficzny.html"

        template = get_template(template_name)

        ret = (
            template.render(dict(praca=self, links=links))
            .replace("\r\n", "")
            .replace("\n", "")
        )
        while ret.find("  ") != -1:
            ret = ret.replace("  ", " ")

        return (
            ret.replace(" , ", ", ")
            .replace(" . ", ". ")
            .replace(". . ", ". ")
            .replace(". , ", ". ")
            .replace(" .", ".")
            .replace(".</b>[", ".</b> [")
        )

    def autorzy_dla_opisu(self):
        # Takie 'autorzy_set.all()' ale na potrzeby opisu bibliograficznego -- zaciąga
        # rekordy zależne za pomocą .select_related:

        if not self.pk:
            return []

        return self.autorzy_set.select_related(
            "autor", "typ_odpowiedzialnosci"
        ).order_by("kolejnosc")

    def get_slug(self):
        if self.pk is None:
            return

        from bpp.util import slugify_function

        slug_tytul_oryginalny = slugify_function(self.tytul_oryginalny)

        slug_trzech_pierwszych_autorow = []
        for wyd_autor in self.autorzy_set.all().select_related("autor")[:3]:
            slug_trzech_pierwszych_autorow.append(
                f"{wyd_autor.autor.nazwisko} {wyd_autor.autor.imiona[:1]}"
            )
        slug_trzech_pierwszych_autorow = " ".join(slug_trzech_pierwszych_autorow)

        if hasattr(self, "zrodlo_id") and self.zrodlo_id is not None:
            slug_zrodla = slugify_function(self.zrodlo.nazwa)
        elif (
            hasattr(self, "wydawnictwo_nadrzedne")
            and self.wydawnictwo_nadrzedne_id is not None
        ):
            slug_zrodla = slugify_function(self.wydawnictwo_nadrzedne.tytul_oryginalny)
        else:
            slug_zrodla = ""

        lt, la, lz = (
            len(slug_tytul_oryginalny),
            len(slug_trzech_pierwszych_autorow),
            len(slug_zrodla),
        )

        if lt + la + lz >= 350:
            if lt > 200:
                lt = 200

            if lt + la + lz >= 350:
                if lz > 100:
                    lz = 100

                if lt + la + lz >= 350:
                    la = 50

        from django.contrib.contenttypes.models import ContentType

        ret = "-".join(
            [
                slug_tytul_oryginalny[:lt],
                slug_zrodla[:lz],
                slug_trzech_pierwszych_autorow[:la],
                str(ContentType.objects.get_for_model(self).pk),
                str(self.pk),
            ]
        )

        return slugify_function(ret)

    # Ten obiekt stanowi bazę do późniejszego zapełniania pól w podklasach. Pola,
    # które powinna podklasa definiować to:
    #
    # opis_bibliograficzny_cache = models.TextField(default="")
    # - generowane przez self.opis_bibliograficzny()
    #
    # opis_bibliograficzny_autorzy_cache = ArrayField(TextField(), blank=True, null=True)
    # -  To pole używane jest na ten moment jedynie przez moduł OAI, do szybkiego
    #    produkowania pola "Creator" dla formatu Dublin Core, vide moduł bpp.oai .
    #    To pole zawiera listę autorów, w kolejności, nazwisko i imię, bez
    #    tytułu
    #
    # slug = models.SlugField(max_length=400, unique=True, db_index=True, null=True, blank=True)
    # - skrót dla rekordu, dla SEO, zależy od m.in. tytułu, autorów, wydawnictwa nadrzędnego, źródła
    #
    # opis_bibliograficzny_zapisani_autorzy_cache = models.TextField(default="")
    # - zależy od klas autorów; to pole używane jest przez Raport autorów oraz Raport
    #   jednostek do szybkiego wypluwania listy zapisanych nazwisk
    #
    # def zaktualizuj_opis_bibliograficzny_cache(self, tylko_opis=False):
    #     autorzy = self.autorzy_dla_opisu()
    #     self.opis_bibliograficzny_cache = self.opis_bibliograficzny()
    #     self.slug = self._get_slug()
    #
    #     if hasattr(self, "autor"):
    #         zapisani = ["%s %s" % (autorzy[0].autor.nazwisko, autorzy[0].autor.imiona)]
    #     else:
    #         zapisani = [x.zapisany_jako for x in autorzy]
    #
    #     oac = ["%s %s" % (x.autor.nazwisko, x.autor.imiona) for x in autorzy]
    #     self.opis_bibliograficzny_autorzy_cache = oac
    #
    #     ozac = ", ".join(zapisani)
    #     self.opis_bibliograficzny_zapisani_autorzy_cache = ozac

    class Meta:
        abstract = True


class ZapobiegajNiewlasciwymCharakterom(models.Model):
    class Meta:
        abstract = True

    def clean_fields(self, *args, **kw):
        try:
            cf = self.charakter_formalny
        except ObjectDoesNotExist:
            cf = None

        if cf is not None:
            if self.charakter_formalny.skrot in ["D", "H", "PAT"]:
                raise ValidationError(
                    {
                        "charakter_formalny": [
                            safestring.mark_safe(
                                'Jeżeli chcesz dodać rekord o typie "%s"'
                                ', <a href="%s">kliknij tutaj</a>.'
                                % (
                                    self.charakter_formalny.nazwa,
                                    reverse(
                                        "admin:bpp_%s_add"
                                        % self.charakter_formalny.nazwa.lower().replace(
                                            " ", "_"
                                        )
                                    ),
                                )
                            )
                        ]
                    }
                )
