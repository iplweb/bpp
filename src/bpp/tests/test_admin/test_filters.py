import pytest
from model_bakery import baker

from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType

from bpp.admin.filters import OstatnioZmienionePrzezFilter, UtworzonePrzezFilter
from bpp.models import Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_OstatnioZmienionePrzezFilter(wydawnictwo_zwarte, admin_user):

    LogEntry.objects.create(
        action_flag=CHANGE,
        object_id=wydawnictwo_zwarte.pk,
        content_type_id=ContentType.objects.get_for_model(wydawnictwo_zwarte).pk,
        user=admin_user,
    )

    f = OstatnioZmienionePrzezFilter(None, {}, Wydawnictwo_Zwarte, None)

    f.value = lambda *args, **kw: admin_user.pk

    assert wydawnictwo_zwarte in f.queryset(None, Wydawnictwo_Zwarte.objects.all())

    assert admin_user.pk in [x[0] for x in f.lookups(None, None)]


@pytest.mark.django_db
def test_UtworzonePrzeZFilter(wydawnictwo_zwarte, admin_user, normal_django_user):
    drugie_wydawnictwo_zwarte = baker.make(Wydawnictwo_Zwarte)
    content_type_id = ContentType.objects.get_for_model(wydawnictwo_zwarte).pk

    LogEntry.objects.create(
        action_flag=ADDITION,
        object_id=wydawnictwo_zwarte.pk,
        user=admin_user,
        content_type_id=content_type_id,
    )

    LogEntry.objects.create(
        action_flag=ADDITION,
        object_id=drugie_wydawnictwo_zwarte.pk,
        user=normal_django_user,
        content_type_id=content_type_id,
    )

    f = UtworzonePrzezFilter(None, {}, Wydawnictwo_Zwarte, None)

    f.value = lambda *args, **kw: admin_user.pk

    assert wydawnictwo_zwarte in f.queryset(None, Wydawnictwo_Zwarte.objects.all())
    assert drugie_wydawnictwo_zwarte not in f.queryset(
        None, Wydawnictwo_Zwarte.objects.all()
    )

    user_ids = [x[0] for x in f.lookups(None, None)]
    assert admin_user.pk in user_ids
