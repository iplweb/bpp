from datetime import date

from import_sqlite.handlers.patent import parse_ddmmyyyy, parse_patent
from import_sqlite.reader import RawRecord


def _rec(**parsed):
    return RawRecord("UML1", "http://x/1", parsed)


def test_parse_ddmmyyyy_ok():
    assert parse_ddmmyyyy("28-06-2023") == date(2023, 6, 28)


def test_parse_ddmmyyyy_empty():
    assert parse_ddmmyyyy("") is None
    assert parse_ddmmyyyy(None) is None
    assert parse_ddmmyyyy("garbage") is None


def test_parse_patent_basic_fields():
    pd = parse_patent(
        _rec(
            title="Zastosowanie X",
            inventors=["Anna Wawruszak", "Andrzej Stepulak"],
            application_number="P.445383",
            application_date="28-06-2023",
            all_fields={
                "Numer patentu/prawa": "Pat.247645",
                "Data udzielenia prawa": "19-05-2025",
            },
        )
    )
    assert pd.tytul == "Zastosowanie X"
    assert pd.rok == 2023
    assert pd.numer_zgloszenia == "P.445383"
    assert pd.data_zgloszenia == date(2023, 6, 28)
    assert pd.numer_prawa == "Pat.247645"
    assert pd.data_decyzji == date(2025, 5, 19)
    assert pd.inventors == ["Anna Wawruszak", "Andrzej Stepulak"]


def test_parse_patent_rok_fallback_to_grant_year():
    pd = parse_patent(
        _rec(
            title="Bez daty zgłoszenia",
            inventors=["Anna Wawruszak"],
            application_number="",
            application_date="",
            all_fields={
                "Numer patentu/prawa": "Pat.100",
                "Data udzielenia prawa": "19-05-2025",
            },
        )
    )
    assert pd.rok == 2025


def test_parse_patent_szczegoly_truncated_overflow_to_adnotacje():
    pd = parse_patent(
        _rec(
            title="T",
            inventors=["A B"],
            all_fields={
                "Numer patentu/prawa": "Pat.1",
                "Nazwa wynalazku / wzoru / utworu w języku angielskim": "X" * 600,
            },
        )
    )
    assert len(pd.szczegoly) <= 512
    assert "X" * 600 in pd.adnotacje  # nadmiar wylądował w adnotacjach
