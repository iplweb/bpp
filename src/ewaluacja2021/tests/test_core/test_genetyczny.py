import json

import openpyxl
from django.core.management import call_command


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
