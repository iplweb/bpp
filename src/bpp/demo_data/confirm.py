"""Podwojne potwierdzenie dla destrukcyjnych komend demo_data."""

from __future__ import annotations


class ConfirmAborted(Exception):
    """Uzytkownik nie potwierdzil albo non-tty bez flag."""


def double_confirm(
    *,
    stdin,
    stdout,
    database: str,
    plan_text: str,
    yes_flag: bool,
    confirm_db_flag: str | None,
):
    """Dwustopniowa walidacja:
    - bypass: yes_flag + confirm_db_flag == database
    - non-tty: musi byc bypass, inaczej ConfirmAborted
    - tty: prompt 'tak/nie' (case-insensitive) + prompt z dokladnym
      wpisaniem nazwy bazy (case-sensitive).
    """
    if yes_flag:
        if confirm_db_flag != database:
            raise ConfirmAborted(f"--confirm-db '{confirm_db_flag}' != '{database}'")
        return

    if not stdin.isatty():
        raise ConfirmAborted(
            "Brak TTY. Uzyj '--yes-i-am-sure --confirm-db <NAME>' "
            "w trybie nie-interaktywnym."
        )

    stdout.write(plan_text + "\n")
    stdout.write(f"Kontynuowac w bazie '{database}'? [tak/nie]: ")
    stdout.flush()
    answer = stdin.readline().strip().lower()
    if answer != "tak":
        raise ConfirmAborted("Anulowane w prompcie #1.")

    stdout.write(f"Aby potwierdzic, wpisz dokladnie nazwe bazy: '{database}': ")
    stdout.flush()
    db_input = stdin.readline().rstrip("\n")
    if db_input != database:
        raise ConfirmAborted(f"Nazwa bazy nie pasuje: '{db_input}' != '{database}'.")
