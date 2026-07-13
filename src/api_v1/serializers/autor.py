from rest_framework import serializers

from api_v1.serializers.util import AbsoluteUrlSerializerMixin

from bpp.models import Autor, Autor_Jednostka, Funkcja_Autora, Tytul


class TytulSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tytul
        fields = ["id", "nazwa", "skrot"]


class Funkcja_AutoraSerializer(serializers.ModelSerializer):
    class Meta:
        model = Funkcja_Autora
        fields = ["id", "nazwa", "skrot"]


class Autor_JednostkaSerializer(serializers.HyperlinkedModelSerializer):
    autor = serializers.HyperlinkedRelatedField(
        view_name="api_v1:autor-detail", read_only=True
    )
    jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )
    funkcja = serializers.HyperlinkedRelatedField(
        view_name="api_v1:funkcja_autora-detail", read_only=True
    )

    class Meta:
        model = Autor_Jednostka
        fields = [
            "id",
            "autor",
            "jednostka",
            "rozpoczal_prace",
            "zakonczyl_prace",
            "funkcja",
        ]


class AutorSerializer(
    AbsoluteUrlSerializerMixin, serializers.HyperlinkedModelSerializer
):
    absolute_url = serializers.SerializerMethodField("get_absolute_url")

    aktualna_jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )

    tytul = serializers.HyperlinkedRelatedField(
        view_name="api_v1:tytul-detail", read_only=True
    )

    aktualna_funkcja = serializers.HyperlinkedRelatedField(
        view_name="api_v1:funkcja_autora-detail", read_only=True
    )

    jednostki = serializers.HyperlinkedRelatedField(
        many=True, read_only=True, view_name="api_v1:autor_jednostka-detail"
    )

    # Pola PII maskowane dla użytkowników niezalogowanych.
    email = serializers.SerializerMethodField()
    urodzony = serializers.SerializerMethodField()
    poprzednie_nazwiska = serializers.SerializerMethodField()

    def _is_authenticated(self):
        request = self.context.get("request")
        return bool(request and request.user.is_authenticated)

    def get_email(self, obj):
        # E-mail to PII — ujawniany wyłącznie zalogowanym.
        return obj.email if self._is_authenticated() else ""

    def get_urodzony(self, obj):
        # Pełna data urodzenia to PII (dzień i miesiąc umożliwiają kradzież
        # tożsamości). Anonimowi otrzymują None — najbezpieczniejszy wariant.
        return obj.urodzony if self._is_authenticated() else None

    def get_poprzednie_nazwiska(self, obj):
        # Zalogowani widzą zawsze; anonim tylko gdy autor na to zezwolił
        # (pokazuj_poprzednie_nazwiska=True) — zgodnie z zachowaniem frontendu.
        if self._is_authenticated() or obj.pokazuj_poprzednie_nazwiska:
            return obj.poprzednie_nazwiska
        return ""

    class Meta:
        model = Autor
        fields = [
            "id",
            "imiona",
            "nazwisko",
            "tytul",
            "aktualna_jednostka",
            "aktualna_funkcja",
            "www",
            "urodzony",
            "zmarl",
            "poprzednie_nazwiska",
            "orcid",
            "pbn_id",
            "expertus_id",
            "slug",
            "jednostki",
            "absolute_url",
            #
            "ostatnio_zmieniony",
        ]
