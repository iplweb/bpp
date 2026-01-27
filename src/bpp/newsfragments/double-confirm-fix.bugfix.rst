Naprawiono błąd podwójnego potwierdzenia w modułach ewaluacja_optymalizacja,
multiseek oraz import_dyscyplin. Kliknięcie przycisków z atrybutem
``data-confirm`` wyświetlało dwa okna dialogowe potwierdzenia. Przyczyną były
zduplikowane handlery - globalny w ``event-handlers.js`` i lokalne w szablonach.
Usunięto duplikaty z szablonów, pozostawiając obsługę w globalnym handlerze.
