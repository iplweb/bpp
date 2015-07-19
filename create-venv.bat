@echo off

echo # Na WINDOWS trzeba:
echo # - zainstalowac nodejs
echo # - zainstalowac npm
echo # - zainstalowac bower,
echo #
echo # Nastepnie uruchamiamy:
echo # - create-venv.bat
echo # - venv\Scripts\activate.bat
echo # - python manage.py bower install
echo # - python manage.py collectstatic
echo #
echo # - npm install grunt (LOKALNIE)
echo # - npm install grunt-sass grunt-contrib-watch grunt-contrib-qunit
echo #
pause


virtualenv --python=c:\python27\python.exe --system-site-packages venv
call venv\scripts\activate.bat

pip install --upgrade pip
pip install --find-links=c:\code\wheelhouse -r src\requirements\requirements.txt
pip install --find-links=c:\code\wheelhouse -r src\requirements\dev\requirements.txt

echo set DJANGO_SETTINGS_MODULE=django_bpp.settings.local>> venv\scripts\activate.bat
echo set DJANGO_BPP_HOSTNAME=localhost>> venv\scripts\activate.bat
echo set DJANGO_BPP_SECRET_KEY=123>> venv\scripts\activate.bat
echo set DJANGO_BPP_DB_NAME=test_bpp>> venv\scripts\activate.bat
echo set DJANGO_BPP_DB_USER=test_bpp>> venv\scripts\activate.bat
echo set DJANGO_BPP_DB_PASSWORD=12345678>> venv\scripts\activate.bat
echo set DJANGO_BPP_DB_HOST=192.168.111.100>> venv\scripts\activate.bat
echo set DJANGO_BPP_DB_PORT=5432>> venv\scripts\activate.bat
echo set DJANGO_BPP_RAVEN_CONFIG_URL=http://4355f955f2ae4522ba06752c05eaff0a:5a62fbddd2ac4c0ab3d25b22c352df2a@sentry.iplweb.pl:9000/13>> venv\scripts\activate.bat
echo set DJANGO_BPP_REDIS_PORT=6379>> venv\scripts\activate.bat
echo set DJANGO_BPP_REDIS_HOST=192.168.111.100>> venv\scripts\activate.bat

call venv\scripts\activate.bat