Import plików XLSX odrzuca teraz nadmiernie duże pliki przed przetwarzaniem i
wczytuje skoroszyt strumieniowo (tryb read-only), co zabezpiecza workera
importu przed wyczerpaniem pamięci (OOM) na „grubym" pliku.
