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

Jak zacząć?
-----------

Zainstaluj:

* Python_ w wersji 2.7,
* Vagrant_,
* VirtualBox_,
* PostgreSQL_

Zainstaluj virtualenv:

.. code-block:: bash

    pip install virtualenv

Zainstaluj virtualenvwrapper_.

Zainstaluj wymagane wtyczki do Vagranta:

.. code-block:: bash

    vagrant plugin install vagrant-hostmanager vagrant-timezone vagrant-cachier vagrant-reload

Sklonuj repozytorium z kodem:

.. code-block:: bash

  git clone https://github.com/mpasternak/django-bpp.git
  cd django-bpp

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

Stwórz maszyny wirtualne:

.. code-block:: bash

    vagrant up

Ustaw zmienne środowiskowe na cele lokalnego developmentu:

.. code-block:: bash

    export PGHOST=bpp-db
    export PGUSER=bpp

Uruchom lokalne testy.

.. code-block:: bash

    ./buildscripts/run-tests.sh

Jeżeli któryś test "utknie" - zdarza się to przezde
wszystkim przy testach korzystających z przeglądarki, Selenium i live-servera
Django, możesz podejrzeć serwer testowy za pomocą oprogramowania typu
`VNC Viever`_ (wejdź na adres VNC :bash:`bpp-selenium:99`)

Zbuduj wersję "release". Poniższe polecenie uruchomi testy na docelowym systemie
operacyjnym (Linux) oraz zbuduje wersję instalacyjną systemu:

.. code-block:: bash

    make release

.. _Python: http://python.org/
.. _Vagrant: http://vagrantup.com/
.. _vagrant-hostmanager: https://github.com/devopsgroup-io/vagrant-hostmanager
.. _Virtualbox: http://virtualbox.org
.. _virtualenvwrapper: https://virtualenvwrapper.readthedocs.io/en/latest/install.html
.. _IPLWeb: http://bpp.iplweb.pl/
.. _PostgreSQL: http://postgresql.org/
.. _Licencja MIT: http://github.com/mpasternak/django-bpp/LICENSE
.. _VNC Viever: https://www.realvnc.com/download/viewer/

Wsparcie komercyjne
-------------------

Wsparcie komercyjne dla projektu świadczy firma IPL, szczegóły na stronie
projektu http://bpp.iplweb.pl/
