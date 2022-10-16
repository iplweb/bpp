"""Klasy pomocnicze dla klas ModelAdmin które chcą korzystać z parametru
GET ``numer_zgloszenia`` czyli wypełniać dane wstępne wg zawartości zgłoszenia
o danym numerze ID. """
from django.utils import timezone

from bpp import const
from bpp.admin.helpers import MODEL_Z_OPLATA_ZA_PUBLIKACJE


class KorzystaZNumeruZgloszeniaMixin:
    """Mixin dla klas korzystajacych z parametru 'numer_zgloszenia', który to numer
    powoduje wypełnienie wstępnych parametrów wg zgłoszenia o ID podanym jako parametr GET.
    """

    def get_zgloszenie_publikacji(self, request):
        if request.method == "GET":
            nz = request.GET.get(const.NUMER_ZGLOSZENIA_PARAM, "")
            if nz.isnumeric():
                from zglos_publikacje.models import Zgloszenie_Publikacji

                try:
                    return Zgloszenie_Publikacji.objects.get(pk=nz)
                except Zgloszenie_Publikacji.DoesNotExist:
                    pass


class KorzystaZNumeruZgloszeniaInlineMixin(KorzystaZNumeruZgloszeniaMixin):
    """Mixin dla klas Inline znajdujacych się w formualrzach ModelAdmin,
    korzystajacych ze zgłoszeń prac przez uzytkownikow. Funkcja ``get_extra`` zwraca
    ilosc formularzy, jaka powinna byc wyswietlona aby pokryc zapotrzebowanie na
    inicjalne wartosci dla autorów."""

    def get_extra(self, request, obj=None, **kwargs):
        z = self.get_zgloszenie_publikacji(request)
        if z is not None:
            return z.zgloszenie_publikacji_autor_set.count()
        return super().get_extra(request=request, obj=obj, **kwargs)


class UzupelniajWstepneDanePoNumerzeZgloszeniaMixin(
    KorzystaZNumeruZgloszeniaMixin,
):
    """Mixin dla klas ModelAdmin które chcą miec wypełniane parametry wg zgłoszenia
    z parametru requestu GET ``numer_zgloszenia``.

    Obecnie dla Wydawnictwo_Ciagle i Wydawnictwo_Zwarte.

    """

    def get_changeform_initial_data(self, request):
        z = self.get_zgloszenie_publikacji(request)
        if z is not None:
            ret = {
                "tytul_oryginalny": z.tytul_oryginalny,
                "rok": z.rok,
                "public_www": z.strona_www,
                "public_dostep_dnia": timezone.now().date(),
            }

            for pole in MODEL_Z_OPLATA_ZA_PUBLIKACJE:
                ret[pole] = getattr(z, pole)

            ret["adnotacje"] = (
                f"E-mail zgłaszającego: <{z.email}>.\nNumer zgłoszenia: {z.id} -- {str(z)}\n"
                f"Pole 'Dostęp dnia' ustawione automatycznie na datę utworzenia rekordu. "
            )

            return ret

        return super().get_changeform_initial_data(request)

    def get_formset_kwargs(self, request, obj, inline, prefix):
        if not (
            prefix == "autorzy_set"
            and obj.pk is None
            and str(type(inline)).find("<locals>.baseModel_AutorInline") > -1
        ):
            return super().get_formset_kwargs(request, obj, inline, prefix)

        z = self.get_zgloszenie_publikacji(request)

        if z is None:
            return super().get_formset_kwargs(request, obj, inline, prefix)

        initial = []
        for zpa in z.zgloszenie_publikacji_autor_set.all():
            initial.append(
                {
                    "autor": zpa.autor_id,
                    "jednostka": zpa.jednostka_id,
                    "dyscyplina_naukowa": zpa.dyscyplina_naukowa_id,
                }
            )

        return {
            "initial": initial,
        }
