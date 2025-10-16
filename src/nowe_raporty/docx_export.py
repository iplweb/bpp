import logging
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from tempfile import NamedTemporaryFile

import bleach
import pypandoc
from django.conf import settings
from flexible_reports.adapters import django_tables2 as flexible_tables

LOGGER = logging.getLogger(__name__)


DEFAULT_ALLOWED_TAGS: Iterable[str] = (
    "table",
    "tr",
    "td",
    "th",
    "b",
    "i",
    "u",
    "sup",
    "sub",
    "h1",
    "h2",
    "h3",
    "h4",
    "em",
    "strong",
    "strike",
    "font",
)

DEFAULT_ALLOWED_ATTRIBUTES: Mapping[str, Iterable[str]] = {"td": ("colspan",)}

_DOCKER_IMAGE = getattr(settings, "HTML2DOCX_DOCKER_IMAGE", "iplweb/html2docx:latest")
_DOCKER_COMMAND: Iterable[str] = getattr(
    settings, "HTML2DOCX_DOCKER_COMMAND", ("docker",)
)


class DocxConversionError(RuntimeError):
    """Raised when DOCX export fails using both pandoc and html2docx."""


def as_docx(  # noqa: PLR0913
    report,
    parent_context,
    allowed_tags: Iterable[str] | None = None,
    allowed_attributes: Mapping[str, Iterable[str]] | None = None,
):
    html = flexible_tables.as_html(report, parent_context)

    cleaned_html = bleach.clean(
        html,
        tuple(allowed_tags or DEFAULT_ALLOWED_TAGS),
        dict(allowed_attributes or DEFAULT_ALLOWED_ATTRIBUTES),
        strip=True,
    )

    output_file = NamedTemporaryFile(delete=False)

    try:
        pypandoc.convert_text(
            cleaned_html,
            "docx",
            format="html",
            outputfile=output_file.name,
        )
        output_file.seek(0)
        return output_file
    except (OSError, RuntimeError) as exc:
        LOGGER.warning(
            "Pandoc conversion failed, retrying with html2docx", exc_info=exc
        )
        try:
            _convert_using_docker_image(cleaned_html, output_file.name)
        except Exception as docker_exc:  # noqa: BLE001
            output_file.close()
            raise DocxConversionError(
                "DOCX conversion failed using both pandoc and html2docx"
            ) from docker_exc

        output_file.seek(0)
        return output_file


def _convert_using_docker_image(html: str, output_path: str) -> None:
    # Use docker to run html2docx container with stdin/stdout piping
    cmd = list(_DOCKER_COMMAND) + [
        "run",
        "--rm",
        "-i",
        _DOCKER_IMAGE,
        "-",  # Read from stdin
    ]

    try:
        process = subprocess.run(  # noqa: S603
            cmd,
            input=html.encode("utf-8"),
            check=True,
            capture_output=True,
            text=False,  # Binary mode for DOCX output
        )

        # Write the captured stdout to the output file
        with open(output_path, "wb") as output_file:
            output_file.write(process.stdout)

        if process.stderr:
            LOGGER.debug(
                "html2docx docker stderr: %s",
                process.stderr.decode("utf-8", errors="replace"),
            )

    except subprocess.CalledProcessError as exc:
        LOGGER.error(
            "html2docx docker conversion failed: %s",
            (
                exc.stderr.decode("utf-8", errors="replace")
                if exc.stderr
                else "No error output"
            ),
        )
        raise
    except FileNotFoundError:
        LOGGER.error("docker executable not found")
        raise

    # Validate output
    output_file_path = Path(output_path)
    if not output_file_path.exists() or output_file_path.stat().st_size == 0:
        raise RuntimeError("html2docx docker produced no output")
