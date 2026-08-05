"""Kompaktowe, płaskie projekcje wyników DjangoQL po API.

Rekord reuse ``SzukajSerializer`` (Faza 0). Tu Autor i Autorzy — relacje jako
string (etykieta) + URL do detalu API, bez chodzenia po hyperlinkach.
"""

from django.urls import reverse
from rest_framework import serializers


class AutorKompaktSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    nazwisko = serializers.CharField()
    imiona = serializers.CharField()
    tytul = serializers.SerializerMethodField()
    orcid = serializers.CharField()
    aktualna_jednostka = serializers.SerializerMethodField()
    autor_url = serializers.SerializerMethodField()
    absolute_url = serializers.SerializerMethodField()

    def get_tytul(self, obj):
        return obj.tytul.skrot if obj.tytul_id else ""

    def get_aktualna_jednostka(self, obj):
        return obj.aktualna_jednostka.nazwa if obj.aktualna_jednostka_id else None

    def get_autor_url(self, obj):
        request = self.context["request"]
        return request.build_absolute_uri(reverse("api_v1:autor-detail", args=[obj.pk]))

    def get_absolute_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())


class AutorzyKompaktSerializer(serializers.Serializer):
    """Wpis autorstwa (autor-na-rekordzie). ``id`` = TupleField ``"<ct>-<pk>"``."""

    id = serializers.SerializerMethodField()
    zapisany_jako = serializers.CharField()
    kolejnosc = serializers.IntegerField()
    autor_url = serializers.SerializerMethodField()
    rekord = serializers.SerializerMethodField()
    typ_odpowiedzialnosci = serializers.SerializerMethodField()
    jednostka = serializers.SerializerMethodField()
    dyscyplina = serializers.SerializerMethodField()

    def get_id(self, obj):
        return f"{obj.id[0]}-{obj.id[1]}"

    def get_autor_url(self, obj):
        request = self.context["request"]
        return request.build_absolute_uri(
            reverse("api_v1:autor-detail", args=[obj.autor_id])
        )

    def get_rekord(self, obj):
        request = self.context["request"]
        rek = obj.rekord
        viewname = self.context["contenttype_to_viewname"].get(rek.id[0])
        rekord_url = None
        if viewname is not None:
            rekord_url = request.build_absolute_uri(
                reverse(viewname, args=(rek.id[1],))
            )
        return {"tytul": rek.tytul_oryginalny, "rekord_url": rekord_url}

    def get_typ_odpowiedzialnosci(self, obj):
        return obj.typ_odpowiedzialnosci.skrot if obj.typ_odpowiedzialnosci_id else None

    def get_jednostka(self, obj):
        return obj.jednostka.nazwa if obj.jednostka_id else None

    def get_dyscyplina(self, obj):
        return obj.dyscyplina_naukowa.nazwa if obj.dyscyplina_naukowa_id else None
