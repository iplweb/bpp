django-bpp
==========

.. image:: https://travis-ci.org/mpasternak/django-bpp.svg?branch=dev
   :target: https://travis-ci.org/mpasternak/django-bpp

.. role:: bash(code)
   :language: bash


O projekcie
-----------

django_bpp to system informatyczny do zarządzania bibliografią publikacji
pracowników naukowych. Oprogramowanie przeznaczone jest dla bibliotek naukowych
i uniwersyteckich w Polsce. Oprogramowanie dystrybuowane jest na zasadach
otwartoźródłowej `licencja MIT`_.

Wersja demo serwisu
-------------------

Live-demo serwisu dostępne jest pod adresem http://bppdemo.iplweb.pl . W razie
pytań lub problemów z dostępem do serwisu demonstracyjnego prosimy o kontakt
pod adresem e-mail michal.dtz@gmail.com.


Dla kogo niniejsza dokumentacja?
--------------------------------

Niniejsza dokumentacja przeznaczona jest dla programistów i zaawansowanych
użytkowników komputerów. Jeżeli jesteś bibliotekarzem i szukasz sposobu na
szybkie wdrożenie systemu django-bpp w swojej instytucji, zapraszam na stronę
firmy IPLWeb_ . Znajdziesz tam m.in. kontener maszyny wirtualnej zawierającej
pre-instalowany system django-bpp, gotowy do pracy, jak równiez bogatą ofertę
wsparcia komercyjnego.

Możesz również prześledzić poniższy proces ze szczegółami, aby dowiedzieć się,
na czym polega tzw. "full-stack dev ops".

Wymagania systemowe
~~~~~~~~~~~~~~~~~~~

Oprogramowanie docelowo działa na Ubuntu Linux 16.04, a rozwijane jest na Mac
OS X. Większość opisanych tu procedur jest testowana własnie na tych systemach.
Nic nie stoi na przeszkodzie, aby spróbować uruchomić niniejsze oprogramowanie
na Windows, jednakże na ten moment nie jest to wspierana konfiguracja.

Jak zacząć?
-----------

Zainstaluj:

* Python_ w wersji 2.7,
* Vagrant_,
* VirtualBox_,
* yarn_,
* Docker_

Wymagane oprogramowanie serwerowe, w tym PostgreSQL_, RabbitMQ_, redis_ zostanie
zainstalowane i skonfigurowane przez skrypty Ansible_ na maszynie wirtualnej
zarządzanej przez Vagrant_. Jest to zalecany sposób testowania i rozwijania
programu, który docelowo działać ma na platformie Ubuntu Linux 16.04 na
"metalowych" serwerach.

Rozwijanie programu z kolei - budowanie pakietów wheel języka Python_, testowanie
za pomocą Selenium_, zapewnienie szybko skonfigurowanej bazy danych obsługuje
Docker_.

Jeżeli używasz macOS:
~~~~~~~~~~~~~~~~~~~~~

Większość procedur instalacyjnych możesz załatwić przez Homebrew_:

.. code-block:: bash

    brew install grunt-cli yarn npm ansible python git
    brew cask install vagrant vagrant-manager virtualbox


Klonowanie repozytorium z kodem
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sklonuj repozytorium z kodem:

.. code-block:: bash

  git clone https://github.com/mpasternak/django-bpp.git
  cd django-bpp

Konfiguracja pakietów języka JavaScript
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Zainstaluj globalnie wymagane pakiety JavaScript za pomocą yarn_.
Zainstaluj następnie wymagane przez django-bpp pakiety:

.. code-block:: bash

    yarn global add grunt-cli
    yarn install

Konfiguracja Pythona
~~~~~~~~~~~~~~~~~~~~

Zainstaluj virtualenv oraz virtualenvwrapper_.:

.. code-block:: bash

    pip install virtualenv virtualenvwrapper

Stwórz i zaktywizuj wirtualne środowisko języka Python:

.. code-block:: bash

    mkvirtualenv django-bpp
    workon django-bpp

Zainstaluj wymagane pakiety:

.. code-block:: bash

    pip install -r requirements_dev.txt

Konfiguracja Vagrant_
~~~~~~~~~~~~~~~~~~~~~

Zainstaluj wymagane wtyczki do Vagrant_:

.. code-block:: bash

    vagrant plugin install vagrant-hostmanager vagrant-timezone vagrant-cachier

Stwórz testowy serwer wirtualny ("staging"):

.. code-block:: bash

    vagrant up


Przygotuj środowisko budowania
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ustaw zmienne środowiskowe na cele lokalnego developmentu:

.. code-block:: bash

    export DJANGO_SETTINGS_MODULE=django_bpp.settings.local
    export PGHOST=localhost
    export PGUSER=postgres

