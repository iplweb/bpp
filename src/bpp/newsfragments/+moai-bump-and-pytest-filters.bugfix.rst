Zbumpowano ``MOAI-iplweb`` z ``==2.0.0`` do ``>=2.0.1`` (release
2.0.1 zawiera fix ``datetime.utcnow()`` → ``datetime.now(UTC)``).
Zniknęły ostrzeżenia ``DeprecationWarning`` z ``moai/oai.py``.

Dodano dwa targetowane filtry w ``pytest.ini`` dla pozostałych
zewnętrznych warningów, których nie mamy gdzie naprawić w bpp:

- ``oaipmh.server`` (paczka ``pyoai`` 2.5.0) — wywołuje
  ``datetime.utcnow()``; nie mamy forka, zgłoszenie upstream
  w toku.
- ``webtest.forms`` (paczka ``webtest`` 3.0.7) — używa
  ``bs4.findAll`` zamiast ``find_all``; nie mamy forka, zgłoszenie
  do ``Pylons/webtest`` w toku.

Zmienione zależności tranzytywne (uv downgrade wymuszone przez
moai-iplweb ``sqlalchemy<2`` i ``setuptools<80``): ``sqlalchemy
2.0.44 → 1.4.54``, ``setuptools 80.9 → 79.0``.
