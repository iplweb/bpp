import pytest
from django.urls import reverse

from bpp.models import Rekord


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = True
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert (
        b"Wydruk dyscypliny zg" in res.content
        and b"oszonej dla publikacji" in res.content
    )


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_NIE_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = False
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert (
        b"Wydruk dyscypliny zg" not in res.content
        or b"oszonej dla publikacji" not in res.content
    )


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_nie_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = False
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert b"<!-- wydruk oswiadczenia -->" not in res.content


@pytest.mark.django_db
def test_oswiadczenie_jedno(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    autor = rekord.autorzy_set.first()
    dyscyplina_pracy = rekord.autorzy_set.first().dyscyplina_naukowa
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, dyscyplina_pracy.pk),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenie_druga_dyscyplina(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    autor = rekord.autorzy_set.first()
    dyscyplina_pracy = rekord.autorzy_set.first().dyscyplina_naukowa
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie-druga-dyscyplina",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, dyscyplina_pracy.pk),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenie_wiele(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    url = reverse(
        "oswiadczenia:wiele-oswiadczen",
        args=(rekord.pk[0], rekord.pk[1]),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_remove_old_oswiadczenia_export_files():
    from datetime import timedelta

    from django.utils import timezone
    from model_bakery import baker

    from oswiadczenia.models import OswiadczeniaExportTask
    from oswiadczenia.tasks import remove_old_oswiadczenia_export_files

    # Create a recent task (should NOT be deleted)
    baker.make(OswiadczeniaExportTask)

    # Create an old task (should be deleted)
    old_task = baker.make(OswiadczeniaExportTask)
    old_task.created_at = timezone.now() - timedelta(days=20)
    old_task.save()

    assert OswiadczeniaExportTask.objects.count() == 2

    remove_old_oswiadczenia_export_files()

    assert OswiadczeniaExportTask.objects.count() == 1
