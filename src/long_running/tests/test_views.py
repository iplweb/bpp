from django.db import transaction

from bpp.system import User
from long_running.views import LongRunningTaskCallerMixin, RestrictToOwnerMixin


def test_LongRunningTaskCallerMixin_task_on_commit(
    mocker, admin_user, transactional_db
):
    class Foo(LongRunningTaskCallerMixin):
        model = User
        task = mocker.MagicMock()

    with transaction.atomic():
        Foo.task_on_commit(Foo, admin_user.pk)
    Foo.task.delay.assert_called_with("bpp", "bppuser", admin_user.pk)


def test_RestrictToOwnerMixin(mocker):
    class Foo(RestrictToOwnerMixin):
        model = mocker.MagicMock()
        request = mocker.MagicMock()

    Foo.get_queryset(Foo)
    assert Foo.model.objects.filter.called_with(owner=Foo.request)
