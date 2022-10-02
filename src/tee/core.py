import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout

from django.core.management import ManagementUtility
from sentry_sdk import capture_exception

from tee.models import Log
from tee.utils import TeeIO

from django.utils import timezone


def execute(argv, **kwargs):
    """This function calls django command specified as ``command_name``,
    saving it's stdout and stderr to an object ``tee.models.Log``, also
    outputting it on stdout/stderr.

    This way one can transparently save output to the database and also
    print it out on the console. This could be useful for cron scripts."""
    stdout = TeeIO(kwargs.get("stdout") if "stdout" in kwargs else sys.stdout)
    stderr = TeeIO(kwargs.get("stderr") if "stderr" in kwargs else sys.stdout)

    log = Log.objects.create(command_name=argv[0], args=argv[1:])

    # TODO: this is memory-inefficient. stdout or stderr should flush from time to time
    # and save the result to the database, like in 1-MB chunks

    try:
        with redirect_stderr(stderr):
            with redirect_stdout(stdout):
                try:
                    utility = ManagementUtility(argv)
                    utility.execute()
                    log.finished_successfully = True
                except Exception as e:
                    capture_exception(e)

                    log.finished_successfully = False
                    log.traceback = traceback.format_exc(limit=65535)

    finally:
        log.stdout = stdout.getvalue()
        log.stderr = stderr.getvalue()
        log.finished_on = timezone.now()
        log.save()
