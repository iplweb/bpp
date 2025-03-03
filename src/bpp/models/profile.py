"""
Profile użytkowników serwisu BPP
"""

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.dispatch import receiver

from django.contrib.auth.models import AbstractUser, UserManager

from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.itercompat import is_iterable

from bpp.const import PUSTY_ADRES_EMAIL
from bpp.models import ModelZAdnotacjami


class BppUserManager(UserManager):
    model = "bpp.BppUser"


class BppUser(AbstractUser, ModelZAdnotacjami):
    active_charmap_tab = models.IntegerField(default=0)

    per_page = models.IntegerField(
        "Ilość wyświetlanych rekordów na stronie", default=20
    )

    multiseek_format = models.CharField(
        "Ostatnio wybrany format wyświetlania w Multiseeku",
        max_length=200,
        null=True,
        blank=True,
    )

    multiseek_order_1 = models.CharField(
        "Ostatnio wybrane pole sortowania w Multiseeku",
        max_length=200,
        null=True,
        blank=True,
    )

    pbn_token = models.CharField(max_length=128, null=True, blank=True)
    pbn_token_updated = models.DateTimeField(null=True, blank=True)

    przedstawiaj_w_pbn_jako = models.ForeignKey(
        "bpp.BppUser",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text="Jeżeli wybrany użytkownik nie ma konta w PBNie, może nadal wysyłać prace jako inny użytkiownik "
        "systemu BPP; wybierz konto z którego ma być wysyłane w tym polu. ",
    )

    def pbn_token_possibly_valid(self):
        if (
            self.pbn_token is None
            or not self.pbn_token
            or self.pbn_token_updated is None
        ):
            return False

        delta = timezone.now() - self.pbn_token_updated
        if delta > timedelta(hours=settings.PBN_TOKEN_HOURS_GRACE_TIME):
            return False

        return True

    class Meta:
        app_label = "bpp"
        verbose_name = "użytkownik"
        verbose_name_plural = "użytkownicy"

    objects = BppUserManager()

    @cached_property
    def cached_groups(self):
        return self.groups.all()

    def clean(self):
        if self.pk is not None:
            if self.przedstawiaj_w_pbn_jako_id == self.pk:
                from django.forms import ValidationError

                raise ValidationError(
                    {
                        "przedstawiaj_w_pbn_jako": "Nie ma potrzeby ustawiać tego pola jako linku do samego siebie. "
                    }
                )

    def get_pbn_user(self):
        if self.przedstawiaj_w_pbn_jako_id:
            return self.przedstawiaj_w_pbn_jako
        return self


# Uzupełnianie pól użytkownika na bazie LDAP:

if getattr(settings, "AUTH_LDAP_SERVER_URI", None):
    from django_auth_ldap.backend import populate_user

    @receiver(populate_user)
    def populate_bppuser(user, ldap_user, **kwargs):
        # Populate the Django user from the LDAP directory.

        AUTH_LDAP_USER_ATTR_MAP = {
            "first_name": ("givenName", "BrakImieniaWActiveDirectory"),
            "last_name": ("sn", "BrakNazwiskaWActiveDirectory"),
            "email": ("mail", PUSTY_ADRES_EMAIL),
        }

        for attr, value in AUTH_LDAP_USER_ATTR_MAP.items():
            ldap_attr, default = value
            ldap_value = ldap_user.attrs.get(ldap_attr, value)

            if is_iterable(ldap_value):
                ldap_value = " ".join([str(x) for x in ldap_value])
            setattr(user, attr, ldap_value)

        user.is_active = True

        # Zresetuj uprawnienia superużytkownika i 'w zespole' dla użytkowników
        # autoryzujących się po LDAP:
        user.is_superuser = False
        user.is_staff = False
