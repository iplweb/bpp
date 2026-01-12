"""Tests for PBN evaluation fields export in WydawnictwoPBNAdapter."""

import pytest
from model_bakery import baker

from bpp.models import Jezyk, Konferencja
from pbn_api.adapters.wydawnictwo import WydawnictwoPBNAdapter
from pbn_api.models import Language


@pytest.mark.django_db
class TestPBNEvaluationFieldsModel:
    """Test that PBN evaluation fields exist on models with correct defaults."""

    def test_wydawnictwo_ciagle_has_evaluation_fields(self, wydawnictwo_ciagle):
        """Verify that Wydawnictwo_Ciagle has all 7 evaluation fields."""
        assert hasattr(wydawnictwo_ciagle, "pbn_czy_projekt_fnp")
        assert hasattr(wydawnictwo_ciagle, "pbn_czy_projekt_ncn")
        assert hasattr(wydawnictwo_ciagle, "pbn_czy_projekt_nprh")
        assert hasattr(wydawnictwo_ciagle, "pbn_czy_projekt_ue")
        assert hasattr(wydawnictwo_ciagle, "pbn_czy_czasopismo_indeksowane")
        assert hasattr(wydawnictwo_ciagle, "pbn_czy_artykul_recenzyjny")
        assert hasattr(wydawnictwo_ciagle, "pbn_czy_edycja_naukowa")

    def test_wydawnictwo_zwarte_has_evaluation_fields(self, wydawnictwo_zwarte):
        """Verify that Wydawnictwo_Zwarte has all 7 evaluation fields."""
        assert hasattr(wydawnictwo_zwarte, "pbn_czy_projekt_fnp")
        assert hasattr(wydawnictwo_zwarte, "pbn_czy_projekt_ncn")
        assert hasattr(wydawnictwo_zwarte, "pbn_czy_projekt_nprh")
        assert hasattr(wydawnictwo_zwarte, "pbn_czy_projekt_ue")
        assert hasattr(wydawnictwo_zwarte, "pbn_czy_czasopismo_indeksowane")
        assert hasattr(wydawnictwo_zwarte, "pbn_czy_artykul_recenzyjny")
        assert hasattr(wydawnictwo_zwarte, "pbn_czy_edycja_naukowa")

    def test_evaluation_fields_default_to_none(self, wydawnictwo_ciagle):
        """Verify that all evaluation fields default to None."""
        assert wydawnictwo_ciagle.pbn_czy_projekt_fnp is None
        assert wydawnictwo_ciagle.pbn_czy_projekt_ncn is None
        assert wydawnictwo_ciagle.pbn_czy_projekt_nprh is None
        assert wydawnictwo_ciagle.pbn_czy_projekt_ue is None
        assert wydawnictwo_ciagle.pbn_czy_czasopismo_indeksowane is None
        assert wydawnictwo_ciagle.pbn_czy_artykul_recenzyjny is None
        assert wydawnictwo_ciagle.pbn_czy_edycja_naukowa is None

    def test_evaluation_fields_can_be_set(self, wydawnictwo_ciagle):
        """Verify that evaluation fields can be set and saved."""
        wydawnictwo_ciagle.pbn_czy_projekt_fnp = True
        wydawnictwo_ciagle.pbn_czy_projekt_ncn = False
        wydawnictwo_ciagle.pbn_czy_projekt_nprh = True
        wydawnictwo_ciagle.save()

        wydawnictwo_ciagle.refresh_from_db()
        assert wydawnictwo_ciagle.pbn_czy_projekt_fnp is True
        assert wydawnictwo_ciagle.pbn_czy_projekt_ncn is False
        assert wydawnictwo_ciagle.pbn_czy_projekt_nprh is True


