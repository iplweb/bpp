from tee.models import Log
from tee.utils import last_n_lines

from django.contrib import admin

from django.utils.safestring import mark_safe


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = [
        "cmd_name",
        "started_on",
        "finished_on",
        "finished_successfully",
        "last_5_lines",
    ]

    list_per_page = 10

    readonly_fields = [
        "started_on",
        "finished_on",
        "finished_successfully",
        "command_name",
        "args",
        "stdout",
        "stderr",
        "traceback",
    ]

    date_hierarchy = "started_on"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def cmd_name(self, obj):
        args = ""
        if obj.args:
            args = f" {' '.join(obj.args)}"
        return f"{obj.command_name}" + args

    def finished_successfully(self, obj: Log):
        if obj.exit_code == 0:
            return True
        return False

    def last_5_lines(self, obj):
        s = obj.stderr

        if obj.traceback:
            s = obj.traceback

        if not s:
            s = obj.stdout

        r = last_n_lines(s, nlines=5)
        if r is None:
            return
        return mark_safe(f"<pre>{r}</pre>")

    last_5_lines.short_description = "Results"
