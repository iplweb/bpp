CI: shardy ``pytest`` w workflow ``Tests`` nie odpalają już ``make
assets`` przy starcie. Obraz ``test-runner`` ma zapieczone CSS i ``.mo``
z buildu obrazu (stage ``test-runner`` w ``docker/bpp_base/Dockerfile``),
więc ``conftest.py`` honoruje teraz zmienną ``BPP_SKIP_ASSETS_BUILD=1``
ustawioną w ``docker-compose.test.ci.yml``.

Wcześniej każdy z ośmiu równoległych shardów wpadał w
``pytest_configure`` i — z powodu braku sentinela
``node_modules/.installed`` w obrazie — odpalał pełny ``yarn install`` +
``grunt build`` przed pierwszym testem. Lokalny dev nie jest zmieniony:
bez tej zmiennej ``conftest.py`` nadal uruchamia ``make assets`` jako
safety net.
