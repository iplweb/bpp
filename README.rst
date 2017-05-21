django_bpp
==========

.. role:: bash(code)
   :language: bash


O projekcie
-----------

django_bpp to system informatyczny do zarządzania bibliografią publikacji
pracowników naukowych. Oprogramowanie przeznaczone jest dla bibliotek naukowych
i uniwersyteckich w Polsce. Oprogramowanie dystrybuowane jest na otwartoźródłowej
licencji MIT.

Wersja demo serwisu
-------------------

Live-demo serwisu dostępne jest pod adresem http://bppdemo.iplweb.pl . W razie
pytań lub problemów z dostępem prosimy o kontakt pod adresem e-mail
michal.dtz@gmail.com.


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

Zainstaluj pakiety developerskie:

.. code-block:: bash

    # Dla Twojego systemu operacyjnego
    pip install -r requirements/`uname -s`.requirements.txt

    # Ogólne
    pip install -r requirements/dev.requirements.txt
    pip install -r requirements/requirements.txt

Stwórz maszyny wirtualne:

.. code-block:: bash

    vagrant up

Ustaw zmienne środowiskowe na cele lokalnego developmentu:

.. code-block:: bash

    export DJANGO_SETTINGS_MODULE=django_bpp.settings.local
    export PGHOST=bpp-db  # host obsługiwany przez Vagrant
    export PGDATABASE=bpp
    export PGUSER=bpp

Uruchom lokalne testy:

.. code-block:: bash

    ./buildscripts/run-tests.sh

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

Wsparcie komercyjne
-------------------

Wsparcie komercyjne dla projektu świadczy firma IPL, szczegóły na stronie
projektu http://bpp.iplweb.pl/

Licencja MIT
------------

Copyright (c) 2017, Michał Pasternak

Niniejszym gwarantuje się, bez opłat, że każda osoba która wejdzie w posiadanie kopii tego oprogramowania i związanych z nim plików dokumentacji (dalej „Oprogramowanie”) może wprowadzać do obrotu Oprogramowanie bez żadnych ograniczeń, w tym bez ograniczeń prawa do użytkowania, kopiowania, modyfikowania, łączenia, publikowania, dystrybuowania, sublicencjonowania i/lub sprzedaży kopii Oprogramowania a także zezwalania osobie, której Oprogramowanie zostało dostarczone czynienia tego samego, z zastrzeżeniem następujących warunków:

Powyższa nota zastrzegająca prawa autorskie oraz niniejsza nota zezwalająca muszą zostać włączone do wszystkich kopii lub istotnych części Oprogramowania.

OPROGRAMOWANIE JEST DOSTARCZONE TAKIM, JAKIE JEST, BEZ JAKIEJKOLWIEK GWARANCJI, WYRAŹNEJ LUB DOROZUMIANEJ, NIE WYŁĄCZAJĄC GWARANCJI PRZYDATNOŚCI HANDLOWEJ LUB PRZYDATNOŚCI DO OKREŚLONYCH CELÓW A TAKŻE BRAKU WAD PRAWNYCH. W ŻADNYM PRZYPADKU TWÓRCA LUB POSIADACZ PRAW AUTORSKICH NIE MOŻE PONOSIĆ ODPOWIEDZIALNOŚCI Z TYTUŁU ROSZCZEŃ LUB WYRZĄDZONEJ SZKODY A TAKŻE ŻADNEJ INNEJ ODPOWIEDZIALNOŚCI CZY TO WYNIKAJĄCEJ Z UMOWY, DELIKTU, CZY JAKIEJKOLWIEK INNEJ PODSTAWY POWSTAŁEJ W ZWIĄZKU Z OPROGRAMOWANIEM LUB UŻYTKOWANIEM GO LUB WPROWADZANIEM GO DO OBROTU.

MIT License
-----------

Copyright (c) 2017, Michał Pasternak

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
