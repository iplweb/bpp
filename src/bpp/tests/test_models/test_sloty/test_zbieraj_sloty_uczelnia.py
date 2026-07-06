import pytest

from bpp.core import zbieraj_sloty


@pytest.mark.django_db
def test_zbieraj_sloty_zaweza_po_uczelni(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia
):
    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()
    autor = zwarte_dwie_uczelnie.autorzy_set.first().autor

    _pkt_all, lista_all, _slot_all = zbieraj_sloty(
        autor.pk,
        1,
        zwarte_dwie_uczelnie.rok,
        zwarte_dwie_uczelnie.rok,
        akcja="wszystko",
    )
    _pkt_u, lista_u, _slot_u = zbieraj_sloty(
        autor.pk,
        1,
        zwarte_dwie_uczelnie.rok,
        zwarte_dwie_uczelnie.rok,
        akcja="wszystko",
        uczelnia_id=jednostka.uczelnia_id,
    )
    assert len(lista_u) <= len(lista_all)
