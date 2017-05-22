django-bpp
==========

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
* npm_

Wymagane oprogramowanie serwerowe, w tym PostgreSQL_, RabbitMQ_, redis_ zostanie
zainstalowane przez skrypty Ansible_ na maszynie wirtualnej zarządzanej przez
Vagrant_.

Konfiguracja Vagrant_
~~~~~~~~~~~~~~~~~~~~~

Zainstaluj wymagane wtyczki do Vagrant_:

.. code-block:: bash

    vagrant plugin install vagrant-hostmanager vagrant-timezone vagrant-cachier vagrant-reload

Stwórz maszyny wirtualne:

.. code-block:: bash

    vagrant up


Klonowanie repozytorium z kodem
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Sklonuj repozytorium z kodem:

.. code-block:: bash

  git clone https://github.com/mpasternak/django-bpp.git
  cd django-bpp

Konfiguracja Pythona
~~~~~~~~~~~~~~~~~~~~

Zainstaluj virtualenv:

.. code-block:: bash

    pip install virtualenv

Zainstaluj virtualenvwrapper_.

Stwórz i zaktywizuj wirtualne środowisko języka Python:

.. code-block:: bash

    mkvirtualenv django-bpp
    workon django-bpp

Zainstaluj django-bpp:

.. code-block:: bash

    pip install -e .

Zainstaluj pakiety developerskie:

.. code-block:: bash

    pip install -r requirements/requirements_dev.txt

Przygotuj środowisko budowania
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ustaw zmienne środowiskowe na cele lokalnego developmentu:

.. code-block:: bash

    export PGHOST=bpp-db
    export PGUSER=bpp

Możesz umieścić te ustawienia w pliku ``bin/postactivate`` środowiska
wirtualnego utworzonego przez ``mkvirtualenv``. Domyślnie będą one w katalogu
``~/.envs/django-bpp/bin/postactivate``.

Następnie uruchom skrypt aby przygotować środowisko budowania. Skrypt ten
instaluje wymagane przez interfejs WWW pakiety języka JavaScript za pomocą
django-bower_ oraz konfiguruje bibliotekę Foundation_ budując ją za pomocą
Grunt_. Następnie kompiluje tak uzbierane pakiety za pomocą django-compressor_.

.. code-block:: bash

    ./buildsrcipts/prepare-build-env.sh

Uruchom lokalne testy
~~~~~~~~~~~~~~~~~~~~~

Uruchom testy lokalnie. Ustawienia domyślne korzystają z serwera bazodanowego
'bpp-db' oraz serwera selenium 'bpp-selenium'. Obydwa te serwery zostaną
utworzone za pomocą Vagrant_.

.. code-block:: bash

    ./buildscripts/run-tests.sh --no-rebuild

Opcja ``--no-rebuild`` nie przebudowuje bazy danych. Testowa baza danych została
utworzona przez skrypt ``prepare-build-env.sh`.

Jeżeli któryś test "utknie" - zdarza się to przezde
wszystkim przy testach korzystających z przeglądarki, Selenium i live-servera
Django, możesz podejrzeć serwer testowy za pomocą oprogramowania typu
`VNC Viever`_ (wejdź na adres VNC :bash:`bpp-selenium:99`)

Release
~~~~~~~

Zbuduj wersję "release". Poniższe polecenie uruchomi testy na docelowym systemie
operacyjnym (Linux) oraz zbuduje wersję instalacyjną systemu:

.. code-block:: bash

    make release

.. _Python: http://python.org/
.. _npm: https://www.npmjs.com/get-npm
.. _Vagrant: http://vagrantup.com/
.. _vagrant-hostmanager: https://github.com/devopsgroup-io/vagrant-hostmanager
.. _Virtualbox: http://virtualbox.org
.. _virtualenvwrapper: https://virtualenvwrapper.readthedocs.io/en/latest/install.html
.. _IPLWeb: http://bpp.iplweb.pl/
.. _PostgreSQL: http://postgresql.org/
.. _Licencja MIT: http://github.com/mpasternak/django-bpp/LICENSE
.. _VNC Viever: https://www.realvnc.com/download/viewer/
.. _django-bower: https://github.com/nvbn/django-bower
.. _Grunt: http://gruntjs.com/
.. _Foundation: http://foundation.zurb.com/
.. _django-compressor: https://django-compressor.readthedocs.io
.. _Ansible: http://ansible.com/
.. _RabbitMQ: http://rabbitmq.com/
.. _redis: http://redis.io/

Wsparcie komercyjne
-------------------

Wsparcie komercyjne dla projektu świadczy firma IPL, szczegóły na stronie
projektu http://bpp.iplweb.pl/
