"""*_Autor jako SoftDeleteModel: pola, managery, soft-delete/restore per
instancja (bez sprawdzania cache — to Task 4)."""

import pytest
from django_softdelete.managers import DeletedManager
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


@pytest.mark.django_db
def test_restore_z_deleted_objects_nie_rzuca(wydawnictwo_ciagle_z_autorem):
    """`deleted_objects.restore()` (ścieżka querysetowa) nie może rzucić
    SoftDeleteException tylko dlatego, że Autor/Jednostka/rekord nie są
    same SoftDeleteModel — patrz inwariant w docstringu soft_delete.py."""
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    pk = wca.pk
    wca.delete()
    Wydawnictwo_Ciagle_Autor.deleted_objects.filter(pk=pk).restore()
    assert Wydawnictwo_Ciagle_Autor.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_restore_z_global_objects_nie_rzuca(wydawnictwo_ciagle_z_autorem):
    """`global_objects.restore()` (druga ścieżka querysetowa) — to samo."""
    wca = wydawnictwo_ciagle_z_autorem.autorzy_set.first()
    pk = wca.pk
    wca.delete()
    Wydawnictwo_Ciagle_Autor.global_objects.filter(pk=pk).restore()
    assert Wydawnictwo_Ciagle_Autor.objects.filter(pk=pk).exists()


@pytest.mark.django_db
def test_autorzy_set_ukrywa_soft_deleted_widoczne_w_global(
    wydawnictwo_ciagle_z_dwoma_autorami,
):
    """`_default_manager` podmieniony na `BppSoftDeleteManager` realnie
    ukrywa soft-deletowany wiersz również przez odwrotną relację
    `rekord.autorzy_set` (reverse FK manager dziedziczy z
    `_default_manager` modelu)."""
    wca = wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.first()
    pk = wca.pk
    wca.delete()
    assert not wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.filter(pk=pk).exists()
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(pk=pk).exists()


@pytest.mark.parametrize("klass", THROUGH_MODELE)
def test_deleted_objects_jest_deletedmanager(klass):
    assert isinstance(klass.deleted_objects, DeletedManager)


@pytest.mark.django_db
def test_deleted_objects_zwraca_tylko_skasowane(wydawnictwo_ciagle_z_dwoma_autorami):
    wca_pozostaje, wca_kasowany = list(
        wydawnictwo_ciagle_z_dwoma_autorami.autorzy_set.all()
    )
    wca_kasowany.delete()

    skasowane_pk = set(
        Wydawnictwo_Ciagle_Autor.deleted_objects.values_list("pk", flat=True)
    )
    assert skasowane_pk == {wca_kasowany.pk}
    assert wca_pozostaje.pk not in skasowane_pk


@pytest.mark.django_db
def test_gate_update_deleted_at_rzuca_na_konkretnym_modelu(
    wydawnictwo_ciagle_z_autorem,
):
    """Gate z Taska 1 był testowany tylko na `BppSoftDeleteQuerySet` w
    izolacji (`test_managers.py`) — tu sprawdzamy, że faktycznie działa na
    realnym queryset-cie konkretnego modelu, przez `objects`."""
    with pytest.raises(RuntimeError, match="Nie ustawiaj deleted_at"):
        Wydawnictwo_Ciagle_Autor.objects.filter(
            pk=wydawnictwo_ciagle_z_autorem.autorzy_set.first().pk
        ).update(deleted_at="2026-06-04")


def test_zgloszenie_publikacji_autor_nie_jest_soft_delete():
    """Czwarty potomek abstraktu jest POZA zakresem soft-delete."""
    from django_softdelete.models import SoftDeleteModel

    from zglos_publikacje.models import Zgloszenie_Publikacji_Autor

    assert not issubclass(Zgloszenie_Publikacji_Autor, SoftDeleteModel)
    assert not hasattr(Zgloszenie_Publikacji_Autor, "global_objects")
