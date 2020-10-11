import multiprocessing
import threading
import traceback

from daphne.testing import _reinstall_reactor
from pytest_django.plugin import _blocking_manager


class DaphneThread(threading.Thread):
    def __init__(self, host, application, kwargs=None, setup=None, teardown=None):
        super().__init__()
        self.host = host
        self.application = application
        self.kwargs = kwargs or {}
        self.setup = setup or (lambda: None)
        self.teardown = teardown or (lambda: None)
        self.port = multiprocessing.Value("i")
        self.ready = threading.Event()
        self.errors = multiprocessing.Queue()

    def run(self):
        # OK, now we are in a forked child process, and want to use the reactor.
        # However, FreeBSD systems like MacOS do not fork the underlying Kqueue,
        # which asyncio (hence asyncioreactor) is built on.
        # Therefore, we should uninstall the broken reactor and install a new one.
        _reinstall_reactor()

        from twisted.internet import reactor

        from daphne.server import Server
        from daphne.endpoints import build_endpoint_description_strings

        try:
            # Create the server class
            endpoints = build_endpoint_description_strings(host=self.host, port=0)
            self.server = Server(
                application=self.application,
                endpoints=endpoints,
                signal_handlers=False,
                **self.kwargs
            )
            # Set up a poller to look for the port
            reactor.callLater(0.1, self.resolve_port)
            # Run with setup/teardown
            self.setup()
            try:
                self.server.run()
            finally:
                self.teardown()
        except Exception as e:
            # Put the error on our queue so the parent gets it
            self.errors.put((e, traceback.format_exc()))

    def resolve_port(self):
        from twisted.internet import reactor

        if self.server.listening_addresses:
            self.port.value = self.server.listening_addresses[0][1]
            self.ready.set()
        else:
            reactor.callLater(0.1, self.resolve_port)

    def terminate(self):
        from twisted.internet import reactor

        reactor.stop()
        # if hasattr(self, 'httpd'):
        #     # Stop the WSGI server
        #     self.httpd.shutdown()
        #     self.httpd.server_close()
        self.join()
        _blocking_manager.unblock()
