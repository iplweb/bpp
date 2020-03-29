from rest_framework import serializers


class ChoicesSerializerField(serializers.SerializerMethodField):
    def to_representation(self, value):
        method_name = "get_{field_name}_display".format(field_name=self.field_name)
        method = getattr(value, method_name)
        return method()


class AbsoluteUrlSerializerMixin:
    def get_absolute_url(self, obj):
        return self.context["request"].build_absolute_uri(obj.get_absolute_url())


class AbsoluteUrlField(AbsoluteUrlSerializerMixin, serializers.RelatedField):
    def to_representation(self, value):
        if value is None:
            return
        return self.get_absolute_url(value)
