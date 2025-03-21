from django.db import models

from django.contrib.postgres.fields import ArrayField


class TupleField(ArrayField):
    def from_db_value(self, value, expression, connection):
        return tuple(value)


class OpcjaWyswietlaniaField(models.CharField):
    POKAZUJ_ZAWSZE = "always"
    POKAZUJ_ZALOGOWANYM = "logged-in"
    POKAZUJ_NIGDY = "never"
    POKAZUJ_GDY_W_ZESPOLE = "staff"

    POKAZUJ_CHOICES = [
        (POKAZUJ_ZAWSZE, "zawsze"),
        (POKAZUJ_ZALOGOWANYM, "tylko dla zalogowanych"),
        (POKAZUJ_GDY_W_ZESPOLE, "tylko dla zespołu"),
        (POKAZUJ_NIGDY, "nigdy"),
    ]

    def __init__(
        self,
        verbose_name,
        default=POKAZUJ_ZAWSZE,
        max_length=50,
        choices=POKAZUJ_CHOICES,
        *args,
        **kw
    ):
        super().__init__(
            verbose_name=verbose_name,
            max_length=max_length,
            choices=choices,
            default=default,
            *args,
            **kw
        )
