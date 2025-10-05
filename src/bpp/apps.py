from django.apps import AppConfig


class BppConfig(AppConfig):
    name = "bpp"
    verbose_name = "BPP"

    def ready(self):
        from django.db.models.signals import post_migrate

        from bpp.system import odtworz_grupy

        post_migrate.connect(odtworz_grupy, sender=self)

        # Ensure BppUserAdmin takes precedence over microsoft_auth's UserAdmin
        self._register_bpp_user_admin()

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
