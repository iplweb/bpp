from django import template

register = template.Library()


@register.filter(name="can_use_query_editor")
def can_use_query_editor(user):
    """True, gdy user moze korzystac z edytora zapytan DjangoQL."""
    # Import w ciele filtra, NIE na top-levelu modułu: Django ładuje ZACHŁANNIE
    # wszystkie moduły templatetagów aplikacji z INSTALLED_APPS przy
    # inicjalizacji silnika szablonów. `bpp.views.zapytanie` ciągnie za sobą
    # `bpp.djangoql_schema`, który przy imporcie rozwiązuje allow-listę przez
    # `apps.get_model()` — m.in. `taggit.Tag`. Na authserverze (minimalne
    # INSTALLED_APPS) kończyło się to `LookupError: No installed app with
    # label 'taggit'` przy renderowaniu formularza logowania.
    from bpp.views.zapytanie import user_can_use_query_editor

    if user is None:
        return False
    return user_can_use_query_editor(user)
