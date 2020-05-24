from rest_framework import serializers

from api_v1.serializers.util import (
    AbsoluteUrlSerializerMixin,
    Wydawnictwo_AutorSerializerMixin,
    WydawnictwoSerializerMixin,
)
from bpp.models import Wydawnictwo_Zwarte, Wydawnictwo_Zwarte_Autor


class Wydawnictwo_Zwarte_AutorSerializer(
    Wydawnictwo_AutorSerializerMixin, serializers.HyperlinkedModelSerializer
):
    rekord = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydawnictwo_zwarte-detail", read_only=True
    )

    class Meta:
        model = Wydawnictwo_Zwarte_Autor
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


class Wydawnictwo_ZwarteSerializer(
    AbsoluteUrlSerializerMixin,
    WydawnictwoSerializerMixin,
    serializers.HyperlinkedModelSerializer,
):

    wydawca = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydawca-detail", read_only=True
    )

    autorzy_set = serializers.HyperlinkedRelatedField(
        many=True, view_name="api_v1:wydawnictwo_zwarte_autor-detail", read_only=True
    )

    konferencja = serializers.HyperlinkedRelatedField(
        view_name="api_v1:konferencja-detail", read_only=True
    )

    seria_wydawnicza = serializers.HyperlinkedRelatedField(
        view_name="api_v1:seria_wydawnicza-detail", read_only=True
    )

    wydawnictwo_nadrzedne = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydawnictwo_zwarte-detail", read_only=True
    )

    class Meta:
        model = Wydawnictwo_Zwarte
        fields = [
            "id",
            #
            "tytul_oryginalny",
            "tytul",
            #
            "rok",
            "status_korekty",
            #
            "wydawnictwo_nadrzedne",
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
            "praca_wybitna",
            "uzasadnienie_wybitnosci",
            #
            "konferencja",
            #
            "seria_wydawnicza",
            "numer_w_serii",
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
            "isbn",
            "e_isbn",
            #
            "liczba_cytowan",
            #
            "oznaczenie_wydania",
            "miejsce_i_rok",
            "wydawca",
            "wydawca_opis",
            "redakcja",
            #
            "openaccess_tryb_dostepu",
            "openaccess_wersja_tekstu",
            "openaccess_licencja",
            "openaccess_czas_publikacji",
            "openaccess_ilosc_miesiecy",
            #
            "utworzono",
            "ostatnio_zmieniony",
            #
            "absolute_url",
            #
            "tekst_przed_pierwszym_autorem",
            "autorzy_set",
            "tekst_po_ostatnim_autorze",
            #
            "nagrody",
        ]
