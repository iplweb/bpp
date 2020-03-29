from rest_framework import serializers

# Serializers define the API representation.
from bpp.models import Zrodlo, Rodzaj_Zrodla


class Rodzaj_ZrodlaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rodzaj_Zrodla
        fields = [
            "id",
            "nazwa",
        ]


class ZrodloSerializer(serializers.HyperlinkedModelSerializer):
    rodzaj = serializers.HyperlinkedRelatedField(
        read_only=True, view_name="api_v1:rodzaj_zrodla-detail"
    )

    class Meta:
        model = Zrodlo
        fields = [
            "id",
            "nazwa",
            "skrot",
            "rodzaj",
            "nazwa_alternatywna",
            "skrot_nazwy_alternatywnej",
            "zasieg",
        ]
