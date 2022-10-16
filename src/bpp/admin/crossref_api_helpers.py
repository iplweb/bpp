"""Klasy pomocnicze dla klas ModelAdmin które chcą korzystać z parametru
GET ``numer_zgloszenia`` czyli wypełniać dane wstępne wg zawartości zgłoszenia
o danym numerze ID. """
import math

from crossref_bpp.core import Komparator
from crossref_bpp.models import CrossrefAPICache
from import_common.normalization import normalize_title
from .util import CustomizableFormsetParamsAdminMixinWyrzucWDjango40

from bpp import const


class KorzystaZCrossRefAPIMixin:
    """Mixin dla klas korzystajacych z parametru 'identyfikator_doi', który to identyfikator
    powoduje wypełnienie wstępnych parametrów wg danych z CrossRef API
    """

    def get_crossref_api_data(self, request):
        if request.method == "GET":
            nz = request.GET.get(const.CROSSREF_API_PARAM, "")
            if nz:
                return CrossrefAPICache.objects.get_by_doi(nz)


class InlineMixin:
    def get_extra_json_list_length(self, json_data):
        return len(json_data.get(self.crossref_api_json_attrname, []))

    def get_extra(self, request, obj=None, **kwargs):
        z = self.get_crossref_api_data(request)
        if z is not None:
            return self.get_extra_json_list_length(z)

        return super().get_extra(request=request, obj=obj, **kwargs)


class KorzystaZCrossRefAPIAutorInlineMixin(InlineMixin, KorzystaZCrossRefAPIMixin):
    """Mixin dla klas Inline znajdujacych się w formualrzach ModelAdmin,
    korzystajacych ze wstepnie uzupełnianych danych przez CrossRef API.

    Funkcja ``get_extra`` zwraca ilosc formularzy, jaka powinna byc wyswietlona
    aby pokryc zapotrzebowanie na inicjalne wartosci dla autorów."""

    crossref_api_json_attrname = "author"


class KorzystaZCrossRefAPIStreszczenieInlineMixin(
    InlineMixin, KorzystaZCrossRefAPIMixin
):
    """Mixin dla klas Inline znajdujacych się w formualrzach ModelAdmin,
    korzystajacych ze wstepnie uzupełnianych danych przez CrossRef API.

    Funkcja ``get_extra`` zwraca ilosc formularzy, jaka powinna byc wyswietlona
    aby pokryc zapotrzebowanie na inicjalne wartosci dla autorów."""

    crossref_api_json_attrname = "abstract"

    def get_extra_json_list_length(self, json_data):
        if json_data.get(self.crossref_api_json_attrname) is not None:
            return 1
        return self.extra


class UzupelniajWstepneDanePoCrossRefAPIMixin(
    KorzystaZCrossRefAPIMixin, CustomizableFormsetParamsAdminMixinWyrzucWDjango40
):
    """Mixin dla klas ModelAdmin które chcą miec wypełniane parametry wg zgłoszenia
    z parametru requestu GET ``identyfikator_doi``.

    Obecnie dla Wydawnictwo_Ciagle.

    """

    def get_changeform_initial_data(self, request):
        z = self.get_crossref_api_data(request)
        if z is not None:
            title = z.get("title")
            if isinstance(title, list):
                title = ". ".join(title)
            title = normalize_title(title)

            zrodlo = Komparator.porownaj_container_title(
                z.get("container-title")[0]
            ).rekord_po_stronie_bpp
            if zrodlo is not None:
                zrodlo = zrodlo.pk

            wydawca_txt = ""
            wydawca_idx = Komparator.porownaj_publisher(
                z.get("publisher")
            ).rekord_po_stronie_bpp
            if wydawca_idx is None:
                wydawca_txt = z.get("publisher")

            charakter_formalny_pk = None
            charakter_formalny = Komparator.porownaj_type(
                z.get("type")
            ).rekord_po_stronie_bpp
            if charakter_formalny is not None:
                charakter_formalny_pk = charakter_formalny.pk

            jezyk_pk = None
            jezyk = Komparator.porownaj_language(
                z.get("language")
            ).rekord_po_stronie_bpp
            if jezyk is not None:
                jezyk_pk = jezyk.pk

            e_issn = None
            if z.get("issn-type", []):
                for _issn in z.get("issn-type"):
                    if _issn.get("type") == "electronic":
                        e_issn = _issn.get("value")
                        break

            licencja_pk = None
            licencja_ilosc_miesiecy = None
            for _licencja in z.get("license", []):
                licencja = Komparator.porownaj_license(_licencja).rekord_po_stronie_bpp
                if licencja is not None:
                    licencja_pk = licencja.pk
                    try:
                        licencja_ilosc_miesiecy = int(
                            math.ceil(int(_licencja.get("delay-in-days")) / 30)
                        )
                    except (TypeError, ValueError):
                        pass
                    break

            ret = {
                "tytul_oryginalny": title,
                "zrodlo": zrodlo,
                "nr_zeszytu": z.get("issue", ""),
                "strony": z.get("page", ""),
                "slowa_kluczowe": ", ".join('"%s"' % x for x in z.get("subject", [])),
                "wydawca": wydawca_idx,
                "wydawca_opis": wydawca_txt,
                "doi": z.get("DOI"),
                "charakter_formalny": charakter_formalny_pk,
                "jezyk": jezyk_pk,
                "adnotacje": "Dodano na podstawie CrossRef API",
                "e_issn": e_issn,
                "openaccess_licencja": licencja_pk,
                "openaccess_ilosc_miesiecy": licencja_ilosc_miesiecy,
                "issn": z.get(
                    "ISSN",
                    [
                        None,
                    ],
                )[0],
                "www": z.get("resource", {}).get("primary", {}).get("URL", ""),
                "tom": z.get("volume", ""),
                "rok": z.get("published", {}).get("date-parts", [[""]])[0][0],
            }

            return ret

        return super().get_changeform_initial_data(request)

    def get_formset_kwargs(self, request, obj, inline, prefix):
        initial = []

        z = self.get_crossref_api_data(request)

        if z is None:
            return super().get_formset_kwargs(request, obj, inline, prefix)

        if (
            prefix == "autorzy_set"
            and obj.pk is None
            and str(type(inline)).find("<locals>.baseModel_AutorInline") > -1
        ):
            for zpa in z.get("author", []):
                rekord = Komparator.porownaj_author(zpa).rekord_po_stronie_bpp
                if rekord:
                    initial.append(
                        {
                            "autor": rekord,
                            # "jednostka": zpa.jednostka_id,
                            # "dyscyplina_naukowa": zpa.dyscyplina_naukowa_id,
                        }
                    )
                else:
                    initial.append({})

        elif prefix == "streszczenia" and obj.pk is None:
            if z.get("abstract") is not None:

                jezyk_pk = None
                jezyk = Komparator.porownaj_language(
                    z.get("language")
                ).rekord_po_stronie_bpp
                if jezyk is not None:
                    jezyk_pk = jezyk.pk

                initial.append(
                    {
                        "jezyk_streszczenia": jezyk_pk,
                        "streszczenie": z.get("abstract", "").replace("&#x0D;", "\n"),
                    }
                )

        return {
            "initial": initial,
        }
