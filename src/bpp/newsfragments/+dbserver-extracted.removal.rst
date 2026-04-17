Wydzielono budowanie obrazu ``iplweb/bpp_dbserver`` z tego
repozytorium do osobnego projektu
(`github.com/iplweb/bpp-dbserver <https://github.com/iplweb/bpp-dbserver>`_).
Usunięty został katalog ``docker/dbserver/`` oraz target ``dbserver``
z ``docker-bake.hcl``; ``docker-compose.yml``, ``docker-compose.test.yml``,
workflowy GitHub Actions i konfiguracja testcontainers pullują teraz
wersjonowany tag ``iplweb/bpp_dbserver:psql-16.13`` zamiast budować
obraz lokalnie. Cel: niezależny release cycle obrazu bazy (bump
Postgresa nie wymaga release'u BPP) i eliminacja tagu ``:latest``
po stronie konsumentów.
