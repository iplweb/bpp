# -*- encoding: utf-8 -*-
# TODO: przenies do bpp/tests/test_cache.py

from django.db import transaction
from django.db import connection
from model_mommy import mommy
import pytest
from bpp.models.autor import Autor
from bpp.models.cache import Rekord, Autorzy
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.struktura import Jednostka
from bpp.models.system import Typ_Odpowiedzialnosci, Jezyk, Charakter_Formalny, \
    Status_Korekty, Typ_KBN
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor
from bpp.models.zrodlo import Zrodlo
from bpp.tests.util import any_doktorat


def pierwszy_rekord():
    return Rekord.objects.all()[0].opis_bibliograficzny_cache


def test_opis_bibliograficzny(db, standard_data):
    wc = mommy.make(Wydawnictwo_Ciagle, szczegoly='Sz', uwagi='U')

    rekord_opis = Rekord.objects.all()[0].opis_bibliograficzny_cache
    wc_opis = wc.opis_bibliograficzny()
    assert rekord_opis == wc_opis


def test_kasowanie(db, standard_data):
    assert Rekord.objects.count() == 0

    wc = mommy.make(Wydawnictwo_Ciagle)
    assert Rekord.objects.count() == 1

    wc.delete()
    assert Rekord.objects.count() == 0


def test_opis_bibliograficzny_dependent(db, standard_data):
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


def test_opis_bibliograficzny_zrodlo(db, standard_data):
    """Zmień nazwę źródła i sprawdź, jak to wpłynie na opis."""
    from bpp.models import cache
    assert cache._CACHE_ENABLED

    from django.conf import settings
    assert settings.TESTING == True
    assert settings.CELERY_ALWAYS_EAGER == True

    z = mommy.make(Zrodlo, nazwa='OMG', skrot='wutlolski')
    c = mommy.make(Wydawnictwo_Ciagle, szczegoly='SZ', uwagi='U', zrodlo=z)

    assert 'wutlolski' in c.opis_bibliograficzny()
    assert 'wutlolski' in pierwszy_rekord()

    z.nazwa = 'LOL'
    z.skrot = 'FOKA'

    assert 'wutlolski' not in c.opis_bibliograficzny()
    assert 'FOKA' in c.opis_bibliograficzny()

    assert 'wutlolski' in pierwszy_rekord()


    assert cache._CACHE_ENABLED

    z.save()

    assert 'FOKA' in c.opis_bibliograficzny()
    assert 'FOKA' in pierwszy_rekord()

    z.nazwa = 'LOL 2'
    z.skrot = "foka 2"
    z.save()

    assert 'foka 2' in c.opis_bibliograficzny()
    assert 'foka 2' in pierwszy_rekord()

@pytest.mark.django_db
def test_post_save_cache(doktorat):
    assert Rekord.objects.all().count() == 1

    doktorat.tytul = 'zmieniono'
    doktorat.save()

    assert Rekord.objects.get(original=doktorat).tytul == 'zmieniono'


def test_deletion_cache(doktorat):
    assert Rekord.objects.all().count() == 1

    doktorat.delete()
    assert Rekord.objects.all().count() == 0

@pytest.mark.django_db
def test_wca_delete_cache(wydawnictwo_ciagle_z_dwoma_autorami):
    """Czy skasowanie obiektu Wydawnictwo_Ciagle_Autor zmieni opis
    wydawnictwa ciągłego w Rekordy materialized view?"""

    assert Rekord.objects.all().count() == 1
    assert Wydawnictwo_Ciagle_Autor.objects.all().count() == 2

    r = Rekord.objects.all()[0]
    assert 'NOWAK' in r.opis_bibliograficzny_cache
    assert 'KOWALSKI' in r.opis_bibliograficzny_cache

    Wydawnictwo_Ciagle_Autor.objects.all()[0].delete()
    aca = Wydawnictwo_Ciagle_Autor.objects.all()[0]
    aca.delete()

    assert Autorzy.objects.filter(rekord=aca).count() == 0
    assert Rekord.objects.all().count() == 1

    r = Rekord.objects.all()[0]
    assert 'NOWAK' not in r.opis_bibliograficzny_cache
    assert 'KOWALSKI' not in r.opis_bibliograficzny_cache

@pytest.mark.django_db
def test_caching_kasowanie_autorow(wydawnictwo_ciagle_z_dwoma_autorami):
    for wca in Wydawnictwo_Ciagle_Autor.objects.all().only('autor'):
        wca.autor.delete()

    assert Wydawnictwo_Ciagle_Autor.objects.count() == 0
    assert Rekord.objects.all().count() == 1

    r = Rekord.objects.all()[0]
    assert 'NOWAK' not in r.opis_bibliograficzny_cache
    assert 'KOWALSKI' not in r.opis_bibliograficzny_cache

