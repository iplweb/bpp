from django.views.generic import RedirectView

from django.contrib.contenttypes.models import ContentType


class NieistniejacaDyscyplina:
    pk = -1
    nazwa = "--"


class RedirectToAdmin(RedirectView):
    def get_redirect_url(self, *args, **kw):
        ctype = ContentType.objects.get(pk=self.kwargs["content_type_id"])
        return "/admin/%s/%s/%i/change/" % (
            ctype.app_label,
            ctype.model,
            self.kwargs["object_id"],
        )
