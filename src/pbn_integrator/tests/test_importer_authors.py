"""
Tests for pbn_integrator.importer.authors module.

These tests verify the author import logic, specifically:
- _przetworz_afiliacje function with default_typ_odpowiedzialnosci parameter
- Correct handling of editors vs authors when affiliation data is missing
"""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from bpp.models import Typ_Odpowiedzialnosci, Uczelnia


@pytest.fixture
def typ_autor(db):
    """Get or create 'autor' responsibility type."""
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="autor", defaults={"skrot": "aut."}
    )[0]


@pytest.fixture
def typ_redaktor(db):
    """Get or create 'redaktor' responsibility type."""
    return Typ_Odpowiedzialnosci.objects.get_or_create(
        nazwa="redaktor", defaults={"skrot": "red."}
    )[0]


@pytest.fixture
def uczelnia_with_obca_jednostka(db):
    """Create Uczelnia with obca_jednostka."""
    uczelnia = Uczelnia.objects.first()
    if uczelnia is None:
        uczelnia = baker.make(Uczelnia)

    if uczelnia.obca_jednostka is None:
        from bpp.models import Jednostka

        obca = baker.make(
            Jednostka,
            uczelnia=uczelnia,
            nazwa="Obca jednostka",
            skupia_pracownikow=False,  # Required for obca_jednostka
        )
        uczelnia.obca_jednostka = obca
        uczelnia.save()

    return uczelnia


@pytest.mark.django_db
class TestPrzetworzAfiliacje:
    """Tests for _przetworz_afiliacje function."""

    def test_returns_default_typ_when_no_affiliation_and_no_default(
        self, typ_autor, typ_redaktor, uczelnia_with_obca_jednostka
    ):
        """When affiliation is None and no default provided, returns autor."""
        from pbn_integrator.importer.authors import _przetworz_afiliacje

        jednostka, afiliuje, typ = _przetworz_afiliacje(
            ta_afiliacja=None,
            default_jednostka=None,
            typ_odpowiedzialnosci_autor=typ_autor,
            typ_odpowiedzialnosci_redaktor=typ_redaktor,
        )

        assert typ == typ_autor
        assert afiliuje is False

    def test_returns_default_typ_when_no_affiliation_with_autor_default(
        self, typ_autor, typ_redaktor, uczelnia_with_obca_jednostka
    ):
        """When affiliation is None and default is autor, returns autor."""
        from pbn_integrator.importer.authors import _przetworz_afiliacje

        jednostka, afiliuje, typ = _przetworz_afiliacje(
            ta_afiliacja=None,
            default_jednostka=None,
            typ_odpowiedzialnosci_autor=typ_autor,
            typ_odpowiedzialnosci_redaktor=typ_redaktor,
            default_typ_odpowiedzialnosci=typ_autor,
        )

        assert typ == typ_autor
        assert afiliuje is False

    def test_returns_default_typ_when_no_affiliation_with_redaktor_default(
        self, typ_autor, typ_redaktor, uczelnia_with_obca_jednostka
    ):
        """When affiliation is None and default is redaktor, returns redaktor.

        This is the key test for the bug fix - when iterating over editors
        and affiliation data is missing, we should still return redaktor.
        """
        from pbn_integrator.importer.authors import _przetworz_afiliacje

        jednostka, afiliuje, typ = _przetworz_afiliacje(
            ta_afiliacja=None,
            default_jednostka=None,
            typ_odpowiedzialnosci_autor=typ_autor,
            typ_odpowiedzialnosci_redaktor=typ_redaktor,
            default_typ_odpowiedzialnosci=typ_redaktor,
        )

        assert typ == typ_redaktor
        assert afiliuje is False

    def test_affiliation_type_overrides_default_for_author(
        self, typ_autor, typ_redaktor, uczelnia_with_obca_jednostka
    ):
        """When affiliation has type=AUTHOR, returns autor regardless of default."""
        from pbn_integrator.importer.authors import _przetworz_afiliacje

        # Function expects a list, not a plain dict
        affiliation = [{"type": "AUTHOR", "institutionId": "some-id"}]

        jednostka, afiliuje, typ = _przetworz_afiliacje(
            ta_afiliacja=affiliation,
            default_jednostka=None,
            typ_odpowiedzialnosci_autor=typ_autor,
            typ_odpowiedzialnosci_redaktor=typ_redaktor,
            default_typ_odpowiedzialnosci=typ_redaktor,  # default is redaktor
        )

        # But affiliation says AUTHOR, so return autor
        assert typ == typ_autor

    def test_affiliation_type_overrides_default_for_editor(
        self, typ_autor, typ_redaktor, uczelnia_with_obca_jednostka
    ):
        """When affiliation has type=EDITOR, returns redaktor regardless of default."""
        from pbn_integrator.importer.authors import _przetworz_afiliacje

        # Function expects a list, not a plain dict
        affiliation = [{"type": "EDITOR", "institutionId": "some-id"}]

        jednostka, afiliuje, typ = _przetworz_afiliacje(
            ta_afiliacja=affiliation,
            default_jednostka=None,
            typ_odpowiedzialnosci_autor=typ_autor,
            typ_odpowiedzialnosci_redaktor=typ_redaktor,
            default_typ_odpowiedzialnosci=typ_autor,  # default is autor
        )

        # But affiliation says EDITOR, so return redaktor
        assert typ == typ_redaktor

    def test_affiliation_list_with_single_element(
        self, typ_autor, typ_redaktor, uczelnia_with_obca_jednostka
    ):
        """When affiliation is list with single element, unwrap and process."""
        from pbn_integrator.importer.authors import _przetworz_afiliacje

        affiliation = [{"type": "EDITOR", "institutionId": "some-id"}]

        jednostka, afiliuje, typ = _przetworz_afiliacje(
            ta_afiliacja=affiliation,
            default_jednostka=None,
            typ_odpowiedzialnosci_autor=typ_autor,
            typ_odpowiedzialnosci_redaktor=typ_redaktor,
        )

        assert typ == typ_redaktor


