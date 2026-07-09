from importer_publikacji.providers import DataProvider, SplitRecord


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
