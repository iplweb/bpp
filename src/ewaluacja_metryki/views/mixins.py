from django.contrib.auth.mixins import (
    LoginRequiredMixin,
    UserPassesTestMixin,
)

from bpp.permissions import moze_wprowadzac_dane


def ma_pelne_uprawnienia_ewaluacji(user):
    """Sprawdza czy użytkownik ma pełne uprawnienia do ewaluacji
    (superuser lub grupa wprowadzania danych).

    Deleguje do centralnej bramki ``bpp.permissions.moze_wprowadzac_dane``
    — jedno źródło prawdy dla „pełnych uprawnień redaktorskich"."""
    return moze_wprowadzac_dane(user)


def ma_uprawnienia_ewaluacji(user):
    """Sprawdza czy użytkownik ma uprawnienia do ewaluacji
    (pełne uprawnienia lub powiązany autor)."""
    if ma_pelne_uprawnienia_ewaluacji(user):
        return True
    return getattr(user, "autor_id", None) is not None


class EwaluacjaRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Mixin wymagający uprawnień do ewaluacji"""

    def test_func(self):
        user = self.request.user
        user.sprobuj_dopasowac_autora()
        return ma_uprawnienia_ewaluacji(user)
