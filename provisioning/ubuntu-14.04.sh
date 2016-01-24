#!/bin/bash -e

#
# Ten skrypt instaluje rzeczy potrzebne do budowania i do uruchamiania pakietu django-bpp
# po stronie systemu operacyjnego Ubuntu 14.04
#
# Ten skrypt NIE może instalować nic za pomocą pip, nie instaluje nic do virtualenv, ten skrypt
# nie dotyka środowiska języka Python, lokalnego bądź globalnego, ten skrypt NIE dotyka go. Ten
# skrypt instaluje Pythona i potrzebne biblioteki. I bazę danych PostgreSQL. I jeszcze parę innych. 

# Niby nie powinniśmy się bawić w aktualizowanie systemu w tym miejscu ALE może się okazać, 
# że pakietów nie da się w tym momencie pobrać, bo system maszyny wirtualnej np. ma stare linki
# więc dla bezpieczeństwa lepiej odpalić o to, ale jeżeli np miałoby nie być sieci...
sudo apt-get -q update || true

sudo apt-get -qy install python python-gevent python-psycopg2 python-imaging python-crypto python-simplejson python-sqlalchemy redis-server zip unzip
