``pobierz_mongodb`` przyjmuje teraz parametr ``on_error``: ``"raise"`` (domyślne,
dotychczasowe fail-fast — błąd zapisu jednego rekordu przerywa cały import) lub
``"skip"`` (deleguje do pakietowego ``download_to_model`` — zły rekord jest
logowany i liczony, a import reszty listy kończy się; zwraca
``DownloadResult(processed, errored)``). Przydatne przy masowych synchronizacjach,
gdzie pojedynczy zepsuty rekord nie powinien przerywać całego przebiegu.
Zachowanie domyślne bez zmian.
