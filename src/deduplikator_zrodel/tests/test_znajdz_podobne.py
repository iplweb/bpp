"""Charakterystyczne testy dla `znajdz_podobne_zrodla`.

Funkcja buduje QuerySet kandydatów na duplikaty danego źródła. Testy pinują
obecne zachowanie filtrów (przed refaktorem zdejmującym # noqa: C901):

- kandydat MUSI mieć powiązane wydawnictwo ciągłe (pub_count > 0),
- własne źródło jest zawsze wykluczone,
- pary oznaczone jako NotADuplicate są wykluczane (w obie strony),
- źródła z IgnoredSource są wykluczane,
- źródła z RÓŻNYM mniswId (gdy główne ma mniswId) są wykluczane,
- dopasowanie po: identycznym ISSN / e-ISSN, tym samym pbn_uid,
  podobnej nazwie (trigram >= 0.5), podobnym skrócie (trigram >= 0.6),
- brak jakiegokolwiek kryterium → pusty QuerySet (Zrodlo.objects.none()).
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from bpp.models.zrodlo import Rodzaj_Zrodla, Zasieg_Zrodla, Zrodlo
from deduplikator_zrodel.models import IgnoredSource, NotADuplicate
from deduplikator_zrodel.utils import znajdz_podobne_zrodla
from pbn_api.models import Journal


@pytest.fixture
def rodzaj():
    return Rodzaj_Zrodla.objects.create(nazwa="Czasopismo")


@pytest.fixture
def zasieg():
    return Zasieg_Zrodla.objects.create(nazwa="Krajowy")


def _zrodlo(rodzaj, zasieg, *, z_publikacja=True, **kw):
    """Tworzy źródło; domyślnie z powiązanym wydawnictwem ciągłym, żeby
    przeszło filtr pub_count > 0 (kandydaci bez publikacji są pomijani)."""
    kw.setdefault("rodzaj", rodzaj)
    kw.setdefault("zasieg", zasieg)
    z = baker.make(Zrodlo, **kw)
    if z_publikacja:
        baker.make(Wydawnictwo_Ciagle, zrodlo=z)
    return z


@pytest.mark.django_db
def test_dopasowanie_po_identycznym_issn(rodzaj, zasieg):
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Glowne", skrot="G", issn="1234-5678")
    kandydat = _zrodlo(rodzaj, zasieg, nazwa="Kandydat", skrot="K", issn="1234-5678")
    wyniki = list(znajdz_podobne_zrodla(glowne))
    assert kandydat in wyniki


@pytest.mark.django_db
def test_dopasowanie_po_e_issn(rodzaj, zasieg):
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Glowne", skrot="G", e_issn="2222-3333")
    kandydat = _zrodlo(rodzaj, zasieg, nazwa="Kandydat", skrot="K", e_issn="2222-3333")
    assert kandydat in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_dopasowanie_po_tym_samym_pbn_uid(rodzaj, zasieg):
    journal = baker.make(Journal)
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Glowne", skrot="G", pbn_uid=journal)
    kandydat = _zrodlo(rodzaj, zasieg, nazwa="Inna", skrot="K", pbn_uid=journal)
    assert kandydat in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_dopasowanie_po_podobnej_nazwie(rodzaj, zasieg):
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Acta Biochimica Polonica", skrot="G")
    kandydat = _zrodlo(rodzaj, zasieg, nazwa="Acta Biochimica Polonica", skrot="K")
    assert kandydat in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_kandydat_bez_publikacji_jest_pomijany(rodzaj, zasieg):
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Glowne", skrot="G", issn="1234-5678")
    bez_pub = _zrodlo(
        rodzaj,
        zasieg,
        z_publikacja=False,
        nazwa="Kandydat",
        skrot="K",
        issn="1234-5678",
    )
    assert bez_pub not in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_wlasne_zrodlo_nie_jest_swoim_duplikatem(rodzaj, zasieg):
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Glowne", skrot="G", issn="1234-5678")
    assert glowne not in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_notaduplicate_wyklucza_kandydata(rodzaj, zasieg):
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Glowne", skrot="G", issn="1234-5678")
    kandydat = _zrodlo(rodzaj, zasieg, nazwa="Kandydat", skrot="K", issn="1234-5678")
    NotADuplicate.objects.create(zrodlo=glowne, duplikat=kandydat)
    assert kandydat not in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_notaduplicate_dziala_w_obie_strony(rodzaj, zasieg):
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Glowne", skrot="G", issn="1234-5678")
    kandydat = _zrodlo(rodzaj, zasieg, nazwa="Kandydat", skrot="K", issn="1234-5678")
    # Zapis w odwrotnej kolejności (duplikat=glowne) — i tak wyklucza.
    NotADuplicate.objects.create(zrodlo=kandydat, duplikat=glowne)
    assert kandydat not in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_ignoredsource_wyklucza_kandydata(rodzaj, zasieg):
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Glowne", skrot="G", issn="1234-5678")
    kandydat = _zrodlo(rodzaj, zasieg, nazwa="Kandydat", skrot="K", issn="1234-5678")
    IgnoredSource.objects.create(zrodlo=kandydat)
    assert kandydat not in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_rozny_mniswid_wyklucza_kandydata(rodzaj, zasieg):
    """Gdy główne źródło ma pbn_uid z mniswId, kandydaci z RÓŻNYM mniswId są
    wykluczani (różne czasopisma ministerialne ≠ duplikaty)."""
    glowne = _zrodlo(
        rodzaj,
        zasieg,
        nazwa="Glowne",
        skrot="G",
        issn="1234-5678",
        pbn_uid=baker.make(Journal, mniswId=111),
    )
    kandydat = _zrodlo(
        rodzaj,
        zasieg,
        nazwa="Kandydat",
        skrot="K",
        issn="1234-5678",
        pbn_uid=baker.make(Journal, mniswId=222),
    )
    assert kandydat not in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_ten_sam_mniswid_nie_wyklucza(rodzaj, zasieg):
    glowne = _zrodlo(
        rodzaj,
        zasieg,
        nazwa="Glowne",
        skrot="G",
        issn="1234-5678",
        pbn_uid=baker.make(Journal, mniswId=111),
    )
    kandydat = _zrodlo(
        rodzaj,
        zasieg,
        nazwa="Kandydat",
        skrot="K",
        issn="1234-5678",
        pbn_uid=baker.make(Journal, mniswId=111),
    )
    assert kandydat in list(znajdz_podobne_zrodla(glowne))


@pytest.mark.django_db
def test_brak_kryteriow_zwraca_pusty_queryset(rodzaj, zasieg):
    """Źródło bez nazwy/skrotu/issn/pbn_uid nie ma żadnego kryterium → none()."""
    glowne = baker.make(
        Zrodlo, rodzaj=rodzaj, zasieg=zasieg, nazwa="", skrot="", issn="", e_issn=""
    )
    _zrodlo(rodzaj, zasieg, nazwa="Cokolwiek", skrot="C", issn="1234-5678")
    assert list(znajdz_podobne_zrodla(glowne)) == []


@pytest.mark.django_db
def test_brak_dopasowania_pomimo_kandydatow(rodzaj, zasieg):
    """Kandydat istnieje (ma publikację), ale nic go nie łączy z głównym."""
    glowne = _zrodlo(rodzaj, zasieg, nazwa="Foo Journal", skrot="fj", issn="1111-1111")
    inny = _zrodlo(rodzaj, zasieg, nazwa="Zupelnie Inne", skrot="zi", issn="9999-9999")
    assert inny not in list(znajdz_podobne_zrodla(glowne))
