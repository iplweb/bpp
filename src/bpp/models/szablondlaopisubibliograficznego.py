from django.db import models
from django.template.loader import get_template

from django.contrib.contenttypes.models import ContentType


class SzablonDlaOpisuBibliograficznegoManager(models.Manager):
    def get_for_model(self, model):
        model = ContentType.objects.get_for_model(model)
        try:
            return self.get(model=model).template.name
        except SzablonDlaOpisuBibliograficznego.DoesNotExist:
            try:
                return self.get(model=None).template.name
            except SzablonDlaOpisuBibliograficznego.DoesNotExist:
                return


class SzablonDlaOpisuBibliograficznego(models.Model):
    objects = SzablonDlaOpisuBibliograficznegoManager()

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

    template = models.ForeignKey("dbtemplates.Template", on_delete=models.PROTECT)

    def __str__(self):
        if self.model_id is not None:
            return f"Powiązanie szablonu {self.template} z modelem {self.model}"
        return f"Powiązanie szablonu {self.template} z każdym modelem"

    class Meta:
        verbose_name = "powiązanie szablonu dla opisu bibliograficznego"
        verbose_name_plural = "powiązania szablonów dla opisu bibliograficznego"

    def render(self, praca):
        template = get_template(self.template.name)

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
