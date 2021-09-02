import json

from django.utils.safestring import mark_safe


def format_json(obj, fld_name):
    result = ""
    if obj:
        result = json.dumps(getattr(obj, fld_name), indent=4, sort_keys=True)
        result_str = f"<pre>{result}</pre>"
        result = mark_safe(result_str)
    return result
