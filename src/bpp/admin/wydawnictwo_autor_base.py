from adminsortable2.admin import SortableAdminMixin
from django.http import HttpResponseRedirect
from django.urls import reverse

from django.contrib import admin
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters

from django.utils.safestring import mark_safe
from django.utils.text import Truncator

from bpp.admin.core import generuj_formularz_dla_autorow
from bpp.admin.helpers import get_rekord_id_from_GET_qs


class Wydawnictwo_Autor_Base(SortableAdminMixin, admin.ModelAdmin):

    # Wartosci do ustawienia dla developera:

    klasa_autora = None  # Wydawnictwo_Ciagle_Autor
    base_rekord_class = None  # Wydawnictwo_Ciagle
    change_list_template = None  # "admin/bpp/wydawnictwo_ciagle_autor/change_list.html"

    # Poniżej nie zmieniamy

    show_full_result_count = False

    ordering = ["kolejnosc"]
    list_select_related = [
        "rekord",
        "jednostka",
        "autor",
        "jednostka__wydzial",
        "typ_odpowiedzialnosci",
    ]
    list_display = [
        "rekord_short",
        "autor",
        "jednostka",
        "zapisany_jako",
        "typ_odpowiedzialnosci",
        "afiliuje",
        "zatrudniony",
        "upowaznienie_pbn",
        "dyscyplina_naukowa",
        "przypieta",
        # "procent",
        "kolejnosc",
    ]
    list_filter = [
        "zatrudniony",
        "afiliuje",
        "upowaznienie_pbn",
        "dyscyplina_naukowa",
        "przypieta",
    ]
    search_fields = [
        "rekord__tytul_oryginalny",
        "rekord__rok",
        "jednostka__nazwa",
        "autor__nazwisko",
        "autor__imiona",
    ]

    @property
    def form(self):
        return generuj_formularz_dla_autorow(
            self.klasa_autora, include_dyscyplina=True, include_rekord=True
        )

    # @admin.display(description="Rekord", ordering="rekord__tytul_oryginalny")
    def rekord_short(self, obj):
        return mark_safe(Truncator(obj.rekord.tytul_oryginalny).chars(100))

    rekord_short.short_description = "Rekord"
    rekord_short.ordering = "rekord__tytul_oryginalny"

    list_per_page = 500

    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}

        # Jeżeli jest podany parametr z ID rekordu w filtrowaniu, to można
        # przekazać go do templatki celem pokazania przycisku "Edycja rekordu"
        v = None
        if request.GET.get("rekord__id__exact"):
            v = request.GET.get("rekord__id__exact")
            try:
                extra_context["rekord_id"] = int(v)
                try:
                    rec = self.base_rekord_class.objects.get(pk=int(v))
                    extra_context["rekord"] = rec
                except BaseException:
                    pass
            except (ValueError, TypeError):
                pass

        return super(Wydawnictwo_Autor_Base, self).changelist_view(
            request=request, extra_context=extra_context
        )

    @staticmethod
    def get_extra_model_filters(request):
        if request.POST.get("rekord_id"):
            return {"rekord__id__iexact": request.POST.get("rekord_id")}
        return {}

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "rekord":
            # setting the user from the request object
            # kwargs["initial"] = 55  # request.user.id
            # making the field readonly
            kwargs["disabled"] = True
            kwargs["initial"] = get_rekord_id_from_GET_qs(request)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def get_changeform_initial_data(self, request):
        ret = super(Wydawnictwo_Autor_Base, self).get_changeform_initial_data(request)
        rekord_id = get_rekord_id_from_GET_qs(request)
        # ret["rekord_pk"] = rekord_id
        ret["rekord"] = rekord_id
        return ret

    def _response_post_save(self, request, obj):
        opts = self.model._meta
        if self.has_view_or_change_permission(request):
            post_url = reverse(
                "admin:%s_%s_changelist" % (opts.app_label, opts.model_name),
                current_app=self.admin_site.name,
            )
            preserved_filters = self.get_preserved_filters(request)
            if "rekord__id__exact" not in preserved_filters:
                preserved_filters += f"rekord__id__exact={obj.rekord.pk}"
            post_url = add_preserved_filters(
                {"preserved_filters": preserved_filters, "opts": opts}, post_url
            )
        else:
            post_url = reverse("admin:index", current_app=self.admin_site.name)
        return HttpResponseRedirect(post_url)
