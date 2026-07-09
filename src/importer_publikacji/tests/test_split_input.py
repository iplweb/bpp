from importer_publikacji.providers import DataProvider, SplitRecord, get_provider


class _DummyProvider(DataProvider):
    name = "Dummy"
    identifier_label = "X"

    def fetch(self, identifier):
        return None

    def validate_identifier(self, identifier):
        return identifier


def test_split_input_default_returns_single_record():
    records = _DummyProvider().split_input("cokolwiek")
    assert records == [SplitRecord(raw="cokolwiek")]
    assert records[0].ok is True
    assert records[0].title == ""
    assert records[0].error == ""


SAMPLE_A = """@article{a,
  title = {Pierwsza praca},
  author = {Kowalski, Jan},
  year = {2021},
}"""

SAMPLE_B = """@book{b,
  title = {Druga praca},
  author = {Nowak, Anna},
  year = {2022},
}"""

# Uszkodzony blok: brak zamkniecia klamry / smiec skladniowy.
BROKEN = "@article{c, title = {Trzecia"


def test_bibtex_split_multiple_entries_order_preserved():
    provider = get_provider("BibTeX")
    records = provider.split_input(SAMPLE_A + "\n\n" + SAMPLE_B)
    assert len(records) == 2
    assert all(r.ok for r in records)
    assert records[0].title == "Pierwsza praca"
    assert records[1].title == "Druga praca"
    # Kazdy raw re-parsuje sie do dokladnie jednego wpisu:
    import bibtexparser

    for r in records:
        assert len(bibtexparser.parse_string(r.raw).entries) == 1


def test_bibtex_split_keeps_broken_block_as_failed_record():
    provider = get_provider("BibTeX")
    records = provider.split_input(SAMPLE_A + "\n\n" + BROKEN + "\n\n" + SAMPLE_B)
    # Nic nie znika: 3 rekordy (2 ok + 1 uszkodzony), kolejnosc zrodlowa.
    assert len(records) == 3
    assert [r.ok for r in records] == [True, False, True]
    assert records[1].error  # niepusty komunikat
    assert records[0].title == "Pierwsza praca"
    assert records[2].title == "Druga praca"


def test_bibtex_peek_title_missing_returns_empty():
    provider = get_provider("BibTeX")
    records = provider.split_input("@misc{x, author = {Ktos, Ktos}}")
    assert len(records) == 1
    assert records[0].title == ""
