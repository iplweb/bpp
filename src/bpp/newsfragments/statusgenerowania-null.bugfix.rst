Status generowania metryk: częściowy indeks unikalny gwarantuje, że istnieje
co najwyżej jeden wiersz bez przypisanej uczelni. Wcześniej dwa równoległe
żądania mogły utworzyć dwa takie wiersze, po czym analiza odpinania publikacji
zwracała błąd 500 aż do ręcznego posprzątania bazy. Migracja usuwa nadmiarowe
wiersze, jeśli już powstały.
