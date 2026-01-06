from unittest.mock import Mock

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse

pytestmark = pytest.mark.uruchom_tylko_bez_microsoft_auth


def test_Uczelnia_wosclient(uczelnia):
    with pytest.raises(ImproperlyConfigured):
        uczelnia.wosclient()

    uczelnia.clarivate_username = "foo"
    uczelnia.clarivate_password = "bar"
    res = uczelnia.wosclient()
    assert res is not None


def test_GetWoSAMRInformation_post_no_args(wd_app, uczelnia):
    res = wd_app.post(reverse("bpp:api_wos_amr", args=(uczelnia.slug,)))
    assert res.json["status"] == "error"


def test_GetWoSAMRInformation_post_good(wd_app, uczelnia, mocker):
    m = Mock()
    m.query_single = Mock(return_value={"timesCited": "-1"})
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    res = wd_app.post(
        reverse("bpp:api_wos_amr", args=(uczelnia.slug,)), params={"pmid": "31337"}
    )

    assert res.json["status"] == "ok"
    assert res.json["timesCited"] == "-1"


def test_GetWoSAMRInformation_post_error(wd_app, uczelnia, mocker):
    m = Mock()
    m.query_single = Mock(side_effect=Exception("lel"))
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    res = wd_app.post(
        reverse("bpp:api_wos_amr", args=(uczelnia.slug,)), params={"pmid": "31337"}
    )

    assert res.json["status"] == "error"
    # Generic error message - raw exception details are not exposed to users
    assert res.json["info"] == "Wewnętrzny błąd systemu"


def test_GetWoSAMRInformation_post_request_error(wd_app, uczelnia, mocker):
    """Test handling of network/connection errors."""
    import requests

    m = Mock()
    m.query_single = Mock(side_effect=requests.ConnectionError("Connection failed"))
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    res = wd_app.post(
        reverse("bpp:api_wos_amr", args=(uczelnia.slug,)), params={"pmid": "31337"}
    )

    assert res.json["status"] == "error"
    assert res.json["info"] == "Błąd komunikacji z Clarivate API"


def test_GetWoSAMRInformation_post_json_error(wd_app, uczelnia, mocker):
    """Test handling of JSON parsing errors."""
    import json

    m = Mock()
    m.query_single = Mock(side_effect=json.JSONDecodeError("msg", "doc", 0))
    mocker.patch("bpp.models.struktura.Uczelnia.wosclient", return_value=m)

    res = wd_app.post(
        reverse("bpp:api_wos_amr", args=(uczelnia.slug,)), params={"pmid": "31337"}
    )

    assert res.json["status"] == "error"
    assert res.json["info"] == "Błąd parsowania odpowiedzi z WOS"
