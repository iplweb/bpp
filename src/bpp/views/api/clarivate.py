import logging

from braces.views import GroupRequiredMixin, JSONResponseMixin
from django.views.generic.detail import BaseDetailView

from bpp.models import Uczelnia
from bpp.models.const import GR_WPROWADZANIE_DANYCH

logger = logging.getLogger("blabla")


class GetWoSAMRInformation(JSONResponseMixin, GroupRequiredMixin, BaseDetailView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Uczelnia

    def get_context_data(self, **kwargs):
        doi = self.request.POST.get("doi", None)
        pmid = self.request.POST.get("pmid", None)

        if doi is None and pmid is None:
            return {'status': 'error',
                    'info': 'Podaj DOI lub PubMedID'}

        try:
            res = self.object.wosclient().query_single(pmid, doi)
        except Exception as e:
            logger.exception("Podczas zapytania WOS-AMR")
            return {'status': 'error',
                    'info': '%s' % e}

        if res.get("message") == 'No Result Found':
            return {'status': 'ok', 'timesCited': None}

        return {'status': 'ok',
                'timesCited': res.get('timesCited')}

    def post(self, request, *args, **kw):
        self.object = self.get_object()
        return self.render_json_response(self.get_context_data())
