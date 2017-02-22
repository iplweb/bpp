# -*- encoding: utf-8 -*-
from model_mommy import mommy

from bpp.models.abstract import BRAK_PAGINACJI
from bpp.models.struktura import Jednostka, Wydzial
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor
import pytest

def test_eksport_pbn_author_afiliacja_w_kontekscie_wydzialu(uczelnia, autor_jan_kowalski, wydawnictwo_zwarte):
    w1 = mommy.make(Wydzial, uczelnia=uczelnia)
    w2 = mommy.make(Wydzial, uczelnia=uczelnia)

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=uczelnia)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=uczelnia)

    # Przypisz autora do DWÓCH jednostek z różnych wydziałów
    autor_jan_kowalski.dodaj_jednostke(j1)
    autor_jan_kowalski.dodaj_jednostke(j2)

    # W pracy określ afiliację do drugiego wydziału
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, j2)

    # I teraz:
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_author(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 0

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_contributors(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "1"

    # Zaś dla drugiego wydziału
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_author(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 1

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_contributors(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "0"


def test_eksport_pbn_editor_afiliacja_w_kontekscie_wydzialu(uczelnia, autor_jan_kowalski, wydawnictwo_zwarte):
    w1 = mommy.make(Wydzial, uczelnia=uczelnia)
    w2 = mommy.make(Wydzial, uczelnia=uczelnia)

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=uczelnia)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=uczelnia)

    # Przypisz autora do DWÓCH jednostek z różnych wydziałów
    autor_jan_kowalski.dodaj_jednostke(j1)
    autor_jan_kowalski.dodaj_jednostke(j2)

    # W pracy określ afiliację do drugiego wydziału
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, j2, typ_odpowiedzialnosci_skrot="red.")

    # I teraz:
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_editor(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 0

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_contributors(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "0"

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_editors(toplevel, w1, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "1"

    # Zaś dla drugiego wydziału
    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_editor(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert len(toplevel) == 1

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_contributors(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "0"

    toplevel = []
    wydawnictwo_zwarte.eksport_pbn_other_editors(toplevel, w2, Wydawnictwo_Zwarte_Autor)
    assert toplevel[0].text == "0"


@pytest.mark.parametrize(
    "input,expected",
    [("s. 35", "35"),
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
     ("s. xiii-xiv.", "xiii-xiv")
     ])
def test_eksport_pbn_zakres_stron(input, expected, wydawnictwo_ciagle):
    wydawnictwo_ciagle.szczegoly = input
    ret = wydawnictwo_ciagle.eksport_pbn_zakres_stron()
    assert ret == expected