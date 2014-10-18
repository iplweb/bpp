# -*- enco
# ding: utf-8 -*-
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Sum
from bpp.models.cache import Rekord
from multiseek.views import MultiseekResults


class MyMultiseekResults(MultiseekResults):
    registry = 'bpp.multiseek.registry'

    def get_queryset(self):
        qset = super(MyMultiseekResults, self).get_queryset()
        return qset.only("content_type__model", "object_id", "opis_bibliograficzny_cache")

    @transaction.atomic
    def get_context_data(self, **kwargs):
        t = None

        ctx = super(MyMultiseekResults, self).get_context_data()

        qset = self.get_queryset()

        if ctx['report_type'] in ['pkt_wewn', 'pkt_wewn_bez']:
            ctx['sumy'] = qset.aggregate(
                Sum('impact_factor'), Sum('punkty_kbn'),
                Sum('index_copernicus'), Sum('punktacja_wewnetrzna'))

        ctx['paginator_count'] = qset.count()
        object_list = ctx['object_list']
        object_list.count = lambda *args, **kw: ctx['paginator_count']

        return ctx
