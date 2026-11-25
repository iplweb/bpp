import re
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
        content = b"PK\x03\x04docx"  # magia ZIP = poprawny .docx

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

    assert output_path.read_bytes() == b"PK\x03\x04docx"
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


def test_html2docx_service_rejects_non_docx(monkeypatch, tmp_path):
    """Status 200 z treścią nie-DOCX (np. strona błędu proxy) => RuntimeError.

    Chroni przed podaniem userowi uszkodzonego .docx, gdy usługa/proxy zwróci
    200 z HTML-em zamiast archiwum ZIP.
    """
    output_path = tmp_path / "out.docx"

    class FakeResp:
        content = b"<html><body>Bad Gateway</body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(requests, "post", lambda *a, **k: FakeResp())
    with override_settings(HTML2DOCX_URL=SERVICE_URL):
        with pytest.raises(RuntimeError, match="non-DOCX"):
            docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))
    assert not output_path.exists()


def test_html2docx_service_propagates_connection_error(monkeypatch, tmp_path):
    """Usługa nieosiągalna (ConnectionError) => wyjątek propaguje.

    Kluczowy scenariusz produkcyjny: kontener html2docx padł. Wyżej zamienia
    się w DocxConversionError (miękki fail, HTTP 500 — bez crasha).
    """
    output_path = tmp_path / "out.docx"

    def fake_post(*args, **kwargs):  # noqa: ARG001
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "post", fake_post)
    with override_settings(HTML2DOCX_URL=SERVICE_URL):
        with pytest.raises(requests.ConnectionError):
            docx_export._convert_using_html2docx_service("<b>x</b>", str(output_path))


# --- FD#444: kartka A4 pionowo/poziomo i marginesy z CSS ---


def _pusty_docx(tmp_path):
    from docx import Document

    sciezka = tmp_path / "pusty.docx"
    Document().save(sciezka)
    return str(sciezka)


def test_fd444_ustaw_strone_docx_pejzaz_a4_i_marginesy(tmp_path):
    import zipfile

    from nowe_raporty.docx_export import ustaw_strone_docx

    sciezka = _pusty_docx(tmp_path)
    ustaw_strone_docx(
        sciezka,
        "landscape",
        {"top": "1cm", "bottom": "10mm", "left": "0.5in", "right": "bzdura"},
    )

    with zipfile.ZipFile(sciezka) as zf:
        xml = zf.read("word/document.xml").decode("utf-8")

    pgsz = re.search(r"<w:pgSz [^>]*/>", xml).group(0)
    assert 'w:orient="landscape"' in pgsz
    assert 'w:w="16838"' in pgsz
    assert 'w:h="11906"' in pgsz
    pgmar = re.search(r"<w:pgMar [^>]*/>", xml).group(0)
    assert 'w:top="567"' in pgmar  # 1 cm
    assert 'w:bottom="567"' in pgmar  # 10 mm
    assert 'w:left="720"' in pgmar  # 0.5 in


def test_fd444_ustaw_strone_docx_nieznana_orientacja(tmp_path):
    from nowe_raporty.docx_export import ustaw_strone_docx

    with pytest.raises(ValueError):
        ustaw_strone_docx(_pusty_docx(tmp_path), "ukosna")


def test_fd444_dlugosc_css_na_emu():
    from docx.shared import Cm, Pt

    from nowe_raporty.docx_export import dlugosc_css_na_emu

    assert dlugosc_css_na_emu("2cm") == Cm(2)
    assert dlugosc_css_na_emu(" 12 PT ") == Pt(12)
    assert dlugosc_css_na_emu("0,5cm") is None
    assert dlugosc_css_na_emu("") is None
    assert dlugosc_css_na_emu(None) is None
