from django import forms
from django.core.exceptions import ValidationError
from django.db import models

from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import OdpowiednikWBPPFilter
from pbn_api.admin.widgets import PrettyJSONWidgetReadonly
from pbn_api.models import Publication

from django.contrib import admin

from bpp.models import Uczelnia


class PublicationFromMongoIdForm(forms.ModelForm):
    # mongoId = forms.CharField(max_length=32)

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop("request")
        super().__init__(*args, **kwargs)

    class Meta:
        model = Publication
        fields = ["mongoId"]

    def clean_mongoId(self):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        client = uczelnia.pbn_client(self.request.user.pbn_token)
        try:
            self.cleaned_data["json"] = client.get_publication_by_id(
                self.cleaned_data["mongoId"]
            )
        except Exception as e:
            raise ValidationError(
                f"Wystąpił błąd po stronie PBN podczas pobierania danych: {e}"
            )

        return self.cleaned_data["mongoId"]


@admin.register(Publication)
class PublicationAdmin(
    BaseMongoDBAdmin,
):
    show_full_result_count = False

    list_display = [
        "title",
        "type",
        "volume",
        "year",
        "publicUri",
        "doi",
        "rekord_w_bpp",
    ]
    search_fields = [
        "mongoId",
        "title",
        "isbn",
        "doi",
        "publicUri",
    ]

    formfield_overrides = {models.JSONField: {"widget": PrettyJSONWidgetReadonly}}

    fields = BaseMongoDBAdmin.readonly_fields + [
        "versions",
    ]

    list_filter = [OdpowiednikWBPPFilter] + BaseMongoDBAdmin.list_filter

    def has_add_permission(self, request):
        return False

    def get_fields(self, request, obj=None):
        if obj is None:
            return ["mongoId"]
        return super().get_fields(request, obj)

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return super().get_readonly_fields(request, obj)

    def get_form(self, request, obj=None, change=False, **kwargs):
        if not change:

            class RequestPublicationFromMongoIdForm(PublicationFromMongoIdForm):
                def __new__(cls, *args, **kwargs):
                    kwargs["request"] = request
                    return PublicationFromMongoIdForm(*args, **kwargs)

            return RequestPublicationFromMongoIdForm

        return super().get_form(request=request, obj=obj, change=change, **kwargs)

    def save_model(self, request, obj, form, change):
        """
        Given a model instance save it to the database.
        """
        from pbn_api.integrator import zapisz_mongodb

        zapisz_mongodb(form.cleaned_data["json"], Publication)
        obj.refresh_from_db()
