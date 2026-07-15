Import pracowników w instalacji z wieloma uczelniami: jednostki oznaczone „do
utworzenia" nie były tworzone (a powiązani z nimi pracownicy po cichu pomijani),
bo pipeline w tle ustalał uczelnię przez „jedyną w systemie" — przy >1 uczelni
degradowało to do braku uczelni. Import zapamiętuje teraz uczelnię z requestu
(host → Site → Uczelnia) i używa jej przy tworzeniu jednostek. Gdy uczelni nie da
się ustalić jednoznacznie, ekran weryfikacji jednostek wyświetla widoczne
ostrzeżenie zamiast po cichu pomijać import.
