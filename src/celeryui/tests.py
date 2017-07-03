"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from datetime import datetime
from django.contrib.auth import get_user_model

from django.test import TestCase
from celeryui.interfaces import IWebTask
from celeryui.models import Report, Status
from celeryui.registry import ReportAdapter, registerAdapter

User = get_user_model()


class SomeAdapter(ReportAdapter):
    def get_readable_title(self):
        return self.original.function.lower().replace("_", " ")

registerAdapter('MAD_EXAMPLE', SomeAdapter)


class TestModels(TestCase):

    def setUp(self):
        u = User.objects.create(username='foo', password='bar')

        r = Report.objects.create(
            ordered_by=u, function='foo', arguments={},
            file=None, started_on=None, finished_on=None,
            progress=0.0)

        self.r = r
        self.u = u

    def test_raport_status(self):
        r = self.r
        self.assertEqual(r.status(), Status.WAITING)

        r.started_on= datetime.now()
        self.assertEqual(r.status(), Status.IN_PROGRESS)

        r.finished_on = datetime.now()
        self.assertEqual(r.status(), Status.COMPLETED)

        r.error = True
        self.assertEqual(r.status(), Status.ERROR)

    def test_adaptation(self):
        r = self.r
        r.function = "MAD_EXAMPLE"
        self.assertEqual(
            IWebTask(self.r).get_readable_title(),
            'mad example')

    def test_context_okay(self):
        def fokay():
            return True

        r = self.r
        self.assertEqual(r.finished_on, None)
        r.run_in_context(fokay)
        self.assertNotEqual(r.finished_on, None)

    def test_context_error(self):
        def ferror():
            1/0

        r = self.r

        self.assertEqual(r.finished_on, None)
        r.run_in_context(ferror)
        self.assertNotEqual(r.finished_on, None)
        self.assertEqual(r.error, True)
        self.assertIn("ZeroDivisionError", r.traceback)

        self.assertRaises(
            ZeroDivisionError, r.run_in_context, ferror, raise_exceptions=True)