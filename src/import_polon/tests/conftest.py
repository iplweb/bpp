from pathlib import Path

import pytest

from bpp.models import Autor_Dyscyplina, Charakter_Formalny, Wydawnictwo_Zwarte


@pytest.fixture
def fn_test_import_polon():
    return Path(__file__).parent / "test_import_polon.xlsx"


@pytest.fixture
def fn_test_import_absencji():
    return Path(__file__).parent / "test_import_absencji.xlsx"


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
