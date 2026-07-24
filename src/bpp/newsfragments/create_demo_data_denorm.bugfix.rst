Naprawiono komendę ``create_demo_data``: nazwy wydziałów i jednostek są teraz
globalnie unikalne także dla motywów z małą pulą nazw (dawniej cyklowanie /
losowanie zderzało się z unikalnym indeksem ``nazwa`` → ``IntegrityError``),
a masowe wstawianie (``bulk_create``) jest odporne na przejściowe deadlocki z
równoległym workerem denorm (Celery ``flush_single``) dzięki retry na
``40P01``/``40001``.
