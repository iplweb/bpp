"""Basic view tests for ewaluacja_optymalizuj_publikacje."""

import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Dyscyplina_Naukowa,
    Jednostka,
    Typ_Odpowiedzialnosci,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
)
from ewaluacja_metryki.models import MetrykaAutora


@pytest.mark.django_db
def test_optymalizuj_publikacje_view_without_metryka_autora(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that the view handles missing MetrykaAutora gracefully"""
    # Create necessary objects
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Informatyka")

    # Create Autor_Dyscyplina for the year
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Create publication
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test publikacja bez metryki",
        rok=2023,
        punkty_kbn=100,
    )

    # Get or create Typ_Odpowiedzialnosci
    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    # Add author to publication with pinned discipline
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    # Ensure denormalization is complete
    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Explicitly ensure there is NO MetrykaAutora for this author
    MetrykaAutora.objects.filter(autor=autor).delete()

    # Test the view using the wydawnictwo's slug
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url)

    # Check that the view returns successfully
    assert response.status_code == 200

    # Check that the context contains the expected data
    assert "publikacja" in response.context
    assert "autorzy_po_dyscyplinach" in response.context

    # Check author data
    autorzy_po_dyscyplinach = response.context["autorzy_po_dyscyplinach"]
    assert len(autorzy_po_dyscyplinach) == 1

    dyscyplina_group = autorzy_po_dyscyplinach[0]
    assert dyscyplina_group["dyscyplina"]["nazwa"] == dyscyplina.nazwa

    autorzy_data = dyscyplina_group["autorzy"]
    assert len(autorzy_data) == 1

    autor_data = autorzy_data[0]
    assert autor_data["autor"] == autor
    assert autor_data["dyscyplina"] == dyscyplina
    assert autor_data["metryka_id"] is None  # MetrykaAutora doesn't exist
    assert autor_data["metryka_missing"] is True
    assert autor_data["metryka"] is None

    # Check that the template renders correctly with missing metryka
    content = response.content.decode("utf-8")
    assert "Kowalski Jan" in content
    assert "Metryka autora nie istnieje" in content
    assert "Sprawdź status generowania metryk" in content
    # Check for the actual rendered URLs
    assert "/ewaluacja_metryki/" in content  # Link to lista
    assert "/ewaluacja_metryki/status-generowania/" in content  # Link to status page

    # Check that the metrics section shows appropriate message
    assert "Brak danych metryki dla tego autora" in content


@pytest.mark.django_db
def test_optymalizuj_publikacje_view_with_metryka_autora(
    admin_client, denorms, rodzaj_autora_n
):
    """Test that the view works correctly when MetrykaAutora exists"""
    # Create necessary objects
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Matematyka")

    # Create Autor_Dyscyplina for the year
    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    # Create MetrykaAutora
    metryka = baker.make(
        MetrykaAutora,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        punkty_nazbierane=250.50,
        slot_nazbierany=2.5,
        slot_maksymalny=4,
        slot_wszystkie=3,  # Provide explicit value
        punkty_wszystkie=300,  # Provide explicit value
        _fill_optional=False,  # Don't fill optional fields with random data
    )

    # Create publication
    wydawnictwo = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test publikacja z metryką",
        rok=2023,
        punkty_kbn=100,
    )

    # Get or create Typ_Odpowiedzialnosci
    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    # Add author to publication
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        afiliuje=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    # Ensure denormalization is complete
    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Test the view using the wydawnictwo's slug
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url)

    # Check that the view returns successfully
    assert response.status_code == 200

    # Check author data
    autorzy_po_dyscyplinach = response.context["autorzy_po_dyscyplinach"]
    assert len(autorzy_po_dyscyplinach) == 1

    dyscyplina_group = autorzy_po_dyscyplinach[0]
    assert dyscyplina_group["dyscyplina"]["nazwa"] == dyscyplina.nazwa

    autorzy_data = dyscyplina_group["autorzy"]
    assert len(autorzy_data) == 1

    autor_data = autorzy_data[0]
    assert autor_data["autor"] == autor
    assert autor_data["metryka_id"] == metryka.pk
    assert autor_data["metryka_missing"] is False
    assert autor_data["metryka"] is not None
    assert autor_data["metryka"]["punkty_nazbierane"] == 250.50

    # Check that the template renders correctly with metryka
    content = response.content.decode("utf-8")
    assert "Nowak Anna" in content

    # Check that there IS a link to metryka details
    assert f"/ewaluacja_metryki/szczegoly/{autor.slug}/{dyscyplina.kod}/" in content

    # Ensure the warning messages are NOT present
    assert "Metryka autora nie istnieje" not in content
    assert "Sprawdź status generowania metryk" not in content

    # Check that metrics data is displayed (not the "Brak danych" message)
    assert "Brak danych metryki dla tego autora" not in content


@pytest.mark.django_db
def test_optymalizuj_publikacje_htmx_request_without_metryka(
    admin_client, denorms, rodzaj_autora_n
):
    """Test HTMX request handling when MetrykaAutora doesn't exist"""
    # Create minimal test data
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor = baker.make(Autor)
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    baker.make(
        Autor_Dyscyplina,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2023,
        rodzaj_autora=rodzaj_autora_n,
    )

    wydawnictwo = baker.make(Wydawnictwo_Ciagle, rok=2023)

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka,
        dyscyplina_naukowa=dyscyplina,
        przypieta=True,
        typ_odpowiedzialnosci=typ_odp,
    )

    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Ensure no MetrykaAutora exists
    MetrykaAutora.objects.filter(autor=autor).delete()

    # Test HTMX request using the wydawnictwo's slug
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url, headers={"HX-Request": "true"})

    # Check that the response is successful
    assert response.status_code == 200

    # Check that the response handles missing MetrykaAutora
    content = response.content.decode("utf-8")
    assert "Metryka autora nie istnieje" in content

    # In HTMX request, we should get the content wrapper without the full page
    assert '<div id="content-wrapper"' in content
    assert "<!DOCTYPE html>" not in content  # Should not have full HTML page


