import pytest

from zglos_publikacje.models import Zgloszenie_Publikacji


@pytest.fixture
def zgloszenie_publikacji(
    typy_odpowiedzialnosci, autor_jan_kowalski, jednostka, rok
) -> Zgloszenie_Publikacji:
    z = Zgloszenie_Publikacji.objects.create(
        tytul_oryginalny="test",
        rok=rok,
        email="foo@bar.pl",
        rodzaj_zglaszanej_publikacji=Zgloszenie_Publikacji.Rodzaje.POZOSTALE,
        strona_www="https://onet.pl/",
    )

    z.zgloszenie_publikacji_autor_set.create(
        autor=autor_jan_kowalski,
        jednostka=jednostka,
        typ_odpowiedzialnosci=typy_odpowiedzialnosci["aut."],
        rok=rok,
    )

    return z


@pytest.fixture
def zgloszenie_publikacji_z_oplata(zgloszenie_publikacji) -> Zgloszenie_Publikacji:
    zgloszenie_publikacji.opl_pub_cost_free = False
    zgloszenie_publikacji.opl_pub_amount = 20000
    zgloszenie_publikacji.opl_pub_research_potential = True
    zgloszenie_publikacji.save()
    return zgloszenie_publikacji
