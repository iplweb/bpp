Tworzenie zadań w tle dla pobrań z PBN
(``pbn_downloader_app.tasks.create_task_with_lock``) oraz wysyłki
oświadczeń (``pbn_wysylka_oswiadczen`` widok startu zadania) jest
teraz chronione przez Postgresowy advisory lock. Wcześniej sprawdzenie
``filter(status="running").exists()`` wewnątrz ``transaction.atomic()``
nie gwarantowało wzajemnego wykluczenia — dwa równoczesne żądania
mogły obydwa nie znaleźć aktywnego zadania i obydwa założyć kolejne,
przez co dwóch workerów mogło naraz wykonywać tę samą operację.