Możesz umieścić te ustawienia w pliku ``bin/postactivate`` środowiska
wirtualnego utworzonego przez ``mkvirtualenv``. Domyślnie znajduje się on
w katalogu ``~/.envs/django-bpp/bin/postactivate``.

Zbuduj pliki CSS i JavaScript
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Następnie uruchom skrypt aby przygotować środowisko budowania oraz kolejny
skrypt, aby zbudować pliki CSS i JS. Skrypty te
instalują wymagane przez interfejs WWW pakiety języka JavaScript za pomocą
yarn_ oraz konfigurują bibliotekę Foundation_ budując ją
za pomocą Grunt_ i SASS. Następnie kompilują tak uzbierane pakiety za pomocą
django-compressor_.

.. code-block:: bash

    ./buildsrcipts/build-assets.sh

Uruchom lokalne testy
~~~~~~~~~~~~~~~~~~~~~

Uruchom testy lokalnie. Domyślna konfiguracja oczekuje, iż serwer bazodanowy
PostgreSQL_ dostępny będzie na porcie 5432 komputera localhost i obsługiwał
będzie język PL/Python 2 oraz sortowanie wg polskiego locale pl_PL.UTF8.
Testy oczekują również, iż serwer Selenium_ dostępny będzie na porcie 4444
hosta lokalnego, jak również dostępny będzie serwer Redis_ na standardowym
porcie 6379. Jak uruchomić szybko te wszystkie usługi w sposób wstępnie
skonfigurowany, wymagany przez django-bpp? Z pomocą przychodzi Docker_:

.. code-block:: bash

     make docker-up

Następnie uruchom testy na maszynie lokalnej:

.. code-block:: bash

    # Ustaw zmienne środowiskowe aby korzystać z kontenerów Dockera:
    . local.rc

    # Skonfiguruj interfejs lo0 (MacOS X) aby kontener 'selenium' miał
    # dostęp do live-servera Django uruchamianego na interfejsie
    # lokalnym:
    make setup-lo0

    # Zbuduj/pobierz pakiety WHL, używane później w nasętępnym kroku przez
    # tox:
    make wheels

    # Uruchom testy
    ./buildscripts/run-tests.sh --debug

W przyszłości możesz uruchamiać testy z opcją ``--no-rebuild``, aby nie
przebudowywać za każdym razem bazy danych.

Jeżeli któryś test "utknie" - zdarza się to przezde
wszystkim przy testach korzystających z przeglądarki, Selenium i live-servera
Django, możesz podejrzeć serwer testowy za pomocą oprogramowania typu
`VNC Viever`_ (wejdź na adres VNC :bash:`localhost:5900`, wpisz hasło
"secret" bez cudzysłowu i zapoznaj się z sytuacją po stronie przeglądarki
WWW).

Release
~~~~~~~

Zbuduj wersję "release". Poniższe polecenie uruchomi testy na docelowym systemie
operacyjnym (Linux) oraz zbuduje wersję instalacyjną systemu. Jest to to samo
polecenie, które uruchamiane jest na serwerze ciągłej integracji Travis-CI_.

.. code-block:: bash

    make -f Makefile.docker travis

Aby zainstalować aktualną wersję pakietu django-bpp na serwerze staging, skorzystaj
z polecenia:

.. code-block:: bash

    make -f Makefile.production staging

Następnie wejdź na adres http://bpp-staging.localnet/ aby sprawdzić
funkcjonowanie serwera.

.. _Python: http://python.org/
.. _yarn: https://yarnpkg.com/en/docs/install
.. _Vagrant: http://vagrantup.com/
.. _vagrant-hostmanager: https://github.com/devopsgroup-io/vagrant-hostmanager
.. _Virtualbox: http://virtualbox.org
.. _virtualenvwrapper: https://virtualenvwrapper.readthedocs.io/en/latest/install.html
.. _IPLWeb: http://bpp.iplweb.pl/
.. _PostgreSQL: http://postgresql.org/
.. _Licencja MIT: http://github.com/mpasternak/django-bpp/LICENSE
.. _VNC Viever: https://www.realvnc.com/download/viewer/
.. _Grunt: http://gruntjs.com/
.. _Foundation: http://foundation.zurb.com/
.. _django-compressor: https://django-compressor.readthedocs.io
.. _Ansible: http://ansible.com/
.. _RabbitMQ: http://rabbitmq.com/
.. _redis: http://redis.io/
.. _Homebrew: http://brew.sh
.. _Docker: http://docker.io/
.. _Selenium: http://seleniumhq.org
.. _Travis-CI: https://travis-ci.org/mpasternak/django-bpp/builds

Wsparcie komercyjne
-------------------

Wsparcie komercyjne dla projektu świadczy firma IPL, szczegóły na stronie
projektu http://bpp.iplweb.pl/
