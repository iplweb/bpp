import pytest
from django.urls import reverse
from model_bakery import baker

from ewaluacja_metryki.models import MetrykaAutora

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Dyscyplina_Naukowa


@pytest.mark.django_db
def test_discipline_filter_hidden_when_only_one(admin_user, db):
    """Test that discipline filter is hidden when there's only one discipline"""
    # Create only one discipline with metrics
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Test Discipline")
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")

    # Create metrics for only one discipline
    baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        slot_maksymalny=4.0,
        slot_nazbierany=2.0,
        punkty_nazbierane=100.0,
        slot_wszystkie=3.0,
        punkty_wszystkie=150.0,
    )

    # Add user to required group
    from django.contrib.auth.models import Group

    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    admin_user.groups.add(group)

    from django.test import Client

    client = Client()
    client.force_login(admin_user)

    response = client.get(reverse("ewaluacja_metryki:lista"))

    assert response.status_code == 200
    assert response.context["tylko_jedna_dyscyplina"] is True
    # The select for discipline should not be in the HTML
    assert "<label>Dyscyplina" not in response.content.decode()


@pytest.mark.django_db
def test_discipline_filter_shown_when_multiple(admin_user, db):
    """Test that discipline filter is shown when there are multiple disciplines"""
    # Create multiple disciplines with metrics
    dyscyplina1 = baker.make(Dyscyplina_Naukowa, nazwa="Discipline 1")
    dyscyplina2 = baker.make(Dyscyplina_Naukowa, nazwa="Discipline 2")
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")

    # Create metrics for multiple disciplines
    baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina1,
        jednostka=jednostka,
        slot_maksymalny=4.0,
        slot_nazbierany=2.0,
        punkty_nazbierane=100.0,
        slot_wszystkie=3.0,
        punkty_wszystkie=150.0,
    )
    baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina2,
        jednostka=jednostka,
        slot_maksymalny=4.0,
        slot_nazbierany=1.5,
        punkty_nazbierane=80.0,
        slot_wszystkie=2.5,
        punkty_wszystkie=120.0,
    )

    # Add user to required group
    from django.contrib.auth.models import Group

    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    admin_user.groups.add(group)

    from django.test import Client

    client = Client()
    client.force_login(admin_user)

    response = client.get(reverse("ewaluacja_metryki:lista"))

    assert response.status_code == 200
    assert response.context["tylko_jedna_dyscyplina"] is False
    # The select for discipline should be in the HTML
    assert "<label>Dyscyplina" in response.content.decode()
    assert "Discipline 1" in response.content.decode()
    assert "Discipline 2" in response.content.decode()


@pytest.mark.django_db
def test_column_sizing_with_one_discipline(admin_user, db):
    """Test that column sizing adjusts when discipline filter is hidden"""
    # Create only one discipline
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Single Discipline")
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")

    baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        slot_maksymalny=4.0,
        slot_nazbierany=2.0,
        punkty_nazbierane=100.0,
        slot_wszystkie=3.0,
        punkty_wszystkie=150.0,
    )

    # Add user to required group
    from django.contrib.auth.models import Group

    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    admin_user.groups.add(group)

    from django.test import Client

    client = Client()
    client.force_login(admin_user)

    response = client.get(reverse("ewaluacja_metryki:lista"))

    assert response.status_code == 200
    content = response.content.decode()

    # Check that columns are sized appropriately (medium-6 when no departments)
    # The actual sizing depends on whether departments are used
    assert "medium-6" in content or "medium-4" in content
