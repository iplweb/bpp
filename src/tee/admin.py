from tee.models import Log
from tee.utils import last_n_lines

from django.contrib import admin

from django.utils.safestring import mark_safe


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = [
        "command_name",
        "started_on",
        "finished_on",
        "finished_successfully",
        "last_5_lines",
    ]

    readonly_fields = [
        "started_on",
        "finished_on",
        "exit_code",
        "exit_value",
        "command_name",
        "args",
        "kwargs",
        "stdout",
        "stderr",
    ]

    def finished_successfully(self, obj: Log):
        if obj.exit_code == 0:
            return True
        return False

    def last_5_lines(self, obj):
        s = obj.stderr

        if obj.traceback:
            s = obj.traceback
        else:
            if obj.exit_code == 0:
                s = obj.stdout

        if not s:
            s = obj.exit_value

        r = last_n_lines(s, nlines=5)
        if r is None:
            return
        return mark_safe(f"<pre>{r}</pre>")

    last_5_lines.short_description = "Results"
