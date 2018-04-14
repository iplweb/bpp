import os

from django.core.files.base import ContentFile
from django.db import transaction

from import_dyscyplin.models import Import_Dyscyplin


def test_Import_Dyscyplin_post_delete_handler(test1_xlsx, normal_django_user, transactional_db):
    path = None
    with transaction.atomic():
        i = Import_Dyscyplin.objects.create(
            owner=normal_django_user,
        )

        i.plik.save("test1.xls", ContentFile(open(test1_xlsx, "rb").read()))
        path = i.plik.path
        i.delete()

    assert not os.path.exists(path)

