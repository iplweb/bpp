import json
from pathlib import Path

from django.utils import timezone
from tqdm import tqdm


def get_fixture(name):
    p = Path(__file__).parent.parent / "fixtures" / f"{name}.json"
    with open(p, "rb") as f:
        ret = json.load(f)
    ret = [x["fields"] for x in ret if x["model"] == f"bpp.{name}"]
    return {x["skrot"].lower().strip(): x for x in ret}


#
# Progress bar
#


def pbar(
    query, count=None, label="Progres...", disable_progress_bar=False, callback=None
):
    if count is None:
        if hasattr(query, "count"):
            try:
                count = query.count()
            except TypeError:
                count = len(query)
        elif hasattr(query, "__len__"):
            count = len(query)

    if callback:
        # Callback provided but progress bar disabled - only use callback
        def callback_only_wrapper():
            for i, item in enumerate(query):
                callback.update(i + 1, count, label)
                yield item
            callback.clear()

        return callback_only_wrapper()

    return tqdm(
        query, total=count, desc=label, unit="items", disable=disable_progress_bar
    )


def year_last_month():
    now = timezone.now().date()
    if now.month >= 2:
        return now.year
    return now.year - 1


def crispy_form_html(self, key):
    from crispy_forms_foundation.layout import HTML, Column, Row
    from django.utils.functional import lazy

    def _():
        return self.initial.get(key, None) or ""

    return Row(Column(HTML(lazy(_, str)())))


def formdefaults_html_before(form):
    return crispy_form_html(form, "formdefaults_pre_html")


def formdefaults_html_after(form):
    return crispy_form_html(form, "formdefaults_post_html")


def dont_log_anonymous_crud_events(
    instance, object_json_repr, created, raw, using, update_fields, **kwargs
):
    """
    Za pomocą tej procedury  moduł django-easyaudit decyduje, czy zalogować dane
    zdarzenie, czy nie.

    Procedura ta sprawdza, czy w parametrach ``kwargs`` zawarty jest parametr
    ``request``, a jeżeli tak -- to czy ma on atrybut ``user`` czyli użytkownik. Jeśli tak,
    to zwracana jest wartość ``True``, aby dane zdarzenie mogło byc zalogowane.

    Jeżeli nie ma parametru ``user``, to takie zdarzenie logowane nie będzie.
    """
    if kwargs.get("request", None) and getattr(kwargs["request"], "user", None):
        return True
