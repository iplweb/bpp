from rest_framework import serializers

from api_v1.serializers.util import ChoicesSerializerField
from bpp.models import Zrodlo, Rodzaj_Zrodla, Wydawca
from bpp.models.wydawca import Poziom_Wydawcy


class Poziom_WydawcySerializer(serializers.HyperlinkedModelSerializer):
    poziom = ChoicesSerializerField()
    wydawca = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydawca-detail", read_only=True
    )

    class Meta:
        model = Poziom_Wydawcy
        fields = ["id", "wydawca", "rok", "poziom"]


class WydawcaSerializer(serializers.HyperlinkedModelSerializer):
    alias_dla = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydawca-detail", read_only=True
    )

    poziom_wydawcy_set = serializers.HyperlinkedRelatedField(
        many=True, read_only=True, view_name="api_v1:poziom_wydawcy-detail"
    )

    class Meta:
        model = Wydawca
        fields = ["id", "nazwa", "alias_dla", "poziom_wydawcy_set"]
