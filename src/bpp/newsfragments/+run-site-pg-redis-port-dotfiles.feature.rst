``manage.py run_site`` zapisuje teraz porty PostgreSQL i Redis-a
(testcontainers) do gitignored plików ``.run_site_pg_port`` i
``.run_site_redis_port`` (analogicznie do ``.run_site_port``). Agent
kodujący może podpiąć ``psql`` / ``redis-cli`` bez parsowania bannera
— w stdoucie banner zawiera teraz gotowe snippety dla obu narzędzi.
Pliki są ulotne: kasowane na exit run_site.
