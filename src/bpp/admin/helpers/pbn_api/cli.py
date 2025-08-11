from pbn_api.exceptions import (
    BrakZdefiniowanegoObiektuUczelniaWSystemieError,
    NeedsPBNAuthorisationException,
)

from bpp.admin.helpers.pbn_api.common import (
    sprawdz_czy_ustawiono_wysylke_tego_charakteru_formalnego,
    sprawdz_wysylke_do_pbn_w_parametrach_uczelni,
    sprobuj_wyslac_do_pbn,
)
from bpp.models import Uczelnia


class TextNotificator:
    def __init__(self, *args, **kw):
        self.output = []

    def info(self, msg, level="INFO"):
        self.output.append(f"{level} {msg}")

    def warning(self, msg):
        self.info(msg, level="WARNING")

    def error(self, msg):
        self.info(msg, level="ERROR")

    def success(self, msg):
        self.info(msg, level="SUCCESS")

    def as_text(self):
        return "\n".join(self.output)

    def as_list(self):
        return self.output


def sprobuj_wyslac_do_pbn_celery(user, obj, force_upload=False, pbn_client=None):
    sprawdz_czy_ustawiono_wysylke_tego_charakteru_formalnego(obj.charakter_formalny)

    try:
        uczelnia = sprawdz_wysylke_do_pbn_w_parametrach_uczelni(
            Uczelnia.objects.get_default()
        )
    except BrakZdefiniowanegoObiektuUczelniaWSystemieError:
        raise ValueError("W systemie brak obiektu Uczelnia.")

    if uczelnia is False:
        raise ValueError("Wysyłka do PBN nie skonfigurowana w obiekcie Uczelnia")

    if user.pbn_token is None:
        raise NeedsPBNAuthorisationException(
            None, None, "Wymagana wcześniejsza autoryzacja w PBN"
        )

    if pbn_client is None:
        pbn_client = uczelnia.pbn_client(user.pbn_token)

    notificator = TextNotificator()

    sent_data = sprobuj_wyslac_do_pbn(
        obj=obj,
        uczelnia=uczelnia,
        force_upload=force_upload,
        pbn_client=pbn_client,
        notificator=notificator,
        raise_exceptions=True,
    )

    return (sent_data, notificator.as_list())
