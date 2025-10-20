Poprawiono wyświetlanie postępu w funkcji "Optymalizuj, odpinając sloty":

- Faza denormalizacji teraz pokazuje liczbę rekordów do przeliczenia zamiast ogólnego komunikatu "Sprawdzanie kolejki przeliczania"
- Procent postępu w pasku jest teraz zaokrąglony do liczby całkowitej (zamiast wielu miejsc po przecinku)
- Po zakończeniu zadania system teraz poprawnie przekierowuje do strony głównej z komunikatem o sukcesie zamiast wyświetlać stronę z "zadaniem w trakcie wykonywania"
- Monitorowanie postępu odbywa się przez bazę danych (dla fazy optymalizacji) i task.info (dla fazy denormalizacji)
