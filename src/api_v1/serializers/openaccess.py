from rest_framework import serializers

from bpp.models import Czas_Udostepnienia_OpenAccess


class Czas_Udostepnienia_OpenAccess_Serializer(serializers.HyperlinkedModelSerializer,):
    class Meta:
        model = Czas_Udostepnienia_OpenAccess
        fields = ["id", "nazwa", "skrot"]
