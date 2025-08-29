autostash DOCKER_CONTEXT=desktop-linux

./bin/jaka-baza.sh

export DJANGO_SETTINGS_MODULE=django_bpp.settings.local
unset ANTHROPIC_API_KEY
