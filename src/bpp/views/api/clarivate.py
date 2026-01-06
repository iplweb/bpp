import json
import logging
import sys

import requests
import rollbar
from braces.views import GroupRequiredMixin, JSONResponseMixin
from django.views.generic.detail import BaseDetailView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Uczelnia

logger = logging.getLogger(__name__)


class GetWoSAMRInformation(JSONResponseMixin, GroupRequiredMixin, BaseDetailView):
    group_required = GR_WPROWADZANIE_DANYCH
    model = Uczelnia

    def get_context_data(self, **kwargs):
        doi = self.request.POST.get("doi", None)
        pmid = self.request.POST.get("pmid", None)

        if doi is None and pmid is None:
            return {"status": "error", "info": "Podaj DOI lub PubMedID"}

        try:
            res = self.object.wosclient().query_single(pmid, doi)
        except requests.RequestException:
            rollbar.report_exc_info(sys.exc_info())
            logger.exception("Błąd połączenia z WOS-AMR")
            return {"status": "error", "info": "Błąd komunikacji z Clarivate API"}
        except (KeyError, ValueError, json.JSONDecodeError):
            rollbar.report_exc_info(sys.exc_info())
            logger.exception("Nieprawidłowa odpowiedź WOS-AMR")
            return {"status": "error", "info": "Błąd parsowania odpowiedzi z WOS"}
        except Exception:
            rollbar.report_exc_info(sys.exc_info())
            logger.exception("Nieoczekiwany błąd WOS-AMR")
            return {"status": "error", "info": "Wewnętrzny błąd systemu"}

        if res.get("message") == "No Result Found":
            return {"status": "ok", "timesCited": None}

        return {"status": "ok", "timesCited": res.get("timesCited")}

    def post(self, request, *args, **kw):
        self.object = self.get_object()
        return self.render_json_response(self.get_context_data())
