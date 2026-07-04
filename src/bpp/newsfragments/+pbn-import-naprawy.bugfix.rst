Import PBN: anulowanie importu przez przycisk (HTMX) nie kończy się już
błędem 500 (odwołanie do nieistniejącej trasy w szablonie postępu).
Dodatkowo zapisy postępu nie nadpisują się nawzajem (zawężone zapisy pola
``progress_data`` i odświeżenie przed modyfikacją), a sondaż autoryzacji
PBN przeniesiono z konstruktora menedżera importu do startu zadania
(brak ukrytego wywołania API przy samym utworzeniu obiektu).
