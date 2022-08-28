"""
Profile użytkowników serwisu BPP
"""

from django.db import models
from django.dispatch import receiver
from django_auth_ldap.backend import populate_user

from django.contrib.auth.models import AbstractUser, UserManager

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

    class Meta:
        app_label = "bpp"
        verbose_name = "użytkownik"
        verbose_name_plural = "użytkownicy"

    objects = BppUserManager()

    @cached_property
    def cached_groups(self):
        return self.groups.all()


# Uzupełnianie pól użytkownika na bazie LDAP:


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
