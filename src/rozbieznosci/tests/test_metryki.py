from rozbieznosci.metryki import (
    DEFAULT_METRYKA,
    METRYKA_CHOICES,
    METRYKI,
    METRYKI_BY_SLUG,
)


def test_cztery_metryki_w_kolejnosci():
    assert [m.slug for m in METRYKI] == ["if", "mnisw", "kw_scopus", "kw_wos"]


def test_pola_metryk():
    by = METRYKI_BY_SLUG
    assert by["if"].field_name == "impact_factor"
    assert by["if"].is_quartile is False
    assert by["if"].recalculates_disciplines is False
    assert by["mnisw"].field_name == "punkty_kbn"
    assert by["mnisw"].recalculates_disciplines is True
    assert by["kw_scopus"].field_name == "kwartyl_w_scopus"
    assert by["kw_scopus"].is_quartile is True
    assert by["kw_wos"].field_name == "kwartyl_w_wos"
    assert by["kw_wos"].is_quartile is True


def test_default_metryka_to_if():
    assert DEFAULT_METRYKA.slug == "if"


def test_choices():
    assert METRYKA_CHOICES[0] == ("if", "Impact Factor")
    assert dict(METRYKA_CHOICES)["mnisw"] == "Punkty MNiSW"
