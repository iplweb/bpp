"""Scalanie autorów a kolejka eksportu PBN w instalacji wielouczelnianej.

Rollbar #5359: scalanie tworzyło wpisy ``PBN_Export_Queue`` BEZ uczelni,
a wysyłka w tle przy >1 uczelni padała na ``Uczelnia.objects.get()``
(``MultipleObjectsReturned``).
"""

from unittest import mock

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Praca_Doktorska
from deduplikator_autorow.utils.merge import scal_autora
from pbn_export_queue.models import PBN_Export_Queue


@pytest.fixture
def user(db):
    return baker.make("bpp.BppUser")


@pytest.fixture
def main_dup(autor_maker, tytuly):
    glowny = autor_maker(imiona="Jan", nazwisko="Kowalski")
    duplikat = autor_maker(imiona="Jan", nazwisko="Kowalski-Duplikat")
    return glowny, duplikat


def test_scal_autora_zapisuje_uczelnie_na_wpisie_kolejki(
    main_dup, user, wydawnictwo_ciagle, jednostka, uczelnia
):
    glowny, duplikat = main_dup
    wydawnictwo_ciagle.dodaj_autora(duplikat, jednostka)

    result = scal_autora(glowny, duplikat, user, skip_pbn=False, uczelnia=uczelnia)

    assert result["success"] is True
    wpis = PBN_Export_Queue.objects.filter_rekord_do_wysylki(wydawnictwo_ciagle).get()
    assert wpis.uczelnia == uczelnia


def test_scal_autora_praca_doktorska_zapisuje_uczelnie(
    main_dup, user, jednostka, uczelnia
):
    glowny, duplikat = main_dup
    praca = baker.make(Praca_Doktorska, autor=duplikat, jednostka=jednostka)

    result = scal_autora(glowny, duplikat, user, skip_pbn=False, uczelnia=uczelnia)

    assert result["success"] is True
    wpis = PBN_Export_Queue.objects.filter_rekord_do_wysylki(praca).get()
    assert wpis.uczelnia == uczelnia


def test_scal_autora_rekord_juz_w_kolejce_nie_wywala_scalania(
    main_dup, user, wydawnictwo_ciagle, jednostka, uczelnia
):
    """Rekord już aktywnie w kolejce: częściowy unikat kolejki nie może
    wywrócić całej transakcji scalania (wcześniej IntegrityError)."""
    glowny, duplikat = main_dup
    dup_pk = duplikat.pk
    wydawnictwo_ciagle.dodaj_autora(duplikat, jednostka)
    PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
        user, wydawnictwo_ciagle, uczelnia=uczelnia
    )

    result = scal_autora(glowny, duplikat, user, skip_pbn=False, uczelnia=uczelnia)

    assert result["success"] is True, result.get("error")
    assert not type(glowny).objects.filter(pk=dup_pk).exists()
    assert (
        PBN_Export_Queue.objects.filter_rekord_do_wysylki(wydawnictwo_ciagle).count()
        == 1
    )
    assert any("już w kolejce" in w for w in result["warnings"])


@pytest.mark.django_db
def test_scal_autorow_view_przekazuje_uczelnie_z_requestu(client, uczelnia):
    user = baker.make("bpp.BppUser", is_active=True)
    grp, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grp)
    client.force_login(user)
    main = baker.make("bpp.Autor")
    dup = baker.make("bpp.Autor")

    with mock.patch(
        "deduplikator_autorow.views.merge.scal_autora",
        return_value={"success": True},
    ) as scal_mock:
        response = client.post(
            reverse("deduplikator_autorow:scal_autorow"),
            {"main_autor_id": main.pk, "duplicate_autor_id": dup.pk},
        )

    assert response.status_code == 200
    assert scal_mock.call_args.kwargs["uczelnia"] == uczelnia
