Ekran „Import pracowników — przetwarzanie” znów pokazuje postęp na żywo
(etapy, log oraz panel wyniku) bez ręcznego przeładowywania strony.
Wcześniej, gdy serwis korzystał równocześnie z powiadomień WebSocket w
innym miejscu, subskrypcja operacji była nadpisywana i strona pozostawała
pusta aż do odświeżenia. Dodatkowo przycisk „Zapisz zmiany do bazy” na
panelu wyniku działa teraz także wtedy, gdy panel pojawił się przez
WebSocket (bez pełnego przeładowania). Wymaga ``django-channels-broadcast``
w wersji 0.2.2 lub nowszej.
