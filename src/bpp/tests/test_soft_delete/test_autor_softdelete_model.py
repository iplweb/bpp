"""*_Autor jako SoftDeleteModel: pola, managery, soft-delete/restore per
instancja (bez sprawdzania cache — to Task 4)."""

import pytest
from django_softdelete.models import SoftDeleteModel

from bpp.models.patent import Patent_Autor
from bpp.models.soft_delete import BppGlobalManager, BppSoftDeleteManager
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor

THROUGH_MODELE = [
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte_Autor,
    Patent_Autor,
]


@pytest.mark.parametrize("klass", THROUGH_MODELE)
def test_through_jest_softdeletemodel(klass):
    assert issubclass(klass, SoftDeleteModel)


@pytest.mark.parametrize("klass", THROUGH_MODELE)
def test_through_ma_pola_soft_delete(klass):
    nazwy = {f.name for f in klass._meta.get_fields()}
    assert {"deleted_at", "restored_at", "transaction_id"} <= nazwy


@pytest.mark.parametrize("klass", THROUGH_MODELE)
def test_through_ma_nasze_managery(klass):
    assert isinstance(klass.objects, BppSoftDeleteManager)
    assert isinstance(klass.global_objects, BppGlobalManager)


@pytest.mark.django_db
def test_soft_delete_ukrywa_w_objects_widoczne_w_global(
    wydawnictwo_ciagle_z_autorem,
):
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    pk = wca.pk
    wca.delete()
    assert not Wydawnictwo_Ciagle_Autor.objects.filter(pk=pk).exists()
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(pk=pk).exists()
    assert Wydawnictwo_Ciagle_Autor.deleted_objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_restore_przywraca_do_objects(wydawnictwo_ciagle_z_autorem):
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    pk = wca.pk
    wca.delete()
    Wydawnictwo_Ciagle_Autor.global_objects.get(pk=pk).restore()
    assert Wydawnictwo_Ciagle_Autor.objects.filter(pk=pk).exists()


def test_zgloszenie_publikacji_autor_nie_jest_soft_delete():
    """Czwarty potomek abstraktu jest POZA zakresem soft-delete."""
    from django_softdelete.models import SoftDeleteModel

    from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

    assert not issubclass(Zgloszenie_Publikacji_Autor, SoftDeleteModel)
    assert not hasattr(Zgloszenie_Publikacji_Autor, "global_objects")
