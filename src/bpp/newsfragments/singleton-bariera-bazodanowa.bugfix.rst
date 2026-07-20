Dodano barierę bazodanową (advisory lock, niezależną od Redisa) chroniącą
dwa najgroźniejsze zadania — optymalizację z odpinaniem oraz odpinanie
wszystkich sensownych możliwości — przed równoległym uruchomieniem po tym,
jak rolling restart workera skasuje lock ``celery_singleton``. Duplikat
przebiegu wycofuje się, zanim wejdzie w masowe odpinanie przypięć uczelni.
