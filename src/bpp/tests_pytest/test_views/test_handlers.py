# -*- encoding: utf-8 -*-

<<<<<<< HEAD
import pytest


def test_handler403_permission_denied(client):
    try:
        client.get("/admin/bpp/")
    except TypeError:
        assert False


def test_handler500(client):
    with pytest.raises(ZeroDivisionError):
        try:
            client.get("/test_500")
        except TypeError:
            assert False


@pytest.mark.django_db
def test_handler404_not_found(client):
    try:
        client.get("/bpp/this_page_does_not_exist_for_sure")
    except TypeError:
        assert False
=======
>>>>>>> 1fcd40ba022ab2e981d82f9f8122adea0be6ebf3
