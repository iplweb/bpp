Workflow ``Docker - oficjalne obrazy``
(``.github/workflows/build-docker-images.yml``) buduje i publikuje
obrazy docker automatycznie tylko przy pushu na ``master``. Dla
branchy ``feature/**``, ``fix/**``, ``hotfix/**`` build odpala się
tylko wtedy, gdy w root repo istnieje pusty plik flaga
``.docker-build`` — zmiana oszczędza Docker Cloud Build minuty
zużywane przez każdy push na długie feature-branche. Ręczne
uruchomienie niezależnie od flagi: ``gh workflow run
build-docker-images.yml --ref <branch>`` (lub GUI GitHub Actions).

Aby włączyć auto-build na branchu::

    touch .docker-build
    git add .docker-build && git commit -m "ci: enable docker auto-build"

Aby wyłączyć::

    git rm .docker-build && git commit -m "ci: disable docker auto-build"
