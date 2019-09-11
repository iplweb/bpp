from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404

from bpp.models import OpcjaWyswietlaniaField, Uczelnia


class UczelniaSettingRequiredMixin(LoginRequiredMixin):
    """Mixin wymagający ustawienia obiektu uczelnia; do ukrywania stron
    w przypadku ustawienia "pokazuj_nigdy", do sprawdzania loginu dla
    "pokazuj_zalogowanym", do przepuszczania zawsze w przypadku "pokazuj_zawsze"

    """
    uczelnia_attr = None

    def dispatch(self, request, *args, **kwargs):

        res = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE

        # TODO: w przypadku wielu uczelni, zmień to
        uczelnia = Uczelnia.objects.first()

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

        return super(LoginRequiredMixin, self).dispatch(request, *args, **kwargs)
