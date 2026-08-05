"""
Testy charakteryzujące (pinning) zachowanie widoku przemapuj_zrodlo.

Utrwalają zachowanie ścieżek confirm/preview/typ_wyboru oraz walidacji przed
refaktoryzacją zdejmującą C901. Testy MUSZĄ przechodzić przeciw kodowi
PRZED refaktoryzacją.
"""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Wydawnictwo_Ciagle, Zrodlo
from przemapuj_zrodla_pbn.models import PrzeMapowanieZrodla


def _make_journal(**kwargs):
    defaults = {
        "title": "",
        "issn": "",
        "eissn": "",
        "websiteLink": "",
        "mniswId": None,
    }
    defaults.update(kwargs)
    return baker.make("pbn_api.Journal", **defaults)


@pytest.mark.django_db
def test_view_odrzuca_zrodlo_ktore_nie_jest_deleted(client, django_user_model):
    user = baker.make(django_user_model)
    user.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)

    journal_active = _make_journal(status="ACTIVE", title="Aktywne")
    zrodlo = baker.make("bpp.Zrodlo", nazwa="Aktywne", pbn_uid=journal_active)

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo", kwargs={"zrodlo_id": zrodlo.pk}
    )
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")


@pytest.mark.django_db
def test_confirm_przemapowanie_na_istniejace_zrodlo(client, django_user_model):
    user = baker.make(django_user_model)
    user.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)

    journal_deleted = _make_journal(status="DELETED", title="Stara", issn="1234-5678")
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Stara", pbn_uid=journal_deleted, issn="1234-5678"
    )

    journal_active = _make_journal(
        status="ACTIVE", title="Stara Nowa", issn="1234-5678", mniswId=999
    )
    zrodlo_nowe = baker.make(
        "bpp.Zrodlo", nazwa="Stara Nowa", pbn_uid=journal_active, issn="1234-5678"
    )

    # Rekord powiązany ze starym źródłem
    wc = baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo_stare)

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo",
        kwargs={"zrodlo_id": zrodlo_stare.pk},
    )
    response = client.post(
        url,
        {
            "typ_wyboru": "zrodlo",
            "zrodlo_docelowe": zrodlo_nowe.pk,
            "confirm": "1",
        },
    )

    assert response.status_code == 302
    assert response.url == reverse("przemapuj_zrodla_pbn:lista_skasowanych_zrodel")

    # Rekord przeniesiony na nowe źródło
    wc.refresh_from_db()
    assert wc.zrodlo_id == zrodlo_nowe.pk

    # Log operacji utworzony
    log = PrzeMapowanieZrodla.objects.filter(
        zrodlo_stare=zrodlo_stare, zrodlo_nowe=zrodlo_nowe
    ).first()
    assert log is not None
    assert log.liczba_rekordow == 1
    assert log.utworzono_przez == user


@pytest.mark.django_db
def test_confirm_przemapowanie_na_journal_tworzy_nowe_zrodlo(client, django_user_model):
    user = baker.make(django_user_model)
    user.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)

    # Rodzaj "czasopismo" jest wymagany przez ścieżkę journal.
    from bpp.models import Rodzaj_Zrodla

    Rodzaj_Zrodla.objects.get_or_create(nazwa="czasopismo")

    journal_deleted = _make_journal(
        status="DELETED", title="Stara JD", issn="2222-3333"
    )
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Stara JD", pbn_uid=journal_deleted, issn="2222-3333"
    )

    # Journal z PBN który NIE ma jeszcze odpowiednika w BPP
    journal_target = _make_journal(
        status="ACTIVE", title="Nowy Z PBN", issn="2222-3333", mniswId=7
    )

    baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo_stare)

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo",
        kwargs={"zrodlo_id": zrodlo_stare.pk},
    )
    response = client.post(
        url,
        {
            "typ_wyboru": "journal",
            "journal_docelowy": str(journal_target.pk),
            "confirm": "1",
        },
    )

    assert response.status_code == 302
    # Nowe źródło utworzone na podstawie journala
    zrodlo_nowe = Zrodlo.objects.get(pbn_uid=journal_target)
    assert zrodlo_nowe.nazwa == "Nowy Z PBN"
    assert zrodlo_nowe.issn == "2222-3333"

    # Rekordy przeniesione
    assert Wydawnictwo_Ciagle.objects.filter(zrodlo=zrodlo_nowe).count() == 1


