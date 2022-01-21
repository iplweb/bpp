from django.db import models


class LiczbaNField(models.DecimalField):
    def __init__(self, *args, **kw):
        if "max_digits" not in kw:
            kw["max_digits"] = 9

        if "decimal_places" not in kw:
            kw["decimal_places"] = 4

        super(LiczbaNField, self).__init__(*args, **kw)
