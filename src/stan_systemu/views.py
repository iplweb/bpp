from braces.views import GroupRequiredMixin
from denorm.models import DirtyInstance
from django.views.generic import TemplateView

from bpp.const import GR_WPROWADZANIE_DANYCH


class IloscObiektowWDenormQueue(GroupRequiredMixin, TemplateView):
    template_name = "stan_systemu/ilosc_obiektow_w_denorm_queue.html"
    group_required = GR_WPROWADZANIE_DANYCH

    def get_context_data(self):
        return {"dirtyinstance_count": DirtyInstance.objects.count()}
