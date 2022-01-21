from django.db import models
from django.template.loader import get_template

from django.contrib.contenttypes.models import ContentType

from django.utils.functional import cached_property


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

    def get_models_for_template(self, template):
        """Zwraca listę wszystkich modeli wykorzystujących dany szablon."""

        res = list(
            self.filter(template=template).values_list("model", flat=True).distinct()
        )
        if None in res:
            return self.all_templated_models
        return [ContentType.objects.get_for_id(id).model_class() for id in res]


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

    def get_models_for_this_szablon(self):
        return SzablonDlaOpisuBibliograficznego.objects.get_models_for_template(
            self.template
        )
