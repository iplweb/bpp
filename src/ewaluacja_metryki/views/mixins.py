from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from bpp.const import GR_WPROWADZANIE_DANYCH


def ma_uprawnienia_ewaluacji(user):
    """Sprawdza czy użytkownik ma uprawnienia do ewaluacji"""
    return user.is_superuser or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()


class EwaluacjaRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin wymagający uprawnień do ewaluacji"""

    def test_func(self):
        return ma_uprawnienia_ewaluacji(self.request.user)
