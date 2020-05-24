from rest_framework import serializers

from api_v1.serializers.util import (
    AbsoluteUrlSerializerMixin,
    Wydawnictwo_AutorSerializerMixin,
    WydawnictwoSerializerMixin,
)
from bpp.models import (
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych,
)


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_DanychSerializer(serializers.ModelSerializer):
    rekord = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydawnictwo_ciagle-detail", read_only=True
    )
    baza = serializers.StringRelatedField()

    class Meta:
        model = Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych
        fields = ["rekord", "baza", "info"]


class Wydawnictwo_Ciagle_AutorSerializer(
    Wydawnictwo_AutorSerializerMixin, serializers.HyperlinkedModelSerializer
):
    rekord = serializers.HyperlinkedRelatedField(
        view_name="api_v1:wydawnictwo_ciagle-detail", read_only=True
    )

    class Meta:
        model = Wydawnictwo_Ciagle_Autor
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


class Wydawnictwo_CiagleSerializer(
    AbsoluteUrlSerializerMixin,
    WydawnictwoSerializerMixin,
    serializers.HyperlinkedModelSerializer,
):

    zrodlo = serializers.HyperlinkedRelatedField(
        view_name="api_v1:zrodlo-detail", read_only=True
    )

    autorzy_set = serializers.HyperlinkedRelatedField(
        many=True, view_name="api_v1:wydawnictwo_ciagle_autor-detail", read_only=True
    )

    konferencja = serializers.HyperlinkedRelatedField(
        view_name="api_v1:konferencja-detail", read_only=True
    )

    zewnetrzna_baza_danych = serializers.HyperlinkedRelatedField(
        many=True,
        view_name="api_v1:wydawnictwo_ciagle_zewnetrzna_baza_danych-detail",
        read_only=True,
    )

    class Meta:
        model = Wydawnictwo_Ciagle
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
            "zrodlo",
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
            "nr_zeszytu",
            #
            "konferencja",
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
            "issn",
            "e_issn",
            #
            "liczba_cytowan",
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
            "zewnetrzna_baza_danych",
        ]
