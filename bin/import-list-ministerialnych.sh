#!/bin/bash

#python src/manage.py import_lista_ministerialna_xlsx --url https://www.gov.pl/attachment/c2510527-171a-451e-b3c4-74ea5a5c6c94 --fn lista-ministerialna-2024.xlsx --rok 2024 --dry-run --download

#python src/manage.py import_lista_ministerialna_xlsx --url https://www.gov.pl/attachment/e0aab563-4aa9-4944-a057-a436527cad3d --fn lista-ministerialna-2023.xlsx --rok 2023 --dry-run --download

python src/manage.py import_lista_ministerialna_xlsx --url https://www.gov.pl/attachment/35896404-7908-4dc7-bcac-39bd0e68babc --fn lista-ministerialna-2022.xlsx --rok 2022 --dry-run --download
