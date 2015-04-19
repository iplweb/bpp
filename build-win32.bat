@echo off

REM #######################################################################
REM pociagnij z glownego PyPI pakiety, ktorych na linuxie NIE zbuduje:
REM #######################################################################

devpi use http://master:3141/root/pypi/ --set-cfg
pip wheel https://pypi.python.org/packages/source/z/zope.interface/zope.interface-4.1.1.tar.gz#md5=edcd5f719c5eb2e18894c4d06e29b6c6
pip wheel "billiard<3.4,>=3.3.0.1"
pip wheel sqlalchemy==0.9.9 coverage==3.6 PyYAML==3.11 lxml==3.4.2

REM #######################################################################
REM wrzuc do /devpi/bpp zbudowane pakiety
REM #######################################################################

devpi use /devpi/bpp/ --set-cfg
devpi upload --from-dir wheelhouse


REM #######################################################################
REM instaluj
REM #######################################################################

pip install -r requirements\requirements.txt
pip install -r requirements\dev\requirements.txt

pip install simplejson

REM instalacja EXEków: psycopg2, pillow http://www.lfd.uci.edu/~gohlke/pythonlibs/

pip install http://www.lfd.uci.edu/~gohlke/pythonlibs/6icuform/Pillow-2.8.1-cp27-none-win32.whl
pip install http://www.lfd.uci.edu/~gohlke/pythonlibs/6icuform/psycopg2-2.5.5-cp27-none-win32.whl


npm install -g bower

python manage.py bower_install -F
python manage.py compress