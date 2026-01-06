from django import forms
from django.contrib import admin, messages
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.html import format_html
from djangoql.admin import DjangoQLSearchMixin

from bpp.models import Jednostka, Uczelnia
from bpp.models.cache import Rekord
from pbn_api.admin.base import BaseMongoDBAdmin
from pbn_api.admin.filters import MaDOIFilter, OdpowiednikWBPPFilter
from pbn_api.admin.widgets import PrettyJSONWidgetReadonly
from pbn_api.models import OswiadczenieInstytucji, Publication
from pbn_integrator.utils import zapisz_oswiadczenie_instytucji


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
            ) from e

        return self.cleaned_data["mongoId"]


@admin.register(Publication)
class PublicationAdmin(
    DjangoQLSearchMixin,
    BaseMongoDBAdmin,
):
    show_full_result_count = False
    djangoql_completion_enabled_by_default = False
    djangoql_completion = True

    list_display = [
        "title",
        "display_mongoId",
        "type",
        "volume",
        "year",
        "display_publicUri",
        "doi",
        "rekord_w_bpp",
        "rekord_w_bpp_pbn_uid",
        "id_mismatch_indicator",
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

    list_filter = [
        OdpowiednikWBPPFilter,
        "year",
        "status",
        MaDOIFilter,
    ] + BaseMongoDBAdmin.list_filter

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
        from pbn_integrator.utils import zapisz_mongodb

        zapisz_mongodb(form.cleaned_data["json"], Publication)
        obj.refresh_from_db()

    def display_mongoId(self, obj):
        """Display mongoId column"""
        return obj.mongoId

    display_mongoId.short_description = "mongoId"
    display_mongoId.admin_order_field = "mongoId"

    def display_publicUri(self, obj):
        """Display publicUri truncated to 150 characters"""
        if obj.publicUri:
            if len(obj.publicUri) > 150:
                return obj.publicUri[:150] + "..."
            return obj.publicUri
        return "-"

    display_publicUri.short_description = "publicUri"
    display_publicUri.admin_order_field = "publicUri"

    def rekord_w_bpp_pbn_uid(self, obj):
        """Display PBN UID from the linked BPP record"""
        rekord = obj.rekord_w_bpp
        if rekord and hasattr(rekord, "pbn_uid_id"):
            return rekord.pbn_uid_id
        return "-"

    rekord_w_bpp_pbn_uid.short_description = "Rekord w bpp PBN UID"

    def id_mismatch_indicator(self, obj):
        """Display an exclamation mark if IDs differ"""
        rekord = obj.rekord_w_bpp
        if rekord and hasattr(rekord, "pbn_uid_id"):
            # Compare the Publication's pk (which is its mongoId) with the BPP record's pbn_uid_id
            if obj.pk and rekord.pbn_uid_id and str(obj.pk) != str(rekord.pbn_uid_id):
                force_import_url = reverse(
                    "admin:pbn_api_publication_import_to_bpp_force", args=[obj.pk]
                )
                return format_html(
                    '<span title="Potencjalny duplikat po stronie PBN - mongoId ({}) inne od '
                    'rekord_w_bpp.pbn_uid_id ({})" '
                    'class="admin-status--red admin-status--bold">!?!</br>inne PBN '
                    "UID<br/>usuń w PBN?</span>"
                    "<hr>"
                    '<a href="{}" class="admin-link--danger" '
                    'title="Zaimportuj mimo ryzyka duplikatu">'
                    "Zaimportuj do BPP mimo wszystko [ryzyko duplikatu]</a>",
                    obj.pk,
                    rekord.pbn_uid_id,
                    force_import_url,
                )
        return ""

    id_mismatch_indicator.short_description = "Potencjalny duplikat w PBN"

    def rekord_w_bpp(self, obj):
        """Display BPP record or import link"""
        if obj.rekord_w_bpp:
            # If there's a BPP record, link to it
            model_name = obj.rekord_w_bpp.original._meta.model_name
            app_label = obj.rekord_w_bpp.original._meta.app_label

            change_url = reverse(
                f"admin:{app_label}_{model_name}_change",
                args=[obj.rekord_w_bpp.original.pk],
            )
            return format_html(
                '<a href="{}" title="Zobacz rekord w BPP">{}</a>',
                change_url,
                str(obj.rekord_w_bpp),
            )
        else:
            if obj.status != "ACTIVE":
                return format_html("Skasowany w PBN - nie można importować.")

            # If no BPP record, show import link
            import_url = reverse(
                "admin:pbn_api_publication_import_to_bpp", args=[obj.pk]
            )
            return format_html(
                '<a href="{}" class="admin-link--danger" '
                'title="Kliknij aby zaimportować do BPP">Zaimportuj do BPP</a>',
                import_url,
            )

    rekord_w_bpp.short_description = "Rekord w BPP"

    def get_urls(self):
        """Add custom URLs for admin views"""
        from django.urls import path

        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/import-to-bpp/",
                self.admin_site.admin_view(self.import_to_bpp_view),
                name="pbn_api_publication_import_to_bpp",
            ),
            path(
                "<path:object_id>/import-to-bpp-force/",
                self.admin_site.admin_view(
                    lambda request, object_id: self.import_to_bpp_view(
                        request, object_id, force=True
                    )
                ),
                name="pbn_api_publication_import_to_bpp_force",
            ),
        ]
        return custom_urls + urls

    def _pobierz_client_i_jednostke(self, request, uczelnia):
        """Get PBN client and default jednostka for import."""
        try:
            client = uczelnia.pbn_client(request.user.pbn_token)
        except Exception as e:
            self.message_user(
                request, f"Nie można utworzyć klienta PBN: {e}", level=messages.ERROR
            )
            return None, None

        default_jednostka = (
            Jednostka.objects.filter(
                uczelnia=uczelnia, widoczna=True, wchodzi_do_raportow=True
            )
            .exclude(pk__in=[-1, uczelnia.obca_jednostka_id])
            .first()
        )

        if not default_jednostka:
            self.message_user(
                request,
                "Nie można znaleźć domyślnej jednostki dla importu.",
                level=messages.ERROR,
            )
            return None, None

        return client, default_jednostka

    def _przetworz_oswiadczenia(self, request, publication, created_record, client):
        """Download and integrate oswiadczenia (statements) from PBN."""
        from pbn_integrator.utils import (
            integruj_oswiadczenia_z_instytucji_pojedyncza_praca,
        )

        try:
            oswiadczenia_data = client.get_institution_statements_of_single_publication(
                publication.pk
            )

            # Save and integrate oswiadczenia
            noted_pub = set()
            noted_aut = set()

            for oswiadczenie in oswiadczenia_data:
                # Save to MongoDB
                zapisz_oswiadczenie_instytucji(
                    oswiadczenie, OswiadczenieInstytucji, client=client
                )

                # Get the saved object
                oswiadczenie_obj = OswiadczenieInstytucji.objects.get(
                    id=oswiadczenie["id"]
                )

                # Integrate oswiadczenia with BPP
                integruj_oswiadczenia_z_instytucji_pojedyncza_praca(
                    oswiadczenie_obj,
                    noted_pub,
                    noted_aut,
                    missing_publication_callback=lambda pbn_uid_id: created_record,
                )

        except Exception as e:
            # Log oświadczenia error but don't fail the whole import
            self.message_user(
                request,
                f"Publikacja zaimportowana, ale wystąpił błąd z oświadczeniami: {str(e)}",
                level=messages.WARNING,
            )

    @transaction.atomic
    def import_to_bpp_view(self, request, object_id, force=False):
        """View to handle single publication import to BPP"""
        from pbn_integrator.importer import importuj_publikacje_po_pbn_uid_id

        # Get the publication
        try:
            publication = self.get_object(request, object_id)
        except Publication.DoesNotExist:
            self.message_user(
                request, "Publikacja nie została znaleziona.", level=messages.ERROR
            )
            return redirect("..")

        # Check if already has BPP record
        if not force and publication.rekord_w_bpp:
            self.message_user(
                request,
                "Ta publikacja już ma dopasowanie w BPP.",
                level=messages.WARNING,
            )
            return redirect("..")

        # Get uczelnia and client
        uczelnia = Uczelnia.objects.get_for_request(request)
        if not uczelnia:
            self.message_user(
                request,
                "Nie można określić uczelni dla tego żądania.",
                level=messages.ERROR,
            )
            return redirect("..")

        client, default_jednostka = self._pobierz_client_i_jednostke(request, uczelnia)
        if not client or not default_jednostka:
            return redirect("..")

        try:
            # Step 1: Import publication from PBN to BPP
            created_record = importuj_publikacje_po_pbn_uid_id(
                publication.pk,
                client,
                default_jednostka,
                force=force,
            )

            if created_record:
                # Step 2: Download oswiadczenia from PBN
                self._przetworz_oswiadczenia(
                    request, publication, created_record, client
                )

                # Update publication cache
                publication.refresh_from_db()

                self.message_user(
                    request,
                    f"Publikacja '{publication.title}' została pomyślnie zaimportowana do BPP.",
                    level=messages.SUCCESS,
                )

                # Redirect to the newly created BPP record
                # Jeśli created_record jest Rekordem (materialized view), użyj .original
                # aby uzyskać prawdziwy obiekt (Wydawnictwo_Ciagle lub Wydawnictwo_Zwarte)
                redirect_record = created_record
                if isinstance(created_record, Rekord):
                    redirect_record = created_record.original

                model_name = redirect_record._meta.model_name
                app_label = redirect_record._meta.app_label

                redirect_url = reverse(
                    f"admin:{app_label}_{model_name}_change", args=[redirect_record.pk]
                )
                return redirect(redirect_url)
            else:
                self.message_user(
                    request,
                    "Import nie utworzył żadnego rekordu w BPP.",
                    level=messages.ERROR,
                )

        except Exception as e:
            self.message_user(
                request, f"Błąd podczas importu: {str(e)}", level=messages.ERROR
            )

        return redirect("..")
