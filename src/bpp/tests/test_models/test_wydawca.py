import pytest
from denorm.models import DirtyInstance
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from model_bakery import baker

from bpp.models import Wydawca
from bpp.models.wydawca import Poziom_Wydawcy


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_delete(wydawnictwo_zwarte, wydawca, denorms):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.save()

    denorms.flush()
    assert DirtyInstance.objects.count() == 0

    with pytest.raises(ProtectedError):
        wydawca.delete()

    wydawnictwo_zwarte.wydawca = None
    wydawnictwo_zwarte.save()

    wydawca.delete()

    assert DirtyInstance.objects.count() == 1
    denorms.flush()


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_change_nazwa(wydawnictwo_zwarte, wydawca, denorms):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.save()

    denorms.flush()
    assert DirtyInstance.objects.all().count() == 0

    wydawca.nazwa = wydawca.nazwa + "X"
    wydawca.save()

    assert DirtyInstance.objects.all().count() == 2


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_change_alias_dla(
    wydawnictwo_zwarte, wydawca, denorms
):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.save()

    denorms.flush()
    assert DirtyInstance.objects.all().count() == 0

    wydawca2 = baker.make(Wydawca)

    wydawca.alias_dla = wydawca2
    wydawca.save()

    assert DirtyInstance.objects.all().count() == 5


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_change_poziom_ten_sam_rok(
    wydawnictwo_zwarte, wydawca, rok, denorms
):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.rok = rok
    wydawnictwo_zwarte.save()

    denorms.flush()
    assert DirtyInstance.objects.all().count() == 0

    pw = wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)

    assert DirtyInstance.objects.all().count() == 1
    denorms.flush()
    pw.poziom = 2
    pw.save()

    # Tu przebuduje wydawce + liste poziomow na wydawcy
    denorms.flush(run_once=True)

    # ... a teraz bedzie przebudowywał wyd. zwrate
    assert DirtyInstance.objects.all().count() == 1
    assert DirtyInstance.objects.first().object_id == wydawnictwo_zwarte.pk


@pytest.mark.django_db
def test_wydawca_get_tier(wydawca, rok):
    assert wydawca.get_tier(rok) == -1

    pw = wydawca.poziom_wydawcy_set.create(rok=rok, poziom=None)
    assert wydawca.get_tier(rok) is None

    pw.poziom = 1
    pw.save()
    assert wydawca.get_tier(rok) == 1


@pytest.mark.django_db
def test_wydawca_alias_get_tier(wydawca, alias_wydawcy, rok):
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)
    assert wydawca.get_tier(rok) == 1

    assert alias_wydawcy.get_tier(rok) == 1
    assert alias_wydawcy.get_tier(rok + 10) == -1


def test_wydawca_alias_nie_pozwol_stworzyc_poziomu_dla_aliasu(alias_wydawcy):
    with pytest.raises(ValidationError):
        alias_wydawcy.poziom_wydawcy_set.create(rok=2020, poziom=1)


def test_wydawca_alias_nie_pozwol_zrobic_aliasu_dla_posiadajacego_poziomy(wydawca):
    wydawca.poziom_wydawcy_set.create(rok=2020, poziom=2)
    w2 = baker.make(Wydawca)
    wydawca.alias_dla = w2
    with pytest.raises(ValidationError):
        wydawca.save()


def test_wydawca_alias_sam_do_siebie(wydawca):
    wydawca.alias_dla = wydawca
    with pytest.raises(ValidationError):
        wydawca.save()


def test_poziom_wydawcy_str(wydawca):
    pw = Poziom_Wydawcy.objects.create(wydawca=wydawca, rok=2020, poziom=1)

    assert str(pw) == 'Poziom wydawcy "Wydawca Testowy" za rok 2020'


@pytest.mark.django_db
def test_denorm_wydawca_ilosc_aliasow(denorms):
    w1 = Wydawca.objects.create(nazwa="123")
    assert w1.ile_aliasow == 0

    Wydawca.objects.create(nazwa="456", alias_dla=w1)

    denorms.flush()
    w1.refresh_from_db()
    assert w1.ile_aliasow == 1


@pytest.mark.django_db
def test_denorm_wydawca_poziomy_wydawcy(denorms):
    w1 = Wydawca.objects.create(nazwa="123")
    assert w1.lista_poziomow == []

    Poziom_Wydawcy.objects.create(wydawca=w1, poziom=2, rok=3333)

    denorms.flush()

    w1.refresh_from_db()
    assert w1.lista_poziomow[0] == [3333, 2]


@pytest.mark.django_db
def test_wydawca_str():
    w1 = baker.make(Wydawca, nazwa="Foo")
    w2 = baker.make(Wydawca, nazwa="Bar", alias_dla=w1)

    assert str(w2) == "Bar (alias dla Foo)"
