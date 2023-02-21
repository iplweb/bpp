import django_filters
from rest_framework import viewsets
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated

from api_v1.permissions import IsGrupaRaportyWyswietlanie
from api_v1.serializers.raport_slotow_uczelnia import (
    RaportSlotowUczelniaSerializer,
    RaportSlotowUczelniaWierszSerializer,
)
from raport_slotow.models.uczelnia import (
    RaportSlotowUczelnia,
    RaportSlotowUczelniaWiersz,
)


class ParentChoiceFilter(django_filters.ModelChoiceFilter):
    def get_queryset(self, request):
        return RaportSlotowUczelnia.objects.filter(owner=request.user)


class RaportSlotowUczelniaWierszFilterSet(django_filters.rest_framework.FilterSet):
    parent = ParentChoiceFilter()

    class Meta:
        fields = ["parent"]
        model = RaportSlotowUczelniaWiersz


class RaportSlotowUczelniaWierszViewSet(viewsets.ReadOnlyModelViewSet):
    authentication_classes = [
        BasicAuthentication,
    ]
    permission_classes = [IsAuthenticated, IsGrupaRaportyWyswietlanie]

    filterset_class = RaportSlotowUczelniaWierszFilterSet

    def get_queryset(self):
        return RaportSlotowUczelniaWiersz.objects.filter(
            parent__owner=self.request.user
        )

    serializer_class = RaportSlotowUczelniaWierszSerializer


class RaportSlotowUczelniaViewSet(viewsets.ModelViewSet):
    authentication_classes = [
        BasicAuthentication,
    ]
    permission_classes = [IsAuthenticated, IsGrupaRaportyWyswietlanie]

    def get_queryset(self):
        return RaportSlotowUczelnia.objects.filter(owner=self.request.user)

    serializer_class = RaportSlotowUczelniaSerializer
