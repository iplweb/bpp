"""Mixin admina dokładający link „zobacz w repozytorium" do change-formów
rekordów publikacji wysłanych do DSpace."""

from django.contrib import admin
from django.utils.html import format_html_join

FIELD_NAME = "dspace_repo_link"


def _fieldsets_contain(fieldsets, field_name):
    """Czy ``field_name`` występuje już w którymś z fieldsetów (uwzględniając
    wiersze będące tuplami/listami pól)."""
    for _name, opts in fieldsets:
        for entry in opts.get("fields", ()):
            if entry == field_name:
                return True
            if isinstance(entry, (list, tuple)) and field_name in entry:
                return True
    return False


class DSpaceLinkAdminMixin:
    """Dla rekordu pomyślnie wysłanego do DSpace (z handle) dokłada na końcu
    change-formu sekcję „Repozytorium DSpace" z linkiem do rekordu w
    repozytorium. Nie pokazuje się na formularzu dodawania ani gdy rekord nie
    został (jeszcze) wysłany.

    Mixin musi stać jako **pierwszy** w liście baz danego ``ModelAdmin``,
    żeby jego ``get_fieldsets``/``get_readonly_fields`` opakowały metody
    admina przez ``super()``."""

    def _dspace_repo_links(self, obj):
        if obj is None or getattr(obj, "pk", None) is None:
            return []
        from dspace_api.links import public_links_for_rec

        return public_links_for_rec(obj)

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        # Pole dorzucamy tylko, gdy realnie jest co pokazać — żeby nie wisiało
        # puste na formularzu dodawania ani na rekordach niewysłanych.
        if self._dspace_repo_links(obj) and FIELD_NAME not in readonly:
            readonly = readonly + [FIELD_NAME]
        return readonly

    def get_fieldsets(self, request, obj=None):
        fieldsets = list(super().get_fieldsets(request, obj))
        # Gdy admin nie ma jawnych fieldsetów, Django i tak dołoży readonly do
        # auto-fieldsetu — wtedy nie dublujemy własną sekcją.
        if self._dspace_repo_links(obj) and not _fieldsets_contain(
            fieldsets, FIELD_NAME
        ):
            fieldsets = fieldsets + [("Repozytorium DSpace", {"fields": (FIELD_NAME,)})]
        return fieldsets

    @admin.display(description="Zobacz w repozytorium")
    def dspace_repo_link(self, obj):
        links = self._dspace_repo_links(obj)
        if not links:
            return "—"
        return format_html_join(
            " · ",
            '<a href="{}" target="_blank" rel="noopener">🔗 {}</a>',
            ((url, uczelnia) for (uczelnia, url) in links),
        )
