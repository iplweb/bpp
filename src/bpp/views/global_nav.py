from django.contrib.contenttypes.models import ContentType
from django.http.response import (
    HttpResponseBadRequest,
    HttpResponseNotAllowed,
    HttpResponseRedirect,
)
from django.urls.base import reverse

lookup_map_user = {
    "bpp.autor": ("bpp:browse_autor", lambda x: (None, {"slug": x.slug})),
    "bpp.jednostka": ("bpp:browse_jednostka", lambda x: (None, {"slug": x.slug})),
    "bpp.zrodlo": ("bpp:browse_zrodlo", lambda x: (None, {"slug": x.slug})),
    "bpp.rekord": (
        "bpp:browse_praca_old",
        lambda x: (None, {"model": x.content_type.model, "pk": x.object_id}),
    ),
}


def _pk_args(x):
    """Return args tuple with primary key for admin URL reverse."""
    return ((x.pk,), {})


class _lookup_map_admin(dict):
    def get(self, arg):
        app_label, name = arg.split(".")
        return (f"admin:{app_label}_{name}_change", _pk_args)


lookup_map_admin = _lookup_map_admin()


def _handle_app_navigation(param):
    """Handle Django app navigation (app:app_label)."""
    app_label = param.replace("app:", "")
    url = reverse("admin:app_list", kwargs={"app_label": app_label})
    return HttpResponseRedirect(url)


def _handle_model_navigation(param):
    """Handle Django model navigation (model:app_label:model_name[:add])."""
    parts = param.split(":")
    if len(parts) < 3:
        return None

    _, app_label, model_name = parts[:3]
    is_add = len(parts) == 4 and parts[3] == "add"

    if is_add:
        url = reverse(f"admin:{app_label}_{model_name}_add")
    else:
        url = reverse(f"admin:{app_label}_{model_name}_changelist")
    return HttpResponseRedirect(url)


def _resolve_lookup_url(lookup_map, klass, source):
    """Resolve URL and args function from lookup map."""
    try:
        url, f = lookup_map.get(f"{klass.app_label}.{klass.model}")
    except (TypeError, KeyError):
        raise KeyError(f"dodaj wpis do mapy lookup ({source}, {klass.model})") from None
    return url, f


def global_nav_redir(request, param):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    source = request.GET.get("source", "user")
    if source not in ("user", "admin"):
        return HttpResponseBadRequest()

    if param.startswith("app:"):
        return _handle_app_navigation(param)

    if param.startswith("model:"):
        response = _handle_model_navigation(param)
        if response:
            return response

    # Original handling for content types
    try:
        content_type_id, object_id = param.split("-", 1)
    except (TypeError, ValueError):
        return HttpResponseBadRequest()

    klass = ContentType.objects.get_for_id(content_type_id)
    if klass.app_label not in ["bpp", "pbn_api"]:
        raise NotImplementedError("Lookups for other apps not implemented")

    lookup_map = lookup_map_user
    if source == "admin":
        lookup_map = lookup_map_admin

    if klass.model == "rekord":
        object_id = [
            int(x.strip())
            for x in object_id.replace("(", "").replace(")", "").split(",")
        ]

    object = klass.get_object_for_this_type(pk=object_id)

    url, f = _resolve_lookup_url(lookup_map, klass, source)
    args, kwargs = f(object)

    return HttpResponseRedirect(reverse(url, args=args, kwargs=kwargs))