@pytest.mark.django_db
class TestUtworzAutorowEditorHandling:
    """Integration tests for utworz_autorow with editors."""

    def test_editor_without_affiliation_gets_redaktor_type(
        self, typ_autor, typ_redaktor, uczelnia_with_obca_jednostka
    ):
        """Editor without affiliation data should still be assigned redaktor type.

        This is the main integration test for the bug fix.
        """

        from pbn_integrator.importer.authors import utworz_autorow

        # Create mock publication with autorzy_set
        mock_autorzy_set = MagicMock()
        mock_autorzy_set.filter.return_value.exists.return_value = False

        mock_publication = MagicMock()
        mock_publication.autorzy_set = mock_autorzy_set

        # Create mock client
        mock_client = MagicMock()

        # Create mock author with pbn_uid_id
        mock_autor = MagicMock()
        mock_autor.pbn_uid_id = "editor-pbn-uid"

        # PBN JSON with editor but NO affiliation for that editor
        pbn_json = {
            "editors": {
                "editor-pbn-uid": {
                    "lastName": "Jamroziak",
                    "name": "Krzysztof",
                }
            },
            "authors": {},
            "affiliations": {},  # Empty - no affiliation data!
            "orderList": {},
        }

        with patch(
            "pbn_integrator.importer.authors._pobierz_lub_utworz_autora",
            return_value=mock_autor,
        ):
            utworz_autorow(
                mock_publication,
                pbn_json,
                mock_client,
                default_jednostka=None,
            )

        # Verify update_or_create was called with redaktor type
        mock_autorzy_set.update_or_create.assert_called_once()
        call_kwargs = mock_autorzy_set.update_or_create.call_args

        # The typ_odpowiedzialnosci should be redaktor, not autor
        assert call_kwargs[1]["typ_odpowiedzialnosci"] == typ_redaktor
