Naprawiono przedwczesne pokazywanie komunikatu "zadanie zakończone" w funkcji "Optymalizuj, odpinając sloty":

- Naprawiono status "Zakończono" pokazujący się od razu po wejściu na stronę statusu zadania. Status teraz zawsze pokazuje "W trakcie" dopóki `task.ready() == False`, bez względu na stan bazy danych (która może zawierać stare rekordy z poprzedniego uruchomienia przed ich skasowaniem przez zadanie Celery).
- System teraz czeka aż zadanie Celery faktycznie zakończy się (`task.ready() == True`) zanim pokaże komunikat o sukcesie w sekcji postępu, zamiast wyświetlać sukces gdy `completed_count == discipline_count == 0` na samym początku procesu.
