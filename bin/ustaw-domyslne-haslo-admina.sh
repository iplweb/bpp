#!/usr/bin/expect
set -euo pipefail

set timeout -1;
spawn uv run python src/manage.py changepassword admin;
expect {
    "Password:" { exp_send "foobar123\r" ; exp_continue }
    "Password (again):" { exp_send "foobar123\r" ; exp_continue }
    eof
}
