"""Shared fixtures for pbn_wysylka_oswiadczen tests."""

import pytest


@pytest.fixture
def publication_with_pbn_uid(
    uczelnia,
    jednostka,
    autor_jan_nowak,
    dyscyplina1,
    jezyki,
    charaktery_formalne,
    typy_kbn,
    statusy_korekt,
    typy_odpowiedzialnosci,
):
    """Create a publication that matches get_publications_queryset criteria."""
    from model_bakery import baker

    from bpp.models import Autor_Dyscyplina, Wydawnictwo_Ciagle

    # Create PBN publication UID
    pbn_pub = baker.make("pbn_api.Publication")

    # Create the publication
    wyd = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Publication of ionic liquids",
        rok=2022,
        pbn_uid=pbn_pub,
    )

    # Set up author discipline
    Autor_Dyscyplina.objects.get_or_create(
        autor=autor_jan_nowak,
        dyscyplina_naukowa=dyscyplina1,
        rok=2022,
    )

    # Add author to publication with discipline
    autor_wyd = wyd.dodaj_autora(
        autor_jan_nowak,
        jednostka,
        dyscyplina_naukowa=dyscyplina1,
        afiliuje=True,
    )
    # Set zatrudniony separately (defaults to False)
    autor_wyd.zatrudniony = True
    autor_wyd.save()

    return wyd
