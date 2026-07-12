Importer publikacji izoluje teraz sesje i paczki między uczelniami w trybie
multi-host: redaktor jednej uczelni nie odczyta ani nie zmodyfikuje sesji,
paczki BibTeX ani jej wpisu należących do innej uczelni (dotąd obiekty
pobierano po samym identyfikatorze — podatność IDOR). W obrębie jednej
uczelni warsztat pozostaje współdzielony; superuser widzi wszystko.
