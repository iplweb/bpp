import pytest
from model_bakery import baker

from crossref_bpp.utils import json_format_with_wrap, perform_trigram_search
from import_common.core import normalized_db_title

from bpp.models import Wydawnictwo_Ciagle


def test_json_format_with_wrap():
    x = "x" * 90
    res = json_format_with_wrap(x)
    assert len(res.split("\n")[0]) == 70


@pytest.mark.django_db
def test_perform_trigram_search():
    wc = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Ta nazwa będzie miała polskie litery."
    )

    baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Ta nazwa będzie miała polskie litery i może coś jeszcze.",
    )
    baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Początek tytułu. Ta nazwa będzie miała polskie litery i może coś jeszcze.",
    )
    baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Kto to wie co to będzie.")
    baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Ta nazwa bedzie miala waskie znaki."
    )
    baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Ta nazwa bedzie miala proste litery."
    )

    ret = perform_trigram_search(
        Wydawnictwo_Ciagle.objects.all(),
        trigram_db_field=normalized_db_title,
        trigram_db_value="Ta nazwa bedzie miala polskie litery",
    )

    assert len(ret) == 2
    assert wc in ret
