# -*- encoding: utf-8 -*-

import pytest
from django.db import DatabaseError, InternalError
from django.db.models import ProtectedError
from psycopg2._psycopg import DatabaseError

from bpp.models import CacheQueue, Wydawca
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
def test_wydawnictwo_zwarte_wydawca_change_poziom_ten_sam_rok(wydawnictwo_zwarte, wydawca, rok):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.rok = rok
    wydawnictwo_zwarte.save()

    aktualizuj_cache.delay()
    assert CacheQueue.objects.all().count() == 0

    pw = wydawca.poziom_wydawcy_set.create(
        rok=rok,
        poziom=1)

    assert CacheQueue.objects.all().count() == 1

    pw.poziom = 2
    pw.save()

    assert CacheQueue.objects.all().count() == 2


@pytest.mark.django_db
def test_wydawnictwo_zwarte_wydawca_change_poziom_rozny_rok(wydawnictwo_zwarte, wydawca, rok):
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.rok = rok
    wydawnictwo_zwarte.save()

    aktualizuj_cache.delay()
    assert CacheQueue.objects.all().count() == 0

    pw = wydawca.poziom_wydawcy_set.create(
        rok=rok + 1,
        poziom=1)

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
    w2 = Wydawca.objects.create(nazwa='fubar')
    pw.wydawca = w2
    with pytest.raises(InternalError):
        pw.save()


@pytest.mark.django_db
def test_wydawca_get_tier(wydawca, rok):
    assert wydawca.get_tier(rok) == -1

    pw = wydawca.poziom_wydawcy_set.create(rok=rok, poziom=None)
    assert wydawca.get_tier(rok) == None

    pw.poziom = 1
    pw.save()
    assert wydawca.get_tier(rok) == 1

