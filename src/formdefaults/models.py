from django.conf import settings
from django.contrib.postgres.fields import JSONField
from django.core.exceptions import ValidationError
from django.db import models

from formdefaults.core import get_form_defaults
from formdefaults.util import full_name, get_python_class_by_name


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

    html_before = models.TextField("Kod HTML przed formularzem", null=True, blank=True)
    html_after = models.TextField("Kod HTML po formularzu", null=True, blank=True)

    objects = FormRepresentationManager()

    def __str__(self):
        return f"Formularz '{self.label}'"

    def get_form_class(self):
        """Zwraca klasę formularza zapisaną pod self.full_name lub None"""
        return get_python_class_by_name(self.full_name)

    class Meta:
        unique_together = [("full_name", "label")]
        verbose_name = "Lista wartości domyślnych formularza"
        verbose_name_plural = "Listy wartości domyślnych formularzy"


class FormFieldRepresentation(models.Model):
    """Default value in a form. """

    parent = models.ForeignKey(
        FormRepresentation,
        on_delete=models.CASCADE,
        related_name="fields_set",
        help_text="Formularz, do którego należy to pole",
    )

    name = models.TextField("Systemowa nazwa pola")
    label = models.TextField("Czytelna etykieta pola", null=True, blank=True)
    klass = models.TextField("Klasa pola")
    order = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "Pole formularza"
        verbose_name_plural = "Pola formularzy"
        unique_together = [
            ("parent", "name"),
        ]
        ordering = ("order",)

    def __str__(self):
        return self.label or self.name


class FormFieldDefaultValue(models.Model):
    parent = models.ForeignKey(
        FormRepresentation,
        on_delete=models.CASCADE,
        related_name="values_set",
        help_text="Formularz, do którego należy pole, dla którego to zdefiniowana jest"
        "ta wartość domyślna pola. ",
    )

    field = models.ForeignKey(
        FormFieldRepresentation,
        verbose_name="Pole formularza",
        on_delete=models.CASCADE,
        related_name="+",
        help_text="Pole formularza, dla którego zdefiniowana jest ta wartość domyślna. ",
    )
    value = JSONField("Wartość", null=True, blank=True)

    # Ustawienie może dotyczyć wyłącznie konkretnego użytkownika lub
    # wszystkich użytkowników systemu
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Użytkownik",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    def clean(self):
        # Rodzic musi istnieć po obydwu stronach, tzn po stronie FormFieldDefaultValue
        # oraz po stronie FormFieldRepresentation
        if self.parent_id is None or (
            self.field_id is not None and self.field.parent is None
        ):
            raise ValidationError(
                "Rodzic dla reprezentacji pola i rodzic dla wartości domyślnej "
                "powinien być określony w bazie danych. Skontaktuj się z administratorem "
                "systemu, jezeli dostajesz ten błąd. "
            )

        if self.parent_id != self.field.parent_id:
            raise ValidationError(
                "Rodzic wartości domyślnej i rodzic wybranego pola musi być identyczny"
            )

        # Tu potrzebujemy zaimplementować: zebranie wartości domyślnych dla w/wym formularza
        # dla self.user, następnie zainicjowanie formularza z tymi parametrami i ewentualną
        # próbę wyrenderowania go. W sytuacji, gdy zostanie podany poprawny JSON ale niepoprawna
        # wartość dla danego pola (np wartość dla pola ID jako liczba zmiennoprzecinkowa a nie
        # całkowita), użytkownik powinien otrzymać adekwatny błąd"""

        try:
            klass = self.parent.get_form_class()
        except Exception as e:
            raise ValidationError(
                f"Nie udało się odnaleźć klasy formularza w kodzie dla '{self.parent.full_name}'. "
                f"Weryfikacja wartości domyślnych formularza nie jest możliwa, a co za tym idzie, "
                f"zapis zmian również. Skontaktuj się z administratorem systemu. "
            )

        initial = get_form_defaults(klass(), user=self.user, update_db_repr=False)
        initial[self.field.name] = self.value

        instance = klass(initial=initial)
        try:
            form_field = instance.fields[self.field.name]
            form_field.required = False

            form_field.to_python(self.value)
            form_field.validate(self.value)
            instance.as_p()
        except Exception as e:
            raise ValidationError(
                "Nie udało się wyrenderować formularza z wpisanymi przykładowymi informacjami. "
                f"Komunikat błędu: {str(e)}. Proszę, skoryguj daną wartośc i spróbuj ponownie, "
                "ewentualnie skontaktuj się z administratorem. "
            )

    class Meta:
        verbose_name = "Wartość domyslna dla pola formularza"
        verbose_name_plural = "Wartości domyślne dla pól formularzy"
        ordering = ("user", "field__order")
