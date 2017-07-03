# -*- encoding: utf-8 -*-

from django.test import TestCase
from bpp.management.commands.look_for_unused_fields import Command as LookForUnusedFields

class TestManagement(TestCase):
    def test_LookForUnusedFields(self):
        LookForUnusedFields().handle(silent=True)