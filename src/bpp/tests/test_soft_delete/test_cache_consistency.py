"""Spójność materializowanego cache (bpp_autorzy_mat / model Autorzy) po
soft-delete wierszy *_Autor (Task 4, faza 01).

UWAGA: zwykły ``django_db`` WYSTARCZA — triggery bazodanowe działają
wewnątrz transakcji testowej (kanarki ``test_soft_delete_preconditions.py``
to pokazują: chodzą pod zwykłym ``django_db``, nie ``transactional_db``).
``transactional_db`` jest tu zbędny i tylko spowalnia (osobny kontener/
commit na test zamiast rollbacku transakcji).
"""

import pytest
from django.contrib.contenttypes.models import ContentType

from bpp.models.cache import Autorzy, AutorzyView
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle_Autor


def _autorzy_mat_dla(wca):
    """Wiersze bpp_autorzy_mat (model Autorzy) wskazujące na danego autora
    w danym rekordzie (kolumna rekord_id = [content_type publikacji, pk
    publikacji] -- patrz AutorzyManager.filter_rekord i migracja 0432)."""
    ct = ContentType.objects.get_for_model(type(wca.rekord)).pk
    return Autorzy.objects.filter(
        autor_id=wca.autor_id,
        rekord_id=[ct, wca.rekord_id],
    )


@pytest.mark.django_db
def test_soft_delete_autorstwa_znika_z_mat(
    denorms, wydawnictwo_ciagle_z_dwoma_autorami
):
    """Soft-delete jednego autorstwa: znika WYŁĄCZNIE ten wiersz, z OBU
    warstw (widok źródłowy i mat-view), drugi autor pracy zostaje.

    Wyrocznia: gdyby gałąź kasująca w bpp_refresh_autor_wydawnictwo_ciagle
    zniknęła (albo bramka WHEN przestała znać deleted_at), pierwsza asercja
    po delete() by padła. Gdyby filtr widoku źródłowego zniknął, druga by
    padła. Gdyby kaskada usuwała OBA wiersze zamiast jednego (zły klucz),
    trzecia by padła.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    denorms.flush()
    wca = wc.autorzy_set.first()
    autor_id = wca.autor_id

    # Przed: autor jest w bpp_autorzy_mat ...
    assert _autorzy_mat_dla(wca).exists()
    # ... i w bpp_autorzy (widok źródłowy)
    assert AutorzyView.objects.filter(autor_id=autor_id).exists()

    drugi_autor_id = wc.autorzy_set.exclude(pk=wca.pk).first().autor_id

    wca.delete()  # soft-delete per instancja

    # Po: znika z mat-view (trigger + filtr widoku) ...
    assert not _autorzy_mat_dla(wca).exists()
    # ... i z widoku źródłowego (mechanizm #1)
    assert not AutorzyView.objects.filter(autor_id=autor_id).exists()
    # Drugi autor pracy NIE zniknął (kaskada jest per-instancja, nie per-rekord)
    assert Autorzy.objects.filter(autor_id=drugi_autor_id).exists()


@pytest.mark.django_db
def test_restore_autorstwa_wraca_do_mat(denorms, wydawnictwo_ciagle_z_autorem):
    """restore() na skasowanym autorstwie musi ponownie wstawić wiersz do
    mat-view. Wyrocznia: gdyby restore() nie odpalał tego samego triggera
    UPDATE (np. hipotetyczny bulk .update() z pominięciem save()), druga
    para asercji by padła mimo że deleted_at wróciło do NULL w bazie."""
    wc = wydawnictwo_ciagle_z_autorem
    denorms.flush()
    wca = wc.autorzy_set.first()
    autor_id = wca.autor_id
    pk = wca.pk

    wca.delete()
    assert not Autorzy.objects.filter(autor_id=autor_id).exists()

    Wydawnictwo_Ciagle_Autor.global_objects.get(pk=pk).restore()

    # Restore → re-insert do mat-view
    assert Autorzy.objects.filter(autor_id=autor_id).exists()
    assert AutorzyView.objects.filter(autor_id=autor_id).exists()


@pytest.mark.django_db
def test_edycja_skasowanego_autorstwa_nie_wskrzesza_w_mat(
    denorms, wydawnictwo_ciagle_z_autorem
):
    """Zapis skasowanego wiersza *_Autor (np. zmiana kolejności) NIE wraca
    do bpp_autorzy_mat -- widok źródłowy go odfiltrowuje po własnym
    deleted_at (mechanizm #1), niezależnie od tego, KTÓRA kolumna
    bramkowana zmieniła się przy tym UPDATE-cie.

    Wyrocznia: gdyby gałąź kasująca w funkcji refresh nie kończyła się
    ``RETURN NULL`` (czyli leciała dalej do upsertu), ten test by padł --
    to dokładnie inwariant "delete-first", którego brak dokumentują
    kanarki w test_soft_delete_preconditions.py dla warstwy publikacji.
    """
    wc = wydawnictwo_ciagle_z_autorem
    denorms.flush()
    wca = wc.autorzy_set.first()
    autor_id = wca.autor_id
    pk = wca.pk

    wca.delete()
    assert not Autorzy.objects.filter(autor_id=autor_id).exists()

    # Edycja skasowanego wiersza (przez global_objects, bo objects ukrywa)
    skasowany = Wydawnictwo_Ciagle_Autor.global_objects.get(pk=pk)
    skasowany.kolejnosc = 99
    skasowany.save()  # odpala trigger jako UPDATE z deleted_at NOT NULL

    # Nadal nie ma go w mat-view (kluczowy przypadek brzegowy ze spec §2.1)
    assert not Autorzy.objects.filter(autor_id=autor_id).exists()


@pytest.mark.django_db
def test_queryset_delete_kaskaduje_per_instancja(
    denorms, wydawnictwo_ciagle_z_dwoma_autorami
):
    """.delete() na QuerySet soft-deletuje per instancję (iterator) --
    wszystkie wiersze znikają z mat-view, gate na .update() nie blokuje
    QuerySet.delete() (django-softdelete: SoftDeleteQuerySet.delete()
    woła obj.delete() w pętli, nie bulk .update()).

    Wyrocznia: gdyby .delete() na queryset trafiał w nasz gate z
    soft_delete.py (blokadę bulk .update() na deleted_at/restored_at),
    ten test rzuciłby RuntimeError zamiast przejść. Gdyby kaskada NIE
    była per-instancja (np. bulk UPDATE z pominięciem triggera), pierwsza
    asercja po delete() by padła, a druga (fizyczne przetrwanie wierszy)
    odróżnia to od hard-delete.
    """
    wc = wydawnictwo_ciagle_z_dwoma_autorami
    denorms.flush()
    ct = ContentType.objects.get_for_model(type(wc)).pk
    assert Autorzy.objects.filter(rekord_id=[ct, wc.pk]).count() == 2

    Wydawnictwo_Ciagle_Autor.objects.filter(rekord=wc).delete()

    # Wszystkie autorstwa tej pracy zniknęły z mat-view
    assert not Autorzy.objects.filter(rekord_id=[ct, wc.pk]).exists()
    # ... ale wiersze fizycznie żyją (soft, nie hard)
    assert Wydawnictwo_Ciagle_Autor.global_objects.filter(rekord=wc).count() == 2
