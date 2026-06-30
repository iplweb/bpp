"""Charakteryzacyjne testy dla helpers.py — pinują OBECNE zachowanie przed
refaktorem redukującym złożoność cyklomatyczną (C901).

Komparatory wykonują zapytania do bazy; na pustej bazie zwracają
``WynikPorownania`` z ``rekord_po_stronie_bpp == None`` (porównaj FD#323).
Dlatego pola mapowane przez Komparator (zrodlo, wydawca, charakter_formalny,
jezyk, openaccess_licencja) wychodzą None / tekst, co jest tu pinowane.
"""

import pytest

from crossref_bpp.admin.helpers import (
    convert_crossref_to_changeform_initial_data,
    merge_crossref_and_pbn_data,
)


# --------------------------------------------------------------------------
# convert_crossref_to_changeform_initial_data
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_convert_empty_dict():
    ret = convert_crossref_to_changeform_initial_data({})
    assert ret["tytul_oryginalny"] is None
    assert ret["zrodlo"] is None
    assert ret["nr_zeszytu"] == ""
    assert ret["strony"] == ""
    assert ret["slowa_kluczowe"] == ""
    assert ret["wydawca"] is None
    assert ret["wydawca_opis"] is None
    assert ret["doi"] is None
    assert ret["charakter_formalny"] is None
    assert ret["jezyk"] is None
    assert ret["adnotacje"] == "Dodano na podstawie CrossRef API"
    assert ret["e_issn"] is None
    assert ret["e_isbn"] is None
    assert ret["isbn"] is None
    assert ret["oznaczenie_wydania"] is None
    assert ret["miejsce_i_rok"] == ""
    assert ret["openaccess_licencja"] is None
    assert ret["openaccess_ilosc_miesiecy"] is None
    assert ret["issn"] is None
    assert ret["www"] == ""
    assert ret["tom"] == ""
    assert ret["rok"] == ""


@pytest.mark.django_db
def test_convert_title_as_list_joined_with_dot_space():
    ret = convert_crossref_to_changeform_initial_data(
        {"title": ["Pierwszy", "Drugi"]}
    )
    assert ret["tytul_oryginalny"] == "Pierwszy. Drugi"


@pytest.mark.django_db
def test_convert_title_as_scalar():
    ret = convert_crossref_to_changeform_initial_data({"title": "Sam tytul"})
    assert ret["tytul_oryginalny"] == "Sam tytul"


@pytest.mark.django_db
def test_convert_keywords_quoted_and_joined():
    ret = convert_crossref_to_changeform_initial_data(
        {"subject": ["alfa", "beta"]}
    )
    assert ret["slowa_kluczowe"] == '"alfa", "beta"'


@pytest.mark.django_db
def test_convert_wydawca_opis_filled_when_no_match():
    ret = convert_crossref_to_changeform_initial_data({"publisher": "Wiley"})
    assert ret["wydawca"] is None
    assert ret["wydawca_opis"] == "Wiley"


@pytest.mark.django_db
def test_convert_basic_scalar_fields_passthrough():
    z = {
        "issue": "3",
        "page": "10-20",
        "DOI": "10.1/x",
        "edition-number": "2nd",
        "volume": "42",
    }
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["nr_zeszytu"] == "3"
    assert ret["strony"] == "10-20"
    assert ret["doi"] == "10.1/x"
    assert ret["oznaczenie_wydania"] == "2nd"
    assert ret["tom"] == "42"


@pytest.mark.django_db
def test_convert_www_from_resource_primary_url():
    z = {"resource": {"primary": {"URL": "http://example.com/a"}}}
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["www"] == "http://example.com/a"


@pytest.mark.django_db
def test_convert_www_missing_resource_is_empty_string():
    ret = convert_crossref_to_changeform_initial_data({"resource": {}})
    assert ret["www"] == ""


