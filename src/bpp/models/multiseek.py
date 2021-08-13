from django.db import models


class BppMultiseekVisibility(models.Model):
    name = models.CharField(max_length=50, db_index=True, unique=True)
    label = models.CharField(max_length=200)
    public = models.BooleanField(default=True, verbose_name="Widoczne dla wszystkich")

    authenticated = models.BooleanField(
        default=True, verbose_name="Widoczne dla zalogowanych"
    )
    staff = models.BooleanField(
        default=True, verbose_name='Widoczne dla osób "w zespole"'
    )

    sort_order = models.PositiveSmallIntegerField(default=0)
