W module optymalizacji ewaluacji zmieniono nazwę tabeli "Ostatnie optymalizacje" na "Ostatnie kalkulacje".
Dodano przycisk "Resetuj przypięcia" w wierszu RAZEM, który resetuje przypięcia dla wszystkich rekordów
z lat 2022-2025, gdzie autor ma dyscyplinę, jest zatrudniony i afiliuje. Operacja działa asynchronicznie
przez zadanie Celery, tworzy snapshot przed zmianami i automatycznie przelicza punktację.