@pytest.mark.django_db
def test_convert_issn_type_electronic_and_print():
    z = {
        "issn-type": [
            {"type": "electronic", "value": "1111-1111"},
            {"type": "print", "value": "2222-2222"},
        ]
    }
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["e_issn"] == "1111-1111"
    assert ret["issn"] == "2222-2222"


@pytest.mark.django_db
def test_convert_isbn_type_electronic_and_print():
    z = {
        "isbn-type": [
            {"type": "electronic", "value": "978-e"},
            {"type": "print", "value": "978-p"},
        ]
    }
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["e_isbn"] == "978-e"
    assert ret["isbn"] == "978-p"


@pytest.mark.django_db
def test_convert_issn_fallback_from_ISSN_when_no_issn_type():
    z = {"ISSN": ["3333-3333"]}
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["issn"] == "3333-3333"


@pytest.mark.django_db
def test_convert_issn_fallback_skipped_when_equals_e_issn():
    # ISSN equal to e_issn (electronic) => issn must stay None
    z = {
        "issn-type": [{"type": "electronic", "value": "4444-4444"}],
        "ISSN": ["4444-4444"],
    }
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["e_issn"] == "4444-4444"
    assert ret["issn"] is None


@pytest.mark.django_db
def test_convert_issn_fallback_kept_when_differs_from_e_issn():
    z = {
        "issn-type": [{"type": "electronic", "value": "4444-4444"}],
        "ISSN": ["5555-5555"],
    }
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["e_issn"] == "4444-4444"
    assert ret["issn"] == "5555-5555"


@pytest.mark.django_db
def test_convert_isbn_fallback_from_ISBN_when_no_isbn_type():
    z = {"ISBN": ["978-fallback"]}
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["isbn"] == "978-fallback"


@pytest.mark.django_db
def test_convert_isbn_fallback_skipped_when_equals_e_isbn():
    z = {
        "isbn-type": [{"type": "electronic", "value": "978-e"}],
        "ISBN": ["978-e"],
    }
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["e_isbn"] == "978-e"
    assert ret["isbn"] is None


@pytest.mark.django_db
def test_convert_issn_empty_ISSN_list_index_error_yields_none():
    z = {"ISSN": []}
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["issn"] is None


@pytest.mark.django_db
def test_convert_rok_from_published_date_parts():
    z = {"published": {"date-parts": [[2021, 5, 1]]}}
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["rok"] == 2021


@pytest.mark.django_db
def test_convert_rok_default_empty_when_no_published():
    ret = convert_crossref_to_changeform_initial_data({})
    assert ret["rok"] == ""


@pytest.mark.django_db
def test_convert_miejsce_i_rok_combines_location_and_year():
    z = {
        "publisher-location": "Warszawa",
        "published": {"date-parts": [[1999]]},
    }
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["miejsce_i_rok"] == "Warszawa 1999"


@pytest.mark.django_db
def test_convert_miejsce_i_rok_empty_without_location():
    z = {"published": {"date-parts": [[1999]]}}
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["miejsce_i_rok"] == ""


@pytest.mark.django_db
def test_convert_container_title_empty_list_yields_no_zrodlo():
    ret = convert_crossref_to_changeform_initial_data({"container-title": []})
    assert ret["zrodlo"] is None


@pytest.mark.django_db
def test_convert_license_unmatched_yields_none_pk_and_no_months():
    # License URL spoza creativecommons => brak dopasowania => pk None
    z = {
        "license": [
            {
                "URL": "http://onlinelibrary.wiley.com/x",
                "delay-in-days": 60,
            }
        ]
    }
    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["openaccess_licencja"] is None
    assert ret["openaccess_ilosc_miesiecy"] is None


# --------------------------------------------------------------------------
# merge_crossref_and_pbn_data
# --------------------------------------------------------------------------


