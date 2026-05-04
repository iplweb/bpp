"""Admin interface for importer_publikacji models."""

import html
import json

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from bpp.admin.core import DynamicAdminFilterMixin

from .models import ImportedAuthor, ImportSession


@admin.register(ImportSession)
class ImportSessionAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "created",
        "provider_name",
        "identifier",
        "status_badge",
        "title_display",
        "created_by",
        "modified_by",
    ]
    list_filter = ["status", "provider_name", "created", "created_by"]
    search_fields = [
        "identifier",
        "normalized_data__title",
        "normalized_data__doi",
        "created_by__username",
        "modified_by__username",
    ]
    list_select_related = ["created_by", "modified_by"]
    date_hierarchy = "created"
    readonly_fields = [
        "created",
        "modified",
        "created_by",
        "modified_by",
        "provider_name",
        "identifier",
        "status",
        "raw_data_display",
        "normalized_data_display",
        "matched_data_display",
        "authors_display",
        "created_record_link",
    ]

    fieldsets = (
        (
            "Podstawowe informacje",
            {
                "fields": (
                    "created",
                    "modified",
                    "created_by",
                    "modified_by",
                )
            },
        ),
        (
            "Dane dostawcy",
            {
                "fields": (
                    "provider_name",
                    "identifier",
                    "status",
                )
            },
        ),
        (
            "Oryginalne dane z API",
            {
                "fields": ("raw_data_display",),
                "classes": ("collapse",),
            },
        ),
        (
            "Znormalizowane dane",
            {
                "fields": ("normalized_data_display",),
                "classes": ("collapse",),
            },
        ),
        (
            "Dopasowane dane",
            {
                "fields": ("matched_data_display",),
                "classes": ("collapse",),
            },
        ),
        (
            "Autorzy",
            {
                "fields": ("authors_display",),
                "classes": ("collapse",),
            },
        ),
        (
            "Utworzony rekord",
            {
                "fields": ("created_record_link",),
                "classes": ("collapse",),
            },
        ),
    )

    def status_badge(self, obj):
        status_colors = {
            "fetched": "primary",
            "verified": "primary",
            "source_matched": "primary",
            "authors_matched": "primary",
            "review": "warning",
            "completed": "success",
            "cancelled": "alert",
        }
        color = status_colors.get(obj.status, "secondary")
        return format_html(
            '<span class="label {}">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_badge.short_description = "Status"

    def title_display(self, obj):
        title = obj.normalized_data.get("title") if obj.normalized_data else ""
        if title:
            return title[:60] + "..." if len(title) > 60 else title
        return "-"

    title_display.short_description = "Tytuł"

    def raw_data_display(self, obj):
        if obj.raw_data:
            formatted = json.dumps(
                obj.raw_data, indent=2, sort_keys=True, ensure_ascii=False
            )
            escaped = html.escape(formatted)
            return mark_safe(
                f'<pre style="white-space: pre-wrap; max-width: 900px; max-height: 600px; overflow-y: auto; font-size: 0.85rem;">{escaped}</pre>'
            )
        return "-"

    raw_data_display.short_description = "Oryginalne dane z API (raw_data)"

    def normalized_data_display(self, obj):
        if obj.normalized_data:
            formatted = json.dumps(
                obj.normalized_data, indent=2, sort_keys=True, ensure_ascii=False
            )
            escaped = html.escape(formatted)
            return mark_safe(
                f'<pre style="white-space: pre-wrap; max-width: 900px; max-height: 600px; overflow-y: auto; font-size: 0.85rem;">{escaped}</pre>'
            )
        return "-"

    normalized_data_display.short_description = "Dane znormalizowane"

    def matched_data_display(self, obj):
        if obj.matched_data:
            formatted = json.dumps(
                obj.matched_data, indent=2, sort_keys=True, ensure_ascii=False
            )
            escaped = html.escape(formatted)
            return mark_safe(
                f'<pre style="white-space: pre-wrap; max-width: 900px; max-height: 400px; overflow-y: auto; font-size: 0.85rem;">{escaped}</pre>'
            )
        return "-"

    matched_data_display.short_description = "Wybory użytkownika (matched_data)"

    def authors_display(self, obj):
        authors = obj.authors.all().order_by("order")
        if not authors:
            return "-"

        rows = []
        for author in authors:
            match_status_colors = {
                "auto_exact": "success",
                "auto_loose": "warning",
                "manual": "primary",
                "unmatched": "alert",
            }
            color = match_status_colors.get(author.match_status, "secondary")

            matched_info = []
            if author.matched_autor:
                matched_info.append(f"Autor: {author.matched_autor}")
            if author.matched_jednostka:
                matched_info.append(f"Jednostka: {author.matched_jednostka}")
            if author.matched_dyscyplina:
                matched_info.append(f"Dyscyplina: {author.matched_dyscyplina}")

            matched_str = " | ".join(matched_info) if matched_info else "-"

            rows.append(
                f"<tr>"
                f"<td>{author.order}</td>"
                f'<td><span class="label {color}">{author.get_match_status_display()}</span></td>'
                f"<td>{author.display_name}</td>"
                f"<td>{matched_str}</td>"
                f"</tr>"
            )

        return mark_safe(
            f'<table class="hover">'
            f"<thead><tr><th>Lp.</th><th>Status</th><th>Nazwa</th><th>Dopasowano do</th></tr></thead>"
            f"<tbody>{''.join(rows)}</tbody>"
            f"</table>"
        )

    authors_display.short_description = "Autorzy"

    def created_record_link(self, obj):
        if obj.created_record_id and obj.created_record_content_type:
            try:
                record = obj.created_record
                if record:
                    admin_url = self._get_admin_url(record)
                    return format_html(
                        '<a href="{}">{}</a> ({})',
                        admin_url,
                        record,
                        obj.created_record_content_type.model,
                    )
            except Exception:
                return format_html(
                    "ID: {} ({}) - nie można załadować",
                    obj.created_record_id,
                    obj.created_record_content_type,
                )
        return "-"

    created_record_link.short_description = "Utworzony rekord"

    def _get_admin_url(self, obj):
        from django.urls import reverse

        opts = obj._meta
        return reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk]
        )

    def has_add_permission(self, request):
        return False


