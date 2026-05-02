Dodano polecenia ``dump_pbn_token`` i ``load_pbn_token`` do
przenoszenia tokenu PBN użytkownika między instancjami BPP — bez
zrzutu całej bazy. ``dump_pbn_token --user=<nazwa>`` wypisuje JSON
z tokenem i datą jego ostatniej aktualizacji na stdout, a
``load_pbn_token --user=<nazwa>`` czyta ten JSON ze stdin i ustawia
te same wartości lokalnemu użytkownikowi.

W ``run_site`` dodano flagę ``--get-pbn-token-from
USERNAME@SSH-HOST``, która automatyzuje ten transfer — łączy się po
SSH ze wskazanym hostem (alias z ``~/.ssh/config``), uruchamia
``dump_pbn_token`` w kontenerze ``appserver`` z katalogu
``bpp-deploy`` i wynik wgrywa do lokalnej bazy. Domyślne ścieżki i
nazwę serwisu można nadpisać flagami ``--remote-deploy-path`` i
``--remote-compose-service``.
