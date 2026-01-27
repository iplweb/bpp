Naprawiono błąd podwójnego potwierdzenia w module ewaluacja_optymalizacja.
Kliknięcie przycisku "Policz całą ewaluację" wyświetlało dwa okna dialogowe
potwierdzenia i wysyłało dwa requesty do serwera. Przyczyną był zduplikowany
handler dla atrybutu ``data-confirm`` - jeden globalny w ``event-handlers.js``
i drugi lokalny w szablonie. Usunięto duplikat z szablonu.
