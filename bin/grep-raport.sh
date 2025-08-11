#!/bin/bash
set -euo pipefail

# Polecenie towarzyszące poleceniu z systemu `import_lista_ministerialna_2023`
# dzieli plik wyjściowy na kilka strumieni, każdy wysyła do oddzielnego
# pliku CSV.

for a in PKT-0 PKT-1 PKT-2 PKT-3 PKT-4 PKT-5; do
    grep $a $1 | sort | uniq > $1-$a.csv;
done
