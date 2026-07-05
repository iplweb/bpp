from django.template import Context, Template


def _render(src, **ctx):
    return Template("{% load polish_inflection %}" + src).render(Context(ctx))


def test_odmien_dopelniacz_mnoga():
    assert (
        _render('{% odmien nazwa "dopelniacz" liczba="mnoga" %}', nazwa="jednostka")
        == "jednostek"
    )


def test_odmien_biernik_pojedyncza():
    assert _render('{% odmien nazwa "biernik" %}', nazwa="jednostka") == "jednostkę"


def test_liczebnikowa_2_daje_mianownik_mnogi_poprawny():
    # regresja live-buga: dawniej "2 jednostek", teraz "2 jednostki"
    assert (
        _render("{% odmiana_liczebnikowa nazwa 2 %}", nazwa="jednostka") == "jednostki"
    )


def test_liczebnikowa_5():
    assert (
        _render("{% odmiana_liczebnikowa nazwa 5 %}", nazwa="jednostka") == "jednostek"
    )


def test_odmien_dziala_na_przemianowanym_lemacie():
    assert (
        _render('{% odmien nazwa "dopelniacz" liczba="mnoga" %}', nazwa="dział")
        == "działów"
    )
