from django.db import models

from tee import const

from django.contrib.postgres.fields import JSONField


class Log(models.Model):
    started_on = models.DateTimeField(auto_now_add=True)
    finished_on = models.DateTimeField(blank=True, null=True)

    exit_code = models.SmallIntegerField(
        blank=True,
        null=True,
        help_text="""If value returned by
    django.core.management.call_command is None, this will be zero. If value returned by d.c.m.call_command
    is an int, this will be that int. If different, this is set to -1 and exit_value field is set. """,
    )

    exit_value = JSONField(
        blank=True,
        null=True,
        help_text="""JSON-encoded value, returned by
    django.core.management.call_command function, if different than None or an int. """,
    )

    command_name = models.TextField()
    args = JSONField(blank=True, null=True)
    kwargs = JSONField(blank=True, null=True)

    stdout = models.TextField(blank=True, null=True)
    stderr = models.TextField(blank=True, null=True)
    traceback = models.TextField(blank=True, null=True)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        if self.kwargs:
            for key in const.IGNORED_KWARGS:
                if key in self.kwargs:
                    del self.kwargs[key]
        return super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self):
        return f'Results of command "{self.command_name}" ran on {self.started_on}'
