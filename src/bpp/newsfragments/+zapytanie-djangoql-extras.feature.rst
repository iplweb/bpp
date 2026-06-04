Wyszukiwarka zapytań DjangoQL (``/bpp/zapytanie/``) obsługuje teraz
agregaty relacji oraz części dat. W zapytaniu można odwołać się do
liczby powiązanych obiektów przez ``<relacja>__count`` (np.
``autorzy__count > 5`` zwraca rekordy z więcej niż pięcioma autorami)
oraz do sum, średnich, minimów i maksimów pól liczbowych powiązanych
modeli przez ``<relacja>__<pole>__sum`` / ``__avg`` / ``__min`` /
``__max``.

Pola dat i czasu można porównywać po wyodrębnionych częściach —
``<pole>__year``, ``__month``, ``__day``, ``__quarter`` itd., a dla
pól ze znacznikiem czasu dodatkowo ``__hour``, ``__minute``,
``__second``.

Nowe pola pojawiają się również w podpowiedziach (autouzupełnianiu)
edytora zapytań.
