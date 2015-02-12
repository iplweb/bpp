# -*- enco
# ding: utf-8 -*-
from django.db import transaction
from django.db.models import Sum
from multiseek.logic import get_registry
from multiseek.views import MultiseekResults, MULTISEEK_SESSION_KEY_REMOVED


class MyMultiseekResults(MultiseekResults):
    registry = 'bpp.multiseek.registry'

    def get_queryset(self, only_those_ids=None):

        if only_those_ids:
            qset = get_registry(self.registry).get_query_for_model(
                self.get_multiseek_data()).filter(pk__in=only_those_ids)
        else:
            qset = super(MyMultiseekResults, self).get_queryset()

        return qset.only("content_type__model", "object_id", "opis_bibliograficzny_cache")

    @transaction.atomic
    def get_context_data(self, **kwargs):
        t = None

        ctx = super(MyMultiseekResults, self).get_context_data()

        if not self.request.GET.get("print-removed", False):
            qset = self.get_queryset()
        else:
            qset = self.get_queryset(only_those_ids=self.request.session.get(MULTISEEK_SESSION_KEY_REMOVED, []))
            ctx['print_removed'] = True

        ctx['paginator_count'] = qset.count()
        object_list = ctx['object_list']
        object_list.count = lambda *args, **kw: ctx['paginator_count']

        if ctx['report_type'] in ['pkt_wewn', 'pkt_wewn_bez', 'table']:
            ctx['sumy'] = qset.aggregate(
                Sum('impact_factor'), Sum('punkty_kbn'),
                Sum('index_copernicus'), Sum('punktacja_wewnetrzna'))


        if 'MULTISEEK_TITLE' not in self.request.session:
            self.request.session['MULTISEEK_TITLE'] = 'Rezultat wyszukiwania'

        return ctx
