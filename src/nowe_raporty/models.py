from django.contrib.auth.models import Group
from django.db import models


class DefinicjaRaportu(models.Model):
    """Konfigurowalna pozycja raportu (zastępuje 4 zahardkodowane warianty).

    Wskazuje na definicję ``flexible_reports.Report`` (template/schemat) i niesie
    uprawnienia: poziom dostępu + wymagane grupy + listę uczelni, na których
    raport ma się pokazywać.
    """

    POZIOM_UCZELNIA = "uczelnia"
    POZIOM_WYDZIAL = "wydzial"
    POZIOM_JEDNOSTKA = "jednostka"
    POZIOM_AUTOR = "autor"
    POZIOM_CHOICES = [
        (POZIOM_UCZELNIA, "Uczelnia"),
        (POZIOM_WYDZIAL, "Wydział"),
        (POZIOM_JEDNOSTKA, "Jednostka"),
        (POZIOM_AUTOR, "Autor"),
    ]

    DOSTEP_WSZYSCY = "wszyscy"
    DOSTEP_ZALOGOWANI = "zalogowani"
    DOSTEP_STAFF = "staff"
    DOSTEP_SUPERUSER = "superuser"
    DOSTEP_CHOICES = [
        (DOSTEP_WSZYSCY, "Wszyscy (także niezalogowani)"),
        (DOSTEP_ZALOGOWANI, "Zalogowani"),
        (DOSTEP_STAFF, "Redagujący (is_staff)"),
        (DOSTEP_SUPERUSER, "Superużytkownicy"),
    ]

    nazwa = models.CharField("Nazwa", max_length=200)
    slug = models.SlugField("Slug", unique=True)
    poziom = models.CharField("Poziom", max_length=20, choices=POZIOM_CHOICES)
    report = models.ForeignKey(
        "flexible_reports.Report",
        verbose_name="Definicja flexible-reports",
        on_delete=models.PROTECT,
    )
    kolejnosc = models.PositiveIntegerField("Kolejność w menu", default=0)
    aktywny = models.BooleanField("Aktywny", default=True)

    poziom_dostepu = models.CharField(
        "Poziom dostępu",
        max_length=20,
        choices=DOSTEP_CHOICES,
        default=DOSTEP_ZALOGOWANI,
    )
    wymagane_grupy = models.ManyToManyField(
        Group,
        verbose_name="Wymagane grupy",
        blank=True,
        help_text="Widoczny gdy użytkownik należy do którejkolwiek z grup "
        "(puste = bez wymogu grupy).",
    )
    uczelnie = models.ManyToManyField(
        "bpp.Uczelnia",
        verbose_name="Pokazuj na stronach uczelni",
        blank=True,
        help_text="Puste = pokazuj na wszystkich uczelniach.",
    )

    IKONY = {
        POZIOM_UCZELNIA: "fi-foundation",
        POZIOM_WYDZIAL: "fi-results-demographics",
        POZIOM_JEDNOSTKA: "fi-map",
        POZIOM_AUTOR: "fi-torsos-all",
    }

    class Meta:
        verbose_name = "definicja raportu"
        verbose_name_plural = "definicje raportów"
        ordering = ["kolejnosc", "nazwa"]

    def __str__(self):
        return self.nazwa

    @property
    def ikona_menu(self):
        return self.IKONY.get(self.poziom, "fi-graph-trend")

    def _poziom_dostepu_ok(self, user):
        if self.poziom_dostepu == self.DOSTEP_WSZYSCY:
            return True
        if self.poziom_dostepu == self.DOSTEP_ZALOGOWANI:
            return user.is_authenticated
        if self.poziom_dostepu == self.DOSTEP_STAFF:
            return user.is_staff
        if self.poziom_dostepu == self.DOSTEP_SUPERUSER:
            return user.is_superuser
        return False

    def _grupy_ok(self, user):
        # .all() (nie .filter) - korzysta z prefetch_related w menu (bez N+1).
        grupy = list(self.wymagane_grupy.all())
        if not grupy:
            return True
        if not user.is_authenticated:
            return False
        user_grupa_ids = set(user.groups.values_list("pk", flat=True))
        return any(g.pk in user_grupa_ids for g in grupy)

    def _uczelnia_ok(self, request):
        uczelnie = list(self.uczelnie.all())
        if not uczelnie:
            return True
        from bpp.models import Uczelnia

        biezaca = Uczelnia.objects.get_for_request(request)
        return biezaca is not None and any(u.pk == biezaca.pk for u in uczelnie)

    def widoczny_dla(self, request):
        """Czy raport jest widoczny dla danego requestu (menu + dispatch).

        Kolejność: aktywny → filtr uczelni (dotyczy też superusera) →
        superuser przepuszczany → poziom dostępu AND wymagane grupy.
        """
        if not self.aktywny:
            return False
        if not self._uczelnia_ok(request):
            return False
        user = request.user
        if user.is_superuser:
            return True
        return self._poziom_dostepu_ok(user) and self._grupy_ok(user)
