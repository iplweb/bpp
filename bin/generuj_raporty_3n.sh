#!/bin/bash
set -euo pipefail

for dyscyplina in `echo "select bpp_dyscyplina_naukowa.nazwa from ewaluacja2021_liczbandlauczelni, bpp_dyscyplina_naukowa where ewaluacja2021_liczbandlauczelni.dyscyplina_naukowa_id = bpp_dyscyplina_naukowa.id; " | psql bpp --csv|tail -n +2|sed s/\ /_/g`; do python src/manage.py raport_3n_plecakowy --dyscyplina="$(echo $dyscyplina|sed s/_/\ /g)"; python src/manage.py raport_3n_genetyczny --dyscyplina="$(echo $dyscyplina|sed s/_/\ /g)"; done

for a in plecakowy_*json; do python src/manage.py raport_3n_to_xlsx "$a"; done

for a in genetyczny_*json; do python src/manage.py raport_3n_to_xlsx "$a"; done
