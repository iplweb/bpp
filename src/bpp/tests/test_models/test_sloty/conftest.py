import pytest

from bpp import const
from bpp.models import (
    Autor_Dyscyplina,
    Charakter_Formalny,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)


@pytest.fixture
@pytest.mark.django_db
def zwarte_z_dyscyplinami(
    wydawnictwo_zwarte,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    charaktery_formalne,
    wydawca,
    typy_odpowiedzialnosci,
    rok,
) -> Wydawnictwo_Zwarte:
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, dyscyplina_naukowa=dyscyplina1, rok=rok
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina2, rok=rok
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

    # domyslnie: ksiazka/autorstwo/wydawca spoza wykazu
    wydawnictwo_zwarte.punkty_kbn = 20
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(skrot="KSP")
    wydawnictwo_zwarte.save()

    return wydawnictwo_zwarte


@pytest.fixture
@pytest.mark.django_db
def ciagle_z_dyscyplinami(
    wydawnictwo_ciagle,
    autor_jan_nowak,
    autor_jan_kowalski,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    typy_odpowiedzialnosci,
    rok,
) -> Wydawnictwo_Ciagle:
    # Przypisz autorów do dyscyplin na ten rok albo będzie awaria:
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, dyscyplina_naukowa=dyscyplina1, rok=rok
    )
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina2, rok=rok
    )

    wydawnictwo_ciagle.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

    return wydawnictwo_ciagle


@pytest.fixture
def charakter_referat():
    return Charakter_Formalny.objects.get_or_create(
        nazwa="referat zjazdowy",
        skrot="refz",
        charakter_sloty=const.CHARAKTER_SLOTY_REFERAT,
    )[0]


@pytest.fixture
def referat_z_dyscyplinami(zwarte_z_dyscyplinami, charakter_referat):
    zwarte_z_dyscyplinami.charakter_formalny = charakter_referat
    zwarte_z_dyscyplinami.save()

    return zwarte_z_dyscyplinami
