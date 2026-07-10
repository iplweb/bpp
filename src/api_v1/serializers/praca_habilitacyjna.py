from rest_framework import serializers
from taggit.serializers import TagListSerializerField

from api_v1.serializers.util import (
    AbsoluteUrlSerializerMixin,
    WydawnictwoSerializerMixin,
)
from bpp.models import Praca_Habilitacyjna


class Praca_HabilitacyjnaSerializer(
    AbsoluteUrlSerializerMixin,
    WydawnictwoSerializerMixin,
    serializers.HyperlinkedModelSerializer,
):
    slowa_kluczowe = TagListSerializerField()

    autor = serializers.HyperlinkedRelatedField(
        view_name="api_v1:autor-detail", read_only=True
    )

    jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )

    wydawca = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydawca-detail", read_only=True
    )

    # ``publikacja_habilitacyjna`` to relacja odwrotna (jeden-do-wielu) z
    # ``Publikacja_Habilitacyjna`` — akcesor to ``publikacja_habilitacyjna_set``.
    # Goły ``serializers.RelatedField`` jest abstrakcyjny (brak to_representation)
    # i wywala 500 (NotImplementedError), gdy relacja ma element. StringRelatedField
    # daje ``__str__`` powiązań i jest spójny z resztą API.
    publikacja_habilitacyjna = serializers.StringRelatedField(
        many=True, read_only=True, source="publikacja_habilitacyjna_set"
    )

    class Meta:
        model = Praca_Habilitacyjna
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
            "oznaczenie_wydania",
            "miejsce_i_rok",
            "wydawca",
            "wydawca_opis",
            #
            "publikacja_habilitacyjna",
        ]
