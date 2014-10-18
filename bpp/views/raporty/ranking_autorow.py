# -*- encoding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.template.defaultfilters import safe
from django_tables2_reports.tables import TableReport

from bpp.models import Autor, Sumy
from django_tables2_reports.views import ReportTableView


class RankingAutorowTable(TableReport):

    class Meta:
        model = Autor
        attrs = {"class": "paleblue"}
        fields = ('autor',
                  'jednostka',
                  'wydzial',
                  'impact_factor',
                  'punkty_kbn')

    def __init__(self, *args, **kwargs):
        kwargs['template'] = "raporty/ranking-autorow-tabelka.html"
        super(RankingAutorowTable, self).__init__(*args, **kwargs)

    def render_autor(self, record):
        return safe('<a href="%s">%s</a>' % (
            reverse('bpp:browse_autor', args=(record.autor.slug,)),
            unicode(record.autor)))


class RankingAutorow(ReportTableView):
    template_name = "raporty/ranking-autorow.html"
    table_class = RankingAutorowTable

    def get_queryset(self):
        return Sumy.objects.filter(rok=self.kwargs['rok']).select_related()

    def get_context_data(self, **kwargs):
        context = super(ReportTableView, self).get_context_data(**kwargs)
        context['rok'] = self.kwargs['rok']
        context['table_title'] = u"Ranking autorów za rok %s" % context['rok']
        return context