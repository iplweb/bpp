import json

import openpyxl
import pytest
from django.core.management import call_command
from model_mommy import mommy

from ewaluacja2021.models import IloscUdzialowDlaAutora, LiczbaNDlaUczelni

from bpp.models import Autor_Dyscyplina, Wydawnictwo_Ciagle


@pytest.fixture
def genetyczny_3n(uczelnia, autor_jan_nowak, dyscyplina1, jednostka, denorms):
    """
    Duży test integracyjny, sprawdza generowanie raportu genetycznego
    3N na bazie jednej pracy.
    """
    ROK = 2021

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )

    IloscUdzialowDlaAutora.objects.create(
        autor=autor_jan_nowak,
        ilosc_udzialow=10,
        ilosc_udzialow_monografie=10,
        dyscyplina_naukowa=dyscyplina1,
    )

    LiczbaNDlaUczelni.objects.create(
        dyscyplina_naukowa=dyscyplina1, uczelnia=uczelnia, liczba_n=100
    )

    for a in range(20):
        wc: Wydawnictwo_Ciagle = mommy.make(
            Wydawnictwo_Ciagle,
            rok=ROK,
            punkty_kbn=5,
            tytul_oryginalny="Czy z tytułu znikły <i>wszystkie</i> tagi <sup>HTML</sup>?",
        )
        wc.dodaj_autora(autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1)

    denorms.flush()

    return {"dyscyplina": dyscyplina1}


def test_genetyczny(genetyczny_3n):
    """
    Duży test integracyjny, sprawdza generowanie raportu genetycznego
    3N na bazie jednej pracy.
    """

    dyscyplina1 = genetyczny_3n["dyscyplina"]
    call_command("raport_3n_genetyczny", dyscyplina=dyscyplina1.nazwa)

    raport = json.loads(open("genetyczny_memetyka_stosowana.json").read())
    assert len(raport["optimum"]) == 10


def test_genetyczny_zapis_xlsx(genetyczny_3n):
    dyscyplina1 = genetyczny_3n["dyscyplina"]
    call_command("raport_3n_genetyczny", dyscyplina=dyscyplina1.nazwa)
    call_command("raport_3n_to_xlsx", "genetyczny_memetyka_stosowana.json")

    res = openpyxl.load_workbook(
        "genetyczny_memetyka_stosowana_output/AAA_rekordy.xlsx"
    )

    assert (
        res.worksheets[0].cell(15, 3).value
        == "Czy z tytułu znikły wszystkie tagi HTML?"
    )
