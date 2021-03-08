#!/usr/bin/expect

set timeout -1;
spawn python src/manage.py changepassword admin;
expect {
    "Password:" { exp_send "foobar123\r" ; exp_continue }
    "Password (again):" { exp_send "foobar123\r" ; exp_continue }
    eof
}
