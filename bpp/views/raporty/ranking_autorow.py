# -*- encoding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.db.models.query_utils import Q
from django.template.defaultfilters import safe
from django_tables2.columns.base import Column
from django_tables2_reports.tables import TableReport

from bpp.models import Autor, Sumy
from django_tables2_reports.views import ReportTableView
from bpp.models.struktura import Wydzial


class RankingAutorowTable(TableReport):

    class Meta:
        model = Autor
        attrs = {"class": "paleblue"}
        fields = ('autor',
                  'jednostka',
                  'wydzial',
                  'impact_factor',
                  'punkty_kbn')
    punkty_kbn = Column("Punkty PK", "punkty_kbn")

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
        qset = Sumy.objects.filter(rok=self.kwargs['rok'])

        wydzialy = self.get_wydzialy()
        if wydzialy:
            qset = qset.filter(wydzial__in=wydzialy)

        return qset.select_related()

    def get_dostepne_wydzialy(self):
        return Wydzial.objects.filter(zezwalaj_na_ranking_autorow=True)

    def get_wydzialy(self):
        base_query = self.get_dostepne_wydzialy()

        wydzialy = self.request.GET.getlist("wydzialy[]")
        if wydzialy:
            try:
                wydzialy = base_query.filter(pk__in=[int(x) for x in wydzialy])
                return wydzialy
            except (TypeError, ValueError):
                pass

        return base_query

    def get_context_data(self, **kwargs):
        context = super(ReportTableView, self).get_context_data(**kwargs)
        context['rok'] = self.kwargs['rok']
        wydzialy = self.get_wydzialy()
        context['wydzialy'] = wydzialy
        context['table_title'] = u"Ranking autorów za rok %s" % context['rok']
        context['tab_subtitle'] = u''
        #if wydzialy.count() != self.get_dostepne_wydzialy.count():
        context['table_subtitle'] = u", ".join([x.nazwa for x in wydzialy])
        return context