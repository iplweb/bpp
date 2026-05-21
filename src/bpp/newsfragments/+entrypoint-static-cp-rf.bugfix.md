Naprawiono błąd w ``docker/appserver/entrypoint-appserver.sh`` powodujący
że nowsze pliki staticów (np. CSS po dodaniu nowego SCSS-a) nie trafiały
na produkcję mimo zredeployowania nowego obrazu.

Poprzednio entrypoint kopiował ``cp -ru /app/staticroot.baked/. "$STATIC_ROOT/"``
— flaga ``-u`` (update only if newer) porównywała mtime źródła z mtime
docelowym. mtime w ``.baked`` pochodzi z czasu ``grunt build`` w trakcie
buildu obrazu, podczas gdy mtime na named volume z czasu ``cp`` przy
poprzednim restarcie kontenera. Jeśli poprzedni restart nastąpił później
niż grunt build w nowym obrazie (typowy scenariusz przy deployach jeden
po drugim), ``cp -u`` cicho skipował kopiowanie i volume utrzymywał stare
pliki — a ``django-compressor`` produkował bundle z tych przestarzałych
źródeł.

Teraz używamy ``cp -rf`` — zawsze nadpisuje pliki istniejące w ``.baked``,
bez sprawdzania mtime. Ochrona tenant-specific zmian (custom branding
wgrany post-deploy do podkatalogów spoza ``.baked``) jest zachowana,
ponieważ ``cp`` i tak nie kasuje plików spoza źródła.

**Symptom dla użytkowników poprzedniego zachowania**: po dodaniu nowych
reguł CSS (np. nowych klas SCSS) i zredeployowaniu obrazu, na produkcji
nadal widoczny jest stary styl. Workaround manualny:
``docker compose exec appserver cp -rf /app/staticroot.baked/. "$STATIC_ROOT/" && docker compose exec appserver python src/manage.py compress -v0 --force``.
Po tym fixie nie jest już potrzebny.
