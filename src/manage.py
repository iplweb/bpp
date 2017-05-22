#!/usr/bin/env python



import os
import sys

def entry_point():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)

if __name__ == "__main__":
    entry_point()
