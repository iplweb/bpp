import pytest
from multiseek.logic import StringQueryObject

from bpp.models import BppMultiseekVisibility
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin


class TestQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
    label = "foo"
    field_name = "bar"
    public = True


class TestQueryObjectDisabled(BppMultiseekVisibilityMixin, StringQueryObject):
    label = "foo"
    field_name = "bar"
    public = True

    def option_enabled(self):
        return False


@pytest.mark.django_db
def test_BppMultiseekVisibilityMixin_option_enabled_disabled():
    b = TestQueryObjectDisabled()
    assert not b.enabled(None)


@pytest.mark.django_db
def test_BppMultiseekVisibilityMixin_request_none():
    b = TestQueryObject()
    vis = b._get_or_create()

    assert b.enabled(None)

    vis.public = False
    vis.save()

    assert b.enabled(None) is False

    assert BppMultiseekVisibility.objects.count() == 1


def test_BppMultiseekVisibilityMixin_request_normal_user(rf, normal_django_user):
    b = TestQueryObject()

    vis = b._get_or_create()

    req = rf.get("/")
    req.user = normal_django_user

    vis.authenticated = False
    vis.save()
    assert not b.enabled(req)

    vis.authenticated = False
    vis.staff = True
    vis.save()
    assert not b.enabled(req)


def test_BppMultiseekVisibilityMixin_request_admin_user(rf, admin_user):
    b = TestQueryObject()

    vis = b._get_or_create()

    req = rf.get("/")
    req.user = admin_user

    vis.authenticated = False
    vis.staff = False
    vis.save()
    assert not b.enabled(req)

    vis.authenticated = True
    vis.staff = False
    vis.save()
    assert not b.enabled(req)

    vis.authenticated = False
    vis.staff = True
    vis.save()
    assert b.enabled(req)
