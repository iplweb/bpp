import pytest
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max

import notifications.core as notifications_core
from import_dyscyplin.models import Import_Dyscyplin
from import_dyscyplin.tasks import przeanalizuj_import_dyscyplin
from notifications.models import Notification

from bpp.models import Autor_Dyscyplina


def test_kasowanie_calosci(
    test4_kasowanie_xlsx,
    normal_django_user,
    mocker,
    transactional_db,
    autor_jan_kowalski,
    rok,
    dyscyplina1,
):
    web_page_uid = "foobar_uid"

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=rok, dyscyplina_naukowa=dyscyplina1
    )

    with transaction.atomic():
        i = Import_Dyscyplin.objects.create(
            owner=normal_django_user, web_page_uid=web_page_uid, rok=rok
        )
        i.plik.save("test1.xlsx", ContentFile(open(test4_kasowanie_xlsx, "rb").read()))
        i.plik.path

    mocker.patch("notifications.core._send")
    przeanalizuj_import_dyscyplin.delay(i.pk)

    i = Import_Dyscyplin.objects.first()
    i.stworz_kolumny()
    i.zatwierdz_kolumny()
    i.przeanalizuj()
    i.integruj_dyscypliny()
    i.integruj_wiersze()

    with pytest.raises(Autor_Dyscyplina.DoesNotExist):
        Autor_Dyscyplina.objects.get(autor=autor_jan_kowalski, rok=rok)


def test_kasowanie_subdyscypliny(
    test5_kasowanie_subdyscypliny,
    normal_django_user,
    mocker,
    transactional_db,
    autor_jan_kowalski,
    rok,
    dyscyplina1,
    dyscyplina2,
):
    web_page_uid = "foobar_uid"

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    with transaction.atomic():
        i = Import_Dyscyplin.objects.create(
            owner=normal_django_user, web_page_uid=web_page_uid, rok=rok
        )
        i.plik.save(
            "test1.xlsx", ContentFile(open(test5_kasowanie_subdyscypliny, "rb").read())
        )
        i.plik.path

    mocker.patch("notifications.core._send")
    przeanalizuj_import_dyscyplin.delay(i.pk)

    i = Import_Dyscyplin.objects.first()
    i.stworz_kolumny()
    i.zatwierdz_kolumny()
    i.przeanalizuj()
    i.integruj_dyscypliny()
    i.integruj_wiersze()

    ad = Autor_Dyscyplina.objects.get(autor=autor_jan_kowalski, rok=rok)
    assert ad.subdyscyplina_naukowa is None


def test_przeanalizuj_import_dyscyplin(
    test1_xlsx, normal_django_user, mocker, transactional_db
):

    web_page_uid = "foobar_uid"

    with transaction.atomic():
        i = Import_Dyscyplin.objects.create(
            owner=normal_django_user, web_page_uid=web_page_uid
        )
        i.plik.save("test1.xls", ContentFile(open(test1_xlsx, "rb").read()))
        i.plik.path

    mocker.patch("notifications.core._send")

    przeanalizuj_import_dyscyplin.delay(i.pk)

    link = f"/import_dyscyplin/detail/{i.pk}/?notification=1"

    notifications_core._send.assert_called_once_with(
        f"import_dyscyplin.import_dyscyplin-{i.pk}",
        {"id": Notification.objects.all().aggregate(x=Max("pk"))["x"], "url": link},
    )
