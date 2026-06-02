import pytest

from bpp.models import (
    Autor_Dyscyplina,
    Charakter_Formalny,
    Jednostka,
    Uczelnia,
    Wydzial,
)
from bpp.models.cache import Cache_Punktacja_Dyscypliny


@pytest.mark.django_db
def test_cache_punktacja_dyscypliny_ma_uczelnia(uczelnia, dyscyplina1):
    obj = Cache_Punktacja_Dyscypliny(
        rekord_id=[1, 1],
        dyscyplina=dyscyplina1,
        pkd=10,
        slot=1,
        uczelnia=uczelnia,
    )
    assert obj.uczelnia_id == uczelnia.pk
    assert obj.serialize()[-1] == uczelnia.pk


@pytest.fixture
def druga_uczelnia(db):
    from django.contrib.sites.models import Site

    site, _ = Site.objects.get_or_create(
        domain="druga.testserver", defaults={"name": "druga"}
    )
    return Uczelnia.objects.create(skrot="DR", nazwa="Druga uczelnia", site=site)


@pytest.fixture
def jednostka_drugiej_uczelni(druga_uczelnia, db):
    wydzial = Wydzial.objects.create(
        uczelnia=druga_uczelnia, skrot="W2", nazwa="Wydział II"
    )
    return Jednostka.objects.create(
        nazwa="Jedn. Drugiej Ucz.",
        skrot="JDU",
        wydzial=wydzial,
        uczelnia=druga_uczelnia,
    )


@pytest.fixture
def zwarte_dwie_uczelnie(
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    jednostka_drugiej_uczelni,
    dyscyplina1,
    rodzaj_autora_n,
    charaktery_formalne,
    wydawca,
    typy_odpowiedzialnosci,
    rok,
):
    # Obaj autorzy w TEJ SAMEJ dyscyplinie, ale w różnych uczelniach.
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        dyscyplina_naukowa=dyscyplina1,
        rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        rok=rok,
        rodzaj_autora=rodzaj_autora_n,
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka_drugiej_uczelni, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_zwarte.punkty_kbn = 20
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(
        skrot="KSP"
    )
    wydawnictwo_zwarte.save()
    return wydawnictwo_zwarte


@pytest.mark.django_db
def test_slotmixin_wszyscy_scoped_po_uczelni(zwarte_dwie_uczelnie, jednostka):
    from bpp.models.sloty.wydawnictwo_zwarte import (
        SlotKalkulator_Wydawnictwo_Zwarte_Prog3,
    )

    kalk_all = SlotKalkulator_Wydawnictwo_Zwarte_Prog3(
        zwarte_dwie_uczelnie, tryb_kalkulacji=None
    )
    kalk_u1 = SlotKalkulator_Wydawnictwo_Zwarte_Prog3(
        zwarte_dwie_uczelnie, tryb_kalkulacji=None, uczelnia=jednostka.uczelnia
    )
    assert kalk_all.wszyscy() == 2
    assert kalk_u1.wszyscy() == 1


@pytest.mark.django_db
def test_uczelnie_rekordu_zwraca_obie(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia
):
    assert set(zwarte_dwie_uczelnie.uczelnie_rekordu()) == {
        jednostka.uczelnia,
        druga_uczelnia,
    }


@pytest.mark.django_db
def test_islot_jawna_uczelnia_scoped(zwarte_dwie_uczelnie, jednostka):
    from bpp.models.sloty.core import ISlot

    kalk = ISlot(zwarte_dwie_uczelnie, uczelnia=jednostka.uczelnia)
    assert kalk.uczelnia == jednostka.uczelnia
    assert kalk.wszyscy() == 1


@pytest.mark.django_db
def test_islot_none_cross_uczelnia_failuje(zwarte_dwie_uczelnie, druga_uczelnia):
    from bpp.models.sloty.core import CannotAdapt, ISlot

    # 2 uczelnie w systemie + praca cross-uczelnia => niejednoznaczne => CannotAdapt
    with pytest.raises(CannotAdapt):
        ISlot(zwarte_dwie_uczelnie)


@pytest.mark.django_db
def test_islot_none_jedna_uczelnia_systemu_rozstrzyga(zwarte_z_dyscyplinami, uczelnia):
    from bpp.models.sloty.core import ISlot

    # tylko jedna uczelnia w systemie => ISlot(obj) rozstrzyga ją
    kalk = ISlot(zwarte_z_dyscyplinami)
    assert kalk.uczelnia == uczelnia


@pytest.mark.django_db
def test_rebuild_tworzy_wiersze_per_uczelnia(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia
):
    from bpp.models.cache import (
        Cache_Punktacja_Autora,
        Cache_Punktacja_Dyscypliny,
    )
    from bpp.models.sloty.core import IPunktacjaCacher

    cacher = IPunktacjaCacher(zwarte_dwie_uczelnie)
    cacher.removeEntries()
    cacher.rebuildEntries()

    cpd = Cache_Punktacja_Dyscypliny.objects.filter(
        rekord_id=[cacher.ctype, zwarte_dwie_uczelnie.pk]
    )
    assert cpd.count() == 2
    assert set(cpd.values_list("uczelnia_id", flat=True)) == {
        jednostka.uczelnia_id,
        druga_uczelnia.pk,
    }
    for row in cpd:
        assert len(row.autorzy_z_dyscypliny) == 1

    cpa = Cache_Punktacja_Autora.objects.filter(
        rekord_id=[cacher.ctype, zwarte_dwie_uczelnie.pk]
    )
    assert cpa.count() == 2
    assert {c.jednostka.uczelnia_id for c in cpa} == {
        jednostka.uczelnia_id,
        druga_uczelnia.pk,
    }


@pytest.mark.django_db
def test_przelicz_per_uczelnia_dzielnik_k1(zwarte_dwie_uczelnie):
    from bpp.models.cache import Cache_Punktacja_Autora

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()

    cpa_nowak = Cache_Punktacja_Autora.objects.get(autor__nazwisko="Nowak")
    cpa_kowalski = Cache_Punktacja_Autora.objects.get(autor__nazwisko="Kowalski")
    # k=1 w obrębie każdej uczelni => każdy ma pełny slot, suma = 2.0
    assert cpa_nowak.slot == cpa_kowalski.slot
    assert cpa_nowak.slot + cpa_kowalski.slot == 2


@pytest.mark.django_db
def test_przelicz_zwrotka_deterministyczna(zwarte_dwie_uczelnie):
    a = zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    b = zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    assert str(a) == str(b)


@pytest.mark.django_db
def test_widok_nie_duplikuje_miedzy_uczelniami(zwarte_dwie_uczelnie):
    from django.contrib.contenttypes.models import ContentType

    from bpp.models.cache import Cache_Punktacja_Autora_Query_View

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    ctype = ContentType.objects.get_for_model(zwarte_dwie_uczelnie).pk

    rows = Cache_Punktacja_Autora_Query_View.objects.filter(
        rekord_id=[ctype, zwarte_dwie_uczelnie.pk]
    )
    # 2 autorow x 2 dyscyplina-agregaty bez joina po uczelni = 4 (kartezjan).
    # Z naprawą: 2.
    assert rows.count() == 2
