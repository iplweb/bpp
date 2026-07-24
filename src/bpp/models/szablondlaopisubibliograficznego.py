from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.utils.functional import cached_property


class SzablonDlaOpisuBibliograficznegoManager(models.Manager):
    def get_for_model(self, model):
        model = ContentType.objects.get_for_model(model)
        try:
            return self.get(model=model).nazwa_szablonu
        except SzablonDlaOpisuBibliograficznego.DoesNotExist:
            try:
                return self.get(model=None).nazwa_szablonu
            except SzablonDlaOpisuBibliograficznego.DoesNotExist:
                return

    @cached_property
    def all_templated_models(self):
        from bpp.models.patent import Patent
        from bpp.models.praca_doktorska import Praca_Doktorska
        from bpp.models.praca_habilitacyjna import Praca_Habilitacyjna
        from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
        from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte

        return [
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Patent,
        ]

    def get_models_for_szablon(self, nazwa_szablonu):
        """Lista modeli mapowanych na dany szablon (po nazwie)."""
        res = list(
            self.filter(nazwa_szablonu=nazwa_szablonu)
            .values_list("model", flat=True)
            .distinct()
        )
        if None in res:
            return self.all_templated_models
        return [ContentType.objects.get_for_id(id).model_class() for id in res]


class SzablonDlaOpisuBibliograficznego(models.Model):
    model = models.OneToOneField(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        limit_choices_to=models.Q(
            app_label="bpp",
            model__in=[
                "wydawnictwo_ciagle",
                "wydawnictwo_zwarte",
                "praca_doktorska",
                "praca_habilitacyjna",
                "patent",
            ],
        ),
        null=True,
        blank=True,
    )

    nazwa_szablonu = models.CharField(
        max_length=255,
        default="opis_bibliograficzny.html",
        help_text=(
            "Nazwa szablonu Django ładowanego z dysku, np. opis_bibliograficzny.html"
        ),
    )

    objects = SzablonDlaOpisuBibliograficznegoManager()

    class Meta:
        verbose_name = "powiązanie szablonu dla opisu bibliograficznego"
        verbose_name_plural = "powiązania szablonów dla opisu bibliograficznego"

    def __str__(self):
        if self.model_id is not None:
            return f"Powiązanie szablonu {self.nazwa_szablonu} z modelem {self.model}"
        return f"Powiązanie szablonu {self.nazwa_szablonu} z każdym modelem"

    def clean(self):
        try:
            get_template(self.nazwa_szablonu)
        except TemplateDoesNotExist as e:
            raise ValidationError(
                {
                    "nazwa_szablonu": (
                        f"Szablon '{self.nazwa_szablonu}' nie istnieje "
                        f"(ani na dysku, ani w dbtemplates)."
                    )
                }
            ) from e

    def render(self, praca):
        template = get_template(self.nazwa_szablonu)

        return (
            template.render(
                dict(praca=praca, autorzy=praca.autorzy_set.all().select_related())
            )
            .replace("\r\n", "")
            .replace("\n", "")
            .replace(".</b>[", ".</b> [")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace("  ", " ")
            .replace(" , ", ", ")
            .replace(" . ", ". ")
            .replace(". . ", ". ")
            .replace(". , ", ". ")
            .replace("., ", ". ")
            .replace(" .", ".")
        )

    def get_models_for_this_szablon(self):
        return SzablonDlaOpisuBibliograficznego.objects.get_models_for_szablon(
            self.nazwa_szablonu
        )
