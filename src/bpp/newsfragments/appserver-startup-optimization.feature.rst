Zoptymalizowano czas startu serwera aplikacji. Migracje bazy danych wykonywane są synchronicznie,
natomiast zadania collectstatic, compress i generate_500_page uruchamiane są w tle równolegle
ze startem serwera uvicorn. Skraca to czas do dostępności serwera o ~15-90 sekund.
