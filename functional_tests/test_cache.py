# -*- encoding: utf-8 -*-
# TODO: przenies do bpp/tests/test_cache.py

from django.db import transaction
from django.db import connection
from model_mommy import mommy
from bpp.models.autor import Autor
from bpp.models.cache import Rekord
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.struktura import Jednostka
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.zrodlo import Zrodlo
from bpp.tests.util import any_doktorat


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


def test_post_save_cache(doktorat):
    assert Rekord.objects.all().count() == 1

    doktorat.tytul = 'zmieniono'
    doktorat.save()

    assert Rekord.objects.get(original=doktorat).tytul == 'zmieniono'

def test_deletion_cache(doktorat):
    assert Rekord.objects.all().count() == 1

    doktorat.delete()
    assert Rekord.objects.all().count() == 0

def test_wca_delete_cache(wydawnictwo_ciagle, autor, autor_jan_kowalski, autor_jan_nowak, jednostka):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_ciagle.dodaj_autora(autor_jan_nowak, jednostka)

# def test_m2m_caching(self):
#     """Czy skasowanie obiektu Wydawnictwo_Ciagle_Autor zmieni opis
#     wydawnictwa ciągłego w Rekordy materialized view?"""
#
#     # Odśwież wpisy w mat view, zapisując Wydawnictwo_Ciagle:
#     self.c.save()
#     self.assertEquals(Rekord.objects.all().count(), 5)
#
#     # Skasuj obiekt
#     aca = Wydawnictwo_Ciagle_Autor.objects.all()[0]
#     aca.delete()
#     self.assertEquals(Autorzy.objects.filter(rekord=aca).count(), 0)


        #
    # def __test_m2m_caching(self, obj, should_be=3):
    #     """Czy skasowanie autora, jednostki, typu odpowiedzialnosci lub zrodla
    #      zmieni opis wydawnictwa ciągłego w Cache?"""
    #
    #     self.assertEquals(Rekord.objects.all().count(), 5)
    #     self.assertEquals(Wydawnictwo_Ciagle_Autor.objects.all().count(), 1)
    #
    #     obj.delete()
    #
    #     self.assertEquals(Wydawnictwo_Ciagle_Autor.objects.all().count(), 0)
    #     self.assertEquals(Rekord.objects.all().count(), should_be)
    #
    # @with_cache
    # def test_m2m_caching_autor(self):
    #     self.__test_m2m_caching(self.a)
    #
    # @with_cache
    # def test_m2m_caching_typ_odpowiedzialnosci(self):
    #     self.__test_m2m_caching(self.typ_odpowiedzialnosci, should_be=5)
    #     self.assertEquals(Autorzy.objects.all().count(), 0)
    #
    # @with_cache
    # def test_m2m_caching_zrodlo(self):
    #     self.__test_m2m_caching(self.zr, should_be=4)
    #
    # @with_cache
    # def test_m2m_caching_jezyk(self):
    #     Rekord.objects.full_refresh()
    #     self.assertEquals(Rekord.objects.all().count(), 5)
    #     self.assertEquals(Wydawnictwo_Ciagle_Autor.objects.all().count(), 1)
    #
    #     Jezyk.objects.all().delete()
    #
    #     self.assertEquals(Rekord.objects.all().count(), 0)
    #     self.assertEquals(Autorzy.objects.all().count(), 0)
    #
    # @with_cache
    # def test_m2m_caching_charakter_formalny(self):
    #     self.assertEquals(AutorzyView.objects.all().count(), 5)
    #     self.assertEquals(Autorzy.objects.all().count(), 5)
    #
    #     Rekord.objects.full_refresh()
    #
    #     self.assertEquals(Rekord.objects.all().count(), 5)
    #     self.assertEquals(Wydawnictwo_Ciagle_Autor.objects.all().count(), 1)
    #
    #     self.assertEquals(AutorzyView.objects.all().count(), 5)
    #     self.assertEquals(Autorzy.objects.all().count(), 5)
    #
    #     Charakter_Formalny.objects.all().delete()
    #
    #     self.assertEquals(Rekord.objects.all().count(), 0)
    #     # XXX: TODO: idealnie, tu powinno byc 0 rekordów, ale PAT, DOK i HAB
    #     # XXX: TODO: mają symulowane pole charakteru i nie zostaną usunięte
    #     self.assertEquals(Autorzy.objects.all().count(), 0)
    #     transaction.commit()
    #
    #
    # @with_cache
    # def test_m2m_caching_uczelnia(self):
    #     self.__test_m2m_caching(self.uczelnia)
    #
    # @with_cache
    # def test_m2m_caching_wydzial(self):
    #     self.__test_m2m_caching(self.wydzial)
    #
    # @with_cache
    # def test_rekord_objects_full_refresh_bug(self):
    #     self.assertEquals(Rekord.objects.all().count(), 5)
    #     self.assertEquals(AutorzyView.objects.all().count(), 5)
    #     self.assertEquals(Autorzy.objects.all().count(), 5)
    #
    #     Rekord.objects.full_refresh()
    #
    #     self.assertEquals(Rekord.objects.all().count(), 5)
    #     self.assertEquals(AutorzyView.objects.all().count(), 5)
    #     self.assertEquals(Autorzy.objects.all().count(), 5)
    #
    #
