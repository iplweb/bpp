Import punktacji źródeł: strona postępu/wyników odświeża status
automatycznie po zakończeniu importu. Moduł przeniesiono ze starego
mechanizmu ``long_running`` (jednorazowy push przez WebSocket, który mógł
przepaść) na ``django-liveops`` — stan jest stanowy i renderowany przy
każdym wczytaniu strony, więc odświeżenie lub deep-link zawsze pokazuje
aktualny wynik.
