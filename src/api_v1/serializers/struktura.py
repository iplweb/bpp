from rest_framework import serializers

from bpp.models import Jednostka, Uczelnia


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


class JednostkaSerializer(serializers.ModelSerializer):
    # Faza C (#438): model Wydzial usunięty. ``wydzial`` to self-FK do
    # jednostki-korzenia (top-level), więc hiperłącze wskazuje zasób Jednostki.
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
