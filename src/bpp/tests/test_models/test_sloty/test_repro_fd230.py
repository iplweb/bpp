"""Repro test dla FD#230 — złe naliczenie punktów dla redakcji monografii HST.

Dla rekordu MIESZANEGO (autorzy z dyscyplin HST oraz nie-HST), redakcja
monografii na poziomie 1 wydawcy musi naliczać autorowi HST mnożnik x2
(40 pkt zamiast 20). Wcześniej kod stosował tu mnożnik x1.0, co było błędem.

Patrz: src/bpp/models/sloty/wydawnictwo_zwarte.py, klasa Prog2 (poziom 1):
    PK 20 + książka redakcja (HST 40).
"""

import pytest

from bpp.models.sloty.core import ISlot
from bpp.models.sloty.wydawnictwo_zwarte import (
    SlotKalkulator_Wydawnictwo_Zwarte_Prog2,
)


@pytest.mark.django_db
def test_fd230_redakcja_hst_oraz_nie_hst_prog_1_ze_zwiekszaniem(
    zwarte_z_dyscyplinami_hst_oraz_nie_hst, rok, typ_odpowiedzialnosci_redaktor
):
    """Redakcja monografii, poziom wydawcy 1, rekord mieszany HST/nie-HST.

    Autor z dyscypliny HST powinien dostać x2 bazy (40), autor nie-HST bazę.
    """
    from bpp.tests.test_models.test_sloty.test_sloty_wydawnictwo_zwarte import (
        powiel_wpisy_dyscyplin_autorow,
    )

    wydawca = zwarte_z_dyscyplinami_hst_oraz_nie_hst.wydawca
    wydawca.poziom_wydawcy_set.create(rok=2022, poziom=1)

    zwarte_z_dyscyplinami_hst_oraz_nie_hst.rok = 2022
    # punktacja bazowa dla redakcji na poziomie 1 (mieszany rekord)
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.punkty_kbn = 20
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.save()

    # przypisania dyscyplin autorów na rok 2022
    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami_hst_oraz_nie_hst, rok, 2022)

    # redakcja monografii: oboje autorzy jako redaktorzy
    for autor in zwarte_z_dyscyplinami_hst_oraz_nie_hst.autorzy_set.all():
        autor.typ_odpowiedzialnosci = typ_odpowiedzialnosci_redaktor
        autor.save()

    i = ISlot(zwarte_z_dyscyplinami_hst_oraz_nie_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)

    autorzy = list(zwarte_z_dyscyplinami_hst_oraz_nie_hst.autorzy_set.all())
    # autorzy[0] = HST (dyscyplina1_hst), autorzy[1] = nie-HST (dyscyplina2)
    pkd_hst = i.pkd_dla_autora(autorzy[0])
    pkd_nie_hst = i.pkd_dla_autora(autorzy[1])

    # autor HST: x2 bazy nie-HST
    assert pkd_hst == pkd_nie_hst * 2
