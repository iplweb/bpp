Eksporty XLSX (porównanie publikacji BPP–PBN, lista publikacji
do wysyłki oświadczeń) sanityzują teraz wartości komórek przed
zapisem. Wartości tekstowe zaczynające się od ``=``, ``+``, ``-``,
``@`` lub białego separatora są poprzedzane apostrofem,
co powstrzymuje Excela / LibreOffice'a przed interpretacją ich
jako formuł (CSV/Formula Injection wg OWASP). Pomocnicza funkcja
``bpp.util.sanitize_xlsx_cell`` / ``sanitize_xlsx_row`` jest
dostępna do wykorzystania w kolejnych eksportach.
