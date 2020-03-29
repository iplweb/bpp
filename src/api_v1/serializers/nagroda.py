from rest_framework import serializers

# Serializers define the API representation.
from api_v1.serializers.util import AbsoluteUrlSerializerMixin, AbsoluteUrlField
from bpp.models import Zrodlo, Rodzaj_Zrodla
from bpp.models.nagroda import Nagroda


class NagrodaSerializer(serializers.ModelSerializer):
    object = AbsoluteUrlField(read_only=True)

    organ_przyznajacy = serializers.StringRelatedField()

    class Meta:
        model = Nagroda
        fields = [
            "id",
            "object",
            "nazwa",
            "organ_przyznajacy",
            "rok_przyznania",
            "uzasadnienie",
            "adnotacja",
        ]
