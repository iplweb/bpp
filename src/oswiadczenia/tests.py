import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Autor_Dyscyplina, Rekord
from oswiadczenia.tasks import sanitize_filename
from oswiadczenia.views import (
    WydrukOswiadczenFilterForm,
    calculate_export_ranges,
    get_autor_dyscyplina_info,
)


def test_wydruk_oswiadczen_filter_form_defaults():
    """Test that filter form provides default values for missing fields."""
    form = WydrukOswiadczenFilterForm(data={})
    assert form.is_valid()
    assert form.cleaned_data["rok_od"] == 2022
    assert form.cleaned_data["rok_do"] == 2025
    assert form.cleaned_data["szukaj_autor"] == ""
    assert form.cleaned_data["szukaj_tytul"] == ""
    assert form.cleaned_data["przypieta"] == ""


def test_wydruk_oswiadczen_filter_form_with_values():
    """Test that filter form accepts valid values."""
    form = WydrukOswiadczenFilterForm(
        data={
            "rok_od": 2023,
            "rok_do": 2024,
            "szukaj_autor": "Kowalski",
            "szukaj_tytul": "publikacja",
            "przypieta": "tak",
        }
    )
    assert form.is_valid()
    assert form.cleaned_data["rok_od"] == 2023
    assert form.cleaned_data["rok_do"] == 2024
    assert form.cleaned_data["szukaj_autor"] == "Kowalski"


def test_wydruk_oswiadczen_filter_form_invalid_rok():
    """Test that filter form rejects invalid year values."""
    form = WydrukOswiadczenFilterForm(data={"rok_od": 2021})  # Min is 2022
    assert not form.is_valid()
    assert "rok_od" in form.errors


def test_calculate_export_ranges_small_count():
    """Test calculate_export_ranges returns empty for small counts."""
    result = calculate_export_ranges(100, chunk_size=5000)
    assert result == []


def test_calculate_export_ranges_large_count():
    """Test calculate_export_ranges returns proper ranges for large counts."""
    result = calculate_export_ranges(12000, chunk_size=5000)
    assert len(result) == 3
    assert result[0] == (0, 5000, "1-5000")
    assert result[1] == (5000, 10000, "5001-10000")
    assert result[2] == (10000, 12000, "10001-12000")


def test_sanitize_filename_removes_invalid_chars():
    """Test that sanitize_filename removes invalid characters."""
    result = sanitize_filename('test/file:name*with?invalid"chars<>|')
    assert "/" not in result
    assert ":" not in result
    assert "*" not in result
    assert "?" not in result
    assert '"' not in result


def test_sanitize_filename_truncates():
    """Test that sanitize_filename truncates to max_length."""
    result = sanitize_filename("a" * 100, max_length=30)
    assert len(result) == 30


@pytest.mark.django_db
def test_get_autor_dyscyplina_info_returns_dict(autor_jan_kowalski, dyscyplina1):
    """Test get_autor_dyscyplina_info returns proper dict structure."""
    # Create Autor_Dyscyplina record
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        rok=2023,
        dyscyplina_naukowa=dyscyplina1,
    )

    result = get_autor_dyscyplina_info(autor_jan_kowalski, 2023)

    assert "ma_dwie_dyscypliny" in result
    assert "dyscyplina_naukowa" in result
    assert "subdyscyplina_naukowa" in result
    assert result["dyscyplina_naukowa"] == dyscyplina1


@pytest.mark.django_db
def test_get_autor_dyscyplina_info_missing():
    """Test get_autor_dyscyplina_info returns defaults for missing record."""
    autor = baker.make(Autor)
    result = get_autor_dyscyplina_info(autor, 2099)

    assert result["ma_dwie_dyscypliny"] is False
    assert result["dyscyplina_naukowa"] is None


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = True
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert (
        b"Wydruk dyscypliny zg" in res.content
        and b"oszonej dla publikacji" in res.content
    )


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_NIE_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = False
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert (
        b"Wydruk dyscypliny zg" not in res.content
        or b"oszonej dla publikacji" not in res.content
    )


@pytest.mark.django_db
def test_praca_tabela_oswiadczenia_nie_drukuj(
    zwarte_z_dyscyplinami,
    admin_client,
    uczelnia,  # noqa
):  # noqa
    uczelnia.drukuj_oswiadczenia = False
    uczelnia.save()

    res = admin_client.get(
        reverse(
            "bpp:browse_rekord",
            args=Rekord.objects.get_for_model(zwarte_z_dyscyplinami).pk,
        ),
        follow=True,
    )
    assert b"<!-- wydruk oswiadczenia -->" not in res.content


@pytest.mark.django_db
def test_oswiadczenie_jedno(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    autor = rekord.autorzy_set.first()
    dyscyplina_pracy = rekord.autorzy_set.first().dyscyplina_naukowa
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, dyscyplina_pracy.pk),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenie_druga_dyscyplina(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    autor = rekord.autorzy_set.first()
    dyscyplina_pracy = rekord.autorzy_set.first().dyscyplina_naukowa
    url = reverse(
        "oswiadczenia:jedno-oswiadczenie-druga-dyscyplina",
        args=(rekord.pk[0], rekord.pk[1], autor.autor.pk, dyscyplina_pracy.pk),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_oswiadczenie_wiele(zwarte_z_dyscyplinami, admin_client):  # noqa
    rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)

    url = reverse(
        "oswiadczenia:wiele-oswiadczen",
        args=(rekord.pk[0], rekord.pk[1]),
    )
    res = admin_client.get(url)
    assert res.status_code == 200
    assert b"window.print" in res.content


@pytest.mark.django_db
def test_remove_old_oswiadczenia_export_files():
    from datetime import timedelta

    from django.utils import timezone
    from model_bakery import baker

    from oswiadczenia.models import OswiadczeniaExportTask
    from oswiadczenia.tasks import remove_old_oswiadczenia_export_files

    # Create a recent task (should NOT be deleted)
    baker.make(OswiadczeniaExportTask)

    # Create an old task (should be deleted)
    old_task = baker.make(OswiadczeniaExportTask)
    old_task.created_at = timezone.now() - timedelta(days=20)
    old_task.save()

    assert OswiadczeniaExportTask.objects.count() == 2

    remove_old_oswiadczenia_export_files()

    assert OswiadczeniaExportTask.objects.count() == 1
