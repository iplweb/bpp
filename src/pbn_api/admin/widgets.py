# Register your models here.
import json

from django.forms import widgets


class PrettyJSONWidget(widgets.Textarea):
    show_only_current = False

    def format_value(self, value):
        try:
            v = json.loads(value)
            if self.show_only_current:
                # Pokazuj tylko ostatnią wersję z PBNu
                v = [value for value in v if value.get("current", False) is True]
            value = json.dumps(v, indent=4, sort_keys=True)
            # these lines will try to adjust size of TextArea to fit to content
            row_lengths = [len(r) for r in value.split("\n")]
            self.attrs["rows"] = min(max(len(row_lengths) + 2, 10), 60)
            self.attrs["cols"] = min(max(max(row_lengths) + 2, 40), 120)
            return value
        except Exception:
            # logger.warning("Error while formatting JSON: {}".format(e))
            return super().format_value(value)


class PrettyJSONWidgetReadonly(PrettyJSONWidget):
    def __init__(self, attrs=None):
        default_attrs = {"readonly": True}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class PrettyJSONWidgetReadonlyOnlyCurrent(PrettyJSONWidgetReadonly):
    show_only_current = True
