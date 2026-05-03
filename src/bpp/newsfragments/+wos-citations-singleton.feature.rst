Task ``zaktualizuj_liczbe_cytowan`` (pobieranie liczby
cytowań z Web of Science) używa teraz
``celery_singleton.Singleton`` z 2-godzinnym lockiem
w Redisie i ``time_limit=2h``. Dwa równoczesne uruchomienia
(np. ręczne kliknięcie + zaplanowany cron) nie odpytają już
zewnętrznego API podwójnie, a zawieszony WoS request
nie zablokuje workera w nieskończoność.
