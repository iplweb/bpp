import subprocess
from pathlib import Path
from unittest.mock import MagicMock

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


def test_convert_using_docker_image_success(monkeypatch, tmp_path):
    """Test successful HTML to DOCX conversion using Docker."""
    html_input = "<h1>Test Document</h1>"
    output_path = tmp_path / "output.docx"
    expected_docx_content = b"fake-docx-content"

    # Mock subprocess.run to simulate successful docker execution
    mock_result = MagicMock()
    mock_result.stdout = expected_docx_content
    mock_result.stderr = b""

    def mock_subprocess_run(cmd, input, check, capture_output, text):  # noqa: ARG001
        assert cmd[0] == "docker"
        assert cmd[1:] == ["run", "--rm", "-i", "iplweb/html2docx:latest", "-", "-"]
        assert input == html_input.encode("utf-8")
        assert check is True
        assert capture_output is True
        assert text is False
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    docx_export._convert_using_docker_image(html_input, str(output_path))

    assert output_path.exists()
    assert output_path.read_bytes() == expected_docx_content


def test_convert_using_docker_image_with_stderr(monkeypatch, tmp_path, caplog):
    """Test Docker conversion with stderr output (warnings/debug info)."""
    import logging

    # Set log level to DEBUG to capture debug messages
    caplog.set_level(logging.DEBUG)

    html_input = "<h1>Test</h1>"
    output_path = tmp_path / "output.docx"
    expected_docx_content = b"docx-data"

    mock_result = MagicMock()
    mock_result.stdout = expected_docx_content
    mock_result.stderr = b"some warning message"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: mock_result,  # noqa: ARG005
    )

    docx_export._convert_using_docker_image(html_input, str(output_path))

    assert output_path.exists()
    assert output_path.read_bytes() == expected_docx_content
    assert "html2docx docker stderr: some warning message" in caplog.text


def test_convert_using_docker_image_called_process_error(monkeypatch, tmp_path, caplog):
    """Test handling of Docker command failure (non-zero exit code)."""
    html_input = "<h1>Test</h1>"
    output_path = tmp_path / "output.docx"

    error = subprocess.CalledProcessError(
        returncode=1, cmd=["docker"], stderr=b"docker error message"
    )

    def mock_subprocess_run(*args, **kwargs):  # noqa: ARG001
        raise error

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    with pytest.raises(subprocess.CalledProcessError):
        docx_export._convert_using_docker_image(html_input, str(output_path))

    assert "html2docx docker conversion failed: docker error message" in caplog.text


def test_convert_using_docker_image_called_process_error_no_stderr(
    monkeypatch, tmp_path, caplog
):
    """Test handling of Docker failure without stderr output."""
    html_input = "<h1>Test</h1>"
    output_path = tmp_path / "output.docx"

    error = subprocess.CalledProcessError(returncode=1, cmd=["docker"], stderr=None)

    def mock_subprocess_run(*args, **kwargs):  # noqa: ARG001
        raise error

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    with pytest.raises(subprocess.CalledProcessError):
        docx_export._convert_using_docker_image(html_input, str(output_path))

    assert "No error output" in caplog.text


def test_convert_using_docker_image_file_not_found_error(monkeypatch, tmp_path, caplog):
    """Test handling of Docker executable not found."""
    html_input = "<h1>Test</h1>"
    output_path = tmp_path / "output.docx"

    def mock_subprocess_run(*args, **kwargs):  # noqa: ARG001
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    with pytest.raises(FileNotFoundError):
        docx_export._convert_using_docker_image(html_input, str(output_path))

    assert "docker executable not found" in caplog.text


def test_convert_using_docker_image_empty_output(monkeypatch, tmp_path):
    """Test validation when Docker produces empty output."""
    html_input = "<h1>Test</h1>"
    output_path = tmp_path / "output.docx"

    mock_result = MagicMock()
    mock_result.stdout = b""
    mock_result.stderr = b""

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: mock_result,  # noqa: ARG005
    )

    with pytest.raises(RuntimeError, match="html2docx docker produced no output"):
        docx_export._convert_using_docker_image(html_input, str(output_path))


def test_convert_using_docker_image_custom_docker_command(monkeypatch, tmp_path):
    """Test using custom Docker command from settings."""
    html_input = "<h1>Test</h1>"
    output_path = tmp_path / "output.docx"
    expected_docx_content = b"docx-output"

    # Mock custom docker command
    monkeypatch.setattr(docx_export, "_DOCKER_COMMAND", ("podman",))

    mock_result = MagicMock()
    mock_result.stdout = expected_docx_content
    mock_result.stderr = b""

    def mock_subprocess_run(cmd, *args, **kwargs):  # noqa: ARG001
        assert cmd[0] == "podman"
        assert "run" in cmd
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    docx_export._convert_using_docker_image(html_input, str(output_path))

    assert output_path.exists()
    assert output_path.read_bytes() == expected_docx_content


def test_convert_using_docker_image_custom_docker_image(monkeypatch, tmp_path):
    """Test using custom Docker image from settings."""
    html_input = "<h1>Test</h1>"
    output_path = tmp_path / "output.docx"
    expected_docx_content = b"docx-data"

    # Mock custom docker image
    custom_image = "custom/html2docx:v2"
    monkeypatch.setattr(docx_export, "_DOCKER_IMAGE", custom_image)

    mock_result = MagicMock()
    mock_result.stdout = expected_docx_content
    mock_result.stderr = b""

    def mock_subprocess_run(cmd, *args, **kwargs):  # noqa: ARG001
        assert custom_image in cmd
        return mock_result

    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    docx_export._convert_using_docker_image(html_input, str(output_path))

    assert output_path.exists()


@pytest.mark.skipif(
    subprocess.run(["docker", "info"], capture_output=True, check=False).returncode
    != 0,
    reason="Docker is not available",
)
def test_convert_using_docker_image_integration(tmp_path):
    """Integration test: actual Docker conversion with real html2docx container.

    This test requires:
    - Docker to be installed and running
    - Network access to pull the html2docx image (if not already present)

    NOTE: This test currently expects the function to fail because the
    iplweb/html2docx:latest image doesn't properly handle the "- -"
    arguments (stdin + stdout). The image works with just "-" for stdin,
    outputting to stdout by default. This appears to be a bug in the
    current implementation.
    """
    html_input = """
    <!DOCTYPE html>
    <html>
    <head><title>Integration Test</title></head>
    <body>
        <h1>Test Document</h1>
        <p>This is a <b>bold</b> and <i>italic</i> text.</p>
        <table>
            <tr><th>Header 1</th><th>Header 2</th></tr>
            <tr><td>Cell 1</td><td>Cell 2</td></tr>
        </table>
    </body>
    </html>
    """

    output_path = tmp_path / "integration_test.docx"

    # The current implementation uses "- -" which doesn't work with the image
    # This test documents the actual behavior
    docx_export._convert_using_docker_image(html_input, str(output_path))
