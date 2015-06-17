# -*- encoding: utf-8 -*-
# TODO: przenies do bpp/tests/test_cache.py

from django.db import transaction
from model_mommy import mommy
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.struktura import Jednostka
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.zrodlo import Zrodlo

def pierwszy_rekord():
    return Rekord.objects.all()[0].opis_bibliograficzny_cache

def test_opis_bibliograficzny(db, statusy_korekt):
    wc = mommy.make(Wydawnictwo_Ciagle, szczegoly='Sz', uwagi='U')

    rekord_opis = Rekord.objects.all()[0].opis_bibliograficzny_cache
    wc_opis = wc.opis_bibliograficzny()
    assert rekord_opis == wc_opis


def test_kasowanie(db, statusy_korekt):
    assert Rekord.objects.count() == 0

    wc = mommy.make(Wydawnictwo_Ciagle)
    assert Rekord.objects.count() == 1

    wc.delete()
    assert Rekord.objects.count() == 0

def test_opis_bibliograficzny_dependent(db, statusy_korekt):
    """Stwórz i skasuj Wydawnictwo_Ciagle_Autor i sprawdź, jak to
    wpłynie na opis."""

    c = mommy.make(Wydawnictwo_Ciagle, szczegoly='sz', uwagi='u')
    assert 'KOWALSKI' not in c.opis_bibliograficzny()
    assert 'KOWALSKI' not in pierwszy_rekord()

    a = mommy.make(Autor, imiona='Jan', nazwisko='Kowalski')
    j = mommy.make(Jednostka)
    wca = c.dodaj_autora(a, j)
    assert 'KOWALSKI' in c.opis_bibliograficzny()
    assert 'KOWALSKI' in pierwszy_rekord()

    wca.delete()
    assert 'KOWALSKI' not in c.opis_bibliograficzny()
    assert 'KOWALSKI' not in pierwszy_rekord()


def test_opis_bibliograficzny_zrodlo(db, statusy_korekt):
    """Zmień nazwę źródła i sprawdź, jak to wpłynie na opis."""

    z = mommy.make(Zrodlo, nazwa='OMG', skrot='wutlolski')
    c = mommy.make(Wydawnictwo_Ciagle, szczegoly='SZ', uwagi='U', zrodlo=z)
    assert 'wutlolski' in c.opis_bibliograficzny()
    assert 'wutlolski' in pierwszy_rekord()

    z.nazwa = 'LOL'
    z.skrot = 'FOKA'

    assert 'wutlolski' not in c.opis_bibliograficzny()
    assert 'FOKA' in c.opis_bibliograficzny()

    assert 'wutlolski' in pierwszy_rekord()

    from bpp.models import cache
    assert cache._CACHE_ENABLED

    z.save()

    assert 'FOKA' in c.opis_bibliograficzny()
    assert 'FOKA' in pierwszy_rekord()

    z.nazwa = 'LOL 2'
    z.skrot = "foka 2"
    z.save()

    assert 'foka 2' in c.opis_bibliograficzny()
    assert 'foka 2' in pierwszy_rekord()