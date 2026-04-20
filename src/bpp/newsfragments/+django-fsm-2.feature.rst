Zastąpiono nieutrzymywany pakiet ``django-fsm`` jego aktywnie
rozwijanym forkiem ``django-fsm-2``. API pozostało niezmienione
(``from django_fsm import FSMField, transition, GET_STATE``),
więc zmiana jest przezroczysta dla kodu i migracji bazy danych.
Dzięki temu znika ostrzeżenie ``UserWarning`` o braku wsparcia
dla ``django-fsm``.
