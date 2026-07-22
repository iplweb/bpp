Kreator pierwszego uruchomienia: dwa równoległe żądania tworzące pierwsze
konto administratora nie mogą już utworzyć dwóch superużytkowników
(blokada transakcyjna zamiast sprawdzenia podatnego na wyścig). Ukończony
kreator nie wykonuje już zapytań do bazy przy każdym żądaniu — po
zakończeniu konfiguracji middleware sam się wyłącza, a widoki ``/setup/``
zwracają 404 (usunięcie uczelni lub użytkownika nie otwiera ponownie
kreatora). Wymaga ``django-first-run-wizard>=0.2.0``.
