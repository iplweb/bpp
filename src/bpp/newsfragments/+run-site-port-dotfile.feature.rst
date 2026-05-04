``manage.py run_site`` zapisuje teraz numer portu runservera do
gitignored pliku ``.run_site_port`` (analogicznie do
``.run_site_token``). Agent kodujący nie musi już parsować bannera
ani logów — składa URL z ``cat .run_site_port`` + ``cat
.run_site_token``. Plik jest ulotny: kasowany na exit run_site.
