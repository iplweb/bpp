import pytest
from model_bakery import baker

from long_running import const
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    LongRunningSingleObjectChannelSubscriberMixin,
    LongRunningTaskCallerMixin,
    RestartLongRunningOperationView,
    RestrictToOwnerMixin,
)
from test_bpp.models import TestOperation

from bpp.system import User


def test_LongRunningTaskCallerMixin_task_on_commit(
    mocker,
    admin_user,
):
    class Foo(LongRunningTaskCallerMixin):
        model = User
        task = mocker.MagicMock()

    toc = mocker.patch("long_running.views.transaction")
    Foo.task_on_commit(Foo, admin_user.pk)
    toc.on_commit.assert_called_once()


def test_RestrictToOwnerMixin(mocker):
    class Foo(RestrictToOwnerMixin):
        model = mocker.MagicMock()
        request = mocker.MagicMock()

    Foo.get_queryset(Foo)
    assert Foo.model.objects.filter.called_with(owner=Foo.request)


def test_LongRunningOperationsView_get_queryset(rf, admin_user):
    class TestLongRunningOperationsView(LongRunningOperationsView):
        model = TestOperation

        class request:
            user = admin_user

    v = TestLongRunningOperationsView()

    baker.make(TestOperation, owner=admin_user)
    rf.user = admin_user
    qset = v.get_queryset()
    assert qset.count() == 1


def test_LongRunningSingleObjectChannelSubscriberMixin(rf, admin_user):
    class Bar:
        def get_context_data(self, *args, **kw):
            return kw

    class Foo(LongRunningSingleObjectChannelSubscriberMixin, Bar):
        class object:
            pk = 5

    v = Foo().get_context_data()
    assert v["extraChannels"] == [5]


def test_LongRunningRouterView_get_not_started():
    class Foo(LongRunningRouterView):
        def get_object(self):
            class ret:
                def get_state(self):
                    return const.PROCESSING_NOT_STARTED

            return ret()

        request = 123

        def get_context_data(self):
            return {}

    assert Foo().get() is not None


def test_LongRunningRouterView_get_started():
    class Foo(LongRunningRouterView):
        def get_object(self):
            class ret:
                def get_state(self):
                    return const.PROCESSING_STARTED

                def get_url(self, arg):
                    return "foo"

                pk = 100

            return ret()

    assert Foo().get().status_code == 302


def test_LongRunningResultsView_parent_obejct(operation):
    class Foo(LongRunningResultsView):
        model = TestOperation
        kwargs = dict(pk=operation.pk)

        class request:
            user = operation.owner

    assert Foo().parent_object == operation


@pytest.mark.django_db
def test_LongRunningResultsView_parent_object_get_details_set(
    wydawnictwo_ciagle, mocker
):
    class Foo(LongRunningResultsView):
        parent_object = wydawnictwo_ciagle

    wydawnictwo_ciagle.get_details_set = mocker.MagicMock()

    Foo().get_queryset()

    wydawnictwo_ciagle.get_details_set.assert_called_once()


@pytest.mark.django_db
def test_CreateLongRunningOperationView(wydawnictwo_ciagle, mocker):
    class Foo(CreateLongRunningOperationView):
        parent_object = wydawnictwo_ciagle

        def get_success_url(self):
            return "120"

        def task_on_commit(self, pk):
            return

        class request:
            user = 123

    class form:
        class instance:
            pk = 5
            owner = None

        def save():
            return wydawnictwo_ciagle

    assert Foo().form_valid(form).status_code == 302
    assert form.instance.owner == 123


def test_RestartLongRunningOperationView_get(operation, mocker):
    obj = mocker.MagicMock()

    class Foo(RestartLongRunningOperationView):
        def get_object(self):
            return obj

        task_on_commit = mocker.MagicMock()

    foo = Foo()
    assert foo.get().status_code == 302
    obj.mark_reset.assert_called_once()
    foo.task_on_commit.assert_called_once()
