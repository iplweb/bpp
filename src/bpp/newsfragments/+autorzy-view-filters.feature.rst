Przeglądanie autorów działa szybciej i poprawniej ukrywa autorów
obcych: lista nie buduje już GROUP BY po wszystkich przypisaniach
autorów, filtr „autorzy bez prac" korzysta ze zmaterializowanej tabeli
cache zamiast skanować pięć tabel źródłowych, a autor przypisany
wyłącznie do jednostki sztucznej (Obca / „Błędna") jest teraz ukrywany
także wtedy, gdy figuruje tylko w jednej z nich.
