Import pracowników: zatwierdzenie importu używa teraz atomowego compare-and-set
na stanie, więc dwa równoległe zatwierdzenia (np. podwójne kliknięcie przy
wielu workerach) nie mogą już uruchomić integracji dwa razy i zduplikować
utworzonych autorów, jednostek czy przepięć prac.
