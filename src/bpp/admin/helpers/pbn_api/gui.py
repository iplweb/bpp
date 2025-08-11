from django.urls import reverse

from pbn_api.exceptions import (
    AlreadyEnqueuedError,
    BrakZdefiniowanegoObiektuUczelniaWSystemieError,
    CharakterFormalnyNieobslugiwanyError,
)
from pbn_api.models import PBN_Export_Queue
from pbn_api.tasks import task_sprobuj_wyslac_do_pbn

from django.contrib import messages

from bpp.admin.helpers import link_do_obiektu
from bpp.admin.helpers.pbn_api.common import (
    sprawdz_czy_ustawiono_wysylke_tego_charakteru_formalnego,
    sprawdz_wysylke_do_pbn_w_parametrach_uczelni,
    sprobuj_wyslac_do_pbn,
)
from bpp.const import PBN_MAX_ROK, PBN_MIN_ROK
from bpp.models.sloty.core import ISlot
from bpp.models.sloty.exceptions import CannotAdapt


def sprobuj_policzyc_sloty(request, obj):
    if obj.rok >= PBN_MIN_ROK and obj.rok <= PBN_MAX_ROK:
        try:
            ISlot(obj)
            messages.success(
                request,
                'Punkty dla dyscyplin dla "%s" będą mogły być obliczone.'
                % link_do_obiektu(obj),
            )
        except CannotAdapt as e:
            messages.error(
                request,
                'Nie można obliczyć punktów dla dyscyplin dla "%s": %s'
                % (link_do_obiektu(obj), e),
            )
    else:
        messages.warning(
            request,
            'Punkty dla dyscyplin dla "%s" nie będą liczone - rok poza zakresem (%i)'
            % (link_do_obiektu(obj), obj.rok),
        )


def sprawdz_wysylke_do_pbn_w_parametrach_uczelni_gui(request, obj):
    from bpp.models.uczelnia import Uczelnia

    uczelnia = Uczelnia.objects.get_for_request(request)
    try:
        res = sprawdz_wysylke_do_pbn_w_parametrach_uczelni(uczelnia)
    except BrakZdefiniowanegoObiektuUczelniaWSystemieError:
        messages.info(
            request,
            'Rekord "%s" nie zostanie wyeksportowany do PBN, ponieważ w systemie brakuje obiektu "Uczelnia", a'
            " co za tym idzie, jakchkolwiek ustawień" % link_do_obiektu(obj),
        )
        return

    return res


def sprawdz_czy_ustawiono_wysylke_tego_charakteru_formalnego_gui(request, obj):
    try:
        sprawdz_czy_ustawiono_wysylke_tego_charakteru_formalnego(obj.charakter_formalny)
    except CharakterFormalnyNieobslugiwanyError:
        messages.info(
            request,
            'Rekord "%s" nie będzie eksportowany do PBN zgodnie z ustawieniem dla charakteru formalnego.'
            % link_do_obiektu(obj),
        )
        return False
    return True


def sprobuj_utworzyc_zlecenie_eksportu_do_PBN_gui(request, obj):
    if not sprawdz_czy_ustawiono_wysylke_tego_charakteru_formalnego_gui(request, obj):
        return

    try:
        res = sprawdz_wysylke_do_pbn_w_parametrach_uczelni_gui(request, obj)
    except BrakZdefiniowanegoObiektuUczelniaWSystemieError:
        messages.error("Brak zdefiniowanego w systemie obiektu Uczelnia.")

    if res is False:
        messages.error("Wysyłka do PBN nie skonfigurowana w obiektu Uczelnia.")

    try:
        ret = PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(request.user, obj)
    except AlreadyEnqueuedError:
        messages.warning(
            request, f"Rekord {obj} jest już w kolejce do eksportu do PBN."
        )
        return

    link_do_kolejki = reverse("admin:pbn_api_pbn_export_queue_change", args=(ret.pk,))

    messages.info(
        request,
        f"Utworzono zlecenie wysyłki rekordu {obj} w tle do PBN. <a href={link_do_kolejki}>"
        f"Kliknij tutaj, aby śledzić stan.</a>",
    )

    task_sprobuj_wyslac_do_pbn.delay_on_commit(ret.pk)


class MessagesNotificator:
    def __init__(self, request):
        self.request = request

    def info(self, msg):
        messages.info(self.request, msg)

    def warning(self, msg):
        messages.warning(self.request, msg)

    def error(self, msg):
        messages.error(self.request, msg)

    def success(self, msg):
        messages.success(self.request, msg)


def sprobuj_wyslac_do_pbn_gui(request, obj, force_upload=False, pbn_client=None):
    if not sprawdz_czy_ustawiono_wysylke_tego_charakteru_formalnego_gui(request, obj):
        return

    uczelnia = sprawdz_wysylke_do_pbn_w_parametrach_uczelni_gui(request, obj)
    if uczelnia is None:
        return

    if uczelnia is False:
        messages.error(request, "Wysyłka do PBN nie skonfigurowana w obiektu Uczelnia.")
        return

    if pbn_client is None:
        pbn_client = uczelnia.pbn_client(request.user.pbn_token)

    sprobuj_wyslac_do_pbn(
        obj=obj,
        uczelnia=uczelnia,
        force_upload=force_upload,
        pbn_client=pbn_client,
        notificator=MessagesNotificator(request),
    )
