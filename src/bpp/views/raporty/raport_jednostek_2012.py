# -*- encoding: utf-8 -*-

from django.views.generic import DetailView
from django_tables2 import RequestConfig

from bpp.models import Jednostka
from bpp.views.raporty.raport_aut_jed_common import WSZYSTKIE_TABELE, \
    get_base_query_jednostka, raport_jednostek_tabela, MSWordFromTemplateResponse, Raport2012CommonView


class RaportJednostek2012(Raport2012CommonView):
    model = Jednostka
    template_name = "raporty/raport_jednostek_autorow_2012/raport_jednostek.html"

    def get_context_data(self, **kwargs):
        rok_min = self.kwargs['rok_min']
        rok_max = self.kwargs.get('rok_max', None)
        if rok_max is None:
            rok_max = rok_min

        rok_min, rok_max = min(rok_min, rok_max), max(rok_min, rok_max)

        base_query = get_base_query_jednostka(
            jednostka=self.object,
            rok_min=rok_min,
            rok_max=rok_max)

        kw = dict(rok_min=rok_min, rok_max=rok_max)

        for key, klass in list(WSZYSTKIE_TABELE.items()):
            kw['tabela_%s' % key] = klass(
                raport_jednostek_tabela(key, base_query, self.object))

        for tabela in [tabela for key, tabela in list(kw.items()) if
                       key.startswith('tabela_')]:
            RequestConfig(self.request).configure(tabela)

        if hasattr(self.request, "GET"):
            output = self.request.GET.get("output", "")
            kw['output'] = output

        return DetailView.get_context_data(self, **kw)

    def get_short_object_name(self):
        return self.object.skrot
