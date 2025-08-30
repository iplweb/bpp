import pytest
from model_bakery import baker

from ewaluacja_liczba_n.models import (
    IloscUdzialowDlaAutora_2022_2025,
    LiczbaNDlaUczelni_2022_2025,
)

from bpp.models import Autor_Dyscyplina, Wydawnictwo_Ciagle


@pytest.fixture
def genetyczny_3n(
    uczelnia,
    autor_jan_nowak,
    dyscyplina1,
    jednostka,
    denorms,
    typ_odpowiedzialnosci_autor,
):
    """
    Duży test integracyjny, sprawdza generowanie raportu genetycznego
    3N na bazie jednej pracy.
    """
    ROK = 2022

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, rok=ROK, dyscyplina_naukowa=dyscyplina1
    )

    IloscUdzialowDlaAutora_2022_2025.objects.create(
        autor=autor_jan_nowak,
        ilosc_udzialow=10,
        ilosc_udzialow_monografie=10,
        dyscyplina_naukowa=dyscyplina1,
    )

    LiczbaNDlaUczelni_2022_2025.objects.create(
        dyscyplina_naukowa=dyscyplina1, uczelnia=uczelnia, liczba_n=100
    )

    for a in range(20):

        wc: Wydawnictwo_Ciagle = baker.make(
            Wydawnictwo_Ciagle,
            rok=ROK,
            punkty_kbn=5,
            tytul_oryginalny="Czy z tytułu znikły <i>wszystkie</i> tagi <sup>HTML</sup>?",
        )
        wc.dodaj_autora(autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1)

    denorms.flush()

    return {"dyscyplina": dyscyplina1}
