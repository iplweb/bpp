Bezpieczeństwo: importery plików XLSX odrzucają teraz bomby dekompresyjne
(zip-bomb) — plik, który po rozpakowaniu przekracza bezpieczny limit
rozmiaru, jest odrzucany przed załadowaniem do pamięci, co chroni workera
importu przed wyczerpaniem pamięci (OOM). Dotyczy import_common,
import_dyscyplin, integrator2, ewaluacja2021 oraz import_polon.
