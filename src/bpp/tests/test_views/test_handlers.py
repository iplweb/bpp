# -*- encoding: utf-8 -*-

import pytest


def test_handler403_permission_denied(client):
    try:
        client.get("/admin/bpp/")
    except TypeError:
        assert False


@pytest.mark.django_db
@pytest.mark.urls("bpp.tests.test_views.urls_test_handlers")
def test_handler500(client):
    with pytest.raises(ZeroDivisionError):
        try:
            client.get("/test_500")
        except TypeError as e:
            assert False


@pytest.mark.django_db
def test_handler404_not_found(client):
    try:
        client.get("/bpp/this_page_does_not_exist_for_sure")
    except TypeError:
        assert False
