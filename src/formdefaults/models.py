from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.db import models

from formdefaults.util import full_name


class FormRepresentationManager(models.Manager):
    def get_or_create_for_instance(self, form_instance):
        """
        Ta klasa otrzymuje jako parametr instancję formularza Django wraz
        z czytelną nazwą i ewentualnym kodem formularza (jeżeli go nie ma,
        zostanie wygenerowany automatycznie na podstawie nazwy).

        Następnie mapuje pola w tym formularzu po nazwie (w kontekście bazy
        danych) i szuka ich ewentualnych ustawień domyślnych (zakodowanych
        w formacie JSON)
        """
        fn = full_name(form_instance)
        res, created = self.get_or_create(full_name=fn)
        return res


class FormRepresentation(models.Model):
    full_name = models.TextField("Kod formularza", primary_key=True)
    label = models.TextField("Nazwa formularza")

    objects = FormRepresentationManager()

    class Meta:
        unique_together = [("full_name", "label")]
        verbose_name = "Formularz"
        verbose_name_plural = "Formularze"


class FormFieldRepresentation(models.Model):
    """Default value in a form. """

    parent = models.ForeignKey(
        FormRepresentation, on_delete=models.CASCADE, related_name="fields_set"
    )

    name = models.TextField("Systemowa nazwa pola")
    label = models.TextField("Czytelna etykieta pola", null=True, blank=True)
    value = JSONField("Wartość", null=True, blank=True)

    # Ustawienie może dotyczyć wyłącznie konkretnego użytkownika lub
    # wszystkich użytkowników systemu
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True
    )

    class Meta:
        unique_together = [("parent", "name", "user")]
        verbose_name = "Pole formularza"
        verbose_name_plural = "Pola formularzy"
