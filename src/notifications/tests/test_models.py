import pytest
from model_bakery import baker

from notifications.models import Notification

from bpp.models import Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_Notifications_objects():
    o = baker.make(Wydawnictwo_Zwarte)
    Notification.objects.send_redirect(o, "http://onet.pl")
