from rest_framework import serializers

from api_v1.serializers.util import ChoicesSerializerField
from bpp.models import (
    Charakter_Formalny,
    Typ_KBN,
    Jezyk,
    Dyscyplina_Naukowa,
    Konferencja,
    Seria_Wydawnicza,
)


class Dyscyplina_NaukowaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dyscyplina_Naukowa
        fields = ["id", "kod", "nazwa", "widoczna"]


class Seria_WydawniczaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seria_Wydawnicza
        fields = ["id", "nazwa"]


class KonferencjaSerializer(serializers.ModelSerializer):
    typ_konferencji = ChoicesSerializerField()

    class Meta:
        model = Konferencja
        fields = [
            "id",
            "nazwa",
            "skrocona_nazwa",
            "rozpoczecie",
            "zakonczenie",
            "miasto",
            "panstwo",
            "baza_scopus",
            "baza_wos",
            "baza_inna",
            "typ_konferencji",
        ]


class Charakter_FormalnySerializer(serializers.HyperlinkedModelSerializer):
    charakter_pbn = serializers.StringRelatedField(read_only=True)
    rodzaj_pbn = ChoicesSerializerField()
    charakter_sloty = ChoicesSerializerField()

    class Meta:
        model = Charakter_Formalny
        fields = [
            "id",
            "nazwa",
            "skrot",
            "charakter_pbn",
            "rodzaj_pbn",
            "charakter_sloty",
        ]


class Typ_KBNSerializer(serializers.ModelSerializer):
    charakter_pbn = serializers.StringRelatedField()

    class Meta:
        model = Typ_KBN
        fields = ["id", "nazwa", "skrot", "artykul_pbn", "charakter_pbn"]


class JezykSerializer(serializers.ModelSerializer):
    class Meta:
        model = Jezyk
        fields = ["id", "nazwa", "skrot"]
