"""Characterization tests for the ``compare_dbtemplates`` management command.

These tests pin the *current* observable behaviour of ``Command.handle`` and
``Command.compare_template`` before the C901 refactor. The filesystem side of
the comparison is stubbed via ``get_filesystem_template_content`` so the tests
are deterministic and do not depend on real template files on disk.

The baseline database already ships dbtemplates rows (loaded via a
data-migration) which cannot be deleted (protected FKs), so each test scopes
the comparison to explicit ``template_names`` instead of relying on an empty
table.
"""

import io
from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from model_bakery import baker

from bpp.management.commands.compare_dbtemplates import Command


@pytest.fixture
def template(db):
    from dbtemplates.models import Template

    return baker.make(Template, name="foo/bar.html", content="line1\nline2\n")


def _run(*args, fs_content, **kwargs):
    """Call the command with the filesystem side stubbed.

    ``fs_content`` may be a string/None (same for every template) or a
    callable taking the template name and returning the content.

    ``mock.patch.object`` replaces the method with a plain Mock, so the stub
    is called as ``get_filesystem_template_content(name)`` — no bound
    ``self`` is passed.
    """
    out = io.StringIO()
    err = io.StringIO()

    if callable(fs_content):
        side_effect = lambda name: fs_content(name)  # noqa: E731
    else:
        side_effect = lambda name: fs_content  # noqa: E731

    with mock.patch.object(
        Command, "get_filesystem_template_content", side_effect=side_effect
    ):
        call_command("compare_dbtemplates", *args, stdout=out, stderr=err, **kwargs)
    return out.getvalue(), err.getvalue()


@pytest.mark.django_db
def test_list_templates(template):
    from dbtemplates.models import Template

    baker.make(Template, name="missing/onfs.html", content="x")

    def fs(name):
        return "content" if name == "foo/bar.html" else None

    out, err = _run("--list", fs_content=fs)

    assert "templates in database:" in out
    assert "✓ foo/bar.html" in out
    assert "✗ missing/onfs.html" in out


@pytest.mark.django_db
def test_no_templates_raises(template):
    # Only a non-existent name is requested → nothing to compare → CommandError.
    with pytest.raises(CommandError, match="No templates to compare"):
        _run("does-not-exist.html", fs_content="whatever")


@pytest.mark.django_db
def test_all_match(template):
    out, err = _run("foo/bar.html", fs_content="line1\nline2\n")

    assert "All 1 templates match their filesystem counterparts" in out


@pytest.mark.django_db
def test_diff_reported(template):
    out, err = _run("foo/bar.html", fs_content="line1\nDIFFERENT\n")

    assert "Template: foo/bar.html" in out
    assert "=" * 60 in out
    assert "-DIFFERENT" in out
    assert "+line2" in out
    assert "Found differences in 1 out of 1 templates" in out


@pytest.mark.django_db
def test_filesystem_not_found(template):
    out, err = _run("foo/bar.html", fs_content=None)

    assert "--- Template: foo/bar.html" in out
    assert "!!! Filesystem template not found" in out
    assert "Found differences in 1 out of 1 templates" in out


@pytest.mark.django_db
def test_only_display_changed_lists_names(template):
    from dbtemplates.models import Template

    baker.make(Template, name="same/same.html", content="aaa")

    def fs(name):
        # foo/bar.html differs; same/same.html matches
        return "aaa" if name == "same/same.html" else "totally other"

    out, err = _run(
        "foo/bar.html", "same/same.html", "--only-display-changed", fs_content=fs
    )

    assert "foo/bar.html" in out
    assert "same/same.html" not in out
    assert "Found differences in 1 out of 2 templates" in out


@pytest.mark.django_db
def test_only_display_changed_to_file(template, tmp_path):
    target = tmp_path / "changed.txt"
    out, err = _run(
        "foo/bar.html",
        "--only-display-changed",
        f"--output={target}",
        fs_content="nope different",
    )

    assert target.read_text(encoding="utf-8").strip() == "foo/bar.html"
    assert f"Changed template names written to {target}" in out


@pytest.mark.django_db
def test_diff_to_file(template, tmp_path):
    target = tmp_path / "diff.txt"
    out, err = _run(
        "foo/bar.html", f"--output={target}", fs_content="line1\nDIFFERENT\n"
    )

    written = target.read_text(encoding="utf-8")
    assert "Template: foo/bar.html" in written
    assert f"Differences written to {target}" in out


@pytest.mark.django_db
def test_specific_template_missing_in_db_warns(template):
    out, err = _run("foo/bar.html", "nonexistent.html", fs_content="line1\nline2\n")

    assert "Template 'nonexistent.html' not found in database" in err
    # foo/bar.html matches, so overall "All N match"
    assert "All 1 templates match their filesystem counterparts" in out


@pytest.mark.django_db
def test_ignore_whitespace_makes_equal(template):
    # Same logical lines, differing only by leading/trailing whitespace.
    out, err = _run(
        "foo/bar.html", "--ignore-whitespace", fs_content="  line1  \n\tline2\t\n"
    )

    assert "All 1 templates match their filesystem counterparts" in out


@pytest.mark.django_db
def test_without_ignore_whitespace_differs(template):
    out, err = _run("foo/bar.html", fs_content="  line1  \n\tline2\t\n")

    assert "Found differences in 1 out of 1 templates" in out


@pytest.mark.django_db
def test_color_branch_when_tty(template):
    # Force the coloring branch (sys.stdout.isatty() True) and ensure the
    # diff body still renders. Django styling is a no-op on a non-tty
    # underlying stream, so we only assert on content, not ANSI codes.
    with mock.patch("sys.stdout.isatty", return_value=True):
        out, err = _run("foo/bar.html", fs_content="line1\nDIFFERENT\n")

    assert "Template: foo/bar.html" in out
    assert "DIFFERENT" in out


@pytest.mark.django_db
def test_compare_template_returns_none_on_match(template):
    cmd = Command()
    options = {
        "ignore_whitespace": False,
        "side_by_side": False,
        "context_lines": 3,
        "no_color": True,
    }
    with mock.patch.object(
        Command, "get_filesystem_template_content", return_value="line1\nline2\n"
    ):
        assert cmd.compare_template(template, options) is None


@pytest.mark.django_db
def test_compare_template_side_by_side(template):
    cmd = Command()
    options = {
        "ignore_whitespace": False,
        "side_by_side": True,
        "context_lines": 3,
        "no_color": True,
    }
    with mock.patch.object(
        Command, "get_filesystem_template_content", return_value="line1\nX\n"
    ):
        result = cmd.compare_template(template, options)

    assert result is not None
    assert any("Template: foo/bar.html" in line for line in result)
    assert any(line.startswith("-X") for line in result)
