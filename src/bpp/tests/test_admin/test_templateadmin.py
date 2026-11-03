import pytest
from dbtemplates.models import Template
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.szablondlaopisubibliograficznego import SzablonDlaOpisuBibliograficznego

PREVIEW_URL = "/admin/dbtemplates/template/preview/"


@pytest.mark.django_db
def test_BppTemplateAdmin_templatka_zmienia_rekordy(
    admin_app, wydawnictwo_zwarte, denorms, wydawnictwo_ciagle
):
    WERSJA_1 = "werjsa 1"
    WERSJA_2 = "wersja 2"

    t, _ign = Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": WERSJA_1},
    )
    SzablonDlaOpisuBibliograficznego.objects.create(
        model=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        nazwa_szablonu=t.name,
    )
    denorms.rebuild_instances_of(Wydawnictwo_Ciagle)
    denorms.flush()

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.opis_bibliograficzny_cache == WERSJA_1
    #
    # Koniec inicjalizacji -- właściwy test poniżej
    #

    url = reverse("admin:dbtemplates_template_change", args=(t.pk,))
    res = admin_app.get(url)
    # Rename wiersza dbtemplate nie jest już testowany: po #329 mapowanie idzie
    # po nazwie (nazwa_szablonu), nie po tożsamości FK — rename gubiłby powiązanie
    # z definicji. Testujemy realny kontrakt: edycja TREŚCI -> przebudowa rekordów.
    res.forms["template_form"]["content"] = WERSJA_2
    res = res.forms["template_form"].submit().maybe_follow()

    denorms.flush()

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.opis_bibliograficzny_cache == WERSJA_2


@pytest.mark.django_db
def test_BppTemplateAdmin_zmiana_szablonu_zmienia_rekordy(
    admin_app, denorms, wydawnictwo_ciagle
):
    WERSJA_1 = "werjsa 1"
    WERSJA_2 = "wersja 2"

    t1, _ign = Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": WERSJA_1},
    )
    t2, _ign = Template.objects.update_or_create(
        name="opis_bibliograficzny_2.html", defaults={"content": WERSJA_2}
    )

    szablon = SzablonDlaOpisuBibliograficznego.objects.create(
        model=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
        nazwa_szablonu=t1.name,
    )
    denorms.rebuildall()

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.opis_bibliograficzny_cache == WERSJA_1

    #
    # Koniec inicjalizacji -- właściwy test poniżej
    #

    url = reverse(
        "admin:bpp_szablondlaopisubibliograficznego_change", args=(szablon.pk,)
    )
    res = admin_app.get(url)

    form = res.forms["szablondlaopisubibliograficznego_form"]
    form["nazwa_szablonu"].value = t2.name
    res = form.submit().maybe_follow()

    denorms.flush()

    wydawnictwo_ciagle.refresh_from_db()
    assert wydawnictwo_ciagle.opis_bibliograficzny_cache == WERSJA_2


@pytest.fixture
def typowy_szablon_opisu():
    t, _ign = Template.objects.update_or_create(
        name="opis_bibliograficzny.html",
        defaults={"content": "123"},
    )
    SzablonDlaOpisuBibliograficznego.objects.update_or_create(
        model=None,
        nazwa_szablonu=t.name,
    )
    return t


@pytest.mark.django_db
def test_dbtemplates_TemplateAdmin_preview_good(
    typowy_szablon_opisu, admin_client, wydawnictwo_ciagle
):

    TEST_STR = "456"
    res = admin_client.post(PREVIEW_URL, {"template": TEST_STR}, follow=True)
    assert TEST_STR.encode() in res.content


@pytest.mark.django_db
def test_dbtemplates_TemplateAdmin_preview_bad(typowy_szablon_opisu, admin_client):

    res = admin_client.post(PREVIEW_URL, {"template": "{% if foobar %}"})
    assert "Wystąpił błąd" in res.rendered_content


@pytest.mark.django_db
def test_dbtemplates_TemplateAdmin_preview_wymaga_uprawnienia(
    typowy_szablon_opisu, client, django_user_model, wydawnictwo_ciagle
):
    user = baker.make(django_user_model, is_staff=True, is_active=True)
    client.force_login(user)

    res = client.post(PREVIEW_URL, {"template": "456"})
    assert res.status_code == 403

    res = client.get(PREVIEW_URL)
    assert res.status_code == 403


@pytest.mark.django_db
def test_dbtemplates_TemplateAdmin_preview_z_uprawnieniem(
    typowy_szablon_opisu, client, django_user_model, wydawnictwo_ciagle
):
    user = baker.make(django_user_model, is_staff=True, is_active=True)
    user.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="dbtemplates", codename="change_template"
        )
    )
    client.force_login(user)

    res = client.post(
        PREVIEW_URL, {"template": "456<script>alert(1)</script><i>ok</i>"}
    )
    assert res.status_code == 200
    content = res.content.decode()
    assert "456" in content
    assert "<i>ok</i>" in content
    assert "<script>alert(1)</script>" not in content


@pytest.mark.django_db
def test_dbtemplates_TemplateAdmin_preview_get_nie_renderuje(
    typowy_szablon_opisu, admin_client, wydawnictwo_ciagle
):
    res = admin_client.get(PREVIEW_URL, {"template": "ZNACZNIK{{ 1|add:41 }}"})
    assert res.status_code == 200
    assert b"ZNACZNIK42" not in res.content
    assert "Podgląd uruchamia się" in res.content.decode()


@pytest.mark.django_db
def test_dbtemplates_TemplateAdmin_preview_wymaga_csrf(
    typowy_szablon_opisu, admin_user, wydawnictwo_ciagle
):
    from django.test import Client

    client = Client(enforce_csrf_checks=True)
    client.force_login(admin_user)
    res = client.post(PREVIEW_URL, {"template": "456"})
    assert res.status_code == 403


@pytest.mark.django_db
def test_dbtemplates_TemplateAdmin_preview_sanityzuje_wynik(
    typowy_szablon_opisu, admin_client, wydawnictwo_ciagle
):
    res = admin_client.post(
        PREVIEW_URL,
        {"template": "<i>ok</i><script>alert(1)</script><b onclick=x()>b</b>"},
    )
    assert res.status_code == 200
    content = res.content.decode()
    assert "<i>ok</i>" in content
    assert "<script>alert(1)</script>" not in content
    assert "onclick" not in content


@pytest.mark.django_db
def test_szablon_admin_changelist_dziala(admin_client):
    from bpp.models.szablondlaopisubibliograficznego import (
        SzablonDlaOpisuBibliograficznego,
    )

    SzablonDlaOpisuBibliograficznego.objects.get_or_create(
        model=None, defaults={"nazwa_szablonu": "opis_bibliograficzny.html"}
    )
    resp = admin_client.get("/admin/bpp/szablondlaopisubibliograficznego/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_dbtemplates_change_form_podglad_wysyla_post(
    typowy_szablon_opisu, admin_client
):
    url = reverse("admin:dbtemplates_template_change", args=(typowy_szablon_opisu.pk,))
    content = admin_client.get(url).content.decode()
    assert 'data-action="open-preview-window"' in content
    assert "form.method = 'post'" in content
    assert "csrfmiddlewaretoken" in content
