``make build`` buduje teraz lokalny obraz developerski ``bpp_testserver:dev`` —
ten, którym ``docker-compose.yml`` uruchamia wszystkie serwisy aplikacyjne,
czyli jedyny budowany obraz, jaki cokolwiek lokalnie odpala. Wcześniej nie miał
on nawet targetu w ``docker-bake.hcl``, więc ``make build`` kończył się na
zielono, odświeżywszy wyłącznie sześć obrazów produkcyjnych, których lokalnie
nie uruchamia nic. Obraz starzał się w nieskończoność, a ponieważ compose
podkłada bind-mountem świeże ``./src`` pod jego stary ``/opt/venv``, kod
z dzisiaj spotykał zależności sprzed tygodnia (objaw: ``ModuleNotFoundError``
na pakiecie dodanym do ``pyproject.toml`` już po zbudowaniu obrazu).

Obrazy produkcyjne przeniesiono pod ``make build-production``, a dawne
zachowanie ``make build`` (wszystko naraz) jest dostępne jako ``make
build-all``. ``PUSH_TO_REGISTRY=true make build`` nie kończy się już cichym
niewypałem, tylko błędem odsyłającym do ``build-production``.
