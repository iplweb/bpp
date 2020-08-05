# -*- encoding: utf-8 -*-


try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from eksport_pbn.forms import zakres_lat


def normalize_quotes(content):
    return content.decode("utf-8").replace("&#x27;", "'")


def test_submit_report_form(admin_app, live_server):
    page = admin_app.get(reverse("eksport_pbn:zamow"))
    res = page.form.submit().maybe_follow()
    assert res.status_code == 200


def test_submit_report_form_validation_data_od_do(admin_app, wydzial, asgi_live_server):
    page = admin_app.get(reverse("eksport_pbn:zamow"))
    page.form["od_daty"] = "2010-01-01"
    page.form["do_daty"] = "2009-01-01"
    res = page.form.submit()
    assert "Wartość w polu 'Od daty'" in normalize_quotes(res.content)


def test_submit_report_form_validation_rok_od_do(admin_app, wydzial, asgi_live_server):
    page = admin_app.get(reverse("eksport_pbn:zamow"))
    page.form["od_roku"] = "2015"
    page.form["do_roku"] = "2014"
    res = page.form.submit()
    assert "Wartość w polu 'Od roku'" in normalize_quotes(res.content)


def test_submit_report_form_validation_artykuly_ksiazki(
    admin_app, wydzial, asgi_live_server
):
    page = admin_app.get(reverse("eksport_pbn:zamow"))
    page.form["artykuly"] = False
    page.form["ksiazki"] = False
    page.form["rozdzialy"] = False
    res = page.form.submit()
    assert "Wybierz przynajmniej jedną" in res.content.decode("utf-8")


def test_zakres_lat():
    assert len(list(zakres_lat())) > 0
