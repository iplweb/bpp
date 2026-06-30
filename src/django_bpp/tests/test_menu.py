"""Charakteryzacyjne testy dla django_bpp.menu.CustomMenu.init_with_context.

Pinują OBECNE zachowanie budowania menu admina zależnie od grup/uprawnień
użytkownika, aby umożliwić bezpieczny refactor (zdjęcie # noqa: C901).

Zachowane quirki (NIE są naprawiane w refaktorze):
- użytkownik bez grup i nie-superuser → IndexError (usuwanie z pustego
  poddrzewa "Dashboard"),
- usuwanie "zgłoszeń" faktycznie kasuje OSTATNI element REDAKTOR_MENU
  ("Importer publikacji"), nie "Zgłoszenia publikacji",
- STRUKTURA_MENU.pop(1) mutuje modułową listę (chronione fixturą snapshotu).
"""

import pytest
from django.contrib.auth.models import Group
from django.test import RequestFactory, override_settings
from model_bakery import baker

from django_bpp import menu as menu_module
from django_bpp.menu import CustomMenu


@pytest.fixture(autouse=True)
def _snapshot_struktura_menu():
    """STRUKTURA_MENU jest mutowane przez pop(1) — przywróć po teście."""
    saved = list(menu_module.STRUKTURA_MENU)
    yield
    menu_module.STRUKTURA_MENU[:] = saved


def _menu_for(user):
    rf = RequestFactory()
    req = rf.get("/admin/")
    req.user = user
    m = CustomMenu()
    m.init_with_context({"request": req})
    return m


def _labels(menu):
    return [str(c.title) for c in menu.children]


def _child(menu, label):
    return next(c for c in menu.children if str(c.title) == label)


@pytest.mark.django_db
def test_superuser_widzi_pelne_menu():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True, first_name="Jan")
    m = _menu_for(u)
    assert _labels(m) == [
        "BPP",
        "Dashboard",
        "WWW",
        "PBN API",
        "Dane systemowe",
        "Struktura",
        "Wprowadzanie danych",
        "Raporty",
        "Administracja",
        "Mój profil",
    ]


@pytest.mark.django_db
def test_superuser_redaktor_zachowuje_importer_publikacji():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True)
    m = _menu_for(u)
    redaktor = _child(m, "Wprowadzanie danych")
    assert len(redaktor.children) == 16
    assert str(redaktor.children[-1].title) == "Importer publikacji"


@pytest.mark.django_db
def test_superuser_administracja_ma_uslugi_docker():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True)
    m = _menu_for(u)
    admin = _child(m, "Administracja")
    labels = [str(c.title) for c in admin.children]
    assert "Grafana" in labels
    assert "Dozzle (logi)" in labels
    assert "Flower (Celery)" in labels


@pytest.mark.django_db
def test_uzytkownik_bez_grup_powoduje_indexerror():
    # Quirk: del self.children[-1].children[-1] na pustym "Dashboard".
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=True)
    with pytest.raises(IndexError):
        _menu_for(u)


@pytest.mark.django_db
def test_grupa_wprowadzanie_danych_kasuje_ostatni_element_redaktora():
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=True, first_name="Ala")
    u.groups.add(Group.objects.get_or_create(name="wprowadzanie danych")[0])
    m = _menu_for(u)
    assert _labels(m) == ["BPP", "Dashboard", "Wprowadzanie danych", "Mój profil"]
    redaktor = _child(m, "Wprowadzanie danych")
    # OSTATNI element ("Importer publikacji") jest usuwany; zostaje 15.
    assert len(redaktor.children) == 15
    assert str(redaktor.children[-1].title) == "Zgłoszenia publikacji"


@pytest.mark.django_db
def test_grupa_zgloszenia_publikacji_nie_kasuje_elementu():
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=True, first_name="Bob")
    u.groups.add(Group.objects.get_or_create(name="wprowadzanie danych")[0])
    u.groups.add(Group.objects.get_or_create(name="zgłoszenia publikacji")[0])
    m = _menu_for(u)
    redaktor = _child(m, "Wprowadzanie danych")
    assert len(redaktor.children) == 16
    assert str(redaktor.children[-1].title) == "Importer publikacji"


@pytest.mark.django_db
def test_grupa_web_dodaje_tylko_www():
    u = baker.make("bpp.BppUser", is_superuser=False, is_staff=True, first_name="Cyd")
    u.groups.add(Group.objects.get_or_create(name="web")[0])
    m = _menu_for(u)
    assert _labels(m) == ["BPP", "Dashboard", "WWW", "Mój profil"]


def _struktura_links(menu):
    struktura = _child(menu, "Struktura")
    return [c.url for c in struktura.children]


@pytest.mark.django_db
def test_struktura_pokazuje_wydzial_domyslnie():
    # Superuser → admin_tools nie przycina pozycji wg uprawnień.
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True, first_name="Dan")
    links = _struktura_links(_menu_for(u))
    # Domyślnie (używaj wydziałów) wydział JEST obecny — pełne 4 pozycje.
    assert "/admin/bpp/wydzial/" in links
    assert len(links) == 4


@pytest.mark.django_db
@override_settings(DJANGO_BPP_UCZELNIA_UZYWA_WYDZIALOW=False)
def test_struktura_bez_wydzialow_usuwa_pozycje():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True, first_name="Ela")
    links = _struktura_links(_menu_for(u))
    # STRUKTURA_MENU.pop(1) usuwa pozycję "wydział".
    assert "/admin/bpp/wydzial/" not in links
    assert len(links) == 3


@pytest.mark.django_db
def test_uzytkownik_z_haslem_ma_zmiane_hasla_w_profilu():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True, first_name="Fil")
    u.set_password("x")
    u.save()
    m = _menu_for(u)
    profil = _child(m, "Mój profil")
    labels = [str(c.title) for c in profil.children]
    assert "Change password" in labels
    assert "Fil" in labels  # first_name jako etykieta użytkownika


@pytest.mark.django_db
def test_profil_bez_uzywalnego_hasla_nie_ma_zmiany_hasla():
    u = baker.make("bpp.BppUser", is_superuser=True, is_staff=True, first_name="Gob")
    u.set_unusable_password()
    u.save()
    m = _menu_for(u)
    profil = _child(m, "Mój profil")
    labels = [str(c.title) for c in profil.children]
    assert "Change password" not in labels