@pytest.mark.django_db
class TestPBNEvaluationFieldsExport:
    """Test that PBN evaluation fields are exported correctly."""

    def test_evaluation_fields_not_exported_when_none(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """Fields with None value should NOT be exported."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        # All fields are None by default

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()

        assert "evaluationBookProjectFNP" not in ret
        assert "evaluationBookProjectNCN" not in ret
        assert "evaluationBookProjectNPHR" not in ret
        assert "evaluationBookProjectUE" not in ret
        assert "evaluationIndexedJournal" not in ret
        assert "evaluationIsReview" not in ret
        assert "evaluationScientificEdition" not in ret

    def test_evaluation_field_fnp_exported_when_true(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationBookProjectFNP should be exported when set to True."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_projekt_fnp = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationBookProjectFNP"] is True

    def test_evaluation_field_fnp_exported_when_false(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationBookProjectFNP should be exported when set to False."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_projekt_fnp = False
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationBookProjectFNP"] is False

    def test_evaluation_field_ncn_exported(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationBookProjectNCN should be exported when set."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_projekt_ncn = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationBookProjectNCN"] is True

    def test_evaluation_field_nprh_exported(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationBookProjectNPHR should be exported when set."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_projekt_nprh = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationBookProjectNPHR"] is True

    def test_evaluation_field_ue_exported(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationBookProjectUE should be exported when set."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_projekt_ue = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationBookProjectUE"] is True

    def test_evaluation_field_indexed_journal_exported(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationIndexedJournal should be exported when set."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_czasopismo_indeksowane = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationIndexedJournal"] is True

    def test_evaluation_field_is_review_exported(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationIsReview should be exported when set."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_artykul_recenzyjny = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationIsReview"] is True

    def test_evaluation_field_scientific_edition_exported(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationScientificEdition should be exported when set."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_edycja_naukowa = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationScientificEdition"] is True

    def test_multiple_evaluation_fields_exported(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """Multiple evaluation fields can be exported together."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.pbn_czy_projekt_fnp = True
        praca.pbn_czy_projekt_ncn = False
        praca.pbn_czy_czasopismo_indeksowane = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationBookProjectFNP"] is True
        assert ret["evaluationBookProjectNCN"] is False
        assert ret["evaluationIndexedJournal"] is True
        # These should NOT be exported (still None)
        assert "evaluationBookProjectNPHR" not in ret
        assert "evaluationBookProjectUE" not in ret


@pytest.mark.django_db
class TestPBNEvaluationTranslationFields:
    """Test computed translation fields based on jezyk/jezyk_orig."""

    def test_translation_from_polish_detected(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jezyki, pbn_language
    ):
        """Translation from Polish detected when jezyk_orig=pol and jezyk!=pol."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

        # Set up: original is Polish, current is English
        # jezyki fixture uses "pol." and "ang." with trailing periods
        polski = jezyki["pol."]
        angielski = jezyki["ang."]

        # Ensure both languages have pbn_uid for export to work
        pbn_lang_en = Language.objects.create(code="en", language={"en": "English"})
        angielski.pbn_uid = pbn_lang_en
        angielski.save()

        polski.pbn_uid = pbn_language
        polski.save()

        praca.jezyk_orig = polski
        praca.jezyk = angielski
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret.get("evaluationTranslationFromPolish") is True
        assert "evaluationTranslationToPolish" not in ret

    def test_translation_to_polish_detected(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jezyki, pbn_language
    ):
        """Translation to Polish detected when jezyk=pol and jezyk_orig!=pol."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

        # Set up: original is English, current is Polish
        polski = jezyki["pol."]
        angielski = jezyki["ang."]

        # Ensure both languages have pbn_uid for export to work
        polski.pbn_uid = pbn_language
        polski.save()

        pbn_lang_en = Language.objects.create(code="en4", language={"en": "English"})
        angielski.pbn_uid = pbn_lang_en
        angielski.save()

        praca.jezyk_orig = angielski
        praca.jezyk = polski
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret.get("evaluationTranslationToPolish") is True
        assert "evaluationTranslationFromPolish" not in ret

    def test_no_translation_when_same_language(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jezyki, pbn_language
    ):
        """No translation flags when jezyk and jezyk_orig are the same."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

        # Set up: both are Polish
        polski = jezyki["pol."]
        polski.pbn_uid = pbn_language
        polski.save()

        praca.jezyk_orig = polski
        praca.jezyk = polski
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert "evaluationTranslationFromPolish" not in ret
        assert "evaluationTranslationToPolish" not in ret

    def test_no_translation_when_jezyk_orig_none(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """No translation flags when jezyk_orig is None."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.jezyk_orig = None
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert "evaluationTranslationFromPolish" not in ret
        assert "evaluationTranslationToPolish" not in ret

    def test_translation_with_pl_abbreviation(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jezyki
    ):
        """Translation detection works with 'pl' abbreviation (no period)."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

        # Create language with 'pl' abbreviation (no period)
        pbn_lang_pl2 = Language.objects.create(code="pl2", language={"pl": "Polish"})
        pl_jezyk = baker.make(Jezyk, nazwa="Polski Alt", skrot="pl", pbn_uid=pbn_lang_pl2)
        angielski = jezyki["ang."]

        # Ensure English has pbn_uid for export to work
        pbn_lang_en = Language.objects.create(code="en2", language={"en": "English"})
        angielski.pbn_uid = pbn_lang_en
        angielski.save()

        praca.jezyk_orig = pl_jezyk
        praca.jezyk = angielski
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret.get("evaluationTranslationFromPolish") is True

    def test_translation_case_insensitive(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina, jezyki
    ):
        """Translation detection is case-insensitive (POL., PL. work too)."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

        # Create language with 'POL.' abbreviation (uppercase with period)
        pbn_lang_pl3 = Language.objects.create(code="pl3", language={"pl": "Polish"})
        pol_upper = baker.make(
            Jezyk, nazwa="Polski Upper", skrot="POL.", pbn_uid=pbn_lang_pl3
        )
        angielski = jezyki["ang."]

        # Ensure English has pbn_uid for export to work
        pbn_lang_en = Language.objects.create(code="en3", language={"en": "English"})
        angielski.pbn_uid = pbn_lang_en
        angielski.save()

        praca.jezyk_orig = pol_upper
        praca.jezyk = angielski
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret.get("evaluationTranslationFromPolish") is True


@pytest.mark.django_db
class TestPBNEvaluationWosConference:
    """Test computed evaluationWosConference field."""

    def test_wos_conference_exported_when_konferencja_has_baza_wos(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationWosConference exported when konferencja.baza_wos is True."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

        # Create a conference with baza_wos=True
        konferencja = baker.make(Konferencja, nazwa="Test Konferencja", baza_wos=True)
        praca.konferencja = konferencja
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret.get("evaluationWosConference") is True

    def test_wos_conference_not_exported_when_baza_wos_false(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationWosConference NOT exported when konferencja.baza_wos is False."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina

        # Create a conference with baza_wos=False
        konferencja = baker.make(Konferencja, nazwa="Test Konferencja", baza_wos=False)
        praca.konferencja = konferencja
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert "evaluationWosConference" not in ret

    def test_wos_conference_not_exported_when_no_konferencja(
        self, pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
    ):
        """evaluationWosConference NOT exported when konferencja is None."""
        praca = pbn_wydawnictwo_ciagle_z_autorem_z_dyscyplina
        praca.konferencja = None
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert "evaluationWosConference" not in ret


@pytest.mark.django_db
class TestPBNEvaluationFieldsZwarte:
    """Test evaluation fields on Wydawnictwo_Zwarte."""

    def test_evaluation_fields_exported_for_zwarte(
        self, pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
    ):
        """Verify evaluation fields work on Wydawnictwo_Zwarte as well."""
        praca = pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina
        praca.pbn_czy_projekt_fnp = True
        praca.pbn_czy_edycja_naukowa = True
        praca.save()

        ret = WydawnictwoPBNAdapter(praca).pbn_get_json()
        assert ret["evaluationBookProjectFNP"] is True
        assert ret["evaluationScientificEdition"] is True
