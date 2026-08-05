from rest_framework import serializers


class ChoicesSerializerField(serializers.SerializerMethodField):
    def to_representation(self, value):
        method_name = "get_{field_name}_display".format(field_name=self.field_name)
        method = getattr(value, method_name)
        return method()


class AbsoluteUrlSerializerMixin(serializers.ModelSerializer):
    absolute_url = serializers.SerializerMethodField("get_absolute_url")

    def get_absolute_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())


class AbsoluteUrlField(AbsoluteUrlSerializerMixin, serializers.RelatedField):
    def to_representation(self, value):
        if value is None:
            return
        return self.get_absolute_url(value)


class Wydawnictwo_AutorSerializerMixin(serializers.HyperlinkedModelSerializer):
    autor = serializers.HyperlinkedRelatedField(
        view_name="api_v1:autor-detail", read_only=True
    )

    jednostka = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jednostka-detail", read_only=True
    )

    typ_odpowiedzialnosci = serializers.StringRelatedField()

    dyscyplina_naukowa = serializers.HyperlinkedRelatedField(
        view_name="api_v1:dyscyplina_naukowa-detail", read_only=True
    )


class WydawnictwoSerializerMixin(serializers.HyperlinkedModelSerializer):
    jezyk = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jezyk-detail", read_only=True
    )
    jezyk_alt = serializers.HyperlinkedRelatedField(
        view_name="api_v1:jezyk-detail", read_only=True
    )
    charakter_formalny = serializers.HyperlinkedRelatedField(
        view_name="api_v1:charakter_formalny-detail", read_only=True
    )

    typ_kbn = serializers.HyperlinkedRelatedField(
        view_name="api_v1:typ_kbn-detail", read_only=True
    )
    status_korekty = serializers.StringRelatedField()

    openaccess_tryb_dostepu = serializers.StringRelatedField()
    openaccess_wersja_tekstu = serializers.StringRelatedField()
    openaccess_licencja = serializers.StringRelatedField()
    openaccess_czas_publikacji = serializers.HyperlinkedRelatedField(
        view_name="api_v1:czas_udostepnienia_openaccess-detail", read_only=True
    )

    nagrody = serializers.HyperlinkedRelatedField(
        many=True, view_name="api_v1:nagroda-detail", read_only=True,
    )
