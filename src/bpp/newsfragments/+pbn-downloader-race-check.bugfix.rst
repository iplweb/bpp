Task ``pbn_downloader_app.tasks.download_institution_publications``
nie wykonuje już redundantnego sprawdzenia stanu
„running” poza transakcją. Atomowy check-and-create
w ``create_task_with_lock`` nadal zapobiega duplikatom;
usunięcie wcześniejszego, nie-atomowego check-a likwiduje
race-window, w którym dwa workery przechodziły check, oba
otrzymywały ``ValueError`` w wyścigu o lock i jeden niepotrzebnie
failował zamiast po prostu czekać.
