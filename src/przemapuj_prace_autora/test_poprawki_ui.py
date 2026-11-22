"""Poprawki UI przemapowania prac autora: brak podwójnych komunikatów,
treść ostrzeżenia w podglądzie, link „Szczegóły" tylko dla uprawnionych,
przycisk na stronie autora tylko dla redakcji, rozpoznawanie jednostki
domyślnej z sufiksem skrótu uczelni."""

import pytest
from cacheops import invalidate_all
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor, Jednostka, Uczelnia, Wydawnictwo_Ciagle_Autor
from przemapuj_prace_autora import service
from przemapuj_prace_autora.forms import PrzemapoaniePracAutoraForm

User = get_user_model()


@pytest.fixture
def uczelnia(db):
    Uczelnia.objects.all().delete()
    u = baker.make(Uczelnia, nazwa="Test University", skrot="TU")
    cache.delete(b"bpp_uczelnia")
    cache.delete("bpp_uczelnia_0")
    cache.delete("bpp_uczelnia_1")
    invalidate_all()
    return u


@pytest.fixture
def jed_a(uczelnia):
    return baker.make(Jednostka, nazwa="Jednostka A", skrot="JA", uczelnia=uczelnia)


@pytest.fixture
def jed_b(uczelnia):
    return baker.make(Jednostka, nazwa="Jednostka B", skrot="JB", uczelnia=uczelnia)


@pytest.fixture
def autor(jed_a):
    a = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    baker.make(Wydawnictwo_Ciagle_Autor, autor=a, jednostka=jed_a)
    return a


def _klient(username, *, grupa=False, is_staff=False, perm=None, superuser=False):
    u = User.objects.create_user(username=username, password="pass", is_staff=is_staff)
    if superuser:
        u.is_superuser = True
        u.save()
    if grupa:
        g, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
        u.groups.add(g)
    if perm:
        u.user_permissions.add(Permission.objects.get(codename=perm))
    c = Client()
    c.login(username=username, password="pass")
    return c


def _url(autor):
    return reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )


@pytest.mark.django_db
def test_komunikat_po_przemapowaniu_wyswietlany_raz(autor, jed_a, jed_b):
    c = _klient("red", grupa=True)
    resp = c.post(
        _url(autor),
        {"jednostka_z": jed_a.pk, "jednostka_do": jed_b.pk, "confirm": "1"},
        follow=True,
    )
    tresc = resp.content.decode()
    # base.html pokazuje komunikat (skrypt channelsBroadcast); szablon nie
    # może dorzucać własnego, statycznego callouta z tym samym tekstem.
    assert "Pomyślnie przemapowano" in tresc
    assert 'class="callout success"' not in tresc


@pytest.mark.django_db
def test_podglad_nie_twierdzi_ze_operacja_nieodwracalna(autor, jed_a, jed_b):
    c = _klient("red", grupa=True)
    resp = c.post(
        _url(autor),
        {"jednostka_z": jed_a.pk, "jednostka_do": jed_b.pk, "preview": "1"},
    )
    tresc = resp.content.decode()
    assert "nieodwracalna" not in tresc
    assert "cofnąć" in tresc


def _szczegoly_widoczne(c, autor):
    tresc = c.get(_url(autor)).content.decode()
    return "/admin/przemapuj_prace_autora/przemapoaniepracautora/" in tresc


@pytest.mark.django_db
def test_szczegoly_ukryte_dla_redaktora_bez_uprawnien(autor, jed_a, jed_b):
    service.przemapuj(autor, jed_a, jed_b, None)
    c = _klient("red", grupa=True, is_staff=True)
    assert not _szczegoly_widoczne(c, autor)


@pytest.mark.django_db
def test_szczegoly_widoczne_z_uprawnieniem_view(autor, jed_a, jed_b):
    service.przemapuj(autor, jed_a, jed_b, None)
    c = _klient(
        "red",
        grupa=True,
        is_staff=True,
        perm="view_przemapoaniepracautora",
    )
    assert _szczegoly_widoczne(c, autor)


@pytest.mark.django_db
def test_szczegoly_widoczne_dla_superusera(autor, jed_a, jed_b):
    service.przemapuj(autor, jed_a, jed_b, None)
    c = _klient("su", is_staff=True, superuser=True)
    assert _szczegoly_widoczne(c, autor)


@pytest.mark.django_db
def test_przycisk_na_stronie_autora_ukryty_bez_grupy(autor):
    Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    c = _klient("plain")
    url = reverse("bpp:browse_autor", kwargs={"slug": autor.slug})
    assert "Przemapuj prace" not in c.get(url).content.decode()


@pytest.mark.django_db
def test_przycisk_na_stronie_autora_widoczny_z_grupa(autor):
    c = _klient("red", grupa=True)
    url = reverse("bpp:browse_autor", kwargs={"slug": autor.slug})
    assert "Przemapuj prace" in c.get(url).content.decode()


@pytest.mark.django_db
def test_jednostka_domyslna_z_sufiksem_rozpoznawana(uczelnia, jed_a):
    jd = baker.make(
        Jednostka, nazwa="Jednostka Domyślna TU", skrot="JD-TU", uczelnia=uczelnia
    )
    a = baker.make(Autor, imiona="Jan", nazwisko="Nowak")
    baker.make(Wydawnictwo_Ciagle_Autor, autor=a, jednostka=jd)
    baker.make(Wydawnictwo_Ciagle_Autor, autor=a, jednostka=jed_a)

    form = PrzemapoaniePracAutoraForm(autor=a)
    assert form.fields["jednostka_z"].initial == jd.pk
    assert jd not in form.fields["jednostka_do"].queryset

    form = PrzemapoaniePracAutoraForm(
        {"jednostka_z": jed_a.pk, "jednostka_do": jd.pk}, autor=a
    )
    assert not form.is_valid()
