==================================================
Konfiguracja SSL z Let's Encrypt dla wdrożenia BPP
==================================================

Ten dokument opisuje sposób konfiguracji certyfikatów SSL z Let's Encrypt dla systemu BPP przy użyciu Docker Compose.

Przegląd
--------

Konfiguracja wykorzystuje podejście wieloetapowe:

1. **Serwer HTTP**: Działa na porcie 80, obsługuje wyzwania ACME
2. **Certbot**: Pobiera certyfikaty z Let's Encrypt
3. **Serwer HTTPS**: Uruchamia główną aplikację z SSL na porcie 443

Wymagania wstępne
-----------------

* Docker i Docker Compose zainstalowane na serwerze
* Nazwa domeny wskazująca na serwer
* Porty 80 i 443 dostępne z internetu
* Brak innych usług wykorzystujących porty 80 i 443

Szybki start
------------

Przygotowanie środowiska
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Skopiuj przykładowy plik środowiskowy
   cp .env.docker.ssl.example .env.docker

   # Edytuj konfigurację
   nano .env.docker

**Wymagana konfiguracja:**

* ``SITE_NAME``: Nazwa domeny (np. ``bpp.uniwersytet.edu.pl``)
* ``ADMIN_EMAIL``: Email do powiadomień z Let's Encrypt
* ``SECRET_KEY``: Wygeneruj bezpieczny klucz Django
* ``DATABASE_URL``: Ciąg połączenia z bazą danych

Uruchomienie skryptu konfiguracyjnego
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Nadaj uprawnienia do wykonania skryptu
   chmod +x deploy/ssl-setup.sh

   # Uruchom konfigurację
   ./deploy/ssl-setup.sh

Wybierz opcję 1 dla początkowej konfiguracji. Skrypt automatycznie:

* Pobierze certyfikaty SSL
* Uruchomi wszystkie usługi
* Skonfiguruje HTTPS

Alternatywna konfiguracja manualna
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Jeśli preferujesz ręczną konfigurację:

.. code-block:: bash

   # Najpierw uruchom serwer HTTP i pobierz certyfikaty
   docker-compose -f docker-compose.ssl.yml --profile ssl-init up -d

   # Poczekaj na pobranie certyfikatów (sprawdź logi)
   docker-compose -f docker-compose.ssl.yml logs -f certbot

   # Po pobraniu certyfikatów, restartuj z HTTPS
   docker-compose -f docker-compose.ssl.yml down
   docker-compose -f docker-compose.ssl.yml up -d

Architektura
------------

Usługi
~~~~~~

* **webserver_http**: Serwer Nginx dla wyzwań ACME (port 80)
* **certbot**: Klient Let's Encrypt do zarządzania certyfikatami
* **webserver_https**: Główny serwer Nginx z SSL (porty 80 i 443)
* **appserver**: Serwer aplikacji Django
* **db**: Baza danych PostgreSQL
* **redis**: Cache i broker wiadomości
* **celerybeat**: Harmonogram zadań
* **workerserver-\***: Procesy zadań w tle
* **ofelia**: Harmonogram cron dla kontenerów

Woluminy
~~~~~~~~

* ``certbot-etc``: Certyfikaty SSL (``/etc/letsencrypt``)
* ``certbot-var``: Katalog roboczy Let's Encrypt
* ``web-root``: Katalog główny dla wyzwań ACME
* ``staticfiles``: Pliki statyczne Django
* ``media``: Pliki przesłane przez użytkowników
* ``postgresql_data``: Przechowywanie bazy danych
* ``redis_data``: Persystencja Redis

Zarządzanie certyfikatami
-------------------------

Automatyczne odnawianie
~~~~~~~~~~~~~~~~~~~~~~

Certyfikaty są automatycznie odnawiane co tydzień poprzez zadanie cron Ofelia:

* Uruchamiane każdej niedzieli o 2:00
* Certyfikaty odnawiane jeśli wygasają w ciągu 30 dni

Ręczne odnawianie
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Używając skryptu konfiguracyjnego
   ./deploy/ssl-setup.sh
   # Wybierz opcję 3

   # Lub bezpośrednio z docker-compose
   docker-compose -f docker-compose.ssl.yml run --rm certbot renew
   docker-compose -f docker-compose.ssl.yml exec webserver_https nginx -s reload

Sprawdzanie statusu certyfikatu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Używając skryptu konfiguracyjnego
   ./deploy/ssl-setup.sh
   # Wybierz opcję 4

   # Lub bezpośrednio
   docker-compose -f docker-compose.ssl.yml run --rm certbot certificates

Testowanie
----------

Certyfikaty testowe (staging)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Do testowania użyj środowiska staging Let's Encrypt:

.. code-block:: bash

   # Używając skryptu konfiguracyjnego
   ./deploy/ssl-setup.sh
   # Wybierz opcję 5

.. note::

   Certyfikaty staging nie są zaufane przez przeglądarki.
   Służą tylko do testowania procesu konfiguracji.

Sprawdzanie zdrowia
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Sprawdź serwer HTTP
   curl http://twoja-domena.com/health

   # Sprawdź serwer HTTPS
   curl https://twoja-domena.com/health

Funkcje bezpieczeństwa
---------------------

Konfiguracja SSL/TLS
~~~~~~~~~~~~~~~~~~~~

* Tylko TLS 1.2 i 1.3
* Silne zestawy szyfrów
* OCSP stapling włączone
* Buforowanie sesji SSL

Nagłówki bezpieczeństwa
~~~~~~~~~~~~~~~~~~~~~~~