@admin.register(ImportedAuthor)
class ImportedAuthorAdmin(DynamicAdminFilterMixin, admin.ModelAdmin):
    list_display = [
        "id",
        "session_link",
        "order",
        "display_name",
        "match_status_badge",
        "matched_autor",
        "matched_jednostka",
        "matched_dyscyplina",
    ]
    list_filter = ["match_status", "session__provider_name", "session__status"]
    search_fields = [
        "family_name",
        "given_name",
        "orcid",
        "matched_autor__nazwisko",
        "matched_autor__imiona",
        "session__identifier",
        "session__normalized_data__title",
    ]
    list_select_related = [
        "session",
        "matched_autor",
        "matched_jednostka",
        "matched_dyscyplina",
    ]
    readonly_fields = ["session", "order", "family_name", "given_name", "orcid"]

    fieldsets = (
        (
            "Podstawowe informacje",
            {
                "fields": (
                    "session_link",
                    "order",
                    "family_name",
                    "given_name",
                    "orcid",
                )
            },
        ),
        (
            "Dopasowanie",
            {
                "fields": (
                    "match_status",
                    "matched_autor",
                    "matched_jednostka",
                    "matched_dyscyplina",
                    "dyscyplina_source",
                )
            },
        ),
    )

    def session_link(self, obj):
        url = self._get_admin_url(obj.session)
        return format_html(
            '<a href="{}">Session #{}</a> ({})',
            url,
            obj.session.id,
            obj.session.provider_name,
        )

    session_link.short_description = "Sesja"

    def match_status_badge(self, obj):
        status_colors = {
            "auto_exact": "success",
            "auto_loose": "warning",
            "manual": "primary",
            "unmatched": "alert",
        }
        color = status_colors.get(obj.match_status, "secondary")
        return format_html(
            '<span class="label {}">{}</span>',
            color,
            obj.get_match_status_display(),
        )

    match_status_badge.short_description = "Status dopasowania"

    def _get_admin_url(self, obj):
        from django.urls import reverse

        opts = obj._meta
        return reverse(
            f"admin:{opts.app_label}_{opts.model_name}_change", args=[obj.pk]
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        # Pozwól przeglądać, ale nie zmieniać
        return False
