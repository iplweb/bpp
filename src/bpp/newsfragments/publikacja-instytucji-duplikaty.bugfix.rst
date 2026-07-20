Import PBN nie tworzy już zdublowanych powiązań publikacja-instytucja-osoba:
trójka (instytucja, publikacja, osoba) w ``PublikacjaInstytucji`` dostała
unikalny constraint, a migracja usuwa duplikaty istniejące w bazie
(zostawiając z każdej grupy wiersz o najniższym identyfikatorze).
