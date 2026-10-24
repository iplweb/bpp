from rest_framework import serializers

from api_v1.permissions import widzi_dane_osobowe
from api_v1.serializers.util import AbsoluteUrlField
from bpp.models.nagroda import Nagroda


class NagrodaSerializer(serializers.ModelSerializer):
    object = AbsoluteUrlField(read_only=True)

    organ_przyznajacy = serializers.StringRelatedField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ``adnotacja`` to wewnętrzna notatka redakcji (nie jest pokazywana
        # na stronach publicznych) — tylko dla uprawnionych redaktorów.
        if not widzi_dane_osobowe(self.context.get("request")):
            self.fields.pop("adnotacja", None)

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