* Strict-Transport-Security (HSTS)
* X-Frame-Options
* X-Content-Type-Options
* X-XSS-Protection
* Content-Security-Policy
* Referrer-Policy

Ograniczanie prędkości
~~~~~~~~~~~~~~~~~~~~~

* Endpointy API: 10 żądań/sekundę
* Endpointy logowania: 5 żądań/minutę

Dodatkowe zabezpieczenia
~~~~~~~~~~~~~~~~~~~~~~~~

* Blokowanie ukrytych plików
* Blokowanie plików kopii zapasowych
* Zapobieganie wykonywaniu przesłanych skryptów
* Ukryte tokeny serwera

Rozwiązywanie problemów
-----------------------

Nieudane pobranie certyfikatu
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

1. Sprawdź rozdzielczość DNS:

.. code-block:: bash

   nslookup twoja-domena.com

2. Sprawdź dostępność portu 80:

.. code-block:: bash

   # Z innej maszyny
   curl http://twoja-domena.com/.well-known/acme-challenge/test

3. Sprawdź logi certbot:

.. code-block:: bash

   docker-compose -f docker-compose.ssl.yml logs certbot

HTTPS nie działa
~~~~~~~~~~~~~~~~

1. Sprawdź czy certyfikaty istnieją:

.. code-block:: bash

   docker-compose -f docker-compose.ssl.yml run --rm --entrypoint sh certbot \
     -c "ls -la /etc/letsencrypt/live/certyfikaty_ssl/"

2. Sprawdź konfigurację nginx:

.. code-block:: bash

   docker-compose -f docker-compose.ssl.yml exec webserver_https nginx -t

3. Sprawdź logi błędów nginx:

.. code-block:: bash

   docker-compose -f docker-compose.ssl.yml logs webserver_https

Limity prędkości
~~~~~~~~~~~~~~~

Let's Encrypt ma limity prędkości:

* 50 certyfikatów na domenę tygodniowo
* 5 duplikatów certyfikatów tygodniowo
* 300 nowych zamówień na konto na 3 godziny

Jeśli przekroczysz limity, użyj certyfikatów staging do testów.

Monitorowanie
-------------

Logi
~~~~

Wyświetl logi wszystkich usług:

.. code-block:: bash

   docker-compose -f docker-compose.ssl.yml logs -f

Wyświetl logi konkretnej usługi:

.. code-block:: bash

   docker-compose -f docker-compose.ssl.yml logs -f webserver_https

Status usług
~~~~~~~~~~~

.. code-block:: bash

   docker-compose -f docker-compose.ssl.yml ps

Kopia zapasowa
--------------

Kopia zapasowa certyfikatów
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Utwórz kopię zapasową
   docker run --rm -v bpp_certbot-etc:/data -v $(pwd):/backup \
     alpine tar czf /backup/letsencrypt-backup.tar.gz -C /data .

   # Przywróć kopię zapasową
   docker run --rm -v bpp_certbot-etc:/data -v $(pwd):/backup \
     alpine tar xzf /backup/letsencrypt-backup.tar.gz -C /data

Czysty start
-----------

Aby usunąć całą konfigurację SSL i rozpocząć od nowa:

.. code-block:: bash

   # Zatrzymaj wszystkie usługi
   docker-compose -f docker-compose.ssl.yml down

   # Usuń woluminy
   docker volume rm bpp_certbot-etc bpp_certbot-var bpp_web-root

   # Rozpocznij od nowa
   ./deploy/ssl-setup.sh

Lista kontrolna dla produkcji
-----------------------------

* ☐ DNS domeny skonfigurowany poprawnie
* ☐ Firewall zezwala na porty 80 i 443
* ☐ Zmienne środowiskowe skonfigurowane w ``.env.docker``
* ☐ Silny ``SECRET_KEY`` wygenerowany
* ☐ ``DEBUG=False`` w produkcji
* ☐ Dane dostępowe do bazy zabezpieczone
* ☐ Konfiguracja email dla powiadomień
* ☐ Monitorowanie i alerty skonfigurowane
* ☐ Strategia kopii zapasowych wdrożona
* ☐ Rotacja logów skonfigurowana
* ☐ Nagłówki bezpieczeństwa zweryfikowane
* ☐ Ograniczanie prędkości przetestowane

Wsparcie
--------

W przypadku problemów:

* **Let's Encrypt**: Sprawdź https://letsencrypt.org/docs/
* **Certbot**: Sprawdź https://certbot.eff.org/docs/
* **Nginx**: Sprawdź https://nginx.org/en/docs/
* **Aplikacja BPP**: Sprawdź dokumentację BPP

Skrypt ssl-setup.sh
-------------------

Interaktywny skrypt ``deploy/ssl-setup.sh`` zapewnia prosty interfejs do zarządzania certyfikatami SSL:

**Dostępne opcje:**

1. **Początkowa konfiguracja** - Pobiera certyfikaty i uruchamia usługi
2. **Uruchom/Restartuj usługi** - Restartuje stos Docker
3. **Odnów certyfikaty** - Ręcznie odnawia certyfikaty SSL
4. **Pokaż status certyfikatów** - Wyświetla informacje o certyfikatach
5. **Test z certyfikatami staging** - Używa środowiska testowego Let's Encrypt
6. **Wyczyść** - Usuwa wszystkie certyfikaty i woluminy
7. **Wyjście** - Kończy działanie skryptu

Skrypt automatycznie sprawdza wymagania wstępne i prowadzi przez proces konfiguracji w języku polskim.
