"""Mixin classes for PBN export queue views."""

from django.contrib.auth.mixins import UserPassesTestMixin

from bpp.const import GR_WPROWADZANIE_DANYCH


def kolejka_dla_requestu(request):
    """Kolejka PBN zawężona do uczelni z domeny requestu (multi-hosted).

    Obowiązuje także superusera: na domenie uczelni X jest zalogowany do PBN
    na profil X, więc wpisy innych uczelni nie mają tu sensu. Pełny wgląd
    w kolejkę wszystkich uczelni daje admin Django.
    """
    from bpp.models import Uczelnia
    from pbn_export_queue.models import PBN_Export_Queue

    return PBN_Export_Queue.objects.dla_uczelni(
        Uczelnia.objects.get_for_request(request)
    )


class PBNExportQueuePermissionMixin(UserPassesTestMixin):
    """Mixin for permission checking - user must be staff or have GR_WPROWADZANIE_DANYCH group

    Zawęża też ``get_queryset`` do kolejki uczelni z domeny requestu."""

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()

    def get_queryset(self):
        return kolejka_dla_requestu(self.request)
