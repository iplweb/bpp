from bpp.models import Dyscyplina_Zrodla


def test_Dyscyplina_Zrodla___str__(zrodlo, dyscyplina1):
    dz = Dyscyplina_Zrodla.objects.create(zrodlo=zrodlo, dyscyplina=dyscyplina1)
    assert (
        str(dz)
        == 'Przypisanie dyscypliny "memetyka stosowana (1.1)" do źródła "Testowe Źródło"'
    )
