#!/bin/bash
set -euo pipefail

# import danych SGSP

pkill -TERM -f "src/manage.py runserver"
dropdb bpp
createdb bpp
python src/manage.py migrate

gzcat ~/Programowanie/bpp-assets/initial_data/bpp.Dyscyplina_Naukowa.yaml.gz | python src/manage.py loaddata --format=yaml -
gzcat ~/Programowanie/bpp-assets/initial_data/pbn_api.Publisher.yaml.gz | python src/manage.py loaddata --format=yaml -
gzcat ~/Programowanie/bpp-assets/initial_data/bpp.Wydawca.yaml.gz | python src/manage.py loaddata --format=yaml -

python src/manage.py import_sgsp ~/Desktop/artykuly_autor_2021.xlsx

python src/manage.py denorm_rebuild

python src/manage.py createsuperuser --noinput --email michal.dtz@gmail.com --username admin

BASEDIR=$(dirname "$0")

$BASEDIR/fix-sequences.sh
