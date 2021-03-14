import json

from django.db import transaction
from django.db.models import Q

from formdefaults.util import full_name


def update_form_db_repr(form_instance, form_repr, user=None):
    """
    Aktualizuje reprezentację formularza w bazie danych:

    1) usuwa wszystkie pola które są w bazie a których nie ma w formularzu
    2) tworzy pola które są w formularzu wraz z domyślnymi wartościami

    :type form_repr: formdefaults.models.FormRepresentation
    :type form_instance: django.forms.Form
    """

    form_fields = form_instance.fields
    form_fields_names = form_fields.keys()

    db_fields = form_repr.fields_set.all()

    # Usuwanie pól, których nie ma w formularzu:
    db_fields.filter(~Q(name__in=form_fields_names)).delete()

    db_fields_dict = {db_field.name: db_field for db_field in db_fields}

    # Przeleć listę pól, w razie potrzeby aktualizując typ lub etykietę
    for no, field_name in enumerate(form_fields_names):
        form_field = form_fields[field_name]

        db_field = db_fields_dict.get(field_name)

        created = False
        if db_field is None:
            created = True
            db_field = db_fields.create(
                parent=form_repr,
                name=field_name,
                klass=full_name(form_field),
                label=form_field.label or field_name.replace("_", " ").capitalize(),
                order=no,
            )

        updated = False
        if db_field.label != form_field.label:
            db_field.label = form_field.label
            updated = True

        if full_name(form_field) != db_field.klass:
            db_field.klass = full_name(form_field)
            updated = True

        if updated:
            db_field.save()

        # Sprawdź, czy wartość domyślna pola może być zapisana w bazie, tzn. czy
        # poddaje się 'testowi' zakodowania jej w formacie JSON. Na tym etapie jeżeli
        # wartość domyślna jest liczona np za pomocą funkcji, to system przejdzie
        # do kolejnego pola, bez tworzenia wartości domyślnej w bazie danych.
        form_field_value = form_field.initial
        try:
            json.dumps(form_field_value)
        except TypeError:
            if not created:
                db_field.delete()
            continue

        if created:
            # Reprezentację pola w bazie danych własnie utworzono, więc z tej okazji
            # zapisz do bazy danych wartość domyślną tego pola w momencie tworzenia go:
            form_repr.values_set.create(
                field=db_field, value=form_field_value, user=user
            )

        # Jeżeli jest podany użytkownik to sprawdź, czy dla niego jest wpis w bazie danych;
        # Jeżeli tego wpisu nie ma to utwórz go z wartością domyślną
        if user is not None:
            user_value, created = form_repr.values_set.get_or_create(
                field=db_field, user=user
            )

            if created:
                user_value.value = form_field_value
                user_value.save()


@transaction.atomic
def get_form_defaults(form_instance, label=None, user=None, update_db_repr=True):
    fn = full_name(form_instance)

    from formdefaults.models import FormRepresentation

    form_repr, crt = FormRepresentation.objects.get_or_create(full_name=fn)

    if update_db_repr:
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
            (qs["field__name"], qs["value"])
            for qs in form_repr.values_set.filter(user=None)
            .select_related("field__name")
            .values("field__name", "value")
        ]
    )

    # Weź listę wartości dla danego użytkownika
    if user is not None:
        user_values = dict(
            [
                (qs["field__name"], qs["value"])
                for qs in form_repr.values_set.filter(user=user)
                .select_related("field__name")
                .values("field__name", "value")
            ]
        )
        values.update(user_values)

    values.update(
        {
            "formdefaults_pre_html": form_repr.html_before,
            "formdefaults_post_html": form_repr.html_after,
        }
    )

    return values
