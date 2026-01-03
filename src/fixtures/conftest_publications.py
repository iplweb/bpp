"""Publication fixtures: wydawnictwo_ciagle, wydawnictwo_zwarte, habilitacja, doktorat, patent."""

import time

import pytest
from model_bakery import baker

from bpp.models import Autor_Dyscyplina, Wydawca
from bpp.models.patent import Patent
from bpp.models.praca_doktorska import Praca_Doktorska
from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
from bpp.models.system import Charakter_Formalny, Jezyk
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from pbn_api.models import Language

from .conftest_models import _zrodlo_maker, current_rok


def set_default(varname, value, dct):
    if varname not in dct:
        dct[varname] = value


def _wydawnictwo_maker(klass, **kwargs):
    if "rok" not in kwargs:
        kwargs["rok"] = current_rok()

    c = time.time()
    kl = str(klass).split(".")[-1].replace("'>", "")

    kw_wyd = dict(
        tytul=f"Tytul {kl} {c}",
        tytul_oryginalny=f"Tytul oryginalny {kl} {c}",
        uwagi=f"Uwagi {kl} {c}",
        szczegoly=f"Szczegóły {kl} {c}",
    )

    if klass == Patent:
        del kw_wyd["tytul"]

    for key, value in kw_wyd.items():
        set_default(key, value, kwargs)

    return baker.make(klass, **kwargs)


def _wydawnictwo_ciagle_maker(**kwargs):
    if "zrodlo" not in kwargs:
        set_default(
            "zrodlo",
            _zrodlo_maker(
                nazwa="Źrodło Ciągłego Wydawnictwa", skrot="Źród. Ciąg. Wyd."
            ),
            kwargs,
        )

    set_default("informacje", "zrodlo-informacje", kwargs)
    set_default("issn", "123-IS-SN-34", kwargs)
    if "jezyk" not in kwargs:
        jezyk = Jezyk.objects.get(nazwa__icontains="polski")
        jezyk.pbn_uid = Language.objects.get_or_create(
            pk="pol",
            language={
                "de": "Polnisch",
                "en": "Polish",
                "pl": "polski",
                "639-1": "pl",
                "639-2": "pol",
                "wikiUrl": "https://en.wikipedia.org/wiki/Polish_language",
            },
        )[0]
        kwargs["jezyk"] = jezyk

    return _wydawnictwo_maker(Wydawnictwo_Ciagle, **kwargs)


def wydawnictwo_ciagle_maker(db):
    return _wydawnictwo_ciagle_maker


@pytest.fixture(scope="function")
@pytest.mark.django_db
def wydawnictwo_ciagle(
    jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    ret = _wydawnictwo_ciagle_maker()
    return ret


def _zwarte_base_maker(klass, **kwargs):
    if klass not in [Praca_Doktorska, Praca_Habilitacyjna, Patent]:
        set_default("liczba_znakow_wydawniczych", 31337, kwargs)

    set_default("informacje", "zrodlo-informacje dla zwarte", kwargs)

    if klass not in [Patent]:
        set_default("miejsce_i_rok", f"Lublin {current_rok()}", kwargs)
        set_default("wydawnictwo", "Wydawnictwo FOLIUM", kwargs)
        set_default("isbn", "123-IS-BN-34", kwargs)
        set_default("redakcja", "Redakcja", kwargs)

    return _wydawnictwo_maker(klass, **kwargs)


def _zwarte_maker(**kwargs):
    return _zwarte_base_maker(Wydawnictwo_Zwarte, **kwargs)


@pytest.fixture(scope="function")
def wydawnictwo_zwarte(
    jezyki, charaktery_formalne, typy_kbn, statusy_korekt, typy_odpowiedzialnosci
):
    """
    :rtype: bpp.models.Wydawnictwo_Zwarte
    """
    return _zwarte_maker(tytul_oryginalny="Wydawnictwo Zwarte ĄćłłóńŹ")


@pytest.fixture
def zwarte_maker(db):
    return _zwarte_maker


@pytest.fixture
def wydawca(db):
    return Wydawca.objects.get_or_create(nazwa="Wydawca Testowy")[0]


@pytest.fixture
def alias_wydawcy(wydawca):
    return Wydawca.objects.create(nazwa="Drugi taki tam", alias_dla=wydawca)


def _habilitacja_maker(**kwargs):
    Charakter_Formalny.objects.get_or_create(nazwa="Praca habilitacyjna", skrot="H")
    return _zwarte_base_maker(Praca_Habilitacyjna, **kwargs)


@pytest.fixture(scope="function")
def habilitacja(jednostka, db, charaktery_formalne, jezyki, typy_odpowiedzialnosci):
    return _habilitacja_maker(
        tytul_oryginalny="Praca habilitacyjna", jednostka=jednostka
    )


@pytest.fixture
def praca_habilitacyjna(
    habilitacja,
) -> Praca_Habilitacyjna:
    return habilitacja


@pytest.fixture
def habilitacja_maker(db):
    return _habilitacja_maker


def _doktorat_maker(**kwargs):
    return _zwarte_base_maker(Praca_Doktorska, **kwargs)


@pytest.fixture(scope="function")
def doktorat(jednostka, charaktery_formalne, jezyki, typy_odpowiedzialnosci):
    return _doktorat_maker(tytul_oryginalny="Praca doktorska", jednostka=jednostka)


@pytest.fixture(scope="function")
def praca_doktorska(doktorat):
    return doktorat


@pytest.fixture
def doktorat_maker(db):
    return _doktorat_maker


def _patent_maker(**kwargs):
    return _zwarte_base_maker(Patent, **kwargs)


@pytest.fixture
def patent(db, typy_odpowiedzialnosci, jezyki, charaktery_formalne, typy_kbn):
    return _patent_maker(tytul_oryginalny="PATENT!")


@pytest.fixture
def patent_maker(db):
    return _patent_maker


@pytest.fixture(scope="function")
def wydawnictwo_ciagle_z_autorem(
    wydawnictwo_ciagle, autor_jan_kowalski, jednostka, typy_odpowiedzialnosci
) -> Wydawnictwo_Ciagle:
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    return wydawnictwo_ciagle


@pytest.fixture(scope="function")
def wydawnictwo_zwarte_z_autorem(wydawnictwo_zwarte, autor_jan_kowalski, jednostka):
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)
    return wydawnictwo_zwarte


