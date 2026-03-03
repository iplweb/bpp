import html
import json

import pytest
from django.template import Context, Template

from importer_publikacji.crossref_fields import (
    categorize_crossref_fields,
)


@pytest.fixture
def sample_crossref_raw_data():
    """Przykładowe dane surowe z CrossRef API."""
    return {
        "DOI": "10.1016/j.example.2024.01.001",
        "type": "journal-article",
        "title": ["Example Article Title"],
        "author": [{"given": "Jan", "family": "Kowalski"}],
        "ISSN": ["1234-5678"],
        "container-title": ["Example Journal"],
        "abstract": "Example abstract text.",
        "volume": "42",
        "page": "1-10",
        "publisher": "Example Publisher",
        "language": "en",
        # ignorowane
        "indexed": {"timestamp": 1234567890},
        "created": {"timestamp": 1234567890},
        "reference-count": 25,
        # obce / nieznane
        "funder": [{"name": "NCN"}],
        "update-policy": "http://example.com",
    }


class TestCategorizeCrossrefFields:
    def test_empty_data(self):
        result = categorize_crossref_fields({})
        assert result == {
            "wyodrebnione": [],
            "ignorowane": [],
            "obce": [],
        }

    def test_none_data(self):
        result = categorize_crossref_fields(None)
        assert result == {
            "wyodrebnione": [],
            "ignorowane": [],
            "obce": [],
        }

    def test_non_dict_data(self):
        result = categorize_crossref_fields("not a dict")
        assert result == {
            "wyodrebnione": [],
            "ignorowane": [],
            "obce": [],
        }

    def test_categorizes_known_fields(self, sample_crossref_raw_data):
        result = categorize_crossref_fields(sample_crossref_raw_data)

        wyodrebnione_keys = [k for k, v in result["wyodrebnione"]]
        assert "DOI" in wyodrebnione_keys
        assert "type" in wyodrebnione_keys
        assert "title" in wyodrebnione_keys
        assert "author" in wyodrebnione_keys
        assert "ISSN" in wyodrebnione_keys
        assert "container-title" in wyodrebnione_keys
        assert "abstract" in wyodrebnione_keys
        assert "volume" in wyodrebnione_keys
        assert "page" in wyodrebnione_keys
        assert "publisher" in wyodrebnione_keys
        assert "language" in wyodrebnione_keys

    def test_categorizes_ignored_fields(self, sample_crossref_raw_data):
        result = categorize_crossref_fields(sample_crossref_raw_data)

        ignorowane_keys = [k for k, v in result["ignorowane"]]
        assert "indexed" in ignorowane_keys
        assert "created" in ignorowane_keys
        assert "reference-count" in ignorowane_keys

    def test_categorizes_foreign_fields(self, sample_crossref_raw_data):
        result = categorize_crossref_fields(sample_crossref_raw_data)

        obce_keys = [k for k, v in result["obce"]]
        assert "funder" in obce_keys
        assert "update-policy" in obce_keys

    def test_results_are_sorted(self, sample_crossref_raw_data):
        result = categorize_crossref_fields(sample_crossref_raw_data)
        for category in (
            "wyodrebnione",
            "ignorowane",
            "obce",
        ):
            keys = [k for k, v in result[category]]
            assert keys == sorted(keys)

    def test_values_preserved(self):
        data = {"DOI": "10.1234/test", "type": "book"}
        result = categorize_crossref_fields(data)
        wyodrebnione_dict = dict(result["wyodrebnione"])
        assert wyodrebnione_dict["DOI"] == "10.1234/test"
        assert wyodrebnione_dict["type"] == "book"

    def test_no_overlap(self, sample_crossref_raw_data):
        result = categorize_crossref_fields(sample_crossref_raw_data)
        all_keys = (
            [k for k, v in result["wyodrebnione"]]
            + [k for k, v in result["ignorowane"]]
            + [k for k, v in result["obce"]]
        )
        assert len(all_keys) == len(set(all_keys))

    def test_all_keys_covered(self, sample_crossref_raw_data):
        result = categorize_crossref_fields(sample_crossref_raw_data)
        all_keys = set(
            [k for k, v in result["wyodrebnione"]]
            + [k for k, v in result["ignorowane"]]
            + [k for k, v in result["obce"]]
        )
        assert all_keys == set(sample_crossref_raw_data.keys())


class TestPrettyJsonFilter:
    def test_renders_dict(self):
        template = Template("{% load importer_tags %}{{ val|pretty_json }}")
        ctx = Context({"val": {"a": 1, "b": "text"}})
        result = html.unescape(template.render(ctx))
        parsed = json.loads(result)
        assert parsed == {"a": 1, "b": "text"}

    def test_renders_list(self):
        template = Template("{% load importer_tags %}{{ val|pretty_json }}")
        ctx = Context({"val": [1, 2, 3]})
        result = template.render(ctx)
        parsed = json.loads(result)
        assert parsed == [1, 2, 3]

    def test_renders_string(self):
        template = Template("{% load importer_tags %}{{ val|pretty_json }}")
        ctx = Context({"val": "hello"})
        result = html.unescape(template.render(ctx))
        assert json.loads(result) == "hello"

    def test_unicode_preserved(self):
        template = Template("{% load importer_tags %}{{ val|pretty_json }}")
        ctx = Context({"val": {"key": "zażółć"}})
        result = template.render(ctx)
        assert "zażółć" in result

    def test_non_serializable_fallback(self):
        template = Template("{% load importer_tags %}{{ val|pretty_json }}")
        ctx = Context({"val": object()})
        result = template.render(ctx)
        assert result  # powinien zwrócić str(value)
