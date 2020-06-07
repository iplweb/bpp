from rest_framework import serializers

from api_v1.serializers.util import (
    AbsoluteUrlSerializerMixin,
    Wydawnictwo_AutorSerializerMixin,
    WydawnictwoSerializerMixin,
)
from bpp.models import (
    Patent_Autor,
    Patent,
)


class Patent_AutorSerializer(
    Wydawnictwo_AutorSerializerMixin, serializers.HyperlinkedModelSerializer
):
    rekord = serializers.HyperlinkedRelatedField(
        view_name="api_v1:patent-detail", read_only=True
    )

    class Meta:
        model = Patent_Autor
        fields = [
            "id",
            "autor",
            "jednostka",
            "zapisany_jako",
            "typ_odpowiedzialnosci",
            "afiliuje",
            "zatrudniony",
            "kolejnosc",
            "rekord",
            "procent",
            "dyscyplina_naukowa",
        ]


class PatentSerializer(
    AbsoluteUrlSerializerMixin,
    WydawnictwoSerializerMixin,
    serializers.HyperlinkedModelSerializer,
):
    rodzaj_prawa = serializers.RelatedField(read_only=True)
    # "bpp.Rodzaj_Prawa_Patentowego", CASCADE, null=True, blank=True
    # )

    wydzial = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydzial-detail", read_only=True
    )

    autorzy_set = serializers.HyperlinkedRelatedField(
        many=True, view_name="api_v1:wydawnictwo_zwarte_autor-detail", read_only=True
    )

    class Meta:
        model = Patent
        fields = [
            "id",
            #
            "tytul_oryginalny",
            #
            "data_zgloszenia",
            "numer_zgloszenia",
            "data_decyzji",
            "numer_prawa_wylacznego",
            "rodzaj_prawa",
            "wdrozenie",
            "wydzial",
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
            "utworzono",
            "ostatnio_zmieniony",
            #
            "absolute_url",
            #
            "tekst_przed_pierwszym_autorem",
            "autorzy_set",
            "tekst_po_ostatnim_autorze",
        ]
