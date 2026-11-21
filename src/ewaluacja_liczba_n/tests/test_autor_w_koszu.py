"""Autor w koszu nie liczy się do liczby N (decyzja właściciela).

Autor w koszu zachowuje dane kadrowe (``Autor_Dyscyplina``), więc bez
filtra jego udziały dalej podbijałyby N i kalkulator.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_ewaluacji_2022_2025


@pytest.mark.django_db
def test_udzialy_autora_z_kosza_nie_licza_sie_do_n(
    uczelnia, jednostka, dyscyplina1, rodzaj_autora_n
):
    jednostka.skupia_pracownikow = True
    jednostka.save()
    zywy = baker.make(Autor, aktualna_jednostka=jednostka)
    w_koszu = baker.make(Autor, aktualna_jednostka=jednostka)
    for autor in (zywy, w_koszu):
        Autor_Dyscyplina.objects.create(
            autor=autor,
            dyscyplina_naukowa=dyscyplina1,
            wymiar_etatu=1,
            procent_dyscypliny=100,
            rodzaj_autora=rodzaj_autora_n,
            rok=2022,
        )

    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)
    assert IloscUdzialowDlaAutoraZaRok.objects.filter(autor=w_koszu).exists()

    w_koszu.delete()
    # Wyliczone wcześniej udziały znikają od razu (menedżer)...
    assert not IloscUdzialowDlaAutoraZaRok.objects.filter(autor=w_koszu).exists()

    # ...a przeliczenie nie tworzy nowych.
    oblicz_liczby_n_dla_ewaluacji_2022_2025(uczelnia)
    assert set(
        IloscUdzialowDlaAutoraZaRok.objects.values_list("autor_id", flat=True)
    ) == {zywy.pk}
