from django.db import models

# Ta klasa na obecną chwilę nie zawiera nic, ale używamy jej, aby oznaczyć
# odpowiednio pola, gdzie chodzi o rok:
YearField = models.IntegerField


class DOIField(models.CharField):
    def __init__(self, *args, **kw):
        if "help_text" not in kw:
            kw["help_text"] = "Digital Object Identifier (DOI)"

        if "max_length" not in kw:
            kw["max_length"] = 2048

        super().__init__(*args, **kw)
