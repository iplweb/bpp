import pytest
from model_mommy import mommy

from bpp.models import Wydawnictwo_Zwarte
from notifications.models import Notification


@pytest.mark.django_db
def test_Notifications_objects():
    o = mommy.make(Wydawnictwo_Zwarte)
    Notification.objects.send_redirect(o, "http://onet.pl")