@pytest.mark.django_db
def test_confirm_cel_skasowany_jest_poza_sugestiami_wiec_formularz_niewalidny(
    client, django_user_model
):
    # Cel skasowany w PBN NIE pojawia się w sugerowanym querysecie (zawiera
    # tylko źródła z aktywnym PBN), więc wybór jest niewalidny dla formularza
    # i widok renderuje stronę (200) bez przemapowania. Strażnik DELETED w
    # widoku jest wewnętrznym zabezpieczeniem nieosiągalnym tą ścieżką.
    user = baker.make(django_user_model)
    user.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)

    journal_deleted = _make_journal(status="DELETED", title="Stara", issn="9999-0000")
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Stara", pbn_uid=journal_deleted, issn="9999-0000"
    )

    # Cel również skasowany w PBN
    journal_deleted2 = _make_journal(
        status="DELETED", title="Stara Cel", issn="9999-0000"
    )
    zrodlo_cel = baker.make(
        "bpp.Zrodlo",
        nazwa="Stara Cel",
        pbn_uid=journal_deleted2,
        issn="9999-0000",
    )
    wc = baker.make("bpp.Wydawnictwo_Ciagle", zrodlo=zrodlo_stare)

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo",
        kwargs={"zrodlo_id": zrodlo_stare.pk},
    )
    response = client.post(
        url,
        {
            "typ_wyboru": "zrodlo",
            "zrodlo_docelowe": zrodlo_cel.pk,
            "confirm": "1",
        },
    )

    # Formularz niewalidny -> render strony (200), brak przemapowania
    assert response.status_code == 200

    # Rekord NIE przeniesiony
    wc.refresh_from_db()
    assert wc.zrodlo_id == zrodlo_stare.pk
    assert not PrzeMapowanieZrodla.objects.filter(zrodlo_stare=zrodlo_stare).exists()


@pytest.mark.django_db
def test_confirm_z_niewalidnym_formularzem_renderuje_strone(client, django_user_model):
    user = baker.make(django_user_model)
    user.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)

    journal_deleted = _make_journal(status="DELETED", title="Stara", issn="")
    zrodlo_stare = baker.make("bpp.Zrodlo", nazwa="Stara", pbn_uid=journal_deleted)

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo",
        kwargs={"zrodlo_id": zrodlo_stare.pk},
    )
    # confirm bez wybranego źródła -> formularz niewalidny -> render strony (200)
    response = client.post(url, {"typ_wyboru": "zrodlo", "confirm": "1"})

    assert response.status_code == 200
    assert not PrzeMapowanieZrodla.objects.filter(zrodlo_stare=zrodlo_stare).exists()


@pytest.mark.django_db
def test_preview_journal_renderuje_podglad(client, django_user_model):
    user = baker.make(django_user_model)
    user.groups.add(Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)[0])
    client.force_login(user)

    journal_deleted = _make_journal(status="DELETED", title="Stara P", issn="1111-2222")
    zrodlo_stare = baker.make(
        "bpp.Zrodlo", nazwa="Stara P", pbn_uid=journal_deleted, issn="1111-2222"
    )

    journal_target = _make_journal(
        status="ACTIVE", title="Stara P Nowa", issn="1111-2222", mniswId=7
    )

    url = reverse(
        "przemapuj_zrodla_pbn:przemapuj_zrodlo",
        kwargs={"zrodlo_id": zrodlo_stare.pk},
    )
    response = client.post(
        url,
        {
            "typ_wyboru": "journal",
            "journal_docelowy": str(journal_target.pk),
            "preview": "1",
        },
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "Podgląd zmian" in content
    # Tytuł docelowego journala pojawia się w podglądzie.
    assert "Stara P Nowa" in content
