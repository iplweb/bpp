from rest_framework import serializers

from api_v1.serializers.util import AbsoluteUrlSerializerMixin

from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora, Tytul


class TytulSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tytul
        fields = ["id", "nazwa", "skrot"]


class Funkcja_AutoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Funkcja_Autora
        fields = ["id", "nazwa", "skrot"]


class Autor_JednostkaSerializer(serializers.HyperlinkedModelSerializer):
    autor = serializers.HyperlinkedRelatedField(
        view_name="api_v1:autor-detail", read_only=True
    )
    jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )
    funkcja = serializers.HyperlinkedRelatedField(
        view_name="api_v1:funkcja_autora-detail", read_only=True
    )

    class Meta:
        model = Autor_Jednostka
        fields = [
            "id",
            "autor",
            "jednostka",
            "rozpoczal_prace",
            "zakonczyl_prace",
            "funkcja",
        ]


class AutorSerializer(
    AbsoluteUrlSerializerMixin, serializers.HyperlinkedModelSerializer
):
    absolute_url = serializers.SerializerMethodField("get_absolute_url")

    aktualna_jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )

    tytul = serializers.HyperlinkedRelatedField(
        view_name="api_v1:tytul-detail", read_only=True
    )

    aktualna_funkcja = serializers.HyperlinkedRelatedField(
        view_name="api_v1:funkcja_autora-detail", read_only=True
    )

    jednostki = serializers.HyperlinkedRelatedField(
        many=True, read_only=True, view_name="api_v1:autor_jednostka-detail"
    )

    class Meta:
        model = Autor
        fields = [
            "id",
            "imiona",
            "nazwisko",
            "tytul",
            "aktualna_jednostka",
            "aktualna_funkcja",
            "pokazuj",
            "email",
            "www",
            "urodzony",
            "zmarl",
            "poprzednie_nazwiska",
            "orcid",
            "pbn_id",
            "expertus_id",
            "slug",
            "jednostki",
            "absolute_url",
            #
            "ostatnio_zmieniony",
        ]
