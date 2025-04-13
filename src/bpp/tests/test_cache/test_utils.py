import pytest
from model_bakery import baker

from ewaluacja2021.models import (
    IloscUdzialowDlaAutora_2022_2025,
    LiczbaNDlaUczelni_2022_2025,
)

from bpp.models import Autor, Autor_Dyscyplina
from bpp.models.cache.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025


def test_oblicz_liczby_n_dla_ewaluacji_2022_2025_prosty(
    uczelnia,
    autor_jan_nowak,
    dyscyplina1,
):
    ad_kwargs = dict(
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=1,
        procent_dyscypliny=100,
        rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
        rok=2022,
    )
    # Musimy utworzyc tu 12 autorow * 5 aby sprawic, ze dyscyplina1 bedzie
    # miała liczbę N większą od 12. W ten sposób nie zostanie usunięta z wykazu
    # dyscyplin raportowanych:
    for elem in range(12 * 5):
        autor = baker.make(Autor)
        Autor_Dyscyplina.objects.create(autor=autor, **ad_kwargs)

    Autor_Dyscyplina.objects.create(autor=autor_jan_nowak, **ad_kwargs)

    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)

    assert (
        IloscUdzialowDlaAutora_2022_2025.objects.get(
            autor=autor_jan_nowak
        ).ilosc_udzialow
        == 1
    )

    # Liczba N wyniesie wobec tego 12 autorów * 5 = 60 + 1 autor == 61/4 =
    assert (
        LiczbaNDlaUczelni_2022_2025.objects.get(dyscyplina_naukowa=dyscyplina1).liczba_n
        == 15.25
    )


@pytest.mark.parametrize(
    "rodzaj_autora",
    [Autor_Dyscyplina.RODZAJE_AUTORA.D, Autor_Dyscyplina.RODZAJE_AUTORA.Z],
)
def test_oblicz_liczby_n_dla_ewaluacji_2022_2025_autor_to_doktorant(
    rodzaj_autora,
    uczelnia,
    autor_jan_nowak,
    dyscyplina1,
):
    ad_kwargs = dict(
        dyscyplina_naukowa=dyscyplina1,
        wymiar_etatu=1,
        procent_dyscypliny=100,
        rok=2022,
    )
    # Musimy utworzyc tu 12 autorow * 5 aby sprawic, ze dyscyplina1 bedzie
    # miała liczbę N większą od 12. W ten sposób nie zostanie usunięta z wykazu
    # dyscyplin raportowanych:
    for elem in range(12 * 5):
        autor = baker.make(Autor)
        Autor_Dyscyplina.objects.create(
            autor=autor, rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N, **ad_kwargs
        )

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, rodzaj_autora=rodzaj_autora, **ad_kwargs
    )

    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)

    assert (
        IloscUdzialowDlaAutora_2022_2025.objects.get(
            autor=autor_jan_nowak
        ).ilosc_udzialow
        == 1
    )

    # Liczba N wyniesie wobec tego 12 autorów * 5 = 60, zaś autor doktorant NIE zostanie dodany do
    # # liczby N zatem 60/4 = 15.
    assert (
        LiczbaNDlaUczelni_2022_2025.objects.get(dyscyplina_naukowa=dyscyplina1).liczba_n
        == 15
    )