@pytest.mark.django_db
def test_merge_no_pbn_data_returns_crossref_only():
    crossref = {"title": ["Tytul"], "DOI": "10.1/x"}
    ret = merge_crossref_and_pbn_data(crossref, {})
    assert ret["has_pbn_data"] is False
    assert ret["tytul_oryginalny"] == "Tytul"
    assert "data_sources" in ret
    assert ret["data_sources"]["tytul_oryginalny"] == "CrossRef"
    assert ret["data_sources"]["doi"] == "CrossRef"


@pytest.mark.django_db
def test_merge_data_sources_only_for_truthy_fields():
    crossref = {"DOI": "10.1/x"}
    ret = merge_crossref_and_pbn_data(crossref, {})
    # nr_zeszytu == "" (falsy) => not in data_sources
    assert "nr_zeszytu" not in ret["data_sources"]
    assert ret["data_sources"]["doi"] == "CrossRef"


@pytest.mark.django_db
def test_merge_pbn_fills_missing_title():
    crossref = {}
    pbn = {"object": {"title": "PBN Tytul"}}
    ret = merge_crossref_and_pbn_data(crossref, pbn)
    assert ret["has_pbn_data"] is True
    assert ret["tytul_oryginalny"] == "PBN Tytul"
    assert ret["data_sources"]["tytul_oryginalny"] == "PBN"


@pytest.mark.django_db
def test_merge_pbn_different_title_becomes_alternatywny():
    crossref = {"title": ["CrossRef Tytul"]}
    pbn = {"object": {"title": "PBN Tytul"}}
    ret = merge_crossref_and_pbn_data(crossref, pbn)
    assert ret["tytul_oryginalny"] == "CrossRef Tytul"
    assert ret["tytul_alternatywny"] == "PBN Tytul"
    assert ret["data_sources"]["tytul_alternatywny"] == "PBN"
    assert "Tytuł w PBN: PBN Tytul" in ret["adnotacje"]


@pytest.mark.django_db
def test_merge_pbn_same_title_no_alternatywny():
    crossref = {"title": ["Ten Sam"]}
    pbn = {"object": {"title": "Ten Sam"}}
    ret = merge_crossref_and_pbn_data(crossref, pbn)
    assert "tytul_alternatywny" not in ret


@pytest.mark.django_db
def test_merge_pbn_mnisw_points():
    ret = merge_crossref_and_pbn_data(
        {}, {"object": {"mniswPointsForInstitution": 140}}
    )
    assert ret["punkty_kbn"] == 140
    assert ret["data_sources"]["punkty_kbn"] == "PBN"


@pytest.mark.django_db
def test_merge_pbn_volume_fills_when_missing():
    ret = merge_crossref_and_pbn_data({}, {"object": {"volume": "7"}})
    assert ret["tom"] == "7"
    assert ret["data_sources"]["tom"] == "PBN"


@pytest.mark.django_db
def test_merge_pbn_volume_conflict_marks_crossref_plus_pbn():
    crossref = {"volume": "5"}
    pbn = {"object": {"volume": "7"}}
    ret = merge_crossref_and_pbn_data(crossref, pbn)
    assert ret["tom"] == "5"
    assert ret["data_sources"]["tom"] == "CrossRef+PBN"


@pytest.mark.django_db
def test_merge_pbn_volume_equal_keeps_crossref_source():
    crossref = {"volume": "7"}
    pbn = {"object": {"volume": "7"}}
    ret = merge_crossref_and_pbn_data(crossref, pbn)
    assert ret["tom"] == "7"
    assert ret["data_sources"]["tom"] == "CrossRef"


@pytest.mark.django_db
def test_merge_pbn_issue_and_pages_fill_and_conflict():
    crossref = {"issue": "1", "page": "1-2"}
    pbn = {"object": {"issue": "9", "pages": "3-4"}}
    ret = merge_crossref_and_pbn_data(crossref, pbn)
    assert ret["nr_zeszytu"] == "1"
    assert ret["data_sources"]["nr_zeszytu"] == "CrossRef+PBN"
    assert ret["strony"] == "1-2"
    assert ret["data_sources"]["strony"] == "CrossRef+PBN"


