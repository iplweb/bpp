"""Import ``django_bpp.asgi`` MUSI wypaść przed nadpisaniem ``ALLOWED_HOSTS``.

``channels.security.websocket.AllowedHostsOriginValidator`` jest FUNKCJĄ
FABRYKUJĄCĄ, nie klasą::

    def AllowedHostsOriginValidator(application):
        allowed_hosts = settings.ALLOWED_HOSTS      # czytane RAZ
        ...
        return OriginValidator(application, allowed_hosts)

Listę czyta więc jeden raz — w momencie importu ``django_bpp/asgi.py``, gdzie
budowany jest ``ProtocolTypeRouter`` — i zapieka ją w instancji
``OriginValidator``. Późniejsze zmiany ``settings.ALLOWED_HOSTS`` nie mają na
nią wpływu.

Nasze testy budują aplikację przez ``_router(settings)``, które NAJPIERW
zawęża ``settings.ALLOWED_HOSTS`` do jednego hosta, a DOPIERO POTEM woła
``build_application()``. To z kolei sięga po ``django_asgi_app`` importem
leniwym (``mcp_server/klient.py:46`` — leniwym celowo, żeby import modułu ASGI
nie zależał od gotowości aplikacji Django). Jeżeli to jest PIERWSZY import
``django_bpp.asgi`` w tym procesie workera, gałąź WebSocketów zostaje na stałe
zamrożona z jednym hostem.

Skutek zmierzony: każdy późniejszy test z ``channels_live_server`` na tym
samym workerze dostawał ``403`` przy handshake'u (origin ``http://localhost:
<port>`` spoza zamrożonej listy), a Playwright timeoutował na
``chatSocket.readyState === 1``. Objaw był oddalony od przyczyny o setki
testów i widoczny tylko przy pewnym rozkładzie shardów — na CI wyglądał jak
flake w ``test_bpp_notifications``.

Import na poziomie modułu ``conftest.py`` wypada przy zbieraniu testów, czyli
zanim jakikolwiek test zdąży cokolwiek nadpisać. Fikstura by nie wystarczyła
tak niezawodnie — jej kolejność względem funkcyjnej fikstury ``settings``
zależałaby od zasięgu.
"""

import django_bpp.asgi  # noqa: F401
