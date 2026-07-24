Przebudowa bazy od zera (odtworzenie wszystkich migracji na pustej bazie)
nie pada już na dwóch latentnych blokerach kolejności. Po pierwsze, usunięto
wywołania ``denorm_init`` w środku historii migracji, które budowały triggery
z dzisiejszych modeli i odwoływały się do kolumn dochodzących dopiero w
późniejszych migracjach — triggery denorm odtwarza teraz sygnał
``post_migrate`` na kompletnym schemacie. Po drugie, migracja indeksów GIN
zakładająca indeks na tabeli ``easyaudit_crudevent`` deklaruje teraz zależność
od aplikacji ``easyaudit``, więc tabela istnieje, zanim indeks zostanie
utworzony. Obie zmiany są no-opem dla istniejących baz.