@pytest.fixture(scope="function")
def wydawnictwo_ciagle_z_dwoma_autorami(
    wydawnictwo_ciagle_z_autorem, autor_jan_nowak, jednostka, typy_odpowiedzialnosci
):
    wydawnictwo_ciagle_z_autorem.dodaj_autora(autor_jan_nowak, jednostka)
    return wydawnictwo_ciagle_z_autorem


@pytest.fixture
def praca_z_dyscyplina(
    wydawnictwo_ciagle_z_autorem, dyscyplina1, rok, db, denorms, rodzaj_autora_n
):
    wydawnictwo_ciagle_z_autorem.punkty_kbn = 5
    wydawnictwo_ciagle_z_autorem.save()

    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    Autor_Dyscyplina.objects.create(
        autor=wca.autor,
        rok=wca.rekord.rok,
        dyscyplina_naukowa=dyscyplina1,
        rodzaj_autora=rodzaj_autora_n,
    )
    wca.dyscyplina_naukowa = dyscyplina1
    wca.save()

    denorms.flush()

    wydawnictwo_ciagle_z_autorem.przelicz_punkty_dyscyplin()

    return wydawnictwo_ciagle_z_autorem


@pytest.fixture
def wydawnictwo_zwarte_przed_korekta(statusy_korekt):
    return baker.make(
        Wydawnictwo_Zwarte, status_korekty=statusy_korekt["przed korektą"]
    )


@pytest.fixture
def wydawnictwo_zwarte_w_trakcie_korekty(statusy_korekt):
    return baker.make(
        Wydawnictwo_Zwarte, status_korekty=statusy_korekt["w trakcie korekty"]
    )


@pytest.fixture
def wydawnictwo_zwarte_po_korekcie(statusy_korekt):
    return baker.make(Wydawnictwo_Zwarte, status_korekty=statusy_korekt["po korekcie"])


@pytest.fixture
def ksiazka(wydawnictwo_zwarte, ksiazka_polska) -> "Wydawnictwo_Zwarte":
    wydawnictwo_zwarte.charakter_formalny = ksiazka_polska
    wydawnictwo_zwarte.save()
    return wydawnictwo_zwarte


@pytest.fixture
def artykul(wydawnictwo_ciagle, artykul_w_czasopismie):
    wydawnictwo_ciagle.charakter_formalny = artykul_w_czasopismie
    wydawnictwo_ciagle.save()
    return wydawnictwo_ciagle


@pytest.fixture
def autor_z_dyscyplina(autor_jan_nowak, dyscyplina1, rok) -> Autor_Dyscyplina:
    return Autor_Dyscyplina.objects.get_or_create(
        autor=autor_jan_nowak, dyscyplina_naukowa=dyscyplina1, rok=rok
    )[0]
