Kolejka eksportu do PBN: usunięto wyścigi (race conditions) przy zlecaniu i
podejmowaniu wysyłki. Dodano częściowy unikat gwarantujący co najwyżej jeden
aktywny wpis na rekord (duplikaty enqueue zamieniają się w idempotentne
``AlreadyEnqueuedError`` zamiast tworzyć zdublowane wpisy), a podejmowanie
pracy przez workera odbywa się teraz atomowo (``select_for_update`` z
pomijaniem zablokowanych wierszy), więc dwa procesy nie wyślą tego samego
rekordu równolegle.
