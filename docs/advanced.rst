Ustawienia zaawansowane
-----------------------

W tej sekcji dokumentacji znajdują się zaawansowane ustawienia serwera. Instrukcje te przeznaczone
są dla administratorów systemu operacyjnego Linux na którym działa system BPP.

Konfiguracja systemu BPP
========================

Konfiguracja od wersji 202209 wzwyż powinna odbywać się przez plik `.env` umieszczony
w katalogu domowym użytkownika, z którego konta uruchamiany jest serwer BPP. Zmienne
konfiguracyjne będą stopniowo migrować do tego formatu.

`Przykładowy plik .env.example w repozytorium kodu na GitHub <https://github.com/iplweb/bpp/blob/dev/.env.example>`_

`Plik django_bpp/settings/base.py repozytorium kodu na GitHub <https://github.com/iplweb/bpp/blob/dev/src/django_bpp/settings/base.py>`_

Zmienne można nadpisać.

Jeżeli zainstalujemy BPP korzystając z pakietu `bpp-on-ansible <https://github.com/iplweb/bpp-on-ansible>`_ ,
to utworzy on domyślny plik ``.env``. Za zmienne odpowiada plik `config.yml <https://github.com/iplweb/bpp-on-ansible/blob/develop/ansible/roles/bpp-site/tasks/config.yml#L13>`_.


Konfiguracja LDAP (ActiveDirectory)
===================================

Konfiguracja LDAP (ActiveDirectory) odbywa się za pomocą zmiennych środowiskowych lub
konfiguracyjnych `AUTH_LDAP_SERVER_URI`, `AUTH_LDAP_BIND_DN`, `AUTH_LDAP_BIND_PASSWORD` oraz
`AUTH_LDAP_USER_SEARCH`. Zmienne te należy ustawić w pliku `.env` w katalogu domowym użytkownika.
