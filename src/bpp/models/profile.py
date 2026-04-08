"""
Profile użytkowników serwisu BPP
"""

from collections.abc import Iterable
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.dispatch import receiver
from django.utils import timezone
from django.utils.functional import cached_property

from bpp.const import PUSTY_ADRES_EMAIL
from bpp.models import ModelZAdnotacjami


class BppUserManager(UserManager):
    model = "bpp.BppUser"


class BppUser(AbstractUser, ModelZAdnotacjami):
    active_charmap_tab = models.IntegerField(default=0)

    per_page = models.IntegerField(
        "Ilość wyświetlanych rekordów na stronie", default=20
    )

    multiseek_format = models.CharField(  # noqa: DJ001
        "Ostatnio wybrany format wyświetlania w Multiseeku",
        max_length=200,
        default="",
        blank=True,
    )

    multiseek_order_1 = models.CharField(  # noqa: DJ001
        "Ostatnio wybrane pole sortowania w Multiseeku",
        max_length=200,
        default="",
        blank=True,
    )

    pbn_token = models.CharField(max_length=128, default="", blank=True)
    pbn_token_updated = models.DateTimeField(null=True, blank=True)

    accessible_sites = models.ManyToManyField(
        "sites.Site",
        verbose_name="Dostępne strony (uczelnie)",
        blank=True,
        related_name="bpp_users",
        help_text="Uczelnie (strony), do których użytkownik ma dostęp. "
        "Superużytkownicy mają dostęp do wszystkich.",
    )

    przedstawiaj_w_pbn_jako = models.ForeignKey(
        "bpp.BppUser",
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        help_text="Jeżeli wybrany użytkownik nie ma konta w PBNie, może nadal wysyłać prace jako inny użytkiownik "
        "systemu BPP; wybierz konto z którego ma być wysyłane w tym polu. ",
    )

    autor = models.OneToOneField(
        "bpp.Autor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user",
        verbose_name="Powiązany autor",
        help_text="Autor powiązany z tym kontem użytkownika",
    )

    def __str__(self):
        ret = ""
        if self.last_name:
            ret += self.last_name + " "
        if self.first_name:
            ret += self.first_name + " "

        ret = ret.strip()

        if ret:
            return ret + f" ({self.username})"

        return self.username

    def sprobuj_dopasowac_autora(self):
        """Próbuje automatycznie dopasować autora do użytkownika.

        Kolejność dopasowania:
        1. Po adresie email (case-insensitive)
        2. Po imieniu i nazwisku (case-insensitive, dokładnie 1 wynik)

        Nic nie robi jeśli autor jest już ustawiony.
        """
        if self.autor_id is not None:
            return

        from bpp.models import Autor

        # Próba dopasowania po emailu
        if self.email and self.email != PUSTY_ADRES_EMAIL:
            wynik = (
                Autor.objects.filter(email__iexact=self.email)
                .exclude(email="")
                .exclude(email=PUSTY_ADRES_EMAIL)
            )
            if wynik.count() == 1:
                self.autor = wynik.first()
                self.save(update_fields=["autor"])
                return

        # Próba dopasowania po imieniu i nazwisku
        if self.first_name and self.last_name:
            wynik = Autor.objects.filter(
                imiona__iexact=self.first_name,
                nazwisko__iexact=self.last_name,
            )
            if wynik.count() == 1:
                self.autor = wynik.first()
                self.save(update_fields=["autor"])
                return

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

            if isinstance(ldap_value, Iterable):
                ldap_value = " ".join([str(x) for x in ldap_value])
            setattr(user, attr, ldap_value)

        user.is_active = True

        # Zresetuj uprawnienia superużytkownika i 'w zespole' dla użytkowników
        # autoryzujących się po LDAP:
        user.is_superuser = False
        user.is_staff = False
