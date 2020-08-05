from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

import notifications.core as notifications_core
from conftest import NORMAL_DJANGO_USER_LOGIN
from import_dyscyplin.models import Import_Dyscyplin
from import_dyscyplin.tasks import przeanalizuj_import_dyscyplin
from notifications.models import Notification


def test_przeanalizuj_import_dyscyplin(
    test1_xlsx, normal_django_user, mocker, transactional_db
):

    web_page_uid = "foobar_uid"

    with transaction.atomic():
        i = Import_Dyscyplin.objects.create(
            owner=normal_django_user, web_page_uid=web_page_uid
        )
        i.plik.save("test1.xls", ContentFile(open(test1_xlsx, "rb").read()))
        path = i.plik.path

    mocker.patch("notifications.core._send")

    przeanalizuj_import_dyscyplin.delay(i.pk)

    link = f"/import_dyscyplin/detail/{i.pk}/?notification=1"

    notifications_core._send.assert_called_once_with(
        f"import_dyscyplin.import_dyscyplin-{i.pk}",
        {"id": Notification.objects.all().aggregate(x=Max("pk"))["x"], "url": link},
    )
