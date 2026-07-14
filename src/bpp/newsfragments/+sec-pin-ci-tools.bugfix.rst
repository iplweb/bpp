Hardening pipeline'u wydań: przypięto do konkretnych wersji (i digestów)
narzędzia dotąd ściągane z ruchomych tagów w jobach z sekretami —
obraz ``aquasec/trivy`` (skan CVE), binarkę buildx ``lab`` (build obrazów)
oraz ``uvx bumpver``/``uvx towncrier`` (bump wersji i changelog). Zamyka to
wektor supply-chain, w którym podmiana ``:latest``/``lab:latest``/najnowszego
pakietu z PyPI mogłaby wykonać nieprzypięty kod obok ``DOCKER_PAT`` /
``contents: write``.