@pytest.mark.django_db
def test_caching_kasowanie_typu_odpowiedzialnosci_autorow(wydawnictwo_ciagle_z_dwoma_autorami):
    assert Wydawnictwo_Ciagle_Autor.objects.filter(rekord=wydawnictwo_ciagle_z_dwoma_autorami).count() == 2

    Typ_Odpowiedzialnosci.objects.all().delete()

    assert Wydawnictwo_Ciagle_Autor.objects.count() == 0
    assert Rekord.objects.all().count() == 1

    r = Rekord.objects.all()[0]
    assert 'NOWAK' not in r.opis_bibliograficzny_cache
    assert 'KOWALSKI' not in r.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_caching_kasowanie_zrodla(wydawnictwo_ciagle_z_dwoma_autorami):
    assert Zrodlo.objects.all().count() == 1

    z = Zrodlo.objects.all()[0]
    z.delete()  # WCA ma zrodlo.on_delete=SET_NULL

    assert Rekord.objects.all().count() == 1
    assert Wydawnictwo_Ciagle.objects.all().count() == 1

    r = Rekord.objects.all()[0]
    assert 'NOWAK' in r.opis_bibliograficzny_cache
    assert 'KOWALSKI' in r.opis_bibliograficzny_cache
    assert z.skrot not in r.opis_bibliograficzny_cache
    assert "None" not in r.opis_bibliograficzny_cache


@pytest.mark.django_db
def test_caching_kasowanie_jezyka(wydawnictwo_ciagle_z_dwoma_autorami):
    xng = Jezyk.objects.create(skrot="xng.", nazwa="taki", pk=500)
    wydawnictwo_ciagle_z_dwoma_autorami.jezyk = xng
    wydawnictwo_ciagle_z_dwoma_autorami.save()

    assert Rekord.objects.all().count() == 1
    xng.delete()

    assert Rekord.objects.all().count() == 0

@pytest.mark.django_db
def test_caching_kasowanie_typu_kbn(wydawnictwo_ciagle_z_dwoma_autorami, standard_data):
    tk = Typ_KBN.objects.all().first()

    wydawnictwo_ciagle_z_dwoma_autorami.typ_kbn = tk
    wydawnictwo_ciagle_z_dwoma_autorami.save()

    assert Rekord.objects.all().count() == 1
    tk.delete()

    assert Rekord.objects.all().count() == 0


@pytest.mark.django_db
def test_caching_kasowanie_charakteru_formalnego(
        wydawnictwo_ciagle_z_dwoma_autorami, patent, autor_jan_kowalski,
        jednostka, standard_data):
    patent.dodaj_autora(autor_jan_kowalski, jednostka)

    cf = Charakter_Formalny.objects.all().first()

    wydawnictwo_ciagle_z_dwoma_autorami.charakter_formalny = cf
    wydawnictwo_ciagle_z_dwoma_autorami.save()

    assert Rekord.objects.all().count() == 2
    Charakter_Formalny.objects.all().delete()

    assert Rekord.objects.all().count() == 0

@pytest.mark.django_db
def test_caching_kasowanie_wydzialu(autor_jan_kowalski, jednostka, wydzial,
                                    wydawnictwo_ciagle):
    assert jednostka.wydzial == wydzial

    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    assert Rekord.objects.all().count() == 1
    assert Jednostka.objects.all().count() == 1
    wydzial.delete()

    assert Rekord.objects.all().count() == 1
    assert Rekord.objects.all()[0].original.autorzy.all().count() == 0
    assert Jednostka.objects.all().count() == 0

@pytest.mark.django_db
def test_caching_kasowanie_uczelni(autor_jan_kowalski, jednostka, wydzial,
                                   uczelnia, wydawnictwo_ciagle):
    assert wydzial.uczelnia == uczelnia
    assert jednostka.wydzial == wydzial
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    assert Rekord.objects.all().count() == 1
    assert Jednostka.objects.all().count() == 1
    uczelnia.delete()

    assert Rekord.objects.all().count() == 1
    assert Rekord.objects.all()[0].original.autorzy.all().count() == 0
    assert Jednostka.objects.all().count() == 0


@pytest.mark.django_db
def test_caching_full_refresh(wydawnictwo_ciagle_z_dwoma_autorami):
    assert Rekord.objects.all().count() == 1
    Rekord.objects.full_refresh()
    assert Rekord.objects.all().count() == 1

@pytest.mark.django_db
def test_caching_kolejnosc(wydawnictwo_ciagle_z_dwoma_autorami):

    a = list(Wydawnictwo_Ciagle_Autor.objects.all().order_by('kolejnosc'))
    assert len(a) == 2

    x = Rekord.objects.get(original=wydawnictwo_ciagle_z_dwoma_autorami)
    assert "[AUT.] KOWALSKI JAN, NOWAK JAN" in x.opis_bibliograficzny_cache

    k = a[0].kolejnosc
    a[0].kolejnosc = a[1].kolejnosc
    a[1].kolejnosc = k
    a[0].save()
    a[1].save()

    x = Rekord.objects.get(original=wydawnictwo_ciagle_z_dwoma_autorami)
    assert "[AUT.] NOWAK JAN, KOWALSKI JAN" in x.opis_bibliograficzny_cache

