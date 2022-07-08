from django.db import models
from django.db.models import JSONField


class Log(models.Model):
    started_on = models.DateTimeField(auto_now_add=True)
    finished_on = models.DateTimeField(blank=True, null=True)
    finished_successfully = models.BooleanField(null=True, blank=True, default=None)

    command_name = models.TextField()
    args = JSONField(blank=True, null=True)

    stdout = models.TextField(blank=True, null=True)
    stderr = models.TextField(blank=True, null=True)
    traceback = models.TextField(blank=True, null=True)

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        return super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    def __str__(self):
        return f'Results of command "{self.command_name}" ran on {self.started_on}'
