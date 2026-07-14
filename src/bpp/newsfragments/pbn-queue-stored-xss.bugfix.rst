Naprawiono podatność stored-XSS przy wyświetlaniu błędów kolejki eksportu do
PBN. Treść błędu pochodząca z PBN (niezaufana) była wstawiana do HTML bez
escapowania — w filtrze ``format_pbn_error``, w widgecie panelu admina oraz
przez ``|safe`` w szablonie szczegółów. Wszystkie te miejsca escapują teraz
dane PBN przed wyrenderowaniem.
