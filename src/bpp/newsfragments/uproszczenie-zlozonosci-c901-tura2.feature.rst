Uproszczono kolejne 22 złożone funkcje oznaczone dotąd ``# noqa: C901``
(scoring i przemapowywanie podobnych źródeł PBN, scalanie i wyszukiwanie
duplikatów autorów oraz źródeł, dopasowywanie autorów po stronie PBN, import
słowników/dyscyplin/czasopism PBN, budowa menu, eksport XLSX raportu slotów,
parsowanie historii komunikatów PBN, finder plików statycznych, middleware
blokujące złośliwe żądania, polecenie porównywania szablonów oraz aktualizacja
liczby cytowań z WoS). Powtarzalne łańcuchy ``if``/``elif`` i zduplikowane
bloki zastąpiono tabelami danych (reguły scoringu, deskryptory pól, listy
strategii dopasowania) oraz wydzielonymi funkcjami pomocniczymi; każda funkcja
ma teraz złożoność cyklomatyczną poniżej 10. Zachowanie jest niezmienione —
zabezpieczone nowymi testami charakteryzującymi pinującymi bieżące zachowanie
przed refaktorem — a kod jest znacznie czytelniejszy i łatwiejszy w utrzymaniu.
