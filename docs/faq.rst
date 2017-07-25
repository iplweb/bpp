Często zadawane pytania
=======================

Przy eksporcie PBN, mogę wybrać datę "data ostatniej zmiany" lub "data ostatniej zmiany dla PBN", jaka jest między nimi różnica?
--------------------------------------------------------------------------------------------------------------------------------


"Data ostatniej zmiany" to data ostatniej zmiany rekordu. To pole
aktualizowane jest automatycznie, zawiera datę i czas w momencie zapisywania
rekordu w module "Redagowanie".

"Data ostatniej zmiany dla PBN" to pole, które wskazuje na datę ostatniej
zmiany rekordu w sytuacji, gdyby zmieniły się jakiekolwiek informacje mające
wpływ na zapis rekordu w systemie PBN. Lub też, innymi słowy - aktualizacja
tego pola nie zachodzi w momencie, gdy zmieniane dane nie mają swojego
odzwierciedlenia w PBN i nie powinny być w PBN aktualizowane.

Przykładowo, jeżeli zmienimy punktację pracy (impact factor, punkty KBN) to
data aktualizacji dla PBN nie powinna ulec zmianie, zmieni się zaś data
ostatniej zmiany.

Jeżeli dodamy lub usuniemy powiązania rekordu z autorem, to data
aktualizacji dla PBN powinna ulec zmianie, jak również data ostatniej zmiany.

Zainteresowanych odsyłamy do `kodu źródłowego`_.


.. _kodu źródłowego: https://github.com/mpasternak/django-bpp/blob/dev/src/bpp/models/abstract.py#L831-L841
