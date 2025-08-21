from django.apps import AppConfig


class BppConfig(AppConfig):
    name = "bpp"
    verbose_name = "Biblioteka Publikacji Pracowników"

    def ready(self):
        from django.db.models.signals import post_migrate

        from bpp.system import odtworz_grupy, ustaw_robots_txt

        post_migrate.connect(ustaw_robots_txt, sender=self)
        post_migrate.connect(odtworz_grupy, sender=self)

        # Ensure BppUserAdmin takes precedence over microsoft_auth's UserAdmin
        self._register_bpp_user_admin()

    def _register_bpp_user_admin(self):
        """Re-register BppUserAdmin to override any previous registrations."""

        # Ten zabieg jest potrzebny, gdyż microsoft_auth modyfikuje formularz admina dla
        # użytkownika, stąd nasz formularz by nie przeszedł. Problem polega na tym, że
        # gdy zostawimy formularz microsoft_auth to zginie nam pole "Przedstawiaj w PBN jako"

        from django.contrib import admin

        from bpp.admin import BppUserAdmin
        from bpp.models import BppUser

        # Unregister any existing admin for BppUser
        if BppUser in admin.site._registry:
            admin.site.unregister(BppUser)

        # Register our BppUserAdmin
        admin.site.register(BppUser, BppUserAdmin)
