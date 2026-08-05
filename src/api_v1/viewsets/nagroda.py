from rest_framework import viewsets

from api_v1.serializers.nagroda import NagrodaSerializer
from bpp.models.nagroda import Nagroda


class NagrodaViewSet(viewsets.ReadOnlyModelViewSet):
    # ``organ_przyznajacy`` to StringRelatedField (join), a ``object`` to
    # GenericForeignKey, z którego serializer buduje absolute_url. GFK nie da
    # się załatwić przez select_related (relacja polimorficzna) — prefetch
    # grupuje wiersze po content_type i robi jedno zapytanie na TYP zamiast
    # na wiersz.
    queryset = (
        Nagroda.objects.all()
        .select_related("organ_przyznajacy")
        .prefetch_related("object")
    )
    serializer_class = NagrodaSerializer
