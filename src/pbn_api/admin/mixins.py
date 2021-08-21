from django.db.models import BLANK_CHOICE_DASH


class ReadOnlyListChangeFormAdminMixin:
    actions = None

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, *args, **kw):
        return False

    def has_change_permission(self, *args, **kw):
        return False

    def get_action_choices(self, request, default_choices=BLANK_CHOICE_DASH):
        return []
