from rest_framework import viewsets

from api_v1.serializers.jednostka import JednostkaSerializer
from bpp.models import Jednostka


class JednostkaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Jednostka.objects.all()
    serializer_class = JednostkaSerializer
