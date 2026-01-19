Naprawiono błąd "NOT NULL constraint" dla pola ``error_traceback`` w tabeli
``pbn_import_importsession``, który występował podczas automatycznego anulowania
utraconej sesji importu PBN. Metoda ``auto_cancel_if_lost()`` używa teraz
``mark_failed()`` zamiast ręcznego ustawiania pól, co zapewnia poprawne
wypełnienie wszystkich wymaganych pól (w tym ``error_traceback`` i ``completed_at``).
