import re
import pytest
from django.db import connection

TABELE = ("bpp_wydawnictwo_ciagle_autor", "bpp_wydawnictwo_zwarte_autor", "bpp_patent_autor")


def _czyta(t):
    return any(re.search(rf"\b{x}\b(?!zy)", t) for x in TABELE)


@pytest.mark.django_db
def test_audyt():
    with connection.cursor() as cur:
        cur.execute("SELECT viewname, definition FROM pg_views WHERE schemaname='public'")
        widoki = cur.fetchall()
    brudne = [(n, "deleted_at" in d) for n, d in widoki if _czyta(d)]
    bez = [n for n, f in brudne if not f]
    linie = [f"WIDOKOW OGOLEM: {len(widoki)}", f"CZYTA SUROWA *_autor: {len(brudne)}", f"BEZ FILTRA: {len(bez)}"]
    linie += [f"  BRAK: {n}" for n in sorted(bez)]
    linie += [f"  ok:   {n}" for n, f in sorted(brudne) if f]
    open("/tmp/audyt.txt", "w").write("\n".join(linie))
    assert True
