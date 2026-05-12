"""Permission hook for django-formdefaults.

System-wide form defaults editing is opened up to any staff user
(``is_staff``) — the default in django-formdefaults restricts it to
``is_superuser``.
"""


def can_edit_system_wide(user, form_repr) -> bool:
    if user is None or not getattr(user, "is_authenticated", False):
        return False
    return bool(getattr(user, "is_staff", False))
