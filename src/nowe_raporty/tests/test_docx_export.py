from pathlib import Path

import pytest
import requests
from django.test import override_settings

from nowe_raporty import docx_export

HTML_CONTENT = "<h1>Test</h1>"

SERVICE_URL = "http://html2docx:3030/convert"


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


def test_as_docx_falls_back_to_service(monkeypatch):
    monkeypatch.setattr(
        docx_export.pypandoc,
        "convert_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("pandoc missing")),
    )

    def service_fallback(html, output_path):
        assert html == HTML_CONTENT
        Path(output_path).write_bytes(b"service-doc")

    monkeypatch.setattr(
        docx_export, "_convert_using_html2docx_service", service_fallback
    )

    temp_file = docx_export.as_docx(object(), {})

    try:
        assert Path(temp_file.name).read_bytes() == b"service-doc"
    finally:
        temp_file.close()
        Path(temp_file.name).unlink(missing_ok=True)


def test_as_docx_raises_when_both_converters_fail(monkeypatch):
    monkeypatch.setattr(
        docx_export.pypandoc,
        "convert_text",
        lambda *args, **kwargs: (_ for _ in ()).throw(OSError("pandoc missing")),
    )

    def service_fallback(html, output_path):  # noqa: ARG001
        raise RuntimeError("service failed")

    monkeypatch.setattr(
        docx_export, "_convert_using_html2docx_service", service_fallback
    )

    with pytest.raises(docx_export.DocxConversionError):
        docx_export.as_docx(object(), {})


def test_html2docx_service_success(monkeypatch, tmp_path):
    """Fallback POST-uje HTML i zapisuje zwrócone bajty docx."""
    output_path = tmp_path / "out.docx"

    class FakeResp:
        content = b"docx-bytes"

        def raise_for_status(self):
            pass

    captured = {}

    def fake_post(url, data, headers, timeout):
        captured["url"] = url
        captured["data"] = data
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResp()

    monkeypatch.setattr(requests, "post", fake_post)
    with override_settings(HTML2DOCX_URL=SERVICE_URL):
        docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))

    assert output_path.read_bytes() == b"docx-bytes"
    assert captured["url"] == SERVICE_URL
    assert captured["data"] == b"<b>x</b>"
    assert captured["timeout"] == (5, 30)


def test_html2docx_service_soft_fail_when_url_none(monkeypatch, tmp_path, caplog):
    """Brak HTML2DOCX_URL => warning + wyjątek, bez próby HTTP (miękki fail)."""
    output_path = tmp_path / "out.docx"

    def fail_post(*args, **kwargs):  # noqa: ARG001
        raise AssertionError("nie powinno wołać requests.post gdy URL=None")

    monkeypatch.setattr(requests, "post", fail_post)

    with override_settings(HTML2DOCX_URL=None):
        with pytest.raises(RuntimeError):
            docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))

    assert "html2docx" in caplog.text.lower()


def test_html2docx_service_raises_on_error_status(monkeypatch, tmp_path):
    """Non-2xx z usługi => wyjątek propaguje (wyżej -> DocxConversionError)."""
    output_path = tmp_path / "out.docx"

    class FakeResp:
        def raise_for_status(self):
            raise requests.HTTPError("500")

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with override_settings(HTML2DOCX_URL=SERVICE_URL):
        with pytest.raises(requests.HTTPError):
            docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))


def test_html2docx_service_empty_output_raises(monkeypatch, tmp_path):
    """Pusty docx z usługi => RuntimeError (walidacja rozmiaru)."""
    output_path = tmp_path / "out.docx"

    class FakeResp:
        content = b""

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with override_settings(HTML2DOCX_URL=SERVICE_URL):
        with pytest.raises(RuntimeError, match="no output"):
            docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))
