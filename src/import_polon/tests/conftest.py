from pathlib import Path

import pytest

from bpp.models import Autor_Dyscyplina, Charakter_Formalny, Wydawnictwo_Zwarte


@pytest.fixture
def fn_test_import_polon():
    return Path(__file__).parent / "test_import_polon.xlsx"


@pytest.fixture
def fn_test_import_polon_bledny():
    return Path(__file__).parent / "test_import_polon_bledny.xlsx"


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


@pytest.fixture
def rodzaj_autora_n(db):
    """Fixture dla rodzaju autora N (pracownik naukowy w liczbie N)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults=dict(
            nazwa="pracownik naukowy w liczbie N",
            jest_w_n=True,
            licz_sloty=True,
            sort=1,
        ),
    )
    return obj


@pytest.fixture
def rodzaj_autora_d(db):
    """Fixture dla rodzaju autora D (doktorant)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="D",
        defaults=dict(nazwa="doktorant", jest_w_n=False, licz_sloty=True, sort=3),
    )
    return obj


@pytest.fixture
def rodzaj_autora_b(db):
    """Fixture dla rodzaju autora B (pracownik badawczy spoza N)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="B",
        defaults=dict(
            nazwa="pracownik badawczy spoza N", jest_w_n=False, licz_sloty=True, sort=2
        ),
    )
    return obj


@pytest.fixture
def rodzaj_autora_z(db):
    """Fixture dla rodzaju autora Z (inny zatrudniony, nie naukowy)"""
    from ewaluacja_common.models import Rodzaj_Autora

    obj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="Z",
        defaults=dict(
            nazwa="inny zatrudniony, nie naukowy",
            jest_w_n=False,
            licz_sloty=False,
            sort=4,
        ),
    )
    return obj
