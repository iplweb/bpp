import pytest


@pytest.mark.django_db
def test_zaktualizuj_cache_ciagle(django_assert_num_queries, wydawnictwo_ciagle_z_dwoma_autorami,
                                  wydawnictwo_zwarte_z_autorem):
    with django_assert_num_queries(2):
        wydawnictwo_ciagle_z_dwoma_autorami.zaktualizuj_cache()


@pytest.mark.django_db
def test_zaktualizuj_cache_zwarte(django_assert_num_queries, wydawnictwo_zwarte_z_autorem):
    with django_assert_num_queries(2):
        wydawnictwo_zwarte_z_autorem.zaktualizuj_cache()
