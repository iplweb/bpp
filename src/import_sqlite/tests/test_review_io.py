from import_sqlite.core.author_matching import Candidate, DistinctAuthor
from import_sqlite.review_io import (
    read_authors_decisions,
    write_authors_csv,
    write_patents_csv,
)


def test_authors_csv_roundtrip_decision(tmp_path):
    p = tmp_path / "autorzy.csv"
    authors = [
        DistinctAuthor(
            nazwisko_zrodlowe="Anna Wawruszak",
            given="Anna",
            family="Wawruszak",
            wystapien=3,
            status="DOKLADNE",
            candidates=[Candidate(441, "Wawruszak Anna", 1.0, 12)],
            prefill_pk=441,
        ),
        DistinctAuthor(
            nazwisko_zrodlowe="Jan Kovalski",
            given="Jan",
            family="Kovalski",
            wystapien=1,
            status="BRAK",
            candidates=[],
            prefill_pk=None,
        ),
    ]
    write_authors_csv(str(p), authors)
    decisions = read_authors_decisions(str(p))
    assert decisions["Anna Wawruszak"] == "441"  # prefill DOKLADNE
    assert decisions["Jan Kovalski"] == ""  # brak prefillu


def test_patents_csv_written(tmp_path):
    p = tmp_path / "patenty.csv"
    write_patents_csv(
        str(p),
        [
            {
                "source_id": "UML1",
                "numer_prawa": "Pat.1",
                "numer_zgloszenia": "P.1",
                "tytul": "T",
                "status": "UTWORZONY",
                "powod": "",
            }
        ],
    )
    content = p.read_text(encoding="utf-8")
    assert "UML1" in content and "UTWORZONY" in content
