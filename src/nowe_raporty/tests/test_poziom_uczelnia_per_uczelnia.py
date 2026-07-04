import pytest
from model_bakery import baker

from nowe_raporty.poziomy import _base_uczelnia


@pytest.mark.django_db
def test_base_uczelnia_wyklucza_obca_uczelnie(
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    autor_uczelnia1,
    autor_uczelnia2,
):
    w1 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="MOJA")
    w1.dodaj_autora(autor_uczelnia1, jednostka_uczelnia1)
    w2 = baker.make("bpp.Wydawnictwo_Ciagle", tytul_oryginalny="OBCA")
    w2.dodaj_autora(autor_uczelnia2, jednostka_uczelnia2)

    tytuly = set(
        _base_uczelnia(uczelnia1, tylko_afiliowane=False).values_list(
            "tytul_oryginalny", flat=True
        )
    )
    assert "MOJA" in tytuly
    assert "OBCA" not in tytuly
