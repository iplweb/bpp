"""Serializer płaskiej pozycji wyniku wyszukiwania ``/api/v1/szukaj/``.

Pozycja jest „płaska" — konsument nie musi chodzić po hyperlinkach, żeby
wyświetlić trafienie. Klucz ``rekord_url`` prowadzi jednak do typowanego
detalu (``wydawnictwo_ciagle-detail`` itd.), gdy potrzeba pełnych danych.
"""

from django.urls import reverse
from rest_framework import serializers


class SzukajSerializer(serializers.Serializer):
    """Serializuje wiersz ``bpp.Rekord`` (mat-view) do płaskiej pozycji wyniku."""

    id = serializers.SerializerMethodField()
    tytul_oryginalny = serializers.CharField()
    rok = serializers.IntegerField()
    opis_bibliograficzny = serializers.SerializerMethodField()
    rekord_url = serializers.SerializerMethodField()
    absolute_url = serializers.SerializerMethodField()

    def get_id(self, obj):
        # Klucz Rekord to TupleField (content_type_id, pk) — string „ct-pk".
        return f"{obj.id[0]}-{obj.id[1]}"

    def get_opis_bibliograficzny(self, obj):
        # Fallback na tytuł, gdy denormalizowany cache jeszcze pusty ("").
        return obj.opis_bibliograficzny_cache or obj.tytul_oryginalny

    def get_rekord_url(self, obj):
        # Mapa content_type_id → viewname budowana w RUNTIME przez viewset
        # (ID ContentType są per-baza; nie hardkodujemy ich).
        viewname = self.context["contenttype_to_viewname"].get(obj.id[0])
        if viewname is None:
            return None
        request = self.context["request"]
        return request.build_absolute_uri(reverse(viewname, args=(obj.id[1],)))

    def get_absolute_url(self, obj):
        # Publiczny URL strony WWW: slug-first (jak embed recent_*).
        request = self.context["request"]
        if obj.slug:
            return request.build_absolute_uri(
                reverse("bpp:browse_praca_by_slug", args=[obj.slug])
            )
        return request.build_absolute_uri(
            reverse("bpp:browse_praca", args=[obj.id[0], obj.id[1]])
        )
