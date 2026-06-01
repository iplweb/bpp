"""Testy double-confirm dla demo_data."""

import io

import pytest

from bpp.demo_data.confirm import ConfirmAborted, double_confirm


def _stdin(text: str) -> io.StringIO:
    buf = io.StringIO(text)
    buf.isatty = lambda: True
    return buf


def _non_tty_stdin(text: str = "") -> io.StringIO:
    buf = io.StringIO(text)
    buf.isatty = lambda: False
    return buf


def test_bypass_via_flags():
    out = io.StringIO()
    double_confirm(
        stdin=_stdin(""),
        stdout=out,
        database="bpp",
        plan_text="...",
        yes_flag=True,
        confirm_db_flag="bpp",
    )


def test_bypass_wrong_db_name_raises():
    out = io.StringIO()
    with pytest.raises(ConfirmAborted):
        double_confirm(
            stdin=_stdin(""),
            stdout=out,
            database="bpp",
            plan_text="...",
            yes_flag=True,
            confirm_db_flag="other_db",
        )


def test_non_tty_without_flags_raises():
    with pytest.raises(ConfirmAborted) as exc:
        double_confirm(
            stdin=_non_tty_stdin(),
            stdout=io.StringIO(),
            database="bpp",
            plan_text="...",
            yes_flag=False,
            confirm_db_flag=None,
        )
    assert "TTY" in str(exc.value) or "--yes-i-am-sure" in str(exc.value)


def test_prompt_one_no_raises():
    with pytest.raises(ConfirmAborted):
        double_confirm(
            stdin=_stdin("nie\n"),
            stdout=io.StringIO(),
            database="bpp",
            plan_text="X",
            yes_flag=False,
            confirm_db_flag=None,
        )


def test_prompt_two_wrong_db_name_raises():
    with pytest.raises(ConfirmAborted):
        double_confirm(
            stdin=_stdin("tak\nzla_baza\n"),
            stdout=io.StringIO(),
            database="bpp",
            plan_text="X",
            yes_flag=False,
            confirm_db_flag=None,
        )


def test_both_prompts_pass():
    double_confirm(
        stdin=_stdin("tak\nbpp\n"),
        stdout=io.StringIO(),
        database="bpp",
        plan_text="X",
        yes_flag=False,
        confirm_db_flag=None,
    )


def test_prompt_one_case_insensitive():
    double_confirm(
        stdin=_stdin("TAK\nbpp\n"),
        stdout=io.StringIO(),
        database="bpp",
        plan_text="X",
        yes_flag=False,
        confirm_db_flag=None,
    )


def test_prompt_two_case_sensitive_db_name():
    with pytest.raises(ConfirmAborted):
        double_confirm(
            stdin=_stdin("tak\nBPP\n"),
            stdout=io.StringIO(),
            database="bpp",
            plan_text="X",
            yes_flag=False,
            confirm_db_flag=None,
        )
