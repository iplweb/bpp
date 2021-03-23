from braces.views import GroupRequiredMixin
from django import forms
from django.db.models import F
from django.views.generic import ListView

from rozbieznosci_if.models import IgnorujRozbieznoscIf

from django.contrib.contenttypes.models import ContentType

from bpp.models import Wydawnictwo_Ciagle


class SetForm(forms.Form):
    _set = forms.IntegerField(min_value=0)


class IgnoreForm(forms.Form):
    _ignore = forms.IntegerField(min_value=0)


class RozbieznosciView(GroupRequiredMixin, ListView):
    template_name = "rozbieznosci_if/index.html"
    group_required = "wprowadzanie danych"
    paginate_by = 150

    def get_queryset(self):
        return (
            Wydawnictwo_Ciagle.objects.exclude(zrodlo=None)
            .filter(
                zrodlo__punktacja_zrodla__rok=F("rok"),
            )
            .exclude(zrodlo__punktacja_zrodla__impact_factor=F("impact_factor"))
            .exclude(
                pk__in=IgnorujRozbieznoscIf.objects.filter(
                    content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
                ).values_list("object_id")
            )
            .order_by(
                "-ostatnio_zmieniony",
            )
            .select_related("zrodlo")
            .annotate(
                punktacja_zrodla_impact_factor=F(
                    "zrodlo__punktacja_zrodla__impact_factor"
                )
            )
        )

    def get(self, request, *args, **kw):
        if "_ignore" in request.GET:
            frm = IgnoreForm(request.GET)
            if frm.is_valid():
                IgnorujRozbieznoscIf.objects.get_or_create(
                    object_id=frm.cleaned_data["_ignore"],
                    content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
                )
        if "_set" in request.GET:
            frm = SetForm(request.GET)
            if frm.is_valid():
                IgnorujRozbieznoscIf.objects.filter(
                    object_id=frm.cleaned_data["_set"],
                    content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
                ).delete()

                try:
                    wc = Wydawnictwo_Ciagle.objects.get(pk=frm.cleaned_data["_set"])
                    if wc.impact_factor != wc.punktacja_zrodla().impact_factor:
                        wc.impact_factor = wc.punktacja_zrodla().impact_factor
                        wc.save()
                except Wydawnictwo_Ciagle.DoesNotExist:
                    pass

        return super(RozbieznosciView, self).get(request, *args, **kw)
