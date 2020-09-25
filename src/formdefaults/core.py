import json

from django.db.models import Q

from formdefaults.models import FormRepresentation
from formdefaults.util import full_name


def update_form_db_repr(form_instance, form_repr, user=None):
    """
    Aktualizuje reprezentację formularza w bazie danych:

    1) usuwa wszystkie pola które są w bazie a których nie ma w formularzu
    2) tworzy pola które są w formularzu wraz z domyślnymi wartościami
    """

    form_field_names = form_instance.fields.keys()
    db_fields = form_repr.fields_set.filter(user=user)

    # Usuwanie pól, których nie ma w formularzu:
    db_fields.filter(~Q(name__in=form_field_names)).delete()

    # Pola, które są już w bazie danych:
    already_there = db_fields.filter(name__in=form_field_names).values_list(
        "name", flat=True
    )

    # Pola, które nalezy dopisać do bazy danych - tworzenie pól, które są w formularzu
    # z domyślnymi wartościami:
    need_to_be_created = [
        field_name for field_name in form_field_names if field_name not in already_there
    ]

    for field_name in need_to_be_created:
        field = form_instance.fields[field_name]

        if field.initial is not None:
            try:
                json.dumps(field.initial)
            except TypeError:
                continue

        form_repr.fields_set.create(
            user=user, name=field_name, label=field.label, value=field.initial
        )


def get_form_defaults(form_instance, label=None, user=None):
    fn = full_name(form_instance)
    form_repr, crt = FormRepresentation.objects.get_or_create(full_name=fn)

    if label is not None:
        if form_repr.label != label:
            form_repr.label = label
            form_repr.save()

    # Automatyczne tworzenie reprezentacji bazodanowej formularza w tej
    # funkcji NIE przewiduje tworzenia oddzielnych ustaleń dla danego użytkownika
    update_form_db_repr(form_instance, form_repr, user=None)

    # Weź listę domyślnych wartości (czyli takich gdzie user=None)
    values = dict(
        [
            (qs["name"], qs["value"])
            for qs in form_repr.fields_set.filter(user=None).values()
        ]
    )

    # Weź listę wartości dla danego użytkownika
    if user is not None:
        user_values = dict(
            [
                (qs["name"], qs["value"])
                for qs in form_repr.fields_set.filter(user=user).values()
            ]
        )
        values.update(user_values)

    return values


def update_form_initial_values(form_instance, label=None, user=None):
    for field, value in get_form_defaults(
        form_instance, label=label, user=user
    ).items():
        form_instance.fields[field].initial = value
