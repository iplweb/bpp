Stopka serwisu (oraz panel admina i Rollbar ``code_version``) na produkcji
pokazuje teraz finalną wersję wydania bez sufiksu ``rcN``. Promocja RC →
produkcja nakłada cienki patch-layer na przetestowany obraz RC, podmieniając
zapieczoną wersję kandydata na finalną; deployment ``:staging`` nadal pokazuje
wersję ``rcN`` wraz z git SHA.
