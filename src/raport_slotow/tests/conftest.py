import pytest
from django.contrib.sites.models import Site
from model_bakery import baker

from bpp.models import (
    Autor_Dyscyplina,
    Cache_Punktacja_Autora_Query,
    Cache_Punktacja_Dyscypliny,
    Charakter_Formalny,
    Jednostka,
    Rekord,
    Uczelnia,
    Wydzial,
)
from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu
from raport_slotow.models.uczelnia import RaportSlotowUczelnia


def _rekord_slotu_maker(autor, jednostka, dyscyplina, wydawnictwo_ciagle, rok):
    wydawnictwo_ciagle.autorzy_set.update(dyscyplina_naukowa=dyscyplina)

    rekord = Rekord.objects.get_for_model(wydawnictwo_ciagle)
    Cache_Punktacja_Dyscypliny.objects.create(
        rekord_id=rekord.pk,
        dyscyplina=dyscyplina,
        uczelnia=jednostka.uczelnia,
        pkd=50,
        slot=20,
        autorzy_z_dyscypliny=[
            autor.pk,
        ],
        zapisani_autorzy_z_dyscypliny=[
            "Foo",
        ],
    )
    return Cache_Punktacja_Autora_Query.objects.create(
        autor=autor,
        jednostka=jednostka,
        dyscyplina=dyscyplina,
        pkdaut=50,
        slot=20,
        rekord=rekord,
    )


@pytest.fixture
def rekord_slotu(
    autor_jan_kowalski, jednostka, dyscyplina1, wydawnictwo_ciagle_z_autorem, rok
):
    return _rekord_slotu_maker(
        autor_jan_kowalski, jednostka, dyscyplina1, wydawnictwo_ciagle_z_autorem, rok
    )


@pytest.fixture
def raport_slotow_uczelnia(db):
    return baker.make(RaportSlotowUczelnia)


# ---------------------------------------------------------------------------
# Fixtures for multi-uczelnia slot-cache tests
# ---------------------------------------------------------------------------


@pytest.fixture
def druga_uczelnia(db):
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
        parent=znajdz_lub_utworz_wezel_wydzialu(wydzial)[0],
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
    """Wydawnictwo_Zwarte co-authored by two authors from two different
    universities (jednostka → uczelnia1, jednostka_drugiej_uczelni →
    druga_uczelnia), both in the same dyscyplina1."""
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
        autor_jan_kowalski,
        jednostka_drugiej_uczelni,
        dyscyplina_naukowa=dyscyplina1,
    )
    wydawnictwo_zwarte.punkty_kbn = 20
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(skrot="KSP")
    wydawnictwo_zwarte.save()
    return wydawnictwo_zwarte
