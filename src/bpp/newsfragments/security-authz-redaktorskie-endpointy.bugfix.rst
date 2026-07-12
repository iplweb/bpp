Naprawiono lukę autoryzacji: operacje redaktorskie — klonowanie rekordów
(„Toż"), nadpisywanie punktacji źródeł, przemapowywanie i usuwanie źródeł,
dodawanie do kolejki PBN oraz cały moduł analizy/optymalizacji ewaluacji
(w tym masowe odpinanie prac i kasowanie metryk) — wymagają teraz uprawnień
„wprowadzanie danych" (lub superusera), a nie samego zalogowania. Dodatkowo
klonowanie „Toż" wykonuje się wyłącznie przez POST z tokenem CSRF (wcześniej
mutowało dane już na GET).
