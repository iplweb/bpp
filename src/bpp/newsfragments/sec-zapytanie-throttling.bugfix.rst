Endpointy zapytań DjangoQL ``/api/v1/zapytanie/*`` są teraz objęte
throttlingiem po użytkowniku, co ogranicza ryzyko przeciążenia bazy przez
zalogowanego użytkownika wysyłającego wiele równoległych, kosztownych zapytań.
