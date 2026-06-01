"""BPP wrapper for django-formdefaults' button template tag.

The upstream ``{% formdefaults_button form %}`` deliberately does NOT
snapshot forms into the DB — that is supposed to happen earlier via
``@register_form``, the ``FORMDEFAULTS_FORMS`` setting, or
``FormDefaultsMixin`` / ``get_form_defaults()`` inside the view.

We want the buttons to appear *only* on forms whose view has opted in
(currently: views using ``FormDefaultsMixin``), so this wrapper checks
for an existing ``FormRepresentation`` row and renders nothing when the
form is not registered. Templates can include the tag unconditionally —
adding a mixin to a previously-unregistered view will make the buttons
appear on the next request, with no template changes.
"""

from django import template
from django.urls import reverse
from formdefaults.models import FormRepresentation
from formdefaults.permissions import can_edit_system_wide_defaults
from formdefaults.util import full_name

register = template.Library()


@register.inclusion_tag("formdefaults/_button.html", takes_context=True)
def bpp_formdefaults_button(context, form):
    request = context.get("request")
    if request is None or not getattr(request.user, "is_authenticated", False):
        return {"show": False}

    if form is None or not hasattr(form, "fields"):
        return {"show": False}

    fqn = full_name(form)
    if not FormRepresentation.objects.filter(full_name=fqn).exists():
        return {"show": False}

    show_system = can_edit_system_wide_defaults(request.user, form_class=type(form))
    return {
        "show": True,
        "url": reverse("formdefaults:user-edit", args=[fqn]),
        "system_url": reverse("formdefaults:system-edit", args=[fqn])
        if show_system
        else None,
        "show_system": show_system,
        "form_full_name": fqn,
    }
