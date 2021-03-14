# -*- encoding: utf-8 -*-

import pytest
from django.core.exceptions import ValidationError
from django.db import InternalError
from django.db.models import ProtectedError
from model_mommy import mommy

from bpp.models import CacheQueue, Wydawca
from bpp.models.wydawca import Poziom_Wydawcy
from bpp.tasks import aktualizuj_cache


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_delete(wydawnictwo_zwarte, wydawca):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.save()

    aktualizuj_cache.delay()
    assert CacheQueue.objects.all().count() == 0

    with pytest.raises(ProtectedError):
        wydawca.delete()

    from django.db import connection

    cursor = connection.cursor()
    cursor.execute("DELETE FROM bpp_wydawca WHERE id = %i" % wydawca.id)
    assert CacheQueue.objects.all().count() == 1

    # Utworz ponownie, bo błąd przy wyjściu z testu
    wydawca.save()


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_change_nazwa(wydawnictwo_zwarte, wydawca):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.save()

    aktualizuj_cache.delay()
    assert CacheQueue.objects.all().count() == 0

    wydawca.nazwa = wydawca.nazwa + "X"
    wydawca.save()

    assert CacheQueue.objects.all().count() == 1


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_change_alias_dla(wydawnictwo_zwarte, wydawca):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.save()

    aktualizuj_cache.delay()
    assert CacheQueue.objects.all().count() == 0

    wydawca2 = mommy.make(Wydawca)

    wydawca.alias_dla = wydawca2
    wydawca.save()

    assert CacheQueue.objects.all().count() == 1


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_change_poziom_ten_sam_rok(
    wydawnictwo_zwarte, wydawca, rok
):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.rok = rok
    wydawnictwo_zwarte.save()

    aktualizuj_cache.delay()
    assert CacheQueue.objects.all().count() == 0

    pw = wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)

    assert CacheQueue.objects.all().count() == 1

    pw.poziom = 2
    pw.save()

    assert CacheQueue.objects.all().count() == 2


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_change_poziom_rozny_rok(
    wydawnictwo_zwarte, wydawca, rok
):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.rok = rok
    wydawnictwo_zwarte.save()

    aktualizuj_cache.delay()
    assert CacheQueue.objects.all().count() == 0

    pw = wydawca.poziom_wydawcy_set.create(rok=rok + 1, poziom=1)

    assert CacheQueue.objects.all().count() == 0

    pw.poziom = 2
    pw.save()

    assert CacheQueue.objects.all().count() == 0


@pytest.mark.django_db
def test_poziom_wydawcy_zmiana_roku(wydawca, rok):
    pw = wydawca.poziom_wydawcy_set.create(rok=rok, poziom=2)
    pw.rok = rok + 1
    with pytest.raises(InternalError):
        pw.save()


@pytest.mark.django_db
def test_poziom_wydawcy_zmiana_id_wydawcy(wydawca, rok):
    pw = wydawca.poziom_wydawcy_set.create(rok=rok, poziom=2)
    w2 = Wydawca.objects.create(nazwa="fubar")
    pw.wydawca = w2
    with pytest.raises(InternalError):
        pw.save()


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
    w2 = mommy.make(Wydawca)
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
