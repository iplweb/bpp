from braces.views import JSONResponseMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView, RedirectView

from import_dyscyplin.views import WprowadzanieDanychRequiredMixin
from rozbieznosci_dyscyplin.models import RozbieznosciView
from rozbieznosci_dyscyplin.util import object_or_something


class NieistniejacaDyscyplina:
    pk = -1
    nazwa = "--"


class RedirectToAdmin(RedirectView):
    def get_redirect_url(self, *args, **kw):
        ctype = ContentType.objects.get(pk=self.kwargs['content_type_id'])
        return '/admin/%s/%s/%i/change/' % (ctype.app_label, ctype.model, self.kwargs['object_id'])


class API_RozbieznosciDyscyplin(WprowadzanieDanychRequiredMixin, JSONResponseMixin, View):

    def serialize_row(self, obj):
        ret = {
            "tytul_oryginalny": "<a target=_blank href='%s'>%s</a>" % (
                reverse("rozbieznosci_dyscyplin:redirect-to-admin",
                        kwargs=dict(
                            content_type_id=obj.rekord.id[0],
                            object_id=obj.rekord.id[1])
                        ),
                obj.rekord.tytul_oryginalny),

            "rok": obj.rekord.rok,

            "autor": "<a target=_blank href='%s'>%s %s</a>" % (
                reverse("admin:bpp_autor_change", args=(obj.autor.pk,)),
                obj.autor.nazwisko, obj.autor.imiona),

            "dyscyplina_rekordu": object_or_something(obj, 'dyscyplina_rekordu').nazwa,
            "dyscyplina_autora": object_or_something(obj, 'dyscyplina_autora').nazwa,
            "subdyscyplina_autora": object_or_something(obj, 'subdyscyplina_autora').nazwa,
        }
        return ret

    def get(self, *args, **kw):
        records = RozbieznosciView.objects.all().select_related("autor", "rekord", "dyscyplina_rekordu", "dyscyplina_autora", "subdyscyplina_autora")
        recordsTotal = records.count()

        start = int(self.request.GET.get("start", 0))
        draw = int(self.request.GET.get("draw", 1))
        length = int(self.request.GET.get("length", 10))

        ordering = int(self.request.GET.get("order[0][column]", 0))
        direction = self.request.GET.get("order[0][dir]", "asc")

        fld = self.request.GET.get("columns[%i][data]" % ordering, "tytul_oryginalny")

        if fld:
            ordering_mapping = {
                "tytul_oryginalny": "rekord__tytul_oryginalny",
                "rok": "rekord__rok",
                "autor": "autor__nazwisko",
                "dyscyplina_rekordu": "rekord__dyscyplina_rekordu",
                "dyscyplina_autora": "rekord__dyscyplina_autora",
                "subdyscyplina_autora": "rekord__subdyscyplina_autora",
            }
            fld = ordering_mapping.get(fld, fld)
        if direction != 'asc':
            fld = '-' + fld

        recordsFiltered = records
        recordsFilteredCount = recordsTotal

        search = self.request.GET.get("search[value]", "")
        if search:
            for elem in search.split(" "):
                try:
                    int(elem)
                    recordsFiltered = recordsFiltered.filter(
                        Q(rekord__rok=elem) |
                        Q(rekord__tytul_oryginalny__icontains=elem)
                    )
                except:
                    recordsFiltered = recordsFiltered.filter(
                        Q(autor__nazwisko__icontains=elem) |
                        Q(autor__imiona__icontains=elem) |
                        Q(rekord__tytul_oryginalny__icontains=elem) |

                        Q(dyscyplina_rekordu__nazwa__icontains=elem) |
                        Q(subdyscyplina_autora__nazwa__icontains=elem) |
                        Q(dyscyplina_autora__nazwa__icontains=elem) |
                        Q(dyscyplina_rekordu__kod__icontains=elem) |
                        Q(subdyscyplina_autora__kod__icontains=elem) |
                        Q(dyscyplina_autora__kod__icontains=elem)
                    )

            recordsFilteredCount = recordsFiltered.count()

        return self.render_json_response(
            {
                "data": [self.serialize_row(obj) for obj in recordsFiltered.order_by(fld)[start:start + length]],
                "draw": draw,
                "recordsTotal": recordsTotal,
                "recordsFiltered": recordsFilteredCount,
            }
        )


class MainView(WprowadzanieDanychRequiredMixin, TemplateView):
    template_name = 'rozbieznosci_dyscyplin/main.html'
