from django.contrib.auth.mixins import AccessMixin
from django.http import Http404

from bpp.models import OpcjaWyswietlaniaField, Uczelnia


class UczelniaSettingRequiredMixin(AccessMixin):
    """Mixin wymagający ustawienia obiektu uczelnia; do ukrywania stron
    w przypadku ustawienia "pokazuj_nigdy", do sprawdzania loginu dla
    "pokazuj_zalogowanym", do przepuszczania zawsze w przypadku "pokazuj_zawsze"
    """

    uczelnia_attr = None

    def dispatch(self, request, *args, **kwargs):

        res = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE

        uczelnia = Uczelnia.objects.get_for_request(request)

        if uczelnia:
            res = getattr(uczelnia, self.uczelnia_attr)

        if res == OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE:
            pass

        elif res == OpcjaWyswietlaniaField.POKAZUJ_NIGDY:
            raise Http404

        elif res == OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM:
            if not request.user.is_authenticated:
                return self.handle_no_permission()

        else:
            raise NotImplementedError

        return super().dispatch(request, *args, **kwargs)
