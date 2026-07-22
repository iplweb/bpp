Naprawiono endpoint ``/api/v1/autor/`` (regresja #568): pole ``email`` było
zadeklarowane w serializerze, ale pominięte w ``Meta.fields`` — każde żądanie
kończyło się błędem 500. E-mail jest teraz usuwany z odpowiedzi dla anonimów
(klucz nieobecny, nie pusty), a zalogowani redaktorzy widzą także autorów
ukrytych (``pokazuj=False``).
