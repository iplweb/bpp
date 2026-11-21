"""Autor w koszu nie liczy się do liczby N — po PRZELICZENIU.

Kosz/przywrócenie autora nie zmienia N automatycznie (jak ewaluacja,
liczbę N przelicza się ręcznie); przeliczenie pomija autorów z kosza.
"""

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok
from ewaluacja_liczba_n.utils import oblicz_liczby_n_dla_okresu


@pytest.mark.django_db
def test_przeliczenie_n_pomija_autora_z_kosza(
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

    oblicz_liczby_n_dla_okresu(uczelnia, rok_min=2022, rok_max=2025)
    w_koszu.delete()
    oblicz_liczby_n_dla_okresu(uczelnia, rok_min=2022, rok_max=2025)

    assert set(
        IloscUdzialowDlaAutoraZaRok.objects.values_list("autor_id", flat=True)
    ) == {zywy.pk}
