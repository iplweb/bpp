from functools import partial

import pytest
from channels.testing import ChannelsLiveServerTestCase
from daphne.testing import DaphneProcess
from django.db.backends.base.creation import TEST_DATABASE_PREFIX


class PatchedDaphneProcess(DaphneProcess):
    def __init__(self, *args, **kwargs):
        self.test_db_name = kwargs.pop("test_db_name")
        super().__init__(*args, **kwargs)

    def run(self):
        pass

        from django.conf import settings

        settings.CELERY_ALWAYS_EAGER = True
        settings.DATABASES["default"]["NAME"] = self.test_db_name

        return super().run()


class PatchedLiveServerTestCase(ChannelsLiveServerTestCase):
    # ProtocolServerProcess = PatchedDaphneProcess

    def __init__(self, *args, **kw):
        self.test_db_name = kw.pop("test_db_name")
        super().__init__(*args, **kw)

    @property
    def ProtocolServerProcess(self):
        return partial(PatchedDaphneProcess, test_db_name=self.test_db_name)

    @property
    def url(self):
        return self.live_server_url


@pytest.fixture(scope="function")
def channels_live_server(request, transactional_db):
    def test_db_name():
        from django.conf import settings

        n = settings.DATABASES["default"].get("TEST", {}).get("NAME", None)
        if n:
            return n
        if settings.DATABASES["default"]["NAME"].startswith(TEST_DATABASE_PREFIX):
            return settings.DATABASES["default"]["NAME"]

        return TEST_DATABASE_PREFIX + settings.DATABASES["default"]["NAME"]

    server = PatchedLiveServerTestCase(test_db_name=test_db_name())
    server._pre_setup()

    yield server

    server._post_teardown()
