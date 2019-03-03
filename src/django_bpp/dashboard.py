"""
This file was generated with the customdashboard management command, it
contains the two classes for the main dashboard and app index dashboard.
You can customize these classes as you want.

To activate your index dashboard add the following to your settings.py::
    ADMIN_TOOLS_INDEX_DASHBOARD = 'django_bpp.dashboard.CustomIndexDashboard'

And to activate the app index dashboard::
    ADMIN_TOOLS_APP_INDEX_DASHBOARD = 'django_bpp.dashboard.CustomAppIndexDashboard'
"""

from django.utils.translation import ugettext_lazy as _

from admin_tools.dashboard import modules, Dashboard, AppIndexDashboard
from admin_tools.utils import get_admin_site_name

from bpp.models.const import GR_WPROWADZANIE_DANYCH


class CustomIndexDashboard(Dashboard):
    def init_with_context(self, context):
        site_name = get_admin_site_name(context)

        user = context['request'].user

        if user.groups.filter(name="dane systemowe"):
            self.children.append(
                modules.ModelList(
                    "Dane systemowe",
                    ['bpp.models.charakter_formalny',
                     'bpp.models.funkcja_autora',
                     'bpp.models.informacjaz',
                     'bpp.models.jezyk',
                     'bpp.models.rodzaj_autora',
                     'bpp.models.status_korekty',
                     'bpp.models.tytul',
                     'bpp.models.typ_kbn',
                     ]
                )
            )

        if user.groups.filter(name="struktura"):
            self.children.append(
            modules.ModelList(
                "Struktura",
                ['bpp.models.uczelnia',
                 'bpp.models.wydzial',
                 'bpp.models.jednostka',
                 ]
                )
            )

        if user.groups.filter(name=GR_WPROWADZANIE_DANYCH):
            self.children.append(
            modules.ModelList(
                "Wprowadzanie danych",
                ['bpp.models.autor',
                 'bpp.models.zrodlo',
                 'bpp.models.bibliografia'
                 ]
                )
            )

        if user.groups.filter(name="administracja"):
            self.children.append(
            modules.ModelList(
                "Administracja",
                ['auth.contrib.group',
                 'auth.contrib.user',
                 'multiseek.models.searchform'
                 ]
            )
        )
        # append an app list module for "Applications"

        if user.is_superuser:
            self.children.append(modules.AppList(
                _('Django'),
            ))

        # append a recent actions module
        self.children.append(modules.RecentActions(_('Recent Actions'), 5))


class CustomAppIndexDashboard(AppIndexDashboard):
    """
    Custom app index dashboard for django_bpp.
    """

    # we disable title because its redundant with the model list module
    title = ''

    def __init__(self, *args, **kwargs):
        AppIndexDashboard.__init__(self, *args, **kwargs)

        # append a model list module and a recent actions module
        self.children += [
            modules.ModelList(self.app_title, self.models),
            modules.RecentActions(
                _('Recent Actions'),
                include_list=self.get_app_content_types(),
                limit=5
            )
        ]

    def init_with_context(self, context):
        """
        Use this method if you need to access the request context.
        """
        return super(CustomAppIndexDashboard, self).init_with_context(context)
