import pytest
from django.core.exceptions import ValidationError

from bpp.models import (
    Autor_Dyscyplina,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle_Autor,
    parse_informacje_as_dict,
    wez_zakres_stron,
)


@pytest.mark.django_db
def test_baza_modelu_odpowiedzialnosci_zapisywanie(
    wydawnictwo_ciagle,
    autor_jan_nowak,
    rok,
    jednostka,
    dyscyplina1,
    dyscyplina2,
    typy_odpowiedzialnosci,
    db,
):
    wydawnictwo_ciagle.rok = rok
    wydawnictwo_ciagle.save()

    ad = Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        rok=rok,
        dyscyplina_naukowa=dyscyplina1,
        procent_dyscypliny=50,
    )

    wca = Wydawnictwo_Ciagle_Autor.objects.create(
        rekord=wydawnictwo_ciagle,
        autor=autor_jan_nowak,
        jednostka=jednostka,
        typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(skrot="aut."),
        zapisany_jako="Foobar",
        dyscyplina_naukowa=None,
    )
    wca.save()

    wca.clean()

    wca.dyscyplina_naukowa = dyscyplina2
    with pytest.raises(ValidationError):
        wca.clean()

    wca.dyscyplina_naukowa = dyscyplina1
    wydawnictwo_ciagle.rok = 50
    wydawnictwo_ciagle.save()
    with pytest.raises(ValidationError):
        wca.clean()

    wydawnictwo_ciagle.rok = rok
    wydawnictwo_ciagle.save()
    wca.clean()

    ad.dyscyplina_naukowa = dyscyplina2
    ad.subdyscyplina_naukowa = dyscyplina1
    ad.save()
    wca.clean()


@pytest.mark.django_db
def test_baza_modelu_odpowiedzialnosci_autorow_dyscyplina_okresl_dyscypline(
    wydawnictwo_ciagle,
    jednostka,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    typy_odpowiedzialnosci,
    rok,
):
    wca = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, zapisany_jako="Kowalski"
    )
    assert wca.okresl_dyscypline() is None

    Autor_Dyscyplina.objects.create(
        rok=rok,
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina1,
        subdyscyplina_naukowa=dyscyplina2,
    )

    assert wca.okresl_dyscypline() is None

    wca.dyscyplina_naukowa = dyscyplina2
    wca.save()
    assert wca.okresl_dyscypline() == dyscyplina2

    wca.dyscyplina_naukowa = None
    wca.save()
    assert wca.okresl_dyscypline() is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "input,expected",
    [
        ("123", "123"),
        ("123 s.", "123"),
        ("123-123", "123-123"),
        ("s. 35", "35"),
        ("ss. 90", "90"),
        ("ss. 190", "190"),
        ("ss. 290", "290"),
        ("s. 10-20", "10-20"),
        ("tia", None),
        ("s. e27-e53", "e27-e53"),
        ("[b.pag.]", "brak"),
        ("[b. pag.]", "brak"),
        ("[b. pag]", "brak"),
        ("s. 132-153.", "132-153"),
        ("s. 143.", "143"),
        ("aosidfjoaisd fjoiasdjf s. 132-153.", "132-153"),
        ("      s. 143.", "143"),
        ("      s.          143.", "143"),
        ("s. P-29.", "P-29"),
        ("s. PP-4.", "PP-4"),
        # ("s. P-27-P-28.", "P-27-P-28"), # to się nie uda
        ("s. xiii-xiv.", "xiii-xiv"),
    ],
)
def test_eksport_pbn_zakres_stron(input, expected):
    assert wez_zakres_stron(input) == expected


@pytest.mark.django_db
def test_eksport_pbn_zakres_stron_pole(wydawnictwo_ciagle):
    """Przetestuj że w sytuacji, gdy jest wypełnione pole 'Strony', to
    jego wartość idzie do eksportu"""
    wydawnictwo_ciagle.szczegoly = "s. 35"
    wydawnictwo_ciagle.strony = "44-44"
    ret = wydawnictwo_ciagle.zakres_stron()
    assert ret == "44-44"

    wydawnictwo_ciagle.strony = None
    ret = wydawnictwo_ciagle.zakres_stron()
    assert ret == "35"


@pytest.mark.django_db
def test_eksport_pbn_get_issue(wydawnictwo_ciagle):
    wydawnictwo_ciagle.nr_zeszytu = "10"
    assert wydawnictwo_ciagle.numer_wydania() == "10"

    wydawnictwo_ciagle.nr_zeszytu = None
    wydawnictwo_ciagle.informacje = "1993 z. 5"
    assert wydawnictwo_ciagle.numer_wydania() == "5"


@pytest.mark.django_db
def test_eksport_pbn_get_volume(wydawnictwo_ciagle):
    wydawnictwo_ciagle.tom = "10"
    assert wydawnictwo_ciagle.numer_tomu() == "10"

    wydawnictwo_ciagle.tom = None
    wydawnictwo_ciagle.informacje = "1992 vol. 5"
    assert wydawnictwo_ciagle.numer_tomu() == "5"


@pytest.mark.parametrize(
    "input,exp_rok,exp_tom,exp_nr",
    [
        ("1960", "1960", None, None),
        ("1960 t. 8", "1960", "8", None),
        ("1960 t 8", "1960", "8", None),
        ("1960 nr 2", "1960", None, "2"),
        ("1960 nr. 2", "1960", None, "2"),
        ("1960 t. 8 nr 2", "1960", "8", "2"),
        ("1960 T. 8 nr 2", "1960", "8", "2"),
        ("1960 T.8nr2", "1960", "8", "2"),
        ("1960 T.8 nr 2", "1960", "8", "2"),
        ("2018 Vol.77 suppl.2", "2018", "77", "suppl.2"),
        ("2020 T. [59] supl.", "2020", "59", "supl."),
        ("2020 Vol.61 no.7-12 supl.5", "2020", "61", "7-12 supl.5"),
        ("2020 Vol. A74 [suppl.]", "2020", "A74", "[suppl.]"),
        ("2020 voL 54 SuPPl. 45", "2020", "54", "SuPPl. 45"),
        ("2018 Vol.48 suppl.", "2018", "48", "suppl."),
        ("2020 Vol.60 supl.3", "2020", "60", "supl.3"),
        ("2020 supl. 2/1", "2020", None, "supl. 2/1"),
        ("2018 Vol.72 no.13 suppl.B", "2018", "72", "13 suppl.B"),
        ("2018 Vol.35 e-suppl.56", "2018", "35", "e-suppl.56"),
        ("2020 Vol.61 no.2 suppl.2", "2020", "61", "2 suppl.2"),
        ("2020 Vol.15 no.5 suppl.", "2020", "15", "5 suppl."),
        ("1998 Vol.4 suppl.2, fig., bibliogr. 11 poz., summ.", "1998", "4", "suppl.2"),
    ],
)
def test_parse_informacje(input, exp_rok, exp_tom, exp_nr):
    res = parse_informacje_as_dict(input)
    assert res.get("rok") == exp_rok
    assert res.get("tom") == exp_tom
    assert res.get("numer") == exp_nr
