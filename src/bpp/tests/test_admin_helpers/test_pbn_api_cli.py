from unittest.mock import MagicMock

import pytest
from model_bakery import baker as mommy

from pbn_api.exceptions import (
    CharakterFormalnyNieobslugiwanyError,
    NeedsPBNAuthorisationException,
)

from bpp.admin.helpers.pbn_api.cli import TextNotificator, sprobuj_wyslac_do_pbn_celery
from bpp.const import RODZAJ_PBN_ARTYKUL
from bpp.models import Uczelnia


@pytest.mark.parametrize("level", ["warning", "success", "error"])
def test_TextNotificator(level):
    tn = TextNotificator()
    getattr(tn, level)(msg="foo")
    assert tn.as_text()


@pytest.mark.django_db
def test_sprobuj_wyslac_do_pbn_celery(wydawnictwo_ciagle, admin_user, mocker):
    cf = mommy.make("bpp.Charakter_Formalny", rodzaj_pbn=None)
    wydawnictwo_ciagle.charakter_formalny = cf
    wydawnictwo_ciagle.save()

    with pytest.raises(CharakterFormalnyNieobslugiwanyError):
        sprobuj_wyslac_do_pbn_celery(admin_user, wydawnictwo_ciagle)

    cf.rodzaj_pbn = RODZAJ_PBN_ARTYKUL
    cf.save()

    with pytest.raises(ValueError, match="brak obiektu Uczelnia"):
        sprobuj_wyslac_do_pbn_celery(admin_user, wydawnictwo_ciagle)

    uczelnia = mommy.make(Uczelnia, pbn_integracja=False)

    with pytest.raises(ValueError, match="nie skonfigurowana"):
        sprobuj_wyslac_do_pbn_celery(admin_user, wydawnictwo_ciagle)

    uczelnia.pbn_integracja = True
    uczelnia.pbn_aktualizuj_na_biezaco = True
    uczelnia.pbn_app_name = uczelnia.pbn_app_token = "fubar"
    uczelnia.save()

    with pytest.raises(NeedsPBNAuthorisationException):
        sprobuj_wyslac_do_pbn_celery(admin_user, wydawnictwo_ciagle)

    admin_user.pbn_token = "fubar"
    admin_user.save()

    wydawnictwo_ciagle.pbn_get_json = MagicMock()

    mocker.patch(
        "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn"
    ).return_value = 200
    sent_data, notificator = sprobuj_wyslac_do_pbn_celery(
        admin_user, wydawnictwo_ciagle
    )
    assert sent_data == 200
