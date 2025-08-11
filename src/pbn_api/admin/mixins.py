from django.db.models import BLANK_CHOICE_DASH

from django.contrib import messages


class ReadOnlyListChangeFormAdminMixin:
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, *args, **kw):
        return False

    # To nie moze byc właczone, bo readonly_fields nie moga miec swoich widgetow.
    # Zatem, versions jest robione za pomoca wiodgetu ktory dostaje atrybut readonly.
    # def has_change_permission(self, *args, **kw):
    #     return False

    def get_action_choices(self, request, default_choices=BLANK_CHOICE_DASH):
        return []

    def save_model(self, request, obj, form, change):
        # Uczyń FAKTYCZNIE readonly :-)
        messages.error(
            request,
            "Obiekt NIE został zapisany -- nie można edytować tej części serwisu.",
        )
        return


class ReadOnlyListChangeFormAdminAddTooMixin(ReadOnlyListChangeFormAdminMixin):
    def has_change_permission(self, *args, **kw):
        return False
