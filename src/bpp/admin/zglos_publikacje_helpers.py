"""Klasy pomocnicze dla klas ModelAdmin które chcą korzystać z parametru
GET ``numer_zgloszenia`` czyli wypełniać dane wstępne wg zawartości zgłoszenia
o danym numerze ID. """


import django
from django import forms

from bpp import const
from bpp.admin.helpers import MODEL_Z_OPLATA_ZA_PUBLIKACJE

CHARMAP_SINGLE_LINE = forms.TextInput(
    attrs={"class": "charmap", "style": "width: 500px"}
)


class CustomizableFormsetParamsAdminMixinWyrzucWDjango40:
    """Mixin zapewniający funkcję ``get_formset_kwargs`` z Django 4.0,
    można go usunąć po przejściu na tą wersję.

    https://github.com/django/django/commit/3119a6decab7788eca662b10e8c18351d20df212
    """

    def get_formset_kwargs(self, request, obj, inline, prefix):
        formset_params = {
            "instance": obj,
            "prefix": prefix,
            "queryset": inline.get_queryset(request),
        }
        if request.method == "POST":
            formset_params.update(
                {
                    "data": request.POST.copy(),
                    "files": request.FILES,
                    "save_as_new": "_saveasnew" in request.POST,
                }
            )
        return formset_params

    def _create_formsets(self, request, obj, change):
        "Helper function to generate formsets for add/change_view."

        class AlreadyImplementedError(NotImplementedError):
            pass

        if django.VERSION >= (4, 0):
            # Nie wymagamy tego w Django 4.0
            raise AlreadyImplementedError(
                "Uzywasz Django 4.0, wyrzuc ten mixin i uzyj natywnej funkcji"
            )

        formsets = []
        inline_instances = []
        prefixes = {}
        get_formsets_args = [request]
        if change:
            get_formsets_args.append(obj)
        for FormSet, inline in self.get_formsets_with_inlines(*get_formsets_args):
            prefix = FormSet.get_default_prefix()
            prefixes[prefix] = prefixes.get(prefix, 0) + 1
            if prefixes[prefix] != 1 or not prefix:
                prefix = f"{prefix}-{prefixes[prefix]}"
            formset_params = self.get_formset_kwargs(request, obj, inline, prefix)
            formset = FormSet(**formset_params)

            def user_deleted_form(request, obj, formset, index, inline=inline):
                """Return whether or not the user deleted the form."""
                return (
                    inline.has_delete_permission(request, obj)
                    and f"{formset.prefix}-{index}-DELETE" in request.POST
                )

            # Bypass validation of each view-only inline form (since the form's
            # data won't be in request.POST), unless the form was deleted.
            if not inline.has_change_permission(request, obj if change else None):
                for index, form in enumerate(formset.initial_forms):
                    if user_deleted_form(request, obj, formset, index):
                        continue
                    form._errors = {}
                    form.cleaned_data = form.initial
            formsets.append(formset)
            inline_instances.append(inline)
        return formsets, inline_instances


class KorzystaZNumeruZgloszeniaMixin:
    """Mixin dla klas korzystajacych z parametru 'numer_zgloszenia', który to numer
    powoduje wypełnienie wstępnych parametrów wg zgłoszenia o ID podanym jako parametr GET.
    """

    def get_zgloszenie_publikacji(self, request):
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
        return self.extra


class UzupelniajWstepneDanePoNumerzeZgloszeniaMixin(
    KorzystaZNumeruZgloszeniaMixin, CustomizableFormsetParamsAdminMixinWyrzucWDjango40
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
            }

            for pole in MODEL_Z_OPLATA_ZA_PUBLIKACJE:
                ret[pole] = getattr(z, pole)

            ret[
                "adnotacje"
            ] = f"E-mail zgłaszającego: <{z.email}>.\nNumer zgłoszenia: {z.id} -- {str(z)}"

            ret["public_www"] = z.strona_www

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
