from rest_framework import viewsets

from api_v1.serializers.nagroda import NagrodaSerializer
from bpp.models.nagroda import Nagroda


class NagrodaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Nagroda.objects.all()
    serializer_class = NagrodaSerializer
