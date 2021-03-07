from rest_framework import serializers
from taggit_serializer.serializers import TagListSerializerField

from api_v1.serializers.util import (
    AbsoluteUrlSerializerMixin,
    WydawnictwoSerializerMixin,
)
from bpp.models import Praca_Doktorska


class Praca_DoktorskaSerializer(
    AbsoluteUrlSerializerMixin,
    WydawnictwoSerializerMixin,
    serializers.HyperlinkedModelSerializer,
):
    autor = serializers.HyperlinkedRelatedField(
        view_name="api_v1:autor-detail", read_only=True
    )

    promotor = serializers.HyperlinkedRelatedField(
        view_name="api_v1:autor-detail", read_only=True
    )

    jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )

    slowa_kluczowe = TagListSerializerField()

    class Meta:
        model = Praca_Doktorska
        fields = [
            "id",
            #
            "tytul_oryginalny",
            "tytul",
            #
            "rok",
            "status_korekty",
            #
            "jezyk",
            "jezyk_alt",
            "charakter_formalny",
            "typ_kbn",
            #
            "www",
            "dostep_dnia",
            "public_www",
            "public_dostep_dnia",
            #
            "pubmed_id",
            "pmc_id",
            "doi",
            "pbn_id",
            #
            "impact_factor",
            "punkty_kbn",
            #
            "informacje",
            "szczegoly",
            "uwagi",
            "slowa_kluczowe",
            "strony",
            "tom",
            #
            "liczba_cytowan",
            #
            "openaccess_tryb_dostepu",
            "openaccess_wersja_tekstu",
            "openaccess_licencja",
            "openaccess_czas_publikacji",
            #
            "utworzono",
            "ostatnio_zmieniony",
            #
            "absolute_url",
            #
            "autor",
            "jednostka",
            #
            "promotor",
            "oznaczenie_wydania",
            "miejsce_i_rok",
            "wydawca",
            "wydawca_opis",
        ]
