from django.contrib.auth.mixins import UserPassesTestMixin

from bpp.const import GR_WPROWADZANIE_DANYCH


class ImporterPermissionMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return (
            user.is_superuser
            or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
        )
