from pathlib import Path

import pytest

from nowe_raporty import docx_export

HTML_CONTENT = "<h1>Test</h1>"


@pytest.fixture(autouse=True)
def mock_html(monkeypatch):
    monkeypatch.setattr(
        docx_export.flexible_tables, "as_html", lambda report, context: HTML_CONTENT
    )


def test_as_docx_uses_pandoc(monkeypatch):
    def convert_text(text, to_format, format, outputfile):  # noqa: ARG001
        Path(outputfile).write_bytes(b"pandoc-doc")

    monkeypatch.setattr(docx_export.pypandoc, "convert_text", convert_text)

    temp_file = docx_export.as_docx(object(), {})

    try:
        assert Path(temp_file.name).read_bytes() == b"pandoc-doc"
    finally:
        temp_file.close()
        Path(temp_file.name).unlink(missing_ok=True)


def test_as_docx_falls_back_to_docker(monkeypatch):
    monkeypatch.setattr(
        docx_export.pypandoc,
        "convert_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("pandoc missing")),
    )

    def docker_fallback(html, output_path):
        assert html == HTML_CONTENT
        Path(output_path).write_bytes(b"docker-doc")

    monkeypatch.setattr(docx_export, "_convert_using_docker_image", docker_fallback)

    temp_file = docx_export.as_docx(object(), {})

    try:
        assert Path(temp_file.name).read_bytes() == b"docker-doc"
    finally:
        temp_file.close()
        Path(temp_file.name).unlink(missing_ok=True)


def test_as_docx_raises_when_both_converters_fail(monkeypatch):
    monkeypatch.setattr(
        docx_export.pypandoc,
        "convert_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("pandoc missing")),
    )

    def docker_fallback(html, output_path):  # noqa: ARG001
        raise RuntimeError("docker failed")

    monkeypatch.setattr(docx_export, "_convert_using_docker_image", docker_fallback)

    with pytest.raises(docx_export.DocxConversionError):
        docx_export.as_docx(object(), {})
