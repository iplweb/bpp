import django_filters
from rest_framework import viewsets

from api_v1.serializers.openaccess import Czas_Udostepnienia_OpenAccess_Serializer

from bpp.models import Czas_Udostepnienia_OpenAccess


class Czas_Udostepnienia_OpenAccess_ViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Czas_Udostepnienia_OpenAccess.objects.all()
    serializer_class = Czas_Udostepnienia_OpenAccess_Serializer
