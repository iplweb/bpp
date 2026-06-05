Widok „Szukaj zapytaniem" oraz wyszukiwarki DjangoQL w panelu
administracyjnym zyskują wygodniejszy edytor zapytań (dzięki
nowej wersji ``djangoql-iplweb``):

* **Podświetlanie składni** w polu zapytania, a w razie błędu —
  czerwona falka pod miejscem, które trzeba poprawić (nieznane
  pole albo błąd składni).
* **Zapytania wieloliniowe** — ``Shift+Enter`` wstawia nową linię,
  zwykły ``Enter`` nadal wykonuje wyszukiwanie.
* **Przycisk „Sformatuj"** — czytelnie wcina i łamie długie
  zapytanie na wiele linii.
* **Panel „Wyjaśnij liczby"** — na żądanie pokazuje, ile rekordów
  pasuje do każdej gałęzi zapytania (czerwone = tu wynik schodzi do
  zera, bursztynowe = martwa gałąź ``or``). Uzupełnia dotychczasowe
  rozbicie „dlaczego 0 wyników".
* **Podpowiedzi wartości w listach** ``pole in ( … )`` — autocomplete
  działa też wewnątrz nawiasów listy, nie tylko po operatorze.

W panelu administracyjnym podświetlanie składni jest włączone dla
wszystkich wyszukiwarek DjangoQL.
