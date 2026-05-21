Cztery widoki wykonujące mutacje danych zostały przerobione z metody
HTTP ``GET`` na ``POST`` z ekranem potwierdzenia. Wcześniej kliknięcie
zwykłego linku (lub np. prefetch w przeglądarce) mogło wykonać ciężką
operację bez świadomej akcji użytkownika i bez ochrony CSRF. Teraz
``GET`` wyświetla ekran potwierdzenia z formularzem ``POST``,
zabezpieczonym tokenem CSRF, a sama mutacja wykonywana jest dopiero
po akceptacji.

Dotyczy widoków:

- ``komparator_pbn_udzialy:rebuild`` — przebudowa rozbieżności PBN
  (uruchamia zadanie Celery z ``clear_existing=True``).
- ``rozbieznosci_if:ustaw_wszystkie`` — masowe ustawienie IF
  z punktacji źródła dla przefiltrowanych rekordów.
- ``rozbieznosci_pk:ustaw_wszystkie`` — masowe ustawienie punktów
  MNiSW z punktacji źródła dla przefiltrowanych rekordów.
- ``snapshot_odpiec:nowy`` — utworzenie nowego snapshotu odpięć.
- ``snapshot_odpiec:aplikuj`` — zaaplikowanie snapshotu na bazę.
