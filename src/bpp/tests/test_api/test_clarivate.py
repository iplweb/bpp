import pytest
from django.core.exceptions import ImproperlyConfigured
from django.urls import reverse
from mock import Mock


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
    assert res.json["info"].find("lel") >= 0
