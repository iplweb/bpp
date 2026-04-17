Naprawiono czyszczenie kontenerów tworzonych przez plugin
``testcontainers_bpp``. Jawny cleanup w ``pytest_unconfigure``
bywał pomijany przy abrupt-exit procesu pytest (``sys.exit`` z
fixture, nieprzechwycony wyjątek), a Ryuk jako fallback również
zawodził przy restarcie Docker Desktop, pozostawiając osierocone
kontenery PostgreSQL / Redis / RabbitMQ. Dodano safety net przez
``atexit``, który zatrzymuje kontenery przy każdym normalnym
zakończeniu procesu pytest (szanuje ``BPP_TESTCONTAINERS_REUSE``).

Dodano też target ``make clean-testcontainers``, który jednym
poleceniem usuwa wszystkie kontenery oznaczone etykietą
``org.testcontainers=true`` oraz stałonazwane ``bpp-tc-*`` —
ratunek gdy cleanup mimo wszystko padnie (np. ``SIGKILL`` na
pytest albo restart demona Docker).
