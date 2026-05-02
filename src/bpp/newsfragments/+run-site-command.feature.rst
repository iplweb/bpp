Nowa komenda ``manage.py run_site`` — uruchamia dev stack BPP w testcontainerach
na losowych portach (PG + Redis), opcjonalnie odtwarza dump bazy
(``--from-dump path``, autodetect ``.sql`` / ``.sql.gz`` / ``.dump``), tworzy
superusera ``admin/admin``, odpala ``runserver`` i otwiera przeglądarkę.
Eliminuje konflikty portów przy wielu konfiguracjach BPP na jednym serwerze.
