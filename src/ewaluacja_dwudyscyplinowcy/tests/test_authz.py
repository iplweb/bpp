import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH

URL_NAME = "ewaluacja_dwudyscyplinowcy:index"


@pytest.mark.django_db
def test_anonim_przekierowany_na_logowanie(client):
    assert client.get(reverse(URL_NAME)).status_code == 302


@pytest.mark.django_db
def test_zwykly_user_dostaje_403(client):
    user = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    client.force_login(user)
    assert client.get(reverse(URL_NAME)).status_code == 403


@pytest.mark.django_db
def test_user_powiazany_z_autorem_bez_grupy_dostaje_403(client):
    autor = baker.make("bpp.Autor")
    user = baker.make("bpp.BppUser", is_staff=False, is_superuser=False, autor=autor)
    client.force_login(user)
    assert client.get(reverse(URL_NAME)).status_code == 403


@pytest.mark.django_db
def test_redaktor_ma_dostep(client):
    user = baker.make("bpp.BppUser", is_staff=True, is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grupa)
    client.force_login(user)
    assert client.get(reverse(URL_NAME)).status_code == 200


@pytest.mark.django_db
def test_widok_liczy_wybrany_okres(admin_client, dyscyplina1, dyscyplina2, monkeypatch):
    """Lista bierze lata z okresu wybranego na pasku okresu, nie z literału 2022–2025."""
    from bpp.models import Autor_Dyscyplina
    from ewaluacja_common.models import OkresEwaluacji
    from ewaluacja_common.okres import KLUCZ_SESJI

    okres_2026 = OkresEwaluacji.objects.get(rok_od=2026)
    session = admin_client.session
    session[KLUCZ_SESJI] = okres_2026.pk
    session.save()

    autor = baker.make("bpp.Autor")
    Autor_Dyscyplina.objects.create(
        autor=autor,
        rok=2027,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    import ewaluacja_dwudyscyplinowcy.views as views

    widziane = {}
    oryginal = views.pobierz_autorow_z_dwiema_dyscyplinami

    def szpieg(lata=None):
        widziane["lata"] = list(lata)
        return oryginal(lata=lata)

    monkeypatch.setattr(views, "pobierz_autorow_z_dwiema_dyscyplinami", szpieg)
    resp = admin_client.get(reverse(URL_NAME))

    assert resp.status_code == 200
    assert widziane["lata"] == [2026, 2027, 2028, 2029, 2030]
    assert resp.context["lata"] == "2026–2030"
    assert resp.context["pokaz_wybor_okresu"] is True
