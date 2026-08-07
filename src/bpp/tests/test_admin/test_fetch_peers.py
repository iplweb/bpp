"""Kontrakt: adminy BPP pobierają dane w trybie ``FETCH_PEERS`` (Django 6.1).

``BaseBppAdminMixin.get_queryset`` włącza ``FETCH_PEERS``, żeby pierwsze
leniwe dotknięcie relacji (albo pola odroczonego) dociągało ją hurtem dla
całego rodzeństwa z tego samego pobrania. To zamienia N+1 na changelistach
admina na 2 zapytania — bez zgadywania z góry, które FK dotknie szablon.

Testy tutaj pilnują dwóch rzeczy, które łatwo zepsuć niechcący:

1. tryb jest w ogóle ustawiany (ktoś mógłby nadpisać ``get_queryset``
   w podklasie i zapomnieć o ``super()``),
2. tryb PRZEŻYWA łańcuch ``.filter()/.order_by()/[slice]`` — to jest cała
   przesłanka, dla której wystarcza jedno wywołanie w ``get_queryset``,
   a nie łatanie każdego miejsca osobno.
"""

import pytest
from django.contrib import admin as dj_admin
from django.db.models import FETCH_PEERS

from bpp.admin.autor import AutorAdmin
from bpp.admin.jednostka import JednostkaAdmin
from bpp.admin.wydawnictwo_ciagle import Wydawnictwo_CiagleAdmin
from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle


def _queryset_admina(klasa_admina, model, rf, admin_user):
    request = rf.get("/admin/")
    request.user = admin_user
    return klasa_admina(model, dj_admin.site).get_queryset(request)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "klasa_admina,model",
    [
        (AutorAdmin, Autor),
        (JednostkaAdmin, Jednostka),
        (Wydawnictwo_CiagleAdmin, Wydawnictwo_Ciagle),
    ],
)
def test_admin_pobiera_w_trybie_fetch_peers(klasa_admina, model, rf, admin_user):
    queryset = _queryset_admina(klasa_admina, model, rf, admin_user)
    assert queryset._fetch_mode is FETCH_PEERS, klasa_admina.__name__


@pytest.mark.django_db
def test_fetch_peers_przezywa_lancuch_querysetu(rf, admin_user):
    """Tryb przenosi się przez ``_clone()`` — filtr, sortowanie i slicing.

    ``ChangeList`` i dalsze mixiny dokładają do querysetu własne ``filter``,
    ``order_by`` i wycinek strony. Gdyby tryb ginął przy klonowaniu,
    ustawienie go w ``get_queryset`` nic by nie dawało.
    """
    queryset = _queryset_admina(AutorAdmin, Autor, rf, admin_user)

    assert queryset.filter(pokazuj=True)._fetch_mode is FETCH_PEERS
    assert queryset.order_by("nazwisko")._fetch_mode is FETCH_PEERS
    assert queryset.filter(pokazuj=True).order_by("nazwisko")[:10]._fetch_mode is (
        FETCH_PEERS
    )
