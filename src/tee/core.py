import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout

import simplejson
from django.core.management import call_command as django_call_command

from tee.models import Log
from tee.utils import TeeIO

from django.utils import timezone


def call_command(command_name, *args, **kwargs):
    """This function calls django command specified as ``command_name``,
    saving it's stdout and stderr to an object ``tee.models.Log``, also
    outputting it on stdout/stderr.

    This way one can transparently save output to the database and also
    print it out on the console. This could be useful for cron scripts."""
    stdout = TeeIO(kwargs.get("stdout") if "stdout" in kwargs else sys.stdout)
    stderr = TeeIO(kwargs.get("stderr") if "stderr" in kwargs else sys.stdout)

    log = Log.objects.create(command_name=command_name, args=args, kwargs=kwargs)
    res = 127
    try:
        with redirect_stderr(stderr):
            with redirect_stdout(stdout):
                try:
                    res = django_call_command(
                        command_name, stdout=stdout, stderr=stderr, *args, **kwargs
                    )
                except Exception:
                    res = 1
                    log.traceback = traceback.format_exc(limit=65535)

    finally:
        log.stdout = stdout.getvalue()
        log.stderr = stderr.getvalue()
        log.finished_on = timezone.now()

        if res is None:
            log.exit_code = 0
        elif isinstance(res, int):
            log.exit_code = res
        else:
            log.exit_code = -1

            # if the return value is json-encodeable, save it to db:
            try:
                simplejson.dumps(res)
                log.exit_value = res
            except TypeError:
                log.exit_value = (
                    "Unable to encode results as JSON, thus unable to store it "
                    "in the database. Repr: %r" % res
                )
        log.save()
