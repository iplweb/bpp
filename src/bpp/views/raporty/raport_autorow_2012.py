# -*- encoding: utf-8 -*-

from django.views.generic import DetailView
from django_tables2 import RequestConfig

from bpp.models import Autor
from bpp.views.raporty.raport_aut_jed_common import WSZYSTKIE_TABELE, \
    raport_jednostek_tabela, get_base_query_autor, raport_autorow_tabela


class RaportAutorow2012(DetailView):
    model = Autor
    template_name = "raporty/raport_jednostek_autorow_2012/raport_autorow.html"

    def get_context_data(self, **kwargs):
        rok_min = self.kwargs['rok_min']
        rok_max = self.kwargs.get('rok_max', None)
        if rok_max is None:
            rok_max = rok_min

        rok_min, rok_max = min(rok_min, rok_max), max(rok_min, rok_max)

        base_query = get_base_query_autor(
            autor=self.object,
            rok_min=rok_min,
            rok_max=rok_max)

        kw = dict(rok_min=rok_min, rok_max=rok_max)

        for key, klass in WSZYSTKIE_TABELE.items():
            kw['tabela_%s' % key] = klass(
                raport_autorow_tabela(key, base_query))

        for tabela in [tabela for key, tabela in kw.items() if
                       key.startswith('tabela_')]:
            RequestConfig(self.request).configure(tabela)

        return DetailView.get_context_data(self, **kw)

