"""Item 6: ekran audytu (LogZmianView) — per-wiersz log zmian po integracji
(utworzenia, zmiany autora/AJ, przepięcia) + wykonane odpięcia."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import (
    ImportPracownikow,
    ImportPracownikowOdpiecie,
    ImportPracownikowRow,
)


def _url(imp):
    return reverse("import_pracownikow:audyt", kwargs={"pk": imp.pk})


@pytest.mark.django_db
def test_audyt_pokazuje_zmiany_przepiecia_i_odpiecia(admin_client, admin_user):
    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
    )
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    jed = baker.make(Jednostka, nazwa="Katedra", skrot="Kat")
    baker.make(
        ImportPracownikowRow,
        parent=imp,
        autor=autor,
        jednostka=jed,
        zmiany_potrzebne=False,
        log_zmian={
            "autor": ["tytuł naukowy -> dr"],
            "autor_jednostka": [],
            "przepiecie": {
                "prace_ciagle": 3,
                "prace_zwarte": 1,
                "z": "Stara",
                "do": "Nowa",
            },
        },
    )
    # wiersz bez zmian — NIE powinien się pojawić (log_zmian=None)
    baker.make(
        ImportPracownikowRow,
        parent=imp,
        autor=baker.make(Autor, nazwisko="Pominmnie", imiona="Bez Zmian"),
        zmiany_potrzebne=False,
        log_zmian=None,
    )
    # wykonane odpięcie
    aj = baker.make(
        Autor_Jednostka,
        autor__nazwisko="Odpiety",
        autor__imiona="Ktos",
        jednostka__skrot="OJ",
    )
    ImportPracownikowOdpiecie.objects.create(
        parent=imp, autor_jednostka=aj, wykonane=True
    )

    resp = admin_client.get(_url(imp))
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    # zmiany autora + przepięcie (bez surowego „->", które Django escapuje na
    # „-&gt;") — sprawdzamy prefiks i przepięcie
    assert "Zmiany obiektu Autor" in tresc
    assert "tytuł naukowy" in tresc
    assert "Przepięto prace: 3 ciągłych, 1 zwartych" in tresc
    # sekcja odpięć
    assert "Odpiety" in tresc
    # wiersz bez zmian nie jest listowany
    assert "Pominmnie" not in tresc


@pytest.mark.django_db
def test_audyt_superuser_widzi_cudzy_import(admin_client, django_user_model):
    """Superuser (admin_client) ma dostęp do audytu cudzego importu."""
    obcy = django_user_model.objects.create_user("obcy_a", "o@o.pl", "x")
    imp = baker.make(
        ImportPracownikow, owner=obcy, stan=ImportPracownikow.STAN_ZINTEGROWANY
    )
    resp = admin_client.get(_url(imp))
    assert resp.status_code == 200


@pytest.mark.django_db
def test_audyt_nieowner_w_grupie_404(client, django_user_model, admin_user):
    """Członek grupy, ale NIE owner (i nie superuser) → 404 (owner-scope)."""
    from django.contrib.auth.models import Group

    imp = baker.make(
        ImportPracownikow,
        owner=admin_user,
        stan=ImportPracownikow.STAN_ZINTEGROWANY,
    )
    inny = django_user_model.objects.create_user(
        username="obcy_audyt", password="x", is_superuser=False
    )
    grupa, _ = Group.objects.get_or_create(name="wprowadzanie danych")
    inny.groups.add(grupa)
    client.force_login(inny)
    resp = client.get(_url(imp))
    assert resp.status_code == 404
