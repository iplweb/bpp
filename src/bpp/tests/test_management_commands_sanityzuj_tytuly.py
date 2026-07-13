import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_sanityzuj_tytuly_naprawia_xss_i_greke(wydawnictwo_ciagle):
    # Zapis surowego XSS z pominięciem save-hooka (symulacja legacy danych).
    type(wydawnictwo_ciagle).objects.filter(pk=wydawnictwo_ciagle.pk).update(
        tytul_oryginalny="<script>alert(1)</script><i>Genus</i> 17<beta>-ol",
        tytul="",
    )

    call_command("sanityzuj_tytuly", "--napraw")

    wydawnictwo_ciagle.refresh_from_db()
    t = wydawnictwo_ciagle.tytul_oryginalny
    assert "<script>" not in t
    assert "alert(1)" not in t
    assert "<i>Genus</i>" in t
    assert "β" in t


@pytest.mark.django_db
def test_sanityzuj_tytuly_dry_run_nie_zmienia(wydawnictwo_ciagle):
    type(wydawnictwo_ciagle).objects.filter(pk=wydawnictwo_ciagle.pk).update(
        tytul_oryginalny="<script>alert(1)</script>x"
    )

    call_command("sanityzuj_tytuly")  # bez --napraw = tylko raport

    wydawnictwo_ciagle.refresh_from_db()
    assert "<script>" in wydawnictwo_ciagle.tytul_oryginalny
