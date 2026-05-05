Klient PBN-API wykonuje teraz wszystkie zapytania HTTP (``GET``,
``POST``, ``DELETE``, autoryzacja OAuth) z jawnymi limitami czasu
łączenia i odpowiedzi. Wcześniej brak ``timeout`` powodował, że
zawieszony serwer PBN mógł zablokować w nieskończoność proces web
albo workera Celery. Wartość można nadpisać przez ``settings``
lub zmienną środowiskową ``PBN_CLIENT_HTTP_TIMEOUT`` (sekundy
jako liczba albo ``connect,read``); domyślnie 30 s connect / 120 s
read.
