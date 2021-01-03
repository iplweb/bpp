# -*- encoding: utf-8 -*-

from django.contrib.auth.models import Group
from django.contrib.contenttypes.models import ContentType

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from mock import Mock

from bpp.admin import Wydawnictwo_ZwarteAdmin
from bpp.admin.filters import CalkowitaLiczbaAutorowFilter, LiczbaZnakowFilter
from bpp.models import (
    Autor,
    Charakter_Formalny,
    Jednostka,
    Patent,
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Wydawnictwo_Zwarte,
    Zrodlo,
)
from bpp.models.wydawnictwo_ciagle import Wydawnictwo_Ciagle
from bpp.system import groups
from bpp.tests.tests_legacy.testutil import SuperuserTestCase, TestCase, UserTestCase
from bpp.tests.util import any_ciagle
from bpp.views.admin import WydawnictwoCiagleTozView


class TestLiczbaZnakowFilter(TestCase):
    def test_simpleIntegerFilters(self):
        for klass in [LiczbaZnakowFilter, CalkowitaLiczbaAutorowFilter]:
            flt = klass(Mock(), [], Wydawnictwo_Zwarte, Wydawnictwo_ZwarteAdmin)

            for elem in ["brak", "zero", "powyzej"]:
                flt.value = Mock(return_value=elem)
                queryset = Mock()
                flt.queryset(Mock(), queryset)
                self.assertEqual(queryset.filter.called, True)

            flt.value = Mock(return_value="__nie ma tego parametru")
            queryset = Mock()
            flt.queryset(Mock(), queryset)
            self.assertEqual(queryset.filter.called, False)


class TestNormalUserAdmin(UserTestCase):
    def test_root(self):
        self.user.is_staff = True
        self.user.is_superuser = False

        for grupa in groups:
            self.user.groups.add(Group.objects.get_by_natural_key(grupa))
        self.user.save()

        self.assertContains(
            self.client.get("/admin/"), "Administracja", status_code=200
        )


class TestAdmin(SuperuserTestCase):
    def test_root(self):
        self.assertContains(
            self.client.get("/admin/"), "Administracja", status_code=200
        )

    def test_custom_app_index(self):
        """Spowoduje wywołanie customappindex z django-admin-tools"""
        self.assertContains(
            self.client.get("/admin/bpp/"), "Użytkownicy", status_code=200
        )

    def test_wyszukiwanie(self):
        """Dla wielu różnych model spróbuj wyszukiwać w tabelce
        i zobacz, czy nie ma błędu."""
        for model in [
            Jednostka,
            Autor,
            Zrodlo,
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Praca_Doktorska,
            Praca_Habilitacyjna,
            Patent,
            Charakter_Formalny,
        ]:
            content_type = ContentType.objects.get_for_model(model)
            url = reverse(
                "admin:%s_%s_changelist" % (content_type.app_label, content_type.model)
            )
            res = self.client.get(url, data={"q": "wtf"})
            self.assertEqual(res.status_code, 200)


class TestAdminViews(TestCase):
    def test_wydawnictwociagletozview(self):
        c1 = any_ciagle()
        self.assertEqual(Wydawnictwo_Ciagle.objects.count(), 1)

        w = WydawnictwoCiagleTozView()
        url = w.get_redirect_url(c1.pk)

        # Czy jest poprawne ID w URLu?
        c2 = Wydawnictwo_Ciagle.objects.all().exclude(pk=c1.pk)
        self.assertIn(str(c2[0].pk), url)

        # Czy stworzył kopię?
        self.assertEqual(Wydawnictwo_Ciagle.objects.count(), 2)
