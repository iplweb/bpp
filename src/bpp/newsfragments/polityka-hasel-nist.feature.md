Nowa polityka haseł zgodna z NIST SP 800-63B: hasło ma co najmniej 15 znaków,
ale nie musi już zawierać cyfr ani znaków specjalnych, a system przestał
wymuszać zmianę hasła co 30 dni (rotację można przywrócić zmienną
`DJANGO_BPP_PASSWORD_DURATION_SECONDS`). Te same wymagania obowiązują teraz
także przy zakładaniu konta w panelu administracyjnym i w kreatorze
pierwszego uruchomienia. Istniejące hasła pozostają ważne.

Nowa komenda `manage.py wymus_zmiane_hasel` wymusza zmianę hasła przy
najbliższym wejściu na stronę wszystkim użytkownikom logującym się hasłem BPP
(albo tylko wskazanym loginom lub członkom grup; `--dry-run` pokazuje, kogo
obejmie).
