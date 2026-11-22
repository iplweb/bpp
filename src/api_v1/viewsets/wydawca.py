from rest_framework import viewsets

from api_v1.serializers.wydawca import Poziom_WydawcySerializer, WydawcaSerializer
from bpp.models import Wydawca
from bpp.models.wydawca import Poziom_Wydawcy


class Poziom_WydawcyViewSet(viewsets.ReadOnlyModelViewSet):
    # Poziomy wydawcy z kosza są niewidoczne (rodzic w koszu).
    queryset = Poziom_Wydawcy.objects.filter(wydawca__deleted_at__isnull=True)
    serializer_class = Poziom_WydawcySerializer


class WydawcaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Wydawca.objects.all()
    serializer_class = WydawcaSerializer
