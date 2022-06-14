import django_filters
from django.forms import NumberInput, TextInput

from bpp.models import Autorzy, Cache_Punktacja_Autora_Sum_Gruop, Dyscyplina_Naukowa


class RaportSlotowUczelniaBezJednostekIWydzialowFilter(django_filters.FilterSet):
    autor__nazwisko = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=TextInput(attrs={"placeholder": "Podaj nazwisko"}),
    )

    dyscyplina = django_filters.ModelChoiceFilter(
        queryset=Dyscyplina_Naukowa.objects.filter(
            pk__in=Autorzy.objects.values("dyscyplina_naukowa_id").distinct()
        )
    )

    slot__min = django_filters.NumberFilter(
        "slot",
        lookup_expr="gte",
        widget=NumberInput(attrs={"placeholder": "min"}),
    )

    slot__max = django_filters.NumberFilter(
        "slot",
        lookup_expr="lte",
        widget=NumberInput(attrs={"placeholder": "max"}),
    )

    avg__min = django_filters.NumberFilter(
        "avg", lookup_expr="gte", widget=NumberInput(attrs={"placeholder": "min"})
    )

    avg__max = django_filters.NumberFilter(
        "avg", lookup_expr="lte", widget=NumberInput(attrs={"placeholder": "max"})
    )

    class Meta:
        model = Cache_Punktacja_Autora_Sum_Gruop
        fields = ["autor__nazwisko", "dyscyplina__nazwa"]


class RaportSlotowUczelniaFilter(RaportSlotowUczelniaBezJednostekIWydzialowFilter):
    suma__min = django_filters.NumberFilter(
        "pkd_aut_sum",
        lookup_expr="gte",
        widget=NumberInput(attrs={"placeholder": "min"}),
    )

    suma__max = django_filters.NumberFilter(
        "pkd_aut_sum",
        lookup_expr="lte",
        widget=NumberInput(attrs={"placeholder": "max"}),
    )

    class Meta:
        model = Cache_Punktacja_Autora_Sum_Gruop
        fields = ["autor__nazwisko", "suma__min", "suma__max"]


class RaportZerowyFilter(django_filters.FilterSet):
    autor__nazwisko = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=TextInput(attrs={"placeholder": "Podaj nazwisko"}),
    )
    rok__min = django_filters.NumberFilter(
        "rok",
        lookup_expr="gte",
        widget=NumberInput(attrs={"placeholder": "min"}),
    )

    rok__max = django_filters.NumberFilter(
        "rok",
        lookup_expr="lte",
        widget=NumberInput(attrs={"placeholder": "max"}),
    )
    dyscyplina_naukowa = django_filters.ModelChoiceFilter(
        queryset=Dyscyplina_Naukowa.objects.filter(
            pk__in=Autorzy.objects.values("dyscyplina_naukowa_id").distinct()
        )
    )


class RaportSlotowUczelniaEwaluacjaFilter(django_filters.FilterSet):
    autorzy__autor__nazwisko = django_filters.CharFilter(
        lookup_expr="icontains",
        widget=TextInput(attrs={"placeholder": "Podaj nazwisko"}),
    )

    autorzy__dyscyplina_naukowa = django_filters.ModelChoiceFilter(
        queryset=Dyscyplina_Naukowa.objects.all()
    )
