"""Klasy pomocnicze dla klas ModelAdmin które chcą korzystać z parametru
GET ``numer_zgloszenia`` czyli wypełniać dane wstępne wg zawartości zgłoszenia
o danym numerze ID. """
from crossref_bpp.admin.helpers import convert_crossref_to_changeform_initial_data
from crossref_bpp.core import Komparator
from crossref_bpp.models import CrossrefAPICache
from ..views.api import ostatnia_dyscyplina, ostatnia_jednostka

from bpp import const


class KorzystaZCrossRefAPIMixin:
    """Mixin dla klas korzystajacych z parametru 'identyfikator_doi', który to identyfikator
    powoduje wypełnienie wstępnych parametrów wg danych z CrossRef API
    """

    def get_crossref_api_data(self, request) -> dict | None:
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
    KorzystaZCrossRefAPIMixin,
):
    """Mixin dla klas ModelAdmin które chcą miec wypełniane parametry wg zgłoszenia
    z parametru requestu GET ``identyfikator_doi``.

    Obecnie dla Wydawnictwo_Ciagle.

    """

    def get_changeform_initial_data(self, request):
        z = self.get_crossref_api_data(request)
        if z is not None:
            return convert_crossref_to_changeform_initial_data(z)

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
                    jednostka = ostatnia_jednostka(request, rekord)
                    dyscyplina = ostatnia_dyscyplina(
                        request,
                        rekord,
                        z.get("published", {}).get("date-parts", [[None]])[0][0],
                    )

                    initial.append(
                        {
                            "autor": rekord,
                            "jednostka": jednostka,
                            "dyscyplina_naukowa": dyscyplina,
                            "zapisany_jako": f"{rekord.imiona} {rekord.nazwisko}",
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