@pytest.mark.django_db
def test_merge_pbn_issue_pages_fill_when_missing():
    pbn = {"object": {"issue": "9", "pages": "3-4"}}
    ret = merge_crossref_and_pbn_data({}, pbn)
    assert ret["nr_zeszytu"] == "9"
    assert ret["data_sources"]["nr_zeszytu"] == "PBN"
    assert ret["strony"] == "3-4"
    assert ret["data_sources"]["strony"] == "PBN"


@pytest.mark.django_db
def test_merge_pbn_uid_precedence_pbnId_first():
    pbn = {"object": {}, "pbnId": "A", "objectId": "B", "mongoId": "C"}
    ret = merge_crossref_and_pbn_data({}, pbn)
    assert ret["pbn_uid"] == "A"
    assert ret["data_sources"]["pbn_uid"] == "PBN"


@pytest.mark.django_db
def test_merge_pbn_uid_falls_back_to_objectId_then_mongoId():
    ret = merge_crossref_and_pbn_data({}, {"object": {}, "objectId": "B"})
    assert ret["pbn_uid"] == "B"
    ret2 = merge_crossref_and_pbn_data({}, {"object": {}, "mongoId": "C"})
    assert ret2["pbn_uid"] == "C"


@pytest.mark.django_db
def test_merge_pbn_sheets():
    ret = merge_crossref_and_pbn_data({}, {"object": {"sheets": "2.5"}})
    assert ret["liczba_arkuszy_wydawniczych"] == "2.5"
    assert ret["data_sources"]["liczba_arkuszy_wydawniczych"] == "PBN"


@pytest.mark.django_db
def test_merge_pbn_conference_name():
    pbn = {"object": {"conference": {"name": "Konferencja X"}}}
    ret = merge_crossref_and_pbn_data({}, pbn)
    assert ret["konferencja_nazwa"] == "Konferencja X"
    assert ret["data_sources"]["konferencja_nazwa"] == "PBN"


@pytest.mark.django_db
def test_merge_pbn_conference_without_name_ignored():
    pbn = {"object": {"conference": {"city": "Lublin"}}}
    ret = merge_crossref_and_pbn_data({}, pbn)
    assert "konferencja_nazwa" not in ret


@pytest.mark.django_db
def test_merge_pbn_authors_added_when_crossref_has_no_author():
    pbn = {"object": {"authors": [{"name": "Jan"}]}}
    ret = merge_crossref_and_pbn_data({}, pbn)
    assert ret["pbn_authors"] == [{"name": "Jan"}]
    assert ret["data_sources"]["pbn_authors"] == "PBN"


@pytest.mark.django_db
def test_merge_pbn_authors_skipped_when_crossref_has_author():
    crossref = {"author": [{"given": "A", "family": "B"}]}
    pbn = {"object": {"authors": [{"name": "Jan"}]}}
    ret = merge_crossref_and_pbn_data(crossref, pbn)
    assert "pbn_authors" not in ret


@pytest.mark.django_db
def test_merge_adnotacje_updated_with_pbn():
    ret = merge_crossref_and_pbn_data({}, {"object": {"title": "T"}})
    assert ret["adnotacje"] == "Dodano na podstawie CrossRef API i PBN API"
    assert ret["data_sources"]["adnotacje"] == "CrossRef+PBN"


@pytest.mark.django_db
def test_merge_pbn_data_not_a_dict_raises_attributeerror():
    # OBECNE zachowanie: pbn_data truthy ale nie-dict => pbn_object == {}
    # (isinstance check), ale pbn_id robi pbn_data.get(...) bez ochrony,
    # więc lista rzuca AttributeError. Pinujemy ten stan.
    with pytest.raises(AttributeError):
        merge_crossref_and_pbn_data({"DOI": "10.1/x"}, ["something"])
