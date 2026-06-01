"""Test parytetu: po zaseedowaniu DefinicjaRaportu z flag Uczelnia.pokazuj_raport_*
nowa metoda widoczny_dla() daje DOKŁADNIE ten sam wynik co dawne
Uczelnia.sprawdz_uprawnienie() — gwarancja płynnego przejścia (slice C).
"""

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory
from model_bakery import baker

from bpp.const import GR_RAPORTY_WYSWIETLANIE
from bpp.models import OpcjaWyswietlaniaField, Uczelnia
from nowe_raporty.models import DefinicjaRaportu
from nowe_raporty.seeding import seed_default_reports

WSZYSTKIE_OPCJE = [
    OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE,
    OpcjaWyswietlaniaField.POKAZUJ_ZALOGOWANYM,
    OpcjaWyswietlaniaField.POKAZUJ_GDY_W_ZESPOLE,
    OpcjaWyswietlaniaField.POKAZUJ_NIGDY,
]


def _req(user):
    r = RequestFactory().get("/")
    r.user = user
    return r


@pytest.mark.django_db
@pytest.mark.parametrize("opcja", WSZYSTKIE_OPCJE)
def test_parytet_widocznosci_raport_autorow(opcja, django_user_model):
    # Stan "przed": flaga widoczności raportu autorów na obiekcie Uczelnia.
    uczelnia = baker.make(Uczelnia, pokazuj_raport_autorow=opcja)

    # Migracja danych: seed tworzy DefinicjaRaportu mapując uprawnienia z flagi.
    seed_default_reports()
    definicja = DefinicjaRaportu.objects.get(slug="raport-autorow")

    grupa = Group.objects.get_or_create(name=GR_RAPORTY_WYSWIETLANIE)[0]

    w_grupie = baker.make(django_user_model, is_staff=False, is_superuser=False)
    w_grupie.groups.add(grupa)

    users = [
        AnonymousUser(),
        baker.make(django_user_model, is_staff=False, is_superuser=False),
        w_grupie,
        baker.make(django_user_model, is_staff=True, is_superuser=False),
        # superuser realistycznie z is_staff=True (Django admin tego wymaga);
        # "superuser zawsze widzi" to zamierzone ulepszenie, zgodne ze starym
        # zachowaniem dla staff-superusera.
        baker.make(django_user_model, is_staff=True, is_superuser=True),
    ]

    for user in users:
        req = _req(user)
        stare = uczelnia.sprawdz_uprawnienie("raport_autorow", req)
        nowe = definicja.widoczny_dla(req)
        assert nowe == stare, (
            f"opcja={opcja} user(staff={user.is_staff},"
            f"super={getattr(user, 'is_superuser', False)}): "
            f"stare={stare} nowe={nowe}"
        )


@pytest.mark.django_db
def test_seed_tworzy_definicje_dla_czterech_raportow():
    seed_default_reports()
    slugi = set(DefinicjaRaportu.objects.values_list("slug", flat=True))
    assert slugi == {
        "raport-autorow",
        "raport-jednostek",
        "raport-wydzialow",
        "raport-uczelni",
    }


@pytest.mark.django_db
def test_seed_definicje_idempotentny():
    seed_default_reports()
    seed_default_reports()
    assert DefinicjaRaportu.objects.filter(slug="raport-autorow").count() == 1


@pytest.mark.django_db
def test_seed_nie_nadpisuje_istniejacej_definicji():
    # Redaktor zmienil uprawnienia w adminie -> seed nie moze tego deptac.
    report = baker.make("flexible_reports.Report", slug="raport-autorow")
    istn = DefinicjaRaportu.objects.create(
        nazwa="MOJA",
        slug="raport-autorow",
        poziom=DefinicjaRaportu.POZIOM_AUTOR,
        report=report,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_SUPERUSER,
    )
    seed_default_reports()
    istn.refresh_from_db()
    assert istn.nazwa == "MOJA"
    assert istn.poziom_dostepu == DefinicjaRaportu.DOSTEP_SUPERUSER


@pytest.mark.django_db
def test_seed_kolejnosc_uczelnia_wydzial_jednostka_autor():
    seed_default_reports()
    kolejnosc = {d.slug: d.kolejnosc for d in DefinicjaRaportu.objects.all()}
    assert kolejnosc["raport-uczelni"] < kolejnosc["raport-wydzialow"]
    assert kolejnosc["raport-wydzialow"] < kolejnosc["raport-jednostek"]
    assert kolejnosc["raport-jednostek"] < kolejnosc["raport-autorow"]
