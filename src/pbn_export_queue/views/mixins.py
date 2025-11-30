"""Mixin classes for PBN export queue views."""

from django.contrib.auth.mixins import UserPassesTestMixin

from bpp.const import GR_WPROWADZANIE_DANYCH


class PBNExportQueuePermissionMixin(UserPassesTestMixin):
    """Mixin for permission checking - user must be staff or have GR_WPROWADZANIE_DANYCH group"""

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
