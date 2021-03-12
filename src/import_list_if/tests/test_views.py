from django.urls import reverse


def test_ListaImportowView_link(admin_app):
    page = admin_app.get(reverse("import_list_if:index"))
    page = page.click("pobierz plik wzorcowy")
    assert page.status_code == 200


def test_NowyImportView_link(admin_app):
    page = admin_app.get(reverse("import_list_if:new"))
    page = page.click("pobierz plik wzorcowy")
    assert page.status_code == 200
