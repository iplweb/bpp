from braces.views._access import AccessMixin
from django.http import Http404

from bpp.models import OpcjaWyswietlaniaField, Uczelnia


class UczelniaSettingRequiredMixin(AccessMixin):
    """Mixin wymagający ustawienia obiektu uczelnia; do ukrywania stron
    w przypadku ustawienia "pokazuj_nigdy", do sprawdzania loginu dla
    "pokazuj_zalogowanym", do przepuszczania zawsze w przypadku "pokazuj_zawsze"

    Opcjonalnie od zalogowanych mozna wymagac konkretnej grupy, przykladowo
    GR_RAPORTY_WYSWIETLANIE
    """

    uczelnia_attr = None
    group_required = None

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
                return self.handle_no_permission(request)

            if getattr(self, "group_required") and self.group_required:
                # Jeżeli wymagana jest jakas grupa to wymagaj jej od zalogowanych
                if (
                    not request.user.is_superuser
                    and not request.user.groups.filter(
                        name=self.group_required
                    ).exists()
                ):
                    return self.handle_no_permission(request)

        elif res == OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE:
            if not request.user.is_staff:
                return self.handle_no_permission(request)

        else:
            raise NotImplementedError

        return super().dispatch(request, *args, **kwargs)
