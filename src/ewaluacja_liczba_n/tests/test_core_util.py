from model_bakery import baker

from ewaluacja2021.core.util import get_lista_prac
from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutora_2022_2025,
    LiczbaNDlaUczelni_2022_2025,
)

from bpp.models import Autor_Dyscyplina, Wydawnictwo_Ciagle


def test_get_lista_prac_zakres_lat(
    autor_jan_nowak, dyscyplina1, jednostka, uczelnia, denorms, typy_odpowiedzialnosci
):
    """Sprawdza, czy lista prac odrzuca prace spoza zakresu 2022-2025"""

    # Zrob dane testowe od 2015 do 2025

    LiczbaNDlaUczelni_2022_2025.objects.create(
        dyscyplina_naukowa=dyscyplina1, uczelnia=uczelnia, liczba_n=100
    )
    IloscUdzialowDlaAutora_2022_2025.objects.create(
        autor=autor_jan_nowak,
        ilosc_udzialow=10,
        ilosc_udzialow_monografie=10,
        dyscyplina_naukowa=dyscyplina1,
    )

    for ROK in range(2015, 2026):
        Autor_Dyscyplina.objects.create(
            autor=autor_jan_nowak, rok=ROK, dyscyplina_naukowa=dyscyplina1
        )

        wc: Wydawnictwo_Ciagle = baker.make(
            Wydawnictwo_Ciagle,
            rok=ROK,
            punkty_kbn=5,
            tytul_oryginalny=f"Test 123 - praca za rok {ROK}",
        )
        wc.dodaj_autora(autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1)

    denorms.flush()

    assert (len(list(get_lista_prac(dyscyplina1.nazwa)))) == 4
