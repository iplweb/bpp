from django.apps import AppConfig


class BppConfig(AppConfig):
    name = "bpp"
    verbose_name = "BPP"

    def ready(self):
        from django.apps import apps
        from django.db.models.signals import post_migrate, post_save

        # Only register post_migrate signal when dbtemplates is available
        # (auth_server uses minimal INSTALLED_APPS without dbtemplates)
        if apps.is_installed("dbtemplates"):
            from bpp.system import odtworz_grupy

            post_migrate.connect(odtworz_grupy, sender=self)

        # Odtwarzaj słowniki referencyjne po każdym ``migrate`` ORAZ po
        # transakcyjnym flushu testów (``TransactionTestCase._fixture_teardown``
        # emituje ``post_migrate``). Bez tego ``TRUNCATE`` zmiata słowniki
        # zaseedowane migracjami danych (0449, …) i kolejne testy na tym
        # samym workerze widzą pustą tabelę → flake. Wzorzec jak
        # ``odtworz_grupy``. Idempotentne, w produkcji no-op na zdrowej bazie.
        from bpp.seed_slowniki import seed_slowniki

        post_migrate.connect(seed_slowniki, sender=self)

        if apps.is_installed("siteblog"):
            from bpp.views.browse import invalidate_uczelnia_cache_on_article_change

            post_save.connect(
                invalidate_uczelnia_cache_on_article_change,
                sender=apps.get_model("siteblog", "Article"),
                dispatch_uid="bpp.invalidate_uczelnia_cache_on_article_change",
            )

        self._podepnij_inwalidacje_cache_publicznego()

        # Ensure BppUserAdmin takes precedence over microsoft_auth's UserAdmin
        self._register_bpp_user_admin()

        # Initialize Rollbar with global hostname handler
        from bpp.rollbar_config import configure_rollbar

        configure_rollbar()

    #: Modele, których zapis zmienia treść publicznych stron przeglądania
    #: objętych ``bpp.views.cache_publiczny.cache_publiczny``.
    MODELE_INWALIDUJACE_CACHE_PUBLICZNY = (
        # Rekordy i ich bezpośredni właściciele.
        "Wydawnictwo_Ciagle",
        "Wydawnictwo_Zwarte",
        "Patent",
        "Praca_Doktorska",
        "Praca_Habilitacyjna",
        "Autor",
        "Jednostka",
        "Zrodlo",
        "Wydzial",
        "Uczelnia",
        # Słowniki — ich nazwy trafiają do opisów bibliograficznych, więc
        # zmiana nazwy zmienia treść publicznych stron. Bez nich obietnica
        # „zapis w adminie unieważnia natychmiast" byłaby dla tych modeli
        # nieprawdziwa (odświeżałby je dopiero TTL).
        "Charakter_Formalny",
        "Typ_KBN",
        "Jezyk",
        "Wydawca",
        "Konferencja",
        "Seria_Wydawnicza",
        "Status_Korekty",
        "Typ_Odpowiedzialnosci",
    )

    def _podepnij_inwalidacje_cache_publicznego(self):
        """Zapis w adminie ma NATYCHMIAST odświeżyć publiczne strony.

        Bez tego jedyną gwarancją świeżości byłby TTL. Inwalidujemy
        hurtowo (bump generacji), bo mapowanie „ten rekord → te URL-e"
        jest w BPP nietrywialne, a nadmiarowa inwalidacja jest bezpieczna
        (najwyżej kosztuje jedno przeliczenie strony).
        """
        from django.apps import apps
        from django.db.models.signals import post_delete, post_save

        from bpp.views.cache_publiczny import uniewaznij_cache_publiczny

        for nazwa in self.MODELE_INWALIDUJACE_CACHE_PUBLICZNY:
            model = apps.get_model("bpp", nazwa)
            for etykieta, sygnal in (("save", post_save), ("delete", post_delete)):
                sygnal.connect(
                    uniewaznij_cache_publiczny,
                    sender=model,
                    dispatch_uid=f"bpp.cache_publiczny.{nazwa}.{etykieta}",
                )

    def _register_bpp_user_admin(self):
        """Re-register BppUserAdmin to override any previous registrations."""

        # microsoft_auth at the currently used version modifies USER_MODEL admin form.
        # bpp.admin also wants to modify it. With the current Django module resolution,
        # the bpp.admin is imported, then bpp.apps.ready is called, then microsoft_auth.admin
        # is imported... this is something we don't want.
        #
        # So, we import the microsoft_auth.admin here so it gets executed and then we re-register
        # the module.

        from django.apps import apps

        if not apps.is_installed("microsoft_auth"):
            return

        try:
            from microsoft_auth import admin  # noqa
        except ImportError:
            # If there is no microsoft_auth module, this whole function is not actually needed.
            return

        from django.contrib import admin  # noqa

        from bpp.admin import BppUserAdmin
        from bpp.models import BppUser

        # Unregister any existing admin for BppUser
        if BppUser in admin.site._registry:
            admin.site.unregister(BppUser)

        # Register our BppUserAdmin
        admin.site.register(BppUser, BppUserAdmin)
