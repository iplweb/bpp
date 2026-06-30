from types import SimpleNamespace

from live_operations.naming import (
    channel_name,
    class_to_snake,
    host_template_name,
    result_template_name,
)


def test_snake_simple():
    assert class_to_snake("ImportPunktacji") == "import_punktacji"


def test_snake_acronym_digit():
    assert class_to_snake("ImportPBN2") == "import_pbn2"


def test_snake_two_words():
    assert class_to_snake("DemoOp") == "demo_op"


def test_snake_leading_acronym():
    # ABCTest → abc_test (inflection-style two-pass)
    assert class_to_snake("ABCTest") == "abc_test"


def test_snake_single_word():
    assert class_to_snake("Import") == "import"


def test_host_template_name_auto():
    class FakeMeta:
        app_label = "myapp"

    class FakeModel:
        _meta = FakeMeta()
        __name__ = "ImportPunktacji"

    assert host_template_name(FakeModel) == "myapp/import_punktacji.html"


def test_result_template_name_auto():
    class FakeMeta:
        app_label = "myapp"

    class FakeModel:
        _meta = FakeMeta()
        __name__ = "ImportPunktacji"

    assert result_template_name(FakeModel) == "myapp/import_punktacji_result.html"


def test_host_template_name_override():
    class FakeMeta:
        app_label = "myapp"

    class FakeModel:
        _meta = FakeMeta()
        __name__ = "MyOp"
        host_template_name = "custom/overridden.html"

    assert host_template_name(FakeModel) == "custom/overridden.html"


def test_result_template_name_override():
    class FakeMeta:
        app_label = "myapp"

    class FakeModel:
        _meta = FakeMeta()
        __name__ = "MyOp"
        result_template_name = "custom/my_result.html"

    assert result_template_name(FakeModel) == "custom/my_result.html"


def test_channel_name():
    op = SimpleNamespace(pk="abc-123")
    assert channel_name(op) == "liveop.abc-123"
