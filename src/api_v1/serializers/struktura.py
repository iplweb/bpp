from rest_framework import serializers

from bpp.models import Jednostka, Uczelnia, Wydzial


class UczelniaSerializer(serializers.ModelSerializer):
    obca_jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )

    class Meta:
        model = Uczelnia
        fields = [
            "id",
            "nazwa",
            "skrot",
            "pbn_id",
            "slug",
            "obca_jednostka",
        ]


class WydzialSerializer(serializers.ModelSerializer):
    uczelnia = serializers.HyperlinkedRelatedField(
        view_name="api_v1:uczelnia-detail", read_only=True
    )

    class Meta:
        model = Wydzial
        fields = [
            "id",
            "uczelnia",
            "nazwa",
            "skrot_nazwy",
            "skrot",
            "opis",
            "slug",
            "poprzednie_nazwy",
            "widoczny",
            "kolejnosc",
            "otwarcie",
            "zamkniecie",
            "ostatnio_zmieniony",
        ]


class JednostkaSerializer(serializers.ModelSerializer):
    # Faza B (#438): ``wydzial`` to teraz self-FK do jednostki-korzenia, więc
    # hiperłącze wskazuje zasób Jednostki (root), nie Wydzialu. Zasób
    # ``/api/v1/wydzial/`` (WydzialViewSet) żyje osobno do Fazy C.
    wydzial = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )
    uczelnia = serializers.HyperlinkedRelatedField(
        view_name="api_v1:uczelnia-detail", read_only=True
    )

    class Meta:
        model = Jednostka
        fields = [
            "id",
            "nazwa",
            "skrot",
            "aktualna",
            "opis",
            "slug",
            "widoczna",
            "wchodzi_do_rankingu_autorow",
            "skupia_pracownikow",
            "wydzial",
            "uczelnia",
            "ostatnio_zmieniony",
        ]
