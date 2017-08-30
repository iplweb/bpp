# -*- encoding: utf-8 -*-

from django.db import models


class OpcjaWyswietlaniaField(models.CharField):
    POKAZUJ_ZAWSZE = 'always'
    POKAZUJ_ZALOGOWANYM = 'logged-in'
    POKAZUJ_NIGDY = 'never'

    POKAZUJ_CHOICES = [
        (POKAZUJ_ZAWSZE, 'zawsze'),
        (POKAZUJ_ZALOGOWANYM, 'tylko dla zalogowanych'),
        (POKAZUJ_NIGDY, 'nigdy')
    ]

    def __init__(self, verbose_name,
                 default=POKAZUJ_ZAWSZE,
                 max_length=50,
                 choices=POKAZUJ_CHOICES,
                 *args, **kw):
        super(OpcjaWyswietlaniaField, self).__init__(
            verbose_name=verbose_name,
            max_length=max_length,
            choices=choices,
            default=default,
            *args, **kw
        )