@pytest.mark.django_db
def test_optymalizuj_publikacje_multiple_authors_mixed_metryka(
    admin_client, denorms, rodzaj_autora_n
):
    """Test view with multiple authors where some have MetrykaAutora and some don't"""
    jednostka = baker.make(Jednostka, skupia_pracownikow=True)
    autor1 = baker.make(Autor, nazwisko="Autor", imiona="Pierwszy")
    autor2 = baker.make(Autor, nazwisko="Autor", imiona="Drugi")
    dyscyplina = baker.make(Dyscyplina_Naukowa)

    # Create Autor_Dyscyplina for both authors
    for autor in [autor1, autor2]:
        baker.make(
            Autor_Dyscyplina,
            autor=autor,
            dyscyplina_naukowa=dyscyplina,
            rok=2023,
            rodzaj_autora=rodzaj_autora_n,
        )

    # Create MetrykaAutora only for autor1
    # Provide explicit values to prevent overflow in procent_wykorzystania_slotow field
    metryka1 = baker.make(
        MetrykaAutora,
        autor=autor1,
        dyscyplina_naukowa=dyscyplina,
        jednostka=jednostka,
        slot_maksymalny=4,  # Maximum slots
        slot_nazbierany=2,  # Used slots (less than max)
        punkty_nazbierane=100,  # Points collected
        slot_wszystkie=3,  # All slots
        punkty_wszystkie=120,  # All points
        _fill_optional=False,  # Don't fill optional fields with random data
    )
    # Explicitly ensure autor2 has no MetrykaAutora
    MetrykaAutora.objects.filter(autor=autor2).delete()

    # Create publication with both authors
    wydawnictwo = baker.make(Wydawnictwo_Ciagle, rok=2023)

    typ_odp, _ = Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )

    for idx, autor in enumerate([autor1, autor2]):
        baker.make(
            Wydawnictwo_Ciagle_Autor,
            rekord=wydawnictwo,
            autor=autor,
            jednostka=jednostka,
            dyscyplina_naukowa=dyscyplina,
            przypieta=True,
            typ_odpowiedzialnosci=typ_odp,
            kolejnosc=idx,  # Set unique kolejnosc for each author
        )

    denorms.flush()
    wydawnictwo.refresh_from_db()

    # Test the view using the wydawnictwo's slug
    url = reverse(
        "ewaluacja_optymalizuj_publikacje:optymalizuj", args=(wydawnictwo.slug,)
    )
    response = admin_client.get(url)

    assert response.status_code == 200

    # Check that both authors are in the context
    autorzy_po_dyscyplinach = response.context["autorzy_po_dyscyplinach"]
    assert len(autorzy_po_dyscyplinach) == 1  # Both authors have same discipline

    dyscyplina_group = autorzy_po_dyscyplinach[0]
    assert dyscyplina_group["dyscyplina"]["nazwa"] == dyscyplina.nazwa

    autorzy_data = dyscyplina_group["autorzy"]
    assert len(autorzy_data) == 2

    # Find which is which
    autor1_data = next(ad for ad in autorzy_data if ad["autor"] == autor1)
    autor2_data = next(ad for ad in autorzy_data if ad["autor"] == autor2)

    # Check autor1 has metryka
    assert autor1_data["metryka_id"] == metryka1.pk
    assert autor1_data["metryka_missing"] is False
    assert autor1_data["metryka"] is not None

    # Check autor2 doesn't have metryka
    assert autor2_data["metryka_id"] is None
    assert autor2_data["metryka_missing"] is True
    assert autor2_data["metryka"] is None

    # Check the rendered content
    content = response.content.decode("utf-8")

    # autor1 should have a link to metryka details
    assert f"/ewaluacja_metryki/szczegoly/{autor1.slug}/{dyscyplina.kod}/" in content

    # At least one warning should be present (for autor2)
    assert "Metryka autora nie istnieje" in content
