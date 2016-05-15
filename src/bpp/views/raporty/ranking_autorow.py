# -*- encoding: utf-8 -*-
from django.core.urlresolvers import reverse
from django.db.models.aggregates import Sum
from django.db.models.query import QuerySet
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
                  'impact_factor_sum',
                  'punkty_kbn_sum')
    punkty_kbn_sum = Column("Punkty PK", "punkty_kbn_sum")
    impact_factor_sum = Column("Impact Factor", "impact_factor_sum")

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

    _cache = None


    def get_queryset(self):
        if self._cache: return self._cache

        qset = Sumy.objects.annotate(
            impact_factor_sum=Sum('impact_factor'),
            punkty_kbn_sum=Sum('punkty_kbn'),
        ).filter(
            rok__gte=self.kwargs['od_roku'],
            rok__lte=self.kwargs['do_roku']
        ).only('autor', 'jednostka', 'wydzial')

        wydzialy = self.get_wydzialy()
        if wydzialy:
            qset = qset.filter(wydzial__in=wydzialy)

        # Przelecenie po całym queryset - za pomocą len(ret) musi tutaj być, bo jest jakiś
        # bug; ret.count() da niekiedy zły wynik; podejrzewam jakieś problemy w Django
        # po stronie sql/query.py get_aggregation
        len(qset)

        self._cache = qset

        return qset

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
        context['od_roku'] = self.kwargs['od_roku']
        context['do_roku'] = self.kwargs['do_roku']
        jeden_rok = False
        if self.kwargs['od_roku'] == self.kwargs['do_roku']:
            context['rok'] = self.kwargs['od_roku']
            jeden_rok = True
        wydzialy = self.get_wydzialy()
        context['wydzialy'] = wydzialy
        if jeden_rok:
            context['table_title'] = u"Ranking autorów za rok %s" % context['rok']
        else:
            context['table_title'] = u"Ranking autorów za lata %s - %s" % (context['od_roku'], context['do_roku'])
        context['tab_subtitle'] = u''
        #if wydzialy.count() != self.get_dostepne_wydzialy.count():
        context['table_subtitle'] = u", ".join([x.nazwa for x in wydzialy])
        return context