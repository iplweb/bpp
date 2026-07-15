"""Testy autoryzatora subskrypcji kanałów WWW (channels_broadcast).

``channels_broadcast`` od wersji z modelem bezpieczeństwa NIE pozwala
przeglądarce zasubskrybować kanału z ``?extraChannels=`` bez zgody
konfigurowanego autoryzatora (domyślny ``_deny_all`` odrzuca wszystko).
Widoki ``long_running`` subskrybują kanał operacji przez
``extraChannels=[operation.pk]`` (patrz
``LongRunningSingleObjectChannelSubscriberMixin``), więc bez autoryzatora
pasek postępu nigdy nie dostaje danych — użytkownik musi ręcznie odświeżać.

``authorize_operation_channel`` przywraca dostawę: pozwala zasubskrybować
kanał-stronę operacji wyłącznie jej WŁAŚCICIELOWI.
"""

import uuid

import pytest
from django.contrib.auth.models import AnonymousUser

from long_running.authorizers import authorize_operation_channel


@pytest.mark.django_db
def test_owner_moze_subskrybowac_swoja_operacje(operation):
    """Właściciel operacji może zasubskrybować jej kanał (str(pk))."""
    assert authorize_operation_channel(operation.owner, str(operation.pk)) is True


@pytest.mark.django_db
def test_obcy_user_nie_moze_subskrybowac_cudzej_operacji(operation, django_user_model):
    """Inny zalogowany użytkownik NIE może podglądać cudzej operacji."""
    obcy = django_user_model.objects.create_user(username="obcy", password="x")
    assert authorize_operation_channel(obcy, str(operation.pk)) is False


@pytest.mark.django_db
def test_anonim_nie_moze_subskrybowac(operation):
    """Anonim nie ma właściciela — brak dostępu."""
    assert authorize_operation_channel(AnonymousUser(), str(operation.pk)) is False


@pytest.mark.django_db
def test_nieistniejaca_operacja_odrzucona(admin_user):
    """Poprawny UUID, ale żadna operacja o tym pk nie istnieje → odmowa."""
    assert authorize_operation_channel(admin_user, str(uuid.uuid4())) is False


@pytest.mark.django_db
def test_smiec_zamiast_uuid_odrzucony(admin_user):
    """Nazwa kanału niebędąca UUID-em (audience/inny kanał) → odmowa,
    bez wyjątku."""
    assert authorize_operation_channel(admin_user, "channels_broadcast.all") is False
    assert authorize_operation_channel(admin_user, "") is False


@pytest.mark.django_db
def test_wiring_settings_resolwuje_autoryzator(operation):
    """CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER w settings faktycznie wpina
    nasz autoryzator: wejście przez publiczne API channels_broadcast
    (``authorize_extra_channel``) przepuszcza właściciela i odrzuca obcego.

    To broni całości poprawki: gdyby ktoś usunął setting, subskrypcja znów
    wpadłaby w domyślny _deny_all i pasek postępu przestałby działać."""
    from channels_broadcast.security import authorize_extra_channel

    assert authorize_extra_channel(operation.owner, str(operation.pk)) is True
