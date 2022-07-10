import pytest
from model_bakery import baker

from ewaluacja2021.models import IloscUdzialowDlaAutora, LiczbaNDlaUczelni

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

        wc: Wydawnictwo_Ciagle = baker.make(
            Wydawnictwo_Ciagle,
            rok=ROK,
            punkty_kbn=5,
            tytul_oryginalny="Czy z tytułu znikły <i>wszystkie</i> tagi <sup>HTML</sup>?",
        )
        wc.dodaj_autora(autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1)

    denorms.flush()

    return {"dyscyplina": dyscyplina1}
