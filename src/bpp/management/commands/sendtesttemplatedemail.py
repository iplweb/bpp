from django.conf import settings
from django.core.management.commands.sendtestemail import (
    Command as SendTestEmailCommand,
)
from templated_email import send_templated_mail


class Command(SendTestEmailCommand):
    def handle(self, *args, **kwargs):

        kw = dict(
            template_name="test_email",
            context={"message": "If you're reading this, it was successful."},
            from_email=None,
        )

        send_templated_mail(recipient_list=kwargs["email"], **kw)

        if kwargs["managers"]:
            if not settings.MANAGERS:
                return
            if not all(
                isinstance(a, (list, tuple)) and len(a) == 2 for a in settings.MANAGERS
            ):
                raise ValueError("The MANAGERS setting must be a list of 2-tuples.")

            send_templated_mail(recipient_list=settings.MANAGERS, **kw)

        if kwargs["admins"]:
            if not settings.ADMINS:
                return
            if not all(
                isinstance(a, (list, tuple)) and len(a) == 2 for a in settings.ADMINS
            ):
                raise ValueError("The ADMINS setting must be a list of 2-tuples.")

            send_templated_mail(recipient_list=settings.ADMINS, **kw)
