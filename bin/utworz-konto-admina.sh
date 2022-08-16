#!/bin/sh
python src/manage.py createsuperuser --username admin --noinput --email admin@admin.pl;
./bin/ustaw-domyslne-haslo-admina.sh
