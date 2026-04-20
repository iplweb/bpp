#!/usr/bin/env python3
"""Wypisz aktualną wersję BPP (z src/django_bpp/version.py).

Bez importu pakietu django_bpp, żeby działało też poza venv - używane
w Makefile w shell-substitution (systemowy python3, bez Django).
"""

import re
import sys
from pathlib import Path

VERSION_FILE = (
    Path(__file__).resolve().parent.parent / "src" / "django_bpp" / "version.py"
)
match = re.search(r'^VERSION\s*=\s*["\']([^"\']+)["\']', VERSION_FILE.read_text(), re.M)
if not match:
    sys.stderr.write(f"Nie znaleziono VERSION w {VERSION_FILE}\n")
    sys.exit(1)
output = match.group(1)
if "--json" in sys.argv:
    import json

    output = json.dumps({"VERSION": output})
sys.stdout.write(output)
