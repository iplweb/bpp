Kosztowne endpointy wyszukiwania API (``/api/v1/szukaj/`` pełnotekstowe oraz
``/api/v1/autor/`` z filtrem ``nazwisko__icontains``) mają teraz limity liczby
żądań (osobne dla anonimowych i zalogowanych), chroniące przed nadużyciami.
Globalny throttling reszty API pozostaje wyłączony bez zmian.
