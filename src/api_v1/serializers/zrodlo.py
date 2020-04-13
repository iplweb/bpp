from rest_framework import serializers

# Serializers define the API representation.
from api_v1.serializers.util import AbsoluteUrlSerializerMixin, ChoicesSerializerField
from bpp.models import Zrodlo, Rodzaj_Zrodla


class Rodzaj_ZrodlaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rodzaj_Zrodla
        fields = [
            "id",
            "nazwa",
        ]


class ZrodloSerializer(
    AbsoluteUrlSerializerMixin, serializers.HyperlinkedModelSerializer
):
    rodzaj = serializers.HyperlinkedRelatedField(
        view_name="api_v1:rodzaj_zrodla-detail", read_only=True
    )

    jezyk = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jezyk-detail", read_only=True
    )

    zasieg = serializers.StringRelatedField()

    openaccess_licencja = serializers.StringRelatedField()
    openaccess_tryb_dostepu = serializers.StringRelatedField()

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
            "www",
            "doi",
            "poprzednia_nazwa",
            "jezyk",
            "wydawca",
            #
            "openaccess_tryb_dostepu",
            "openaccess_licencja",
            #
            "issn",
            "e_issn",
            #
            "absolute_url",
            #
            "ostatnio_zmieniony",
        ]
