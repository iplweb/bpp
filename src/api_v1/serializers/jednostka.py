from rest_framework import serializers

from bpp.models import Jednostka


class JednostkaSerializer(serializers.ModelSerializer):
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
            "wchodzi_do_raportow",
            "skupia_pracownikow",
            "wydzial",
            "uczelnia",
        ]
