from rest_framework import serializers

from api_v1.permissions import widzi_dane_osobowe
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

    # Dane osobowe: pełne wartości widzi wyłącznie użytkownik z uprawnieniem
    # do wprowadzania danych lub superuser (``widzi_dane_osobowe``). Każdy
    # inny — anonim i zwykły zalogowany — dostaje identyczną, okrojoną wersję.
    email = serializers.SerializerMethodField()
    urodzony = serializers.SerializerMethodField()
    poprzednie_nazwiska = serializers.SerializerMethodField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # E-mail jest USUWANY z odpowiedzi (klucz nieobecny), nie tylko
        # maskowany. ``urodzony`` i ``poprzednie_nazwiska`` zostają w kształcie
        # odpowiedzi (maskowane w get_*), żeby nie zmieniać kontraktu pól.
        if not self._widzi_dane_osobowe():
            self.fields.pop("email", None)

    def _widzi_dane_osobowe(self):
        return widzi_dane_osobowe(self.context.get("request"))

    def get_email(self, obj):
        return obj.email if self._widzi_dane_osobowe() else ""

    def get_urodzony(self, obj):
        # Pełna data urodzenia to dana osobowa — bez uprawnień None.
        return obj.urodzony if self._widzi_dane_osobowe() else None

    def get_poprzednie_nazwiska(self, obj):
        # Bez uprawnień — tylko gdy autor na to zezwolił
        # (pokazuj_poprzednie_nazwiska=True), zgodnie z zachowaniem frontendu.
        if self._widzi_dane_osobowe() or obj.pokazuj_poprzednie_nazwiska:
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
            "email",
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
